"""robot_manager 노드: RobotSample · RobotStatus 발행 (T15).

BRD 4.1.6, 계약 `docs/contracts/ros-interfaces.md` 3.1 · 3.2절.

- `/robot/sample` (QOS_SENSOR): TCP pose와 외력. **취득 시각을 각각 따로** 싣는다.
- `/robot/status` (QOS_STATE, TRANSIENT_LOCAL): 기동 직후 1회 + 바뀔 때 + 주기.
  scan_manager는 `connected`가 한 번도 오지 않으면 스캔을 시작하지 않고,
  정지 완료를 `connected && !moving`으로만 판단한다.

조회는 두산 서비스를 직접 부르고 응답을 기다리지 않는다(`call_async` + 콜백). 서비스 호출 안에서
다른 응답을 기다리면 이동 중에 샘플이 끊긴다(BRD 4.2.3).

실패한 값은 0으로 채우지 않는다. pose · wrench를 NaN으로 두고 `valid=false`로 발행한다
(계약 1장, CLAUDE.md 규칙 4). 수신 측은 `valid`만 보고 판단한다.

ExecuteMotion(T13)이 들어오면 `motion_id` · `operation`과 순응 · 힘 제어 상태를 여기에 싣는다.
T15에서는 각각 0 · OP_NONE · false다.
"""
from collections import deque
from functools import partial

import rclpy
from contact_scan_interfaces.msg import RobotSample, RobotStatus
from contact_scan_qos import QOS_SENSOR, QOS_STATE
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from robot_manager import dsr_client, motion_state
from robot_manager.conversions import posx_to_pose_fields, tool_force_to_wrench_fields

NAN = float('nan')


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


