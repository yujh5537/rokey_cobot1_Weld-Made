"""용접 순서 · 판정 · 안전복귀 (weld-motion.md 5절, weld-ros-interfaces.md 5 · 7장). 가짜 Ports 로 ROS 없이 돈다."""

import math

import pytest

from conftest import FIXTURE_SCAN_ID
from conftest import PARAM_VALUES
from scan_manager.result_store import Stamp
from weld_manager.contract_enums import LineStatus
from weld_manager.contract_enums import MotionReason as MR
from weld_manager.contract_enums import Reason
from weld_manager.contract_enums import WeldPhase as P
from weld_manager.params import check
from weld_manager.sequence import classify
from weld_manager.sequence import HomeRunner
from weld_manager.sequence import MotionKind
from weld_manager.sequence import MotionRequest
from weld_manager.sequence import MotionResult
from weld_manager.sequence import orientation_error_rad
from weld_manager.sequence import OutcomeKind
from weld_manager.sequence import Ports
from weld_manager.sequence import VerdictKind
from weld_manager.sequence import WeldRunner
from weld_manager.state_machine import Command
from weld_manager.state_machine import InvalidTransition
from weld_manager.state_machine import Signal
from weld_manager.state_machine import WeldStateMachine
from weld_manager.weld_path import LINES
from weld_manager.weld_path import load_scan
from weld_manager.weld_path import plan_weld
from weld_manager.weld_path import rotate
from weld_manager.weld_path import tool_frame
from weld_manager.weld_record import Pose

WELD_ID = '20260923-120000-0001'
FRAMES = dict(result_frame_id='workpiece_fixture', motion_frame_id='base_link')
HOME_POSE = ((0.421, -0.156, 0.294), (0.0516, 0.9987, 0.0, 0.0))
Q_TILT = (0.0, 0.9238795, 0.3826834, 0.0)


def reached(request, **changes):
    if request.kind is MotionKind.PATH:
        position, orientation = request.waypoints[-1], request.orientation
    elif request.kind is MotionKind.HOME:
        position, orientation = HOME_POSE
    else:
        position, orientation = request.target, request.orientation
    return MotionResult(**{'reason': MR.TARGET_REACHED, 'position': tuple(position),
                           'orientation': tuple(orientation), **changes})


class FakePorts(Ports):
    """가짜 로봇 + 진짜 상태 기계. script = {n번째 goal(1부터): 결과 또는 (ports, request) → 결과}."""

    def __init__(self, sm, script=None):
        self.sm = sm
        self.script = script or {}
        self.calls, self.saved, self.logs, self.events = [], [], [], []
        self.stop, self.latch, self.still = False, 0, True
        self.after = {}           # {n: (ports) → None} n번째 goal 이 Result 를 돌려주기 직전에 할 일(= 모션 도중)
        self.on_notify = {}       # {(Signal, k): (ports) → None} 그 신호의 k 번째 알림이 받아들여진 직후 할 일(= goal 사이)
        self._notified = {}
        self._clock = 0

    def press_stop(self):
        self.stop = True
        self.sm.request(Command.STOP)

    def stop_requested(self):
        return self.stop

    def safety_reason_code(self):
        return self.latch

    def execute(self, motion_id, request):
        self.calls.append((motion_id, request))
        self.events.append(('goal', request.label))
        n = len(self.calls)
        action = self.script.get(n)
        result = action(self, request) if callable(action) else action or reached(request)
        if n in self.after:
            self.after[n](self)
        return result

    def notify(self, signal, **kwargs):
        self.events.append(('notify', signal))
        try:
            self.sm.notify(signal, **kwargs)
        except InvalidTransition:
            if self.sm.phase is P.STOPPING:
                return False
            raise
        k = self._notified[signal] = self._notified.get(signal, 0) + 1
        if (signal, k) in self.on_notify:
            self.on_notify[(signal, k)](self)
        return True

    def wait_still(self):
        return self.still

    def now(self):
        self._clock += 1
        return Stamp(1_790_000_000 + self._clock)

    def save_result(self, record):
        self.saved.append(record)
        self.events.append(('save', record.success))

    def log(self, level, message, position=None):
        self.logs.append((level, message))

    # 보기 편하게
    def kinds(self):
        return [r.kind for _, r in self.calls]


