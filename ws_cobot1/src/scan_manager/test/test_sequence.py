"""시퀀스 순수 로직: 모션 순서 · 결과 판정 · 실패 · 중지 경로 (ROS 없음, 가짜 Ports).

수치는 테스트용 임의값이다.
"""

import pytest
from scan_manager.contract_enums import Direction
from scan_manager.contract_enums import MotionReason
from scan_manager.contract_enums import Operation
from scan_manager.contract_enums import Phase
from scan_manager.contract_enums import Reason
from scan_manager.sequence import classify
from scan_manager.sequence import MotionPlanner
from scan_manager.sequence import MotionRequest
from scan_manager.sequence import MotionResult
from scan_manager.sequence import OutcomeKind
from scan_manager.sequence import run_home
from scan_manager.sequence import ScanRunner
from scan_manager.sequence import StepOutcome
from scan_manager.sequence import TOP
from scan_manager.sequence import VerdictKind
from scan_manager.state_machine import Command
from scan_manager.state_machine import Signal
from sequence_helpers import BOX_SIZE
from sequence_helpers import FakePorts
from sequence_helpers import make_params
from sequence_helpers import READY

ORDER = (Direction.POS_X, Direction.NEG_X, Direction.POS_Y, Direction.NEG_Y)
CHANGE = ['lift', 'to_origin_xy', 'recontact']
RETURN_LABELS = {'final_lift', 'home'}


@pytest.fixture
def params():
    return make_params()


@pytest.fixture
def ports(params):
    return FakePorts(params)


def run(ports, params):
    return ScanRunner(MotionPlanner(params), ports, params.direction_order).run()


def no_return_motion(ports):
    return not RETURN_LABELS & set(ports.labels())


# ---- 정상 경로 ----

def test_normal_run_order_and_motion_ids(ports, params):
    outcome = run(ports, params)

    assert outcome.kind is OutcomeKind.DONE
    assert ports.sm.phase is Phase.DONE
    expected = ['to_origin', 'descend', 'slide_POS_X']
    for direction in ORDER[1:]:
        expected += CHANGE + [f'slide_{direction.name}']
    expected += ['final_lift', 'home']
    assert ports.labels() == expected
    # motion_id 는 scan 안에서 1 부터 증가한다(계약 6.2절)
    assert [motion_id for motion_id, _ in ports.requests] == list(range(1, len(expected) + 1))


def test_prepare_moves_then_confirms_still_then_tares(ports, params):
    run(ports, params)
    head = [step[0] for step in ports.trace[:4]]
    assert head == ['execute', 'wait_still', 'tare', 'notify']
    assert ports.trace[3] == ('notify', Signal.PREPARE_DONE)


def test_direction_change_is_three_moves_without_descend(ports, params):
    run(ports, params)

    descends = [r for _, r in ports.requests if r.operation is Operation.DESCEND]
    assert len(descends) == 1  # 첫 하강뿐이다. 방향 전환에서 재하강하지 않는다(7.3절)
    requests = [r for _, r in ports.requests]
    first_slide = requests[2]
    lift, to_origin_xy, recontact, next_slide = requests[3:7]
    assert [r.operation for r in (lift, to_origin_xy, recontact)] == [Operation.MOVE_TO] * 3
    assert next_slide.operation is Operation.SLIDE and next_slide.direction is Direction.NEG_X

    origin_x, origin_y, _ = params.origin_position
    first_contact_z = ports.first_contact[2]
    assert lift.target_position[:2] != (origin_x, origin_y)  # 멈춘 자리에서 수직으로만 올린다
    assert to_origin_xy.target_position == (origin_x, origin_y, lift.target_position[2])
    assert recontact.target_position == pytest.approx(
        (origin_x, origin_y, first_contact_z + params.recontact_margin_m))
    # 내림만 저속이다
    assert (lift.speed, to_origin_xy.speed) == (params.move_speed_mps,) * 2
    assert recontact.speed == params.recontact_speed_mps
    assert first_slide.speed == next_slide.speed == params.slide_speed_mps
    # 탐색 중 자세는 기준점의 자세 그대로다
    assert {r.target_orientation for r in (lift, to_origin_xy, recontact)} == {
        params.origin_orientation}


