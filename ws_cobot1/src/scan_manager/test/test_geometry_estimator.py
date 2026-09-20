"""geometry_estimator 단위 테스트. ROS 없이 돈다.

기대값을 잡는 법: "캘리퍼스로 잰 치수"에 해당하는 참값 블록을 정하고, 정방향 모델(팁이 모서리를 d 만큼 지나치면
얼마나 내려앉는가)로 판정 좌표를 만든 뒤, 추정기가 참값을 되찾는지 본다. 정방향 모델은 추정기의 식을 쓰지 않는다.
"""
import ast
import math
from pathlib import Path

import pytest
from scan_manager.contract_enums import Direction
from scan_manager.geometry_estimator import (
    BiasParams,
    EdgeObservation,
    edge_correction_m,
    estimate_box,
    GEOM_MISSING_POINT,
    GEOM_NEGATIVE_HEIGHT,
    GEOM_NONPOSITIVE_WIDTH,
    overshoot_m,
    top_correction_m,
    TopObservation,
)

MM = 1e-3
TIP_R = 0.225 * MM                       # units-frames.md v0.1.2 실측 팁 반지름
SHARP = BiasParams(tip_radius_m=TIP_R, detect_latency_s=0.040, edge_round_radius_m=0.0, edge_bias_offset_m=0.0)
SLIDE_V = 10 * MM                        # 테스트용 속도
DESCEND_V = 5 * MM

# 참값 블록: 80 mm 큐브가 작업대 좌표 원점에서 (+3, −2) mm 어긋나 놓였다 (축 평행)
TRUE = dict(x_pos=43 * MM, x_neg=-37 * MM, y_pos=38 * MM, y_neg=-42 * MM, z_top=80 * MM, support_z=0.0)
SIGN = {Direction.POS_X: 1, Direction.NEG_X: -1, Direction.POS_Y: 1, Direction.NEG_Y: -1}
KEY = {Direction.POS_X: 'x_pos', Direction.NEG_X: 'x_neg', Direction.POS_Y: 'y_pos', Direction.NEG_Y: 'y_neg'}


def drop_for_overshoot(d, r, big_r):
    """정방향 모델: 구 중심이 둥근 부분의 시작점을 d 만큼 지났을 때 팁 최하단이 내려앉은 양."""
    reach = r + big_r
    assert 0 <= d <= reach
    return reach - math.sqrt(reach * reach - d * d)


def observe_edges(params, overshoot=0.1 * MM, true=TRUE):
    """참값 모서리에서 정방향 모델로 만든 판정 좌표."""
    delta = drop_for_overshoot(overshoot, params.tip_radius_m, params.edge_round_radius_m)
    travelled_past_nominal = (overshoot - params.edge_round_radius_m
                              + SLIDE_V * params.detect_latency_s + params.edge_bias_offset_m)
    return {d: EdgeObservation(true[KEY[d]] + SIGN[d] * travelled_past_nominal, delta, SLIDE_V) for d in SIGN}


def observe_top(params, true=TRUE):
    return TopObservation(true['z_top'] - DESCEND_V * params.detect_latency_s, DESCEND_V)


# ---------------------------------------------------------------- 편향 보정

def test_brd_example_value():
    # BRD 1.4: r = 3 mm, δ = 0.5 mm, 10 mm/s, 40 ms → 약 1.7 + 0.4 = 2.1 mm
    params = BiasParams(3 * MM, 0.040, 0.0, 0.0)
    assert overshoot_m(0.5 * MM, 3 * MM, 0.0) == pytest.approx(math.sqrt(2.75) * MM)     # 1.658 mm
    assert edge_correction_m(0.5 * MM, 10 * MM, params) == pytest.approx(2.058 * MM, abs=1e-6)


@pytest.mark.parametrize('d_mm', [0.0, 0.05, 0.1, 0.2, 0.225])
def test_overshoot_inverts_forward_model(d_mm):
    delta = drop_for_overshoot(d_mm * MM, TIP_R, 0.0)
    assert overshoot_m(delta, TIP_R, 0.0) == pytest.approx(d_mm * MM, abs=1e-12)


@pytest.mark.parametrize('delta_mm', [0.225, 0.3, 0.4, 0.45, 0.5, 1.0, 5.0])
def test_overshoot_is_clamped_to_tip_radius_once_tip_has_left_the_edge(delta_mm):
    # δ ≥ r: 식을 그대로 쓰면 δ = 0.4 mm 에서 0.141 mm(덜 보정), δ > 0.45 mm 에서 제곱근 안이 음수다
    assert overshoot_m(delta_mm * MM, TIP_R, 0.0) == pytest.approx(TIP_R)


