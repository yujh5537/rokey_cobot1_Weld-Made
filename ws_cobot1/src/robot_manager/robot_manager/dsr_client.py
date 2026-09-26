"""dsr_controller2 서비스 호출 (T15).

`docs/env/api-check-log.md`(T04)에서 확인한 것:
- 서비스는 `/<ns>/dsr_controller2/...` 아래에 있다. `/dsr01/motion/...`이 아니다.
- `DSR_ROBOT2` Python 래퍼는 응답을 시간 제한 없이 기다려서 실기에서 멈춘 적이 있다(T02).
  그래서 래퍼를 쓰지 않고 서비스를 직접 부르며, 호출마다 시간 제한을 둔다.

이 모듈만 `dsr_msgs2`를 import한다. CI에는 두산 드라이버가 없으므로 순수 계산 모듈과 분리한다.
"""
import math

from dsr_msgs2.srv import (GetCurrentPosx, GetRobotState, GetToolForce, MoveJoint, MoveLine,
                           MoveSplineTask, MoveStop, ReleaseComplianceCtrl, ReleaseForce,
                           SetDesiredForce, TaskComplianceCtrl)
from std_msgs.msg import Float64MultiArray

from robot_manager.paths import SPLINE_MAX_POINTS

DR_BASE = 0
DR_MV_MOD_ABS, DR_MV_MOD_REL = 0, 1
DR_FC_MOD_REL = 1
SYNC, ASYNC = 0, 1
SPLINE_VEL_CONST = 1  # MoveSplineTask.opt: DEFAULT 0 · CONST 1 (경유점 사이에서 속도를 일정하게)
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
    'move_spline': (MoveSplineTask, 'motion/move_spline_task'),   # phase 2 ExecutePath (spline)
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


def _posx_problem(posx):
    return len(posx) != 6 or not all(math.isfinite(v) for v in posx)


def _path_vel_acc(speed_mps, acc_ratio):
    """(vel, acc) [mm/s, mm/s²]. 0 이하 · NaN 은 ValueError (0 속도 이동을 보내지 않는다)."""
    if not (math.isfinite(speed_mps) and speed_mps > 0.0 and math.isfinite(acc_ratio) and acc_ratio > 0.0):
        raise ValueError(f'속도 {speed_mps!r} m/s · 가속 비 {acc_ratio!r} 는 양수여야 한다')
    speed_mm_s = speed_mps * MM_PER_M
    return speed_mm_s, acc_ratio * speed_mm_s


def path_line_request(posx_mm_deg, speed_mps, acc_ratio):
    """ExecutePath line 모드의 한 점: 비동기 절대 직선 이동(amovel).

    `move_line_request` 와 같지만 가속이 `path_acc_ratio` 파라미터를 따른다(계약 6장, 단위 1/s).
    radius 는 0 이다. ASYNC 에서는 드라이버가 radius 를 버리므로 블렌딩을 기대하지 않는다(D31).
    """
    if _posx_problem(posx_mm_deg):
        raise ValueError(f'posx 가 올바르지 않다: {list(posx_mm_deg)!r}')
    speed_mm_s, acc_mm_s2 = _path_vel_acc(speed_mps, acc_ratio)
    return MoveLine.Request(
        pos=list(posx_mm_deg), vel=[speed_mm_s, speed_mm_s], acc=[acc_mm_s2, acc_mm_s2],
        time=0.0, radius=0.0, ref=DR_BASE, mode=DR_MV_MOD_ABS, blend_type=0, sync_type=ASYNC)


def move_spline_request(posx_list, speed_mps, acc_ratio):
    """ExecutePath spline 모드: 경유점 전체를 비동기 spline 한 번으로(amovesx).

    드라이버는 요청을 검사하지 않는다(dsr_controller2.cpp 557~583행, 현지 소스 확인 2026-09-24).
    - `pos_cnt` 가 100 을 넘으면 고정 배열 밖에 쓴다 → 여기서 막는다
    - `pos.at(i)` 로 `pos_cnt` 개를 읽으므로 둘이 다르면 드라이버에서 예외가 난다 → 항상 같게 채운다
    - 각 점의 `data[0..5]` 를 범위 검사 없이 읽는다 → 6 개가 아닌 점을 막는다
    vel · acc 의 두 번째 값(deg/s)은 `move_line_request` 와 같은 규칙으로 같은 숫자를 쓴다.
    """
    points = [list(p) for p in posx_list]
    if not 1 <= len(points) <= SPLINE_MAX_POINTS:
        raise ValueError(f'spline 경유점 {len(points)} 개 (1~{SPLINE_MAX_POINTS})')
    for i, p in enumerate(points):
        if _posx_problem(p):
            raise ValueError(f'spline 경유점 {i} 의 posx 가 올바르지 않다: {p!r}')
    speed_mm_s, acc_mm_s2 = _path_vel_acc(speed_mps, acc_ratio)
    return MoveSplineTask.Request(
        pos=[Float64MultiArray(data=p) for p in points], pos_cnt=len(points),
        vel=[speed_mm_s, speed_mm_s], acc=[acc_mm_s2, acc_mm_s2], time=0.0, ref=DR_BASE,
        mode=DR_MV_MOD_ABS, opt=SPLINE_VEL_CONST, sync_type=ASYNC)


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
