"""weld_manager 노드 시험용 가짜 상대: robot_manager · safety_monitor · scan_manager 의 계약 면만 흉내 낸다.

실제 로봇 · 드라이버 · Virtual Mode 와 무관하다. 수치는 시험용 임의값이다.
- /robot/execute_motion · /robot/execute_path: goal 을 받은 순서(1 부터, 두 서버 합쳐)대로 script 를 본다.
  script[n] = 'hold'  → /robot/stop 이 오거나 취소될 때까지 붙잡고 있다가 STOP_REQUESTED · CANCELED 로 끝낸다
  script[n] = (reason, reason_code) → 그 사유로 곧바로 끝낸다
  없으면 목표에 도착한다(MOVE_TO = target, PATH = 마지막 경유점, HOME = HOME_POSE)
- /robot/stop: 요청을 적어 두고 붙잡은 goal 을 풀어 준다.
- /robot/status · /robot/sample · /safety/status · /scan/state: 주기 발행. 값은 속성으로 바꾼다.
"""

import threading

from builtin_interfaces.msg import Time
from contact_scan_interfaces.action import ExecuteMotion
from contact_scan_interfaces.action import ExecutePath
from contact_scan_interfaces.msg import RobotSample
from contact_scan_interfaces.msg import RobotStatus
from contact_scan_interfaces.msg import SafetyStatus
from contact_scan_interfaces.msg import ScanState
from contact_scan_interfaces.srv import StopRobot
from contact_scan_qos import QOS_SENSOR
from contact_scan_qos import QOS_STATE
from geometry_msgs.msg import Pose
from rclpy.action import ActionServer
from rclpy.action import CancelResponse
from rclpy.action import GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.node import Node

HOME_POSE = ((0.425, -0.184, 0.60), (0.0, 1.0, 0.0, 0.0))    # 부재 위 높은 곳, 수직
R = ExecuteMotion.Result


def _pose(position, orientation):
    pose = Pose()
    pose.position.x, pose.position.y, pose.position.z = position
    pose.orientation.x, pose.orientation.y, pose.orientation.z, pose.orientation.w = orientation
    return pose


class FakePeers(Node):

    def __init__(self, script=None, with_path_server=True):
        super().__init__('fake_peers')
        self.script = dict(script or {})
        self.goals = []                 # (kind, goal) 받은 순서대로. kind = 'MOVE_TO' | 'HOME' | 'PATH'
        self.stop_requests = []
        self.position, self.orientation = HOME_POSE
        self.connected, self.latched, self.latch_code = True, False, 0
        self.scan_phase = ScanState.PHASE_DONE
        self.publish_scan_state = True
        self.publish_sample = True
        self.force = (0.0, 0.0, 1.5)
        self._stop = threading.Event()
        self._lock = threading.Lock()
        group = ReentrantCallbackGroup()
        self._servers = [ActionServer(
            self, ExecuteMotion, '/robot/execute_motion', execute_callback=self._execute_motion,
            goal_callback=lambda _g: GoalResponse.ACCEPT, cancel_callback=lambda _h: CancelResponse.ACCEPT,
            callback_group=group)]
        if with_path_server:
            self._servers.append(ActionServer(
                self, ExecutePath, '/robot/execute_path', execute_callback=self._execute_path,
                goal_callback=lambda _g: GoalResponse.ACCEPT, cancel_callback=lambda _h: CancelResponse.ACCEPT,
                callback_group=group))
        self.create_service(StopRobot, '/robot/stop', self._on_stop, callback_group=group)
        self._status_pub = self.create_publisher(RobotStatus, '/robot/status', QOS_STATE)
        self._sample_pub = self.create_publisher(RobotSample, '/robot/sample', QOS_SENSOR)
        self._safety_pub = self.create_publisher(SafetyStatus, '/safety/status', QOS_STATE)
        self._scan_pub = self.create_publisher(ScanState, '/scan/state', QOS_STATE)
        self._sample_id = 0
        self.create_timer(0.05, self._publish, callback_group=group)

    # ---- 발행 ----

    def _now(self) -> Time:
        return self.get_clock().now().to_msg()

    def _publish(self):
        now = self._now()
        self._status_pub.publish(RobotStatus(stamp=now, connected=self.connected, moving=False))
        self._safety_pub.publish(SafetyStatus(stamp=now, latched=self.latched, reason_code=self.latch_code,
                                              level=SafetyStatus.LEVEL_STOP if self.latched else 0))
        if self.publish_scan_state:
            self._scan_pub.publish(ScanState(stamp=now, phase=self.scan_phase))
        if self.publish_sample:
            self._sample_id += 1
            sample = RobotSample(sample_id=self._sample_id, frame_id='base_link', valid=True,
                                 pose=_pose(self.position, self.orientation), pose_stamp=now, force_stamp=now)
            sample.wrench.force.x, sample.wrench.force.y, sample.wrench.force.z = self.force
            self._sample_pub.publish(sample)

    # ---- 모션 ----

    def _take(self, kind, goal):
        with self._lock:
            self.goals.append((kind, goal))
            return len(self.goals)

    def _finish(self, handle, result_type, reason, code, position, orientation, detail=''):
        self.position, self.orientation = position, orientation
        result = result_type.Result(reason=reason, reason_code=code, detail=detail, frame_id='base_link',
                                    pose=_pose(position, orientation), pose_stamp=self._now())
        if reason == R.REASON_TARGET_REACHED:
            handle.succeed()
        elif reason == R.REASON_CANCELED:
            handle.canceled()
        else:
            handle.abort()
        return result

    def _run(self, handle, result_type, n, target, orientation):
        action = self.script.get(n)
        if action == 'hold':
            while not (self._stop.is_set() or handle.is_cancel_requested):
                self._stop.wait(0.02)
            self._stop.clear()
            reason = R.REASON_STOP_REQUESTED if not handle.is_cancel_requested else R.REASON_CANCELED
            code = 200 if reason == R.REASON_STOP_REQUESTED else 201
            # 멈춘 자리: 출발점과 목표의 가운데쯤(시험용)
            middle = tuple((a + b) / 2 for a, b in zip(self.position, target))
            return self._finish(handle, result_type, reason, code, middle, orientation, '시험: 붙잡았다가 정지')
        if isinstance(action, tuple):
            reason, code = action
            return self._finish(handle, result_type, reason, code, self.position, self.orientation, '시험: 대본')
        return self._finish(handle, result_type, R.REASON_TARGET_REACHED, 0, target, orientation)

    def _execute_motion(self, handle):
        goal = handle.request
        kind = 'HOME' if goal.operation == 4 else 'MOVE_TO'
        n = self._take(kind, goal)
        if kind == 'HOME':
            target, orientation = HOME_POSE
        else:
            p, q = goal.target.position, goal.target.orientation
            target, orientation = (p.x, p.y, p.z), (q.x, q.y, q.z, q.w)
        return self._run(handle, ExecuteMotion, n, target, orientation)

    def _execute_path(self, handle):
        goal = handle.request
        n = self._take('PATH', goal)
        last = goal.waypoints[-1]
        target = (last.position.x, last.position.y, last.position.z)
        q = last.orientation
        feedback = ExecutePath.Feedback(distance_travelled=0.05, waypoint_index=1, frame_id='base_link')
        handle.publish_feedback(feedback)
        return self._run(handle, ExecutePath, n, target, (q.x, q.y, q.z, q.w))

    def _on_stop(self, request, response):
        self.stop_requests.append(request)
        self._stop.set()
        response.accepted = True
        return response

    def kinds(self):
        with self._lock:
            return [kind for kind, _ in self.goals]
