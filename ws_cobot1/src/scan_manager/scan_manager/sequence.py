"""스캔 시퀀스의 순수 로직 (rclpy 없음). 기준: ros-interfaces.md 5.4 · 7.1 · 7.3 · 7.4절, BRD 4.2.5 · 4.2.6.

세 부분이다.

- MotionPlanner: 파라미터 → ExecuteMotion goal 에 실을 값(MotionRequest). 방향 전환 3단계, 마무리 순서.
- classify(): 모션 하나의 Result → 도달 / 측정 확보 / 중지 경로 / 실패(ReasonCode).
- ScanRunner · run_home(): 순서를 돈다. 다른 노드와의 통신 · 기록 · 상태 기계는 Ports 뒤에 있다.
  노드는 Ports 를 구현하고, 테스트는 가짜 Ports 로 ROS 없이 순서를 검증한다.

규칙
- 측정값의 출처는 판정 좌표(ContactEvent)다. 정지 좌표(ExecuteMotion.Result.pose)는 따로 기록한다.
- 실패 · 중단 · 형상 계산 실패에서는 **자동으로 홈 복귀하지 않는다**(7.4절, CLAUDE.md 규칙 3).
- 중지는 STOPPED 로만 간다. 이 파일에는 중지 뒤에 모션을 보내는 경로가 없다.
  다만 중지를 접수했어도 모션이 실패 사유로 끝났으면 실패(ERROR)다. 사실을 가리지 않는다.
- 스캔의 모든 모션(마무리 복귀 포함)은 보내기 전에 안전 래치를 본다. 관제자의 안전복귀는 막지 않는다.
- 측정값은 기록(디스크)을 확인한 뒤에 상태 기계에 알린다(result_store/README.md).
"""

from dataclasses import dataclass
from enum import Enum
import itertools
from typing import Optional, Tuple

from .contract_enums import Direction
from .contract_enums import MotionReason
from .contract_enums import Operation
from .contract_enums import Reason
from .params import ScanParams
from .result_store import TOP  # 측정 대상 '윗면'(record_attempt_failed 의 target). 모서리는 Direction
from .state_machine import Signal

Position = Tuple[float, float, float]
Orientation = Tuple[float, float, float, float]


# ---- 모션 요청 ----

@dataclass(frozen=True)
class MotionRequest:
    """ExecuteMotion goal 에 실을 값. 쓰지 않는 필드는 None 이다(계약 5.4절의 "~만 사용")."""

    operation: Operation
    label: str                                  # 로그 · 테스트용 이름
    speed: Optional[float] = None               # m/s. OP_HOME 은 쓰지 않는다
    target_position: Optional[Position] = None  # OP_MOVE_TO 만
    target_orientation: Optional[Orientation] = None
    direction: Direction = Direction.NONE       # OP_SLIDE 만
    max_distance: Optional[float] = None        # OP_DESCEND · OP_SLIDE
    timeout_s: Optional[float] = None


class MotionPlanner:

    def __init__(self, params: ScanParams):
        self._p = params

    def _move_to(self, label, position, speed) -> MotionRequest:
        # 탐색 중 자세는 수직 고정이다(units-frames.md). 기준점의 자세를 그대로 쓴다.
        return MotionRequest(
            Operation.MOVE_TO, label, speed=speed, target_position=tuple(position),
            target_orientation=self._p.origin_orientation, timeout_s=self._p.motion_timeout_s)

    def to_origin(self) -> MotionRequest:
        return self._move_to('to_origin', self._p.origin_position, self._p.move_speed_mps)

    def descend(self) -> MotionRequest:
        return MotionRequest(
            Operation.DESCEND, 'descend', speed=self._p.descend_speed_mps,
            max_distance=self._p.max_descend_m, timeout_s=self._p.motion_timeout_s)

    def slide(self, direction: Direction) -> MotionRequest:
        return MotionRequest(
            Operation.SLIDE, f'slide_{Direction(direction).name}', speed=self._p.slide_speed_mps,
            direction=Direction(direction), max_distance=self._p.max_slide_m,
            timeout_s=self._p.motion_timeout_s)

    def lift(self, stop_position: Position, label='lift') -> MotionRequest:
        x, y, z = stop_position
        return self._move_to(label, (x, y, z + self._p.lift_height_m), self._p.move_speed_mps)

    def change_direction(self, stop_position: Position, first_contact_z: float):
        """7.3절: ① 올림 ② 기준 원점의 x · y 로 수평 이동 ③ 첫 접촉 z + margin 까지 저속 내림.

        재하강(OP_DESCEND)은 하지 않는다. 남은 틈은 다음 SLIDE 의 −z 목표 힘이 메운다.
        """
        lifted_z = stop_position[2] + self._p.lift_height_m
        origin_x, origin_y, _ = self._p.origin_position
        return (
            self.lift(stop_position),
            self._move_to('to_origin_xy', (origin_x, origin_y, lifted_z), self._p.move_speed_mps),
            self._move_to(
                'recontact', (origin_x, origin_y, first_contact_z + self._p.recontact_margin_m),
                self._p.recontact_speed_mps),
        )

    def home(self) -> MotionRequest:
        return MotionRequest(Operation.HOME, 'home', timeout_s=self._p.motion_timeout_s)


