"""재시작의 판단(resume.py): 기록 → 상태 복원 · 재개 계획 · 거절 (ROS 없음).

가짜 Ports 에 **실제 ResultStore** 를 붙여 스캔을 돌리고, "프로세스 재시작"은 새 상태 기계 + 새 store 인스턴스로 흉내 낸다.
확인하는 것: ① 기록만으로 되돌린 상태 기계가 죽지 않은 프로세스와 같은 판정을 낸다 ② 기록으로 세운 계획이
메모리의 값과 같다 ③ 그 계획으로 끝까지 가면 기존 측정값이 그대로다. 수치는 테스트용 임의값이다.
"""

import random

import pytest
from result_store_helpers import FakeClock
from scan_manager import resume as scan_resume
from scan_manager.contract_enums import Direction
from scan_manager.contract_enums import MotionReason
from scan_manager.contract_enums import Phase
from scan_manager.contract_enums import Reason
from scan_manager.result_store import ConfigSnapshot
from scan_manager.result_store import Detection
from scan_manager.result_store import EVENT_CONTACT
from scan_manager.result_store import EVENT_EDGE
from scan_manager.result_store import Frames
from scan_manager.result_store import Interruption
from scan_manager.result_store import Measurement
from scan_manager.result_store import PoseRecord
from scan_manager.result_store import ResultStore
from scan_manager.result_store import ResultStoreError
from scan_manager.result_store import Stamp
from scan_manager.sequence import MotionPlanner
from scan_manager.sequence import MotionResult
from scan_manager.sequence import OutcomeKind
from scan_manager.sequence import ResumeRunner
from scan_manager.sequence import run_home
from scan_manager.sequence import ScanRunner
from scan_manager.sequence import StepOutcome
from scan_manager.state_machine import Command
from scan_manager.state_machine import Signal
from sequence_helpers import BOX_SIZE
from sequence_helpers import DOWN
from sequence_helpers import FakePorts
from sequence_helpers import FRESH_STATUS
from sequence_helpers import make_params
from sequence_helpers import READY
from sequence_helpers import SCAN_ID

FRAME = 'base_link'
NEWER_SCAN_ID = '20260920-130000-0002'
# 정상 경로의 n 번째 모션: to_origin, descend, slide_POS_X, (lift, to_origin_xy, recontact, slide) x3, final_lift, home
SLIDE_POS_X = 3
LAST_MEASURING = 15
FINAL_LIFT = 16


