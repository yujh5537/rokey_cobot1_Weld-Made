"""contact_detector 노드.

지금은 골격이다: 파라미터를 읽어 검증하고 판정기(detector_core.ContactDetector)를 만든다.
/robot/sample 구독, /contact/event 발행, /contact/tare 서비스는 아직 없다.

파라미터에 코드 기본값을 두지 않는다(CLAUDE.md 규칙 7). 값은 contact_scan_bringup/config/*.yaml 에서 온다.
값이 없으면 기동하지 않는다.
"""
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.parameter import Parameter

from contact_detector.detector_core import ContactDetector, DetectorConfig

SOURCES = ('sim', 'robot_force')


class ContactDetectorNode(Node):

    def __init__(self, **kwargs):
        super().__init__('contact_detector', **kwargs)
        self.source = self._required('source', Parameter.Type.STRING)
        if self.source not in SOURCES:
            raise ValueError(f"source='{self.source}' 는 지원하지 않는다. {' | '.join(SOURCES)} 중에서 고른다")

        self.detector = ContactDetector(DetectorConfig(
            contact_threshold_n=self._required('contact_threshold_n', Parameter.Type.DOUBLE),
            debounce_n=self._required('debounce_n', Parameter.Type.INTEGER),
            over_force_n=self._required('over_force_n', Parameter.Type.DOUBLE),
            over_force_debounce_n=self._required('over_force_debounce_n', Parameter.Type.INTEGER),
        ))
        self.edge_drop_m = self._required('edge_drop_m', Parameter.Type.DOUBLE)

        c = self.detector.config
        self.get_logger().info(
            f'source={self.source} contact_threshold_n={c.contact_threshold_n} debounce_n={c.debounce_n} '
            f'over_force_n={c.over_force_n} over_force_debounce_n={c.over_force_debounce_n} '
            f'edge_drop_m={self.edge_drop_m}')

    def _required(self, name, param_type):
        value = self.declare_parameter(name, param_type).value
        if value is None:
            raise ValueError(f"파라미터 '{name}' 값이 없다. contact_scan_bringup/config/*.yaml 의 contact_detector 절을 확인한다")
        return value


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = ContactDetectorNode()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
