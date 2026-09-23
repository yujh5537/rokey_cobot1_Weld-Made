#!/usr/bin/env python3
"""두산 API 호출 경로 확인 (T04, [E19]).

`docs/env/api-check-log.md` 표의 API를 dsr_controller2 서비스로 직접 불러 성공 여부를 기록한다.
호출이 된다는 확인이지 접촉 검출 성능 검증이 아니다.

    # 다른 터미널에서 브링업 (Virtual 확인은 팀 도메인과 분리한다)
    export ROS_DOMAIN_ID=99 && sod && sodvir
    # 확인
    export ROS_DOMAIN_ID=99 && sod
    python3 docs/env/check_api_calls.py                                   # 조회만 (기본)
    python3 docs/env/check_api_calls.py --steps all --move-home           # Virtual 전체

단계 (--steps, 쉼표로 구분):
  query            robot_system · mode · 툴 · TCP · posx · get_tool_force 조회. 로봇을 움직이지 않는다
  poscond          check_position_condition을 참 · 거짓 · 넓은 범위 조건으로 부른다. 움직이지 않는다.
                   응답 success가 조건 판정 결과다(dsr_controller2.cpp). 호출 실패와 구분되지 않는다
  amovel_stop      move_line ASYNC(amovel)로 +z 방향 이동을 시작하고 도중에 move_stop(DR_QSTOP)
  compliance_force task_compliance_ctrl → set_desired_force(0 N, DR_FC_MOD_REL) → 해제
  drl              drl_start로 set_external_force_reset() 실행 (외력 센서 초기화)
  gripper          /onrobot/sendCommand 'o' → 'c'. Virtual 전용 (실기는 탐침이 떨어지므로 거부)

실기(robot_system=REAL)에서는 조회 외 단계를 --real-ok 없이는 실행하지 않는다.
실기 명령은 사람이 직접 실행한다(CLAUDE.md 규칙 1).

**robot_manager(contact_scan_bringup launch)와 동시에 돌리지 않는다.** 두산 서비스 조회가 겹치면
dsr_controller2 가 응답을 멈출 수 있고(api-check-log.md), 끝날 때 로봇 모드를 되돌리므로 스캔 중인
로봇의 모드가 바뀐다. launch 를 끄고 돌린다.

DSR_ROBOT2 함수 대신 서비스를 직접 부른다. DSR_ROBOT2 함수는 응답을 시간 제한 없이 기다려
실기에서 멈춘 적이 있다(`measure_idle_force.py` 참고). 움직이는 호출은 다시 보내지 않는다.
"""
import argparse
import math
import sys
import time

import rclpy
from dsr_msgs2.srv import (CheckPositionCondition, DrlStart, GetCurrentPosx, GetCurrentTcp,
                           GetCurrentTool, GetDrlState, GetRobotMode, GetRobotSystem,
                           GetToolForce, MoveJoint, MoveLine, MoveStop, ReleaseComplianceCtrl,
                           ReleaseForce, SetDesiredForce, SetRobotMode, TaskComplianceCtrl)
from onrobot_rg_msgs.srv import SetCommand

PREFIX = '/dsr01/dsr_controller2/'
GRIPPER_SRV = '/onrobot/sendCommand'
STEPS = ('query', 'poscond', 'amovel_stop', 'compliance_force', 'drl', 'gripper')
MOVING_STEPS = ('amovel_stop', 'compliance_force', 'drl', 'gripper')

# DR_common2.py / DRFC.py 값
DR_BASE = 0
DR_AXIS_Z = 2
DR_MV_MOD_ABS, DR_MV_MOD_REL = 0, 1
DR_QSTOP = 1
DR_FC_MOD_REL = 1
SYNC, ASYNC = 0, 1
ROBOT_SYSTEM = {0: 'REAL', 1: 'VIRTUAL'}
ROBOT_MODE_MANUAL = 0
ROBOT_MODE_AUTONOMOUS = 1
DRL_STATE = {0: 'PLAY', 1: 'STOP', 2: 'HOLD'}

