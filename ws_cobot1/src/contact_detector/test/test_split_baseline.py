"""하강 기준과 밀기 기준을 나눈다 (#109). ROS 없이 돈다.

수치는 2026-09-21 실기 기록(docs/test-reports/realrobot-session_20260921.md)에서 가져왔다.
- 5-2: 홈에서 정지 상태로 잡은 F0 = (0.321, 0.514, 2.101) N. 출발 약 4 s 뒤 외력 추정이 (1.97, 1.31, 0.56) N
  계단식으로 치우쳐 |F - F0| 2.43 N, 21.7 s 에 3.04 N 으로 기어올라 큐브 45 mm 위에서 거짓 CONTACT
- 17 시 54 분 시험 407: 이동 중 7.5~9 s 에 잡은 F0 에서 21 s 에 3.15 N 벗어나 윗면 38 mm 위 거짓 CONTACT
  (자세에 따라 흐른다: 같은 하강에서 Fz 1.8 → 4.1 N)
- 5-5: 새 탐침 접촉 강성 약 43 N/mm. 하강 3 mm/s
- 5-1: +x 로 미는 동안 허공에서도 Fx 약 -5 N (옆 이동 이력)
"""
import math

import pytest

from contact_detector.detector_core import (
    ContactDetector,
    DescendRefConfig,
    DetectorConfig,
    EdgeConfig,
    OP_DESCEND,
    OP_MOVE_TO,
    OP_SLIDE,
    Sample,
    TYPE_CONTACT,
    TYPE_EDGE,
    TYPE_OVER_FORCE,
)

MM = 1e-3
DT = 0.02
CONFIG = DetectorConfig(contact_threshold_n=3.0, debounce_n=3, over_force_n=30.0, over_force_debounce_n=1)
DESCEND_REF = DescendRefConfig(window_s=1.0, lag_s=0.3, min_samples=10, hold_threshold_n=6.0)

STATIC_F0 = (0.321, 0.514, 2.101)          # 5-2 정지 tare
MOVING_BIAS = (1.97, 1.31, 0.56)           # 5-2 출발 4 s 뒤 계단식 치우침 (|.| = 2.43 N)
STIFFNESS = 43000.0                        # 5-5 [N/m]
Z0 = 0.28784                               # 홈 팁 높이 (units-frames.md v0.1.11)
Z_TOP = 0.18040                            # 큐브 윗면 (units-frames.md v0.1.11)
V_DOWN = 0.003


def run(detector, samples):
    return [d for s in samples for d in detector.update(s)]


def descent(z_top=Z_TOP, seconds=40.0, motion_id=1, start_t=0.0, noise=None, extra=(0.0, 0.0, 0.0),
            operation=OP_DESCEND, start_id=1, path_drift=None, gap=None):
    """홈에서 3 mm/s 하강. 4 s 뒤 치우침이 붙고 천천히 기어오른다(21.7 s 에 3.04 N). 윗면에서 반력이 생긴다.

    path_drift: (시작 s, 끝 s, (dx, dy, dz)) 동안 추정값이 그만큼 서서히 흐른다(자세에 따른 흐름, 407).
    gap: (시작 s, 길이 s) 동안 샘플이 없다.
    """
    samples = []
    for i in range(int(seconds / DT)):
        t = i * DT
        if gap and gap[0] <= t < gap[0] + gap[1]:
            continue
        z = Z0 - V_DOWN * t
        k = 0.0 if t < 4.0 else 1.0 + 0.25 * (t - 4.0) / 17.7
        f = [STATIC_F0[j] + k * MOVING_BIAS[j] + extra[j] for j in range(3)]
        if path_drift:
            a, b, d = path_drift
            r = min(max((t - a) / (b - a), 0.0), 1.0)
            f = [f[j] + r * d[j] for j in range(3)]
        if noise:
            f[2] += noise(i, t)
        if z < z_top:
            f[2] += STIFFNESS * (z_top - z)                 # 누르면 반작용이 위로
        samples.append(Sample(
            sample_id=start_id + i, pose_stamp=start_t + t, force_stamp=start_t + t + 0.004,
            position=(0.4236, -0.1861, z), force=tuple(f), motion_id=motion_id, operation=operation))
    return samples


def contact_before_over_force(detections):
    """합성 하강은 CONTACT 뒤에도 멈추지 않는다(실기는 robot_manager 가 멈춘다). CONTACT 가 과대 외력보다 먼저인지 본다."""
    types = [x.type for x in detections]
    return TYPE_CONTACT in types and (TYPE_OVER_FORCE not in types
                                      or types.index(TYPE_CONTACT) < types.index(TYPE_OVER_FORCE))


def contacts(detections):
    return [x for x in detections if x.type == TYPE_CONTACT]


def detector(descend_ref=DESCEND_REF, edge=None, static=STATIC_F0):
    d = ContactDetector(CONFIG, edge, descend_ref)
    if static is not None:
        d.set_baseline(static)                             # scan_manager 가 준비 단계에서 잡는 정지 F0
    return d


