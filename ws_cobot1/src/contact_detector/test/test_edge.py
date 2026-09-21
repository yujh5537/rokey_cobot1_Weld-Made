"""접촉 소실(EDGE) 판정 단위 테스트. ROS 없이 돈다.

z 궤적을 직접 만들어 넣는다: 평평한 윗면, 기울어진 윗면, 서서히 밀리는 탐침, 틈을 메우는 하강, 모서리.
"""
import math

import pytest
from conftest import BASELINE
from contact_detector.detector_core import (
    ContactDetector,
    DetectorConfig,
    EdgeConfig,
    OP_DESCEND,
    OP_SLIDE,
    Sample,
    TYPE_EDGE,
)

MM = 1e-3
DT = 0.0234                  # 실기 기록기 실측 주기(2026-09-20 idle_30s.csv). 테스트용 값이다
SLIDE_V = 5 * MM
TIP_R = 0.225 * MM
FALL_V = 10 * MM             # 모서리를 벗어난 뒤 내려앉는 속도 (테스트용 가정)
PRESS = 4.0                  # 누르는 힘 [N] (테스트용)

CONFIG = DetectorConfig(contact_threshold_n=3.0, debounce_n=3, over_force_n=30.0, over_force_debounce_n=1)
EDGE = EdgeConfig(edge_drop_m=0.5 * MM, debounce_n=3, arm_force_n=1.5, trend_window_s=0.5,
                  trend_min_samples=10, max_gap_s=0.2)


def detector(edge=EDGE, tared=True):
    d = ContactDetector(CONFIG, edge)
    if tared:
        d.set_baseline(BASELINE)
    return d


def slide(z_of_t, press_of_t=lambda t: PRESS, seconds=6.0, motion_id=1, operation=OP_SLIDE, start_id=1):
    samples = []
    for i in range(int(seconds / DT)):
        t = i * DT
        samples.append(Sample(
            sample_id=start_id + i, pose_stamp=t, force_stamp=t + 0.0005,
            position=(0.40 + SLIDE_V * t, 0.0, z_of_t(t)),
            force=(BASELINE[0], BASELINE[1], BASELINE[2] - press_of_t(t)),
            motion_id=motion_id, operation=operation))
    return samples


def edge_profile(t_edge, z_surface=lambda t: 0.080):
    """t_edge 에서 구 중심이 모서리에 닿는다. r 만큼 지날 때까지 굴러 내려오고, 그 뒤로는 FALL_V 로 내려앉는다."""
    def z(t):
        d = SLIDE_V * (t - t_edge)
        if d <= 0:
            return z_surface(t)
        if d < TIP_R:
            return z_surface(t_edge) - (TIP_R - math.sqrt(TIP_R ** 2 - d ** 2))
        return z_surface(t_edge) - TIP_R - FALL_V * (t - t_edge - TIP_R / SLIDE_V)
    return z


def run(d, samples):
    return [x for s in samples for x in d.update(s)]


def test_edge_on_flat_top():
    samples = slide(edge_profile(t_edge=3.0))
    detections = run(detector(), samples)
    assert [x.type for x in detections] == [TYPE_EDGE]
    e = detections[0]
    # 판정 샘플 = 하강량이 처음 0.5 mm 를 넘은 샘플. 그 순간의 하강량을 δ 로 싣는다
    assert e.first_sample.sample_id == e.sample.sample_id - 2 and e.debounce_count == 3
    true_drop = 0.080 - e.first_sample.position[2]
    assert true_drop > 0.5 * MM
    assert e.z_drop_m == pytest.approx(true_drop, abs=0.03 * MM)
    # 모서리를 지나친 거리: r + (δ − r) 을 내려앉는 동안 더 간 거리
    past_edge = e.first_sample.position[0] - (0.40 + SLIDE_V * 3.0)
    assert past_edge == pytest.approx(TIP_R + SLIDE_V * (true_drop - TIP_R) / FALL_V, abs=1e-9)
    assert e.force_delta_n == pytest.approx(PRESS)


def test_tilted_top_is_not_an_edge():
    # 윗면이 0.87° 기울어 있으면 5 mm/s 로 16 s(80 mm) 미는 동안 z 가 1.2 mm 내려간다. 누적으로는 0.5 mm 를 넘는다
    tilt = lambda t: 0.080 - math.tan(math.radians(0.87)) * SLIDE_V * t    # noqa: E731
    assert 0.080 - tilt(16.0) > 1.2 * MM
    assert run(detector(), slide(tilt, seconds=16.0)) == []


def test_edge_on_tilted_top_reports_drop_from_trend():
    tilt = lambda t: 0.080 - math.tan(math.radians(0.87)) * SLIDE_V * t    # noqa: E731
    detections = run(detector(), slide(edge_profile(8.0, tilt), seconds=10.0))
    assert [x.type for x in detections] == [TYPE_EDGE]
    e = detections[0]
    # 하강량은 밀기 시작 z 가 아니라 추세선(기울어진 윗면의 연장) 기준이다
    expected = tilt(e.first_sample.pose_stamp) - e.first_sample.position[2]
    assert e.z_drop_m == pytest.approx(expected, abs=0.03 * MM)
    assert e.z_drop_m < 0.080 - e.first_sample.position[2]


