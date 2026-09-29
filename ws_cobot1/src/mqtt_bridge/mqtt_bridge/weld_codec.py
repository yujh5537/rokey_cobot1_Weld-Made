"""Phase 2 weld MQTT boundary: payload validation and ROS message encoding."""

import math

from mqtt_bridge.conversions import non_finite_to_none, ros_time_to_epoch_ms
from mqtt_bridge.encoders import encode_pose, encode_reason_name

VERSION = "0.2"
PHASES = ('IDLE', 'PREPARING', 'APPROACH', 'WELDING', 'RETREAT',
          'DONE', 'ERROR', 'STOPPING', 'STOPPED', 'HOMING')
STATUSES = ('NOT_ATTEMPTED', 'DONE', 'FAILED', 'STOPPED', 'SKIPPED')
LEVELS = ('INFO', 'WARN', 'ERROR')
CONFIG = {
    'weld_speed_mm_s': ('weld_speed_mps', 'weld_speed_set', 1000),
    'travel_speed_mm_s': ('travel_speed_mps', 'travel_speed_set', 1000),
    'standoff_mm': ('standoff_m', 'standoff_set', 1000),
    'weave_amplitude_mm': ('weave_amplitude_m', 'weave_amplitude_set', 1000),
    'weave_pitch_mm': ('weave_pitch_m', 'weave_pitch_set', 1000),
    'tilt_deg': ('tilt_deg', 'tilt_set', 1),
}


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{label} must be a finite number')
    return float(value)


def decode_start(message):
    payload = message['payload']
    if not isinstance(payload, dict):
        raise ValueError('payload must be an object')
    if set(payload) - {'scan_id', 'start_line', 'end_line', 'config'}:
        raise ValueError('unknown weld start field')
    scan_id = payload.get('scan_id', '')
    if not isinstance(scan_id, str):
        raise ValueError('scan_id must be a string')
    start, end = payload.get('start_line', 0), payload.get('end_line', 7)
    if any(isinstance(v, bool) or not isinstance(v, int) for v in (start, end)) or not 0 <= start <= end <= 7:
        raise ValueError('line range must be within 0..7, start <= end')
    config = payload.get('config', {})
    if not isinstance(config, dict) or set(config) - CONFIG.keys():
        raise ValueError('invalid weld config')
    patch = {}
    for key, value in config.items():
        field, flag, scale = CONFIG[key]
        patch[field] = _number(value, key) / scale
        patch[flag] = True
    return dict(request_id=message['request_id'], scan_id=scan_id,
                start_line=start, end_line=end, config=patch,
                use_override=bool(config))


def _time(stamp):
    return ros_time_to_epoch_ms(stamp.sec, stamp.nanosec)


def _point(point):
    return dict(x=non_finite_to_none(point.x * 1000),
                y=non_finite_to_none(point.y * 1000),
                z=non_finite_to_none(point.z * 1000))


def _pose(pose):
    return encode_pose(dict(x=pose.position.x, y=pose.position.y, z=pose.position.z,
                            qx=pose.orientation.x, qy=pose.orientation.y,
                            qz=pose.orientation.z, qw=pose.orientation.w))


def _name(table, value):
    return table[value] if 0 <= value < len(table) else f'UNKNOWN_{value}'


def encode_state(msg, published_at_ms):
    return dict(schema_version=VERSION, stamp_ms=_time(msg.stamp),
                weld_id=msg.weld_id, scan_id=msg.scan_id,
                phase=_name(PHASES, msg.phase),
                line_index=None if msg.line_index == 255 else msg.line_index,
                line_total=msg.line_total, lines_done=msg.lines_done,
                line_progress=non_finite_to_none(msg.line_progress),
                motion_id=msg.motion_id, published_at_ms=published_at_ms)


def encode_config(msg):
    return {key: non_finite_to_none(getattr(msg, field) * scale)
            for key, (field, _, scale) in CONFIG.items()}


def encode_result(msg, published_at_ms):
    lines = []
    for line in msg.lines:
        seam = line.seam
        lines.append(dict(index=line.index,
                          seam=dict(start=_point(seam.start), end=_point(seam.end),
                                    length_mm=non_finite_to_none(seam.length * 1000),
                                    valid=seam.valid),
                          status=_name(STATUSES, line.status),
                          reason_code=line.reason_code,
                          reason=encode_reason_name(line.reason_code),
                          detail=line.detail,
                          stop_pose=dict(position=_point(line.stop_pose.position),
                                         orientation=dict(x=line.stop_pose.orientation.x,
                                                          y=line.stop_pose.orientation.y,
                                                          z=line.stop_pose.orientation.z,
                                                          w=line.stop_pose.orientation.w))
                          if line.stop_pose_valid else None,
                          started_at_ms=_time(line.started_at),
                          finished_at_ms=_time(line.finished_at)))
    return dict(schema_version=VERSION, weld_id=msg.weld_id, scan_id=msg.scan_id,
                stamp_ms=_time(msg.stamp), success=msg.success,
                reason_code=msg.reason_code, reason=encode_reason_name(msg.reason_code),
                detail=msg.detail, frame_id=msg.frame_id,
                base_to_fixture_mm=_point(msg.base_to_fixture),
                start_line=msg.start_line, end_line=msg.end_line,
                lines=lines, config=encode_config(msg.config),
                started_at_ms=_time(msg.started_at), finished_at_ms=_time(msg.finished_at),
                published_at_ms=published_at_ms)


def encode_log(msg, published_at_ms):
    return dict(schema_version=VERSION, stamp_ms=_time(msg.stamp),
                weld_id=msg.scan_id, level=_name(LEVELS, msg.level),
                phase=_name(PHASES, msg.phase), direction='NONE',
                motion_id=msg.motion_id, code=msg.code,
                code_name=encode_reason_name(msg.code), message=msg.message,
                frame_id=msg.frame_id,
                pose=_pose(msg.pose) if msg.pose_valid else None,
                pose_valid=msg.pose_valid, published_at_ms=published_at_ms)


def encode_command_result(request_id, weld_id, success, code, detail, published_at_ms):
    return dict(schema_version=VERSION, request_id=request_id, weld_id=weld_id,
                success=success, reason_code=code, reason=encode_reason_name(code),
                detail=detail, published_at_ms=published_at_ms)
