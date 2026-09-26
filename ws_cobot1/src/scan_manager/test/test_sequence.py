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
from scan_manager.sequence import damage_suspect_reason
from scan_manager.sequence import MotionPlanner
from scan_manager.sequence import MotionRequest
from scan_manager.sequence import MotionResult
from scan_manager.sequence import OutcomeKind
from scan_manager.sequence import ResumePlan
from scan_manager.sequence import ResumeRunner
from scan_manager.sequence import run_home
from scan_manager.sequence import ScanRunner
from scan_manager.sequence import StepOutcome
from scan_manager.sequence import TOP
from scan_manager.sequence import VerdictKind
from scan_manager.state_machine import Command
from scan_manager.state_machine import Failure
from scan_manager.state_machine import Signal
from sequence_helpers import BOX_SIZE
from sequence_helpers import DOWN
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
    # 404(상태가 안 온다)와 섞지 않는다. 407 = 정지를 요청했는데 완료를 확인하지 못했다 (계약 6.1)
    assert outcome.kind is OutcomeKind.FAILED and outcome.reason_code == Reason.STOP_UNCONFIRMED
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


def test_run_home_lifts_before_home(params):
    """계약 7.5: 수직 올림 → 도착 확인 → HOME. 올림은 x · y 와 자세를 바꾸지 않는다."""
    ports = home_ports(params)
    before = ports.position
    outcome = run_home(MotionPlanner(params), ports, first_motion_id=8)
    assert outcome.kind is OutcomeKind.DONE
    assert [(m, r.operation) for m, r in ports.requests] == [
        (8, Operation.MOVE_TO), (9, Operation.HOME)]
    lift = ports.requests[0][1]
    assert lift.label == 'home_lift'
    assert lift.target_position == (before[0], before[1], before[2] + params.lift_height_m)
    assert lift.target_orientation == DOWN          # 기준점 자세가 아니라 지금 자세 그대로
    assert ports.sm.phase is Phase.STOPPED  # 안전복귀는 출발했던 phase 로 돌아간다


def test_run_home_does_not_send_home_when_the_lift_fails(params):
    """올림이 도착으로 끝나지 않으면 HOME 을 보내지 않는다 (#130 에서 2회 나갔다)."""
    for injected in (MotionResult(accepted=False),
                     MotionResult(reason=MotionReason.TIMEOUT, reason_code=int(Reason.TIMEOUT)),
                     MotionResult(reason=MotionReason.ROBOT_ERROR,
                                  reason_code=int(Reason.ROBOT_ERROR))):
        ports = home_ports(params)
        ports.override['home_lift'] = injected
        outcome = run_home(MotionPlanner(params), ports)
        assert outcome.kind is OutcomeKind.FAILED
        assert ports.labels() == ['home_lift']      # HOME 은 없다
        assert ports.sm.phase is Phase.ERROR


def test_run_home_refuses_when_the_position_is_unknown(params):
    """위치를 모르면 올림도 HOME 도 하지 않는다. 사람이 펜던트로 조그한다 (계약 7.5 ①)."""
    ports = home_ports(params)
    ports.position = None
    outcome = run_home(MotionPlanner(params), ports)
    assert outcome.kind is OutcomeKind.FAILED and outcome.reason_code == Reason.NOT_SUPPORTED
    assert ports.requests == []                     # 모션을 하나도 보내지 않았다
    assert '조그' in outcome.detail
    assert ports.sm.phase is Phase.ERROR


@pytest.mark.parametrize('code', [Reason.OVER_FORCE, Reason.DROP_LIMIT, Reason.OUT_OF_WORKSPACE])
def test_run_home_refuses_after_a_damage_suspect_failure(params, code):
    """손상 가능 사유로 끝났으면 자동복귀하지 않는다 (계약 7.5 ②)."""
    ports = home_ports(params)
    ports.damage_reason = damage_suspect_reason(
        Failure(int(code), 'detail', Phase.EDGE_SEARCH))
    assert ports.damage_reason                      # 이 사유들은 실제로 막는다
    outcome = run_home(MotionPlanner(params), ports)
    assert outcome.kind is OutcomeKind.FAILED and outcome.reason_code == Reason.NOT_SUPPORTED
    assert ports.requests == []
    assert ports.sm.phase is Phase.ERROR


@pytest.mark.parametrize('code', [Reason.TIMEOUT, Reason.NO_CONTACT, Reason.SAMPLE_STALE,
                                  Reason.STOP_UNCONFIRMED, Reason.ROBOT_ERROR])
