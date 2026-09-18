"""계약 상수의 순수 Python 사본 (docs/contracts/ros-interfaces.md 3.4절 · 6.1절).

rclpy · contact_scan_interfaces 를 import 하지 않는다. ROS 를 source 하지 않은 셸에서도
상태 기계와 그 테스트가 돌아야 하기 때문이다. 값이 msg 상수와 같은지는
test/test_contract_match.py 가 colcon test · CI 에서 확인한다.

번호를 바꾸거나 추가할 때는 계약 문서 · contact_scan_interfaces · 이 파일을 같이 고친다.
"""

from enum import IntEnum


class Phase(IntEnum):
    """ScanState.PHASE_* (3.4절)."""

    IDLE = 0
    PREPARING = 1
    TOP_SEARCH = 2
    EDGE_SEARCH = 3
    GEOMETRY = 4
    DONE = 5
    ERROR = 6
    STOPPING = 7
    STOPPED = 8
    HOMING = 9
    RESUMING = 10


class Direction(IntEnum):
    """ScanState.DIR_* (3.4절). ExecuteMotion.DIR_* 와 같은 값."""

    NONE = 0
    POS_X = 1
    NEG_X = 2
    POS_Y = 3
    NEG_Y = 4


class Reason(IntEnum):
    """ReasonCode (6.1절). v0.1 이후 번호는 추가만 하고 바꾸지 않는다."""

    OK = 0
    # 1xx 요청 거절
    BUSY = 100
    INVALID_REQUEST = 101
    INVALID_VALUE = 102
    SAFETY_LATCHED = 103
    ROBOT_DISCONNECTED = 104
    NO_RESUMABLE_SCAN = 105
    DUPLICATE_REQUEST = 106
    NOT_SUPPORTED = 107
    PARAM_SET_FAILED = 108
    # 2xx 동작 종료
    STOP_REQUESTED = 200
    CANCELED = 201
    MAX_DISTANCE = 202
    TIMEOUT = 203
    ROBOT_ERROR = 204
    DROP_LIMIT = 205
    # 3xx 접촉 · 툴
    NO_CONTACT = 300
    NO_EDGE = 301
    TOOL_REG_SUSPECT = 302
    TARE_FAILED = 303
    ROBOT_MOVING = 304
    TARE_UNSTABLE = 305
    TARE_TIMEOUT = 306
    NO_SAMPLE = 307
    # 4xx 안전
    OVER_FORCE = 400
    OVER_SPEED = 401
    OUT_OF_WORKSPACE = 402
    SAMPLE_STALE = 403
    ROBOT_STATUS_LOST = 404
    HB_EXPIRED = 405
    CONDITION_ACTIVE = 406
    # 5xx 형상
    INVALID_SHAPE = 500
    INSUFFICIENT_POINTS = 501
