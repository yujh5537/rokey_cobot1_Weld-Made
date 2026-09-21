"""작업 중지 · 안전복귀 · 재시작의 독립성과 거절 사유 (계약 4.1 · 4.3 · 5.1~5.3 · 7.4절)."""

from conftest import drive
from conftest import FRESH_STATUS
from conftest import READY
import pytest
from scan_manager.contract_enums import Direction
from scan_manager.contract_enums import Phase
from scan_manager.contract_enums import Reason
from scan_manager.state_machine import ACTIVE_PHASES
from scan_manager.state_machine import Command
from scan_manager.state_machine import COMMAND_TRANSITIONS
from scan_manager.state_machine import Conditions
from scan_manager.state_machine import InvalidTransition
from scan_manager.state_machine import REST_PHASES
from scan_manager.state_machine import ScanStateMachine
from scan_manager.state_machine import Signal
from scan_manager.state_machine import SIGNAL_TRANSITIONS
from scan_manager.state_machine import status_stale

LATCHED = Conditions(robot_connected=True, safety_latched=True, **FRESH_STATUS)
DISCONNECTED = Conditions(robot_connected=False, safety_latched=False, **FRESH_STATUS)
UNKNOWN = Conditions()   # 상태를 한 번도 받지 못했다(나이 · 한계도 없다)


def stopped_at(steps):
    """정상 경로를 steps 만큼 간 뒤 중지 · 정지 완료 확인까지."""
    sm = drive(ScanStateMachine(), steps)
    assert sm.request(Command.STOP).accepted
    sm.notify(Signal.STOP_CONFIRMED)
    assert sm.phase is Phase.STOPPED
    return sm


# ---- 세 명령은 독립이다 (CLAUDE.md 절대 규칙 3, 계약 1장) ----

def test_stopping_has_no_path_to_home_resume_or_restart():
    """STOPPING 에서 갈 수 있는 곳은 STOPPED · ERROR · (멱등) STOPPING 뿐이다."""
    reachable = set()
    for table in (COMMAND_TRANSITIONS, SIGNAL_TRANSITIONS):
        for by_phase in table.values():
            reachable |= by_phase.get(Phase.STOPPING, frozenset())
    assert reachable == {Phase.STOPPING, Phase.STOPPED, Phase.ERROR}


def test_stop_command_only_targets_stopping_or_stays():
    for phase, targets in COMMAND_TRANSITIONS[Command.STOP].items():
        assert targets in (frozenset({Phase.STOPPING}), frozenset({phase}))


def test_stopped_has_no_signal_driven_exit():
    """STOPPED 를 떠나는 길은 관제자 명령(START · HOME · RESUME)뿐이다."""
    for by_phase in SIGNAL_TRANSITIONS.values():
        assert Phase.STOPPED not in by_phase


def test_stop_does_not_home_or_resume_by_itself():
    seen = []
    sm = drive(ScanStateMachine(on_change=seen.append), 3)
    del seen[:]
    sm.request(Command.STOP)
    sm.notify(Signal.STOP_CONFIRMED)
    assert [s.phase for s in seen] == [Phase.STOPPING, Phase.STOPPED]
    for signal in (Signal.HOMING_DONE, Signal.RESUME_READY, Signal.PREPARE_DONE):
        with pytest.raises(InvalidTransition):
            sm.notify(signal)
    assert sm.phase is Phase.STOPPED


def test_stop_confirmation_is_required_for_stopped():
    sm = drive(ScanStateMachine(), 2)
    outcome = sm.request(Command.STOP)
    assert outcome.accepted and outcome.state.phase is Phase.STOPPING  # 접수 ≠ 완료


@pytest.mark.parametrize('command', [Command.START, Command.HOME, Command.RESUME,
                                     Command.SET_CONFIG])
def test_everything_but_stop_is_busy_while_stopping(command):
    sm = drive(ScanStateMachine(), 2)
    sm.request(Command.STOP)
    outcome = sm.request(command, conditions=READY, scan_id='20260918-220000-0002')
    assert (outcome.accepted, outcome.reason) == (False, Reason.BUSY)


def test_stop_is_idempotent():
    sm = drive(ScanStateMachine(), 2)
    assert sm.request(Command.STOP).changed
    again = sm.request(Command.STOP)
    assert again.accepted and not again.changed
    assert again.state.phase is Phase.STOPPING


@pytest.mark.parametrize('steps', [None, 8])
def test_stop_with_nothing_to_stop_is_accepted_without_change(steps):
    sm = ScanStateMachine() if steps is None else drive(ScanStateMachine(), steps)
    before = sm.snapshot()
    outcome = sm.request(Command.STOP)
    assert outcome.accepted and not outcome.changed
    assert sm.snapshot() == before


