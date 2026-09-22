"""SLIDE 스텝 모드: 멈춘 상태에서 힘을 읽으며 z 를 맞춰 윗면을 긁고 모서리를 확정한다 (rclpy 없음).

9/17 `tactile_probe/edge_scan.py` 의 `slide_top` 을 옮겼다. 같은 M0609 로 원점 + ±X · ±Y 를 한 번에
끝낸 방식이다 (원본 `~/tactile_probe_logs/scan_20260917_171305.csv`).

왜 멈춰서 읽나: 연속 힘 제어 SLIDE 는 움직이는 중의 외력 추정값이 방향마다 1.5~8.6 N 치우쳐(9/22 T25)
누름을 믿을 수 없었다. 여기서는 위치 제어로 한 스텝 가고, 멈춘 뒤 여러 샘플을 평균낸 ΔFz 만 본다.

순서
  0. 기준 힘: lift 만큼 들고, 긁을 방향으로 nudge 만큼 움직여 멈춘 뒤 F0 (마지막 이동 방향을 긁기와 같게.
     9/21 실기 1-1절: 멈춘 상태에서도 마지막 이동 방향만으로 Fz 가 1.9 N 달라진다)
  1. 누르기: press_step 씩 내려가 ΔFz ≥ release_n (처음 닿음). 한계 = 시작 z − press_max_m
  2. 긁기: coarse 만큼 이동 → 누름 맞추기(keep_contact). ΔFz 를 [follow_lo, follow_hi] 로 유지하도록 z 를
     z_step 씩 조절한다. 힘이 빠지면 최근 접촉 높이(중앙값)보다 drop_m 아래까지 내려가 보고,
     그래도 follow_lo 미만일 때만 접촉 소실 후보로 본다 → 흔들림을 모서리로 오판하지 않는다.
     평평한 윗면이면 drop_m 아래에서는 follow_lo 를 훨씬 넘는다(0.5 mm ≈ 7 N). 모서리를 넘으면 반지름 약
     2 mm 팁이 모서리 각에 걸려 1~2 N 이 남는데(9/22 18:0x 위치 기록), 이 값은 F0 치우침(±0.6 N)만큼
     release_n 을 넘나든다. 그래서 소실 기준은 follow_lo 이고, 최근 접촉 높이는 follow_lo 이상으로 누른
     자리만 쌓는다(약한 걸침이 기준 높이를 끌어내리면 모서리를 타고 흘러내린다)
  3. 다듬기: 접촉 높이 + lift 로 들고, 마지막으로 제대로 누른 자리 뒤에서 긁는 방향으로 nudge 만큼 들어와
     공중에서 F0 를 다시 잰 뒤 다시 누르고 fine 씩 전진해 소실 지점을 다시 찾는다 → 모서리
  4. 끝나면 lift 만큼 든다 (팁을 모서리에 걸쳐 두지 않는다)

실패하면 가능한 한 면에서 떨어진 뒤 StepFailure 를 낸다. 단위: m · N.
"""
import math
from dataclasses import dataclass
from statistics import median

# StepFailure.kind
NO_EDGE = 'no_edge'            # max_slide 까지 소실 없음
NO_CONTACT = 'no_contact'      # 시작 자리에서 누르지 못함
OVER_FORCE = 'over_force'      # |ΔF| > max_force_n
SIDE_HIT = 'side_hit'          # 수평 |ΔF| > side_hit_n (턱 · 걸림)
Z_DRIFT = 'z_drift'            # 긁는 동안 누르는 높이가 크게 바뀜 (탐침 밀림 · 물체 이동 · 기울기)
UNSTABLE = 'unstable'          # 누름을 맞추지 못함 / 다듬기 실패

UP = (0.0, 0.0, 1.0)


