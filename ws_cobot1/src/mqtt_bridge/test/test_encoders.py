"""encoder tests."""

import json
import math

from mqtt_bridge.encoders import (
    ROBOT_OPERATION_NAMES,
    encode_command_ack, encode_contact_event, encode_reason_name,
    encode_robot_operation, encode_robot_sample, encode_ros_connection,
    encode_ros_heartbeat, encode_scan_config, encode_scan_result,
)


def config():
    return {
        "contact_threshold_n": 4.0, "edge_drop_m": 0.0005,
        "debounce_n": 3, "debounce_set": True, "over_force_n": 30.0,
        "descend_speed_mps": 0.005, "slide_speed_mps": 0.01,
        "max_descend_m": 0.08, "max_slide_m": 0.15,
        "motion_timeout_s": 30.0, "lift_height_m": 0.05,
        "target_force_n": 5.0, "drop_limit_m": 0.005,
    }


def point(x, y, z):
    return {"x": x, "y": y, "z": z}


def segment(a, b, length):
    return {"start": a, "end": b, "length": length, "valid": True}


def scan_result():
    v = [
        point(0, 0, .05), point(.1, 0, .05), point(.1, .06, .05), point(0, .06, .05),
        point(0, 0, 0), point(.1, 0, 0), point(.1, .06, 0), point(0, .06, 0),
    ]
    e = [
        segment(v[0], v[1], .1), segment(v[1], v[2], .06),
        segment(v[2], v[3], .1), segment(v[3], v[0], .06),
        segment(v[4], v[5], .1), segment(v[5], v[6], .06),
        segment(v[6], v[7], .1), segment(v[7], v[4], .06),
        segment(v[0], v[4], .05), segment(v[1], v[5], .05),
        segment(v[2], v[6], .05), segment(v[3], v[7], .05),
    ]
    return {
        "scan_id": "scan", "stamp": {"sec": 1, "nanosec": 0},
        "success": True, "reason_code": 0, "detail": "", "frame_id": "workpiece_fixture",
        "z_top": .05, "z_top_valid": True,
        "x_pos": .1, "x_pos_valid": True, "x_neg": 0.0, "x_neg_valid": True,
        "y_pos": .06, "y_pos_valid": True, "y_neg": 0.0, "y_neg_valid": True,
        "width": .1, "length": .06, "height": .05, "dims_valid": True,
        "support_z": 0.0, "support_z_valid": True,
        "vertices": v, "box_valid": True, "edges": e, "path_candidates": e[:4],
        "config": config(),
        "started_at": {"sec": 1, "nanosec": 0},
        "finished_at": {"sec": 2, "nanosec": 0},
    }


def test_robot_sample_units_and_enum():
    sample = {
        "sample_id": 1, "frame_id": "base_link",
        "pose": {"x": .1, "y": 0.0, "z": .05, "qx": 0.0, "qy": 0.0, "qz": 0.0, "qw": 1.0},
        "pose_stamp": {"sec": 1, "nanosec": 20_000_000},
        "wrench": {"fx": 0.0, "fy": 0.0, "fz": -1.0, "tx": 0.0, "ty": 0.0, "tz": 0.0},
        "force_stamp": {"sec": 1, "nanosec": 24_000_000},
        "valid": True, "motion_id": 7, "operation": 3,
    }
    out = encode_robot_sample(sample, 1030)
    assert out["pose"]["x_mm"] == 100.0
    assert out["operation"] == "SLIDE"


def test_contact_nan_becomes_null():
    event = {
        "event_id": 1, "scan_id": "scan", "motion_id": 7, "sample_id": 1,
        "type": 0, "source": "robot_force", "frame_id": "base_link",
        "pose": {"x": 0.0, "y": 0.0, "z": .05, "qx": 0.0, "qy": 0.0, "qz": 0.0, "qw": 1.0},
        "wrench": {"fx": 0.0, "fy": 0.0, "fz": -1.0, "tx": 0.0, "ty": 0.0, "tz": 0.0},
        "pose_stamp": {"sec": 1, "nanosec": 0},
        "force_stamp": {"sec": 1, "nanosec": 0},
        "detect_stamp": {"sec": 1, "nanosec": 0},
        "force_delta_n": 1.0, "z_drop_m": math.nan,
        "z_drop_valid": False, "debounce_count": 3,
    }
    out = encode_contact_event(event, 1000)
    assert out["z_drop_mm"] is None
    json.dumps(out, allow_nan=False)


