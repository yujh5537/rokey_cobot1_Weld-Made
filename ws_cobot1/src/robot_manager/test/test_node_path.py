"""robot_manager `/robot/execute_path` 노드 시험 (phase 2, P1). 계약 weld-ros-interfaces.md 5.2.

드라이버 대신 `FakeArm` 이 call_sync 를 받아 위치를 옮긴다. test_node.py 와 같이 dsr_msgs2 가 없으면
건너뛰고, CI 에서는 실패로 만든다. 실제 드라이버 호출 확인은 P1-3(Virtual)에서 한다.
"""
import importlib.util
import math
import os

import pytest

if importlib.util.find_spec('dsr_msgs2') is None:
    if os.environ.get('CI'):
        raise AssertionError('CI 인데 dsr_msgs2 가 없다. .github/workflows/ci.yml 의 "dsr_msgs2 빌드" 단계를 확인한다')
    pytest.skip('두산 드라이버가 없는 환경에서는 건너뛴다', allow_module_level=True)

import rclpy  # noqa: E402
from builtin_interfaces.msg import Duration, Time  # noqa: E402
from contact_scan_interfaces.action import ExecuteMotion, ExecutePath  # noqa: E402
from contact_scan_interfaces.msg import ContactEvent, ReasonCode, RobotSample  # noqa: E402
from contact_scan_interfaces.srv import StopRobot  # noqa: E402
from geometry_msgs.msg import Pose  # noqa: E402
from rclpy.action import GoalResponse  # noqa: E402
from rclpy.parameter import Parameter  # noqa: E402

from robot_manager import path_executor  # noqa: E402
from robot_manager.robot_manager import RobotManager  # noqa: E402

R = ExecutePath.Result
BASE_PARAMS = [
    Parameter('sample_rate_hz', Parameter.Type.DOUBLE, 50.0),
    Parameter('status_rate_hz', Parameter.Type.DOUBLE, 20.0),
    Parameter('service_timeout_s', Parameter.Type.DOUBLE, 0.05),
    Parameter('dsr_namespace', Parameter.Type.STRING, 'test_no_driver'),
    Parameter('drop_limit_m', Parameter.Type.DOUBLE, 0.005),
    Parameter('slide_target_force_n', Parameter.Type.DOUBLE, 3.0),
    Parameter('compliance_stiffness', Parameter.Type.DOUBLE_ARRAY,
              [3000.0, 3000.0, 3000.0, 200.0, 200.0, 200.0]),
    Parameter('arrival_tolerance_m', Parameter.Type.DOUBLE, 0.003),
    Parameter('arrival_grace_s', Parameter.Type.DOUBLE, 0.3),     # 시험 시간을 줄인다
]
# 시험용 값. 실제 값은 contact_scan_bringup/config/*.yaml
PATH_PARAMS = [
    Parameter('path_mode', Parameter.Type.STRING, 'line'),
    Parameter('path_max_points', Parameter.Type.INTEGER, 100),
    Parameter('path_max_speed_mps', Parameter.Type.DOUBLE, 0.100),
    Parameter('path_min_z_m', Parameter.Type.DOUBLE, 0.100),
    Parameter('path_acc_ratio', Parameter.Type.DOUBLE, 4.0),
]
START = (0.400, -0.200, 0.300)
DOWN = (1.0, 0.0, 0.0, 0.0)


@pytest.fixture
def ros():
    rclpy.init()
    yield
    rclpy.shutdown()


class FakeGoalHandle:
    def __init__(self, goal):
        self.request = goal
        self.is_cancel_requested = False
        self.state = None
        self.feedback = []

    def publish_feedback(self, feedback):
        self.feedback.append(feedback)

    def succeed(self):
        self.state = 'succeeded'

    def abort(self):
        self.state = 'aborted'

    def canceled(self):
        self.state = 'canceled'


