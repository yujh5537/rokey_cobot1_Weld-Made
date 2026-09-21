"""노드 배선 테스트: 샘플 → /robot/stop → /safety/status, /safety/reset (로봇 · 드라이버 연결 없음).

executor 를 테스트가 직접 한 스텝씩 돌린다. 별도 스레드로 spin 하면 결과가 부하에 흔들린다.
"""
import math
import time

import pytest

rclpy = pytest.importorskip('rclpy')
pytest.importorskip('contact_scan_interfaces')

from contact_scan_interfaces.msg import ReasonCode, RobotSample, RobotStatus, SafetyStatus  # noqa: E402
from contact_scan_interfaces.srv import ResetSafety, StopRobot  # noqa: E402
from contact_scan_qos import QOS_SENSOR, QOS_STATE  # noqa: E402
from rclpy.executors import SingleThreadedExecutor  # noqa: E402
from rclpy.parameter import Parameter  # noqa: E402
from safety_monitor.safety_monitor import SafetyMonitorNode  # noqa: E402

MM = 1e-3
Z0 = 0.080
# 테스트용 값이다. 실기 · sim 의 값은 contact_scan_bringup/config/*.yaml 에 있다
PARAMS = {
    'over_force_n': 30.0, 'drop_limit_m': 5 * MM,
    'sample_stale_ms': 300, 'robot_status_timeout_ms': 600, 'confirm_n': 1,
    'startup_grace_s': 0.0,      # 테스트는 유예 없이 본다. 실제 값은 yaml 에 있다
    'stop_confirm_timeout_s': 0.3, 'stop_retry_period_s': 0.4,
    'status_publish_period_s': 1.0, 'check_period_s': 0.05,
}


def overrides(**changes):
    values = {**PARAMS, **changes}
    return [Parameter(k, value=v) for k, v in values.items() if v is not None]


class Rig:
    """safety_monitor + 가짜 robot_manager(샘플 · 상태 발행, /robot/stop 서버)."""

    def __init__(self, with_stop_server=True, **changes):
        self.node = SafetyMonitorNode(parameter_overrides=overrides(**changes))
        self.io = rclpy.create_node('fake_robot_manager')
        self.status_msgs = []
        self.stop_requests = []
        self.accept = True                        # 가짜 서버의 응답
        self.answer_stop = True                   # False 면 응답을 아예 돌려주지 않는다(드라이버 무응답)
        self.sample_pub = self.io.create_publisher(RobotSample, '/robot/sample', QOS_SENSOR)
        self.status_pub = self.io.create_publisher(RobotStatus, '/robot/status', QOS_STATE)
        self.io.create_subscription(SafetyStatus, '/safety/status', self.status_msgs.append, QOS_STATE)
        self.reset_client = self.io.create_client(ResetSafety, '/safety/reset')
        if with_stop_server:
            self.io.create_service(StopRobot, '/robot/stop', self.on_stop)
        self.executor = SingleThreadedExecutor()
        self.executor.add_node(self.node)
        self.executor.add_node(self.io)
        self.sample_id = 0
        # 기동 직후 1회 발행한 SafetyStatus 까지 받고 나서 시작한다 (STATE 는 TRANSIENT_LOCAL)
        self.pump(until=lambda: self.sample_pub.get_subscription_count() > 0
                  and self.reset_client.service_is_ready() and self.status_msgs
                  and (not with_stop_server or self.node.stop_client.service_is_ready()))

    def close(self):
        self.executor.shutdown()
        self.io.destroy_node()
        self.node.destroy_node()

    def on_stop(self, request, response):
        self.stop_requests.append(request)
        while not self.answer_stop:               # 응답을 미룬다. 호출자가 막히면 테스트가 여기서 멎는다
            return response                       # (막히지 않으므로 돌아온다. accepted 기본값 False)
        response.accepted = self.accept
        response.reason_code = ReasonCode.OK if self.accept else ReasonCode.ROBOT_DISCONNECTED
        response.detail = '' if self.accept else '드라이버 미연결'
        return response

    def pump(self, seconds=5.0, until=None):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline and not (until and until()):
            self.executor.spin_once(timeout_sec=0.01)
        return until() if until else True

    def send(self, fz=0.0, z=Z0, operation=RobotSample.OP_SLIDE, motion_id=4, valid=True):
        self.sample_id += 1
        msg = RobotSample()
        msg.sample_id = self.sample_id
        msg.frame_id = 'base_link'
        msg.pose_stamp = msg.force_stamp = self.io.get_clock().now().to_msg()
        msg.pose.position.x, msg.pose.position.y, msg.pose.position.z = 0.4, 0.0, z
        msg.wrench.force.x, msg.wrench.force.y, msg.wrench.force.z = 0.1, 0.2, fz
        msg.valid, msg.operation, msg.motion_id = valid, operation, motion_id
        self.sample_pub.publish(msg)
        self.pump(0.02)
        return msg

    def status(self, connected=True, moving=False):
        msg = RobotStatus()
        msg.stamp = self.io.get_clock().now().to_msg()
        msg.connected, msg.moving = connected, moving
        self.status_pub.publish(msg)
        self.pump(0.05)
        return msg

    @property
    def last(self) -> SafetyStatus:
        return self.status_msgs[-1]

    def wait_stop(self, count=1, timeout_s=3.0):
        self.pump(timeout_s, until=lambda: len(self.stop_requests) >= count)
        return self.stop_requests


