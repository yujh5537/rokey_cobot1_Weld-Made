"""이름 표가 표에 없는 값을 만났을 때 (#90, 계약 v0.1.22).

`test_encoders.py` 가 아니라 따로 둔다 — #161 이 같은 파일의 import 블록과 끝에
`robot/status` 6 필드 시험을 더해서, 같은 자리에 쓰면 머지할 때 충돌한다.
다루는 주제도 다르다: 여기는 **값 -> 이름 번역**만 본다.
"""

import json

from mqtt_bridge.encoders import (
    ROBOT_OPERATION_NAMES, encode_command_ack, encode_reason_name,
    encode_robot_operation, encode_robot_sample,
)


def config():
    """encode_command_ack 의 applied 에 실리는 최소 설정. 계약 4장 예시 값이다."""
    return {
        "contact_threshold_n": 4.0, "edge_drop_m": 0.0005,
        "debounce_n": 3, "debounce_set": True, "over_force_n": 30.0,
        "descend_speed_mps": 0.005, "slide_speed_mps": 0.01,
        "max_descend_m": 0.08, "max_slide_m": 0.15,
        "motion_timeout_s": 30.0, "lift_height_m": 0.05,
        "target_force_n": 5.0, "drop_limit_m": 0.005,
    }


def sample(operation):
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
    assert encode_robot_sample(sample(5), 1002)["operation"] == "WELD_PATH"


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
    out = encode_robot_sample(sample(7), 1001)
    assert out["operation"] == "UNKNOWN_7"
    assert out["pose"]["x_mm"] == 100.0
    assert out["wrench"]["fz_n"] == -1.0
    json.dumps(out, allow_nan=False)
