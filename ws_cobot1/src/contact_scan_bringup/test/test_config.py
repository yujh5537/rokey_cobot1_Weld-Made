"""sim.yaml · real.yaml 이 계약(ros-interfaces.md 6.4 · 7.2)을 지키는지 검사한다. ROS 실행 없이 돈다."""
import math
from pathlib import Path

import pytest
import yaml

CONFIG_DIR = Path(__file__).resolve().parents[1] / 'config'

# 파일 이름 → contact_detector 의 source 값
SOURCE_BY_FILE = {'sim.yaml': 'sim', 'real.yaml': 'robot_force'}

# SetConfig 가 이름으로 전파하는 파라미터 (6.4). 이 PR 시점에 yaml 에 절이 있는 노드만 검사한다.
CONTRACT_PARAMS = {
    'contact_detector': ['contact_threshold_n', 'edge_drop_m', 'debounce_n', 'over_force_n'],
    'safety_monitor': ['over_force_n', 'drop_limit_m'],
}

# 두 노드가 같은 값을 써야 하는 파라미터 (7.2 이중 감시)
SHARED_PARAMS = {
    'over_force_n': ['contact_detector', 'safety_monitor'],
    'drop_limit_m': ['safety_monitor', 'robot_manager'],
}


def _params(file_name):
    data = yaml.safe_load((CONFIG_DIR / file_name).read_text(encoding='utf-8'))
    return {node: body['ros__parameters'] for node, body in data.items()}


@pytest.mark.parametrize('file_name', SOURCE_BY_FILE)
def test_contract_param_names_exist(file_name):
    params = _params(file_name)
    for node, names in CONTRACT_PARAMS.items():
        for name in names:
            assert name in params[node], f'{file_name}: {node}.{name} 이 없다'


@pytest.mark.parametrize('file_name', SOURCE_BY_FILE)
def test_shared_params_have_same_value(file_name):
    params = _params(file_name)
    for name, nodes in SHARED_PARAMS.items():
        values = {node: params[node][name] for node in nodes}
        assert len(set(values.values())) == 1, f'{file_name}: {name} 값이 노드마다 다르다 {values}'


@pytest.mark.parametrize('file_name, source', SOURCE_BY_FILE.items())
def test_source_matches_file(file_name, source):
    assert _params(file_name)['contact_detector']['source'] == source


@pytest.mark.parametrize('file_name', SOURCE_BY_FILE)
def test_no_zero_or_nan_placeholder(file_name):
    """정하지 않은 값을 0 이나 NaN 으로 채워 두지 않는다. 미정이면 주석으로 둔다."""
    for node, names in CONTRACT_PARAMS.items():
        for name in names:
            value = _params(file_name)[node][name]
            assert value > 0 and math.isfinite(value), f'{file_name}: {node}.{name} = {value}'


@pytest.mark.parametrize('file_name', SOURCE_BY_FILE)
def test_state_publish_period_positive(file_name):
    """0 이하면 scan_manager 가 기동하지 않는다 (PR #50)."""
    assert _params(file_name)['scan_manager']['state_publish_period_s'] > 0


@pytest.mark.parametrize('file_name', SOURCE_BY_FILE)
def test_result_dir_is_absolute(file_name):
    """result_dir 은 절대경로여야 한다 (#187).

    상대 경로는 노드를 띄운 셸의 현재 디렉터리 기준이라, 같은 코드로도 launch 위치에 따라
    기록이 다른 곳에 남는다. 9/23 실기에서 ~/data 와 ws_cobot1/data 로 갈렸다.
    scan_manager 가 os.path.expanduser 를 하므로 ~ 로 시작해도 된다.
    """
    value = _params(file_name)['scan_manager']['result_dir']
    assert value.startswith(('~', '/')), f'{file_name}: result_dir = {value!r} 이 상대 경로다'


