"""경로 생성 검산 (weld-motion.md 1~5절). ROS 없이 돈다."""

import math

import pytest

from conftest import FIXTURE_SCAN_ID
from conftest import PARAM_VALUES
from conftest import write_result
from weld_manager.params import check
from weld_manager.weld_path import LINES
from weld_manager.weld_path import load_scan
from weld_manager.weld_path import NoScanResult
from weld_manager.weld_path import PathRejected
from weld_manager.weld_path import plan_line
from weld_manager.weld_path import plan_weld
from weld_manager.weld_path import quaternion_from_axes
from weld_manager.weld_path import quaternion_to_zyz_deg
from weld_manager.weld_path import rotate
from weld_manager.weld_path import ScanInput
from weld_manager.weld_path import tool_frame
from weld_manager.weld_path import weave_points

R2 = math.sqrt(0.5)
FRAMES = dict(result_frame_id='workpiece_fixture', motion_frame_id='base_link')


def with_(**changes):
    result = check({**PARAM_VALUES, **changes})
    assert result.ok, result.describe()
    return result.params


def close(a, b, tol=1e-9):
    return all(math.isclose(x, y, abs_tol=tol) for x, y in zip(a, b))


def angle_diff(a, b):
    return abs((a - b + 180.0) % 360.0 - 180.0)


def box_scan(cube_mm, base_to_fixture=(0.420255, -0.156675, 0.095006), scan_id='20260923-000000-0001'):
    """큐브 (x⁻, x⁺, y⁻, y⁺, z_top, z_support) [Base mm] → ScanInput(작업대 좌표 m). 계약 3.5절 순서."""
    x0, x1, y0, y1, zt, zs = (v / 1000.0 for v in cube_mm)
    bx, by, bz = base_to_fixture
    top = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    v = [(x - bx, y - by, zt - bz) for x, y in top] + [(x - bx, y - by, zs - bz) for x, y in top]
    edges = ([(v[i], v[(i + 1) % 4]) for i in range(4)]
             + [(v[i + 4], v[(i + 1) % 4 + 4]) for i in range(4)]
             + [(v[i], v[i + 4]) for i in range(4)])
    return ScanInput(
        scan_id=scan_id, frame_id='workpiece_fixture', motion_frame_id='base_link', edges=tuple(edges),
        z_top=zt - bz, support_z=zs - bz, base_to_fixture=base_to_fixture)


# ---- 자세 (2절) ----

def test_tilt_zero_is_vertical():
    frame = tool_frame(LINES[0].t, LINES[0].n_out, 0.0, 0.0)
    assert close(frame.z, (0.0, 0.0, -1.0))
    assert math.isclose(quaternion_to_zyz_deg(frame.quaternion)[1], 180.0, abs_tol=1e-9)


def test_l0_at_45_points_down_and_inward():
    # P2 지시서: L0 의 d = (0, .707, −.707). 팁은 이음선을 향해 아래 · 안쪽을 본다
    frame = tool_frame(LINES[0].t, LINES[0].n_out, math.radians(45.0), 0.0)
    assert close(frame.z, (0.0, R2, -R2))


@pytest.mark.parametrize('spec', LINES, ids=lambda s: s.name)
def test_axes_are_right_handed_and_match_quaternion(spec):
    frame = tool_frame(spec.t, spec.n_out, math.radians(45.0), math.radians(20.0))
    q = frame.quaternion
    assert math.isclose(sum(c * c for c in q), 1.0, abs_tol=1e-12) and q[3] >= 0.0
    for basis, axis in (((1, 0, 0), frame.x), ((0, 1, 0), frame.y), ((0, 0, 1), frame.z)):
        assert close(rotate(q, basis), axis, 1e-12)
    # 위빙 방향은 이음선 · 툴 축에 모두 수직이다
    assert math.isclose(sum(a * b for a, b in zip(frame.weave, spec.t)), 0.0, abs_tol=1e-12)
    assert math.isclose(sum(a * b for a, b in zip(frame.weave, frame.z)), 0.0, abs_tol=1e-12)


