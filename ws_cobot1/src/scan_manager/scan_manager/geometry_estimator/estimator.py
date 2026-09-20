"""윗면 1점 + 모서리 4점 → 윗면 사각형 · 외곽 엣지·경로 후보 · 직육면체 (BRD 4.3.1~4.3.3 · 4.3.5).

rclpy 를 import 하지 않는다. scan_manager 가 함수로 부른다.

- 프레임: 입력 좌표와 support_z_m 은 같은 프레임이어야 한다. 출력도 그 프레임이다. 프레임 변환은 하지 않는다
  (Base → 작업대 좌표의 평행 이동은 scan_manager 가 호출 전에 한다. units-frames.md).
- 전제: 부재의 변이 축과 평행하다(BRD 6장). 모서리 관측은 진행 축의 좌표 하나만 쓴다.
- 미측정값은 None 이다. 0 을 넣지 않는다. 실패해도 얻은 값은 돌려준다.
- 순서 규약(꼭짓점 · 엣지 · 경로 후보)은 ros-interfaces.md 3.5절 그대로다.
- 결과물은 외곽 엣지·경로 후보다. 용접 이음 판정이 아니다.
"""
from dataclasses import dataclass, field
from typing import Dict, Mapping, Optional, Tuple

from ..contract_enums import Direction
from .bias import BiasParams, edge_correction_m, top_correction_m

Point = Tuple[float, float, float]

EDGE_DIRECTIONS = (Direction.POS_X, Direction.NEG_X, Direction.POS_Y, Direction.NEG_Y)
_TRAVEL_SIGN = {Direction.POS_X: 1.0, Direction.NEG_X: -1.0, Direction.POS_Y: 1.0, Direction.NEG_Y: -1.0}

# 실패 사유. scan_manager 가 ReasonCode 로 옮긴다 (ros-interfaces.md 6.1절)
GEOM_MISSING_POINT = 'GEOM_MISSING_POINT'                # → INSUFFICIENT_POINTS(501)
GEOM_NONPOSITIVE_WIDTH = 'GEOM_NONPOSITIVE_WIDTH'        # → INVALID_SHAPE(500). 가로 또는 세로가 0 이하
GEOM_NEGATIVE_HEIGHT = 'GEOM_NEGATIVE_HEIGHT'            # → INVALID_SHAPE(500). 높이가 0 이하


@dataclass(frozen=True)
class TopObservation:
    """윗면 CONTACT 판정 좌표."""

    z_m: Optional[float]                  # 판정 샘플의 TCP z
    descend_speed_mps: Optional[float]    # 그 하강의 속도


@dataclass(frozen=True)
class EdgeObservation:
    """한 방향의 EDGE 판정 좌표."""

    coordinate_m: Optional[float]         # 판정 샘플의 TCP 좌표 중 진행 축의 값 (±X 는 x, ±Y 는 y)
    z_drop_m: Optional[float]             # ContactEvent.z_drop_m. 판정 시점의 실제 하강량 δ
    slide_speed_mps: Optional[float]      # 그 밀기의 속도


@dataclass(frozen=True)
class Correction:
    """보정 1건. result_store 의 BiasCorrection 과 같은 이름을 쓴다.

    corrected = raw_coordinate_m − 진행 방향 부호 x correction_m  (윗면은 raw + correction)
    """

    raw_coordinate_m: Optional[float] = None
    correction_m: Optional[float] = None
    corrected_m: Optional[float] = None
    valid: bool = False
    inputs: Mapping[str, Optional[float]] = field(default_factory=dict)
    detail: str = ''                      # 무효인 이유


@dataclass(frozen=True)
class Segment:
    start: Point
    end: Point
    length: float


@dataclass(frozen=True)
class BoxEstimate:
    """필드 이름은 ScanResult.msg · result_store.ShapeResult 와 같다."""

    success: bool
    error: str                            # '' | GEOM_*
    detail: str
    z_top: Optional[float] = None         # 보정 후
    x_pos: Optional[float] = None
    x_neg: Optional[float] = None
    y_pos: Optional[float] = None
    y_neg: Optional[float] = None
    support_z: Optional[float] = None
    width: Optional[float] = None         # x_pos − x_neg
    length: Optional[float] = None        # y_pos − y_neg
    height: Optional[float] = None        # z_top − support_z
    dims_valid: bool = False
    vertices: Tuple[Optional[Point], ...] = (None,) * 8
    edges: Tuple[Optional[Segment], ...] = (None,) * 12
    path_candidates: Tuple[Optional[Segment], ...] = (None,) * 4
    box_valid: bool = False
    top_correction: Correction = field(default_factory=Correction)
    bias_corrections: Mapping[Direction, Correction] = field(default_factory=dict)


def _segment(start: Point, end: Point) -> Segment:
    length = sum((b - a) ** 2 for a, b in zip(start, end)) ** 0.5
    return Segment(start, end, length)


