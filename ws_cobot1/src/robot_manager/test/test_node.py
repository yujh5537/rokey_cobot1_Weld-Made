"""robot_manager 노드 테스트 (T15).

두산 드라이버(dsr_msgs2)가 없는 개인 PC 에서는 건너뛴다. **CI 에는 dsr_msgs2 를 고정 커밋으로
빌드해 넣으므로 반드시 돌아야 하고**, 없으면 건너뛰지 않고 실패한다.
여기서는 **드라이버가 없을 때의 동작**을 본다. 실기·Virtual 동작은 PR 본문에 따로 적는다.
"""
import importlib.util
import os

import time

import pytest

# CI 에는 dsr_msgs2 를 고정 커밋으로 빌드해 넣는다(.github/workflows/ci.yml). 없는데 조용히
# 건너뛰면 실기에서 로봇을 움직이는 코드가 검증 밖에 있게 되므로, CI 에서는 실패로 만든다.
# 드라이버가 없는 개인 PC 에서는 그대로 건너뛴다.
if importlib.util.find_spec('dsr_msgs2') is None:
    if os.environ.get('CI'):
        raise AssertionError(
            'CI 인데 dsr_msgs2 가 없다. 이 파일이 통째로 건너뛰어지면 robot_manager 노드 시험이 '
            '한 건도 돌지 않는다. .github/workflows/ci.yml 의 "dsr_msgs2 빌드" 단계를 확인한다')
    pytest.skip('두산 드라이버가 없는 환경에서는 건너뛴다', allow_module_level=True)

import rclpy  # noqa: E402
from contact_scan_interfaces.msg import ReasonCode, RobotSample, RobotStatus  # noqa: E402
from contact_scan_qos import QOS_SENSOR, QOS_STATE  # noqa: E402
from rclpy.executors import SingleThreadedExecutor  # noqa: E402
from rclpy.parameter import Parameter  # noqa: E402

from robot_manager.robot_manager import RobotManager  # noqa: E402

PARAMS = [
    Parameter('sample_rate_hz', Parameter.Type.DOUBLE, 50.0),
    Parameter('status_rate_hz', Parameter.Type.DOUBLE, 20.0),
    Parameter('service_timeout_s', Parameter.Type.DOUBLE, 0.05),
    # 브링업이 없는 환경이므로 실제 서비스와 겹치지 않는 이름을 쓴다
    Parameter('dsr_namespace', Parameter.Type.STRING, 'test_no_driver'),
    # 아래 셋은 기본값이 없다. yaml(또는 여기)에 없으면 기동하지 않는다 (현지 리뷰, PR #73)
    Parameter('drop_limit_m', Parameter.Type.DOUBLE, 0.005),
    Parameter('slide_target_force_n', Parameter.Type.DOUBLE, 3.0),
    Parameter('compliance_stiffness', Parameter.Type.DOUBLE_ARRAY,
              [3000.0, 3000.0, 3000.0, 200.0, 200.0, 200.0]),
    Parameter('arrival_tolerance_m', Parameter.Type.DOUBLE, 0.003),
]


@pytest.fixture
def ros():
    rclpy.init()
    yield
    rclpy.shutdown()


def collect(node, seconds, timeout_extra=0.5):
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    end = node.get_clock().now().nanoseconds / 1e9 + seconds
    while node.get_clock().now().nanoseconds / 1e9 < end:
        executor.spin_once(timeout_sec=timeout_extra)
    executor.remove_node(node)


def test_publishes_status_before_any_driver_response(ros):
    """scan_manager는 status를 한 번도 못 받으면 스캔을 시작하지 않는다. 기동 직후 1회 발행한다."""
    node = RobotManager(parameter_overrides=PARAMS)
    listener = rclpy.create_node('status_listener')
    received = []
    listener.create_subscription(RobotStatus, '/robot/status', received.append, QOS_STATE)
    try:
        executor = SingleThreadedExecutor()
        executor.add_node(node)
        executor.add_node(listener)
        for _ in range(50):
            executor.spin_once(timeout_sec=0.05)
            if received:
                break
        assert received, '기동 직후 status가 발행되지 않았다'
        assert received[0].connected is False      # 드라이버가 없으니 미연결
        assert received[0].operation == RobotSample.OP_NONE
        assert received[0].motion_id == 0
        assert received[0].compliance_active is False
        assert received[0].force_ctrl_active is False
    finally:
        listener.destroy_node()
        node.destroy_node()


def test_sample_is_invalid_with_nan_when_driver_is_missing(ros):
    """실패한 조회를 0으로 채우지 않는다 (CLAUDE.md 규칙 4)."""
    node = RobotManager(parameter_overrides=PARAMS)
    listener = rclpy.create_node('sample_listener')
    received = []
    listener.create_subscription(RobotSample, '/robot/sample', received.append, QOS_SENSOR)
    try:
        executor = SingleThreadedExecutor()
        executor.add_node(node)
        executor.add_node(listener)
        for _ in range(60):
            executor.spin_once(timeout_sec=0.05)
            if len(received) >= 2:
                break
        assert received, '샘플이 발행되지 않았다'
        sample = received[0]
        assert sample.valid is False
        assert sample.pose.position.x != sample.pose.position.x          # NaN
        assert sample.wrench.force.z != sample.wrench.force.z            # NaN
        assert sample.frame_id == 'base_link'
        assert sample.sample_id == 1                                     # 발행마다 +1
        assert sample.pose_stamp.sec or sample.pose_stamp.nanosec        # 시각은 채운다
    finally:
        listener.destroy_node()
        node.destroy_node()


def test_sample_id_increases(ros):
    node = RobotManager(parameter_overrides=PARAMS)
    listener = rclpy.create_node('id_listener')
    received = []
    listener.create_subscription(RobotSample, '/robot/sample', received.append, QOS_SENSOR)
    try:
        executor = SingleThreadedExecutor()
        executor.add_node(node)
        executor.add_node(listener)
        for _ in range(80):
            executor.spin_once(timeout_sec=0.05)
            if len(received) >= 3:
                break
        assert len(received) >= 3
        ids = [s.sample_id for s in received[:3]]
        assert ids == sorted(ids) and len(set(ids)) == 3
    finally:
        listener.destroy_node()
        node.destroy_node()


def test_does_not_send_while_a_call_is_outstanding(ros):
    """앞 요청의 응답이 안 왔으면 새 조회를 시작하지 않는다 (병후 리뷰, PR #72).

    같은 서비스로 여러 건이 동시에 뜨면 드라이버가 응답을 멈춘다.
    """
    node = RobotManager(parameter_overrides=PARAMS)
    try:
        class Pending:                      # 응답이 오지 않는 호출 하나
            def service_is_ready(self):
                return True

            def call_async(self, request):
                class Future:
                    def add_done_callback(self, callback):
                        pass
                return Future()

        node.queue.submit(Pending(), 'req', None, 'stuck')
        assert node.queue.busy() is True
        node.attempt = None
        before = node.cycle
        node.on_sample_timer()
        assert node.cycle == before, '응답을 기다리는 중에는 새 조회를 시작하지 않는다'
        assert node.attempt is None
    finally:
        node.destroy_node()


def test_moving_is_true_again_when_positions_go_stale(ros):
    """정지 상태로 창을 채운 뒤 posx 가 끊기면 moving 이 다시 True 가 된다."""
    node = RobotManager(parameter_overrides=PARAMS)
    try:
        now = node.now_s()
        for i in range(7):                 # 창(0.3 s)을 덮는다
            node.positions.append((now - 0.29 + i * 0.045, (0.4, 0.0, 0.2)))
        assert node.moving_from_positions() is False
        node.positions.clear()
        for i in range(3):        # 창(0.3 s)보다 오래된 위치만 남은 상태
            node.positions.append((now - 5.0 + i * 0.05, (0.4, 0.0, 0.2)))
        assert node.moving_from_positions() is True
    finally:
        node.destroy_node()


@pytest.mark.parametrize('missing', ['drop_limit_m', 'slide_target_force_n',
                                     'compliance_stiffness', 'arrival_tolerance_m'])
