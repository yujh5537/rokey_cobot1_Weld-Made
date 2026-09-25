"""weld_manager 노드 + 가짜 상대(fake_peers). 계약 5.1 시작 거절 표 · 7장 중지 · 안전복귀를 ROS 로 본다.

colcon test(설치된 contact_scan_interfaces v0.2.0 이상)에서만 돈다. 조 공용 도메인(30)에 뜨지 않게
contact_scan_testing 으로 빈 도메인(31~39)을 점유한다(#126).
"""

import os
import shutil
import threading
import time

import pytest

rclpy = pytest.importorskip('rclpy')
testing = pytest.importorskip('contact_scan_testing')
action_types = pytest.importorskip('contact_scan_interfaces.action')
if not hasattr(action_types, 'RunWeld'):
    pytest.skip('contact_scan_interfaces 에 phase 2 타입이 없다', allow_module_level=True)
os.environ.update(testing.isolated_ros_env())   # rclpy.init 전에 건다

from conftest import FIXTURE  # noqa: E402
from conftest import FIXTURE_SCAN_ID  # noqa: E402
from conftest import PARAM_VALUES  # noqa: E402
from contact_scan_interfaces.action import ExecuteMotion  # noqa: E402
from contact_scan_interfaces.action import ReturnHome  # noqa: E402
from contact_scan_interfaces.action import RunWeld  # noqa: E402
from contact_scan_interfaces.msg import ScanState  # noqa: E402
from contact_scan_interfaces.msg import WeldLine  # noqa: E402
from contact_scan_interfaces.msg import WeldResult  # noqa: E402
from contact_scan_interfaces.msg import WeldState  # noqa: E402
from contact_scan_interfaces.srv import StopWeld  # noqa: E402
from contact_scan_qos import QOS_STATE  # noqa: E402
from fake_peers import FakePeers  # noqa: E402
from rclpy.action import ActionClient  # noqa: E402
from rclpy.executors import MultiThreadedExecutor  # noqa: E402
from rclpy.parameter import Parameter  # noqa: E402

from weld_manager.weld_manager import WeldManager  # noqa: E402

R = ExecuteMotion.Result
WAIT_S = 10.0


def wait_for(condition, timeout=WAIT_S):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.02)
    return False


def wait_future(future, timeout=WAIT_S):
    assert wait_for(future.done, timeout), 'future 가 끝나지 않았다'
    return future.result()


@pytest.fixture(scope='module', autouse=True)
def ros():
    rclpy.init()
    yield
    rclpy.try_shutdown()


class Harness:
    def __init__(self, result_dir, script=None, with_path_server=True, params=None):
        values = {**PARAM_VALUES, 'result_dir': str(result_dir), **(params or {})}
        overrides = [Parameter(name, value=value) for name, value in values.items()]
        self.weld = WeldManager(parameter_overrides=overrides)
        self.fake = FakePeers(script, with_path_server)
        self.client = rclpy.create_node('weld_test_client')
        self.run_client = ActionClient(self.client, RunWeld, '/weld/run')
        self.home_client = ActionClient(self.client, ReturnHome, '/weld/home')
        self.stop_client = self.client.create_client(StopWeld, '/weld/stop')
        self.states, self.results = [], []
        self.client.create_subscription(WeldState, '/weld/state', self.states.append, QOS_STATE)
        self.client.create_subscription(WeldResult, '/weld/result', self.results.append, QOS_STATE)
        self.executor = MultiThreadedExecutor(num_threads=8)
        for node in (self.weld, self.fake, self.client):
            self.executor.add_node(node)
        self.thread = threading.Thread(target=self.executor.spin, daemon=True)
        self.thread.start()
        # 가짜가 상태 · 샘플을 몇 번 내고 weld_manager 가 받을 때까지
        assert wait_for(lambda: self.weld._robot_status is not None and self.weld._sample is not None
                        and (self.weld._scan_state is not None or not self.fake.publish_scan_state))

    def run(self, start=0, end=7, scan_id='', override=None, wait=True):
        goal = RunWeld.Goal(request_id='t', scan_id=scan_id, start_line=start, end_line=end)
        if override:
            goal.use_override = True
            for name, value in override.items():
                setattr(goal.config_override, name, value)
                flag = {'weld_speed_mps': 'weld_speed_set', 'travel_speed_mps': 'travel_speed_set',
                        'standoff_m': 'standoff_set', 'weave_amplitude_m': 'weave_amplitude_set',
                        'weave_pitch_m': 'weave_pitch_set', 'tilt_deg': 'tilt_set'}[name]
                setattr(goal.config_override, flag, True)
        assert self.run_client.wait_for_server(timeout_sec=WAIT_S)
        handle = wait_future(self.run_client.send_goal_async(goal))
        assert handle.accepted          # 항상 accept 하고 거절은 Result 로 준다
        future = handle.get_result_async()
        return wait_future(future, 60.0).result if wait else future

    def home(self):
        assert self.home_client.wait_for_server(timeout_sec=WAIT_S)
        handle = wait_future(self.home_client.send_goal_async(ReturnHome.Goal(request_id='h')))
        return wait_future(handle.get_result_async(), 30.0).result

    def stop(self):
        assert self.stop_client.wait_for_service(timeout_sec=WAIT_S)
        return wait_future(self.stop_client.call_async(StopWeld.Request(request_id='s', requester='test')))

    def phase(self):
        return self.weld.state_machine.phase

    def close(self):
        self.executor.shutdown(timeout_sec=2.0)
        for node in (self.weld, self.fake, self.client):
            node.destroy_node()


