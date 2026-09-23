"""scan_manager 노드 (T10 골격 + T19a 시퀀스 · 서버 · geometry 연결).

- 서버: /scan/run · /scan/home · /scan/resume (Action), /scan/stop · /scan/set_config (Service).
  노드가 뜨자마자 준비된다(mqtt_bridge 가 server_is_ready() 로 본다).
- 시퀀스는 /scan/run · /scan/resume 의 execute 콜백 안에서 돈다. 순서는 sequence.ScanRunner · ResumeRunner,
  이 파일은 그 Ports 를 구현한다.
- 작업 중지 · 안전복귀 · 재시작은 독립된 명령이다. /scan/stop 은 정지만 요청하고, 홈 복귀나 재시작을 부르지 않는다.
- 상태 기계의 on_change(락 안)에서는 /scan/state 발행과 쓰기 큐 투입만 한다. 디스크 쓰기는 전용 스레드 1개가 한다.
- 재시작(/scan/resume)은 기록(result_store)을 읽어 중단됐던 단계부터 잇는다. 판단은 resume.py, 순서는 sequence.ResumeRunner.
  프로세스가 재시작된 뒤에는 HOME · RESUME 이 올 때 기록의 휴지 상태(STOPPED · ERROR)를 상태 기계에 되돌린다.
- SetConfig 를 수락하면 다른 노드의 파라미터를 이름으로 갱신한다(계약 2.4 P01~P03). 무엇을 어디로 보내고
  부분 실패를 어떻게 알리는지는 propagation.py, 서비스 호출만 이 파일이 한다.

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
from contact_scan_interfaces.msg import RobotSample
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
from contact_scan_qos import QOS_SENSOR
from contact_scan_qos import QOS_STATE
from rcl_interfaces.msg import Parameter as ParameterMsg
from rcl_interfaces.msg import ParameterType
from rcl_interfaces.msg import ParameterValue
from rcl_interfaces.srv import GetParameters
from rcl_interfaces.srv import SetParameters
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
from . import propagation
from . import resume as scan_resume
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
from .result_store import ResultAlreadySaved
from .result_store import ResultStore
from .result_store import ResultStoreError
from .result_store import Stamp
from .result_store.records import CONFIG_FIELDS
from .sequence import damage_suspect_reason as _damage_suspect_reason
from .sequence import MatchedEvent
from .sequence import MotionPlanner
from .sequence import MotionResult
from .sequence import OutcomeKind
from .sequence import Ports
from .sequence import ResumeRunner
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
from .state_machine import status_stale

# 설계 출발값. 실제 값은 contact_scan_bringup/config/*.yaml 에 둔다.
DEFAULT_STATE_PUBLISH_PERIOD_S = 1.0

# 아래 셋은 구조에서 나오는 값이지 튜닝 값이 아니다.
# 동시에 막힐 수 있는 콜백: 시퀀스(execute) 1 + 거절로 바로 끝나는 goal 1 + 구독 1 + /scan/stop 1
#   + 전파를 기다리는 /scan/set_config 1 + 기동 뒤 되읽기 타이머 1. 상대가 꺼져 있을 때 뒤의 둘이
#   몇 초씩 스레드를 차지하므로, 그동안에도 응답을 받을 스레드가 남아야 한다.
MIN_EXECUTOR_THREADS = 6
# 기동 뒤 되읽기를 **executor 가 돌기 시작한 다음에** 한 번 돌리기 위한 타이머 주기.
# 상대 노드를 찾을 때까지 기다리는 것은 이 값이 아니라 server_wait_timeout_s 다(_read_peers).
STARTUP_READ_DELAY_S = 0.5
# 기다리는 동안 종료 요청을 들여다보는 간격(s). 기다림의 한도는 전부 파라미터다.
_WAIT_SLICE_S = 0.1
# ScanConfig.debounce_n 이 uint8 이라는 사실. 메시지 정의에서 나오는 값이다.
_UINT8_MAX = 255
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


def _parameter_value(item) -> ParameterValue:
    """propagation.Item → rcl_interfaces ParameterValue. 상대 노드가 선언한 형과 맞아야 수락된다."""
    if item.integer:
        return ParameterValue(type=ParameterType.PARAMETER_INTEGER, integer_value=int(item.value))
    return ParameterValue(type=ParameterType.PARAMETER_DOUBLE, double_value=float(item.value))


def _plain_value(value: ParameterValue):
    """GetParameters 의 한 칸 → 파이썬 값. 선언만 되고 값이 없는 칸(NOT_SET)은 None 이다."""
    if value.type == ParameterType.PARAMETER_DOUBLE:
        return value.double_value
    if value.type == ParameterType.PARAMETER_INTEGER:
        return value.integer_value
    return None


class _Closing(Exception):
    """노드가 종료 중이다. 기다리던 시퀀스 스레드를 빠져나오게 한다."""


class _Job:
    """진행 중인 명령 하나(/scan/run · /scan/resume · /scan/home)의 문맥."""

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
        # 설정 락. SetConfig 의 접수 · 전파 · 되읽기 전체와 START 의 설정 확정을 서로 배제한다.
        # 락 순서는 _config_lock → _job_lock 이다. /scan/stop 은 _job_lock 만 잡으므로
        # 전파가 몇 초 걸려도 정지 요청은 기다리지 않는다(규칙 3: 정지는 독립된 명령이다).
        self._config_lock = threading.Lock()
        self._config = {name: None for name, _flag in CONFIG_FIELDS}  # SetConfig 로 받은 값
        # 다른 노드에서 **읽어 온** 실제 값. {노드: {파라미터 이름: 값}}. 읽지 못한 칸은 없다(0 을 넣지 않는다).
        self._peer_config = {}
        self._last_motion_id = {}                                     # scan_id → 마지막 motion_id
        # 작업의 기록에 남기지 못한 안전복귀가 있었다(기록을 읽지 못해 어느 작업인지 몰랐다 · 쓰기 실패).
        # 다음 START 까지 재시작을 받지 않는다: 기록은 "복귀한 적 없음"인데 로봇은 홈에 있을 수 있다.
        # 기록할 작업이 확실히 없던 복귀(새 시스템 · 가장 최근 작업이 DONE)에는 세우지 않는다.
        self._unrecorded_home = False
        self._status_cond = threading.Condition()
        self._robot_status = None
        # /robot/sample 의 마지막 유효 pose (위치, 자세, pose_stamp). 안전복귀의 올림에 쓴다(계약 7.5)
        self._robot_pose = None
        self._safety_status = None
        self._store = None
        self._store_dir = None
        self._begun = None
        self._begin_args = None
        self._begin_future = None
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
        # 안전복귀(계약 7.5)가 "지금 위치를 아는가"를 묻는다. 측정에는 쓰지 않는다 —
        # 측정값의 출처는 판정 좌표(ContactEvent)다
        self.create_subscription(
            RobotSample, '/robot/sample', self._on_robot_sample, QOS_SENSOR, callback_group=subs)
        self.create_subscription(
            SafetyStatus, '/safety/status', self._on_safety_status, QOS_STATE, callback_group=subs)
        self.create_subscription(
            ContactEvent, '/contact/event', self._matcher.offer, QOS_EVENT, callback_group=subs)
        self._motion_client = ActionClient(
            self, ExecuteMotion, '/robot/execute_motion', callback_group=clients)
        self._tare_client = self.create_client(TareForce, '/contact/tare', callback_group=clients)
        self._robot_stop_client = self.create_client(
            StopRobot, '/robot/stop', callback_group=clients)
        # 전파(계약 2.4 P01~P03). 표준 인터페이스라 자체 정의가 없다. clients 그룹에 둔다 —
        # 서비스 콜백(services, MutuallyExclusive)이 응답을 기다려도 다른 스레드가 응답을 처리한다.
        self._param_clients = {
            node: (
                self.create_client(
                    SetParameters, f'/{node}/set_parameters', callback_group=clients),
                self.create_client(
                    GetParameters, f'/{node}/get_parameters', callback_group=clients))
            for node, _items in propagation.TARGETS}
        # 기동 뒤 1회 되읽기용. 기다리는 동안 상태 발행 타이머가 멈추지 않게 전용 그룹에 둔다.
        self._startup_group = MutuallyExclusiveCallbackGroup()
        self._startup_read_timer = None
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
        # 전파(P01~P03)는 상대 노드의 응답을 기다린다. services 와 같은 그룹에 두면 그동안
        # /scan/stop 이 아예 돌지 못한다. 그래서 SetConfig 만 따로 둔다.
        self.create_service(
            SetConfig, '/scan/set_config', self._on_set_config,
            callback_group=MutuallyExclusiveCallbackGroup())

        # 최신성 점검은 발행 주기에 얹는다(타이머 · 파라미터를 새로 만들지 않는다).
        self._status_stale = {'/safety/status': False, '/robot/status': False}
        self._state_timer = self.create_timer(period, self._on_state_timer)
        self._on_change(self.state_machine.snapshot())

    def announce_ready(self):
        """executor 에 올린 뒤에 부른다(그때부터 서버가 응답한다)."""
        missing = scan_params.check(self._parameter_values()).describe()
        self.get_logger().info(
            'scan_manager 준비: /scan/run · /scan/home · /scan/resume · /scan/stop · /scan/set_config'
            + (f' (지금 값으로는 START 를 거절한다. {missing})' if missing else ''))
        # 다른 노드의 계약 파라미터를 1회 읽어 둔다. 기다리면 executor 가 아직 안 도니 응답이 오지 않는다 —
        # 한 번만 도는 타이머에 맡긴다. 못 읽어도 START 는 막지 않는다(그때 다시 읽는다).
        self._startup_read_timer = self.create_timer(
            STARTUP_READ_DELAY_S, self._read_peers_once, callback_group=self._startup_group)

    def _read_peers_once(self):
        if self._startup_read_timer is not None:
            self._startup_read_timer.cancel()
        try:
            with self._config_lock:   # SetConfig 의 되읽기가 쓴 값을 옛 값으로 되덮지 않는다
                self._refresh_peers('기동 뒤 되읽기')
        except _Closing:
            pass                      # 종료 중이다. 알릴 것이 없다
        except Exception as exc:      # 되읽기 실패로 노드가 죽지 않게 한다. START 직전에 다시 읽는다
            self.get_logger().warn(f'기동 뒤 되읽기 실패: {exc!r}')

    # ---- 발행 ----

    def _now_msg(self):
        return self.get_clock().now().to_msg()

    def _now_stamp(self) -> Stamp:
        return Stamp(*self.get_clock().now().seconds_nanoseconds())

    def _shutting_down(self) -> bool:
        """종료 중인가. context 가 내려간 뒤의 발행은 RCLError 를 낸다.

        _closing 만 보면 늦다: SIGINT 는 rclpy 의 처리기가 context 를 먼저 내리고, close() 는 그 뒤에 불린다.
        그 사이에 마지막 상태 전이(STOPPED · ERROR)가 일어나면 /scan/state 발행이 터진다.
        """
        return self._closing.is_set() or not rclpy.ok(context=self.context)

    def _publish_quietly(self, publisher, build_msg) -> bool:
        """종료 중이 아닐 때만 발행한다. 발행했으면 True.

        검사와 발행 사이에 context 가 내려가는 창이 있다. 그때 난 예외는 삼키고, 종료와 무관한 발행 실패는
        그대로 올린다(조용한 종료가 평소의 발행 실패까지 덮지 않게 한다).
        """
        if self._shutting_down():
            return False
        try:
            publisher.publish(build_msg())
        except Exception:
            if not self._shutting_down():
                raise
            return False
        return True

    def _publish_state(self, snapshot: Snapshot):
        with self._state_pub_lock:
            self._state_seq += 1
            self._publish_quietly(self._state_pub, lambda: to_msg(snapshot, self._now_msg()))

    def _on_state_timer(self):
        self._publish_state_periodic()
        self._watch_status_freshness()

    def _publish_state_periodic(self):
        # 스냅숏을 뜬 뒤에 상태가 바뀌었으면 그 변경이 이미 발행됐다. 옛 상태로 덮어쓰지 않는다.
        seq = self._state_seq
        snapshot = self.state_machine.snapshot()
        with self._state_pub_lock:
            if seq == self._state_seq:
                self._publish_quietly(self._state_pub, lambda: to_msg(snapshot, self._now_msg()))

    def _on_change(self, snapshot: Snapshot):
        # 상태 기계의 락 안이다. 발행하고 큐에 넣기만 한다(디스크 쓰기 · 대기 금지).
        self._publish_state(snapshot)
        if not snapshot.scan_id or self._store is None or self._closing.is_set():
            return
        try:
            if snapshot.scan_id != self._begun:
                if self._begin_args is None:
                    return  # 이 노드가 시작하지 않은 작업(기록이 없다)
                self._begun = snapshot.scan_id
                job = self._begin_future = self._writer.submit(
                    self._store.begin_scan, snapshot.scan_id, state=snapshot, **self._begin_args)
                self._begin_args = None
            else:
                job = self._writer.submit(self._store.record_state, snapshot)
        except RuntimeError:
            return  # 종료 중이라 쓰기 스레드가 이미 닫혔다. 상태 기계의 호출자에게 예외를 넘기지 않는다
        job.add_done_callback(self._log_write_error)

    def _log_write_error(self, job):
        if job.exception() is not None:
            self.get_logger().error(f'result_store 쓰기 실패: {job.exception()!r}')

    def _write(self, method, *args, **kwargs):
        """다음 단계로 가기 전에 디스크에 있어야 하는 기록. 쓰기 스레드에 맡기고 끝을 기다린다."""
        if self._closing.is_set():
            raise _Closing()  # 종료 중의 기록 실패를 작업의 실패로 남기지 않는다
        try:
            return self._writer.submit(method, *args, **kwargs).result()
        except RuntimeError as exc:
            if self._closing.is_set():
                raise _Closing() from exc
            raise

    def log(self, level, code, message, pose=None, frame_id=''):
        """/scan/log + 노드 로그. 상태 기계의 락 안(on_change)에서 부르지 않는다.

        pose: 관련 좌표의 원본(ContactEvent.pose · ExecuteMotion.Result.pose). 없으면 NaN + pose_valid=false.
        """
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
        msg.pose_valid = pose is not None
        if pose is not None:
            msg.pose = pose
            msg.frame_id = frame_id
        else:
            nan = conversions.NAN
            p, q = msg.pose.position, msg.pose.orientation
            p.x = p.y = p.z = q.x = q.y = q.z = q.w = nan  # 재지 않은 값에 기본 자세 (0, 0, 0, 1) 을 남기지 않는다
        self._publish_quietly(self._log_pub, lambda: msg)
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
            f'type={event.type} (판정 좌표)', event.pose, event.frame_id)

    # ---- 구독 ----

    def _on_robot_status(self, msg):
        with self._status_cond:
            self._robot_status = msg
            self._status_cond.notify_all()

    def _on_robot_sample(self, msg):
        """마지막 유효 pose 만 들고 있는다(계약 7.5). 무효 샘플은 버린다 — pose 가 NaN 이다."""
        if not msg.valid:
            return
        with self._status_cond:
            self._robot_pose = (
                conversions.position_of(msg.pose),
                (msg.pose.orientation.x, msg.pose.orientation.y,
                 msg.pose.orientation.z, msg.pose.orientation.w),
                msg.pose_stamp)

    def current_pose(self, max_age_s):
        """안전복귀가 쓸 (위치, 자세). 모르면 None (계약 7.5 ①).

        나이는 수신 시각이 아니라 pose_stamp 로 잰다. /robot/sample 은 SENSOR QoS 라 늦게 붙은
        구독자에게 옛 샘플이 다시 오지는 않지만, robot_manager 가 살아 있으면서 조회만 막힌 동안
        마지막 샘플이 그대로 남는다. 시계가 0 이면(use_sim_time 인데 /clock 없음) 잴 수 없으니
        모르는 것으로 본다 — wait_still() 과 같은 관례다.
        """
        with self._status_cond:
            latest = self._robot_pose
        if latest is None:
            return None
        position, orientation, stamp = latest
        now_ns = self.get_clock().now().nanoseconds
        if now_ns <= 0 or not (stamp.sec or stamp.nanosec):
            return None
        age_s = (now_ns - (stamp.sec * 1_000_000_000 + stamp.nanosec)) / 1e9
        if age_s > max_age_s:
            self.get_logger().warn(
                f'마지막 유효 TCP pose 가 {age_s:.2f} s 전이다(한도 {max_age_s:.2f} s). '
                f'지금 위치를 모르는 것으로 본다')
            return None
        return position, orientation

    def _on_safety_status(self, msg):
        with self._status_cond:
            self._safety_status = msg

    def _status_age_s(self, msg, now_ns):
        """상태 메시지의 stamp 가 지난 시간(s). 잴 수 없으면 None.

        수신 시각이 아니라 stamp 를 쓴다. TRANSIENT_LOCAL 이라 **발행자 프로세스가 살아 있는 한**
        늦게 붙은 구독자도 마지막 샘플을 받는다 — 발행이 멈춘 채 프로세스만 살아 있으면 옛 샘플을
        "방금" 받게 되고, 수신 시각으로는 그것을 거를 수 없다(이슈 #120).
        시계가 0 이면(use_sim_time 인데 /clock 이 없다) 잴 수 없다 — wait_still() 과 같은 관례다.
        """
        if now_ns <= 0:
            return None
        return (now_ns - (msg.stamp.sec * 1_000_000_000 + msg.stamp.nanosec)) / 1e9

    def _timeout_param(self, name):
        """끊김 한도 파라미터. 없거나 0 이하면 None 이고, 그러면 최신성을 판정할 수 없다."""
        value = self.get_parameter_or(name).value
        return None if value is None or scan_params.positive(value) else float(value)

    def conditions(self) -> Conditions:
        """명령 시점의 보호 조건. 아직 받지 못한 것은 None 이고 거절 사유가 된다.

        최신성은 **재기만** 한다. 한계 시간과 비교해 거절하는 규칙은 상태 기계(status_stale)에 있다.
        """
        now_ns = self.get_clock().now().nanoseconds
        with self._status_cond:
            robot, safety = self._robot_status, self._safety_status
        return Conditions(
            robot_connected=None if robot is None else bool(robot.connected),
            safety_latched=None if safety is None else bool(safety.latched),
            robot_status_age_s=None if robot is None else self._status_age_s(robot, now_ns),
            safety_status_age_s=None if safety is None else self._status_age_s(safety, now_ns),
            robot_status_timeout_s=self._timeout_param('robot_status_timeout_s'),
            safety_status_timeout_s=self._timeout_param('safety_status_timeout_s'))

    def _watch_status_freshness(self):
        """끊김 · 회복을 각각 한 번씩 알린다. 막지는 않는다(이슈 #120).

        관문은 START 를 누른 뒤에야 알려 준다. 오늘 사고는 **아무도 모른 채 한 시간이 지난 것**이라
        주기 점검으로 먼저 알린다. 한 번도 받지 못한 토픽은 여기서 알리지 않는다(기동 직후의 정상 상태다).
        """
        conditions = self.conditions()
        watched = (
            ('/safety/status', conditions.safety_latched is not None, Reason.SAFETY_LATCHED,
             status_stale('/safety/status', 'safety_status_timeout_s',
                          conditions.safety_status_age_s, conditions.safety_status_timeout_s),
             'START · 재시작을 거절한다'),
            ('/robot/status', conditions.robot_connected is not None, Reason.ROBOT_DISCONNECTED,
             status_stale('/robot/status', 'robot_status_timeout_s',
                          conditions.robot_status_age_s, conditions.robot_status_timeout_s),
             'START · 재시작 · 안전복귀를 거절한다'),
        )
        for topic, received, code, stale, effect in watched:
            if not received or bool(stale) == self._status_stale[topic]:
                continue  # 한 번도 못 받았거나, 이미 알린 상태 그대로다. 되풀이하지 않는다
            self._status_stale[topic] = bool(stale)
            if stale:
                self.log(ScanLog.LEVEL_WARN, code, f'{stale}. {effect}')
            else:
                self.log(ScanLog.LEVEL_INFO, Reason.OK, f'{topic} 수신 회복')

    def safety_reason_code(self) -> int:
        with self._status_cond:
            safety = self._safety_status
        if safety is None or not safety.latched:
            return 0
        return int(safety.reason_code) or int(Reason.SAFETY_LATCHED)  # 래치 중이면 0 이 아닌 코드

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

    # ---- 파라미터 · 설정 ----

    def _parameter_values(self) -> dict:
        values = {
            spec.name: self.get_parameter_or(spec.name).value for spec in scan_params.SPECS}
        for name, value in values.items():
            if value is not None and not isinstance(value, (str, float, int)):
                values[name] = list(value)  # 배열 파라미터가 array 형으로 와도 list 로 본다
        values['direction_order'] = list(self._direction_order)
        return values

    def _effective_config(self, override=None) -> dict:
        """ScanConfig 12개의 현재 값. 모르는 값은 None 이다(0 을 채우지 않는다. 규칙 4).

        - 자기 모션 6개: yaml ← SetConfig ← override.
        - 다른 노드 6개: **그 노드에서 읽어 온 실제 값**(`_peer_config`). 요청값이 아니다 — 전파가 거절됐거나
          읽지 못했으면 None 으로 둔다. 같은 값이어야 하는 쌍이 어긋나 있으면 대표값이 없으므로 None 이다
          (propagation.applied_from_readback).
        """
        config = {name: None for name, _flag in CONFIG_FIELDS}
        config.update(propagation.applied_from_readback(self._peer_config))
        for name in scan_params.MOTION_CONFIG_NAMES:
            config[name] = self.get_parameter_or(name).value
        for source in (self._config, override or {}):
            config.update({
                k: v for k, v in source.items()
                if v is not None and k in scan_params.MOTION_CONFIG_NAMES})
        return config

    # ---- 전파 (계약 2.4 P01~P03) ----

    def _peer_timeout(self):
        """상대 노드를 기다리는 한도. 없으면 None 이다(기다리지 않는다. CLAUDE.md 규칙 7: 예비값 없음)."""
        value = self.get_parameter_or('server_wait_timeout_s').value
        return value if isinstance(value, (int, float)) and value > 0 else None

    def _wait_for_peer(self, client, timeout_s) -> bool:
        """서버가 뜰 때까지 기다린다. rclpy 의 wait_for_service 와 달리 **종료 요청을 본다.**"""
        return self._wait(client.service_is_ready, timeout_s, time.sleep)

    def _propagate(self, plans) -> dict:
        """계획을 순서대로 보낸다. {노드: propagation.NodeResult}.

        보내는 순서는 propagation.TARGETS 가 정한다(감시 쪽 먼저). 실패한 노드가 있어도 **되돌리지 않고**
        남은 노드를 계속 보낸다 — 중간에 멈추면 어긋난 조합이 더 늘어난다.
        한 노드를 기다리는 한도는 server_wait_timeout_s 다. 응답을 받는 것은 clients 그룹의 다른 스레드다.
        """
        timeout_s = self._peer_timeout()
        if timeout_s is None:
            return {
                node_plan.node: propagation.NodeResult(
                    node_plan.node, False,
                    'server_wait_timeout_s 가 없어 상대를 기다릴 한도를 모른다. yaml 을 확인한다')
                for node_plan in plans}
        results = {}
        for node_plan in plans:
            client = self._param_clients[node_plan.node][0]
            if not self._wait_for_peer(client, timeout_s):
                results[node_plan.node] = propagation.NodeResult(
                    node_plan.node, False, f'/{node_plan.node}/set_parameters 가 없다(미기동)')
                continue
            request = SetParameters.Request(parameters=[
                ParameterMsg(name=item.param_name, value=_parameter_value(item))
                for item in node_plan.items])
            future = client.call_async(request)
            if not self.wait_future(future, timeout_s):
                results[node_plan.node] = propagation.NodeResult(
                    node_plan.node, False, f'{timeout_s:.1f} s 안에 응답이 없다')
                continue
            refused = [
                f'{item.param_name}: {result.reason or "거절"}'
                for item, result in zip(node_plan.items, future.result().results)
                if not result.successful]
            results[node_plan.node] = propagation.NodeResult(
                node_plan.node, not refused, '; '.join(refused))
        return results

    def _read_peers(self) -> dict:
        """세 노드에서 계약 파라미터를 읽어 {노드: {이름: 값}} 으로. 읽지 못한 칸은 넣지 않는다.

        전파한 적이 없어도 그 노드의 yaml 값이 **실제 값**이다. 그것을 읽어야 applied · ScanResult.config 의
        빈칸이 사실로 찬다. 읽지 못하면 그 칸은 NaN + *_set=false 로 남는다(측정은 그 값 없이도 된다).
        """
        timeout_s = self._peer_timeout()
        if timeout_s is None:
            return {}   # 기다릴 한도를 모른다. 못 읽은 것으로 둔다(START 는 필수값 검사에서 걸린다)
        readback = {}
        for node, _items in propagation.TARGETS:
            names = propagation.read_names(node)
            client = self._param_clients[node][1]
            if not self._wait_for_peer(client, timeout_s):
                continue
            future = client.call_async(GetParameters.Request(names=list(names)))
            if not self.wait_future(future, timeout_s):
                continue
            values = future.result().values
            readback[node] = {
                name: value
                for name, value in zip(names, (_plain_value(v) for v in values))
                if value is not None and self._reportable(node, name, value)}
        return readback

    def _reportable(self, node, name, value) -> bool:
        """ScanConfig 에 실을 수 있는 값인가. 실을 수 없으면 "못 읽음"으로 두고 알린다.

        debounce_n 은 uint8 이라 0~255 밖의 값은 메시지에 담기지 않는다(담으려 하면 예외가 난다).
        그 노드에 그런 값이 들어가 있으면 응답을 잃는 대신 그 칸만 비운다.
        """
        if name not in propagation.INTEGER_CONFIG or 0 <= value <= _UINT8_MAX:
            return True
        self.get_logger().warn(
            f'{node}.{name} = {value} 는 ScanConfig 의 uint8 범위 밖이다. 그 칸을 비운다')
        return False

    def _refresh_peers(self, why) -> dict:
        """_read_peers 를 돌려 _peer_config 를 갱신한다. 못 읽은 칸은 WARN 으로만 알린다."""
        self._peer_config = self._read_peers()
        missing = propagation.unread_names(self._peer_config)
        if missing:
            self.get_logger().warn(
                f'{why}: 다른 노드의 값을 읽지 못했다 ({", ".join(missing)}). '
                'ScanConfig 의 그 칸은 NaN + *_set=false 로 남는다')
        return self._peer_config

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
        if hasattr(result, 'result'):
            result.result = conversions.blank_result_msg()   # 재지 않은 값에 0 을 남기지 않는다
        if hasattr(result, 'final_pose'):
            result.final_pose = conversions.nan_pose()
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
        ports = _NodePorts(self, job)

        def run():
            # 기록을 만들지 못하면(디스크 오류 등) 로봇을 움직이기 전에 끝낸다
            self._begin_future.result()
            return ScanRunner(MotionPlanner(job.params), ports, job.params.direction_order).run()
        return self._run_job(goal_handle, result, job, ports, run)

    def _run_job(self, goal_handle, result, job, ports, run):
        """접수된 작업(새 작업 · 재시작)을 돌리고 Result 를 채운다. 두 Result 의 규칙은 같다(계약 5.1 · 5.3절)."""
        try:
            outcome = run()
            if job.result_msg is None:
                # 측정이 끝나기 전에 끝난 작업(중단). 실패는 fail() 이 이미 발행했다
                self._publish_partial_result(job, outcome.reason_code, outcome.detail)
        except _Closing:
            outcome = None
        except Exception as exc:  # 기록 실패 등. 모션은 동기로 기다리므로 이 시점에 진행 중인 모션은 없다
            # 종료가 깨운 예외면 None(= _Closing 과 같다)
            outcome = self._internal_failure(job, exc, ports=ports)
        finally:
            # 예외로 끝나도 남긴다. 같은 작업의 안전복귀 · 재시작이 motion_id 를 이어서 발급한다(계약 6.2절).
            # 모션 없이 끝난 재시작(last_motion_id = 0)이 앞선 번호를 지우지 않게 큰 쪽을 둔다.
            self._last_motion_id[job.scan_id] = max(
                ports.last_motion_id, self._last_motion_id.get(job.scan_id, 0))
            self._end_job(job)

        result.scan_id = job.scan_id
        result.result = job.result_msg if job.result_msg is not None else conversions.blank_result_msg()
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
        """START 를 접수한다. 거절이면 (reason_code, detail), 접수면 _Job.

        _config_lock 을 먼저 잡는다: 전파가 도는 중이면 끝난 값으로 시작한다(반쯤 전파된 값으로 재지 않는다).
        락 순서는 _config_lock → _job_lock 으로 고정이다(SetConfig 와 같다).

        **다른 노드를 기다리는 되읽기는 _job_lock 을 잡기 전에 끝낸다.** /scan/stop 은 _job_lock 만
        잡으므로, 상대 노드가 꺼져 있어 되읽기가 몇 초 걸려도 정지는 그동안 계속 받는다(규칙 3).
        """
        if self.state_machine.is_busy:
            # 값싼 거절을 되읽기보다 앞에 둔다(락 없이 본다. 접수는 _accept_run 이 락 안에서 다시 판정한다)
            return Reason.BUSY, f'phase={self.state_machine.phase.name}'
        with self._config_lock:
            # 전파한 적이 없어도 그 노드의 yaml 값이 실제 값이다. 기록의 config 를 사실로 채운다.
            self._refresh_peers('START 직전 되읽기')
            mismatches = propagation.pair_mismatches(self._peer_config)
            if mismatches:
                # 1차 감시와 2차 감시가 다른 값을 들고 있다(계약 7.2). 이 상태로 시작하면 2차가 먼저
                # 걸려 래치부터 난다. 읽지 못한 칸은 어긋남으로 보지 않는다(모른다고 막지 않는다).
                return Reason.PARAM_SET_FAILED, propagation.mismatch_detail(mismatches)
            return self._accept_run(request)

    def _accept_run(self, request):
        """_begin_run 의 뒷부분. _config_lock 을 쥔 채 부른다. 여기서는 아무것도 기다리지 않는다."""
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

            store = self._store_for(params.result_dir)
            scan_id = new_scan_id()
            while (store.result_dir / scan_id).exists():
                scan_id = new_scan_id()  # 같은 초에 난수까지 겹친 경우. 남의 기록에 쓰지 않는다
            started_at = self._now_stamp()
            job = _Job(scan_id, params, conversions.config_to_msg(config), started_at)
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
            self._unrecorded_home = False
        self.log(ScanLog.LEVEL_INFO, Reason.OK, f'작업 시작 request_id={request.request_id}')
        return job

    def _end_job(self, job):
        # 마지막 상태(DONE · STOPPED · ERROR)는 on_change 가 큐에 넣기만 했다. 명령의 Result 를 돌려주기 전에
        # 디스크에 쓰인 것을 확인한다. 그래야 Result 를 받은 쪽이 기록을 읽어도 옛 상태를 보지 않는다.
        try:
            if not self._closing.is_set():
                self._write(lambda: None)
        except RuntimeError:
            pass  # 종료 중이라 쓰기 스레드가 이미 닫혔다
        with self._job_lock:
            if self._job is job:
                self._matcher.end()  # 그 사이에 새 작업이 접수됐으면 그 작업의 matcher 를 지우지 않는다
                self._job = None

    def _internal_failure(self, job, exc, recorded=True, ports=None):
        """돌던 명령이 예외로 끝났다. 종료 중이면 None 을 돌려준다(_Closing 과 같은 취급).

        종료 경로에서 터진 예외(context 가 내려간 뒤의 발행 · 기록)는 작업의 실패가 아니다. 여기서 FAILED 로
        보내면 그 전이가 다시 발행을 부르고(ERROR), 그것도 터져 "실패 처리도 실패" 와 트레이스백이 남는다.
        ports 를 주면 그 작업이 아는 정지 좌표가 실패 기록에 남는다(BRD 4.2.5 의 "위치").
        """
        if self._shutting_down():
            self.get_logger().info(f'종료 중 예외. 작업의 실패로 남기지 않는다: {exc!r}')
            return None
        detail = f'internal: {exc!r}'
        self.get_logger().error(detail)
        try:
            if ports is None:
                ports = _NodePorts(self, job, recorded=recorded)
            ports.fail(int(Reason.ROBOT_ERROR), detail, None)
        except Exception as nested:
            self.get_logger().error(f'실패 처리도 실패: {nested!r}')
        if self.state_machine.is_busy:
            # 로그 · 기록이 먼저 터져 FAILED 를 알리지 못한 경우. 동작 중 phase 에 남으면 계속 BUSY 다
            try:
                self.state_machine.notify(
                    Signal.FAILED, reason_code=int(Reason.ROBOT_ERROR), detail=detail)
            except InvalidTransition:
                pass
        return RunOutcome(OutcomeKind.FAILED, int(Reason.ROBOT_ERROR), detail)

    def _publish_result(self, job, shape):
        job.result_msg = conversions.result_to_msg(
            job.scan_id, shape, job.config_msg, self._now_msg())
        self._publish_quietly(self._result_pub, lambda: job.result_msg)

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
            adoption_failed = False
            if self.state_machine.phase is Phase.IDLE:
                # 프로세스가 재시작된 뒤의 안전복귀도 그 작업의 기록에 남아야 한다. 남지 않으면 뒤따르는 재시작이
                # "복귀한 적 없음"으로 읽고 홈에서 중단 좌표로 곧장 움직인다(계약 5.3절). 되돌리지 못해도 복귀는 한다.
                _why, adoption_failed = self._adopt_recorded_scan()
            before = self.state_machine.snapshot()
            job = _Job(before.scan_id, checked.params)
            self._job = job
            outcome = self.state_machine.request(Command.HOME, conditions=self.conditions())
            if not outcome.accepted:
                self._job = None
                return self._reject(goal_handle, result, outcome.reason, outcome.detail)
        recorded = bool(job.scan_id) and self._store is not None and self._begun == job.scan_id
        ports = _NodePorts(self, job, recorded=recorded)
        try:
            if recorded:
                # 기록 실패(디스크 오류 · 기록 파일 없음)는 안전복귀를 막지 않는다(래치 · 측정 파라미터와 같은 방침).
                recorded = ports.recorded = self._record_home(
                    self._store.record_home_requested, job.scan_id, before.phase)
            if adoption_failed or (job.scan_id and not recorded):
                self._unrecorded_home = True
            self.log(
                ScanLog.LEVEL_INFO, Reason.OK,
                f'안전복귀 시작 request_id={goal_handle.request.request_id}')
            first = self._last_motion_id.get(job.scan_id, 0) + 1
            outcome = run_home(MotionPlanner(job.params), ports, first_motion_id=first)
            final = ports.last_result.raw if ports.last_result is not None else None
            if recorded and outcome.kind is not OutcomeKind.STOPPED:
                self._record_home(
                    self._store.record_home_finished, job.scan_id,
                    outcome.kind is OutcomeKind.DONE,
                    final_pose=conversions.stop_pose_record(final))
        except _Closing:
            outcome, final = None, None
        except Exception as exc:
            # 종료가 깨운 예외면 _internal_failure 가 None 을 준다(= _Closing 과 같다)
            outcome, final = self._internal_failure(job, exc, recorded, ports), None
        finally:
            if ports.last_motion_id:
                self._last_motion_id[job.scan_id] = max(
                    ports.last_motion_id, self._last_motion_id.get(job.scan_id, 0))
            self._end_job(job)

        if final is not None and conversions.has_stop_pose(final):
            result.final_pose = final.pose
            result.frame_id = final.frame_id
        else:
            result.final_pose = conversions.nan_pose()
        return self._finish_goal(goal_handle, result, outcome)

    def _record_home(self, method, *args, **kwargs) -> bool:
        """안전복귀의 사실을 기록한다. 실패하면 ERROR 로그만 남기고 False (복귀는 계속한다)."""
        try:
            self._write(method, *args, **kwargs)
        except _Closing:
            raise
        except Exception as exc:
            self.log(
                ScanLog.LEVEL_ERROR, Reason.ROBOT_ERROR,
                f'안전복귀 기록 실패({method.__name__}): {exc!r}. 기록 없이 복귀를 계속한다')
            return False
        return True

    # ---- /scan/resume ----

    def _execute_resume(self, goal_handle):
        request = goal_handle.request
        result = Resume.Result()
        result.scan_id = request.scan_id
        begun = self._begin_resume(request)
        if isinstance(begun, scan_resume.Refusal):
            return self._reject(goal_handle, result, begun.reason, begun.detail)
        job, resumption = begun
        ports = _NodePorts(self, job, carried_pose=resumption.stop_pose)
        first = max(self._last_motion_id.get(job.scan_id, 0), resumption.last_motion_id) + 1

        def run():
            # 재시작의 사실을 남기지 못하면(디스크 오류 등) 로봇을 움직이기 전에 끝낸다.
            # ERROR 를 잇는 재시작은 남길 곳이 다르다: 실패 기록에 찍는다(FAILED 는 Interruption 을
            # 남기지 않는다. 계약 9장 허용 목록, v0.1.19)
            self._write(
                self._store.record_failure_resume if resumption.from_failure
                else self._store.record_resume, job.scan_id)
            return ResumeRunner(
                MotionPlanner(job.params), ports, job.params.direction_order, resumption.plan,
                first_motion_id=first).run()
        return self._run_job(goal_handle, result, job, ports, run)

    def _begin_resume(self, request):
        """RESUME 을 접수한다. 거절이면 Refusal, 접수면 (_Job, Resumption).

        판정 · 기록 읽기 · 계획을 **접수 전에** 끝낸다. 거절된 재시작은 RESUMING 에 들어가지 않는다.
        """
        machine = self.state_machine
        try:
            # 큐에 남은 상태 기록이 디스크에 쓰인 뒤에 읽는다. **락 밖에서** 기다린다: /scan/stop 이 같은 락을 쓴다
            self._write(lambda: None)
        except _Closing:
            return scan_resume.Refusal(Reason.CANCELED, 'scan_manager 종료')
        if machine.is_busy:
            return scan_resume.Refusal(Reason.BUSY, f'phase={machine.phase.name}')
        with self._config_lock:
            # 재시작도 로봇을 다시 움직인다. 1차 감시와 2차 감시가 다른 값을 들고 있으면 시작하지 않는다
            # (계약 7.2). START 와 같은 규칙이다. 되읽기는 _job_lock 을 잡기 전에 끝낸다(규칙 3).
            self._refresh_peers('RESUME 직전 되읽기')
            mismatches = propagation.pair_mismatches(self._peer_config)
            if mismatches:
                return scan_resume.Refusal(
                    Reason.PARAM_SET_FAILED, propagation.mismatch_detail(mismatches))
            return self._accept_resume(request, machine)

    def _accept_resume(self, request, machine):
        """_begin_resume 의 뒷부분. _config_lock 을 쥔 채 부른다. 여기서는 아무것도 기다리지 않는다."""
        with self._job_lock:
            if machine.is_busy:
                return scan_resume.Refusal(Reason.BUSY, f'phase={machine.phase.name}')
            if self._job is not None:
                # 직전 명령이 휴지 phase 를 발행했지만 아직 끝나지 않았다(마지막 상태 기록을 쓰는 중).
                # 지금 읽으면 옛 기록이다. 그 명령의 Result 가 나간 뒤에 다시 보내면 된다.
                return scan_resume.Refusal(Reason.BUSY, '직전 명령을 마무리하는 중이다')
            if self._unrecorded_home:
                # IDLE 일 때만 보면 안 된다: 거절된 HOME 도 기록에서 상태를 되돌려 IDLE 을 벗어나게 한다
                return scan_resume.Refusal(
                    Reason.NOT_SUPPORTED,
                    '기록에 남기지 못한 안전복귀가 있었다. 홈 안전복귀 뒤의 재접근 절차는 TBD')
            not_adopted = ''
            if machine.phase is Phase.IDLE:
                if not self.get_parameter_or('result_dir').value:
                    return scan_resume.Refusal(
                        Reason.INVALID_VALUE, 'result_dir 파라미터가 없어 기록을 찾을 수 없다')
                not_adopted, _failed = self._adopt_recorded_scan()
            conditions = self.conditions()
            reason, detail = machine.check(
                Command.RESUME, conditions=conditions, scan_id=request.scan_id)
            if reason is not Reason.OK:
                return scan_resume.Refusal(reason, not_adopted or detail)

            scan_id = machine.snapshot().scan_id
            if self._store is None or self._begun != scan_id:
                return scan_resume.Refusal(
                    Reason.NO_RESUMABLE_SCAN, f'{scan_id} 의 기록이 없다(기록을 만들지 못한 작업)')
            try:
                record = self._store.load(scan_id)
                has_result = self._store.has_result(scan_id)
            except (ResultStoreError, OSError) as exc:
                return scan_resume.Refusal(
                    Reason.NO_RESUMABLE_SCAN, f'{scan_id} 의 기록을 읽을 수 없다: {exc}')
            planned = scan_resume.plan_resume(
                record, result_file_exists=has_result,
                direction_order=[Direction[name] for name in self._direction_order])
            if isinstance(planned, scan_resume.Refusal):
                return planned

            # 재시작의 첫 모션도 지금 어디 있는지를 알아야 보낼 수 있다(계약 7.6). **접수 때** 막는다 —
            # 실행 중에 실패하면 실패 기록에 resumed_at 이 찍혀 다시 이을 기회가 사라진다.
            # 여기서 거절하면 기록이 그대로 남아, 샘플이 돌아온 뒤 다시 RESUME 할 수 있다
            if self.current_pose(planned.params.pose_max_age_s) is None:
                return scan_resume.Refusal(
                    Reason.NOT_SUPPORTED,
                    '지금 TCP 위치를 모른다(/robot/sample 의 유효 pose 가 없거나 오래됐다). '
                    '재시작의 첫 모션 목표를 만들 수 없다 — 샘플이 돌아온 뒤 다시 RESUME 한다')

            job = _Job(
                scan_id, planned.params, conversions.config_to_msg(planned.config),
                planned.started_at)
            job.top, job.edges = planned.top, dict(planned.edges)  # 측정값 캐시는 기록에서 다시 만든다
            self._job = job
            outcome = machine.request(
                Command.RESUME, conditions=conditions, scan_id=request.scan_id)
            if not outcome.accepted:
                self._job = None
                return scan_resume.Refusal(outcome.reason, outcome.detail)
        plan = planned.plan
        self.log(
            ScanLog.LEVEL_INFO, Reason.OK,
            f'재시작 request_id={request.request_id}: {plan.phase.name} 에서 잇는다. 기존 측정값 유지'
            f'(윗면 {"확정" if planned.top is not None else "없음"}, '
            f'모서리 {len(plan.confirmed)}/{machine.progress_total})')
        return job, planned

    def _adopt_recorded_scan(self):
        """프로세스가 재시작된 뒤(IDLE), 가장 최근 작업이 STOPPED · ERROR 로 끝나 있으면 상태 기계를 되돌린다.

        (되돌리지 않은 이유, 실패했는가)를 돌려준다. 되돌렸으면 ("", False).
        실패 = 기록을 보지 못했다(result_dir 없음 · 읽기 오류). 되돌릴 작업이 있었는지 **모른다.**
        실패가 아닌데 이유가 있으면 되돌릴 작업이 확실히 없는 것이다(기록 없음 · DONE · 작업 도중에 끝난 기록).
        예외를 던지지 않는다. 명령 접수 락 안에서 부른다.
        되돌린 뒤의 HOME · RESUME 은 같은 프로세스에서 중지한 경우와 같은 경로로 판정 · 기록된다.
        """
        result_dir = self.get_parameter_or('result_dir').value
        if not result_dir:
            return 'result_dir 파라미터가 없어 기록을 찾을 수 없다', True
        try:
            record, why = scan_resume.latest_record(self._store_for(result_dir))
            if record is None:
                return why, False
            restoration, why = scan_resume.restoration_from(record)
            if restoration is None:
                return why, False
            self._begun, self._begin_args = restoration.scan_id, None  # begin_scan 을 다시 부르지 않는다
            self._last_motion_id[restoration.scan_id] = restoration.last_motion_id
            try:
                self.state_machine.restore(
                    scan_id=restoration.scan_id, phase=restoration.phase,
                    progress=restoration.progress, resume_phase=restoration.resume_phase,
                    moved_since_stop=restoration.moved_since_stop, failure=restoration.failure)
            except ValueError:
                self._begun = None
                raise
        except (ResultStoreError, OSError, ValueError) as exc:
            self.get_logger().error(f'기록에서 상태를 되돌리지 못했다: {exc!r}')
            return f'기록에서 상태를 되돌리지 못했다: {exc}', True
        self.log(
            ScanLog.LEVEL_INFO, Reason.OK,
            f'기록에서 되돌렸다: {restoration.scan_id} {restoration.phase.name} '
            f'{restoration.progress}/{self.state_machine.progress_total}')
        return '', False

    # ---- /scan/stop ----

    def _on_stop(self, request, response):
        """정지를 **요청**하고 접수만 돌려준다. 정지 완료 확인 · 중단 위치 기록은 시퀀스 스레드가 한다.

        홈 복귀 · 재시작을 부르지 않는다(CLAUDE.md 규칙 3). 다른 노드의 완료를 여기서 기다리지 않는다.
        """
        handle = None
        # 락 순서: 명령 접수 락 → 작업 락 → 상태 기계 락. START · HOME 의 접수와 겹치지 않게 한다.
        # (겹치면 STOP 이 STOPPING 으로 바꿔 놓고도 그 작업의 stop_event 를 세우지 못해 첫 모션이 나간다)
        with self._job_lock:
            job = self._job
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
        sent = self.request_robot_stop(
            request.request_id, request.reason or int(Reason.STOP_REQUESTED), request.detail)
        robot_stop = '/robot/stop 요청함' if sent else '/robot/stop 서버가 없다'
        if handle is not None:
            handle.cancel_goal_async()

        response.accepted = outcome.accepted
        response.reason_code = int(outcome.reason)
        phase = outcome.state.phase.name
        response.detail = (
            f'phase={phase}. {robot_stop}' if outcome.changed
            else f'멈출 작업이 없다(phase={phase}). {robot_stop}')
        level = ScanLog.LEVEL_INFO if sent else ScanLog.LEVEL_WARN
        self.log(level, Reason.STOP_REQUESTED, f'작업 중지 접수: {response.detail}')
        return response

    def request_robot_stop(self, request_id, reason, detail) -> bool:
        """/robot/stop 을 요청한다(멱등). 응답은 기다리지 않는다. 서버가 없으면 False."""
        if not self._robot_stop_client.service_is_ready():
            return False
        self._robot_stop_client.call_async(StopRobot.Request(
            request_id=request_id, requester=self.get_name(), reason=int(reason), detail=detail)
        ).add_done_callback(self._on_robot_stop_response)
        return True

    def _on_robot_stop_response(self, future):
        """기다리지는 않지만 버리지도 않는다. 정지 완료는 어차피 /robot/status 로만 확인한다."""
        try:
            response = future.result()
        except Exception as exc:
            self.log(ScanLog.LEVEL_WARN, Reason.ROBOT_ERROR, f'/robot/stop 호출 실패: {exc!r}')
            return
        if not response.accepted:
            self.log(
                ScanLog.LEVEL_WARN, response.reason_code,
                f'/robot/stop 이 접수되지 않았다: {response.detail}')

    # ---- /scan/set_config ----

    def _on_set_config(self, request, response):
        """자기 값 6개를 적용하고, 나머지 6개를 세 노드에 전파한다(계약 2.4 · 4.3).

        락: 전체를 _config_lock 으로 감싼다(START 의 설정 확정과 서로 배제). 작업 락(_job_lock)은
        접수 판정과 자기 값 반영에만 짧게 잡는다 — 전파를 기다리는 동안 /scan/stop 이 막히지 않게 한다.
        상대 노드가 꺼져 있으면 START 가 server_wait_timeout_s x 노드 수만큼 늦어진다(정지는 아니다).

        **교착은 없다.** 이 콜백은 자기 전용 MutuallyExclusive 그룹에서 돌고, set_parameters ·
        get_parameters 의 응답은 clients(Reentrant) 의 다른 스레드가 처리한다. 콜백 안에서 spin 하지
        않는다(wait_future 는 done_callback + Event 로 기다린다).
        """
        values = conversions.config_values_from_msg(request.config)
        with self._config_lock:
            with self._job_lock:   # 접수 판정과 자기 값 반영 사이에 START 가 끼지 않게 한다
                outcome = self.state_machine.request(Command.SET_CONFIG)
                problems = () if not outcome.accepted else scan_params.check_values(values)
                if outcome.accepted and not problems:
                    # 자기 몫만 들고 있는다. 다른 노드 몫은 그 노드가 실제 값이고, 여기서 읽는 곳이 없다.
                    self._config.update({
                        k: v for k, v in values.items()
                        if k in scan_params.MOTION_CONFIG_NAMES})
            if not outcome.accepted:
                response.reason_code, response.detail = int(outcome.reason), outcome.detail
            elif problems:
                # 범위 밖이면 같이 온 정상값도 적용하지 않는다(T19a). 전파도 하지 않는다.
                response.reason_code = int(Reason.INVALID_VALUE)
                response.detail = '; '.join(problems)
            else:
                try:
                    plans = propagation.plan(values)
                    results = self._propagate(plans)
                    own = sorted(set(values) & set(scan_params.MOTION_CONFIG_NAMES))
                    summary = propagation.summarize(plans, results, own)
                    response.success = summary.success
                    response.detail = summary.detail
                    if not summary.success:
                        response.reason_code = int(Reason.PARAM_SET_FAILED)
                    # applied 에 실을 값은 요청값이 아니라 그 노드에서 읽은 실제 값이다
                    self._refresh_peers('SetConfig 뒤 되읽기')
                    mismatches = propagation.pair_mismatches(self._peer_config)
                    if mismatches:
                        response.success = False
                        response.reason_code = int(Reason.PARAM_SET_FAILED)
                        response.detail += ' / ' + propagation.mismatch_detail(mismatches)
                except _Closing:
                    # 기다리는 도중에 노드가 내려간다. 예외를 서비스 콜백 밖으로 내보내지 않는다
                    response.success = False
                    response.reason_code = int(Reason.PARAM_SET_FAILED)
                    response.detail = '전파 도중 scan_manager 가 종료됐다. 어디까지 갔는지 알 수 없다'
                except Exception as exc:
                    # 응답 없이 끝내지 않는다. mqtt_bridge 는 SetConfig 응답을 기다릴 뿐 한도가 없다
                    self.get_logger().error(f'전파 중 예상 밖 오류: {exc!r}')
                    response.success = False
                    response.reason_code = int(Reason.PARAM_SET_FAILED)
                    response.detail = f'전파 중 오류: {exc!r}'
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

    def __init__(self, node: ScanManager, job: _Job, recorded=True, carried_pose=None):
        self._node = node
        self._job = job
        self._params = job.params
        self.recorded = recorded    # result_store 에 이 작업의 기록이 있는가(쓸 수 있는가)
        # 재시작: 직전 중지의 중단 좌표(PoseRecord). 모션을 하나도 보내지 않고 다시 중지되면 그대로 이어 적는다
        self._carried_pose = carried_pose
        self.last_motion_id = 0
        self.last_result = None   # 가장 최근에 받은 Result (정지 좌표의 출처)
        self._last_event = None   # 가장 최근에 짝이 맞은 ContactEvent (판정 좌표의 출처)
        # 이번 모션에서 로봇이 움직였을 수 있는데 쓸 수 있는 Result.pose 가 없다 → 정지 좌표를 모른다.
        # 앞 모션의 좌표를 이 모션의 정지 좌표라고 적지 않으려고 따로 둔다(모르는 값을 채우지 않는다).
        self._stop_pose_unknown = False

    def _stop_pose(self):
        """(정지 좌표의 원본 Pose, frame_id). 이 모션의 정지 좌표를 모르면 (None, '')."""
        raw = self.last_result.raw if self.last_result is not None else None
        if self._stop_pose_unknown or raw is None or not conversions.has_stop_pose(raw):
            return None, ''
        return raw.pose, raw.frame_id

    def _stop_pose_record(self):
        """정지 좌표(PoseRecord). 기록에 남길 "로봇이 마지막으로 멈춘 자리"다. 모르면 None.

        - 이번 모션이 로봇을 움직였을 수 있는데 쓸 수 있는 Result.pose 가 없으면(Result 가 끝내 오지 않음 ·
          응답 없는 goal 의 늦은 수락 · 다른 프레임의 Result.pose · pose_stamp=0) 모르는 것이다.
        - 로봇을 움직이지 않은 채 끝난 명령(goal 거절 · 서버 없음 · 보내지 않은 goal)에서는 로봇이 그대로
          앞 모션의 정지 좌표에 있다. record_stop 과 같은 규칙으로 그 좌표를 쓰고, 그것도 없으면
          직전 중지의 좌표(재시작으로 이어받은 것)를 쓴다.
        """
        if self._stop_pose_unknown:
            return None
        raw = self.last_result.raw if self.last_result is not None else None
        if raw is None:
            return self._carried_pose
        return conversions.stop_pose_record(raw)

    def stop_requested(self):
        return self._job.stop_event.is_set()

    def safety_reason_code(self):
        return self._node.safety_reason_code()

    def execute(self, motion_id, request):
        node, job, p = self._node, self._job, self._params
        self.last_motion_id = motion_id
        self._stop_pose_unknown = False
        # 발급하자마자 남긴다. 명령이 끝난 뒤에 남기면, 중지 직후에 접수된 안전복귀가 옛 값으로 번호를 되풀이한다(계약 6.2절)
        node._last_motion_id[job.scan_id] = max(motion_id, node._last_motion_id.get(job.scan_id, 0))
        if not node._motion_client.wait_for_server(timeout_sec=p.server_wait_timeout_s):
            return MotionResult(available=False)
        node._matcher.begin(
            job.scan_id, motion_id, _EXPECTED_EVENT.get(request.operation), p.motion_frame_id)
        node.state_machine.set_motion_id(motion_id)
        handle = None
        try:
            goal = conversions.goal_from_request(request, job.scan_id, motion_id, p.motion_frame_id)
            with job.lock:
                # 시퀀스의 중지 확인과 여기 사이(서버 대기 등)에 /scan/stop 이 왔으면 goal 을 보내지 않는다.
                # /scan/stop 은 이 락 안에서 stop_event 를 세우므로, 이 뒤에 오는 중지는 아래의 cancel 이 받는다.
                if job.stop_event.is_set():
                    return MotionResult(
                        reason=MotionReason.STOP_REQUESTED, reason_code=int(Reason.STOP_REQUESTED),
                        detail=f'{request.label}: 중지가 접수돼 goal 을 보내지 않았다')
                sent = node._motion_client.send_goal_async(goal)
            if not node.wait_future(sent, p.server_wait_timeout_s):
                # 요청은 이미 나갔다. 늦게 수락되면 아무도 모르는 모션이 돈다 → 늦은 수락은 바로 취소하고 정지도 요청한다
                sent.add_done_callback(self._cancel_late_goal)
                self._stop_untracked(f'{request.label}: goal 응답이 오지 않았다')
                self._stop_pose_unknown = True   # 늦게 수락됐으면 움직였다. 어디서 멈췄는지는 모른다
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
                self._stop_untracked(f'{request.label}: Result 가 오지 않았다')
                self._stop_pose_unknown = True   # 돌던 모션이다. 정지 좌표를 주는 Result 가 없다
                return MotionResult(
                    reason=MotionReason.TIMEOUT, detail=f'{backstop:.1f} s 안에 Result 가 오지 않았다')
            raw = done.result().result
            handle = None  # 끝난 goal 이다
            if conversions.has_stop_pose(raw) and raw.frame_id != p.motion_frame_id:
                # 좌표를 쓰는 쪽은 frame_id 를 확인한다(계약 1장). 다른 프레임의 좌표로 다음 모션을 만들지 않는다
                self._stop_pose_unknown = True   # 기록 · 로그에도 쓰지 않는다. 앞 모션의 좌표로 대신하지 않는다
                return MotionResult(
                    reason=MotionReason.ROBOT_ERROR, reason_code=int(Reason.ROBOT_ERROR),
                    detail=f'Result.frame_id={raw.frame_id!r} 가 {p.motion_frame_id!r} 가 아니다',
                    compliance_released=bool(raw.compliance_released))
            self.last_result = conversions.motion_result_from_msg(raw)
            return self.last_result
        except BaseException:
            if handle is not None:
                handle.cancel_goal_async()  # 수락된 모션을 두고 빠져나가지 않는다(종료 중 포함)
            raise
        finally:
            with job.lock:
                job.motion_handle = None
            node.state_machine.set_motion_id(0)

    @staticmethod
    def _cancel_late_goal(future):
        try:
            handle = future.result()
        except Exception:
            return
        if handle.accepted:
            handle.cancel_goal_async()

    def _stop_untracked(self, detail):
        """추적하지 못하는 모션이 돌고 있을 수 있다. 정지를 요청한다(멱등). 홈 복귀 · 재시작은 부르지 않는다."""
        sent = self._node.request_robot_stop(
            f'scan_manager-{self._job.scan_id}', int(Reason.ROBOT_ERROR), detail)
        self._node.log(
            ScanLog.LEVEL_WARN, Reason.ROBOT_ERROR,
            f'{detail}. /robot/stop {"요청함" if sent else "서버가 없다"}')

    def wait_event(self, event_id):
        event = self._node._matcher.wait(event_id, self._params.event_wait_timeout_s)
        if self._node._closing.is_set():
            raise _Closing()  # 종료가 기다림을 깨웠다. 이벤트 미도착(실패)으로 적지 않는다
        if event is None:
            return None
        self._last_event = event
        return MatchedEvent(conversions.position_of(event.pose), raw=event)

    def wait_still(self):
        return self._node.wait_still(self._params.stop_confirm_timeout_s)

    def current_pose(self):
        return self._node.current_pose(self._params.pose_max_age_s)

    def damage_suspect_reason(self):
        """직전 실패가 손상 의심 사유였는가 (계약 7.5 ②).

        상태 기계의 failure 는 다음 START 까지 남는다. 안전복귀는 그 실패 뒤에 오는 명령이므로
        여기서 보는 것이 맞다. 정상 중지(STOPPED)에는 failure 가 없어 "" 다 — 평소 경로는 그대로다.
        """
        return _damage_suspect_reason(
            self._node.state_machine.failure, self._node.safety_reason_code())

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
        node.log(
            ScanLog.LEVEL_INFO, Reason.OK, '윗면 접촉 확정 (판정 좌표)', event.raw.pose,
            event.raw.frame_id)

    def record_edge(self, direction, event, result, request):
        node, job = self._node, self._job
        node._write(
            node._store.record_edge, job.scan_id, direction, self._measurement(event, result))
        raw = event.raw
        job.edges[direction] = EdgeMeasurement(
            event.position, raw.z_drop_m if raw.z_drop_valid else None, request.speed)
        node.log(
            ScanLog.LEVEL_INFO, Reason.OK, f'{direction.name} 모서리 확정 (판정 좌표)', raw.pose,
            raw.frame_id)

    def record_attempt_failed(self, target, reason_code, detail, result):
        stop_pose = conversions.stop_pose_record(result.raw)
        self._node._write(
            self._node._store.record_attempt_failed, self._job.scan_id, target, reason_code, detail,
            stop_pose)

    def notify(self, signal):
        # 작업 락 안에서 알린다. /scan/stop 이 "접수 직전의 Snapshot" 을 뜨고 STOP 을 요청하는 사이에
        # 전이가 끼면 중단 기록의 phase · 방향 · 진행도가 실제와 어긋난다(마무리 HOMING 에서는 ValueError).
        with self._job.lock:
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

    def republish_result(self):
        node, job = self._node, self._job
        stored = node._store.load_result(job.scan_id)
        try:
            # 원본은 한 번만 쓴다. 이 호출은 쓰지 않고, 진행 기록의 result_saved 표시가 빠져 있었다면
            # (원본을 쓴 직후에 프로세스가 죽은 경우) 있는 파일대로 고친다(result_store/README.md).
            node._write(node._store.save_result, job.scan_id, stored.shape, stored.bias_corrections)
        except ResultAlreadySaved:
            pass
        node._publish_result(job, stored.shape)  # stamp 는 새로 찍는다(mqtt_bridge 의 중복 제거 키)
        node.log(
            ScanLog.LEVEL_INFO, stored.shape.reason_code,
            '저장된 원본을 다시 발행했다. 다시 계산하지 않는다')
        return StepOutcome(stored.shape.success, stored.shape.reason_code, stored.shape.detail)

    def fail(self, reason_code, detail, position):
        """원인 · 단계 · 위치를 남기고 ERROR 로 보낸다(BRD 4.2.5). 홈 복귀는 하지 않는다."""
        node, job = self._node, self._job
        phase = node.state_machine.phase.name
        pose, frame_id = self._stop_pose()
        where = '정지 좌표' if pose is not None else '좌표 없음'
        node.log(ScanLog.LEVEL_ERROR, reason_code, f'{phase} 실패: {detail} ({where})', pose, frame_id)
        node.state_machine.notify(Signal.FAILED, reason_code=reason_code, detail=detail)
        if self.recorded and job.scan_id:
            try:
                kept = node._write(
                    _record_first_failure, node._store, job.scan_id, node.state_machine.failure,
                    self._stop_pose_record())
                if kept is not None:
                    node.get_logger().info(
                        f'기록의 실패 사유는 첫 실패({kept.reason_code} {kept.phase.name})를 그대로 둔다')
            except Exception as exc:  # 기록을 못 해도(디스크 오류 등) 결과 발행까지는 간다
                node.get_logger().error(f'실패 기록을 쓰지 못했다: {exc!r}')
        if job.result_msg is None and job.started_at is not None:
            node._publish_partial_result(job, reason_code, detail)

    def record_stop(self, position, result, during_final_homing):
        node, job = self._node, self._job
        with job.lock:
            before = job.stop_snapshot
        # 중단 위치 = 로봇이 마지막으로 멈춘 자리. 보내지 않은 goal(result.raw 없음)은 로봇을 움직이지 않았으므로
        # 그 앞의 Result 를 쓴다. 이 명령에서 받은 Result 가 없으면 직전 중지의 좌표가 그대로다(재시작).
        raw = result.raw if result is not None else None
        if raw is None and self.last_result is not None:
            raw = self.last_result.raw
        pose = conversions.stop_pose_record(raw) if raw is not None else self._carried_pose
        if self.recorded and job.scan_id and before is not None:
            node._write(node._store.record_stop, job.scan_id, Interruption(
                before.phase, before.direction, before.progress, pose=pose,
                during_final_homing=during_final_homing))
        stop_pose, frame_id = self._stop_pose()
        where = '정지 좌표' if stop_pose is not None else '좌표 없음'
        node.log(
            ScanLog.LEVEL_INFO, Reason.STOP_REQUESTED, f'정지 완료 확인 ({where})', stop_pose, frame_id)

    def log_info(self, message, position=None):
        # 시퀀스는 좌표를 튜플로 준다. 그 좌표의 원본(판정 좌표면 이벤트, 아니면 정지 좌표)을 찾아 싣는다
        event = self._last_event
        if position is None:
            pose, frame_id = None, ''
        elif event is not None and conversions.position_of(event.pose) == tuple(position):
            pose, frame_id = event.pose, event.frame_id
        else:
            pose, frame_id = self._stop_pose()
        self._node.log(ScanLog.LEVEL_INFO, Reason.OK, message, pose, frame_id)


def _record_first_failure(store, scan_id, failure, pose=None):
    """실패 사유 · 단계 · 위치를 기록한다. 이미 있으면 덮어쓰지 않고 그 기록을 돌려준다(썼으면 None).

    작업이 실패한 뒤의 안전복귀가 또 실패해도 작업의 실패 원인(예: NO_EDGE)과 그때 멈춘 자리가 남아야 한다.
    안전복귀의 실패는 home_return.completed=false 와 /scan/log 에 남는다. 쓰기 스레드에서 돈다.
    """
    existing = store.load(scan_id).failure
    if existing is not None:
        return existing
    store.record_failure(scan_id, failure, pose)
    return None


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
        # 첫 SIGINT 를 처리하러 가는 사이에 온 두 번째 SIGINT. 기다리는 시퀀스 스레드는 풀어 준다
        _shutdown_quietly(node, executor)


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
