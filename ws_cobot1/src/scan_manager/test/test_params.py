"""파라미터 검사: 필수 항목 누락, 범위, "없음"과 0 의 구분 (ROS 없음). 수치는 테스트용 임의값이다."""

import math

import pytest
from scan_manager import params as P
from scan_manager.contract_enums import Direction
from sequence_helpers import make_params
from sequence_helpers import VALUES

ZERO_IS_A_VALUE = ('support_z_m', 'edge_round_radius_m', 'edge_bias_offset_m', 'detect_latency_s')


def test_complete_values_make_params():
    params = make_params()
    assert params.descend_speed_mps == VALUES['descend_speed_mps']
    assert params.origin_position == (0.40, 0.00, 0.10)
    assert params.origin_orientation == (0.0, 1.0, 0.0, 0.0)
    assert params.base_to_fixture == (0.40, 0.00, 0.00)
    # 필수가 아닌 이름 · 프레임 · 순서에만 코드 기본값이 있다
    assert params.result_frame_id == 'workpiece_fixture'
    assert params.motion_frame_id == 'base_link'
    assert params.direction_order == (
        Direction.POS_X, Direction.NEG_X, Direction.POS_Y, Direction.NEG_Y)


def test_no_numeric_parameter_has_a_code_default():
    for spec in P.SPECS:
        if spec.kind in (P.DOUBLE, P.DOUBLE_ARRAY):
            assert spec.required and spec.default is None, spec.name


def test_contract_names_are_kept():
    # ros-interfaces.md 6.4절. SetConfig 가 이름으로 다룬다
    assert P.MOTION_CONFIG_NAMES == (
        'descend_speed_mps', 'slide_speed_mps', 'max_descend_m', 'max_slide_m',
        'motion_timeout_s', 'lift_height_m')
    assert set(P.MOTION_CONFIG_NAMES) <= set(P.SPEC_BY_NAME)


def test_missing_required_names_are_listed():
    values = {k: v for k, v in VALUES.items() if k not in ('tip_radius_m', 'search_origin_pose')}
    values['detect_latency_s'] = None  # None 도 "없음"이다
    result = P.check(values)
    assert not result.ok and result.params is None
    assert result.missing == ('search_origin_pose', 'tip_radius_m', 'detect_latency_s')
    for name in result.missing:
        assert name in result.describe()


def test_empty_values_list_every_required_name():
    result = P.check({})
    assert set(result.missing) == {spec.name for spec in P.SPECS if spec.required}


@pytest.mark.parametrize('name', ZERO_IS_A_VALUE)
def test_zero_is_a_value_not_a_missing_marker(name):
    result = P.check({**VALUES, name: 0.0})
    assert result.ok, result.describe()
    assert getattr(result.params, name) == 0.0


@pytest.mark.parametrize('name', [
    'descend_speed_mps', 'slide_speed_mps', 'max_descend_m', 'max_slide_m', 'motion_timeout_s',
    'lift_height_m', 'move_speed_mps', 'recontact_margin_m', 'recontact_speed_mps', 'tip_radius_m',
    'event_wait_timeout_s', 'stop_confirm_timeout_s', 'server_wait_timeout_s'])
@pytest.mark.parametrize('bad', [0.0, -0.01, math.nan, math.inf, True, 'fast'])
def test_positive_parameters_reject_zero_and_non_numbers(name, bad):
    result = P.check({**VALUES, name: bad})
    assert not result.ok and result.missing == ()
    assert any(problem.startswith(f'{name} = ') for problem in result.invalid)


@pytest.mark.parametrize('name, bad', [
    ('detect_latency_s', -0.001), ('edge_round_radius_m', -0.001), ('support_z_m', math.nan),
    ('edge_bias_offset_m', math.inf), ('result_dir', ''),
    ('base_to_fixture', [0.4, 0.0]), ('base_to_fixture', [0.4, 0.0, math.nan]),
    ('search_origin_pose', [0.4, 0.0, 0.1, 0.0, 3.14, 0.0]),          # 오일러 6개는 받지 않는다
    ('search_origin_pose', [0.4, 0.0, 0.1, 0.0, 0.5, 0.0, 0.0]),      # 단위 quaternion 이 아니다
    ('direction_order', ['POS_X', 'NEG_X', 'POS_Y']),
    ('direction_order', ['POS_X', 'POS_X', 'POS_Y', 'NEG_Y']),
    ('direction_order', ['POS_X', 'NEG_X', 'POS_Y', 'NONE']),
])
def test_out_of_range_values(name, bad):
    result = P.check({**VALUES, name: bad})
    assert not result.ok
    assert any(problem.startswith(f'{name} = ') for problem in result.invalid)


def test_negative_edge_bias_offset_is_allowed():
    assert P.check({**VALUES, 'edge_bias_offset_m': -0.0003}).ok


def test_recontact_margin_must_stay_below_the_lift():
    result = P.check({**VALUES, 'recontact_margin_m': VALUES['lift_height_m']})
    assert not result.ok and 'recontact_margin_m' in result.describe()


def test_descend_limit_must_not_reach_the_support_surface():
    # 기준점 z 0.10, 지지면 z 0.0 → 하강 한계는 0.10 미만이어야 한다(units-frames.md: 작업대 면을 윗면으로 잡지 않게)
    assert P.check({**VALUES, 'max_descend_m': 0.0999}).ok
    for too_far in (0.10, 0.15):
        result = P.check({**VALUES, 'max_descend_m': too_far})
        assert not result.ok and 'max_descend_m' in result.describe()
    raised_table = P.check({**VALUES, 'base_to_fixture': [0.40, 0.00, 0.05]})  # 지지면이 올라오면 같은 값도 닿는다
    assert not raised_table.ok and 'max_descend_m' in raised_table.describe()


def test_check_values_covers_other_nodes_config():
    assert P.check_values({'contact_threshold_n': 3.0, 'debounce_n': 3, 'drop_limit_m': 0.004}) == ()
    problems = P.check_values({'over_force_n': -1.0, 'debounce_n': 0, 'edge_drop_m': None})
    assert len(problems) == 2  # None 은 "주지 않음"이라 검사하지 않는다
    assert P.check_values({'debounce_n': 2.5}) != ()


def test_node_params_snapshot_is_plain_and_excludes_contract_config():
    snapshot = make_params().node_params()
    assert not set(P.MOTION_CONFIG_NAMES) & set(snapshot)
    assert snapshot['tip_radius_m'] == VALUES['tip_radius_m']
    assert snapshot['search_origin_pose'] == VALUES['search_origin_pose']
    assert isinstance(snapshot['base_to_fixture'], list)


def test_home_needs_only_its_own_parameters():
    # 측정 · 보정 파라미터가 비어 있어도 안전복귀는 막지 않는다
    values = {name: VALUES[name] for name in P.HOME_PARAM_NAMES if name in VALUES}
    result = P.check_home(values)
    assert result.ok and result.params.motion_timeout_s == VALUES['motion_timeout_s']
    assert result.params.motion_frame_id == 'base_link'

    result = P.check_home({'motion_timeout_s': -1.0, 'server_wait_timeout_s': 0.2})
    assert not result.ok and result.missing == (
        'stop_confirm_timeout_s', 'robot_status_timeout_s',
        # 계약 7.5(v0.1.17): 안전복귀는 HOME 전에 수직으로 올린다
        'lift_height_m', 'move_speed_mps', 'pose_max_age_s')
    assert any(problem.startswith('motion_timeout_s = ') for problem in result.invalid)
