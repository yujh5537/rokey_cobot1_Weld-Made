"""robot_manager 노드: 샘플 · 상태 발행(T15)과 ExecuteMotion(T13).

계약 `docs/contracts/ros-interfaces.md` 3.1 · 3.2 · 5.4절, BRD 4.1.6 · 4.2.1~4.2.3 · 4.2.6.

- `/robot/sample` (QOS_SENSOR): TCP pose와 외력. **취득 시각을 각각 따로** 싣는다.
- `/robot/status` (QOS_STATE): 기동 직후 1회 + 바뀔 때 + 주기.
- `/robot/execute_motion` (Action): 하강 · 슬라이딩 · 이동 · 홈. 동시에 1개만 받는다.
- `/contact/event` 구독: 현재 goal과 `motion_id`가 같고 동작이 맞을 때만 정지에 쓴다.

**두산 호출은 한 줄로 줄을 세운다**(`call_queue.CallQueue`). 조회와 모션을 동시에 부르면
`dsr_controller2`가 모든 서비스 응답을 멈췄다(2026-09-20 Virtual, `docs/env/api-check-log.md`).
이동은 `amovel`(= `move_line` ASYNC)이라 서비스가 바로 응답하므로, 이동 중에도 샘플 조회와
정지 요청이 계속 처리된다(BRD 4.2.3).

실패한 값은 0으로 채우지 않는다. NaN으로 두고 `valid=false`로 발행한다(CLAUDE.md 규칙 4).
순응 · 힘 제어를 켜면 반드시 `finally`에서 해제한다(규칙 2).
"""
import math
import threading
import time
from collections import deque

import rclpy
from contact_scan_interfaces.action import ExecuteMotion
from contact_scan_interfaces.srv import StopRobot
from contact_scan_interfaces.msg import ContactEvent, ReasonCode, RobotSample, RobotStatus
from contact_scan_qos import QOS_EVENT, QOS_SENSOR, QOS_STATE
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.exceptions import ParameterUninitializedException
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter

from robot_manager import dsr_client, motion_state, motions
from robot_manager.call_queue import CallQueue
from robot_manager.conversions import posx_to_pose_fields, tool_force_to_wrench_fields

NAN = float('nan')
LOOP_PERIOD_S = 0.02       # 모션 감시 주기


class Attempt:
    """한 번의 조회 묶음. posx → force → (주기적으로) robot_state 를 차례로 부른다."""

    def __init__(self, started_s, want_state):
        self.started_s = started_s
        self.want_state = want_state
        self.posx = self.force = None
        self.pose_stamp = self.force_stamp = None
        self.posx_done = self.force_done = self.state_done = False

    @property
    def complete(self):
        return self.posx_done and self.force_done and (self.state_done or not self.want_state)


class Motion:
    """실행 중인 goal 하나의 상태."""

    def __init__(self, goal, started_s):
        self.goal = goal
        self.started_s = started_s
        self.start_position = None
        self.start_z = None
        self.moved = False              # 한 번이라도 움직였는가 (도착 판정용)
        self.compliance_on = False
        self.force_on = False
        self.event = None               # 정지 사유가 된 ContactEvent
        self.stop_at_accept = None      # 수락 시점에 남아 있던 /robot/stop 요청 (OP_HOME 전용, #115)


