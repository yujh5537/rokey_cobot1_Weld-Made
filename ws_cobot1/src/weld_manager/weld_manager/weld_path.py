"""용접 경로 생성 (순수 Python, rclpy 없음). 기준: docs/phase2/weld-motion.md 1~5절.

스캔 결과(result_store 의 result.json)에서 모서리 8 개를 골라, 선마다
  툴 자세(두 면 법선의 이등분면 안에서 연직으로부터 tilt 만큼 바깥으로) · 스탠드오프 · 지그재그 위빙 경유점 ·
  접근 / 후퇴 / 선 사이 안전 높이(z_safe)
를 만들고 작업영역을 검사한다. 결과(WeldPlan)의 좌표는 **Base**(goal 의 프레임)다.

프레임과 단위
- 스캔 결과는 작업대 좌표(`workpiece_fixture`)다. Base = 작업대 + `base_to_fixture`(평행 이동만, units-frames.md).
  `base_to_fixture` 는 **그 스캔의 `node_params` 값**을 쓴다. yaml 의 현재 값이 아니다(스캔 뒤 바뀌었으면 틀린 곳으로 간다).
- 길이 m, 각 rad, 자세 quaternion (x, y, z, w). 두산 ZYZ(deg)는 robot_manager 가 바꾼다. 여기의 ZYZ 함수는 로그 · 시험용이다.

PR #184 리뷰로 정해진 것
- D22: standoff_m 은 팁 구 표면 ↔ 이음선 최단거리다. 축 방향 물러남 s′ 은 선 방향에 따라 다르다 → tip_retreat()
- D23 · D28: 세로선은 툴 외형(tool_profile_u_m · tool_profile_r_m)이 옆면 · 작업대와 겹치지 않는지 본다 → tool_profile_problem()
- D24: tool_roll_deg 는 선별 배열이고, 위빙 방향 normalize(t × d) 는 roll 과 무관하다 → ToolFrame.weave
- D28: start_line ~ end_line 만 계획한다 → plan_weld()
"""

from dataclasses import dataclass
import math
from typing import Dict, List, Optional, Sequence, Tuple

from scan_manager.result_store import check_scan_id
from scan_manager.result_store import ResultStoreError

from .contract_enums import LINE_COUNT
from .params import WeldParams

Vec3 = Tuple[float, float, float]
Quat = Tuple[float, float, float, float]

_EPS = 1e-9
_R2 = math.sqrt(0.5)
UP: Vec3 = (0.0, 0.0, 1.0)


class NoScanResult(Exception):
    """용접할 스캔 결과가 없거나 무효다 → NO_SCAN_RESULT(602)."""


class PathRejected(Exception):
    """만든 경로를 보낼 수 없다(작업영역 밖 · 자세를 정할 수 없음) → PATH_REJECTED(604)."""


# ---- 벡터 ----

def _add(a: Sequence[float], b: Sequence[float]) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _sub(a: Sequence[float], b: Sequence[float]) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _scale(a: Sequence[float], k: float) -> Vec3:
    return (a[0] * k, a[1] * k, a[2] * k)


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Sequence[float], b: Sequence[float]) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a: Sequence[float]) -> float:
    return math.sqrt(_dot(a, a))


def _unit(a: Sequence[float]) -> Vec3:
    n = _norm(a)
    if not math.isfinite(n) or n < _EPS:
        raise ValueError(f'길이가 0 인 벡터다: {tuple(a)!r}')
    return _scale(a, 1.0 / n)


def _finite_vec(value, size) -> bool:
    return (
        isinstance(value, (list, tuple)) and len(value) == size
        and all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                for v in value))


# ---- 자세 ----

