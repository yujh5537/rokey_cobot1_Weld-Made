"""contract_enums 의 사본이 msg 상수와 같은지 본다. contact_scan_interfaces(v0.2.0 이상)가 없는 셸에서는 건너뛴다."""

import pytest

from weld_manager.contract_enums import LINE_COUNT
from weld_manager.contract_enums import LINE_NONE
from weld_manager.contract_enums import LineStatus
from weld_manager.contract_enums import MotionReason
from weld_manager.contract_enums import Operation
from weld_manager.contract_enums import Reason
from weld_manager.contract_enums import WeldPhase

msg = pytest.importorskip('contact_scan_interfaces.msg')
action = pytest.importorskip('contact_scan_interfaces.action')
if not hasattr(msg, 'WeldState'):
    pytest.skip('contact_scan_interfaces 에 phase 2 타입이 없다(v0.2.0 전 설치본)', allow_module_level=True)


@pytest.mark.parametrize('enum, source, prefix', [
    (WeldPhase, msg.WeldState, 'PHASE_'),
    (LineStatus, msg.WeldLine, 'STATUS_'),
    (Operation, msg.RobotSample, 'OP_'),
    (MotionReason, action.ExecuteMotion.Result, 'REASON_'),
    (Reason, msg.ReasonCode, ''),
])
def test_copy_matches_msg(enum, source, prefix):
    for member in enum:
        assert getattr(source, prefix + member.name) == member.value, member


def test_path_reasons_are_same_numbers():
    # ExecutePath.Result.REASON_* 는 ExecuteMotion 과 같은 값이다(5.2절)
    for name in ('TARGET_REACHED', 'TIMEOUT', 'STOP_REQUESTED', 'CANCELED', 'OVER_FORCE',
                 'ROBOT_ERROR', 'REJECTED'):
        assert getattr(action.ExecutePath.Result, 'REASON_' + name) == MotionReason[name].value


def test_line_constants():
    assert msg.WeldState.LINE_NONE == LINE_NONE
    assert len(msg.WeldResult().lines) == LINE_COUNT