class FakeArm:
    """call_sync 자리에 들어가 이동 명령을 받고, 감시 루프가 한 바퀴 돌 때마다(is_moving 호출) 조금씩 간다.

    - `ticks`: 한 점에 닿는 데 걸리는 감시 바퀴 수
    - `ignore`: 처음 몇 번의 이동 명령을 실행하지 않는다(#153 의 "출발 안 함")
    - `stop_after`: 이 수만큼 점에 닿은 뒤 다음 점까지 절반만 가고 선다(드라이버 알람 흉내)
    - `on_command`: 이동 명령마다 (arm, label) 로 불린다. 도중 정지 · 취소 · 이벤트를 넣는 곳
    """

    def __init__(self, node, ticks=2, ignore=0, stop_after=None, on_command=None):
        self.node = node
        self.ticks, self.ignore, self.stop_after, self.on_command = ticks, ignore, stop_after, on_command
        self.targets, self.count, self.reached = [], 0, 0
        self.calls, self.requests = [], []
        self.set_position(START)

    def set_position(self, position):
        self.position = position
        self.node.last_pose = (Pose(), Time(sec=1), position)

    def call_sync(self, client, request, label):
        self.calls.append((label, self.node.operation))
        self.requests.append((label, request))
        if label == 'move_stop':
            self.targets = []
            return True
        if label == 'move_line':
            targets = [tuple(v / 1000.0 for v in request.pos[:3])]
        elif label == 'move_spline_task':
            targets = [tuple(v / 1000.0 for v in p.data[:3]) for p in request.pos]
        else:
            return True
        if self.on_command:
            self.on_command(self, label)
        if self.ignore > 0:
            self.ignore -= 1
            return True
        self.targets, self.count = targets, 0
        return True

    def is_moving(self, *args, **kwargs):
        if not self.targets:
            return False
        if self.stop_after is not None and self.reached >= self.stop_after:
            self.set_position(tuple((a + b) / 2 for a, b in zip(self.position, self.targets[0])))
            self.targets = []
            return True
        self.count += 1
        if self.count >= self.ticks:
            self.set_position(self.targets.pop(0))
            self.reached += 1
            self.count = 0
        return True

    def labels(self):
        return [label for label, _ in self.calls]


def make_node(monkeypatch, extra=(), path_params=PATH_PARAMS, **arm_kwargs):
    node = RobotManager(parameter_overrides=BASE_PARAMS + list(path_params) + list(extra))
    node.connected = True
    node.moving = False
    arm = FakeArm(node, **arm_kwargs)
    stops = []
    monkeypatch.setattr(node, 'call_sync', arm.call_sync)
    monkeypatch.setattr(node, 'set_state', lambda *args: None)
    monkeypatch.setattr(node, 'stop_robot', lambda why, motion=None: stops.append(why) or (True, ''))
    monkeypatch.setattr(path_executor.motion_state, 'is_moving', arm.is_moving)
    monkeypatch.setattr(path_executor.motion_state, 'has_moved', lambda *args, **kwargs: True)
    arm.stops = stops
    return node, arm


def pose(x, y, z, q=DOWN):
    p = Pose()
    p.position.x, p.position.y, p.position.z = x, y, z
    p.orientation.x, p.orientation.y, p.orientation.z, p.orientation.w = q
    return p


def path_goal(n=3, step=0.005, frame='base_link', speed=0.01, tol=0.001, timeout_s=0.0, motion_id=7):
    goal = ExecutePath.Goal(weld_id='20260925-100000-abcd', motion_id=motion_id, line_index=4,
                            frame_id=frame, speed=speed, path_tolerance_m=tol)
    goal.waypoints = [pose(START[0] + step * (i + 1), START[1], START[2]) for i in range(n)]
    goal.timeout = Duration(sec=int(timeout_s), nanosec=int((timeout_s % 1.0) * 1e9))
    return goal


def run(node, goal):
    assert node.on_path_goal_request(goal) == GoalResponse.ACCEPT
    handle = FakeGoalHandle(goal)
    result = node.execute_path(handle)
    return result, handle


def assert_cleaned(node):
    assert node.motion is None, '끝나면 goal 자리를 비운다'
    assert node.operation == RobotSample.OP_NONE and node.motion_id == 0


