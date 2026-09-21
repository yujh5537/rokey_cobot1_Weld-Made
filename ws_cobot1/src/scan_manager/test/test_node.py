"""노드 껍데기가 /scan/state 를 계약대로 발행하는지 확인한다 (로봇 · 드라이버 연결 없음)."""

import os
import signal
import subprocess
import sys
import threading
import time

import pytest

rclpy = pytest.importorskip('rclpy')
pytest.importorskip('contact_scan_interfaces')

from conftest import READY  # noqa: E402
from contact_scan_interfaces.msg import ScanLog  # noqa: E402
from contact_scan_interfaces.msg import ScanState  # noqa: E402
from contact_scan_qos import QOS_STATE  # noqa: E402
import fake_peers as F  # noqa: E402
from rclpy.executors import SingleThreadedExecutor  # noqa: E402
from rclpy.parameter import Parameter  # noqa: E402
from scan_manager.contract_enums import Reason  # noqa: E402
from scan_manager.scan_manager import _Job  # noqa: E402
from scan_manager.scan_manager import ScanManager  # noqa: E402
from scan_manager.state_machine import Command  # noqa: E402
from scan_manager.state_machine import Phase  # noqa: E402
from scan_manager.state_machine import Signal  # noqa: E402
from sequence_helpers import isolated_ros_env  # noqa: E402

os.environ.update(isolated_ros_env())  # 이 파일만 돌려도 조 공용 도메인(30)에 뜨지 않는다


@pytest.fixture
def ros():
    rclpy.init()
    yield
    rclpy.try_shutdown()


def _spin_until(executor, condition, timeout_s=5.0):
    deadline = time.monotonic() + timeout_s
    while not condition() and time.monotonic() < deadline:
        executor.spin_once(timeout_sec=0.1)
    return condition()


def test_publishes_idle_then_changes(ros):
    node = ScanManager()
    # 발행 뒤에 붙은 구독자도 TRANSIENT_LOCAL 로 마지막 상태를 받는다
    listener = rclpy.create_node('scan_state_listener')
    received = []
    listener.create_subscription(ScanState, '/scan/state', received.append, QOS_STATE)
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    executor.add_node(listener)
    try:
        assert _spin_until(executor, lambda: received)
        first = received[0]
        assert first.phase == ScanState.PHASE_IDLE
        assert first.scan_id == ''
        assert first.direction == ScanState.DIR_NONE
        assert (first.progress, first.progress_total) == (0, 4)
        assert first.motion_id == 0

        # 상태가 바뀌면 주기를 기다리지 않고 발행한다
        node.state_machine.request(
            Command.START, conditions=READY, scan_id='20260918-210000-0001')
        assert _spin_until(
            executor,
            lambda: any(m.phase == ScanState.PHASE_PREPARING for m in received))
        assert received[-1].scan_id == '20260918-210000-0001'
    finally:
        executor.shutdown()
        listener.destroy_node()
        node.destroy_node()


def test_a_late_node_reads_a_stalled_publishers_retained_message_as_stale(ros):
    """발행이 멈춘 채 살아 있는 발행자에 늦게 붙으면, 옛 샘플을 "방금" 받는다.

    TRANSIENT_LOCAL 은 **발행자 프로세스가 살아 있는 동안** 늦은 구독자에게 마지막 샘플을 준다.
    여기서는 타이머만 멈춘다(프로세스는 산다) — 감시자가 행에 걸리거나 발행 타이머가 죽은 경우다.
    **수신 시각으로 보면 이때 START 가 통과한다.** stamp 로 봐야 걸린다(이슈 #120).

    발행자 프로세스가 아예 죽으면 늦은 구독자는 아무것도 받지 못하고, 그것은 지금도 "미수신"으로
    거절된다(sim 종단에서 확인). 이 관문이 실제로 막는 쪽은 **이미 떠 있던** scan_manager 가
    마지막 "안전 정상"을 영원히 들고 있는 경우이며, 그것은 test_node_scan.py 가 시험한다.
    """
    peers = F.FakePeers()
    executor = SingleThreadedExecutor()
    executor.add_node(peers)
    node = None
    try:
        for _ in range(20):                       # 몇 번 발행하게 둔다
            executor.spin_once(timeout_sec=0.05)
        peers.quiet()                             # 여기서 죽는다. 마지막 메시지는 latched=false 다
        time.sleep(0.4)

        node = ScanManager(parameter_overrides=[
            Parameter('safety_status_timeout_s', value=0.3),
            Parameter('robot_status_timeout_s', value=0.3)])
        executor.add_node(node)
        assert _spin_until(executor, lambda: node.conditions().safety_latched is not None)

        conditions = node.conditions()
        assert conditions.safety_latched is False          # 죽은 감시자의 "안전 정상"을 받았다
        assert conditions.safety_status_age_s > 0.3        # 그러나 stamp 는 오래됐다
        reason, detail = node.state_machine.check(
            Command.START, conditions=conditions, scan_id='x')
        assert reason is Reason.SAFETY_LATCHED and '끊김' in detail
    finally:
        executor.shutdown()
        if node is not None:
            node.destroy_node()
        peers.destroy_node()


