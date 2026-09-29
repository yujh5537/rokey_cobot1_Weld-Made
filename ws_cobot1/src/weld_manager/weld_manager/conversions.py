"""순수 계산 결과 ↔ ROS 메시지 (weld-ros-interfaces.md 3~5장). rclpy 노드는 없고 메시지 타입만 쓴다.

- 좌표 · 단위는 그대로 옮긴다(m · quaternion). 단위 변환은 mqtt_bridge 의 일이다.
- 모르는 값은 NaN + *_valid=false 다. 기본 자세 (0, 0, 0, 1) 이나 0 으로 채우지 않는다(CLAUDE.md 규칙 4).
- builtin_interfaces/Time 에는 유효 플래그가 없다. 0 은 "없음"으로 읽는다(1차 scan_manager 의 has_stop_pose 와 같은 관례).
"""

import math
from typing import Dict, Optional

from builtin_interfaces.msg import Duration
from builtin_interfaces.msg import Time
from contact_scan_interfaces.action import ExecuteMotion
from contact_scan_interfaces.action import ExecutePath
from contact_scan_interfaces.msg import Segment
from contact_scan_interfaces.msg import WeldConfig
from contact_scan_interfaces.msg import WeldLine
from contact_scan_interfaces.msg import WeldResult
from contact_scan_interfaces.msg import WeldState
from geometry_msgs.msg import Point
from geometry_msgs.msg import Pose

from .contract_enums import LINE_COUNT
from .contract_enums import MotionReason
from .contract_enums import Operation
from .sequence import MotionKind
from .sequence import MotionRequest
from .sequence import MotionResult

NAN = float('nan')
# WeldConfig 의 (값 필드, *_set 필드). 값 필드 이름 = weld_manager 파라미터 이름
CONFIG_FIELDS = (
    ('weld_speed_mps', 'weld_speed_set'),
    ('travel_speed_mps', 'travel_speed_set'),
    ('standoff_m', 'standoff_set'),
    ('weave_amplitude_m', 'weave_amplitude_set'),
    ('weave_pitch_m', 'weave_pitch_set'),
    ('tilt_deg', 'tilt_set'),
)


# ---- 기본 ----

def time_msg(stamp) -> Time:
    """result_store.Stamp → Time. None 이면 0(= 없음)."""
    return Time() if stamp is None else Time(sec=int(stamp.sec), nanosec=int(stamp.nanosec))


def duration_msg(seconds: float) -> Duration:
    sec = math.floor(seconds)
    return Duration(sec=int(sec), nanosec=int(round((seconds - sec) * 1e9)) % 1_000_000_000)


def pose_msg(position, orientation) -> Pose:
    pose = Pose()
    pose.position.x, pose.position.y, pose.position.z = (float(v) for v in position)
    q = pose.orientation
    q.x, q.y, q.z, q.w = (float(v) for v in orientation)
    return pose


def nan_pose() -> Pose:
    pose = Pose()
    p, q = pose.position, pose.orientation
    p.x = p.y = p.z = q.x = q.y = q.z = q.w = NAN
    return pose


def position_of(pose: Pose):
    return (pose.position.x, pose.position.y, pose.position.z)


def orientation_of(pose: Pose):
    q = pose.orientation
    return (q.x, q.y, q.z, q.w)


def _stamped(time: Time) -> bool:
    return bool(time.sec or time.nanosec)


# ---- WeldConfig ----

def config_to_msg(values: Dict[str, float]) -> WeldConfig:
    """적용 설정 스냅샷(전부 *_set=true). 값이 없는 항목은 NaN + *_set=false."""
    msg = WeldConfig()
    for name, flag in CONFIG_FIELDS:
        value = values.get(name)
        setattr(msg, name, NAN if value is None else float(value))
        setattr(msg, flag, value is not None)
    return msg


def override_from_msg(msg: WeldConfig) -> Dict[str, float]:
    """*_set=true 인 항목만 {파라미터 이름: 값}."""
    return {name: getattr(msg, name) for name, flag in CONFIG_FIELDS if getattr(msg, flag)}


# ---- WeldState · WeldResult ----

def state_to_msg(snapshot, stamp: Time) -> WeldState:
    msg = WeldState()
    msg.stamp = stamp
    msg.weld_id = snapshot.weld_id
    msg.scan_id = snapshot.scan_id
    msg.phase = int(snapshot.phase)
    msg.line_index = int(snapshot.line_index)
    msg.line_total = int(snapshot.line_total)
    msg.lines_done = int(snapshot.lines_done)
    msg.line_progress = float(snapshot.line_progress)
    msg.motion_id = int(snapshot.motion_id)
    return msg


def _segment(seam) -> Segment:
    start, end = seam
    return Segment(start=Point(x=start[0], y=start[1], z=start[2]), end=Point(x=end[0], y=end[1], z=end[2]),
                   length=math.dist(start, end), valid=True)


