"""mqtt_bridge boundary helper tests."""

import math
from types import SimpleNamespace

import pytest

from contact_scan_interfaces.msg import ScanConfig
from mqtt_bridge.encoders import encode_scan_config
from mqtt_bridge.mqtt_bridge import (
    _safe_ros_callback, _scan_config_dict, _scan_config_from_patch,
    _scan_result_dedup_key, epoch_ms_to_time, prefixed_topic,
    serialize_json, strip_topic_prefix,
)


def test_topic_prefix_helpers():
    assert prefixed_topic("", "scan/state") == "scan/state"
    assert prefixed_topic("/cell-a/", "/scan/state") == "cell-a/scan/state"
    assert strip_topic_prefix("cell-a", "cell-a/cmd/scan/start") == "cmd/scan/start"


def test_strict_json_rejects_nan():
    with pytest.raises(ValueError):
        serialize_json({"x": math.nan})


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
