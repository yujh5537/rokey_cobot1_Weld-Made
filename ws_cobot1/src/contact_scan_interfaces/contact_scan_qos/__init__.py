"""Topic QoS 프로파일 (docs/contracts/ros-interfaces.md 6.3절).

발행 · 구독 양쪽이 이 정의를 import 해서 쓴다. 불일치하면 연결되지 않는다.
값은 계약에 고정된 것이라 ROS 파라미터로 빼지 않는다. 바꿀 때는 계약 문서와 같이 바꾼다.

    from contact_scan_qos import QOS_SENSOR
    node.create_subscription(RobotSample, '/robot/sample', callback, QOS_SENSOR)

Service · Action 은 기본값을 쓴다.
"""

from rclpy.qos import DurabilityPolicy
from rclpy.qos import HistoryPolicy
from rclpy.qos import QoSProfile
from rclpy.qos import ReliabilityPolicy


def _profile(reliability, durability, depth):
    return QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=depth,
        reliability=reliability,
        durability=durability,
    )


# /robot/sample
QOS_SENSOR = _profile(ReliabilityPolicy.BEST_EFFORT, DurabilityPolicy.VOLATILE, 5)
# /robot/status · /scan/state · /scan/result · /safety/status
QOS_STATE = _profile(ReliabilityPolicy.RELIABLE, DurabilityPolicy.TRANSIENT_LOCAL, 1)
# /contact/event
QOS_EVENT = _profile(ReliabilityPolicy.RELIABLE, DurabilityPolicy.VOLATILE, 50)
# /scan/log
QOS_LOG = _profile(ReliabilityPolicy.RELIABLE, DurabilityPolicy.VOLATILE, 100)
# /web/heartbeat
QOS_HEARTBEAT = _profile(ReliabilityPolicy.BEST_EFFORT, DurabilityPolicy.VOLATILE, 1)

# 계약 2.1절 연결 표의 QoS 열 이름으로 찾을 때 쓴다.
PROFILES = {
    'SENSOR': QOS_SENSOR,
    'STATE': QOS_STATE,
    'EVENT': QOS_EVENT,
    'LOG': QOS_LOG,
    'HEARTBEAT': QOS_HEARTBEAT,
}
