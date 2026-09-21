"""ROS 를 source 하지 않은 셸에서도 `python3 -m pytest src/scan_manager/test` 가 돌게 한다."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scan_manager.state_machine import Command  # noqa: E402
from scan_manager.state_machine import Conditions  # noqa: E402
from scan_manager.state_machine import ScanStateMachine  # noqa: E402
from scan_manager.state_machine import Signal  # noqa: E402

# /robot/status · /safety/status 를 "방금 받았다"는 뜻. 한계 시간은 real.yaml 과 같은 값이다.
# 끊김 자체를 시험하는 테스트만 나이 · 한계를 직접 준다(이슈 #120).
FRESH_STATUS = dict(
    robot_status_age_s=0.0, safety_status_age_s=0.0,
    robot_status_timeout_s=2.0, safety_status_timeout_s=5.0)
READY = Conditions(robot_connected=True, safety_latched=False, **FRESH_STATUS)

# 정상 경로에서 phase 를 하나씩 앞으로 보내는 Signal 순서 (START 뒤)
_FORWARD = (
    [Signal.PREPARE_DONE, Signal.TOP_FOUND]
    + [Signal.EDGE_FOUND] * 4
    + [Signal.GEOMETRY_DONE, Signal.HOMING_DONE]
)


def drive(sm, steps, scan_id='20260918-210000-0001'):
    """START 뒤 정상 경로의 Signal 을 steps 개만큼 보낸다."""
    outcome = sm.request(Command.START, conditions=READY, scan_id=scan_id)
    assert outcome.accepted, outcome
    for signal in _FORWARD[:steps]:
        sm.notify(signal)
    return sm


@pytest.fixture
def sm():
    return ScanStateMachine()
