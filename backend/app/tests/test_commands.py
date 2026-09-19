import sys
from pathlib import Path

import pytest


APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

import main


@pytest.fixture(autouse=True)
def clear_command_state():
    """각 테스트가 서로 영향을 주지 않도록 명령 상태를 초기화한다."""
    with main.command_lock:
        main.pending_commands.clear()

    yield

    with main.command_lock:
        main.pending_commands.clear()


def make_state(request_id: str, topic: str = "cmd/scan/start"):
    state = {
        "request_id": request_id,
        "command_topic": topic,
        "status": "PUBLISHED",
        "created_at_ms": 1000,
        "updated_at_ms": 1000,
        "request": {
            "schema_version": "0.1",
            "request_id": request_id,
            "timestamp_ms": 1000,
            "payload": {},
        },
    }

    with main.command_lock:
        main.pending_commands[request_id] = state


def test_ack_accepted_changes_to_accepted():
    request_id = "req-accepted"
    make_state(request_id)

    result = main.update_command_from_ack({
        "schema_version": "0.1",
        "request_id": request_id,
        "accepted": True,
        "reason_code": 0,
        "reason": "OK",
        "detail": "",
        "published_at_ms": 1100,
    })

    assert result["status"] == "ACCEPTED"
    assert result["request_id"] == request_id


def test_ack_rejected_changes_to_rejected():
    request_id = "req-rejected"
    make_state(request_id)

    result = main.update_command_from_ack({
        "schema_version": "0.1",
        "request_id": request_id,
        "accepted": False,
        "reason_code": 107,
        "reason": "NOT_SUPPORTED",
        "detail": "start server unavailable",
        "published_at_ms": 1100,
    })

    assert result["status"] == "REJECTED"
    assert result["ack"]["accepted"] is False


def test_command_result_success_changes_to_succeeded():
    request_id = "req-success"
    make_state(request_id)

    main.update_command_from_ack({
        "request_id": request_id,
        "accepted": True,
    })

    result = main.update_command_from_result({
        "schema_version": "0.1",
        "request_id": request_id,
        "scan_id": "scan-001",
        "success": True,
        "reason_code": 0,
        "reason": "OK",
        "detail": "",
        "published_at_ms": 1200,
    })

    assert result["status"] == "SUCCEEDED"
    assert result["result"]["success"] is True


def test_command_result_failure_changes_to_failed():
    request_id = "req-failed"
    make_state(request_id)

    main.update_command_from_ack({
        "request_id": request_id,
        "accepted": True,
    })

    result = main.update_command_from_result({
        "schema_version": "0.1",
        "request_id": request_id,
        "scan_id": "scan-002",
        "success": False,
        "reason_code": 301,
        "reason": "NO_EDGE",
        "detail": "direction=NEG_X",
        "published_at_ms": 1200,
    })

    assert result["status"] == "FAILED"
    assert result["result"]["success"] is False


@pytest.mark.parametrize(
    "topic",
    [
        "cmd/scan/set_config",
        "cmd/safety/reset",
    ],
)
def test_service_ack_is_final_success(topic):
    request_id = f"req-{topic.replace('/', '-')}"
    make_state(request_id, topic)

    result = main.update_command_from_ack({
        "schema_version": "0.1",
        "request_id": request_id,
        "accepted": True,
        "reason_code": 0,
        "reason": "OK",
        "detail": "",
        "published_at_ms": 1100,
    })

    assert result["status"] == "SUCCEEDED"


def test_two_published_commands_get_different_request_ids(monkeypatch):
    class FakePublishInfo:
        rc = 0

    def fake_publish(*args, **kwargs):
        return FakePublishInfo()

    monkeypatch.setattr(main.mqtt_client, "publish", fake_publish)

    request = main.CommandRequest(payload={})

    first = main.publish_command(
        "cmd/scan/start",
        request,
    )

    second = main.publish_command(
        "cmd/scan/start",
        request,
    )

    assert first["status"] == "PUBLISHED"
    assert second["status"] == "PUBLISHED"
    assert first["request_id"] != second["request_id"]
