"""계약 상수의 순수 Python 사본 (docs/phase2/weld-ros-interfaces.md 3 · 5 · 6장, docs/contracts/ros-interfaces.md 6.1절).

rclpy · contact_scan_interfaces 를 import 하지 않는다. ROS 를 source 하지 않은 셸에서도 경로 계산 · 상태 기계와
그 테스트가 돌아야 하기 때문이다. 값이 msg 상수와 같은지는 test/test_contract_match.py 가 확인한다.

번호를 바꾸거나 추가할 때는 계약 문서 · contact_scan_interfaces · 이 파일을 같이 고친다.
"""

from enum import IntEnum

LINE_COUNT = 8       # WeldState.line_total · WeldResult.lines 의 길이
LINE_NONE = 255      # WeldState.LINE_NONE


class WeldPhase(IntEnum):
    """WeldState.PHASE_* (3.2절)."""

    IDLE = 0
    PREPARING = 1
    APPROACH = 2
    WELDING = 3
    RETREAT = 4
    DONE = 5
    ERROR = 6
    STOPPING = 7
    STOPPED = 8
    HOMING = 9


class LineStatus(IntEnum):
    """WeldLine.STATUS_* (3.3절)."""

    NOT_ATTEMPTED = 0
    DONE = 1
    FAILED = 2
    STOPPED = 3
    SKIPPED = 4


class Operation(IntEnum):
    """RobotSample.OP_* · ExecuteMotion.OP_*. WELD_PATH 는 표시용이고 ExecuteMotion goal 에는 쓰지 않는다."""

    NONE = 0
    MOVE_TO = 1
    DESCEND = 2
    SLIDE = 3
    HOME = 4
    WELD_PATH = 5


class MotionReason(IntEnum):
    """ExecuteMotion.Result.REASON_* (ExecutePath 도 같은 값을 쓴다, 5.2절)."""

    TARGET_REACHED = 0
    CONTACT = 1
    EDGE = 2
    MAX_DISTANCE = 3
    TIMEOUT = 4
    STOP_REQUESTED = 5
    CANCELED = 6
    OVER_FORCE = 7
    ROBOT_ERROR = 8
    REJECTED = 9


class Reason(IntEnum):
    """ReasonCode (1차 6.1절 + phase 2 의 6xx). weld_manager 가 쓰는 것만 옮겼다."""

    OK = 0
    BUSY = 100
    INVALID_REQUEST = 101
    INVALID_VALUE = 102
    SAFETY_LATCHED = 103
    ROBOT_DISCONNECTED = 104
    STOP_REQUESTED = 200
    CANCELED = 201
    TIMEOUT = 203
    ROBOT_ERROR = 204
    TOOL_REG_SUSPECT = 302   # 시작 때 무접촉 |F| 가 크다(툴 미등록 의심, 5.1절)
    NO_SAMPLE = 307          # 시작 때 /robot/sample 이 없다(5.1절)
    OVER_FORCE = 400
    SAMPLE_STALE = 403
    ROBOT_STATUS_LOST = 404
    SCAN_ACTIVE = 600
    WELD_ACTIVE = 601
    NO_SCAN_RESULT = 602
    LINE_OUT_OF_RANGE = 603
    PATH_REJECTED = 604
