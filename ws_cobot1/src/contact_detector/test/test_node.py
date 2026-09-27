"""노드 배선 테스트: /robot/sample → /contact/event, /contact/tare, 파라미터 (로봇 · 드라이버 연결 없음)."""
import math
import time

import pytest

rclpy = pytest.importorskip('rclpy')
pytest.importorskip('contact_scan_interfaces')

from contact_detector.contact_detector import ContactDetectorNode  # noqa: E402
from contact_scan_interfaces.msg import ContactEvent, ReasonCode, RobotSample, ScanState  # noqa: E402
from contact_scan_interfaces.srv import TareForce  # noqa: E402
from contact_scan_qos import QOS_EVENT, QOS_SENSOR, QOS_STATE  # noqa: E402
from rclpy.executors import SingleThreadedExecutor  # noqa: E402
from rclpy.parameter import Parameter  # noqa: E402

# 테스트용 값이다. 실기 · sim 의 값은 contact_scan_bringup/config/*.yaml 에 있다
PARAMS = {
    'source': 'robot_force',
    'contact_threshold_n': 3.0, 'edge_drop_m': 0.0005, 'debounce_n': 3,
    'over_force_n': 30.0, 'over_force_debounce_n': 1,
    'edge_arm_force_n': 1.5, 'edge_trend_window_s': 0.5, 'edge_trend_min_samples': 5,
    'stale_age_ms': 1000,        # 테스트 프로세스 안의 처리 지연으로 샘플이 버려지지 않게 넉넉히 둔다
    'tare_duration_s': 0.6, 'tare_min_samples': 5, 'tare_max_std_n': 0.3, 'tare_max_force_n': 5.0,
    # #109 기능은 끈 채로 기존 노드 시험을 돈다(판정 로직은 test_split_baseline.py 가 본다)
    'descend_ref_window_s': 0.0, 'descend_ref_lag_s': 0.3, 'descend_ref_min_samples': 10, 'descend_hold_threshold_n': 6.0, 'descend_ref_settle_s': 5.5,
    'edge_arm_still_window_s': 0.0, 'edge_arm_still_m': 0.0001, 'edge_arm_travel_m': 0.0005,
    'edge_force_drop_n': 0.0, 'edge_force_window_s': 0.5, 'edge_force_lag_s': 0.1, 'edge_force_settle_s': 1.5,
}
F0 = (0.6, 0.8, 1.5)          # 실기 무접촉 잔류 외력과 비슷한 크기


def overrides(**changes):
    values = {**PARAMS, **changes}
    return [Parameter(k, value=v) for k, v in values.items() if v is not None]


class Rig:
    """판정 노드 + 가짜 robot_manager(샘플 발행) + 이벤트 수신기.

    별도 스레드로 spin 하지 않는다. 테스트가 executor 를 직접 한 스텝씩 돌려서 결과가 부하에 흔들리지 않게 한다.
    """

    def __init__(self, **changes):
        self.node = ContactDetectorNode(parameter_overrides=overrides(**changes))
        self.io = rclpy.create_node('fake_robot_manager')
        self.events = []
        self.pub = self.io.create_publisher(RobotSample, '/robot/sample', QOS_SENSOR)
        self.state_pub = self.io.create_publisher(ScanState, '/scan/state', QOS_STATE)
        self.io.create_subscription(ContactEvent, '/contact/event', self.events.append, QOS_EVENT)
        self.tare_client = self.io.create_client(TareForce, '/contact/tare')
        self.executor = SingleThreadedExecutor()
        self.executor.add_node(self.node)
        self.executor.add_node(self.io)
        self.sample_id = 0
        self.pump(until=lambda: self.pub.get_subscription_count() > 0 and self.tare_client.service_is_ready())

    def close(self):
        self.executor.shutdown()
        self.io.destroy_node()
        self.node.destroy_node()

    def pump(self, seconds=5.0, until=None):
        """executor 를 돌린다. until 이 참이 되면 바로 끝낸다."""
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline and not (until and until()):
            self.executor.spin_once(timeout_sec=0.01)
        return until() if until else True

    def send(self, extra_fz=0.0, z=0.2, operation=RobotSample.OP_NONE, motion_id=0, valid=True, age_s=0.0):
        self.sample_id += 1
        msg = RobotSample()
        msg.sample_id = self.sample_id
        msg.frame_id = 'base_link'
        stamp = (self.io.get_clock().now() - rclpy.duration.Duration(seconds=age_s)).to_msg()
        msg.pose_stamp = msg.force_stamp = stamp
        msg.pose.position.x, msg.pose.position.y, msg.pose.position.z = 0.4, 0.0, z
        msg.pose.orientation.w = 1.0
        msg.wrench.force.x, msg.wrench.force.y, msg.wrench.force.z = F0[0], F0[1], F0[2] + extra_fz
        msg.valid = valid
        msg.operation = operation
        msg.motion_id = motion_id
        self.pub.publish(msg)
        self.pump(0.02)                              # 약 50 Hz
        return msg

    def tare(self, duration_s=0.0, extra_fz=lambda i: 0.0):
        future = self.tare_client.call_async(TareForce.Request(duration_s=duration_s, scan_id='t'))
        i = 0
        while not future.done() and i < 300:
            self.send(extra_fz=extra_fz(i))
            i += 1
        assert future.done()
        return future.result()

    def wait_events(self, count, timeout_s=3.0):
        self.pump(timeout_s, until=lambda: len(self.events) >= count)
        return self.events


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