class StepFailure(RuntimeError):
    def __init__(self, kind, message):
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True)
class StepParams:
    coarse_m: float          # 긁기 스텝
    fine_m: float            # 다듬기 스텝 (수평)
    z_step_m: float          # 누름 맞추기 z 스텝
    press_step_m: float      # 처음 누를 때 내려가는 스텝
    press_max_m: float       # 처음 누를 때 시작 z 에서 내려갈 수 있는 최대 거리
    lift_m: float            # 기준 힘을 잴 때 · 끝났을 때 드는 높이
    nudge_m: float           # 기준 힘 전에 긁을 방향으로 움직이는 거리
    release_n: float         # 처음 누를 때 이 이상이면 닿음 (소실 기준은 follow_lo_n)
    follow_lo_n: float       # 누름 하한 (이보다 약하면 조금 더 누름)
    follow_hi_n: float       # 누름 상한 (이보다 세면 조금 올라감)
    max_force_n: float       # |ΔF| 가 이보다 크면 들고 중단
    side_hit_n: float        # 수평 |ΔF| 가 이보다 크면 물러나고 중단
    drop_m: float            # 힘이 빠졌을 때 최근 접촉 높이보다 이만큼 아래까지 내려가 봄
    z_tol_m: float           # 긁는 동안 누르는 높이 변화 한계의 최솟값
    max_slope_deg: float     # 높이 변화 한계 = max(z_tol_m, 긁은 거리 × tan(이 각도))
    max_slide_m: float       # 한 방향 최대 긁기 거리

    def validate(self):
        for name in ('coarse_m', 'fine_m', 'z_step_m', 'press_step_m', 'press_max_m', 'lift_m',
                     'release_n', 'drop_m', 'z_tol_m', 'max_slide_m'):
            value = getattr(self, name)
            if not (math.isfinite(value) and value > 0.0):
                raise ValueError(f'{name} = {value}: 0 보다 커야 한다')
        if self.nudge_m < 0.0:
            raise ValueError('nudge_m 은 0 이상이어야 한다')
        if not (0.0 < self.release_n < self.follow_lo_n < self.follow_hi_n < self.max_force_n):
            raise ValueError('0 < release_n < follow_lo_n < follow_hi_n < max_force_n 이어야 한다')
        if not (0.0 < self.side_hit_n < self.max_force_n):
            raise ValueError('0 < side_hit_n < max_force_n 이어야 한다')
        if self.fine_m > self.coarse_m:
            raise ValueError('fine_m 은 coarse_m 보다 클 수 없다')
        if self.z_step_m > self.drop_m:
            raise ValueError('z_step_m 은 drop_m 보다 클 수 없다 (내려가 볼 칸이 없다)')


@dataclass(frozen=True)
class StepEdge:
    position: tuple          # 모서리: 소실 지점의 (x, y) + 최근 접촉 높이 중앙값 z [m]
    lost_z: float            # 소실을 확인한 순간의 실제 z [m]
    z_drop_m: float          # 최근 접촉 높이 중앙값 − lost_z (소실을 확인하려고 더 내려간 깊이)
    force_delta: tuple       # 소실 판정 순간의 ΔF (Fx, Fy, Fz) [N]
    travelled_m: float       # 거친 긁기로 간 거리


class StepIO:
    """robot_manager 가 채운다. 시험에서는 가짜로 바꾼다.

    position() → (x, y, z) [m]. 마지막 이동이 끝난 뒤의 값
    force() → (Fx, Fy, Fz) [N]. 멈춘 상태에서 새로 받은 샘플 여러 개의 평균
    move_rel((dx, dy, dz)) → 위치 제어로 이동하고 멈출 때까지 기다린다
    log(text)
    """


def _add(a, b, k=1.0):
    return tuple(x + k * y for x, y in zip(a, b))