@pytest.fixture
def result_dir(tmp_path):
    target = tmp_path / FIXTURE_SCAN_ID
    target.mkdir()
    shutil.copy(FIXTURE, target / 'result.json')
    return tmp_path


@pytest.fixture
def make(result_dir):
    made = []

    def factory(**kwargs):
        harness = Harness(result_dir, **kwargs)
        made.append(harness)
        return harness
    yield factory
    for harness in made:
        harness.close()


# ---- 정상 ----

def test_full_weld(make, result_dir):
    h = make()
    result = h.run()
    assert result.success, (result.reason_code, result.detail)
    assert result.result.success and result.result.scan_id == FIXTURE_SCAN_ID
    assert [line.status for line in result.result.lines] == [WeldLine.STATUS_DONE] * 8
    # 선마다 MOVE_TO · MOVE_TO · PATH · MOVE_TO, 끝에 올림 · HOME
    assert h.fake.kinds() == ['MOVE_TO', 'MOVE_TO', 'PATH', 'MOVE_TO'] * 8 + ['MOVE_TO', 'HOME']
    goals = [goal for _, goal in h.fake.goals]
    assert [g.motion_id for g in goals] == list(range(1, 35))
    path = goals[2]
    assert path.weld_id == result.weld_id and path.line_index == 0 and path.frame_id == 'base_link'
    assert len(path.waypoints) > 2 and abs(path.speed - PARAM_VALUES['weld_speed_mps']) < 1e-12
    assert goals[0].frame_id == 'base_link' and goals[0].scan_id == result.weld_id
    assert h.phase().name == 'DONE'
    assert wait_for(lambda: h.results and h.results[-1].weld_id == result.weld_id)
    saved = result_dir / FIXTURE_SCAN_ID / 'weld' / f'{result.weld_id}.json'
    assert saved.exists()


def test_end_line_and_progress(make):
    h = make()
    result = h.run(start=0, end=3)
    assert result.success
    statuses = [line.status for line in result.result.lines]
    assert statuses == [WeldLine.STATUS_DONE] * 4 + [WeldLine.STATUS_SKIPPED] * 4
    assert len(h.fake.goals) == 4 * 4 + 2
    # 경로 feedback(0.05 m)이 WELDING 중 진행률로 나갔다
    assert wait_for(lambda: any(s.phase == WeldState.PHASE_WELDING and s.line_progress > 0 for s in h.states))


# ---- 시작 거절 (5.1 표) ----