def test_tare_then_contact_event_fields(rig):
    result = rig.tare()
    assert result.success and result.error == ReasonCode.OK
    assert (result.offset.force.x, result.offset.force.y, result.offset.force.z) == pytest.approx(F0)
    assert result.baseline_norm_n == pytest.approx(math.sqrt(sum(v * v for v in F0)))
    assert math.isnan(result.offset.torque.x)                      # 쓰지 않는 값은 0 이 아니라 NaN

    state = ScanState(scan_id='20260920-150000-ab12')
    rig.state_pub.publish(state)
    rig.pump(0.2)
    sent = [rig.send(extra_fz=f, z=0.2 - 0.0001 * i, operation=RobotSample.OP_DESCEND, motion_id=7)
            for i, f in enumerate([0.0, 0.0, 4.0, 5.0, 6.0, 7.0])]
    events = rig.wait_events(1)
    assert len(events) == 1
    e = events[0]
    first, confirm = sent[2], sent[4]
    assert (e.type, e.source, e.frame_id) == (ContactEvent.TYPE_CONTACT, 'robot_force', 'base_link')
    assert (e.event_id, e.scan_id, e.motion_id) == (1, '20260920-150000-ab12', 7)
    # 판정 샘플 = 조건이 처음 성립한 샘플 (계약 3.3 v0.1.5)
    assert e.sample_id == first.sample_id
    assert e.pose.position.z == pytest.approx(first.pose.position.z)
    assert e.wrench.force.z == pytest.approx(first.wrench.force.z)
    assert e.force_stamp == first.force_stamp
    # 확정 샘플
    assert e.detect_stamp == confirm.force_stamp
    assert e.force_delta_n == pytest.approx(6.0)
    assert e.debounce_count == 3
    assert math.isnan(e.z_drop_m) and not e.z_drop_valid            # EDGE 가 아니면 NaN


def test_edge_event_carries_drop(rig):
    assert rig.tare().success
    for i in range(30):                                             # 누르며 평평하게 민다
        rig.send(extra_fz=4.0, z=0.080, operation=RobotSample.OP_SLIDE, motion_id=9)
    sent = [rig.send(extra_fz=4.0, z=0.080 - 0.0008, operation=RobotSample.OP_SLIDE, motion_id=9) for _ in range(4)]
    events = rig.wait_events(1)
    assert [e.type for e in events] == [ContactEvent.TYPE_EDGE]
    assert events[0].sample_id == sent[0].sample_id
    assert events[0].z_drop_valid and events[0].z_drop_m == pytest.approx(0.0008, abs=2e-5)


def test_over_force_without_tare_and_no_contact_without_tare(rig):
    for _ in range(5):
        rig.send(extra_fz=10.0, operation=RobotSample.OP_DESCEND, motion_id=1)
    assert rig.wait_events(1, timeout_s=0.5) == []                  # tare 전에는 CONTACT 를 내지 않는다
    rig.send(extra_fz=40.0, operation=RobotSample.OP_MOVE_TO, motion_id=2)
    events = rig.wait_events(1)
    assert [e.type for e in events] == [ContactEvent.TYPE_OVER_FORCE]


def test_stale_and_invalid_samples_are_not_judged(rig):
    assert rig.tare().success
    for _ in range(5):
        rig.send(extra_fz=10.0, operation=RobotSample.OP_DESCEND, motion_id=1, age_s=3.0)     # 3 s 묵은 샘플
    for _ in range(5):
        rig.send(extra_fz=10.0, operation=RobotSample.OP_DESCEND, motion_id=1, valid=False)
    assert rig.wait_events(1, timeout_s=0.5) == []


def test_tare_failures_keep_old_baseline(rig):
    assert rig.tare().success
    unstable = rig.tare(extra_fz=lambda i: 3.0 if i % 2 else -3.0)
    assert not unstable.success and unstable.error == ReasonCode.TARE_UNSTABLE
    assert rig.node.detector.baseline == pytest.approx(F0)          # 실패한 tare 는 기준값을 바꾸지 않는다
    suspect = rig.tare(extra_fz=lambda i: 8.0)
    assert suspect.error == ReasonCode.TOOL_REG_SUSPECT


def test_tare_without_samples(rig):
    future = rig.tare_client.call_async(TareForce.Request(duration_s=0.2))
    assert rig.pump(3.0, until=future.done)
    result = future.result()
    assert not result.success and result.error == ReasonCode.NO_SAMPLE and result.sample_count == 0
    assert math.isnan(result.offset.force.x) and math.isnan(result.baseline_norm_n)


def test_set_parameters_validates_and_keeps_baseline(rig):
    assert rig.tare().success
    ok = rig.node.set_parameters([Parameter('contact_threshold_n', value=4.5)])[0]
    assert ok.successful and rig.node.detector.config.contact_threshold_n == 4.5
    assert rig.node.detector.baseline == pytest.approx(F0)
    bad = rig.node.set_parameters([Parameter('debounce_n', value=0)])[0]
    assert not bad.successful and rig.node.detector.config.debounce_n == 3
    assert not rig.node.set_parameters([Parameter('source', value='sim')])[0].successful


@pytest.mark.parametrize('missing', list(PARAMS))
def test_does_not_start_when_a_parameter_is_missing(ros, missing):
    with pytest.raises(Exception, match=missing):
        ContactDetectorNode(parameter_overrides=overrides(**{missing: None}))


def test_rejects_unknown_source(ros):
    with pytest.raises(ValueError, match='rg2'):
        ContactDetectorNode(parameter_overrides=overrides(source='rg2'))
