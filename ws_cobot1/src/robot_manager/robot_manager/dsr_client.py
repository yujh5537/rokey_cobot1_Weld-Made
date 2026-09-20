"""dsr_controller2 서비스 호출 (T15).

`docs/env/api-check-log.md`(T04)에서 확인한 것:
- 서비스는 `/<ns>/dsr_controller2/...` 아래에 있다. `/dsr01/motion/...`이 아니다.
- `DSR_ROBOT2` Python 래퍼는 응답을 시간 제한 없이 기다려서 실기에서 멈춘 적이 있다(T02).
  그래서 래퍼를 쓰지 않고 서비스를 직접 부르며, 호출마다 시간 제한을 둔다.

이 모듈만 `dsr_msgs2`를 import한다. CI에는 두산 드라이버가 없으므로 순수 계산 모듈과 분리한다.
"""
from dsr_msgs2.srv import GetCurrentPosx, GetRobotState, GetToolForce

DR_BASE = 0

# GetRobotState.srv: 0 INITIALIZING · 1 STANDBY · 2 MOVING · 3 SAFE_OFF
STATE_MOVING = 2

SERVICES = {
    'posx': (GetCurrentPosx, 'aux_control/get_current_posx'),
    'force': (GetToolForce, 'aux_control/get_tool_force'),
    'state': (GetRobotState, 'system/get_robot_state'),
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