def test_first_contact_z_is_the_detection_not_the_stop_pose(ports, params):
    run(ports, params)
    descend_result_z = BOX_SIZE[2] - params.descend_speed_mps * params.detect_latency_s
    assert ports.first_contact[2] == pytest.approx(descend_result_z)
    recontact = next(r for _, r in ports.requests if r.label == 'recontact')
    assert recontact.target_position[2] == pytest.approx(
        descend_result_z + params.recontact_margin_m)


def test_measurement_is_recorded_before_the_state_machine_is_told(ports, params):
    run(ports, params)
    steps = [s for s in ports.trace if s[0] in ('record_top', 'record_edge', 'notify')]
    assert steps.index(('record_top',)) + 1 == steps.index(('notify', Signal.TOP_FOUND))
    for direction in ORDER:
        at = steps.index(('record_edge', direction))
        assert steps[at + 1] == ('notify', Signal.EDGE_FOUND)


def test_result_is_computed_before_the_final_return(ports, params):
    run(ports, params)
    names = [s for s in ports.trace if s[0] in ('compute_geometry', 'execute', 'notify')]
    geometry_at = names.index(('compute_geometry',))
    assert names[geometry_at + 1] == ('notify', Signal.GEOMETRY_DONE)
    assert names.index(('execute', 'final_lift')) > geometry_at
    assert names[-3:] == [
        ('execute', 'final_lift'), ('execute', 'home'), ('notify', Signal.HOMING_DONE)]


def test_box_dimensions_are_recovered_through_the_real_estimator(ports, params):
    run(ports, params)
    shape = ports.geometry.shape
    assert shape.success and shape.box_valid
    # 작업대 좌표: 밑면 중심이 원점이다
    assert shape.x_pos.value == pytest.approx(0.05)
    assert shape.x_neg.value == pytest.approx(-0.05)
    assert shape.y_pos.value == pytest.approx(0.03)
    assert shape.y_neg.value == pytest.approx(-0.03)
    assert shape.z_top.value == pytest.approx(0.04)
    assert (shape.width, shape.length, shape.height) == pytest.approx(BOX_SIZE)


def test_direction_order_parameter_is_followed():
    params = make_params(direction_order=['NEG_Y', 'POS_X', 'POS_Y', 'NEG_X'])
    ports = FakePorts(params)
    assert run(ports, params).kind is OutcomeKind.DONE
    slides = [r.direction for _, r in ports.requests if r.operation is Operation.SLIDE]
    assert slides == [Direction.NEG_Y, Direction.POS_X, Direction.POS_Y, Direction.NEG_X]


# ---- 실패: 자동 복귀 없음 ----

@pytest.mark.parametrize('label, target, result, code', [
    ('descend', TOP, MotionResult(reason=MotionReason.MAX_DISTANCE, reason_code=300), Reason.NO_CONTACT),
    ('slide_NEG_X', Direction.NEG_X,
     MotionResult(reason=MotionReason.MAX_DISTANCE, reason_code=301), Reason.NO_EDGE),
    ('slide_POS_Y', Direction.POS_Y, MotionResult(reason=MotionReason.TIMEOUT), Reason.TIMEOUT),
    ('slide_POS_X', Direction.POS_X, MotionResult(accepted=False), Reason.ROBOT_ERROR),
    ('descend', TOP, MotionResult(available=False), Reason.ROBOT_DISCONNECTED),
    ('slide_POS_X', Direction.POS_X, MotionResult(reason=MotionReason.OVER_FORCE), Reason.OVER_FORCE),
    ('slide_NEG_Y', Direction.NEG_Y,
     MotionResult(reason=MotionReason.ROBOT_ERROR, reason_code=205), Reason.DROP_LIMIT),
])
def test_search_failure_ends_in_error_without_returning_home(ports, params, label, target, result, code):
    stop_position = (0.41, 0.0, 0.039)
    ports.override[label] = MotionResult(**{**result.__dict__, 'position': stop_position})

    outcome = run(ports, params)

    assert outcome.kind is OutcomeKind.FAILED and outcome.reason_code == code
    assert ports.sm.phase is Phase.ERROR
    assert ports.labels()[-1] == label      # 실패한 모션 뒤로 아무 모션도 보내지 않는다
    assert no_return_motion(ports)
    # 원인 · 단계 · 위치 (BRD 4.2.5)
    assert ports.attempt_failures == [(target, code, outcome.detail)]
    assert ports.failure == (code, outcome.detail, stop_position)
    assert ports.sm.failure.phase in (Phase.TOP_SEARCH, Phase.EDGE_SEARCH)
    if not result.accepted:
        assert 'goal rejected' in outcome.detail


