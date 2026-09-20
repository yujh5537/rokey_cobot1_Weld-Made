#!/usr/bin/env python3
"""무접촉 정지 상태의 외력 측정과 샘플 기록 (T02 BRD 4.1.5, T08 · T24 TR-01).

조회만 한다. 로봇을 움직이는 서비스는 부르지 않는다. 하강은 사람이 따로 시킨다.
현재 툴·TCP 이름, 현재 TCP 위치, 외력(get_tool_force)을 N번 읽어 요약하고,
`--csv`를 주면 샘플마다 위치·힘을 파일로 남긴다.

    sod && sodvir (또는 sodreal)      # 다른 터미널에서 브링업
    sod
    python3 docs/env/measure_idle_force.py --pose home --samples 50 --interval 0.1

    # ① 정지 · 무접촉 30초
    python3 docs/env/measure_idle_force.py --pose home --duration 30 --interval 0.02 \
        --csv idle_30s.csv
    # ② 정지 2초 → 저속 하강 → 접촉 → 정지 (하강은 사람이 시킨다)
    python3 docs/env/measure_idle_force.py --pose origin_above --duration 30 --interval 0 \
        --csv descend_01.csv

`--csv` 형식은 `contact_detector`의 오프라인 분석기(`analyze_samples`)가 읽는 형식이다.

    t_pose_s,t_force_s,x_mm,y_mm,z_mm,fx_n,fy_n,fz_n,valid

- `t_*_s`: 각 조회의 **응답을 받은 시각** [s]. 기록 시작이 0인 같은 시계다
- 위치는 `get_current_posx(ref=DR_BASE)`의 x · y · z [mm], 힘은 `get_tool_force(ref=DR_BASE)`의 Fx · Fy · Fz [N]
- `valid`: 위치와 힘을 모두 제대로 받은 줄만 1이다. 실패한 줄은 숫자 칸을 비우고 `valid=0`으로 남긴다

실패한 조회는 0으로 채우지 않고 invalid로 센다(CLAUDE.md 규칙 4).

DSR_ROBOT2를 쓰지 않고 dsr_controller2 서비스를 직접 부른다. DSR_ROBOT2 함수는 응답을
시간 제한 없이 기다려서, 응답이 사라지면 스크립트가 영원히 멈췄다(2026-09-19 실기에서 세 번).
여기서는 호출마다 시간 제한을 두고, 응답이 없으면 같은 요청을 다시 보낸다.
"""
import argparse
import math
import statistics
import sys
import time

import rclpy
from dsr_msgs2.srv import GetCurrentPosx, GetCurrentTcp, GetCurrentTool, GetToolForce

PREFIX = '/dsr01/dsr_controller2/'
AXES = ('Fx', 'Fy', 'Fz', 'Tx', 'Ty', 'Tz')
REF = {'base': 0, 'tool': 1}


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--pose', required=True, help='측정 자세 이름 (기록용, 예: home, origin_above)')
    p.add_argument('--samples', type=int, default=50)
    p.add_argument('--duration', type=float, default=None,
                   help='기록 시간 [s]. 주면 --samples 대신 이 시간 동안 읽는다')
    p.add_argument('--interval', type=float, default=0.1, help='조회 간격 [s]. 0이면 쉬지 않고 읽는다')
    p.add_argument('--csv', help='샘플을 기록할 파일. 주면 샘플마다 위치도 같이 읽는다')
    p.add_argument('--ref', choices=tuple(REF), default='base', help='힘 기준 좌표계')
    p.add_argument('--timeout', type=float, default=1.5, help='조회 1회 시간 제한 [s]')
    p.add_argument('--retries', type=int, default=3, help='응답이 없을 때 다시 보내는 횟수')
    return p.parse_args(argv)


class Caller:
    """서비스 호출마다 시간 제한과 재시도를 둔다. 실패하면 None을 돌려준다."""

    def __init__(self, node, timeout, retries):
        self.node, self.timeout, self.retries = node, timeout, retries
        self.timeouts = 0

    def client(self, srv_type, name):
        return self.node.create_client(srv_type, PREFIX + name)

    def call(self, client, request):
        for _ in range(1 + self.retries):
            future = client.call_async(request)
            rclpy.spin_until_future_complete(self.node, future, timeout_sec=self.timeout)
            if future.done():
                return future.result()
            client.remove_pending_request(future)
            self.timeouts += 1
        return None


def read_posx(res):
    """응답에서 x · y · z [mm]를 꺼낸다. 실패하면 None (0으로 채우지 않는다)."""
    if not (res and res.success and res.task_pos_info):
        return None
    xyz = list(res.task_pos_info[0].data[:3])
    return xyz if len(xyz) == 3 and all(math.isfinite(v) for v in xyz) else None


