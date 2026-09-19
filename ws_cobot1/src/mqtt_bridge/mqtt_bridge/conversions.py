"""mqtt_bridge에서 사용하는 공통 단위·시간 변환 함수."""

import math


def meters_to_mm(value_m: float) -> float:
    """meter를 millimeter로 바꾼다."""
    return value_m * 1000.0


def meters_per_second_to_mm_per_second(value_mps: float) -> float:
    """m/s를 mm/s로 바꾼다."""
    return value_mps * 1000.0


def millimeters_to_meters(value_mm: float) -> float:
    """millimeter를 meter로 바꾼다."""
    return value_mm / 1000.0


def millimeters_per_second_to_meters_per_second(value_mmps: float) -> float:
    """mm/s를 m/s로 바꾼다."""
    return value_mmps / 1000.0


def ros_time_to_epoch_ms(sec: int, nanosec: int) -> int:
    """ROS Time(sec, nanosec)을 epoch millisecond 정수로 바꾼다."""
    return sec * 1000 + nanosec // 1_000_000


def non_finite_to_none(value):
    """NaN/Infinity를 JSON null에 대응하는 None으로 바꾼다."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def value_or_none(value, valid: bool):
    """valid=False이면 값 대신 None을 돌려준다."""
    if not valid:
        return None
    return non_finite_to_none(value)


def strip_enum_prefix(enum_name: str, prefix: str) -> str:
    """enum 이름 앞의 고정 접두사를 제거한다."""
    if enum_name.startswith(prefix):
        return enum_name[len(prefix):]
    return enum_name
