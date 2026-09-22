"""step_slide 순수 모듈 시험. 가짜 로봇이 윗면이 평평한 상자를 흉내 낸다 (rclpy 없음)."""
import math
import random

import pytest

from robot_manager import step_slide
from robot_manager.step_slide import StepFailure, StepParams

K = 14000.0          # 윗면 강성 [N/m]. 9/22 실기 0.1 mm 당 약 1.4 N (t25_all.sh)
TOP_Z = 0.1753       # 윗면 z [m]
HALF = 0.040         # 80 mm 큐브 반폭 [m]
BIAS = (0.4, 1.3, 2.0)   # 무접촉 외력 치우침 [N]


def params(**changes):
    base = dict(coarse_m=0.0005, fine_m=0.0001, z_step_m=0.00005, press_step_m=0.0001,
                press_max_m=0.003, lift_m=0.001, nudge_m=0.001, release_n=1.5, follow_lo_n=3.0,
                follow_hi_n=7.0, max_force_n=12.0, side_hit_n=8.0, drop_m=0.0005, z_tol_m=0.001,
                max_slope_deg=5.0, max_slide_m=0.060)
    base.update(changes)
    return StepParams(**base)


class Box:
    """(0, 0) 중심, 반폭 HALF 인 상자. 윗면 기울기 slope_x [rad], 벽 (x 위치, 높이) 선택."""

    def __init__(self, slope_x=0.0, wall_x=None, noise_n=0.0, seed=0, corner_n=0.0, corner_w=0.003):
        self.slope_x, self.wall_x, self.noise_n = slope_x, wall_x, noise_n
        self.corner_n, self.corner_w = corner_n, corner_w
        self.rng = random.Random(seed)

    def top(self, x, y):
        if abs(x) > HALF or abs(y) > HALF:
            return None
        return TOP_Z + math.tan(self.slope_x) * x

    def force(self, pos, last_move):
        x, y, z = pos
        fx, fy, fz = BIAS
        surface = self.top(x, y)
        if surface is not None and z < surface:
            press = K * (surface - z)
            fz += press
            # 마찰: 마지막 수평 이동의 반대 방향
            h = math.hypot(last_move[0], last_move[1])
            if h > 0:
                fx -= 0.3 * press * last_move[0] / h
                fy -= 0.3 * press * last_move[1] / h
        past = max(abs(x), abs(y)) - HALF
        if surface is None and 0.0 < past < self.corner_w and z < TOP_Z:
            fz += self.corner_n      # 둥근 팁이 모서리 각에 걸친 힘. 더 눌러도 늘지 않는다 (9/22 motion 3104)
        if self.wall_x is not None and x >= self.wall_x and surface is not None and z < surface + 0.005:
            fx -= 30000.0 * (x - self.wall_x + 0.0001)
        if self.noise_n:
            fz += self.rng.uniform(-self.noise_n, self.noise_n)
        return (fx, fy, fz)


class FakeIO:
    def __init__(self, box, start, drift_n=0.0, drift_after=3):
        self.box, self.pos = box, tuple(start)
        self.drift_n, self.drift_after = drift_n, drift_after   # 이동 drift_after 번 뒤 Fz 치우침이 바뀜
        self.last_horizontal = (0.0, 0.0, 0.0)
        self.moves = 0
        self.horizontal = []      # (출발 위치, 이동량)
        self.reads = []           # 힘을 읽은 (위치, 마지막 수평 이동)
        self.lines = []

    def position(self):
        return self.pos

    def force(self):
        f = self.box.force(self.pos, self.last_horizontal)
        self.reads.append((self.pos, self.last_horizontal))
        if self.moves > self.drift_after:
            f = (f[0], f[1], f[2] + self.drift_n)
        return f

    def move_rel(self, d):
        self.moves += 1
        if abs(d[0]) > 1e-12 or abs(d[1]) > 1e-12:
            self.last_horizontal = tuple(d)
            self.horizontal.append((self.pos, tuple(d)))
        self.pos = tuple(a + b for a, b in zip(self.pos, d))

    def log(self, text):
        self.lines.append(text)


def pressed_start(x=0.0, y=0.0, depth=0.0005):
    return (x, y, TOP_Z - depth)     # DESCEND 가 접촉으로 멈춘 자리 (약 7 N 눌림)


@pytest.mark.parametrize('direction, axis, sign', [
    ((1.0, 0.0, 0.0), 0, 1), ((-1.0, 0.0, 0.0), 0, -1), ((0.0, 1.0, 0.0), 1, 1), ((0.0, -1.0, 0.0), 1, -1)])
def test_finds_each_edge_within_a_fine_step(direction, axis, sign):
    io = FakeIO(Box(), pressed_start())
    edge = step_slide.run(io, direction, params())
    assert sign * edge.position[axis] == pytest.approx(HALF, abs=0.00015)
    assert edge.position[2] == pytest.approx(TOP_Z, abs=0.0006)     # 접촉 높이 (누른 깊이 포함)
    assert edge.z_drop_m >= 0.0005 - 0.00005 - 1e-9                 # drop_m 만큼 내려가 봤다
    assert io.pos[2] > edge.lost_z                                  # 끝나면 든다


def test_starting_above_the_surface_presses_down_first():
    io = FakeIO(Box(), (0.0, 0.0, TOP_Z + 0.001))     # 방향 전환 뒤 1 mm 떠서 시작
    edge = step_slide.run(io, (1.0, 0.0, 0.0), params())
    assert edge.position[0] == pytest.approx(HALF, abs=0.00015)


