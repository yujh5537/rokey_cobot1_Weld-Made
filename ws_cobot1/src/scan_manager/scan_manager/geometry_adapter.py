"""측정 5점 → geometry_estimator → result_store 의 ShapeResult (순수 Python, rclpy 없음).

geometry_estimator(현지, T17)를 import 하는 곳은 scan_manager 안에서 이 파일 하나다.

- 프레임: 판정 좌표는 Base 다. ScanResult 는 작업대 좌표이므로 **호출 전에 base_to_fixture 를 뺀다**
  (평행 이동만. units-frames.md). support_z_m 은 이미 작업대 좌표의 값이다.
- 속도는 그 모션의 goal 에 실제로 실은 값을 넘긴다. 모르면 estimator 가 보정 없이 통과시키지 않고
  GEOM_MISSING_POINT 로 실패시킨다.
- 실패 · 중단으로 끝난 작업도 같은 경로를 탄다. 확보한 값만 유효하고 나머지는 None 이다(0 금지, CLAUDE.md 규칙 4).
"""

from dataclasses import dataclass
from typing import Dict, Mapping, Optional, Tuple

from .contract_enums import Direction
from .contract_enums import Reason
from .geometry_estimator import BiasParams
from .geometry_estimator import BoxEstimate
from .geometry_estimator import Correction
from .geometry_estimator import EDGE_DIRECTIONS
from .geometry_estimator import EdgeObservation
from .geometry_estimator import estimate_box
from .geometry_estimator import GEOM_MISSING_POINT
from .geometry_estimator import GEOM_NEGATIVE_HEIGHT
from .geometry_estimator import GEOM_NONPOSITIVE_WIDTH
from .geometry_estimator import TopObservation
from .params import ScanParams
from .result_store import BiasCorrection
from .result_store import Measured
from .result_store import SegmentRecord
from .result_store import ShapeResult
from .result_store import Stamp

Position = Tuple[float, float, float]

# 계약 6.1절: geometry_estimator 내부 오류 문자열 → ReasonCode. 원문은 detail 에 넣는다.
GEOM_REASON = {
    GEOM_MISSING_POINT: Reason.INSUFFICIENT_POINTS,
    GEOM_NONPOSITIVE_WIDTH: Reason.INVALID_SHAPE,
    GEOM_NEGATIVE_HEIGHT: Reason.INVALID_SHAPE,
}
# 밀기 방향 → 판정 좌표에서 읽을 축 (±X 는 x, ±Y 는 y)
AXIS = {Direction.POS_X: 0, Direction.NEG_X: 0, Direction.POS_Y: 1, Direction.NEG_Y: 1}


@dataclass(frozen=True)
class TopMeasurement:
    position_m: Position          # CONTACT 판정 좌표 (Base)
    descend_speed_mps: float      # 그 DESCEND goal 의 speed


@dataclass(frozen=True)
class EdgeMeasurement:
    position_m: Position          # EDGE 판정 좌표 (Base)
    z_drop_m: Optional[float]     # ContactEvent.z_drop_m. z_drop_valid=false 면 None
    slide_speed_mps: float        # 그 SLIDE goal 의 speed


@dataclass(frozen=True)
class GeometryOutput:
    shape: ShapeResult
    bias_corrections: Dict[Direction, BiasCorrection]  # result.json 에만 남긴다(계약 3.5절)
    top_correction: Correction                         # result_store 에 아직 자리가 없다
    estimate: BoxEstimate


def to_fixture(position_m: Position, base_to_fixture: Position) -> Position:
    """Base 좌표 → 작업대 좌표. 평행 이동만 한다."""
    return tuple(p - o for p, o in zip(position_m, base_to_fixture))


def bias_params(params: ScanParams) -> BiasParams:
    return BiasParams(
        tip_radius_m=params.tip_radius_m, detect_latency_s=params.detect_latency_s,
        edge_round_radius_m=params.edge_round_radius_m,
        edge_bias_offset_m=params.edge_bias_offset_m)