# ---- 새 작업 시작 · SetConfig (4.3절, 5.1절) ----

@pytest.mark.parametrize('command', [Command.START, Command.SET_CONFIG])
def test_start_and_set_config_allowed_phases(command):
    assert set(COMMAND_TRANSITIONS[command]) == {
        Phase.IDLE, Phase.DONE, Phase.ERROR, Phase.STOPPED}


@pytest.mark.parametrize('steps', [0, 1, 2, 6, 7])
def test_start_and_set_config_are_busy_while_running(steps):
    sm = drive(ScanStateMachine(), steps)
    for command in (Command.START, Command.SET_CONFIG, Command.HOME):
        outcome = sm.request(command, conditions=READY, scan_id='20260918-220000-0002')
        assert (outcome.accepted, outcome.reason) == (False, Reason.BUSY)


def test_set_config_needs_no_conditions_and_changes_nothing(sm):
    outcome = sm.request(Command.SET_CONFIG)
    assert outcome.accepted and not outcome.changed


@pytest.mark.parametrize('conditions, reason', [
    (LATCHED, Reason.SAFETY_LATCHED),
    (DISCONNECTED, Reason.ROBOT_DISCONNECTED),
    (UNKNOWN, Reason.SAFETY_LATCHED),
    (Conditions(robot_connected=None, safety_latched=False, **FRESH_STATUS),
     Reason.ROBOT_DISCONNECTED),
    # 둘 다 걸리면 계약 5.1절에 적힌 순서대로 SAFETY_LATCHED 가 먼저다
    (Conditions(robot_connected=False, safety_latched=True, **FRESH_STATUS),
     Reason.SAFETY_LATCHED),
])
def test_start_rejections(sm, conditions, reason):
    outcome = sm.request(Command.START, conditions=conditions, scan_id='a')
    assert (outcome.accepted, outcome.reason) == (False, reason)
    assert sm.phase is Phase.IDLE and sm.snapshot().scan_id == ''


def test_busy_wins_over_latch():
    sm = drive(ScanStateMachine(), 2)
    outcome = sm.request(Command.START, conditions=LATCHED, scan_id='b')
    assert outcome.reason is Reason.BUSY


def test_new_start_from_stopped_discards_the_old_scan():
    sm = stopped_at(4)
    outcome = sm.request(Command.START, conditions=READY, scan_id='new')
    assert outcome.accepted
    assert (outcome.state.scan_id, outcome.state.progress) == ('new', 0)
    sm.request(Command.STOP)
    sm.notify(Signal.STOP_CONFIRMED)
    assert sm.request(Command.RESUME, conditions=READY).accepted
    assert sm.notify(Signal.RESUME_READY).phase is Phase.PREPARING


def test_start_clears_previous_failure():
    sm = drive(ScanStateMachine(), 1)
    sm.notify(Signal.FAILED, reason_code=Reason.NO_CONTACT)
    assert sm.failure is not None
    assert sm.request(Command.START, conditions=READY, scan_id='c').accepted
    assert sm.failure is None


# ---- 안전복귀 (5.2절) ----

@pytest.mark.parametrize('phase', sorted(ACTIVE_PHASES | {Phase.STOPPING}))
def test_home_is_not_in_table_while_busy(phase):
    assert phase not in COMMAND_TRANSITIONS[Command.HOME]


def test_home_returns_to_the_phase_it_left():
    for make, origin in [
        (ScanStateMachine, Phase.IDLE),
        (lambda: drive(ScanStateMachine(), 8), Phase.DONE),
        (lambda: stopped_at(3), Phase.STOPPED),
    ]:
        sm = make()
        outcome = sm.request(Command.HOME, conditions=READY)
        assert outcome.accepted and outcome.state.phase is Phase.HOMING
        assert sm.notify(Signal.HOMING_DONE).phase is origin


def test_home_from_error_keeps_the_failure():
    sm = drive(ScanStateMachine(), 2)
    sm.notify(Signal.FAILED, reason_code=Reason.NO_EDGE)
    sm.request(Command.HOME, conditions=READY)
    assert sm.notify(Signal.HOMING_DONE).phase is Phase.ERROR
    assert sm.failure.reason_code == Reason.NO_EDGE


def test_home_is_not_blocked_by_latch_but_needs_connection():
    sm = stopped_at(3)
    assert sm.request(Command.HOME, conditions=DISCONNECTED).reason \
        is Reason.ROBOT_DISCONNECTED
    assert sm.request(Command.HOME, conditions=UNKNOWN).reason \
        is Reason.ROBOT_DISCONNECTED
    assert sm.request(Command.HOME, conditions=LATCHED).accepted


