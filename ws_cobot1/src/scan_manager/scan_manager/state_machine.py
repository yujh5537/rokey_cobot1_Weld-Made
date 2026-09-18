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
홈 복귀나 재시작으로 이어지는 전이는 표에 없다.
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
    Command.RESUME: _to({Phase.STOPPED}, Phase.RESUMING),
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


@dataclass(frozen=True)
class Conditions:
    """명령 시점의 보호 조건. None 은 "아직 수신하지 못함"이며 거절 사유가 된다."""

    robot_connected: Optional[bool] = None  # /robot/status.connected
    safety_latched: Optional[bool] = None   # /safety/status.latched


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
    """ERROR 로 간 사유."""

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
    """phase · 방향 · 진행도 n/4 를 들고 Command 와 Signal 로만 바뀐다."""

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

    def _check(self, command, conditions, scan_id):
        phase = self._phase
        if phase not in COMMAND_TRANSITIONS[command]:
            if command is Command.RESUME and phase in REST_PHASES:
                if phase is Phase.ERROR:
                    # 이상 상태별 재시작 허용 조건은 TBD(9장)
                    return Reason.NOT_SUPPORTED, '오류로 끝난 작업의 재시작 절차는 TBD'
                return Reason.NO_RESUMABLE_SCAN, f'phase={phase.name}'
            return Reason.BUSY, f'phase={phase.name}'

        if command is Command.RESUME:
            if self._resume_phase is None:
                return Reason.NO_RESUMABLE_SCAN, '재개할 단계가 없다'
            if scan_id and scan_id != self._scan_id:
                return Reason.NO_RESUMABLE_SCAN, f'중단된 작업은 {self._scan_id}'
            if self._moved_since_stop:
                return Reason.NOT_SUPPORTED, '홈 안전복귀 뒤의 재접근 절차는 TBD'

        if command in (Command.START, Command.RESUME):
            if conditions.safety_latched is None:
                return Reason.SAFETY_LATCHED, '/safety/status 미수신'
            if conditions.safety_latched:
                return Reason.SAFETY_LATCHED, ''
        if command in (Command.START, Command.RESUME, Command.HOME):
            if conditions.robot_connected is None:
                return Reason.ROBOT_DISCONNECTED, '/robot/status 미수신'
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
                self._failure = Failure(int(reason_code), detail, phase)
                self._resume_phase = None
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
