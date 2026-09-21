#!/usr/bin/env python3
"""J6 180° 회전으로 TCP x · y 를 확인한다. 순수 계산이고 로봇에 연결하지 않는다.

탐침을 바꾸면 TCP z 는 작업대 기준점 접촉으로 맞추지만(units-frames.md '탐침 상태 전제조건'),
x · y 는 그 방법으로 잡히지 않는다. 표시되는 팁 좌표는 등록된 TCP 로 계산되므로 같은 자세에서는
x · y 가 틀려도 드러나지 않는다. 툴 z축(= J6 축, TCP 자세 [0,0,0])으로 180° 돌리면 드러난다.

절차 (사람이 한다. 로봇 명령은 Claude 가 실행하지 않는다):
1. 작업대에 십자 표시(가는 펜)를 붙이고, 팁을 표시 중심 바로 위 0.5~1 mm 에 맞춘다(돋보기)
   → `python3 docs/env/probe_point.py --label xy_0 --file <세션>/tcp_xy.csv`
2. **J6 만 +180°** 조그한다(홈 J6 −204.84° → −24.84°. −180° 로 돌리면 한계를 넘는다)
   팁이 표시에서 벗어난다. 벗어난 거리가 등록 TCP x · y 오차의 두 배다
3. **Base x · y 평행 이동만으로** 팁을 다시 표시 중심 위에 맞춘다(자세 · 높이는 건드리지 않는다)
   → `python3 docs/env/probe_point.py --label xy_180 --file <세션>/tcp_xy.csv`
4. `python3 docs/env/tcp_xy_from_180.py <세션>/tcp_xy.csv --tcp -1.30 3.71 252.12`

원리: 등록 TCP t0 로 읽은 팁 좌표 P' = F + R t0, 실제 팁 = F + R t 가 두 자세에서 같은 점이면
P2' − P1' = (R1 − R2)(t − t0). 툴 z축 회전은 z 성분을 구속하지 않으므로 x · y 만 최소제곱으로 푼다.
눈으로 맞추는 정밀도가 약 0.2~0.3 mm 이면 x · y 오차 추정은 그 절반 정도다.
"""
import argparse
import csv
import sys

import numpy as np

from pivot_tcp import rot_zyz


def solve_xy(pose_a, pose_b):
    """두 자세(x, y, z, A, B, C; mm · deg ZYZ)의 표시 팁 좌표에서 TCP x · y 보정량을 구한다.

    돌려주는 값: (dx, dy) 보정량 [mm], z 방향 잔차 [mm], 두 자세의 툴 z축 회전각 [deg].
    """
    p1, p2 = np.array(pose_a[:3], float), np.array(pose_b[:3], float)
    r1, r2 = rot_zyz(*pose_a[3:]), rot_zyz(*pose_b[3:])
    a = (r1 - r2)[:, :2]
    d = p2 - p1
    delta, *_ = np.linalg.lstsq(a, d, rcond=None)
    residual = d - a @ delta
    rel = r1.T @ r2
    spin = float(np.degrees(np.arctan2(rel[1, 0], rel[0, 0])))
    tilt = float(np.degrees(np.arccos(np.clip(rel[2, 2], -1.0, 1.0))))
    return tuple(delta), float(np.linalg.norm(residual)), spin, tilt


def read_labels(path, label_a, label_b):
    rows = {}
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if row.get('valid', '1') == '1':
                rows[row['label']] = [float(row[k]) for k in
                                      ('x_mm', 'y_mm', 'z_mm', 'rz1_deg', 'ry_deg', 'rz2_deg')]
    missing = [l for l in (label_a, label_b) if l not in rows]
    if missing:
        sys.exit(f'{path} 에 유효한 줄이 없다: {", ".join(missing)}')
    return rows[label_a], rows[label_b]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('csv', help='probe_point.py 기록 파일')
    p.add_argument('--labels', nargs=2, default=('xy_0', 'xy_180'))
    p.add_argument('--tcp', nargs=3, type=float, required=True, metavar=('X', 'Y', 'Z'),
                   help='두 점을 찍을 때 등록돼 있던 TCP [mm]')
    args = p.parse_args(argv)

    pose_a, pose_b = read_labels(args.csv, *args.labels)
    (dx, dy), residual, spin, tilt = solve_xy(pose_a, pose_b)
    print(f'툴 z축 회전 {spin:+.1f}°, 축 기울기 차 {tilt:.2f}°')
    if abs(abs(spin) - 180.0) > 20.0:
        print('  경고: 180° 에서 20° 넘게 벗어났다. 회전각이 작으면 추정이 불안정하다')
    if tilt > 1.0:
        print('  경고: 툴 z축이 두 자세에서 1° 넘게 다르다. J6 만 돌렸는지 확인한다')
    print(f'z 방향 잔차 {residual:.2f} mm (1 mm 를 넘으면 높이가 바뀌었거나 표시를 잘못 맞춘 것이다)')
    x, y, z = args.tcp
    print(f'TCP x · y 보정량: dx {dx:+.2f} mm, dy {dy:+.2f} mm')
    print(f'새 TCP 후보: [{x + dx:.2f}, {y + dy:.2f}, {z:.2f}]')
    print('  반영: apply_tool_tcp.py --tcp-x --tcp-y 로 등록 → 같은 절차로 다시 찍어 보정량이 0.3 mm 안인지 본다')


if __name__ == '__main__':
    main()