# ---- 모션 결과 판정 ----

@dataclass(frozen=True)
class MotionResult:
    """ExecuteMotion 한 번의 끝. 노드가 Result 를 이 모양으로 옮긴다."""

    available: bool = True               # false = 서버가 server_wait_timeout_s 안에 뜨지 않았다
    accepted: bool = True                # false = goal 거절. ROS 2 의 거절에는 사유가 없다
    reason: Optional[MotionReason] = None
    reason_code: int = 0
    detail: str = ''
    event_id: int = 0
    position: Optional[Position] = None  # 정지 좌표(Base). 판정 좌표가 아니다
    compliance_released: bool = True
    raw: object = None                   # 기록에 쓸 원본(ExecuteMotion.Result)


class VerdictKind(Enum):
    REACHED = 'REACHED'      # OP_MOVE_TO · OP_HOME 이 목표에 닿았다
    MEASURED = 'MEASURED'    # CONTACT · EDGE 로 끝났다. 짝이 되는 이벤트를 기다릴 차례
    STOPPED = 'STOPPED'      # 작업 중지 경로. 실패가 아니다
    FAILED = 'FAILED'


@dataclass(frozen=True)
class MotionVerdict:
    kind: VerdictKind
    reason_code: int = 0
    detail: str = ''


def _failed(code, detail) -> MotionVerdict:
    return MotionVerdict(VerdictKind.FAILED, int(code), detail)


def classify(request: MotionRequest, result: MotionResult, *, stop_requested: bool,
             safety_reason_code: int = 0) -> MotionVerdict:
    """모션 하나의 결과를 판정한다.

    stop_requested: 이 노드가 /scan/stop 을 접수했는가.
    safety_reason_code: /safety/status 가 래치 중이면 그 reason_code, 아니면 0.
    """
    if not result.available:
        return _failed(Reason.ROBOT_DISCONNECTED, '/robot/execute_motion 서버가 없다')
    if not result.accepted:
        # 사유를 추측하지 않는다(실행 중 · 미연결 · 잘못된 값 중 무엇인지 알 수 없다)
        return _failed(Reason.ROBOT_ERROR, f'{request.label}: goal rejected')
    if not result.compliance_released:
        # 계약 9장 TBD(해제 실패 보고). 순응 · 힘 제어가 켜진 채일 수 있으므로 더 진행하지 않는다.
        return _failed(
            result.reason_code or Reason.ROBOT_ERROR,
            f'{request.label}: compliance_released=false ({result.detail})')

    reason = result.reason
    if reason in (MotionReason.STOP_REQUESTED, MotionReason.CANCELED):
        if stop_requested:
            return MotionVerdict(VerdictKind.STOPPED, int(Reason.STOP_REQUESTED), result.detail)
        # 이 노드가 요청하지 않은 정지(예: safety_monitor 의 /robot/stop). Result 의 코드는
        # STOP_REQUESTED · CANCELED 라서 실패 사유로 쓰지 않는다(작업 중지로 읽힌다).
        return _failed(
            safety_reason_code or Reason.ROBOT_ERROR,
            f'{request.label}: 요청하지 않은 정지 {reason.name} '
            f'(reason_code={result.reason_code}, {result.detail})')

    verdict = _classify_ended(request, result)
    if stop_requested and verdict.kind is not VerdictKind.FAILED:
        # 중지와 동시에 도달 · 측정으로 끝난 모션. 중지가 우선이다(늦게 온 측정값 방침은 T26).
        # 실패 사유(OVER_FORCE · ROBOT_ERROR · MAX_DISTANCE · TIMEOUT …)로 끝났으면 중지를 접수했어도
        # 실패다. STOPPED 로 보내면 그 사실이 가려지고 재시작 대상이 된다(병후 결정 2026-09-20).
        return MotionVerdict(
            VerdictKind.STOPPED, int(Reason.STOP_REQUESTED),
            f'{request.label}: 중지 접수 뒤에 {reason.name} 로 끝났다')
    return verdict


