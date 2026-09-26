"""ROS values -> mqtt-schema.md v0.1 JSON encoders."""

from mqtt_bridge.conversions import (
    meters_per_second_to_mm_per_second,
    meters_to_mm,
    non_finite_to_none,
    ros_time_to_epoch_ms,
    value_or_none,
)

SCHEMA_VERSION = "0.1"

ROBOT_OPERATION_NAMES = {0: "NONE", 1: "MOVE_TO", 2: "DESCEND", 3: "SLIDE", 4: "HOME"}
REASON_NAMES = {
    0: "OK",
    100: "BUSY", 101: "INVALID_REQUEST", 102: "INVALID_VALUE",
    103: "SAFETY_LATCHED", 104: "ROBOT_DISCONNECTED",
    105: "NO_RESUMABLE_SCAN", 106: "DUPLICATE_REQUEST",
    107: "NOT_SUPPORTED", 108: "PARAM_SET_FAILED",
    200: "STOP_REQUESTED", 201: "CANCELED", 202: "MAX_DISTANCE",
    203: "TIMEOUT", 204: "ROBOT_ERROR", 205: "DROP_LIMIT",
    300: "NO_CONTACT", 301: "NO_EDGE", 302: "TOOL_REG_SUSPECT",
    303: "TARE_FAILED", 304: "ROBOT_MOVING", 305: "TARE_UNSTABLE",
    306: "TARE_TIMEOUT", 307: "NO_SAMPLE",
    400: "OVER_FORCE", 401: "OVER_SPEED", 402: "OUT_OF_WORKSPACE",
    403: "SAMPLE_STALE", 404: "ROBOT_STATUS_LOST", 405: "HB_EXPIRED",
    406: "CONDITION_ACTIVE", 407: "STOP_UNCONFIRMED",
    500: "INVALID_SHAPE", 501: "INSUFFICIENT_POINTS",
    # 6xx 용접 (phase 2, 계약 v0.2.0 #184). 이름만 — WELD_PATH 동작 이름 · UNKNOWN_<n> 규칙은 의석의 브리지 표 PR
    600: "SCAN_ACTIVE", 601: "WELD_ACTIVE", 602: "NO_SCAN_RESULT",
    603: "LINE_OUT_OF_RANGE", 604: "PATH_REJECTED",
}
SCAN_PHASE_NAMES = {
    0: "IDLE", 1: "PREPARING", 2: "TOP_SEARCH", 3: "EDGE_SEARCH",
    4: "GEOMETRY", 5: "DONE", 6: "ERROR", 7: "STOPPING",
    8: "STOPPED", 9: "HOMING", 10: "RESUMING",
}
SCAN_DIRECTION_NAMES = {0: "NONE", 1: "POS_X", 2: "NEG_X", 3: "POS_Y", 4: "NEG_Y"}
CONTACT_EVENT_TYPE_NAMES = {0: "CONTACT", 1: "EDGE", 2: "OVER_FORCE"}
SCAN_LOG_LEVEL_NAMES = {0: "INFO", 1: "WARN", 2: "ERROR"}
SAFETY_LEVEL_NAMES = {0: "OK", 1: "WARN", 2: "STOP"}


def _enum_name(table, value, label):
    if value not in table:
        raise ValueError(f"unknown {label}: {value}")
    return table[value]


def encode_robot_operation(value):
    return _enum_name(ROBOT_OPERATION_NAMES, value, "robot operation")


def encode_reason_name(value):
    return _enum_name(REASON_NAMES, value, "reason code")


def encode_scan_phase(value):
    return _enum_name(SCAN_PHASE_NAMES, value, "scan phase")


def encode_scan_direction(value):
    return _enum_name(SCAN_DIRECTION_NAMES, value, "scan direction")


def encode_contact_event_type(value):
    return _enum_name(CONTACT_EVENT_TYPE_NAMES, value, "contact event type")


