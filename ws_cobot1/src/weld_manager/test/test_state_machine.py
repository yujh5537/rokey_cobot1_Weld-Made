"""상태 기계 전이 (weld-ros-interfaces.md 3.2 · 4.1 · 7장). ROS 없이 돈다."""

import pytest

from weld_manager.contract_enums import LINE_NONE
from weld_manager.contract_enums import Reason
from weld_manager.contract_enums import WeldPhase as P
from weld_manager.state_machine import Command
from weld_manager.state_machine import InvalidTransition
from weld_manager.state_machine import REST_PHASES
from weld_manager.state_machine import Signal
from weld_manager.state_machine import WeldStateMachine

IDS = dict(weld_id='20260923-120000-0001', scan_id='20260923-110000-0001')


@pytest.fixture
def changes():
    return []


@pytest.fixture
def sm(changes):
    return WeldStateMachine(on_change=changes.append)


def started(sm):
    assert sm.request(Command.START, **IDS).accepted
    return sm


def one_line(sm, line=0):
    sm.notify(Signal.APPROACH, line=line)
    sm.notify(Signal.WELD)
    sm.notify(Signal.RETREAT)
    sm.notify(Signal.LINE_DONE)


def test_normal_path(sm, changes):
    started(sm)
    for line in range(8):
        one_line(sm, line)
    sm.notify(Signal.HOMING)
    sm.notify(Signal.HOMING_DONE)
    state = sm.snapshot()
    assert state.phase is P.DONE and state.lines_done == 8 and state.line_index == LINE_NONE
    phases = [c.phase for c in changes]
    assert phases[:5] == [P.PREPARING, P.APPROACH, P.WELDING, P.RETREAT, P.RETREAT]
    assert phases[-2:] == [P.HOMING, P.DONE]


def test_line_index_and_progress(sm):
    started(sm)
    sm.notify(Signal.APPROACH, line=3)
    sm.set_progress(0.5)                    # WELDING 이 아니면 무시한다
    assert sm.snapshot().line_index == 3 and sm.snapshot().line_progress == 0.0
    sm.notify(Signal.WELD)
    sm.set_progress(0.5)
    assert sm.snapshot().line_progress == 0.5
    sm.set_progress(1.7)
    assert sm.snapshot().line_progress == 1.0   # 0~1 로 자른다
    sm.notify(Signal.RETREAT)
    assert sm.snapshot().line_progress == 0.0   # 그 밖은 0 (3.2절)


def test_start_is_rejected_while_busy(sm):
    started(sm)
    outcome = sm.request(Command.START, **IDS)
    assert not outcome.accepted and outcome.reason is Reason.BUSY


@pytest.mark.parametrize('phase_steps', [0, 1, 2, 3])
def test_stop_goes_to_stopping_then_stopped_only(sm, phase_steps):
    started(sm)
    steps = [lambda: sm.notify(Signal.APPROACH, line=0), lambda: sm.notify(Signal.WELD),
             lambda: sm.notify(Signal.RETREAT)]
    for step in steps[:phase_steps]:
        step()
    outcome = sm.request(Command.STOP)
    assert outcome.accepted and outcome.changed and sm.phase is P.STOPPING
    # 중지 뒤에는 시퀀스의 진행 보고가 거절된다(노드는 이것을 "중지"로 읽는다)
    with pytest.raises(InvalidTransition):
        sm.notify(Signal.APPROACH, line=1)
    sm.notify(Signal.STOP_CONFIRMED)
    assert sm.phase is P.STOPPED and sm.snapshot().line_index == LINE_NONE


def test_stop_in_rest_is_not_accepted_but_ok(sm):
    outcome = sm.request(Command.STOP)       # 4.1절: 멈출 것이 없다 = accepted false, OK
    assert not outcome.accepted and outcome.reason is Reason.OK and sm.phase is P.IDLE


def test_stop_is_idempotent_while_stopping(sm):
    started(sm)
    sm.request(Command.STOP)
    again = sm.request(Command.STOP)
    assert again.accepted and not again.changed


def test_failure_goes_to_error_and_keeps_reason(sm):
    started(sm)
    sm.notify(Signal.APPROACH, line=0)
    sm.notify(Signal.FAILED, reason_code=400, detail='과대 외력')
    assert sm.phase is P.ERROR and sm.failure.reason_code == 400 and sm.failure.phase is P.APPROACH
    with pytest.raises(ValueError):
        started(sm).notify(Signal.FAILED)       # 사유 없는 실패는 받지 않는다


