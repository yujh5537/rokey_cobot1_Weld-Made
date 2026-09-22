"""힘 꺾임 EDGE (#128). ROS 없이 돈다.

수치는 2026-09-21 실기 밀기 4회(오전 5, 오후 85 · 102, 17 시 332)에서 가져왔다.
- 윗면을 미는 동안 Fz 약 +1.9 N, 모서리를 벗어나면 0.4 s 안에 약 -1.9 N (약 3.8 N 꺾임)
- 모서리 앞 Fz 잡음: 최근 0.5 s 중앙값보다 최대 0.65 N 낮았다
- z 는 모서리 뒤 일정 속도로 떨어진다: 0.2~0.35 mm/s(오전 · 오후) 또는 약 2 mm/s(17 시). 추세선이 기울기를 따라가
  0.5 mm 조건이 성립하지 않았다
- 오전 1회는 9.8 N 으로 눌린 채 시작해 순응이 켜진 뒤 약 1 s 동안 Fz 가 0.7 N 까지 풀렸다
"""
import math

import pytest

from contact_detector.detector_core import (
    ContactDetector,
    DetectorConfig,
    EdgeConfig,
    OP_SLIDE,
    Sample,
    TYPE_EDGE,
)

MM = 1e-3
DT = 0.02
V_SLIDE = 0.005
X0 = 0.42356
X_EDGE = X0 + 0.040                  # 큐브 중심 + 40 mm
Z_TOP = 0.18040
F_PRESS = 1.9
F_AIR = -1.9
CONFIG = DetectorConfig(contact_threshold_n=3.0, debounce_n=3, over_force_n=30.0, over_force_debounce_n=1)
FORCE = dict(force_drop_n=1.0, force_window_s=0.5, force_lag_s=0.1, force_settle_s=1.5)


def edge_config(**force):
    return EdgeConfig(edge_drop_m=0.5 * MM, debounce_n=3, arm_force_n=1.5, trend_window_s=0.5,
                      trend_min_samples=10, max_gap_s=0.1,
                      arm_still_window_s=0.2, arm_still_m=0.1 * MM, arm_travel_m=0.5 * MM, **force)


def noise(i):
    """결정적인 잡음. 폭 ±0.3 N, 가끔 -0.6 N (실기 모서리 앞 최대 0.65 N)."""
    return 0.3 * math.sin(1.7 * i) * math.cos(0.31 * i) - (0.3 if i % 37 == 0 else 0.0)


def slide(seconds=12.0, fall_mps=0.0003, start_press_n=None, gap=None):
    """+x 5 mm/s 로 밀기. 모서리를 지나면 Fz 가 0.4 s 에 걸쳐 꺾이고 z 가 fall_mps 로 떨어진다.

    start_press_n: 눌린 채 시작하면 처음 1 s 동안 Fz 가 그 값에서 F_PRESS 로 풀린다(z 는 그동안 0.7 mm 올라온다).
    gap: (시작 s, 길이 s) 동안 샘플이 없다.
    """
    samples = []
    for i in range(int(seconds / DT)):
        t = i * DT
        if gap and gap[0] <= t < gap[0] + gap[1]:
            continue
        x = X0 + V_SLIDE * t
        z = Z_TOP
        fz = F_PRESS
        if start_press_n is not None and t < 1.0:
            fz = start_press_n + (F_PRESS - start_press_n) * t
            z = Z_TOP - 0.7 * MM * (1.0 - min(t / 0.4, 1.0))
        past = (x - X_EDGE) / V_SLIDE
        if past > 0:
            fz = F_PRESS + (F_AIR - F_PRESS) * min(past / 0.4, 1.0)
            z = Z_TOP - fall_mps * past
        samples.append(Sample(
            sample_id=i + 1, pose_stamp=t, force_stamp=t + 0.004, position=(x, -0.18606, z),
            force=(-5.0, 0.8, fz + noise(i)), motion_id=7, operation=OP_SLIDE))
    return samples


def edges(edge, samples):
    d = ContactDetector(CONFIG, edge)
    d.set_baseline((0.0, 0.0, 2.0))
    return [x for s in samples for x in d.update(s) if x.type == TYPE_EDGE]


@pytest.mark.parametrize('fall_mps', [0.0003, 0.002])
def test_z_trend_alone_misses_a_steady_fall(fall_mps):
    """실기에서 본 문제. 일정 속도 하강은 추세선이 따라가 0.5 mm 를 넘지 못한다(느리면 끝까지, 빨라도 창 0.5 s 면)."""
    assert edges(edge_config(), slide(fall_mps=fall_mps)) == []


@pytest.mark.parametrize('fall_mps', [0.0003, 0.002])
def test_force_break_finds_the_edge_right_after_it(fall_mps):
    found = edges(edge_config(**FORCE), slide(fall_mps=fall_mps))
    assert len(found) == 1
    edge = found[0]
    assert edge.edge_signal == 'force'
    assert 0.0 <= edge.first_sample.position[0] - X_EDGE < 1.5 * MM     # 실기 재생: 모서리 뒤 0.9~1.0 mm
    assert edge.z_drop_m is None or edge.z_drop_m >= 0.0                # 편향 보정(bias.py)은 음수를 받지 않는다


