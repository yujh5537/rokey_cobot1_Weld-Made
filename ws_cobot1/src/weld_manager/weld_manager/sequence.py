"""용접 순서의 순수 로직 (rclpy 없음). 기준: docs/phase2/weld-motion.md 5절, weld-ros-interfaces.md 5 · 7장.

세 부분이다(scan_manager/sequence.py 와 같은 구조. 코드는 가져오지 않았다).
- classify(): 모션 하나의 Result → 도착 / 중지 / 실패(ReasonCode).
- WeldRunner: start_line..end_line 의 선마다 접근 1 → 접근 2 → 경로 → 후퇴, 끝나면 결과 저장 → 마무리 홈 복귀.
- run_home(): 관제자의 안전복귀. 툴 축 뒤로 물러남 → z_safe → OP_HOME.
다른 노드와의 통신 · 상태 기계 · 파일은 Ports 뒤에 있다. 노드가 Ports 를 구현하고, 시험은 가짜 Ports 로 ROS 없이 순서를 본다.

규칙
- 어떤 goal 이든 도착이 아니면 **그 자리에서 끝낸다**: 다음 goal 을 보내지 않고, 자동 복귀 · 재시도 없음(CLAUDE.md 규칙 3).
- STOPPED 는 이 노드가 /weld/stop 으로 요청한 정지뿐이다. 요청하지 않은 정지는 ERROR 다(D25).
- 모션 사이에 안전 래치가 걸리면 다음 goal 을 보내지 않는다. 안전복귀(run_home)는 래치 중에도 간다(1차와 같다).
- 결과(/weld/result · 파일)는 마무리 홈 복귀보다 먼저 낸다(7.3절). 중지 · 실패도 한 번 낸다.
- 정지 좌표는 그 선을 끝낸 모션이 준 좌표만 쓴다. 로봇이 움직였을 수 있는데 좌표를 못 받았으면 모른다(None)로 둔다.
"""

from dataclasses import dataclass
from dataclasses import replace
from enum import Enum
import itertools
import math
from typing import List, Optional, Tuple

from scan_manager.result_store import Stamp

from .contract_enums import LINE_COUNT
from .contract_enums import LINE_NONE
from .contract_enums import LineStatus
from .contract_enums import MotionReason
from .contract_enums import Reason
from .params import WeldParams
from .state_machine import Signal
from .weld_path import rotate
from .weld_path import WeldPlan
from .weld_record import LineRecord
from .weld_record import Pose
from .weld_record import WeldRecord

Vec3 = Tuple[float, float, float]
Quat = Tuple[float, float, float, float]


# ---- 모션 요청 · 결과 ----

class MotionKind(Enum):
    MOVE_TO = 'MOVE_TO'   # ExecuteMotion OP_MOVE_TO
    HOME = 'HOME'         # ExecuteMotion OP_HOME
    PATH = 'PATH'         # ExecutePath


@dataclass(frozen=True)
class MotionRequest:
    """goal 에 실을 값. 좌표는 Base(m), 자세는 quaternion. 쓰지 않는 필드는 기본값."""

    kind: MotionKind
    label: str
    speed: Optional[float] = None               # m/s. HOME 은 쓰지 않는다
    target: Optional[Vec3] = None               # MOVE_TO
    orientation: Optional[Quat] = None          # MOVE_TO · PATH (선 안에서는 한 자세)
    waypoints: Tuple[Vec3, ...] = ()            # PATH
    line_index: int = LINE_NONE                 # PATH 의 관측용 (ExecutePath.line_index)
    path_length_m: Optional[float] = None       # PATH: line_progress 의 분모
    path_tolerance_m: Optional[float] = None    # PATH
    timeout_s: Optional[float] = None


@dataclass(frozen=True)
class MotionResult:
    """goal 하나의 끝. 노드가 ExecuteMotion · ExecutePath 의 Result 를 이 모양으로 옮긴다."""

    available: bool = True       # false = 서버가 없거나 goal 응답이 오지 않았다(움직였는지 모른다)
    accepted: bool = True        # false = goal 거절. 로봇은 움직이지 않았다
    reason: Optional[MotionReason] = None
    reason_code: int = 0
    detail: str = ''
    position: Optional[Vec3] = None      # 정지 좌표(Base). Result 에 없으면 None
    orientation: Optional[Quat] = None


class VerdictKind(Enum):
    REACHED = 'REACHED'
    STOPPED = 'STOPPED'
    FAILED = 'FAILED'