def quaternion_from_axes(x: Vec3, y: Vec3, z: Vec3) -> Quat:
    """열이 (x, y, z) 인 회전행렬 → quaternion (x, y, z, w). w ≥ 0 으로 부호를 고른다."""
    m00, m01, m02 = x[0], y[0], z[0]
    m10, m11, m12 = x[1], y[1], z[1]
    m20, m21, m22 = x[2], y[2], z[2]
    trace = m00 + m11 + m22
    if trace > 0.0:
        s = 2.0 * math.sqrt(trace + 1.0)
        q = ((m21 - m12) / s, (m02 - m20) / s, (m10 - m01) / s, 0.25 * s)
    elif m00 > m11 and m00 > m22:
        s = 2.0 * math.sqrt(1.0 + m00 - m11 - m22)
        q = (0.25 * s, (m01 + m10) / s, (m02 + m20) / s, (m21 - m12) / s)
    elif m11 > m22:
        s = 2.0 * math.sqrt(1.0 + m11 - m00 - m22)
        q = ((m01 + m10) / s, 0.25 * s, (m12 + m21) / s, (m02 - m20) / s)
    else:
        s = 2.0 * math.sqrt(1.0 + m22 - m00 - m11)
        q = ((m02 + m20) / s, (m12 + m21) / s, 0.25 * s, (m10 - m01) / s)
    n = math.sqrt(sum(c * c for c in q))
    q = tuple(c / n for c in q)
    return q if q[3] >= 0.0 else tuple(-c for c in q)


def rotate(q: Quat, v: Sequence[float]) -> Vec3:
    """quaternion q 로 벡터 v 를 돌린다 (v' = q v q*)."""
    qx, qy, qz, qw = q
    u = (qx, qy, qz)
    t = _scale(_cross(u, v), 2.0)
    return _add(_add(v, _scale(t, qw)), _cross(u, t))


def quaternion_to_zyz_deg(q: Quat) -> Vec3:
    """quaternion → 두산 ZYZ(고유 회전) deg. robot_manager/motions.py 와 같은 규약(import 하지 않는다).

    가운데 각 B 는 0~180°, 앞 · 뒤 각은 −180~180° 로 접는다. 로그 · 펜던트 대조 · 시험용이다.
    """
    x, y, z, w = q
    half_b = math.atan2(math.hypot(x, y), math.hypot(z, w))
    sum_half = math.atan2(z, w)
    if math.isclose(math.hypot(x, y), 0.0, abs_tol=_EPS):
        a, c = 2.0 * sum_half, 0.0
    else:
        diff_half = math.atan2(-x, y)
        a, c = sum_half + diff_half, sum_half - diff_half

    def wrap(deg):
        return (deg + 180.0) % 360.0 - 180.0
    return wrap(math.degrees(a)), math.degrees(2.0 * half_b), wrap(math.degrees(c))


@dataclass(frozen=True)
class ToolFrame:
    """한 선의 툴 자세. x · y · z 는 툴 축(Base 기준), weave 는 위빙 방향."""

    x: Vec3
    y: Vec3
    z: Vec3          # = d: 플랜지 → 팁 방향
    weave: Vec3      # 이음선을 가로지르는 방향 normalize(t × d). roll 과 무관(가정)

    @property
    def quaternion(self) -> Quat:
        return quaternion_from_axes(self.x, self.y, self.z)


def tool_frame(t: Vec3, n_out: Vec3, tilt_rad: float, roll_rad: float) -> ToolFrame:
    """weld-motion.md 2절.

    d = −(cos θ · ẑ + sin θ · n̂_out),  x_tool = normalize(t̂ × d),  y_tool = d × x_tool,
    그다음 d 둘레로 roll 만큼 돌린다(tool_roll_deg).
    t̂ 와 d 가 평행하면(세로선 + tilt 0) x_tool 을 정할 수 없고, 탐침 몸통이 모서리선 위에 놓인다 → PathRejected.
    """
    d = _scale(_add(_scale(UP, math.cos(tilt_rad)), _scale(n_out, math.sin(tilt_rad))), -1.0)
    across = _cross(t, d)
    if _norm(across) < 1e-6:
        raise PathRejected('툴 축이 이음선과 평행해 자세를 정할 수 없다(세로선은 tilt_deg > 0 이어야 한다)')
    x0 = _unit(across)
    y0 = _cross(d, x0)
    cr, sr = math.cos(roll_rad), math.sin(roll_rad)
    x = _add(_scale(x0, cr), _scale(y0, sr))
    y = _cross(d, x)
    return ToolFrame(x=x, y=y, z=d, weave=x0)


