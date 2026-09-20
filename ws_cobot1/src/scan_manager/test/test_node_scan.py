"""scan_manager 노드: 서버 5개 · 시퀀스 · 중지 · 결과 발행을 가짜 상대 노드로 검증한다.

로봇 · 드라이버 · Virtual Mode 를 쓰지 않는다. 상대 노드는 fake_peers.FakePeers 하나다.
수치는 테스트용 임의값이다.
"""

import math
import os
import threading
import time

import pytest

rclpy = pytest.importorskip('rclpy')
pytest.importorskip('contact_scan_interfaces')

# 다른 패키지의 테스트 · 실행 중인 노드와 섞이지 않게 한다
os.environ['ROS_DOMAIN_ID'] = str(100 + os.getpid() % 100)

from contact_scan_interfaces.action import Resume  # noqa: E402
from contact_scan_interfaces.action import ReturnHome  # noqa: E402
from contact_scan_interfaces.action import RunScan  # noqa: E402
from contact_scan_interfaces.msg import ScanConfig  # noqa: E402
from contact_scan_interfaces.msg import ScanLog  # noqa: E402
from contact_scan_interfaces.msg import ScanResult  # noqa: E402
from contact_scan_interfaces.msg import ScanState  # noqa: E402
from contact_scan_interfaces.srv import SetConfig  # noqa: E402
from contact_scan_interfaces.srv import StopScan  # noqa: E402
from contact_scan_qos import QOS_LOG  # noqa: E402
from contact_scan_qos import QOS_STATE  # noqa: E402
import fake_peers as F  # noqa: E402
from rclpy.action import ActionClient  # noqa: E402
from rclpy.executors import MultiThreadedExecutor  # noqa: E402
from rclpy.parameter import Parameter  # noqa: E402
from scan_manager.contract_enums import Direction  # noqa: E402
from scan_manager.contract_enums import Operation  # noqa: E402
from scan_manager.contract_enums import Phase  # noqa: E402
from scan_manager.contract_enums import Reason  # noqa: E402
from scan_manager.result_store import ResultStore  # noqa: E402
from scan_manager.result_store import STATUS_FAILED  # noqa: E402
from scan_manager.scan_manager import ScanManager  # noqa: E402
from sequence_helpers import BOX_SIZE  # noqa: E402
from sequence_helpers import READY  # noqa: E402
from sequence_helpers import VALUES  # noqa: E402

TIMEOUT_S = 20.0
RETURN_OPS = {Operation.HOME}


def overrides(result_dir, **changes):
    values = {**VALUES, 'result_dir': str(result_dir), **changes}
    return [Parameter(name, value=value) for name, value in values.items() if value is not None]