def _classify_ended(request: MotionRequest, result: MotionResult) -> MotionVerdict:
    """정지 요청이 아닌 사유로 끝난 모션."""
    op, reason = request.operation, result.reason
    if reason is MotionReason.TARGET_REACHED and op in (Operation.MOVE_TO, Operation.HOME):
        return MotionVerdict(VerdictKind.REACHED)
    measured = (
        (reason is MotionReason.CONTACT and op is Operation.DESCEND)
        or (reason is MotionReason.EDGE and op is Operation.SLIDE))
    if measured:
        if not result.event_id:
            return _failed(
                Reason.ROBOT_ERROR, f'{request.label}: {reason.name} 인데 event_id 가 0 이다')
        return MotionVerdict(VerdictKind.MEASURED)
    if reason is MotionReason.MAX_DISTANCE and op is Operation.DESCEND:
        return _failed(Reason.NO_CONTACT, f'max_descend_m {request.max_distance} 안에 접촉이 없다')
    if reason is MotionReason.MAX_DISTANCE and op is Operation.SLIDE:
        return _failed(Reason.NO_EDGE, f'max_slide_m {request.max_distance} 안에 접촉 소실이 없다')
    if reason is MotionReason.TIMEOUT:
        return _failed(Reason.TIMEOUT, f'{request.label}: {result.detail}')
    if reason is MotionReason.OVER_FORCE:
        return _failed(Reason.OVER_FORCE, f'{request.label}: {result.detail}')
    if reason in (MotionReason.ROBOT_ERROR, MotionReason.REJECTED):
        # DROP_LIMIT(205) 등 robot_manager 가 준 코드를 그대로 쓴다
        return _failed(
            result.reason_code or Reason.ROBOT_ERROR, f'{request.label}: {result.detail}')
    return _failed(
        Reason.ROBOT_ERROR,
        f'{request.label}: {op.name} 에 맞지 않는 종료 사유 {getattr(reason, "name", reason)}')


# ---- 순서 ----

@dataclass(frozen=True)
class MatchedEvent:
    """Result.event_id 와 짝이 맞은 ContactEvent."""

    position: Position   # 판정 좌표(Base)
    raw: object = None   # ContactEvent 원본


@dataclass(frozen=True)
class StepOutcome:
    """tare · 형상 계산처럼 모션이 아닌 단계의 결과."""

    success: bool
    reason_code: int = 0
    detail: str = ''


class Ports:
    """ScanRunner 가 바깥에 시키는 일. 노드가 구현한다(테스트는 가짜).

    기다리는 메서드는 부르는 스레드(시퀀스 스레드)를 막아도 된다. 상태 기계의 락을 쥔 채 부르지 않는다.
    """

    def stop_requested(self) -> bool:
        """이 작업에 /scan/stop 이 접수됐는가."""
        raise NotImplementedError

    def safety_reason_code(self) -> int:
        """/safety/status 가 래치 중이면 **0 이 아닌** ReasonCode(그 reason_code), 아니면 0."""
        raise NotImplementedError

    def execute(self, motion_id: int, request: MotionRequest) -> MotionResult:
        """goal 을 보내고 Result 까지 기다린다. motion_id 의 표시 · 해제도 여기서 한다."""
        raise NotImplementedError

    def wait_event(self, event_id: int) -> Optional[MatchedEvent]:
        """event_wait_timeout_s 안에 짝이 맞는 이벤트. 없으면 None."""
        raise NotImplementedError

    def wait_still(self) -> bool:
        """**이 호출보다 뒤에 찍힌** /robot/status 로 connected && !moving 을 확인한다."""
        raise NotImplementedError

    def tare(self) -> StepOutcome:
        raise NotImplementedError

    def record_top(self, event: MatchedEvent, result: MotionResult, request: MotionRequest):
        """디스크에 쓰인 것을 확인하고 돌아온다."""
        raise NotImplementedError

    def record_edge(self, direction: Direction, event: MatchedEvent, result: MotionResult,
                    request: MotionRequest):
        raise NotImplementedError

    def record_attempt_failed(self, target, reason_code: int, detail: str, result: MotionResult):
        """target 은 TOP 또는 Direction."""
        raise NotImplementedError

    def notify(self, signal: Signal) -> bool:
        """상태 기계에 알린다. 그 사이에 STOP 이 접수돼 받아들여지지 않았으면 False."""
        raise NotImplementedError

    def compute_geometry(self) -> StepOutcome:
        """형상 계산 → result_store 원본 저장 → /scan/result 발행(7.4절)."""
        raise NotImplementedError

    def fail(self, reason_code: int, detail: str, position: Optional[Position]):
        """실패를 로그에 남기고 FAILED 를 알린 뒤 기록한다(BRD 4.2.5: 원인 · 단계 · 위치)."""
        raise NotImplementedError

    def record_stop(self, position: Optional[Position], result: Optional[MotionResult],
                    during_final_homing: bool):
        """중단 위치를 기록한다. notify(STOP_CONFIRMED) 보다 먼저 불린다."""
        raise NotImplementedError

    def log_info(self, message: str, position: Optional[Position] = None):
        raise NotImplementedError