def _stop_request(node):
    return node.on_stop_request(
        StopRobot.Request(requester='weld_manager', reason=ReasonCode.STOP_REQUESTED, detail='관제자 중지'),
        StopRobot.Response())


# ---- 수락 · 거절 --------------------------------------------------------------------------

def test_path_and_motion_share_one_slot(ros, monkeypatch):
    """ExecuteMotion 실행 중이면 경로를, 경로 실행 중이면 ExecuteMotion 을 BUSY 로 거절한다(계약 5.2)."""
    node, _ = make_node(monkeypatch)
    try:
        descend = ExecuteMotion.Goal(motion_id=5, operation=RobotSample.OP_DESCEND,
                                     max_distance=0.01, speed=0.003)
        assert node.on_goal_request(descend) == GoalResponse.ACCEPT
        assert node.on_path_goal_request(path_goal()) == GoalResponse.REJECT
        node.motion = None
        assert node.on_path_goal_request(path_goal()) == GoalResponse.ACCEPT
        assert node.on_goal_request(descend) == GoalResponse.REJECT
    finally:
        node.destroy_node()


@pytest.mark.parametrize('state', ['disconnected', 'stop_pending', 'compliance', 'force'])
def test_goal_is_rejected_in_unsafe_states(ros, monkeypatch, state):
    node, _ = make_node(monkeypatch)
    try:
        if state == 'disconnected':
            node.connected = False
        elif state == 'stop_pending':
            node.stop_requested = (ReasonCode.OVER_FORCE, 'safety_monitor: 과대 외력')
        elif state == 'compliance':
            node.compliance_active = True       # 1차 SLIDE 해제 실패 뒤 남은 상태 (안전망)
        else:
            node.force_ctrl_active = True
        assert node.on_path_goal_request(path_goal()) == GoalResponse.REJECT
        assert node.motion is None
    finally:
        node.destroy_node()


def test_node_starts_without_path_params_but_rejects_paths(ros, monkeypatch):
    """path_* 가 없어도 1차 스캔은 돌아야 한다. 기동은 하고 경로만 거절한다(기본값은 두지 않는다)."""
    node, _ = make_node(monkeypatch, path_params=())
    try:
        assert node.path_limits()[0] is None and 'path_' in node.path_limits()[1]
        assert node.on_path_goal_request(path_goal()) == GoalResponse.REJECT
    finally:
        node.destroy_node()


def test_bad_path_mode_is_rejected(ros, monkeypatch):
    node, _ = make_node(monkeypatch, extra=[Parameter('path_mode', Parameter.Type.STRING, 'blend')])
    try:
        assert 'path_mode' in node.path_limits()[1]
        assert node.on_path_goal_request(path_goal()) == GoalResponse.REJECT
    finally:
        node.destroy_node()


@pytest.mark.parametrize('goal_kwargs, word', [
    ({'n': 0}, '없다'),
    ({'n': 101}, 'path_max_points'),
    ({'speed': 0.2}, 'path_max_speed_mps'),
    ({'frame': 'workpiece_fixture'}, 'frame_id'),
])
def test_invalid_path_is_accepted_then_rejected_with_604(ros, monkeypatch, goal_kwargs, word):
    """ROS 2 거절에는 사유를 실을 수 없다. 수락한 뒤 움직이지 않고 REJECTED · PATH_REJECTED(604) 로 끝낸다."""
    node, arm = make_node(monkeypatch)
    try:
        result, handle = run(node, path_goal(**goal_kwargs))
        assert (result.reason, result.reason_code) == (R.REASON_REJECTED, ReasonCode.PATH_REJECTED)
        assert word in result.detail
        assert arm.labels() == [], '거절한 경로는 한 점도 보내지 않는다'
        assert result.waypoints_done == 0 and handle.state == 'aborted'
        assert_cleaned(node)
    finally:
        node.destroy_node()


