"""전이표: 정상 경로 · 실패 경로 · 허용되지 않는 전이 (계약 3.4절 · 7.4절)."""

from conftest import drive
from conftest import READY
import pytest
from scan_manager.contract_enums import Direction
from scan_manager.contract_enums import Phase
from scan_manager.contract_enums import Reason
from scan_manager.state_machine import ACTIVE_PHASES
from scan_manager.state_machine import Command
from scan_manager.state_machine import COMMAND_TRANSITIONS
from scan_manager.state_machine import InvalidTransition
from scan_manager.state_machine import REST_PHASES
from scan_manager.state_machine import ScanStateMachine
from scan_manager.state_machine import Signal
from scan_manager.state_machine import SIGNAL_TRANSITIONS

# phase 별로 그 phase 에 도달하는 방법
REACH = {
    Phase.IDLE: lambda sm: sm,
    Phase.PREPARING: lambda sm: drive(sm, 0),
    Phase.TOP_SEARCH: lambda sm: drive(sm, 1),
    Phase.EDGE_SEARCH: lambda sm: drive(sm, 2),
    Phase.GEOMETRY: lambda sm: drive(sm, 6),
    Phase.HOMING: lambda sm: drive(sm, 7),
    Phase.DONE: lambda sm: drive(sm, 8),
    Phase.ERROR: lambda sm: _then(drive(sm, 0), Signal.FAILED),
    Phase.STOPPING: lambda sm: _stop(drive(sm, 2)),
    Phase.STOPPED: lambda sm: _then(_stop(drive(sm, 2)), Signal.STOP_CONFIRMED),
    Phase.RESUMING: lambda sm: _resume(
        _then(_stop(drive(sm, 2)), Signal.STOP_CONFIRMED)),
}


def _then(sm, signal):
    kwargs = {'reason_code': Reason.TARE_FAILED} if signal is Signal.FAILED else {}
    sm.notify(signal, **kwargs)
    return sm


def _stop(sm):
    assert sm.request(Command.STOP).accepted
    return sm


def _resume(sm):
    assert sm.request(Command.RESUME, conditions=READY).accepted
    return sm


def at(phase):
    sm = REACH[phase](ScanStateMachine())
    assert sm.phase is phase
    return sm


def test_initial_state():
    state = ScanStateMachine().snapshot()
    assert state.phase is Phase.IDLE
    assert state.scan_id == ''
    assert state.direction is Direction.NONE
    assert (state.progress, state.progress_total) == (0, 4)
    assert state.motion_id == 0


def test_every_phase_is_reachable():
    for phase in Phase:
        at(phase)


def test_phase_sets_cover_all_phases():
    assert REST_PHASES | ACTIVE_PHASES | {Phase.STOPPING} == set(Phase)
    assert not REST_PHASES & ACTIVE_PHASES


def test_normal_path():
    seen = []
    sm = ScanStateMachine(on_change=seen.append)
    drive(sm, 8)
    phases = [(s.phase, s.direction, s.progress) for s in seen]
    assert phases == [
        (Phase.PREPARING, Direction.NONE, 0),
        (Phase.TOP_SEARCH, Direction.NONE, 0),
        (Phase.EDGE_SEARCH, Direction.POS_X, 0),
        (Phase.EDGE_SEARCH, Direction.NEG_X, 1),
        (Phase.EDGE_SEARCH, Direction.POS_Y, 2),
        (Phase.EDGE_SEARCH, Direction.NEG_Y, 3),
        (Phase.GEOMETRY, Direction.NONE, 4),
        (Phase.HOMING, Direction.NONE, 4),
        (Phase.DONE, Direction.NONE, 4),
    ]
    assert all(s.scan_id == '20260918-210000-0001' for s in seen)
    assert all(s.progress_total == 4 for s in seen)


def test_direction_order_is_configurable():
    order = (Direction.NEG_Y, Direction.POS_Y, Direction.NEG_X, Direction.POS_X)
    sm = drive(ScanStateMachine(direction_order=order), 3)
    assert sm.snapshot().direction is Direction.POS_Y
    with pytest.raises(ValueError):
        ScanStateMachine(direction_order=(Direction.POS_X, Direction.POS_X))