def test_ordinary_failures_do_not_block_the_home_return(params, code):
    """접촉이 원인이 아닌 실패는 안전복귀를 막지 않는다. 전부 막으면 복귀 수단이 사라진다."""
    assert damage_suspect_reason(Failure(int(code), '', Phase.EDGE_SEARCH)) == ''


def test_no_failure_means_no_block(params):
    """정상 중지(STOPPED)에는 failure 가 없다. 평소 안전복귀 경로는 그대로다."""
    assert damage_suspect_reason(None) == ''


def test_run_home_failure_and_stop(params):
    failing = home_ports(params)
    failing.override['home'] = MotionResult(accepted=False)
    assert run_home(MotionPlanner(params), failing).kind is OutcomeKind.FAILED
    assert failing.sm.phase is Phase.ERROR

    stopping = home_ports(params)
    stopping.stop_during = 'home'
    assert run_home(MotionPlanner(params), stopping).kind is OutcomeKind.STOPPED
    assert stopping.sm.phase is Phase.STOPPED

    # 올림 도중의 중지도 STOPPED 다(실패가 아니다). HOME 은 나가지 않는다
    lifting = home_ports(params)
    lifting.stop_during = 'home_lift'
    assert run_home(MotionPlanner(params), lifting).kind is OutcomeKind.STOPPED
    assert lifting.labels() == ['home_lift'] and lifting.sm.phase is Phase.STOPPED


def test_latch_does_not_block_the_operator_home(params):
    ports = home_ports(params)
    ports.safety_code = int(Reason.OVER_FORCE)  # 래치 중이다
    outcome = run_home(MotionPlanner(params), ports)
    # 올림도 래치를 보지 않는다 — 래치 때문에 돌아오지 못하면 안 된다(계약 7.5)
    assert outcome.kind is OutcomeKind.DONE and ports.labels() == ['home_lift', 'home']


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


@pytest.mark.parametrize('stop_code, latched, expected', [
    # safety_monitor 가 /robot/stop 에 실은 사유가 Result.reason_code 로 돌아온다. 그것이 1순위다
    # latched=0 은 사람이 /safety/reset 을 먼저 누른 경우다. 래치만 보면 여기서 204 로 샌다
    (205, 0, Reason.DROP_LIMIT),
    (400, 0, Reason.OVER_FORCE),
    # Result 가 사유를 모르면 그때 래치를 본다
    (200, 205, Reason.DROP_LIMIT),
    (201, 400, Reason.OVER_FORCE),
    (0, 205, Reason.DROP_LIMIT),
    # 둘 다 없으면 그제서야 ROBOT_ERROR
    (200, 0, Reason.ROBOT_ERROR),
    (0, 0, Reason.ROBOT_ERROR),
])
def test_classify_unrequested_stop_prefers_the_result_reason_code(stop_code, latched, expected):
    """요청하지 않은 정지의 사유는 Result.reason_code → 래치 → ROBOT_ERROR 순으로 본다 (계약 7.5)."""
    result = MotionResult(reason=MotionReason.STOP_REQUESTED, reason_code=stop_code)
    verdict = classify(SLIDE, result, stop_requested=False, safety_reason_code=latched)
    assert (verdict.kind, verdict.reason_code) == (VerdictKind.FAILED, expected)


def test_classify_our_own_stop_is_still_a_stop_even_with_a_reason_code():
    """우리가 요청한 중지는 그대로 STOPPED 다. 1순위 규칙이 이것을 실패로 바꾸면 안 된다."""
    result = MotionResult(reason=MotionReason.STOP_REQUESTED, reason_code=205)
    verdict = classify(SLIDE, result, stop_requested=True, safety_reason_code=205)
    assert (verdict.kind, verdict.reason_code) == (VerdictKind.STOPPED, Reason.STOP_REQUESTED)


@pytest.mark.parametrize('code', [Reason.OVER_FORCE, Reason.DROP_LIMIT, Reason.OUT_OF_WORKSPACE])
def test_damage_suspect_also_reads_the_current_latch(code):
    """실패 기록이 사유를 놓쳐 204 로 남아도, 래치 사유가 손상 의심이면 자동복귀를 막는다."""
    failure = Failure(int(Reason.ROBOT_ERROR), 'detail', Phase.EDGE_SEARCH)
    assert damage_suspect_reason(failure) == ''            # 실패만 보면 못 막는다
    assert damage_suspect_reason(failure, int(code))       # 래치를 같이 보면 막는다
    assert damage_suspect_reason(None, int(code))          # 실패 기록이 아예 없어도 막는다