class Rig:
    """scan_manager + 가짜 상대 노드 + 관제 클라이언트(mqtt_bridge 자리)를 한 executor 에서 돌린다."""

    def __init__(self, result_dir, start_peers=True, **changes):
        self.result_dir = result_dir
        self.node = ScanManager(parameter_overrides=overrides(result_dir, **changes))
        self.peers = F.FakePeers() if start_peers else None
        self.client = rclpy.create_node('fake_bridge')
        self.states, self.results, self.logs = [], [], []
        self.client.create_subscription(ScanState, '/scan/state', self.states.append, QOS_STATE)
        self.client.create_subscription(ScanResult, '/scan/result', self.results.append, QOS_STATE)
        self.client.create_subscription(ScanLog, '/scan/log', self.logs.append, QOS_LOG)
        self.run_client = ActionClient(self.client, RunScan, '/scan/run')
        self.home_client = ActionClient(self.client, ReturnHome, '/scan/home')
        self.resume_client = ActionClient(self.client, Resume, '/scan/resume')
        self.stop_client = self.client.create_client(StopScan, '/scan/stop')
        self.config_client = self.client.create_client(SetConfig, '/scan/set_config')
        self.executor = MultiThreadedExecutor(num_threads=8)
        for node in filter(None, (self.node, self.peers, self.client)):
            self.executor.add_node(node)
        self._thread = threading.Thread(target=self.executor.spin, daemon=True)
        self._thread.start()

    def close(self):
        self.node.close()
        self.executor.shutdown(timeout_sec=5.0)
        self._thread.join(timeout=5.0)  # spin 이 끝난 뒤에 노드를 없앤다
        for node in filter(None, (self.client, self.peers, self.node)):
            node.destroy_node()

    # -- 기다림 --

    def wait(self, condition, timeout_s=TIMEOUT_S):
        deadline = time.monotonic() + timeout_s
        while not condition() and time.monotonic() < deadline:
            time.sleep(0.01)
        return condition()

    def wait_ready(self):
        """가짜 상대 노드의 상태를 scan_manager 가 받을 때까지."""
        conditions = self.node.conditions
        assert self.wait(lambda: None not in (
            conditions().robot_connected, conditions().safety_latched))

    def wait_phase(self, phase):
        assert self.wait(lambda: self.node.state_machine.phase is phase), (
            self.node.state_machine.phase)

    def _result_of(self, future):
        assert self.wait(future.done), '응답이 오지 않았다'
        return future.result()

    # -- 관제 명령 --

    def send(self, client, goal):
        """(goal 이 수락됐는가, Result 를 돌려줄 future)"""
        assert client.wait_for_server(timeout_sec=TIMEOUT_S)
        handle = self._result_of(client.send_goal_async(goal))
        return handle, handle.get_result_async()

    def run(self, goal=None):
        _handle, result = self.send(self.run_client, goal or RunScan.Goal(request_id='run-1'))
        return self._result_of(result).result

    def home(self):
        _handle, result = self.send(self.home_client, ReturnHome.Goal(request_id='home-1'))
        return self._result_of(result).result

    def stop(self):
        assert self.stop_client.wait_for_service(timeout_sec=TIMEOUT_S)
        return self._result_of(self.stop_client.call_async(
            StopScan.Request(request_id='stop-1', requester='fake_bridge', reason=200)))

    def set_config(self, config):
        assert self.config_client.wait_for_service(timeout_sec=TIMEOUT_S)
        return self._result_of(self.config_client.call_async(
            SetConfig.Request(request_id='cfg-1', config=config)))

    # -- 조회 --

    def operations(self):
        return [Operation(goal.operation) for goal in self.peers.goals]

    def store(self):
        return ResultStore(self.result_dir)

    def error_logs(self):
        return [log for log in self.logs if log.level == ScanLog.LEVEL_ERROR]


@pytest.fixture
def ros():
    rclpy.init()
    yield
    rclpy.try_shutdown()


@pytest.fixture
def make_rig(ros, tmp_path):
    rigs = []

    def make(**changes):
        rig = Rig(tmp_path / 'data', **changes)
        rigs.append(rig)
        return rig
    yield make
    for rig in rigs:
        rig.close()


@pytest.fixture
def rig(make_rig):
    rig = make_rig()
    rig.wait_ready()
    return rig


def phases(rig):
    seen = []
    for state in rig.states:
        if not seen or seen[-1] != state.phase:
            seen.append(state.phase)
    return [Phase(p) for p in seen]


# ---- 서버 ----

def test_all_five_servers_are_ready_without_any_peer(make_rig):
    rig = make_rig(start_peers=False)
    for client in (rig.run_client, rig.home_client, rig.resume_client):
        assert client.wait_for_server(timeout_sec=TIMEOUT_S)
    assert rig.stop_client.wait_for_service(timeout_sec=TIMEOUT_S)
    assert rig.config_client.wait_for_service(timeout_sec=TIMEOUT_S)