def test_slow_probe_creep_is_not_an_edge():
    # 탐침이 홀더 안으로 서서히 밀려 들어간다: 80 s 에 1.3 mm (PR #80 의 두 시점 비교와 같은 빠르기)
    creep = lambda t: 0.080 - 1.3 * MM * t / 80.0                           # noqa: E731
    assert run(detector(), slide(creep, seconds=40.0)) == []


def test_sudden_probe_slip_cannot_be_told_from_an_edge():
    # 한계를 고정해 둔다: 한 번에 0.8 mm 툭 들어가면 모서리와 같은 모양이다. 소프트웨어로 가를 수 없다
    slip = lambda t: 0.080 - (0.8 * MM if t > 2.0 else 0.0)                 # noqa: E731
    assert [x.type for x in run(detector(), slide(slip))] == [TYPE_EDGE]


def test_gap_closing_at_slide_start_is_not_an_edge():
    # 계약 7.3: SLIDE 는 접촉면 1 mm 위에서 시작하고 목표 힘이 틈을 메운다. 닿기 전에는 누르는 힘이 없다
    t_touch = 1.0
    z = lambda t: 0.081 - 1.0 * MM * min(t, t_touch) / t_touch               # noqa: E731
    press = lambda t: 0.0 if t < t_touch else PRESS                           # noqa: E731
    d = detector()
    assert run(d, slide(z, press, seconds=4.0)) == []
    assert d.edge_armed
    # 같은 시작 뒤에 모서리가 오면 잡는다
    z_then_edge = lambda t: z(t) if t < 3.0 else edge_profile(3.0)(t)         # noqa: E731
    assert [x.type for x in run(detector(), slide(z_then_edge, press, seconds=5.0))] == [TYPE_EDGE]


def test_not_armed_without_pressing_force():
    d = detector()
    assert run(d, slide(edge_profile(3.0), press_of_t=lambda t: 1.0)) == []
    assert not d.edge_armed


def test_drop_shorter_than_debounce_is_ignored():
    blip = lambda t: 0.080 - (0.8 * MM if 2.0 <= t < 2.0 + 2 * DT else 0.0)  # noqa: E731
    assert run(detector(), slide(blip)) == []


def test_trend_survives_a_long_debounce():
    # 기준선을 얼린 동안 창이 비면 안 된다: 디바운스 10 회(0.23 s)가 창 0.25 s 에 가까워도 확정돼야 한다
    long_debounce = EdgeConfig(edge_drop_m=0.5 * MM, debounce_n=10, arm_force_n=1.5,
                               trend_window_s=0.25, trend_min_samples=5, max_gap_s=0.2)
    step = lambda t: 0.080 - (0.8 * MM if t > 3.0 else 0.0)                 # noqa: E731
    detections = run(detector(edge=long_debounce), slide(step))
    assert [x.type for x in detections] == [TYPE_EDGE]
    assert detections[0].debounce_count == 10
    assert detections[0].z_drop_m == pytest.approx(0.8 * MM, abs=1e-6)


def test_edge_config_requires_max_gap():
    with pytest.raises(ValueError):
        EdgeConfig(edge_drop_m=0.5 * MM, debounce_n=3, arm_force_n=1.5,
                   trend_window_s=0.5, trend_min_samples=10, max_gap_s=0.0)


def test_no_edge_without_tare_or_outside_slide_or_when_disabled():
    samples = slide(edge_profile(3.0))
    assert run(detector(tared=False), samples) == []
    assert run(detector(), slide(edge_profile(3.0), operation=OP_DESCEND, press_of_t=lambda t: 0.0)) == []
    assert run(detector(edge=None), samples) == []


def test_edge_right_after_arming_is_found_late_with_understated_drop():
    # 한계를 고정해 둔다: 누름 확인 0.2 s 만에 모서리가 오면 추세선이 내려앉는 중의 z 로만 만들어진다.
    # 그래도 EDGE 는 나오지만 늦고, 하강량이 실제보다 작게 실린다. 밀기는 모서리에서 충분히 떨어져 시작해야 한다
    detections = run(detector(), slide(edge_profile(0.2), seconds=1.0))
    assert [x.type for x in detections] == [TYPE_EDGE]
    e = detections[0]
    true_drop = 0.080 - e.first_sample.position[2]
    assert true_drop > 2 * EDGE.edge_drop_m          # 늦게 잡혔다: 이미 임계의 두 배 넘게 내려앉은 뒤다
    assert e.z_drop_m < true_drop                     # 하강량이 작게 실린다


def test_once_per_motion_and_state_does_not_leak_into_next_motion():
    d = detector()
    assert len(run(d, slide(edge_profile(3.0), motion_id=1))) == 1
    # 다음 동작은 누름 확인부터 다시 한다. 앞 동작의 낮은 z 가 기준선에 남아 있으면 안 된다
    assert run(d, slide(lambda t: 0.080, motion_id=2, start_id=1000)) == []
    assert len(run(d, slide(edge_profile(3.0), motion_id=3, start_id=2000))) == 1


def test_edge_config_rejects_bad_values():
    with pytest.raises(ValueError):
        EdgeConfig(edge_drop_m=0.0, debounce_n=3, arm_force_n=1.5, trend_window_s=0.5,
                   trend_min_samples=10, max_gap_s=0.2)
    with pytest.raises(ValueError):
        EdgeConfig(edge_drop_m=0.0005, debounce_n=3, arm_force_n=1.5, trend_window_s=0.5,
                   trend_min_samples=1, max_gap_s=0.2)
