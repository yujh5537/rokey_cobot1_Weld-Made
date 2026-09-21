"""ExecuteMotion 순수 계산 테스트 (T13). ROS 없이 돈다."""
import math

import pytest
from robot_manager.conversions import zyz_deg_to_quaternion
from robot_manager.motions import (DIR_NEG_X, DIR_NEG_Y, DIR_POS_X, DIR_POS_Y, direction_vector,
                                   drop_exceeded, pose_to_posx_mm_deg, quaternion_to_zyz_deg,
                                   relative_target_mm, travelled_m)


def test_direction_vectors_follow_base_axes():
    assert direction_vector(DIR_POS_X) == (1.0, 0.0, 0.0)
    assert direction_vector(DIR_NEG_X) == (-1.0, 0.0, 0.0)
    assert direction_vector(DIR_POS_Y) == (0.0, 1.0, 0.0)
    assert direction_vector(DIR_NEG_Y) == (0.0, -1.0, 0.0)


@pytest.mark.parametrize('direction', [0, 5, 255])
def test_unknown_direction_is_rejected(direction):
    with pytest.raises(ValueError):
        direction_vector(direction)


@pytest.mark.parametrize('angles', [
    (0, 0, 0), (0, 90, 0), (30, 45, 60), (-120, 30, 15), (20.76, 179.87, -159.97),
])
def test_quaternion_to_zyz_round_trip(angles):
    """계약(quaternion) → 두산(ZYZ) 역변환이 같은 회전을 가리키는지."""
    q = zyz_deg_to_quaternion(*angles)
    back = zyz_deg_to_quaternion(*quaternion_to_zyz_deg(*q))
    dot = sum(a * b for a, b in zip(q, back))
    assert abs(abs(dot) - 1.0) < 1e-9


def test_quaternion_to_zyz_handles_gimbal():
    """ry가 0이면 두 Z 회전이 겹친다. 앞쪽에 합치고 뒤쪽은 0으로 둔다."""
    q = zyz_deg_to_quaternion(40.0, 0.0, 25.0)
    rz1, ry, rz2 = quaternion_to_zyz_deg(*q)
    assert ry == pytest.approx(0.0, abs=1e-6)
    assert rz2 == pytest.approx(0.0, abs=1e-6)
    assert rz1 == pytest.approx(65.0, abs=1e-6)


def test_pose_to_posx_converts_m_to_mm():
    posx = pose_to_posx_mm_deg((0.42356, -0.18606, 0.1006), (0.0, 0.0, 0.0, 1.0))
    assert posx[:3] == pytest.approx([423.56, -186.06, 100.6])


@pytest.mark.parametrize('position', [(0.1, 0.2), (float('nan'), 0.0, 0.0)])
def test_pose_to_posx_rejects_bad_position(position):
    with pytest.raises(ValueError):
        pose_to_posx_mm_deg(position, (0.0, 0.0, 0.0, 1.0))


def test_pose_to_posx_rejects_zero_quaternion():
    with pytest.raises(ValueError):
        pose_to_posx_mm_deg((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 0.0))


def test_relative_target_is_in_mm_and_keeps_orientation():
    assert relative_target_mm((0.0, 0.0, -1.0), 0.02) == pytest.approx([0.0, 0.0, -20.0, 0.0, 0.0, 0.0])
    assert relative_target_mm((1.0, 0.0, 0.0), 0.1) == pytest.approx([100.0, 0.0, 0.0, 0.0, 0.0, 0.0])


@pytest.mark.parametrize('distance', [0.0, -0.01, float('nan')])
def test_relative_target_rejects_bad_distance(distance):
    with pytest.raises(ValueError):
        relative_target_mm((0.0, 0.0, -1.0), distance)


def test_travelled_is_straight_line_distance():
    assert travelled_m((0.4, 0.0, 0.2), (0.4, 0.0, 0.18)) == pytest.approx(0.02)
    assert travelled_m((0.0, 0.0, 0.0), (0.03, 0.04, 0.0)) == pytest.approx(0.05)


def test_travelled_is_zero_when_position_unknown():
    assert travelled_m(None, (0.4, 0.0, 0.2)) == 0.0
    assert travelled_m((0.4, 0.0, 0.2), None) == 0.0


def test_drop_limit_uses_slide_start_z():
    assert drop_exceeded(0.18, 0.174, 0.005) is True      # 6 mm 내려감
    assert drop_exceeded(0.18, 0.176, 0.005) is False     # 4 mm
    assert drop_exceeded(0.18, 0.185, 0.005) is False     # 올라간 것은 제한이 아니다
    assert drop_exceeded(None, 0.174, 0.005) is False     # 모르면 판정하지 않는다


def test_drop_limit_boundary_is_not_exceeded():
    """경계는 초과가 아니다. 이진수로 정확한 값(0.5, 0.25)으로 본다."""
    assert drop_exceeded(1.0, 0.5, 0.5) is False
    assert drop_exceeded(1.0, 0.25, 0.5) is True


def test_math_import_is_used_for_distance():
    assert travelled_m((0, 0, 0), (1, 1, 1)) == pytest.approx(math.sqrt(3))
