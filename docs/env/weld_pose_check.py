#!/usr/bin/env python3
"""용접 자세 도달성 점검 (phase 2, 2026-09-23 M1). 사람이 실기 앞에서 돌린다.

`docs/phase2/measurements-20260923.md` M1 의 16 자세(기울임 45° · 스탠드오프 3 mm)를 차례로 간다.
자세마다 ① 그 자세 **위 --lift mm** 로 movel → ② Enter 를 누르면 자세로 내려감 → ③ posx · posj 를 읽어 CSV 에 남김
→ ④ Enter 로 다시 위로. 어느 단계든 `s` 를 치면 그 자세를 건너뛰고, `q` 면 끝낸다(로봇은 그 자리에 선다).

    sod && cd ~/ws_cobot_pjt
    python3 docs/env/weld_pose_check.py --dry-run                 # 목록만 출력. ROS 없이 된다
    python3 docs/env/weld_pose_check.py                            # Virtual(에뮬레이터) — 먼저 여기서 오류를 잡는다
    python3 docs/env/weld_pose_check.py --real-ok --vel 10         # 실기. 입회자 비상정지 대기, 사람이 돌린다(CLAUDE.md 규칙 1)

- 좌표 · 자세는 `scratchpad/weld_poses.py`(병후) 계산값. 큐브 좌표가 바뀌었으면 --cube 로 다시 준다(x- x+ y- y+ z_top z_support, mm).
- `move_line` 은 SYNC 로 부른다(끝날 때까지 서비스가 기다린다). 그래서 --timeout 을 넉넉히 둔다.
- 로봇이 자세를 못 만들면(관절 한계 · 특이점) 서비스가 success=false 를 돌려준다. 그 줄을 CSV 에 reach=0 으로 남긴다.
- 다른 조회 프로그램(measure_idle_force.py · robot_manager)과 같이 돌리지 않는다(서비스 동시 호출 시 드라이버 정지).
"""
import argparse
import csv
import math
import os
import sys
import time

PREFIX = '/dsr01/dsr_controller2/'
ARRIVE_TOL_MM = 1.0   # 지령 ↔ 실측 posx 위치 차. 이보다 크면 도달 실패로 본다

HEADER = ['time', 'line', 'where', 'x_mm', 'y_mm', 'z_mm', 'a_deg', 'b_deg', 'c_deg', 'reach',
          'posx_read', 'posj_read', 'clearance_mm', 'note']
DEFAULT_CUBE = (378.48, 462.03, -198.75, -114.60, 178.003, 97.006)   # 9/22 스텝 모드 모서리 · 윗면 · 작업대+테이프 2 (units-frames v0.1.18)


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--cube', type=float, nargs=6, default=DEFAULT_CUBE, metavar='MM',
                   help='x- x+ y- y+ z_top z_support [mm, Base]')
    p.add_argument('--standoff', type=float, default=3.0, help='스탠드오프 [mm]')
    p.add_argument('--tilt', type=float, default=45.0, help='기울임 [deg]. 막히면 30 으로 낮춰 다시')
    p.add_argument('--bottom-margin', type=float, default=5.0, help='세로선 끝 = 지지면 + 이 값 [mm]')
    p.add_argument('--lift', type=float, default=30.0, help='자세 위로 띄우는 높이 [mm]')
    p.add_argument('--safe-z', type=float, default=None,
                   help='자세 사이를 옮길 높이 [mm, Base]. 기본 = 큐브 윗면 + --lift.\n                        세로선(L4~L7)은 목표 위 30 mm 가 큐브 옆구리라 이 높이 없이 옮기면 큐브를 통과한다')
    p.add_argument('--vel', type=float, default=20.0, help='movel 속도 [mm/s]. 실기는 10')
    p.add_argument('--only', default='', help='선 이름 목록 (예: L0,L4). 비면 전부')
    p.add_argument('--file', default='weld_pose_check.csv')
    p.add_argument('--timeout', type=float, default=60.0, help='movel SYNC 대기 [s]')
    p.add_argument('--dry-run', action='store_true', help='자세 목록만 출력 (ROS 없이)')
    p.add_argument('--real-ok', action='store_true', help='실기 허용. 사람이 로봇 앞에 있을 때만')
    return p.parse_args(argv)


