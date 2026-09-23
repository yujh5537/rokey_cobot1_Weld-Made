"""scan_manager 상태 기계 (순수 Python, rclpy 없음).

기준: docs/contracts/ros-interfaces.md v0.1.1 의 3.4 · 4.1 · 4.3 · 5.1~5.3 · 7.1 · 7.4절.
전이도와 전이표는 이 패키지의 README.md 에 있다.

입력은 두 종류다.

- Command: 관제자 명령(Action goal · Service). 허용되지 않으면 예외 없이
  ``Outcome(accepted=False, reason=ReasonCode)`` 를 돌려준다. 그 값을 goal 거절 · 응답에 그대로 싣는다.
- Signal: 노드 내부의 진행 보고. 현재 phase 에서 허용되지 않으면 ``InvalidTransition`` 을 던진다.
  조용히 무시하지 않는다. 경합(예: 중지 직후에 도착한 EDGE)을 어떻게 다룰지는 호출 측이 정한다.

작업 중지 · 안전복귀 · 재시작은 서로 독립된 명령이다. STOP 은 STOPPING 으로만 가고,
STOPPING 에서는 STOP_CONFIRMED(→ STOPPED) 와 FAILED(→ ERROR) 만 받는다.
홈 복귀나 재시작으로 이어지는 전이는 표에 없다. **자동 재개는 없다** — ERROR 에서 다시 시작하려면
사람이 /safety/reset 을 하고 /scan/resume 을 보내야 한다(계약 9장, RESUMABLE_FAILURE_CODES).

restore() 는 입력이 아니다. 프로세스가 재시작된 뒤 기록의 휴지 상태를 되돌리는 입구이며 전이표를 거치지 않는다.
"""

from dataclasses import dataclass
from enum import Enum
import threading
from typing import Callable, Optional

from .contract_enums import Direction
from .contract_enums import Phase
from .contract_enums import Reason


class Command(Enum):
    """관제자 명령. 거절될 수 있다."""

    START = 'START'            # /scan/run goal
    STOP = 'STOP'              # /scan/stop
    HOME = 'HOME'              # /scan/home goal (안전복귀)
    RESUME = 'RESUME'          # /scan/resume goal
    SET_CONFIG = 'SET_CONFIG'  # /scan/set_config. phase 는 바뀌지 않는다


class Signal(Enum):
    """노드 내부의 진행 보고. 허용되지 않으면 InvalidTransition."""

    PREPARE_DONE = 'PREPARE_DONE'      # 시작 조건 점검 · tare 끝
    TOP_FOUND = 'TOP_FOUND'            # 윗면 접촉 확보
    EDGE_FOUND = 'EDGE_FOUND'          # 모서리 1개 확보
    GEOMETRY_DONE = 'GEOMETRY_DONE'    # 형상 계산 · 저장 · /scan/result 발행 끝
    HOMING_DONE = 'HOMING_DONE'        # 홈 복귀 끝 (마무리 · 안전복귀 공용)
    STOP_CONFIRMED = 'STOP_CONFIRMED'  # /robot/status 로 connected && !moving 확인
    RESUME_READY = 'RESUME_READY'      # 재시작 준비 끝. 중단됐던 단계로 돌아간다
    FAILED = 'FAILED'                  # 실패 · 안전 이상. reason_code 필수