def test_refuses_to_start_without_required_params(ros, missing):
    """값이 없으면 기본값으로 조용히 도는 대신 기동을 거부한다.

    drop_limit_m 은 계약 7.2 가 safety_monitor 와 같은 값을 요구하는데, 그 일치는
    contact_scan_bringup 의 yaml 만 보고 검사된다. 코드에 기본값이 있으면 yaml 에서
    줄이 사라져도 검사는 통과하면서 1차 · 2차 감시의 기준만 어긋난다 (현지 리뷰, PR #73).
    """
    params = [p for p in PARAMS if p.name != missing]
    with pytest.raises(ValueError, match=missing):
        RobotManager(parameter_overrides=params)


def test_slide_is_rejected_when_start_z_is_unknown(ros):
    """기준 z 를 모르면 1차 하강 제한이 감시 없이 도는 것과 같다. 거절한다."""
    from contact_scan_interfaces.action import ExecuteMotion

    node = RobotManager(parameter_overrides=PARAMS)
    try:
        assert node.last_pose is None      # 드라이버가 없어 유효 샘플이 없다
        goal = ExecuteMotion.Goal(scan_id='t', motion_id=1, operation=RobotSample.OP_SLIDE,
                                  direction=1, speed=0.01, max_distance=0.02)
        assert 'start_z' in node.reject_reason(goal) or '위치' in node.reject_reason(goal)
    finally:
        node.destroy_node()


def test_move_to_in_another_frame_is_rejected(ros):
    """target 프레임이 이 노드의 프레임이 아니면 거절한다. 빈 문자열도 거절한다.

    작업대 프레임 좌표를 Base 로 알고 움직이면 약 47 cm 어긋나고, 도착 판정도 같은
    착각 위에서 재므로 "도착"까지 찍어 준다 (현지 리뷰, PR #73).
    """
    from contact_scan_interfaces.action import ExecuteMotion

    node = RobotManager(parameter_overrides=PARAMS)
    try:
        def goal(frame):
            return ExecuteMotion.Goal(scan_id='t', motion_id=1, operation=RobotSample.OP_MOVE_TO,
                                      frame_id=frame, speed=0.01)
        assert node.reject_reason(goal(node.frame_id)) == ''
        assert 'fixture' in node.reject_reason(goal('fixture'))
        assert node.reject_reason(goal('')) != '', '빈 프레임을 Base 로 보지 않는다'
        # HOME 은 관절각 목표라 프레임을 보지 않는다. PARAMS 에 home_joint_deg 가 없으므로
        # 예외가 아니라 그 이유로 거절되어야 한다
        home = ExecuteMotion.Goal(scan_id='t', motion_id=2, operation=RobotSample.OP_HOME)
        assert 'home_joint_deg' in node.reject_reason(home)
    finally:
        node.destroy_node()


def test_move_to_that_stops_short_of_the_target_is_a_robot_error(ros):
    """멈춘 것과 도착한 것은 다르다.

    드라이버 알람 · 외력 · 충돌 · 관절 한계로 중간에 서도 moving 은 false 가 된다.
    scan_manager 는 TARGET_REACHED · OK 를 믿고 바로 하강하므로, 엉뚱한 자리에서
    작업대나 부재 옆면을 윗면으로 잡게 된다 (병후 리뷰, PR #73).
    """
    from contact_scan_interfaces.action import ExecuteMotion

    node = RobotManager(parameter_overrides=PARAMS)
    try:
        goal = ExecuteMotion.Goal(scan_id='t', motion_id=1, operation=RobotSample.OP_MOVE_TO,
                                  speed=0.02)
        goal.target.position.x, goal.target.position.y, goal.target.position.z = 0.4, -0.2, 0.3
        motion = type('M', (), {'goal': goal})()

        node.last_pose = None                       # 위치를 모르면 도착을 말할 수 없다
        reason, code, detail = node.finished_without_event(motion)
        assert code == ReasonCode.ROBOT_ERROR and '위치' in detail

        node.last_pose = (None, None, (0.4, -0.2, 0.3))          # 목표와 같은 자리
        reason, code, _ = node.finished_without_event(motion)
        assert reason == ExecuteMotion.Result.REASON_TARGET_REACHED and code == ReasonCode.OK

        node.last_pose = (None, None, (0.4, -0.2, 0.28))         # 20 mm 모자람 (허용 3 mm)
        reason, code, detail = node.finished_without_event(motion)
        assert code == ReasonCode.ROBOT_ERROR and '20.0 mm' in detail
    finally:
        node.destroy_node()


def test_stop_that_is_not_confirmed_is_reported_as_robot_error(ros, monkeypatch):
    """정지 미확인을 정상 코드로 돌려주면 scan_manager 는 STOPPED 로 가는데 로봇은 움직인다.

    계약 4.1 "접수와 정지 완료는 다르다" (병후 리뷰, PR #73).
    """
    from contact_scan_interfaces.action import ExecuteMotion
    from contact_scan_interfaces.msg import ContactEvent

    node = RobotManager(parameter_overrides=PARAMS)
    try:
        event = ContactEvent()
        event.type = ContactEvent.TYPE_EDGE
        motion = type('M', (), {'event': event})()

        monkeypatch.setattr(node, 'stop_robot', lambda why, motion=None: (False, '멈춤을 확인하지 못했다'))
        reason, code, detail = node.stop_for_event(motion)
        assert reason == ExecuteMotion.Result.REASON_ROBOT_ERROR
        assert code == ReasonCode.ROBOT_ERROR and '확인하지 못했다' in detail

        monkeypatch.setattr(node, 'stop_robot', lambda why, motion=None: (True, ''))
        reason, code, _ = node.stop_for_event(motion)
        assert reason == ExecuteMotion.Result.REASON_EDGE and code == ReasonCode.OK
    finally:
        node.destroy_node()


def test_moving_stays_true_when_a_sample_gap_empties_the_window(ros):
    """샘플 공백 뒤 갓 들어온 점 두어 개로는 "정지"라고 말하지 않는다.

    2026-09-21 실기: 359 ms 공백 뒤 창에 25 ms 짜리 두 점만 남았고, 3 mm/s 로 내려가는
    중인데 그 사이 변위가 0.076 mm(< moving_eps_m 0.2 mm)라 정지로 판정됐다. robot_manager
    가 동작을 MAX_DISTANCE 로 완료 보고한 뒤에도 로봇은 12 mm 를 더 내려갔고, 결과의 정지
    좌표도 그만큼 틀렸다. eps_m 은 창 전체를 덮었을 때만 뜻이 있는 값이다.
    """
    node = RobotManager(parameter_overrides=PARAMS)
    try:
        now = node.now_s()
        node.positions.clear()
        node.positions.append((now - 0.025, (0.4, 0.0, 0.117495)))
        node.positions.append((now, (0.4, 0.0, 0.117419)))
        assert node.moving_from_positions() is True, '창을 덜 덮었으면 정지라고 하지 않는다'
    finally:
        node.destroy_node()


def test_stop_service_is_offered_and_accepts(ros):
    """/robot/stop 이 없으면 safety_monitor 는 로봇을 멈출 수단이 아예 없다.

    2026-09-21 실기에서 safety_monitor 가 SAMPLE_STALE 로 정지를 요청했지만
    `/robot/stop 서버가 없다` 로 끝났다. 서버가 한 번도 만들어진 적이 없었다.
    """
    from contact_scan_interfaces.srv import StopRobot

    node = RobotManager(parameter_overrides=PARAMS)
    try:
        names = [name for name, _ in node.get_service_names_and_types()]
        assert '/robot/stop' in names, '계약이 요구하는 정지 서비스가 없다'

        # 미연결이면 사실대로 거절한다. 멈출 수 없는데 접수했다고 하지 않는다
        node.connected = False
        response = node.on_stop_request(
            StopRobot.Request(requester='safety_monitor', reason=ReasonCode.OVER_FORCE,
                              detail='시험'), StopRobot.Response())
        assert response.accepted is False
        assert response.reason_code == ReasonCode.ROBOT_DISCONNECTED

        # 연결돼 있으면 접수하고, 감시 고리가 볼 수 있게 남긴다
        node.connected = True
        node.motion = object()        # 동작 중이면 watch 가 처리한다(별도 스레드를 띄우지 않는다)
        response = node.on_stop_request(
            StopRobot.Request(requester='safety_monitor', reason=ReasonCode.OVER_FORCE,
                              detail='과대 외력'), StopRobot.Response())
        assert response.accepted is True
        assert node.stop_requested is not None
        assert node.stop_requested[0] == ReasonCode.OVER_FORCE
        assert 'safety_monitor' in node.stop_requested[1]
    finally:
        node.destroy_node()


