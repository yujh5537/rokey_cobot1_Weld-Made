"""하강 기준과 밀기 기준을 나눈다 (#109). ROS 없이 돈다.

수치는 2026-09-21 실기 기록(docs/test-reports/realrobot-session_20260921.md)에서 가져왔다.
- 5-2: 홈에서 정지 상태로 잡은 F0 = (0.321, 0.514, 2.101) N. 출발 약 4 s 뒤 외력 추정이 (1.97, 1.31, 0.56) N
  계단식으로 치우쳐 |F - F0| 2.43 N, 21.7 s 에 3.04 N 으로 기어올라 큐브 45 mm 위에서 거짓 CONTACT
- 5-5: 새 탐침 접촉 강성 약 43 N/mm. 하강 3 mm/s
- 5-1: +x 로 미는 동안 허공에서도 Fx 약 -5 N (옆 이동 이력)
"""
import math

import pytest

from contact_detector.detector_core import (
    ContactDetector,
    DescendTareConfig,
    DetectorConfig,
    EdgeConfig,
    OP_DESCEND,
    OP_MOVE_TO,
    OP_SLIDE,
    Sample,
    TARE_TOOL_REG_SUSPECT,
    TARE_UNSTABLE,
    TareConfig,
    TYPE_CONTACT,
    TYPE_EDGE,
    TYPE_OVER_FORCE,
)

MM = 1e-3
DT = 0.02
CONFIG = DetectorConfig(contact_threshold_n=3.0, debounce_n=3, over_force_n=30.0, over_force_debounce_n=1)
DESCEND_TARE = DescendTareConfig(delay_s=6.0, duration_s=1.5,
                                 tare=TareConfig(min_samples=30, max_std_n=0.3, max_force_n=6.0))

STATIC_F0 = (0.321, 0.514, 2.101)          # 5-2 정지 tare
MOVING_BIAS = (1.97, 1.31, 0.56)           # 5-2 출발 4 s 뒤 계단식 치우침 (|.| = 2.43 N)
STIFFNESS = 43000.0                        # 5-5 [N/m]
Z0 = 0.28784                               # 홈 팁 높이 (units-frames.md v0.1.11)
Z_TOP = 0.18040                            # 큐브 윗면 (units-frames.md v0.1.11)
V_DOWN = 0.003


def run(detector, samples):
    return [d for s in samples for d in detector.update(s)]


def descent(z_top=Z_TOP, seconds=40.0, motion_id=1, start_t=0.0, noise=None, extra=(0.0, 0.0, 0.0),
            operation=OP_DESCEND, start_id=1):
    """홈에서 3 mm/s 하강. 4 s 뒤 치우침이 붙고 천천히 기어오른다(21.7 s 에 3.04 N). 윗면에서 반력이 생긴다."""
    samples = []
    for i in range(int(seconds / DT)):
        t = i * DT
        z = Z0 - V_DOWN * t
        k = 0.0 if t < 4.0 else 1.0 + 0.25 * (t - 4.0) / 17.7
        f = [STATIC_F0[j] + k * MOVING_BIAS[j] + extra[j] for j in range(3)]
        if noise:
            f[2] += noise(i, t)
        if z < z_top:
            f[2] += STIFFNESS * (z_top - z)                 # 누르면 반작용이 위로
        samples.append(Sample(
            sample_id=start_id + i, pose_stamp=start_t + t, force_stamp=start_t + t + 0.004,
            position=(0.4236, -0.1861, z), force=tuple(f), motion_id=motion_id, operation=operation))
    return samples


def detector(descend_tare=DESCEND_TARE, edge=None):
    d = ContactDetector(CONFIG, edge, descend_tare)
    d.set_baseline(STATIC_F0)                              # scan_manager 가 준비 단계에서 잡는 정지 F0
    return d


# ---------------------------------------------------------------- 하강: 이동 중 자동 영점

def test_static_baseline_reproduces_the_false_contact_in_the_air():
    """자동 영점이 없으면(이전 동작) 9/21 5-2 처럼 윗면 한참 위에서 거짓 CONTACT 가 난다."""
    contacts = [d for d in run(detector(descend_tare=None), descent()) if d.type == TYPE_CONTACT]
    assert contacts, '재현 조건이 틀렸다'
    assert contacts[0].first_sample.position[2] - Z_TOP > 0.020        # 20 mm 넘게 위 허공


