"""ROS 를 source 하지 않은 셸에서도 `python3 -m pytest src/safety_monitor/test` 가 돌게 한다.

그리고 노드 테스트를 **다른 테스트 프로세스 · 떠 있는 노드 · 실기와 분리한다.** rclpy 를 쓰는 테스트는
in-process 라도 DDS 로 나가므로, 같은 도메인에서 동시에 돌면 서로의 토픽 · 서비스를 발견한다
(`/robot/stop` · `/robot/sample` 처럼 이름이 겹친다). colcon test 는 패키지를 **병렬로** 돌리므로
격리가 없으면 CI 와 저녁 통합에서 간헐 실패가 난다(2026-09-20 확인: 병렬 7 failures, 순차 0).

번호를 고르는 규칙은 contact_scan_testing 에 있다(#126). PID 로 고르던 방식은
실행마다 1/9 로 겹쳤다 — 2026-09-21 CI 에서 scan_manager 시험과 7.2 초 겹쳤다.
rclpy.init() 전에 정해야 하므로 import 시점에 환경 변수를 세운다.
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