class FakeGoalHandle:
    """execute_motion 을 드라이버 없이 돌리기 위한 goal handle."""

    def __init__(self, goal):
        self.request = goal
        self.is_cancel_requested = False
        self.state = None

    def publish_feedback(self, feedback):
        pass

    def succeed(self):
        self.state = 'succeeded'

    def abort(self):
        self.state = 'aborted'

    def canceled(self):
        self.state = 'canceled'


def _descend_goal():
    from contact_scan_interfaces.action import ExecuteMotion
    return ExecuteMotion.Goal(motion_id=5, operation=RobotSample.OP_DESCEND,
                              max_distance=0.01, speed=0.003)


def _stop(node, detail='과대 외력'):
    from contact_scan_interfaces.srv import StopRobot
    return node.on_stop_request(
        StopRobot.Request(requester='safety_monitor', reason=ReasonCode.OVER_FORCE, detail=detail),
        StopRobot.Response())


def _wait_until(predicate, timeout_s=2.0):
    import time
    end = time.monotonic() + timeout_s
    while time.monotonic() < end and not predicate():
        time.sleep(0.01)
    return predicate()


def test_stop_between_accept_and_execute_stops_the_motion(ros, monkeypatch):
    """수락과 실행 사이에 온 정지 요청을 실행 시작에서 지우면, 접수해 놓고 동작이 그대로 나간다.

    on_goal_request 가 self.motion 을 채운 뒤라 정지 스레드는 뜨지 않는다(동작 중으로 보인다).
    watch 의 첫 확인에서 처리되어야 한다 (PR #101 리뷰).
    """
    from contact_scan_interfaces.action import ExecuteMotion
    from robot_manager.robot_manager import Motion

    node = RobotManager(parameter_overrides=PARAMS)
    try:
        node.connected = True
        goal = _descend_goal()
        node.motion = Motion(goal, node.now_s())          # on_goal_request 가 수락한 직후
        assert _stop(node).accepted is True
        sent, stops = [], []
        monkeypatch.setattr(node, 'send_move', lambda motion: sent.append(motion) or True)
        monkeypatch.setattr(node, 'stop_robot', lambda why, motion=None: stops.append(why) or (True, ''))

        handle = FakeGoalHandle(goal)
        result = node.execute_motion(handle)

        assert result.reason == ExecuteMotion.Result.REASON_STOP_REQUESTED
        assert handle.state == 'aborted'                  # 정지된 동작은 성공이 아니다
        assert stops and 'safety_monitor' in stops[0]
        assert node.stop_requested is None                # 처리했으니 다음 goal 을 막지 않는다
    finally:
        node.destroy_node()


def test_idle_stop_request_is_cleared_once_the_stop_is_confirmed(ros, monkeypatch):
    """동작이 없을 때 온 요청은 정지를 확인하면 지운다. 안 지우면 재기동 전까지 모든 goal 이 거절된다.

    safety_monitor 는 과대 외력이면 정지 중에도 부른다(stops = condition.stops or moving).
    2026-09-21 10:34 홈에서 툴을 만져 과대 외력이 난 경우다.
    """
    node = RobotManager(parameter_overrides=PARAMS)
    try:
        node.connected = True
        monkeypatch.setattr(node, 'stop_robot', lambda why, motion=None: (True, ''))
        assert _stop(node, '홈에서 툴 접촉').accepted is True
        assert _wait_until(lambda: node.stop_requested is None), '정지를 확인했는데 요청이 남았다'
        assert node.reject_reason(_descend_goal()) == ''
    finally:
        node.destroy_node()


def test_goal_is_rejected_while_a_stop_is_unconfirmed(ros, monkeypatch):
    """멈췄는지 모르는 로봇에 다음 동작을 보내지 않는다. robot_manager 가 마지막 방어선이다."""
    import threading

    node = RobotManager(parameter_overrides=PARAMS)
    release = threading.Event()
    try:
        node.connected = True

        def slow_unconfirmed_stop(why):
            release.wait(2.0)
            return False, '멈춤을 확인하지 못했다'
        monkeypatch.setattr(node, 'stop_robot', slow_unconfirmed_stop)
        _stop(node)
        assert node.reject_reason(_descend_goal()).startswith('STOP_REQUESTED')   # 정지 진행 중
        release.set()
        import time
        time.sleep(0.1)
        assert node.stop_requested is not None                                  # 확인 못 했으니 남긴다
        assert node.reject_reason(_descend_goal()).startswith('STOP_REQUESTED')
    finally:
        release.set()
        node.destroy_node()


def test_a_newer_request_is_not_cleared_by_an_older_stop(ros, monkeypatch):
    """정지 스레드가 끝날 때 그 사이 새로 온 요청까지 지우면, 두 번째 요청을 접수해 놓고 멈추지 않는다."""
    node = RobotManager(parameter_overrides=PARAMS)
    try:
        node.connected = True
        newer = (ReasonCode.OVER_FORCE, 'safety_monitor: 두 번째')

        def stop_while_another_request_arrives(why):
            node.stop_requested = newer          # 첫 정지를 확인하는 사이에 새 요청이 들어왔다
            return True, ''
        monkeypatch.setattr(node, 'stop_robot', stop_while_another_request_arrives)
        _stop(node, '첫 번째')
        import time
        time.sleep(0.2)
        assert node.stop_requested is newer
    finally:
        node.destroy_node()


def test_request_arriving_as_the_motion_ends_is_settled_not_carried_over(ros, monkeypatch):
    """watch 의 마지막 확인 뒤 · 동작 종료 전에 온 요청이 다음 goal 에 먹히지 않는다.

    동작은 이미 끝났으므로 결과는 그대로 두고, 정지를 확인한 뒤 지운다 (yujh5537 리뷰, PR #101).
    """
    from contact_scan_interfaces.action import ExecuteMotion
    from robot_manager.robot_manager import Motion

    node = RobotManager(parameter_overrides=PARAMS)
    try:
        node.connected = True
        goal = _descend_goal()
        node.motion = Motion(goal, node.now_s())
        stops = []
        monkeypatch.setattr(node, 'stop_robot', lambda why, motion=None: stops.append(why) or (True, ''))

        def run_and_request_at_the_end(goal_handle, motion):
            _stop(node, '끝나는 순간')           # 동작 중이라 스레드는 뜨지 않는다
            return (ExecuteMotion.Result.REASON_MAX_DISTANCE, ReasonCode.MAX_DISTANCE, '')
        monkeypatch.setattr(node, 'run_motion', run_and_request_at_the_end)

        result = node.execute_motion(FakeGoalHandle(goal))
        assert result.reason == ExecuteMotion.Result.REASON_MAX_DISTANCE     # 결과는 바꾸지 않는다
        assert len(stops) == 1 and '동작 종료 직후' in stops[0]
        assert node.stop_requested is None
        assert node.reject_reason(_descend_goal()) == ''
    finally:
        node.destroy_node()


def test_unconfirmed_stop_during_a_motion_keeps_the_request_until_stop_is_called_again(ros, monkeypatch):
    """동작 중 경로도 정지를 확인하지 못하면 요청을 남긴다. 동작 없음 경로와 같은 약속이다 (#113).

    지우면 멈췄는지 모르는 로봇에 다음 동작이 나간다. 복구는 안전복귀(#115) 또는 /robot/stop 을
    다시 부르는 것이다: 동작이 없으니 정지 스레드가 다시 확인하고, 확인되면 지운다.
    """
    from contact_scan_interfaces.action import ExecuteMotion
    from robot_manager.robot_manager import Motion

    node = RobotManager(parameter_overrides=PARAMS)
    try:
        node.connected = True
        goal = _descend_goal()
        node.motion = Motion(goal, node.now_s())
        _stop(node)
        monkeypatch.setattr(node, 'send_move', lambda motion: True)
        monkeypatch.setattr(node, 'stop_robot', lambda why, motion=None: (False, '멈춤을 확인하지 못했다'))

        handle = FakeGoalHandle(goal)
        result = node.execute_motion(handle)
        assert result.reason == ExecuteMotion.Result.REASON_ROBOT_ERROR and handle.state == 'aborted'
        assert node.stop_requested is not None, '확인하지 못했는데 요청이 사라졌다'
        # HOME 이 아닌 동작은 거절한다. 안전복귀(OP_HOME)는 받는다(#115, 별도 시험)
        assert node.reject_reason(_descend_goal()).startswith('STOP_REQUESTED')

        # 복구: 멈춘 것을 확인한 뒤 /robot/stop 을 다시 부른다
        monkeypatch.setattr(node, 'stop_robot', lambda why, motion=None: (True, ''))
        assert _stop(node, '복구').accepted is True
        assert _wait_until(lambda: node.stop_requested is None)
        assert node.reject_reason(_descend_goal()) == ''
    finally:
        node.destroy_node()


