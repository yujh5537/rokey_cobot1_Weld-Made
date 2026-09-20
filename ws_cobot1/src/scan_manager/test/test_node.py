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
from contact_scan_interfaces.msg import ScanState  # noqa: E402
from contact_scan_qos import QOS_STATE  # noqa: E402
from rclpy.executors import SingleThreadedExecutor  # noqa: E402
from rclpy.parameter import Parameter  # noqa: E402
from scan_manager.scan_manager import ScanManager  # noqa: E402
from scan_manager.state_machine import Command  # noqa: E402


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


def test_rejects_non_positive_period(ros):
    with pytest.raises(ValueError):
        ScanManager(parameter_overrides=[
            Parameter('state_publish_period_s', value=0.0)])


@pytest.mark.parametrize('gap_s', [0.0, 0.05, 0.5])
def test_two_sigints_exit_quietly(gap_s):
    """launch 의 Ctrl-C 는 SIGINT 를 두 번 보낼 수 있다. 트레이스백 · 0 이 아닌 종료 코드 없이 끝나야 한다."""
    env = {**os.environ, 'ROS_DOMAIN_ID': str(100 + os.getpid() % 100)}
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