def test_low_point_anywhere_rejects_the_whole_path(ros, monkeypatch):
    """z 하한은 수락 시점에 모든 점을 본다. 마지막 점만 낮아도 첫 점을 보내지 않는다."""
    node, arm = make_node(monkeypatch)
    try:
        goal = path_goal(n=4)
        goal.waypoints[3].position.z = 0.0999
        result, _ = run(node, goal)
        assert result.reason_code == ReasonCode.PATH_REJECTED and '경유점 3' in result.detail
        assert arm.labels() == []
    finally:
        node.destroy_node()


# ---- line 모드 ------------------------------------------------------------------------------

def test_line_mode_visits_every_point_in_order(ros, monkeypatch):
    node, arm = make_node(monkeypatch)
    try:
        goal = path_goal(n=3)
        result, handle = run(node, goal)
        assert (result.reason, result.reason_code) == (R.REASON_TARGET_REACHED, ReasonCode.OK)
        assert handle.state == 'succeeded'
        assert arm.labels() == ['move_line'] * 3
        sent = [tuple(v / 1000.0 for v in r.pos[:3]) for _, r in arm.requests]
        expected = [(p.position.x, p.position.y, p.position.z) for p in goal.waypoints]
        assert all(math.dist(a, b) < 1e-9 for a, b in zip(sent, expected))
        first = arm.requests[0][1]
        assert list(first.vel) == pytest.approx([10.0, 10.0]) and list(first.acc) == pytest.approx([40.0, 40.0])
        assert result.waypoints_done == 3
        assert result.distance_travelled == pytest.approx(0.015)
        assert result.frame_id == 'base_link'
        assert_cleaned(node)
    finally:
        node.destroy_node()


def test_samples_carry_weld_path_operation_while_running(ros, monkeypatch):
    """/robot/sample 의 operation 은 실행 중 OP_WELD_PATH(5), 끝나면 0 (계약 2.1, 웹 비드 궤적의 근거)."""
    node, arm = make_node(monkeypatch)
    try:
        run(node, path_goal(n=2))
        assert [op for _, op in arm.calls] == [RobotSample.OP_WELD_PATH] * 2
        assert node.operation == RobotSample.OP_NONE
    finally:
        node.destroy_node()


def test_feedback_reports_waypoint_index_and_distance(ros, monkeypatch):
    node, _ = make_node(monkeypatch, ticks=10)
    try:
        _, handle = run(node, path_goal(n=3))
        indexes = [f.waypoint_index for f in handle.feedback]
        assert indexes == sorted(indexes) and indexes[-1] == 2 and 0 in indexes
        distances = [f.distance_travelled for f in handle.feedback]
        assert distances == sorted(distances)
        assert all(f.frame_id == 'base_link' for f in handle.feedback)
    finally:
        node.destroy_node()


def test_stop_request_stops_before_the_next_point(ros, monkeypatch):
    """/robot/stop 이 오면 멈춤을 확인하고 STOP_REQUESTED 로 끝낸다. 다음 점은 보내지 않는다."""
    def stop_on_second(arm, label):
        if len(arm.labels()) == 2:
            assert _stop_request(arm.node).accepted
    node, arm = make_node(monkeypatch, on_command=stop_on_second, ticks=5)
    try:
        result, handle = run(node, path_goal(n=4))
        assert (result.reason, result.reason_code) == (R.REASON_STOP_REQUESTED, ReasonCode.STOP_REQUESTED)
        assert arm.labels().count('move_line') == 2
        assert arm.stops and 'weld_manager' in arm.stops[0]
        assert result.waypoints_done == 1 and handle.state == 'aborted'
        assert node.stop_requested is None, '확인한 요청은 지운다'
        assert_cleaned(node)
    finally:
        node.destroy_node()


def test_unconfirmed_stop_is_robot_error_and_keeps_the_request(ros, monkeypatch):
    def stop_on_first(arm, label):
        _stop_request(arm.node)
    node, arm = make_node(monkeypatch, on_command=stop_on_first, ticks=5)
    try:
        monkeypatch.setattr(node, 'stop_robot', lambda why, motion=None: (False, '멈춤을 확인하지 못했다'))
        result, _ = run(node, path_goal(n=3))
        assert (result.reason, result.reason_code) == (R.REASON_ROBOT_ERROR, ReasonCode.ROBOT_ERROR)
        assert node.stop_requested is not None, '멈췄는지 모르면 다음 goal 을 막는다(#113)'
    finally:
        node.destroy_node()