def test_home_is_not_rejected_by_a_leftover_stop_request(ros, monkeypatch):
    """정지 확인에 실패해 남은 요청이 있어도 안전복귀는 받는다. 시연 중 안전복귀가 막히면 안 된다 (#115).

    다른 동작은 계속 거절한다. HOME 은 출발 전에 정지를 한 번 더 시도하고 그 요청을 지운다.
    지우지 않으면 watch 의 첫 확인에서 HOME 이 곧바로 멈춘다.
    """
    from contact_scan_interfaces.action import ExecuteMotion

    node = RobotManager(parameter_overrides=PARAMS + [
        Parameter('home_joint_deg', Parameter.Type.DOUBLE_ARRAY, [-24.14, 17.03, 51.68, -0.18, 111.39, -204.84])])
    try:
        node.connected = True
        node.stop_requested = (ReasonCode.OVER_FORCE, 'safety_monitor: 확인 실패로 남은 요청')
        assert node.reject_reason(_descend_goal()).startswith('STOP_REQUESTED')
        home = ExecuteMotion.Goal(motion_id=7, operation=RobotSample.OP_HOME)
        assert node.reject_reason(home) == ''

        from rclpy.action import GoalResponse
        assert node.on_goal_request(home) == GoalResponse.ACCEPT
        stops, sent = [], []
        monkeypatch.setattr(node, 'stop_robot', lambda why, motion=None: stops.append(why) or (False, '확인 못 함'))
        monkeypatch.setattr(node, 'send_move', lambda motion: sent.append(motion) or True)
        monkeypatch.setattr(node, 'arrived', lambda motion, elapsed: True)
        monkeypatch.setattr(node, 'finished_without_event', lambda motion: (
            ExecuteMotion.Result.REASON_TARGET_REACHED, ReasonCode.OK, ''))

        result = node.execute_motion(FakeGoalHandle(home))
        assert '안전복귀 전' in stops[0]                 # 출발 전에 정지를 한 번 더 시도했다
        assert sent, '확인에 실패해도 관제자 명령이므로 출발한다'
        assert result.reason == ExecuteMotion.Result.REASON_TARGET_REACHED
        assert node.stop_requested is None
    finally:
        node.destroy_node()


def test_stop_request_arriving_during_home_still_stops_it(ros, monkeypatch):
    """HOME 을 받은 뒤에 새로 온 정지 요청은 HOME 을 멈춘다. safety_monitor 가 멈출 수 있어야 한다."""
    from contact_scan_interfaces.action import ExecuteMotion

    node = RobotManager(parameter_overrides=PARAMS + [
        Parameter('home_joint_deg', Parameter.Type.DOUBLE_ARRAY, [-24.14, 17.03, 51.68, -0.18, 111.39, -204.84])])
    try:
        node.connected = True
        home = ExecuteMotion.Goal(motion_id=8, operation=RobotSample.OP_HOME)
        from rclpy.action import GoalResponse
        assert node.on_goal_request(home) == GoalResponse.ACCEPT      # 수락 시점에 남은 요청 없음
        _stop(node, 'HOME 도중 과대 외력')                              # 수락 뒤 · 실행 전
        monkeypatch.setattr(node, 'stop_robot', lambda why, motion=None: (True, ''))
        monkeypatch.setattr(node, 'send_move', lambda motion: True)

        handle = FakeGoalHandle(home)
        result = node.execute_motion(handle)
        assert result.reason == ExecuteMotion.Result.REASON_STOP_REQUESTED
        assert handle.state == 'aborted'
    finally:
        node.destroy_node()


# ---- T14: 순응 · 힘 제어는 모든 종료 경로에서 해제된다 (BRD 4.5.2, CLAUDE.md 규칙 2) ----

def _slide_goal():
    from contact_scan_interfaces.action import ExecuteMotion
    return ExecuteMotion.Goal(motion_id=9, operation=RobotSample.OP_SLIDE,
                              direction=ExecuteMotion.Goal.DIR_POS_X, max_distance=0.06, speed=0.005)


def _slide_rig(monkeypatch, fail=()):
    """SLIDE 를 드라이버 없이 돌린다. 불린 두산 서비스 이름을 순서대로 남긴다.

    fail: 실패(또는 응답 시간 초과)로 돌려줄 호출 이름. call_sync 는 둘을 구분하지 않는다.
    """
    from robot_manager.robot_manager import Motion

    node = RobotManager(parameter_overrides=PARAMS)
    node.connected = True
    node.last_pose = (None, None, (0.42, -0.19, 0.18))
    node.last_force = (0.0, 0.0, 2.0)
    calls = []
    stamps = node.release_stamps = {}

    def fake_call_sync(client, request, label):
        calls.append(label)
        stamps[label] = time.monotonic()
        return label not in fail
    monkeypatch.setattr(node, 'call_sync', fake_call_sync)
    monkeypatch.setattr(node, 'send_move', lambda motion: calls.append('move_line') or True)
    goal = _slide_goal()
    node.motion = Motion(goal, node.now_s())
    return node, goal, calls


def _released(calls):
    return 'release_force' in calls and 'release_compliance_ctrl' in calls


def _raise(exc):
    raise exc


@pytest.mark.parametrize('ending', [
    'exception', 'cancel', 'stop_request', 'event', 'timeout', 'drop_limit', 'edge'])
def test_force_control_is_released_on_every_exit_path(ros, monkeypatch, ending):
    """켠 순응 · 힘 제어는 끝나는 방식과 무관하게 해제한다. 예외 주입을 포함한다 (BRD 4.5.2)."""
    from contact_scan_interfaces.action import ExecuteMotion
    from contact_scan_interfaces.msg import ContactEvent

    node, goal, calls = _slide_rig(monkeypatch)
    try:
        monkeypatch.setattr(node, 'stop_robot', lambda why, motion=None: (True, ''))
        handle = FakeGoalHandle(goal)
        if ending == 'exception':
            monkeypatch.setattr(node, 'watch', lambda gh, m: _raise(RuntimeError('주입한 예외')))
        elif ending == 'cancel':
            handle.is_cancel_requested = True
        elif ending == 'stop_request':
            _stop(node, '안전 이상')
        elif ending == 'event':
            event = ContactEvent()
            event.type = ContactEvent.TYPE_EDGE
            node.motion.event = event
        elif ending == 'timeout':
            node.motion.started_s -= 1000.0
        elif ending == 'drop_limit':
            def move_then_drop(motion):                         # 기준 z(0.18)는 시작 때 잡힌다
                calls.append('move_line')
                node.last_pose = (None, None, (0.42, -0.19, 0.17))  # 밀기 중 10 mm 내려감
                return True
            monkeypatch.setattr(node, 'send_move', move_then_drop)
        elif ending == 'edge':
            monkeypatch.setattr(node, 'watch', lambda gh, m: (
                ExecuteMotion.Result.REASON_EDGE, ReasonCode.OK, ''))

        result = node.execute_motion(handle)

        R = ExecuteMotion.Result
        expected = {'exception': R.REASON_ROBOT_ERROR, 'cancel': R.REASON_CANCELED,
                    'stop_request': R.REASON_STOP_REQUESTED, 'event': R.REASON_EDGE,
                    'timeout': R.REASON_TIMEOUT, 'drop_limit': R.REASON_ROBOT_ERROR,
                    'edge': R.REASON_EDGE}[ending]
        assert result.reason == expected, f'{ending}: 다른 경로로 끝났다 reason={result.reason}'
        if ending == 'drop_limit':
            assert result.reason_code == ReasonCode.DROP_LIMIT
        assert _released(calls), f'{ending}: 해제를 부르지 않았다 {calls}'
        assert calls.index('release_force') < calls.index('release_compliance_ctrl')   # 힘 먼저
        # 힘 제어 램프(release_force_time_s)가 끝난 뒤 순응을 푼다. 파라미터 값과 비교한다
        ramp_s = float(node.param('release_force_time_s'))
        gap = node.release_stamps['release_compliance_ctrl'] - node.release_stamps['release_force']
        assert gap >= ramp_s - 0.02, f'{ending}: 램프를 기다리지 않았다 ({gap:.3f} s < {ramp_s})'
        assert result.compliance_released is True
        assert node.motion is None                                 # 다음 goal 을 받을 수 있다
        assert not node.compliance_active and not node.force_ctrl_active
    finally:
        node.destroy_node()


