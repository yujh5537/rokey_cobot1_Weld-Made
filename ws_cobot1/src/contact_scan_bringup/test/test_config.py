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


def test_weld_state_timeout_is_positive_and_the_same_in_sim_and_real():
    """scan_manager 가 /weld/state 를 끊긴 것으로 보는 한도 (phase 2 계약 7.1, 출발값 5.0).

    필수 파라미터라 없으면 START 가 거절된다. 끊기면 용접이 없다고 보고 통과시키는 값이라
    sim 과 real 이 다르면 Virtual 에서 본 배타 동작이 실기에서 달라진다.
    """
    values = {f: _params(f)['scan_manager'].get('weld_state_timeout_s') for f in SOURCE_BY_FILE}
    for file_name, value in values.items():
        assert value is not None, f'{file_name}: scan_manager.weld_state_timeout_s 이 없다'
        assert value > 0 and math.isfinite(value), f'{file_name}: weld_state_timeout_s = {value}'
    assert len(set(values.values())) == 1, f'sim 과 real 의 weld_state_timeout_s 가 다르다 {values}'


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
    'tip_radius_m', 'weave_amplitude_m', 'weave_pitch_m', 'tilt_deg', 'tool_roll_deg', 'standoff_line_offset_m',
    'tilt_line_offset_deg', 'target_shift_m', 'approach_m',
    'top_line_offset_dir', 'travel_clearance_m', 'bottom_margin_m', 'workspace_margin_m', 'path_tolerance_m',
    'continue_on_line_failure', 'orientation_tolerance_deg', 'motion_timeout_s', 'path_point_dwell_s',
    'tool_check_max_force_n', 'server_wait_timeout_s',
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
def test_continue_on_line_failure_is_a_bool(file_name):
    """D33 스위치는 bool 만 받는다(weld_manager 는 1 · 'true' 를 거절한다)."""
    assert isinstance(_params(file_name)['weld_manager']['continue_on_line_failure'], bool)


@pytest.mark.parametrize('file_name', SOURCE_BY_FILE)
def test_weld_state_period_is_shorter_than_scan_timeout(file_name):
    """병후 #197(9/28): scan_manager 601 은 /weld/state 가 weld_state_timeout_s 보다 오래되면 "용접 없음" 으로 통과한다.
    weld_manager 의 주기 발행이 그보다 짧아야 용접 중에 스캔이 접수되지 않는다."""
    params = _params(file_name)
    assert params['weld_manager']['state_publish_period_s'] < params['scan_manager']['weld_state_timeout_s']


@pytest.mark.parametrize('file_name', SOURCE_BY_FILE)
def test_top_line_offset_dir_is_tool_or_vertical(file_name):
    """D34: 9/29 는 yaml 한 줄 전환. 값은 두 가지뿐이다."""
    assert _params(file_name)['weld_manager']['top_line_offset_dir'] in ('tool', 'vertical')


@pytest.mark.parametrize('file_name', SOURCE_BY_FILE)
def test_standoff_line_offsets_keep_every_line_off_the_seam(file_name):
    """D36: 선별 보정을 더한 스탠드오프는 8 선 모두 0 보다 커야 한다(0 이하 = 접촉, weld_manager 가 102 로 거절)."""
    weld = _params(file_name)['weld_manager']
    offsets = weld['standoff_line_offset_m']
    assert len(offsets) == 8
    assert all(weld['standoff_m'] + off > 0.0 for off in offsets), offsets
    assert len(weld['target_shift_m']) == 3


@pytest.mark.parametrize('file_name', SOURCE_BY_FILE)
def test_tilt_line_offsets_stay_in_range_and_vertical_lines_keep_tilt(file_name):
    """D38: 선별 기울임 합은 0~80 이고, 세로선(L4~L7)은 0 이면 계획이 거절되므로 0 보다 커야 한다."""
    weld = _params(file_name)['weld_manager']
    offsets = weld['tilt_line_offset_deg']
    assert len(offsets) == 8
    tilts = [weld['tilt_deg'] + off for off in offsets]
    assert all(0.0 <= t <= 80.0 for t in tilts), tilts
    assert all(t > 0.0 for t in tilts[4:]), tilts


@pytest.mark.parametrize('file_name', SOURCE_BY_FILE)
def test_path_timeout_covers_max_points(file_name):
    """학민 #191 🔵: robot_manager 의 최대 경유점(path_max_points)을 실어도 제한 시간이 이동 시간을 덮어야 한다.
    100 점 · 위빙 경로(선 길이 약 100 mm + 진폭 왕복) / weld_speed + 점 수 × dwell 을 계산값으로 본다."""
    params = _params(file_name)
    weld, robot = params['weld_manager'], params['robot_manager']
    n = robot['path_max_points']
    travel_s = (0.100 + n * 2 * weld['weave_amplitude_m']) / weld['weld_speed_mps']
    assert weld['motion_timeout_s'] + n * weld['path_point_dwell_s'] > travel_s + n * robot['arrival_grace_s']


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