@pytest.mark.parametrize('code', [Reason.SAFETY_LATCHED, Reason.HB_EXPIRED, Reason.SAMPLE_STALE])
def test_a_latch_that_is_not_a_damage_reason_does_not_block_the_home_return(code):
    """막는 것은 래치가 걸렸다는 사실이 아니라 **사유**다 (T10: 래치는 안전복귀를 막지 않는다)."""
    assert damage_suspect_reason(None, int(code)) == ''


def test_run_home_refuses_when_only_the_latch_says_damage(params):
    """기록은 204 인데 래치가 400 인 경우. 종단으로 막히는지 본다."""
    ports = home_ports(params)
    ports.damage_reason = damage_suspect_reason(
        Failure(int(Reason.ROBOT_ERROR), 'detail', Phase.EDGE_SEARCH), int(Reason.OVER_FORCE))
    outcome = run_home(MotionPlanner(params), ports)
    assert outcome.kind is OutcomeKind.FAILED and outcome.reason_code == Reason.NOT_SUPPORTED
    assert ports.requests == []                            # 올림도 보내지 않는다


def test_resume_lifts_from_where_the_robot_is_now_not_from_the_record(ports, params):
    """계약 7.6: 중단 뒤 사람이 옮겼으면 기록 좌표로 되돌아가면 안 된다."""
    stopped_at(ports, params, NORMAL_LABELS.index('slide_POS_X') + 1)
    recorded = ports.position
    moved = (recorded[0] + 0.03, recorded[1] - 0.02, recorded[2] + 0.01)
    ports.position = moved                                 # 사람이 펜던트로 조그했다
    mark = len(ports.requests)
    resume(ports, params)
    lift = next(r for _, r in ports.requests[mark:] if r.label == 'resume_lift')
    assert lift.target_position[:2] == moved[:2]           # 지금 자리의 x · y 다
    assert lift.target_position[2] == pytest.approx(moved[2] + params.lift_height_m)
    assert lift.target_position[:2] != recorded[:2]        # 기록 좌표가 아니다


@pytest.mark.parametrize('n', [1, 2])
def test_resume_before_the_top_lifts_vertically_before_moving_sideways(ports, params, n):
    """계약 7.6: to_origin 은 직선이라 출발부터 옆으로 간다. 팁이 닿아 있으면 긁는다.

    n=1 준비 중 중지 · n=2 하강 중 중지. 둘 다 첫 모션이 수직 올림이어야 한다.
    """
    stopped_at(ports, params, n)
    here = ports.position
    mark = len(ports.requests)
    resume(ports, params)
    first = ports.requests[mark][1]
    assert first.label == 'resume_lift'
    assert first.target_position[:2] == here[:2]          # x · y 를 바꾸지 않는다
    assert first.target_position[2] == pytest.approx(here[2] + params.lift_height_m)


def test_resume_refuses_when_the_position_is_unknown(ports, params):
    """위치를 모르면 첫 모션을 보내지 않는다 (계약 7.6). 절대 좌표 이동은 눈을 감고 하는 것이다."""
    stopped_at(ports, params, NORMAL_LABELS.index('slide_POS_X') + 1)
    ports.position = None
    mark = len(ports.requests)
    outcome = resume(ports, params)
    assert outcome.kind is OutcomeKind.FAILED and outcome.reason_code == Reason.NOT_SUPPORTED
    assert ports.requests[mark:] == []                     # 모션이 한 번도 나가지 않는다


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


# ---- 재시작 (T26) ----
# 준비는 방향 전환(7.3절)과 같은 절차다: 올림 → 정지 확인 → tare → 기준 원점에서 다시 닿기 → 그 방향을 처음부터.

NORMAL_LABELS = ['to_origin', 'descend', 'slide_POS_X']
for _direction in ORDER[1:]:
    NORMAL_LABELS += CHANGE + [f'slide_{_direction.name}']
MEASURING = len(NORMAL_LABELS)            # 여기까지가 측정. 그 뒤는 마무리 복귀
NORMAL_LABELS += ['final_lift', 'home']
RESUME_APPROACH = ['resume_lift', 'to_origin_xy', 'recontact']


