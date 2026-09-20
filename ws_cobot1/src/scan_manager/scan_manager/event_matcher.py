"""ContactEvent ↔ ExecuteMotion.Result 짝 맞추기 (순수 Python, rclpy 없음).

- 이벤트는 현재 동작의 motion_id 와 대조한 뒤에만 쓴다(계약 5.4절, .claude/rules/ros2-nodes.md).
  motion_id 가 0 이거나 다르면 쓰지 않고 on_ignored 로 알리기만 한다.
- 짝은 Result.event_id == ContactEvent.event_id 로 맞춘다.
- 이벤트는 Result 보다 먼저 올 수도 나중에 올 수도 있다. 먼저 온 것은 보관하고, 늦는 것은 wait() 가 기다린다.

이벤트 객체는 motion_id · event_id · type · scan_id · frame_id 속성만 본다(ContactEvent.msg 를 그대로 넣는다).
offer() 는 구독 콜백에서, begin() · wait() · end() 는 시퀀스 스레드에서 부른다.
"""

import threading
from typing import Callable, Optional

IGNORED_NO_MOTION = 'no_motion'            # 진행 중인 동작이 없다
IGNORED_MOTION_ID = 'motion_id_mismatch'   # motion_id 가 0 이거나 현재 동작과 다르다
IGNORED_SCAN_ID = 'scan_id_mismatch'       # 다른 작업의 이벤트
IGNORED_TYPE = 'type_mismatch'             # 이 동작이 기다리는 종류가 아니다 (예: DESCEND 중의 EDGE)
IGNORED_FRAME = 'frame_id_mismatch'        # 좌표의 프레임이 다르다. 좌표를 쓰는 쪽은 frame_id 를 확인한다(계약 1장)


class EventMatcher:

    def __init__(self, on_ignored: Optional[Callable[[object, str], None]] = None):
        self._on_ignored = on_ignored
        self._cond = threading.Condition()
        self._scan_id = ''
        self._motion_id = 0
        self._expected_type = None
        self._frame_id = ''
        self._events = {}

    def begin(self, scan_id: str, motion_id: int, expected_type=None, frame_id: str = '') -> None:
        """새 동작을 시작한다. 앞선 동작의 이벤트는 버린다.

        expected_type: 측정값으로 쓸 ContactEvent.type. None 이면 이 동작은 이벤트를 기다리지 않는다
        (OP_MOVE_TO · OP_HOME). 그동안 온 이벤트는 전부 무시된다.
        frame_id: 측정값으로 받을 좌표의 프레임. 주면 event.frame_id 가 다른 이벤트를 무시한다.
        """
        if not motion_id:
            raise ValueError('motion_id 는 0 이 아니어야 한다(0 = 없음)')
        with self._cond:
            self._scan_id = scan_id
            self._motion_id = int(motion_id)
            self._expected_type = expected_type
            self._frame_id = frame_id
            self._events = {}

    def end(self) -> None:
        with self._cond:
            self._motion_id = 0
            self._expected_type = None
            self._events = {}
            self._cond.notify_all()

    def offer(self, event) -> bool:
        """구독 콜백에서 부른다. 현재 동작의 측정값 후보로 보관했으면 True."""
        with self._cond:
            reason = self._why_ignored(event)
            if reason is None:
                self._events[int(event.event_id)] = event
                self._cond.notify_all()
                return True
        if self._on_ignored is not None:
            self._on_ignored(event, reason)
        return False

    def _why_ignored(self, event) -> Optional[str]:
        if not self._motion_id:
            return IGNORED_NO_MOTION
        if not event.motion_id or int(event.motion_id) != self._motion_id:
            return IGNORED_MOTION_ID
        # scan_id 는 contact_detector 가 /scan/state 에서 옮겨 적는 태그다. 비어 있으면 대조하지 않는다.
        if event.scan_id and event.scan_id != self._scan_id:
            return IGNORED_SCAN_ID
        if self._expected_type is None or int(event.type) != int(self._expected_type):
            return IGNORED_TYPE
        if self._frame_id and event.frame_id != self._frame_id:
            return IGNORED_FRAME
        return None

    def wait(self, event_id: int, timeout_s: float):
        """Result.event_id 와 짝이 맞는 이벤트를 돌려준다. timeout_s 안에 오지 않으면 None."""
        if not event_id:
            return None
        with self._cond:
            self._cond.wait_for(
                lambda: int(event_id) in self._events or not self._motion_id, timeout=timeout_s)
            return self._events.get(int(event_id))