def test_over_force_stops_the_path(ros, monkeypatch):
    def over_force(arm, label):
        if len(arm.labels()) == 2:
            arm.node.on_event(ContactEvent(type=ContactEvent.TYPE_OVER_FORCE, force_delta_n=12.5))
    node, arm = make_node(monkeypatch, on_command=over_force, ticks=5)
    try:
        result, _ = run(node, path_goal(n=4))
        assert (result.reason, result.reason_code) == (R.REASON_OVER_FORCE, ReasonCode.OVER_FORCE)
        assert '12.50' in result.detail and arm.stops == ['과대 외력']
    finally:
        node.destroy_node()


@pytest.mark.parametrize('event_type', [ContactEvent.TYPE_CONTACT, ContactEvent.TYPE_EDGE])
def test_contact_events_do_not_stop_or_crash_the_path(ros, monkeypatch, event_type):
    """접촉 이벤트로 멈추지 않는다(계약 5.2). on_event 는 goal.operation 을 읽는데 ExecutePath 에는 그 필드가
    없다 — 어댑터가 없으면 여기서 AttributeError 가 난다."""
    def contact(arm, label):
        arm.node.on_event(ContactEvent(type=event_type, motion_id=7))
    node, _ = make_node(monkeypatch, on_command=contact)
    try:
        result, _ = run(node, path_goal(n=2))
        assert result.reason == R.REASON_TARGET_REACHED
    finally:
        node.destroy_node()


def test_cancel_is_confirmed_before_reporting(ros, monkeypatch):
    holder = {}

    def cancel_on_second(arm, label):
        if len(arm.labels()) == 2:
            holder['handle'].is_cancel_requested = True
    node, _ = make_node(monkeypatch, on_command=cancel_on_second, ticks=5)
    try:
        goal = path_goal(n=3)
        assert node.on_path_goal_request(goal) == GoalResponse.ACCEPT
        handle = holder['handle'] = FakeGoalHandle(goal)
        result = node.execute_path(handle)
        assert (result.reason, result.reason_code) == (R.REASON_CANCELED, ReasonCode.CANCELED)
        assert handle.state == 'canceled'
    finally:
        node.destroy_node()


def test_timeout_stops_the_path(ros, monkeypatch):
    node, arm = make_node(monkeypatch, ticks=10 ** 6)
    try:
        result, _ = run(node, path_goal(n=3, timeout_s=0.3))
        assert (result.reason, result.reason_code) == (R.REASON_TIMEOUT, ReasonCode.TIMEOUT)
        assert arm.stops == ['제한 시간 초과']
    finally:
        node.destroy_node()


def test_point_that_does_not_start_is_sent_again_once(ros, monkeypatch):
    """드라이버가 amovel 을 실행하지 않으면 move_stop 뒤 한 번 다시 보낸다(1차 #153 과 같은 규칙)."""
    node, arm = make_node(monkeypatch, ignore=1)
    try:
        result, _ = run(node, path_goal(n=2))
        assert result.reason == R.REASON_TARGET_REACHED
        assert arm.labels()[:3] == ['move_line', 'move_stop', 'move_line']
    finally:
        node.destroy_node()


def test_point_that_never_starts_is_a_robot_error(ros, monkeypatch):
    node, arm = make_node(monkeypatch, ignore=99)
    try:
        result, _ = run(node, path_goal(n=2))
        assert (result.reason, result.reason_code) == (R.REASON_ROBOT_ERROR, ReasonCode.ROBOT_ERROR)
        assert '출발하지 않았다' in result.detail and result.waypoints_done == 0
    finally:
        node.destroy_node()


