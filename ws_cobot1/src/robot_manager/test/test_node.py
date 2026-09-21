"""robot_manager 노드 테스트 (T15).

두산 드라이버(dsr_msgs2)가 없는 개인 PC 에서는 건너뛴다. **CI 에는 dsr_msgs2 를 고정 커밋으로
빌드해 넣으므로 반드시 돌아야 하고**, 없으면 건너뛰지 않고 실패한다.
여기서는 **드라이버가 없을 때의 동작**을 본다. 실기·Virtual 동작은 PR 본문에 따로 적는다.
"""
import importlib.util
import os

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

        monkeypatch.setattr(node, 'stop_robot', lambda why: (False, '멈춤을 확인하지 못했다'))
        reason, code, detail = node.stop_for_event(motion)
        assert reason == ExecuteMotion.Result.REASON_ROBOT_ERROR
        assert code == ReasonCode.ROBOT_ERROR and '확인하지 못했다' in detail

        monkeypatch.setattr(node, 'stop_robot', lambda why: (True, ''))
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
        monkeypatch.setattr(node, 'stop_robot', lambda why: stops.append(why) or (True, ''))

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
        monkeypatch.setattr(node, 'stop_robot', lambda why: (True, ''))
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
        monkeypatch.setattr(node, 'stop_robot', lambda why: stops.append(why) or (True, ''))

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
        monkeypatch.setattr(node, 'stop_robot', lambda why: (False, '멈춤을 확인하지 못했다'))

        handle = FakeGoalHandle(goal)
        result = node.execute_motion(handle)
        assert result.reason == ExecuteMotion.Result.REASON_ROBOT_ERROR and handle.state == 'aborted'
        assert node.stop_requested is not None, '확인하지 못했는데 요청이 사라졌다'
        # HOME 이 아닌 동작은 거절한다. 안전복귀(OP_HOME)는 받는다(#115, 별도 시험)
        assert node.reject_reason(_descend_goal()).startswith('STOP_REQUESTED')

        # 복구: 멈춘 것을 확인한 뒤 /robot/stop 을 다시 부른다
        monkeypatch.setattr(node, 'stop_robot', lambda why: (True, ''))
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
        monkeypatch.setattr(node, 'stop_robot', lambda why: stops.append(why) or (False, '확인 못 함'))
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
        monkeypatch.setattr(node, 'stop_robot', lambda why: (True, ''))
        monkeypatch.setattr(node, 'send_move', lambda motion: True)

        handle = FakeGoalHandle(home)
        result = node.execute_motion(handle)
        assert result.reason == ExecuteMotion.Result.REASON_STOP_REQUESTED
        assert handle.state == 'aborted'
    finally:
        node.destroy_node()