def _correct_top(top: Optional[TopObservation], params: BiasParams) -> Correction:
    if top is None or top.z_m is None:
        return Correction(detail='윗면 판정 좌표가 없다')
    inputs = {'descend_speed_mps': top.descend_speed_mps, 'detect_latency_s': params.detect_latency_s}
    try:
        raw = float(top.z_m)
        if raw != raw:
            raise ValueError('z_m 이 NaN 이다')
        correction = top_correction_m(top.descend_speed_mps, params)
    except (TypeError, ValueError) as e:
        return Correction(inputs=inputs, detail=f'윗면: {e}')
    return Correction(raw, correction, raw + correction, True, inputs)


def _correct_edge(direction: Direction, edge: Optional[EdgeObservation], params: BiasParams) -> Correction:
    if edge is None or edge.coordinate_m is None:
        return Correction(detail=f'{direction.name} 판정 좌표가 없다')
    inputs = {
        'z_drop_m': edge.z_drop_m,
        'slide_speed_mps': edge.slide_speed_mps,
        'tip_radius_m': params.tip_radius_m,
        'detect_latency_s': params.detect_latency_s,
        'edge_round_radius_m': params.edge_round_radius_m,
        'edge_bias_offset_m': params.edge_bias_offset_m,
    }
    try:
        raw = float(edge.coordinate_m)
        if raw != raw:
            raise ValueError('coordinate_m 이 NaN 이다')
        correction = edge_correction_m(edge.z_drop_m, edge.slide_speed_mps, params)
    except (TypeError, ValueError) as e:
        return Correction(inputs=inputs, detail=f'{direction.name}: {e}')
    return Correction(raw, correction, raw - _TRAVEL_SIGN[direction] * correction, True, inputs)


def estimate_box(top: Optional[TopObservation], edges: Mapping[Direction, Optional[EdgeObservation]],
                 support_z_m: float, params: BiasParams) -> BoxEstimate:
    """5점과 지지면 높이로 직육면체를 만든다. 예외를 던지지 않고 BoxEstimate.error 로 알린다."""
    top_c = _correct_top(top, params)
    edge_c: Dict[Direction, Correction] = {
        d: _correct_edge(d, edges.get(d), params) for d in EDGE_DIRECTIONS}
    support_ok = support_z_m is not None and support_z_m == support_z_m

    partial = dict(
        z_top=top_c.corrected_m,
        x_pos=edge_c[Direction.POS_X].corrected_m, x_neg=edge_c[Direction.NEG_X].corrected_m,
        y_pos=edge_c[Direction.POS_Y].corrected_m, y_neg=edge_c[Direction.NEG_Y].corrected_m,
        support_z=float(support_z_m) if support_ok else None,
        top_correction=top_c, bias_corrections=edge_c,
    )

    missing = [c.detail for c in (top_c, *edge_c.values()) if not c.valid]
    if not support_ok:
        missing.append('support_z_m 이 없다')
    if missing:
        return BoxEstimate(False, GEOM_MISSING_POINT, ' / '.join(missing), **partial)

    z_top, z_bot = partial['z_top'], partial['support_z']
    x_pos, x_neg, y_pos, y_neg = (partial[k] for k in ('x_pos', 'x_neg', 'y_pos', 'y_neg'))
    width, length, height = x_pos - x_neg, y_pos - y_neg, z_top - z_bot

    if width <= 0 or length <= 0:
        return BoxEstimate(False, GEOM_NONPOSITIVE_WIDTH,
                           f'가로 {width:.6f} m, 세로 {length:.6f} m: 0 이하인 값이 있다', **partial)
    if height <= 0:
        return BoxEstimate(False, GEOM_NEGATIVE_HEIGHT,
                           f'높이 {height:.6f} m (z_top {z_top:.6f} − support_z {z_bot:.6f}): 0 이하다', **partial)

    # 3.5절: 윗면은 +z 에서 내려다봐 (x−, y−) 부터 반시계. i + 4 가 i 의 바로 아래
    corners = ((x_neg, y_neg), (x_pos, y_neg), (x_pos, y_pos), (x_neg, y_pos))
    vertices = tuple((x, y, z_top) for x, y in corners) + tuple((x, y, z_bot) for x, y in corners)
    top_edges = tuple(_segment(vertices[i], vertices[(i + 1) % 4]) for i in range(4))
    bottom_edges = tuple(_segment(vertices[i + 4], vertices[(i + 1) % 4 + 4]) for i in range(4))
    vertical_edges = tuple(_segment(vertices[i], vertices[i + 4]) for i in range(4))

    return BoxEstimate(
        True, '', '', width=width, length=length, height=height, dims_valid=True,
        vertices=vertices, edges=top_edges + bottom_edges + vertical_edges,
        path_candidates=top_edges, box_valid=True, **partial)
