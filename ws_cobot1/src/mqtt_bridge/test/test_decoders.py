"""decoder tests."""

import pytest

from mqtt_bridge.decoders import (
    decode_safety_reset, decode_scan_config_patch, decode_scan_home,
    decode_scan_resume, decode_scan_set_config, decode_scan_start,
    decode_scan_stop, decode_web_connection, decode_web_heartbeat,
)

RID = "3f2b8c1e-6a4d-4e0b-9a53-1c7d2f0e9b11"


def command(payload=None):
    return {
        "schema_version": "0.1",
        "request_id": RID,
        "timestamp_ms": 1789720000123,
        "payload": {} if payload is None else payload,
    }


def test_start_and_config_override():
    assert decode_scan_start(command())["use_override"] is False
    result = decode_scan_start(command({"config_override": {
        "slide_speed_mmps": 10.0,
        "edge_drop_mm": 0.5,
    }}))
    assert result["use_override"] is True
    assert result["config_override"] == {
        "edge_drop_m": 0.0005,
        "edge_drop_set": True,
        "slide_speed_mps": 0.01,
        "slide_speed_set": True,
    }


def test_stop_home_resume_set_config_reset():
    assert decode_scan_stop(command({"detail": "operator stop"}))["reason"] == 200
    assert decode_scan_home(command()) == {"request_id": RID}
    assert decode_scan_resume(command())["scan_id"] == ""
    cfg = decode_scan_set_config(command({"max_slide_mm": 150.0}))
    assert cfg["config"]["max_slide_m"] == 0.15
    assert decode_safety_reset(command({"detail": "checked"}))["detail"] == "checked"


def test_unknown_config_key_rejected():
    with pytest.raises(ValueError):
        decode_scan_config_patch({"unknown": 1})


def test_web_heartbeat_and_connection():
    hb = decode_web_heartbeat({
        "schema_version": "0.1", "session_id": "s", "seq": 7, "timestamp_ms": 10,
    })
    conn = decode_web_connection({
        "schema_version": "0.1", "connected": True, "timestamp_ms": 11,
    })
    assert hb["seq"] == 7
    assert conn["connected"] is True