# 홈 관절각 기본값: docs/contracts/units-frames.md (T03). 실기에서 다른 자세를 쓰려면 --home-joint
# 2026-09-23 새 홈(계약 v0.1.18, #169). 옛 홈 [-24.14, 17.03, 51.68, -0.18, 111.39, -204.84] 은
# J6 가 ±180° 밖이라 다른 자세에서 movej 하면 손목이 약 170° 돈다. real.yaml 의 home_joint_deg 와 같은 값이다
HOME_JOINT_DEG = [-21.19, 15.24, 52.97, -0.08, 111.80, -15.14]


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--steps', default='query,poscond',
                   help=f'쉼표로 구분. all = 전부. 선택: {", ".join(STEPS)}')
    p.add_argument('--move-home', action='store_true',
                   help='움직이는 단계 전에 홈 관절각으로 movej (Virtual 초기 자세는 특이점이라 필요)')
    p.add_argument('--home-joint', type=float, nargs=6, default=HOME_JOINT_DEG, metavar='DEG')
    p.add_argument('--dz', type=float, default=20.0, help='amovel 이동 거리, +z 위쪽 [mm]')
    p.add_argument('--vel', type=float, default=20.0, help='amovel 속도 [mm/s]')
    p.add_argument('--stop-after', type=float, default=0.4, help='amovel 시작 후 move_stop까지 [s]')
    p.add_argument('--timeout', type=float, default=3.0, help='호출 1회 시간 제한 [s]')
    p.add_argument('--real-ok', action='store_true', help='실기에서 조회 외 단계를 허용 (사람이 로봇 앞에 있을 때만)')
    args = p.parse_args(argv)
    args.steps = list(STEPS) if args.steps == 'all' else [s.strip() for s in args.steps.split(',') if s.strip()]
    unknown = [s for s in args.steps if s not in STEPS]
    if unknown:
        p.error(f'모르는 단계: {unknown}')
    return args


class Checker:
    """서비스 호출과 결과 기록. 실패한 호출은 None으로 두고 0으로 채우지 않는다(CLAUDE.md 규칙 4)."""

    def __init__(self, node, timeout):
        self.node, self.timeout = node, timeout
        self.clients = {}
        self.rows = []  # (API, 경로, 결과, 비고)

    def client(self, srv_type, name):
        full = name if name.startswith('/') else PREFIX + name
        if full not in self.clients:
            self.clients[full] = self.node.create_client(srv_type, full)
        return self.clients[full]

    def call(self, srv_type, name, request, retries=0):
        """(응답 또는 None, 걸린 시간 s). 움직이는 호출은 retries=0으로 둔다."""
        c = self.client(srv_type, name)
        if not c.wait_for_service(timeout_sec=self.timeout):
            return None, float('nan')
        for _ in range(1 + retries):
            t0 = time.monotonic()
            future = c.call_async(request)
            rclpy.spin_until_future_complete(self.node, future, timeout_sec=self.timeout)
            if future.done():
                return future.result(), time.monotonic() - t0
            c.remove_pending_request(future)
        return None, float('nan')

    def record(self, api, name, ok, note):
        path = name if name.startswith('/') else PREFIX + name
        mark = {True: '성공', False: '실패', None: '응답 없음', 'skip': '건너뜀'}[ok]
        self.rows.append((api, path, mark, note))
        print(f'[{mark:5}] {api:40} {path}  {note}')

    def posx(self):
        res, _ = self.call(GetCurrentPosx, 'aux_control/get_current_posx', GetCurrentPosx.Request(ref=DR_BASE), retries=2)
        if res and res.success and res.task_pos_info:
            return list(res.task_pos_info[0].data[:6])
        return None

    def force(self):
        res, _ = self.call(GetToolForce, 'aux_control/get_tool_force', GetToolForce.Request(ref=DR_BASE), retries=2)
        if res and res.success and len(res.tool_force) == 6 and all(math.isfinite(v) for v in res.tool_force):
            return list(res.tool_force)
        return None


def ok_of(res):
    return None if res is None else bool(res.success)


def fmt(v, n=2):
    return 'None' if v is None else '[' + ', '.join(f'{x:.{n}f}' for x in v) + ']'