def run(io, direction, p: StepParams):
    """direction = 수평 단위 벡터 (x, y, 0). 모서리를 StepEdge 로 돌려준다. 실패하면 StepFailure."""
    p.validate()
    u = tuple(float(v) for v in direction)
    start = io.position()

    # 0. 기준 힘: 떠 있는 상태, 마지막 이동 = 긁는 방향
    io.move_rel((0.0, 0.0, p.lift_m))
    if p.nudge_m > 0.0:
        io.move_rel(_add((0.0, 0.0, 0.0), u, p.nudge_m))
    base = io.force()
    io.log(f'스텝 긁기: 기준 힘 F0 = ({base[0]:.2f}, {base[1]:.2f}, {base[2]:.2f}) N')
    cur = {'base': base}      # 다듬기 직전에 다시 잰다

    def lift_and_fail(kind, message, back=False):
        if back:
            io.move_rel(_add((0.0, 0.0, 0.0), u, -p.lift_m))
        io.move_rel((0.0, 0.0, p.lift_m))
        raise StepFailure(kind, message)

    def read():
        raw = io.force()
        df = tuple(r - b for r, b in zip(raw, cur['base']))
        # 수평 힘을 먼저 본다: 무언가에 걸렸으면 들기 전에 옆으로 물러나야 한다 (걸린 채 들면 끌고 올라간다)
        side = math.hypot(df[0], df[1])
        if side > p.side_hit_n:
            lift_and_fail(SIDE_HIT, f'수평 힘 {side:.1f} N > {p.side_hit_n:.1f} N (턱 · 걸림). 물러나고 중단',
                          back=True)
        total = math.sqrt(sum(v * v for v in df))
        if total > p.max_force_n:
            lift_and_fail(OVER_FORCE, f'힘 {total:.1f} N > {p.max_force_n:.1f} N. 들고 중단')
        return df

    # 1. 누르기
    floor_z = start[2] - p.press_max_m
    df = read()
    while df[2] < p.release_n:
        if io.position()[2] - p.press_step_m < floor_z - 1e-9:
            lift_and_fail(NO_CONTACT, f'시작 자리에서 {p.press_max_m * 1000:.1f} mm 내려가도 누르지 못했다')
        io.move_rel((0.0, 0.0, -p.press_step_m))
        df = read()
    ref_z = io.position()[2]
    hist = [ref_z]
    state = {'df': df, 'good': io.position()}

    def keep_contact():
        """ΔFz 를 [follow_lo, follow_hi] 로 맞춘다. 닿아 있으면 True,
        최근 접촉 높이 − drop_m 까지 내려가도 follow_lo 미만이면 False."""
        f = read()
        for _ in range(200):
            floor = median(hist[-10:]) - p.drop_m
            can_go_down = io.position()[2] - p.z_step_m >= floor - 1e-9
            if f[2] > p.follow_hi_n:
                io.move_rel((0.0, 0.0, p.z_step_m))
            elif f[2] >= p.follow_lo_n:
                hist.append(io.position()[2])
                state['df'] = f
                state['good'] = io.position()
                return True
            elif can_go_down:
                io.move_rel((0.0, 0.0, -p.z_step_m))
            else:
                state['df'] = f
                return False
            f = read()
        lift_and_fail(UNSTABLE, '누르는 힘을 맞추지 못했다 (힘이 계속 출렁임)')

    if not keep_contact():
        lift_and_fail(NO_CONTACT, '누른 직후 접촉을 유지하지 못했다')

    # 2. 긁기
    travelled = 0.0
    while True:
        if travelled >= p.max_slide_m - 1e-9:
            lift_and_fail(NO_EDGE, f'{p.max_slide_m * 1000:.0f} mm 긁어도 접촉 소실이 없었다')
        io.move_rel(_add((0.0, 0.0, 0.0), u, p.coarse_m))
        travelled += p.coarse_m
        if not keep_contact():
            break
        dz = io.position()[2] - ref_z
        z_lim = max(p.z_tol_m, travelled * math.tan(math.radians(p.max_slope_deg)))
        if abs(dz) > z_lim:
            lift_and_fail(Z_DRIFT, f'{travelled * 1000:.1f} mm 긁는 동안 누르는 높이가 {dz * 1000:+.2f} mm '
                                   f'바뀜 (한계 ±{z_lim * 1000:.2f} mm). 탐침 밀림 · 물체 이동 · 윗면 기울기 확인',
                          back=True)
    io.log(f'스텝 긁기: {travelled * 1000:.1f} mm 에서 접촉 소실 후보 → 가는 스텝으로 다시')

    # 3. 다듬기 (못 누르면 coarse 씩 더 뒤에서 다시, 최대 7 번 = 4.5 mm)
    #   a. 접촉 높이 + lift 로 든다. drop_m 만 들면 모서리 아래로 내려간 팁이 윗면보다 낮아
    #      돌아가는 길에 옆면에 걸린다 (9/22 motion 3104: Fx −3 N, 세 번 다 못 누름)
    #   b. 마지막으로 follow_lo 이상 누른 자리(윗면이 확실한 곳)보다 nudge 만큼 뒤로 갔다가 nudge 만큼 전진한다.
    #      마지막 수평 이동을 긁는 방향과 같게 둬야 Fz 읽기 조건이 F0 · 긁기와 같다 (9/21: 방향만으로 1.9 N 차이)
    #   c. 공중에서 F0 를 다시 잰다. 1 분 가까이 긁는 동안 외력 추정값이 흘러 실행마다 ±0.6 N 달랐다
    #   d. 접촉 높이까지 내려가 누름을 맞춘다. 못 누르면(돌아온 자리도 모서리 밖) coarse 만큼 더 뒤에서 다시
    lost = io.position()
    good = state['good']
    ref = median(hist[-10:])
    # 마지막 누른 자리는 모서리에서 한 스텝 안이라 걸침이 섞여 있다(9/22 18:40: 4방향 중 3방향이 거기서 못 누르고
    # 한 스텝 더 뒤에서 성공). 처음부터 한 스텝 더 뒤에서 시작한다
    for attempt in range(1, 8):
        back = p.coarse_m * attempt + p.nudge_m
        io.move_rel((0.0, 0.0, ref + p.lift_m - io.position()[2]))
        here = io.position()
        io.move_rel((good[0] - back * u[0] - here[0], good[1] - back * u[1] - here[1], 0.0))
        if p.nudge_m > 0.0:
            io.move_rel(_add((0.0, 0.0, 0.0), u, p.nudge_m))
        old = cur['base']
        cur['base'] = io.force()
        io.log(f'스텝 긁기 다듬기 {attempt}차: 소실 지점보다 '
               f'{sum((a - b) * c for a, b, c in zip(lost, io.position(), u)) * 1000:.1f} mm 뒤로 돌아옴, '
               f'F0z {old[2]:.2f} → {cur["base"][2]:.2f} N')
        io.move_rel((0.0, 0.0, ref - io.position()[2]))
        if keep_contact():
            break
    else:
        lift_and_fail(UNSTABLE, '마지막으로 누른 자리로 돌아왔는데 다시 누르지 못했다')
    span = sum((a - b) * c for a, b, c in zip(lost, io.position(), u))
    for _ in range(int(math.ceil((span + 4 * p.coarse_m) / p.fine_m))):
        io.move_rel(_add((0.0, 0.0, 0.0), u, p.fine_m))
        if not keep_contact():
            q = io.position()
            z_ref = median(hist[-10:])
            edge = StepEdge(position=(q[0], q[1], z_ref), lost_z=q[2], z_drop_m=max(0.0, z_ref - q[2]),
                            force_delta=tuple(state['df']), travelled_m=travelled)
            io.move_rel((0.0, 0.0, p.lift_m))
            return edge
    lift_and_fail(UNSTABLE, '가는 스텝으로 모서리를 다시 찾지 못했다')