# 새 작업 시작 · SetConfig · 안전복귀를 받는 phase (4.3절, 5.1절, 5.2절). 그 밖은 BUSY.
REST_PHASES = frozenset({Phase.IDLE, Phase.DONE, Phase.ERROR, Phase.STOPPED})
# STOP 이 STOPPING 으로 보내는 phase.
ACTIVE_PHASES = frozenset({
    Phase.PREPARING, Phase.TOP_SEARCH, Phase.EDGE_SEARCH,
    Phase.GEOMETRY, Phase.HOMING, Phase.RESUMING,
})
# 재시작으로 돌아갈 수 있는 phase. 마무리 HOMING 은 대상이 아니다(7.4절).
RESUMABLE_PHASES = frozenset({
    Phase.PREPARING, Phase.TOP_SEARCH, Phase.EDGE_SEARCH, Phase.GEOMETRY,
})
# ERROR 로 끝난 작업에서 /safety/reset 뒤 RESUME 을 허용하는 실패 사유 (계약 5.3 · 9장, v0.1.17).
#
# **허용 목록이다.** 여기 없는 사유는 전부 불허다 — 새 사유가 생겼을 때 저절로 허용되지 않는다.
# 셋의 공통점은 **측정값이 오염되지 않는다**는 것이다: 샘플이 끊겼거나(403) 로봇 상태가 끊겼거나(404)
# 정지 완료를 확인하지 못했을 뿐(407), 탐침이 무언가에 세게 닿지 않았다.
#
# OVER_FORCE(400) · DROP_LIMIT(205) 는 탐침 · 부재가 상했을 수 있다. 사람이 눈으로 보고 새 START 를
# 해야 한다. 알 수 없는 오류(ROBOT_ERROR 204)도 무엇에 닿았는지 모르므로 불허다.
RESUMABLE_FAILURE_CODES = frozenset({
    int(Reason.SAMPLE_STALE),        # 403
    int(Reason.ROBOT_STATUS_LOST),   # 404
    int(Reason.STOP_UNCONFIRMED),    # 407
})


def failure_is_resumable(failure) -> bool:
    """이 실패 뒤에 RESET + RESUME 을 받아도 되는가 (계약 9장 허용 목록).

    failure 가 없으면 False 다 — "실패가 없다"는 ERROR 재시작의 근거가 되지 않는다.
    """
    return failure is not None and int(failure.reason_code) in RESUMABLE_FAILURE_CODES


# 모서리 탐색 순서 (정의서 1.3). 계약에는 순서가 없어서 생성자 인자로 바꿀 수 있게 했다.
DEFAULT_DIRECTION_ORDER = (
    Direction.POS_X, Direction.NEG_X, Direction.POS_Y, Direction.NEG_Y,
)


def _same(phases):
    return {phase: frozenset({phase}) for phase in phases}


def _to(phases, target):
    return {phase: frozenset({target}) for phase in phases}


# 전이표: 이벤트 → {현재 phase: 갈 수 있는 phase 집합}.
# 표에 없는 (이벤트, phase) 는 허용되지 않는다. 집합의 원소가 둘 이상이면 상태 기계가 하나로 정한다.
# 대상이 현재 phase 와 같으면 "접수하되 phase 는 그대로"다.
COMMAND_TRANSITIONS = {
    Command.START: _to(REST_PHASES, Phase.PREPARING),
    Command.SET_CONFIG: _same(REST_PHASES),
    # 멈출 것이 없어도 접수한다(4.1절의 멱등). 이때 phase 는 그대로다.
    Command.STOP: {
        **_to(ACTIVE_PHASES, Phase.STOPPING),
        **_same(REST_PHASES | {Phase.STOPPING}),
    },
    Command.HOME: _to(REST_PHASES, Phase.HOMING),
    # ERROR 는 _check 가 실패 사유로 한 번 더 거른다(허용 목록). 여기서 막으면 거절 사유가
    # NO_RESUMABLE_SCAN 이 되어 "왜 안 되는지"가 사라진다
    Command.RESUME: _to({Phase.STOPPED, Phase.ERROR}, Phase.RESUMING),
}
SIGNAL_TRANSITIONS = {
    Signal.PREPARE_DONE: _to({Phase.PREPARING}, Phase.TOP_SEARCH),
    Signal.TOP_FOUND: _to({Phase.TOP_SEARCH}, Phase.EDGE_SEARCH),
    # n < 4 이면 다음 방향으로 EDGE_SEARCH 유지, 4/4 이면 GEOMETRY
    Signal.EDGE_FOUND: {
        Phase.EDGE_SEARCH: frozenset({Phase.EDGE_SEARCH, Phase.GEOMETRY}),
    },
    Signal.GEOMETRY_DONE: _to({Phase.GEOMETRY}, Phase.HOMING),
    # 마무리 복귀 → DONE, 안전복귀 → 출발했던 휴지 phase
    Signal.HOMING_DONE: {Phase.HOMING: frozenset({Phase.DONE}) | REST_PHASES},
    Signal.STOP_CONFIRMED: _to({Phase.STOPPING}, Phase.STOPPED),
    Signal.RESUME_READY: {Phase.RESUMING: RESUMABLE_PHASES},
    # 실패는 ERROR 로만 간다. 자동 홈 복귀는 없다(7.4절).
    Signal.FAILED: _to(ACTIVE_PHASES | {Phase.STOPPING}, Phase.ERROR),
}