def test_home_failure_is_error():
    sm = stopped_at(3)
    sm.request(Command.HOME, conditions=READY)
    assert sm.notify(Signal.FAILED, reason_code=Reason.ROBOT_ERROR).phase is Phase.ERROR


# ---- 재시작 (5.3절, 7.4절) ----

@pytest.mark.parametrize('steps, phase, direction, progress', [
    (0, Phase.PREPARING, Direction.NONE, 0),
    (1, Phase.TOP_SEARCH, Direction.NONE, 0),
    (2, Phase.EDGE_SEARCH, Direction.POS_X, 0),
    (4, Phase.EDGE_SEARCH, Direction.POS_Y, 2),
    (6, Phase.GEOMETRY, Direction.NONE, 4),
])
def test_resume_returns_to_the_interrupted_step(steps, phase, direction, progress):
    sm = stopped_at(steps)
    scan_id = sm.snapshot().scan_id
    assert sm.snapshot().direction is Direction.NONE  # 모서리 탐색 중에만 유효
    outcome = sm.request(Command.RESUME, conditions=READY)
    assert outcome.accepted and outcome.state.phase is Phase.RESUMING
    state = sm.notify(Signal.RESUME_READY)
    assert (state.phase, state.direction, state.progress) == (phase, direction, progress)
    assert state.scan_id == scan_id  # 새 작업이 아니다


def test_resume_accepts_matching_scan_id_only():
    sm = stopped_at(3)
    assert sm.request(Command.RESUME, conditions=READY, scan_id='other').reason \
        is Reason.NO_RESUMABLE_SCAN
    assert sm.request(
        Command.RESUME, conditions=READY, scan_id=sm.snapshot().scan_id).accepted


def test_stop_during_resuming_keeps_the_resume_point():
    sm = stopped_at(4)
    sm.request(Command.RESUME, conditions=READY)
    sm.request(Command.STOP)
    sm.notify(Signal.STOP_CONFIRMED)
    sm.request(Command.RESUME, conditions=READY)
    state = sm.notify(Signal.RESUME_READY)
    assert (state.phase, state.direction, state.progress) == (
        Phase.EDGE_SEARCH, Direction.POS_Y, 2)


def test_stop_during_finishing_homing_is_not_resumable():
    sm = stopped_at(7)
    assert sm.snapshot().progress == 4
    outcome = sm.request(Command.RESUME, conditions=READY)
    assert (outcome.accepted, outcome.reason) == (False, Reason.NO_RESUMABLE_SCAN)
    # 이후는 관제자의 안전복귀
    assert sm.request(Command.HOME, conditions=READY).accepted


def test_resume_after_safe_return_is_not_supported():
    sm = stopped_at(3)
    sm.request(Command.HOME, conditions=READY)
    sm.notify(Signal.HOMING_DONE)
    outcome = sm.request(Command.RESUME, conditions=READY)
    assert (outcome.accepted, outcome.reason) == (False, Reason.NOT_SUPPORTED)


def test_resume_after_interrupted_safe_return_is_not_supported():
    sm = stopped_at(3)
    sm.request(Command.HOME, conditions=READY)
    sm.request(Command.STOP)
    sm.notify(Signal.STOP_CONFIRMED)
    assert sm.request(Command.RESUME, conditions=READY).reason is Reason.NOT_SUPPORTED


@pytest.mark.parametrize('make, reason', [
    (ScanStateMachine, Reason.NO_RESUMABLE_SCAN),
    (lambda: drive(ScanStateMachine(), 8), Reason.NO_RESUMABLE_SCAN),
    (lambda: drive(ScanStateMachine(), 3), Reason.BUSY),
])
def test_resume_rejections_by_phase(make, reason):
    outcome = make().request(Command.RESUME, conditions=READY)
    assert (outcome.accepted, outcome.reason) == (False, reason)


def test_resume_from_error_is_not_supported():
    sm = drive(ScanStateMachine(), 3)
    sm.notify(Signal.FAILED, reason_code=Reason.OVER_FORCE)
    assert sm.request(Command.RESUME, conditions=READY).reason is Reason.NOT_SUPPORTED


@pytest.mark.parametrize('conditions, reason', [
    (LATCHED, Reason.SAFETY_LATCHED),
    (DISCONNECTED, Reason.ROBOT_DISCONNECTED),
    (UNKNOWN, Reason.SAFETY_LATCHED),
])
def test_resume_guard_rejections(conditions, reason):
    sm = stopped_at(3)
    outcome = sm.request(Command.RESUME, conditions=conditions)
    assert (outcome.accepted, outcome.reason) == (False, reason)
    assert sm.phase is Phase.STOPPED
    # 거절은 재개 지점을 지우지 않는다
    assert sm.request(Command.RESUME, conditions=READY).accepted