def step_query(ck):
    for api, srv, name, show in (
        ('get_robot_system', GetRobotSystem, 'system/get_robot_system',
         lambda r: f'robot_system={r.robot_system} ({ROBOT_SYSTEM.get(r.robot_system, "?")})'),
        ('get_robot_mode', GetRobotMode, 'system/get_robot_mode', lambda r: f'robot_mode={r.robot_mode}'),
        ('get_current_tool', GetCurrentTool, 'tool/get_current_tool', lambda r: f'tool={r.info!r}'),
        ('get_current_tcp', GetCurrentTcp, 'tcp/get_current_tcp', lambda r: f'tcp={r.info!r}'),
    ):
        res, dt = ck.call(srv, name, srv.Request(), retries=2)
        ck.record(api, name, ok_of(res), (show(res) if res else '') + f' ({dt * 1000:.0f} ms)')

    res, dt = ck.call(GetCurrentPosx, 'aux_control/get_current_posx', GetCurrentPosx.Request(ref=DR_BASE), retries=2)
    pos = list(res.task_pos_info[0].data[:6]) if res and res.success and res.task_pos_info else None
    ck.record('get_current_posx (ref=DR_BASE)', 'aux_control/get_current_posx', ok_of(res),
              f'posx={fmt(pos)} ({dt * 1000:.0f} ms)')

    res, dt = ck.call(GetToolForce, 'aux_control/get_tool_force', GetToolForce.Request(ref=DR_BASE), retries=2)
    ck.record('get_tool_force (ref=DR_BASE)', 'aux_control/get_tool_force', ok_of(res),
              f'force={fmt(list(res.tool_force)) if res else None} N·Nm ({dt * 1000:.0f} ms)')


def step_poscond(ck):
    """응답이 success 하나뿐이라, 호출 성공과 조건 결과가 구분되는지 참 · 거짓 조건으로 확인한다."""
    pos = ck.posx()
    if pos is None:
        ck.record('check_position_condition', 'force/check_position_condition', None, 'posx 조회 실패로 건너뜀')
        return
    z = pos[2]
    # 비교값이 어느 성분인지 가리려고 호출 직전 posx 6개를 그대로 남긴다. Virtual 에서 구한 비교값
    # z 179.89 가 홈 posx 의 ry(-179.87)와 0.02 차이라, 위치가 아니라 자세 성분과 비교할 가능성이
    # 있다(yujh5537 리뷰, PR #66)
    ck.record('posx (poscond 직전)', 'aux_control/get_current_posx', True, f'posx={fmt(pos)}')
    # 넓은 범위는 컨트롤러가 비교하는 값이 무엇이든 참이다. 호출 자체가 True를 돌려줄 수 있는지 본다
    for label, lo, hi, expected in (('참 조건', z - 5.0, z + 5.0, True), ('거짓 조건', z + 50.0, z + 60.0, False),
                                    ('넓은 범위', -10000.0, 10000.0, True)):
        req = CheckPositionCondition.Request(axis=DR_AXIS_Z, min=lo, max=hi, ref=DR_BASE,
                                             mode=DR_MV_MOD_ABS, pos=[0.0] * 6)
        res, dt = ck.call(CheckPositionCondition, 'force/check_position_condition', req, retries=2)
        # 결과 칸은 판정이 기대와 맞았는지다
        ck.record(f'check_position_condition ({label})', 'force/check_position_condition',
                  None if res is None else res.success == expected,
                  f'z={z:.2f}, 범위 [{lo:.1f}, {hi:.1f}] → 기대 {expected}, 받음 {res.success if res else None} '
                  f'({dt * 1000:.0f} ms)')