def test_failure_while_stopping(sm):
    started(sm)
    sm.request(Command.STOP)
    sm.notify(Signal.FAILED, reason_code=404, detail='정지 확인 실패')
    assert sm.phase is P.ERROR


@pytest.mark.parametrize('origin', [P.STOPPED, P.ERROR, P.DONE, P.IDLE])
def test_home_returns_to_origin_rest_phase(sm, origin):
    if origin is not P.IDLE:
        started(sm)
        if origin is P.STOPPED:
            sm.request(Command.STOP)
            sm.notify(Signal.STOP_CONFIRMED)
        elif origin is P.ERROR:
            sm.notify(Signal.FAILED, reason_code=204)
        else:
            for line in range(8):
                one_line(sm, line)
            sm.notify(Signal.HOMING)
            sm.notify(Signal.HOMING_DONE)
    assert sm.phase is origin
    assert sm.request(Command.HOME).accepted and sm.phase is P.HOMING
    sm.notify(Signal.HOMING_DONE)
    assert sm.phase is origin


def test_home_is_rejected_while_busy(sm):
    started(sm)
    outcome = sm.request(Command.HOME)
    assert not outcome.accepted and outcome.reason is Reason.BUSY


def test_stop_during_safety_home(sm):
    sm.request(Command.HOME)
    sm.request(Command.STOP)
    sm.notify(Signal.STOP_CONFIRMED)
    assert sm.phase is P.STOPPED
    # 다음 안전복귀는 STOPPED 로 돌아간다(앞 안전복귀의 출발 phase 가 남지 않는다)
    sm.request(Command.HOME)
    sm.notify(Signal.HOMING_DONE)
    assert sm.phase is P.STOPPED


@pytest.mark.parametrize('phase_signals', [
    [Signal.APPROACH],                                # 접근 중
    [Signal.APPROACH, Signal.WELD],                   # 경로 중
    [Signal.APPROACH, Signal.WELD, Signal.RETREAT],   # 후퇴 중
])
def test_line_failed_goes_to_retreat_and_next_line_continues(sm, phase_signals):
    # D33: 어느 단계에서 실패했든 LINE_FAILED → RETREAT(복구 이동) → 다음 선 APPROACH. lines_done 은 그대로
    started(sm)
    one_line(sm, 0)
    for signal in phase_signals:
        sm.notify(signal, line=1) if signal is Signal.APPROACH else sm.notify(signal)
    state = sm.notify(Signal.LINE_FAILED)
    assert state.phase is P.RETREAT and state.line_index == 1 and state.lines_done == 1
    assert state.line_progress == 0.0
    state = sm.notify(Signal.APPROACH, line=2)
    assert state.phase is P.APPROACH and state.line_index == 2
    sm.notify(Signal.WELD); sm.notify(Signal.RETREAT); sm.notify(Signal.LINE_DONE)
    sm.notify(Signal.HOMING); sm.notify(Signal.HOMING_DONE)
    assert sm.phase is P.DONE and sm.snapshot().lines_done == 2


def test_line_failed_needs_an_active_line(sm):
    started(sm)
    with pytest.raises(InvalidTransition):
        sm.notify(Signal.LINE_FAILED)                 # PREPARING 에는 실패할 선이 없다


@pytest.mark.parametrize('signal', [Signal.WELD, Signal.RETREAT, Signal.LINE_DONE, Signal.LINE_FAILED,
                                    Signal.HOMING, Signal.HOMING_DONE, Signal.STOP_CONFIRMED])
def test_out_of_order_signals_raise(sm, signal):
    started(sm)
    with pytest.raises(InvalidTransition):
        sm.notify(signal)


def test_approach_needs_line(sm):
    started(sm)
    with pytest.raises(ValueError):
        sm.notify(Signal.APPROACH)
    with pytest.raises(ValueError):
        sm.notify(Signal.APPROACH, line=8)


def test_motion_id_cleared_at_rest(sm):
    started(sm)
    sm.notify(Signal.APPROACH, line=0)
    sm.set_motion_id(5)
    assert sm.snapshot().motion_id == 5
    sm.notify(Signal.FAILED, reason_code=204)
    assert sm.snapshot().motion_id == 0 and sm.phase in REST_PHASES
