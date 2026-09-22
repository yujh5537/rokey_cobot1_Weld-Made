"""측정 5점 → 실제 geometry_estimator → ShapeResult (ROS 없음). 수치는 테스트용 임의값이다."""

import pytest
from result_store_helpers import CONFIG
from result_store_helpers import FakeClock
from result_store_helpers import FRAMES
from result_store_helpers import ORDER
from result_store_helpers import snapshot
from scan_manager import geometry_adapter as G
from scan_manager.contract_enums import Direction
from scan_manager.contract_enums import Reason
from scan_manager.result_store import ResultStore
from scan_manager.result_store import Stamp
from sequence_helpers import make_params
from sequence_helpers import SCAN_ID
from sequence_helpers import SIGN

STARTED, FINISHED = Stamp(100, 5), Stamp(160, 7)
# 실기처럼 작업대 원점이 Base 와 x · y · z 모두 떨어져 있는 경우
ORIGIN = (0.4235, -0.1871, 0.1006)
HALF = {Direction.POS_X: 0.05, Direction.NEG_X: 0.05, Direction.POS_Y: 0.03, Direction.NEG_Y: 0.03}
TOP_Z = 0.04
Z_DROP = 0.0005


def measurements(params, origin=ORIGIN, skip=(), z_drop=Z_DROP):
    """정방향 모델: 참값 상자에서 판정 좌표(Base)를 만든다. δ ≥ r 이므로 기하 항은 r 이다."""
    latency = params.detect_latency_s
    top = G.TopMeasurement(
        (origin[0], origin[1], origin[2] + TOP_Z - params.descend_speed_mps * latency),
        params.descend_speed_mps)
    edges = {}
    for direction, half in HALF.items():
        if direction in skip:
            continue
        overshoot = (params.tip_radius_m + params.slide_speed_mps * latency
                     + params.edge_bias_offset_m)
        position = [origin[0], origin[1], origin[2] + TOP_Z - Z_DROP]
        position[G.AXIS[direction]] += SIGN[direction] * (half + overshoot)
        edges[direction] = G.EdgeMeasurement(tuple(position), z_drop, params.slide_speed_mps)
    return top, edges


def compute(params, top, edges, **kwargs):
    return G.compute_shape(top, edges, params, started_at=STARTED, finished_at=FINISHED, **kwargs)


@pytest.fixture
def params():
    # 기준점은 작업대 원점의 위 0.10 m (하강 한계가 지지면에 닿지 않아야 한다)
    origin = [ORIGIN[0], ORIGIN[1], ORIGIN[2] + 0.10, 0.0, 1.0, 0.0, 0.0]
    return make_params(base_to_fixture=list(ORIGIN), search_origin_pose=origin)


def test_to_fixture_is_a_translation():
    assert G.to_fixture((0.45, -0.15, 0.14), ORIGIN) == pytest.approx((0.0265, 0.0371, 0.0394))


def test_box_is_recovered_in_the_fixture_frame(params):
    output = compute(params, *measurements(params))
    shape = output.shape

    assert shape.success and shape.reason_code == 0 and shape.detail == ''
    assert shape.frame_id == params.result_frame_id
    assert (shape.started_at, shape.finished_at) == (STARTED, FINISHED)
    assert (shape.x_pos.value, shape.x_neg.value) == pytest.approx((0.05, -0.05))
    assert (shape.y_pos.value, shape.y_neg.value) == pytest.approx((0.03, -0.03))
    assert shape.z_top.value == pytest.approx(TOP_Z)
    assert shape.support_z.value == params.support_z_m
    assert (shape.width, shape.length, shape.height) == pytest.approx((0.10, 0.06, 0.04))
    assert shape.dims_valid and shape.box_valid
    # 순서 규약(계약 3.5절): 0 = (x−, y−) 윗면, 4 = 그 바로 아래
    assert shape.vertices[0] == pytest.approx((-0.05, -0.03, TOP_Z))
    assert shape.vertices[6] == pytest.approx((0.05, 0.03, 0.0))
    assert len(shape.edges) == 12 and len(shape.path_candidates) == 4
    assert all(segment.valid for segment in shape.edges + shape.path_candidates)
    assert shape.path_candidates[0].length == pytest.approx(0.10)


def test_bias_corrections_keep_the_raw_detection_in_base(params):
    top, edges = measurements(params)
    output = compute(params, top, edges)
    for direction, correction in output.bias_corrections.items():
        assert correction.valid
        assert correction.raw_coordinate_m == edges[direction].position_m[G.AXIS[direction]]
        assert correction.inputs['slide_speed_mps'] == params.slide_speed_mps
        assert correction.inputs['tip_radius_m'] == params.tip_radius_m
    assert output.top_correction.valid
    assert output.top_correction.correction_m == pytest.approx(
        params.descend_speed_mps * params.detect_latency_s)