def ensure_autonomous(ck):
    """자동 모드로 바꾼다. (성공 여부, 되돌릴 원래 모드 또는 None)을 돌려준다.

    원래 모드를 돌려주는 이유: 스크립트가 끝난 뒤 로봇이 자동 모드로 남으면 원격 모션 명령이
    계속 먹는 상태로 방치된다. run() 이 finally 에서 되돌린다(ok778ts123 리뷰, PR #66).
    """
    res, _ = ck.call(GetRobotMode, 'system/get_robot_mode', GetRobotMode.Request(), retries=2)
    if res and res.success and res.robot_mode == ROBOT_MODE_AUTONOMOUS:
        return True, None
    # 원래 모드를 읽지 못하면 안전한 쪽(수동)으로 되돌린다. None 이면 restore_mode 가 아무것도 하지 않아
    # 자동 모드로 남는다 — 이 함수가 막으려던 바로 그 상태다(ok778ts123 리뷰, PR #66)
    previous = res.robot_mode if res and res.success else ROBOT_MODE_MANUAL
    res, _ = ck.call(SetRobotMode, 'system/set_robot_mode', SetRobotMode.Request(robot_mode=ROBOT_MODE_AUTONOMOUS))
    ck.record('set_robot_mode (AUTONOMOUS)', 'system/set_robot_mode', ok_of(res),
              f'모션 명령 전 자동 모드 전환 (원래 모드 {previous})')
    return bool(res and res.success), previous


def restore_mode(ck, previous):
    if previous is None:
        return
    res, _ = ck.call(SetRobotMode, 'system/set_robot_mode', SetRobotMode.Request(robot_mode=previous), retries=2)
    ck.record(f'set_robot_mode (원래 모드 {previous})', 'system/set_robot_mode', ok_of(res),
              'finally 에서 되돌림' + ('' if res and res.success else '. 실패 — 펜던트에서 직접 되돌린다'))


def move_home(ck, joint, real):
    # ±180° 밖 관절각이면 현재 자세에 따라 크게 돌 수 있다(#60 · ok778ts123 리뷰).
    # 옛 홈의 J6 −204.84 deg 가 그런 값이었다. 새 홈(v0.1.18)은 −15.14 로 범위 안이다
    if any(abs(j) > 180.0 for j in joint):
        print(f'주의: 홈 관절각 {fmt(joint)} 에 ±180° 밖 값이 있다. 현재 자세에 따라 크게 돌 수 있다.')
        if real:
            # 경고만 찍고 바로 움직이면 반응할 틈이 없다. 실기에서만 한 번 확인받는다
            try:
                answer = input('케이블과 주변을 확인했으면 y 를 누른다 (그 밖은 홈 이동을 건너뛴다): ')
            except EOFError:
                answer = ''
            if answer.strip().lower() != 'y':
                ck.record('move_joint (SYNC, 홈)', 'motion/move_joint', 'skip', '사람이 확인하지 않아 건너뜀')
                return False
    req = MoveJoint.Request(pos=joint, vel=20.0, acc=40.0, time=0.0, radius=0.0, mode=DR_MV_MOD_ABS,
                            blend_type=0, sync_type=SYNC)
    ck.timeout, saved = 60.0, ck.timeout  # 동기 이동은 도착까지 응답하지 않는다
    try:
        res, dt = ck.call(MoveJoint, 'motion/move_joint', req)
    finally:
        ck.timeout = saved
    ck.record('move_joint (SYNC, 홈)', 'motion/move_joint', ok_of(res), f'{fmt(joint)} deg ({dt:.1f} s)')
    return bool(res and res.success)