def test_rounded_edge_correction_can_be_negative():
    # R = 1.7 mm 로 둥글린 모서리: δ = 0.5 mm 로 판정한 좌표는 공칭 모서리보다 0.4 mm 안쪽이다
    rounded = BiasParams(TIP_R, 0.0, 1.7 * MM, 0.0)
    d = overshoot_m(0.5 * MM, TIP_R, 1.7 * MM)
    assert d == pytest.approx(math.sqrt(2 * 1.925 * 0.5 - 0.25) * MM)                    # 1.294 mm
    assert edge_correction_m(0.5 * MM, SLIDE_V, rounded) == pytest.approx(d - 1.7 * MM)
    assert edge_correction_m(0.5 * MM, SLIDE_V, rounded) < 0


def test_top_correction_is_speed_times_latency():
    assert top_correction_m(DESCEND_V, SHARP) == pytest.approx(0.2 * MM)


@pytest.mark.parametrize('bad', [None, float('nan'), float('inf'), -0.1 * MM, True])
def test_bad_inputs_raise(bad):
    with pytest.raises(ValueError):
        overshoot_m(bad, TIP_R, 0.0)
    with pytest.raises(ValueError):
        edge_correction_m(0.1 * MM, bad, SHARP)


def test_params_reject_negative_or_missing():
    with pytest.raises(ValueError):
        BiasParams(-TIP_R, 0.04, 0.0, 0.0)
    with pytest.raises(ValueError):
        BiasParams(TIP_R, None, 0.0, 0.0)
    BiasParams(TIP_R, 0.04, 0.0, -0.3 * MM)      # 실측 보정 상수는 음수일 수 있다


# ---------------------------------------------------------------- 형상

@pytest.mark.parametrize('params', [
    SHARP,
    BiasParams(TIP_R, 0.040, 1.7 * MM, 0.0),                 # 둥근 모서리
    BiasParams(TIP_R, 0.025, 0.0, 0.15 * MM),                # 실측 보정 상수
    BiasParams(3 * MM, 0.040, 0.0, 0.0),                     # BRD 출발값의 팁
])
def test_recovers_caliper_dimensions(params):
    box = estimate_box(observe_top(params), observe_edges(params), TRUE['support_z'], params)
    assert box.success and box.error == ''
    for name, value in TRUE.items():
        assert getattr(box, name) == pytest.approx(value, abs=1e-9), name
    assert (box.width, box.length, box.height) == pytest.approx((80 * MM, 80 * MM, 80 * MM), abs=1e-9)
    assert box.dims_valid and box.box_valid


def test_without_correction_width_would_be_too_large():
    # 보정 방향 확인: 판정 좌표는 네 방향 모두 바깥으로 밀려 있다
    edges = observe_edges(SHARP)
    raw_width = edges[Direction.POS_X].coordinate_m - edges[Direction.NEG_X].coordinate_m
    assert raw_width - 80 * MM == pytest.approx(2 * (0.1 + 0.4) * MM)


def test_recovers_when_tip_has_fully_left_the_edge():
    # 실기 조건: edge_drop_m(0.5 mm) > r(0.225 mm). 팁이 모서리를 r 만큼 지난 뒤 옆면을 따라 0.5 mm 까지 내려앉았다.
    # 그동안 수평으로 더 나간 거리를 실측 보정 상수로 넣으면 치수가 돌아온다
    extra = 0.275 * MM
    params = BiasParams(TIP_R, 0.040, 0.0, extra)
    past = TIP_R + SLIDE_V * 0.040 + extra
    edges = {d: EdgeObservation(TRUE[KEY[d]] + SIGN[d] * past, 0.5 * MM, SLIDE_V) for d in SIGN}
    box = estimate_box(observe_top(params), edges, 0.0, params)
    assert box.success
    assert box.width == pytest.approx(80 * MM, abs=1e-9)
    # 상수를 넣지 않으면 그만큼 크게 나온다 (방향당 0.275 mm)
    loose = estimate_box(observe_top(SHARP), edges, 0.0, SHARP)
    assert loose.width - 80 * MM == pytest.approx(2 * extra)


def test_order_convention():
    box = estimate_box(observe_top(SHARP), observe_edges(SHARP), 0.0, SHARP)
    xn, xp, yn, yp, zt = -37 * MM, 43 * MM, -42 * MM, 38 * MM, 80 * MM
    expected_top = [(xn, yn, zt), (xp, yn, zt), (xp, yp, zt), (xn, yp, zt)]      # (x−, y−) 부터 반시계
    for i in range(4):
        assert box.vertices[i] == pytest.approx(expected_top[i], abs=1e-9)
        assert box.vertices[i + 4] == pytest.approx(expected_top[i][:2] + (0.0,), abs=1e-9)   # 바로 아래
        assert (box.edges[i].start, box.edges[i].end) == (box.vertices[i], box.vertices[(i + 1) % 4])
        assert (box.edges[i + 4].start, box.edges[i + 4].end) == (box.vertices[i + 4], box.vertices[(i + 1) % 4 + 4])
        assert (box.edges[i + 8].start, box.edges[i + 8].end) == (box.vertices[i], box.vertices[i + 4])
        assert box.path_candidates[i] == box.edges[i]                               # 같은 선분 · 같은 방향
    # 경로 후보 0 = y− 변, 1 = x+ 변, 2 = y+ 변, 3 = x− 변
    assert [round(s.length / MM, 6) for s in box.path_candidates] == [80, 80, 80, 80]
    assert all(v[1] == pytest.approx(yn) for v in (box.path_candidates[0].start, box.path_candidates[0].end))
    assert all(v[0] == pytest.approx(xp) for v in (box.path_candidates[1].start, box.path_candidates[1].end))
    assert len(box.vertices) == 8 and len(box.edges) == 12 and len(box.path_candidates) == 4
    assert [round(e.length / MM, 6) for e in box.edges[8:]] == [80] * 4