def test_scan_result_success_and_failure():
    ok = encode_scan_result(scan_result(), 2000)
    assert ok["width_mm"] == 100.0
    assert len(ok["vertices"]) == 8
    assert len(ok["edges"]) == 12
    assert len(ok["path_candidates"]) == 4

    bad = scan_result()
    bad["success"] = False
    bad["reason_code"] = 301
    bad["x_neg"] = math.nan
    bad["x_neg_valid"] = False
    bad["width"] = bad["length"] = bad["height"] = math.nan
    bad["dims_valid"] = False
    bad["box_valid"] = False
    out = encode_scan_result(bad, 2001)
    assert out["reason"] == "NO_EDGE"
    assert out["x_neg_mm"] is None
    assert out["vertices"] is None
    json.dumps(out, allow_nan=False)


def test_config_ack_heartbeat_connection():
    cfg = encode_scan_config(config())
    assert cfg["slide_speed_mmps"] == 10.0
    ack = encode_command_ack("id", True, 0, "", 10, config())
    assert ack["reason"] == "OK"
    assert ack["applied"]["edge_drop_mm"] == 0.5
    assert encode_ros_heartbeat(3, 11)["seq"] == 3
    assert encode_ros_connection(True, 12)["connected"] is True


# --- 이름 표 (#90, 계약 v0.1.22) ---------------------------------------------

def _weld_sample(operation):
    return {
        "sample_id": 1, "frame_id": "base_link",
        "pose": {"x": .1, "y": 0.0, "z": .05, "qx": 0.0, "qy": 0.0, "qz": 0.0, "qw": 1.0},
        "pose_stamp": {"sec": 1, "nanosec": 20_000_000},
        "wrench": {"fx": 0.0, "fy": 0.0, "fz": -1.0, "tx": 0.0, "ty": 0.0, "tz": 0.0},
        "force_stamp": {"sec": 1, "nanosec": 24_000_000},
        "valid": True, "motion_id": 8, "operation": operation,
    }


def test_weld_path_operation_has_a_name():
    """phase 2 의 OP_WELD_PATH=5. 이 이름이 없으면 용접 중 robot/sample 이 통째로 버려진다."""
    assert ROBOT_OPERATION_NAMES[5] == "WELD_PATH"
    assert encode_robot_operation(5) == "WELD_PATH"


def test_weld_path_operation_encodes_in_a_sample():
    """#191 이 싣는 operation=5 가 실제 robot/sample JSON 에서 이름으로 나온다."""
    assert encode_robot_sample(_weld_sample(5), 1002)["operation"] == "WELD_PATH"


def test_unknown_value_becomes_unknown_name_instead_of_raising():
    """표에 없는 값에서 멈추지 않는다. 이름을 모르는 것보다 소식이 끊기는 것이 나쁘다 (#90)."""
    assert encode_robot_operation(7) == "UNKNOWN_7"
    assert encode_reason_name(999) == "UNKNOWN_999"


def test_unknown_reason_still_leaves_the_number_usable():
    """이름을 몰라도 숫자는 그대로 간다. 웹은 reason_code 로 판단할 수 있다."""
    ack = encode_command_ack("id", False, 999, "모르는 사유", 10, config())
    assert ack["reason_code"] == 999
    assert ack["reason"] == "UNKNOWN_999"
    json.dumps(ack, allow_nan=False)


def test_robot_sample_survives_an_unknown_operation():
    """모르는 operation 하나 때문에 TCP 위치 · 힘이 사라지지 않는다."""
    out = encode_robot_sample(_weld_sample(7), 1001)
    assert out["operation"] == "UNKNOWN_7"
    assert out["pose"]["x_mm"] == 100.0
    assert out["wrench"]["fz_n"] == -1.0
    json.dumps(out, allow_nan=False)