def test_move_failure_has_no_measurement_target(ports, params):
    ports.override['to_origin_xy'] = MotionResult(reason=MotionReason.TIMEOUT)
    outcome = run(ports, params)
    assert outcome.reason_code == Reason.TIMEOUT
    assert ports.attempt_failures == []
    assert no_return_motion(ports)


def test_event_that_never_arrives_is_a_failure_not_a_silent_pass(ports, params):
    ports.drop_events.add('slide_POS_X')
    outcome = run(ports, params)
    assert outcome.kind is OutcomeKind.FAILED and outcome.reason_code == Reason.TIMEOUT
    assert 'event_id' in outcome.detail
    assert Direction.POS_X not in ports.edges
    assert ports.attempt_failures[0][0] is Direction.POS_X
    assert no_return_motion(ports)


def test_tare_failure_code_is_passed_through(ports, params):
    ports.tare_outcome = StepOutcome(False, int(Reason.TOOL_REG_SUSPECT), 'baseline 11.8 N')
    outcome = run(ports, params)
    assert outcome.reason_code == Reason.TOOL_REG_SUSPECT
    assert ports.sm.failure.phase is Phase.PREPARING
    assert ports.labels() == ['to_origin']


def test_tare_is_not_called_while_the_robot_is_not_confirmed_still(ports, params):
    ports.still = False
    outcome = run(ports, params)
    assert outcome.reason_code == Reason.ROBOT_MOVING
    assert ('tare',) not in ports.trace


def test_geometry_failure_does_not_return_home(ports, params):
    ports.geometry_outcome = StepOutcome(False, int(Reason.INVALID_SHAPE), 'GEOM_NEGATIVE_HEIGHT: ...')
    outcome = run(ports, params)
    assert outcome.kind is OutcomeKind.FAILED and outcome.reason_code == Reason.INVALID_SHAPE
    assert ports.sm.phase is Phase.ERROR and ports.sm.failure.phase is Phase.GEOMETRY
    assert no_return_motion(ports)


def test_final_homing_failure_keeps_the_measurement_result(ports, params):
    ports.override['home'] = MotionResult(reason=MotionReason.ROBOT_ERROR, reason_code=204)
    outcome = run(ports, params)
    assert outcome.kind is OutcomeKind.HOMING_FAILED and outcome.reason_code == Reason.ROBOT_ERROR
    assert ports.sm.phase is Phase.ERROR and ports.sm.failure.phase is Phase.HOMING
    assert ports.geometry.shape.success          # 측정 결과는 그대로 유효하다(7.4절)
    assert ports.attempt_failures == []


def test_compliance_not_released_stops_the_sequence(ports, params):
    ports.override['slide_POS_X'] = MotionResult(
        reason=MotionReason.EDGE, event_id=7, compliance_released=False)
    outcome = run(ports, params)
    assert outcome.kind is OutcomeKind.FAILED and outcome.reason_code == Reason.ROBOT_ERROR
    assert 'compliance_released=false' in outcome.detail
    assert ports.labels()[-1] == 'slide_POS_X'


