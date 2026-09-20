"""ROS msg ↔ 순수 자료형(result_store 레코드 · sequence 요청/결과) 변환. rclpy 는 쓰지 않고 msg 타입만 쓴다.

- 무효 값: Python 안에서는 None, msg 에서는 NaN + 짝이 되는 *_valid=false (계약 1장). 0 을 넣지 않는다.
- 단위는 바꾸지 않는다(ROS 내부 단위 그대로). mm 변환은 mqtt_bridge 의 일이다.
"""

import math

from builtin_interfaces.msg import Duration
from builtin_interfaces.msg import Time
from contact_scan_interfaces.action import ExecuteMotion
from contact_scan_interfaces.msg import ContactEvent
from contact_scan_interfaces.msg import ScanConfig
from contact_scan_interfaces.msg import ScanResult
from contact_scan_interfaces.msg import ScanState
from contact_scan_interfaces.msg import Segment
from geometry_msgs.msg import Point

from .contract_enums import MotionReason
from .result_store import ConfigSnapshot
from .result_store import Detection
from .result_store import EVENT_CONTACT
from .result_store import EVENT_EDGE
from .result_store import PoseRecord
from .result_store import ShapeResult
from .result_store import Stamp
from .result_store import WrenchRecord
from .result_store.records import CONFIG_FIELDS
from .sequence import MotionRequest
from .sequence import MotionResult
from .state_machine import Snapshot

NAN = math.nan
_EVENT_TYPE = {ContactEvent.TYPE_CONTACT: EVENT_CONTACT, ContactEvent.TYPE_EDGE: EVENT_EDGE}
_INTEGER_CONFIG = ('debounce_n',)  # uint8 이라 NaN 을 실을 수 없다. 모르면 0 + debounce_set=false


# ---- 시각 · 좌표 ----

def stamp_from_msg(time_msg) -> Stamp:
    return Stamp(int(time_msg.sec), int(time_msg.nanosec))


def stamp_to_msg(stamp: Stamp) -> Time:
    return Time(sec=stamp.sec, nanosec=stamp.nanosec)


def duration_msg(seconds: float) -> Duration:
    whole = int(seconds)
    return Duration(sec=whole, nanosec=int(round((seconds - whole) * 1e9)))


def position_of(pose_msg):
    p = pose_msg.position
    return (p.x, p.y, p.z)


def pose_record(pose_msg, frame_id: str, stamp_msg) -> PoseRecord:
    q = pose_msg.orientation
    return PoseRecord(position_of(pose_msg), (q.x, q.y, q.z, q.w), frame_id, stamp_from_msg(stamp_msg))


# ---- 상태 ----

def state_to_msg(snapshot: Snapshot, stamp_msg) -> ScanState:
    msg = ScanState()
    msg.stamp = stamp_msg
    msg.scan_id = snapshot.scan_id
    msg.phase = int(snapshot.phase)
    msg.direction = int(snapshot.direction)
    msg.progress = snapshot.progress
    msg.progress_total = snapshot.progress_total
    msg.motion_id = snapshot.motion_id
    return msg


# ---- 이벤트 → 측정값 ----

def detection_from_event(event: ContactEvent) -> Detection:
    """판정 좌표(ContactEvent) → result_store 의 Detection. CONTACT · EDGE 만 측정값이다."""
    w = event.wrench
    return Detection(
        event_type=_EVENT_TYPE[event.type], event_id=int(event.event_id),
        sample_id=int(event.sample_id), motion_id=int(event.motion_id),
        pose=pose_record(event.pose, event.frame_id, event.pose_stamp),
        force_stamp=stamp_from_msg(event.force_stamp),
        detect_stamp=stamp_from_msg(event.detect_stamp),
        force_delta_n=event.force_delta_n,
        z_drop_m=event.z_drop_m if event.z_drop_valid else None,
        z_drop_valid=bool(event.z_drop_valid), source=event.source,
        debounce_count=int(event.debounce_count),
        wrench=WrenchRecord(
            (w.force.x, w.force.y, w.force.z), (w.torque.x, w.torque.y, w.torque.z)),
    )


# ---- 모션 ----