class RecordingPorts(FakePorts):
    """가짜 로봇 + 실제 상태 기계 + 실제 ResultStore. 노드가 기록하는 시점 · 내용을 그대로 따른다."""

    def __init__(self, params, result_dir, start=True, position=None):
        self.store = ResultStore(result_dir, now_fn=FakeClock())
        self._begun = not start
        super().__init__(params, on_change=self._on_change, start=start)
        if position is not None:
            self.position = position    # 프로세스가 다시 떠도 로봇은 그 자리에 있다

    def _on_change(self, snapshot):
        if not snapshot.scan_id:
            return
        if not self._begun:
            self._begun = True
            p = self.params
            self.store.begin_scan(
                snapshot.scan_id, state=snapshot, frames=Frames(FRAME, p.result_frame_id),
                config=ConfigSnapshot(
                    descend_speed_mps=p.descend_speed_mps, slide_speed_mps=p.slide_speed_mps,
                    max_descend_m=p.max_descend_m, max_slide_m=p.max_slide_m,
                    motion_timeout_s=p.motion_timeout_s, lift_height_m=p.lift_height_m),
                direction_order=p.direction_order, started_at=Stamp(1),
                node_params=p.node_params())
        else:
            self.store.record_state(snapshot)

    def _pose(self, position):
        return None if position is None else PoseRecord(tuple(position), DOWN, FRAME, Stamp(7))

    def _measurement(self, event_type, event, result):
        motion_id = self.requests[-1][0]
        z_drop = event.raw['z_drop_m']
        detection = Detection(
            event_type=event_type, event_id=result.event_id, sample_id=5000 + result.event_id,
            motion_id=motion_id, pose=self._pose(event.position), force_stamp=Stamp(7),
            detect_stamp=Stamp(7), force_delta_n=3.3, z_drop_m=z_drop,
            z_drop_valid=z_drop is not None, source='sim', debounce_count=3)
        return Measurement(detection, self._pose(result.position))

    def record_top(self, event, result, request):
        self.store.record_top(SCAN_ID, self._measurement(EVENT_CONTACT, event, result))
        super().record_top(event, result, request)

    def record_edge(self, direction, event, result, request):
        self.store.record_edge(SCAN_ID, direction, self._measurement(EVENT_EDGE, event, result))
        super().record_edge(direction, event, result, request)

    def record_stop(self, position, result, during_final_homing):
        super().record_stop(position, result, during_final_homing)
        before = self.stop_snapshot
        # 노드와 같다: 이 명령에서 받은 Result 가 있으면 그 pose(없을 수 있다), 없으면 직전 중지의 좌표
        recorded = result.position if result is not None else position
        self.store.record_stop(SCAN_ID, Interruption(
            before.phase, before.direction, before.progress, pose=self._pose(recorded),
            during_final_homing=during_final_homing))

    def fail(self, reason_code, detail, position):
        super().fail(reason_code, detail, position)
        self.store.record_failure(SCAN_ID, self.sm.failure)

    def compute_geometry(self):
        outcome = super().compute_geometry()
        self.store.save_result(SCAN_ID, self.geometry.shape, self.geometry.bias_corrections)
        return outcome

    def republish_result(self):
        self.trace.append(('republish_result',))
        self.republished += 1
        shape = self.store.load_result(SCAN_ID).shape   # 메모리의 계산 결과가 아니라 저장된 원본
        return StepOutcome(shape.success, shape.reason_code, shape.detail)

    # -- 관제자 --

    def home(self, stop=False):
        """안전복귀(/scan/home). stop=True 면 복귀 도중에 중지된다."""
        origin = self.sm.phase
        assert self.sm.request(Command.HOME, conditions=READY).accepted
        self.store.record_home_requested(SCAN_ID, origin)
        self._stop = False
        self.stop_during = 'home' if stop else None
        outcome = run_home(MotionPlanner(self.params), self, first_motion_id=len(self.requests) + 1)
        if not stop:
            self.store.record_home_finished(SCAN_ID, outcome.kind is OutcomeKind.DONE)
        return outcome


@pytest.fixture
def params():
    return make_params()


@pytest.fixture
def result_dir(tmp_path):
    return tmp_path / 'data'


def scan(params, result_dir, stop_at=None, **injections):
    ports = RecordingPorts(params, result_dir)
    ports.stop_at_request = stop_at
    for name, value in injections.items():
        setattr(ports, name, value)
    outcome = ScanRunner(MotionPlanner(params), ports, params.direction_order).run()
    return ports, outcome


def reopen(params, result_dir, old):
    """프로세스 재시작: 메모리(상태 기계 · 측정값 캐시)는 사라지고 파일과 로봇의 위치만 남는다."""
    ports = RecordingPorts(params, result_dir, start=False, position=old.position)
    ports.requests = list(old.requests)     # 테스트가 motion_id 의 연속을 보려고 넘긴다(노드는 기록에서 읽는다)
    return ports


def adopt(ports):
    """노드의 _adopt_recorded_scan 과 같다. 되돌리지 않았으면 그 이유."""
    try:
        record, why = scan_resume.latest_record(ports.store)
    except ResultStoreError as error:        # 노드는 이것을 "되돌릴 작업이 있었는지 모른다"로 다룬다
        record, why = None, str(error)
    restoration = None
    if record is not None:
        restoration, why = scan_resume.restoration_from(record)
    if restoration is not None:
        ports.sm.restore(
            scan_id=restoration.scan_id, phase=restoration.phase, progress=restoration.progress,
            resume_phase=restoration.resume_phase, moved_since_stop=restoration.moved_since_stop,
            failure=restoration.failure)
    return restoration, why