def encode_scan_log_level(value):
    return _enum_name(SCAN_LOG_LEVEL_NAMES, value, "scan log level")


def encode_safety_level(value):
    return _enum_name(SAFETY_LEVEL_NAMES, value, "safety level")


def encode_point(point):
    return {
        "x_mm": non_finite_to_none(meters_to_mm(point["x"])),
        "y_mm": non_finite_to_none(meters_to_mm(point["y"])),
        "z_mm": non_finite_to_none(meters_to_mm(point["z"])),
    }


def encode_pose(pose):
    return {
        "x_mm": non_finite_to_none(meters_to_mm(pose["x"])),
        "y_mm": non_finite_to_none(meters_to_mm(pose["y"])),
        "z_mm": non_finite_to_none(meters_to_mm(pose["z"])),
        "qx": non_finite_to_none(pose["qx"]),
        "qy": non_finite_to_none(pose["qy"]),
        "qz": non_finite_to_none(pose["qz"]),
        "qw": non_finite_to_none(pose["qw"]),
    }


def encode_wrench(wrench):
    return {
        "fx_n": non_finite_to_none(wrench["fx"]),
        "fy_n": non_finite_to_none(wrench["fy"]),
        "fz_n": non_finite_to_none(wrench["fz"]),
        "tx_nm": non_finite_to_none(wrench["tx"]),
        "ty_nm": non_finite_to_none(wrench["ty"]),
        "tz_nm": non_finite_to_none(wrench["tz"]),
    }


def encode_robot_sample(sample, published_at_ms):
    return {
        "schema_version": SCHEMA_VERSION,
        "sample_id": sample["sample_id"],
        "frame_id": sample["frame_id"],
        "pose": encode_pose(sample["pose"]),
        "pose_stamp_ms": ros_time_to_epoch_ms(**sample["pose_stamp"]),
        "wrench": encode_wrench(sample["wrench"]),
        "force_stamp_ms": ros_time_to_epoch_ms(**sample["force_stamp"]),
        "valid": sample["valid"],
        "motion_id": sample["motion_id"],
        "operation": encode_robot_operation(sample["operation"]),
        "published_at_ms": published_at_ms,
    }


def encode_robot_status(status, published_at_ms):
    code = status["error_code"]
    return {
        "schema_version": SCHEMA_VERSION,
        "stamp_ms": ros_time_to_epoch_ms(**status["stamp"]),
        "connected": status["connected"],
        "moving": status["moving"],
        "error": status["error"],
        "error_code": code,
        "error_name": encode_reason_name(code),
        "compliance_active": status["compliance_active"],
        "force_ctrl_active": status["force_ctrl_active"],
        "motion_id": status["motion_id"],
        "operation": encode_robot_operation(status["operation"]),
        # SLIDE 누름 목표 (계약 3.2, v0.1.21). 모르는 값은 NaN → null 이다. 0 으로 채우지 않는다.
        # slide_force_estimate_n 은 **추정**이다(기준 + 설정). 실측 누름이 아니다 —
        # 웹은 이 값을 "실측"이라고 표시하면 안 된다
        "slide_mode": status["slide_mode"],
        "slide_force_setpoint_n": non_finite_to_none(status["slide_force_setpoint_n"]),
        "slide_force_baseline_n": non_finite_to_none(status["slide_force_baseline_n"]),
        "slide_force_estimate_n": non_finite_to_none(status["slide_force_estimate_n"]),
        "step_press_lo_n": non_finite_to_none(status["step_press_lo_n"]),
        "step_press_hi_n": non_finite_to_none(status["step_press_hi_n"]),
        "detail": status["detail"],
        "published_at_ms": published_at_ms,
    }


def encode_scan_state(state, published_at_ms):
    return {
        "schema_version": SCHEMA_VERSION,
        "stamp_ms": ros_time_to_epoch_ms(**state["stamp"]),
        "scan_id": state["scan_id"],
        "phase": encode_scan_phase(state["phase"]),
        "direction": encode_scan_direction(state["direction"]),
        "progress": state["progress"],
        "progress_total": state["progress_total"],
        "motion_id": state["motion_id"],
        "published_at_ms": published_at_ms,
    }


