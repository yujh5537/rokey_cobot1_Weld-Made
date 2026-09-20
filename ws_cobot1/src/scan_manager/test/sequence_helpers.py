"""시퀀스 · 파라미터 · 형상 연결 테스트의 공용 입력과 가짜 Ports.

수치는 테스트용 임의값이다. 설계 출발값도 실측값도 아니다.
가상 직육면체는 sim.yaml 의 sim 박스와 같은 모양(밑면 중심 (0.40, 0.00, 0.00), 0.10 x 0.06 x 0.04)이며,
가짜 로봇은 geometry_estimator 의 보정식을 거꾸로 적용한 정방향 모델로 판정 좌표를 만든다.
"""

import itertools
import math
import os

from scan_manager import geometry_adapter
from scan_manager.contract_enums import Direction
from scan_manager.contract_enums import MotionReason
from scan_manager.contract_enums import Operation
from scan_manager.contract_enums import Phase
from scan_manager.params import check
from scan_manager.result_store import Stamp
from scan_manager.sequence import MatchedEvent
from scan_manager.sequence import MotionResult
from scan_manager.sequence import Ports
from scan_manager.sequence import StepOutcome
from scan_manager.state_machine import Command
from scan_manager.state_machine import Conditions
from scan_manager.state_machine import InvalidTransition
from scan_manager.state_machine import ScanStateMachine

DOWN = (0.0, 1.0, 0.0, 0.0)
VALUES = {
    'descend_speed_mps': 0.004,
    'slide_speed_mps': 0.012,
    'max_descend_m': 0.09,
    'max_slide_m': 0.14,
    'motion_timeout_s': 25.0,
    'lift_height_m': 0.03,
    'move_speed_mps': 0.05,
    'recontact_margin_m': 0.0015,
    'recontact_speed_mps': 0.003,
    'search_origin_pose': [0.40, 0.00, 0.10, *DOWN],
    'base_to_fixture': [0.40, 0.00, 0.00],
    'support_z_m': 0.0,
    'tip_radius_m': 0.000225,
    'detect_latency_s': 0.03,
    'edge_round_radius_m': 0.0,
    'edge_bias_offset_m': 0.0002,
    'result_dir': '/tmp/unused',
    'event_wait_timeout_s': 0.2,
    'stop_confirm_timeout_s': 0.5,
    'server_wait_timeout_s': 0.2,
}
SCAN_ID = '20260920-120000-0001'
READY = Conditions(robot_connected=True, safety_latched=False)

# 가상 직육면체 (Base)
BOX_CENTER = (0.40, 0.00)
BOX_SIZE = (0.10, 0.06, 0.04)
BOX_BOTTOM_Z = 0.0
Z_DROP_M = 0.0005   # tip_radius_m 보다 크다 → 팁이 모서리를 완전히 벗어난 구간(d = r)
HOME_POSITION = (0.42, -0.18, 0.29)
SIGN = {Direction.POS_X: 1.0, Direction.NEG_X: -1.0, Direction.POS_Y: 1.0, Direction.NEG_Y: -1.0}


# 이 조에 배정된 ROS_DOMAIN_ID 는 30~39 다. 30 은 조 공용(실기 · 팀원의 Virtual)이라 쓰지 않는다.
# 범위 밖 번호는 같은 망의 다른 조와 섞인다.
TEST_DOMAIN_IDS = range(31, 40)


def isolated_ros_env() -> dict:
    """노드 테스트가 쓸 ROS 환경 변수. 다른 테스트 · 떠 있는 노드 · 실기와 섞이지 않게 한다.

    - ROS_DOMAIN_ID: 31~39 중 하나(PID 로 고른다. 같은 PC 의 다른 테스트 프로세스와 겹칠 확률을 줄인다).
    - ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST: 이 PC 밖으로 나가지 않는다. 가짜 상대 노드에 보내는 goal 이
      같은 망의 robot_manager(Virtual · 실기)로 갈 길을 막는 것은 이 설정이다(CLAUDE.md 규칙 1).
    """
    domain = TEST_DOMAIN_IDS[os.getpid() % len(TEST_DOMAIN_IDS)]
    return {'ROS_DOMAIN_ID': str(domain), 'ROS_AUTOMATIC_DISCOVERY_RANGE': 'LOCALHOST'}


def make_params(**overrides):
    result = check({**VALUES, **overrides})
    assert result.ok, result.describe()
    return result.params


def edge_coordinate(direction, box_center=BOX_CENTER, box_size=BOX_SIZE):
    axis = geometry_adapter.AXIS[direction]
    return box_center[axis] + SIGN[direction] * box_size[axis] / 2.0