def test_bias_corrections_match_result_store_names():
    edges = observe_edges(SHARP)
    box = estimate_box(observe_top(SHARP), edges, 0.0, SHARP)
    c = box.bias_corrections[Direction.NEG_X]
    assert c.valid and c.raw_coordinate_m == edges[Direction.NEG_X].coordinate_m
    assert c.correction_m == pytest.approx(0.5 * MM)                     # d 0.1 + v·t 0.4
    assert c.corrected_m == pytest.approx(c.raw_coordinate_m + c.correction_m)   # −x 방향으로 갔으니 +x 로 되돌린다
    assert {'z_drop_m', 'tip_radius_m', 'slide_speed_mps', 'detect_latency_s'} <= set(c.inputs)
    assert box.top_correction.corrected_m == pytest.approx(80 * MM)


# ---------------------------------------------------------------- 비정상

def failed_with(edges=None, top='default', support=0.0):
    edges = observe_edges(SHARP) if edges is None else edges
    top = observe_top(SHARP) if top == 'default' else top
    return estimate_box(top, edges, support, SHARP)


def assert_no_box(box):
    assert not box.success and not box.box_valid and not box.dims_valid
    assert box.vertices == (None,) * 8 and box.edges == (None,) * 12 and box.path_candidates == (None,) * 4
    assert (box.width, box.length, box.height) == (None, None, None)       # 0 이 아니다


def test_missing_direction_keeps_what_was_measured():
    edges = observe_edges(SHARP)
    del edges[Direction.POS_Y]
    box = failed_with(edges)
    assert box.error == GEOM_MISSING_POINT and 'POS_Y' in box.detail
    assert_no_box(box)
    assert box.y_pos is None
    assert box.x_pos == pytest.approx(TRUE['x_pos']) and box.z_top == pytest.approx(TRUE['z_top'])
    assert not box.bias_corrections[Direction.POS_Y].valid


@pytest.mark.parametrize('broken', [
    EdgeObservation(None, 0.1 * MM, SLIDE_V),
    EdgeObservation(float('nan'), 0.1 * MM, SLIDE_V),
    EdgeObservation(0.043, None, SLIDE_V),               # 하강량을 모르면 보정할 수 없다. 보정 없이 통과시키지 않는다
    EdgeObservation(0.043, float('nan'), SLIDE_V),
    EdgeObservation(0.043, 0.1 * MM, None),
])
def test_incomplete_edge_observation_is_missing_point(broken):
    edges = observe_edges(SHARP)
    edges[Direction.POS_X] = broken
    box = failed_with(edges)
    assert box.error == GEOM_MISSING_POINT and 'POS_X' in box.detail
    assert box.x_pos is None
    assert_no_box(box)


def test_missing_top_or_support():
    assert failed_with(top=None).error == GEOM_MISSING_POINT
    assert failed_with(top=TopObservation(None, DESCEND_V)).z_top is None
    assert failed_with(support=None).error == GEOM_MISSING_POINT
    assert failed_with(support=float('nan')).support_z is None


def test_nonpositive_width():
    edges = observe_edges(SHARP)
    edges[Direction.POS_X], edges[Direction.NEG_X] = edges[Direction.NEG_X], edges[Direction.POS_X]
    box = failed_with(edges)
    assert box.error == GEOM_NONPOSITIVE_WIDTH
    assert_no_box(box)
    assert box.x_pos is not None and box.x_pos < box.x_neg        # 얻은 좌표는 남긴다


def test_negative_or_zero_height():
    assert failed_with(support=0.090).error == GEOM_NEGATIVE_HEIGHT
    box = failed_with(support=TRUE['z_top'])
    assert box.error == GEOM_NEGATIVE_HEIGHT
    assert_no_box(box)


def test_module_does_not_import_rclpy():
    root = Path(__file__).resolve().parents[1] / 'scan_manager' / 'geometry_estimator'
    files = sorted(root.glob('*.py'))
    assert files
    for path in files:
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                [node.module or ''] if isinstance(node, ast.ImportFrom) else [])
            assert not any(n.split('.')[0] in ('rclpy', 'contact_scan_interfaces', 'numpy') for n in names), path