def test_moving_baseline_removes_the_false_contact_and_finds_the_top():
    d = detector()
    contacts = [x for x in run(d, descent()) if x.type == TYPE_CONTACT]
    assert d.descend_tare_state == 'done'
    assert d.descend_tare_result.success
    assert len(contacts) == 1
    assert contacts[0].first_sample.position[2] == pytest.approx(Z_TOP, abs=0.2 * MM)
    # 판정 기준은 이동 중 F0 다(치우침이 흡수됐다)
    assert d.descend_baseline[0] == pytest.approx(STATIC_F0[0] + MOVING_BIAS[0] * 1.03, abs=0.05)


def test_contact_is_withheld_while_the_moving_baseline_is_collected_but_over_force_still_watches():
    """영점을 잡는 동안(delay_s + duration_s)은 CONTACT 를 보류한다. 그 사이 닿으면 과대 외력만 멈춘다.

    이 구간에 내려가는 거리(3 mm/s x 7.5 s = 22.5 mm)보다 윗면이 아래에 있어야 한다(계약 3.3).
    """
    near_top = Z0 - 0.005                                   # 출발 5 mm 아래에 윗면
    window_s = DESCEND_TARE.delay_s + DESCEND_TARE.duration_s
    detections = run(detector(), descent(z_top=near_top, seconds=window_s - 0.1))
    assert not [x for x in detections if x.type == TYPE_CONTACT]
    assert [x for x in detections if x.type == TYPE_OVER_FORCE]


def test_failed_moving_baseline_falls_back_to_the_static_one():
    """모으는 동안 흔들리면(무접촉 · 등속이 아니면) 자동 영점을 버리고 /contact/tare 의 F0 로 판정한다."""
    d = detector()
    wobble = lambda i, t: (1.0 if i % 2 else -1.0) if 6.0 <= t <= 7.6 else 0.0   # noqa: E731
    run(d, descent(seconds=9.0, noise=wobble))
    assert d.descend_tare_state == 'failed'
    assert d.descend_tare_result.error == TARE_UNSTABLE
    assert d._judge_baseline() == STATIC_F0


def test_tool_registration_suspect_is_not_adopted():
    """툴 미등록(외력 12 N 치우침)이면 자동 영점도 채택하지 않는다(TOOL_REG_SUSPECT, BRD 4.1.5)."""
    d = detector()
    run(d, descent(seconds=9.0, extra=(0.0, 0.0, 10.0)))
    assert d.descend_tare_state == 'failed'
    assert d.descend_tare_result.error == TARE_TOOL_REG_SUSPECT


def test_each_descent_takes_its_own_baseline():
    """다음 하강(새 motion_id)은 앞 하강의 F0 를 쓰지 않고 다시 잡는다. 자세 · 이력이 다를 수 있다."""
    d = detector()
    run(d, descent(seconds=9.0, motion_id=1))
    assert d.descend_tare_state == 'done'
    second = descent(seconds=1.0, motion_id=2, start_t=100.0, start_id=10000)
    run(d, second)
    assert d.descend_tare_state == 'waiting' and d.descend_baseline is None


def test_descend_after_another_operation_restarts_even_with_the_same_motion_id():
    d = detector()
    run(d, descent(seconds=9.0, motion_id=0))
    run(d, descent(seconds=0.2, motion_id=0, operation=OP_MOVE_TO, start_t=50.0, start_id=5000))
    run(d, descent(seconds=0.2, motion_id=0, start_t=60.0, start_id=6000))
    assert d.descend_tare_state == 'waiting'


def test_config_rejects_bad_descend_tare_values():
    with pytest.raises(ValueError):
        DescendTareConfig(delay_s=-1.0, duration_s=1.5, tare=DESCEND_TARE.tare)
    with pytest.raises(ValueError):
        DescendTareConfig(delay_s=6.0, duration_s=0.0, tare=DESCEND_TARE.tare)


# ---------------------------------------------------------------- 밀기: z 로 판정 켜기

EDGE_Z = EdgeConfig(edge_drop_m=0.5 * MM, debounce_n=3, arm_force_n=1.5, trend_window_s=0.5,
                    trend_min_samples=10, max_gap_s=0.2,
                    arm_still_window_s=0.2, arm_still_m=0.1 * MM, arm_travel_m=0.5 * MM)
EDGE_FORCE = EdgeConfig(edge_drop_m=0.5 * MM, debounce_n=3, arm_force_n=1.5, trend_window_s=0.5,
                        trend_min_samples=10, max_gap_s=0.2)
LATERAL_BIAS = (-5.0, 0.0, 0.0)            # 5-1: 옆으로 미는 동안 허공에서도 Fx -5 N
ENABLE_S = 0.3                             # 힘 제어를 켜는 동안(팁은 멈춰 있다)
SLIDE_V = 0.005


