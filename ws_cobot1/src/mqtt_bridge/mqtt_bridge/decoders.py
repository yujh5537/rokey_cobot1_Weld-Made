"""MQTT JSON -> ROS request value decoders."""

from mqtt_bridge.conversions import (
    millimeters_per_second_to_meters_per_second,
    millimeters_to_meters,
)

STOP_REQUESTED = 200

ALLOWED_CONFIG_KEYS = {
    "contact_threshold_n", "edge_drop_mm", "debounce_n", "over_force_n",
    "descend_speed_mmps", "slide_speed_mmps", "max_descend_mm",
    "max_slide_mm", "motion_timeout_s", "lift_height_mm",
    "target_force_n", "drop_limit_mm",
}


def _require_object(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def decode_scan_config_patch(config_json):
    config_json = _require_object(config_json, "config")
    unknown = set(config_json) - ALLOWED_CONFIG_KEYS
    if unknown:
        raise ValueError("unknown config key(s): " + ", ".join(sorted(unknown)))

    result = {}
    direct = {
        "contact_threshold_n": ("contact_threshold_n", "contact_threshold_set"),
        "debounce_n": ("debounce_n", "debounce_set"),
        "over_force_n": ("over_force_n", "over_force_set"),
        "motion_timeout_s": ("motion_timeout_s", "motion_timeout_set"),
        "target_force_n": ("target_force_n", "target_force_set"),
    }
    distance = {
        "edge_drop_mm": ("edge_drop_m", "edge_drop_set"),
        "max_descend_mm": ("max_descend_m", "max_descend_set"),
        "max_slide_mm": ("max_slide_m", "max_slide_set"),
        "lift_height_mm": ("lift_height_m", "lift_height_set"),
        "drop_limit_mm": ("drop_limit_m", "drop_limit_set"),
    }
    speed = {
        "descend_speed_mmps": ("descend_speed_mps", "descend_speed_set"),
        "slide_speed_mmps": ("slide_speed_mps", "slide_speed_set"),
    }

    for src, (dst, flag) in direct.items():
        if src in config_json:
            result[dst] = config_json[src]
            result[flag] = True
    for src, (dst, flag) in distance.items():
        if src in config_json:
            result[dst] = millimeters_to_meters(config_json[src])
            result[flag] = True
    for src, (dst, flag) in speed.items():
        if src in config_json:
            result[dst] = millimeters_per_second_to_meters_per_second(config_json[src])
            result[flag] = True
    return result


def decode_scan_start(message):
    payload = _require_object(message["payload"], "payload")
    override = payload.get("config_override")
    if override is None:
        return {"request_id": message["request_id"], "use_override": False, "config_override": {}}
    return {
        "request_id": message["request_id"],
        "use_override": True,
        "config_override": decode_scan_config_patch(override),
    }


def decode_scan_stop(message):
    payload = _require_object(message["payload"], "payload")
    detail = payload.get("detail", "")
    if not isinstance(detail, str):
        raise ValueError("payload.detail must be a string")
    return {
        "request_id": message["request_id"],
        "requester": "mqtt_bridge",
        "reason": STOP_REQUESTED,
        "detail": detail,
    }


def decode_scan_home(message):
    _require_object(message["payload"], "payload")
    return {"request_id": message["request_id"]}


def decode_scan_resume(message):
    _require_object(message["payload"], "payload")
    scan_id = message.get("scan_id", "")
    if not isinstance(scan_id, str):
        raise ValueError("scan_id must be a string")
    return {"request_id": message["request_id"], "scan_id": scan_id}


def decode_scan_set_config(message):
    return {
        "request_id": message["request_id"],
        "config": decode_scan_config_patch(message["payload"]),
    }


def decode_safety_reset(message):
    payload = _require_object(message["payload"], "payload")
    detail = payload.get("detail", "")
    if not isinstance(detail, str):
        raise ValueError("payload.detail must be a string")
    return {"request_id": message["request_id"], "detail": detail}


def decode_web_heartbeat(message):
    message = _require_object(message, "heartbeat")
    required = ("schema_version", "session_id", "seq", "timestamp_ms")
    missing = [key for key in required if key not in message]
    if missing:
        raise ValueError("missing heartbeat field(s): " + ", ".join(missing))
    if message["schema_version"] != "0.1":
        raise ValueError("unsupported schema_version")
    if not isinstance(message["session_id"], str):
        raise ValueError("session_id must be a string")
    if not isinstance(message["seq"], int) or isinstance(message["seq"], bool):
        raise ValueError("seq must be an integer")
    if not isinstance(message["timestamp_ms"], int) or isinstance(message["timestamp_ms"], bool):
        raise ValueError("timestamp_ms must be an integer")
    return {
        "session_id": message["session_id"],
        "seq": message["seq"],
        "timestamp_ms": message["timestamp_ms"],
    }


def decode_web_connection(message):
    message = _require_object(message, "connection")
    required = ("schema_version", "connected", "timestamp_ms")
    missing = [key for key in required if key not in message]
    if missing:
        raise ValueError("missing connection field(s): " + ", ".join(missing))
    if message["schema_version"] != "0.1":
        raise ValueError("unsupported schema_version")
    if not isinstance(message["connected"], bool):
        raise ValueError("connected must be a boolean")
    if not isinstance(message["timestamp_ms"], int) or isinstance(message["timestamp_ms"], bool):
        raise ValueError("timestamp_ms must be an integer")
    return {"connected": message["connected"], "timestamp_ms": message["timestamp_ms"]}
