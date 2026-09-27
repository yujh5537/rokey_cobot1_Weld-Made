"""ROS 를 source 하지 않은 셸에서도 `python3 -m pytest src/contact_detector/test` 가 돌게 한다.

그리고 노드 테스트(test_node.py)를 **다른 테스트 프로세스 · 떠 있는 노드 · 실기와 분리한다.**
2026-09-22 16:03 에 이 패키지의 테스트가 `ROS_DOMAIN_ID=30` · `SUBNET` 셸에서 돌아
실기의 `/contact/event` 에 가짜 이벤트를 넣었다(#126).
"""

from pathlib import Path
import sys

import pytest

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

from contact_detector.detector_core import DetectorConfig  # noqa: E402
from contact_detector.detector_core import OP_DESCEND  # noqa: E402
from contact_detector.detector_core import Sample  # noqa: E402

# 테스트용 값이다. 실기 · sim 의 값은 contact_scan_bringup/config/*.yaml 에 있다
DT = 0.02
BASELINE = (0.1, 2.0, -1.5)      # PR #57 처럼 Fy 에 잔류 외력이 남은 상황


@pytest.fixture
def config():
    return DetectorConfig(contact_threshold_n=3.0, debounce_n=3, over_force_n=30.0, over_force_debounce_n=1)


def make_samples(extra_fz, operation=OP_DESCEND, motion_id=1, z0=0.200, speed=0.005, start_id=1):
    """기준값 위에 Fz 로 extra_fz[i] 를 더한 샘플 열. z 는 speed 로 등속 하강한다."""
    samples = []
    for i, extra in enumerate(extra_fz):
        t = i * DT
        samples.append(Sample(
            sample_id=start_id + i, pose_stamp=t, force_stamp=t + 0.004,
            position=(0.4, 0.0, z0 - speed * t),
            force=(BASELINE[0], BASELINE[1], BASELINE[2] + extra),
            motion_id=motion_id, operation=operation))
    return samples
