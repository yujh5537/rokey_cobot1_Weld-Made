"""순수 결과 ↔ 메시지 변환의 경계 규칙 (NaN · 시각 0 · 모르는 값). 설치된 contact_scan_interfaces 가 있어야 돈다."""

import math

import pytest

msg = pytest.importorskip('contact_scan_interfaces.msg')
if not hasattr(msg, 'WeldConfig'):
    pytest.skip('contact_scan_interfaces 에 phase 2 타입이 없다', allow_module_level=True)

from builtin_interfaces.msg import Time  # noqa: E402
from contact_scan_interfaces.action import ExecuteMotion  # noqa: E402
from contact_scan_interfaces.msg import WeldConfig  # noqa: E402

from weld_manager import conversions  # noqa: E402
from weld_manager.contract_enums import MotionReason  # noqa: E402
from weld_manager.sequence import MotionKind  # noqa: E402
from weld_manager.sequence import MotionRequest  # noqa: E402


def test_override_takes_only_set_fields():
    config = WeldConfig(tilt_deg=30.0, tilt_set=True, standoff_m=0.004, standoff_set=False)
    assert conversions.override_from_msg(config) == {'tilt_deg': 30.0}


def test_config_snapshot_marks_missing_as_nan():
    config = conversions.config_to_msg({'tilt_deg': 45.0})
    assert config.tilt_set and config.tilt_deg == 45.0
    assert not config.weld_speed_set and math.isnan(config.weld_speed_mps)


def test_blank_result_has_no_zero_coordinates():
    result = conversions.blank_result_msg()
    assert len(result.lines) == 8
    assert all(not line.seam.valid and math.isnan(line.seam.start.x) for line in result.lines)
    assert all(not line.stop_pose_valid and math.isnan(line.stop_pose.orientation.w) for line in result.lines)
    assert math.isnan(result.base_to_fixture.x)


def test_result_without_stamp_has_no_position():
    raw = ExecuteMotion.Result(reason=0)        # pose 는 기본값(0), pose_stamp 0 = 좌표 없음
    result = conversions.motion_result_from_msg(raw)
    assert result.reason is MotionReason.TARGET_REACHED
    assert result.position is None and result.orientation is None
    raw.pose_stamp = Time(sec=5)
    assert conversions.motion_result_from_msg(raw).position == (0.0, 0.0, 0.0)


def test_unknown_reason_is_not_guessed():
    assert conversions.motion_result_from_msg(ExecuteMotion.Result(reason=42)).reason is None


def test_goals_carry_frame_and_timeout():
    request = MotionRequest(MotionKind.MOVE_TO, 'x', speed=0.02, target=(0.4, -0.2, 0.5),
                            orientation=(0.0, 1.0, 0.0, 0.0), timeout_s=12.5)
    goal = conversions.motion_goal(request, '20260923-120000-0001', 7, 'base_link')
    assert goal.operation == 1 and goal.frame_id == 'base_link' and goal.motion_id == 7
    assert (goal.timeout.sec, goal.timeout.nanosec) == (12, 500_000_000)
    home = conversions.motion_goal(MotionRequest(MotionKind.HOME, 'h', timeout_s=1.0), 'w', 8, 'base_link')
    assert home.operation == 4
    with pytest.raises(ValueError):
        conversions.path_goal(request, 'w', 9, 'base_link')
