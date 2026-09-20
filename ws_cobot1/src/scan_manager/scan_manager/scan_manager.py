"""scan_manager 노드 (T10 골격 + T19a 시퀀스 · 서버 · geometry 연결).

- 서버: /scan/run · /scan/home · /scan/resume (Action), /scan/stop · /scan/set_config (Service).
  노드가 뜨자마자 준비된다(mqtt_bridge 가 server_is_ready() 로 본다).
- 시퀀스는 /scan/run 의 execute 콜백 안에서 돈다. 순서는 sequence.ScanRunner, 이 파일은 그 Ports 를 구현한다.
- 작업 중지 · 안전복귀 · 재시작은 독립된 명령이다. /scan/stop 은 정지만 요청하고, 홈 복귀나 재시작을 부르지 않는다.
- 상태 기계의 on_change(락 안)에서는 /scan/state 발행과 쓰기 큐 투입만 한다. 디스크 쓰기는 전용 스레드 1개가 한다.
- SetConfig 전파(P01~P03), 재시작 로직은 여기 없다(T19b · T26). /scan/resume 은 NOT_SUPPORTED 로 끝낸다.

executor 구성과 교착이 없는 이유는 README.md 에 있다.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import os
import random
import signal
import threading
import time

from contact_scan_interfaces.action import ExecuteMotion
from contact_scan_interfaces.action import Resume
from contact_scan_interfaces.action import ReturnHome
from contact_scan_interfaces.action import RunScan
from contact_scan_interfaces.msg import ContactEvent
from contact_scan_interfaces.msg import RobotStatus
from contact_scan_interfaces.msg import SafetyStatus
from contact_scan_interfaces.msg import ScanLog
from contact_scan_interfaces.msg import ScanResult
from contact_scan_interfaces.msg import ScanState
from contact_scan_interfaces.srv import SetConfig
from contact_scan_interfaces.srv import StopRobot
from contact_scan_interfaces.srv import StopScan
from contact_scan_interfaces.srv import TareForce
from contact_scan_qos import QOS_EVENT
from contact_scan_qos import QOS_LOG
from contact_scan_qos import QOS_STATE
import rclpy
from rclpy.action import ActionClient
from rclpy.action import ActionServer
from rclpy.action import CancelResponse
from rclpy.action import GoalResponse
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import ExternalShutdownException
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter

from . import conversions
from . import params as scan_params
from .contract_enums import Direction
from .contract_enums import MotionReason
from .contract_enums import Operation
from .contract_enums import Phase
from .contract_enums import Reason
from .event_matcher import EventMatcher
from .geometry_adapter import compute_shape
from .geometry_adapter import EdgeMeasurement
from .geometry_adapter import TopMeasurement
from .result_store import Frames
from .result_store import Interruption
from .result_store import Measurement
from .result_store import ResultStore
from .result_store import Stamp
from .result_store.records import CONFIG_FIELDS
from .sequence import MatchedEvent
from .sequence import MotionPlanner
from .sequence import MotionResult
from .sequence import OutcomeKind
from .sequence import Ports
from .sequence import run_home
from .sequence import RunOutcome
from .sequence import ScanRunner
from .sequence import StepOutcome
from .state_machine import Command
from .state_machine import Conditions
from .state_machine import InvalidTransition
from .state_machine import ScanStateMachine
from .state_machine import Signal
from .state_machine import Snapshot

# 설계 출발값. 실제 값은 contact_scan_bringup/config/*.yaml 에 둔다.
DEFAULT_STATE_PUBLISH_PERIOD_S = 1.0

# 아래 둘은 구조에서 나오는 값이지 튜닝 값이 아니다.
# 동시에 막힐 수 있는 콜백: 시퀀스(execute) 1 + 거절로 바로 끝나는 goal 1 + 구독 1 + Service 1.
MIN_EXECUTOR_THREADS = 4
# 기다리는 동안 종료 요청을 들여다보는 간격(s). 기다림의 한도는 전부 파라미터다.
_WAIT_SLICE_S = 0.1
# 종료할 때 실행 중인 콜백이 빠져나오기를 기다리는 한도(s). 넘으면 그대로 끝낸다.
_SHUTDOWN_GRACE_S = 5.0

_PARAM_TYPE = {
    scan_params.DOUBLE: Parameter.Type.DOUBLE,
    scan_params.DOUBLE_ARRAY: Parameter.Type.DOUBLE_ARRAY,
    scan_params.STRING: Parameter.Type.STRING,
    scan_params.STRING_ARRAY: Parameter.Type.STRING_ARRAY,
}
_EXPECTED_EVENT = {
    Operation.DESCEND: ContactEvent.TYPE_CONTACT,
    Operation.SLIDE: ContactEvent.TYPE_EDGE,
}


def to_msg(snapshot: Snapshot, stamp) -> ScanState:
    return conversions.state_to_msg(snapshot, stamp)


def new_scan_id() -> str:
    """계약 6.2절. **벽시계**로 발급한다(result_store 가 사전순을 "가장 최근"으로 쓴다)."""
    return f'{datetime.now():%Y%m%d-%H%M%S}-{random.randrange(10000):04d}'


class _Closing(Exception):
    """노드가 종료 중이다. 기다리던 시퀀스 스레드를 빠져나오게 한다."""


class _Job:
    """진행 중인 명령 하나(/scan/run 또는 /scan/home)의 문맥."""

    def __init__(self, scan_id, params, config_msg=None, started_at=None):
        self.scan_id = scan_id
        self.params = params
        self.config_msg = config_msg
        self.started_at = started_at
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.stop_snapshot = None     # STOP 접수 직전의 Snapshot
        self.motion_handle = None     # 진행 중인 ExecuteMotion goal
        self.top = None
        self.edges = {}
        self.result_msg = None        # 발행한 ScanResult. None 이면 아직 발행하지 않았다


class ScanManager(Node):

    def __init__(self, **kwargs):
        super().__init__('scan_manager', **kwargs)
        period = self.declare_parameter(
            'state_publish_period_s', DEFAULT_STATE_PUBLISH_PERIOD_S).value
        if not period > 0.0:
            raise ValueError(f'state_publish_period_s 는 0 보다 커야 한다: {period}')
        # 모션 · 보정 수치에는 코드 예비값이 없다. 값이 없어도 기동하고, START 에서 거절한다.
        for spec in scan_params.SPECS:
            self.declare_parameter(spec.name, _PARAM_TYPE[spec.kind])
        order = self.get_parameter_or('direction_order').value
        if order is None:
            order = scan_params.SPEC_BY_NAME['direction_order'].default
        problem = scan_params.SPEC_BY_NAME['direction_order'].check(list(order))
        if problem:
            raise ValueError(f'direction_order = {list(order)}: {problem}')
        self._direction_order = tuple(order)  # 기동할 때만 읽는다(상태 기계가 순서를 들고 있다)

        self._closing = threading.Event()
        self._job = None
        self._job_lock = threading.Lock()
        self._config = {name: None for name, _flag in CONFIG_FIELDS}  # SetConfig 로 받은 값
        self._last_motion_id = {}                                     # scan_id → 마지막 motion_id
        self._status_cond = threading.Condition()
        self._robot_status = None
        self._safety_status = None
        self._store = None
        self._store_dir = None
        self._begun = None
        self._begin_args = None
        self._writer = ThreadPoolExecutor(max_workers=1, thread_name_prefix='result_store')
        self._matcher = EventMatcher(on_ignored=self._on_event_ignored)

        self._state_seq = 0
        self._state_pub_lock = threading.Lock()
        self._state_pub = self.create_publisher(ScanState, '/scan/state', QOS_STATE)
        self._result_pub = self.create_publisher(ScanResult, '/scan/result', QOS_STATE)
        self._log_pub = self.create_publisher(ScanLog, '/scan/log', QOS_LOG)
        self.state_machine = ScanStateMachine(
            direction_order=[Direction[name] for name in self._direction_order],
            on_change=self._on_change)

        subs = MutuallyExclusiveCallbackGroup()       # 시퀀스가 기다리는 동안에도 항상 처리된다
        actions = ReentrantCallbackGroup()
        services = MutuallyExclusiveCallbackGroup()
        clients = ReentrantCallbackGroup()
        self.create_subscription(
            RobotStatus, '/robot/status', self._on_robot_status, QOS_STATE, callback_group=subs)
        self.create_subscription(
            SafetyStatus, '/safety/status', self._on_safety_status, QOS_STATE, callback_group=subs)
        self.create_subscription(
            ContactEvent, '/contact/event', self._matcher.offer, QOS_EVENT, callback_group=subs)
        self._motion_client = ActionClient(
            self, ExecuteMotion, '/robot/execute_motion', callback_group=clients)
        self._tare_client = self.create_client(TareForce, '/contact/tare', callback_group=clients)
        self._robot_stop_client = self.create_client(
            StopRobot, '/robot/stop', callback_group=clients)
        self._action_servers = [
            ActionServer(
                self, action_type, name, execute_callback=execute, callback_group=actions,
                goal_callback=lambda _goal: GoalResponse.ACCEPT,
                # 작업 중지는 /scan/stop 하나로 한다(정지 확인 · 중단 위치 기록이 거기에 묶여 있다)
                cancel_callback=lambda _handle: CancelResponse.REJECT)
            for action_type, name, execute in (
                (RunScan, '/scan/run', self._execute_run),
                (ReturnHome, '/scan/home', self._execute_home),
                (Resume, '/scan/resume', self._execute_resume),
            )]
        self.create_service(StopScan, '/scan/stop', self._on_stop, callback_group=services)
        self.create_service(
            SetConfig, '/scan/set_config', self._on_set_config, callback_group=services)

        self._state_timer = self.create_timer(period, self._publish_state_periodic)
        self._on_change(self.state_machine.snapshot())

    def announce_ready(self):
        """executor 에 올린 뒤에 부른다(그때부터 서버가 응답한다)."""
        missing = scan_params.check(self._parameter_values()).describe()
        self.get_logger().info(
            'scan_manager 준비: /scan/run · /scan/home · /scan/resume · /scan/stop · /scan/set_config'
            + (f' (지금 값으로는 START 를 거절한다. {missing})' if missing else ''))

    # ---- 발행 ----

    def _now_msg(self):
        return self.get_clock().now().to_msg()

    def _now_stamp(self) -> Stamp:
        return Stamp(*self.get_clock().now().seconds_nanoseconds())

    def _publish_state(self, snapshot: Snapshot):
        with self._state_pub_lock:
            self._state_seq += 1
            self._state_pub.publish(to_msg(snapshot, self._now_msg()))

    def _publish_state_periodic(self):
        # 스냅숏을 뜬 뒤에 상태가 바뀌었으면 그 변경이 이미 발행됐다. 옛 상태로 덮어쓰지 않는다.
        seq = self._state_seq
        snapshot = self.state_machine.snapshot()
        with self._state_pub_lock:
            if seq == self._state_seq:
                self._state_pub.publish(to_msg(snapshot, self._now_msg()))

    def _on_change(self, snapshot: Snapshot):
        # 상태 기계의 락 안이다. 발행하고 큐에 넣기만 한다(디스크 쓰기 · 대기 금지).
        self._publish_state(snapshot)
        if not snapshot.scan_id or self._store is None or self._closing.is_set():
            return
        if snapshot.scan_id != self._begun:
            if self._begin_args is None:
                return  # 이 노드가 시작하지 않은 작업(기록이 없다)
            self._begun = snapshot.scan_id
            job = self._writer.submit(
                self._store.begin_scan, snapshot.scan_id, state=snapshot, **self._begin_args)
            self._begin_args = None
        else:
            job = self._writer.submit(self._store.record_state, snapshot)
        job.add_done_callback(self._log_write_error)

    def _log_write_error(self, job):
        if job.exception() is not None:
            self.get_logger().error(f'result_store 쓰기 실패: {job.exception()!r}')

    def _write(self, method, *args, **kwargs):
        """다음 단계로 가기 전에 디스크에 있어야 하는 기록. 쓰기 스레드에 맡기고 끝을 기다린다."""
        return self._writer.submit(method, *args, **kwargs).result()

    def log(self, level, code, message, position=None, orientation=None):
        """/scan/log + 노드 로그. 상태 기계의 락 안(on_change)에서 부르지 않는다."""
        snapshot = self.state_machine.snapshot()
        msg = ScanLog()
        msg.stamp = self._now_msg()
        msg.scan_id = snapshot.scan_id
        msg.level = level
        msg.phase = int(snapshot.phase)
        msg.direction = int(snapshot.direction)
        msg.motion_id = snapshot.motion_id
        msg.code = int(code)
        msg.message = message
        msg.pose_valid = position is not None
        nan = conversions.NAN
        x, y, z = position if position is not None else (nan, nan, nan)
        msg.pose.position.x, msg.pose.position.y, msg.pose.position.z = x, y, z
        if position is not None:
            msg.frame_id = self.get_parameter_or('motion_frame_id').value or \
                scan_params.SPEC_BY_NAME['motion_frame_id'].default
        self._log_pub.publish(msg)
        # rclpy 로거는 호출 위치마다 severity 를 고정한다. 그래서 줄을 나눈다.
        text = f'[{snapshot.phase.name} code={int(code)}] {message}'
        if level == ScanLog.LEVEL_ERROR:
            self.get_logger().error(text)
        elif level == ScanLog.LEVEL_WARN:
            self.get_logger().warning(text)
        else:
            self.get_logger().info(text)

    def _on_event_ignored(self, event, reason):
        self.log(
            ScanLog.LEVEL_INFO, Reason.OK,
            f'ContactEvent 무시({reason}): event_id={event.event_id} motion_id={event.motion_id} '
            f'type={event.type} (판정 좌표)', conversions.position_of(event.pose))

    # ---- 구독 ----

    def _on_robot_status(self, msg):
        with self._status_cond:
            self._robot_status = msg
            self._status_cond.notify_all()

    def _on_safety_status(self, msg):
        with self._status_cond:
            self._safety_status = msg

    def conditions(self) -> Conditions:
        """명령 시점의 보호 조건. 아직 받지 못한 것은 None 이고 거절 사유가 된다."""
        with self._status_cond:
            robot, safety = self._robot_status, self._safety_status
        return Conditions(
            robot_connected=None if robot is None else bool(robot.connected),
            safety_latched=None if safety is None else bool(safety.latched))

    def safety_reason_code(self) -> int:
        with self._status_cond:
            safety = self._safety_status
        return int(safety.reason_code) if safety is not None and safety.latched else 0

    # ---- 기다림 ----

    def _wait(self, is_done, timeout_s, waiter) -> bool:
        """waiter(남은 시간)로 기다리며 종료 요청을 들여다본다. 한도 안에 끝나면 True."""
        deadline = time.monotonic() + timeout_s
        while not is_done():
            if self._closing.is_set():
                raise _Closing()
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                return False
            waiter(min(remaining, _WAIT_SLICE_S))
        return True

    def wait_future(self, future, timeout_s) -> bool:
        """콜백 안에서 spin 하지 않는다(교착). 완료 콜백이 Event 를 세우고, 이 스레드는 그것을 기다린다."""
        done = threading.Event()
        future.add_done_callback(lambda _future: done.set())
        return self._wait(done.is_set, timeout_s, done.wait)

    def wait_still(self, timeout_s) -> bool:
        """**지금보다 뒤에 찍힌** /robot/status 로 connected && !moving 을 확인한다(계약 1장 "접수 ≠ 완료").

        요청 전의 오래된 moving=false 로 통과시키지 않는다.
        """
        asked_at = self.get_clock().now().nanoseconds

        def still():
            status = self._robot_status
            if status is None or not status.connected or status.moving:
                return False
            return status.stamp.sec * 1_000_000_000 + status.stamp.nanosec > asked_at

        with self._status_cond:
            return self._wait(still, timeout_s, self._status_cond.wait)

    # ---- 파라미터 · 설정 ----

    def _parameter_values(self) -> dict:
        values = {
            spec.name: self.get_parameter_or(spec.name).value for spec in scan_params.SPECS}
        values['direction_order'] = list(self._direction_order)
        return values

    def _effective_config(self, override=None) -> dict:
        """ScanConfig 12개의 현재 값: yaml ← SetConfig ← override. 모르는 값은 None 이다.

        scan_manager 가 아는 것은 자기 모션 6개뿐이다. 다른 노드의 6개는 SetConfig 로 받은 것만 안다
        (전파 P01~P03 은 T19b). 모르는 값을 0 으로 채우지 않는다.
        """
        config = {name: None for name, _flag in CONFIG_FIELDS}
        for name in scan_params.MOTION_CONFIG_NAMES:
            config[name] = self.get_parameter_or(name).value
        config.update({k: v for k, v in self._config.items() if v is not None})
        config.update(override or {})
        return config

    def _store_for(self, result_dir) -> ResultStore:
        if self._store is None or self._store_dir != result_dir:
            self._store = ResultStore(os.path.expanduser(result_dir), now_fn=self._now_stamp)
            self._store_dir = result_dir
        return self._store

    # ---- 거절 ----

    def _reject(self, goal_handle, result, reason_code, detail):
        """거절할 goal 을 끝내는 **한 곳**. 방식을 바꿀 때는 여기와 goal_callback 만 고친다.

        ROS 2 의 goal reject 에는 사유가 없고, mqtt_bridge 는 reject 를 BUSY 로 고정해 낸다.
        그래서 goal 은 항상 accept 하고, 거절할 요청은 phase 를 바꾸지 않은 채 바로
        Result(success=false, reason_code=1xx)로 끝낸다. 실제 사유가 scan/command_result 로 웹에 간다.
        """
        result.success = False
        result.reason_code = int(reason_code)
        result.detail = detail
        self.log(ScanLog.LEVEL_WARN, reason_code, f'명령 거절: {detail}')
        goal_handle.abort()
        return result

    # ---- /scan/run ----

    def _execute_run(self, goal_handle):
        request = goal_handle.request
        result = RunScan.Result()
        rejection = self._begin_run(request)
        if isinstance(rejection, tuple):
            return self._reject(goal_handle, result, *rejection)
        job = rejection
        try:
            ports = _NodePorts(self, job)
            outcome = ScanRunner(
                MotionPlanner(job.params), ports, job.params.direction_order).run()
            self._last_motion_id[job.scan_id] = ports.last_motion_id
            if job.result_msg is None:
                # 측정이 끝나기 전에 끝난 작업(중단). 실패는 fail() 이 이미 발행했다
                self._publish_partial_result(job, outcome.reason_code, outcome.detail)
        except _Closing:
            outcome = None
        except Exception as exc:  # 기록 실패 등. 모션은 동기로 기다리므로 이 시점에 진행 중인 모션은 없다
            outcome = self._internal_failure(job, exc)
        finally:
            self._end_job(job)

        result.scan_id = job.scan_id
        if job.result_msg is not None:
            result.result = job.result_msg
        # success 는 명령 전체(마무리 복귀 포함)의 성공 여부다. result.result.success 는 측정의 성공 여부다
        return self._finish_goal(goal_handle, result, outcome)

    def _finish_goal(self, goal_handle, result, outcome):
        """시작된 명령의 끝. outcome 이 None 이면 노드가 종료 중이다."""
        if outcome is not None and outcome.kind is OutcomeKind.DONE:
            result.success = True
            goal_handle.succeed()
            return result
        result.success = False
        result.reason_code = int(outcome.reason_code) if outcome else int(Reason.CANCELED)
        result.detail = outcome.detail if outcome else 'scan_manager 종료'
        try:
            goal_handle.abort()
        except Exception:  # 종료 중에는 context 가 이미 내려가 있을 수 있다
            if outcome is not None:
                raise
        return result

    def _begin_run(self, request):
        """START 를 접수한다. 거절이면 (reason_code, detail), 접수면 _Job."""
        with self._job_lock:
            if self.state_machine.is_busy:
                return Reason.BUSY, f'phase={self.state_machine.phase.name}'
            override = {}
            if request.use_override:
                override = {
                    k: v for k, v in conversions.config_values_from_msg(
                        request.config_override).items()}
                problems = scan_params.check_values(override)
                if problems:
                    return Reason.INVALID_VALUE, 'config_override: ' + '; '.join(problems)
            config = self._effective_config(override)
            values = self._parameter_values()
            values.update({name: config[name] for name in scan_params.MOTION_CONFIG_NAMES})
            checked = scan_params.check(values)
            if not checked.ok:
                return Reason.INVALID_VALUE, checked.describe()
            params = checked.params

            scan_id = new_scan_id()
            started_at = self._now_stamp()
            job = _Job(scan_id, params, conversions.config_to_msg(config), started_at)
            self._store_for(params.result_dir)
            # on_change 가 START 의 통지에서 begin_scan 을 큐에 넣는다. 거절되면 기록이 생기지 않는다.
            self._begin_args = {
                'config': conversions.config_snapshot(config),
                'frames': Frames(detection=params.motion_frame_id, result=params.result_frame_id),
                'direction_order': params.direction_order,
                'started_at': started_at,
                'node_params': params.node_params(),
            }
            self._job = job
            outcome = self.state_machine.request(
                Command.START, conditions=self.conditions(), scan_id=scan_id)
            if not outcome.accepted:
                self._job = self._begin_args = None
                return outcome.reason, outcome.detail
        self.log(ScanLog.LEVEL_INFO, Reason.OK, f'작업 시작 request_id={request.request_id}')
        return job

    def _end_job(self, job):
        self._matcher.end()
        # 마지막 상태(DONE · STOPPED · ERROR)는 on_change 가 큐에 넣기만 했다. 명령의 Result 를 돌려주기 전에
        # 디스크에 쓰인 것을 확인한다. 그래야 Result 를 받은 쪽이 기록을 읽어도 옛 상태를 보지 않는다.
        if not self._closing.is_set():
            self._write(lambda: None)
        with self._job_lock:
            if self._job is job:
                self._job = None

    def _internal_failure(self, job, exc):
        detail = f'internal: {exc!r}'
        self.get_logger().error(detail)
        try:
            _NodePorts(self, job).fail(int(Reason.ROBOT_ERROR), detail, None)
        except Exception as nested:  # 기록 자체가 안 되는 경우. 상태만은 ERROR 로 보낸다
            self.get_logger().error(f'실패 기록도 실패: {nested!r}')
        return RunOutcome(OutcomeKind.FAILED, int(Reason.ROBOT_ERROR), detail)

    def _publish_result(self, job, shape):
        job.result_msg = conversions.result_to_msg(
            job.scan_id, shape, job.config_msg, self._now_msg())
        self._result_pub.publish(job.result_msg)

    def _publish_partial_result(self, job, reason_code, detail):
        """실패 · 중단으로 끝난 작업의 결과. 확보한 값만 유효하고 나머지는 NaN + *_valid=false 다."""
        if job.params is None or job.started_at is None:
            return
        output = compute_shape(
            job.top, job.edges, job.params, started_at=job.started_at,
            finished_at=self._now_stamp(), ended_with=(int(reason_code), detail))
        self._publish_result(job, output.shape)

    # ---- /scan/home ----

    def _execute_home(self, goal_handle):
        result = ReturnHome.Result()
        with self._job_lock:
            if self.state_machine.is_busy:
                return self._reject(
                    goal_handle, result, Reason.BUSY, f'phase={self.state_machine.phase.name}')
            # OP_HOME 에 실을 제한 시간 · 정지 확인 한도만 본다. 측정 파라미터가 비었다고 홈 복귀를 막지 않는다
            checked = scan_params.check_home({
                **self._parameter_values(),
                'motion_timeout_s': self._effective_config()['motion_timeout_s']})
            if not checked.ok:
                return self._reject(goal_handle, result, Reason.INVALID_VALUE, checked.describe())
            before = self.state_machine.snapshot()
            job = _Job(before.scan_id, checked.params)
            self._job = job
            outcome = self.state_machine.request(Command.HOME, conditions=self.conditions())
            if not outcome.accepted:
                self._job = None
                return self._reject(goal_handle, result, outcome.reason, outcome.detail)
        recorded = bool(job.scan_id) and self._store is not None and self._begun == job.scan_id
        try:
            if recorded:
                self._write(self._store.record_home_requested, job.scan_id, before.phase)
            self.log(
                ScanLog.LEVEL_INFO, Reason.OK,
                f'안전복귀 시작 request_id={goal_handle.request.request_id}')
            ports = _NodePorts(self, job, recorded=recorded)
            first = self._last_motion_id.get(job.scan_id, 0) + 1
            outcome = run_home(MotionPlanner(job.params), ports, first_motion_id=first)
            self._last_motion_id[job.scan_id] = first
            done = outcome.kind is OutcomeKind.DONE
            final = ports.last_result.raw if ports.last_result is not None else None
            if recorded and outcome.kind is not OutcomeKind.STOPPED:
                self._write(
                    self._store.record_home_finished, job.scan_id, done,
                    final_pose=conversions.stop_pose_record(final) if final is not None else None)
        except _Closing:
            outcome, done, final = None, False, None
        except Exception as exc:
            outcome, done, final = self._internal_failure(job, exc), False, None
        finally:
            self._end_job(job)

        if final is not None:
            result.final_pose = final.pose
            result.frame_id = final.frame_id
        return self._finish_goal(goal_handle, result, outcome)

    # ---- /scan/resume ----

    def _execute_resume(self, goal_handle):
        # 재시작 로직은 T26. 그 전까지는 상태 기계에 묻지도 않는다(phase 를 바꾸지 않는다).
        result = Resume.Result()
        result.scan_id = goal_handle.request.scan_id
        return self._reject(
            goal_handle, result, Reason.NOT_SUPPORTED, '재시작은 아직 구현되지 않았다(T26)')

    # ---- /scan/stop ----

    def _on_stop(self, request, response):
        """정지를 **요청**하고 접수만 돌려준다. 정지 완료 확인 · 중단 위치 기록은 시퀀스 스레드가 한다.

        홈 복귀 · 재시작을 부르지 않는다(CLAUDE.md 규칙 3). 다른 노드의 완료를 여기서 기다리지 않는다.
        """
        job = self._job
        handle = None
        if job is not None:
            with job.lock:
                before = self.state_machine.snapshot()
                outcome = self.state_machine.request(Command.STOP)
                if outcome.changed:
                    job.stop_snapshot = before
                    job.stop_event.set()
                    handle = job.motion_handle
        else:
            outcome = self.state_machine.request(Command.STOP)

        # 멈출 작업이 없어도 로봇 정지는 요청한다(멱등, 계약 4.1절). 응답은 기다리지 않는다.
        if self._robot_stop_client.service_is_ready():
            self._robot_stop_client.call_async(StopRobot.Request(
                request_id=request.request_id, requester=self.get_name(),
                reason=request.reason or int(Reason.STOP_REQUESTED), detail=request.detail))
            robot_stop = '/robot/stop 요청함'
        else:
            robot_stop = '/robot/stop 서버가 없다'
        if handle is not None:
            handle.cancel_goal_async()

        response.accepted = outcome.accepted
        response.reason_code = int(outcome.reason)
        phase = outcome.state.phase.name
        response.detail = (
            f'phase={phase}. {robot_stop}' if outcome.changed
            else f'멈출 작업이 없다(phase={phase}). {robot_stop}')
        level = ScanLog.LEVEL_INFO if self._robot_stop_client.service_is_ready() else ScanLog.LEVEL_WARN
        self.log(level, Reason.STOP_REQUESTED, f'작업 중지 접수: {response.detail}')
        return response

    # ---- /scan/set_config ----

    def _on_set_config(self, request, response):
        outcome = self.state_machine.request(Command.SET_CONFIG)
        values = conversions.config_values_from_msg(request.config)
        problems = () if not outcome.accepted else scan_params.check_values(values)
        if not outcome.accepted:
            response.reason_code, response.detail = int(outcome.reason), outcome.detail
        elif problems:
            response.reason_code, response.detail = int(Reason.INVALID_VALUE), '; '.join(problems)
        else:
            self._config.update(values)  # *_set 인 항목만. 다른 노드로의 전파(P01~P03)는 T19b
            response.success = True
            response.detail = '적용: ' + (', '.join(sorted(values)) or '없음')
        # applied 는 "적용 후 전체 값"이다. 모르는 값은 NaN + *_set=false 로 둔다(0 금지)
        response.applied = conversions.config_to_msg(self._effective_config())
        self.log(
            ScanLog.LEVEL_INFO if response.success else ScanLog.LEVEL_WARN, response.reason_code,
            f'SetConfig request_id={request.request_id}: {response.detail}')
        return response

    # ---- 종료 ----

    def close(self):
        """기다리는 스레드를 풀고, 큐에 남은 기록을 디스크에 쓴 뒤 쓰기 스레드를 닫는다."""
        self._closing.set()
        with self._status_cond:
            self._status_cond.notify_all()
        self._matcher.end()
        self._writer.shutdown(wait=True)

    def destroy_node(self):
        self.close()
        for server in self._action_servers:
            server.destroy()
        self._motion_client.destroy()
        return super().destroy_node()


class _NodePorts(Ports):
    """sequence.Ports 의 구현. 시퀀스 스레드(Action execute 콜백)에서만 불린다."""

    def __init__(self, node: ScanManager, job: _Job, recorded=True):
        self._node = node
        self._job = job
        self._params = job.params
        self._recorded = recorded   # result_store 에 이 작업의 기록이 있는가
        self.last_motion_id = 0
        self.last_result = None

    def stop_requested(self):
        return self._job.stop_event.is_set()

    def safety_reason_code(self):
        return self._node.safety_reason_code()

    def execute(self, motion_id, request):
        node, job, p = self._node, self._job, self._params
        self.last_motion_id = motion_id
        if not node._motion_client.wait_for_server(timeout_sec=p.server_wait_timeout_s):
            return MotionResult(available=False)
        node._matcher.begin(job.scan_id, motion_id, _EXPECTED_EVENT.get(request.operation))
        node.state_machine.set_motion_id(motion_id)
        try:
            goal = conversions.goal_from_request(request, job.scan_id, motion_id, p.motion_frame_id)
            sent = node._motion_client.send_goal_async(goal)
            if not node.wait_future(sent, p.server_wait_timeout_s):
                return MotionResult(available=False)
            handle = sent.result()
            if not handle.accepted:
                return MotionResult(accepted=False)
            with job.lock:
                job.motion_handle = handle
                stop_came_first = job.stop_event.is_set()
            if stop_came_first:
                handle.cancel_goal_async()  # /scan/stop 이 handle 을 받기 전에 왔다
            done = handle.get_result_async()
            # 제한 시간은 robot_manager 가 지킨다(REASON_TIMEOUT). 여기의 한도는 Result 가 끝내 안 올 때의 대비다.
            backstop = request.timeout_s + p.stop_confirm_timeout_s
            if not node.wait_future(done, backstop):
                handle.cancel_goal_async()
                return MotionResult(
                    reason=MotionReason.TIMEOUT, detail=f'{backstop:.1f} s 안에 Result 가 오지 않았다')
            self.last_result = conversions.motion_result_from_msg(done.result().result)
            return self.last_result
        finally:
            with job.lock:
                job.motion_handle = None
            node.state_machine.set_motion_id(0)

    def wait_event(self, event_id):
        event = self._node._matcher.wait(event_id, self._params.event_wait_timeout_s)
        if event is None:
            return None
        return MatchedEvent(conversions.position_of(event.pose), raw=event)

    def wait_still(self):
        return self._node.wait_still(self._params.stop_confirm_timeout_s)

    def tare(self):
        node, p = self._node, self._params
        if not node._tare_client.wait_for_service(timeout_sec=p.server_wait_timeout_s):
            return StepOutcome(False, int(Reason.TARE_FAILED), '/contact/tare 서버가 없다')
        # duration_s=0: contact_detector 의 파라미터 tare_duration_s 를 쓴다(계약 4.2절)
        future = node._tare_client.call_async(
            TareForce.Request(duration_s=0.0, scan_id=self._job.scan_id))
        if not node.wait_future(future, p.motion_timeout_s):
            return StepOutcome(False, int(Reason.TARE_TIMEOUT), '/contact/tare 응답이 없다')
        response = future.result()
        if not response.success:
            return StepOutcome(False, int(response.error), response.detail)
        node.log(
            ScanLog.LEVEL_INFO, Reason.OK,
            f'tare 완료: |F0|={response.baseline_norm_n:.3f} N, std={response.std_norm_n:.3f} N, '
            f'n={response.sample_count}')
        return StepOutcome(True)

    def _measurement(self, event, result):
        return Measurement(
            conversions.detection_from_event(event.raw), conversions.stop_pose_record(result.raw))

    def record_top(self, event, result, request):
        node, job = self._node, self._job
        node._write(node._store.record_top, job.scan_id, self._measurement(event, result))
        job.top = TopMeasurement(event.position, request.speed)
        node.log(ScanLog.LEVEL_INFO, Reason.OK, '윗면 접촉 확정 (판정 좌표)', event.position)

    def record_edge(self, direction, event, result, request):
        node, job = self._node, self._job
        node._write(
            node._store.record_edge, job.scan_id, direction, self._measurement(event, result))
        raw = event.raw
        job.edges[direction] = EdgeMeasurement(
            event.position, raw.z_drop_m if raw.z_drop_valid else None, request.speed)
        node.log(
            ScanLog.LEVEL_INFO, Reason.OK, f'{direction.name} 모서리 확정 (판정 좌표)', event.position)

    def record_attempt_failed(self, target, reason_code, detail, result):
        stop_pose = conversions.stop_pose_record(result.raw) if result.raw is not None else None
        self._node._write(
            self._node._store.record_attempt_failed, self._job.scan_id, target, reason_code, detail,
            stop_pose)

    def notify(self, signal):
        try:
            self._node.state_machine.notify(signal)
        except InvalidTransition:
            if self._node.state_machine.phase is Phase.STOPPING:
                return False  # 그 사이에 /scan/stop 이 접수됐다
            raise
        return True

    def compute_geometry(self):
        node, job = self._node, self._job
        output = compute_shape(
            job.top, job.edges, job.params, started_at=job.started_at,
            finished_at=node._now_stamp())
        # 원본 저장 → 발행 순서(계약 7.4절). 실패한 형상도 저장한다.
        node._write(node._store.save_result, job.scan_id, output.shape, output.bias_corrections)
        node._publish_result(job, output.shape)
        top = output.top_correction
        node.log(
            ScanLog.LEVEL_INFO if output.shape.success else ScanLog.LEVEL_ERROR,
            output.shape.reason_code,
            f'형상 계산 {"성공" if output.shape.success else "실패: " + output.shape.detail}. '
            f'윗면 보정 {top.correction_m} m (result_store 에는 방향별 보정만 남는다)')
        return StepOutcome(output.shape.success, output.shape.reason_code, output.shape.detail)

    def fail(self, reason_code, detail, position):
        """원인 · 단계 · 위치를 남기고 ERROR 로 보낸다(BRD 4.2.5). 홈 복귀는 하지 않는다."""
        node, job = self._node, self._job
        phase = node.state_machine.phase.name
        node.log(
            ScanLog.LEVEL_ERROR, reason_code, f'{phase} 실패: {detail} (정지 좌표)', position)
        node.state_machine.notify(Signal.FAILED, reason_code=reason_code, detail=detail)
        if self._recorded and job.scan_id:
            node._write(node._store.record_failure, job.scan_id, node.state_machine.failure)
        if job.result_msg is None and job.started_at is not None:
            node._publish_partial_result(job, reason_code, detail)

    def record_stop(self, position, result, during_final_homing):
        node, job = self._node, self._job
        with job.lock:
            before = job.stop_snapshot
        pose = None
        if result is not None and result.raw is not None:
            pose = conversions.stop_pose_record(result.raw)
        if self._recorded and job.scan_id and before is not None:
            node._write(node._store.record_stop, job.scan_id, Interruption(
                before.phase, before.direction, before.progress, pose=pose,
                during_final_homing=during_final_homing))
        node.log(ScanLog.LEVEL_INFO, Reason.STOP_REQUESTED, '정지 완료 확인 (정지 좌표)', position)

    def log_info(self, message, position=None):
        self._node.log(ScanLog.LEVEL_INFO, Reason.OK, message, position)


def main(args=None):
    node = executor = None
    try:
        try:
            rclpy.init(args=args)
            node = ScanManager()
            executor = MultiThreadedExecutor(
                num_threads=max(os.cpu_count() or 1, MIN_EXECUTOR_THREADS))
            executor.add_node(node)
            node.announce_ready()
            executor.spin()
        except (KeyboardInterrupt, ExternalShutdownException):
            pass
        finally:
            _shutdown_quietly(node, executor)
    except KeyboardInterrupt:
        pass  # 첫 SIGINT 를 처리하러 가는 사이에 온 두 번째 SIGINT


def _shutdown_quietly(node, executor):
    """정리하는 동안 SIGINT 가 또 와도(launch 의 Ctrl-C) 트레이스백 없이 끝낸다."""
    try:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    except ValueError:
        pass  # 메인 스레드가 아니다
    try:
        if node is not None:
            node.close()
        if executor is not None:
            executor.shutdown(timeout_sec=_SHUTDOWN_GRACE_S)
        if node is not None:
            node.destroy_node()
        rclpy.try_shutdown()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