# ---------- 순수 계산 (weld-motion.md 2 · 3절) ----------
def norm(v):
    n = math.sqrt(sum(c * c for c in v))
    return tuple(c / n for c in v)


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def mat_to_quat(x, y, z):
    m = [[x[0], y[0], z[0]], [x[1], y[1], z[1]], [x[2], y[2], z[2]]]
    t = m[0][0] + m[1][1] + m[2][2]
    if t > 0:
        s = math.sqrt(t + 1) * 2
        return ((m[2][1] - m[1][2]) / s, (m[0][2] - m[2][0]) / s, (m[1][0] - m[0][1]) / s, s / 4)
    if m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1 + m[0][0] - m[1][1] - m[2][2]) * 2
        return (s / 4, (m[0][1] + m[1][0]) / s, (m[0][2] + m[2][0]) / s, (m[2][1] - m[1][2]) / s)
    if m[1][1] > m[2][2]:
        s = math.sqrt(1 + m[1][1] - m[0][0] - m[2][2]) * 2
        return ((m[0][1] + m[1][0]) / s, s / 4, (m[1][2] + m[2][1]) / s, (m[0][2] - m[2][0]) / s)
    s = math.sqrt(1 + m[2][2] - m[0][0] - m[1][1]) * 2
    return ((m[0][2] + m[2][0]) / s, (m[1][2] + m[2][1]) / s, s / 4, (m[1][0] - m[0][1]) / s)


def quaternion_to_zyz_deg(x, y, z, w):
    """robot_manager/motions.py 와 같은 식 (두산 ZYZ 고유 회전)."""
    half_b = math.atan2(math.hypot(x, y), math.hypot(z, w))
    sum_half = math.atan2(z, w)
    if math.isclose(math.hypot(x, y), 0.0, abs_tol=1e-9):
        a, c = 2.0 * sum_half, 0.0
    else:
        diff_half = math.atan2(-x, y)
        a, c = sum_half + diff_half, sum_half - diff_half
    wrap = lambda d: (d + 180.0) % 360.0 - 180.0
    return wrap(math.degrees(a)), math.degrees(2.0 * half_b), wrap(math.degrees(c))


def weld_poses(cube, standoff, tilt_deg, bottom_margin):
    """[(선, 위치, [x, y, z, a, b, c]), ...] — 16 자세."""
    x_neg, x_pos, y_neg, y_pos, z_top, z_sup = cube
    r2 = math.sqrt(0.5)
    v = [(x_neg, y_neg, z_top), (x_pos, y_neg, z_top), (x_pos, y_pos, z_top), (x_neg, y_pos, z_top)]
    z_bot = z_sup + bottom_margin
    lines = [
        ('L0', v[0], v[1], (0, -1, 0)), ('L1', v[1], v[2], (1, 0, 0)),
        ('L2', v[2], v[3], (0, 1, 0)), ('L3', v[3], v[0], (-1, 0, 0)),
        ('L4', v[0], (x_neg, y_neg, z_bot), (-r2, -r2, 0)), ('L5', v[1], (x_pos, y_neg, z_bot), (r2, -r2, 0)),
        ('L6', v[2], (x_pos, y_pos, z_bot), (r2, r2, 0)), ('L7', v[3], (x_neg, y_pos, z_bot), (-r2, r2, 0)),
    ]
    th = math.radians(tilt_deg)
    out = []
    for name, s, e, n_out in lines:
        t = norm(tuple(ei - si for si, ei in zip(s, e)))
        d = tuple(-(math.cos(th) * (0, 0, 1)[i] + math.sin(th) * n_out[i]) for i in range(3))
        x_tool = norm(cross(t, d))
        y_tool = cross(d, x_tool)
        a, b, c = quaternion_to_zyz_deg(*mat_to_quat(x_tool, y_tool, d))
        off = tuple(-standoff * ci for ci in d)
        for where, pt in (('start' if name < 'L4' else 'top', s), ('end' if name < 'L4' else 'bottom', e)):
            p = tuple(pi + oi for pi, oi in zip(pt, off))
            out.append((name, where, [round(p[0], 2), round(p[1], 2), round(p[2], 2), round(a, 2), round(b, 2), round(c, 2)]))
    return out