def test_sim_and_real_result_dirs_differ():
    """sim 과 real 의 기록이 한 디렉터리에 섞이면 안 된다 (#187).

    weld_tracer 가 '가장 최근 결과'를 고르므로, 섞이면 sim 박스 좌표를 실기가 따라갈 수 있다(현지).
    """
    dirs = {f: _params(f)['scan_manager']['result_dir'] for f in SOURCE_BY_FILE}
    assert len(set(dirs.values())) == len(dirs), f'sim 과 real 의 result_dir 이 같다 {dirs}'


# phase 2 weld_manager 절 (docs/phase2/weld-motion.md 6절). 이름은 계약에 속한다
WELD_PARAMS = [
    'weld_speed_mps', 'travel_speed_mps', 'approach_speed_mps', 'weld_speed_min_mps', 'standoff_m',
    'tip_radius_m', 'weave_amplitude_m', 'weave_pitch_m', 'tilt_deg', 'tool_roll_deg', 'approach_m',
    'travel_clearance_m', 'bottom_margin_m', 'workspace_margin_m', 'path_tolerance_m',
    'orientation_tolerance_deg', 'motion_timeout_s', 'tool_check_max_force_n', 'server_wait_timeout_s',
    'stop_confirm_timeout_s', 'sample_timeout_s', 'state_publish_period_s', 'scan_state_timeout_s',
    'result_dir', 'result_frame_id', 'motion_frame_id',
]
# M2(#186 툴 치수)를 재기 전이라 real.yaml 에는 두지 않는다(미측정값을 채우지 않는다, 규칙 4)
TOOL_PROFILE = ['tool_profile_u_m', 'tool_profile_r_m']


@pytest.mark.parametrize('file_name', SOURCE_BY_FILE)
def test_weld_manager_has_contract_params(file_name):
    weld = _params(file_name)['weld_manager']
    missing = [name for name in WELD_PARAMS if name not in weld]
    assert not missing, f'{file_name}: weld_manager 에 {missing} 가 없다'


@pytest.mark.parametrize('file_name', SOURCE_BY_FILE)
def test_tool_profile_is_both_or_neither(file_name):
    """외형 두 배열은 같이 있거나 같이 없다. 있으면 길이가 같고 u 는 오름차순이다."""
    weld = _params(file_name)['weld_manager']
    present = [name for name in TOOL_PROFILE if name in weld]
    assert len(present) in (0, 2), f'{file_name}: {present} 만 있다'
    if present:
        u, r = weld['tool_profile_u_m'], weld['tool_profile_r_m']
        assert len(u) == len(r) and u == sorted(set(u)) and all(v > 0 for v in r)


@pytest.mark.parametrize('file_name, node, name', [
    (f, 'scan_manager', 'result_dir') for f in SOURCE_BY_FILE] + [
    (f, 'scan_manager', 'tip_radius_m') for f in SOURCE_BY_FILE])
def test_weld_manager_shares_values_with_scan_manager(file_name, node, name):
    """result_dir 이 다르면 weld_manager 가 스캔 결과를 못 찾고, tip_radius_m 이 다르면 스탠드오프 정의가 어긋난다(계약 6절)."""
    params = _params(file_name)
    assert params['weld_manager'][name] == params[node][name]


@pytest.mark.parametrize('file_name', SOURCE_BY_FILE)
def test_weld_frame_matches_robot_manager(file_name):
    """ExecutePath 는 frame_id 가 robot_manager.frame_id 와 다르면 604 로 거절한다."""
    params = _params(file_name)
    assert params['weld_manager']['motion_frame_id'] == params['robot_manager']['frame_id']


@pytest.mark.parametrize('file_name', SOURCE_BY_FILE)
def test_weld_speeds_fit_robot_limits(file_name):
    """용접 속도는 robot_manager 상한 이하, 하한은 이동 판정 최저 속도(eps / 창)보다 커야 한다(#152)."""
    params = _params(file_name)
    weld, robot = params['weld_manager'], params['robot_manager']
    assert weld['weld_speed_mps'] <= robot['path_max_speed_mps']
    assert weld['weld_speed_min_mps'] > robot['moving_eps_m'] / robot['moving_window_s']