def test_roll_turns_tool_but_not_weave_or_axis():
    spec = LINES[1]
    plain = tool_frame(spec.t, spec.n_out, math.radians(45.0), 0.0)
    rolled = tool_frame(spec.t, spec.n_out, math.radians(45.0), math.radians(90.0))
    assert close(rolled.z, plain.z) and close(rolled.weave, plain.weave)
    assert close(rolled.x, plain.y, 1e-12)


def test_quaternion_from_axes_handles_all_branches():
    # trace ≤ 0 인 행렬(180° 회전 근처)도 같은 회전을 돌려준다
    for axes in (((1, 0, 0), (0, -1, 0), (0, 0, -1)), ((-1, 0, 0), (0, 1, 0), (0, 0, -1)),
                 ((-1, 0, 0), (0, -1, 0), (0, 0, 1)), ((0, 1, 0), (1, 0, 0), (0, 0, -1))):
        q = quaternion_from_axes(*axes)
        for basis, axis in zip(((1, 0, 0), (0, 1, 0), (0, 0, 1)), axes):
            assert close(rotate(q, basis), axis, 1e-12)


def test_zyz_matches_units_frames_home():
    # units-frames.md 48행: 새 홈 ZYZ (87.17, 180.00, 93.08) ↔ quaternion (0.0515581, 0.99866999, 3.83e−05, ~0)
    a, b, c = quaternion_to_zyz_deg((0.0515581, 0.99866999, 3.83e-05, -8.49e-08))
    assert math.isclose(b, 180.0, abs_tol=0.01)
    # b = 180° 에서는 a − c 만 정해진다: 87.17 − 93.08 = −5.91
    assert angle_diff(a - c, 87.17 - 93.08) < 0.02


def test_vertical_line_needs_tilt():
    with pytest.raises(PathRejected, match='tilt_deg > 0'):
        tool_frame(LINES[4].t, LINES[4].n_out, 0.0, 0.0)


# ---- M1 표 (docs/phase2/measurements-20260923.md, #186) ----
# 큐브 (x⁻ x⁺ y⁻ y⁺ z_top z_sup) Base mm = weld_pose_check.py DEFAULT_CUBE, 스탠드오프 3 mm · 기울임 45° · bottom_margin 5 mm
M1_CUBE = (378.48, 462.03, -198.75, -114.60, 178.003, 97.006)
M1 = {
    'L0': ([378.48, -200.87, 180.12], [462.03, -200.87, 180.12], (90.00, 135.00, -180.00)),
    'L1': ([464.15, -198.75, 180.12], [464.15, -114.60, 180.12], (-180.00, 135.00, -180.00)),
    'L2': ([462.03, -112.48, 180.12], [378.48, -112.48, 180.12], (-90.00, 135.00, -180.00)),
    'L3': ([376.36, -114.60, 180.12], [376.36, -198.75, 180.12], (0.00, 135.00, -180.00)),
    'L4': ([376.98, -200.25, 180.12], [376.98, -200.25, 104.13], (45.00, 135.00, -90.00)),
    'L5': ([463.53, -200.25, 180.12], [463.53, -200.25, 104.13], (135.00, 135.00, -90.00)),
    'L6': ([463.53, -113.10, 180.12], [463.53, -113.10, 104.13], (-135.00, 135.00, -90.00)),
    'L7': ([376.98, -113.10, 180.12], [376.98, -113.10, 104.13], (-45.00, 135.00, -90.00)),
}


@pytest.mark.parametrize('index', range(8), ids=lambda i: LINES[i].name)
def test_m1_poses(index):
    params = with_(weave_amplitude_m=0.0)   # M1 은 위빙 없는 선의 양 끝이다
    plan, _ = plan_line(box_scan(M1_CUBE), index, params)
    start_mm, end_mm, zyz = M1[plan.name]
    p_start, p_end = plan.path[0], plan.path[-2]    # path = [p0, pN, P_ret]
    assert close([v * 1000.0 for v in p_start], start_mm, 0.006)   # 표는 0.01 로 반올림
    assert close([v * 1000.0 for v in p_end], end_mm, 0.006)
    got = quaternion_to_zyz_deg(plan.orientation)
    assert all(angle_diff(g, w) < 0.006 for g, w in zip(got, zyz)), got


# ---- 위빙 (4절) ----

