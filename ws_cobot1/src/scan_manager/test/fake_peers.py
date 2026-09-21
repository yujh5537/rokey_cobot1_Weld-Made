"""테스트 안에서 띄우는 가짜 상대 노드: robot_manager · contact_detector · safety_monitor 의 계약 면만 흉내 낸다.

실제 로봇 · 드라이버 · Virtual Mode 와 무관하다. 동작 규칙은 계약(ros-interfaces.md 3.3 · 4.1 · 4.2 · 5.4절)과
열린 PR #72 · #73 의 README 를 따른다.
- /robot/execute_motion: 동시에 1개. 실행 중 · 미연결 · speed <= 0(OP_HOME 제외)이면 goal 을 거절한다.
- /contact/event: DESCEND → CONTACT, SLIDE → EDGE. 발행 시점(Result 앞 · 뒤 · 없음)을 바꿀 수 있다.
- /robot/status: 주기 발행. stamp 는 발행 시각이다.
- 가상 직육면체까지의 거리가 goal 의 max_distance 를 넘으면 REASON_MAX_DISTANCE 로 끝낸다
  (yaml 의 max_descend_m · max_slide_m · 기준점이 상자를 실제로 덮는지 드러난다).
- 상자는 Box 로 받는다. 기본값은 sequence_helpers 의 상수(테스트 안의 가상값)이고,
  **sim.yaml 을 쓰는 시험은 그 yaml 의 sim_box_* 로 만든 Box 를 넘긴다** — 상자가 yaml 과
  따로 놀면 yaml 을 옮겼을 때 "접촉이 없다"로 깨진다(2026-09-21, PR #100).
- FakeParamPeer: 계약 2.4 의 전파 대상(P01~P03)을 흉내 낸다. 계약 파라미터만 선언해 두면 rclpy 가
  /<노드 이름>/set_parameters · get_parameters 를 열어 주므로, scan_manager 가 실제로 쓰는 경로 그대로
  시험할 수 있다. 이름이 계약 이름과 같아야 하므로 노드 이름을 robot_manager · contact_detector ·
  safety_monitor 로 둔다.
가상 직육면체와 정방향 모델은 sequence_helpers 와 같다. 수치는 테스트용 임의값이다.
"""

import math
import threading
import time
from typing import NamedTuple, Tuple

from contact_scan_interfaces.action import ExecuteMotion
from contact_scan_interfaces.msg import ContactEvent
from contact_scan_interfaces.msg import RobotStatus
from contact_scan_interfaces.msg import SafetyStatus
from contact_scan_interfaces.srv import StopRobot
from contact_scan_interfaces.srv import TareForce
from contact_scan_qos import QOS_EVENT
from contact_scan_qos import QOS_STATE
from rcl_interfaces.msg import SetParametersResult
from rclpy.action import ActionServer
from rclpy.action import CancelResponse
from rclpy.action import GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.node import Node
from scan_manager import geometry_adapter
from scan_manager.contract_enums import Direction
from scan_manager.contract_enums import Operation
from sequence_helpers import BOX_BOTTOM_Z
from sequence_helpers import BOX_CENTER
from sequence_helpers import BOX_SIZE
from sequence_helpers import DOWN
from sequence_helpers import edge_coordinate
from sequence_helpers import HOME_POSITION
from sequence_helpers import SIGN
from sequence_helpers import VALUES
from sequence_helpers import Z_DROP_M

STATUS_PERIOD_S = 0.02
FRAME = 'base_link'

NORMAL = 'normal'
MAX_DISTANCE = 'max_distance'      # 접촉 · 소실 없이 끝까지 간다
HOLD = 'hold'                      # /robot/stop 이나 cancel 이 올 때까지 움직인다
ROBOT_ERROR = 'robot_error'
EVENT_AFTER = 'event_after'        # 이벤트가 Result 보다 늦게 온다
EVENT_NEVER = 'event_never'        # Result 는 event_id 를 가리키는데 이벤트가 끝내 오지 않는다
STRAY_EVENT = 'stray_event'        # motion_id 가 다른 이벤트가 먼저 끼어든다
HOLD_THEN_OVER_FORCE = 'hold_then_over_force'   # 정지 요청이 올 때까지 움직이다가 과대 외력으로 끝난다