def goal_from_request(request: MotionRequest, scan_id: str, motion_id: int,
                      frame_id: str) -> ExecuteMotion.Goal:
    """쓰지 않는 필드는 msg 기본값으로 둔다(계약 5.4절: target 은 MOVE_TO 만, direction 은 SLIDE 만)."""
    goal = ExecuteMotion.Goal()
    goal.scan_id = scan_id
    goal.motion_id = int(motion_id)
    goal.operation = int(request.operation)
    goal.frame_id = frame_id
    goal.direction = int(request.direction)
    if request.target_position is not None:
        p, q = goal.target.position, goal.target.orientation
        p.x, p.y, p.z = request.target_position
        q.x, q.y, q.z, q.w = request.target_orientation
    if request.speed is not None:
        goal.speed = float(request.speed)
    if request.max_distance is not None:
        goal.max_distance = float(request.max_distance)
    if request.timeout_s is not None:
        goal.timeout = duration_msg(request.timeout_s)
    return goal


def motion_result_from_msg(result: ExecuteMotion.Result) -> MotionResult:
    try:
        reason = MotionReason(result.reason)
    except ValueError:
        reason = None  # 모르는 값은 classify 가 실패로 판정한다
    return MotionResult(
        reason=reason, reason_code=int(result.reason_code), detail=result.detail,
        event_id=int(result.event_id), position=position_of(result.pose),
        compliance_released=bool(result.compliance_released), raw=result)


def stop_pose_record(result: ExecuteMotion.Result) -> PoseRecord:
    """정지 좌표(ExecuteMotion.Result.pose). 판정 좌표와 섞지 않는다."""
    return pose_record(result.pose, result.frame_id, result.pose_stamp)


# ---- 설정 ----

def config_values_from_msg(msg: ScanConfig) -> dict:
    """*_set=true 인 항목만 {이름: 값} 으로. 나머지는 "주지 않음"이다."""
    return {
        name: (int if name in _INTEGER_CONFIG else float)(getattr(msg, name))
        for name, flag in CONFIG_FIELDS if getattr(msg, flag)
    }


def config_to_msg(values) -> ScanConfig:
    """{이름: 값 | None} → ScanConfig. 모르는 값은 NaN + *_set=false 다(0 을 채우지 않는다).

    debounce_n 은 uint8 이라 NaN 을 실을 수 없다. 모르면 msg 기본값 0 이 남으므로 **debounce_set 으로만** 판단한다.
    """
    msg = ScanConfig()
    for name, flag in CONFIG_FIELDS:
        value = values.get(name)
        known = value is not None
        setattr(msg, flag, known)
        if name in _INTEGER_CONFIG:
            if known:
                setattr(msg, name, int(value))
        else:
            setattr(msg, name, float(value) if known else NAN)
    return msg


def config_snapshot(values) -> ConfigSnapshot:
    return ConfigSnapshot(**{name: values.get(name) for name, _flag in CONFIG_FIELDS})


# ---- 결과 ----

def _point(values) -> Point:
    if values is None:
        return Point(x=NAN, y=NAN, z=NAN)
    return Point(x=values[0], y=values[1], z=values[2])


def _segment(record) -> Segment:
    return Segment(
        start=_point(record.start), end=_point(record.end),
        length=record.length if record.valid else NAN, valid=record.valid)


def result_to_msg(scan_id: str, shape: ShapeResult, config: ScanConfig, stamp_msg) -> ScanResult:
    """ShapeResult → ScanResult. 무효 값은 NaN + *_valid=false, 배열은 길이를 유지한다(계약 3.5절).

    stamp 는 발행할 때마다 새로 찍는다(mqtt_bridge 가 (scan_id, stamp) 로 중복을 거른다).
    """
    msg = ScanResult()
    msg.scan_id = scan_id
    msg.stamp = stamp_msg
    msg.success = shape.success
    msg.reason_code = shape.reason_code
    msg.detail = shape.detail
    msg.frame_id = shape.frame_id
    for name in ('z_top', 'x_pos', 'x_neg', 'y_pos', 'y_neg', 'support_z'):
        measured = getattr(shape, name)
        setattr(msg, name, measured.value if measured.valid else NAN)
        setattr(msg, f'{name}_valid', measured.valid)
    for name in ('width', 'length', 'height'):
        setattr(msg, name, getattr(shape, name) if shape.dims_valid else NAN)
    msg.dims_valid = shape.dims_valid
    msg.vertices = [_point(v) for v in shape.vertices]
    msg.box_valid = shape.box_valid
    msg.edges = [_segment(s) for s in shape.edges]
    msg.path_candidates = [_segment(s) for s in shape.path_candidates]
    msg.config = config
    msg.started_at = stamp_to_msg(shape.started_at)
    msg.finished_at = stamp_to_msg(shape.finished_at)
    return msg
