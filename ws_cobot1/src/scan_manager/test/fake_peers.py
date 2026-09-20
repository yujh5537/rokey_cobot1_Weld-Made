"""테스트 안에서 띄우는 가짜 상대 노드: robot_manager · contact_detector · safety_monitor 의 계약 면만 흉내 낸다.

실제 로봇 · 드라이버 · Virtual Mode 와 무관하다. 동작 규칙은 계약(ros-interfaces.md 3.3 · 4.1 · 4.2 · 5.4절)과
열린 PR #72 · #73 의 README 를 따른다.
- /robot/execute_motion: 동시에 1개. 실행 중 · 미연결 · speed <= 0(OP_HOME 제외)이면 goal 을 거절한다.
- /contact/event: DESCEND → CONTACT, SLIDE → EDGE. 발행 시점(Result 앞 · 뒤 · 없음)을 바꿀 수 있다.
- /robot/status: 주기 발행. stamp 는 발행 시각이다.
가상 직육면체와 정방향 모델은 sequence_helpers 와 같다. 수치는 테스트용 임의값이다.
"""

import math
import threading
import time

from contact_scan_interfaces.action import ExecuteMotion
from contact_scan_interfaces.msg import ContactEvent
from contact_scan_interfaces.msg import RobotStatus
from contact_scan_interfaces.msg import SafetyStatus
from contact_scan_interfaces.srv import StopRobot
from contact_scan_interfaces.srv import TareForce
from contact_scan_qos import QOS_EVENT
from contact_scan_qos import QOS_STATE
from rclpy.action import ActionServer
from rclpy.action import CancelResponse
from rclpy.action import GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.node import Node
from scan_manager import geometry_adapter
from scan_manager.contract_enums import Direction
from scan_manager.contract_enums import Operation
from sequence_helpers import BOX_BOTTOM_Z
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


def key(operation, direction=Direction.NONE):
    return (int(operation), int(direction))


class FakePeers(Node):

    def __init__(self):
        super().__init__('fake_peers')
        group = ReentrantCallbackGroup()
        self.behavior = {}             # key(op, dir) → 위의 상수
        self.connected = True
        self.latched = False
        self.safety_code = 0
        self.tare_error = 0            # 0 이 아니면 그 코드로 실패한다
        self.reject_operations = set() # 이 operation 의 goal 은 거절한다
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
        self.create_timer(STATUS_PERIOD_S, self._publish, callback_group=group)
        self._server = ActionServer(
            self, ExecuteMotion, '/robot/execute_motion', self._execute, callback_group=group,
            goal_callback=self._on_goal, cancel_callback=self._on_cancel)
        self.create_service(StopRobot, '/robot/stop', self._on_stop, callback_group=group)
        self.create_service(TareForce, '/contact/tare', self._on_tare, callback_group=group)

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
        response.success = not self.tare_error
        response.error = self.tare_error
        response.detail = 'fake tare failure' if self.tare_error else ''
        response.sample_count = 50
        response.baseline_norm_n = 2.4
        response.std_norm_n = 0.3
        return response

    # -- /robot/execute_motion --

    def _on_goal(self, goal):
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
        if behavior == ROBOT_ERROR:
            return self._result(R.REASON_ROBOT_ERROR, 204, detail='fake driver error')
        if behavior == HOLD:
            while not self._halt.wait(0.005):
                pass
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

        latency, r = VALUES['detect_latency_s'], VALUES['tip_radius_m']
        if descend:
            detected = (x, y, BOX_BOTTOM_Z + BOX_SIZE[2] - goal.speed * latency)
            self.position = (x, y, detected[2] - 0.0002)
            event_type, z_drop = ContactEvent.TYPE_CONTACT, None
        else:
            direction = Direction(goal.direction)
            axis = geometry_adapter.AXIS[direction]
            reach = r + VALUES['edge_round_radius_m']
            d = reach if Z_DROP_M >= reach else math.sqrt(2 * reach * Z_DROP_M - Z_DROP_M ** 2)
            overshoot = (d - VALUES['edge_round_radius_m'] + goal.speed * latency
                         + VALUES['edge_bias_offset_m'])
            detected = [x, y, z - Z_DROP_M]
            detected[axis] = edge_coordinate(direction) + SIGN[direction] * overshoot
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
