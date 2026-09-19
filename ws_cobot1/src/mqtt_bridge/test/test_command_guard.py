"""command_guard tests."""

from mqtt_bridge.command_guard import CommandGuard, REASON_DUPLICATE_REQUEST, REASON_INVALID_REQUEST

RID1 = "3f2b8c1e-6a4d-4e0b-9a53-1c7d2f0e9b11"
RID2 = "0a1b2c3d-1111-4222-8333-444455556666"


def command(rid=RID1, ts=10_000):
    return {"schema_version": "0.1", "request_id": rid, "timestamp_ms": ts, "payload": {}}


def test_valid_command():
    assert CommandGuard().validate("cmd/scan/start", command(), 10_000).accepted


def test_duplicate_rejected():
    guard = CommandGuard()
    assert guard.validate("cmd/scan/start", command(), 10_000).accepted
    second = guard.validate("cmd/scan/start", command(), 10_000)
    assert not second.accepted
    assert second.reason_code == REASON_DUPLICATE_REQUEST


def test_expired_start_rejected_but_stop_allowed():
    start = CommandGuard(cmd_expiry_s=5.0).validate(
        "cmd/scan/start", command(RID1, 1_000), 10_000
    )
    stop = CommandGuard(cmd_expiry_s=5.0).validate(
        "cmd/scan/stop", command(RID2, 1_000), 10_000
    )
    assert not start.accepted
    assert start.reason_code == REASON_INVALID_REQUEST
    assert stop.accepted


def test_uuid_v4_required():
    result = CommandGuard().validate(
        "cmd/scan/start",
        {"schema_version": "0.1", "request_id": "request-1", "timestamp_ms": 10_000, "payload": {}},
        10_000,
    )
    assert not result.accepted
    assert result.reason_code == REASON_INVALID_REQUEST