def test_weave_80mm_line_has_21_points_and_ends_on_seam():
    spec = LINES[0]
    frame = tool_frame(spec.t, spec.n_out, math.radians(45.0), 0.0)
    start, end = (0.0, 0.0, 0.0), (0.080, 0.0, 0.0)
    points = weave_points(start, end, (0.0, 0.0, 0.0), frame.weave, 0.002, 0.004)
    assert len(points) == 21
    assert close(points[0], start) and close(points[-1], end)
    lateral = [sum(a * b for a, b in zip(p, frame.weave)) for p in points]
    assert all(math.isclose(abs(v), 0.002, abs_tol=1e-12) for v in lateral[1:-1])
    assert all(lateral[k] * lateral[k + 1] < 0 for k in range(1, 19))   # 번갈아 반대쪽
    length = sum(math.dist(a, b) for a, b in zip(points, points[1:]))
    assert math.isclose(length, 0.1108, abs_tol=1e-4)   # 직선의 약 1.38 배 → 10 mm/s 에 약 11 s


def test_weave_zero_is_two_points():
    spec = LINES[0]
    frame = tool_frame(spec.t, spec.n_out, math.radians(45.0), 0.0)
    for amplitude, pitch in ((0.0, 0.004), (0.002, 0.0)):
        points = weave_points((0, 0, 0), (0.08, 0, 0), (0, 0, 0), frame.weave, amplitude, pitch)
        assert len(points) == 2


def test_short_last_step_ends_exactly_on_seam():
    spec = LINES[0]
    frame = tool_frame(spec.t, spec.n_out, math.radians(45.0), 0.0)
    points = weave_points((0, 0, 0), (0.0101, 0, 0), (0, 0, 0), frame.weave, 0.002, 0.004)
    assert len(points) == 4 and close(points[-1], (0.0101, 0.0, 0.0))


# ---- 선 계획 · 작업영역 (3 · 5절) ----

def test_line_plan_order_and_heights(params):
    scan = box_scan(M1_CUBE)
    plan, _ = plan_line(scan, 0, params)
    z_safe = (178.003 + 50.0) / 1000.0
    assert math.isclose(plan.approach1[2], z_safe, abs_tol=1e-12)
    assert math.isclose(plan.retreat[2], z_safe, abs_tol=1e-12)
    # 접근점 = 첫 경유점에서 툴 축 뒤로 approach_m
    back = [a - b for a, b in zip(plan.approach2, plan.path[0])]
    assert math.isclose(math.hypot(*back), 0.030, abs_tol=1e-12)
    assert plan.approach1[:2] == plan.approach2[:2]
    assert plan.retreat[:2] == plan.path[-1][:2]
    # 위빙이 있어도 첫 · 마지막 경유점은 이음선 + 스탠드오프 위다
    assert close([v * 1000 for v in plan.path[0]], M1['L0'][0], 0.006)


def test_vertical_seam_stops_above_support(params):
    scan = box_scan(M1_CUBE)
    plan, _ = plan_line(scan, 4, params)
    start, end = plan.seam_fixture
    assert math.isclose(end[2], scan.support_z + 0.005, abs_tol=1e-12)
    assert math.isclose(start[2], scan.z_top, abs_tol=1e-12)


def test_path_length_without_weave(params):
    plan, _ = plan_line(box_scan(M1_CUBE), 0, with_(weave_amplitude_m=0.0))
    assert math.isclose(plan.path_length_m, 0.030 + (462.03 - 378.48) / 1000.0 + 0.030, abs_tol=1e-9)


def test_fixture_plan_all_lines(fixture_store, params):
    scan = load_scan(fixture_store, FIXTURE_SCAN_ID, **FRAMES)
    plan = plan_weld(scan, 0, params)
    assert sorted(plan.lines) == list(range(8)) and len(plan.seams) == 8
    # Base = 작업대 + 그 스캔의 base_to_fixture (0.425, −0.184, 0.4)
    assert scan.base_to_fixture == (0.425, -0.184, 0.4)
    p0 = plan.lines[0].path[0]
    seam0 = plan.seams[0][0]
    assert math.isclose(p0[0], seam0[0] + 0.425, abs_tol=1e-9)
    assert math.isclose(plan.z_safe_base, scan.z_top + 0.050 + 0.4, abs_tol=1e-12)