def test_start_without_status_is_refused_with_the_real_reason(make_rig):
    rig = make_rig(start_peers=False)  # /robot/status · /safety/status 를 받은 적이 없다
    handle, result_future = rig.send(rig.run_client, RunScan.Goal(request_id='run-1'))

    assert handle.accepted  # goal 은 수락하고 Result 로 거절한다(mqtt_bridge 가 사유를 웹에 싣는다)
    result = rig._result_of(result_future).result
    assert not result.success and result.scan_id == ''
    assert result.reason_code == Reason.SAFETY_LATCHED and '미수신' in result.detail
    assert rig.node.state_machine.phase is Phase.IDLE     # 거절은 phase 를 바꾸지 않는다
    assert not (rig.result_dir).exists()                  # 거절된 작업의 기록도 없다


@pytest.mark.parametrize('setup, code', [
    (lambda peers: setattr(peers, 'latched', True), Reason.SAFETY_LATCHED),
    (lambda peers: setattr(peers, 'connected', False), Reason.ROBOT_DISCONNECTED),
])
def test_start_is_refused_by_conditions(make_rig, setup, code):
    rig = make_rig()
    setup(rig.peers)
    rig.wait_ready()
    assert rig.wait(lambda: rig.node.conditions() != READY)
    result = rig.run()
    assert not result.success and result.reason_code == code
    assert rig.node.state_machine.phase is Phase.IDLE
    assert rig.peers.goals == []


def test_missing_required_parameters_refuse_start_and_name_them(make_rig):
    rig = make_rig(tip_radius_m=None, search_origin_pose=None)
    rig.wait_ready()
    result = rig.run()
    assert not result.success and result.reason_code == Reason.INVALID_VALUE
    assert 'tip_radius_m' in result.detail and 'search_origin_pose' in result.detail
    assert rig.node.state_machine.phase is Phase.IDLE
    assert rig.peers.goals == []


def test_resume_is_not_supported_yet(rig):
    _handle, result = rig.send(rig.resume_client, Resume.Goal(request_id='r-1', scan_id=''))
    result = rig._result_of(result).result
    assert not result.success and result.reason_code == Reason.NOT_SUPPORTED
    assert rig.node.state_machine.phase is Phase.IDLE


# ---- 정상 경로 ----

def test_full_scan_recovers_the_box_and_publishes_before_homing(rig):
    result = rig.run()

    assert result.success and result.reason_code == 0
    assert rig.node.state_machine.phase is Phase.DONE
    # (STATE 는 KEEP_LAST 1 이라 늦게 붙은 구독자는 처음의 IDLE 을 못 받을 수 있다)
    assert [p for p in phases(rig) if p is not Phase.IDLE] == [
        Phase.PREPARING, Phase.TOP_SEARCH, Phase.EDGE_SEARCH, Phase.GEOMETRY, Phase.HOMING,
        Phase.DONE]
    # 모션: 기준점 → 하강 → (밀기, 방향 전환 x3) ... → 들어 올림 → 홈. 재하강은 없다
    ops = rig.operations()
    assert ops.count(Operation.DESCEND) == 1 and ops.count(Operation.SLIDE) == 4
    assert ops.count(Operation.MOVE_TO) == 1 + 3 * 3 + 1 and ops[-1] is Operation.HOME
    assert [g.motion_id for g in rig.peers.goals] == list(range(1, len(ops) + 1))
    assert {g.scan_id for g in rig.peers.goals} == {result.scan_id}
    assert {g.frame_id for g in rig.peers.goals} == {'base_link'}
    assert len(rig.peers.tare_requests) == 1 and rig.peers.tare_requests[0].duration_s == 0.0

    assert rig.wait(lambda: rig.results)
    published = rig.results[-1]
    assert len(rig.results) == 1                      # 작업 종료 시 1회
    assert published.success and published.scan_id == result.scan_id
    assert published.frame_id == 'workpiece_fixture'
    assert (published.x_pos, published.x_neg) == pytest.approx((0.05, -0.05))
    assert (published.y_pos, published.y_neg) == pytest.approx((0.03, -0.03))
    assert published.z_top == pytest.approx(BOX_SIZE[2])
    assert (published.width, published.length, published.height) == pytest.approx(BOX_SIZE)
    assert published.box_valid and published.dims_valid and len(published.path_candidates) == 4
    # RunScan.Result.result 는 /scan/result 와 같은 내용이다(7.4절)
    # (config 의 모르는 값이 NaN 이라 msg 를 통째로 == 로 비교할 수 없다)
    assert (result.result.scan_id, result.result.stamp) == (published.scan_id, published.stamp)
    assert result.result.vertices == published.vertices

    # 결과는 복귀를 기다리지 않는다: finished_at · 발행 시각이 HOME goal 보다 앞선다
    home_goal_at = next(
        s.stamp for s in rig.states if s.phase == ScanState.PHASE_HOMING and s.motion_id)
    as_ns = lambda t: t.sec * 1_000_000_000 + t.nanosec  # noqa: E731
    assert as_ns(published.finished_at) <= as_ns(published.stamp) < as_ns(home_goal_at)
    assert as_ns(published.stamp) > 0

    record = rig.store().load(result.scan_id)
    assert record.result_saved and record.result_success and record.state.phase is Phase.DONE
    assert record.top.valid and len(record.confirmed_edges) == 4
    # 판정 좌표와 정지 좌표를 따로 기록한다
    edge = record.edges[Direction.POS_X]
    assert edge.detection.pose.position_m != edge.stop_pose.position_m
    assert record.node_params['tip_radius_m'] == VALUES['tip_radius_m']
    assert rig.error_logs() == []