def params(**changes):
    result = check({**PARAM_VALUES, **changes})
    assert result.ok, result.describe()
    return result.params


@pytest.fixture
def scan(fixture_store):
    return load_scan(fixture_store, FIXTURE_SCAN_ID, **FRAMES)


def run(scan, script=None, start=0, end=7, after=None, tolerance=None, on_notify=None, start_pose=None,
        **param_changes):
    p = params(**param_changes)
    plan = plan_weld(scan, start, end, p)
    sm = WeldStateMachine()
    assert sm.request(Command.START, weld_id=WELD_ID, scan_id=scan.scan_id).accepted
    ports = FakePorts(sm, script)
    ports.after = after or {}
    ports.on_notify = on_notify or {}
    outcome = WeldRunner(ports, plan, p, WELD_ID, 'workpiece_fixture', tolerance, start_pose).run()
    return outcome, ports, plan


def statuses(record):
    return [line.status for line in record.lines]


# ---- 정상 ----

def test_all_eight_lines_then_home(scan):
    outcome, ports, plan = run(scan)
    assert outcome.kind is OutcomeKind.DONE and ports.sm.phase is P.DONE
    assert ports.sm.snapshot().lines_done == 8
    # 선마다 접근 1 · 접근 2 (MOVE_TO) → 경로(PATH) → 후퇴(MOVE_TO), 끝에 올림 → HOME
    per_line = [MotionKind.MOVE_TO, MotionKind.MOVE_TO, MotionKind.PATH, MotionKind.MOVE_TO]
    assert ports.kinds() == per_line * 8 + [MotionKind.MOVE_TO, MotionKind.HOME]
    assert [mid for mid, _ in ports.calls] == list(range(1, 35))   # weld 안에서 1부터
    record = outcome.record
    assert record.success and statuses(record) == [LineStatus.DONE] * 8
    assert len(ports.saved) == 1
    # 7.3절: 결과가 마무리 복귀보다 먼저다
    save_at = ports.events.index(('save', True))
    assert ports.events.index(('notify', Signal.HOMING)) > save_at
    assert ports.events.index(('goal', '마무리 올림')) > save_at


def test_goal_values_follow_the_plan(scan):
    outcome, ports, plan = run(scan)
    p = params()
    first = [r for _, r in ports.calls[:4]]
    line = plan.lines[0]
    assert first[0].target == line.approach1 and first[0].speed == p.travel_speed_mps
    assert first[1].target == line.approach2 and first[1].speed == p.approach_speed_mps
    assert first[2].waypoints == line.path and first[2].speed == p.weld_speed_mps
    assert first[2].line_index == 0 and first[2].path_length_m == line.path_length_m
    assert first[2].path_tolerance_m == p.path_tolerance_m
    assert first[3].target == line.retreat and first[3].speed == p.travel_speed_mps
    assert all(r.orientation == line.orientation for r in first)
    assert all(r.timeout_s == p.motion_timeout_s for _, r in ports.calls)


def test_end_line_three_does_only_the_top_loop(scan):
    outcome, ports, _ = run(scan, end=3)
    assert outcome.kind is OutcomeKind.DONE and len(ports.calls) == 4 * 4 + 2
    assert statuses(outcome.record) == [LineStatus.DONE] * 4 + [LineStatus.SKIPPED] * 4
    assert outcome.record.success and outcome.record.end_line == 3


def test_middle_range_skips_both_sides(scan):
    outcome, _, _ = run(scan, start=2, end=4)
    S, D = LineStatus.SKIPPED, LineStatus.DONE
    assert statuses(outcome.record) == [S, S, D, D, D, S, S, S]


