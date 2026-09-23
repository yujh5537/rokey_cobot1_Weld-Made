"""생성된 Python 타입의 상수 · 배열 길이가 계약 v0.1 과 같은지 확인한다."""

from contact_scan_interfaces.action import ExecuteMotion
from contact_scan_interfaces.msg import ReasonCode
from contact_scan_interfaces.msg import RobotSample
from contact_scan_interfaces.msg import ScanResult
from contact_scan_interfaces.msg import ScanState

# 계약 6.1절 v0.1 동결값. 번호는 추가만 하고 바꾸지 않는다.
# 코드를 추가할 때는 계약 문서 · ReasonCode.msg · 이 표를 같이 고친다.
REASON_CODES_V0_1 = {
    'OK': 0,
    'BUSY': 100,
    'INVALID_REQUEST': 101,
    'INVALID_VALUE': 102,
    'SAFETY_LATCHED': 103,
    'ROBOT_DISCONNECTED': 104,
    'NO_RESUMABLE_SCAN': 105,
    'DUPLICATE_REQUEST': 106,
    'NOT_SUPPORTED': 107,
    'PARAM_SET_FAILED': 108,
    'STOP_REQUESTED': 200,
    'CANCELED': 201,
    'MAX_DISTANCE': 202,
    'TIMEOUT': 203,
    'ROBOT_ERROR': 204,
    'DROP_LIMIT': 205,
    'NO_CONTACT': 300,
    'NO_EDGE': 301,
    'TOOL_REG_SUSPECT': 302,
    'TARE_FAILED': 303,
    'ROBOT_MOVING': 304,
    'TARE_UNSTABLE': 305,
    'TARE_TIMEOUT': 306,
    'NO_SAMPLE': 307,
    'OVER_FORCE': 400,
    'OVER_SPEED': 401,
    'OUT_OF_WORKSPACE': 402,
    'SAMPLE_STALE': 403,
    'ROBOT_STATUS_LOST': 404,
    'HB_EXPIRED': 405,
    'CONDITION_ACTIVE': 406,
    'STOP_UNCONFIRMED': 407,   # v0.1.21 추가 (계약 9장의 재시작 허용 목록)
    'INVALID_SHAPE': 500,
    'INSUFFICIENT_POINTS': 501,
}


def constants_of(cls, prefix=''):
    """rosidl Python 타입의 상수를 {이름: 값} 으로 돌려준다."""
    # 생성기가 클래스에 넣는 대문자 속성은 상수와 SLOT_TYPES 뿐이다.
    names = [n for n in vars(cls) if n.isupper() and n != 'SLOT_TYPES']
    return {n: getattr(cls, n) for n in names if n.startswith(prefix)}


def test_reason_code_has_34_constants_with_frozen_values():
    actual = constants_of(ReasonCode)
    assert len(REASON_CODES_V0_1) == 34
    assert actual == REASON_CODES_V0_1


def test_reason_code_values_are_unique():
    values = list(constants_of(ReasonCode).values())
    assert len(values) == len(set(values))


def test_op_constants_match_between_sample_and_execute_motion():
    expected = {'OP_NONE': 0, 'OP_MOVE_TO': 1, 'OP_DESCEND': 2, 'OP_SLIDE': 3, 'OP_HOME': 4}
    assert constants_of(RobotSample, 'OP_') == expected
    assert constants_of(ExecuteMotion.Goal, 'OP_') == expected


def test_dir_constants_match_between_scan_state_and_execute_motion():
    expected = {'DIR_NONE': 0, 'DIR_POS_X': 1, 'DIR_NEG_X': 2, 'DIR_POS_Y': 3, 'DIR_NEG_Y': 4}
    assert constants_of(ScanState, 'DIR_') == expected
    assert constants_of(ExecuteMotion.Goal, 'DIR_') == expected


def test_scan_result_fixed_array_lengths():
    result = ScanResult()
    assert len(result.vertices) == 8
    assert len(result.edges) == 12
    assert len(result.path_candidates) == 4


def test_nested_result_field_keeps_contract_name():
    # RunScan/Resume 의 Result 에는 계약대로 'result' 필드가 있다 (...Result.result).
    from contact_scan_interfaces.action import Resume
    from contact_scan_interfaces.action import RunScan
    assert isinstance(RunScan.Result().result, ScanResult)
    assert isinstance(Resume.Result().result, ScanResult)
