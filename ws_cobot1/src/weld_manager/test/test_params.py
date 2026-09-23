"""파라미터 검사: 누락 · 범위 · 덮어쓰기 (weld-motion.md 6절, weld-ros-interfaces.md 3.1절)."""

import math

import pytest

from weld_manager.params import CONFIG_NAMES
from weld_manager.params import check
from weld_manager.params import check_override
from weld_manager.params import SPECS


def test_all_values_pass(param_values):
    result = check(param_values)
    assert result.ok, result.describe()
    assert result.params.result_frame_id == 'workpiece_fixture'   # 이름표만 기본값이 있다
    assert result.params.motion_frame_id == 'base_link'
    assert math.isclose(result.params.tilt_rad, math.pi / 4)


def test_motion_numbers_have_no_code_default():
    # 규칙 7: 모션 수치는 yaml 에만 둔다. 기본값이 있는 것은 프레임 이름표뿐이다
    defaults = [spec.name for spec in SPECS if spec.default is not None]
    assert sorted(defaults) == ['motion_frame_id', 'result_frame_id']
    assert all(spec.required for spec in SPECS if spec.default is None)


def test_missing_values_are_listed_not_filled(param_values):
    del param_values['standoff_m']
    param_values['tilt_deg'] = None           # yaml 에 줄이 없는 것과 같다
    result = check(param_values)
    assert not result.ok
    assert set(result.missing) == {'standoff_m', 'tilt_deg'}


@pytest.mark.parametrize('name, value', [
    ('tilt_deg', 80.1), ('tilt_deg', -1.0), ('standoff_m', 0.0), ('weld_speed_mps', 0.0),
    ('weave_amplitude_m', -0.001), ('approach_m', float('nan')), ('tool_roll_deg', float('inf')),
    ('bottom_margin_m', -0.001), ('result_dir', ''), ('weld_speed_mps', True),
])
def test_out_of_range(param_values, name, value):
    param_values[name] = value
    result = check(param_values)
    assert not result.ok
    assert any(line.startswith(name) for line in result.invalid)


@pytest.mark.parametrize('name, value', [
    ('weave_amplitude_m', 0.0), ('weave_pitch_m', 0.0), ('tilt_deg', 0.0), ('tilt_deg', 80.0),
    ('tool_roll_deg', -30.0), ('bottom_margin_m', 0.0),
])
def test_zero_and_bounds_are_values(param_values, name, value):
    param_values[name] = value
    assert check(param_values).ok


def test_speed_above_path_max_is_rejected(param_values):
    param_values['travel_speed_mps'] = 0.101
    result = check(param_values)
    assert not result.ok
    assert 'path_max_speed_mps' in result.invalid[0]


def test_override_applies_to_job_only(param_values):
    before = dict(param_values)
    override = {'tilt_deg': 30.0, 'weave_amplitude_m': 0.0}
    result = check(param_values, override)
    assert result.ok
    assert result.params.tilt_deg == 30.0 and result.params.weave_amplitude_m == 0.0
    assert param_values == before and override == {'tilt_deg': 30.0, 'weave_amplitude_m': 0.0}


def test_override_problems():
    assert check_override({'tilt_deg': 30.0}) == ()
    problems = check_override({'tilt_deg': 90.0, 'approach_m': 0.05})
    assert len(problems) == 2
    assert 'WeldConfig 항목이 아니다' in problems[1]   # approach_m 은 WeldConfig 에 없다


def test_config_values_are_weld_config_fields(params):
    assert tuple(params.config_values()) == CONFIG_NAMES
