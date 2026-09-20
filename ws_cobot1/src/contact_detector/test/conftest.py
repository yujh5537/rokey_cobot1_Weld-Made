"""ROS 를 source 하지 않은 셸에서도 `python3 -m pytest src/contact_detector/test` 가 돌게 한다."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
