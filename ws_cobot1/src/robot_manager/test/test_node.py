"""robot_manager 노드 테스트 (T15).

두산 드라이버(dsr_msgs2)가 없으면 건너뛴다. CI에는 드라이버가 없다.
여기서는 **드라이버가 없을 때의 동작**을 본다. 실기·Virtual 동작은 PR 본문에 따로 적는다.
"""
import pytest

pytest.importorskip('dsr_msgs2', reason='두산 드라이버가 없는 환경(CI)에서는 건너뛴다')

import rclpy  # noqa: E402
from contact_scan_interfaces.msg import RobotSample, RobotStatus  # noqa: E402
from contact_scan_qos import QOS_SENSOR, QOS_STATE  # noqa: E402
from rclpy.executors import SingleThreadedExecutor  # noqa: E402
from rclpy.parameter import Parameter  # noqa: E402

from robot_manager.robot_manager import RobotManager  # noqa: E402

PARAMS = [
    Parameter('sample_rate_hz', Parameter.Type.DOUBLE, 50.0),
    Parameter('status_rate_hz', Parameter.Type.DOUBLE, 20.0),
    Parameter('service_timeout_s', Parameter.Type.DOUBLE, 0.05),
    # 브링업이 없는 환경이므로 실제 서비스와 겹치지 않는 이름을 쓴다
    Parameter('dsr_namespace', Parameter.Type.STRING, 'test_no_driver'),
]


@pytest.fixture
def ros():
    rclpy.init()
    yield
    rclpy.shutdown()


def collect(node, seconds, timeout_extra=0.5):
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    end = node.get_clock().now().nanoseconds / 1e9 + seconds
    while node.get_clock().now().nanoseconds / 1e9 < end:
        executor.spin_once(timeout_sec=timeout_extra)
    executor.remove_node(node)


def test_publishes_status_before_any_driver_response(ros):
    """scan_manager는 status를 한 번도 못 받으면 스캔을 시작하지 않는다. 기동 직후 1회 발행한다."""
    node = RobotManager(parameter_overrides=PARAMS)
    listener = rclpy.create_node('status_listener')
    received = []
    listener.create_subscription(RobotStatus, '/robot/status', received.append, QOS_STATE)
    try:
        executor = SingleThreadedExecutor()
        executor.add_node(node)
        executor.add_node(listener)
        for _ in range(50):
            executor.spin_once(timeout_sec=0.05)
            if received:
                break
        assert received, '기동 직후 status가 발행되지 않았다'
        assert received[0].connected is False      # 드라이버가 없으니 미연결
        assert received[0].operation == RobotSample.OP_NONE
        assert received[0].motion_id == 0
        assert received[0].compliance_active is False
        assert received[0].force_ctrl_active is False
    finally:
        listener.destroy_node()
        node.destroy_node()


def test_sample_is_invalid_with_nan_when_driver_is_missing(ros):
    """실패한 조회를 0으로 채우지 않는다 (CLAUDE.md 규칙 4)."""
    node = RobotManager(parameter_overrides=PARAMS)
    listener = rclpy.create_node('sample_listener')
    received = []
    listener.create_subscription(RobotSample, '/robot/sample', received.append, QOS_SENSOR)
    try:
        executor = SingleThreadedExecutor()
        executor.add_node(node)
        executor.add_node(listener)
        for _ in range(60):
            executor.spin_once(timeout_sec=0.05)
            if len(received) >= 2:
                break
        assert received, '샘플이 발행되지 않았다'
        sample = received[0]
        assert sample.valid is False
        assert sample.pose.position.x != sample.pose.position.x          # NaN
        assert sample.wrench.force.z != sample.wrench.force.z            # NaN
        assert sample.frame_id == 'base_link'
        assert sample.sample_id == 1                                     # 발행마다 +1
        assert sample.pose_stamp.sec or sample.pose_stamp.nanosec        # 시각은 채운다
    finally:
        listener.destroy_node()
        node.destroy_node()


def test_sample_id_increases(ros):
    node = RobotManager(parameter_overrides=PARAMS)
    listener = rclpy.create_node('id_listener')
    received = []
    listener.create_subscription(RobotSample, '/robot/sample', received.append, QOS_SENSOR)
    try:
        executor = SingleThreadedExecutor()
        executor.add_node(node)
        executor.add_node(listener)
        for _ in range(80):
            executor.spin_once(timeout_sec=0.05)
            if len(received) >= 3:
                break
        assert len(received) >= 3
        ids = [s.sample_id for s in received[:3]]
        assert ids == sorted(ids) and len(set(ids)) == 3
    finally:
        listener.destroy_node()
        node.destroy_node()


def test_does_not_send_while_a_call_is_outstanding(ros):
    """앞 요청의 응답이 안 왔으면 새로 보내지 않는다 (병후 리뷰, PR #72).

    같은 서비스로 여러 건이 동시에 뜨면 드라이버가 응답을 멈춘다.
    """
    node = RobotManager(parameter_overrides=PARAMS)
    try:
        node.pending_calls = 1
        node.last_call_s = node.now_s()
        node.attempt = None
        before = node.cycle
        node.on_sample_timer()
        assert node.cycle == before, '응답을 기다리는 중에는 새 조회를 시작하지 않는다'
        assert node.attempt is None

        # 너무 오래 기다리면 포기하고 다시 보낸다 (영구 정지를 막는다)
        node.last_call_s = node.now_s() - 10.0
        node.on_sample_timer()
        assert node.cycle == before + 1
        assert node.pending_calls == 0
    finally:
        node.destroy_node()


def test_moving_is_true_again_when_positions_go_stale(ros):
    """정지 상태로 창을 채운 뒤 posx 가 끊기면 moving 이 다시 True 가 된다."""
    node = RobotManager(parameter_overrides=PARAMS)
    try:
        now = node.now_s()
        for i in range(3):
            node.positions.append((now - 0.2 + i * 0.05, (0.4, 0.0, 0.2)))
        assert node.moving_from_positions() is False
        node.positions.clear()
        for i in range(3):        # 창(0.3 s)보다 오래된 위치만 남은 상태
            node.positions.append((now - 5.0 + i * 0.05, (0.4, 0.0, 0.2)))
        assert node.moving_from_positions() is True
    finally:
        node.destroy_node()