class RobotManager(Node):

    def __init__(self, **kwargs):
        super().__init__('robot_manager', **kwargs)
        self.declare_parameter('frame_id', 'base_link')          # units-frames.md 가칭
        self.declare_parameter('dsr_namespace', 'dsr01')
        self.declare_parameter('sample_rate_hz', 50.0)           # 설계 출발값. 실측은 README
        self.declare_parameter('status_rate_hz', 10.0)
        self.declare_parameter('service_timeout_s', 0.5)
        # 이보다 늦은 응답을 서비스 이름과 함께 남긴다(#130). 0 이면 끈다
        self.declare_parameter('slow_call_warn_s', 0.0)
        # moving 판정: get_robot_state 는 Virtual 에서 이동 중에도 STANDBY(1)를 돌려줬다
        # (2026-09-20 확인, docs/env/api-check-log.md). 그래서 위치 변화로 본다.
        self.declare_parameter('moving_eps_m', 0.0002)
        self.declare_parameter('moving_window_s', 0.3)
        # 계약 이름 (ros-interfaces.md 6.4). 값은 contact_scan_bringup/config/*.yaml 에 둔다
        # 아래 셋은 기본값을 두지 않는다. yaml 에 없으면 기동하지 않는다 (CLAUDE.md 규칙 7,
        # 현지 리뷰 PR #73). 특히 drop_limit_m 은 계약 7.2 가 safety_monitor 와 같은 값을
        # 요구하고 그 일치는 contact_scan_bringup/test/test_config.py 가 yaml 만 보고 검사한다.
        # 코드에 기본값이 있으면 yaml 에서 줄이 사라져도 검사는 통과하면서 1차 · 2차 감시의
        # 기준만 조용히 어긋난다.
        self.declare_parameter('slide_target_force_n', Parameter.Type.DOUBLE)
        self.declare_parameter('drop_limit_m', Parameter.Type.DOUBLE)
        # 계약 이름이 아닌 것
        # 빈 리스트를 기본값으로 주면 rclpy 가 BYTE_ARRAY 로 추론한다. 타입만 선언한다
        self.declare_parameter('home_joint_deg', Parameter.Type.DOUBLE_ARRAY)  # 없으면 OP_HOME 거절
        self.declare_parameter('home_speed_deg_s', 20.0)
        self.declare_parameter('compliance_stiffness', Parameter.Type.DOUBLE_ARRAY)
        self.declare_parameter('motion_timeout_s', 60.0)         # goal.timeout 이 0 일 때 쓴다
        self.declare_parameter('stop_settle_s', 1.5)             # 정지 명령 후 멈춤을 기다리는 시간
        self.declare_parameter('feedback_period_s', 0.1)
        # 명령 후 이 시간 안에 움직이기 시작하지 않으면 도착으로 본다 (병후 리뷰, PR #73)
        self.declare_parameter('arrival_grace_s', 1.0)
        # OP_MOVE_TO 도착 판정 허용치. 멈춘 것과 도착한 것은 다르다 (병후 리뷰, PR #73)
        self.declare_parameter('arrival_tolerance_m', Parameter.Type.DOUBLE)
        # release_force 의 전환 시간. 0 이면 즉시 전환이라 해제 순간 참조 외력이 점프한다
        # (두산 매뉴얼 5.1.4 알아두기, 현지 리뷰 PR #73)
        self.declare_parameter('release_force_time_s', 0.3)

        self.frame_id = self.get_parameter('frame_id').value
        self.service_timeout_s = float(self.get_parameter('service_timeout_s').value)
        self.moving_eps_m = float(self.get_parameter('moving_eps_m').value)
        self.moving_window_s = float(self.get_parameter('moving_window_s').value)
        sample_hz = float(self.get_parameter('sample_rate_hz').value)
        status_hz = float(self.get_parameter('status_rate_hz').value)
        if sample_hz <= 0.0 or status_hz <= 0.0:
            raise ValueError('sample_rate_hz와 status_rate_hz는 0보다 커야 한다')
        self.require_params('drop_limit_m', 'slide_target_force_n', 'compliance_stiffness',
                            'arrival_tolerance_m')

        group = ReentrantCallbackGroup()
        self.srv_clients = dsr_client.make_clients(self, self.get_parameter('dsr_namespace').value)
        for client in self.srv_clients.values():
            client.callback_group = group
        slow_call_warn_s = float(self.get_parameter('slow_call_warn_s').value)
        self.queue = CallQueue(self.now_s, self.service_timeout_s, self.get_logger(),
                               slow_s=slow_call_warn_s if slow_call_warn_s > 0.0 else None)

        self.sample_pub = self.create_publisher(RobotSample, '/robot/sample', QOS_SENSOR)
        self.status_pub = self.create_publisher(RobotStatus, '/robot/status', QOS_STATE)
        self.create_subscription(ContactEvent, '/contact/event', self.on_event, QOS_EVENT,
                                 callback_group=group)

        self.sample_id = 0
        self.cycle = 0
        self.attempt = None
        self.state_every = max(1, round(sample_hz / status_hz))
        self.positions = deque()
        self.last_pose = None          # 마지막 유효 샘플의 (Pose, stamp, (x, y, z))
        self.last_force = None         # 마지막 유효 샘플의 (Fx, Fy, Fz) [N]. REL 기준선 확인용
        self.connected = False
        self.moving = False
        self.compliance_active = False
        self.force_ctrl_active = False
        self.motion_id = 0
        self.operation = RobotSample.OP_NONE
        self.detail = '기동 직후. 아직 로봇 상태를 읽지 않았다'
        self.last_status_key = None

        self.motion = None
        self.motion_lock = threading.Lock()
        # /robot/stop 접수 내용 (reason_code, 사유). 정지를 확인할 때까지 남긴다. 남아 있는 동안은
        # 새 goal 을 받지 않는다. 읽고 지우는 것은 stop_lock 안에서 한다(서비스 · Action · 정지
        # 스레드가 같이 만진다). 지울 때는 '내가 처리한 그 요청'일 때만 지운다 — 그 사이 새로 온
        # 요청을 지우면 접수해 놓고 멈추지 않는다 (yujh5537 리뷰, PR #101)
        self.stop_requested = None
        self.stop_lock = threading.Lock()

        self.publish_status()  # 기동 직후 1회 (TRANSIENT_LOCAL 이라 늦게 뜬 구독자도 받는다)
        self.create_timer(1.0 / sample_hz, self.on_sample_timer, callback_group=group)
        self.create_timer(1.0 / status_hz, self.on_status_timer, callback_group=group)
        # 계약 2.x: /robot/stop 은 robot_manager 가 제공한다. safety_monitor 와 scan_manager 의
        # 유일한 정지 수단이다. 2026-09-21 실기까지 이 서버가 없어서 safety_monitor 의 정지
        # 요청이 전부 '서버가 없다' 로 떨어졌다. 감시자가 멈출 수단 없이 돌고 있었다.
        self.create_service(StopRobot, '/robot/stop', self.on_stop_request, callback_group=group)
        self.action_server = ActionServer(
            self, ExecuteMotion, '/robot/execute_motion',
            goal_callback=self.on_goal_request,
            cancel_callback=lambda goal_handle: CancelResponse.ACCEPT,
            execute_callback=self.execute_motion,
            callback_group=group)
        self.get_logger().info(
            f'robot_manager 시작. 샘플 {sample_hz} Hz, 상태 {status_hz} Hz, '
            f'서비스 {dsr_client.prefix(self.get_parameter("dsr_namespace").value)}')

    # ---- 공통 -------------------------------------------------------------
    def now_s(self):
        return self.get_clock().now().nanoseconds / 1e9

    def require_params(self, *names):
        """yaml 에 없으면 기동하지 않는다. 기본값으로 조용히 도는 것보다 낫다.

        `declare_parameter(name, Type)` 만으로는 **읽을 때** 예외가 난다. 그러면 첫 SLIDE
        goal 이 올 때까지 잘못된 설정이 드러나지 않는다. 여기서 한 번 읽어 기동 시점에
        끝낸다 (현지 리뷰, PR #73).
        """
        missing = []
        for name in names:
            try:
                self.get_parameter(name)
            except ParameterUninitializedException:
                missing.append(name)
        if missing:
            raise ValueError(
                f'파라미터 {missing} 가 설정되지 않았다. '
                'contact_scan_bringup/config/*.yaml 의 robot_manager 절에 넣는다. '
                '기본값을 코드에 두지 않는다 (CLAUDE.md 규칙 7, 계약 7.2)')

    def param(self, name):
        return self.get_parameter(name).value

    def home_joint_deg(self):
        """홈 관절각 [deg] 6개. 설정되지 않았으면 빈 목록 (OP_HOME 을 거절한다).

        기본값 없이 선언한 파라미터는 읽을 때 예외가 나므로, 여기서 잡지 않으면 거절이
        아니라 goal 콜백 예외가 된다 (2026-09-21 노드 시험에서 발견).
        """
        try:
            return list(self.param('home_joint_deg') or [])
        except ParameterUninitializedException:
            return []

    # ---- 샘플 -------------------------------------------------------------
    def on_sample_timer(self):
        self.queue.poll()  # 시간 초과 검사
        if self.attempt is not None:
            if self.now_s() - self.attempt.started_s < self.service_timeout_s * 3:
                return  # 아직 조회 중. 요청을 쌓지 않는다
            self.finish(self.attempt)
        if self.queue.busy():
            return  # 보낸 호출의 응답을 기다리는 중이다. 조회를 쌓지 않는다 (병후 리뷰, PR #72)
        self.cycle += 1
        attempt = self.attempt = Attempt(self.now_s(), want_state=self.cycle % self.state_every == 0)
        self.queue.submit(self.srv_clients['posx'], dsr_client.posx_request(),
                          lambda res, a=attempt: self.on_posx(a, res), 'get_current_posx')

    def on_posx(self, attempt, response):
        attempt.posx = dsr_client.read_posx(response)
        attempt.pose_stamp = self.get_clock().now().to_msg()  # 응답을 받은 시각
        attempt.posx_done = True
        if attempt is not self.attempt:
            return
        self.queue.submit(self.srv_clients['force'], dsr_client.force_request(),
                          lambda res, a=attempt: self.on_force(a, res), 'get_tool_force')

    def on_force(self, attempt, response):
        attempt.force = dsr_client.read_force(response)
        attempt.force_stamp = self.get_clock().now().to_msg()
        attempt.force_done = True
        if attempt is not self.attempt:
            return
        if attempt.want_state:
            self.queue.submit(self.srv_clients['state'], dsr_client.state_request(),
                              lambda res, a=attempt: self.on_state(a, res), 'get_robot_state')
            return
        self.finish(attempt)

    def on_state(self, attempt, response):
        attempt.state_done = True
        connected, _ = dsr_client.read_moving(response)   # robot_state 는 연결 확인용으로만 쓴다
        self.set_state(connected, self.moving_from_positions(),
                       self.detail if connected else '로봇 상태 응답 없음. 브링업 확인')
        if attempt is self.attempt:
            self.finish(attempt)

    def track_position(self, position, stamp_s):
        self.positions.append((stamp_s, position))
        motion_state.trim(self.positions, stamp_s, self.moving_window_s)

    def moving_from_positions(self):
        # 판정 직전에도 창을 정리한다. posx 응답이 끊기면 옛 위치만 남아 "정지"로 굳는다
        # (병후 리뷰, PR #72). 창이 비면 점이 2개 미만이 되어 "이동 중"으로 돌아간다
        motion_state.trim(self.positions, self.now_s(), self.moving_window_s)
        return motion_state.is_moving(self.positions, self.moving_eps_m, self.moving_window_s)

    def finish(self, attempt):
        self.attempt = None
        if attempt.want_state and not attempt.state_done:
            self.set_state(False, None, '로봇 상태 조회 시간 초과')
        self.sample_id += 1
        msg = RobotSample()
        msg.sample_id = self.sample_id
        msg.frame_id = self.frame_id
        msg.motion_id = self.motion_id
        msg.operation = self.operation
        now = self.get_clock().now().to_msg()
        msg.pose_stamp = attempt.pose_stamp or now
        msg.force_stamp = attempt.force_stamp or now

        pose_ok = force_ok = False
        try:
            (x, y, z), (qx, qy, qz, qw) = posx_to_pose_fields(attempt.posx or [])
            msg.pose.position.x, msg.pose.position.y, msg.pose.position.z = x, y, z
            msg.pose.orientation.x, msg.pose.orientation.y = qx, qy
            msg.pose.orientation.z, msg.pose.orientation.w = qz, qw
            self.track_position((x, y, z), self.now_s())
            self.last_pose = (msg.pose, msg.pose_stamp, (x, y, z))
            pose_ok = True
        except ValueError:
            msg.pose.position.x = msg.pose.position.y = msg.pose.position.z = NAN
            msg.pose.orientation.x = msg.pose.orientation.y = NAN
            msg.pose.orientation.z = msg.pose.orientation.w = NAN
        try:
            (fx, fy, fz), (tx, ty, tz) = tool_force_to_wrench_fields(attempt.force or [])
            msg.wrench.force.x, msg.wrench.force.y, msg.wrench.force.z = fx, fy, fz
            msg.wrench.torque.x, msg.wrench.torque.y, msg.wrench.torque.z = tx, ty, tz
            self.last_force = (fx, fy, fz)
            force_ok = True
        except ValueError:
            msg.wrench.force.x = msg.wrench.force.y = msg.wrench.force.z = NAN
            msg.wrench.torque.x = msg.wrench.torque.y = msg.wrench.torque.z = NAN

        msg.valid = pose_ok and force_ok
        self.sample_pub.publish(msg)

    # ---- 상태 -------------------------------------------------------------
    def on_status_timer(self):
        """발행 전에 moving 을 다시 본다. 두산 조회는 샘플 줄에서 같이 한다.

        큐가 밀려 state 갈래가 안 돌면 낡은 moving 이 그대로 나간다(최대
        `abandon_after_s`). 계약상 정지 완료의 유일한 근거가 `connected && !moving`
        이므로 그 사이 "정지"로 보고하면 안 된다. 창이 비면 점이 2개 미만이 되어
        "이동 중"으로 떨어진다. 두산 호출이 아니라 위치 버퍼 위의 계산이라 비용이 없다.
        (병후 리뷰, PR #72 · #83)
        """
        self.set_state(self.connected, self.moving_from_positions(), self.detail)
        self.publish_status()

    def set_state(self, connected, moving, detail):
        """moving을 모르면(None) True로 둔다. 모르는 상태를 정지로 보고하지 않는다."""
        self.connected = connected
        self.moving = True if moving is None else moving
        self.detail = detail
        if self.status_key() != self.last_status_key:
            self.publish_status()

    def status_key(self):
        return (self.connected, self.moving, self.compliance_active, self.force_ctrl_active,
                self.motion_id, self.operation, self.detail)

    def publish_status(self):
        msg = RobotStatus()
        msg.stamp = self.get_clock().now().to_msg()
        msg.connected = self.connected
        msg.moving = self.moving
        msg.error = False
        msg.error_code = ReasonCode.OK
        msg.compliance_active = self.compliance_active
        msg.force_ctrl_active = self.force_ctrl_active
        msg.motion_id = self.motion_id
        msg.operation = self.operation
        msg.detail = self.detail
        self.status_pub.publish(msg)
        self.last_status_key = self.status_key()

    # ---- 이벤트 -----------------------------------------------------------
    def on_event(self, event):
        """계약 5.4절의 대조 규칙. 맞지 않는 이벤트는 정지에 쓰지 않고 로그만 남긴다."""
        motion = self.motion
        if event.type == ContactEvent.TYPE_OVER_FORCE:
            if motion is not None:   # 과대 외력은 대조 없이 항상 우선 정지
                motion.event = event
            return
        if motion is None or event.motion_id == 0 or event.motion_id != motion.goal.motion_id:
            self.get_logger().info(
                f'이벤트 무시: type={event.type} motion_id={event.motion_id} (현재 '
                f'{motion.goal.motion_id if motion else "없음"})')
            return
        wanted = {RobotSample.OP_DESCEND: ContactEvent.TYPE_CONTACT,
                  RobotSample.OP_SLIDE: ContactEvent.TYPE_EDGE}.get(motion.goal.operation)
        if wanted is None or event.type != wanted:
            self.get_logger().info(
                f'이벤트 무시: 동작 {motion.goal.operation}에 맞지 않는 type={event.type}')
            return
        motion.event = event

    # ---- ExecuteMotion ----------------------------------------------------
    def on_goal_request(self, goal_request):
        """동시에 1개만 받는다(계약 5.4). 거절 사유는 로그로 남긴다."""
        with self.motion_lock:
            if self.motion is not None:
                self.get_logger().warn(f'goal 거절 (BUSY): motion_id={goal_request.motion_id}')
                return GoalResponse.REJECT
            if not self.connected:
                self.get_logger().warn(
                    f'goal 거절 (ROBOT_DISCONNECTED): motion_id={goal_request.motion_id}')
                return GoalResponse.REJECT
            problem = self.reject_reason(goal_request)
            if problem:
                self.get_logger().warn(f'goal 거절 ({problem}): motion_id={goal_request.motion_id}')
                return GoalResponse.REJECT
            self.motion = Motion(goal_request, self.now_s())
            # 수락 시점에 남아 있던 정지 요청. OP_HOME 은 이것만 정리하고 출발한다(run_motion).
            # 수락 뒤에 새로 온 요청은 여기 없으므로 watch 가 HOME 을 멈춘다
            self.motion.stop_at_accept = self.stop_requested
        return GoalResponse.ACCEPT

    def reject_reason(self, goal):
        op = goal.operation
        if self.stop_requested is not None and op != RobotSample.OP_HOME:
            # robot_manager 가 마지막 방어선이다. 래치는 SafetyStatus 로 늦게 전달돼 scan_manager 에만
            # 기대기 어렵다. 요청은 정지가 확인되면 지워지므로 영구 거절이 되지 않는다.
            # 안전복귀(OP_HOME)는 거절하지 않는다. 관제자가 직접 누른 명령이고, 시연 중 안전복귀가
            # 막히면 안 된다(#115). 출발 전에 정지를 한 번 더 시도한다(run_motion)
            return 'STOP_REQUESTED: 처리되지 않은 정지 요청이 있다. 정지를 먼저 확인한다'
        if op == RobotSample.OP_NONE or op > RobotSample.OP_HOME:
            return f'INVALID_VALUE: operation={op}'
        if op == RobotSample.OP_SLIDE:
            if goal.direction not in motions.DIRECTION_VECTORS:
                return 'INVALID_VALUE: SLIDE direction'
            if float(self.param('slide_target_force_n')) <= 0.0:
                return 'INVALID_VALUE: slide_target_force_n 이 설정되지 않았다'
            # 기준 z 를 모르면 1차 하강 제한(계약 7.2)이 감시 없이 도는 것과 같다. 조회가
            # 실패 중인 상황이 바로 감시가 필요한 상황이라 거절한다 (현지 리뷰, PR #73)
            if self.last_pose is None:
                return 'INVALID_VALUE: 마지막 위치를 모른다. 하강 제한 기준 z 를 잡을 수 없다'
        if op in (RobotSample.OP_DESCEND, RobotSample.OP_SLIDE) and goal.max_distance <= 0.0:
            return 'INVALID_VALUE: max_distance'
        if op == RobotSample.OP_HOME and not self.home_joint_deg():
            return 'INVALID_VALUE: home_joint_deg 파라미터가 비어 있다'
        # target 은 이 노드의 프레임(Base)으로만 받는다. 작업대 프레임(base_to_fixture 약
        # 0.42 · -0.19 · 0.10 m)의 좌표를 Base 로 알고 movel 하면 세 축 합쳐 약 47 cm 어긋나고,
        # distance_to_target 도 같은 착각 위에서 재므로 도착까지 찍어 준다. 빈 문자열도 거절한다.
        # "비었으면 Base 로 본다"는 관용이 바로 그 경로다 (현지 리뷰, PR #73)
        if op == RobotSample.OP_MOVE_TO and goal.frame_id != self.frame_id:
            return (f'INVALID_VALUE: target 프레임 {goal.frame_id!r} 는 이 노드의 '
                    f'{self.frame_id!r} 가 아니다')
        if op != RobotSample.OP_HOME and goal.speed <= 0.0:
            return 'INVALID_VALUE: speed'
        return ''

    def execute_motion(self, goal_handle):
        goal = goal_handle.request
        motion = self.motion
        motion.start_position = self.last_pose[2] if self.last_pose else None
        motion.start_z = motion.start_position[2] if motion.start_position else None
        # 샘플에 지금 동작을 싣는다. contact_detector 의 판정 모드 스위치다 (계약 3.1)
        self.motion_id, self.operation = goal.motion_id, goal.operation
        # 여기서 stop_requested 를 지우지 않는다. 수락(on_goal_request)과 실행 사이에 온 요청은
        # watch 의 첫 확인에서 처리된다. 지우면 접수해 놓고 동작을 그대로 실행한다
        self.set_state(self.connected, self.moving, f'motion {goal.motion_id} 실행 중')
        self.get_logger().info(
            f'goal 수락: scan={goal.scan_id} motion_id={goal.motion_id} op={goal.operation} '
            f'dir={goal.direction} speed={goal.speed} max={goal.max_distance}')
        try:
            reason, code, detail = self.run_motion(goal_handle, motion)
        except Exception as exc:                       # 예상 못 한 오류도 해제를 거친다
            self.get_logger().error(f'모션 실행 중 오류: {exc}')
            reason = ExecuteMotion.Result.REASON_ROBOT_ERROR
            code, detail = ReasonCode.ROBOT_ERROR, str(exc)
        finally:
            released = self.release_all(motion)
            self.settle_leftover_stop_request()
            self.motion_id, self.operation = 0, RobotSample.OP_NONE
            self.set_state(self.connected, self.moving, '')
            with self.motion_lock:
                self.motion = None
        result = self.build_result(motion, reason, code, detail, released)
        if reason == ExecuteMotion.Result.REASON_CANCELED:
            goal_handle.canceled()
        elif code in (ReasonCode.OK, ReasonCode.MAX_DISTANCE, ReasonCode.NO_CONTACT, ReasonCode.NO_EDGE):
            goal_handle.succeed()
        else:
            goal_handle.abort()
        self.get_logger().info(f'goal 종료: reason={reason} code={code} {detail}')
        return result

    def run_motion(self, goal_handle, motion):
        """명령을 보내고 끝날 때까지 지켜본다. (reason, reason_code, detail)."""
        goal = motion.goal
        leftover = motion.stop_at_accept
        if goal.operation == RobotSample.OP_HOME and leftover is not None:
            # 정지 확인에 실패해 남은 요청이 있는 채로 안전복귀를 받았다(#115). 안 비우면 watch 의
            # 첫 확인에서 HOME 이 곧바로 멈춘다. 정지를 한 번 더 시도하고, 수락 시점의 그 요청만
            # 지운다(그 뒤에 온 새 요청은 남겨 watch 가 HOME 을 멈추게 한다)
            stopped, why = self.stop_robot(f'안전복귀 전 정지 재확인 ({leftover[1]})')
            if stopped:
                self.get_logger().info('안전복귀 전 정지를 확인했다. 남은 정지 요청을 지우고 출발한다')
            else:
                self.get_logger().error(
                    f'안전복귀 전에도 정지를 확인하지 못했다({why}). 관제자 명령이므로 그대로 출발한다')
            self.clear_stop_request(leftover)
        if goal.operation == RobotSample.OP_SLIDE and motion.start_z is None:
            # 기준 z 를 모르면 1차 하강 제한(계약 7.2)이 감시 없이 도는 것과 같다. reject_reason
            # 에서 한 번 걸리지만 수락과 실행 사이에 샘플이 끊길 수 있어 여기서도 막는다.
            # 조용히 감시 없이 도는 것보다 소리내어 끝낸다 (현지 리뷰, PR #73)
            self.get_logger().error(
                'SLIDE 기준 z 를 잡지 못했다(마지막 위치 없음). 1차 하강 제한을 걸 수 없어 거절한다')
            return (ExecuteMotion.Result.REASON_REJECTED, ReasonCode.INVALID_VALUE,
                    'start_z 없음. 하강 제한 감시 불가')
        if goal.operation == RobotSample.OP_SLIDE and not self.start_slide_force(motion):
            return (ExecuteMotion.Result.REASON_ROBOT_ERROR, ReasonCode.ROBOT_ERROR,
                    '순응 · 힘 제어를 켜지 못했다')
        if not self.send_move(motion):
            return (ExecuteMotion.Result.REASON_ROBOT_ERROR, ReasonCode.ROBOT_ERROR, '이동 명령 실패')
        return self.watch(goal_handle, motion)

    def send_move(self, motion):
        """이동 명령(비동기). 서비스 응답은 받되 도착은 기다리지 않는다."""
        goal = motion.goal
        if goal.operation == RobotSample.OP_HOME:
            request = dsr_client.move_joint_request(self.home_joint_deg(),
                                                    float(self.param('home_speed_deg_s')))
            return self.call_sync(self.srv_clients['move_joint'], request, 'move_joint')
        if goal.operation == RobotSample.OP_MOVE_TO:
            target = motions.pose_to_posx_mm_deg(
                (goal.target.position.x, goal.target.position.y, goal.target.position.z),
                (goal.target.orientation.x, goal.target.orientation.y,
                 goal.target.orientation.z, goal.target.orientation.w))
            request = dsr_client.move_line_request(target, goal.speed, relative=False)
        else:
            vector = ((0.0, 0.0, -1.0) if goal.operation == RobotSample.OP_DESCEND
                      else motions.direction_vector(goal.direction))
            request = dsr_client.move_line_request(
                motions.relative_target_mm(vector, goal.max_distance), goal.speed, relative=True)
        return self.call_sync(self.srv_clients['move_line'], request, 'move_line')

    def start_slide_force(self, motion):
        """SLIDE: 순응 제어 → −z 목표 힘. 켠 것은 release_all 이 finally 에서 해제한다.

        **`slide_target_force_n` 은 `DR_FC_MOD_REL` 이라 "더 누르는 힘"이다.** 드라이버 정의는
        "relative value to initial state (the instance when this function is called)" 이므로,
        기준선은 이 호출 시점에 이미 실려 있는 힘이다. **SLIDE 가 어디서 시작하느냐에 따라 실제
        누름이 다르다**(계약 2.4, v0.1.9): 첫 방향은 DESCEND 접촉 자리에서 바로 밀므로
        **접촉력 + slide_target_force_n**, 2~4 방향과 재시작은 방향 전환(7.3)으로 윗면
        recontact_margin_m 위에서 시작하므로 **≈ slide_target_force_n** 이다. 기준선을 로그로
        남겨 실기에서 한 번에 확인할 수 있게 한다(병후 · 현지 지적, PR #73 · #105). 매뉴얼 5.1.4 는
        "접촉할 대상물에 근접하여 DR_FC_MOD_REL 로 힘제어를 시작"하라고 권한다(REL 유지 여부는 TBD).
        """
        baseline = self.last_force
        if baseline is None:
            self.get_logger().warning(
                'SLIDE 시작: 직전 힘을 모른다. DR_FC_MOD_REL 기준선을 확인할 수 없다')
        else:
            fz = baseline[2]
            self.get_logger().info(
                f'SLIDE 시작: DR_FC_MOD_REL 기준선 Fz={fz:.2f} N '
                f'(|F|={math.dist(baseline, (0.0, 0.0, 0.0)):.2f} N). '
                f'목표 {float(self.param("slide_target_force_n")):.2f} N 은 여기에 더해진다')
        # 켜는 호출을 보내기 **전에** 해제 대상으로 표시한다. call_sync 는 응답 시간 초과도 False 로
        # 돌려주는데, 그때 컨트롤러는 이미 켰을 수 있다. 성공 응답을 받은 뒤에만 표시하면 release_all 이
        # 해제를 부르지 않아 순응 · 힘 제어가 켜진 채 남는다(CLAUDE.md 규칙 2, T14). 켜지지 않았는데
        # 해제를 부르다 실패하면 compliance_released=false 로 보고된다 — 모르면 해제됐다고 하지 않는다
        motion.compliance_on = self.compliance_active = True
        if not self.call_sync(
                self.srv_clients['compliance_on'],
                dsr_client.compliance_on_request(list(self.param('compliance_stiffness'))),
                'task_compliance_ctrl'):
            self.get_logger().error('task_compliance_ctrl 응답 없음 또는 거절. 켜졌을 수 있어 해제를 부른다'
                                    '(켜기 시간 초과 뒤 해제 — 해제 실패면 compliance_released=false)')
            return False
        motion.force_on = self.force_ctrl_active = True
        if not self.call_sync(self.srv_clients['force_on'],
                              dsr_client.force_on_request(float(self.param('slide_target_force_n'))),
                              'set_desired_force'):
            self.get_logger().error('set_desired_force 응답 없음 또는 거절. 켜졌을 수 있어 해제를 부른다'
                                    '(켜기 시간 초과 뒤 해제 — 해제 실패면 compliance_released=false)')
            return False
        return True

    def watch(self, goal_handle, motion):
        """정지 조건을 감시한다. 조회 · 이벤트는 다른 콜백에서 계속 들어온다."""
        goal = motion.goal
        timeout_s = (goal.timeout.sec + goal.timeout.nanosec / 1e9) or float(self.param('motion_timeout_s'))
        feedback_period = float(self.param('feedback_period_s'))
        drop_limit = float(self.param('drop_limit_m'))
        next_feedback = 0.0
        while True:
            time.sleep(LOOP_PERIOD_S)
            now = self.now_s()
            elapsed = now - motion.started_s
            position = self.last_pose[2] if self.last_pose else None
            if self.moving:
                motion.moved = True
            if now >= next_feedback:
                next_feedback = now + feedback_period
                self.publish_feedback(goal_handle, motion, elapsed)

            if goal_handle.is_cancel_requested:
                stopped, why = self.stop_robot('Action 취소')
                if not stopped:   # 취소를 접수했다고 멈춘 것이 아니다 (병후 리뷰, PR #73)
                    return (ExecuteMotion.Result.REASON_ROBOT_ERROR, ReasonCode.ROBOT_ERROR,
                            f'Action 취소. {why}')
                return (ExecuteMotion.Result.REASON_CANCELED, ReasonCode.CANCELED, 'Action 취소')
            request = self.take_stop_request()
            if request is not None:
                reason_code, detail = request
                stopped, why = self.stop_robot(f'정지 요청 ({detail})')
                if not stopped:   # 접수했다고 멈춘 것이 아니다 (계약 4.1)
                    # 확인 못 했으니 되돌려 놓는다. 동작 없음 경로(stop_idle)와 같은 약속이다:
                    # 멈췄는지 모르는 로봇에 다음 goal 을 보내지 않는다 (#113). 안전복귀(OP_HOME)만은
                    # 받는다(#115). finally 의 settle_leftover_stop_request 가 한 번 더 확인하고, 그래도
                    # 안 되면 안전복귀 또는 /robot/stop 재호출로 풀린다(README)
                    self.restore_stop_request(request)
                    return (ExecuteMotion.Result.REASON_ROBOT_ERROR, ReasonCode.ROBOT_ERROR,
                            f'정지 요청 ({detail}). {why}')
                return (ExecuteMotion.Result.REASON_STOP_REQUESTED,
                        reason_code or ReasonCode.STOP_REQUESTED, detail)
            if motion.event is not None:
                return self.stop_for_event(motion)
            if goal.operation == RobotSample.OP_SLIDE and motions.drop_exceeded(
                    motion.start_z, position[2] if position else None, drop_limit):
                stopped, why = self.stop_robot('하강 제한 초과')
                return (ExecuteMotion.Result.REASON_ROBOT_ERROR, ReasonCode.DROP_LIMIT,
                        f'SLIDE 하강 제한 {drop_limit} m 초과'
                        + ('' if stopped else f'. {why}'))
            if elapsed > timeout_s:
                stopped, why = self.stop_robot('제한 시간 초과')
                if not stopped:
                    return (ExecuteMotion.Result.REASON_ROBOT_ERROR, ReasonCode.ROBOT_ERROR,
                            f'{timeout_s:.1f} s 안에 끝나지 않았다. {why}')
                return (ExecuteMotion.Result.REASON_TIMEOUT, ReasonCode.TIMEOUT,
                        f'{timeout_s:.1f} s 안에 끝나지 않았다')
            if not self.connected:
                return (ExecuteMotion.Result.REASON_ROBOT_ERROR, ReasonCode.ROBOT_DISCONNECTED,
                        '로봇 연결이 끊겼다')
            if self.arrived(motion, elapsed):
                return self.finished_without_event(motion)

    def arrived(self, motion, elapsed):
        """로봇이 멈췄으면 명령한 만큼 갔다고 본다.

        `moving`을 위치 변화로 보기 때문에, 명령 직후 아직 움직이기 전 구간을 도착으로
        잘못 보지 않도록 `arrival_grace_s`를 둔다.

        **멈춘 것과 도착한 것은 다르다.** 여기서는 "멈췄다"만 판정하고, 목표에 실제로
        닿았는지는 `finished_without_event`가 본다 (병후 리뷰, PR #73).
        """
        if self.moving:
            return False
        return motion.moved or elapsed > float(self.param('arrival_grace_s'))

    def finished_without_event(self, motion):
        op = motion.goal.operation
        if op == RobotSample.OP_DESCEND:
            return (ExecuteMotion.Result.REASON_MAX_DISTANCE, ReasonCode.NO_CONTACT,
                    '최대 거리까지 접촉이 없었다')
        if op == RobotSample.OP_SLIDE:
            return (ExecuteMotion.Result.REASON_MAX_DISTANCE, ReasonCode.NO_EDGE,
                    '최대 거리까지 접촉 소실이 없었다')
        if op == RobotSample.OP_MOVE_TO:
            # 멈췄다고 도착한 것이 아니다. 드라이버 알람 · 외력 · 충돌 · 관절 한계로 중간에
            # 서도 moving 은 false 가 된다. scan_manager 는 이 OK 를 믿고 바로 하강하므로,
            # 엉뚱한 자리에서 작업대나 옆면을 윗면으로 잡게 된다 (병후 리뷰, PR #73)
            gap = self.distance_to_target(motion)
            tolerance = float(self.param('arrival_tolerance_m'))
            if gap is None:
                return (ExecuteMotion.Result.REASON_ROBOT_ERROR, ReasonCode.ROBOT_ERROR,
                        '이동이 끝났지만 현재 위치를 몰라 도착을 확인하지 못했다')
            if gap > tolerance:
                return (ExecuteMotion.Result.REASON_ROBOT_ERROR, ReasonCode.ROBOT_ERROR,
                        f'이동이 끝났지만 목표에서 {gap * 1000:.1f} mm 떨어져 있다 '
                        f'(허용 {tolerance * 1000:.1f} mm)')
        return (ExecuteMotion.Result.REASON_TARGET_REACHED, ReasonCode.OK, '')

    def distance_to_target(self, motion):
        """목표와 현재 위치의 거리 [m]. 둘 중 하나라도 모르면 None (0으로 채우지 않는다)."""
        if self.last_pose is None:
            return None
        target = motion.goal.target.position
        x, y, z = self.last_pose[2]
        return math.dist((x, y, z), (target.x, target.y, target.z))

    def stop_for_event(self, motion):
        event = motion.event
        if event.type == ContactEvent.TYPE_OVER_FORCE:
            stopped, why = self.stop_robot('과대 외력')
            if not stopped:
                return (ExecuteMotion.Result.REASON_ROBOT_ERROR, ReasonCode.ROBOT_ERROR,
                        f'과대 외력 {event.force_delta_n:.2f} N. {why}')
            return (ExecuteMotion.Result.REASON_OVER_FORCE, ReasonCode.OVER_FORCE,
                    f'과대 외력 {event.force_delta_n:.2f} N')
        stopped, why = self.stop_robot(
            '접촉' if event.type == ContactEvent.TYPE_CONTACT else '접촉 소실')
        if not stopped:
            # 정지를 확인하지 못했는데 정상 코드로 돌려주면 scan_manager 는 STOPPED 로 가고
            # 로봇은 아직 움직인다. 계약 4.1 의 "접수와 정지 완료는 다르다" (병후 리뷰, PR #73)
            return (ExecuteMotion.Result.REASON_ROBOT_ERROR, ReasonCode.ROBOT_ERROR, why)
        if event.type == ContactEvent.TYPE_CONTACT:
            return (ExecuteMotion.Result.REASON_CONTACT, ReasonCode.OK, '')
        return (ExecuteMotion.Result.REASON_EDGE, ReasonCode.OK, '')

    def on_stop_request(self, request, response):
        """`/robot/stop` (계약 4.1). **접수는 정지 완료가 아니다.**

        정지 완료는 요청한 쪽이 `/robot/status` 의 `connected && !moving` 으로 확인한다.
        여기서는 접수만 하고, 실제 정지는 동작 감시 고리(`watch`)가 한다. 동작이 없으면
        별도 스레드에서 바로 `move_stop` 을 보낸다.

        이미 정지 중이어도 `accepted=true` 다(멱등). 미연결이면 `accepted=false` 와
        `ROBOT_DISCONNECTED` 로 사실대로 돌려준다 — 드라이버가 응답하지 않으면 이 경로로는
        멈출 수 없고 물리 비상정지가 유일한 수단이다.
        """
        who = request.requester or '알 수 없음'
        if not self.connected:
            response.accepted = False
            response.reason_code = ReasonCode.ROBOT_DISCONNECTED
            response.detail = ('로봇이 연결되지 않았다. 이 경로로는 멈출 수 없다. '
                               '물리 비상정지를 눌러야 한다')
            self.get_logger().error(f'{who} 의 정지 요청을 받았지만 로봇이 미연결이다')
            return response

        entry = (request.reason, f'{who}: {request.detail}'.strip())
        with self.stop_lock:
            self.stop_requested = entry
        self.get_logger().warn(
            f'정지 요청 접수: requester={who} reason={request.reason} {request.detail}')
        with self.motion_lock:
            running = self.motion is not None
        if not running:
            # 동작이 없으면 감시 고리가 없다. 손으로 움직이는 중일 수 있으니 직접 보낸다.
            # call_sync 는 줄 선 호출의 응답을 기다리므로 서비스 응답을 막지 않도록 스레드로 뺀다.
            # 수락 직후 · 실행 전이면 running 이 True 라 여기로 오지 않고 watch 가 처리한다
            threading.Thread(target=self.stop_idle, args=(entry, f'{who} 요청(동작 없음)'),
                             daemon=True).start()
        response.accepted = True
        response.reason_code = ReasonCode.OK
        response.detail = '접수. 정지 완료는 /robot/status 의 connected && !moving 으로 확인한다'
        return response

    def take_stop_request(self):
        """남은 정지 요청을 꺼내고 지운다. watch 가 부른다. 없으면 None."""
        with self.stop_lock:
            request, self.stop_requested = self.stop_requested, None
        return request

    def restore_stop_request(self, entry):
        """정지를 확인하지 못한 요청을 되돌려 놓는다. 그 사이 새 요청이 왔으면 그것을 남긴다."""
        with self.stop_lock:
            if self.stop_requested is None:
                self.stop_requested = entry

    def clear_stop_request(self, entry):
        """`entry` 가 아직 남은 요청일 때만 지운다. 그 사이 새로 온 요청은 남긴다."""
        with self.stop_lock:
            if self.stop_requested is entry:
                self.stop_requested = None

    def stop_idle(self, entry, why):
        """동작이 없을 때 온 요청. 정지를 확인해야 지운다.

        확인하지 못하면 남겨 둔다. 그동안 새 goal 은 거절된다 — 멈췄는지 모르는 로봇에
        다음 동작을 보내지 않는다. safety_monitor 는 확인될 때까지 다시 요청한다.
        """
        stopped, _ = self.stop_robot(why)
        if stopped:
            self.clear_stop_request(entry)

    def settle_leftover_stop_request(self):
        """동작이 끝나는 사이에 온 요청(watch 의 마지막 확인 뒤)을 처리한다.

        동작은 이미 끝났으니 결과는 바꾸지 않는다. 대신 정지를 확인하고 지운다. 확인하지
        못하면 남겨 두어 다음 goal 을 거절하게 한다. 이것이 없으면 요청이 다음 goal 까지
        남아 있다가 조용히 무시되거나(이전 코드), 확인 없이 영구히 남는다.
        """
        entry = self.stop_requested
        if entry is None:
            return
        self.get_logger().warn(f'동작이 끝나는 사이에 온 정지 요청을 처리한다: {entry[1]}')
        stopped, _ = self.stop_robot(f'동작 종료 직후 정지 요청 ({entry[1]})')
        if stopped:
            self.clear_stop_request(entry)

    def stop_robot(self, why):
        """move_stop 뒤 실제로 멈출 때까지 기다린다. 접수와 정지 완료는 다르다(계약 4.1).

        `(정지 확인됨, 사유)`를 돌려준다. 확인하지 못했으면 호출한 쪽이 결과를
        ROBOT_ERROR 로 격상한다. 경고만 남기고 정상 코드로 끝내면 scan_manager 가
        STOPPED 로 가는데 로봇은 아직 움직이는 중일 수 있다 (병후 리뷰, PR #73).

        `moving` 은 "위치를 모르면 이동 중"이므로(#72), 조회가 끊긴 상황에서는 반드시
        여기로 온다. 그것이 의도다 — 모르면 멈췄다고 하지 않는다.
        """
        self.get_logger().info(f'정지: {why}')
        accepted = self.call_sync(self.srv_clients['move_stop'], dsr_client.move_stop_request(),
                                  'move_stop')
        deadline = self.now_s() + float(self.param('stop_settle_s'))
        while self.moving and self.now_s() < deadline:
            time.sleep(LOOP_PERIOD_S)
        if self.moving:
            detail = ('move_stop 응답 없음. ' if not accepted else '') + \
                f'정지 명령 뒤 {self.param("stop_settle_s")} s 동안 멈춤을 확인하지 못했다'
            self.get_logger().error(detail)
            return False, detail
        if not accepted:
            detail = 'move_stop 응답은 없었으나 움직임은 멈췄다'
            self.get_logger().warn(detail)
        return True, ''  

    def release_all(self, motion):
        """순응 · 힘 제어 해제. 모든 종료 경로에서 부른다(CLAUDE.md 규칙 2).

        해제 호출이 실패했을 때 무엇을 보고할지는 계약에서 TBD다. 여기서는 사실대로
        `compliance_released=false`로 두고 로그를 남긴다. 성공한 것으로 적지 않는다.
        """
        released = True
        if motion is not None and motion.force_on:
            ramp_s = float(self.param('release_force_time_s'))
            if self.call_sync(self.srv_clients['force_off'], dsr_client.force_off_request(ramp_s),
                              'release_force'):
                self.force_ctrl_active = False
            else:
                released = False
                self.get_logger().error('release_force 실패(응답 없음 또는 거절)')
            # 힘 제어가 순응 제어로 넘어가는 시간(ramp_s)이 끝난 뒤 순응을 푼다. **성공이든 시간 초과든**
            # 해제 요청은 보냈으므로 램프가 진행 중일 수 있다. ReleaseForce 응답은 success 하나뿐이라
            # 램프가 끝난 뒤 돌아오는지 알 수 없다. 매뉴얼도 엇갈린다: 5.1.4 예제는 release_force() →
            # wait(0.5) → release_compliance_ctrl() 이고, 5.1.5 예제는 기다림 없이 바로 부른다(DRL 에서는
            # 블로킹일 수 있다는 뜻). ROS 서비스 동작을 모르니 **안전한 쪽으로 기다린다** (PR #121 리뷰).
            # 이 대기는 어떤 락도 잡지 않은 채 Action 스레드에서만 돈다. 샘플 타이머는 따로 돈다
            if motion.compliance_on:
                time.sleep(ramp_s)
        if motion is not None and motion.compliance_on:
            if self.call_sync(self.srv_clients['compliance_off'], dsr_client.compliance_off_request(),
                              'release_compliance_ctrl'):
                self.compliance_active = False
            else:
                released = False
                self.get_logger().error('release_compliance_ctrl 실패')
        return released

    def call_sync(self, client, request, label):
        """줄을 선 호출의 응답을 기다린다. Action 실행 스레드에서만 부른다."""
        done = threading.Event()
        box = {}

        def on_done(response):
            box['response'] = response
            done.set()

        self.queue.submit(client, request, on_done, label)
        if not done.wait(timeout=self.service_timeout_s * 4 + 1.0):
            self.get_logger().error(f'{label} 응답을 기다리다 포기했다')
            return False
        return dsr_client.succeeded(box.get('response'))

    def publish_feedback(self, goal_handle, motion, elapsed):
        feedback = ExecuteMotion.Feedback()
        if self.last_pose:
            feedback.pose, feedback.pose_stamp = self.last_pose[0], self.last_pose[1]
        feedback.frame_id = self.frame_id
        feedback.distance_travelled = motions.travelled_m(
            motion.start_position, self.last_pose[2] if self.last_pose else None)
        feedback.elapsed.sec = int(elapsed)
        feedback.elapsed.nanosec = int((elapsed % 1.0) * 1e9)
        goal_handle.publish_feedback(feedback)

    def build_result(self, motion, reason, code, detail, released):
        result = ExecuteMotion.Result()
        if self.last_pose:       # 정지 시점 pose = 중단 위치의 출처 (판정 좌표와 다르다)
            result.pose, result.pose_stamp = self.last_pose[0], self.last_pose[1]
        result.frame_id = self.frame_id
        result.reason = reason
        result.reason_code = code
        result.detail = detail
        result.event_id = motion.event.event_id if motion is not None and motion.event else 0
        result.distance_travelled = motions.travelled_m(
            motion.start_position if motion is not None else None,
            self.last_pose[2] if self.last_pose else None)
        result.compliance_released = released
        return result


def main(args=None):
    rclpy.init(args=args)
    node = RobotManager()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