@pytest.fixture
def ros():
    rclpy.init()
    yield
    rclpy.try_shutdown()


@pytest.fixture
def rig(ros):
    r = Rig()
    yield r
    r.close()


def test_publishes_ok_on_startup(rig):
    assert rig.status_msgs
    first = rig.status_msgs[0]
    assert first.level == SafetyStatus.LEVEL_OK and first.reason_code == ReasonCode.OK
    assert not first.latched and not first.stop_required and not first.stop_confirmed
    assert not first.position_valid and math.isnan(first.position.x)      # 미측정은 0 이 아니다


def test_over_force_requests_stop_and_latches(rig):
    rig.status(moving=True)
    rig.send(fz=-40.0, motion_id=11)
    requests = rig.wait_stop()
    assert len(requests) == 1
    assert requests[0].requester == 'safety_monitor' and requests[0].reason == ReasonCode.OVER_FORCE
    assert '40' in requests[0].detail and requests[0].request_id

    rig.pump(0.2)
    s = rig.last
    assert s.level == SafetyStatus.LEVEL_STOP and s.latched and s.stop_required
    assert s.reason_code == ReasonCode.OVER_FORCE and s.motion_id == 11
    assert s.position_valid and s.position.z == pytest.approx(Z0)
    assert not s.stop_confirmed and '완료 대기' in s.detail                # 접수 ≠ 정지 완료

    rig.status(connected=True, moving=False)                              # 정지 완료
    assert rig.last.stop_confirmed and rig.last.latched                   # 래치는 그대로


def test_drop_limit_uses_first_slide_sample(rig):
    rig.status(moving=True)
    rig.send(z=Z0, operation=RobotSample.OP_SLIDE)
    rig.send(z=Z0 - 4.9 * MM, operation=RobotSample.OP_SLIDE)
    assert rig.stop_requests == []
    rig.send(z=Z0 - 5.2 * MM, operation=RobotSample.OP_SLIDE)
    assert rig.wait_stop()[0].reason == ReasonCode.DROP_LIMIT
    assert rig.last.reason_code == ReasonCode.DROP_LIMIT


def test_stop_is_requested_once_per_condition(rig):
    rig.status(moving=True)
    for _ in range(5):
        rig.send(fz=-40.0)
    rig.pump(0.2)
    assert len(rig.stop_requests) == 1                                    # 매 샘플마다 두드리지 않는다


def test_rejected_stop_is_reported(rig):
    rig.accept = False
    rig.status(moving=True)
    rig.send(fz=-40.0)
    rig.wait_stop()
    rig.pump(0.2)
    assert rig.last.stop_required and not rig.last.stop_confirmed
    assert '거절' in rig.last.detail and '드라이버 미연결' in rig.last.detail


def test_unconfirmed_stop_escalates_and_retries_slowly(rig):
    """드라이버가 무응답이면 /robot/stop 도 /robot/status 도 같이 죽는다. 그 사실을 계속 올려야 한다."""
    rig.answer_stop = False                                               # 응답 accepted=False
    rig.status(moving=True)
    rig.send(fz=-40.0)
    rig.wait_stop()
    rig.pump(0.5)                                                         # stop_confirm_timeout_s 0.3 초과
    assert '물리 비상정지' in rig.last.detail
    assert rig.last.level == SafetyStatus.LEVEL_STOP and not rig.last.stop_confirmed
    before = len(rig.stop_requests)
    rig.pump(0.5)                                                         # 재시도 주기 0.4
    assert len(rig.stop_requests) > before
    assert len(rig.stop_requests) < 10                                    # 느리게만 다시 부른다