@pytest.mark.parametrize('phase', sorted(ACTIVE_PHASES | {Phase.STOPPING}))
def test_failure_goes_to_error_and_never_homes(phase):
    sm = at(phase)
    state = sm.notify(Signal.FAILED, reason_code=Reason.ROBOT_ERROR, detail='x')
    assert state.phase is Phase.ERROR
    assert sm.failure.reason_code == Reason.ROBOT_ERROR
    assert sm.failure.phase is phase
    assert sm.failure.detail == 'x'
    # ERROR 에서 스스로 움직이는 Signal 은 없다 (자동 복귀 없음, 7.4절)
    for signal in Signal:
        with pytest.raises(InvalidTransition):
            sm.notify(signal, reason_code=Reason.ROBOT_ERROR)
    assert sm.phase is Phase.ERROR


def test_geometry_failure_keeps_scan_id_and_progress():
    sm = at(Phase.GEOMETRY)
    state = sm.notify(Signal.FAILED, reason_code=Reason.INVALID_SHAPE)
    assert (state.phase, state.progress) == (Phase.ERROR, 4)
    assert state.scan_id != ''


def test_failed_requires_nonzero_reason():
    sm = at(Phase.PREPARING)
    for bad in (None, 0, Reason.OK):
        with pytest.raises(ValueError):
            sm.notify(Signal.FAILED, reason_code=bad)
    assert sm.phase is Phase.PREPARING


@pytest.mark.parametrize('phase', list(Phase))
@pytest.mark.parametrize('signal', list(Signal))
def test_signal_outside_table_raises_and_changes_nothing(phase, signal):
    if phase in SIGNAL_TRANSITIONS[signal]:
        return
    sm = at(phase)
    before = sm.snapshot()
    with pytest.raises(InvalidTransition) as err:
        sm.notify(signal, reason_code=Reason.ROBOT_ERROR)
    assert (err.value.phase, err.value.signal) == (phase, signal)
    assert sm.snapshot() == before


@pytest.mark.parametrize('phase', list(Phase))
@pytest.mark.parametrize('signal', list(Signal))
def test_signal_inside_table_lands_in_listed_target(phase, signal):
    targets = SIGNAL_TRANSITIONS[signal].get(phase)
    if targets is None:
        return
    sm = at(phase)
    assert sm.notify(signal, reason_code=Reason.ROBOT_ERROR).phase in targets


@pytest.mark.parametrize('phase', list(Phase))
@pytest.mark.parametrize('command', list(Command))
def test_command_follows_table(phase, command):
    sm = at(phase)
    before = sm.snapshot()
    new_id = '20260918-220000-0002' if command is Command.START else ''
    outcome = sm.request(command, conditions=READY, scan_id=new_id)
    targets = COMMAND_TRANSITIONS[command].get(phase)
    if targets is None:
        assert not outcome.accepted
        assert outcome.reason is not Reason.OK
        assert sm.snapshot() == before
    else:
        assert outcome.accepted and outcome.reason is Reason.OK
        assert outcome.state.phase in targets
        assert outcome.changed == (outcome.state.phase is not phase)


def test_motion_id_is_cleared_at_rest():
    sm = at(Phase.TOP_SEARCH)
    sm.set_motion_id(3)
    assert sm.snapshot().motion_id == 3
    sm.notify(Signal.FAILED, reason_code=Reason.NO_CONTACT)
    assert sm.snapshot().motion_id == 0
    with pytest.raises(ValueError):
        sm.set_motion_id(4)


def test_start_requires_scan_id(sm):
    with pytest.raises(ValueError):
        sm.request(Command.START, conditions=READY)


# ---- check() · restore() (T26) ----

def test_check_gives_the_verdict_of_request_without_changing_anything(sm):
    stopped = REACH[Phase.STOPPED](sm)
    before = stopped.snapshot()
    assert stopped.check(Command.RESUME, conditions=READY) == (Reason.OK, '')
    assert stopped.check(Command.RESUME)[0] is Reason.SAFETY_LATCHED      # 조건 미수신
    assert stopped.check(Command.RESUME, conditions=READY, scan_id='20990101-000000-0000')[0] \
        is Reason.NO_RESUMABLE_SCAN
    assert stopped.snapshot() == before
    assert stopped.request(Command.RESUME, conditions=READY).accepted


