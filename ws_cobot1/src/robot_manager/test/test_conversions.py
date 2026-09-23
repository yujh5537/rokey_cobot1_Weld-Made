"""단위 변환 테스트. ROS도 두산 드라이버도 없이 돈다 (T15)."""
import math

import pytest
from robot_manager.conversions import (mm_to_m, posx_to_pose_fields, tool_force_to_wrench_fields,
                                       zyz_deg_to_quaternion)


def quat_mul(q1, q2):
    x1, y1, z1, w1 = q1
    x2, y2, z2, w2 = q2
    return (w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2)


def qz(deg):
    a = math.radians(deg) / 2
    return (0.0, 0.0, math.sin(a), math.cos(a))


def qy(deg):
    a = math.radians(deg) / 2
    return (0.0, math.sin(a), 0.0, math.cos(a))


def same_rotation(q1, q2):
    """quaternion은 부호가 반대여도 같은 회전이다."""
    dot = sum(a * b for a, b in zip(q1, q2))
    return abs(abs(dot) - 1.0) < 1e-9


@pytest.mark.parametrize('angles', [
    (0, 0, 0), (90, 0, 0), (0, 90, 0), (0, 0, 90), (20.76, -179.87, -159.97),  # 홈 자세 (T03)
    (-30, 45, 120), (180, 180, 180), (0.1, -0.2, 0.3),
])
def test_zyz_matches_elementary_rotation_product(angles):
    """닫힌 식이 qz·qy·qz 곱과 같은 회전인지 본다 (ZYZ 고유 회전)."""
    rz1, ry, rz2 = angles
    expected = quat_mul(quat_mul(qz(rz1), qy(ry)), qz(rz2))
    assert same_rotation(zyz_deg_to_quaternion(rz1, ry, rz2), expected)


def test_zyz_is_unit_quaternion():
    q = zyz_deg_to_quaternion(12.3, -45.6, 78.9)
    assert math.isclose(math.sqrt(sum(v * v for v in q)), 1.0, rel_tol=1e-12)


def test_mm_to_m():
    assert mm_to_m(423.56) == pytest.approx(0.42356)


def test_posx_converts_mm_to_m():
    (x, y, z), _ = posx_to_pose_fields([424.46, -183.09, 539.96, 20.76, -179.87, -159.97])
    assert (x, y, z) == pytest.approx((0.42446, -0.18309, 0.53996))


@pytest.mark.parametrize('posx', [
    [],                                              # 응답 없음
    [1.0, 2.0, 3.0],                                 # 길이 부족
    [1.0, 2.0, float('nan'), 0.0, 0.0, 0.0],         # NaN
    [1.0, 2.0, float('inf'), 0.0, 0.0, 0.0],
])
def test_posx_rejects_bad_values(posx):
    """실패한 조회를 0으로 채우지 않는다 (CLAUDE.md 규칙 4)."""
    with pytest.raises(ValueError):
        posx_to_pose_fields(posx)


def test_tool_force_passes_values_through():
    force, torque = tool_force_to_wrench_fields([1.0, -2.0, 3.5, 0.1, 0.2, -0.3])
    assert force == pytest.approx((1.0, -2.0, 3.5))
    assert torque == pytest.approx((0.1, 0.2, -0.3))


@pytest.mark.parametrize('force', [[], [0.0] * 5, [0.0, 0.0, float('nan'), 0.0, 0.0, 0.0]])
def test_tool_force_rejects_bad_values(force):
    with pytest.raises(ValueError):
        tool_force_to_wrench_fields(force)


# ---- 이동 판정 (motion_state) ------------------------------------------------
from collections import deque  # noqa: E402

from robot_manager.motion_state import has_moved, is_moving, trim  # noqa: E402


def window(*points):
    return deque(points)


def test_unknown_position_counts_as_moving():
    """모르는 상태를 정지로 보고하면 scan_manager가 STOPPING에서 못 빠져나온다."""
    assert is_moving(window(), 0.0002) is True
    assert is_moving(window((0.0, (0.0, 0.0, 0.0))), 0.0002) is True


def test_still_robot_is_not_moving():
    points = window((0.0, (0.4, 0.0, 0.2)), (0.1, (0.4, 0.0, 0.2)), (0.2, (0.4, 0.0, 0.20005)))
    assert is_moving(points, 0.0002) is False


