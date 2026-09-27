"""ExecuteMotion 의 순수 계산 (T13). ROS도 두산 드라이버도 없이 돈다.

- 계약 단위(m · quaternion) → 두산 단위(mm · deg ZYZ) 역변환
- SLIDE 방향(Base 축) → 단위 벡터
- 이동 거리, SLIDE 하강 제한 판정

종료 사유(reason) 고르기는 `decide_reason`에 모아 뒀다. 계약 `ros-interfaces.md` 5.4 · 6.1절.
"""
import math

MM_PER_M = 1000.0

# ExecuteMotion.action / ScanState 와 같은 값
DIR_NONE, DIR_POS_X, DIR_NEG_X, DIR_POS_Y, DIR_NEG_Y = 0, 1, 2, 3, 4
DIRECTION_VECTORS = {
    DIR_POS_X: (1.0, 0.0, 0.0),
    DIR_NEG_X: (-1.0, 0.0, 0.0),
    DIR_POS_Y: (0.0, 1.0, 0.0),
    DIR_NEG_Y: (0.0, -1.0, 0.0),
}


def direction_vector(direction):
    """SLIDE 방향(Base 축 기준) → 단위 벡터. 모르는 값이면 ValueError."""
    if direction not in DIRECTION_VECTORS:
        raise ValueError(f'SLIDE 방향 값이 올바르지 않다: {direction}')
    return DIRECTION_VECTORS[direction]


def quaternion_to_zyz_deg(x, y, z, w):
    """quaternion → 두산 posx 자세(ZYZ 오일러, deg). `conversions.zyz_deg_to_quaternion`의 역이다.

    b(가운데 Y 회전)가 0 또는 180°에 가까우면 두 Z 회전이 한 축으로 겹쳐 나뉘지 않는다(짐벌).
    그때는 뒤쪽 Z를 0으로 두고 앞쪽에 합친다.
    """
    norm = math.sqrt(x * x + y * y + z * z + w * w)
    if not math.isfinite(norm) or norm == 0.0:
        raise ValueError(f'quaternion 이 올바르지 않다: {(x, y, z, w)}')
    x, y, z, w = (v / norm for v in (x, y, z, w))
    # 닫힌 식(conversions)의 역: x = -sin(b/2)sin((a-c)/2) 꼴을 그대로 푼다
    half_b = math.atan2(math.hypot(x, y), math.hypot(z, w))
    sum_half = math.atan2(z, w)          # (a + c) / 2
    if math.isclose(math.hypot(x, y), 0.0, abs_tol=1e-9):
        a, c = 2.0 * sum_half, 0.0       # 짐벌: 앞쪽 Z에 합친다
    else:
        diff_half = math.atan2(-x, y)    # (a - c) / 2
        a, c = sum_half + diff_half, sum_half - diff_half
    return math.degrees(a), math.degrees(2.0 * half_b), math.degrees(c)


def pose_to_posx_mm_deg(position_m, orientation_xyzw):
    """계약 Pose(m · quaternion) → 두산 posx [mm, deg] 6개."""
    if len(position_m) != 3 or not all(math.isfinite(v) for v in position_m):
        raise ValueError(f'목표 위치가 올바르지 않다: {list(position_m)!r}')
    rz1, ry, rz2 = quaternion_to_zyz_deg(*orientation_xyzw)
    return [position_m[0] * MM_PER_M, position_m[1] * MM_PER_M, position_m[2] * MM_PER_M, rz1, ry, rz2]


def relative_target_mm(vector, distance_m):
    """단위 벡터 × 거리 → 두산 상대 이동 posx [mm, deg]. 자세는 그대로 둔다."""
    if not math.isfinite(distance_m) or distance_m <= 0.0:
        raise ValueError(f'이동 거리가 올바르지 않다: {distance_m}')
    return [vector[0] * distance_m * MM_PER_M,
            vector[1] * distance_m * MM_PER_M,
            vector[2] * distance_m * MM_PER_M, 0.0, 0.0, 0.0]


def travelled_m(start_position_m, current_position_m):
    """시작점에서 지금까지의 직선 거리 [m]. 한쪽이라도 모르면 0.0."""
    if start_position_m is None or current_position_m is None:
        return 0.0
    return math.dist(start_position_m, current_position_m)


def lateral_m(start_position_m, current_position_m):
    """시작점에서 지금까지의 x · y 거리 [m]. 한쪽이라도 모르면 0.0. SLIDE 의 "움직였다" 판정용이다.

    힘 제어를 켜면 팁이 z 로 0.3~0.5 mm 움직인다(9/22 실기). 이것을 밀기 출발로 보면 안 된다.
    """
    if start_position_m is None or current_position_m is None:
        return 0.0
    return math.dist(start_position_m[:2], current_position_m[:2])


def drop_exceeded(start_z_m, current_z_m, drop_limit_m):
    """SLIDE 하강 제한(계약 7.2 1차 감시). 기준은 SLIDE 첫 샘플의 z다."""
    if start_z_m is None or current_z_m is None:
        return False
    return (start_z_m - current_z_m) > drop_limit_m