def tip_retreat(frame: ToolFrame, t: Vec3, standoff_m: float, tip_radius_m: float) -> float:
    """weld-motion.md 3절(D22): 구 표면 ↔ 이음선 = standoff_m 이 되는 축 방향 물러남 s′.

    k = sqrt(1 − (d · t̂)²)   툴 축과 이음선이 이루는 각의 sin. 윗면선 1, 세로선 sin θ
    s′ = (standoff_m + r) / k − r
    TCP 는 구 중심에서 d 방향으로 r 인 점(수직 자세의 최하단점)이라, 구 중심 = TCP − r·d 이고
    구 중심 ↔ 이음선 거리 = (s′ + r)·k = standoff_m + r 이다.
    """
    k = math.sqrt(max(0.0, 1.0 - _dot(frame.z, t) ** 2))
    if k < 1e-6:
        raise PathRejected('툴 축이 이음선과 평행해 스탠드오프를 정할 수 없다')
    return (standoff_m + tip_radius_m) / k - tip_radius_m


def weave_points(start: Vec3, end: Vec3, offset: Vec3, weave: Vec3,
                 amplitude_m: float, pitch_m: float) -> List[Vec3]:
    """weld-motion.md 4절의 지그재그. 시작 · 끝은 이음선 위(진폭 0). 진폭이나 피치가 0 이면 두 점."""
    length = _norm(_sub(end, start))
    t = _unit(_sub(end, start))
    if amplitude_m == 0.0 or pitch_m == 0.0:
        return [_add(start, offset), _add(end, offset)]
    # 부동소수 때문에 80 / 0.004 가 20.000000001 이 되어 점이 하나 늘지 않게 한다
    count = max(1, math.ceil(length / pitch_m - 1e-9))
    points = []
    for k in range(count + 1):
        s = min(k * pitch_m, length)
        a = 0.0 if k in (0, count) else amplitude_m * (-1.0) ** k
        points.append(_add(_add(_add(start, _scale(t, s)), offset), _scale(weave, a)))
    return points


# ---- 스캔 결과 ----

@dataclass(frozen=True)
class ScanInput:
    """result.json 에서 쓰는 것만. 좌표는 작업대 좌표(m)."""

    scan_id: str
    frame_id: str                       # 결과 프레임 (workpiece_fixture)
    motion_frame_id: str                # 스캔이 goal 에 쓴 프레임 (base_link)
    edges: Tuple[Tuple[Vec3, Vec3], ...]  # ScanResult.edges[12] 의 (start, end)
    z_top: float
    support_z: float
    base_to_fixture: Vec3

    def to_base(self, p: Vec3) -> Vec3:
        return _add(p, self.base_to_fixture)

    @property
    def top_vertices(self) -> Tuple[Vec3, ...]:
        """윗면 꼭짓점 0~3 (= edges[0..3] 의 시작점, 계약 3.5절 순서)."""
        return tuple(self.edges[i][0] for i in range(4))


def scan_from_record(record, result_frame_id: str, motion_frame_id: str) -> ScanInput:
    """ResultRecord(scan_manager.result_store) → ScanInput. 쓸 수 없으면 NoScanResult."""
    sid, shape, node = record.scan_id, record.shape, record.node_params
    if not shape.success:
        raise NoScanResult(f'{sid}: 스캔이 성공하지 않았다(reason_code={shape.reason_code} {shape.detail})')
    if not shape.box_valid:
        raise NoScanResult(f'{sid}: box_valid=false')
    if shape.frame_id != result_frame_id:
        raise NoScanResult(f'{sid}: 결과 프레임 {shape.frame_id!r} 가 {result_frame_id!r} 가 아니다')
    if not (shape.z_top.valid and shape.support_z.valid):
        raise NoScanResult(f'{sid}: z_top · support_z 가 없다')
    b2f = node.get('base_to_fixture')
    if not _finite_vec(b2f, 3):
        raise NoScanResult(f'{sid}: node_params.base_to_fixture 가 없거나 올바르지 않다({b2f!r})')
    if node.get('motion_frame_id') != motion_frame_id:
        raise NoScanResult(
            f'{sid}: 스캔의 motion_frame_id {node.get("motion_frame_id")!r} 가 {motion_frame_id!r} 가 아니다')
    edges = tuple((tuple(seg.start), tuple(seg.end)) for seg in shape.edges)
    return ScanInput(
        scan_id=sid, frame_id=shape.frame_id, motion_frame_id=motion_frame_id, edges=edges,
        z_top=float(shape.z_top.value), support_z=float(shape.support_z.value),
        base_to_fixture=tuple(float(v) for v in b2f))


