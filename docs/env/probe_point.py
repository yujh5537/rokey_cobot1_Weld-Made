#!/usr/bin/env python3
"""직접교시로 찍은 점 하나를 기록한다 (T03 후속 · T08).

로봇을 움직이지 않는다. 조회만 한다. 손으로 원하는 자세를 잡은 뒤 이것을 부르면
현재 팁 좌표 · 외력 · 툴 · TCP를 한 줄로 CSV에 덧붙인다.

**다른 조회 프로그램과 같이 돌리지 않는다.** 두산 서비스를 동시에 부르면 dsr_controller2 가
응답을 멈춘다(2026-09-20 확인, `docs/env/api-check-log.md`). `measure_idle_force.py` 를 켜 두었다면
먼저 끄고 이것을 쓴다.

    sod && cd ~/ws_cobot_pjt
    python3 docs/env/probe_point.py --label top_center
    python3 docs/env/probe_point.py --label edge_x_side --file edge.csv

머리줄: time,label,x_mm,y_mm,z_mm,rz1_deg,ry_deg,rz2_deg,fx_n,fy_n,fz_n,tool,tcp,valid
- 좌표는 `get_current_posx(ref=DR_BASE)`, 힘은 `get_tool_force(ref=DR_BASE)`다.
- 툴 · TCP 이름을 같이 남긴다. 등록이 풀린 상태에서 찍은 값을 나중에 구분하기 위해서다
  (툴 미등록이면 외력에 12 N 안팎의 치우침이 생긴다. `docs/env/tool-tcp-register.md`).
- 조회에 실패하면 그 칸을 비우고 valid=0으로 남긴다. 0으로 채우지 않는다(CLAUDE.md 규칙 4).
"""
import argparse
import math
import os
import sys
import time

import rclpy
from dsr_msgs2.srv import GetCurrentPosx, GetCurrentTcp, GetCurrentTool, GetToolForce

PREFIX = '/dsr01/dsr_controller2/'
HEADER = 'time,label,x_mm,y_mm,z_mm,rz1_deg,ry_deg,rz2_deg,fx_n,fy_n,fz_n,tool,tcp,valid\n'


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--label', required=True, help='이 점의 이름 (예: top_center, edge_x_side)')
    p.add_argument('--file', default='probe_points.csv', help='기록 파일 (없으면 만든다)')
    p.add_argument('--timeout', type=float, default=8.0, help='서비스 연결 · 조회 대기 [s]')
    return p.parse_args(argv)


def call(node, client, request, timeout):
    if not client.wait_for_service(timeout_sec=timeout):
        return None
    future = client.call_async(request)
    rclpy.spin_until_future_complete(node, future, timeout_sec=timeout)
    if not future.done():
        client.remove_pending_request(future)
        return None
    return future.result()


def read(node, args):
    c = lambda t, n: node.create_client(t, PREFIX + n)
    # 첫 호출 전에 탐색이 끝나야 한다. 준비될 때까지 기다린 뒤 잠깐 둔다
    probe = c(GetCurrentPosx, 'aux_control/get_current_posx')
    if not probe.wait_for_service(timeout_sec=args.timeout):
        print(f'서비스가 안 보인다: {PREFIX}aux_control/get_current_posx')
        print('  - 브링업(sodreal)이 떠 있는지, ROS_DOMAIN_ID 가 같은지 확인한다'
              f' (지금 {os.environ.get("ROS_DOMAIN_ID", "미설정")})')
        return None, None, None, None
    time.sleep(0.3)
    posx = call(node, c(GetCurrentPosx, 'aux_control/get_current_posx'),
                GetCurrentPosx.Request(ref=0), args.timeout)
    force = call(node, c(GetToolForce, 'aux_control/get_tool_force'),
                 GetToolForce.Request(ref=0), args.timeout)
    tool = call(node, c(GetCurrentTool, 'tool/get_current_tool'), GetCurrentTool.Request(), args.timeout)
    tcp = call(node, c(GetCurrentTcp, 'tcp/get_current_tcp'), GetCurrentTcp.Request(), args.timeout)

    pose = None
    if posx and posx.success and posx.task_pos_info:
        values = list(posx.task_pos_info[0].data[:6])
        if len(values) == 6 and all(math.isfinite(v) for v in values):
            pose = values
    wrench = None
    if force and force.success and all(math.isfinite(v) for v in force.tool_force[:3]):
        wrench = list(force.tool_force[:3])
    return pose, wrench, (tool.info if tool and tool.success else None), (tcp.info if tcp and tcp.success else None)


def main():
    args = parse_args(rclpy.utilities.remove_ros_args(sys.argv)[1:])
    rclpy.init()
    node = rclpy.create_node('probe_point')
    try:
        pose, wrench, tool, tcp = read(node, args)
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

    cell = lambda v, n=3: '' if v is None else f'{v:.{n}f}'
    valid = pose is not None and wrench is not None
    row = [time.strftime('%H:%M:%S'), args.label,
           *[cell(v) for v in (pose or [None] * 6)],
           *[cell(v, 2) for v in (wrench or [None] * 3)],
           tool or '', tcp or '', '1' if valid else '0']

    new_file = not os.path.exists(args.file)
    with open(args.file, 'a', encoding='utf-8') as f:
        if new_file:
            f.write(HEADER)
        f.write(','.join(row) + '\n')

    if pose:
        print(f'{args.label}: x {pose[0]:.3f}  y {pose[1]:.3f}  z {pose[2]:.3f} mm   '
              f'자세 ({pose[3]:.2f}, {pose[4]:.2f}, {pose[5]:.2f}) deg')
    else:
        print(f'{args.label}: 좌표 조회 실패')
    if wrench:
        print(f'  힘 Fx {wrench[0]:+.2f}  Fy {wrench[1]:+.2f}  Fz {wrench[2]:+.2f} N')
    else:
        print('  힘 조회 실패')
    print(f'  툴 {tool!r} · TCP {tcp!r} → {args.file}')
    if tool != 'rg2_probe' or tcp != 'rg2_probe_tip':
        print('  ⚠️ 툴 · TCP 등록이 풀렸다. apply_tool_tcp.py 를 먼저 실행한다')
    return 0 if valid else 1


if __name__ == '__main__':
    sys.exit(main())