def test_rest_phases_constant():
    assert REST_PHASES == {Phase.IDLE, Phase.DONE, Phase.ERROR, Phase.STOPPED}


# ---- 상태 토픽이 끊긴 경우 (이슈 #120) ----
# /safety/status · /robot/status 는 TRANSIENT_LOCAL 이라 발행자가 죽어도 마지막 메시지가 남는다.
# "한 번도 못 받음"(None)만 걸러서는 "받다가 끊김"을 알 수 없다.

LIMITS = dict(robot_status_timeout_s=2.0, safety_status_timeout_s=5.0)


def aged(safety=0.0, robot=0.0, latched=False, connected=True, **limits):
    return Conditions(
        robot_connected=connected, safety_latched=latched,
        safety_status_age_s=safety, robot_status_age_s=robot, **{**LIMITS, **limits})


def ask(sm, command, conditions):
    """RESUME 은 중단된 작업을 가리켜야 한다(scan_id='' = 가장 최근 것)."""
    return sm.check(
        command, conditions=conditions, scan_id='' if command is Command.RESUME else 'x')


@pytest.mark.parametrize('command', [Command.START, Command.RESUME])
def test_a_stale_safety_status_refuses_start_and_resume(command):
    reason, detail = ask(stopped_at(3), command, aged(safety=5.01))
    assert reason is Reason.SAFETY_LATCHED
    assert '끊김' in detail and '미수신' not in detail   # 한 번도 못 받은 것과 문구가 다르다


@pytest.mark.parametrize('command', [Command.START, Command.RESUME, Command.HOME])
def test_a_stale_robot_status_refuses_start_resume_and_home(command):
    reason, detail = ask(stopped_at(3), command, aged(robot=2.01))
    assert (reason, '끊김' in detail) == (Reason.ROBOT_DISCONNECTED, True)


def test_home_is_not_blocked_by_a_stale_safety_status():
    """감시자가 죽었다고 돌아오지 못하면 안 된다 (CLAUDE.md 규칙 3). 래치가 HOME 을 막지 않는 것과 같다."""
    sm = stopped_at(3)
    assert sm.request(Command.HOME, conditions=aged(safety=99.0)).accepted


def test_the_gap_is_reported_before_the_latch():
    """끊긴 뒤의 latched 는 죽은 감시자가 남긴 옛 값이다. 사람이 볼 것은 '감시자가 죽었다' 쪽이다."""
    sm = ScanStateMachine()
    _reason, detail = sm.check(
        Command.START, conditions=aged(safety=5.01, latched=True), scan_id='x')
    assert '끊김' in detail


def test_never_received_keeps_its_own_wording():
    sm = ScanStateMachine()
    assert sm.check(Command.START, conditions=UNKNOWN, scan_id='x')[1] == '/safety/status 미수신'


@pytest.mark.parametrize('conditions', [
    aged(safety=5.0, robot=2.0),      # 정확히 한계 시간이면 통과다(엄격히 넘어야 끊김)
    aged(safety=-0.5, robot=-0.5),    # stamp 가 미래다. 시계 뒤틀림으로 막지 않는다
])
def test_the_boundary_and_a_future_stamp_still_pass(conditions):
    sm = ScanStateMachine()
    assert sm.request(Command.START, conditions=conditions, scan_id='x').accepted


@pytest.mark.parametrize('conditions, reason', [
    # ROS 시계가 0 이다(use_sim_time 인데 /clock 이 없다). 나이를 잴 수 없으면 통과시키지 않는다
    (aged(safety=None), Reason.SAFETY_LATCHED),
    (aged(robot=None), Reason.ROBOT_DISCONNECTED),
    # 한도 파라미터가 없다. 판정할 수 없으면 통과시키지 않는다
    (aged(safety_status_timeout_s=None), Reason.SAFETY_LATCHED),
    (aged(robot_status_timeout_s=None), Reason.ROBOT_DISCONNECTED),
])
def test_what_cannot_be_judged_does_not_pass(conditions, reason):
    sm = ScanStateMachine()
    outcome = sm.request(Command.START, conditions=conditions, scan_id='x')
    assert (outcome.accepted, outcome.reason) == (False, reason)
    assert '판정할 수 없다' in outcome.detail
    assert sm.phase is Phase.IDLE


def test_status_stale_names_the_topic_the_age_and_the_limit():
    text = status_stale('/safety/status', 'safety_status_timeout_s', 7.25, 5.0)
    assert '/safety/status' in text and '7.2' in text and '5.0' in text
    assert status_stale('/safety/status', 'safety_status_timeout_s', 4.9, 5.0) is None
