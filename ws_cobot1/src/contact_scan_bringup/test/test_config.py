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