def _observations(top, edges, base_to_fixture):
    top_obs = None
    if top is not None:
        top_obs = TopObservation(
            z_m=to_fixture(top.position_m, base_to_fixture)[2],
            descend_speed_mps=top.descend_speed_mps)
    edge_obs = {}
    for direction in EDGE_DIRECTIONS:
        edge = edges.get(direction)
        if edge is None:
            edge_obs[direction] = None
            continue
        edge_obs[direction] = EdgeObservation(
            coordinate_m=to_fixture(edge.position_m, base_to_fixture)[AXIS[direction]],
            z_drop_m=edge.z_drop_m, slide_speed_mps=edge.slide_speed_mps)
    return top_obs, edge_obs


def _segments(values, count):
    if all(v is None for v in values):
        return tuple(SegmentRecord() for _ in range(count))
    return tuple(SegmentRecord(tuple(s.start), tuple(s.end), s.length, True) for s in values)


def _measured(value) -> Measured:
    return Measured.missing() if value is None else Measured.of(value)


def _bias_correction(direction, correction: Correction, edge) -> BiasCorrection:
    # raw_coordinate_m 은 판정 좌표의 프레임(Base) 값이다. estimator 의 raw 는 작업대 좌표라 쓰지 않는다.
    raw = edge.position_m[AXIS[direction]] if (correction.valid and edge is not None) else None
    return BiasCorrection(
        raw_coordinate_m=raw, correction_m=correction.correction_m if correction.valid else None,
        valid=correction.valid, inputs=dict(correction.inputs))


def compute_shape(
    top: Optional[TopMeasurement],
    edges: Mapping[Direction, Optional[EdgeMeasurement]],
    params: ScanParams,
    *,
    started_at: Stamp,
    finished_at: Stamp,
    ended_with: Optional[Tuple[int, str]] = None,
) -> GeometryOutput:
    """형상을 계산한다.

    ended_with: 측정이 끝나기 전에 끝난 작업의 (reason_code, detail). 주면 계산 결과와 무관하게
      success=false 이고 그 사유가 결과에 실린다(예: NO_EDGE, STOP_REQUESTED). 확보한 값은 그대로 유효하다.
    """
    top_obs, edge_obs = _observations(top, edges, params.base_to_fixture)
    box = estimate_box(top_obs, edge_obs, params.support_z_m, bias_params(params))

    if ended_with is not None:
        success, reason_code, detail = False, int(ended_with[0]), ended_with[1]
        if not reason_code:
            raise ValueError('ended_with 의 reason_code 는 0 이 아니어야 한다')
    elif box.success:
        success, reason_code, detail = True, int(Reason.OK), ''
    else:
        success, reason_code = False, int(GEOM_REASON[box.error])
        detail = f'{box.error}: {box.detail}'

    full = box.success  # 치수 · 직육면체는 5점이 다 있고 형상이 정상일 때만 있다
    shape = ShapeResult(
        success=success, reason_code=reason_code, detail=detail,
        frame_id=params.result_frame_id, started_at=started_at, finished_at=finished_at,
        z_top=_measured(box.z_top), x_pos=_measured(box.x_pos), x_neg=_measured(box.x_neg),
        y_pos=_measured(box.y_pos), y_neg=_measured(box.y_neg),
        support_z=_measured(box.support_z),
        width=box.width if full else None, length=box.length if full else None,
        height=box.height if full else None, dims_valid=full,
        vertices=tuple(box.vertices) if full else (None,) * 8,
        edges=_segments(box.edges if full else (None,) * 12, 12),
        path_candidates=_segments(box.path_candidates if full else (None,) * 4, 4),
        box_valid=full,
    )
    corrections = {
        direction: _bias_correction(direction, box.bias_corrections[direction], edges.get(direction))
        for direction in EDGE_DIRECTIONS
    }
    return GeometryOutput(shape, corrections, box.top_correction, box)