@dataclass(frozen=True)
class Verdict:
    kind: VerdictKind
    reason_code: int = 0
    detail: str = ''


def orientation_error_rad(a: Quat, b: Quat) -> float:
    """두 자세 사이의 회전각 (q 와 −q 는 같은 자세)."""
    dot = abs(sum(x * y for x, y in zip(a, b)))
    norm = math.sqrt(sum(x * x for x in a) * sum(y * y for y in b))
    return 2.0 * math.acos(min(1.0, dot / norm))


def _failed(code, detail) -> Verdict:
    return Verdict(VerdictKind.FAILED, int(code), detail)


def classify(request: MotionRequest, result: MotionResult, *, stop_requested: bool,
             safety_code: int = 0, orientation_tolerance_rad: Optional[float] = None) -> Verdict:
    """모션 하나의 결과를 판정한다.

    stop_requested: 이 작업에 /weld/stop 이 접수됐는가.
    safety_code: /safety/status 가 래치 중이면 그 reason_code, 아니면 0.
    orientation_tolerance_rad: 주면 도착한 자세를 목표와 대조한다(robot_manager 는 위치만 본다). None 이면 보지 않는다.
    """
    label = request.label
    if not result.available:
        server = '/robot/execute_path' if request.kind is MotionKind.PATH else '/robot/execute_motion'
        return _failed(Reason.ROBOT_DISCONNECTED, f'{label}: {server} 서버가 없거나 goal 응답이 오지 않았다')
    if not result.accepted:
        return _failed(Reason.ROBOT_ERROR, f'{label}: goal 이 거절됐다')   # ROS 2 의 거절에는 사유가 없다

    reason = result.reason
    if reason in (MotionReason.STOP_REQUESTED, MotionReason.CANCELED):
        if stop_requested:
            return Verdict(VerdictKind.STOPPED, int(Reason.STOP_REQUESTED), result.detail)
        # D25: 이 노드가 요청하지 않은 정지(웹의 스캔 중지 버튼 · safety_monitor)는 ERROR 다
        return _failed(
            safety_code or Reason.ROBOT_ERROR,
            f'{label}: 요청하지 않은 정지 {reason.name} (reason_code={result.reason_code}, {result.detail})')

    verdict = _classify_ended(request, result, orientation_tolerance_rad)
    if stop_requested and verdict.kind is VerdictKind.REACHED:
        # 중지와 동시에 도착한 모션. 중지가 우선이다. 실패 사유로 끝났으면 중지를 접수했어도 실패다(사실을 가리지 않는다)
        return Verdict(VerdictKind.STOPPED, int(Reason.STOP_REQUESTED), f'{label}: 중지 접수 뒤에 도착했다')
    return verdict


def _classify_ended(request, result, orientation_tolerance_rad) -> Verdict:
    label, reason = request.label, result.reason
    if reason is MotionReason.TARGET_REACHED:
        if (orientation_tolerance_rad is not None and request.orientation is not None
                and request.kind is not MotionKind.HOME):
            if result.orientation is None:
                return _failed(Reason.ROBOT_ERROR, f'{label}: 도착했지만 자세를 받지 못해 확인할 수 없다')
            error = orientation_error_rad(request.orientation, result.orientation)
            if error > orientation_tolerance_rad:
                return _failed(Reason.ROBOT_ERROR,
                               f'{label}: 도착했지만 자세가 목표와 {math.degrees(error):.2f}° 다르다 '
                               f'(허용 {math.degrees(orientation_tolerance_rad):.2f}°)')
        return Verdict(VerdictKind.REACHED)
    if reason is MotionReason.TIMEOUT:
        return _failed(Reason.TIMEOUT, f'{label}: {result.detail}')
    if reason is MotionReason.OVER_FORCE:
        return _failed(Reason.OVER_FORCE, f'{label}: {result.detail}')
    if reason in (MotionReason.ROBOT_ERROR, MotionReason.REJECTED):
        # PATH_REJECTED(604) 등 robot_manager 가 준 코드를 그대로 쓴다
        return _failed(result.reason_code or Reason.ROBOT_ERROR, f'{label}: {result.detail}')
    name = getattr(reason, 'name', reason)
    return _failed(Reason.ROBOT_ERROR, f'{label}: {request.kind.name} 에 맞지 않는 종료 사유 {name}')


# ---- 바깥일 ----