def test_unknown_config_values_are_nan_with_set_false_never_zero(rig):
    result = rig.run()
    config = result.result.config
    assert config.descend_speed_set and config.descend_speed_mps == VALUES['descend_speed_mps']
    for name, flag in (('contact_threshold_n', 'contact_threshold_set'),
                       ('over_force_n', 'over_force_set'), ('drop_limit_m', 'drop_limit_set')):
        assert getattr(config, flag) is False and math.isnan(getattr(config, name))
    assert config.debounce_set is False  # uint8 은 NaN 을 실을 수 없다. *_set 으로만 판단한다


@pytest.mark.parametrize('behavior', [F.EVENT_AFTER, F.STRAY_EVENT])
def test_event_order_and_stray_events_do_not_matter(rig, behavior):
    rig.peers.behavior[F.key(Operation.SLIDE, Direction.NEG_X)] = behavior
    result = rig.run()
    assert result.success
    assert result.result.x_neg == pytest.approx(-0.05)  # 끼어든 (9, 9, 9) · (8, 8, 8) 을 쓰지 않았다
    if behavior == F.STRAY_EVENT:
        assert sum('motion_id_mismatch' in log.message for log in rig.logs) == 2


def test_config_override_applies_to_this_scan_only(rig):
    goal = RunScan.Goal(request_id='run-1', use_override=True)
    goal.config_override.slide_speed_mps = 0.02
    goal.config_override.slide_speed_set = True
    goal.config_override.descend_speed_mps = 9.9  # *_set=false 라 적용되지 않는다

    result = rig.run(goal)

    assert result.success
    speeds = {g.speed for g in rig.peers.goals if g.operation == Operation.SLIDE}
    assert speeds == {0.02}
    assert result.result.config.slide_speed_mps == 0.02
    assert result.result.x_pos == pytest.approx(0.05)  # 보정에도 그 모션에 실은 속도를 쓴다
    assert rig.node._effective_config()['slide_speed_mps'] == VALUES['slide_speed_mps']


# ---- 실패: 자동 복귀 없음 ----