# ---- 시작 상승 (D30) ----

LOW = Pose((0.46, -0.21, 0.43), Q_TILT)      # 부재 옆 낮은 자리, 기울인 자세 (sim 픽스처 z_safe ≈ 0.4899)


def test_start_below_z_safe_lifts_straight_up_first(scan):
    outcome, ports, plan = run(scan, start_pose=LOW)
    assert outcome.kind is OutcomeKind.DONE and len(ports.calls) == 35
    lift = ports.calls[0][1]
    assert lift.label == '시작 상승' and lift.kind is MotionKind.MOVE_TO
    assert lift.target[:2] == LOW.position[:2] and math.isclose(lift.target[2], plan.z_safe_base)
    assert lift.orientation == LOW.orientation            # 자세를 바꾸지 않는다(순수 이동)
    assert lift.speed == params().travel_speed_mps
    assert ports.calls[1][1].label == 'L0 접근 1'
    assert any('D30' in message for _, message in ports.logs)


def test_start_above_z_safe_does_not_lift(scan):
    # sim 픽스처(base_to_fixture z 0.4)의 z_safe ≈ 0.49 m 보다 높은 자리. HOME_POSE(실기 홈 팁 0.294 m)는 여기선 낮다
    outcome, ports, _ = run(scan, start_pose=Pose((0.425, -0.184, 0.60), (0.0, 1.0, 0.0, 0.0)))
    assert len(ports.calls) == 34 and ports.calls[0][1].label == 'L0 접근 1'


def test_start_just_below_z_safe_within_tolerance_does_not_lift(scan):
    plan = plan_weld(scan, 0, 7, params())
    near = Pose((0.46, -0.21, plan.z_safe_base - params().path_tolerance_m / 2), Q_TILT)
    outcome, ports, _ = run(scan, start_pose=near)
    assert ports.calls[0][1].label == 'L0 접근 1'


def test_start_lift_failure_ends_there(scan):
    outcome, ports, _ = run(scan, {1: MotionResult(reason=MR.OVER_FORCE, reason_code=400)}, start_pose=LOW)
    assert outcome.kind is OutcomeKind.FAILED and len(ports.calls) == 1
    assert outcome.record.lines[0].status is LineStatus.FAILED


def test_start_lift_stopped(scan):
    outcome, ports, _ = run(scan, stop_during(1), start_pose=LOW)
    assert outcome.kind is OutcomeKind.STOPPED and len(ports.calls) == 1


def test_lift_only_before_the_first_line(scan):
    outcome, ports, _ = run(scan, start=2, end=3, start_pose=LOW)
    labels = [r.label for _, r in ports.calls]
    assert labels.count('시작 상승') == 1 and labels[1] == 'L2 접근 1'


# ---- 중지 (/weld/stop) ----

def stop_during(n, position=(0.43, -0.2, 0.44)):
    def action(ports, request):
        ports.press_stop()
        return MotionResult(reason=MR.STOP_REQUESTED, reason_code=200, position=position,
                            orientation=request.orientation or Q_TILT)
    return {n: action}


def test_stop_during_l2_path(scan):
    # L2 의 경로 = 3 번째 선의 3 번째 goal = 4·2 + 3 = 11
    outcome, ports, plan = run(scan, stop_during(11))
    assert outcome.kind is OutcomeKind.STOPPED and ports.sm.phase is P.STOPPED
    assert len(ports.calls) == 11                       # 더 움직이지 않는다
    D, St, N = LineStatus.DONE, LineStatus.STOPPED, LineStatus.NOT_ATTEMPTED
    record = outcome.record
    assert statuses(record) == [D, D, St, N, N, N, N, N]
    assert not record.success and record.reason_code == Reason.STOP_REQUESTED
    line = record.lines[2]
    # 정지 좌표는 작업대 좌표로 남긴다 (Base − base_to_fixture)
    b = plan.base_to_fixture
    assert all(math.isclose(a, e - o) for a, e, o in zip(line.stop_pose.position, (0.43, -0.2, 0.44), b))
    assert ports.events[-1] == ('notify', Signal.STOP_CONFIRMED)
    assert ports.events.index(('save', False)) < len(ports.events) - 1   # 결과를 낸 뒤 STOPPED