class Ports:
    """러너가 바깥에 시키는 일. 노드가 구현한다(시험은 가짜). 기다리는 메서드는 시퀀스 스레드를 막아도 된다."""

    def stop_requested(self) -> bool:
        """이 작업에 /weld/stop 이 접수됐는가."""
        raise NotImplementedError

    def safety_reason_code(self) -> int:
        """/safety/status 가 래치 중이면 그 reason_code, 아니면 0."""
        raise NotImplementedError

    def execute(self, motion_id: int, request: MotionRequest) -> MotionResult:
        """goal 을 보내고 Result 까지 기다린다. PATH 의 진행률(line_progress)은 노드가 feedback 으로 갱신한다."""
        raise NotImplementedError

    def notify(self, signal: Signal, **kwargs) -> bool:
        """상태 기계에 알린다. 중지가 먼저 접수돼 그 전이가 허용되지 않으면 False(→ 러너는 중지로 간다)."""
        raise NotImplementedError

    def wait_still(self) -> bool:
        """/robot/status 로 connected && !moving 을 확인한다. 제한 시간 안에 못 보면 False."""
        raise NotImplementedError

    def now(self) -> Stamp:
        raise NotImplementedError

    def save_result(self, record: WeldRecord) -> None:
        """결과 원본을 파일로 쓰고 /weld/result 로 낸다. 실패는 노드가 로그로 남긴다(작업 흐름은 막지 않는다)."""
        raise NotImplementedError

    def log(self, level: str, message: str, position: Optional[Vec3] = None) -> None:
        raise NotImplementedError


class OutcomeKind(Enum):
    DONE = 'DONE'
    STOPPED = 'STOPPED'
    FAILED = 'FAILED'
    HOMING_FAILED = 'HOMING_FAILED'   # 용접선은 다 끝났고 마무리 복귀만 실패. 결과는 유효하다(7.3절)


@dataclass(frozen=True)
class RunOutcome:
    kind: OutcomeKind
    reason_code: int = 0
    detail: str = ''
    record: Optional[WeldRecord] = None
    last_motion_id: int = 0


class _Stop(Exception):
    pass


class _Fail(Exception):

    def __init__(self, reason_code, detail):
        super().__init__(detail)
        self.reason_code = int(reason_code)
        self.detail = detail


class _Runner:
    """모션 보내기 · 판정 · 중지 / 실패 마무리의 공통 부분."""

    def __init__(self, ports: Ports, params: WeldParams, first_motion_id: int = 1,
                 block_on_latch: bool = True, orientation_tolerance_rad: Optional[float] = None):
        if first_motion_id < 1:
            raise ValueError('motion_id 는 1 부터다(0 = 없음)')
        self._ports = ports
        self._params = params
        self._ids = itertools.count(first_motion_id)
        self.last_motion_id = first_motion_id - 1
        self._block_on_latch = block_on_latch
        self._tolerance = orientation_tolerance_rad
        self.last_pose: Optional[Pose] = None     # 가장 최근에 안 로봇 자리(Base). 모르면 None

    def _notify(self, signal: Signal, **kwargs) -> None:
        if not self._ports.notify(signal, **kwargs):
            raise _Stop()

    def _execute(self, request: MotionRequest) -> MotionResult:
        if self._ports.stop_requested():
            raise _Stop()
        if self._block_on_latch:
            latched = self._ports.safety_reason_code()
            if latched:
                raise _Fail(latched, f'{request.label}: 안전 래치 중이라 모션을 보내지 않았다')
        self.last_motion_id = next(self._ids)
        result = self._ports.execute(self.last_motion_id, request)
        if result.position is not None and result.orientation is not None:
            self.last_pose = Pose(tuple(result.position), tuple(result.orientation))
        elif not (result.available and not result.accepted):
            # 거절된 goal 만 로봇이 움직이지 않은 것이 확실하다. 그 밖에 좌표 · 자세를 못 받았으면
            # 어디서 멈췄는지 모른다 — 앞 좌표로 대신하지 않는다
            self.last_pose = None
        verdict = classify(request, result, stop_requested=self._ports.stop_requested(),
                           safety_code=self._ports.safety_reason_code(),
                           orientation_tolerance_rad=self._tolerance)
        if verdict.kind is VerdictKind.STOPPED:
            if verdict.detail:
                self._ports.log('info', verdict.detail, result.position)
            raise _Stop()
        if verdict.kind is VerdictKind.FAILED:
            raise _Fail(verdict.reason_code, verdict.detail)
        return result

    def _move_to(self, label, target, orientation, speed) -> MotionResult:
        return self._execute(MotionRequest(
            MotionKind.MOVE_TO, label, speed=speed, target=tuple(target), orientation=orientation,
            timeout_s=self._params.motion_timeout_s))

    def _home(self) -> MotionResult:
        return self._execute(MotionRequest(MotionKind.HOME, 'home', timeout_s=self._params.motion_timeout_s))