def load_scan(store, scan_id: str, result_frame_id: str, motion_frame_id: str) -> ScanInput:
    """RunWeld.scan_id 로 결과를 읽는다(5.1절). "" = scan_id 사전순 최신의 success=true 결과.

    진행 기록(progress.json)만 있는 작업은 후보가 아니다. 가장 최근 성공 결과가 쓸 수 없는 모양이면
    더 옛 결과로 조용히 넘어가지 않고 거절한다(관제자가 모르는 스캔을 따라가지 않게).
    """
    if scan_id:
        try:
            check_scan_id(scan_id)
        except ValueError as error:
            raise NoScanResult(str(error)) from None
        if not store.has_result(scan_id):
            raise NoScanResult(f'{scan_id}: result.json 이 없다({store.result_dir})')
        try:
            record = store.load_result(scan_id)
        except ResultStoreError as error:
            raise NoScanResult(f'{scan_id}: 읽지 못했다 — {error}') from None
        return scan_from_record(record, result_frame_id, motion_frame_id)

    unreadable = []
    for candidate in store.scan_ids():
        if not store.has_result(candidate):
            continue
        try:
            record = store.load_result(candidate)
        except ResultStoreError as error:
            unreadable.append(f'{candidate}: {error}')
            continue
        if record.shape.success:
            return scan_from_record(record, result_frame_id, motion_frame_id)
    detail = f'성공한 스캔 결과가 없다({store.result_dir})'
    if unreadable:
        detail += '. 읽지 못한 결과: ' + '; '.join(unreadable)
    raise NoScanResult(detail)


# ---- 8 선 ----

@dataclass(frozen=True)
class LineSpec:
    """weld-motion.md 1절 표의 한 줄."""

    name: str
    edge_index: int     # ScanResult.edges[] 의 번호
    t: Vec3             # 진행 방향 (데이터와 대조한다)
    n_out: Vec3         # 바깥 방향 (두 면 법선의 합, 정규화)
    vertical: bool


LINES: Tuple[LineSpec, ...] = (
    LineSpec('L0', 0, (1.0, 0.0, 0.0), (0.0, -1.0, 0.0), False),
    LineSpec('L1', 1, (0.0, 1.0, 0.0), (1.0, 0.0, 0.0), False),
    LineSpec('L2', 2, (-1.0, 0.0, 0.0), (0.0, 1.0, 0.0), False),
    LineSpec('L3', 3, (0.0, -1.0, 0.0), (-1.0, 0.0, 0.0), False),
    LineSpec('L4', 8, (0.0, 0.0, -1.0), (-_R2, -_R2, 0.0), True),
    LineSpec('L5', 9, (0.0, 0.0, -1.0), (_R2, -_R2, 0.0), True),
    LineSpec('L6', 10, (0.0, 0.0, -1.0), (_R2, _R2, 0.0), True),
    LineSpec('L7', 11, (0.0, 0.0, -1.0), (-_R2, _R2, 0.0), True),
)
assert len(LINES) == LINE_COUNT


def seam(scan: ScanInput, index: int, bottom_margin_m: float) -> Tuple[Vec3, Vec3]:
    """선 index 의 이음선 (작업대 좌표). 세로선의 끝은 z = support_z + bottom_margin_m (1절)."""
    spec = LINES[index]
    start, end = scan.edges[spec.edge_index]
    if spec.vertical:
        end = (end[0], end[1], scan.support_z + bottom_margin_m)
    delta = _sub(end, start)
    if _norm(delta) < _EPS or _dot(_unit(delta), spec.t) < 1.0 - 1e-6:
        # 계약 순서(3.5절)와 다른 결과이거나, bottom_margin 이 너무 커서 세로선이 없어졌다
        raise PathRejected(
            f'{spec.name}: 이음선 {start} → {end} 의 방향이 계약 {spec.t} 와 다르거나 길이가 없다')
    return start, end