class InvalidTransition(Exception):
    """현재 phase 에서 허용되지 않는 Signal."""

    def __init__(self, phase, signal):
        super().__init__(f'{signal.name} 은 phase={phase.name} 에서 허용되지 않는다')
        self.phase = phase
        self.signal = signal


def status_stale(topic: str, limit_name: str, age_s, timeout_s) -> Optional[str]:
    """상태 토픽이 끊겼는가. 끊겼거나 판정할 수 없으면 사람이 읽는 사유, 아니면 None (이슈 #120).

    구독자가 **이미 받은** 마지막 상태는 발행이 끊겨도 그대로 남는다. "한 번도 못 받음"(None)만 걸러서는
    "받다가 끊김"을 알 수 없고, 죽기 직전의 latched=false 가 영원히 "안전 정상"으로 읽힌다.

    나이를 **수신 시각이 아니라 메시지 stamp** 로 재는 이유는 따로 있다. /safety/status · /robot/status 는
    TRANSIENT_LOCAL 이라 **발행자 프로세스가 살아 있는 한** 늦게 붙은 구독자도 마지막 샘플을 받는다.
    발행이 멈춘 채 프로세스만 살아 있으면(행 · 타이머 정지) 늦게 뜬 노드는 옛 샘플을 "방금" 받는다 —
    수신 시각으로 보면 그것이 통과한다. (발행자 프로세스가 아예 죽었으면 늦은 구독자는 아무것도 받지 못하고,
    그것은 지금도 "미수신"으로 거절된다.)

    - 한계 시간(파라미터)이 없으면 판정할 수 없다 → 통과시키지 않는다.
    - 나이를 잴 수 없으면(ROS 시계가 0) 판정할 수 없다 → 통과시키지 않는다.
    - 나이가 음수(stamp 가 미래)면 발행이 살아 있다는 뜻이므로 통과다. 시계 뒤틀림으로 막지 않는다.
    - 정확히 한계 시간이면 통과다. 엄격히 넘어야 끊김이다.
    """
    if timeout_s is None:
        return f'{topic} 최신성을 판정할 수 없다({limit_name} 파라미터가 없다)'
    if age_s is None:
        return f'{topic} 최신성을 판정할 수 없다(ROS 시계가 0 이다)'
    if age_s > timeout_s:
        return f'{topic} 끊김(마지막 stamp 가 {age_s:.1f} s 전, 한계 {timeout_s:.1f} s)'
    return None


@dataclass(frozen=True)
class Conditions:
    """명령 시점의 보호 조건. None 은 "아직 수신하지 못함"이며 거절 사유가 된다.

    ``*_age_s`` 는 마지막으로 받은 상태 메시지의 stamp 가 지난 시간이다. 노드가 재고(잴 수 없으면 None),
    한계 시간과 비교해 "끊김"을 판정하는 것은 여기다(``status_stale``). 끊김을 False 나 0 으로 적지 않는다.
    """

    robot_connected: Optional[bool] = None  # /robot/status.connected
    safety_latched: Optional[bool] = None   # /safety/status.latched
    robot_status_age_s: Optional[float] = None    # /robot/status.stamp 의 나이(s). None = 잴 수 없음
    safety_status_age_s: Optional[float] = None   # /safety/status.stamp 의 나이(s)
    robot_status_timeout_s: Optional[float] = None   # 끊김으로 보는 한도. None = 파라미터 없음
    safety_status_timeout_s: Optional[float] = None


@dataclass(frozen=True)
class Snapshot:
    """ScanState.msg 에 그대로 옮길 값 (stamp 제외)."""

    scan_id: str
    phase: Phase
    direction: Direction
    progress: int
    progress_total: int
    motion_id: int


@dataclass(frozen=True)
class Failure:
    """가장 최근에 ERROR 로 간 사유.

    다음 START 가 접수될 때까지 남는다. ERROR 에서 안전복귀하다가 중지해 STOPPED 가 된 경우처럼
    phase 가 ERROR 가 아니어도 값이 있을 수 있으므로, 현재 상태는 phase 로 판단한다.
    """

    reason_code: int
    detail: str
    phase: Phase  # 실패가 난 phase