def resume(ports, params):
    plan = ports.resume()
    first = max(motion_id for motion_id, _ in ports.requests) + 1 if ports.requests else 1
    return ResumeRunner(
        MotionPlanner(params), ports, params.direction_order, plan, first_motion_id=first).run()


def stopped_at(ports, params, n):
    ports.stop_at_request = n
    assert run(ports, params).kind is OutcomeKind.STOPPED
    assert ports.sm.phase is Phase.STOPPED


def assert_box_recovered(ports):
    shape = ports.geometry.shape
    assert shape.success
    assert (shape.width, shape.length, shape.height) == pytest.approx(BOX_SIZE, abs=1e-9)


def test_resume_after_stop_in_the_first_slide_keeps_the_top_and_continues(ports, params):
    stopped_at(ports, params, NORMAL_LABELS.index('slide_POS_X') + 1)
    top_before, stop_position = ports.top, ports.stop_record[0]

    outcome = resume(ports, params)

    assert outcome.kind is OutcomeKind.DONE and ports.sm.phase is Phase.DONE
    assert ports.top is top_before                        # 윗면은 다시 재지 않는다(BRD TR-08)
    assert ports.labels_since_resume() == (
        RESUME_APPROACH + NORMAL_LABELS[NORMAL_LABELS.index('slide_POS_X'):])
    lift = ports.requests[ports.resumed_at_request][1]
    assert lift.target_position == pytest.approx(
        (stop_position[0], stop_position[1], stop_position[2] + params.lift_height_m))
    assert_box_recovered(ports)


def test_resume_preparation_lifts_then_confirms_still_then_tares_before_it_is_ready(ports, params):
    stopped_at(ports, params, NORMAL_LABELS.index('slide_POS_X') + 1)
    mark = len(ports.trace)
    resume(ports, params)
    head = ports.trace[mark:mark + 6]
    assert head == [
        ('current_pose',),                                # 7.6: 어디 있는지 먼저 묻는다
        ('execute', 'resume_lift'), ('wait_still',), ('tare',),
        ('notify', Signal.RESUME_READY), ('execute', 'to_origin_xy')]


@pytest.mark.parametrize('n', range(1, MEASURING + 1))
def test_resume_from_every_measuring_motion_finishes_without_measuring_twice(ports, params, n):
    stopped_at(ports, params, n)
    top_before, edges_before = ports.top, dict(ports.edges)

    outcome = resume(ports, params)

    assert outcome.kind is OutcomeKind.DONE
    since = ports.labels_since_resume()
    assert ('descend' in since) == (top_before is None)
    for direction in ORDER:                               # 확정된 방향에는 모션이 한 번도 나가지 않는다
        assert (f'slide_{direction.name}' in since) == (direction not in edges_before)
    assert ports.top is top_before or top_before is None
    assert all(ports.edges[d] is edges_before[d] for d in edges_before)
    assert since[-2:] == ['final_lift', 'home'] and 'home' not in since[:-1]
    ids = [motion_id for motion_id, _ in ports.requests]
    assert ids == list(range(1, len(ids) + 1))            # 같은 scan 안에서 되풀이되지 않는다
    assert_box_recovered(ports)


def test_resume_from_preparing_starts_over_from_the_origin(ports, params):
    stopped_at(ports, params, 1)
    mark = len(ports.trace)
    resume(ports, params)
    assert ports.trace[mark] == ('current_pose',)                 # 7.6: 첫 모션 전에 위치부터 확인한다
    assert ports.trace[mark + 1] == ('execute', 'resume_lift')    # 7.6: 움직인다면 첫 모션은 수직 올림
    assert ports.trace[mark + 2] == ('notify', Signal.RESUME_READY)  # 그 뒤엔 준비할 것이 없다. PREPARING 이 기준점 · tare 를 한다
    assert ports.labels_since_resume()[:3] == ['resume_lift', 'to_origin', 'descend']


def test_resume_from_the_descent_goes_back_up_and_tares_in_the_air(ports, params):
    stopped_at(ports, params, 2)
    mark = len(ports.trace)
    resume(ports, params)
    assert ports.trace[mark:mark + 7] == [
        ('current_pose',),                                # 7.6: 어디 있는지 먼저 묻는다
        ('execute', 'resume_lift'),                       # 7.6: 옆으로 옮기기 전에 띄운다
        ('execute', 'to_origin'), ('wait_still',), ('tare',),
        ('notify', Signal.RESUME_READY), ('execute', 'descend')]


