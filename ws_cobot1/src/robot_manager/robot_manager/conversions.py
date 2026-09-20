"""두산 단위(mm · deg) ↔ 계약 단위(m · quaternion) 변환 (T15).

`docs/contracts/units-frames.md`: 두산 API는 mm · deg(ZYZ 오일러), ROS 내부는 m · rad · quaternion이다.
변환은 robot_manager 한 곳에서만 한다. 이 모듈은 rclpy도 dsr_msgs2도 import하지 않아서
ROS나 두산 드라이버 없이 테스트할 수 있다.
"""
import math

MM_PER_M = 1000.0


def mm_to_m(value_mm):
    return value_mm / MM_PER_M


def zyz_deg_to_quaternion(rz1_deg, ry_deg, rz2_deg):
    """두산 posx의 자세(ZYZ 오일러, deg)를 quaternion (x, y, z, w)으로 바꾼다.

    두산은 Z(rz1) → Y(ry) → Z(rz2) 순서의 **고유(intrinsic) 회전**을 쓴다.
    q = qz(rz1) * qy(ry) * qz(rz2).
    """
    a, b, c = (math.radians(v) / 2.0 for v in (rz1_deg, ry_deg, rz2_deg))
    # q = qz(a)·qy(b)·qz(c)를 전개한 것. 중간 quaternion 곱을 줄여 반올림 오차를 줄인다
    return (
        -math.sin(a - c) * math.sin(b),   # x
        math.cos(a - c) * math.sin(b),    # y
        math.sin(a + c) * math.cos(b),    # z
        math.cos(a + c) * math.cos(b),    # w
    )


def posx_to_pose_fields(posx_mm_deg):
    """posx [x, y, z (mm), rz1, ry, rz2 (deg)] → ((x, y, z) [m], (qx, qy, qz, qw)).

    길이가 6이 아니거나 유한하지 않은 값이 있으면 ValueError. 값을 0으로 채우지 않는다.
    """
    if len(posx_mm_deg) != 6 or not all(math.isfinite(v) for v in posx_mm_deg):
        raise ValueError(f'posx 값이 올바르지 않다: {list(posx_mm_deg)!r}')
    x, y, z, rz1, ry, rz2 = posx_mm_deg
    return (mm_to_m(x), mm_to_m(y), mm_to_m(z)), zyz_deg_to_quaternion(rz1, ry, rz2)


def tool_force_to_wrench_fields(force):
    """get_tool_force 결과 [Fx, Fy, Fz, Tx, Ty, Tz] → ((Fx, Fy, Fz), (Tx, Ty, Tz)).

    두산도 계약도 N · N·m이라 값은 그대로다. 유효성만 확인한다.
    """
    if len(force) != 6 or not all(math.isfinite(v) for v in force):
        raise ValueError(f'외력 값이 올바르지 않다: {list(force)!r}')
    return tuple(force[:3]), tuple(force[3:])