def test_stop_pressed_as_goal_arrives(scan):
    # 1 번째 goal(L0 접근 1)이 도착하는 순간 중지 → 중지가 우선(도착으로 치지 않는다). 정지 자리 = 도착 좌표
    outcome, ports, plan = run(scan, after={1: FakePorts.press_stop})
    assert outcome.kind is OutcomeKind.STOPPED and len(ports.calls) == 1
    pose = outcome.record.lines[0].stop_pose
    expected = [a - b for a, b in zip(plan.lines[0].approach1, plan.base_to_fixture)]
    assert all(math.isclose(a, e, abs_tol=1e-12) for a, e in zip(pose.position, expected))


def test_stop_between_lines_keeps_finished_line_done(scan):
    # L0 을 다 끝낸(LINE_DONE) 직후 중지 → 다음 선의 APPROACH 알림이 거절되고(경합) 멈춘다.
    # L0 은 DONE, L1 은 시작하지 않았다. 네 번째 goal 뒤로 더 보내지 않는다
    outcome, ports, _ = run(scan, on_notify={(Signal.LINE_DONE, 1): FakePorts.press_stop})
    assert outcome.kind is OutcomeKind.STOPPED and len(ports.calls) == 4
    assert statuses(outcome.record)[:2] == [LineStatus.DONE, LineStatus.NOT_ATTEMPTED]
    assert outcome.record.lines[0].stop_pose is None      # 끝난 선에는 정지 좌표를 달지 않는다


def test_stop_during_retreat_marks_line_stopped(scan):
    # 후퇴도 선 절차의 일부다(5절 표). 후퇴 도중 중지면 그 선은 STOPPED
    outcome, _, _ = run(scan, stop_during(4))
    assert statuses(outcome.record)[0] is LineStatus.STOPPED


def test_stop_not_confirmed_is_failure(scan):
    def action(ports, request):
        ports.still = False
        return stop_during(3)[3](ports, request)
    outcome, ports, _ = run(scan, {3: action})
    assert outcome.kind is OutcomeKind.FAILED and ports.sm.phase is P.ERROR
    assert outcome.reason_code == Reason.ROBOT_STATUS_LOST


def test_stop_during_final_homing_publishes_once(scan):
    outcome, ports, _ = run(scan, stop_during(34), end=7)      # 34 = HOME
    assert outcome.kind is OutcomeKind.STOPPED and ports.sm.phase is P.STOPPED
    assert len(ports.saved) == 1 and ports.saved[0].success      # 용접선은 끝났다. 결과는 한 번만


# ---- 실패 ----

@pytest.mark.parametrize('result, latch, code', [
    (MotionResult(reason=MR.STOP_REQUESTED, reason_code=403), 403, 403),      # safety_monitor 정지(래치)
    (MotionResult(reason=MR.STOP_REQUESTED, reason_code=200), 0, 204),        # 웹의 스캔 중지 버튼(D25)
    (MotionResult(reason=MR.CANCELED, reason_code=201), 0, 204),
    (MotionResult(reason=MR.OVER_FORCE, reason_code=400, detail='31 N'), 0, 400),
    (MotionResult(reason=MR.TIMEOUT, reason_code=203), 0, 203),
    (MotionResult(reason=MR.REJECTED, reason_code=604, detail='z < path_min_z_m'), 0, 604),
    (MotionResult(reason=MR.ROBOT_ERROR, reason_code=204), 0, 204),
    (MotionResult(accepted=False), 0, 204),
    (MotionResult(available=False), 0, 104),
    (MotionResult(reason=MR.CONTACT), 0, 204),                               # 맞지 않는 종료 사유
])
def test_failures_end_in_error_without_more_motion(scan, result, latch, code):
    def action(ports, request):
        ports.latch = latch
        return result
    outcome, ports, _ = run(scan, {7: action})             # 7 = L1 접근 2
    assert outcome.kind is OutcomeKind.FAILED and ports.sm.phase is P.ERROR
    assert outcome.reason_code == code and ports.sm.failure.reason_code == code
    assert len(ports.calls) == 7                           # 자동 복귀 · 재시도 없음
    record = outcome.record
    assert statuses(record)[:3] == [LineStatus.DONE, LineStatus.FAILED, LineStatus.NOT_ATTEMPTED]
    assert record.lines[1].reason_code == code and not record.success