def test_start_line_skips_earlier_lines(fixture_store, params):
    plan = plan_weld(load_scan(fixture_store, FIXTURE_SCAN_ID, **FRAMES), 5, params)
    assert sorted(plan.lines) == [5, 6, 7] and len(plan.seams) == 8


def test_tilt_zero_rejects_when_vertical_lines_are_included(fixture_store):
    scan = load_scan(fixture_store, FIXTURE_SCAN_ID, **FRAMES)
    with pytest.raises(PathRejected, match='L4'):
        plan_weld(scan, 0, with_(tilt_deg=0.0))


def test_workspace_margin_rejects(fixture_store):
    # 접근점은 모서리에서 대각선 바깥으로 (3 + 30)·sin45 ≈ 23 mm → 여유 10 mm 면 밖이다
    scan = load_scan(fixture_store, FIXTURE_SCAN_ID, **FRAMES)
    with pytest.raises(PathRejected, match='workspace_margin'):
        plan_weld(scan, 0, with_(workspace_margin_m=0.010))


def test_bottom_margin_taller_than_box_rejects(fixture_store):
    scan = load_scan(fixture_store, FIXTURE_SCAN_ID, **FRAMES)   # 상자 높이 약 40 mm
    with pytest.raises(PathRejected):
        plan_weld(scan, 0, with_(bottom_margin_m=0.050))


def test_start_line_out_of_range_is_programming_error(fixture_store, params):
    scan = load_scan(fixture_store, FIXTURE_SCAN_ID, **FRAMES)
    with pytest.raises(ValueError):
        plan_weld(scan, 8, params)


# ---- 결과 읽기 (5.1절) ----

def _failed(data):
    data['shape']['success'] = False
    data['shape']['reason_code'] = 501
    data['shape']['detail'] = '시험: 실패한 스캔'


def test_latest_success_skips_newer_failed_and_unfinished(store, tmp_path):
    write_result(tmp_path, '20260923-100000-0001')                     # 옛 성공
    write_result(tmp_path, '20260923-110000-0002', edit=_failed)       # 새 실패
    unfinished = tmp_path / '20260923-120000-0003'                     # 진행 기록만 있음
    unfinished.mkdir()
    (unfinished / 'progress.json').write_text('{}', encoding='utf-8')
    assert load_scan(store, '', **FRAMES).scan_id == '20260923-100000-0001'


def test_latest_success_skips_unreadable(store, tmp_path):
    write_result(tmp_path, '20260923-100000-0001')
    broken = write_result(tmp_path, '20260923-110000-0002')
    broken.write_text('{ 깨진 파일', encoding='utf-8')
    assert load_scan(store, '', **FRAMES).scan_id == '20260923-100000-0001'


def test_newest_success_unusable_is_not_silently_replaced(store, tmp_path):
    write_result(tmp_path, '20260923-100000-0001')

    def no_offset(data):
        del data['node_params']['base_to_fixture']
    write_result(tmp_path, '20260923-110000-0002', edit=no_offset)
    with pytest.raises(NoScanResult, match='base_to_fixture'):
        load_scan(store, '', **FRAMES)


@pytest.mark.parametrize('scan_id, match', [
    ('20260923-100000-9999', 'result.json 이 없다'), ('abc', '형식'),
])
def test_explicit_scan_id_problems(store, tmp_path, scan_id, match):
    write_result(tmp_path, '20260923-100000-0001')
    with pytest.raises(NoScanResult, match=match):
        load_scan(store, scan_id, **FRAMES)


def test_explicit_failed_scan_is_rejected(store, tmp_path):
    write_result(tmp_path, '20260923-100000-0001', edit=_failed)
    with pytest.raises(NoScanResult, match='성공하지 않았다'):
        load_scan(store, '20260923-100000-0001', **FRAMES)


def test_empty_store(store):
    with pytest.raises(NoScanResult, match='성공한 스캔 결과가 없다'):
        load_scan(store, '', **FRAMES)


def test_frame_mismatch_is_rejected(fixture_store):
    with pytest.raises(NoScanResult, match='motion_frame_id'):
        load_scan(fixture_store, FIXTURE_SCAN_ID, result_frame_id='workpiece_fixture',
                  motion_frame_id='world')
