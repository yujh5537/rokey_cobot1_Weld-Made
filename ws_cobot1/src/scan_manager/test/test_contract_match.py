"""자체 enum 이 contact_scan_interfaces 의 상수와 같은지 양방향으로 확인한다.

ROS 를 source 하지 않은 셸에서는 skip 되고, colcon test · CI 에서는 실행된다.
"""

import pytest
from scan_manager.contract_enums import Direction
from scan_manager.contract_enums import MotionReason
from scan_manager.contract_enums import Operation
from scan_manager.contract_enums import Phase
from scan_manager.contract_enums import Reason
from scan_manager.contract_enums import WELD_REST_PHASES
from scan_manager.contract_enums import WeldPhase

pytest.importorskip('contact_scan_interfaces')

from contact_scan_interfaces.action import ExecuteMotion  # noqa: E402
from contact_scan_interfaces.msg import ReasonCode  # noqa: E402
from contact_scan_interfaces.msg import ScanState  # noqa: E402
from contact_scan_interfaces.msg import WeldState  # noqa: E402


def _constants(msg_type, prefix=''):
    """rosidl 이 생성한 상수 중 prefix 로 시작하는 것을 {이름(접두어 제외): 값} 으로."""
    names = [
        n for n in vars(type(msg_type))
        if n.isupper() and not n.startswith('_') and n.startswith(prefix)
    ]
    return {n[len(prefix):]: getattr(msg_type, n) for n in names}


def _members(enum_type):
    return {member.name: int(member) for member in enum_type}


def test_phase_matches_scan_state():
    assert _members(Phase) == _constants(ScanState, 'PHASE_')
    assert len(Phase) == 11


def test_weld_phase_matches_weld_state():
    """phase 2 계약 3.2 · 7.1. 휴지 4 개는 WeldState 상수 그대로다."""
    assert _members(WeldPhase) == _constants(WeldState, 'PHASE_')
    assert {int(p) for p in WELD_REST_PHASES} == {
        WeldState.PHASE_IDLE, WeldState.PHASE_DONE, WeldState.PHASE_ERROR, WeldState.PHASE_STOPPED}


def test_direction_matches_scan_state_and_execute_motion():
    assert _members(Direction) == _constants(ScanState, 'DIR_')
    assert _members(Direction) == _constants(ExecuteMotion.Goal, 'DIR_')


def test_operation_matches_execute_motion():
    assert _members(Operation) == _constants(ExecuteMotion.Goal, 'OP_')


def test_motion_reason_matches_execute_motion_result():
    assert _members(MotionReason) == _constants(ExecuteMotion.Result, 'REASON_')


def test_reason_matches_reason_code():
    assert _members(Reason) == _constants(ReasonCode)


def test_rejection_codes_used_by_state_machine():
    assert Reason.BUSY == ReasonCode.BUSY == 100
    assert Reason.SAFETY_LATCHED == ReasonCode.SAFETY_LATCHED == 103
    assert Reason.ROBOT_DISCONNECTED == ReasonCode.ROBOT_DISCONNECTED == 104
    assert Reason.NO_RESUMABLE_SCAN == ReasonCode.NO_RESUMABLE_SCAN == 105
    assert Reason.NOT_SUPPORTED == ReasonCode.NOT_SUPPORTED == 107
    assert Reason.WELD_ACTIVE == ReasonCode.WELD_ACTIVE == 601