def plan_from_record(ports, params):
    return scan_resume.plan_resume(
        ports.store.load(SCAN_ID), result_file_exists=ports.store.has_result(SCAN_ID),
        direction_order=params.direction_order)


def resume_from_record(ports, params, stop_at=None):
    """노드의 재시작 경로: 판정 → 기록에서 계획 → 접수 → record_resume → ResumeRunner."""
    assert ports.sm.check(Command.RESUME, conditions=READY) == (Reason.OK, '')
    resumption = plan_from_record(ports, params)
    assert isinstance(resumption, scan_resume.Resumption), resumption
    ports.top, ports.edges = resumption.top, dict(resumption.edges)
    assert ports.sm.request(Command.RESUME, conditions=READY).accepted
    ports.store.record_resume(SCAN_ID)
    ports._stop, ports.stop_at_request = False, stop_at
    ports.resumed_at_request = len(ports.requests)
    return ResumeRunner(
        MotionPlanner(resumption.params), ports, params.direction_order, resumption.plan,
        first_motion_id=resumption.last_motion_id + 1).run()


# ---- 프로세스가 재시작된 뒤에도 같은 자리에서 잇는다 ----

@pytest.mark.parametrize('n', range(1, LAST_MEASURING + 1))
def test_a_restarted_process_resumes_from_the_record_alone(params, result_dir, n):
    old, outcome = scan(params, result_dir, stop_at=n)
    assert outcome.kind is OutcomeKind.STOPPED
    before = old.store.load(SCAN_ID)
    expected_plan = old.memory_plan()
    live_verdict = old.sm.check(Command.RESUME, conditions=READY)

    ports = reopen(params, result_dir, old)
    restoration, _why = adopt(ports)

    assert ports.sm.snapshot() == old.sm.snapshot()
    assert ports.sm.check(Command.RESUME, conditions=READY) == live_verdict == (Reason.OK, '')
    assert plan_from_record(ports, params).plan == expected_plan
    assert restoration.last_motion_id == n

    assert resume_from_record(ports, params).kind is OutcomeKind.DONE

    after = ports.store.load(SCAN_ID)
    assert after.scan_id == before.scan_id and after.state.phase is Phase.DONE
    if before.top.valid:
        assert after.top == before.top                     # 같은 판정 좌표 · 같은 stamp (BRD TR-08)
    for direction in before.confirmed_edges:
        assert after.edges[direction] == before.edges[direction]
    since = ports.labels_since_resume()
    assert ('descend' in since) != before.top.valid
    assert all(f'slide_{d.name}' not in since for d in before.confirmed_edges)
    ids = [motion_id for motion_id, _ in ports.requests]
    assert ids == list(range(1, len(ids) + 1))             # scan 안에서 되풀이되지 않는다(계약 6.2절)
    shape = ports.store.load_result(SCAN_ID).shape
    assert shape.success
    assert (shape.width, shape.length, shape.height) == pytest.approx(BOX_SIZE, abs=1e-9)
    assert after.interruptions[-1].resumed_at is not None


def test_result_saved_before_the_stop_is_read_back_after_a_restart(params, result_dir):
    old, _ = scan(params, result_dir, stop_before_notify=Signal.GEOMETRY_DONE)
    saved = old.store.load_result(SCAN_ID)
    ports = reopen(params, result_dir, old)
    adopt(ports)

    assert plan_from_record(ports, params).plan.result_saved
    assert resume_from_record(ports, params).kind is OutcomeKind.DONE
    assert ports.republished == 1 and ('compute_geometry',) not in ports.trace
    assert ports.store.load_result(SCAN_ID) == saved       # 원본은 한 번만 쓴다
    assert ports.labels_since_resume() == ['final_lift', 'home']