def slide(z_of_t, seconds, start_x=0.4236, start_id=1, gap_at=None):
    """밀기. 처음 ENABLE_S 동안은 멈춰 있고(힘 제어 켜는 중), 그 뒤 +x 로 5 mm/s. 옆 이동 이력이 늘 실린다."""
    samples, t, i = [], 0.0, 0
    while t < seconds:
        if gap_at is not None and gap_at[0] <= t < gap_at[1]:
            t += DT
            continue
        x = start_x + SLIDE_V * max(0.0, t - ENABLE_S)
        bias = LATERAL_BIAS if t >= ENABLE_S else (0.0, 0.0, 0.0)
        f = tuple(STATIC_F0[j] + bias[j] for j in range(3))
        samples.append(Sample(sample_id=start_id + i, pose_stamp=t, force_stamp=t + 0.004,
                              position=(x, -0.1861, z_of_t(t)), force=f, motion_id=7, operation=OP_SLIDE))
        t += DT
        i += 1
    return samples


def gap_fill(t):
    """2~4 방향: 윗면 1 mm 위에서 시작해, 밀기가 시작되면 2 mm/s 로 틈을 메운 뒤 윗면을 따라간다."""
    if t < ENABLE_S:
        return Z_TOP + 1 * MM
    return max(Z_TOP, Z_TOP + 1 * MM - 0.002 * (t - ENABLE_S))


def armed_at(d, samples):
    for s in samples:
        d.update(s)
        if d.edge_armed:
            return s.pose_stamp
    return None


def test_force_arming_turns_on_before_the_gap_is_filled():
    """(이전 동작) 하강용 F0 로 |F - F0| 를 보면 옆 이동 이력 5 N 때문에 닿기 전에 켜진다."""
    t = armed_at(detector(descend_tare=None, edge=EDGE_FORCE), slide(gap_fill, 2.0))
    fill_done = ENABLE_S + 0.5
    assert t is not None and t < fill_done


def test_z_arming_waits_until_the_gap_is_filled_and_the_tip_slides():
    t = armed_at(detector(descend_tare=None, edge=EDGE_Z), slide(gap_fill, 2.0))
    fill_done = ENABLE_S + 0.5                              # 1 mm ÷ 2 mm/s
    assert t is not None and t >= fill_done + 0.75 * EDGE_Z.arm_still_window_s - DT


def test_z_arming_does_not_turn_on_while_force_control_is_being_enabled():
    """힘 제어를 켜는 동안에는 팁이 떠 있는데 z 도 멈춰 있다. x · y 가 움직이지 않으면 켜지 않는다."""
    d = detector(descend_tare=None, edge=EDGE_Z)
    for s in slide(gap_fill, ENABLE_S):
        d.update(s)
    assert not d.edge_armed


def test_first_direction_in_contact_arms_and_finds_the_edge():
    """첫 방향: 윗면에 눌린 채 시작한다. 밀기 시작 뒤 곧 켜지고, 모서리에서 EDGE 를 낸다."""
    t_edge = ENABLE_S + 0.040 / SLIDE_V                     # 중심에서 40 mm

    def z(t):
        return Z_TOP if t < t_edge else Z_TOP - 0.010 * (t - t_edge)   # 모서리 뒤 10 mm/s 로 내려앉음
    d = detector(descend_tare=None, edge=EDGE_Z)
    samples = slide(z, t_edge + 1.0)
    edges = [x for x in run(d, samples) if x.type == TYPE_EDGE]
    assert len(edges) == 1
    assert edges[0].first_sample.position[0] == pytest.approx(0.4236 + 0.040, abs=1.0 * MM)


def test_sample_gap_restarts_the_arming_window():
    d = detector(descend_tare=None, edge=EDGE_Z)
    t = armed_at(d, slide(lambda t: Z_TOP, 2.0, gap_at=(ENABLE_S + 0.02, ENABLE_S + 0.32)))
    assert t is not None and t >= ENABLE_S + 0.32 + 0.75 * EDGE_Z.arm_still_window_s - DT


def test_edge_config_needs_all_three_z_arming_values():
    with pytest.raises(ValueError):
        EdgeConfig(edge_drop_m=0.5 * MM, debounce_n=3, arm_force_n=1.5, trend_window_s=0.5,
                   trend_min_samples=10, max_gap_s=0.2, arm_still_window_s=0.2)
    assert not EDGE_FORCE.arm_by_z and EDGE_Z.arm_by_z
    assert math.isfinite(EDGE_Z.arm_still_m)