def _reject_cases():
    def setter(**attrs):
        return lambda h: [setattr(h.fake, k, v) for k, v in attrs.items()]
    return [
        ('no_scan_state', {'publish_scan_state': False}, {}, 101),
        ('scan_active', {'scan_phase': ScanState.PHASE_EDGE_SEARCH}, {}, 600),
        ('latched', {'latched': True, 'latch_code': 403}, {}, 103),
        ('disconnected', {'connected': False}, {}, 104),
        ('no_result', {}, {'scan_id': '20260101-000000-0000'}, 602),
        ('line_range', {}, {'start': 3, 'end': 2}, 603),
        ('override', {}, {'override': {'tilt_deg': 90.0}}, 102),
        ('slow_override', {}, {'override': {'weld_speed_mps': 0.001}}, 102),
        ('no_sample', {'publish_sample': False}, {}, 307),
        ('tool_force', {'force': (0.0, 0.0, -12.0)}, {}, 302),
        ('tilt_zero_vertical', {}, {'override': {'tilt_deg': 0.0}}, 604),
    ]


@pytest.mark.parametrize('name, fake_attrs, run_kwargs, code', _reject_cases(), ids=lambda c: c if isinstance(c, str) else '')
def test_start_rejections(make, name, fake_attrs, run_kwargs, code):
    publish_scan = fake_attrs.get('publish_scan_state', True)
    h = make()
    h.fake.publish_scan_state = publish_scan
    if not publish_scan:
        h.weld._scan_state = None           # 이미 받은 것을 지운다(한 번도 못 받은 경우)
    if not fake_attrs.get('publish_sample', True):
        h.fake.publish_sample = False
        time.sleep(PARAM_VALUES['sample_timeout_s'] + 0.2)   # 마지막 샘플이 오래되게
    for key, value in fake_attrs.items():
        if key not in ('publish_scan_state', 'publish_sample'):
            setattr(h.fake, key, value)
    time.sleep(0.2)                         # 바뀐 값이 한 번 이상 발행되게
    result = h.run(**run_kwargs)
    assert not result.success and result.reason_code == code, (result.reason_code, result.detail)
    assert h.fake.goals == []               # 로봇을 움직이지 않았다
    assert h.phase().name == 'IDLE'          # phase 도 바뀌지 않았다
    assert all(line.status == WeldLine.STATUS_NOT_ATTEMPTED for line in result.result.lines)


def test_start_below_z_safe_lifts_first(make):
    # D30: 거절하지 않고 같은 x · y · 현재 자세로 z_safe 까지 올린 뒤 시작한다
    h = make()
    h.fake.position = (0.46, -0.21, 0.43)
    time.sleep(0.2)
    result = h.run(start=0, end=0)
    assert result.success, result.detail
    lift = h.fake.goals[0][1]
    assert h.fake.kinds()[:2] == ['MOVE_TO', 'MOVE_TO'] and len(h.fake.goals) == 1 + 4 + 2
    p = lift.target.position
    assert (round(p.x, 6), round(p.y, 6)) == (0.46, -0.21) and abs(p.z - 0.48986501464843746) < 1e-9
    q = lift.target.orientation
    assert (q.x, q.y, q.z, q.w) == (0.0, 1.0, 0.0, 0.0)      # 가짜의 지금 자세 그대로


def test_tilt_zero_l0_only_is_accepted(make):
    h = make()
    result = h.run(start=0, end=0, override={'tilt_deg': 0.0, 'weave_amplitude_m': 0.0})
    assert result.success, result.detail
    assert len(h.fake.goals) == 4 + 2


# ---- 중지 · 실패 · 안전복귀 (7장) ----

def test_weld_stop_during_path_then_home(make):
    h = make(script={3: 'hold'})                      # L0 의 경로를 붙잡는다
    future = h.run(wait=False)
    assert wait_for(lambda: len(h.fake.goals) == 3)
    busy = h.run()                                     # 실행 중의 두 번째 START
    assert not busy.success and busy.reason_code == 100
    params = h.weld.set_parameters([Parameter('tilt_deg', value=30.0)])
    assert not params[0].successful                    # 실행 중 값 변경 금지
    response = h.stop()
    assert response.accepted
    result = wait_future(future, 30.0).result
    assert not result.success and result.reason_code == 200
    line = result.result.lines[0]
    assert line.status == WeldLine.STATUS_STOPPED and line.stop_pose_valid
    assert [r.requester for r in h.fake.stop_requests] == ['weld_manager']
    assert h.phase().name == 'STOPPED' and len(h.fake.goals) == 3

    home = h.home()
    assert home.success, home.detail
    assert h.fake.kinds()[3:] == ['MOVE_TO', 'MOVE_TO', 'HOME']   # 물러남 → z_safe → 홈
    assert [g.motion_id for _, g in h.fake.goals[3:]] == [4, 5, 6]  # 앞 작업의 번호를 잇는다
    assert h.phase().name == 'STOPPED'