# ---------- ROS ----------
def run(args):
    import rclpy
    from dsr_msgs2.srv import GetCurrentPosj, GetCurrentPosx, GetRobotMode, MoveLine
    rclpy.init()
    node = rclpy.create_node('weld_pose_check')
    clients = {n: node.create_client(t, PREFIX + s) for n, (t, s) in {
        'posx': (GetCurrentPosx, 'aux_control/get_current_posx'),
        'posj': (GetCurrentPosj, 'aux_control/get_current_posj'),
        'mode': (GetRobotMode, 'system/get_robot_mode'),
        'movel': (MoveLine, 'motion/move_line')}.items()}

    def call(name, req, timeout):
        c = clients[name]
        if not c.wait_for_service(timeout_sec=5.0):
            return None
        f = c.call_async(req)
        rclpy.spin_until_future_complete(node, f, timeout_sec=timeout)
        return f.result()

    def read_posx():
        r = call('posx', GetCurrentPosx.Request(ref=0), 5.0)
        return list(r.task_pos_info[0].data[:6]) if r and r.success and r.task_pos_info else None

    def read_posj():
        r = call('posj', GetCurrentPosj.Request(), 5.0)
        return list(r.pos[:6]) if r and r.success else None

    def movel(posx):
        req = MoveLine.Request(pos=[float(v) for v in posx], vel=[args.vel, args.vel], acc=[4 * args.vel, 4 * args.vel],
                               time=0.0, radius=0.0, ref=0, mode=0, blend_type=0, sync_type=0)
        r = call('movel', req, args.timeout)
        return bool(r and r.success)

    if read_posx() is None:
        print('posx 조회 실패 — 브링업(sodvir / sodreal)이 떠 있는지, 다른 조회 프로그램이 돌고 있는지 확인', file=sys.stderr)
        return 2
    new_file = not os.path.exists(args.file)
    with open(args.file, 'a', newline='') as fh:
        w = csv.writer(fh)
        if new_file:
            w.writerow(HEADER)
        safe_z = args.safe_z if args.safe_z is not None else args.cube[4] + args.lift
        print(f'자세 사이 이동 높이(안전 높이) = {safe_z:.2f} mm  '
              f'(큐브 윗면 {args.cube[4]:.2f} + {args.lift:.0f})')

        def to_safe_z():
            """현재 자세 그대로 수직으로 안전 높이까지 올린다. 이미 위면 아무것도 안 한다."""
            p = read_posx()
            if p is None:
                return False
            if p[2] >= safe_z - 0.5:
                return True
            return movel(p[:2] + [safe_z] + p[3:])

        def arrived(target):
            p = read_posx()
            if p is None:
                return False, float('inf')
            g = max(abs(a - b) for a, b in zip(p[:3], target[:3]))
            return g <= ARRIVE_TOL_MM, g

        for line, where, posx in weld_poses(args.cube, args.standoff, args.tilt, args.bottom_margin):
            if args.only and line not in args.only.split(','):
                continue
            above = posx[:2] + [posx[2] + args.lift] + posx[3:]
            over = posx[:2] + [max(safe_z, above[2])] + posx[3:]   # 목표 x·y 위 안전 높이
            print(f'\n[{line} {where}] 안전 높이 {over[2]:.0f} → 위 {args.lift:.0f} mm → {fmt(above)}')
            ans = input('  Enter = 이동 / s = 건너뜀 / q = 종료: ').strip().lower()
            if ans == 'q':
                break
            if ans == 's':
                continue
            # ① 지금 자리에서 수직으로 안전 높이까지
            if not to_safe_z():
                print(f'  ❌ 안전 높이 {safe_z:.0f} mm 로 올리지 못했다 — 중단한다')
                w.writerow([time.strftime('%H:%M:%S'), line, where + '_safez'] + posx + [0, '', '', '', f'안전 높이 {safe_z:.1f} 실패'])
                fh.flush()
                break
            # ② 안전 높이에서 목표 x·y 로 수평 이동 + 회전
            movel(over)
            ok_over, gap_over = arrived(over)
            if not ok_over:
                print(f'  위 자세 실패 (관절 한계 · 특이점?) — 안전 높이에서 {gap_over:.2f} mm 차이')
                w.writerow([time.strftime('%H:%M:%S'), line, where + '_above'] + posx + [0, '', '', '', f'안전 높이 접근 실패 {gap_over:.2f} mm'])
                fh.flush()
                to_safe_z()
                continue
            # ③ 안전 높이에서 목표 위 --lift 까지 수직 하강
            if above[2] < over[2] - 0.5:
                movel(above)
                ok_ab, gap_ab = arrived(above)
                if not ok_ab:
                    print(f'  위 {args.lift:.0f} mm 자세 실패 — 지령과 {gap_ab:.2f} mm 차이')
                    w.writerow([time.strftime('%H:%M:%S'), line, where + '_above'] + posx + [0, '', '', '', f'위 {args.lift:.0f} mm 실패 {gap_ab:.2f} mm'])
                    fh.flush()
                    to_safe_z()
                    continue
            ans = input(f'  자세로 내려갈까요 → {fmt(posx)}  (Enter / s / q): ').strip().lower()
            if ans == 'q':
                break
            if ans == 's':
                continue
            ok = movel(posx)
            px, pj = read_posx(), read_posj()
            # 두산 move_line 의 success 는 "명령을 받았다"이지 "그 자세를 만들었다"가 아니다.
            # 9/23 실기에서 L1 이 한 번도 안 움직였는데 success=true 가 왔다 → 도달은 posx 로 확인한다.
            gap = (max(abs(a - b) for a, b in zip(px[:3], posx[:3]))
                   if px else float('inf'))
            hit = gap <= ARRIVE_TOL_MM      # 이름을 arrived 로 쓰면 위 도우미 함수를 덮어쓴다
            reach = int(bool(ok) and hit)
            why = '' if reach else (
                'movel success=false' if not ok else
                ('posx 조회 실패' if px is None else f'안 움직였다: 지령과 {gap:.2f} mm 차이'))
            print(f'  reach={reach}  posx={fmt(px) if px else "?"}  posj={fmt(pj) if pj else "?"}'
                  + (f'  ← {why}' if why else ''))
            clearance = input('  손가락 · 홀더 ↔ 큐브 · 작업대 최소 거리 [mm] (모르면 빈칸): ').strip()
            note = input('  메모: ').strip()
            w.writerow([time.strftime('%H:%M:%S'), line, where] + posx + [reach, fmt(px) if px else '', fmt(pj) if pj else '', clearance, (note + ' / ' + why).strip(' /') if why else note])
            fh.flush()
            input('  Enter = 위로 올림: ')
            movel(above)
            to_safe_z()          # 다음 자세로 옆으로 가기 전에 큐브 위로 뺀다
    node.destroy_node()
    rclpy.shutdown()
    return 0


def fmt(vals):
    return '[' + ', '.join(f'{v:.2f}' for v in vals) + ']'


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    poses = weld_poses(args.cube, args.standoff, args.tilt, args.bottom_margin)
    if args.dry_run:
        for line, where, posx in poses:
            print(f'{line:3} {where:7} {fmt(posx)}')
        return 0
    if not args.real_ok:
        print('실기라면 --real-ok 를 붙인다(사람이 로봇 앞에서). Virtual 이면 그냥 진행한다.')
    return run(args)


if __name__ == '__main__':
    sys.exit(main())