@pytest.mark.parametrize('timed_out', ['task_compliance_ctrl', 'set_desired_force'])
def test_enable_that_times_out_is_still_released(ros, monkeypatch, timed_out):
    """켜는 호출이 시간 초과여도 컨트롤러는 켰을 수 있다. 해제를 부른다.

    이전에는 성공 응답을 받은 뒤에만 해제 대상으로 표시해, 응답이 늦으면 켜진 채 남았다.
    """
    from contact_scan_interfaces.action import ExecuteMotion

    node, goal, calls = _slide_rig(monkeypatch, fail=(timed_out,))
    try:
        result = node.execute_motion(FakeGoalHandle(goal))
        assert result.reason == ExecuteMotion.Result.REASON_ROBOT_ERROR
        assert 'release_compliance_ctrl' in calls
        if timed_out == 'set_desired_force':
            assert 'release_force' in calls
        assert 'move_line' not in calls                      # 켜지 못했으면 움직이지 않는다
    finally:
        node.destroy_node()


def test_release_that_fails_is_reported_not_hidden(ros, monkeypatch):
    """해제 호출이 실패하면 compliance_released=false 로 사실대로 알린다. 성공으로 적지 않는다."""
    from contact_scan_interfaces.action import ExecuteMotion

    node, goal, calls = _slide_rig(monkeypatch, fail=('release_compliance_ctrl',))
    try:
        monkeypatch.setattr(node, 'watch', lambda gh, m: (
            ExecuteMotion.Result.REASON_EDGE, ReasonCode.OK, ''))
        result = node.execute_motion(FakeGoalHandle(goal))
        assert result.compliance_released is False
        assert node.compliance_active is True              # 해제됐다고 기록하지 않는다
        assert node.motion is None
    finally:
        node.destroy_node()


def test_descend_never_touches_force_control(ros, monkeypatch):
    """힘 제어를 켜지 않는 동작에서 해제를 부르지 않는다. 불필요한 호출이 줄을 막지 않게 한다."""
    from contact_scan_interfaces.action import ExecuteMotion
    from robot_manager.robot_manager import Motion

    node = RobotManager(parameter_overrides=PARAMS)
    try:
        node.connected = True
        calls = []
        monkeypatch.setattr(node, 'call_sync', lambda c, r, label: calls.append(label) or True)
        monkeypatch.setattr(node, 'send_move', lambda motion: True)
        monkeypatch.setattr(node, 'watch', lambda gh, m: (
            ExecuteMotion.Result.REASON_CONTACT, ReasonCode.OK, ''))
        goal = _descend_goal()
        node.motion = Motion(goal, node.now_s())
        result = node.execute_motion(FakeGoalHandle(goal))
        assert result.compliance_released is True
        assert not any(label.startswith(('release', 'task_compliance', 'set_desired')) for label in calls)
    finally:
        node.destroy_node()


def test_release_force_that_times_out_still_waits_for_the_ramp(ros, monkeypatch):
    """release_force 가 시간 초과여도 컨트롤러는 램프를 시작했을 수 있다. 기다린 뒤 순응을 푼다.

    이 PR 의 전제("시간 초과여도 실행됐을 수 있다")를 해제 쪽에도 적용한다 (PR #121 리뷰).
    """
    from contact_scan_interfaces.action import ExecuteMotion

    node, goal, calls = _slide_rig(monkeypatch, fail=('release_force',))
    try:
        monkeypatch.setattr(node, 'watch', lambda gh, m: (
            ExecuteMotion.Result.REASON_EDGE, ReasonCode.OK, ''))
        result = node.execute_motion(FakeGoalHandle(goal))
        ramp_s = float(node.param('release_force_time_s'))
        gap = node.release_stamps['release_compliance_ctrl'] - node.release_stamps['release_force']
        assert gap >= ramp_s - 0.02, f'시간 초과 뒤 램프를 기다리지 않았다 ({gap:.3f} s)'
        assert result.compliance_released is False           # release_force 가 실패했으니 사실대로
        assert node.force_ctrl_active is True
    finally:
        node.destroy_node()
# ---- SLIDE 스텝 모드 (계약 7.2, v0.1.15) -------------------------------------------------------
STEP_PARAMS = PARAMS + [
    Parameter('slide_mode', Parameter.Type.STRING, 'step'),
    Parameter('step_coarse_m', Parameter.Type.DOUBLE, 0.0005),
    Parameter('step_fine_m', Parameter.Type.DOUBLE, 0.0001),
    Parameter('step_z_m', Parameter.Type.DOUBLE, 0.00005),
    Parameter('step_press_step_m', Parameter.Type.DOUBLE, 0.0001),
    Parameter('step_press_max_m', Parameter.Type.DOUBLE, 0.003),
    Parameter('step_lift_m', Parameter.Type.DOUBLE, 0.001),
    Parameter('step_nudge_m', Parameter.Type.DOUBLE, 0.001),
    Parameter('step_release_n', Parameter.Type.DOUBLE, 1.5),
    Parameter('step_follow_lo_n', Parameter.Type.DOUBLE, 3.0),
    Parameter('step_follow_hi_n', Parameter.Type.DOUBLE, 7.0),
    Parameter('step_max_force_n', Parameter.Type.DOUBLE, 12.0),
    Parameter('step_side_hit_n', Parameter.Type.DOUBLE, 8.0),
    Parameter('step_drop_m', Parameter.Type.DOUBLE, 0.0005),
    Parameter('step_z_tol_m', Parameter.Type.DOUBLE, 0.001),
    Parameter('step_max_slope_deg', Parameter.Type.DOUBLE, 5.0),
    Parameter('step_settle_s', Parameter.Type.DOUBLE, 0.01),
    Parameter('step_force_samples', Parameter.Type.INTEGER, 3),
    Parameter('step_still_m', Parameter.Type.DOUBLE, 0.00005),
    Parameter('step_still_window_s', Parameter.Type.DOUBLE, 0.05),
    Parameter('step_move_timeout_s', Parameter.Type.DOUBLE, 0.5),
]


def _step_rig(monkeypatch, run):
    """스텝 모드 SLIDE 를 드라이버 없이 돌린다. run 이 step_slide.run 을 대신한다."""
    from robot_manager import step_slide
    from robot_manager.robot_manager import Motion

    node = RobotManager(parameter_overrides=STEP_PARAMS)
    node.connected = True
    node.last_pose = (None, None, (0.42, -0.19, 0.18))
    node.last_force = (0.0, 0.0, 2.0)
    calls = []
    monkeypatch.setattr(node, 'call_sync', lambda client, request, label: calls.append(label) or True)
    monkeypatch.setattr(step_slide, 'run', run)
    goal = _slide_goal()
    node.motion = Motion(goal, node.now_s())
    return node, goal, calls


def _edge():
    from robot_manager.step_slide import StepEdge
    return StepEdge(position=(0.4636, -0.19, 0.1795), lost_z=0.1790, z_drop_m=0.0005,
                    force_delta=(0.3, -0.2, 0.8), travelled_m=0.0435)