@pytest.mark.parametrize('safety_code, expected', [
    (0, Reason.ROBOT_ERROR), (int(Reason.OVER_FORCE), Reason.OVER_FORCE)])
def test_stop_that_nobody_requested_is_a_failure(ports, params, safety_code, expected):
    def stopped_by_someone_else(_request):
        ports.safety_code = safety_code  # 모션 도중에 safety_monitor 가 래치를 걸고 로봇을 세웠다
        return MotionResult(reason=MotionReason.STOP_REQUESTED, reason_code=200)
    ports.override['slide_NEG_X'] = stopped_by_someone_else
    outcome = run(ports, params)
    assert outcome.kind is OutcomeKind.FAILED and outcome.reason_code == expected
    assert ports.sm.phase is Phase.ERROR
    assert no_return_motion(ports)


@pytest.mark.parametrize('latch_after, last_sent, failed_phase', [
    ('to_origin', 'to_origin', Phase.TOP_SEARCH),       # tare 중에 걸렸다 → 하강을 보내지 않는다
    ('descend', 'descend', Phase.EDGE_SEARCH),          # 윗면 기록 중 → 첫 밀기를 보내지 않는다
    ('slide_NEG_Y', 'slide_NEG_Y', Phase.HOMING),       # 형상 계산 중 → 마무리 복귀도 보내지 않는다
])
def test_latch_between_motions_blocks_the_next_motion(ports, params, latch_after, last_sent, failed_phase):
    ports.latch_after = latch_after
    outcome = run(ports, params)
    assert outcome.reason_code == Reason.OVER_FORCE and '안전 래치' in outcome.detail
    assert ports.labels()[-1] == last_sent
    assert ports.sm.phase is Phase.ERROR and ports.sm.failure.phase is failed_phase
    assert no_return_motion(ports)
    if failed_phase is Phase.HOMING:
        assert outcome.kind is OutcomeKind.HOMING_FAILED and ports.geometry.shape.success
    else:
        assert outcome.kind is OutcomeKind.FAILED
    assert ports.attempt_failures == []  # 탐색을 시도하지 않았으므로 '탐색 실패'로 적지 않는다


# ---- 작업 중지: 홈 복귀 · 재시작을 부르지 않는다 ----

def test_stop_during_motion_confirms_then_records_then_reports(ports, params):
    ports.stop_during = 'slide_NEG_X'

    outcome = run(ports, params)

    assert outcome.kind is OutcomeKind.STOPPED and outcome.reason_code == Reason.STOP_REQUESTED
    assert ports.sm.phase is Phase.STOPPED
    tail = ports.trace[-4:]
    assert tail == [
        ('execute', 'slide_NEG_X'), ('wait_still',), ('record_stop',),
        ('notify', Signal.STOP_CONFIRMED)]
    position, result, during_final_homing = ports.stop_record
    assert position == result.position and during_final_homing is False
    assert ports.failure is None


def test_stop_never_sends_another_motion(ports, params):
    ports.stop_during = 'slide_POS_X'
    run(ports, params)
    assert ports.labels()[-1] == 'slide_POS_X'
    assert no_return_motion(ports)
    # 중지 뒤에 남는 길은 관제자의 명령뿐이다: HOME · RESUME 은 아무도 부르지 않았다
    assert ports.sm.phase is Phase.STOPPED
    assert ports.sm.request(Command.HOME, conditions=READY).accepted


def test_stop_during_final_homing_is_marked(ports, params):
    ports.stop_during = 'home'
    outcome = run(ports, params)
    assert outcome.kind is OutcomeKind.STOPPED
    assert ports.stop_record[2] is True
    assert ports.geometry.shape.success