@dataclass(frozen=True)
class Outcome:
    """Command 처리 결과. accepted 는 접수 여부이지 완료가 아니다."""

    accepted: bool
    reason: Reason
    detail: str
    changed: bool  # phase 가 바뀌었는지
    state: Snapshot


class ScanStateMachine:
    """phase · 방향 · 진행도 n/4 를 들고 Command 와 Signal 로만 바뀐다.

    on_change 는 상태가 바뀔 때마다 락을 쥔 채로 불린다. 그래서 상태가 바뀐 순서와 발행 순서가 같다.
    대신 콜백 안에서 오래 걸리는 일 · 다른 노드의 응답 대기를 하면 다른 콜백의 request · notify 가 막힌다.
    발행처럼 바로 끝나는 일만 한다.
    """

    def __init__(
        self,
        direction_order=DEFAULT_DIRECTION_ORDER,
        on_change: Optional[Callable[[Snapshot], None]] = None,
    ):
        order = tuple(Direction(d) for d in direction_order)
        if sorted(order) != sorted(DEFAULT_DIRECTION_ORDER):
            raise ValueError('direction_order 는 ±X · ±Y 네 방향을 한 번씩 담아야 한다')
        self._order = order
        self._on_change = on_change
        self._lock = threading.RLock()

        self._phase = Phase.IDLE
        self._scan_id = ''
        self._progress = 0
        self._direction = Direction.NONE
        self._motion_id = 0
        self._failure: Optional[Failure] = None
        # 재시작으로 돌아갈 phase. 방향은 progress 에서 되찾으므로 따로 두지 않는다.
        self._resume_phase: Optional[Phase] = None
        self._moved_since_stop = False
        # HOMING 의 출발 phase. None 이면 스캔 마무리 복귀다.
        self._homing_origin: Optional[Phase] = None

    # ---- 조회 ----

    @property
    def phase(self) -> Phase:
        return self._phase

    @property
    def is_busy(self) -> bool:
        return self._phase not in REST_PHASES

    @property
    def failure(self) -> Optional[Failure]:
        return self._failure

    @property
    def progress_total(self) -> int:
        return len(self._order)

    def snapshot(self) -> Snapshot:
        with self._lock:
            return Snapshot(
                scan_id=self._scan_id,
                phase=self._phase,
                direction=self._direction,
                progress=self._progress,
                progress_total=self.progress_total,
                motion_id=self._motion_id,
            )

    # ---- Command ----

    def request(
        self,
        command: Command,
        *,
        conditions: Optional[Conditions] = None,
        scan_id: str = '',
    ) -> Outcome:
        """관제자 명령을 처리한다. 거절은 예외가 아니라 Outcome 으로 돌려준다.

        scan_id: START 는 새로 발급한 ID(필수), RESUME 은 goal 의 scan_id("" = 가장 최근 중단 작업).
        """
        command = Command(command)
        conditions = conditions or Conditions()
        with self._lock:
            if command is Command.START and not scan_id:
                raise ValueError('START 에는 scan_manager 가 발급한 scan_id 가 필요하다')
            reason, detail = self._check(command, conditions, scan_id)
            if reason is not Reason.OK:
                return Outcome(False, reason, detail, False, self.snapshot())

            before = self._phase
            if before in ACTIVE_PHASES or command is not Command.STOP:
                self._apply_command(command, scan_id)
            changed = self._phase is not before
            if changed:
                self._emit()
            return Outcome(True, Reason.OK, '', changed, self.snapshot())

    def check(
        self,
        command: Command,
        *,
        conditions: Optional[Conditions] = None,
        scan_id: str = '',
    ):
        """request() 가 내릴 판정 (Reason, detail) 만 돌려준다. 상태는 바뀌지 않는다.

        재시작은 접수 전에 기록을 읽어 계획을 세운다. 그 전에 상태 기계의 답을 먼저 알아야
        거절될 요청이 RESUMING 에 들어가지 않는다.
        """
        with self._lock:
            return self._check(Command(command), conditions or Conditions(), scan_id)

    def restore(
        self,
        *,
        scan_id: str,
        phase: Phase,
        progress: int,
        resume_phase: Optional[Phase] = None,
        moved_since_stop: bool = False,
        failure: Optional[Failure] = None,
    ) -> Snapshot:
        """프로세스가 재시작된 뒤, 기록에 남은 휴지 상태(STOPPED · ERROR)로 되돌린다.

        전이가 아니다. 이 프로세스가 죽지 않았다면 있었을 상태를 기록의 사실로 다시 만든다.
        그 뒤의 HOME · RESUME 은 같은 프로세스에서 중지한 경우와 같은 판정을 받는다.
        IDLE 에서만 부를 수 있다. 어떤 기록을 되돌릴지는 호출 측(resume.restoration_from)이 정한다.
        """
        phase = Phase(phase)
        with self._lock:
            if self._phase is not Phase.IDLE:
                raise ValueError(f'phase={self._phase.name} 에서는 되돌릴 수 없다(IDLE 에서만)')
            if phase not in (Phase.STOPPED, Phase.ERROR):
                raise ValueError(f'되돌릴 수 있는 phase 는 STOPPED · ERROR 다({phase.name})')
            if not scan_id:
                raise ValueError('되돌릴 작업의 scan_id 가 필요하다')
            if isinstance(progress, bool) or not 0 <= int(progress) <= self.progress_total:
                raise ValueError(f'progress 가 0~{self.progress_total} 이 아니다({progress!r})')
            if resume_phase is not None:
                resume_phase = Phase(resume_phase)
                allowed = (phase is Phase.STOPPED
                           or (phase is Phase.ERROR and failure_is_resumable(failure)))
                if not allowed or resume_phase not in RESUMABLE_PHASES:
                    raise ValueError(
                        f'재개 지점 {resume_phase.name} 은 phase={phase.name} 에 둘 수 없다')
            self._scan_id = scan_id
            self._progress = int(progress)
            self._failure = failure
            self._resume_phase = resume_phase
            self._moved_since_stop = bool(moved_since_stop)
            self._enter(phase)
            self._emit()
            return self.snapshot()

    def _check(self, command, conditions, scan_id):
        phase = self._phase
        if phase not in COMMAND_TRANSITIONS[command]:
            if command is Command.RESUME and phase in REST_PHASES:
                return Reason.NO_RESUMABLE_SCAN, f'phase={phase.name}'
            return Reason.BUSY, f'phase={phase.name}'

        if command is Command.RESUME:
            if phase is Phase.ERROR and not failure_is_resumable(self._failure):
                # 허용 목록 밖이다. 안전 점검 · 복귀 뒤 새 START 만 가능하다 (계약 9장, v0.1.17)
                code = None if self._failure is None else self._failure.reason_code
                return Reason.NOT_SUPPORTED, (
                    f'오류 사유 {code} 는 재시작 허용 목록에 없다. 안전 점검 뒤 새 START 로 시작한다'
                    if code else '오류로 끝났는데 사유 기록이 없다. 새 START 로 시작한다')
            if self._resume_phase is None:
                return Reason.NO_RESUMABLE_SCAN, '재개할 단계가 없다'
            if scan_id and scan_id != self._scan_id:
                return Reason.NO_RESUMABLE_SCAN, f'중단된 작업은 {self._scan_id}'
            if self._moved_since_stop:
                return Reason.NOT_SUPPORTED, '홈 안전복귀 뒤의 재접근 절차는 TBD'

        if command in (Command.START, Command.RESUME):
            if conditions.safety_latched is None:
                return Reason.SAFETY_LATCHED, '/safety/status 미수신'
            # 끊김을 래치보다 먼저 본다: 끊긴 뒤의 latched 는 죽은 감시자가 남긴 옛 값이라 믿을 수 없다.
            # 안전복귀(HOME)는 이 관문에 들어오지 않는다 — 감시자가 죽었다고 돌아오지 못하면 안 된다(규칙 3).
            stale = status_stale(
                '/safety/status', 'safety_status_timeout_s',
                conditions.safety_status_age_s, conditions.safety_status_timeout_s)
            if stale:
                return Reason.SAFETY_LATCHED, stale
            if conditions.safety_latched:
                return Reason.SAFETY_LATCHED, ''
        if command in (Command.START, Command.RESUME, Command.HOME):
            if conditions.robot_connected is None:
                return Reason.ROBOT_DISCONNECTED, '/robot/status 미수신'
            stale = status_stale(
                '/robot/status', 'robot_status_timeout_s',
                conditions.robot_status_age_s, conditions.robot_status_timeout_s)
            if stale:
                return Reason.ROBOT_DISCONNECTED, stale
            if not conditions.robot_connected:
                return Reason.ROBOT_DISCONNECTED, ''
        return Reason.OK, ''

    def _apply_command(self, command, scan_id):
        phase = self._phase
        if command is Command.START:
            self._scan_id = scan_id
            self._progress = 0
            self._failure = None
            self._resume_phase = None
            self._moved_since_stop = False
            self._enter(Phase.PREPARING)
        elif command is Command.STOP:
            if phase in RESUMABLE_PHASES:
                self._resume_phase = phase
                self._moved_since_stop = False
            elif phase is Phase.HOMING and self._homing_origin is None:
                # 측정은 끝났으므로 재시작 대상이 아니다(7.4절)
                self._resume_phase = None
            # RESUMING · 안전복귀 HOMING 중의 중지는 기존 재개 지점을 그대로 둔다
            self._enter(Phase.STOPPING)
        elif command is Command.HOME:
            self._homing_origin = phase
            self._moved_since_stop = True
            self._enter(Phase.HOMING)
        elif command is Command.RESUME:
            self._enter(Phase.RESUMING)
        # SET_CONFIG: 상태 변화 없음

    # ---- Signal ----

    def notify(
        self,
        signal: Signal,
        *,
        reason_code: Optional[int] = None,
        detail: str = '',
    ) -> Snapshot:
        """진행 보고를 반영한다. 허용되지 않으면 InvalidTransition."""
        signal = Signal(signal)
        with self._lock:
            phase = self._phase
            targets = SIGNAL_TRANSITIONS[signal].get(phase)
            if targets is None:
                raise InvalidTransition(phase, signal)

            if signal is Signal.FAILED:
                if not reason_code:
                    raise ValueError('FAILED 에는 0 이 아닌 reason_code 가 필요하다')
                failure = Failure(int(reason_code), detail, phase)
                self._failure = failure
                # 재개 지점은 **허용 목록에 있는 사유일 때만** 남긴다 (계약 9장, v0.1.17).
                # 그 밖에는 지운다 — 남겨 두면 허용 판정이 한 겹만 틀려도 오염된 기준으로 재개한다.
                # 실패한 그 단계가 곧 재개 지점이다(중지와 달리 FAILED 는 _resume_phase 를 세우는
                # 경로를 거치지 않는다). 마무리 HOMING 은 RESUMABLE_PHASES 에 없어 저절로 빠진다.
                self._resume_phase = (
                    phase if failure_is_resumable(failure) and phase in RESUMABLE_PHASES else None)
                target = Phase.ERROR
            elif signal is Signal.EDGE_FOUND:
                self._progress += 1
                done = self._progress >= self.progress_total
                target = Phase.GEOMETRY if done else Phase.EDGE_SEARCH
            elif signal is Signal.HOMING_DONE:
                origin = self._homing_origin
                target = Phase.DONE if origin is None else origin
            elif signal is Signal.RESUME_READY:
                target = self._resume_phase
            else:
                (target,) = targets

            assert target in targets, (signal, phase, target)
            self._enter(target)
            if signal is Signal.RESUME_READY:
                self._resume_phase = None
            self._emit()
            return self.snapshot()

    def set_motion_id(self, motion_id: int) -> None:
        """진행 중인 ExecuteMotion goal 의 motion_id. 없으면 0."""
        with self._lock:
            if motion_id and self._phase in REST_PHASES:
                raise ValueError(f'phase={self._phase.name} 에서는 모션을 시작할 수 없다')
            if motion_id != self._motion_id:
                self._motion_id = int(motion_id)
                self._emit()

    # ---- 내부 ----

    def _enter(self, target):
        if target is Phase.EDGE_SEARCH:
            # progress 가 곧 다음 방향의 순번이다. 재시작도 같은 식으로 중단 방향을 되찾는다.
            self._direction = self._order[self._progress]
        else:
            self._direction = Direction.NONE  # 모서리 탐색 중에만 유효(3.4절)
        if target is not Phase.HOMING:
            self._homing_origin = None
        if target in REST_PHASES:
            self._motion_id = 0
        self._phase = target

    def _emit(self):
        if self._on_change is not None:
            self._on_change(self.snapshot())
