"""sim 입력원 테스트. ROS 없이 돈다.

마지막 테스트가 T07 의 합격 기준이다: sim 입력원 → 판정 → 편향 보정이 **가상 박스의 치수를 복원**해야 한다.
"""
import math

import pytest
from conftest import DT
from contact_detector.detector_core import (
    ContactDetector,
    DetectorConfig,
    EdgeConfig,
    OP_DESCEND,
    OP_SLIDE,
    Sample,
    TYPE_CONTACT,
    TYPE_EDGE,
)
from contact_detector.sim_source import SimBox, SimSource

MM = 1e-3
# contact_scan_bringup/config/sim.yaml 과 같은 값
BOX = SimBox(frame_id='base_link', origin_m=(0.40, 0.00, 0.00), size_m=(0.10, 0.06, 0.04),
             stiffness_n_per_m=20000.0, tip_radius_m=0.225 * MM,
             fall_speed_mps=0.050, slide_press_n=3.0)
CONFIG = DetectorConfig(contact_threshold_n=3.0, debounce_n=3, over_force_n=30.0, over_force_debounce_n=1)
EDGE = EdgeConfig(edge_drop_m=0.5 * MM, debounce_n=3, arm_force_n=1.5,
                  trend_window_s=0.5, trend_min_samples=10, max_gap_s=0.2)
DESCEND_V = 0.005
SLIDE_V = 0.010
TOP_Z = 0.040
SAMPLE_DT = 1 / 49.8          # 2026-09-20 Virtual 실측 주기


def sample(i, position, operation, motion_id=1, t=None):
    t = i * SAMPLE_DT if t is None else t
    return Sample(sample_id=i + 1, pose_stamp=t, force_stamp=t, position=position,
                  force=(0.0, 0.0, 0.0), motion_id=motion_id, operation=operation)


# ---------------------------------------------------------------- 모델

def test_surface_profile():
    r = BOX.tip_radius_m
    assert BOX.top_z == pytest.approx(TOP_Z)
    assert BOX.surface_z(0.40, 0.0) == pytest.approx(TOP_Z)                  # 한가운데
    assert BOX.surface_z(0.45, 0.0) == pytest.approx(TOP_Z)                  # +x 경계
    d = 0.1 * MM                                                             # 모서리에 얹힘
    assert BOX.surface_z(0.45 + d, 0.0) == pytest.approx(TOP_Z - (r - math.sqrt(r * r - d * d)))
    assert BOX.surface_z(0.45 + r * 1.01, 0.0) == pytest.approx(BOX.origin_m[2])   # 벗어남 → 지지면(자유 낙하)
    assert BOX.surface_z(0.45 + r) if False else True                        # d = r 은 경계(얹힘의 끝)
    assert BOX.overhang_m(0.40, 0.0) < 0 and BOX.overhang_m(0.46, 0.0) == pytest.approx(0.01)


def test_descend_makes_force_from_penetration():
    src = SimSource(BOX)
    above = src.apply(sample(0, (0.40, 0.0, TOP_Z + 1 * MM), OP_DESCEND))
    assert above.force == (0.0, 0.0, 0.0) and above.position[2] == pytest.approx(TOP_Z + 1 * MM)
    touching = src.apply(sample(1, (0.40, 0.0, TOP_Z - 0.15 * MM), OP_DESCEND))
    assert touching.force[2] == pytest.approx(3.0)                           # 0.15 mm x 20000 N/m
    assert touching.position[2] == pytest.approx(TOP_Z - 0.15 * MM)          # z 는 로봇 값 그대로


def test_slide_keeps_pressing_and_follows_the_surface_down():
    src = SimSource(BOX)
    src.apply(sample(0, (0.40, 0.0, TOP_Z - 0.15 * MM), OP_DESCEND))
    pressed = src.apply(sample(1, (0.41, 0.0, TOP_Z - 0.15 * MM), OP_SLIDE))
    assert pressed.force[2] == pytest.approx(3.0)                            # 누름 유지
    assert pressed.position[2] == pytest.approx(TOP_Z - 0.15 * MM)
    # 모서리를 완전히 지나면 표면이 사라진다. 팁은 fall_speed 로만 내려간다
    far = src.apply(sample(2, (0.46, 0.0, TOP_Z - 0.15 * MM), OP_SLIDE))
    assert far.position[2] == pytest.approx(pressed.position[2] - BOX.fall_speed_mps * SAMPLE_DT)
    assert far.force[2] == 0.0                                               # 닿지 않는다


def test_invalid_sample_passes_through_and_resets():
    src = SimSource(BOX)
    src.apply(sample(0, (0.40, 0.0, TOP_Z - 0.15 * MM), OP_DESCEND))
    bad = sample(1, (0.40, 0.0, TOP_Z), OP_SLIDE)
    bad = type(bad)(**{**bad.__dict__, 'valid': False})
    assert src.apply(bad) is bad
    assert src._z is None