@pytest.mark.parametrize('phase', list(Phase))
@pytest.mark.parametrize('command', list(Command))
def test_check_agrees_with_request_in_every_phase(phase, command):
    kwargs = {'conditions': READY, 'scan_id': '20260918-220000-0002' if command is Command.START else ''}
    checked = REACH[phase](ScanStateMachine()).check(command, **kwargs)
    outcome = REACH[phase](ScanStateMachine()).request(command, **kwargs)
    assert checked == (outcome.reason, outcome.detail)


def test_restore_rebuilds_a_stopped_scan_that_resumes_like_the_original():
    original = _then(_stop(drive(ScanStateMachine(), 3)), Signal.STOP_CONFIRMED)   # EDGE_SEARCH 1/4 에서 중지
    seen = []
    restored = ScanStateMachine(on_change=seen.append)
    snapshot = restored.restore(
        scan_id=original.snapshot().scan_id, phase=Phase.STOPPED, progress=1,
        resume_phase=Phase.EDGE_SEARCH)

    assert snapshot == original.snapshot() and seen == [snapshot]
    for machine in (original, restored):
        assert machine.request(Command.RESUME, conditions=READY).accepted
        state = machine.notify(Signal.RESUME_READY)
        assert (state.phase, state.direction, state.progress) == (
            Phase.EDGE_SEARCH, Direction.NEG_X, 1)


def test_restore_keeps_the_facts_that_refuse_a_resume():
    scan_id = '20260918-210000-0001'
    moved = ScanStateMachine()
    moved.restore(
        scan_id=scan_id, phase=Phase.STOPPED, progress=2, resume_phase=Phase.EDGE_SEARCH,
        moved_since_stop=True)
    assert moved.check(Command.RESUME, conditions=READY)[0] is Reason.NOT_SUPPORTED

    finished = ScanStateMachine()
    finished.restore(scan_id=scan_id, phase=Phase.STOPPED, progress=4)     # 마무리 복귀 중의 중지
    assert finished.check(Command.RESUME, conditions=READY)[0] is Reason.NO_RESUMABLE_SCAN

    failed = ScanStateMachine()
    failed.restore(scan_id=scan_id, phase=Phase.ERROR, progress=1)
    assert failed.check(Command.RESUME, conditions=READY)[0] is Reason.NOT_SUPPORTED
    assert failed.request(Command.HOME, conditions=READY).accepted         # 안전복귀는 된다


@pytest.mark.parametrize('phase', [p for p in Phase if p is not Phase.IDLE])
def test_restore_is_only_for_an_idle_machine(phase):
    machine = REACH[phase](ScanStateMachine())
    before = machine.snapshot()
    with pytest.raises(ValueError):
        machine.restore(scan_id='20260918-230000-0003', phase=Phase.STOPPED, progress=0)
    assert machine.snapshot() == before


@pytest.mark.parametrize('kwargs', [
    {'phase': Phase.EDGE_SEARCH, 'progress': 0},                           # 동작 중인 phase 로는 되돌리지 않는다
    {'phase': Phase.DONE, 'progress': 4},
    {'phase': Phase.STOPPED, 'progress': 5},
    {'phase': Phase.STOPPED, 'progress': 0, 'resume_phase': Phase.HOMING},
    {'phase': Phase.ERROR, 'progress': 0, 'resume_phase': Phase.EDGE_SEARCH},
    {'phase': Phase.STOPPED, 'progress': 0, 'scan_id': ''},
])
def test_restore_rejects_what_the_table_could_never_produce(sm, kwargs):
    arguments = {'scan_id': '20260918-210000-0001', **kwargs}
    with pytest.raises(ValueError):
        sm.restore(**arguments)
    assert sm.phase is Phase.IDLE and sm.snapshot().scan_id == ''