def test_missing_edge_is_insufficient_points_and_keeps_what_was_measured(params):
    output = compute(params, *measurements(params, skip=(Direction.NEG_Y,)))
    shape = output.shape
    assert not shape.success and shape.reason_code == Reason.INSUFFICIENT_POINTS
    assert shape.detail.startswith('GEOM_MISSING_POINT')  # 원문은 detail 에 남긴다(계약 6.1절)
    assert shape.y_pos.valid and shape.z_top.valid
    assert shape.y_neg.valid is False and shape.y_neg.value is None   # 0 이 아니다
    assert shape.dims_valid is False and shape.width is None
    assert shape.box_valid is False and shape.vertices == (None,) * 8
    assert all(not s.valid and s.start is None for s in shape.edges + shape.path_candidates)
    assert output.bias_corrections[Direction.NEG_Y].valid is False
    assert output.bias_corrections[Direction.NEG_Y].raw_coordinate_m is None


def test_unknown_z_drop_is_corrected_with_zero_overshoot(params):
    # #146: δ 를 모르면(z_drop_valid=false) 실패가 아니라 기하 항 d = 0 으로 보정한다. δ 는 None 그대로 남는다.
    # 이 정방향 모델은 δ ≥ R + r(기하 항 R + r)이라, d = 0 가정은 방향당 R + r 만큼 덜 보정한다(오차의 최대치)
    output = compute(params, *measurements(params, z_drop=None))
    shape = output.shape
    assert shape.success and shape.reason_code == Reason.OK
    reach = params.tip_radius_m + params.edge_round_radius_m
    assert shape.width == pytest.approx(2 * HALF[Direction.POS_X] + 2 * reach)
    assert shape.length == pytest.approx(2 * HALF[Direction.POS_Y] + 2 * reach)
    assert all(c.valid and c.inputs['z_drop_m'] is None for c in output.bias_corrections.values())


def test_non_positive_width_is_invalid_shape(params):
    top, edges = measurements(params)
    edges[Direction.POS_X], edges[Direction.NEG_X] = edges[Direction.NEG_X], edges[Direction.POS_X]
    shape = compute(params, top, edges).shape
    assert not shape.success and shape.reason_code == Reason.INVALID_SHAPE
    assert 'GEOM_NONPOSITIVE_WIDTH' in shape.detail
    assert shape.x_pos.valid and shape.dims_valid is False


def test_negative_height_is_invalid_shape(params):
    top, edges = measurements(params)
    sunk = G.TopMeasurement((top.position_m[0], top.position_m[1], ORIGIN[2] - 0.01), top.descend_speed_mps)
    shape = compute(params, sunk, edges).shape
    assert shape.reason_code == Reason.INVALID_SHAPE and 'GEOM_NEGATIVE_HEIGHT' in shape.detail


def test_scan_that_ended_early_reports_its_own_reason(params):
    top, edges = measurements(params, skip=(Direction.POS_Y, Direction.NEG_Y))
    shape = compute(params, top, edges, ended_with=(int(Reason.NO_EDGE), 'max_slide_m 안에 없다')).shape
    assert not shape.success
    assert (shape.reason_code, shape.detail) == (Reason.NO_EDGE, 'max_slide_m 안에 없다')
    assert shape.x_pos.value == pytest.approx(0.05) and shape.z_top.value == pytest.approx(TOP_Z)
    assert shape.y_pos.value is None and not shape.y_pos.valid


def test_nothing_measured_yet(params):
    shape = compute(params, None, {}, ended_with=(int(Reason.STOP_REQUESTED), 'stopped')).shape
    assert shape.reason_code == Reason.STOP_REQUESTED
    for name in ('z_top', 'x_pos', 'x_neg', 'y_pos', 'y_neg'):
        measured = getattr(shape, name)
        assert measured.value is None and not measured.valid
    assert shape.support_z.valid  # 지지면 높이는 파라미터라 안다


def test_ended_with_needs_a_reason(params):
    with pytest.raises(ValueError):
        compute(params, None, {}, ended_with=(0, ''))


def test_output_is_accepted_by_result_store(params, tmp_path):
    store = ResultStore(tmp_path, now_fn=FakeClock())
    store.begin_scan(
        SCAN_ID, state=snapshot(SCAN_ID), config=CONFIG, frames=FRAMES, direction_order=ORDER,
        node_params=params.node_params())
    output = compute(params, *measurements(params))

    store.save_result(SCAN_ID, output.shape, output.bias_corrections)

    saved = store.load_result(SCAN_ID)
    assert saved.shape == output.shape
    assert saved.bias_corrections[Direction.POS_X].correction_m == pytest.approx(
        output.bias_corrections[Direction.POS_X].correction_m)
    assert saved.node_params['tip_radius_m'] == params.tip_radius_m
    # 파일에는 NaN 이 나오지 않는다(무효 값은 null)
    assert 'NaN' not in (tmp_path / SCAN_ID / 'result.json').read_text(encoding='utf-8')