def test_without_stop_server(ros):
    r = Rig(with_stop_server=False)
    try:
        r.status(moving=True)
        r.send(fz=-40.0)
        r.pump(0.15)
        assert r.last.level == SafetyStatus.LEVEL_STOP and r.last.latched
        assert r.last.stop_required and not r.last.stop_confirmed
        assert '서버가 없다' in r.last.detail
        # 확인 제한 시간을 넘겨 UNCONFIRMED 로 올라가도 거절 사유는 남아 있어야 한다
        r.pump(0.4)
        assert '물리 비상정지' in r.last.detail and '서버가 없다' in r.last.detail
    finally:
        r.close()


def test_reset_refuses_while_condition_is_true_then_succeeds(rig):
    rig.status(moving=True)
    rig.send(fz=-40.0)
    rig.wait_stop()

    future = rig.reset_client.call_async(ResetSafety.Request(request_id='r1'))
    assert rig.pump(3.0, until=future.done)
    assert not future.result().success and future.result().reason_code == ReasonCode.CONDITION_ACTIVE
    assert 'OVER_FORCE' in future.result().detail and rig.last.latched

    rig.send(fz=0.0)                                                      # 조건 해소
    future = rig.reset_client.call_async(ResetSafety.Request(request_id='r2'))
    assert rig.pump(3.0, until=future.done)
    assert future.result().success
    rig.pump(0.1)
    assert not rig.last.latched and rig.last.level == SafetyStatus.LEVEL_OK
    assert not rig.last.stop_required                                     # 정지 요청 상태도 같이 지운다


def test_reset_is_idempotent(rig):
    future = rig.reset_client.call_async(ResetSafety.Request(request_id='r0'))
    assert rig.pump(3.0, until=future.done)
    assert future.result().success


def test_sample_gap_warns_when_idle_and_stops_when_moving(rig):
    rig.status(moving=False)
    rig.send()
    rig.pump(0.5)                                                         # sample_stale_ms 300 초과
    assert rig.last.level == SafetyStatus.LEVEL_WARN
    assert rig.last.reason_code == ReasonCode.SAMPLE_STALE
    assert rig.stop_requests == []                                        # 서 있으면 정지를 요청하지 않는다


def test_no_freshness_alarm_before_first_message(rig):
    rig.pump(0.6)
    assert rig.last.level == SafetyStatus.LEVEL_OK and rig.stop_requests == []


def test_warn_then_error_does_not_kill_the_node(rig):
    """rclpy 는 같은 줄에서 severity 가 바뀌면 ValueError 를 던진다. 그러면 타이머 콜백에서 노드가 죽는다.

    2차 감시가 통째로 사라지는 경로라 회귀 테스트로 고정한다 (이슈 #102).
    """
    # 1) 서 있는 동안 샘플이 끊긴다 → WARN
    rig.status(moving=False)
    rig.send()
    rig.pump(0.5)                                                         # sample_stale_ms 300 초과
    assert rig.last.level == SafetyStatus.LEVEL_WARN

    # 2) 같은 조건이 이번에는 STOP 으로 난다 → 같은 자리에서 severity 가 바뀐다
    rig.status(moving=True)
    rig.send()
    rig.pump(0.5)
    assert rig.last.level == SafetyStatus.LEVEL_STOP
    assert rig.last.reason_code == ReasonCode.SAMPLE_STALE

    # 노드가 살아서 계속 판정하고 발행한다
    before = len(rig.status_msgs)
    rig.send(fz=-40.0)
    rig.pump(0.3)
    assert len(rig.status_msgs) > before
    assert 'OVER_FORCE' in rig.node.state.watch.active                    # 새 조건도 계속 판정한다
    assert rig.last.reason_code == ReasonCode.SAMPLE_STALE                # reason_code 는 래치를 건 첫 원인


def test_set_parameters_validates(rig):
    assert rig.node.set_parameters([Parameter('drop_limit_m', value=0.003)])[0].successful
    assert rig.node.state.watch.limits.drop_limit_m == 0.003
    bad = rig.node.set_parameters([Parameter('over_force_n', value=-1.0)])[0]
    assert not bad.successful and rig.node.state.watch.limits.over_force_n == 30.0


@pytest.mark.parametrize('missing', list(PARAMS))
def test_does_not_start_when_a_parameter_is_missing(ros, missing):
    with pytest.raises(Exception, match=missing):
        SafetyMonitorNode(parameter_overrides=overrides(**{missing: None}))
