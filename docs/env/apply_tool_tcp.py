#!/usr/bin/env python3
"""툴 무게·TCP를 컨트롤러에 다시 만들고 적용한 뒤 검증한다 (T02). 실기에서는 사람이 실행한다.

sodreal을 다시 켜면 ROS로 등록한 툴·TCP가 지워진다(2026-09-19 실기 확인).
측정·탐색 직전에 실행하고, 마지막 줄이 OK인지 본다.

    sod
    python3 docs/env/apply_tool_tcp.py

순서: 수동 모드 → 툴 지우기·만들기·적용 → TCP 지우기·만들기·적용 → 자동 모드 → 검증.
같은 이름이 남아 있어도 값이 확실히 바뀌도록 항상 지우고 다시 만든다.
검증: 현재 툴·TCP 이름, 그리고 |TCP 위치 − 플랜지 위치|가 |TCP 오프셋|과 0.2 mm 안에서 맞는지.

값은 docs/env/tool-tcp-register.md 2·3절과 docs/contracts/units-frames.md의 값이다.
바뀌면 세 곳을 같이 고친다. robot_manager(T13)에서는 real.yaml 파라미터로 옮긴다.
"""
import math
import sys
import time

import rclpy
from dsr_msgs2.srv import (ConfigCreateTcp, ConfigCreateTool, ConfigDeleteTcp, ConfigDeleteTool,
                           GetCurrentPosx, GetCurrentTcp, GetCurrentTool, GetCurrentToolFlangePosx,
                           SetCurrentTcp, SetCurrentTool, SetRobotMode)

from measure_idle_force import Caller

TOOL_NAME = 'rg2_probe'
TOOL_WEIGHT_KG = 1.3
TOOL_COG_MM = [0.0, 31.08, 29.84]
TCP_NAME = 'rg2_probe_tip'
TCP_POS = [-1.30, 3.71, 250.21, 0.0, 0.0, 0.0]  # 최하단점: 구 중심 z 249.76 + 팁 반지름 0.45
MANUAL, AUTONOMOUS = 0, 1


def ok(res):
    return res is not None and res.success


def main():
    rclpy.init()
    node = rclpy.create_node('apply_tool_tcp')
    caller = Caller(node, timeout=3.0, retries=2)
    c = {k: caller.client(t, n) for k, t, n in [
        ('mode', SetRobotMode, 'system/set_robot_mode'),
        ('del_tool', ConfigDeleteTool, 'tool/config_delete_tool'),
        ('new_tool', ConfigCreateTool, 'tool/config_create_tool'),
        ('set_tool', SetCurrentTool, 'tool/set_current_tool'),
        ('get_tool', GetCurrentTool, 'tool/get_current_tool'),
        ('del_tcp', ConfigDeleteTcp, 'tcp/config_delete_tcp'),
        ('new_tcp', ConfigCreateTcp, 'tcp/config_create_tcp'),
        ('set_tcp', SetCurrentTcp, 'tcp/set_current_tcp'),
        ('get_tcp', GetCurrentTcp, 'tcp/get_current_tcp'),
        ('posx', GetCurrentPosx, 'aux_control/get_current_posx'),
        ('flange', GetCurrentToolFlangePosx, 'aux_control/get_current_tool_flange_posx'),
    ]}
    manual = False
    try:
        deadline = time.monotonic() + 10.0
        missing = [v.srv_name for v in c.values()
                   if not v.wait_for_service(timeout_sec=max(0.1, deadline - time.monotonic()))]
        if missing:
            print(f'서비스 연결 안 됨: {missing}. sodreal이 떠 있는지 확인')
            return 1
        time.sleep(0.5)

        def step(label, key, req, required=True):
            res = caller.call(c[key], req)
            print(f'  {label}: {"성공" if ok(res) else "실패"}')
            if required and not ok(res):
                raise RuntimeError(label)

        print('[1/5] 수동 모드')
        step('전환', 'mode', SetRobotMode.Request(robot_mode=MANUAL))
        manual = True
        print(f'[2/5] 툴 {TOOL_NAME}')
        step('지우기(없으면 실패해도 됨)', 'del_tool', ConfigDeleteTool.Request(name=TOOL_NAME), required=False)
        step('만들기', 'new_tool', ConfigCreateTool.Request(
            name=TOOL_NAME, weight=TOOL_WEIGHT_KG, cog=TOOL_COG_MM, inertia=[0.0] * 6))
        step('적용', 'set_tool', SetCurrentTool.Request(name=TOOL_NAME))
        print(f'[3/5] TCP {TCP_NAME} {TCP_POS}')
        step('지우기(없으면 실패해도 됨)', 'del_tcp', ConfigDeleteTcp.Request(name=TCP_NAME), required=False)
        step('만들기', 'new_tcp', ConfigCreateTcp.Request(name=TCP_NAME, pos=TCP_POS))
        step('적용', 'set_tcp', SetCurrentTcp.Request(name=TCP_NAME))
    except RuntimeError as e:
        print(f'실패: {e}. 펜던트 알람·제어권을 확인한다')
        return 1
    finally:
        if manual:
            print('[4/5] 자동 모드')
            res = caller.call(c['mode'], SetRobotMode.Request(robot_mode=AUTONOMOUS))
            print(f'  전환: {"성공" if ok(res) else "실패. 펜던트에서 자동 모드로 되돌린다"}')

    try:
        print('[5/5] 검증')
        tool = caller.call(c['get_tool'], GetCurrentTool.Request())
        tcp = caller.call(c['get_tcp'], GetCurrentTcp.Request())
        posx = caller.call(c['posx'], GetCurrentPosx.Request(ref=0))
        flange = caller.call(c['flange'], GetCurrentToolFlangePosx.Request(ref=0))
    finally:
        node.destroy_node()
        rclpy.shutdown()

    names_ok = bool(tool and tcp and tool.info == TOOL_NAME and tcp.info == TCP_NAME)
    print(f'  현재 툴 = {tool.info if tool else None!r}, TCP = {tcp.info if tcp else None!r}')
    dist_ok = False
    if ok(posx) and posx.task_pos_info and ok(flange):
        dist = math.dist(posx.task_pos_info[0].data[:3], flange.pos[:3])
        expect = math.hypot(*TCP_POS[:3])
        dist_ok = abs(dist - expect) < 0.2
        print(f'  |TCP − 플랜지| = {dist:.2f} mm (기대 {expect:.2f} mm)')
    else:
        print('  위치 조회 실패')

    if names_ok and dist_ok:
        print(f'OK: tool={TOOL_NAME}, tcp={TCP_NAME} {TCP_POS[:3]}')
        return 0
    print('실패: 현재 툴·TCP가 기대값과 다르다')
    return 1


if __name__ == '__main__':
    sys.exit(main())
