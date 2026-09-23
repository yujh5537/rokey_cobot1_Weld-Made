"""encoders.py 의 이름 표가 contact_scan_interfaces 의 상수와 같은지 확인한다.

표는 손으로 옮겨 적은 것이라 계약에 상수가 늘어나면 조용히 어긋난다.
어긋나면 encode_* 가 ValueError 를 내고, 구독 보호막이 그 줄을 버리거나
완료 통지가 통째로 안 나간다. 정작 알려야 할 코드일수록 웹이 못 받는다.
(#161 리뷰: ReasonCode 407 이 빠져 있었다)

ROS 를 source 하지 않은 셸에서는 skip 되고, colcon test · CI 에서는 실행된다.
"""

import pytest
from mqtt_bridge.encoders import (
    CONTACT_EVENT_TYPE_NAMES, REASON_NAMES, SAFETY_LEVEL_NAMES,
    SCAN_DIRECTION_NAMES, SCAN_LOG_LEVEL_NAMES, SCAN_PHASE_NAMES,
)

pytest.importorskip('contact_scan_interfaces')

from contact_scan_interfaces.msg import ContactEvent  # noqa: E402
from contact_scan_interfaces.msg import ReasonCode  # noqa: E402
from contact_scan_interfaces.msg import SafetyStatus  # noqa: E402
from contact_scan_interfaces.msg import ScanLog  # noqa: E402
from contact_scan_interfaces.msg import ScanState  # noqa: E402


def _constants(msg_type, prefix=''):
    """rosidl 이 생성한 상수 중 prefix 로 시작하는 것을 {값: 이름(접두어 제외)} 으로."""
    names = [
        n for n in vars(type(msg_type))
        if n.isupper() and not n.startswith('_') and n.startswith(prefix)
        # SLOT_TYPES 처럼 상수가 아닌 rosidl 내부 속성은 뺀다 (접두어가 없는 표 때문에 필요)
        and isinstance(getattr(msg_type, n), int) and not isinstance(getattr(msg_type, n), bool)
    ]
    return {getattr(msg_type, n): n[len(prefix):] for n in names}


TABLES = [
    ('REASON_NAMES', REASON_NAMES, ReasonCode(), ''),
    ('SCAN_PHASE_NAMES', SCAN_PHASE_NAMES, ScanState(), 'PHASE_'),
    ('SCAN_DIRECTION_NAMES', SCAN_DIRECTION_NAMES, ScanState(), 'DIR_'),
    ('CONTACT_EVENT_TYPE_NAMES', CONTACT_EVENT_TYPE_NAMES, ContactEvent(), 'TYPE_'),
    ('SCAN_LOG_LEVEL_NAMES', SCAN_LOG_LEVEL_NAMES, ScanLog(), 'LEVEL_'),
    ('SAFETY_LEVEL_NAMES', SAFETY_LEVEL_NAMES, SafetyStatus(), 'LEVEL_'),
]


@pytest.mark.parametrize('name, table, msg, prefix', TABLES, ids=[t[0] for t in TABLES])
def test_name_table_matches_interface(name, table, msg, prefix):
    """빠진 코드도 남는 코드도 없어야 한다. 값·이름이 모두 같아야 한다."""
    assert table == _constants(msg, prefix), name


def test_reason_names_covers_stop_unconfirmed():
    """계약 v0.1.17 에서 늘어난 코드. 정지 미확인을 웹에 알리는 유일한 경로다."""
    assert REASON_NAMES[ReasonCode.STOP_UNCONFIRMED] == 'STOP_UNCONFIRMED'