@pytest.mark.parametrize('label', CHANGE)
def test_resume_from_a_direction_change_redoes_it_from_where_the_robot_is(ports, params, label):
    stopped_at(ports, params, NORMAL_LABELS.index(label) + 1)
    assert set(ports.edges) == {Direction.POS_X}
    resume(ports, params)
    assert ports.labels_since_resume()[:4] == RESUME_APPROACH + ['slide_NEG_X']


@pytest.mark.parametrize('signal, n, phase, progress', [
    (Signal.TOP_FOUND, 1, Phase.TOP_SEARCH, 0),
    (Signal.EDGE_FOUND, 1, Phase.EDGE_SEARCH, 0),
    (Signal.EDGE_FOUND, 3, Phase.EDGE_SEARCH, 2),
])
def test_measurement_recorded_but_not_notified_is_not_measured_again(
        ports, params, signal, n, phase, progress):
    ports.stop_before_notify = (signal, n)
    assert run(ports, params).kind is OutcomeKind.STOPPED
    assert (ports.resume_point.phase, ports.resume_point.progress) == (phase, progress)
    top_before, edges_before = ports.top, dict(ports.edges)
    assert len(edges_before) == (0 if signal is Signal.TOP_FOUND else progress + 1)   # 기록이 한 칸 앞서 있다

    assert resume(ports, params).kind is OutcomeKind.DONE

    since = ports.labels_since_resume()
    assert 'descend' not in since and ports.top is top_before
    assert all(f'slide_{d.name}' not in since for d in edges_before)
    assert all(ports.edges[d] is edges_before[d] for d in edges_before)
    assert any('기록에 확정돼 있다' in message for message in ports.infos)
    assert_box_recovered(ports)


def test_last_edge_recorded_but_not_notified_goes_straight_to_geometry(ports, params):
    ports.stop_before_notify = (Signal.EDGE_FOUND, 4)
    run(ports, params)
    assert resume(ports, params).kind is OutcomeKind.DONE
    assert ports.labels_since_resume() == ['final_lift', 'home']
    assert_box_recovered(ports)


def test_result_saved_before_the_stop_is_republished_not_recomputed(ports, params):
    ports.stop_before_notify = Signal.GEOMETRY_DONE
    run(ports, params)
    assert ports.resume_point.phase is Phase.GEOMETRY and ports.geometry is not None
    computed = ports.trace.count(('compute_geometry',))

    assert resume(ports, params).kind is OutcomeKind.DONE

    assert ports.republished == 1 and ports.trace.count(('compute_geometry',)) == computed
    assert ports.labels_since_resume() == ['final_lift', 'home']


def test_stop_in_geometry_before_the_result_exists_computes_it_from_the_kept_measurements(ports, params):
    ports.stop_after_notify = (Signal.EDGE_FOUND, 4)          # GEOMETRY 에 들어선 직후 · 계산 전
    assert run(ports, params).kind is OutcomeKind.STOPPED
    assert ports.resume_point.phase is Phase.GEOMETRY and ports.geometry is None
    edges_before = dict(ports.edges)

    assert resume(ports, params).kind is OutcomeKind.DONE

    assert ports.trace.count(('compute_geometry',)) == 1 and ports.republished == 0
    assert ports.labels_since_resume() == ['final_lift', 'home']
    assert all(ports.edges[d] is edges_before[d] for d in edges_before)
    assert_box_recovered(ports)


def test_stop_during_resume_preparation_can_be_resumed_again(ports, params):
    stopped_at(ports, params, NORMAL_LABELS.index('slide_NEG_X') + 1)
    plan = ports.resume()
    ports.stop_during = 'resume_lift'
    first = len(ports.requests) + 1
    outcome = ResumeRunner(
        MotionPlanner(params), ports, params.direction_order, plan, first_motion_id=first).run()
    assert outcome.kind is OutcomeKind.STOPPED and ports.sm.phase is Phase.STOPPED
    assert ports.resume_point.phase is Phase.EDGE_SEARCH      # RESUMING 중의 중지는 재개 지점을 바꾸지 않는다
    assert ports.labels()[-1] == 'resume_lift'                # 중지 뒤에 모션을 보내지 않는다

    assert resume(ports, params).kind is OutcomeKind.DONE
    assert 'slide_POS_X' not in ports.labels_since_resume()
    assert_box_recovered(ports)


