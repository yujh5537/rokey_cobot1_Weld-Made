"""ExecutePath 의 순수 계산 (phase 2, P1). ROS 도 두산 드라이버도 없이 돈다.

- 파라미터 검사: `path_*` 값이 쓸 수 있는지. 못 쓰면 노드는 ExecutePath 만 받지 않는다
- goal 검사: 계약 `docs/phase2/weld-ros-interfaces.md` 5.2 의 `PATH_REJECTED(604)` 사유
- 경로 길이 · 진행(feedback 의 `waypoint_index` · `distance_travelled`, spline 의 `waypoints_done` 추정)
- 계약 단위(m · quaternion) → 두산 posx [mm, deg] 목록. 변환은 `motions.pose_to_posx_mm_deg` 를 그대로 쓴다
"""
import math
from typing import NamedTuple, Optional, Sequence, Tuple

from robot_manager.motions import pose_to_posx_mm_deg

PATH_MODES = ('line', 'spline')

# move_spline_task 의 경유점 배열 크기. 파라미터가 아니라 드라이버의 고정값이다.
# 컨트롤러는 pos_cnt 를 검사하지 않고 이 크기의 배열에 그대로 쓴다
# (DRFC.h MAX_SPLINE_POINT, dsr_controller2.cpp 557~567행. 현지 소스 확인 2026-09-24, D31)
SPLINE_MAX_POINTS = 100


class PathLimits(NamedTuple):
    """robot_manager 의 `path_*` 파라미터(계약 6장)와 노드 프레임. 값은 yaml 에서 온다."""
    mode: str               # path_mode: 'line' | 'spline'
    max_points: int         # path_max_points
    max_speed_mps: float    # path_max_speed_mps
    min_z_m: float          # path_min_z_m (Base z 하한)
    acc_ratio: float        # path_acc_ratio [1/s]. 가속 = 이 값 × 속도
    frame_id: str           # robot_manager 의 frame_id


class Waypoint(NamedTuple):
    position: Tuple[float, float, float]            # m
    orientation: Tuple[float, float, float, float]  # quaternion x, y, z, w


class PathProgress(NamedTuple):
    waypoint_index: int      # 향하고 있는 경유점. 전부 지났으면 마지막 점
    waypoints_done: int      # 지난 경유점 수
    distance_m: float        # 출발점부터 경로를 따라 잰 거리
    off_path_m: float        # 경로에서 떨어진 거리


def _finite(*values):
    return all(isinstance(v, (int, float)) and math.isfinite(v) for v in values)


def limits_problem(limits: PathLimits) -> Optional[str]:
    """`path_*` 파라미터를 쓸 수 없으면 그 이유, 쓸 수 있으면 None."""
    if limits.mode not in PATH_MODES:
        return f'path_mode {limits.mode!r} (line | spline)'
    if isinstance(limits.max_points, bool) or not isinstance(limits.max_points, int) \
            or limits.max_points < 1:
        return f'path_max_points {limits.max_points!r} 는 1 이상의 정수여야 한다'
    if limits.mode == 'spline' and limits.max_points > SPLINE_MAX_POINTS:
        return (f'path_max_points {limits.max_points} 는 spline 의 한도 {SPLINE_MAX_POINTS} 를 넘는다'
                f'(드라이버가 개수를 검사하지 않는다)')
    if not _finite(limits.max_speed_mps) or limits.max_speed_mps <= 0.0:
        return f'path_max_speed_mps {limits.max_speed_mps!r} 는 양수여야 한다'
    if not _finite(limits.min_z_m):
        return f'path_min_z_m {limits.min_z_m!r} 가 숫자가 아니다'
    if not _finite(limits.acc_ratio) or limits.acc_ratio <= 0.0:
        return f'path_acc_ratio {limits.acc_ratio!r} 는 양수여야 한다'
    if not limits.frame_id:
        return 'frame_id 가 비어 있다'
    return None


def _quaternion_problem(q):
    if len(q) != 4 or not _finite(*q):
        return 'quaternion 이 숫자가 아니다'
    if math.sqrt(sum(v * v for v in q)) == 0.0:
        return 'quaternion 크기가 0 이다'
    return None