def _blank_segment() -> Segment:
    return Segment(start=Point(x=NAN, y=NAN, z=NAN), end=Point(x=NAN, y=NAN, z=NAN), length=NAN, valid=False)


def line_to_msg(line) -> WeldLine:
    msg = WeldLine()
    msg.index = int(line.index)
    msg.seam = _segment(line.seam)
    msg.status = int(line.status)
    msg.reason_code = int(line.reason_code)
    msg.detail = line.detail
    if line.stop_pose is None:
        msg.stop_pose, msg.stop_pose_valid = nan_pose(), False
    else:
        msg.stop_pose = pose_msg(line.stop_pose.position, line.stop_pose.orientation)
        msg.stop_pose_valid = True
    msg.started_at = time_msg(line.started_at)
    msg.finished_at = time_msg(line.finished_at)
    return msg


def record_to_msg(record, stamp: Time) -> WeldResult:
    msg = WeldResult()
    msg.weld_id = record.weld_id
    msg.scan_id = record.scan_id
    msg.stamp = stamp
    msg.success = bool(record.success)
    msg.reason_code = int(record.reason_code)
    msg.detail = record.detail
    msg.frame_id = record.frame_id
    msg.base_to_fixture.x, msg.base_to_fixture.y, msg.base_to_fixture.z = record.base_to_fixture
    msg.start_line = int(record.start_line)
    msg.end_line = int(record.end_line)
    msg.lines = [line_to_msg(line) for line in record.lines]
    msg.config = config_to_msg(dict(record.config))
    msg.started_at = time_msg(record.started_at)
    msg.finished_at = time_msg(record.finished_at)
    return msg


def blank_result_msg(weld_id: str = '', scan_id: str = '') -> WeldResult:
    """용접을 시작하지 못한 명령의 Result 에 싣는다. 좌표는 NaN, *_valid 는 false, 선은 NOT_ATTEMPTED."""
    msg = WeldResult()
    msg.weld_id, msg.scan_id = weld_id, scan_id
    msg.base_to_fixture.x = msg.base_to_fixture.y = msg.base_to_fixture.z = NAN
    lines = []
    for index in range(LINE_COUNT):
        line = WeldLine(index=index, seam=_blank_segment(), stop_pose=nan_pose(), stop_pose_valid=False)
        lines.append(line)
    msg.lines = lines
    msg.config = config_to_msg({})
    return msg


# ---- goal · Result ----

def motion_goal(request: MotionRequest, weld_id: str, motion_id: int, frame_id: str) -> ExecuteMotion.Goal:
    """MOVE_TO · HOME → ExecuteMotion goal. scan_id 자리에는 weld_id 를 싣는다(robot_manager 는 로그에만 쓴다)."""
    goal = ExecuteMotion.Goal()
    goal.scan_id = weld_id
    goal.motion_id = int(motion_id)
    goal.frame_id = frame_id
    if request.kind is MotionKind.MOVE_TO:
        goal.operation = int(Operation.MOVE_TO)
        goal.target = pose_msg(request.target, request.orientation)
        goal.speed = float(request.speed)
    elif request.kind is MotionKind.HOME:
        goal.operation = int(Operation.HOME)
    else:
        raise ValueError(f'ExecuteMotion 으로 보낼 수 없는 요청: {request.kind}')
    if request.timeout_s is not None:
        goal.timeout = duration_msg(request.timeout_s)
    return goal


def path_goal(request: MotionRequest, weld_id: str, motion_id: int, frame_id: str) -> ExecutePath.Goal:
    if request.kind is not MotionKind.PATH:
        raise ValueError(f'ExecutePath 로 보낼 수 없는 요청: {request.kind}')
    goal = ExecutePath.Goal()
    goal.weld_id = weld_id
    goal.motion_id = int(motion_id)
    goal.line_index = int(request.line_index)
    goal.waypoints = [pose_msg(p, request.orientation) for p in request.waypoints]
    goal.frame_id = frame_id
    goal.speed = float(request.speed)
    goal.path_tolerance_m = float(request.path_tolerance_m)
    goal.timeout = duration_msg(request.timeout_s)
    return goal


def motion_result_from_msg(raw) -> MotionResult:
    """ExecuteMotion.Result · ExecutePath.Result → MotionResult. 정지 좌표는 pose_stamp 가 있을 때만 쓴다."""
    try:
        reason: Optional[MotionReason] = MotionReason(raw.reason)
    except ValueError:
        reason = None           # 모르는 값. classify 가 "맞지 않는 종료 사유"로 실패시킨다
    known = _stamped(raw.pose_stamp) and all(
        math.isfinite(v) for v in (*position_of(raw.pose), *orientation_of(raw.pose)))
    return MotionResult(
        reason=reason, reason_code=int(raw.reason_code), detail=raw.detail,
        position=position_of(raw.pose) if known else None,
        orientation=orientation_of(raw.pose) if known else None)
