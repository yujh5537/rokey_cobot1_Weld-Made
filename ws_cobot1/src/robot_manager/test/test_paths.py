"""ExecutePath 순수 계산 테스트 (phase 2, P1). ROS 없이 돈다."""
import math

import pytest
from robot_manager.motions import pose_to_posx_mm_deg
from robot_manager.paths import (SPLINE_MAX_POINTS, PathLimits, Waypoint, limits_problem,
                                 path_length_m, path_problem, progress, to_posx_list)

NAN = float('nan')
DOWN = (1.0, 0.0, 0.0, 0.0)      # 툴 z 가 아래를 보는 자세(x 축 180° 회전)
# 시험용 값. 실제 값은 contact_scan_bringup/config/*.yaml
LIMITS = PathLimits(mode='line', max_points=100, max_speed_mps=0.100, min_z_m=0.100,
                    acc_ratio=4.0, frame_id='base_link')


def wp(x, y, z, q=DOWN):
    return Waypoint((x, y, z), q)


def line_of(n, z=0.2):
    return [wp(0.4 + 0.001 * i, 0.0, z) for i in range(n)]


def check(waypoints, frame_id='base_link', speed=0.01, tol=0.003, limits=LIMITS):
    return path_problem(waypoints, frame_id, speed, tol, limits)


# ---- 파라미터 ----------------------------------------------------------------------------

def test_limits_ok():
    assert limits_problem(LIMITS) is None
    assert limits_problem(LIMITS._replace(mode='spline')) is None


@pytest.mark.parametrize('change, word', [
    ({'mode': 'blend'}, 'path_mode'),
    ({'mode': ''}, 'path_mode'),
    ({'max_points': 0}, 'path_max_points'),
    ({'max_points': True}, 'path_max_points'),
    ({'max_points': 10.0}, 'path_max_points'),
    ({'max_speed_mps': 0.0}, 'path_max_speed_mps'),
    ({'max_speed_mps': NAN}, 'path_max_speed_mps'),
    ({'min_z_m': NAN}, 'path_min_z_m'),
    ({'acc_ratio': 0.0}, 'path_acc_ratio'),
    ({'acc_ratio': -4.0}, 'path_acc_ratio'),
    ({'frame_id': ''}, 'frame_id'),
])
def test_limits_problem_names_the_parameter(change, word):
    problem = limits_problem(LIMITS._replace(**change))
    assert problem and word in problem


def test_spline_cannot_exceed_driver_array():
    """spline 은 드라이버 고정 배열(100)을 넘길 수 없다. line 은 한 점씩이라 제한이 없다."""
    assert SPLINE_MAX_POINTS == 100
    over = LIMITS._replace(max_points=SPLINE_MAX_POINTS + 1)
    assert limits_problem(over) is None
    assert 'spline' in limits_problem(over._replace(mode='spline'))
    assert limits_problem(over._replace(mode='spline', max_points=SPLINE_MAX_POINTS)) is None


# ---- goal 검사 (PATH_REJECTED 604) --------------------------------------------------------

def test_valid_path_passes():
    assert check(line_of(21)) is None


def test_empty_path_is_rejected():
    assert '없다' in check([])


def test_point_count_boundary():
    assert check(line_of(100)) is None
    assert 'path_max_points' in check(line_of(101))


@pytest.mark.parametrize('speed', [0.0, -0.01, NAN, math.inf])
def test_bad_speed_is_rejected(speed):
    assert 'speed' in check(line_of(3), speed=speed)


def test_speed_limit_boundary():
    assert check(line_of(3), speed=0.100) is None
    assert 'path_max_speed_mps' in check(line_of(3), speed=0.1001)


@pytest.mark.parametrize('frame', ['', 'workpiece_fixture', 'BASE_LINK'])
def test_other_frame_is_rejected(frame):
    """빈 문자열도 거절한다. 작업대 좌표를 Base 로 알고 움직이면 약 47 cm 어긋난다(1차 PR #73 과 같은 이유)."""
    assert 'frame_id' in check(line_of(3), frame_id=frame)


@pytest.mark.parametrize('tol', [0.0, -0.001, NAN])
def test_bad_tolerance_is_rejected(tol):
    assert 'path_tolerance_m' in check(line_of(3), tol=tol)


@pytest.mark.parametrize('bad, word', [
    (wp(0.4, NAN, 0.2), '위치'),
    (Waypoint((0.4, 0.0), DOWN), '위치'),
    (wp(0.4, 0.0, 0.2, (0.0, 0.0, 0.0, 0.0)), 'quaternion'),
    (wp(0.4, 0.0, 0.2, (NAN, 0.0, 0.0, 1.0)), 'quaternion'),
])
def test_bad_waypoint_names_its_index(bad, word):
    path = line_of(3)
    path[1] = bad
    problem = check(path)
    assert '경유점 1' in problem and word in problem


def test_z_floor_checks_every_point_at_accept():
    """z 하한은 수락 시점에 전부 본다. 마지막 점만 낮아도 거절한다."""
    path = line_of(5)
    path[4] = wp(0.404, 0.0, 0.0999)
    problem = check(path)
    assert '경유점 4' in problem and 'path_min_z_m' in problem