def test_stop_in_geometry_before_the_result_exists_is_computed_after_a_restart(params, result_dir):
    old, _ = scan(params, result_dir, stop_after_notify=(Signal.EDGE_FOUND, 4))
    before = old.store.load(SCAN_ID)
    assert before.resume_point.phase is Phase.GEOMETRY and not old.store.has_result(SCAN_ID)
    ports = reopen(params, result_dir, old)
    adopt(ports)

    assert not plan_from_record(ports, params).plan.result_saved
    assert resume_from_record(ports, params).kind is OutcomeKind.DONE

    assert ports.trace.count(('compute_geometry',)) == 1 and ports.republished == 0
    assert ports.labels_since_resume() == ['final_lift', 'home']
    after = ports.store.load(SCAN_ID)
    assert after.top == before.top and after.edges == before.edges
    shape = ports.store.load_result(SCAN_ID).shape
    assert (shape.width, shape.length, shape.height) == pytest.approx(BOX_SIZE, abs=1e-9)


def test_result_file_without_the_flag_is_still_republished(params, result_dir):
    """원본을 쓴 직후 · 진행 기록에 표시하기 전에 프로세스가 죽었다."""
    old, _ = scan(params, result_dir, stop_before_notify=Signal.GEOMETRY_DONE)
    record = old.store.load(SCAN_ID)
    assert record.result_saved
    resumption = scan_resume.plan_resume(
        _with(record, result_saved=False, result_success=None), result_file_exists=True,
        direction_order=params.direction_order)
    assert resumption.plan.result_saved


def _with(record, **fields):
    for name, value in fields.items():
        setattr(record, name, value)
    return record


# ---- 되돌리지 않는 경우 · 거절 ----

def test_nothing_recorded_means_nothing_to_adopt(params, result_dir):
    ports = RecordingPorts(params, result_dir, start=False)
    restoration, why = adopt(ports)
    assert restoration is None and '기록이 없다' in why
    assert ports.sm.check(Command.RESUME, conditions=READY)[0] is Reason.NO_RESUMABLE_SCAN


def test_a_record_left_in_an_active_phase_is_not_adopted(params, result_dir):
    """작업 도중에 프로세스가 죽었다. 중지 기록이 없어 로봇이 어디서 멈췄는지 모른다."""
    old, _ = scan(params, result_dir, stop_at=SLIDE_POS_X)
    snapshot = old.sm.snapshot()
    old.store.record_state(type(snapshot)(SCAN_ID, Phase.EDGE_SEARCH, Direction.POS_X, 0, 4, 3))

    ports = reopen(params, result_dir, old)
    restoration, why = adopt(ports)                          # 노드와 같은 길: 파일에서 읽는다
    assert restoration is None and 'phase=EDGE_SEARCH' in why and '모른다' in why
    assert ports.sm.phase is Phase.IDLE
    assert ports.sm.check(Command.RESUME, conditions=READY)[0] is Reason.NO_RESUMABLE_SCAN
    refusal = plan_from_record(ports, params)
    assert refusal.reason is Reason.NO_RESUMABLE_SCAN


def test_a_newer_scan_hides_the_stopped_one(params, result_dir):
    old, _ = scan(params, result_dir, stop_at=SLIDE_POS_X)
    snapshot = old.sm.snapshot()
    newer = type(snapshot)(NEWER_SCAN_ID, Phase.PREPARING, Direction.NONE, 0, 4, 0)
    old.store.begin_scan(
        NEWER_SCAN_ID, state=newer, config=ConfigSnapshot(), frames=Frames(FRAME, 'workpiece_fixture'),
        direction_order=params.direction_order)
    old.store.record_state(type(snapshot)(NEWER_SCAN_ID, Phase.DONE, Direction.NONE, 4, 4, 0))

    ports = reopen(params, result_dir, old)
    restoration, why = adopt(ports)
    assert restoration is None and NEWER_SCAN_ID in why and 'DONE' in why
    assert ports.sm.check(Command.RESUME, conditions=READY)[0] is Reason.NO_RESUMABLE_SCAN