class WeldRunner(_Runner):
    """용접 한 번: (APPROACH → WELDING → RETREAT) × start_line..end_line → 결과 → HOMING → DONE.

    노드가 상태 기계를 START(→ PREPARING) 로 바꾸고 경로를 만든 뒤 run() 을 부른다.
    """

    def __init__(self, ports: Ports, plan: WeldPlan, params: WeldParams, weld_id: str, frame_id: str,
                 orientation_tolerance_rad: Optional[float] = None):
        super().__init__(ports, params, 1, True, orientation_tolerance_rad)
        self._plan = plan
        self._weld_id = weld_id
        self._frame_id = frame_id
        self._started_at: Optional[Stamp] = None
        self._current: Optional[int] = None    # 진행 중인 선. 끝났거나 선 밖이면 None
        self._homing = False
        self._published: Optional[WeldRecord] = None
        chosen = range(plan.start_line, plan.end_line + 1)
        self._lines: List[LineRecord] = [
            LineRecord(i, plan.seams[i], LineStatus.NOT_ATTEMPTED if i in chosen else LineStatus.SKIPPED)
            for i in range(LINE_COUNT)]

    def run(self) -> RunOutcome:
        p = self._params
        self._started_at = self._ports.now()
        try:
            last = None
            for index in range(self._plan.start_line, self._plan.end_line + 1):
                line = self._plan.lines[index]
                last = line
                # 알림이 받아들여진 뒤에 "진행 중"으로 표시한다. 그 사이에 중지가 접수되면 이 선은 시작하지 않은 것이다
                self._notify(Signal.APPROACH, line=index)
                self._current = index
                self._lines[index] = replace(self._lines[index], started_at=self._ports.now())
                self._move_to(f'{line.name} 접근 1', line.approach1, line.orientation, p.travel_speed_mps)
                self._move_to(f'{line.name} 접근 2', line.approach2, line.orientation, p.approach_speed_mps)
                self._notify(Signal.WELD)
                self._execute(MotionRequest(
                    MotionKind.PATH, f'{line.name} 경로', speed=p.weld_speed_mps,
                    orientation=line.orientation, waypoints=line.path, line_index=index,
                    path_length_m=line.path_length_m, path_tolerance_m=p.path_tolerance_m,
                    timeout_s=p.motion_timeout_s))
                self._notify(Signal.RETREAT)
                # 5절 표: 후퇴는 travel_speed_mps (6절 표의 approach_speed_mps "후퇴" 와 어긋난다 — 병후 확인 대기)
                self._move_to(f'{line.name} 후퇴', line.retreat, line.orientation, p.travel_speed_mps)
                self._lines[index] = replace(
                    self._lines[index], status=LineStatus.DONE, finished_at=self._ports.now())
                self._current = None
                self._notify(Signal.LINE_DONE)
            self._publish(success=True, reason_code=0, detail='')
            self._homing = True
            self._notify(Signal.HOMING)
            # 7.3절: HOMING = OP_MOVE_TO z_safe → OP_HOME. 마지막 후퇴가 이미 z_safe 라 거의 제자리 이동이다
            self._move_to('마무리 올림', last.retreat, last.orientation, p.travel_speed_mps)
            self._home()
            self._notify(Signal.HOMING_DONE)
            return RunOutcome(OutcomeKind.DONE, 0, '', self._published, self.last_motion_id)
        except _Stop:
            return self._finish_stop()
        except _Fail as failure:
            return self._finish_fail(failure)

    # ---- 마무리 ----

    def _stop_pose_fixture(self) -> Optional[Pose]:
        if self.last_pose is None:
            return None
        b = self._plan.base_to_fixture
        x, y, z = self.last_pose.position
        return Pose((x - b[0], y - b[1], z - b[2]), self.last_pose.orientation)

    def _end_current_line(self, status: LineStatus, reason_code: int, detail: str) -> None:
        if self._current is None:
            return
        self._lines[self._current] = replace(
            self._lines[self._current], status=status, reason_code=int(reason_code), detail=detail,
            stop_pose=self._stop_pose_fixture(), finished_at=self._ports.now())
        self._current = None

    def _publish(self, success: bool, reason_code: int, detail: str) -> None:
        if self._published is not None:
            return    # 마무리 복귀 중의 중지 · 실패: 결과는 이미 냈다(한 번만)
        record = WeldRecord(
            weld_id=self._weld_id, scan_id=self._plan.scan_id, success=success,
            reason_code=int(reason_code), detail=detail, frame_id=self._frame_id,
            base_to_fixture=self._plan.base_to_fixture, start_line=self._plan.start_line,
            end_line=self._plan.end_line, lines=tuple(self._lines), config=self._params.config_values(),
            started_at=self._started_at, finished_at=self._ports.now())
        self._ports.save_result(record)
        self._published = record

    def _finish_stop(self) -> RunOutcome:
        if not self._ports.wait_still():
            return self._finish_fail(_Fail(
                Reason.ROBOT_STATUS_LOST, '정지 완료(connected && !moving)를 확인하지 못했다'))
        self._end_current_line(LineStatus.STOPPED, Reason.STOP_REQUESTED, '작업 중지')
        self._publish(False, Reason.STOP_REQUESTED, '작업 중지')
        self._ports.notify(Signal.STOP_CONFIRMED)
        return RunOutcome(OutcomeKind.STOPPED, int(Reason.STOP_REQUESTED), 'stopped',
                          self._published, self.last_motion_id)

    def _finish_fail(self, failure: _Fail) -> RunOutcome:
        self._end_current_line(LineStatus.FAILED, failure.reason_code, failure.detail)
        self._publish(False, failure.reason_code, failure.detail)
        self._ports.notify(Signal.FAILED, reason_code=failure.reason_code, detail=failure.detail)
        kind = OutcomeKind.HOMING_FAILED if self._homing else OutcomeKind.FAILED
        return RunOutcome(kind, failure.reason_code, failure.detail, self._published, self.last_motion_id)