def test_stop_before_the_first_resume_motion_keeps_the_known_stop_position(ports, params):
    stopped_at(ports, params, NORMAL_LABELS.index('slide_POS_X') + 1)
    stop_position = ports.stop_record[0]
    plan = ports.resume()
    ports.request_stop()
    sent = len(ports.requests)

    outcome = ResumeRunner(
        MotionPlanner(params), ports, params.direction_order, plan, first_motion_id=sent + 1).run()

    assert outcome.kind is OutcomeKind.STOPPED and len(ports.requests) == sent
    assert ports.stop_record[0] == stop_position              # 로봇은 움직이지 않았다


def test_stop_then_resume_twice_in_different_directions(ports, params):
    stopped_at(ports, params, NORMAL_LABELS.index('slide_POS_X') + 1)
    ports.stop_at_request = None
    plan = ports.resume()
    ports.stop_during = 'slide_POS_Y'
    first = len(ports.requests) + 1
    outcome = ResumeRunner(
        MotionPlanner(params), ports, params.direction_order, plan, first_motion_id=first).run()
    assert outcome.kind is OutcomeKind.STOPPED
    assert (ports.resume_point.phase, ports.resume_point.progress) == (Phase.EDGE_SEARCH, 2)

    assert resume(ports, params).kind is OutcomeKind.DONE
    assert ports.labels_since_resume()[:4] == RESUME_APPROACH + ['slide_POS_Y']
    assert_box_recovered(ports)


def test_latch_blocks_the_first_resume_motion(ports, params):
    stopped_at(ports, params, NORMAL_LABELS.index('slide_POS_X') + 1)
    plan = ports.resume()
    ports.safety_code = 400
    sent = len(ports.requests)
    outcome = ResumeRunner(
        MotionPlanner(params), ports, params.direction_order, plan, first_motion_id=sent + 1).run()
    assert (outcome.kind, outcome.reason_code) == (OutcomeKind.FAILED, 400)
    assert len(ports.requests) == sent and ports.sm.phase is Phase.ERROR


def test_resume_preparation_failure_is_an_error_and_never_returns_home(ports, params):
    stopped_at(ports, params, NORMAL_LABELS.index('slide_POS_X') + 1)
    ports.tare_outcome = StepOutcome(False, int(Reason.TARE_UNSTABLE), 'fake')
    outcome = resume(ports, params)
    assert (outcome.kind, outcome.reason_code) == (OutcomeKind.FAILED, Reason.TARE_UNSTABLE)
    assert ports.sm.phase is Phase.ERROR and ports.labels_since_resume() == ['resume_lift']


def test_stop_during_final_homing_is_not_resumable(ports, params):
    stopped_at(ports, params, MEASURING + 1)
    assert ports.stop_record[2] is True
    outcome = ports.sm.request(Command.RESUME, conditions=READY)
    assert not outcome.accepted and outcome.reason is Reason.NO_RESUMABLE_SCAN


@pytest.mark.parametrize('fields', [
    {'phase': Phase.HOMING},
    {'phase': Phase.EDGE_SEARCH, 'first_contact_z': None},
    {'phase': Phase.PREPARING, 'first_contact_z': 0.04, 'position': (0.4, 0.0, 0.04)},
    {'first_contact_z': 0.04, 'position': None},
    {'first_contact_z': 0.04, 'confirmed': ORDER[:3], 'progress': 1},
    {'first_contact_z': 0.04, 'confirmed': (), 'progress': 1},
    {'phase': Phase.GEOMETRY, 'first_contact_z': 0.04, 'confirmed': ORDER, 'progress': 3},
    {'first_contact_z': 0.04, 'result_saved': True},
])
def test_resume_plan_rejects_facts_that_contradict_each_other(fields):
    base = {
        'phase': Phase.EDGE_SEARCH, 'progress': 0, 'confirmed': (), 'first_contact_z': None,
        'position': (0.41, 0.0, 0.04)}
    with pytest.raises(ValueError):
        ResumePlan(**{**base, **fields})


def test_confirmed_directions_must_be_the_head_of_the_search_order(ports, params):
    plan = ResumePlan(
        phase=Phase.EDGE_SEARCH, progress=1, confirmed=(Direction.NEG_X,), first_contact_z=0.04,
        position=(0.41, 0.0, 0.04))
    with pytest.raises(ValueError):
        ResumeRunner(MotionPlanner(params), ports, params.direction_order, plan)