def test_an_unreadable_latest_record_is_not_skipped_for_an_older_one(params, result_dir):
    old, _ = scan(params, result_dir, stop_at=SLIDE_POS_X)
    newer = result_dir / NEWER_SCAN_ID
    newer.mkdir()
    (newer / 'progress.json').write_text('{ not json', encoding='utf-8')

    ports = reopen(params, result_dir, old)
    restoration, why = adopt(ports)
    assert restoration is None and NEWER_SCAN_ID in why and '읽을 수 없다' in why
    assert ports.sm.phase is Phase.IDLE


def test_a_resume_that_got_past_its_preparation_used_up_the_resume_point(params, result_dir):
    """중지 → 재시작 → DONE → 안전복귀 중 중지. 상태 기계는 RESUME_READY 에서 재개 지점을 지웠다."""
    old, _ = scan(params, result_dir, stop_at=SLIDE_POS_X)
    assert resume_from_record(old, params).kind is OutcomeKind.DONE
    assert old.home(stop=True).kind is OutcomeKind.STOPPED
    live = old.sm.check(Command.RESUME, conditions=READY)
    assert live[0] is Reason.NO_RESUMABLE_SCAN

    ports = reopen(params, result_dir, old)
    restoration, _why = adopt(ports)
    assert restoration.resume_phase is None
    assert ports.sm.snapshot() == old.sm.snapshot()
    assert ports.sm.check(Command.RESUME, conditions=READY) == live
    assert plan_from_record(ports, params).reason is Reason.NO_RESUMABLE_SCAN


@pytest.mark.parametrize('ending, reason', [
    ('final_homing_stop', Reason.NO_RESUMABLE_SCAN),
    ('home', Reason.NOT_SUPPORTED),
    ('home_then_stop', Reason.NOT_SUPPORTED),
    ('failed', Reason.NOT_SUPPORTED),
    ('failed_then_home_then_stop', Reason.NO_RESUMABLE_SCAN),
])
def test_refusals_are_the_same_with_and_without_a_restart(params, result_dir, ending, reason):
    if ending == 'final_homing_stop':
        old, _ = scan(params, result_dir, stop_at=FINAL_LIFT)
    elif ending.startswith('failed'):
        error = MotionResult(reason=MotionReason.ROBOT_ERROR, reason_code=204, position=None)
        old, _ = scan(params, result_dir, override={'slide_NEG_X': error})
        if ending != 'failed':
            old.home(stop=True)
    else:
        old, _ = scan(params, result_dir, stop_at=SLIDE_POS_X)
        old.home(stop=ending == 'home_then_stop')
    live = old.sm.check(Command.RESUME, conditions=READY)
    assert live[0] is reason

    ports = reopen(params, result_dir, old)
    restoration, _why = adopt(ports)
    assert restoration is not None
    assert ports.sm.snapshot() == old.sm.snapshot()
    assert ports.sm.check(Command.RESUME, conditions=READY) == live
    # 상태 기계가 먼저 거르지만, 기록만 봐도 이을 수 없다고 나와야 한다
    assert isinstance(plan_from_record(ports, params), scan_resume.Refusal)
    # 기존 측정값 · 로그는 그대로 남아 있다(BRD 4.4.9)
    record = ports.store.load(SCAN_ID)
    assert record.top.valid and record.confirmed_edges == old.store.load(SCAN_ID).confirmed_edges


def test_conditions_refuse_a_restored_scan_like_any_other(params, result_dir):
    old, _ = scan(params, result_dir, stop_at=SLIDE_POS_X)
    ports = reopen(params, result_dir, old)
    adopt(ports)
    latched = type(READY)(robot_connected=True, safety_latched=True, **FRESH_STATUS)
    offline = type(READY)(robot_connected=False, safety_latched=False, **FRESH_STATUS)
    assert ports.sm.check(Command.RESUME, conditions=latched)[0] is Reason.SAFETY_LATCHED
    assert ports.sm.check(Command.RESUME, conditions=offline)[0] is Reason.ROBOT_DISCONNECTED
    assert ports.sm.check(Command.RESUME, conditions=READY, scan_id=NEWER_SCAN_ID)[0] \
        is Reason.NO_RESUMABLE_SCAN
    assert ports.sm.phase is Phase.STOPPED