def test_step_mode_edge_is_published_and_matched_by_result_event_id(ros, monkeypatch):
    """스텝 모드는 EDGE 를 스스로 확정해 /contact/event 로 내고, Result.event_id 로 짝을 맞춘다."""
    from contact_scan_interfaces.action import ExecuteMotion
    from contact_scan_interfaces.msg import ContactEvent
    from contact_scan_qos import QOS_EVENT
    from robot_manager.robot_manager import STEP_EVENT_ID_BASE

    node, goal, calls = _step_rig(monkeypatch, lambda io, direction, params: _edge())
    listener = rclpy.create_node('step_event_listener')
    received = []
    listener.create_subscription(ContactEvent, '/contact/event', received.append, QOS_EVENT)
    try:
        result = node.execute_motion(FakeGoalHandle(goal))
        collect(listener, 0.5, 0.05)
        assert result.reason == ExecuteMotion.Result.REASON_EDGE
        assert result.reason_code == ReasonCode.OK
        assert result.event_id > STEP_EVENT_ID_BASE
        assert result.compliance_released is True
        # 위치 제어만 쓴다. 순응 · 힘 제어를 켜지도 풀지도 않는다
        assert not any(c in calls for c in ('task_compliance_ctrl', 'set_desired_force',
                                            'release_force', 'release_compliance_ctrl')), calls
        edges = [e for e in received if e.type == ContactEvent.TYPE_EDGE]
        assert edges, '스텝 모드 EDGE 가 발행되지 않았다'
        event = edges[-1]
        assert event.event_id == result.event_id
        assert event.motion_id == goal.motion_id
        assert event.source == 'robot_step'
        assert event.frame_id == 'base_link'
        assert event.pose.position.x == pytest.approx(0.4636)
        assert event.pose.position.z == pytest.approx(0.1795)     # 최근 접촉 높이, 소실 z 가 아니다
        assert event.z_drop_valid is True and event.z_drop_m == pytest.approx(0.0005)
        assert node.motion is None
    finally:
        listener.destroy_node()
        node.destroy_node()


@pytest.mark.parametrize('kind, reason, code', [
    ('no_edge', 'REASON_MAX_DISTANCE', ReasonCode.NO_EDGE),
    ('over_force', 'REASON_OVER_FORCE', ReasonCode.OVER_FORCE),
    ('z_drift', 'REASON_ROBOT_ERROR', ReasonCode.ROBOT_ERROR),
])
def test_step_mode_failures_map_to_contract_reasons(ros, monkeypatch, kind, reason, code):
    from contact_scan_interfaces.action import ExecuteMotion
    from robot_manager.step_slide import StepFailure

    node, goal, _ = _step_rig(monkeypatch, lambda io, d, p: _raise(StepFailure(kind, '시험')))
    try:
        result = node.execute_motion(FakeGoalHandle(goal))
        assert result.reason == getattr(ExecuteMotion.Result, reason)
        assert result.reason_code == code
        assert result.event_id == 0
    finally:
        node.destroy_node()


def test_step_mode_stop_request_aborts_the_slide(ros, monkeypatch):
    """스텝 사이의 check() 가 정지 요청을 본다. 정지를 확인한 뒤 STOP_REQUESTED 로 끝난다."""
    from contact_scan_interfaces.action import ExecuteMotion

    def run(io, direction, params):
        _stop(node, '안전 이상')
        io.check()
        raise AssertionError('check() 가 정지 요청을 보지 못했다')

    node, goal, _ = _step_rig(monkeypatch, run)
    stops = []
    monkeypatch.setattr(node, 'stop_robot', lambda why, motion=None: stops.append(why) or (True, ''))
    try:
        result = node.execute_motion(FakeGoalHandle(goal))
        assert result.reason == ExecuteMotion.Result.REASON_STOP_REQUESTED
        assert stops and '안전 이상' in stops[0]
        assert node.stop_requested is None
    finally:
        node.destroy_node()


def test_step_mode_ignores_detector_edge_but_still_stops_on_over_force(ros, monkeypatch):
    from contact_scan_interfaces.msg import ContactEvent
    from robot_manager.robot_manager import Motion

    node = RobotManager(parameter_overrides=STEP_PARAMS)
    try:
        goal = _slide_goal()
        node.motion = Motion(goal, node.now_s())
        node.motion.step_mode = True
        edge = ContactEvent(type=ContactEvent.TYPE_EDGE, motion_id=goal.motion_id, event_id=7)
        node.on_event(edge)
        assert node.motion.event is None, 'contact_detector 의 EDGE 로 멈추면 안 된다'
        over = ContactEvent(type=ContactEvent.TYPE_OVER_FORCE, motion_id=goal.motion_id, event_id=8)
        node.on_event(over)
        assert node.motion.event is over
    finally:
        node.destroy_node()


def test_step_mode_goal_is_rejected_without_step_params(ros):
    """slide_mode: step 인데 step_* 가 없으면 goal 을 거절한다 (기본값을 코드에 두지 않는다)."""
    from rclpy.action import GoalResponse

    node = RobotManager(parameter_overrides=PARAMS + [
        Parameter('slide_mode', Parameter.Type.STRING, 'step')])
    try:
        node.connected = True
        node.last_pose = (None, None, (0.42, -0.19, 0.18))
        assert node.on_goal_request(_slide_goal()) == GoalResponse.REJECT
        assert node.on_goal_request(_descend_goal()) == GoalResponse.ACCEPT   # 하강은 상관없다
    finally:
        node.destroy_node()


def test_step_force_averages_only_samples_received_after_settling(ros, monkeypatch):
    import threading
    from robot_manager.robot_manager import Motion, NodeStepIO

    node = RobotManager(parameter_overrides=STEP_PARAMS)
    try:
        node.connected = True
        node.last_pose = (None, None, (0.42, -0.19, 0.18))
        node.last_force_sample = (10, (9.0, 9.0, 9.0))          # 이전 샘플. 평균에 들어가면 안 된다
        node.motion = Motion(_slide_goal(), node.now_s())
        io = NodeStepIO(node, FakeGoalHandle(node.motion.goal), node.motion, 0.005, 60.0)

        def feed():
            for i in range(1, 6):
                time.sleep(0.02)
                node.last_force_sample = (10 + i, (float(i), 0.0, 2.0 * i))
        threading.Thread(target=feed, daemon=True).start()
        fx, fy, fz = io.force()
        assert fx == pytest.approx((1 + 2 + 3) / 3)
        assert fz == pytest.approx((2 + 4 + 6) / 3)
    finally:
        node.destroy_node()


def test_step_move_waits_for_min_travel_time_then_stillness(ros, monkeypatch):
    """이동 시간이 지나기 전의 정지는 도착이 아니다. 지난 뒤 창 안에서 멈추면 돌아온다."""
    import threading
    from robot_manager.robot_manager import Motion, NodeStepIO

    node = RobotManager(parameter_overrides=STEP_PARAMS)
    try:
        node.connected = True
        node.last_pose = (None, None, (0.42, -0.19, 0.18))
        node.last_force_sample = (0, (0.0, 0.0, 0.0))
        node.motion = Motion(_slide_goal(), node.now_s())
        sent = []
        monkeypatch.setattr(node, 'call_sync', lambda c, r, label: sent.append(label) or True)
        io = NodeStepIO(node, FakeGoalHandle(node.motion.goal), node.motion, 0.005, 60.0)
        alive = True

        def feed():   # 2 mm 이동: 0.1 s 뒤 도착한 위치를 샘플마다 되풀이한다
            n = 0
            while alive:
                time.sleep(0.01)
                n += 1
                z = 0.18 if n < 10 else 0.18
                x = 0.42 + min(0.002, 0.0002 * n)
                node.last_pose = (None, None, (x, -0.19, z))
                node.last_force_sample = (n, (0.0, 0.0, 0.0))
        threading.Thread(target=feed, daemon=True).start()
        t0 = time.monotonic()
        io.move_rel((0.002, 0.0, 0.0))
        alive = False
        took = time.monotonic() - t0
        assert sent == ['move_line']
        assert took >= 0.002 / 0.005 - 0.01, f'이동 시간(0.4 s)보다 먼저 돌아왔다: {took:.2f} s'
        assert took < 0.4 + 0.5, f'멈춘 뒤에도 오래 기다렸다: {took:.2f} s'
    finally:
        node.destroy_node()


