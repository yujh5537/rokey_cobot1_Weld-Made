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

    def __init__(self, slope_x=0.0, wall_x=None, noise_n=0.0, seed=0):
        self.slope_x, self.wall_x, self.noise_n = slope_x, wall_x, noise_n
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
        if self.wall_x is not None and x >= self.wall_x and surface is not None and z < surface + 0.005:
            fx -= 30000.0 * (x - self.wall_x + 0.0001)
        if self.noise_n:
            fz += self.rng.uniform(-self.noise_n, self.noise_n)
        return (fx, fy, fz)


class FakeIO:
    def __init__(self, box, start):
        self.box, self.pos = box, tuple(start)
        self.last_horizontal = (0.0, 0.0, 0.0)
        self.moves = 0
        self.lines = []

    def position(self):
        return self.pos

    def force(self):
        return self.box.force(self.pos, self.last_horizontal)

    def move_rel(self, d):
        self.moves += 1
        if abs(d[0]) > 1e-12 or abs(d[1]) > 1e-12:
            self.last_horizontal = tuple(d)
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