def test_slow_descend_is_moving():
    """5 mm/s 하강이면 0.3 s 창에서 1.5 mm 움직인다."""
    points = window(*[(i * 0.1, (0.4, 0.0, 0.2 - 0.005 * i * 0.1)) for i in range(4)])
    assert is_moving(points, 0.0002) is True


def test_one_mm_per_second_descend_is_moving():
    """1 mm/s 하강도 이동으로 읽어야 한다 (9/23 실기 #152).

    real.yaml 의 moving_window_s 0.3 · moving_eps_m 0.2 mm 에서 1 mm/s 는 창 하나에 0.3 mm 다.
    실기 샘플 간격(약 20 ms)으로 창을 채워도 첫 점에서 0.2 mm 를 넘는 점이 있어야 한다.
    넘지 못하면 "멈췄다 = 도착"이 되어 goal 이 끝나고, 로봇은 감시 없이 계속 내려간다.
    2026-09-23 공중 10 mm 하강 3 회가 1.15 · 3.22 · 0.93 mm 만 가고 '도착'으로 끝났다.
    """
    points = window(*[(i * 0.02, (0.4, 0.0, 0.2 - 0.001 * i * 0.02)) for i in range(16)])
    assert is_moving(points, 0.0002, window_s=0.3) is True


def test_speed_below_eps_over_window_reads_as_still():
    """이 파라미터 조합이 지켜 주는 최저 속도는 moving_eps_m / moving_window_s 다.

    0.2 mm / 0.3 s = 약 0.67 mm/s. 그보다 느리면 창을 다 덮어도 변위가 eps 에 못 미쳐
    움직이는 로봇이 "멈췄다"로 읽힌다. 하강 속도를 그 아래로 내리려면
    moving_eps_m · moving_window_s 를 같이 본다 (real.yaml 주석).
    """
    points = window(*[(i * 0.02, (0.4, 0.0, 0.2 - 0.0005 * i * 0.02)) for i in range(16)])
    assert is_moving(points, 0.0002, window_s=0.3) is False


def test_trim_drops_old_points():
    points = window((0.0, (0, 0, 0)), (0.5, (0, 0, 0)), (0.9, (0, 0, 0)))
    trim(points, now_s=1.0, window_s=0.3)
    assert [t for t, _ in points] == [0.9]


def test_stale_points_are_dropped_then_unknown_means_moving():
    """posx 응답이 끊기면 창이 비고, 그때는 "이동 중"으로 본다 (병후 리뷰, PR #72)."""
    points = window((0.0, (0.4, 0.0, 0.2)), (0.1, (0.4, 0.0, 0.2)), (0.2, (0.4, 0.0, 0.2)))
    assert is_moving(points, 0.0002) is False          # 정지 상태로 창이 차 있다
    trim(points, now_s=5.0, window_s=0.3)              # 5초간 새 위치가 없었다
    assert len(points) == 0
    assert is_moving(points, 0.0002) is True           # 모르면 이동 중


def test_unknown_position_is_not_counted_as_having_moved():
    """샘플 공백 뒤 모르는 상태는 "움직였다"가 아니다. 출발 전 도착 판정을 막는다 (9/22 실기 943)."""
    assert has_moved(window(), 0.0002) is False
    assert has_moved(window((0.0, (0.4, 0.0, 0.2))), 0.0002) is False
    # 공백 뒤 갓 들어온 두 점: is_moving 은 모르니 True 지만, 움직임이 확인된 것은 아니다
    gap = window((1.00, (0.4, 0.0, 0.2)), (1.02, (0.4, 0.0, 0.2)))
    assert is_moving(gap, 0.0002, 0.3) is True
    assert has_moved(gap, 0.0002) is False


def test_confirmed_displacement_counts_as_having_moved():
    """점이 몇 개 없어도 eps 넘게 떨어져 있으면 움직인 것이 확인된 것이다."""
    points = window((1.00, (0.4, 0.0, 0.2)), (1.05, (0.4003, 0.0, 0.2)))
    assert has_moved(points, 0.0002) is True
    still = window((0.0, (0.4, 0.0, 0.2)), (0.1, (0.4, 0.0, 0.2)), (0.2, (0.4, 0.0, 0.20005)))
    assert has_moved(still, 0.0002) is False