def test_arrival_grace_counts_from_move_command_not_from_accept(ros, monkeypatch):
    """수락 뒤 이동 명령까지 1 s 넘게 걸려도 출발 전에 도착으로 보지 않는다 (9/22 실기 1022).

    수락 시각부터 유예를 재면, 서비스 지연으로 명령이 늦게 나간 동작은 감시 첫 바퀴에서 이미 유예가
    끝나 있다. 로봇은 아직 서 있으니 "멈췄다 = 도착"이 되고, 로봇은 그 뒤 감시 없이 움직인다.
    """
    from contact_scan_interfaces.action import ExecuteMotion

    node = RobotManager(parameter_overrides=PARAMS)
    try:
        node.connected = True
        goal = _descend_goal()
        from rclpy.action import GoalResponse
        assert node.on_goal_request(goal) == GoalResponse.ACCEPT
        node.motion.started_s -= 1.5                    # 수락은 1.5 s 전 (실행 대기 · 서비스 지연)
        node.moving = False                             # 명령 직후라 아직 서 있다
        sent, finished = [], []
        monkeypatch.setattr(node, 'send_move', lambda motion: sent.append(node.now_s()) or True)
        monkeypatch.setattr(node, 'set_state', lambda *args: None)   # 상태 타이머 없이 moving 을 고정한다
        monkeypatch.setattr(node, 'finished_without_event', lambda motion: finished.append(node.now_s()) or (
            ExecuteMotion.Result.REASON_MAX_DISTANCE, ReasonCode.NO_CONTACT, ''))
        from robot_manager import robot_manager as rm
        monkeypatch.setattr(rm.motion_state, 'is_moving', lambda *args, **kwargs: False)   # 위치로도 서 있다
        monkeypatch.setattr(rm.motion_state, 'has_moved', lambda *args, **kwargs: False)

        node.execute_motion(FakeGoalHandle(goal))
        grace = float(node.param('arrival_grace_s'))
        assert finished, '멈춰 있으면 유예 뒤에는 끝나야 한다'
        assert finished[0] - sent[0] >= grace - 0.05, '유예는 이동 명령을 보낸 뒤부터 잰다'
    finally:
        node.destroy_node()

def test_start_of_motion_is_not_arrival_while_status_moving_is_stale(ros, monkeypatch):
    """출발 순간 위치로는 움직였는데 상태 타이머의 self.moving 이 아직 False 여도 도착으로 보지 않는다.

    9/22 실기 1061(HOME) · 1062(하강)가 0.13 · 0.25 s 만에 끝났고 로봇은 그 뒤 감시 없이 움직였다.
    "움직였는가"는 최신 위치로, "지금 움직이는가"는 한 주기 늦은 self.moving 으로 보면 이렇게 된다.
    """
    from contact_scan_interfaces.action import ExecuteMotion
    from robot_manager import robot_manager as rm

    node = RobotManager(parameter_overrides=PARAMS)
    try:
        node.connected = True
        goal = _descend_goal()
        from rclpy.action import GoalResponse
        assert node.on_goal_request(goal) == GoalResponse.ACCEPT
        node.moving = False                                        # 상태 타이머는 아직 출발 전 값
        monkeypatch.setattr(node, 'send_move', lambda motion: True)
        monkeypatch.setattr(node, 'set_state', lambda *args: None)
        calls = {'n': 0}

        def moving(*args, **kwargs):                               # 위치로는 처음 20 바퀴 동안 움직이다 선다
            calls['n'] += 1
            return calls['n'] <= 20
        monkeypatch.setattr(rm.motion_state, 'is_moving', moving)
        monkeypatch.setattr(rm.motion_state, 'has_moved', lambda *args, **kwargs: True)
        finished = []
        monkeypatch.setattr(node, 'finished_without_event', lambda motion: finished.append(calls['n']) or (
            ExecuteMotion.Result.REASON_MAX_DISTANCE, ReasonCode.NO_CONTACT, ''))

        node.execute_motion(FakeGoalHandle(goal))
        assert finished and finished[0] > 20, '위치로 움직이는 동안에는 끝내지 않는다'
    finally:
        node.destroy_node()


def _slide_node(monkeypatch, restart_max=1):
    """드라이버 없이 SLIDE 를 돌린다. 옆 이동 명령 · 드라이버 호출을 기록한다."""
    from contact_scan_interfaces.action import ExecuteMotion
    from geometry_msgs.msg import Pose
    from builtin_interfaces.msg import Time
    from rclpy.action import GoalResponse

    node = RobotManager(parameter_overrides=PARAMS + [
        Parameter('move_restart_max', Parameter.Type.INTEGER, restart_max)])
    node.connected = True
    start = (0.42, -0.18, 0.1808)
    node.last_pose = (Pose(), Time(), start)
    goal = ExecuteMotion.Goal(motion_id=6, operation=RobotSample.OP_SLIDE, direction=4,
                              max_distance=0.06, speed=0.005)
    assert node.on_goal_request(goal) == GoalResponse.ACCEPT
    node.moving = False
    rec = {'sent': [], 'calls': [], 'finished': [], 'start': start, 'goal': goal}
    monkeypatch.setattr(node, 'start_slide_force', lambda motion: True)
    monkeypatch.setattr(node, 'send_move', lambda motion: rec['sent'].append(node.now_s()) or True)
    monkeypatch.setattr(node, 'call_sync', lambda client, request, label: rec['calls'].append(label) or True)
    monkeypatch.setattr(node, 'set_state', lambda *args: None)
    monkeypatch.setattr(node, 'finished_without_event', lambda motion: rec['finished'].append(node.now_s()) or (
        ExecuteMotion.Result.REASON_MAX_DISTANCE, ReasonCode.NO_EDGE, ''))
    return node, rec
def test_slide_force_settle_in_z_is_not_counted_as_departure(ros, monkeypatch):
    """힘 제어를 켜는 동안 팁이 z 로 0.4 mm 움직여도 밀기가 출발한 것으로 보지 않는다 (9/22 실기 1083).

    옆 이동 명령이 늦게 나가 그 사이 멈춘 순간을 "움직였다 + 멈췄다 = 도착"으로 보면 0.3 mm 만 가고
    "최대 거리까지 접촉 소실 없음"으로 끝난다. 유예(arrival_grace_s)가 지나기 전에는 아무것도 하지 않고,
    지나면 출발하지 않은 것으로 보고 옆 이동 명령을 다시 보낸다(#153). 접촉 소실 없음으로 끝내지 않는다.
    """
    from geometry_msgs.msg import Pose
    from builtin_interfaces.msg import Time
    from robot_manager import robot_manager as rm

    node, rec = _slide_node(monkeypatch)
    try:
        calls = {'n': 0}
        start = rec['start']

        def moving(*args, **kwargs):             # 힘 제어로 z 가 움직이는 동안만 이동 중
            calls['n'] += 1
            node.last_pose = (Pose(), Time(), (start[0], start[1], start[2] + 0.0004))
            return calls['n'] <= 10
        monkeypatch.setattr(rm.motion_state, 'is_moving', moving)
        monkeypatch.setattr(rm.motion_state, 'has_moved', lambda *args, **kwargs: True)

        node.execute_motion(FakeGoalHandle(rec['goal']))
        grace = float(node.param('arrival_grace_s'))
        assert len(rec['sent']) >= 2 and rec['sent'][1] - rec['sent'][0] >= grace - 0.05, \
            'z 만 움직인 것은 출발이 아니다. 유예가 지나야 다시 보낸다'
        assert not rec['finished'], '출발하지 않은 밀기를 "접촉 소실 없음"으로 끝내지 않는다'
    finally:
        node.destroy_node()


