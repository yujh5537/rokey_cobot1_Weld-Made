"""weld_manager 상태 기계 (순수 Python, rclpy 없음). 기준: docs/phase2/weld-ros-interfaces.md 3.2 · 4.1 · 7장.

    IDLE → PREPARING → (APPROACH → WELDING → RETREAT) × 선 → HOMING → DONE
    실패 → ERROR,  STOP → STOPPING → STOPPED,  안전복귀(HOME) → HOMING → 출발했던 휴지 phase
    한 선의 ROBOT_ERROR(204) 실패(D33) → LINE_FAILED → RETREAT(복구 이동) → 다음 선 APPROACH. lines_done 은 늘지 않는다

입력은 두 종류다(scan_manager 의 상태 기계와 같은 구분).
- Command: 관제자 명령. 허용되지 않으면 예외 없이 Outcome(accepted=False, reason) 을 돌려준다.
- Signal: 시퀀스의 진행 보고. 허용되지 않으면 InvalidTransition 을 던진다. 조용히 무시하지 않는다.
  (예: STOP 이 접수돼 STOPPING 인데 시퀀스가 다음 선의 APPROACH 를 보고하면 예외 — 노드가 그것을 "중지"로 읽는다)

재시작(RESUME)은 없다(D7). 중지 · 안전복귀 · 시작은 서로를 부르지 않는다(CLAUDE.md 규칙 3).
on_change 는 락을 쥔 채 불린다. 그 안에서는 발행만 하고 파일을 쓰지 않는다(result_store/README.md 의 주의와 같다).
"""

from dataclasses import dataclass
from dataclasses import replace
from enum import Enum
import threading
from typing import Callable, Optional

from .contract_enums import LINE_COUNT
from .contract_enums import LINE_NONE
from .contract_enums import Reason
from .contract_enums import WeldPhase


class Command(Enum):
    START = 'START'   # /weld/run goal
    STOP = 'STOP'     # /weld/stop
    HOME = 'HOME'     # /weld/home goal (안전복귀)


class Signal(Enum):
    APPROACH = 'APPROACH'              # 선 line 의 접근 시작 (line 필수)
    WELD = 'WELD'                      # 그 선의 ExecutePath 시작
    RETREAT = 'RETREAT'                # 그 선의 후퇴 시작
    LINE_DONE = 'LINE_DONE'            # 그 선을 끝까지 지났다 (lines_done + 1)
    LINE_FAILED = 'LINE_FAILED'        # 그 선이 204 로 실패했고 복구 이동으로 넘어간다 (D33). phase 는 RETREAT
    HOMING = 'HOMING'                  # 마무리 홈 복귀 시작 (마지막 선 뒤)
    HOMING_DONE = 'HOMING_DONE'        # 홈 복귀 끝 (마무리 → DONE, 안전복귀 → 출발한 휴지 phase)
    STOP_CONFIRMED = 'STOP_CONFIRMED'  # /robot/status 로 connected && !moving 확인
    FAILED = 'FAILED'                  # 실패 · 안전 이상 → ERROR


REST_PHASES = frozenset({WeldPhase.IDLE, WeldPhase.DONE, WeldPhase.ERROR, WeldPhase.STOPPED})
ACTIVE_PHASES = frozenset({
    WeldPhase.PREPARING, WeldPhase.APPROACH, WeldPhase.WELDING, WeldPhase.RETREAT, WeldPhase.HOMING,
})
# 시퀀스 신호 → {현재 phase: 다음 phase}. HOMING_DONE 은 안전복귀일 때 출발 phase 로 가므로 따로 다룬다.
SIGNAL_TRANSITIONS = {
    Signal.APPROACH: {WeldPhase.PREPARING: WeldPhase.APPROACH, WeldPhase.RETREAT: WeldPhase.APPROACH},
    Signal.WELD: {WeldPhase.APPROACH: WeldPhase.WELDING},
    Signal.RETREAT: {WeldPhase.WELDING: WeldPhase.RETREAT},
    Signal.LINE_DONE: {WeldPhase.RETREAT: WeldPhase.RETREAT},
    Signal.LINE_FAILED: {WeldPhase.APPROACH: WeldPhase.RETREAT, WeldPhase.WELDING: WeldPhase.RETREAT,
                         WeldPhase.RETREAT: WeldPhase.RETREAT},
    Signal.HOMING: {WeldPhase.RETREAT: WeldPhase.HOMING},
    Signal.HOMING_DONE: {WeldPhase.HOMING: WeldPhase.DONE},
    Signal.STOP_CONFIRMED: {WeldPhase.STOPPING: WeldPhase.STOPPED},
    Signal.FAILED: {phase: WeldPhase.ERROR for phase in ACTIVE_PHASES | {WeldPhase.STOPPING}},
}


class InvalidTransition(Exception):
    def __init__(self, phase, signal):
        super().__init__(f'{signal.name} 은 phase={phase.name} 에서 허용되지 않는다')
        self.phase = phase
        self.signal = signal