def test_stop_that_cannot_be_confirmed_is_an_error(ports, params):
    ports.stop_during = 'descend'
    ports.still = None  # 준비 단계의 정지 확인은 통과시키고, 중지 확인만 실패시킨다

    calls = iter([True, False])
    ports.wait_still = lambda: next(calls)
    outcome = run(ports, params)
    assert outcome.kind is OutcomeKind.FAILED and outcome.reason_code == Reason.ROBOT_STATUS_LOST
    assert ports.sm.phase is Phase.ERROR
    assert ports.stop_record is None


def test_measurement_that_arrives_after_stop_is_not_recorded(ports, params):
    ports.stop_after_event = 'slide_POS_Y'
    outcome = run(ports, params)
    assert outcome.kind is OutcomeKind.STOPPED
    assert Direction.POS_Y not in ports.edges
    assert ports.sm.snapshot().progress == 2
    assert any('중지 접수 뒤' in message for message in ports.infos)


def test_stop_between_record_and_notify_goes_to_the_stop_path(ports, params):
    ports.stop_before_notify = Signal.TOP_FOUND
    outcome = run(ports, params)
    assert outcome.kind is OutcomeKind.STOPPED
    assert ('notify_refused', Signal.TOP_FOUND) in ports.trace
    assert ports.labels() == ['to_origin', 'descend']


def test_stop_before_the_first_motion_sends_nothing(ports, params):
    ports.request_stop()
    outcome = run(ports, params)
    assert outcome.kind is OutcomeKind.STOPPED
    assert ports.labels() == []
    assert ports.stop_record == (None, None, False)


# ---- 안전복귀 ----

def home_ports(params):
    ports = FakePorts(params)
    ports.request_stop()
    ports.sm.notify(Signal.STOP_CONFIRMED)
    ports._stop = False
    assert ports.sm.request(Command.HOME, conditions=READY).accepted
    return ports


def test_run_home_sends_one_home_motion(params):
    ports = home_ports(params)
    outcome = run_home(MotionPlanner(params), ports, first_motion_id=8)
    assert outcome.kind is OutcomeKind.DONE
    assert [(m, r.operation) for m, r in ports.requests] == [(8, Operation.HOME)]
    assert ports.sm.phase is Phase.STOPPED  # 안전복귀는 출발했던 phase 로 돌아간다


def test_run_home_failure_and_stop(params):
    failing = home_ports(params)
    failing.override['home'] = MotionResult(accepted=False)
    assert run_home(MotionPlanner(params), failing).kind is OutcomeKind.FAILED
    assert failing.sm.phase is Phase.ERROR

    stopping = home_ports(params)
    stopping.stop_during = 'home'
    assert run_home(MotionPlanner(params), stopping).kind is OutcomeKind.STOPPED
    assert stopping.sm.phase is Phase.STOPPED


def test_latch_does_not_block_the_operator_home(params):
    ports = home_ports(params)
    ports.safety_code = int(Reason.OVER_FORCE)  # 래치 중이다
    outcome = run_home(MotionPlanner(params), ports)
    assert outcome.kind is OutcomeKind.DONE and ports.labels() == ['home']


# ---- classify · planner ----

DESCEND = MotionRequest(Operation.DESCEND, 'descend', speed=0.004, max_distance=0.09)
SLIDE = MotionRequest(Operation.SLIDE, 'slide', speed=0.01, direction=Direction.POS_X, max_distance=0.1)
MOVE = MotionRequest(Operation.MOVE_TO, 'move', speed=0.05, target_position=(0, 0, 0))