def stopped_record(params, result_dir, n=SLIDE_POS_X):
    ports, _ = scan(params, result_dir, stop_at=n)
    return ports.store.load(SCAN_ID)


def refusal_of(record, params, **kwargs):
    arguments = {'result_file_exists': False, 'direction_order': params.direction_order, **kwargs}
    planned = scan_resume.plan_resume(record, **arguments)
    assert isinstance(planned, scan_resume.Refusal), planned
    return planned


def test_without_a_stop_position_the_tip_cannot_be_lifted(params, result_dir):
    record = stopped_record(params, result_dir)
    record.interruptions[-1] = Interruption(
        Phase.EDGE_SEARCH, Direction.POS_X, 0, pose=None, stopped_at=Stamp(9))
    refusal = refusal_of(record, params)
    assert refusal.reason is Reason.NO_RESUMABLE_SCAN and '중단 좌표' in refusal.detail


def test_before_the_top_no_stop_position_is_needed(params, result_dir):
    record = stopped_record(params, result_dir, n=1)
    record.interruptions[-1] = Interruption(
        Phase.PREPARING, Direction.NONE, 0, pose=None, stopped_at=Stamp(9))
    planned = scan_resume.plan_resume(
        record, result_file_exists=False, direction_order=params.direction_order)
    assert planned.plan.position is None and planned.plan.phase is Phase.PREPARING


def test_a_different_search_order_is_refused(params, result_dir):
    record = stopped_record(params, result_dir)
    other = tuple(reversed(params.direction_order))
    refusal = refusal_of(record, params, direction_order=other)
    assert refusal.reason is Reason.INVALID_VALUE and 'direction_order' in refusal.detail


def test_recorded_settings_that_no_longer_pass_are_refused_by_name(params, result_dir):
    record = stopped_record(params, result_dir)
    del record.node_params['tip_radius_m']
    refusal = refusal_of(record, params)
    assert refusal.reason is Reason.INVALID_VALUE and 'tip_radius_m' in refusal.detail


def test_coordinates_in_another_frame_are_not_used(params, result_dir):
    record = stopped_record(params, result_dir)
    last = record.interruptions[-1]
    wrong = PoseRecord(last.pose.position_m, DOWN, 'workpiece_fixture', Stamp(9))
    record.interruptions[-1] = Interruption(
        last.phase, last.direction, last.progress, pose=wrong, stopped_at=Stamp(9))
    assert 'frame_id' in refusal_of(record, params).detail


def test_an_interruption_already_resumed_is_not_resumed_twice(params, result_dir):
    ports, _ = scan(params, result_dir, stop_at=SLIDE_POS_X)
    ports.store.record_resume(SCAN_ID)
    record = ports.store.load(SCAN_ID)
    assert '중지 기록이 없다' in refusal_of(record, params).detail


def test_confirmed_directions_out_of_the_search_order_are_refused(params, result_dir):
    ports, _ = scan(params, result_dir, stop_at=SLIDE_POS_X)
    ports.store.record_edge(                     # +x 가 없는데 −x 가 확정돼 있다
        SCAN_ID, Direction.NEG_X, ports._measurement(
            EVENT_EDGE, type('E', (), {'position': (0.35, 0.0, 0.0395), 'raw': {'z_drop_m': 0.0005}})(),
            MotionResult(event_id=900, position=(0.349, 0.0, 0.0395))))
    refusal = refusal_of(ports.store.load(SCAN_ID), params)
    assert refusal.reason is Reason.NO_RESUMABLE_SCAN and '앞부분이 아니다' in refusal.detail


