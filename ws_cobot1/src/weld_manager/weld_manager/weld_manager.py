"""weld_manager 노드 (phase 2). 기준: docs/phase2/weld-ros-interfaces.md 2 · 5 · 7장, weld-motion.md.

- 서버: /weld/run (RunWeld) · /weld/home (ReturnHome) · /weld/stop (StopWeld)
- 클라이언트: /robot/execute_motion (접근 · 후퇴 · 안전 높이 · 홈) · /robot/execute_path (경로) · /robot/stop
- 구독: /scan/state (배타) · /robot/status (연결 · 정지 확인) · /safety/status (래치) · /robot/sample (시작 때 위치 · 툴 등록)
- 발행: /weld/state (변경 시 + 주기) · /weld/result (끝날 때 한 번) · /weld/log (ScanLog 형식)

순서 · 판정 · 경로 계산은 순수 모듈(sequence · weld_path)에 있고, 이 파일은 그것을 ROS 에 잇기만 한다.
scan_manager 노드의 방식을 따랐다(코드는 가져오지 않았다):
- goal 은 항상 accept 하고, 거절 사유는 Result(success=false, reason_code)로 준다. ROS 2 의 reject 에는 사유가 없다.
- 중지는 /weld/stop 하나로 한다. RunWeld 의 Action 취소는 받지 않는다(정지 확인이 /weld/stop 에 묶여 있다).
- goal 을 보내기 직전의 중지 확인과 보내기는 작업 락 안에서 한다. 그 뒤에 온 중지는 goal 취소로 받는다.
- 정지 완료는 요청 뒤에 찍힌 /robot/status 의 connected && !moving 으로만 본다.
- 실행 중에는 파라미터 변경을 거절한다(시연 중 값 변경 금지).
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import math
import os
import signal
import threading
import time

import rclpy
from contact_scan_interfaces.action import ExecuteMotion
from contact_scan_interfaces.action import ExecutePath
from contact_scan_interfaces.action import ReturnHome
from contact_scan_interfaces.action import RunWeld
from contact_scan_interfaces.msg import RobotSample
from contact_scan_interfaces.msg import RobotStatus
from contact_scan_interfaces.msg import SafetyStatus
from contact_scan_interfaces.msg import ScanLog
from contact_scan_interfaces.msg import ScanState
from contact_scan_interfaces.msg import WeldResult
from contact_scan_interfaces.msg import WeldState
from contact_scan_interfaces.srv import StopRobot
from contact_scan_interfaces.srv import StopWeld
from contact_scan_qos import QOS_LOG
from contact_scan_qos import QOS_SENSOR
from contact_scan_qos import QOS_STATE
from rcl_interfaces.msg import SetParametersResult
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
from scan_manager.result_store import ResultStore
from scan_manager.result_store import Stamp

from . import conversions
from . import params as weld_params
from . import weld_record
from .contract_enums import MotionReason
from .contract_enums import Reason
from .contract_enums import WeldPhase
from .sequence import HomeRunner
from .sequence import MotionKind
from .sequence import MotionResult
from .sequence import OutcomeKind
from .sequence import Ports
from .sequence import RunOutcome
from .sequence import WeldRunner
from .state_machine import Command
from .state_machine import InvalidTransition
from .state_machine import Signal
from .state_machine import Snapshot
from .state_machine import WeldStateMachine
from .weld_path import line_range_problem
from .weld_path import load_scan
from .weld_path import NoScanResult
from .weld_path import PathRejected
from .weld_path import plan_weld
from .weld_record import Pose

MIN_EXECUTOR_THREADS = 6
_WAIT_SLICE_S = 0.1        # 기다리는 동안 종료 요청을 들여다보는 간격. 기다림의 한도는 파라미터다
_SHUTDOWN_GRACE_S = 5.0
_SCAN_REST = frozenset({ScanState.PHASE_IDLE, ScanState.PHASE_DONE, ScanState.PHASE_ERROR,
                        ScanState.PHASE_STOPPED})
_PARAM_TYPE = {
    weld_params.DOUBLE: Parameter.Type.DOUBLE,
    weld_params.DOUBLE_ARRAY: Parameter.Type.DOUBLE_ARRAY,
    weld_params.STRING: Parameter.Type.STRING,
}


class _Closing(Exception):
    """노드가 종료 중이다. 작업의 실패로 남기지 않는다."""


class _Job:
    def __init__(self, weld_id, scan_id, params, plan=None):
        self.weld_id = weld_id
        self.scan_id = scan_id
        self.params = params
        self.plan = plan
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.handle = None          # 진행 중인 goal (ExecuteMotion · ExecutePath)
        self.record = None          # 낸 WeldRecord
        self.record_msg = None
        self.goal_handle = None     # RunWeld goal (feedback 용)


def _age_s(now_ns: int, stamp) -> float:
    return (now_ns - (stamp.sec * 1_000_000_000 + stamp.nanosec)) / 1e9


class WeldManager(Node):

    def __init__(self, **kwargs):
        super().__init__('weld_manager', **kwargs)
        # 모션 수치에는 코드 예비값이 없다. 값이 없어도 기동하고, START 에서 거절한다(규칙 7)
        for spec in weld_params.SPECS:
            self.declare_parameter(spec.name, _PARAM_TYPE[spec.kind])

        self._closing = threading.Event()
        self._job = None
        self._job_lock = threading.Lock()
        self._status_cond = threading.Condition()
        self._scan_state = self._robot_status = self._safety_status = self._sample = None
        self._last_motion_id = 0        # 가장 최근 작업의 마지막 motion_id (안전복귀가 이어서 발급한다)
        self._last_z_safe = None        # 가장 최근 계획의 z_safe (Base). 안전복귀의 올림 높이
        self._writer = ThreadPoolExecutor(max_workers=1, thread_name_prefix='weld_record')
        self._state_seq = 0
        self._state_pub_lock = threading.Lock()

        self._state_pub = self.create_publisher(WeldState, '/weld/state', QOS_STATE)
        self._result_pub = self.create_publisher(WeldResult, '/weld/result', QOS_STATE)
        self._log_pub = self.create_publisher(ScanLog, '/weld/log', QOS_LOG)
        self.state_machine = WeldStateMachine(on_change=self._on_change)

        subs = MutuallyExclusiveCallbackGroup()       # 시퀀스가 기다리는 동안에도 항상 처리된다
        actions = ReentrantCallbackGroup()
        services = MutuallyExclusiveCallbackGroup()
        clients = ReentrantCallbackGroup()
        self.create_subscription(ScanState, '/scan/state', self._keep('_scan_state'), QOS_STATE,
                                 callback_group=subs)
        self.create_subscription(RobotStatus, '/robot/status', self._keep('_robot_status'), QOS_STATE,
                                 callback_group=subs)
        self.create_subscription(SafetyStatus, '/safety/status', self._keep('_safety_status'), QOS_STATE,
                                 callback_group=subs)
        self.create_subscription(RobotSample, '/robot/sample', self._keep('_sample'), QOS_SENSOR,
                                 callback_group=subs)
        self._motion_client = ActionClient(self, ExecuteMotion, '/robot/execute_motion', callback_group=clients)
        self._path_client = ActionClient(self, ExecutePath, '/robot/execute_path', callback_group=clients)
        self._robot_stop_client = self.create_client(StopRobot, '/robot/stop', callback_group=clients)
        self._action_servers = [
            ActionServer(self, action_type, name, execute_callback=execute, callback_group=actions,
                         goal_callback=lambda _goal: GoalResponse.ACCEPT,
                         cancel_callback=lambda _handle: CancelResponse.REJECT)
            for action_type, name, execute in (
                (RunWeld, '/weld/run', self._execute_run),
                (ReturnHome, '/weld/home', self._execute_home))]
        self.create_service(StopWeld, '/weld/stop', self._on_stop, callback_group=services)
        self.add_on_set_parameters_callback(self._on_set_parameters)

        period = self.get_parameter_or('state_publish_period_s').value
        self._state_timer = None
        if period is not None and period > 0.0:
            self._state_timer = self.create_timer(float(period), self._publish_state_periodic)
        else:
            # 주기 발행이 없으면 scan_manager 는 오래된 /weld/state 를 "용접 없음"으로 본다(안전한 쪽)
            self.get_logger().warning('state_publish_period_s 가 없어 /weld/state 를 변경 때만 발행한다')
        self._on_change(self.state_machine.snapshot())

    def announce_ready(self):
        missing = weld_params.check(self._parameter_values()).describe()
        self.get_logger().info(
            'weld_manager 준비: /weld/run · /weld/home · /weld/stop'
            + (f' (지금 값으로는 START 를 거절한다. {missing})' if missing else ''))

    # ---- 발행 ----

    def _now_msg(self):
        return self.get_clock().now().to_msg()

    def _now_stamp(self) -> Stamp:
        return Stamp(*self.get_clock().now().seconds_nanoseconds())

    def _shutting_down(self) -> bool:
        return self._closing.is_set() or not rclpy.ok(context=self.context)

    def _publish_quietly(self, publisher, build_msg) -> bool:
        if self._shutting_down():
            return False
        try:
            publisher.publish(build_msg())
        except Exception:
            if not self._shutting_down():
                raise
            return False
        return True

    def _on_change(self, snapshot: Snapshot):
        # 상태 기계의 락 안이다. 발행만 한다(파일 쓰기 · 대기 금지)
        with self._state_pub_lock:
            self._state_seq += 1
            msg = conversions.state_to_msg(snapshot, self._now_msg())
            self._publish_quietly(self._state_pub, lambda: msg)
        job = self._job
        if job is not None and job.goal_handle is not None and not self._shutting_down():
            try:
                job.goal_handle.publish_feedback(RunWeld.Feedback(state=msg))
            except Exception as exc:    # 피드백 실패로 작업을 멈추지 않는다
                self.get_logger().debug(f'RunWeld feedback 실패: {exc!r}')

    def _publish_state_periodic(self):
        seq = self._state_seq
        snapshot = self.state_machine.snapshot()
        with self._state_pub_lock:
            if seq == self._state_seq:     # 그 사이에 바뀌었으면 이미 발행됐다. 옛 상태로 덮지 않는다
                self._publish_quietly(self._state_pub,
                                      lambda: conversions.state_to_msg(snapshot, self._now_msg()))

    def log(self, level: str, code, message: str, position=None):
        snapshot = self.state_machine.snapshot()
        msg = ScanLog()
        msg.stamp = self._now_msg()
        msg.scan_id = snapshot.weld_id            # 2.1절: scan_id 자리에 weld_id
        msg.level = {'info': ScanLog.LEVEL_INFO, 'warn': ScanLog.LEVEL_WARN,
                     'error': ScanLog.LEVEL_ERROR}[level]
        msg.phase = int(snapshot.phase)           # WeldState.PHASE_*
        msg.direction = 0
        msg.motion_id = int(snapshot.motion_id)
        msg.code = int(code)
        msg.message = message
        if position is None:
            msg.pose, msg.pose_valid = conversions.nan_pose(), False
        else:
            msg.pose = conversions.pose_msg(position, (conversions.NAN,) * 4)
            msg.pose_valid, msg.frame_id = True, self._frame_id()
        self._publish_quietly(self._log_pub, lambda: msg)
        text = f'[{snapshot.phase.name} code={int(code)}] {message}'
        if level == 'error':
            self.get_logger().error(text)
        elif level == 'warn':
            self.get_logger().warning(text)
        else:
            self.get_logger().info(text)

    def _frame_id(self):
        return self.get_parameter_or('motion_frame_id').value or 'base_link'

    # ---- 구독 ----

    def _keep(self, attribute):
        def callback(msg):
            with self._status_cond:
                setattr(self, attribute, msg)
                self._status_cond.notify_all()
        return callback

    def safety_reason_code(self) -> int:
        with self._status_cond:
            safety = self._safety_status
        if safety is None or not safety.latched:
            return 0
        return int(safety.reason_code) or int(Reason.SAFETY_LATCHED)

    def _fresh_sample(self, timeout_s):
        """(샘플, 문제). 쓸 수 있는 최근 샘플이면 문제는 ''."""
        with self._status_cond:
            sample = self._sample
        if sample is None:
            return None, '/robot/sample 을 한 번도 받지 못했다'
        if not sample.valid:
            return None, '/robot/sample 이 valid=false 다'
        now_ns = self.get_clock().now().nanoseconds
        age = max(_age_s(now_ns, sample.pose_stamp), _age_s(now_ns, sample.force_stamp))
        if age > timeout_s:
            return None, f'/robot/sample 이 {age:.2f} s 전 것이다(> sample_timeout_s {timeout_s} s)'
        return sample, ''

    # ---- 기다림 ----

    def _wait(self, is_done, timeout_s, waiter) -> bool:
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
        done = threading.Event()
        future.add_done_callback(lambda _future: done.set())
        return self._wait(done.is_set, timeout_s, done.wait)

    def wait_still(self, timeout_s) -> bool:
        """요청 뒤에 찍힌 /robot/status 로 connected && !moving 을 확인한다(요청 전의 옛 moving=false 로 통과시키지 않는다)."""
        asked_at = self.get_clock().now().nanoseconds
        if asked_at <= 0:
            self.get_logger().error('ROS 시계가 0 이다(use_sim_time 인데 /clock 없음?). 정지를 확인할 수 없다')
            return False

        def still():
            status = self._robot_status
            if status is None or not status.connected or status.moving:
                return False
            return status.stamp.sec * 1_000_000_000 + status.stamp.nanosec > asked_at

        with self._status_cond:
            return self._wait(still, timeout_s, self._status_cond.wait)

    # ---- 파라미터 ----

    def _parameter_values(self) -> dict:
        values = {spec.name: self.get_parameter_or(spec.name).value for spec in weld_params.SPECS}
        for name, value in values.items():
            if value is not None and not isinstance(value, (str, float, int)):
                values[name] = list(value)      # 배열 파라미터가 array 형으로 와도 list 로 본다
        return values

    def _on_set_parameters(self, _params):
        if self.state_machine.is_busy:
            return SetParametersResult(
                successful=False, reason=f'용접 실행 중(phase={self.state_machine.phase.name})에는 바꾸지 않는다')
        return SetParametersResult(successful=True)

    # ---- /weld/run ----

    def _reject(self, goal_handle, result, reason_code, detail):
        """거절할 goal 을 끝내는 한 곳. phase 를 바꾸지 않고 Result(success=false, 1xx · 6xx · 3xx)로 끝낸다."""
        result.success = False
        result.reason_code = int(reason_code)
        result.detail = detail
        if hasattr(result, 'result'):
            result.result = conversions.blank_result_msg()
        if hasattr(result, 'final_pose'):
            result.final_pose = conversions.nan_pose()
        self.log('warn', reason_code, f'명령 거절: {detail}')
        goal_handle.abort()
        return result

    def _start_problem(self, request):
        """5.1절 시작 거절 표를 순서대로 본다. 문제면 (reason_code, detail), 통과면 (params, plan, weld_id)."""
        if self.state_machine.is_busy:
            return Reason.BUSY, f'phase={self.state_machine.phase.name}'
        base = weld_params.check(self._parameter_values())
        if not base.ok:         # yaml 이 비었다(표 밖, 노드 설정 문제)
            return Reason.INVALID_VALUE, f'weld_manager 파라미터: {base.describe()}'
        p = base.params
        now_ns = self.get_clock().now().nanoseconds
        with self._status_cond:
            scan, robot = self._scan_state, self._robot_status
        if scan is None:
            return Reason.INVALID_REQUEST, '/scan/state 를 받지 못했다(scan_manager 가 떠 있는가)'
        age = _age_s(now_ns, scan.stamp)
        if age > p.scan_state_timeout_s:
            return Reason.INVALID_REQUEST, f'/scan/state 가 {age:.1f} s 전 것이다(> {p.scan_state_timeout_s} s)'
        if scan.phase not in _SCAN_REST:
            return Reason.SCAN_ACTIVE, f'스캔 진행 중(scan phase={scan.phase})'
        latched = self.safety_reason_code()
        if latched:
            return Reason.SAFETY_LATCHED, f'안전 래치 중(reason_code={latched})'
        if robot is None or not robot.connected:
            return Reason.ROBOT_DISCONNECTED, '/robot/status 가 없거나 connected=false'
        try:
            store = ResultStore(os.path.expanduser(p.result_dir))
            scan_input = load_scan(store, request.scan_id, p.result_frame_id, p.motion_frame_id)
        except NoScanResult as error:
            return Reason.NO_SCAN_RESULT, str(error)
        problem = line_range_problem(request.start_line, request.end_line)
        if problem:
            return Reason.LINE_OUT_OF_RANGE, problem
        override = conversions.override_from_msg(request.config_override) if request.use_override else {}
        problems = weld_params.check_override(override)
        checked = weld_params.check(self._parameter_values(), override)
        if problems or not checked.ok:
            return Reason.INVALID_VALUE, 'config_override: ' + '; '.join(problems or checked.invalid)
        p = checked.params
        sample, why = self._fresh_sample(p.sample_timeout_s)
        if sample is None:
            return Reason.NO_SAMPLE, why
        if sample.frame_id != p.motion_frame_id:
            return Reason.NO_SAMPLE, f'/robot/sample 의 frame_id {sample.frame_id!r} 가 {p.motion_frame_id!r} 가 아니다'
        f = sample.wrench.force
        force = math.sqrt(f.x * f.x + f.y * f.y + f.z * f.z)
        if force > p.tool_check_max_force_n:
            return (Reason.TOOL_REG_SUSPECT,
                    f'무접촉 |F| {force:.2f} N > tool_check_max_force_n {p.tool_check_max_force_n} N '
                    '(툴 · TCP 등록이 빠졌는지 본다)')
        try:
            plan = plan_weld(scan_input, request.start_line, request.end_line, p)
        except PathRejected as error:
            return Reason.PATH_REJECTED, str(error)
        # 팁이 z_safe 아래여도 거절하지 않는다. 러너가 먼저 수직 상승한다(D30). 홈이라고 가정하지 않는다
        start_pose = Pose(conversions.position_of(sample.pose), conversions.orientation_of(sample.pose))
        return p, plan, weld_record.new_weld_id(datetime.now()), start_pose

    def _execute_run(self, goal_handle):
        request = goal_handle.request
        result = RunWeld.Result()
        checked = self._start_problem(request)
        if not isinstance(checked[0], weld_params.WeldParams):
            return self._reject(goal_handle, result, *checked)
        params, plan, weld_id, start_pose = checked
        job = _Job(weld_id, plan.scan_id, params, plan)
        with self._job_lock:
            if self.state_machine.is_busy:     # 검사와 접수 사이에 다른 명령이 들어왔다
                return self._reject(goal_handle, result, Reason.BUSY, f'phase={self.state_machine.phase.name}')
            job.goal_handle = goal_handle
            self._job = job
            outcome = self.state_machine.request(Command.START, weld_id=weld_id, scan_id=plan.scan_id)
            if not outcome.accepted:
                self._job = None
                return self._reject(goal_handle, result, outcome.reason, 'START 거절')
        self.log('info', Reason.OK,
                 f'용접 시작 request_id={request.request_id} scan_id={plan.scan_id} '
                 f'선 L{plan.start_line}~L{plan.end_line}')
        ports = _NodePorts(self, job)
        try:
            outcome = WeldRunner(ports, plan, params, weld_id, params.result_frame_id,
                                 params.orientation_tolerance_rad, start_pose).run()
        except _Closing:
            outcome = None
        except Exception as exc:
            outcome = self._internal_failure(exc)
        finally:
            self._last_motion_id = ports.last_motion_id
            self._last_z_safe = plan.z_safe_base
            self._end_job(job)
        result.weld_id = weld_id
        result.result = job.record_msg if job.record_msg is not None else conversions.blank_result_msg(
            weld_id, plan.scan_id)
        return self._finish_goal(goal_handle, result, outcome)

    def _finish_goal(self, goal_handle, result, outcome):
        if outcome is not None and outcome.kind is OutcomeKind.DONE:
            result.success = True
            goal_handle.succeed()
            return result
        result.success = False
        result.reason_code = int(outcome.reason_code) if outcome else int(Reason.CANCELED)
        result.detail = outcome.detail if outcome else 'weld_manager 종료'
        try:
            goal_handle.abort()
        except Exception:
            if outcome is not None:
                raise
        return result

    def _end_job(self, job):
        try:
            if not self._closing.is_set():
                self._writer.submit(lambda: None).result()   # 큐에 남은 쓰기를 끝낸 뒤 Result 를 준다
        except RuntimeError:
            pass
        with self._job_lock:
            if self._job is job:
                self._job = None

    def _internal_failure(self, exc):
        if self._shutting_down():
            return None
        detail = f'internal: {exc!r}'
        self.get_logger().error(detail)
        if self.state_machine.is_busy:
            try:
                self.state_machine.notify(Signal.FAILED, reason_code=int(Reason.ROBOT_ERROR), detail=detail)
            except InvalidTransition:
                pass
        return RunOutcome(OutcomeKind.FAILED, int(Reason.ROBOT_ERROR), detail)

    # ---- /weld/home ----

    def _execute_home(self, goal_handle):
        result = ReturnHome.Result()
        checked = weld_params.check(self._parameter_values())
        if not checked.ok:
            return self._reject(goal_handle, result, Reason.INVALID_VALUE, checked.describe())
        p = checked.params
        with self._status_cond:
            robot = self._robot_status
        if robot is None or not robot.connected:
            return self._reject(goal_handle, result, Reason.ROBOT_DISCONNECTED, '/robot/status 가 없거나 connected=false')
        sample, why = self._fresh_sample(p.sample_timeout_s)
        pose = None
        if sample is not None and sample.frame_id == p.motion_frame_id:
            pose = Pose(conversions.position_of(sample.pose), conversions.orientation_of(sample.pose))
        with self._job_lock:
            snapshot = self.state_machine.snapshot()
            job = _Job(snapshot.weld_id, snapshot.scan_id, p)
            self._job = job
            outcome = self.state_machine.request(Command.HOME)
            if not outcome.accepted:
                self._job = None
                return self._reject(goal_handle, result, outcome.reason, f'phase={snapshot.phase.name}')
        self.log('info', Reason.OK, f'안전복귀 시작 request_id={goal_handle.request.request_id}'
                 + ('' if pose is not None else f' (현재 자리를 모른다: {why})'))
        ports = _NodePorts(self, job)
        try:
            outcome = HomeRunner(ports, p, pose, self._last_z_safe, self._last_motion_id + 1).run()
        except _Closing:
            outcome = None
        except Exception as exc:
            outcome = self._internal_failure(exc)
        finally:
            self._last_motion_id = max(self._last_motion_id, ports.last_motion_id)
            self._end_job(job)
        final = ports.last_raw
        if final is not None and (final.pose_stamp.sec or final.pose_stamp.nanosec):
            result.final_pose, result.frame_id = final.pose, final.frame_id
        else:
            result.final_pose = conversions.nan_pose()
        return self._finish_goal(goal_handle, result, outcome)

    # ---- /weld/stop ----

    def _on_stop(self, request, response):
        """정지를 요청하고 접수만 돌려준다. 정지 확인 · 기록은 시퀀스 스레드가 한다. 다른 노드를 기다리지 않는다."""
        handle = None
        with self._job_lock:
            job = self._job
            if job is not None:
                with job.lock:
                    outcome = self.state_machine.request(Command.STOP)
                    if outcome.changed:
                        job.stop_event.set()
                        handle = job.handle
            else:
                outcome = self.state_machine.request(Command.STOP)
        sent = False
        if outcome.accepted:
            # 용접이 멈출 것이 있을 때만 로봇을 세운다. 휴지 중의 /weld/stop 이 스캔 모션을 멈추면 안 된다
            sent = self.request_robot_stop(request.request_id, request.reason or int(Reason.STOP_REQUESTED),
                                           request.detail)
            if handle is not None:
                handle.cancel_goal_async()
        response.accepted = outcome.accepted
        response.reason_code = int(outcome.reason)
        phase = outcome.state.phase.name
        if outcome.accepted:
            response.detail = f'phase={phase}. ' + ('/robot/stop 요청함' if sent else '/robot/stop 서버가 없다')
        else:
            response.detail = f'멈출 것이 없다(phase={phase})'
        self.log('info' if (sent or not outcome.accepted) else 'warn', Reason.STOP_REQUESTED,
                 f'용접 중지 접수: {response.detail}')
        return response

    def request_robot_stop(self, request_id, reason, detail) -> bool:
        if not self._robot_stop_client.service_is_ready():
            return False
        self._robot_stop_client.call_async(StopRobot.Request(
            request_id=request_id, requester=self.get_name(), reason=int(reason), detail=detail)
        ).add_done_callback(self._on_robot_stop_response)
        return True

    def _on_robot_stop_response(self, future):
        try:
            response = future.result()
        except Exception as exc:
            self.log('warn', Reason.ROBOT_ERROR, f'/robot/stop 호출 실패: {exc!r}')
            return
        if not response.accepted:
            self.log('warn', response.reason_code, f'/robot/stop 이 접수되지 않았다: {response.detail}')

    # ---- 종료 ----

    def close(self):
        self._closing.set()
        with self._status_cond:
            self._status_cond.notify_all()
        self._writer.shutdown(wait=True)

    def destroy_node(self):
        self.close()
        for server in self._action_servers:
            server.destroy()
        self._motion_client.destroy()
        self._path_client.destroy()
        return super().destroy_node()


class _NodePorts(Ports):
    """sequence.Ports 의 구현. 시퀀스 스레드(Action execute 콜백)에서만 불린다."""

    def __init__(self, node: WeldManager, job: _Job):
        self._node = node
        self._job = job
        self._p = job.params
        self.last_motion_id = 0
        self.last_raw = None        # 가장 최근에 받은 Result 원본 (안전복귀의 final_pose)

    def stop_requested(self):
        return self._job.stop_event.is_set()

    def safety_reason_code(self):
        return self._node.safety_reason_code()

    def execute(self, motion_id, request):
        node, job, p = self._node, self._job, self._p
        self.last_motion_id = motion_id
        path = request.kind is MotionKind.PATH
        client = node._path_client if path else node._motion_client
        node.state_machine.set_motion_id(motion_id)
        handle = None
        try:
            if not client.wait_for_server(timeout_sec=p.server_wait_timeout_s):
                return MotionResult(available=False)
            build = conversions.path_goal if path else conversions.motion_goal
            goal = build(request, job.weld_id, motion_id, p.motion_frame_id)
            feedback = self._progress(request) if path else None
            with job.lock:
                # 중지 확인과 보내기 사이에 온 /weld/stop 은 여기서 막는다. 그 뒤의 중지는 아래 cancel 이 받는다
                if job.stop_event.is_set():
                    return self._not_sent(request, '중지가 접수돼 goal 을 보내지 않았다')
                sent = client.send_goal_async(goal, feedback_callback=feedback)
            if not node.wait_future(sent, p.server_wait_timeout_s):
                sent.add_done_callback(_cancel_late_goal)          # 늦게 수락되면 아무도 모르는 모션이 돈다
                self._stop_untracked(f'{request.label}: goal 응답이 오지 않았다')
                return MotionResult(available=False)               # 움직였는지 모른다
            handle = sent.result()
            if not handle.accepted:
                return MotionResult(accepted=False)
            with job.lock:
                job.handle = handle
                stop_first = job.stop_event.is_set()
            if stop_first:
                handle.cancel_goal_async()
            done = handle.get_result_async()
            backstop = request.timeout_s + p.stop_confirm_timeout_s   # 제한 시간은 robot_manager 가 지킨다
            if not node.wait_future(done, backstop):
                handle.cancel_goal_async()
                self._stop_untracked(f'{request.label}: Result 가 오지 않았다')
                return MotionResult(reason=MotionReason.TIMEOUT, reason_code=int(Reason.TIMEOUT),
                                    detail=f'{backstop:.1f} s 안에 Result 가 오지 않았다')
            raw = done.result().result
            handle = None
            self.last_raw = raw
            stamped = bool(raw.pose_stamp.sec or raw.pose_stamp.nanosec)
            if stamped and raw.frame_id != p.motion_frame_id:
                return MotionResult(reason=MotionReason.ROBOT_ERROR, reason_code=int(Reason.ROBOT_ERROR),
                                    detail=f'Result.frame_id={raw.frame_id!r} 가 {p.motion_frame_id!r} 가 아니다')
            return conversions.motion_result_from_msg(raw)
        except BaseException:
            if handle is not None:
                handle.cancel_goal_async()          # 수락된 모션을 두고 빠져나가지 않는다(종료 중 포함)
            raise
        finally:
            with job.lock:
                job.handle = None
            node.state_machine.set_motion_id(0)

    def _not_sent(self, request, detail):
        """보내지 않은 goal. 로봇은 그 자리다 — 지금 샘플이 정지 자리다."""
        sample, _ = self._node._fresh_sample(self._p.sample_timeout_s)
        position = orientation = None
        if sample is not None:
            position = conversions.position_of(sample.pose)
            orientation = conversions.orientation_of(sample.pose)
        return MotionResult(reason=MotionReason.STOP_REQUESTED, reason_code=int(Reason.STOP_REQUESTED),
                            detail=f'{request.label}: {detail}', position=position, orientation=orientation)

    def _progress(self, request):
        length = request.path_length_m or 0.0
        state_machine = self._node.state_machine

        def on_feedback(message):
            if length > 0.0:
                state_machine.set_progress(message.feedback.distance_travelled / length)
        return on_feedback

    def _stop_untracked(self, detail):
        sent = self._node.request_robot_stop(f'weld_manager-{self._job.weld_id}', int(Reason.ROBOT_ERROR), detail)
        self._node.log('warn', Reason.ROBOT_ERROR, f'{detail}. /robot/stop {"요청함" if sent else "서버가 없다"}')

    def notify(self, signal, **kwargs):
        try:
            self._node.state_machine.notify(signal, **kwargs)
            return True
        except InvalidTransition:
            if self._node.state_machine.phase is WeldPhase.STOPPING:
                return False          # 중지가 먼저 접수됐다 → 러너는 중지로 간다
            raise

    def wait_still(self):
        return self._node.wait_still(self._p.stop_confirm_timeout_s)

    def now(self):
        return self._node._now_stamp()

    def save_result(self, record):
        node, job = self._node, self._job
        try:
            path = node._writer.submit(weld_record.save, self._p.result_dir, record).result()
            node.log('info', record.reason_code, f'용접 결과 저장: {path}')
        except Exception as exc:     # 파일 실패로 결과 발행 · 복귀를 막지 않는다
            node.log('error', Reason.ROBOT_ERROR, f'용접 결과 파일 저장 실패: {exc!r}')
        job.record = record
        job.record_msg = conversions.record_to_msg(record, node._now_msg())
        node._publish_quietly(node._result_pub, lambda: job.record_msg)

    def log(self, level, message, position=None):
        self._node.log(level, Reason.OK, message, position)


def _cancel_late_goal(future):
    try:
        handle = future.result()
    except Exception:
        return
    if handle.accepted:
        handle.cancel_goal_async()


def main(args=None):
    node = executor = None
    try:
        try:
            rclpy.init(args=args)
            node = WeldManager()
            executor = MultiThreadedExecutor(num_threads=max(os.cpu_count() or 1, MIN_EXECUTOR_THREADS))
            executor.add_node(node)
            node.announce_ready()
            executor.spin()
        except (KeyboardInterrupt, ExternalShutdownException):
            pass
        finally:
            _shutdown_quietly(node, executor)
    except KeyboardInterrupt:
        _shutdown_quietly(node, executor)


def _shutdown_quietly(node, executor):
    try:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    except ValueError:
        pass
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
