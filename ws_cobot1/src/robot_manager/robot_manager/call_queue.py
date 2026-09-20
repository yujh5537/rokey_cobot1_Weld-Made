"""두산 서비스 호출을 한 번에 하나만 보내는 큐 (T13).

`get_current_posx`와 `get_tool_force`를 동시에 부르자 `dsr_controller2`가 모든 서비스 응답을
멈췄다(2026-09-20 Virtual, `docs/env/api-check-log.md`). 조회와 모션 명령이 섞이는 T13부터는
호출 지점이 여러 곳이라 한곳에서 줄을 세운다.

rclpy를 import하지 않는다. 클라이언트는 `service_is_ready()`와 `call_async()`만 있으면 된다.
"""
from collections import deque


class Call:
    def __init__(self, client, request, on_done, label):
        self.client, self.request, self.on_done, self.label = client, request, on_done, label
        self.sent_s = None
        self.reported = False      # 시간 초과를 호출자에게 알렸는가


class CallQueue:
    """`submit`한 순서대로 하나씩 보낸다. 응답 · 시간 초과 뒤에 다음 것을 보낸다.

    `on_done(response)`는 응답이 없으면 `None`으로 불린다. 호출자는 값을 0으로 채우지 않는다.
    """

    def __init__(self, now_s, timeout_s, logger=None, abandon_after_s=5.0):
        self.now_s, self.timeout_s, self.logger = now_s, timeout_s, logger
        # 시간 초과를 알린 뒤에도 이만큼은 다음 호출을 보내지 않는다. 응답이 늦을 뿐인
        # 요청이 살아 있는데 새로 보내면 같은 서비스로 여러 건이 동시에 뜬다
        # (병후 리뷰, PR #72). 드라이버가 느려지는 것은 멈추기 직전 증상이다
        self.abandon_after_s = abandon_after_s
        self.waiting = deque()
        self.current = None
        self.timeouts = 0

    def submit(self, client, request, on_done, label=''):
        self.waiting.append(Call(client, request, on_done, label))
        self.pump()

    def busy(self):
        """보낸 요청의 응답을 아직 기다리는 중인가."""
        return self.current is not None

    def pump(self):
        while self.current is None and self.waiting:
            call = self.waiting.popleft()
            if not call.client.service_is_ready():
                self.finish(call, None, '서비스 없음')
                continue
            self.current = call
            call.sent_s = self.now_s()
            future = call.client.call_async(call.request)
            future.add_done_callback(lambda fut, c=call: self.on_future(c, fut))
            return

    def on_future(self, call, future):
        if call is not self.current:
            return  # 시간 초과로 이미 넘어간 호출. 늦게 온 응답은 버린다
        try:
            response = future.result()
        except Exception as exc:
            response = None
            if self.logger:
                self.logger.warn(f'{call.label} 호출 실패: {exc}')
        self.current = None
        self.finish(call, response, '')
        self.pump()

    def poll(self):
        """시간 초과를 검사한다. 주기적으로(타이머에서) 부른다.

        시간 초과를 알리는 것과 그 자리를 비우는 것은 다르다. 알린 뒤에도 응답이 올 수
        있으므로 `abandon_after_s` 까지는 다음 호출을 보내지 않는다.
        """
        call = self.current
        if call is not None:
            waited = self.now_s() - call.sent_s
            if not call.reported and waited > self.timeout_s:
                call.reported = True
                self.timeouts += 1
                if self.logger:
                    self.logger.warn(f'{call.label} 응답 시간 초과')
                self.finish(call, None, '시간 초과')
            if waited <= self.abandon_after_s:
                return      # 아직 응답을 기다린다. 새로 보내지 않는다
            self.current = None
            if self.logger:
                self.logger.warn(f'{call.label} 응답을 {waited:.1f} s 기다리다 포기한다')
        self.pump()

    def finish(self, call, response, note):
        if call.on_done is not None:
            call.on_done(response)

    def clear_waiting(self):
        """보내지 않은 호출을 버린다. 보낸 호출의 응답은 그대로 기다린다."""
        dropped, self.waiting = list(self.waiting), deque()
        for call in dropped:
            self.finish(call, None, '취소')
