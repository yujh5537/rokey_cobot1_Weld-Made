"""mqtt_bridge boundary helper tests."""

import math
from types import SimpleNamespace

import pytest

from contact_scan_interfaces.msg import ReasonCode, ScanConfig, ScanLog, ScanState
from mqtt_bridge.encoders import encode_scan_config
from mqtt_bridge.mqtt_bridge import (
    MqttBridge, _safe_ros_callback, _scan_config_dict, _scan_config_from_patch,
    _scan_result_dedup_key, epoch_ms_to_time, prefixed_topic,
    serialize_json, strip_topic_prefix,
)

def test_topic_prefix_helpers():
    assert prefixed_topic("", "scan/state") == "scan/state"
    assert prefixed_topic("/cell-a/", "/scan/state") == "cell-a/scan/state"
    assert strip_topic_prefix("cell-a", "cell-a/cmd/scan/start") == "cmd/scan/start"

def _stop_test_bridge():
    acks = []
    command_results = []
    published = []

    bridge = SimpleNamespace(
        _pending_stop=[],
        _last_scan_id="",
        _scan_phase=ScanState.PHASE_IDLE,
        _last_error_scan_id="",
        _last_error_code=ReasonCode.ROBOT_ERROR,
        _last_error_detail="",
    )

    bridge._ack = lambda *args: acks.append(args)
    bridge._command_result = lambda *args: command_results.append(args)
    bridge._publish = (
        lambda topic, message, qos, retain:
        published.append((topic, message, qos, retain))
    )

    bridge._stop_error = (
        lambda scan_id:
        MqttBridge._stop_error(bridge, scan_id)
    )

    bridge._finish_stops = (
        lambda scan_id, success, reason_code, detail:
        MqttBridge._finish_stops(
            bridge,
            scan_id,
            success,
            reason_code,
            detail,
        )
    )

    return bridge, acks, command_results, published

def test_strict_json_rejects_nan():
    with pytest.raises(ValueError):
        serialize_json({"x": math.nan})


def test_joint_snapshot_validation_and_rate_limit(monkeypatch):
    published = []
    warnings = []
    bridge = SimpleNamespace(
        _last_joint=0.0,
        _last_gripper_joint=0.0,
        _joint_period=0.05,
        _joint_state_topic="/dsr01/joint_states",
        get_logger=lambda: SimpleNamespace(warning=warnings.append),
        _publish=lambda *args: published.append(args),
    )
    monkeypatch.setattr("mqtt_bridge.mqtt_bridge.time.monotonic", lambda: 10.0)
    header = SimpleNamespace(stamp=SimpleNamespace(sec=3, nanosec=4_000_000))

    for names, positions in [
        (["joint_1"], []),
        (["joint_1"], [math.nan]),
        (["joint_1"], [math.inf]),
        (["joint_1", "joint_1"], [0.0, 1.0]),
    ]:
        msg = SimpleNamespace(name=names, position=positions, header=header)
        MqttBridge._on_joint_state(bridge, msg)
        assert not published
        assert bridge._last_joint == 0.0
        assert bridge._last_gripper_joint == 0.0

    assert len(warnings) == 4

    # joint_state_broadcaster: M0609 six-axis source.
    names = [f"joint_{i}" for i in range(6, 0, -1)]
    positions = [i / 10 for i in range(6)]
    msg = SimpleNamespace(name=names, position=positions, header=header)
    MqttBridge._on_joint_state(bridge, msg)

    topic, payload, qos, retain = published[0]
    assert (topic, qos, retain) == ("robot/joints", 0, False)
    assert payload["names"] == [f"joint_{i}" for i in range(1, 7)]
    assert payload["positions_rad"] == [0.5, 0.4, 0.3, 0.2, 0.1, 0.0]
    assert payload["stamp_ms"] == 3004

    # Same arm source inside the rate window is dropped.
    MqttBridge._on_joint_state(bridge, msg)
    assert len(published) == 1

    # joint_state_publisher: merged M0609 + RG2 snapshot.
    merged_names = [
        "joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "joint_6",
        "rg2_finger_joint",
        "rg2_left_inner_knuckle_joint",
        "rg2_left_inner_finger_joint",
        "rg2_right_outer_knuckle_joint",
        "rg2_right_inner_knuckle_joint",
        "rg2_right_inner_finger_joint",
    ]
    merged_positions = [0.0] * 6 + [0.1, -0.1, 0.1, -0.1, -0.1, 0.1]
    merged = SimpleNamespace(
        name=merged_names,
        position=merged_positions,
        header=header,
    )
    MqttBridge._on_joint_state(bridge, merged)

    topic, payload, qos, retain = published[1]
    assert (topic, qos, retain) == ("robot/gripper_joints", 0, False)
    assert payload["names"] == merged_names[6:]
    assert payload["positions_rad"] == merged_positions[6:]
    assert payload["frame_id"] == "rg2_base_link"


def test_epoch_ms_to_time():
    stamp = epoch_ms_to_time(1789720002431)
    assert stamp.sec == 1789720002
    assert stamp.nanosec == 431000000


def test_scan_config_patch_sets_only_sent_fields():
    config = _scan_config_from_patch({"slide_speed_mps": 0.01, "slide_speed_set": True})
    assert config.slide_speed_mps == 0.01
    assert config.slide_speed_set is True
    assert config.edge_drop_set is False

def test_unknown_debounce_is_encoded_as_null():
    config = ScanConfig()
    config.debounce_n = 0
    config.debounce_set = False

    out = encode_scan_config(_scan_config_dict(config))
    assert out["debounce_n"] is None

    config.debounce_set = True

    out = encode_scan_config(_scan_config_dict(config))
    assert out["debounce_n"] == 0