# ---------------------------------------------------------------- 하강: 이동 기준

def test_static_baseline_reproduces_the_false_contact_in_the_air():
    """이전 동작(정지 F0 하나): 5-2 의 치우침만으로 공중에서 CONTACT."""
    found = contacts(run(detector(descend_ref=None), descent()))
    assert found and found[0].first_sample.position[2] > Z_TOP + 0.030


def test_moving_reference_removes_the_false_contact_and_finds_the_top():
    d = detector()
    found = contacts(run(d, descent()))
    assert len(found) == 1 and not found[0].hold
    assert found[0].first_sample.position[2] == pytest.approx(Z_TOP, abs=0.2 * MM)


def test_drift_along_the_path_does_not_give_a_false_contact():
    """407: 한 번 잡은 이동 중 F0 에서 14 s 동안 약 3 N 흐르면 공중에서 CONTACT 가 났다. 이동 기준은 따라간다."""
    drift = (9.0, 23.0, (1.2, -0.3, 2.3))                  # |.| 약 2.6 N, 5-2 의 기어오름에 더해진다
    found = contacts(run(detector(), descent(path_drift=drift)))
    assert len(found) == 1
    assert found[0].first_sample.position[2] == pytest.approx(Z_TOP, abs=0.2 * MM)


def test_contact_right_after_start_is_judged_with_the_hold_threshold():
    """출발 뒤 1 s 는 이동 기준이 없다. 판정을 끄지 않고 정지 F0 와 6 N 으로 본다. 과대 외력보다 먼저 멈춘다."""
    near_top = Z0 - 0.002                                   # 출발 2 mm 아래(0.67 s)에 윗면
    detections = run(detector(), descent(z_top=near_top, seconds=1.5))
    found = contacts(detections)
    assert len(found) == 1 and found[0].hold
    assert found[0].first_sample.position[2] == pytest.approx(near_top, abs=0.2 * MM)
    assert contact_before_over_force(detections)


def test_without_any_tare_the_hold_uses_the_force_at_descend_start():
    """/contact/tare 를 한 번도 안 했으면 이번 DESCEND 첫 샘플의 F 를 둔한 판정의 기준으로 쓴다."""
    d = detector(static=None)
    near_top = Z0 - 0.002
    found = contacts(run(d, descent(z_top=near_top, seconds=1.5)))
    assert d.descend_start_force == pytest.approx(STATIC_F0)
    assert len(found) == 1 and found[0].hold


def test_without_any_tare_the_full_descent_still_finds_the_top():
    found = contacts(run(detector(static=None), descent()))
    assert len(found) == 1 and not found[0].hold
    assert found[0].first_sample.position[2] == pytest.approx(Z_TOP, abs=0.2 * MM)


def test_short_sample_gap_keeps_the_reference():
    """실기 공백(120~360 ms)으로는 구간을 비우지 않는다. 비우면 1 s 동안 둔한 판정으로 떨어져 더 눌린 좌표를 낸다."""
    gap_at = (Z0 - Z_TOP) / V_DOWN - 0.5                    # 윗면 1.5 mm 위에서 0.36 s 공백
    found = contacts(run(detector(), descent(gap=(gap_at, 0.36))))
    assert len(found) == 1 and not found[0].hold
    assert found[0].first_sample.position[2] == pytest.approx(Z_TOP, abs=0.2 * MM)


def test_long_sample_gap_falls_back_to_the_hold_threshold():
    """구간 안에 남은 샘플이 min_samples 보다 적으면 기준이 없다. 그동안도 판정은 한다(6 N)."""
    gap_at = (Z0 - Z_TOP) / V_DOWN - 1.0
    detections = run(detector(), descent(gap=(gap_at, 0.9)))
    found = contacts(detections)
    assert len(found) == 1 and found[0].hold
    assert contact_before_over_force(detections)


def test_recreating_the_detector_mid_descent_keeps_judging():
    """파라미터를 바꾸면 노드가 detector 를 새로 만든다. 구간을 다시 쌓는 동안도 정지 F0 와 올린 임계로 판정한다."""
    samples = descent()
    t_change = (Z0 - (Z_TOP + 0.002)) / V_DOWN              # 윗면 2 mm 위(0.67 s 앞)
    first = detector()
    run(first, [x for x in samples if x.pose_stamp < t_change])
    second = ContactDetector(CONFIG, None, DESCEND_REF)
    second.set_baseline(first.baseline)
    detections = run(second, [x for x in samples if x.pose_stamp >= t_change])
    found = contacts(detections)
    assert len(found) == 1 and found[0].hold
    assert contact_before_over_force(detections)


def test_reference_is_frozen_while_the_contact_builds_up():
    """조건이 성립한 샘플은 구간에 넣지 않는다. 닿는 힘이 기준을 끌어올려 판정이 풀리지 않게."""
    d = detector()
    run(d, descent())
    ref = d.descend_baseline
    assert ref is not None and abs(ref[2] - (STATIC_F0[2] + MOVING_BIAS[2] * 1.4)) < 0.3


