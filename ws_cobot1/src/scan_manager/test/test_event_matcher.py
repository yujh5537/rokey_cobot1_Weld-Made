"""ContactEvent ↔ Result 짝 맞추기: 도착 순서, motion_id 대조 (ROS 없음)."""

from dataclasses import dataclass
import threading
import time

import pytest
from scan_manager import event_matcher as M

CONTACT, EDGE, OVER_FORCE = 0, 1, 2
SCAN = '20260920-120000-0001'


@dataclass
class Event:
    event_id: int
    motion_id: int
    type: int = EDGE
    scan_id: str = SCAN


@pytest.fixture
def ignored():
    return []


@pytest.fixture
def matcher(ignored):
    return M.EventMatcher(on_ignored=lambda event, reason: ignored.append((event.event_id, reason)))


def test_event_before_result(matcher):
    matcher.begin(SCAN, 3, EDGE)
    event = Event(event_id=11, motion_id=3)
    assert matcher.offer(event)
    assert matcher.wait(11, timeout_s=0.0) is event


def test_event_after_result(matcher):
    matcher.begin(SCAN, 3, EDGE)
    event = Event(event_id=12, motion_id=3)
    timer = threading.Timer(0.05, matcher.offer, args=(event,))
    timer.start()
    started = time.monotonic()
    assert matcher.wait(12, timeout_s=2.0) is event
    assert time.monotonic() - started < 1.0  # 도착하면 바로 깨어난다
    timer.join()


def test_event_that_never_arrives(matcher):
    matcher.begin(SCAN, 3, EDGE)
    matcher.offer(Event(event_id=13, motion_id=3))
    assert matcher.wait(14, timeout_s=0.05) is None  # 다른 event_id 로는 짝이 맞지 않는다


def test_result_without_event_id_has_no_pair(matcher):
    matcher.begin(SCAN, 3, EDGE)
    matcher.offer(Event(event_id=15, motion_id=3))
    assert matcher.wait(0, timeout_s=0.0) is None


@pytest.mark.parametrize('motion_id', [0, 2, 4])
def test_motion_id_mismatch_is_ignored_and_reported(matcher, ignored, motion_id):
    matcher.begin(SCAN, 3, EDGE)
    assert not matcher.offer(Event(event_id=16, motion_id=motion_id))
    assert ignored == [(16, M.IGNORED_MOTION_ID)]
    assert matcher.wait(16, timeout_s=0.0) is None


def test_event_without_a_motion_in_progress_is_ignored(matcher, ignored):
    assert not matcher.offer(Event(event_id=17, motion_id=1))
    matcher.begin(SCAN, 1, EDGE)
    matcher.end()
    assert not matcher.offer(Event(event_id=18, motion_id=1))
    assert ignored == [(17, M.IGNORED_NO_MOTION), (18, M.IGNORED_NO_MOTION)]


def test_wrong_type_is_not_a_measurement(matcher, ignored):
    matcher.begin(SCAN, 2, CONTACT)  # DESCEND 는 CONTACT 만 측정값이다
    assert not matcher.offer(Event(event_id=19, motion_id=2, type=EDGE))
    assert not matcher.offer(Event(event_id=20, motion_id=2, type=OVER_FORCE))
    assert matcher.offer(Event(event_id=21, motion_id=2, type=CONTACT))
    assert [reason for _, reason in ignored] == [M.IGNORED_TYPE] * 2


def test_move_motion_takes_no_event(matcher, ignored):
    matcher.begin(SCAN, 5)  # OP_MOVE_TO · OP_HOME
    assert not matcher.offer(Event(event_id=22, motion_id=5, type=CONTACT))
    assert ignored == [(22, M.IGNORED_TYPE)]


def test_scan_id_is_checked_only_when_tagged(matcher, ignored):
    matcher.begin(SCAN, 3, EDGE)
    assert matcher.offer(Event(event_id=23, motion_id=3, scan_id=''))
    assert not matcher.offer(Event(event_id=24, motion_id=3, scan_id='20260920-110000-9999'))
    assert ignored == [(24, M.IGNORED_SCAN_ID)]


def test_begin_drops_events_of_the_previous_motion(matcher):
    matcher.begin(SCAN, 3, EDGE)
    matcher.offer(Event(event_id=25, motion_id=3))
    matcher.begin(SCAN, 4, EDGE)
    assert matcher.wait(25, timeout_s=0.0) is None


def test_end_wakes_a_waiter(matcher):
    matcher.begin(SCAN, 3, EDGE)
    threading.Timer(0.05, matcher.end).start()
    started = time.monotonic()
    assert matcher.wait(26, timeout_s=5.0) is None
    assert time.monotonic() - started < 2.0


def test_motion_id_zero_cannot_begin(matcher):
    with pytest.raises(ValueError):
        matcher.begin(SCAN, 0, EDGE)
