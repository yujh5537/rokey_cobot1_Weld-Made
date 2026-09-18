"""scan_manager 노드 껍데기 (T10).

상태 기계를 들고 /scan/state 를 발행한다(변경 시 + 주기, 계약 2.1절).
Action · Service 서버, ExecuteMotion 호출, tare 는 T19, 중지 · 안전복귀 · 재시작 처리는 T26 에서 얹는다.
"""

from contact_scan_interfaces.msg import ScanState
from contact_scan_qos import QOS_STATE
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node

from .state_machine import ScanStateMachine
from .state_machine import Snapshot

# 설계 출발값. 실제 값은 contact_scan_bringup/config/*.yaml 에 둔다.
DEFAULT_STATE_PUBLISH_PERIOD_S = 1.0


def to_msg(snapshot: Snapshot, stamp) -> ScanState:
    msg = ScanState()
    msg.stamp = stamp
    msg.scan_id = snapshot.scan_id
    msg.phase = int(snapshot.phase)
    msg.direction = int(snapshot.direction)
    msg.progress = snapshot.progress
    msg.progress_total = snapshot.progress_total
    msg.motion_id = snapshot.motion_id
    return msg


class ScanManager(Node):

    def __init__(self, **kwargs):
        super().__init__('scan_manager', **kwargs)
        period = self.declare_parameter(
            'state_publish_period_s', DEFAULT_STATE_PUBLISH_PERIOD_S).value
        if not period > 0.0:
            raise ValueError(f'state_publish_period_s 는 0 보다 커야 한다: {period}')

        self._state_pub = self.create_publisher(ScanState, '/scan/state', QOS_STATE)
        self.state_machine = ScanStateMachine(on_change=self._publish_state)
        self._state_timer = self.create_timer(
            period, lambda: self._publish_state(self.state_machine.snapshot()))
        self._publish_state(self.state_machine.snapshot())

    def _publish_state(self, snapshot: Snapshot):
        self._state_pub.publish(to_msg(snapshot, self.get_clock().now().to_msg()))


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = ScanManager()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
