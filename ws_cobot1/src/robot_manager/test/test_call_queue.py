"""호출 큐 테스트 (T13). ROS도 두산 드라이버도 없이 돈다.

지키려는 것: 두산 서비스를 **동시에 두 개 보내지 않는다.** 동시에 부르면 dsr_controller2 가
모든 응답을 멈췄다(2026-09-20 Virtual).
"""
from robot_manager.call_queue import CallQueue


class FakeFuture:
    def __init__(self):
        self.callback = None

    def add_done_callback(self, callback):
        self.callback = callback

    def deliver(self, value):
        self._value = value
        self.callback(self)

    def result(self):
        return self._value


class FakeClient:
    """보낸 요청을 들고 있다가 시험에서 직접 응답을 넣는다."""

    def __init__(self, ready=True):
        self.ready = ready
        self.futures = []
        self.requests = []

    def service_is_ready(self):
        return self.ready

    def call_async(self, request):
        self.requests.append(request)
        future = FakeFuture()
        self.futures.append(future)
        return future


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_sends_one_at_a_time():
    clock, client = Clock(), FakeClient()
    queue = CallQueue(clock, timeout_s=1.0)
    got = []
    queue.submit(client, 'A', lambda r: got.append(('A', r)), 'a')
    queue.submit(client, 'B', lambda r: got.append(('B', r)), 'b')

    assert client.requests == ['A'], '첫 응답 전에 두 번째를 보내면 안 된다'
    client.futures[0].deliver('A응답')
    assert client.requests == ['A', 'B']
    assert got == [('A', 'A응답')]

    client.futures[1].deliver('B응답')
    assert got == [('A', 'A응답'), ('B', 'B응답')]


def test_timeout_reports_none_but_keeps_the_slot():
    """시간 초과를 알리는 것과 자리를 비우는 것은 다르다 (병후 리뷰, PR #72).

    알린 뒤에도 응답이 올 수 있으므로, 그 사이에 새 호출을 보내면 같은 서비스로
    여러 건이 동시에 뜬다.
    """
    clock, client = Clock(), FakeClient()
    queue = CallQueue(clock, timeout_s=0.5, abandon_after_s=5.0)
    got = []
    queue.submit(client, 'A', lambda r: got.append(r), 'a')
    queue.submit(client, 'B', lambda r: got.append(r), 'b')

    clock.t = 0.6
    queue.poll()
    assert got == [None], '시간 초과는 None 으로 알린다. 값을 지어내지 않는다'
    assert client.requests == ['A'], '아직 응답을 기다리므로 다음 호출을 보내지 않는다'
    assert queue.timeouts == 1
    assert queue.busy() is True

    clock.t = 2.0
    queue.poll()
    assert client.requests == ['A'], '포기 시간 전에는 계속 기다린다'

    clock.t = 6.0
    queue.poll()
    assert client.requests == ['A', 'B'], '포기 시간이 지나면 다음 호출을 보낸다'
    assert queue.busy() is True


def test_late_response_after_timeout_is_ignored():
    clock, client = Clock(), FakeClient()
    queue = CallQueue(clock, timeout_s=0.5, abandon_after_s=5.0)
    got = []
    queue.submit(client, 'A', lambda r: got.append(r), 'a')
    clock.t = 6.0
    queue.poll()          # 알리고, 포기까지 했다
    client.futures[0].deliver('늦게 온 응답')
    assert got == [None], '이미 시간 초과 처리한 호출의 늦은 응답은 버린다'


def test_missing_service_reports_none_without_sending():
    queue = CallQueue(Clock(), timeout_s=1.0)
    client = FakeClient(ready=False)
    got = []
    queue.submit(client, 'A', lambda r: got.append(r), 'a')
    assert got == [None]
    assert client.requests == []


def test_clear_waiting_drops_queued_calls_only():
    clock, client = Clock(), FakeClient()
    queue = CallQueue(clock, timeout_s=1.0)
    got = []
    queue.submit(client, 'A', lambda r: got.append(('A', r)), 'a')
    queue.submit(client, 'B', lambda r: got.append(('B', r)), 'b')
    queue.clear_waiting()
    assert got == [('B', None)], '보내지 않은 것만 취소한다'
    client.futures[0].deliver('A응답')
    assert ('A', 'A응답') in got