@pytest.mark.parametrize(
    ("phase", "scan_id"),
    [
        (ScanState.PHASE_IDLE, ""),
        (ScanState.PHASE_DONE, "scan-1"),
        (ScanState.PHASE_ERROR, "scan-1"),
        (ScanState.PHASE_STOPPED, "scan-1"),
    ],
)
def test_accepted_stop_in_terminal_phase_finishes_immediately(phase, scan_id):
    bridge, acks, command_results, _published = _stop_test_bridge()

    response = SimpleNamespace(
        accepted=True,
        reason_code=ReasonCode.OK,
        detail="멈출 작업이 없다",
    )
    future = SimpleNamespace(result=lambda: response)

    MqttBridge._on_stop_response(
        bridge,
        "req-1",
        phase,
        scan_id,
        future,
    )

    assert acks == [
        ("req-1", True, ReasonCode.OK, "멈출 작업이 없다")
    ]
    assert command_results == [
        (
            "req-1",
            scan_id,
            True,
            ReasonCode.STOP_REQUESTED,
            "멈출 작업이 없다",
        )
    ]
    assert bridge._pending_stop == []


def test_stopped_state_finishes_only_matching_scan():
    bridge, _acks, command_results, _published = _stop_test_bridge()

    bridge._pending_stop = [
        ("req-a", "scan-a"),
        ("req-b", "scan-b"),
    ]

    state = ScanState()
    state.scan_id = "scan-a"
    state.phase = ScanState.PHASE_STOPPED

    MqttBridge._on_scan_state(bridge, state)

    assert command_results == [
        (
            "req-a",
            "scan-a",
            True,
            ReasonCode.STOP_REQUESTED,
            "",
        )
    ]
    assert bridge._pending_stop == [
        ("req-b", "scan-b"),
    ]


def test_error_state_finishes_stop_with_latest_matching_error():
    bridge, _acks, command_results, published = _stop_test_bridge()

    bridge._pending_stop = [
        ("req-1", "scan-1"),
    ]

    log = ScanLog()
    log.scan_id = "scan-1"
    log.level = ScanLog.LEVEL_ERROR
    log.phase = ScanState.PHASE_STOPPING
    log.code = ReasonCode.ROBOT_STATUS_LOST
    log.message = "정지 완료 확인 실패"

    MqttBridge._on_scan_log(bridge, log)

    state = ScanState()
    state.scan_id = "scan-1"
    state.phase = ScanState.PHASE_ERROR

    MqttBridge._on_scan_state(bridge, state)

    assert command_results == [
        (
            "req-1",
            "scan-1",
            False,
            ReasonCode.ROBOT_STATUS_LOST,
            "정지 완료 확인 실패",
        )
    ]
    assert bridge._pending_stop == []

    assert [item[0] for item in published] == [
        "scan/log",
        "scan/state",
    ]


def test_error_state_falls_back_to_robot_error_without_matching_log():
    bridge, _acks, command_results, _published = _stop_test_bridge()

    bridge._pending_stop = [
        ("req-1", "scan-1"),
    ]

    state = ScanState()
    state.scan_id = "scan-1"
    state.phase = ScanState.PHASE_ERROR

    MqttBridge._on_scan_state(bridge, state)

    assert command_results == [
        (
            "req-1",
            "scan-1",
            False,
            ReasonCode.ROBOT_ERROR,
            "",
        )
    ]
    assert bridge._pending_stop == []


def test_active_stop_response_closes_if_scan_already_errored():
    bridge, acks, command_results, _published = _stop_test_bridge()

    bridge._last_scan_id = "scan-1"
    bridge._scan_phase = ScanState.PHASE_ERROR

    bridge._last_error_scan_id = "scan-1"
    bridge._last_error_code = ReasonCode.OVER_FORCE
    bridge._last_error_detail = "과대 외력"

    response = SimpleNamespace(
        accepted=True,
        reason_code=ReasonCode.OK,
        detail="",
    )
    future = SimpleNamespace(result=lambda: response)

    MqttBridge._on_stop_response(
        bridge,
        "req-1",
        ScanState.PHASE_EDGE_SEARCH,
        "scan-1",
        future,
    )

    assert acks == [
        ("req-1", True, ReasonCode.OK, "")
    ]
    assert command_results == [
        (
            "req-1",
            "scan-1",
            False,
            ReasonCode.OVER_FORCE,
            "과대 외력",
        )
    ]
    assert bridge._pending_stop == []

def test_safe_ros_callback_contains_exceptions():
    class Logger:
        def __init__(self):
            self.errors = []

        def error(self, message):
            self.errors.append(message)

    logger = Logger()

    def boom(_msg):
        raise ValueError("unknown enum")

    wrapped = _safe_ros_callback(logger, "/robot/status", boom)
    assert wrapped(object()) is None
    assert logger.errors == ["/robot/status callback failed: unknown enum"]


def test_scan_result_dedup_key_allows_resume_result_with_same_scan_id():
    first = SimpleNamespace(
        scan_id="20260919-000000-abcd",
        stamp=SimpleNamespace(sec=10, nanosec=100),
    )
    resumed = SimpleNamespace(
        scan_id="20260919-000000-abcd",
        stamp=SimpleNamespace(sec=20, nanosec=200),
    )
    duplicate = SimpleNamespace(
        scan_id="20260919-000000-abcd",
        stamp=SimpleNamespace(sec=10, nanosec=100),
    )

    assert _scan_result_dedup_key(first) != _scan_result_dedup_key(resumed)
    assert _scan_result_dedup_key(first) == _scan_result_dedup_key(duplicate)