@pytest.mark.parametrize('op, direction, behavior, code, failed_phase', [
    (Operation.DESCEND, Direction.NONE, F.MAX_DISTANCE, Reason.NO_CONTACT, Phase.TOP_SEARCH),
    (Operation.SLIDE, Direction.POS_Y, F.MAX_DISTANCE, Reason.NO_EDGE, Phase.EDGE_SEARCH),
    (Operation.SLIDE, Direction.NEG_X, F.EVENT_NEVER, Reason.TIMEOUT, Phase.EDGE_SEARCH),
    (Operation.SLIDE, Direction.POS_X, F.ROBOT_ERROR, Reason.ROBOT_ERROR, Phase.EDGE_SEARCH),
])
def test_search_failure_is_recorded_and_never_returns_home(rig, op, direction, behavior, code, failed_phase):
    rig.peers.behavior[F.key(op, direction)] = behavior

    result = rig.run()

    assert not result.success and result.reason_code == code
    assert rig.node.state_machine.phase is Phase.ERROR
    assert rig.operations()[-1] is op and not RETURN_OPS & set(rig.operations())
    # 원인 · 단계 · 위치: 로그와 result_store
    errors = rig.error_logs()
    assert len(errors) == 1 and errors[0].code == code and errors[0].pose_valid
    assert errors[0].phase == int(failed_phase)
    record = rig.store().load(result.scan_id)
    assert (record.failure.reason_code, record.failure.phase) == (code, failed_phase)
    target = record.top if op is Operation.DESCEND else record.edges[direction]
    assert target.status == STATUS_FAILED and target.reason_code == code
    assert target.stop_pose is not None and not record.result_saved

    # 결과는 실패로 1회 발행된다. 얻지 못한 값은 NaN + *_valid=false 이고 0 이 아니다
    assert rig.wait(lambda: rig.results) and len(rig.results) == 1
    published = rig.results[0]
    assert not published.success and published.reason_code == code
    assert published.z_top_valid is (op is not Operation.DESCEND)
    assert not published.y_neg_valid and math.isnan(published.y_neg)
    assert not published.dims_valid and math.isnan(published.width)
    assert not published.box_valid and math.isnan(published.vertices[0].x)
    assert not published.path_candidates[0].valid and math.isnan(published.path_candidates[0].length)
    assert published.frame_id == 'workpiece_fixture'
    if op is Operation.SLIDE and direction is Direction.POS_Y:
        assert published.x_pos == pytest.approx(0.05)  # 확보한 값은 작업대 좌표로 실린다


def test_rejected_motion_goal_fails_without_guessing_the_reason(rig):
    rig.peers.reject_operations.add(int(Operation.DESCEND))  # ROS 2 의 goal 거절에는 사유가 없다

    result = rig.run()

    assert not result.success and result.reason_code == Reason.ROBOT_ERROR
    assert 'goal rejected' in result.detail
    assert rig.node.state_machine.phase is Phase.ERROR
    assert not RETURN_OPS & set(rig.operations())


def test_tare_failure_code_is_passed_through(rig):
    rig.peers.tare_error = int(Reason.TARE_UNSTABLE)
    result = rig.run()
    assert not result.success and result.reason_code == Reason.TARE_UNSTABLE
    assert rig.operations() == [Operation.MOVE_TO]
    assert rig.store().load(result.scan_id).failure.phase is Phase.PREPARING


def test_final_homing_failure_keeps_the_measurement_result(rig):
    rig.peers.behavior[F.key(Operation.HOME)] = F.ROBOT_ERROR

    result = rig.run()

    assert not result.success and result.reason_code == Reason.ROBOT_ERROR  # 명령 전체는 실패
    assert result.result.success and result.result.box_valid                # 측정 결과는 유효
    assert rig.node.state_machine.phase is Phase.ERROR
    assert len(rig.results) == 1 and rig.results[0].success
    record = rig.store().load(result.scan_id)
    assert record.result_saved and record.result_success
    assert record.failure.phase is Phase.HOMING


# ---- 작업 중지 ----