NO_POSE = 'no_pose'                # 실패로 끝나면서 Result.pose 를 채우지 못했다(pose_stamp = 0)
EVENT_WRONG_FRAME = 'event_wrong_frame'    # 이벤트의 frame_id 가 Base 가 아니다
RESULT_WRONG_FRAME = 'result_wrong_frame'  # Result 의 frame_id 가 Base 가 아니다

MODEL_KEYS = ('detect_latency_s', 'tip_radius_m', 'edge_round_radius_m', 'edge_bias_offset_m')

# 전파 대상 노드의 출발값. 실제 yaml 과 같은 이름이고, 값은 테스트용이다.
# over_force_n 과 drop_limit_m 은 두 노드가 같은 값으로 시작한다(계약 7.2).
PEER_PARAMS = {
    'safety_monitor': {'over_force_n': 30.0, 'drop_limit_m': 0.005},
    'contact_detector': {
        'contact_threshold_n': 3.0, 'edge_drop_m': 0.0005, 'debounce_n': 3, 'over_force_n': 30.0},
    'robot_manager': {'slide_target_force_n': 3.0, 'drop_limit_m': 0.005},
}


class FakeParamPeer(Node):
    """계약 파라미터만 들고 있는 가짜 노드. 전파(P01~P03)의 상대 역할만 한다.

    reject: 이 이름들은 범위 밖으로 보고 거절한다(상대 노드의 on_set_parameters 가 거절하는 경우).
    delay_s: set_parameters 응답을 이만큼 늦춘다(응답 지연 · 사실상 무응답).
    """

    def __init__(self, name, values=None, reject=(), delay_s=0.0):
        super().__init__(name)
        self.reject = set(reject)
        self.delay_s = delay_s
        self.set_calls = []            # 받은 (이름, 값) 목록
        self.first_set_s = None        # 처음 받은 시각. 노드 사이의 전파 순서를 본다
        for param, value in (values or PEER_PARAMS[name]).items():
            self.declare_parameter(param, value)
        self.add_on_set_parameters_callback(self._on_set)

    def _on_set(self, params):
        if self.delay_s:
            time.sleep(self.delay_s)
        if self.first_set_s is None:
            self.first_set_s = time.monotonic()
        self.set_calls.extend((p.name, p.value) for p in params)
        refused = sorted(p.name for p in params if p.name in self.reject)
        if refused:
            return SetParametersResult(
                successful=False, reason=f'{", ".join(refused)} 가 범위 밖이다')
        return SetParametersResult(successful=True)

    def value(self, name):
        return self.get_parameter(name).value


def param_peers(names=('safety_monitor', 'contact_detector', 'robot_manager'), **kwargs):
    """전파 대상 3개(또는 그 일부). 빠진 이름은 "그 노드가 안 떠 있다"가 된다."""
    return {name: FakeParamPeer(name, **kwargs.get(name, {})) for name in names}


class Box(NamedTuple):
    """가짜 로봇이 만지는 가상 직육면체. 기본값은 sequence_helpers 의 상수다."""

    center_xy: Tuple[float, float] = BOX_CENTER
    size: Tuple[float, float, float] = BOX_SIZE
    bottom_z: float = BOX_BOTTOM_Z

    @property
    def top_z(self) -> float:
        return self.bottom_z + self.size[2]

    @classmethod
    def from_sim_yaml(cls, contact_detector_params) -> 'Box':
        """sim.yaml 의 contact_detector 절에서 만든다. 실제 sim 입력원과 같은 상자가 된다."""
        origin = contact_detector_params['sim_box_origin_m']
        size = tuple(contact_detector_params['sim_box_size_m'])
        return cls(center_xy=(origin[0], origin[1]), size=size, bottom_z=origin[2])