@pytest.mark.parametrize('request_, result, kind, code', [
    (MOVE, MotionResult(reason=MotionReason.TARGET_REACHED), VerdictKind.REACHED, 0),
    (DESCEND, MotionResult(reason=MotionReason.CONTACT, event_id=3), VerdictKind.MEASURED, 0),
    (SLIDE, MotionResult(reason=MotionReason.EDGE, event_id=4), VerdictKind.MEASURED, 0),
    (DESCEND, MotionResult(reason=MotionReason.CONTACT, event_id=0), VerdictKind.FAILED, 204),
    (DESCEND, MotionResult(reason=MotionReason.EDGE, event_id=5), VerdictKind.FAILED, 204),
    (SLIDE, MotionResult(reason=MotionReason.CONTACT, event_id=5), VerdictKind.FAILED, 204),
    (DESCEND, MotionResult(reason=MotionReason.TARGET_REACHED), VerdictKind.FAILED, 204),
    (MOVE, MotionResult(reason=MotionReason.MAX_DISTANCE), VerdictKind.FAILED, 204),
    (MOVE, MotionResult(reason=MotionReason.REJECTED, reason_code=101), VerdictKind.FAILED, 101),
    (MOVE, MotionResult(reason=None), VerdictKind.FAILED, 204),
])
def test_classify(request_, result, kind, code):
    verdict = classify(request_, result, stop_requested=False)
    assert (verdict.kind, verdict.reason_code) == (kind, code)


@pytest.mark.parametrize('reason', [
    MotionReason.STOP_REQUESTED, MotionReason.CANCELED, MotionReason.EDGE])
def test_classify_stop_wins_over_a_motion_that_ended_well(reason):
    verdict = classify(SLIDE, MotionResult(reason=reason, event_id=9), stop_requested=True)
    assert verdict.kind is VerdictKind.STOPPED
    reached = classify(MOVE, MotionResult(reason=MotionReason.TARGET_REACHED), stop_requested=True)
    assert reached.kind is VerdictKind.STOPPED


@pytest.mark.parametrize('result, code', [
    (MotionResult(reason=MotionReason.OVER_FORCE), Reason.OVER_FORCE),
    (MotionResult(reason=MotionReason.ROBOT_ERROR, reason_code=205), Reason.DROP_LIMIT),
    (MotionResult(reason=MotionReason.REJECTED), Reason.ROBOT_ERROR),
    (MotionResult(reason=MotionReason.MAX_DISTANCE), Reason.NO_EDGE),
    (MotionResult(reason=MotionReason.TIMEOUT), Reason.TIMEOUT),
    (MotionResult(reason=MotionReason.STOP_REQUESTED, compliance_released=False), Reason.ROBOT_ERROR),
    (MotionResult(accepted=False), Reason.ROBOT_ERROR),
])
def test_classify_a_failure_is_not_hidden_by_a_stop_request(result, code):
    verdict = classify(SLIDE, result, stop_requested=True)
    assert (verdict.kind, verdict.reason_code) == (VerdictKind.FAILED, code)


def test_failure_during_stop_ends_in_error_not_stopped(ports, params):
    def over_force_while_stopping(_request):
        ports.request_stop()
        return MotionResult(reason=MotionReason.OVER_FORCE, reason_code=400, position=(0.41, 0.0, 0.04))
    ports.override['slide_POS_X'] = over_force_while_stopping
    outcome = run(ports, params)
    assert outcome.kind is OutcomeKind.FAILED and outcome.reason_code == Reason.OVER_FORCE
    assert ports.sm.phase is Phase.ERROR and ports.stop_record is None
    assert no_return_motion(ports)


def test_planner_uses_parameters_only(params):
    planner = MotionPlanner(params)
    descend, slide, home = planner.descend(), planner.slide(Direction.NEG_Y), planner.home()
    assert (descend.speed, descend.max_distance) == (params.descend_speed_mps, params.max_descend_m)
    assert (slide.speed, slide.max_distance) == (params.slide_speed_mps, params.max_slide_m)
    assert slide.direction is Direction.NEG_Y
    assert home.speed is None and home.target_position is None
    assert planner.to_origin().target_position == params.origin_position
    assert {r.timeout_s for r in (descend, slide, home, planner.to_origin())} == {
        params.motion_timeout_s}
    assert planner.lift((0.1, 0.2, 0.3)).target_position == pytest.approx(
        (0.1, 0.2, 0.3 + params.lift_height_m))


def test_motion_id_must_start_at_one_or_above(ports, params):
    with pytest.raises(ValueError):
        ScanRunner(MotionPlanner(params), ports, params.direction_order, first_motion_id=0)