def test_a_recorded_failure_is_not_resumed_even_if_the_phase_says_stopped(params, result_dir):
    """상태 기계가 먼저 거르지만, 기록만 봐도 같은 답이 나와야 한다(메모리와 기록이 어긋난 경우의 대비)."""
    ports, _ = scan(params, result_dir, stop_at=SLIDE_POS_X)
    failure = type('F', (), {'reason_code': 301, 'detail': 'fake', 'phase': Phase.EDGE_SEARCH})()
    ports.store.record_failure(SCAN_ID, failure)
    refusal = refusal_of(ports.store.load(SCAN_ID), params)
    assert refusal.reason is Reason.NOT_SUPPORTED and 'TBD' in refusal.detail


def test_the_plan_uses_the_recorded_settings_not_the_current_ones(params, result_dir):
    record = stopped_record(params, result_dir)
    planned = scan_resume.plan_resume(
        record, result_file_exists=False, direction_order=params.direction_order)
    assert planned.params == params
    assert planned.top.descend_speed_mps == params.descend_speed_mps
    assert planned.top.position_m == tuple(record.top.detection.pose.position_m)
    assert planned.plan.first_contact_z == record.top.detection.pose.position_m[2]   # 판정 좌표의 z (7.3절)
    assert planned.started_at == record.started_at
    assert planned.config['contact_threshold_n'] is None      # 모르는 값을 0 으로 채우지 않는다


# ---- 무작위 명령열: 죽지 않은 프로세스와 되돌린 프로세스가 끝까지 같은 판정을 낸다 ----

@pytest.mark.parametrize('seed', range(30))
def test_restored_and_live_state_machines_never_disagree(params, result_dir, seed):
    rng = random.Random(seed)
    ports, outcome = scan(params, result_dir, stop_at=rng.randint(1, 17))

    for _ in range(8):
        live = ports.sm.check(Command.RESUME, conditions=READY)
        restored = reopen(params, result_dir, ports)
        restoration, why = adopt(restored)
        if ports.sm.phase is Phase.DONE:
            assert restoration is None and restored.sm.check(
                Command.RESUME, conditions=READY)[0] is live[0] is Reason.NO_RESUMABLE_SCAN
            if rng.random() < 0.5:
                break
            ports.home(stop=True)                           # 끝난 작업의 안전복귀 중 중지 → STOPPED
            continue
        assert restoration is not None, why
        assert restored.sm.snapshot() == ports.sm.snapshot()
        assert restored.sm.check(Command.RESUME, conditions=READY) == live
        planned = plan_from_record(restored, params)
        if live[0] is Reason.OK:
            assert isinstance(planned, scan_resume.Resumption), planned
            if ports.resume_point is not None:              # 재시작된 프로세스에는 견줄 메모리가 없을 수 있다
                assert planned.plan == ports.memory_plan()
        else:
            assert isinstance(planned, scan_resume.Refusal)

        if rng.random() < 0.5:
            ports = restored                                # 여기서 프로세스가 재시작됐다
        action = rng.choice(['resume', 'resume', 'resume', 'home', 'home_then_stop'])
        if ports.sm.phase is Phase.ERROR or live[0] is not Reason.OK:
            action = rng.choice(['home', 'home_then_stop', 'end'])
        if action == 'end':
            break
        if action == 'resume':
            stop_at = len(ports.requests) + rng.randint(1, 9) if rng.random() < 0.7 else None
            if rng.random() < 0.15:
                ports.override = {'to_origin_xy': MotionResult(
                    reason=MotionReason.ROBOT_ERROR, reason_code=204, position=None)}
            outcome = resume_from_record(ports, params, stop_at=stop_at)
        else:
            outcome = ports.home(stop=action == 'home_then_stop')
        assert outcome.kind in (OutcomeKind.DONE, OutcomeKind.STOPPED, OutcomeKind.FAILED)

    record = ports.store.load(SCAN_ID)
    ids = [motion_id for motion_id, _ in ports.requests]
    assert ids == sorted(set(ids)) and record.last_motion_id == (ids[-1] if ids else 0)