def test_z_floor_boundary_is_allowed():
    assert check([wp(0.4, 0.0, LIMITS.min_z_m)]) is None


def test_contract_order_count_before_frame():
    """여러 문제가 겹치면 계약 5.2 의 순서(빈 목록 → 개수 → 속도 → 프레임 → 값 → z)로 첫 것을 준다."""
    assert 'path_max_points' in check(line_of(101), frame_id='x', speed=0.0)
    assert 'speed' in check(line_of(3), frame_id='x', speed=0.0)
    low_and_nan = [wp(0.4, 0.0, 0.0), wp(NAN, 0.0, 0.2)]
    assert '경유점 1' in check(low_and_nan)


# ---- 길이 · 진행 ---------------------------------------------------------------------------

START = (0.0, 0.0, 0.3)
STRAIGHT = [wp(0.01, 0.0, 0.3), wp(0.02, 0.0, 0.3)]


def test_path_length_includes_first_leg():
    """첫 점까지도 경로다(계약 5.2 "첫 점까지도 직선으로 간다")."""
    assert path_length_m(START, STRAIGHT) == pytest.approx(0.02)
    assert path_length_m(START, [wp(0.0, 0.0, 0.3)]) == 0.0


@pytest.mark.parametrize('position, index, done, distance, off', [
    ((-0.005, 0.0, 0.3), 0, 0, 0.0, 0.005),        # 출발점 뒤
    ((0.005, 0.001, 0.3), 0, 0, 0.005, 0.001),     # 첫 구간 중간, 1 mm 옆
    ((0.01, 0.0, 0.3), 1, 1, 0.01, 0.0),           # 첫 경유점 위
    ((0.015, 0.0, 0.3), 1, 1, 0.015, 0.0),
    ((0.02, 0.0, 0.3), 1, 2, 0.02, 0.0),           # 끝: 향하는 점은 마지막 점 그대로
    ((0.03, 0.0, 0.3), 1, 2, 0.02, 0.01),          # 끝을 지나침
])
def test_progress_on_straight_path(position, index, done, distance, off):
    p = progress(position, START, STRAIGHT)
    assert (p.waypoint_index, p.waypoints_done) == (index, done)
    assert p.distance_m == pytest.approx(distance)
    assert p.off_path_m == pytest.approx(off)


def zigzag(n, pitch=0.002, amplitude=0.0015):
    """위빙처럼 이웃 구간이 1~2 mm 안에 붙은 경로."""
    return [wp(0.4 + pitch * i, amplitude * (1 if i % 2 else -1), 0.2) for i in range(n)]


def test_progress_never_goes_back():
    """뒤 구간이 더 가까워도 `from_index` 앞으로는 가지 않는다(위빙에서 진행률이 튀지 않게)."""
    path = zigzag(10)
    start = (0.4, -0.0015, 0.21)
    near_segment_2 = tuple((a + b) / 2 for a, b in zip(path[1].position, path[2].position))
    assert progress(near_segment_2, start, path).waypoint_index == 2
    later = progress(near_segment_2, start, path, from_index=5)
    assert later.waypoint_index >= 5
    assert later.distance_m >= progress(path[4].position, start, path).distance_m


def test_progress_follows_zigzag_step_by_step():
    """직전 결과를 넘기며 따라가면 경유점마다 하나씩 늘어난다."""
    path = zigzag(12)
    start = (0.398, -0.0015, 0.2)
    index = 0
    for i, w in enumerate(path):
        p = progress(w.position, start, path, from_index=index)
        assert p.waypoints_done == i + 1
        index = p.waypoint_index
    assert p.distance_m == pytest.approx(path_length_m(start, path))


def test_progress_handles_repeated_point_and_bad_index():
    path = [wp(0.01, 0.0, 0.3), wp(0.01, 0.0, 0.3), wp(0.02, 0.0, 0.3)]
    p = progress((0.01, 0.0, 0.3), START, path)
    assert p.distance_m == pytest.approx(0.01)
    assert progress((0.02, 0.0, 0.3), START, path, from_index=99).waypoints_done == 3
    assert progress((0.0, 0.0, 0.3), START, path, from_index=-3).waypoints_done == 0


def test_progress_without_waypoints_raises():
    with pytest.raises(ValueError):
        progress((0.0, 0.0, 0.0), START, [])


# ---- 두산 단위 ----------------------------------------------------------------------------

def test_to_posx_list_matches_single_conversion():
    """변환은 1차 ExecuteMotion 과 같은 함수를 쓴다(자세 규약이 둘로 갈리지 않게)."""
    q45 = (0.9238795, 0.0, 0.0, 0.3826834)
    path = [wp(0.42356, -0.18606, 0.1506), wp(0.43, -0.18, 0.16, q45)]
    out = to_posx_list(path)
    assert len(out) == 2
    for posx, w in zip(out, path):
        assert posx == pose_to_posx_mm_deg(w.position, w.orientation)
    assert out[0][:3] == pytest.approx([423.56, -186.06, 150.6])


def test_to_posx_list_rejects_bad_value():
    with pytest.raises(ValueError):
        to_posx_list([wp(0.4, 0.0, 0.2, (0.0, 0.0, 0.0, 0.0))])