@pytest.mark.parametrize('corner_n', [1.8, 2.6])
def test_weak_force_on_the_corner_does_not_drag_the_tip_down(corner_n):
    """9/22 motion 3104: 모서리를 넘은 뒤 1.6~1.9 N 이 남아 release 1.5 를 넘었다. 최근 접촉 높이가 따라
    내려가 모서리를 2.9 mm 타고 내려갔고, drop_m 만 들고 물러나다 옆면에 걸려 다시 누르지 못했다."""
    io = FakeIO(Box(corner_n=corner_n), pressed_start())
    edge = step_slide.run(io, (-1.0, 0.0, 0.0), params())
    assert edge.position[0] == pytest.approx(-HALF, abs=0.00015)
    assert min(pos[2] for pos, _ in io.horizontal) > TOP_Z - 0.0006 - 1e-9   # 흘러내리지 않았다
    backing = [(pos, d) for pos, d in io.horizontal if d[0] > 0.0]            # 긁는 방향(−x) 반대로 물러남
    assert backing and all(pos[2] > TOP_Z for pos, _ in backing)             # 윗면 위로 든 채 물러났다


def test_f0_drift_during_the_slide_is_removed_before_refining():
    """긁기 시작 뒤 Fz 치우침이 1.5 N 올라 모서리 걸침 1.8 N 이 3.3 N 으로 읽혀도 (follow_lo 3 N 넘음)
    높이 기준 덕분에 흘러내리지 않고, 다듬기 전에 F0 를 다시 재서 모서리를 제자리에서 잡는다."""
    io = FakeIO(Box(corner_n=1.8), pressed_start(), drift_n=1.5, drift_after=40)   # 긁기 중간부터
    edge = step_slide.run(io, (1.0, 0.0, 0.0), params())
    assert edge.position[0] == pytest.approx(HALF, abs=0.00015)
    assert min(pos[2] for pos, _ in io.horizontal) > TOP_Z - 0.0006 - 1e-9
    assert any('다듬기 1차' in line for line in io.lines)


@pytest.mark.parametrize('direction', [(1.0, 0.0, 0.0), (0.0, -1.0, 0.0)])
def test_refine_reads_force_after_moving_in_the_slide_direction(direction):
    """다듬기에서 F0 · 누름을 읽을 때 마지막 수평 이동이 긁는 방향이다 (9/21: 방향만으로 Fz 1.9 N 차이)."""
    io = FakeIO(Box(corner_n=1.8), pressed_start())
    step_slide.run(io, direction, params())
    for pos, last in io.reads:
        assert last[0] * direction[0] + last[1] * direction[1] > 0.0


def test_no_surface_within_press_max_is_no_contact():
    io = FakeIO(Box(), (0.0, 0.0, TOP_Z + 0.005))
    with pytest.raises(StepFailure) as err:
        step_slide.run(io, (1.0, 0.0, 0.0), params())
    assert err.value.kind == step_slide.NO_CONTACT


def test_force_noise_is_not_mistaken_for_an_edge():
    """프로토타입 로그: 누른 깊이를 고정하면 누름이 1~7 N 을 오가 중간에 끝으로 오판했다."""
    io = FakeIO(Box(noise_n=1.2, seed=3), pressed_start())
    edge = step_slide.run(io, (1.0, 0.0, 0.0), params())
    assert edge.position[0] == pytest.approx(HALF, abs=0.0003)


def test_gently_tilted_top_is_followed():
    io = FakeIO(Box(slope_x=math.radians(2.0)), pressed_start())
    edge = step_slide.run(io, (1.0, 0.0, 0.0), params())
    assert edge.position[0] == pytest.approx(HALF, abs=0.00015)


def test_steep_top_is_a_z_drift_failure():
    io = FakeIO(Box(slope_x=math.radians(-10.0)), pressed_start())
    with pytest.raises(StepFailure) as err:
        step_slide.run(io, (1.0, 0.0, 0.0), params())
    assert err.value.kind == step_slide.Z_DRIFT


def test_wall_on_the_top_is_a_side_hit_and_backs_off():
    io = FakeIO(Box(wall_x=0.010), pressed_start())
    with pytest.raises(StepFailure) as err:
        step_slide.run(io, (1.0, 0.0, 0.0), params())
    assert err.value.kind == step_slide.SIDE_HIT
    assert io.pos[0] < 0.010 and io.pos[2] > TOP_Z      # 벽에서 물러나 들었다


def test_no_edge_within_max_slide():
    io = FakeIO(Box(), pressed_start())
    with pytest.raises(StepFailure) as err:
        step_slide.run(io, (1.0, 0.0, 0.0), params(max_slide_m=0.020))
    assert err.value.kind == step_slide.NO_EDGE
    assert io.pos[2] > TOP_Z


def test_over_force_lifts_and_fails():
    io = FakeIO(Box(), pressed_start(depth=0.0005))     # 들면 윗면 0.5 mm 위 → 2 mm 내려가면 1.5 mm 눌림(21 N)
    with pytest.raises(StepFailure) as err:
        step_slide.run(io, (1.0, 0.0, 0.0), params(press_step_m=0.002, press_max_m=0.003))
    assert err.value.kind == step_slide.OVER_FORCE
    assert io.pos[2] > TOP_Z - 0.001


@pytest.mark.parametrize('change', [
    dict(release_n=4.0),            # release ≥ follow_lo
    dict(follow_hi_n=13.0),         # follow_hi ≥ max_force
    dict(fine_m=0.001),             # fine > coarse
    dict(z_step_m=0.001),           # z_step > drop
    dict(coarse_m=0.0),
])
def test_invalid_params_are_rejected(change):
    with pytest.raises(ValueError):
        params(**change).validate()
