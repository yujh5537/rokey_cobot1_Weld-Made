"""contact_scan_qos 의 프로파일이 계약 6.3절 표와 같은지 확인한다."""

import contact_scan_qos
import pytest
from rclpy.qos import DurabilityPolicy
from rclpy.qos import HistoryPolicy
from rclpy.qos import ReliabilityPolicy

BEST_EFFORT = ReliabilityPolicy.BEST_EFFORT
RELIABLE = ReliabilityPolicy.RELIABLE
VOLATILE = DurabilityPolicy.VOLATILE
TRANSIENT_LOCAL = DurabilityPolicy.TRANSIENT_LOCAL

# 계약 6.3절 표
CONTRACT = {
    'SENSOR': (BEST_EFFORT, VOLATILE, 5),
    'STATE': (RELIABLE, TRANSIENT_LOCAL, 1),
    'EVENT': (RELIABLE, VOLATILE, 50),
    'LOG': (RELIABLE, VOLATILE, 100),
    'HEARTBEAT': (BEST_EFFORT, VOLATILE, 1),
}


def test_profile_names_match_contract():
    assert set(contact_scan_qos.PROFILES) == set(CONTRACT)


@pytest.mark.parametrize('name', sorted(CONTRACT))
def test_profile_values_match_contract(name):
    reliability, durability, depth = CONTRACT[name]
    profile = contact_scan_qos.PROFILES[name]
    assert profile.reliability == reliability
    assert profile.durability == durability
    assert profile.history == HistoryPolicy.KEEP_LAST
    assert profile.depth == depth


@pytest.mark.parametrize('name', sorted(CONTRACT))
def test_module_constant_is_the_same_object_as_table_entry(name):
    assert getattr(contact_scan_qos, f'QOS_{name}') is contact_scan_qos.PROFILES[name]