@dataclass(frozen=True)
class LinePlan:
    """선 하나의 계획. 좌표는 Base(m), 자세는 선 전체에 같다."""

    index: int
    name: str
    seam_fixture: Tuple[Vec3, Vec3]  # WeldLine.seam (작업대 좌표)
    orientation: Quat
    approach1: Vec3                   # (P_app.x, P_app.y, z_safe)   OP_MOVE_TO, travel_speed
    approach2: Vec3                   # P_app                        OP_MOVE_TO, approach_speed
    path: Tuple[Vec3, ...]            # [p_0 … p_N, P_ret]           ExecutePath, weld_speed
    retreat: Vec3                     # (P_ret.x, P_ret.y, z_safe)   OP_MOVE_TO, travel_speed

    @property
    def path_length_m(self) -> float:
        """ExecutePath 가 지나는 길이. 출발점은 approach2(P_app)다. line_progress 의 분모."""
        points = (self.approach2,) + self.path
        return sum(_norm(_sub(b, a)) for a, b in zip(points, points[1:]))


def tool_profile_problem(spec: 'LineSpec', retreat_m: float, bottom_tcp_z: float,
                         scan: 'ScanInput', params: WeldParams) -> Optional[str]:
    """weld-motion.md 5절 툴 외형 검사(D23). 세로선만 본다. 윗면선은 툴 전체가 이등분 축 뒤라 겹칠 수 없다.

    툴 외형 (u, R): 팁에서 축 방향 뒤로 u 부터 다음 u 전까지 축에서 가장 멀리 뻗은 반폭이 R 이하.
    두 조건 모두 u 가 작을수록 불리하므로 각 구간의 시작 u 에서만 본다.
      옆면:   R < (s′ + u) · tan θ          (부재 쪽으로 뻗은 부분이 모서리선 바깥에 있다)
      작업대: z_TCP + u · cos θ − R · sin θ ≥ support_z   (세로선 아래 끝, 작업대 좌표)
    """
    if not spec.vertical:
        return None
    theta = params.tilt_rad
    for u, r in params.tool_profile:
        if not r < (retreat_m + u) * math.tan(theta):
            return (f'툴 외형 (u {u * 1000:.1f} mm, R {r * 1000:.1f} mm) 이 옆면에 닿는다: '
                    f'R < (s′ {retreat_m * 1000:.2f} + u) · tan {params.tilt_deg:g}° 이어야 한다')
        lowest = bottom_tcp_z + u * math.cos(theta) - r * math.sin(theta)
        if lowest < scan.support_z - _EPS:
            return (f'툴 외형 (u {u * 1000:.1f} mm, R {r * 1000:.1f} mm) 이 작업대에 닿는다: '
                    f'가장 낮은 점 z {lowest * 1000:.2f} mm < support_z {scan.support_z * 1000:.2f} mm')
    return None


def plan_line(scan: ScanInput, index: int, params: WeldParams) -> Tuple[LinePlan, Tuple[Vec3, ...]]:
    """(LinePlan, 작업영역 검사용 작업대 좌표 점들). 툴 외형이 겹치면 PathRejected."""
    spec = LINES[index]
    start, end = seam(scan, index, params.bottom_margin_m)
    try:
        frame = tool_frame(spec.t, spec.n_out, params.tilt_rad, params.tool_roll_rad(index))
        retreat_m = tip_retreat(frame, spec.t, params.standoff_m, params.tip_radius_m)
    except PathRejected as error:
        raise PathRejected(f'{spec.name}: {error}') from None
    offset = _scale(frame.z, -retreat_m)
    problem = tool_profile_problem(spec, retreat_m, end[2] + offset[2], scan, params)
    if problem:
        raise PathRejected(f'{spec.name}: {problem}')
    points = weave_points(start, end, offset, frame.weave,
                          params.weave_amplitude_m, params.weave_pitch_m)
    back = _scale(frame.z, -params.approach_m)            # 툴 축 뒤로
    p_app = _add(points[0], back)
    p_ret = _add(points[-1], back)
    z_safe = scan.z_top + params.travel_clearance_m
    fixture_targets = (
        (p_app[0], p_app[1], z_safe), p_app, *points, p_ret, (p_ret[0], p_ret[1], z_safe))
    base = [scan.to_base(p) for p in fixture_targets]
    plan = LinePlan(
        index=index, name=spec.name, seam_fixture=(start, end), orientation=frame.quaternion,
        approach1=base[0], approach2=base[1], path=tuple(base[2:-1]), retreat=base[-1])
    return plan, fixture_targets