def test_unrequested_stop_is_error(make):
    h = make(script={3: (R.REASON_STOP_REQUESTED, 200)})   # 스캔 중지 버튼 같은 남의 /robot/stop
    result = h.run()
    assert not result.success and result.reason_code == 204
    assert h.phase().name == 'ERROR' and len(h.fake.goals) == 3


def test_over_force_is_error(make):
    h = make(script={2: (R.REASON_OVER_FORCE, 400)})
    result = h.run()
    assert result.reason_code == 400 and h.phase().name == 'ERROR'
    assert result.result.lines[0].status == WeldLine.STATUS_FAILED


# ---- 선 실패 뒤 계속 (D33) ----

def test_unreachable_line_is_failed_and_the_rest_continue(make):
    # L1 접근 1(goal 5)이 204 → L1 FAILED. 가짜의 자리는 L0 후퇴점(z_safe)이라 복구 이동 없이 L2 로. 끝까지 가고 홈
    h = make(script={5: (R.REASON_ROBOT_ERROR, 204)})
    result = h.run()
    assert not result.success and result.reason_code == 204 and result.detail == 'L1 FAILED'
    statuses = [line.status for line in result.result.lines]
    assert statuses == [WeldLine.STATUS_DONE, WeldLine.STATUS_FAILED] + [WeldLine.STATUS_DONE] * 6
    assert result.result.lines[1].reason_code == 204 and not result.result.success
    kinds = h.fake.kinds()
    assert kinds[:5] == ['MOVE_TO', 'MOVE_TO', 'PATH', 'MOVE_TO', 'MOVE_TO'] and len(kinds) == 4 + 1 + 24 + 2
    assert kinds[-2:] == ['MOVE_TO', 'HOME'] and h.phase().name == 'DONE'
    assert wait_for(lambda: h.results and not h.results[-1].success and h.results[-1].detail == 'L1 FAILED')


def test_failure_below_z_safe_recovers_by_backing_off_and_lifting(make):
    # L1 경로(goal 7)가 204 → 가짜의 자리는 접근점(z_safe 아래) → 물러남 · 올림 두 MOVE_TO 뒤 L2 접근 1
    h = make(script={7: (R.REASON_ROBOT_ERROR, 204)})
    result = h.run()
    assert not result.success and result.detail == 'L1 FAILED'
    kinds = h.fake.kinds()
    assert kinds[4:10] == ['MOVE_TO', 'MOVE_TO', 'PATH', 'MOVE_TO', 'MOVE_TO', 'MOVE_TO']
    assert len(kinds) == 4 + 3 + 2 + 24 + 2
    lift = h.fake.goals[8][1]
    assert abs(lift.target.position.z - 0.48986501464843746) < 1e-9      # z_safe (sim 픽스처)
    assert h.phase().name == 'DONE'


def test_continue_off_stops_at_first_failure(make):
    h = make(script={5: (R.REASON_ROBOT_ERROR, 204)}, params={'continue_on_line_failure': False})
    result = h.run()
    assert not result.success and result.reason_code == 204
    assert h.phase().name == 'ERROR' and len(h.fake.goals) == 5


def test_path_server_missing(make):
    h = make(with_path_server=False, params={'server_wait_timeout_s': 0.5})
    result = h.run()
    assert result.reason_code == 104 and '/robot/execute_path' in result.result.lines[0].detail
    assert h.fake.kinds() == ['MOVE_TO', 'MOVE_TO']


def test_stop_in_idle_does_not_stop_robot(make):
    h = make()
    response = h.stop()
    assert not response.accepted and response.reason_code == 0
    time.sleep(0.2)
    assert h.fake.stop_requests == []        # 휴지 중의 /weld/stop 이 스캔 모션을 멈추면 안 된다


def test_missing_parameters_reject_start(make):
    h = make(params={'standoff_m': 0.0})     # 범위 밖(0 = 접촉)
    result = h.run()
    assert result.reason_code == 102 and 'standoff_m' in result.detail