class FakePorts(Ports):
    """가상 직육면체 위의 가짜 로봇 + 실제 상태 기계. 부른 순서를 trace 에 남긴다."""

    def __init__(self, params, direction_order=None):
        self.params = params
        self.sm = ScanStateMachine(direction_order=direction_order or params.direction_order)
        assert self.sm.request(Command.START, conditions=READY, scan_id=SCAN_ID).accepted
        self.trace = []
        self.requests = []            # (motion_id, MotionRequest)
        self.position = HOME_POSITION
        self.first_contact = None
        self.top = None
        self.edges = {}
        self.attempt_failures = []    # (target, code, detail)
        self.failure = None           # (code, detail, position)
        self.stop_record = None       # (position, result, during_final_homing)
        self.geometry = None
        self.infos = []
        self._event_ids = itertools.count(101)
        self._events = {}
        self._stop = False
        # 주입
        self.override = {}            # label → MotionResult | callable(request) → MotionResult
        self.drop_events = set()      # 이 label 의 이벤트는 끝내 오지 않는다
        self.stop_during = None       # 이 label 의 모션 도중에 /scan/stop 이 온다
        self.stop_after_event = None  # 이 label 의 측정값을 받은 직후에 /scan/stop 이 온다
        self.stop_before_notify = None  # 이 Signal 을 알리기 직전에 /scan/stop 이 온다
        self.latch_after = None       # 이 label 의 모션이 끝난 직후에 안전 래치가 걸린다(모션 사이의 래치)
        self.still = True
        self.tare_outcome = StepOutcome(True)
        self.safety_code = 0
        self.geometry_outcome = None  # StepOutcome 으로 덮어쓰면 계산하지 않고 그 값을 돌려준다

    # -- 관제자 --

    def request_stop(self):
        outcome = self.sm.request(Command.STOP)
        assert outcome.accepted
        self._stop = True

    # -- Ports --

    def stop_requested(self):
        return self._stop

    def safety_reason_code(self):
        return self.safety_code

    def execute(self, motion_id, request):
        self.trace.append(('execute', request.label))
        self.requests.append((motion_id, request))
        self.sm.set_motion_id(motion_id)
        try:
            injected = self.override.get(request.label)
            if injected is not None:
                return injected(request) if callable(injected) else injected
            if self.stop_during == request.label:
                self.request_stop()
                return MotionResult(
                    reason=MotionReason.STOP_REQUESTED, reason_code=200, position=self.position)
            return self._simulate(request)
        finally:
            self.sm.set_motion_id(0)
            if self.latch_after == request.label:
                self.safety_code = 400

    def _simulate(self, request):
        p = self.params
        if request.operation is Operation.MOVE_TO:
            self.position = tuple(request.target_position)
            return MotionResult(reason=MotionReason.TARGET_REACHED, position=self.position)
        if request.operation is Operation.HOME:
            self.position = HOME_POSITION
            return MotionResult(reason=MotionReason.TARGET_REACHED, position=self.position)
        x, y, z = self.position
        if request.operation is Operation.DESCEND:
            top_z = BOX_BOTTOM_Z + BOX_SIZE[2]
            detected = (x, y, top_z - request.speed * p.detect_latency_s)
            self.position = (x, y, detected[2] - 0.0002)   # 정지 좌표는 판정 좌표보다 더 내려가 있다
            return self._measured(request, MotionReason.CONTACT, detected, None)
        direction = request.direction
        axis = geometry_adapter.AXIS[direction]
        reach = p.tip_radius_m + p.edge_round_radius_m
        d = reach if Z_DROP_M >= reach else math.sqrt(2 * reach * Z_DROP_M - Z_DROP_M ** 2)
        overshoot = (d - p.edge_round_radius_m + request.speed * p.detect_latency_s
                     + p.edge_bias_offset_m)
        detected = [x, y, z - Z_DROP_M]
        detected[axis] = edge_coordinate(direction) + SIGN[direction] * overshoot
        stopped = list(detected)
        stopped[axis] += SIGN[direction] * 0.0004
        self.position = tuple(stopped)
        return self._measured(request, MotionReason.EDGE, tuple(detected), Z_DROP_M)

    def _measured(self, request, reason, detected, z_drop):
        event_id = next(self._event_ids)
        if request.label not in self.drop_events:
            self._events[event_id] = MatchedEvent(detected, raw={'z_drop_m': z_drop})
        if self.stop_after_event == request.label:
            self.request_stop()
        return MotionResult(reason=reason, event_id=event_id, position=self.position)

    def wait_event(self, event_id):
        self.trace.append(('wait_event', event_id))
        return self._events.get(event_id)

    def wait_still(self):
        self.trace.append(('wait_still',))
        return self.still

    def tare(self):
        self.trace.append(('tare',))
        return self.tare_outcome

    def record_top(self, event, result, request):
        self.trace.append(('record_top',))
        self.top = geometry_adapter.TopMeasurement(event.position, request.speed)
        self.first_contact = event.position

    def record_edge(self, direction, event, result, request):
        self.trace.append(('record_edge', direction))
        self.edges[direction] = geometry_adapter.EdgeMeasurement(
            event.position, event.raw['z_drop_m'], request.speed)

    def record_attempt_failed(self, target, reason_code, detail, result):
        self.trace.append(('record_attempt_failed', target))
        self.attempt_failures.append((target, reason_code, detail))

    def notify(self, signal):
        if self.stop_before_notify == signal:
            self.request_stop()
        try:
            self.sm.notify(signal)
        except InvalidTransition:
            assert self.sm.phase is Phase.STOPPING
            self.trace.append(('notify_refused', signal))
            return False
        self.trace.append(('notify', signal))
        return True

    def compute_geometry(self):
        self.trace.append(('compute_geometry',))
        if self.geometry_outcome is not None:
            return self.geometry_outcome
        self.geometry = geometry_adapter.compute_shape(
            self.top, self.edges, self.params, started_at=Stamp(1), finished_at=Stamp(2))
        shape = self.geometry.shape
        return StepOutcome(shape.success, shape.reason_code, shape.detail)

    def fail(self, reason_code, detail, position):
        from scan_manager.state_machine import Signal
        self.trace.append(('fail', reason_code))
        self.failure = (reason_code, detail, position)
        self.sm.notify(Signal.FAILED, reason_code=reason_code, detail=detail)

    def record_stop(self, position, result, during_final_homing):
        self.trace.append(('record_stop',))
        self.stop_record = (position, result, during_final_homing)

    def log_info(self, message, position=None):
        self.infos.append(message)

    # -- 조회 --

    def labels(self):
        return [request.label for _, request in self.requests]
