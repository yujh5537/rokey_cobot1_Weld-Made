"""파라미터 검사: 누락 · 범위 · 덮어쓰기 (weld-motion.md 6절, weld-ros-interfaces.md 3.1절 · 6장)."""

import math

import pytest

from weld_manager.params import CONFIG_NAMES
from weld_manager.params import check
from weld_manager.params import check_override
from weld_manager.params import SPECS


def test_all_values_pass(param_values):
    result = check(param_values)
    assert result.ok, result.describe()
    params = result.params
    assert params.result_frame_id == 'workpiece_fixture'   # 이름표만 기본값이 있다
    assert params.motion_frame_id == 'base_link'
    assert math.isclose(params.tilt_rad, math.pi / 4)
    assert params.tool_roll_deg == (0.0,) * 8 and params.tool_roll_rad(3) == 0.0
    assert params.tool_profile == ((0.0, 0.002), (0.003, 0.006), (0.012, 0.015))


def test_motion_numbers_have_no_code_default():
    # 규칙 7: 모션 수치는 yaml 에만 둔다. 기본값이 있는 것은 프레임 이름표뿐이다
    defaults = [spec.name for spec in SPECS if spec.default is not None]
    assert sorted(defaults) == ['motion_frame_id', 'result_frame_id']
    assert all(spec.required for spec in SPECS if spec.default is None)


def test_orientation_tolerance_zero_turns_it_off(param_values):
    # 6절 표(38b55e8): 출발값 15°, 0 = 끔. 없으면 다른 수치처럼 START 를 거절한다
    params = check(param_values).params
    assert math.isclose(params.orientation_tolerance_rad, math.radians(15.0))
    assert check({**param_values, 'orientation_tolerance_deg': 0.0}).params.orientation_tolerance_rad is None
    assert not check({**param_values, 'orientation_tolerance_deg': -1.0}).ok
    del param_values['orientation_tolerance_deg']
    assert check(param_values).missing == ('orientation_tolerance_deg',)


def test_speed_upper_bound_is_not_ours(param_values):
    # D29: 상한은 robot_manager 의 path_max_speed_mps 가 거른다. weld_manager 에는 그 이름이 없다
    assert 'path_max_speed_mps' not in {spec.name for spec in SPECS}
    param_values['travel_speed_mps'] = 5.0
    assert check(param_values).ok


def test_missing_values_are_listed_not_filled(param_values):
    del param_values['standoff_m']
    param_values['tilt_deg'] = None           # yaml 에 줄이 없는 것과 같다
    result = check(param_values)
    assert not result.ok
    assert set(result.missing) == {'standoff_m', 'tilt_deg'}


@pytest.mark.parametrize('name, value', [
    ('tilt_deg', 80.1), ('tilt_deg', -1.0), ('standoff_m', 0.0), ('weld_speed_mps', 0.0),
    ('weave_amplitude_m', -0.001), ('approach_m', float('nan')), ('tip_radius_m', 0.0),
    ('bottom_margin_m', -0.001), ('result_dir', ''), ('weld_speed_mps', True),
    ('tool_roll_deg', [0.0] * 7), ('tool_roll_deg', [0.0] * 7 + [float('inf')]), ('tool_roll_deg', 0.0),
    ('tool_profile_u_m', []), ('tool_profile_u_m', [0.0, 0.012, 0.003]),
    ('tool_profile_u_m', [0.0, 0.003, 0.003]), ('tool_profile_u_m', [-0.001, 0.003, 0.012]),
    ('tool_profile_r_m', [0.002, 0.0, 0.015]), ('tool_check_max_force_n', 0.0),
    ('continue_on_line_failure', 1), ('continue_on_line_failure', 'true'),    # D33: bool 만
])
def test_out_of_range(param_values, name, value):
    param_values[name] = value
    result = check(param_values)
    assert not result.ok
    assert any(line.startswith(name) for line in result.invalid), result.invalid


@pytest.mark.parametrize('name, value', [
    ('weave_amplitude_m', 0.0), ('weave_pitch_m', 0.0), ('tilt_deg', 0.0), ('tilt_deg', 80.0),
    ('tool_roll_deg', [-30.0, 0, 0, 0, 0, 0, 0, 60.0]), ('bottom_margin_m', 0.0),
    ('continue_on_line_failure', False),
])
def test_zero_and_bounds_are_values(param_values, name, value):
    param_values[name] = value
    assert check(param_values).ok


@pytest.mark.parametrize('name', ['weld_speed_mps', 'travel_speed_mps', 'approach_speed_mps'])
def test_speed_below_minimum_is_rejected(param_values, name):
    # #152 거짓 도착: 이동 판정(약 0.67 mm/s)보다 느리면 "멈춤"으로 보인다
    param_values[name] = 0.001
    result = check(param_values)
    assert not result.ok
    assert 'weld_speed_min_mps' in result.invalid[0]


def test_profile_arrays_must_have_same_length(param_values):
    param_values['tool_profile_r_m'] = [0.002, 0.006]
    result = check(param_values)
    assert not result.ok and '길이가 같아야' in result.invalid[0]


def test_override_applies_to_job_only(param_values):
    before = {k: list(v) if isinstance(v, list) else v for k, v in param_values.items()}
    override = {'tilt_deg': 30.0, 'weave_amplitude_m': 0.0}
    result = check(param_values, override)
    assert result.ok
    assert result.params.tilt_deg == 30.0 and result.params.weave_amplitude_m == 0.0
    assert param_values == before and override == {'tilt_deg': 30.0, 'weave_amplitude_m': 0.0}


def test_override_below_minimum_speed_is_rejected(param_values):
    assert not check(param_values, {'weld_speed_mps': 0.001}).ok


def test_override_problems():
    assert check_override({'tilt_deg': 30.0}) == ()
    problems = check_override({'tilt_deg': 90.0, 'approach_m': 0.05})
    assert len(problems) == 2
    assert 'WeldConfig 항목이 아니다' in problems[1]   # approach_m 은 WeldConfig 에 없다


def test_config_values_are_weld_config_fields(params):
    assert tuple(params.config_values()) == CONFIG_NAMES
