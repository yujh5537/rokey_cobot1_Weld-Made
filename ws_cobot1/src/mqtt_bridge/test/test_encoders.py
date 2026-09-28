"""encoder tests."""

import json
import math

from mqtt_bridge.encoders import (
    encode_command_ack, encode_contact_event, encode_robot_sample,
    encode_robot_status, encode_ros_connection, encode_ros_heartbeat, encode_scan_config,
    encode_scan_result,
)

NAN = float("nan")


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


def robot_status(**changes):
    """계약 3.2 (v0.1.21). SLIDE 누름 목표 6개를 포함한다."""
    return {
        "stamp": {"sec": 1, "nanosec": 0}, "connected": True, "moving": True,
        "error": False, "error_code": 0,
        "compliance_active": True, "force_ctrl_active": True,
        "motion_id": 7, "operation": 3, "detail": "",
        "slide_mode": "force", "slide_force_setpoint_n": 3.0,
        "slide_force_baseline_n": 5.3, "slide_force_estimate_n": 8.3,
        "step_press_lo_n": NAN, "step_press_hi_n": NAN,
        **changes,
    }


def test_robot_status_carries_the_three_force_mode_values():
    """설정 · 시작 기준 · 추정 합을 각각 싣는다. 웹이 셋을 구분할 수 있어야 한다."""
    out = encode_robot_status(robot_status(), 1030)
    assert out["slide_mode"] == "force"
    assert out["slide_force_setpoint_n"] == 3.0
    assert out["slide_force_baseline_n"] == 5.3
    assert out["slide_force_estimate_n"] == 8.3
    # step 전용 값은 force 모드에서 null 이다 (0 이 아니다)
    assert out["step_press_lo_n"] is None and out["step_press_hi_n"] is None
    assert json.dumps(out)      # NaN 이 그대로 새어 나가면 JSON 이 깨진다


def test_robot_status_in_step_mode_has_no_rel_values():
    """step 모드의 REL 세 값은 제어 목표가 아니다 → null. 대신 목표 누름 띠를 싣는다."""
    out = encode_robot_status(robot_status(
        slide_mode="step", slide_force_setpoint_n=NAN, slide_force_baseline_n=NAN,
        slide_force_estimate_n=NAN, step_press_lo_n=3.0, step_press_hi_n=7.0), 1030)
    assert out["slide_mode"] == "step"
    for key in ("slide_force_setpoint_n", "slide_force_baseline_n", "slide_force_estimate_n"):
        assert out[key] is None, key
    assert out["step_press_lo_n"] == 3.0 and out["step_press_hi_n"] == 7.0


def test_robot_status_unknown_baseline_is_null_not_zero():
    """기준선을 모르면 null 이다. 0 이면 '설정값 = 실제 누름'이라는 거짓이 된다 (규칙 4)."""
    out = encode_robot_status(robot_status(
        slide_force_baseline_n=NAN, slide_force_estimate_n=NAN), 1030)
    assert out["slide_force_setpoint_n"] == 3.0
    assert out["slide_force_baseline_n"] is None
    assert out["slide_force_estimate_n"] is None
