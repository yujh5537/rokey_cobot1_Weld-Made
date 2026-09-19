#!/usr/bin/env python3
"""피벗 보정으로 TCP 오프셋 계산 (T02). 순수 계산이고 로봇에 연결하지 않는다.

탐침 팁을 같은 고정점에 대고 자세만 바꿔 4번 이상 찍는다. 매번
`aux_control/get_current_tool_flange_posx`(ref=0)로 읽은 플랜지 posx
[x, y, z, A, B, C] (mm, deg, ZYZ)를 한 줄씩 적은 파일을 넣는다.

    python3 docs/env/pivot_tcp.py flange_poses.txt

모든 자세에서 R_i @ t + p_i = P 이므로, 최소제곱으로
t(플랜지 기준 TCP 오프셋)와 P(고정점의 Base 좌표)를 함께 푼다.
"""
import math
import sys

import numpy as np


def rot_zyz(a_deg, b_deg, c_deg):
    a, b, c = (math.radians(v) for v in (a_deg, b_deg, c_deg))

    def rz(t):
        return np.array([[math.cos(t), -math.sin(t), 0], [math.sin(t), math.cos(t), 0], [0, 0, 1]])

    def ry(t):
        return np.array([[math.cos(t), 0, math.sin(t)], [0, 1, 0], [-math.sin(t), 0, math.cos(t)]])

    return rz(a) @ ry(b) @ rz(c)


def solve(poses):
    """poses: [[x, y, z, A, B, C], ...] 플랜지 posx. 반환: (t, P, 자세별 잔차 mm, 최대 기울기 차 deg)."""
    if len(poses) < 4:
        raise ValueError('자세가 4개 이상 필요하다')
    rows, rhs, rots = [], [], []
    for x, y, z, a, b, c in poses:
        r = rot_zyz(a, b, c)
        rots.append(r)
        rows.append(np.hstack([r, -np.eye(3)]))
        rhs.append(-np.array([x, y, z]))
    sol, *_ = np.linalg.lstsq(np.vstack(rows), np.hstack(rhs), rcond=None)
    t, p = sol[:3], sol[3:]
    resid = [float(np.linalg.norm(r @ t + np.array(q[:3]) - p)) for r, q in zip(rots, poses)]
    spread = max(math.degrees(math.acos(np.clip(ri[:, 2] @ rj[:, 2], -1, 1)))
                 for ri in rots for rj in rots)
    return t, p, resid, spread


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    poses = []
    with open(sys.argv[1]) as f:
        for line in f:
            line = line.split('#')[0].replace(',', ' ').replace('[', ' ').replace(']', ' ').strip()
            if line:
                poses.append([float(v) for v in line.split()])
    t, p, resid, spread = solve(poses)
    print(f'자세 {len(poses)}개, 툴 축 방향 최대 차이 {spread:.1f} deg (30 deg 이상 권장)')
    print(f'TCP 오프셋 t (플랜지 기준, mm): x {t[0]:+.2f}  y {t[1]:+.2f}  z {t[2]:+.2f}  |t| {np.linalg.norm(t):.2f}')
    print(f'고정점 P (Base, mm): {p[0]:.2f}, {p[1]:.2f}, {p[2]:.2f}')
    for i, e in enumerate(resid, 1):
        print(f'  자세 {i}: 잔차 {e:.2f} mm')
    print(f'잔차 최대 {max(resid):.2f} mm. 1 mm 이하면 찍기가 일관됐다고 본다')
    return 0


if __name__ == '__main__':
    sys.exit(main())