def test_rejects_non_positive_period(ros):
    with pytest.raises(ValueError):
        ScanManager(parameter_overrides=[
            Parameter('state_publish_period_s', value=0.0)])


@pytest.mark.parametrize('gap_s', [0.0, 0.05, 0.5])
def test_two_sigints_exit_quietly(gap_s):
    """launch 의 Ctrl-C 는 SIGINT 를 두 번 보낼 수 있다. 트레이스백 · 0 이 아닌 종료 코드 없이 끝나야 한다."""
    env = {**os.environ, **isolated_ros_env()}
    process = subprocess.Popen(
        [sys.executable, '-c', 'from scan_manager.scan_manager import main; main()'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True)
    lines, ready = [], threading.Event()

    def read():
        for line in process.stderr:
            lines.append(line)
            if 'scan_manager 준비' in line:
                ready.set()
    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    try:
        assert ready.wait(30.0), ''.join(lines)
        process.send_signal(signal.SIGINT)
        time.sleep(gap_s)
        process.send_signal(signal.SIGINT)
        assert process.wait(timeout=30.0) == 0, ''.join(lines)
    finally:
        process.kill()
    reader.join(timeout=5.0)
    assert 'Traceback' not in ''.join(lines), ''.join(lines)


def test_state_change_while_the_context_is_down_does_not_raise():
    """종료 경로의 마지막 상태 전이(STOPPED · ERROR)가 발행을 부른다. context 가 내려간 뒤라도 조용히 넘어간다.

    SIGINT 는 rclpy 의 처리기가 context 를 먼저 내리고, close() 는 그 뒤에 불린다. 그 사이를 재현하려고
    _closing 을 세우지 않은 채 context 만 내린다(2026-09-21 Virtual Mode 에서 본 트레이스백의 조건).
    """
    context = rclpy.Context()
    rclpy.init(context=context)
    node = ScanManager(context=context)
    try:
        rclpy.shutdown(context=context)
        assert not node._closing.is_set()   # 아직 close() 전이다

        node.state_machine.request(Command.START, conditions=READY, scan_id='20260921-120000-0001')
        node.state_machine.notify(Signal.FAILED, reason_code=204, detail='종료 중')
        node._publish_state_periodic()      # 상태 발행 타이머가 한 번 더 돌아도 된다
        node.log(ScanLog.LEVEL_ERROR, 204, '종료 중 로그')
    finally:
        node.destroy_node()


def test_shutdown_exception_is_not_recorded_as_a_job_failure():
    """종료가 깨운 예외는 작업의 실패가 아니다. FAILED 로 보내면 그 전이가 또 발행을 부른다."""
    context = rclpy.Context()
    rclpy.init(context=context)
    node = ScanManager(context=context)
    try:
        scan_id = '20260921-120000-0002'
        node.state_machine.request(Command.START, conditions=READY, scan_id=scan_id)
        rclpy.shutdown(context=context)
        job = _Job(scan_id, params=None)
        assert node._internal_failure(job, RuntimeError('publisher context is invalid')) is None
        assert node.state_machine.phase is not Phase.ERROR   # FAILED 로 보내지 않았다
    finally:
        node.destroy_node()


def test_publish_failure_outside_shutdown_still_raises(ros):
    """조용한 종료가 평소의 발행 실패까지 덮지 않는다."""
    node = ScanManager()

    class Broken:
        def publish(self, _msg):
            raise RuntimeError('발행 실패')

    try:
        with pytest.raises(RuntimeError):
            node._publish_quietly(Broken(), lambda: None)
    finally:
        node.destroy_node()