def test_stopping_short_of_a_point_is_a_robot_error(ros, monkeypatch):
    """멈춘 것과 도착한 것은 다르다. 두 번째 점을 향하다 섰으면 거리와 함께 204."""
    node, arm = make_node(monkeypatch, stop_after=1)
    try:
        result, _ = run(node, path_goal(n=3))
        assert (result.reason, result.reason_code) == (R.REASON_ROBOT_ERROR, ReasonCode.ROBOT_ERROR)
        assert '경유점 1' in result.detail and '2.5 mm' in result.detail
        assert result.waypoints_done == 1
    finally:
        node.destroy_node()


def test_unknown_start_position_sends_nothing(ros, monkeypatch):
    node, arm = make_node(monkeypatch)
    try:
        node.last_pose = None
        result, _ = run(node, path_goal(n=2))
        assert result.reason_code == ReasonCode.ROBOT_ERROR and '출발 위치' in result.detail
        assert arm.labels() == []
        assert_cleaned(node)
    finally:
        node.destroy_node()


def test_unexpected_exception_still_frees_the_slot(ros, monkeypatch):
    node, arm = make_node(monkeypatch)
    try:
        def boom(*args, **kwargs):
            raise RuntimeError('주입한 예외')
        monkeypatch.setattr(path_executor.PathRunner, 'run', boom)
        result, handle = run(node, path_goal(n=2))
        assert result.reason == R.REASON_ROBOT_ERROR and '주입한 예외' in result.detail
        assert handle.state == 'aborted'
        assert_cleaned(node)
    finally:
        node.destroy_node()


# ---- spline 모드 ----------------------------------------------------------------------------

SPLINE = [Parameter('path_mode', Parameter.Type.STRING, 'spline')]


def test_spline_mode_goes_straight_to_first_point_then_one_spline(ros, monkeypatch):
    """계약 "첫 점까지도 직선": 첫 점은 amovel, 나머지는 amovesx 한 번(점 사이에서 서지 않는다)."""
    node, arm = make_node(monkeypatch, extra=SPLINE)
    try:
        goal = path_goal(n=4)
        result, handle = run(node, goal)
        assert result.reason == R.REASON_TARGET_REACHED and handle.state == 'succeeded'
        assert arm.labels() == ['move_line', 'move_spline_task']
        spline = arm.requests[1][1]
        assert spline.pos_cnt == 3 and len(spline.pos) == 3
        assert spline.pos[0].data[0] == pytest.approx(goal.waypoints[1].position.x * 1000.0)
        assert result.waypoints_done == 4
        assert result.distance_travelled == pytest.approx(0.020)
    finally:
        node.destroy_node()


def test_spline_mode_with_one_point_is_a_single_line(ros, monkeypatch):
    node, arm = make_node(monkeypatch, extra=SPLINE)
    try:
        result, _ = run(node, path_goal(n=1))
        assert result.reason == R.REASON_TARGET_REACHED and arm.labels() == ['move_line']
    finally:
        node.destroy_node()


def test_spline_that_stops_midway_is_a_robot_error_with_estimated_progress(ros, monkeypatch):
    """spline 이 도중에 서면 204. 지난 점 수는 위치로 추정한다(계약 허용)."""
    node, _ = make_node(monkeypatch, extra=SPLINE, stop_after=3)   # 첫 점 + spline 두 점
    try:
        result, _ = run(node, path_goal(n=5))
        assert (result.reason, result.reason_code) == (R.REASON_ROBOT_ERROR, ReasonCode.ROBOT_ERROR)
        assert 'spline' in result.detail
        assert result.waypoints_done == 3
        assert result.distance_travelled == pytest.approx(0.0175)
    finally:
        node.destroy_node()


def test_spline_limit_over_driver_array_is_refused(ros, monkeypatch):
    node, _ = make_node(monkeypatch, extra=SPLINE + [Parameter('path_max_points', Parameter.Type.INTEGER, 150)])
    try:
        assert 'spline' in node.path_limits()[1]
        assert node.on_path_goal_request(path_goal()) == GoalResponse.REJECT
    finally:
        node.destroy_node()