def step_amovel_stop(ck, args):
    start = ck.posx()
    if start is None:
        ck.record('amovel + move_stop', 'motion/move_line', None, 'posx 조회 실패로 건너뜀')
        return
    req = MoveLine.Request(pos=[0.0, 0.0, args.dz, 0.0, 0.0, 0.0], vel=[args.vel, args.vel],
                           acc=[4 * args.vel, 4 * args.vel], time=0.0, radius=0.0, ref=DR_BASE,
                           mode=DR_MV_MOD_REL, blend_type=0, sync_type=ASYNC)
    res, dt_call = ck.call(MoveLine, 'motion/move_line', req)
    ck.record('amovel (move_line sync_type=ASYNC)', 'motion/move_line', ok_of(res),
              f'+z {args.dz} mm @ {args.vel} mm/s 요청, 응답까지 {dt_call * 1000:.0f} ms')
    if not (res and res.success):
        return
    time.sleep(args.stop_after)
    mid = ck.posx()
    res, dt_stop = ck.call(MoveStop, 'motion/move_stop', MoveStop.Request(stop_mode=DR_QSTOP))
    time.sleep(0.5)
    end1 = ck.posx()
    time.sleep(0.5)
    end2 = ck.posx()
    dz = lambda p: None if p is None or start is None else p[2] - start[2]
    moved, drift = dz(end2), (None if end1 is None or end2 is None else abs(end2[2] - end1[2]))
    stopped_early = moved is not None and 0.0 < moved < args.dz - 1.0 and drift is not None and drift < 0.05
    note = (f'정지 호출 {dt_stop * 1000:.0f} ms. z 변화: 정지 직전 {dz(mid)}, 정지 후 {moved} mm '
            f'(요청 {args.dz}), 정지 후 0.5 s 사이 변화 {drift} mm → '
            + ('도중 정지 확인' if stopped_early else '도중 정지 확인 안 됨'))
    ck.record('motion/move_stop (DR_QSTOP)', 'motion/move_stop', ok_of(res) and stopped_early, note)

    back = MoveLine.Request(pos=start, vel=[args.vel, args.vel], acc=[4 * args.vel, 4 * args.vel], time=0.0,
                            radius=0.0, ref=DR_BASE, mode=DR_MV_MOD_ABS, blend_type=0, sync_type=SYNC)
    ck.timeout, saved = 30.0, ck.timeout
    try:
        res, _ = ck.call(MoveLine, 'motion/move_line', back)
    finally:
        ck.timeout = saved
    print(f'  시작 위치로 복귀: {ok_of(res)}')


def step_compliance_force(ck):
    """순응 → 힘 제어 → 해제. 켜는 호출이 시간 초과여도 상태를 모르므로 해제는 항상 부른다(CLAUDE.md 규칙 2)."""
    try:
        before = ck.force()
        req = TaskComplianceCtrl.Request(stx=[3000.0, 3000.0, 3000.0, 200.0, 200.0, 200.0], ref=DR_BASE, time=0.0)
        res, dt = ck.call(TaskComplianceCtrl, 'force/task_compliance_ctrl', req)
        ck.record('task_compliance_ctrl', 'force/task_compliance_ctrl', ok_of(res),
                  f'stx=[3000,3000,3000,200,200,200] ({dt * 1000:.0f} ms). 직전 force={fmt(before)}')
        if not (res and res.success):
            return
        # 목표 힘 0 N: 호출 경로만 확인한다. 공중에서 0이 아닌 힘을 걸면 로봇이 그 방향으로 움직인다
        req = SetDesiredForce.Request(fd=[0.0] * 6, dir=[0, 0, 1, 0, 0, 0], ref=DR_BASE, time=0.0, mod=DR_FC_MOD_REL)
        p0 = ck.posx()
        res, dt = ck.call(SetDesiredForce, 'force/set_desired_force', req)
        time.sleep(1.0)
        p1, during = ck.posx(), ck.force()
        drift = None if p0 is None or p1 is None else math.dist(p0[:3], p1[:3])
        ck.record('set_desired_force (DR_FC_MOD_REL, fd=0)', 'force/set_desired_force', ok_of(res),
                  f'dir z만 힘 제어 ({dt * 1000:.0f} ms). 1 s 동안 위치 변화 {drift} mm, force={fmt(during)}')
    finally:
        res, dt = ck.call(ReleaseForce, 'force/release_force', ReleaseForce.Request(time=0.0), retries=2)
        ck.record('release_force', 'force/release_force', ok_of(res), f'finally에서 호출 ({dt * 1000:.0f} ms)')
        res, dt = ck.call(ReleaseComplianceCtrl, 'force/release_compliance_ctrl',
                          ReleaseComplianceCtrl.Request(), retries=2)
        ck.record('release_compliance_ctrl', 'force/release_compliance_ctrl', ok_of(res),
                  f'finally에서 호출 ({dt * 1000:.0f} ms)')