def encode_contact_event(event, published_at_ms):
    z_drop_mm = (
        non_finite_to_none(meters_to_mm(event["z_drop_m"]))
        if event["z_drop_valid"] else None
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "event_id": event["event_id"],
        "scan_id": event["scan_id"],
        "motion_id": event["motion_id"],
        "sample_id": event["sample_id"],
        "type": encode_contact_event_type(event["type"]),
        "source": event["source"],
        "frame_id": event["frame_id"],
        "pose": encode_pose(event["pose"]),
        "wrench": encode_wrench(event["wrench"]),
        "pose_stamp_ms": ros_time_to_epoch_ms(**event["pose_stamp"]),
        "force_stamp_ms": ros_time_to_epoch_ms(**event["force_stamp"]),
        "detect_stamp_ms": ros_time_to_epoch_ms(**event["detect_stamp"]),
        "force_delta_n": non_finite_to_none(event["force_delta_n"]),
        "z_drop_mm": z_drop_mm,
        "z_drop_valid": event["z_drop_valid"],
        "debounce_count": event["debounce_count"],
        "published_at_ms": published_at_ms,
    }


def encode_scan_log(log, published_at_ms):
    return {
        "schema_version": SCHEMA_VERSION,
        "stamp_ms": ros_time_to_epoch_ms(**log["stamp"]),
        "scan_id": log["scan_id"],
        "level": encode_scan_log_level(log["level"]),
        "phase": encode_scan_phase(log["phase"]),
        "direction": encode_scan_direction(log["direction"]),
        "motion_id": log["motion_id"],
        "code": log["code"],
        "code_name": encode_reason_name(log["code"]),
        "message": log["message"],
        "frame_id": log["frame_id"],
        "pose": encode_pose(log["pose"]) if log["pose_valid"] else None,
        "pose_valid": log["pose_valid"],
        "published_at_ms": published_at_ms,
    }


def encode_safety_status(status, published_at_ms):
    code = status["reason_code"]
    return {
        "schema_version": SCHEMA_VERSION,
        "stamp_ms": ros_time_to_epoch_ms(**status["stamp"]),
        "level": encode_safety_level(status["level"]),
        "reason_code": code,
        "reason": encode_reason_name(code),
        "stop_required": status["stop_required"],
        "stop_confirmed": status["stop_confirmed"],
        "latched": status["latched"],
        "motion_id": status["motion_id"],
        "position": encode_point(status["position"]) if status["position_valid"] else None,
        "position_valid": status["position_valid"],
        "detail": status["detail"],
        "published_at_ms": published_at_ms,
    }


def encode_scan_config(config):
    return {
        "contact_threshold_n": non_finite_to_none(config["contact_threshold_n"]),
        "edge_drop_mm": non_finite_to_none(meters_to_mm(config["edge_drop_m"])),
        "debounce_n": value_or_none(
            config["debounce_n"],
            config["debounce_set"],
        ),
        "over_force_n": non_finite_to_none(config["over_force_n"]),
        "descend_speed_mmps": non_finite_to_none(
            meters_per_second_to_mm_per_second(config["descend_speed_mps"])
        ),
        "slide_speed_mmps": non_finite_to_none(
            meters_per_second_to_mm_per_second(config["slide_speed_mps"])
        ),
        "max_descend_mm": non_finite_to_none(meters_to_mm(config["max_descend_m"])),
        "max_slide_mm": non_finite_to_none(meters_to_mm(config["max_slide_m"])),
        "motion_timeout_s": non_finite_to_none(config["motion_timeout_s"]),
        "lift_height_mm": non_finite_to_none(meters_to_mm(config["lift_height_m"])),
        "target_force_n": non_finite_to_none(config["target_force_n"]),
        "drop_limit_mm": non_finite_to_none(meters_to_mm(config["drop_limit_m"])),
    }