class OutcomeKind(Enum):
    DONE = 'DONE'
    STOPPED = 'STOPPED'
    FAILED = 'FAILED'                # 측정이 끝나기 전의 실패
    HOMING_FAILED = 'HOMING_FAILED'  # 마무리 복귀 실패. 측정 결과는 유효하다(7.4절)


@dataclass(frozen=True)
class RunOutcome:
    kind: OutcomeKind
    reason_code: int = 0
    detail: str = ''


class _Stop(Exception):
    pass


class _Fail(Exception):

    def __init__(self, reason_code, detail):
        super().__init__(detail)
        self.reason_code = int(reason_code)
        self.detail = detail


class _Runner:

    def __init__(self, planner: MotionPlanner, ports: Ports, first_motion_id: int = 1,
                 block_on_latch: bool = True):
        if first_motion_id < 1:
            raise ValueError('motion_id 는 1 부터다(0 = 없음)')
        self._plan = planner
        self._ports = ports
        self._block_on_latch = block_on_latch
        self._motion_ids = itertools.count(first_motion_id)
        self.last_motion_id = first_motion_id - 1
        self._last_result: Optional[MotionResult] = None
        self._position: Optional[Position] = None  # 가장 최근에 안 정지 좌표

    def _check_stop(self):
        if self._ports.stop_requested():
            raise _Stop()

    def _notify(self, signal: Signal):
        if not self._ports.notify(signal):
            raise _Stop()

    def _execute(self, request: MotionRequest, target=None) -> MotionResult:
        """모션 하나. 중지는 _Stop, 실패는 _Fail 로 빠진다. target 은 측정 대상(TOP · Direction)."""
        self._check_stop()
        if self._block_on_latch:
            # 모션 사이(tare · 기록 · 형상 계산 중)에 걸린 안전 래치. 모션 중의 래치는 로봇 정지의 Result 로 잡힌다.
            latched = self._ports.safety_reason_code()
            if latched:
                raise _Fail(latched, f'{request.label}: 안전 래치 중이라 모션을 보내지 않았다')
        self.last_motion_id = next(self._motion_ids)
        result = self._ports.execute(self.last_motion_id, request)
        self._last_result = result
        if result.position is not None:
            self._position = result.position
        verdict = classify(
            request, result, stop_requested=self._ports.stop_requested(),
            safety_reason_code=self._ports.safety_reason_code())
        if verdict.kind is VerdictKind.STOPPED:
            if verdict.detail:
                self._ports.log_info(verdict.detail, result.position)
            raise _Stop()
        if verdict.kind is VerdictKind.FAILED:
            self._attempt_failed(target, verdict.reason_code, verdict.detail, result)
        return result

    def _attempt_failed(self, target, reason_code, detail, result):
        if target is not None:
            self._ports.record_attempt_failed(target, reason_code, detail, result)
        raise _Fail(reason_code, detail)

    def _measure(self, request: MotionRequest, target) -> Tuple[MatchedEvent, MotionResult]:
        result = self._execute(request, target)
        event = self._ports.wait_event(result.event_id)
        if event is None:
            # 측정값 없이 통과시키지 않는다
            self._attempt_failed(
                target, Reason.TIMEOUT,
                f'{request.label}: event_id={result.event_id} 인 ContactEvent 가 오지 않았다', result)
        if self._ports.stop_requested():
            self._ports.log_info(
                f'{request.label}: 중지 접수 뒤에 도착한 측정값은 기록하지 않는다(판정 좌표)',
                event.position)
            raise _Stop()
        return event, result

    def _finish_stop(self, during_final_homing: bool) -> RunOutcome:
        if not self._ports.wait_still():
            return self._finish_fail(_Fail(
                Reason.ROBOT_STATUS_LOST, '정지 완료(connected && !moving)를 확인하지 못했다'))
        self._ports.record_stop(self._position, self._last_result, during_final_homing)
        self._ports.notify(Signal.STOP_CONFIRMED)
        return RunOutcome(OutcomeKind.STOPPED, int(Reason.STOP_REQUESTED), 'stopped')

    def _finish_fail(self, failure: _Fail, kind=OutcomeKind.FAILED) -> RunOutcome:
        self._ports.fail(failure.reason_code, failure.detail, self._position)
        return RunOutcome(kind, failure.reason_code, failure.detail)