def path_problem(waypoints: Sequence[Waypoint], frame_id: str, speed_mps: float,
                 path_tolerance_m: float, limits: PathLimits) -> Optional[str]:
    """goal 을 거절할 이유(`PATH_REJECTED` 의 detail), 없으면 None. 계약 5.2 의 순서대로 본다.

    z 하한은 경유점 **전부**를 수락 시점에 본다. 실행 도중에 걸러서 멈추면 이미 일부를 지난 뒤다.
    """
    n = len(waypoints)
    if n == 0:
        return '경유점이 없다'
    if n > limits.max_points:
        return f'경유점 {n} 개가 path_max_points {limits.max_points} 를 넘는다'
    if not _finite(speed_mps) or speed_mps <= 0.0:
        return f'speed {speed_mps!r} 는 양수여야 한다'
    if speed_mps > limits.max_speed_mps:
        return f'speed {speed_mps:.4f} m/s 가 path_max_speed_mps {limits.max_speed_mps:.4f} 를 넘는다'
    if frame_id != limits.frame_id:
        return f'frame_id {frame_id!r} 는 이 노드의 {limits.frame_id!r} 가 아니다'
    # 허용치가 0 이하이면 도착을 판정할 수 없다. 계약 5.2 의 목록 밖이지만 1차 INVALID_VALUE 와 같은 뜻
    if not _finite(path_tolerance_m) or path_tolerance_m <= 0.0:
        return f'path_tolerance_m {path_tolerance_m!r} 는 양수여야 한다'
    for i, w in enumerate(waypoints):
        if len(w.position) != 3 or not _finite(*w.position):
            return f'경유점 {i} 의 위치가 숫자가 아니다'
        problem = _quaternion_problem(w.orientation)
        if problem:
            return f'경유점 {i} 의 {problem}'
    for i, w in enumerate(waypoints):
        if w.position[2] < limits.min_z_m:
            return (f'경유점 {i} 의 z {w.position[2]:.4f} m 가 path_min_z_m {limits.min_z_m:.4f} '
                    f'보다 낮다')
    return None


def vertices(start, waypoints: Sequence[Waypoint]):
    """경로의 꼭짓점: 출발 위치 + 경유점 위치. 첫 점까지도 직선이다(계약 5.2)."""
    return [tuple(start)] + [tuple(w.position) for w in waypoints]


def cumulative_m(points):
    """꼭짓점마다 출발점부터의 경로 거리 [m]. 첫 값은 0."""
    out = [0.0]
    for a, b in zip(points, points[1:]):
        out.append(out[-1] + math.dist(a, b))
    return out


def path_length_m(start, waypoints: Sequence[Waypoint]) -> float:
    """출발 위치에서 마지막 경유점까지 경로 길이 [m]."""
    return cumulative_m(vertices(start, waypoints))[-1]


def _project(p, a, b):
    """점 p 를 선분 ab 에 투영: (0~1 로 자른 비율, 거리)."""
    ab = [bb - aa for aa, bb in zip(a, b)]
    length2 = sum(v * v for v in ab)
    if length2 == 0.0:
        return 1.0, math.dist(p, b)      # 길이 0 인 구간은 끝점에 도착한 것으로 본다
    t = sum((pp - aa) * v for pp, aa, v in zip(p, a, ab)) / length2
    t = min(1.0, max(0.0, t))
    closest = [aa + t * v for aa, v in zip(a, ab)]
    return t, math.dist(p, closest)


def progress(position, start, waypoints: Sequence[Waypoint], from_index: int = 0) -> PathProgress:
    """현재 위치가 경로의 어디쯤인지. 경유점 `from_index` 로 가는 구간부터 **앞으로만** 찾는다.

    위빙 경로는 이웃 구간이 1~2 mm 안에 붙어 있어, 처음부터 찾으면 지난 구간이나 앞 구간으로 튄다.
    그래서 뒤로는 가지 않고, 앞 구간 가운데 가장 가까운 곳을 고른다(같으면 앞쪽). 호출자는 직전
    결과의 `waypoint_index` 를 다음 `from_index` 로 넘긴다. spline 에서는 추정값이다(계약 허용).
    """
    if not waypoints:
        raise ValueError('경유점이 없다')
    pts = vertices(start, waypoints)
    cum = cumulative_m(pts)
    n = len(waypoints)
    first = min(max(0, from_index), n - 1)
    best = None
    for seg in range(first, n):          # 구간 seg: pts[seg] → pts[seg + 1] = waypoints[seg]
        t, off = _project(position, pts[seg], pts[seg + 1])
        if best is None or off < best[2]:
            best = (seg, t, off)
    seg, t, off = best
    distance = cum[seg] + t * (cum[seg + 1] - cum[seg])
    done = seg + 1 if t >= 1.0 else seg
    return PathProgress(waypoint_index=min(done, n - 1), waypoints_done=done,
                        distance_m=distance, off_path_m=off)


def to_posx_list(waypoints: Sequence[Waypoint]):
    """경유점 → 두산 posx [mm, deg] 목록. 값이 잘못됐으면 ValueError(path_problem 을 먼저 부른다)."""
    return [pose_to_posx_mm_deg(w.position, w.orientation) for w in waypoints]