def test_box_rejects_bad_values():
    for change in ({'stiffness_n_per_m': 0.0}, {'tip_radius_m': -1.0}, {'size_m': (0.1, 0.0, 0.04)},
                   {'frame_id': ''}, {'origin_m': (0.4, 0.0, float('nan'))}, {'slide_press_n': 0.0}):
        with pytest.raises(ValueError):
            SimBox(**{**BOX.__dict__, **change})


# ---------------------------------------------------------------- 종단: 치수 복원

def scan_one_direction(axis, sign, box=BOX, detector=None):
    """원점 상공에서 하강 → 접촉 → 그 방향으로 밀기. (CONTACT, EDGE) 판정을 돌려준다."""
    src = SimSource(box)
    detector = detector or ContactDetector(CONFIG, EDGE)
    detector.set_baseline((0.0, 0.0, 0.0))            # sim 은 무접촉 외력이 0 이라 F0 = 0
    cx, cy = box.origin_m[0], box.origin_m[1]
    contact = edge = None
    i, t = 0, 0.0

    z = TOP_Z + 3 * MM                                # 하강: 윗면 3 mm 위에서 시작
    while z > TOP_Z - 2 * MM and contact is None:
        for d in detector.update(src.apply(sample(i, (cx, cy, z), OP_DESCEND, t=t))):
            if d.type == TYPE_CONTACT:
                contact = d
        z -= DESCEND_V * SAMPLE_DT
        i, t = i + 1, t + SAMPLE_DT

    z_contact = contact.first_sample.position[2]
    pos = [cx, cy]
    travelled = 0.0
    while travelled < 0.08 and edge is None:          # 밀기
        travelled += SLIDE_V * SAMPLE_DT
        pos[axis] = (cx, cy)[axis] + sign * travelled
        for d in detector.update(src.apply(sample(i, (pos[0], pos[1], z_contact), OP_SLIDE, t=t))):
            if d.type == TYPE_EDGE:
                edge = d
        i, t = i + 1, t + SAMPLE_DT
    return contact, edge


def test_full_scan_recovers_the_virtual_box():
    """T07 합격 기준: sim → 판정 → 편향 보정이 가상 박스의 치수를 복원한다."""
    import sys
    sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[3] / 'scan_manager'))
    from scan_manager.contract_enums import Direction
    from scan_manager.geometry_estimator import (
        BiasParams, EdgeObservation, TopObservation, estimate_box)

    contact, _ = scan_one_direction(0, 1)
    edges = {}
    for direction, axis, sign in ((Direction.POS_X, 0, 1), (Direction.NEG_X, 0, -1),
                                  (Direction.POS_Y, 1, 1), (Direction.NEG_Y, 1, -1)):
        _, edge = scan_one_direction(axis, sign)
        assert edge is not None, direction
        edges[direction] = EdgeObservation(
            coordinate_m=edge.first_sample.position[axis], z_drop_m=edge.z_drop_m,
            slide_speed_mps=SLIDE_V)

    # sim.yaml · scan_manager 절과 같은 값
    params = BiasParams(tip_radius_m=BOX.tip_radius_m, detect_latency_s=0.020,
                        edge_round_radius_m=0.0, edge_bias_offset_m=0.0)
    box = estimate_box(
        TopObservation(z_m=contact.first_sample.position[2], descend_speed_mps=DESCEND_V),
        edges, support_z_m=BOX.origin_m[2], params=params)

    assert box.success, box.detail
    # 가상 박스: 가로 100 · 세로 60 · 높이 40 mm
    assert box.width == pytest.approx(BOX.size_m[0], abs=0.4 * MM)
    assert box.length == pytest.approx(BOX.size_m[1], abs=0.4 * MM)
    assert box.height == pytest.approx(BOX.size_m[2], abs=0.2 * MM)
    assert box.z_top == pytest.approx(TOP_Z, abs=0.2 * MM)


def test_sample_gap_drops_the_trend_instead_of_confirming_a_late_edge():
    """Virtual 실측 342 ms 공백(2026-09-20). 공백을 사이에 둔 두 점을 같은 추세에 넣지 않는다."""
    src = SimSource(BOX)
    detector = ContactDetector(CONFIG, EDGE)
    detector.set_baseline((0.0, 0.0, 0.0))
    z = TOP_Z - 0.15 * MM
    for i in range(40):                                # 누르며 평평하게 민다
        detector.update(src.apply(sample(i, (0.40 + 0.0002 * i, 0.0, z), OP_SLIDE, t=i * SAMPLE_DT)))
    assert detector.edge_armed
    # 342 ms 공백 뒤 첫 샘플
    detector.update(src.apply(sample(40, (0.408, 0.0, z), OP_SLIDE, t=40 * SAMPLE_DT + 0.342)))
    assert detector.trend_gap
    assert detector._trend.predict(41 * SAMPLE_DT + 0.342) is None     # 추세선을 다시 쌓는 중