class ScanRunner(_Runner):
    """새 작업 하나: PREPARING → TOP_SEARCH → EDGE_SEARCH ×4 → GEOMETRY → HOMING → DONE.

    START 가 접수된 뒤(phase=PREPARING)에 run() 을 부른다.
    """

    def __init__(self, planner, ports, direction_order, first_motion_id: int = 1):
        super().__init__(planner, ports, first_motion_id)
        self._order = tuple(Direction(d) for d in direction_order)

    def run(self) -> RunOutcome:
        try:
            self._prepare()
            first_contact_z = self._find_top()
            for index, direction in enumerate(self._order):
                if index:
                    self._change_direction(first_contact_z)
                self._find_edge(direction)
            self._geometry()
        except _Stop:
            return self._finish_stop(during_final_homing=False)
        except _Fail as failure:
            return self._finish_fail(failure)

        # 여기부터는 측정이 끝난 뒤다. 실패해도 ScanResult 는 그대로 유효하다(7.4절).
        try:
            self._final_homing()
        except _Stop:
            return self._finish_stop(during_final_homing=True)
        except _Fail as failure:
            return self._finish_fail(failure, OutcomeKind.HOMING_FAILED)
        return RunOutcome(OutcomeKind.DONE)

    def _prepare(self):
        # tare 는 무접촉 · 정지 상태에서 한다. 그 자리가 측정을 시작할 기준 원점 상공이다.
        self._execute(self._plan.to_origin())
        self._check_stop()
        if not self._ports.wait_still():
            raise _Fail(Reason.ROBOT_MOVING, 'tare 전에 정지(connected && !moving)를 확인하지 못했다')
        self._check_stop()
        tare = self._ports.tare()
        if not tare.success:
            raise _Fail(tare.reason_code or Reason.TARE_FAILED, f'tare: {tare.detail}')
        self._notify(Signal.PREPARE_DONE)

    def _find_top(self) -> float:
        request = self._plan.descend()
        event, result = self._measure(request, TOP)
        self._ports.record_top(event, result, request)
        self._notify(Signal.TOP_FOUND)
        return event.position[2]  # 첫 접촉 z = 판정 좌표의 z (7.3절)

    def _find_edge(self, direction: Direction):
        request = self._plan.slide(direction)
        event, result = self._measure(request, direction)
        self._ports.record_edge(direction, event, result, request)
        self._notify(Signal.EDGE_FOUND)

    def _change_direction(self, first_contact_z: float):
        if self._position is None:
            raise _Fail(Reason.ROBOT_ERROR, '방향 전환: 직전 모션의 정지 좌표를 모른다')
        for request in self._plan.change_direction(self._position, first_contact_z):
            self._execute(request)

    def _geometry(self):
        self._check_stop()
        outcome = self._ports.compute_geometry()
        if not outcome.success:
            raise _Fail(outcome.reason_code or Reason.INVALID_SHAPE, outcome.detail)
        self._notify(Signal.GEOMETRY_DONE)

    def _final_homing(self):
        if self._position is None:
            raise _Fail(Reason.ROBOT_ERROR, '마무리 복귀: 직전 모션의 정지 좌표를 모른다')
        self._execute(self._plan.lift(self._position, label='final_lift'))
        self._execute(self._plan.home())
        self._notify(Signal.HOMING_DONE)


def run_home(planner: MotionPlanner, ports: Ports, first_motion_id: int = 1) -> RunOutcome:
    """관제자의 안전복귀(/scan/home). HOME 이 접수된 뒤(phase=HOMING)에 부른다.

    홈 복귀 경로 · 순서는 TBD(계약 7.4절)라 OP_HOME 하나만 보낸다.
    """
    # 안전 래치는 안전복귀를 막지 않는다(T10 결정, scan_manager/README.md)
    runner = _Runner(planner, ports, first_motion_id, block_on_latch=False)
    try:
        runner._execute(planner.home())
        runner._notify(Signal.HOMING_DONE)
    except _Stop:
        return runner._finish_stop(during_final_homing=False)
    except _Fail as failure:
        return runner._finish_fail(failure)
    return RunOutcome(OutcomeKind.DONE)