def encode_segment(segment):
    return {
        "start": encode_point(segment["start"]),
        "end": encode_point(segment["end"]),
        "length_mm": non_finite_to_none(meters_to_mm(segment["length"])),
        "valid": segment["valid"],
    }


def _optional_mm(value, valid):
    return non_finite_to_none(meters_to_mm(value)) if valid else None


def encode_scan_result(result, published_at_ms):
    if result["box_valid"]:
        vertices = [encode_point(v) for v in result["vertices"]]
        edges = [encode_segment(e) for e in result["edges"]]
        paths = [encode_segment(e) for e in result["path_candidates"]]
    else:
        vertices = edges = paths = None

    code = result["reason_code"]
    return {
        "schema_version": SCHEMA_VERSION,
        "scan_id": result["scan_id"],
        "stamp_ms": ros_time_to_epoch_ms(**result["stamp"]),
        "success": result["success"],
        "reason_code": code,
        "reason": encode_reason_name(code),
        "detail": result["detail"],
        "frame_id": result["frame_id"],
        "z_top_mm": _optional_mm(result["z_top"], result["z_top_valid"]),
        "z_top_valid": result["z_top_valid"],
        "x_pos_mm": _optional_mm(result["x_pos"], result["x_pos_valid"]),
        "x_pos_valid": result["x_pos_valid"],
        "x_neg_mm": _optional_mm(result["x_neg"], result["x_neg_valid"]),
        "x_neg_valid": result["x_neg_valid"],
        "y_pos_mm": _optional_mm(result["y_pos"], result["y_pos_valid"]),
        "y_pos_valid": result["y_pos_valid"],
        "y_neg_mm": _optional_mm(result["y_neg"], result["y_neg_valid"]),
        "y_neg_valid": result["y_neg_valid"],
        "width_mm": _optional_mm(result["width"], result["dims_valid"]),
        "length_mm": _optional_mm(result["length"], result["dims_valid"]),
        "height_mm": _optional_mm(result["height"], result["dims_valid"]),
        "dims_valid": result["dims_valid"],
        "support_z_mm": _optional_mm(result["support_z"], result["support_z_valid"]),
        "support_z_valid": result["support_z_valid"],
        "vertices": vertices,
        "box_valid": result["box_valid"],
        "edges": edges,
        "path_candidates": paths,
        "config": encode_scan_config(result["config"]),
        "started_at_ms": ros_time_to_epoch_ms(**result["started_at"]),
        "finished_at_ms": ros_time_to_epoch_ms(**result["finished_at"]),
        "published_at_ms": published_at_ms,
    }


def encode_command_ack(request_id, accepted, reason_code, detail, published_at_ms, applied=None):
    message = {
        "schema_version": SCHEMA_VERSION,
        "request_id": request_id,
        "accepted": accepted,
        "reason_code": reason_code,
        "reason": encode_reason_name(reason_code),
        "detail": detail,
    }
    if applied is not None:
        message["applied"] = encode_scan_config(applied)
    message["published_at_ms"] = published_at_ms
    return message


def encode_command_result(request_id, scan_id, success, reason_code, detail, published_at_ms):
    return {
        "schema_version": SCHEMA_VERSION,
        "request_id": request_id,
        "scan_id": scan_id,
        "success": success,
        "reason_code": reason_code,
        "reason": encode_reason_name(reason_code),
        "detail": detail,
        "published_at_ms": published_at_ms,
    }


def encode_ros_heartbeat(seq, published_at_ms):
    return {"schema_version": SCHEMA_VERSION, "seq": seq, "published_at_ms": published_at_ms}


def encode_ros_connection(connected, published_at_ms):
    return {
        "schema_version": SCHEMA_VERSION,
        "connected": connected,
        "published_at_ms": published_at_ms,
    }