def stop_during_slide(rig, direction=Direction.NEG_X):
    rig.peers.behavior[F.key(Operation.SLIDE, direction)] = F.HOLD
    _handle, result_future = rig.send(rig.run_client, RunScan.Goal(request_id='run-1'))
    assert rig.wait(lambda: any(
        g.operation == Operation.SLIDE and g.direction == direction for g in rig.peers.goals))
    response = rig.stop()
    return response, rig._result_of(result_future).result


def test_stop_requests_robot_stop_and_cancel_then_confirms_by_a_fresh_status(rig):
    response, result = stop_during_slide(rig)

    assert response.accepted                                   # 접수는 즉시
    assert not result.success and result.reason_code == Reason.STOP_REQUESTED
    assert rig.node.state_machine.phase is Phase.STOPPED
    # /robot/stop 과 goal cancel 을 함께 보낸다(계약 4.1절)
    assert len(rig.peers.stop_requests) == 1 and rig.peers.cancel_count == 1
    assert rig.peers.stop_requests[0].requester == 'scan_manager'
    assert phases(rig)[-2:] == [Phase.STOPPING, Phase.STOPPED]

    record = rig.store().load(result.scan_id)
    assert len(record.interruptions) == 1
    stop = record.interruptions[0]
    assert (stop.phase, stop.direction, stop.progress) == (Phase.EDGE_SEARCH, Direction.NEG_X, 1)
    assert stop.pose is not None and not stop.during_final_homing
    assert record.state.phase is Phase.STOPPED and record.failure is None
    assert len(record.confirmed_edges) == 1 and record.top.valid   # 확정 측정값은 남는다

    assert rig.wait(lambda: rig.results) and len(rig.results) == 1
    published = rig.results[0]
    assert not published.success and published.reason_code == Reason.STOP_REQUESTED
    assert published.x_pos_valid and not published.x_neg_valid and math.isnan(published.x_neg)


def test_stop_does_not_call_home_or_resume(rig):
    _response, _result = stop_during_slide(rig)
    sent = len(rig.peers.goals)
    time.sleep(0.5)
    assert len(rig.peers.goals) == sent                        # 중지 뒤에 아무 모션도 보내지 않는다
    assert not RETURN_OPS & set(rig.operations())
    assert rig.node.state_machine.phase is Phase.STOPPED


def test_stop_is_not_confirmed_by_a_status_older_than_the_request(make_rig):
    rig = make_rig(stop_confirm_timeout_s=0.4)
    rig.wait_ready()
    rig.peers.behavior[F.key(Operation.DESCEND)] = F.HOLD
    _handle, result_future = rig.send(rig.run_client, RunScan.Goal(request_id='run-1'))
    assert rig.wait(lambda: any(g.operation == Operation.DESCEND for g in rig.peers.goals))
    # 마지막으로 받은 status 가 moving=false 인 채로 발행이 끊긴다
    rig.peers._moving = False
    time.sleep(0.1)
    rig.peers.publish_status = False
    time.sleep(0.1)

    rig.stop()
    result = rig._result_of(result_future).result

    assert result.reason_code == Reason.ROBOT_STATUS_LOST
    assert rig.node.state_machine.phase is Phase.ERROR
    assert rig.store().load(result.scan_id).interruptions == []


def test_stop_with_nothing_to_stop_is_accepted_and_changes_nothing(rig):
    response = rig.stop()
    assert response.accepted and '멈출 작업이 없다' in response.detail
    assert rig.node.state_machine.phase is Phase.IDLE
    assert len(rig.peers.stop_requests) == 1  # 로봇 정지 요청은 멱등이라 그래도 보낸다


def test_home_after_stop_is_a_separate_command(rig):
    _response, stopped = stop_during_slide(rig)

    result = rig.home()

    assert result.success and result.frame_id == 'base_link'
    assert rig.operations()[-1] is Operation.HOME
    assert rig.node.state_machine.phase is Phase.STOPPED       # 안전복귀는 출발했던 phase 로 돌아간다
    assert rig.peers.goals[-1].motion_id == rig.peers.goals[-2].motion_id + 1
    record = rig.store().load(stopped.scan_id)
    assert record.home_return.requested and record.home_return.completed
    assert record.home_return_since_resume_point