def workspace_problem(scan: ScanInput, points: Sequence[Vec3], params: WeldParams) -> Optional[str]:
    """weld-motion.md 5절 (작업대 좌표): z ≥ support_z + bottom_margin, x · y 는 부재 ± workspace_margin."""
    xs = [v[0] for v in scan.top_vertices]
    ys = [v[1] for v in scan.top_vertices]
    margin = params.workspace_margin_m
    x_lo, x_hi = min(xs) - margin, max(xs) + margin
    y_lo, y_hi = min(ys) - margin, max(ys) + margin
    z_lo = scan.support_z + params.bottom_margin_m
    for p in points:
        if p[2] < z_lo - _EPS:
            return f'z {p[2]:.4f} m 가 support_z + bottom_margin({z_lo:.4f} m) 아래다'
        if not (x_lo - _EPS <= p[0] <= x_hi + _EPS and y_lo - _EPS <= p[1] <= y_hi + _EPS):
            return (f'x · y ({p[0]:.4f}, {p[1]:.4f}) m 가 부재 ± workspace_margin '
                    f'[{x_lo:.4f}, {x_hi:.4f}] × [{y_lo:.4f}, {y_hi:.4f}] 밖이다')
    return None


@dataclass(frozen=True)
class WeldPlan:
    scan_id: str
    start_line: int
    end_line: int
    seams: Tuple[Tuple[Vec3, Vec3], ...]   # 8 선 전부(작업대 좌표). WeldResult.lines[i].seam
    lines: Dict[int, LinePlan]             # start_line ~ end_line 만
    base_to_fixture: Vec3
    z_safe_base: float                     # 선 사이 이동 높이 (Base z)


def line_range_problem(start_line: int, end_line: int) -> Optional[str]:
    """5.1절 LINE_OUT_OF_RANGE(603): start · end 가 0~7 이고 start ≤ end."""
    last = LINE_COUNT - 1
    if not (0 <= start_line <= last and 0 <= end_line <= last):
        return f'start_line {start_line} · end_line {end_line} 은 0~{last} 이어야 한다'
    if end_line < start_line:
        return f'end_line {end_line} 이 start_line {start_line} 보다 작다'
    return None


def plan_weld(scan: ScanInput, start_line: int, end_line: int, params: WeldParams) -> WeldPlan:
    """start_line ~ end_line 선의 계획(D28). 작업영역 밖 · 자세를 정할 수 없음 · 툴 외형 겹침은 PathRejected(→ 604).

    선 범위(603)는 호출 측이 line_range_problem() 으로 먼저 거른다(5.1절 순서). 여기서 범위 밖이면 프로그램 오류다.
    """
    problem = line_range_problem(start_line, end_line)
    if problem:
        raise ValueError(problem)
    seams = tuple(seam(scan, i, params.bottom_margin_m) for i in range(LINE_COUNT))
    lines = {}
    for index in range(start_line, end_line + 1):
        plan, fixture_targets = plan_line(scan, index, params)
        problem = workspace_problem(scan, fixture_targets, params)
        if problem:
            raise PathRejected(f'{plan.name}: {problem}')
        lines[index] = plan
    return WeldPlan(
        scan_id=scan.scan_id, start_line=start_line, end_line=end_line, seams=seams, lines=lines,
        base_to_fixture=scan.base_to_fixture,
        z_safe_base=scan.to_base((0.0, 0.0, scan.z_top + params.travel_clearance_m))[2])