def test_noise_on_the_top_face_is_not_an_edge():
    """모서리 앞 잡음(최대 0.65 N 낮음)으로는 꺾임이 성립하지 않는다."""
    before_edge = [s for s in slide() if s.position[0] < X_EDGE]
    assert edges(edge_config(**FORCE), before_edge) == []


def test_pressed_start_is_ignored_during_settle():
    """눌린 채(9.8 N) 시작하면 순응이 켜진 뒤 1 s 동안 Fz 가 풀린다. settle 이 없으면 그것을 모서리로 본다."""
    pressed = slide(start_press_n=9.8)
    assert [e.edge_signal for e in edges(edge_config(**dict(FORCE, force_settle_s=0.0)), pressed)] == ['force']
    found = edges(edge_config(**FORCE), pressed)
    assert len(found) == 1 and found[0].first_sample.position[0] > X_EDGE


def test_gap_rebuilds_the_reference():
    """공백 뒤에는 기준 구간을 다시 쌓는다. 공백 전의 Fz(누르던 값)와 비교해 공백 직후에 확정하지 않는다.

    꺾임이 공백 안에서 끝나면 힘으로는 모서리를 놓친다(좌표가 틀린 EDGE 보다 낫다). 그 방향은 다시 민다(절차서 4번).
    """
    found = edges(edge_config(**FORCE), slide(gap=(7.9, 0.3)))          # 모서리(8.0 s)를 덮는 공백
    assert all(e.first_sample.pose_stamp >= 8.2 + 0.2 for e in found)


def test_off_by_default():
    assert not edge_config().by_force
    assert edge_config(**FORCE).by_force


def test_config_rejects_bad_force_values():
    with pytest.raises(ValueError):
        edge_config(force_drop_n=1.0, force_window_s=0.5)                  # 셋 중 하나 빠짐
    with pytest.raises(ValueError):
        edge_config(**dict(FORCE, force_drop_n=0.0))
    with pytest.raises(ValueError):
        edge_config(**dict(FORCE, force_lag_s=0.5))                       # lag >= window
    with pytest.raises(ValueError):
        edge_config(**dict(FORCE, force_settle_s=-1.0))


def late_start(delay_s=1.2, seconds=14.0):
    """재출발처럼 delay_s 동안 제자리에 있다가 출발한다. 출발 0.5 s 뒤 0.3 s 동안 Fz 가 2.5 N 빠졌다 돌아온다.

    9/22 실기 1553: 재출발 0.66 s 뒤, 옆 2 mm 에서 가짜 EDGE. 모서리는 출발점에서 40 mm 뒤다.
    """
    samples = []
    for i in range(int(seconds / DT)):
        t = i * DT
        moving = max(0.0, t - delay_s)
        x = X0 + V_SLIDE * moving
        fz = F_PRESS
        since = t - delay_s - 0.5
        if 0.0 <= since < 0.3:
            fz = F_PRESS - 2.5
        past = (x - X_EDGE) / V_SLIDE
        z = Z_TOP
        if past > 0:
            fz = F_PRESS + (F_AIR - F_PRESS) * min(past / 0.4, 1.0)
            z = Z_TOP - 0.0003 * past
        samples.append(Sample(
            sample_id=i + 1, pose_stamp=t, force_stamp=t + 0.004, position=(x, -0.18606, z),
            force=(-5.0, 0.8, fz + noise(i)), motion_id=7, operation=OP_SLIDE))
    return samples


def test_late_departure_dip_is_a_false_edge_without_move_settle():
    """첫 샘플 기준 대기(1.5 s)만으로는 늦게 출발한 밀기의 출발 흔들림을 못 거른다 (#154)."""
    found = edges(edge_config(**FORCE), late_start())
    assert found and found[0].first_sample.position[0] - X0 < 5 * MM, '출발 직후(모서리 40 mm 앞)에서 난다'


def test_move_settle_waits_from_the_real_departure():
    """판정이 켜진 시점(실제 옆 출발)부터도 기다리면 출발 흔들림을 거르고 모서리만 잡는다 (#154)."""
    found = edges(edge_config(**dict(FORCE, force_settle_move_s=1.0)), late_start())
    assert len(found) == 1
    assert 0.0 <= found[0].first_sample.position[0] - X_EDGE < 1.5 * MM


def test_move_settle_keeps_an_on_time_slide_the_same():
    """정상 출발(바로 움직임)이면 결과가 같다."""
    base = edges(edge_config(**FORCE), slide())
    with_move = edges(edge_config(**dict(FORCE, force_settle_move_s=1.0)), slide())
    assert [e.first_sample.sample_id for e in base] == [e.first_sample.sample_id for e in with_move]


def test_config_rejects_negative_move_settle():
    with pytest.raises(ValueError):
        edge_config(**dict(FORCE, force_settle_move_s=-0.1))