def test_home_is_not_blocked_by_missing_measurement_parameters(make_rig):
    rig = make_rig(tip_radius_m=None, detect_latency_s=None)
    rig.wait_ready()
    assert rig.run().reason_code == Reason.INVALID_VALUE   # 측정은 시작하지 못하지만

    result = rig.home()                                    # 안전복귀는 된다

    assert result.success and rig.operations() == [Operation.HOME]
    assert rig.node.state_machine.phase is Phase.IDLE
    assert not rig.result_dir.exists()                     # 작업이 없으니 기록도 없다


def test_second_run_while_busy_is_refused_and_leaves_the_first_alone(rig):
    rig.peers.behavior[F.key(Operation.DESCEND)] = F.HOLD
    _handle, first = rig.send(rig.run_client, RunScan.Goal(request_id='run-1'))
    rig.wait_phase(Phase.PREPARING)
    assert rig.wait(lambda: any(g.operation == Operation.DESCEND for g in rig.peers.goals))

    second = rig.run(RunScan.Goal(request_id='run-2'))
    home = rig.home()

    assert (second.success, second.reason_code) == (False, Reason.BUSY)
    assert (home.success, home.reason_code) == (False, Reason.BUSY)
    assert rig.node.state_machine.phase is Phase.TOP_SEARCH
    rig.stop()
    assert rig._result_of(first).result.reason_code == Reason.STOP_REQUESTED


# ---- 설정 ----

def test_set_config_applies_only_flagged_fields_and_reports_unknowns_as_nan(rig):
    config = ScanConfig(
        slide_speed_mps=0.02, slide_speed_set=True, over_force_n=25.0, over_force_set=True,
        descend_speed_mps=9.9)  # descend_speed_set=false 라 적용되지 않는다

    response = rig.set_config(config)

    assert response.success and response.reason_code == 0
    applied = response.applied
    assert (applied.slide_speed_mps, applied.slide_speed_set) == (0.02, True)
    assert (applied.over_force_n, applied.over_force_set) == (25.0, True)
    assert applied.descend_speed_mps == VALUES['descend_speed_mps'] and applied.descend_speed_set
    assert math.isnan(applied.contact_threshold_n) and not applied.contact_threshold_set

    rig.run()
    assert {g.speed for g in rig.peers.goals if g.operation == Operation.SLIDE} == {0.02}


def test_set_config_rejects_out_of_range_and_applies_nothing(rig):
    response = rig.set_config(ScanConfig(
        slide_speed_mps=-0.01, slide_speed_set=True, max_slide_m=0.2, max_slide_set=True))
    assert not response.success and response.reason_code == Reason.INVALID_VALUE
    assert 'slide_speed_mps' in response.detail
    assert response.applied.max_slide_m == VALUES['max_slide_m']  # 같이 온 정상값도 적용하지 않는다


def test_set_config_is_busy_while_scanning(rig):
    rig.peers.behavior[F.key(Operation.DESCEND)] = F.HOLD
    _handle, first = rig.send(rig.run_client, RunScan.Goal(request_id='run-1'))
    assert rig.wait(lambda: any(g.operation == Operation.DESCEND for g in rig.peers.goals))

    response = rig.set_config(ScanConfig(slide_speed_mps=0.02, slide_speed_set=True))

    assert not response.success and response.reason_code == Reason.BUSY
    rig.stop()
    rig._result_of(first)


def test_each_scan_gets_a_fresh_result_stamp(rig):
    first = rig.run()
    second = rig.run()
    assert first.success and second.success and first.scan_id != second.scan_id
    assert len(rig.results) == 2
    keys = {(r.scan_id, r.stamp.sec, r.stamp.nanosec) for r in rig.results}
    assert len(keys) == 2  # mqtt_bridge 의 중복 제거 키 (scan_id, stamp)