def key(operation, direction=Direction.NONE):
    return (int(operation), int(direction))


class FakePeers(Node):

    def __init__(self, model=None, box=None):
        """model: 정방향 모델의 값(MODEL_KEYS). scan_manager 의 보정 파라미터와 같아야 치수가 복원된다.

        box: 만질 가상 직육면체. 기본값은 테스트 안의 상수다. sim.yaml 로 띄우는 시험은
             Box.from_sim_yaml(...) 로 **그 yaml 의 상자**를 넘긴다.
        """
        super().__init__('fake_peers')
        self.model = {name: (model or VALUES)[name] for name in MODEL_KEYS}
        self.box = box or Box()
        group = ReentrantCallbackGroup()
        self.behavior = {}             # key(op, dir) → 위의 상수
        self.hold_goal = None          # n 번째로 수락한 goal 을 HOLD 로 돌린다(같은 operation 이 여러 번 나올 때)
        self.connected = True
        self.latched = False
        self.safety_code = 0
        self.tare_error = 0            # 0 이 아니면 그 코드로 실패한다
        self.latch_during_tare = 0     # 0 이 아니면 tare 도중에 그 코드로 안전 래치가 걸린다(모션 사이의 래치)
        self.reject_operations = set() # 이 operation 의 goal 은 거절한다
        self.slow_accept = {}          # operation → goal 응답을 이만큼(s) 늦게 돌려준다
        self.goals = []                # 수락한 goal
        self.rejected = 0
        self.stop_requests = []
        self.cancel_count = 0
        self.tare_requests = []
        self.position = HOME_POSITION
        self._busy = threading.Lock()
        self._moving = False
        self._halt = threading.Event()
        self._event_id = 100
        self._events = self.create_publisher(ContactEvent, '/contact/event', QOS_EVENT)
        self._status = self.create_publisher(RobotStatus, '/robot/status', QOS_STATE)
        self._safety = self.create_publisher(SafetyStatus, '/safety/status', QOS_STATE)
        self.publish_status = True
        self.publish_safety = True
        self._timer = self.create_timer(STATUS_PERIOD_S, self._publish, callback_group=group)
        self._server = ActionServer(
            self, ExecuteMotion, '/robot/execute_motion', self._execute, callback_group=group,
            goal_callback=self._on_goal, cancel_callback=self._on_cancel)
        self.create_service(StopRobot, '/robot/stop', self._on_stop, callback_group=group)
        self.create_service(TareForce, '/contact/tare', self._on_tare, callback_group=group)

    def quiet(self):
        """정리 전에 부른다. 주기 발행을 멈추고 돌고 있던 콜백이 끝나기를 잠깐 기다린다.

        executor 를 내리는 순간에 50 Hz 타이머 콜백이 돌고 있으면 rclpy 가 "exception was never retrieved" 를 남긴다.
        """
        self._timer.cancel()
        self._halt.set()
        time.sleep(3 * STATUS_PERIOD_S)

    def destroy_node(self):
        self._halt.set()
        self._server.destroy()
        return super().destroy_node()

    # -- 상태 --

    def _publish(self):
        now = self.get_clock().now().to_msg()
        if self.publish_status:
            self._status.publish(RobotStatus(
                stamp=now, connected=self.connected, moving=self._moving))
        if self.publish_safety:
            self._safety.publish(SafetyStatus(
                stamp=now, latched=self.latched, reason_code=self.safety_code,
                level=SafetyStatus.LEVEL_STOP if self.latched else SafetyStatus.LEVEL_OK))

    # -- /robot/stop · /contact/tare --

    def _on_stop(self, request, response):
        self.stop_requests.append(request)
        self._halt.set()
        response.accepted = True
        return response

    def _on_tare(self, request, response):
        self.tare_requests.append(request)
        if self.latch_during_tare:
            self.latched, self.safety_code = True, self.latch_during_tare
            time.sleep(10 * STATUS_PERIOD_S)  # 래치가 /safety/status 로 나간 뒤에 응답한다
        response.success = not self.tare_error
        response.error = self.tare_error
        response.detail = 'fake tare failure' if self.tare_error else ''
        response.sample_count = 50
        response.baseline_norm_n = 2.4
        response.std_norm_n = 0.3
        return response

    # -- /robot/execute_motion --

    def _on_goal(self, goal):
        time.sleep(self.slow_accept.get(int(goal.operation), 0.0))
        invalid = goal.operation != Operation.HOME and goal.speed <= 0.0
        refused = goal.operation in self.reject_operations
        if not self.connected or invalid or refused or self._busy.locked():
            self.rejected += 1
            return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def _on_cancel(self, _handle):
        self.cancel_count += 1
        self._halt.set()
        return CancelResponse.ACCEPT

    def _execute(self, handle):
        goal = handle.request
        with self._busy:
            self.goals.append(goal)
            self._halt.clear()
            self._moving = True
            try:
                result = self._run(goal)
            finally:
                self._moving = False
        if handle.is_cancel_requested:
            handle.canceled()
        elif result.reason in (
                ExecuteMotion.Result.REASON_TARGET_REACHED, ExecuteMotion.Result.REASON_CONTACT,
                ExecuteMotion.Result.REASON_EDGE):
            handle.succeed()
        else:
            handle.abort()
        return result

    def _result(self, reason, reason_code=0, event_id=0, detail=''):
        result = ExecuteMotion.Result()
        result.reason = reason
        result.reason_code = reason_code
        result.detail = detail
        result.event_id = event_id
        result.frame_id = FRAME
        result.pose_stamp = self.get_clock().now().to_msg()
        result.compliance_released = True
        p, q = result.pose.position, result.pose.orientation
        p.x, p.y, p.z = self.position
        q.x, q.y, q.z, q.w = DOWN
        return result

    def _run(self, goal):
        R = ExecuteMotion.Result
        behavior = self.behavior.get(key(goal.operation, goal.direction), NORMAL)
        if self.hold_goal == len(self.goals):
            behavior = HOLD
        if behavior == NO_POSE:
            result = self._result(R.REASON_ROBOT_ERROR, 204, detail='fake: pose unknown')
            result.pose, result.frame_id = type(result.pose)(), ''
            result.pose_stamp.sec = result.pose_stamp.nanosec = 0
            return result
        if behavior == RESULT_WRONG_FRAME:
            result = self._result(R.REASON_TARGET_REACHED)
            result.frame_id = 'workpiece_fixture'
            return result
        if behavior == ROBOT_ERROR:
            return self._result(R.REASON_ROBOT_ERROR, 204, detail='fake driver error')
        if behavior == HOLD_THEN_OVER_FORCE:
            while not self._halt.wait(0.005):
                pass
            return self._result(R.REASON_OVER_FORCE, 400, detail='fake over force while stopping')
        if behavior == HOLD:
            while not self._halt.wait(0.005):
                pass
            # 실제 robot_manager 는 먼저 온 것으로 정지한다. 여기서는 scan_manager 가 /robot/stop 과 cancel 을
            # **둘 다** 보냈는지 보려고, 나머지 하나가 도착할 때까지 잠깐 기다린다(끝난 goal 의 cancel 은 콜백이 불리지 않는다).
            deadline = time.monotonic() + 2.0
            while not (self.stop_requests and self.cancel_count) and time.monotonic() < deadline:
                time.sleep(0.005)
            return self._result(R.REASON_STOP_REQUESTED, 200)
        if goal.operation == Operation.MOVE_TO:
            t = goal.target.position
            self.position = (t.x, t.y, t.z)
            return self._result(R.REASON_TARGET_REACHED)
        if goal.operation == Operation.HOME:
            self.position = HOME_POSITION
            return self._result(R.REASON_TARGET_REACHED)

        x, y, z = self.position
        descend = goal.operation == Operation.DESCEND
        if behavior == MAX_DISTANCE:
            if descend:
                self.position = (x, y, z - goal.max_distance)
            else:
                moved = [x, y, z]
                moved[geometry_adapter.AXIS[Direction(goal.direction)]] += (
                    SIGN[Direction(goal.direction)] * goal.max_distance)
                self.position = tuple(moved)
            return self._result(R.REASON_MAX_DISTANCE, 300 if descend else 301)

        latency, r = self.model['detect_latency_s'], self.model['tip_radius_m']
        if descend:
            detected = (x, y, self.box.top_z - goal.speed * latency)
            if z - detected[2] > goal.max_distance:   # 상자 윗면이 max_descend_m 보다 멀다
                self.position = (x, y, z - goal.max_distance)
                return self._result(R.REASON_MAX_DISTANCE, 300)
            self.position = (x, y, detected[2] - 0.0002)
            event_type, z_drop = ContactEvent.TYPE_CONTACT, None
        else:
            direction = Direction(goal.direction)
            axis = geometry_adapter.AXIS[direction]
            reach = r + self.model['edge_round_radius_m']
            d = reach if Z_DROP_M >= reach else math.sqrt(2 * reach * Z_DROP_M - Z_DROP_M ** 2)
            overshoot = (d - self.model['edge_round_radius_m'] + goal.speed * latency
                         + self.model['edge_bias_offset_m'])
            detected = [x, y, z - Z_DROP_M]
            detected[axis] = (edge_coordinate(direction, self.box.center_xy, self.box.size)
                              + SIGN[direction] * overshoot)
            if abs(detected[axis] - self.position[axis]) > goal.max_distance:   # 모서리가 max_slide_m 보다 멀다
                moved = [x, y, z]
                moved[axis] += SIGN[direction] * goal.max_distance
                self.position = tuple(moved)
                return self._result(R.REASON_MAX_DISTANCE, 301)
            stopped = list(detected)
            stopped[axis] += SIGN[direction] * 0.0004
            self.position, detected = tuple(stopped), tuple(detected)
            event_type, z_drop = ContactEvent.TYPE_EDGE, Z_DROP_M

        self._event_id += 1
        event = self._event(goal, event_type, detected, z_drop, self._event_id)
        if behavior == STRAY_EVENT:
            stray = self._event(goal, event_type, (9.0, 9.0, 9.0), z_drop, self._event_id + 1000)
            stray.motion_id = goal.motion_id + 100
            self._events.publish(stray)
            unknown = self._event(goal, event_type, (8.0, 8.0, 8.0), z_drop, self._event_id + 2000)
            unknown.motion_id = 0
            self._events.publish(unknown)
        if behavior == EVENT_WRONG_FRAME:
            event.frame_id = 'workpiece_fixture'
        if behavior == EVENT_AFTER:
            threading.Timer(0.15, self._events.publish, args=(event,)).start()
        elif behavior != EVENT_NEVER:
            self._events.publish(event)
            time.sleep(0.02)  # 실제로는 이벤트를 받고 정지한 뒤에 Result 가 나온다
        reason = R.REASON_CONTACT if descend else R.REASON_EDGE
        return self._result(reason, event_id=self._event_id)

    def _event(self, goal, event_type, position, z_drop, event_id):
        now = self.get_clock().now().to_msg()
        event = ContactEvent()
        event.event_id = event_id
        event.scan_id = goal.scan_id
        event.motion_id = goal.motion_id
        event.sample_id = 5000 + event_id
        event.type = event_type
        event.source = 'sim'
        event.frame_id = FRAME
        event.pose.position.x, event.pose.position.y, event.pose.position.z = position
        q = event.pose.orientation
        q.x, q.y, q.z, q.w = DOWN
        event.pose_stamp = event.force_stamp = event.detect_stamp = now
        event.force_delta_n = 3.3
        event.z_drop_m = math.nan if z_drop is None else z_drop
        event.z_drop_valid = z_drop is not None
        event.debounce_count = 3
        return event