def test_unknown_stop_position_is_not_invented(scan):
    # 움직였을 수 있는데 좌표를 못 받았으면 정지 좌표를 모른다 — 앞 goal 의 좌표로 채우지 않는다
    outcome, _, _ = run(scan, {7: MotionResult(available=False)})
    assert outcome.record.lines[1].stop_pose is None
    # 거절된 goal 은 로봇이 움직이지 않았다 → 앞 goal 의 도착 좌표가 지금 자리다
    outcome, _, _ = run(scan, {7: MotionResult(accepted=False)})
    assert outcome.record.lines[1].stop_pose is not None


def test_latch_between_goals_blocks_next_goal(scan):
    outcome, ports, _ = run(scan, after={2: lambda ports: setattr(ports, 'latch', 403)})
    assert outcome.kind is OutcomeKind.FAILED and outcome.reason_code == 403
    assert len(ports.calls) == 2


def test_orientation_mismatch_is_caught_when_tolerance_given(scan):
    wrong = {3: lambda ports, request: reached(request, orientation=(0.0, 1.0, 0.0, 0.0))}
    outcome, ports, _ = run(scan, wrong, tolerance=math.radians(1.0))
    assert outcome.kind is OutcomeKind.FAILED and '자세' in outcome.detail
    outcome, _, _ = run(scan, wrong, tolerance=None)          # 허용치가 없으면 보지 않는다
    assert outcome.kind is OutcomeKind.DONE


def test_final_homing_failure_keeps_result(scan):
    outcome, ports, _ = run(scan, {34: MotionResult(reason=MR.TIMEOUT, reason_code=203)})
    assert outcome.kind is OutcomeKind.HOMING_FAILED and ports.sm.phase is P.ERROR
    assert len(ports.saved) == 1 and ports.saved[0].success   # 용접 결과는 유효하다(7.3절)


# ---- classify 단독 ----

REQ = MotionRequest(MotionKind.MOVE_TO, 't', speed=0.01, target=(0, 0, 0), orientation=Q_TILT)


def test_reached_after_stop_is_stop():
    verdict = classify(REQ, reached(REQ), stop_requested=True)
    assert verdict.kind is VerdictKind.STOPPED


def test_failure_after_stop_is_still_failure():
    verdict = classify(REQ, MotionResult(reason=MR.OVER_FORCE), stop_requested=True)
    assert verdict.kind is VerdictKind.FAILED and verdict.reason_code == Reason.OVER_FORCE


def test_orientation_error():
    assert math.isclose(orientation_error_rad(Q_TILT, tuple(-c for c in Q_TILT)), 0.0, abs_tol=1e-6)
    assert math.isclose(orientation_error_rad((0, 0, 0, 1), (0, 0, math.sin(0.25), math.cos(0.25))), 0.5)


# ---- 안전복귀 ----