class Recorder:
    """분석기(`contact_detector`의 analyze_samples)가 읽는 CSV로 남긴다."""

    HEADER = 't_pose_s,t_force_s,x_mm,y_mm,z_mm,fx_n,fy_n,fz_n,valid\n'
    FLUSH_EVERY = 50

    def __init__(self, path):
        self.f = open(path, 'w', encoding='utf-8', newline='')
        self.f.write(self.HEADER)
        self.n = 0

    def row(self, t_pose, t_force, pos, force):
        """위치나 힘이 없으면 그 칸을 비우고 valid=0으로 남긴다."""
        valid = pos is not None and force is not None
        cell = lambda v, n=3: '' if v is None else f'{v:.{n}f}'
        pos = pos if pos is not None else (None,) * 3
        force = force if force is not None else (None,) * 3
        self.f.write(','.join([cell(t_pose), cell(t_force),
                               *[cell(v, 4) for v in pos[:3]],
                               *[cell(v, 4) for v in force[:3]],
                               '1' if valid else '0']) + '\n')
        self.n += 1
        if self.n % self.FLUSH_EVERY == 0:
            self.f.flush()  # 중간에 멈춰도 기록이 남게 한다

    def close(self):
        self.f.close()


def summarize(values):
    return statistics.fmean(values), (statistics.stdev(values) if len(values) > 1 else float('nan'))


def measure(args, node):
    caller = Caller(node, args.timeout, args.retries)
    c_tool = caller.client(GetCurrentTool, 'tool/get_current_tool')
    c_tcp = caller.client(GetCurrentTcp, 'tcp/get_current_tcp')
    c_posx = caller.client(GetCurrentPosx, 'aux_control/get_current_posx')
    c_force = caller.client(GetToolForce, 'aux_control/get_tool_force')

    deadline = time.monotonic() + 10.0
    missing = [c.srv_name for c in (c_tool, c_tcp, c_posx, c_force)
               if not c.wait_for_service(timeout_sec=max(0.1, deadline - time.monotonic()))]
    if missing:
        print(f'서비스 연결 안 됨: {missing}. sodreal이 떠 있는지 확인')
        return None
    time.sleep(0.5)  # 응답 경로까지 연결될 시간을 준다

    tool = caller.call(c_tool, GetCurrentTool.Request())
    tcp = caller.call(c_tcp, GetCurrentTcp.Request())
    print(f"tool = {tool.info if tool else None!r}, tcp = {tcp.info if tcp else None!r}")
    posx = caller.call(c_posx, GetCurrentPosx.Request(ref=0))
    if read_posx(posx):
        print('posx (mm, deg) = [' + ', '.join(f'{v:.3f}' for v in posx.task_pos_info[0].data[:6]) + ']')
    else:
        print('posx (mm, deg) = 조회 실패')

    samples, invalid = [], 0
    req_force = GetToolForce.Request(ref=REF[args.ref])
    req_posx = GetCurrentPosx.Request(ref=0)
    recorder = Recorder(args.csv) if args.csv else None
    t0 = time.monotonic()
    rows = 0
    try:
        while (time.monotonic() - t0 < args.duration) if args.duration is not None else (rows < args.samples):
            rows += 1
            pos = t_pose = None
            if recorder:  # 기록할 때만 샘플마다 위치를 읽는다. 조회 수가 두 배가 된다
                res = caller.call(c_posx, req_posx)
                t_pose = time.monotonic() - t0
                pos = read_posx(res)
            res = caller.call(c_force, req_force)
            t_force = time.monotonic() - t0
            f = list(res.tool_force) if res and res.success else None
            if not (f and len(f) == 6 and all(math.isfinite(v) for v in f)):
                f = None
            if f:
                samples.append(f)
            else:
                invalid += 1
            if recorder:
                recorder.row(t_pose, t_force, pos, f)
            if args.interval > 0:
                time.sleep(args.interval)
    finally:
        if recorder:
            elapsed = time.monotonic() - t0
            recorder.close()
            hz = rows / elapsed if elapsed > 0 else float('nan')
            print(f'기록: {rows}줄, {elapsed:.1f} s, 평균 {hz:.1f} Hz → {args.csv}')
    return samples, invalid, caller.timeouts


def main():
    args = parse_args(rclpy.utilities.remove_ros_args(sys.argv)[1:])
    rclpy.init()
    node = rclpy.create_node('measure_idle_force')
    try:
        result = measure(args, node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
    if result is None:
        return 1
    samples, invalid, timeouts = result

    print(f'\npose={args.pose} ref={args.ref} valid={len(samples)} invalid={invalid} '
          f'시간초과(재시도 포함)={timeouts}')
    if not samples:
        print('유효 샘플 없음. 값을 기록하지 않는다.')
        return 1

    for i, name in enumerate(AXES):
        mean, std = summarize([s[i] for s in samples])
        unit = 'N' if name.startswith('F') else 'Nm'
        print(f'  {name}: mean {mean:+8.3f}  std {std:7.3f} {unit}')
    mags = [math.hypot(s[0], s[1], s[2]) for s in samples]
    mag_mean, mag_std = summarize(mags)
    print(f'  F크기: mean {mag_mean:.3f}  std {mag_std:.3f}  max {max(mags):.3f} N')

    # docs/env/tool-tcp-register.md 표에 그대로 붙인다
    print('\n| 자세 | ref | 유효/무효 | F크기 평균 [N] | F크기 표준편차 [N] | F크기 최대 [N] | Fz 평균 [N] |')
    fz_mean, _ = summarize([s[2] for s in samples])
    print(f'| {args.pose} | {args.ref} | {len(samples)}/{invalid} | {mag_mean:.2f} | {mag_std:.2f} '
          f'| {max(mags):.2f} | {fz_mean:+.2f} |')
    return 0


if __name__ == '__main__':
    sys.exit(main())
