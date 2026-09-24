"""ROS 를 source 하지 않은 셸에서도 `python3 -m pytest src/robot_manager/test` 가 돌게 한다.

그리고 노드 테스트를 **다른 테스트 프로세스 · 떠 있는 노드 · 실기와 분리한다.** 이 패키지에는
격리가 없어서 셸의 ROS_DOMAIN_ID 를 그대로 물려받았다. 2026-09-21 CI 에서 test_sample_id_increases
가 받은 sample_id 가 `[1, 29, 2]` 였던 것(#122 의 ros 잡 실패)은 병렬로 돌던 다른 패키지의
`/robot/sample` 이 섞인 것이다(#126).
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# 노드 테스트를 다른 테스트 프로세스 · 떠 있는 Virtual · 실기와 분리한다(#126).
# rclpy.init() 전에 정해야 하므로 import 시점에 건다. 헬퍼는 contact_scan_interfaces 가
# 설치하지만, ROS 를 source 하지 않은 셸에서도 돌게 소스 경로를 대비로 둔다.
try:
    from contact_scan_testing import apply_isolated_ros_env  # noqa: E402
except ImportError:  # pragma: no cover - ROS 를 source 하지 않은 셸
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'contact_scan_interfaces'))
    from contact_scan_testing import apply_isolated_ros_env  # noqa: E402

apply_isolated_ros_env()