def test_slide_that_does_not_start_is_sent_again(ros, monkeypatch):
    """옆 이동 명령이 실행되지 않으면 move_stop 뒤 한 번 다시 보내고, 출발하면 평소처럼 감시한다 (#153).

    9/22 실기: 힘 제어를 켠 뒤 보낸 amovel 을 드라이버가 32 회 중 8 회 실행하지 않았고, 그때마다 1 s 뒤
    "최대 거리까지 접촉 소실 없음"으로 끝나 통합 스캔이 중단됐다(20260922-134332-0152).
    """
    from contact_scan_interfaces.action import ExecuteMotion
    from geometry_msgs.msg import Pose
    from builtin_interfaces.msg import Time
    from robot_manager import robot_manager as rm

    node, rec = _slide_node(monkeypatch)
    try:
        start = rec['start']
        ticks = {'n': 0}

        def moving(*args, **kwargs):             # 두 번째 명령 뒤에만 옆으로 5 mm 가고 선다
            if len(rec['sent']) < 2:
                return False
            ticks['n'] += 1
            node.last_pose = (Pose(), Time(), (start[0], start[1] - 0.005, start[2]))
            return ticks['n'] <= 5
        monkeypatch.setattr(rm.motion_state, 'is_moving', moving)
        monkeypatch.setattr(rm.motion_state, 'has_moved', lambda *args, **kwargs: len(rec['sent']) >= 2)

        result = node.execute_motion(FakeGoalHandle(rec['goal']))
        assert len(rec['sent']) == 2, '한 번만 다시 보낸다'
        assert rec['calls'][:1] == ['move_stop'], '다시 보내기 전에 남은 명령을 비운다'
        assert result.reason == ExecuteMotion.Result.REASON_MAX_DISTANCE and rec['finished'], \
            '출발한 뒤에는 평소 도착 판정으로 끝난다'
    finally:
        node.destroy_node()


@pytest.mark.parametrize('restart_max', [0, 1])
def test_slide_that_never_starts_is_a_robot_error_not_no_edge(ros, monkeypatch, restart_max):
    """다시 보내도 출발하지 않으면 가짜 "접촉 소실 없음"(301)이 아니라 ROBOT_ERROR 로 끝낸다 (#153)."""
    from contact_scan_interfaces.action import ExecuteMotion
    from robot_manager import robot_manager as rm

    node, rec = _slide_node(monkeypatch, restart_max)
    try:
        monkeypatch.setattr(rm.motion_state, 'is_moving', lambda *args, **kwargs: False)
        monkeypatch.setattr(rm.motion_state, 'has_moved', lambda *args, **kwargs: False)
        handle = FakeGoalHandle(rec['goal'])
        result = node.execute_motion(handle)
        assert len(rec['sent']) == 1 + restart_max
        assert result.reason == ExecuteMotion.Result.REASON_ROBOT_ERROR
        assert result.reason_code == ReasonCode.ROBOT_ERROR and '출발하지 않았다' in result.detail
        assert not rec['finished'] and handle.state == 'aborted'
        assert rec['calls'].count('move_stop') == restart_max + 1, '다시 보낼 때마다 비우고, 끝낼 때 세운다'
    finally:
        node.destroy_node()

def test_stopping_a_slide_releases_force_before_waiting_for_stop(ros, monkeypatch):
    """SLIDE 를 세울 때는 멈춤을 기다리기 전에 힘 제어부터 푼다 (9/22 실기 1123).

    move_stop 은 옆 이동만 세운다. 힘 제어가 켜진 채면 모서리 밖에서 팁을 계속 끌어내려 멈춤이
    확인되지 않는다. 해제는 한 번만 하고, 순응은 release_all 이 램프 뒤에 푼다.
    """
    from robot_manager.robot_manager import Motion

    node = RobotManager(parameter_overrides=PARAMS)
    try:
        calls = []
        monkeypatch.setattr(node, 'call_sync', lambda client, request, label: calls.append(label) or True)
        node.moving = False
        motion = Motion(_descend_goal(), node.now_s())
        motion.force_on = motion.compliance_on = True

        stopped, _ = node.stop_robot('접촉 소실', motion)
        assert stopped
        assert calls == ['move_stop', 'release_force'], '멈춤을 기다리기 전에 힘 제어를 푼다'
        assert motion.force_on is False and motion.force_released_s is not None

        assert node.release_all(motion) is True
        assert calls == ['move_stop', 'release_force', 'release_compliance_ctrl'], '힘 제어 해제는 한 번만'
    finally:
        node.destroy_node()

def test_stopping_without_force_control_does_not_release(ros, monkeypatch):
    """힘 제어가 없는 동작(하강 · 이동)의 정지는 그대로다."""
    from robot_manager.robot_manager import Motion

    node = RobotManager(parameter_overrides=PARAMS)
    try:
        calls = []
        monkeypatch.setattr(node, 'call_sync', lambda client, request, label: calls.append(label) or True)
        node.moving = False
        motion = Motion(_descend_goal(), node.now_s())
        stopped, _ = node.stop_robot('접촉', motion)
        assert stopped and calls == ['move_stop']
    finally:
        node.destroy_node()


def _move_to_node(monkeypatch, target, restart_max=1):
    """드라이버 없이 MOVE_TO 를 돌린다. 이동 명령 · 드라이버 호출을 기록한다."""
    from contact_scan_interfaces.action import ExecuteMotion
    from geometry_msgs.msg import Pose
    from builtin_interfaces.msg import Time
    from rclpy.action import GoalResponse

    node = RobotManager(parameter_overrides=PARAMS + [
        Parameter('move_restart_max', Parameter.Type.INTEGER, restart_max)])
    node.connected = True
    start = (0.42, -0.18, 0.1808)
    node.last_pose = (Pose(), Time(), start)
    goal = ExecuteMotion.Goal(motion_id=8, operation=RobotSample.OP_MOVE_TO,
                              frame_id='base_link', speed=0.03)
    goal.target.position.x, goal.target.position.y, goal.target.position.z = target
    goal.target.orientation.w = 1.0
    assert node.on_goal_request(goal) == GoalResponse.ACCEPT
    node.moving = False
    rec = {'sent': [], 'calls': [], 'finished': [], 'start': start, 'goal': goal}
    monkeypatch.setattr(node, 'send_move', lambda motion: rec['sent'].append(node.now_s()) or True)
    monkeypatch.setattr(node, 'call_sync', lambda client, request, label: rec['calls'].append(label) or True)
    monkeypatch.setattr(node, 'set_state', lambda *args: None)
    monkeypatch.setattr(node, 'finished_without_event', lambda motion: rec['finished'].append(node.now_s()) or (
        ExecuteMotion.Result.REASON_TARGET_REACHED, ReasonCode.OK, ''))
    return node, rec


def test_move_to_that_never_started_is_sent_again(ros, monkeypatch):
    """MOVE_TO 가 유예 안에 출발하지 않으면 move_stop 뒤 같은 명령을 다시 보낸다 (9/23 실기 12:52).

    모서리 뒤 올림(50 mm)이 86 ms 만에 끝나고 한 걸음도 가지 않아 통합 스캔이 중단됐다.
    도착 허용치 검사가 ROBOT_ERROR 로 잡아 주지만, 다시 보내면 그 자리에서 이어갈 수 있다.
    """
    from robot_manager import robot_manager as rm

    node, rec = _move_to_node(monkeypatch, (0.42, -0.18, 0.2308))   # 50 mm 위
    try:
        monkeypatch.setattr(rm.motion_state, 'is_moving', lambda *a, **k: False)
        monkeypatch.setattr(rm.motion_state, 'has_moved', lambda *a, **k: False)
        node.execute_motion(FakeGoalHandle(rec['goal']))
        assert len(rec['sent']) == 2, '출발하지 않은 이동 명령을 한 번 다시 보낸다'
        assert 'move_stop' in rec['calls'], '다시 보내기 전에 남은 명령을 비운다'
    finally:
        node.destroy_node()


def test_move_to_already_at_target_is_not_sent_again(ros, monkeypatch):
    """목표에 이미 닿아 있으면(0 mm 이동) 안 움직이는 것이 정상이라 다시 보내지 않는다."""
    from robot_manager import robot_manager as rm

    node, rec = _move_to_node(monkeypatch, (0.42, -0.18, 0.1808))   # 지금 자리
    try:
        monkeypatch.setattr(rm.motion_state, 'is_moving', lambda *a, **k: False)
        monkeypatch.setattr(rm.motion_state, 'has_moved', lambda *a, **k: False)
        node.execute_motion(FakeGoalHandle(rec['goal']))
        assert len(rec['sent']) == 1, '허용치 안이면 다시 보내지 않는다'
        assert rec['finished'], '도착으로 끝난다'
    finally:
        node.destroy_node()