def test_contact_reference_is_kept_for_the_slide_until_a_new_tare():
    """밀기의 보고값 |F - F0| 에는 CONTACT 때의 이동 기준을 쓴다. 그 뒤 /contact/tare 를 하면 그 값이 이긴다."""
    d = detector()
    run(d, descent())
    slide_sample = Sample(sample_id=99999, pose_stamp=100.0, force_stamp=100.0, position=(0.43, -0.1861, Z_TOP),
                          force=STATIC_F0, motion_id=2, operation=OP_SLIDE)
    d.update(slide_sample)
    assert d.active_baseline == d.descend_baseline
    new_f0 = (0.5, 0.5, 2.5)
    d.set_baseline(new_f0)
    d.update(slide_sample)
    assert d.active_baseline == new_f0


def test_each_descent_builds_its_own_reference():
    d = detector()
    run(d, descent(seconds=9.0, motion_id=1))
    run(d, descent(seconds=0.5, motion_id=2, start_t=100.0, start_id=10000))
    assert d.contact_hold                                    # 새 하강은 구간이 빈 채로 시작한다


def test_descend_after_another_operation_restarts_even_with_the_same_motion_id():
    d = detector()
    run(d, descent(seconds=9.0, motion_id=0))
    run(d, descent(seconds=0.2, motion_id=0, operation=OP_MOVE_TO, start_t=50.0, start_id=5000))
    run(d, descent(seconds=0.2, motion_id=0, start_t=60.0, start_id=6000))
    assert d.contact_hold


def test_config_rejects_bad_descend_ref_values():
    for bad in (dict(window_s=0.0), dict(lag_s=1.0), dict(lag_s=-0.1), dict(min_samples=0),
                dict(hold_threshold_n=0.0)):
        values = dict(window_s=1.0, lag_s=0.3, min_samples=10, hold_threshold_n=6.0)
        values.update(bad)
        with pytest.raises(ValueError):
            DescendRefConfig(**values)


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
    t = armed_at(detector(descend_ref=None, edge=EDGE_FORCE), slide(gap_fill, 2.0))
    fill_done = ENABLE_S + 0.5
    assert t is not None and t < fill_done


def test_z_arming_waits_until_the_gap_is_filled_and_the_tip_slides():
    t = armed_at(detector(descend_ref=None, edge=EDGE_Z), slide(gap_fill, 2.0))
    fill_done = ENABLE_S + 0.5                              # 1 mm ÷ 2 mm/s
    assert t is not None and t >= fill_done + 0.75 * EDGE_Z.arm_still_window_s - DT


def test_z_arming_does_not_turn_on_while_force_control_is_being_enabled():
    """힘 제어를 켜는 동안에는 팁이 떠 있는데 z 도 멈춰 있다. x · y 가 움직이지 않으면 켜지 않는다."""
    d = detector(descend_ref=None, edge=EDGE_Z)
    for s in slide(gap_fill, ENABLE_S):
        d.update(s)
    assert not d.edge_armed


def test_first_direction_in_contact_arms_and_finds_the_edge():
    """첫 방향: 윗면에 눌린 채 시작한다. 밀기 시작 뒤 곧 켜지고, 모서리에서 EDGE 를 낸다."""
    t_edge = ENABLE_S + 0.040 / SLIDE_V                     # 중심에서 40 mm

    def z(t):
        return Z_TOP if t < t_edge else Z_TOP - 0.010 * (t - t_edge)   # 모서리 뒤 10 mm/s 로 내려앉음
    d = detector(descend_ref=None, edge=EDGE_Z)
    samples = slide(z, t_edge + 1.0)
    edges = [x for x in run(d, samples) if x.type == TYPE_EDGE]
    assert len(edges) == 1
    assert edges[0].first_sample.position[0] == pytest.approx(0.4236 + 0.040, abs=1.0 * MM)


def test_sample_gap_restarts_the_arming_window():
    d = detector(descend_ref=None, edge=EDGE_Z)
    t = armed_at(d, slide(lambda t: Z_TOP, 2.0, gap_at=(ENABLE_S + 0.02, ENABLE_S + 0.32)))
    assert t is not None and t >= ENABLE_S + 0.32 + 0.75 * EDGE_Z.arm_still_window_s - DT


def test_edge_config_needs_all_three_z_arming_values():
    with pytest.raises(ValueError):
        EdgeConfig(edge_drop_m=0.5 * MM, debounce_n=3, arm_force_n=1.5, trend_window_s=0.5,
                   trend_min_samples=10, max_gap_s=0.2, arm_still_window_s=0.2)
    assert not EDGE_FORCE.arm_by_z and EDGE_Z.arm_by_z
    assert math.isfinite(EDGE_Z.arm_still_m)
