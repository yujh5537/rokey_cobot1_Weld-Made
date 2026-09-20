"""MQTT 명령이 ROS로 전달 가능한지 검사한다."""

import time
import uuid
from collections import deque
from dataclasses import dataclass


REASON_OK = 0
REASON_INVALID_REQUEST = 101
REASON_DUPLICATE_REQUEST = 106

SCHEMA_VERSION = "0.1"
REQUIRED_FIELDS = (
    "schema_version",
    "request_id",
    "timestamp_ms",
    "payload",
)


@dataclass(frozen=True)
class GuardResult:
    """공통 명령 검증 결과."""

    accepted: bool
    reason_code: int
    reason: str
    detail: str = ""


def is_uuid4(value) -> bool:
    """문자열이 UUID v4인지 확인한다."""
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False
    return parsed.version == 4


class CommandGuard:
    """필수 필드·중복·만료를 순서대로 검사한다."""

    def __init__(self, dedup_cache_size: int = 100, cmd_expiry_s: float = 5.0):
        if dedup_cache_size < 1:
            raise ValueError("dedup_cache_size must be >= 1")
        if cmd_expiry_s < 0.0:
            raise ValueError("cmd_expiry_s must be >= 0")
        self._recent_request_ids = deque(maxlen=dedup_cache_size)
        self._cmd_expiry_ms = int(cmd_expiry_s * 1000)

    def validate(self, topic: str, message: dict, now_ms: int | None = None) -> GuardResult:
        """명령 하나를 검증한다."""
        if now_ms is None:
            now_ms = int(time.time() * 1000)

        if not isinstance(message, dict):
            return GuardResult(False, REASON_INVALID_REQUEST, "INVALID_REQUEST",
                               "command must be a JSON object")

        missing = [field for field in REQUIRED_FIELDS if field not in message]
        if missing:
            return GuardResult(
                False,
                REASON_INVALID_REQUEST,
                "INVALID_REQUEST",
                "missing required field(s): " + ", ".join(missing),
            )

        if message["schema_version"] != SCHEMA_VERSION:
            return GuardResult(False, REASON_INVALID_REQUEST, "INVALID_REQUEST",
                               "unsupported schema_version")

        request_id = message["request_id"]
        if not is_uuid4(request_id):
            return GuardResult(False, REASON_INVALID_REQUEST, "INVALID_REQUEST",
                               "request_id must be UUID v4")

        timestamp_ms = message["timestamp_ms"]
        if not isinstance(timestamp_ms, int) or isinstance(timestamp_ms, bool):
            return GuardResult(False, REASON_INVALID_REQUEST, "INVALID_REQUEST",
                               "timestamp_ms must be an integer")

        if not isinstance(message["payload"], dict):
            return GuardResult(False, REASON_INVALID_REQUEST, "INVALID_REQUEST",
                               "payload must be a JSON object")

        if request_id in self._recent_request_ids:
            return GuardResult(False, REASON_DUPLICATE_REQUEST, "DUPLICATE_REQUEST",
                               "request_id was already received")

        self._recent_request_ids.append(request_id)

        if topic == "cmd/scan/stop":
            return GuardResult(True, REASON_OK, "OK")

        if now_ms - timestamp_ms > self._cmd_expiry_ms:
            return GuardResult(False, REASON_INVALID_REQUEST, "INVALID_REQUEST",
                               "command expired")

        return GuardResult(True, REASON_OK, "OK")