@dataclass(frozen=True)
class Snapshot:
    """WeldState.msg 의 내용 (stamp 는 노드가 발행할 때 찍는다)."""

    weld_id: str = ''
    scan_id: str = ''
    phase: WeldPhase = WeldPhase.IDLE
    line_index: int = LINE_NONE
    line_total: int = LINE_COUNT
    lines_done: int = 0
    line_progress: float = 0.0     # WELDING 에서만 유효, 그 밖은 0
    motion_id: int = 0


@dataclass(frozen=True)
class Outcome:
    accepted: bool
    reason: Reason
    state: Snapshot
    changed: bool = False


@dataclass(frozen=True)
class Failure:
    reason_code: int
    detail: str
    phase: WeldPhase      # 실패한 단계


class WeldStateMachine:
    """스레드 안전. 노드의 여러 콜백 · 시퀀스 스레드가 같이 부른다."""

    def __init__(self, on_change: Optional[Callable[[Snapshot], None]] = None):
        self._lock = threading.RLock()
        self._state = Snapshot()
        self._on_change = on_change
        self._home_origin: Optional[WeldPhase] = None   # 안전복귀가 끝나면 돌아갈 휴지 phase
        self._failure: Optional[Failure] = None

    # ---- 읽기 ----

    def snapshot(self) -> Snapshot:
        with self._lock:
            return self._state

    @property
    def phase(self) -> WeldPhase:
        return self.snapshot().phase

    @property
    def is_busy(self) -> bool:
        return self.phase not in REST_PHASES

    @property
    def failure(self) -> Optional[Failure]:
        with self._lock:
            return self._failure

    # ---- 명령 ----

    def request(self, command: Command, *, weld_id: str = '', scan_id: str = '') -> Outcome:
        with self._lock:
            phase = self._state.phase
            if command is Command.START:
                if phase not in REST_PHASES:
                    return Outcome(False, Reason.BUSY, self._state)
                if not weld_id or not scan_id:
                    raise ValueError('START 에는 weld_id · scan_id 가 필요하다')
                self._failure = None
                self._set(Snapshot(weld_id=weld_id, scan_id=scan_id, phase=WeldPhase.PREPARING))
                return Outcome(True, Reason.OK, self._state, changed=True)
            if command is Command.STOP:
                if phase in ACTIVE_PHASES:
                    self._set(replace(self._state, phase=WeldPhase.STOPPING, line_progress=0.0))
                    return Outcome(True, Reason.OK, self._state, changed=True)
                if phase is WeldPhase.STOPPING:
                    return Outcome(True, Reason.OK, self._state)             # 이미 멈추는 중(멱등)
                return Outcome(False, Reason.OK, self._state)                # 4.1절: 멈출 것이 없다
            if command is Command.HOME:
                if phase not in REST_PHASES:
                    return Outcome(False, Reason.BUSY, self._state)
                self._home_origin = phase
                self._set(replace(self._state, phase=WeldPhase.HOMING, line_index=LINE_NONE,
                                  line_progress=0.0, motion_id=0))
                return Outcome(True, Reason.OK, self._state, changed=True)
            raise ValueError(f'모르는 명령: {command!r}')

    # ---- 진행 보고 ----

    def notify(self, signal: Signal, *, line: Optional[int] = None,
               reason_code: int = 0, detail: str = '') -> Snapshot:
        with self._lock:
            phase = self._state.phase
            if signal is Signal.HOMING_DONE and phase is WeldPhase.HOMING and self._home_origin is not None:
                target = self._home_origin
            else:
                table = SIGNAL_TRANSITIONS[signal]
                if phase not in table:
                    raise InvalidTransition(phase, signal)
                target = table[phase]
            state = replace(self._state, phase=target)
            if signal is Signal.APPROACH:
                if line is None or not 0 <= line < LINE_COUNT:
                    raise ValueError(f'APPROACH 에는 선 번호(0~{LINE_COUNT - 1})가 필요하다: {line!r}')
                state = replace(state, line_index=line, line_progress=0.0)
            elif signal is Signal.LINE_DONE:
                state = replace(state, lines_done=state.lines_done + 1, line_progress=0.0)
            elif signal is Signal.FAILED:
                if not reason_code:
                    raise ValueError('FAILED 에는 0 이 아닌 reason_code 가 필요하다')
                self._failure = Failure(int(reason_code), detail, phase)
            if target is not WeldPhase.WELDING:
                state = replace(state, line_progress=0.0)
            if target in (WeldPhase.HOMING, WeldPhase.DONE) or target in REST_PHASES:
                state = replace(state, line_index=LINE_NONE)
            if target in REST_PHASES:
                self._home_origin = None
                state = replace(state, motion_id=0)
            self._set(state)
            return state

    def set_motion_id(self, motion_id: int) -> None:
        with self._lock:
            if motion_id != self._state.motion_id:
                self._set(replace(self._state, motion_id=int(motion_id)))

    def set_progress(self, progress: float) -> None:
        """WELDING 중의 선 안 진행률(0~1로 자른다). 다른 phase 에서는 무시한다(계약: 그 밖은 0)."""
        with self._lock:
            if self._state.phase is not WeldPhase.WELDING:
                return
            value = min(1.0, max(0.0, float(progress)))
            if value != self._state.line_progress:
                self._set(replace(self._state, line_progress=value))

    def _set(self, state: Snapshot) -> None:
        self._state = state
        if self._on_change is not None:
            self._on_change(state)