class HomeRunner(_Runner):
    """관제자의 안전복귀(/weld/home, 7.2절). 휴지 phase 에서 HOME 이 접수된 뒤(phase=HOMING) 에 부른다.

    current_pose(Base, 지금 로봇 자리)를 알면: 툴 축 뒤(−d)로 approach_m 물러남 → z_safe 로 올림 → OP_HOME.
    모르면 물러남 · 올림 없이 OP_HOME 만 보낸다(기울인 자세에서 곧장 관절 이동 — 관제자가 보고 누른다).
    z_safe 를 모르면(이 프로세스에서 계획한 적이 없다) 물러남까지만 하고 OP_HOME.
    안전 래치 중에도 간다(안전복귀를 막지 않는다).
    """

    def __init__(self, ports: Ports, params: WeldParams, current_pose: Optional[Pose],
                 z_safe_base: Optional[float], first_motion_id: int = 1):
        super().__init__(ports, params, first_motion_id, block_on_latch=False)
        self._pose = current_pose
        self._z_safe = z_safe_base

    def run(self) -> RunOutcome:
        p = self._params
        try:
            if self._pose is None:
                self._ports.log('warn', '안전복귀: 현재 자리를 몰라 물러남 · 올림 없이 OP_HOME 만 보낸다')
            else:
                q = self._pose.orientation
                d = rotate(q, (0.0, 0.0, 1.0))                  # 툴 z 축 = 플랜지 → 팁
                back = tuple(c - p.approach_m * di for c, di in zip(self._pose.position, d))
                self._move_to('안전복귀 물러남', back, q, p.approach_speed_mps)
                if self._z_safe is None:
                    self._ports.log('warn', '안전복귀: z_safe 를 몰라 물러난 뒤 바로 OP_HOME 을 보낸다')
                else:
                    lift = (back[0], back[1], max(back[2], self._z_safe))
                    self._move_to('안전복귀 올림', lift, q, p.travel_speed_mps)
            self._home()
            self._notify(Signal.HOMING_DONE)
            return RunOutcome(OutcomeKind.DONE, 0, '', None, self.last_motion_id)
        except _Stop:
            if not self._ports.wait_still():
                return self._fail(_Fail(Reason.ROBOT_STATUS_LOST, '정지 완료(connected && !moving)를 확인하지 못했다'))
            self._ports.notify(Signal.STOP_CONFIRMED)
            return RunOutcome(OutcomeKind.STOPPED, int(Reason.STOP_REQUESTED), 'stopped', None,
                              self.last_motion_id)
        except _Fail as failure:
            return self._fail(failure)

    def _fail(self, failure: _Fail) -> RunOutcome:
        self._ports.notify(Signal.FAILED, reason_code=failure.reason_code, detail=failure.detail)
        return RunOutcome(OutcomeKind.FAILED, failure.reason_code, failure.detail, None, self.last_motion_id)
