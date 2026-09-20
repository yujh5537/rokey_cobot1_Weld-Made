"""dsr_controller2 서비스 호출 (T15).

`docs/env/api-check-log.md`(T04)에서 확인한 것:
- 서비스는 `/<ns>/dsr_controller2/...` 아래에 있다. `/dsr01/motion/...`이 아니다.
- `DSR_ROBOT2` Python 래퍼는 응답을 시간 제한 없이 기다려서 실기에서 멈춘 적이 있다(T02).
  그래서 래퍼를 쓰지 않고 서비스를 직접 부르며, 호출마다 시간 제한을 둔다.

이 모듈만 `dsr_msgs2`를 import한다. CI에는 두산 드라이버가 없으므로 순수 계산 모듈과 분리한다.
"""
from dsr_msgs2.srv import (GetCurrentPosx, GetRobotState, GetToolForce, MoveJoint, MoveLine,
                           MoveStop, ReleaseComplianceCtrl, ReleaseForce, SetDesiredForce,
                           TaskComplianceCtrl)

DR_BASE = 0
DR_MV_MOD_ABS, DR_MV_MOD_REL = 0, 1
DR_FC_MOD_REL = 1
SYNC, ASYNC = 0, 1
DR_QSTOP = 1          # DR_common2.py: QSTOP_STO 0 · QSTOP 1 · SSTOP 2 · HOLD 3
MM_PER_M = 1000.0

# GetRobotState.srv: 0 INITIALIZING · 1 STANDBY · 2 MOVING · 3 SAFE_OFF
STATE_MOVING = 2

SERVICES = {
    'posx': (GetCurrentPosx, 'aux_control/get_current_posx'),
    'force': (GetToolForce, 'aux_control/get_tool_force'),
    'state': (GetRobotState, 'system/get_robot_state'),
    'move_line': (MoveLine, 'motion/move_line'),
    'move_joint': (MoveJoint, 'motion/move_joint'),
    'move_stop': (MoveStop, 'motion/move_stop'),
    'compliance_on': (TaskComplianceCtrl, 'force/task_compliance_ctrl'),
    'compliance_off': (ReleaseComplianceCtrl, 'force/release_compliance_ctrl'),
    'force_on': (SetDesiredForce, 'force/set_desired_force'),
    'force_off': (ReleaseForce, 'force/release_force'),
}


def prefix(namespace):
    return f'/{namespace.strip("/")}/dsr_controller2/'


def make_clients(node, namespace):
    """{이름: rclpy Client}. 콜백 그룹은 호출자가 노드에서 정한다."""
    return {name: node.create_client(srv_type, prefix(namespace) + path)
            for name, (srv_type, path) in SERVICES.items()}


def posx_request():
    return GetCurrentPosx.Request(ref=DR_BASE)


def force_request():
    return GetToolForce.Request(ref=DR_BASE)


def state_request():
    return GetRobotState.Request()


def read_posx(response):
    """응답에서 posx [mm, deg] 6개를 꺼낸다. 실패하면 None (0으로 채우지 않는다)."""
    if not (response and response.success and response.task_pos_info):
        return None
    values = list(response.task_pos_info[0].data[:6])
    return values if len(values) == 6 else None


def read_force(response):
    if not (response and response.success):
        return None
    values = list(response.tool_force[:6])
    return values if len(values) == 6 else None


def read_moving(response):
    """(connected, moving). 응답이 없으면 (False, None)."""
    if not (response and response.success):
        return False, None
    return True, response.robot_state == STATE_MOVING


def move_line_request(posx_mm_deg, speed_mps, relative):
    """비동기 직선 이동(amovel). 속도는 m/s → mm/s.

    `sync_type=ASYNC`라 서비스는 바로 응답한다. 도착은 따로 확인한다(BRD 4.2.3).
    """
    speed_mm_s = speed_mps * MM_PER_M
    return MoveLine.Request(
        pos=list(posx_mm_deg), vel=[speed_mm_s, speed_mm_s], acc=[4 * speed_mm_s, 4 * speed_mm_s],
        time=0.0, radius=0.0, ref=DR_BASE,
        mode=DR_MV_MOD_REL if relative else DR_MV_MOD_ABS, blend_type=0, sync_type=ASYNC)


def move_joint_request(joint_deg, vel_deg_s):
    return MoveJoint.Request(pos=list(joint_deg), vel=vel_deg_s, acc=2 * vel_deg_s, time=0.0,
                             radius=0.0, mode=DR_MV_MOD_ABS, blend_type=0, sync_type=ASYNC)


def move_stop_request():
    return MoveStop.Request(stop_mode=DR_QSTOP)


def compliance_on_request(stiffness):
    return TaskComplianceCtrl.Request(stx=list(stiffness), ref=DR_BASE, time=0.0)


def compliance_off_request():
    return ReleaseComplianceCtrl.Request()


def force_on_request(target_force_n):
    """-z 로 누르는 힘. 방향은 z 만 힘 제어, 나머지는 순응 제어."""
    return SetDesiredForce.Request(fd=[0.0, 0.0, -abs(target_force_n), 0.0, 0.0, 0.0],
                                   dir=[0, 0, 1, 0, 0, 0], ref=DR_BASE, time=0.0, mod=DR_FC_MOD_REL)


def force_off_request(transition_s=0.3):
    """힘 제어 해제.

    `time` 은 강성 제어로 넘어가는 전환 시간 [s] (0~1.0). **0 이면 즉시 전환이다.**
    두산 매뉴얼 5.1.4 알아두기: 해제 시 참조 외력이 센서값으로 바뀌므로
    `DR_FC_MOD_REL` 을 쓴 경우 그 순간 참조 외력이 점프한다. EDGE 로 멈춘 직후
    탐침이 모서리에 걸쳐 있는 상태에서 순응 제어가 그 점프에 반응하면 튀거나 더
    눌릴 수 있다. 매뉴얼 예제도 `release_force(0.5)` 를 쓴다 (현지 리뷰, PR #73).
    """
    return ReleaseForce.Request(time=float(transition_s))


def succeeded(response):
    return bool(response is not None and getattr(response, 'success', False))