def home(pose, z_safe, origin=P.STOPPED, script=None, latch=0):
    p = params()
    sm = WeldStateMachine()
    if origin is P.STOPPED:
        sm.request(Command.START, weld_id=WELD_ID, scan_id='20260923-110000-0001')
        sm.request(Command.STOP)
        sm.notify(Signal.STOP_CONFIRMED)
    assert sm.request(Command.HOME).accepted
    ports = FakePorts(sm, script)
    ports.latch = latch
    outcome = HomeRunner(ports, p, pose, z_safe, first_motion_id=9).run()
    return outcome, ports, p


def test_home_backs_off_along_tool_axis_then_lifts(scan):
    # 세로선(L4) 도중 멈춘 자리: 툴 축 d 는 아래 · 부재 안쪽(+x · +y)을 본다
    frame = tool_frame(LINES[4].t, LINES[4].n_out, math.radians(45.0), 0.0)
    d, q = frame.z, frame.quaternion
    assert all(math.isclose(a, b, abs_tol=1e-12) for a, b in zip(d, (0.5, 0.5, -math.sqrt(0.5))))
    pose = Pose((0.40, -0.20, 0.42), q)
    outcome, ports, p = home(pose, z_safe=0.49)
    assert outcome.kind is OutcomeKind.DONE and ports.sm.phase is P.STOPPED   # 출발한 휴지 phase 로
    kinds = ports.kinds()
    assert kinds == [MotionKind.MOVE_TO, MotionKind.MOVE_TO, MotionKind.HOME]
    back, lift = ports.calls[0][1], ports.calls[1][1]
    axis = rotate(q, (0.0, 0.0, 1.0))
    assert all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(axis, d))
    expected = [c - p.approach_m * di for c, di in zip(pose.position, axis)]
    assert all(math.isclose(a, e, abs_tol=1e-9) for a, e in zip(back.target, expected))
    assert back.speed == p.approach_speed_mps and back.orientation == q
    assert lift.target[:2] == back.target[:2] and math.isclose(lift.target[2], 0.49)
    assert [mid for mid, _ in ports.calls] == [9, 10, 11]   # 앞 작업의 번호를 잇는다


def test_home_does_not_go_down_to_z_safe(scan):
    pose = Pose((0.40, -0.20, 0.60), (0.0, 1.0, 0.0, 0.0))   # 수직, 이미 z_safe 보다 위
    outcome, ports, p = home(pose, z_safe=0.49)
    lift = ports.calls[1][1]
    assert math.isclose(lift.target[2], 0.60 + p.approach_m)   # 물러난 높이 그대로


def test_home_without_pose_sends_home_only():
    outcome, ports, _ = home(None, z_safe=0.49)
    assert ports.kinds() == [MotionKind.HOME] and outcome.kind is OutcomeKind.DONE
    assert any(level == 'warn' for level, _ in ports.logs)


def test_home_without_z_safe_backs_off_then_home():
    outcome, ports, _ = home(Pose((0.4, -0.2, 0.42), (0.0, 1.0, 0.0, 0.0)), z_safe=None)
    assert ports.kinds() == [MotionKind.MOVE_TO, MotionKind.HOME]


def test_home_is_not_blocked_by_latch():
    outcome, ports, _ = home(None, z_safe=None, latch=403)
    assert outcome.kind is OutcomeKind.DONE and len(ports.calls) == 1


def test_home_from_idle_returns_to_idle():
    outcome, ports, _ = home(None, z_safe=None, origin=P.IDLE)
    assert ports.sm.phase is P.IDLE


def test_home_stopped_midway():
    outcome, ports, _ = home(Pose((0.4, -0.2, 0.42), (0.0, 1.0, 0.0, 0.0)), 0.49, script=stop_during(1))
    assert outcome.kind is OutcomeKind.STOPPED and ports.sm.phase is P.STOPPED and len(ports.calls) == 1


def test_home_failure_goes_to_error():
    outcome, ports, _ = home(None, None, script={1: MotionResult(reason=MR.TIMEOUT, reason_code=203)})
    assert outcome.kind is OutcomeKind.FAILED and ports.sm.phase is P.ERROR
