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


# ---- 하강 제한 1차 · 2차 (계약 7.2, v0.1.21) ----

@pytest.mark.parametrize('file_name', SOURCE_BY_FILE)
def test_second_stage_drop_limit_is_behind_the_first(file_name):
    """2차(safety_monitor)는 1차(robot_manager)보다 여유만큼 뒤에 있어야 한다.

    같으면 잡음 한 샘플로도 2차가 먼저 걸려 1차가 정상 동작인데 래치부터 걸린다(#53).
    `drop_limit_m` 자체는 위 test_shared_params_have_same_value 가 같은 값임을 본다 —
    여유는 safety_monitor 전용 파라미터라 그 쌍 검사에 들어가지 않는다.
    """
    params = _params(file_name)
    margin = params['safety_monitor']['drop_limit_margin_m']
    assert margin > 0 and math.isfinite(margin), f'{file_name}: 여유가 0 이면 1차와 같아진다'
    first = params['robot_manager']['drop_limit_m']
    second = params['safety_monitor']['drop_limit_m'] + margin
    assert second > first, f'{file_name}: 2차 {second} 가 1차 {first} 보다 뒤에 있어야 한다'


@pytest.mark.parametrize('file_name', SOURCE_BY_FILE)
def test_decided_drop_limits_are_5mm_and_10mm(file_name):
    """팀 결정(2026-09-23): 1차 5 mm · 2차 10 mm. 되돌리면 이 시험이 알려 준다.

    10 은 간섭 거리 D = 12 mm(그리퍼 밖 탐침 길이, 자 실측)보다 2 mm 작다.
    9 mm(2026-09-22)는 근거 없이 정한 값이었다. 근거와 되돌릴 조건은 real.yaml 주석.
    """
    params = _params(file_name)
    assert params['robot_manager']['drop_limit_m'] == pytest.approx(0.005)
    assert params['safety_monitor']['drop_limit_m'] == pytest.approx(0.005)
    assert params['safety_monitor']['drop_limit_margin_m'] == pytest.approx(0.005)


@pytest.mark.parametrize('file_name', SOURCE_BY_FILE)
def test_margin_is_not_a_contract_name(file_name):
    """여유는 SetConfig 전파 대상이 아니다. 다른 노드에 같은 이름을 두지 않는다."""
    for node, values in _params(file_name).items():
        if node != 'safety_monitor':
            assert 'drop_limit_margin_m' not in values, f'{file_name}: {node} 에 여유가 있다'


# ---- 최신성 (계약 6.3 예외, 결정 3) ----

@pytest.mark.parametrize('file_name', SOURCE_BY_FILE)
def test_sample_stale_is_500ms(file_name):
    """결정 3: real · sim 모두 500 ms. **700 으로 올리지 않는다**(추후 검토만).

    #130 의 근본 원인이 풀리면 real 을 300 으로 되돌린다. 그때 이 시험도 같이 고친다.
    """
    assert _params(file_name)['safety_monitor']['sample_stale_ms'] == 500


@pytest.mark.parametrize('file_name', SOURCE_BY_FILE)
def test_sample_stale_is_not_stricter_than_the_detector(file_name):
    """정지를 요청하는 기준은 샘플을 버리는 기준보다 관대해야 한다."""
    params = _params(file_name)
    assert params['safety_monitor']['sample_stale_ms'] > params['contact_detector']['stale_age_ms']


# ---- 과대 외력 전역 30 N vs 스텝 12 N (계약 7.2, 결정 8) ----

@pytest.mark.parametrize('file_name', SOURCE_BY_FILE)
def test_global_over_force_stays_30n(file_name):
    """결정 8: 전역 과대 외력은 30 N 을 유지한다. 사람보다 빠른 영역이라 올리지 않는다."""
    for node in ('contact_detector', 'safety_monitor'):
        assert _params(file_name)[node]['over_force_n'] == pytest.approx(30.0)


def test_step_force_limit_is_local_and_below_the_global_one():
    """스텝 모드의 12 N 은 전역 30 N 과 다른 것이다. 30 으로 올리지 않는다.

    12 N = 스텝 알고리즘이 스스로 들고 중단하는 운용 한계(robot_manager 안에서만 쓴다).
    30 N = 전역 안전 정지 · 래치 한계. sim 은 step 모드를 쓰지 않아 검사하지 않는다.
    """
    params = _params('real.yaml')
    step_limit = params['robot_manager']['step_max_force_n']
    assert step_limit == pytest.approx(12.0)
    assert step_limit < params['safety_monitor']['over_force_n']


def test_step_press_stays_inside_the_first_drop_limit():
    """계약 7.2: step_press_max_m + step_drop_m < drop_limit_m (하강 제한에 먼저 걸린다)."""
    params = _params('real.yaml')['robot_manager']
    assert params['step_press_max_m'] + params['step_drop_m'] < params['drop_limit_m']


# ---- 안전복귀 (계약 7.5, 결정 7) ----

@pytest.mark.parametrize('file_name', SOURCE_BY_FILE)
def test_home_return_params_exist(file_name):
    """안전복귀는 HOME 전에 수직으로 올린다. 그 올림에 필요한 값이 없으면 /scan/home 이 거절된다."""
    scan = _params(file_name)['scan_manager']
    for name in ('lift_height_m', 'move_speed_mps', 'pose_max_age_s', 'motion_timeout_s'):
        assert name in scan, f'{file_name}: scan_manager.{name} 이 없다'
        assert scan[name] > 0 and math.isfinite(scan[name]), f'{file_name}: {name} = {scan[name]}'


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