class RobotManager(Node):

    def __init__(self, **kwargs):
        super().__init__('robot_manager', **kwargs)
        self.declare_parameter('frame_id', 'base_link')          # units-frames.md 가칭
        self.declare_parameter('dsr_namespace', 'dsr01')
        self.declare_parameter('sample_rate_hz', 50.0)           # 설계 출발값. 실측 주기는 T15 PR에 적는다
        self.declare_parameter('status_rate_hz', 10.0)
        self.declare_parameter('service_timeout_s', 0.5)
        # moving 판정: get_robot_state 는 Virtual 에서 이동 중에도 STANDBY(1)를 돌려줬다
        # (2026-09-20 확인, docs/env/api-check-log.md). 그래서 위치 변화로 본다.
        self.declare_parameter('moving_eps_m', 0.0002)       # 이 창 안에서 이만큼 움직이면 이동 중
        self.declare_parameter('moving_window_s', 0.3)

        self.frame_id = self.get_parameter('frame_id').value
        self.service_timeout_s = float(self.get_parameter('service_timeout_s').value)
        sample_hz = float(self.get_parameter('sample_rate_hz').value)
        status_hz = float(self.get_parameter('status_rate_hz').value)
        if sample_hz <= 0.0 or status_hz <= 0.0:
            raise ValueError('sample_rate_hz와 status_rate_hz는 0보다 커야 한다')

        group = ReentrantCallbackGroup()
        self.srv_clients = dsr_client.make_clients(self, self.get_parameter('dsr_namespace').value)
        for client in self.srv_clients.values():
            client.callback_group = group

        self.sample_pub = self.create_publisher(RobotSample, '/robot/sample', QOS_SENSOR)
        self.status_pub = self.create_publisher(RobotStatus, '/robot/status', QOS_STATE)

        self.sample_id = 0
        self.cycle = 0
        self.attempt = None
        # 두산 호출을 한 줄로 묶었으므로, 상태 조회는 샘플 몇 번마다 한 번 끼워 넣는다
        self.state_every = max(1, round(sample_hz / status_hz))
        self.moving_eps_m = float(self.get_parameter('moving_eps_m').value)
        self.moving_window_s = float(self.get_parameter('moving_window_s').value)
        self.positions = deque()     # (시각 s, (x, y, z) m) — moving 판정용
        self.connected = False
        self.moving = False
        self.compliance_active = False   # T13에서 갱신한다
        self.force_ctrl_active = False
        self.motion_id = 0
        self.operation = RobotSample.OP_NONE
        self.detail = '기동 직후. 아직 로봇 상태를 읽지 않았다'
        self.last_status_key = None

        self.publish_status()  # 기동 직후 1회 (TRANSIENT_LOCAL 이라 늦게 뜬 구독자도 받는다)
        self.create_timer(1.0 / sample_hz, self.on_sample_timer, callback_group=group)
        self.create_timer(1.0 / status_hz, self.on_status_timer, callback_group=group)
        self.get_logger().info(
            f'robot_manager 시작. 샘플 {sample_hz} Hz, 상태 {status_hz} Hz, '
            f'서비스 {dsr_client.prefix(self.get_parameter("dsr_namespace").value)}')

    # ---- 샘플 -------------------------------------------------------------
    def now_s(self):
        return self.get_clock().now().nanoseconds / 1e9

    def on_sample_timer(self):
        if self.attempt is not None:
            if self.now_s() - self.attempt.started_s < self.service_timeout_s:
                return  # 아직 응답을 기다리는 중. 요청을 쌓지 않는다
            self.finish(self.attempt)  # 시간 초과. 못 받은 값은 NaN으로 발행한다
        self.cycle += 1
        attempt = self.attempt = Attempt(self.now_s(), want_state=self.cycle % self.state_every == 0)
        self.call(self.srv_clients['posx'], dsr_client.posx_request(), attempt, 'posx')

    def call(self, client, request, attempt, kind):
        """두산 호출은 **한 번에 하나만** 보낸다.

        posx와 force를 동시에 부르면 dsr_controller2가 서비스 응답을 멈춘 적이 있다
        (2026-09-20 Virtual, 이후 브링업을 다시 띄워야 회복). 드라이버(DRFL) 호출이
        동시 호출에 안전하지 않은 것으로 보여, 응답을 받은 뒤 다음 것을 부른다.
        """
        if not client.service_is_ready():
            self.on_response(attempt, kind, None)
            return
        client.call_async(request).add_done_callback(partial(self.on_response, attempt, kind))

    def on_response(self, attempt, kind, future):
        stamp = self.get_clock().now().to_msg()  # 응답을 받은 시각 (발행 시각이 아니다)
        response = None
        if future is not None:
            try:
                response = future.result()
            except Exception as exc:  # 드라이버가 죽는 등
                self.get_logger().warn(f'{kind} 조회 실패: {exc}')
        if kind == 'posx':
            attempt.posx, attempt.pose_stamp, attempt.posx_done = dsr_client.read_posx(response), stamp, True
            if attempt is self.attempt:  # posx 응답을 받은 뒤에 force를 부른다 (직렬)
                self.call(self.srv_clients['force'], dsr_client.force_request(), attempt, 'force')
            return
        if kind == 'force':
            attempt.force, attempt.force_stamp, attempt.force_done = dsr_client.read_force(response), stamp, True
            if attempt.want_state and attempt is self.attempt:  # 상태도 같은 줄에서 부른다
                self.call(self.srv_clients['state'], dsr_client.state_request(), attempt, 'state')
                return
        else:  # state
            attempt.state_done = True
            connected, _ = dsr_client.read_moving(response)   # robot_state 는 연결 확인용으로만 쓴다
            self.set_state(connected, self.moving_from_positions(),
                           '' if connected else '로봇 상태 응답 없음. 브링업 확인')
        if attempt.complete and attempt is self.attempt:
            self.finish(attempt)

    def track_position(self, position, stamp_s):
        """최근 창 안의 위치를 모아 둔다. moving 판정에 쓴다."""
        self.positions.append((stamp_s, position))
        motion_state.trim(self.positions, stamp_s, self.moving_window_s)

    def moving_from_positions(self):
        return motion_state.is_moving(self.positions, self.moving_eps_m)

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
            pose_ok = True
        except ValueError:
            msg.pose.position.x = msg.pose.position.y = msg.pose.position.z = NAN
            msg.pose.orientation.x = msg.pose.orientation.y = NAN
            msg.pose.orientation.z = msg.pose.orientation.w = NAN
        try:
            (fx, fy, fz), (tx, ty, tz) = tool_force_to_wrench_fields(attempt.force or [])
            msg.wrench.force.x, msg.wrench.force.y, msg.wrench.force.z = fx, fy, fz
            msg.wrench.torque.x, msg.wrench.torque.y, msg.wrench.torque.z = tx, ty, tz
            force_ok = True
        except ValueError:
            msg.wrench.force.x = msg.wrench.force.y = msg.wrench.force.z = NAN
            msg.wrench.torque.x = msg.wrench.torque.y = msg.wrench.torque.z = NAN

        msg.valid = pose_ok and force_ok
        self.sample_pub.publish(msg)

    # ---- 상태 -------------------------------------------------------------
    def on_status_timer(self):
        """상태는 주기적으로 **발행만** 한다. 조회는 샘플 줄(on_response)에서 같이 한다."""
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
        msg.error = False           # T13 · T14에서 모션 오류를 싣는다
        msg.error_code = 0
        msg.compliance_active = self.compliance_active
        msg.force_ctrl_active = self.force_ctrl_active
        msg.motion_id = self.motion_id
        msg.operation = self.operation
        msg.detail = self.detail
        self.status_pub.publish(msg)
        self.last_status_key = self.status_key()


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