def drl_state(ck):
    res, _ = ck.call(GetDrlState, 'drl/get_drl_state', GetDrlState.Request(), retries=2)
    return res.drl_state if res and res.success else None


def step_drl(ck, robot_system):
    before, state0 = ck.force(), drl_state(ck)
    req = DrlStart.Request(robot_system=robot_system, code='set_external_force_reset()\n')
    res, dt = ck.call(DrlStart, 'drl/drl_start', req)
    states = []
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        s = drl_state(ck)
        states.append(s)
        if s == 1 and len(states) > 1:  # STOP
            break
        time.sleep(0.2)
    after = ck.force()
    seq = ' → '.join(DRL_STATE.get(s, str(s)) for s in [state0] + states)
    ck.record('drl_script_run (set_external_force_reset)', 'drl/drl_start', ok_of(res),
              f'robot_system={robot_system} ({dt * 1000:.0f} ms). drl_state {seq}. '
              f'force 전 {fmt(before)} → 후 {fmt(after)}')


def step_gripper(ck, robot_system):
    if robot_system != 1:
        ck.record('/onrobot/sendCommand', GRIPPER_SRV, 'skip', '실기에서는 거부 (탐침 파지 중 열면 떨어진다)')
        return
    for cmd in ('o', 'c'):
        res, dt = ck.call(SetCommand, GRIPPER_SRV, SetCommand.Request(command=cmd))
        ck.record(f'/onrobot/sendCommand ({cmd!r})', GRIPPER_SRV, ok_of(res),
                  f'message={res.message if res else None!r} ({dt * 1000:.0f} ms)')
        time.sleep(0.5)


def run(args, node):
    ck = Checker(node, args.timeout)
    res, _ = ck.call(GetRobotSystem, 'system/get_robot_system', GetRobotSystem.Request(), retries=2)
    if not (res and res.success):
        print('get_robot_system 응답 없음. 브링업과 ROS_DOMAIN_ID를 확인한다.')
        return None
    system = res.robot_system
    print(f'robot_system = {system} ({ROBOT_SYSTEM.get(system, "?")}), steps = {args.steps}\n')

    moving = [s for s in args.steps if s in MOVING_STEPS]
    if moving and system != 1 and not args.real_ok:
        print(f'실기에서 {moving} 단계는 --real-ok 없이 실행하지 않는다.')
        return None

    if 'query' in args.steps:
        step_query(ck)
    if 'poscond' in args.steps:
        step_poscond(ck)
    previous_mode = None
    try:
        if moving and moving != ['gripper']:
            switched, previous_mode = ensure_autonomous(ck)
            if not switched:
                print('자동 모드 전환 실패. 움직이는 단계를 건너뛴다.')
                moving = ['gripper'] if 'gripper' in moving else []
            elif args.move_home and not move_home(ck, args.home_joint, real=system != 1):
                print('홈 이동 실패. 움직이는 단계를 건너뛴다.')
                moving = ['gripper'] if 'gripper' in moving else []
        if 'amovel_stop' in moving:
            step_amovel_stop(ck, args)
        if 'compliance_force' in moving:
            step_compliance_force(ck)
        if 'drl' in moving:
            step_drl(ck, system)
        if 'gripper' in moving:
            step_gripper(ck, system)
    finally:
        restore_mode(ck, previous_mode)
    return ck.rows, system


def main():
    args = parse_args(rclpy.utilities.remove_ros_args(sys.argv)[1:])
    rclpy.init()
    node = rclpy.create_node('check_api_calls')
    try:
        result = run(args, node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
    if result is None:
        return 1
    rows, system = result
    print(f'\n# {time.strftime("%Y-%m-%d %H:%M")} robot_system={ROBOT_SYSTEM.get(system, system)}')
    print('| API | 경로 | 결과 | 비고 |\n|---|---|---|---|')
    for api, path, mark, note in rows:
        print(f'| {api} | `{path}` | {mark} | {note} |')
    return 0 if all(r[2] in ('성공', '건너뜀') for r in rows) else 2


if __name__ == '__main__':
    sys.exit(main())
