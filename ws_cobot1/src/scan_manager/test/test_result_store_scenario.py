"""시뮬레이션: T10 상태 기계 + 가상 직육면체 + result_store 를 묶어 작업 흐름 전체를 돌린다.

로봇 · ROS 는 없다. 여기의 SimScanManager 는 T19 · T26 이 만들 노드의 축소판이며,
result_store/README.md 의 "사용 주의"에 적은 연결 방식(쓰기 전용 스레드 1개)을 그대로 따른다.
가상 직육면체의 치수 · 보정량은 테스트용 임의값이다.
"""

from concurrent.futures import ThreadPoolExecutor
import itertools
import random
import threading

import pytest
from conftest import FRESH_STATUS
from result_store_helpers import CONFIG
from result_store_helpers import FakeClock
from result_store_helpers import FRAMES
from result_store_helpers import NODE_PARAMS
from result_store_helpers import SCAN_A
from result_store_helpers import SCAN_B
from scan_manager.contract_enums import Direction
from scan_manager.contract_enums import Phase
from scan_manager.contract_enums import Reason
from scan_manager.result_store import BiasCorrection
from scan_manager.result_store import Detection
from scan_manager.result_store import EVENT_CONTACT
from scan_manager.result_store import EVENT_EDGE
from scan_manager.result_store import Interruption
from scan_manager.result_store import Measured
from scan_manager.result_store import Measurement
from scan_manager.result_store import PoseRecord
from scan_manager.result_store import ResultStore
from scan_manager.result_store import SegmentRecord
from scan_manager.result_store import ShapeResult
from scan_manager.result_store import STATUS_CONFIRMED
from scan_manager.result_store import STATUS_FAILED
from scan_manager.result_store import STATUS_NOT_ATTEMPTED
from scan_manager.result_store import TOP
from scan_manager.state_machine import Command
from scan_manager.state_machine import Conditions
from scan_manager.state_machine import DEFAULT_DIRECTION_ORDER
from scan_manager.state_machine import ScanStateMachine
from scan_manager.state_machine import Signal

READY = Conditions(robot_connected=True, safety_latched=False, **FRESH_STATUS)
DOWN = (0.0, 1.0, 0.0, 0.0)

# 가상 직육면체 (base_link). 작업대 좌표의 원점은 base_link 의 (0.4, 0.0, 0.0) 이고 축은 평행하다.
FIXTURE_ORIGIN = (0.4, 0.0, 0.0)
BOX = {Direction.POS_X: 0.45, Direction.NEG_X: 0.35, Direction.POS_Y: 0.03, Direction.NEG_Y: -0.03}
BOX_TOP_Z = 0.04
BIAS_M = 0.0034   # 판정 좌표가 실제 모서리보다 진행 방향으로 더 나간 양
Z_DROP_M = 0.0021
AXIS = {Direction.POS_X: (0, 1), Direction.NEG_X: (0, -1),
        Direction.POS_Y: (1, 1), Direction.NEG_Y: (1, -1)}


class SimScanManager:
    """노드의 축소판. 상태는 on_change → 쓰기 스레드, 측정값 · 결과는 쓰기 스레드에 맡기고 끝을 기다린다."""

    def __init__(self, result_dir, clock, no_edge_in=None):
        self.clock = clock
        self.store = ResultStore(result_dir, now_fn=clock)
        # 쓰기 전용 스레드 1개 = 순서가 보장되는 큐. on_change 는 넣기만 하고 돌아온다.
        self.writer = ThreadPoolExecutor(max_workers=1, thread_name_prefix='result_store')
        self.write_errors = []
        self.sm = ScanStateMachine(on_change=self._on_change)
        self.no_edge_in = no_edge_in
        self._recording = True
        self._begin_args = None
        self._begun = None
        self._ids = itertools.count(1)
        self._motion_ids = itertools.count(1)
        self.tcp = [0.4, 0.0, 0.3]

    # -- result_store 연결 --

    def _on_change(self, snap):
        # 상태 기계의 락 안이다. 디스크에 쓰지 않고 큐에 넣기만 한다.
        if not self._recording or not snap.scan_id:
            return
        if snap.scan_id != self._begun:
            self._begun = snap.scan_id
            job = self.writer.submit(
                self.store.begin_scan, snap.scan_id, state=snap, **self._begin_args)
        else:
            job = self.writer.submit(self.store.record_state, snap)
        job.add_done_callback(self._collect_error)

    def _collect_error(self, job):
        if job.exception() is not None:
            self.write_errors.append(job.exception())

    def _write(self, method, *args, **kwargs):
        """측정값 · 결과처럼 다음 단계로 가기 전에 디스크에 있어야 하는 기록."""
        return self.writer.submit(method, *args, **kwargs).result()

    def flush(self):
        self.writer.submit(lambda: None).result()
        assert self.write_errors == []

    def kill(self):
        """프로세스 종료. 메모리의 상태 기계와 store 인스턴스는 사라지고 파일만 남는다."""
        self.flush()
        self.writer.shutdown(wait=True)
        self.sm = self.store = None

    # -- 가상 로봇 --

    def _pose(self, position=None):
        return PoseRecord(tuple(position or self.tcp), DOWN, 'base_link', self.clock())

    def _detection(self, event_type, position, motion_id, z_drop=None):
        number = next(self._ids)
        return Detection(
            event_type=event_type, event_id=number, sample_id=1000 + number, motion_id=motion_id,
            pose=self._pose(position), force_stamp=self.clock(), detect_stamp=self.clock(),
            force_delta_n=3.2, z_drop_m=z_drop, z_drop_valid=z_drop is not None,
            source='sim', debounce_count=3)

    def _begin_motion(self):
        motion_id = next(self._motion_ids)  # scan 안에서 1부터 증가(계약 6.2절)
        self.sm.set_motion_id(motion_id)
        return motion_id

    # -- 시퀀스 --

    def start(self, scan_id):
        self._begin_args = {
            'config': CONFIG, 'frames': FRAMES, 'direction_order': DEFAULT_DIRECTION_ORDER,
            'started_at': self.clock(), 'node_params': NODE_PARAMS}
        outcome = self.sm.request(Command.START, conditions=READY, scan_id=scan_id)
        assert outcome.accepted
        self.scan_id = scan_id

    def find_top(self):
        self.sm.notify(Signal.PREPARE_DONE)
        motion_id = self._begin_motion()
        self.tcp = [0.4, 0.0, BOX_TOP_Z]
        detection = self._detection(EVENT_CONTACT, self.tcp, motion_id)
        self.tcp[2] -= 0.0003  # 정지 좌표는 판정 좌표보다 조금 더 내려가 있다
        self._write(self.store.record_top, self.scan_id, Measurement(detection, self._pose()))
        self.sm.set_motion_id(0)
        self.sm.notify(Signal.TOP_FOUND)  # 기록이 디스크에 있은 뒤에 알린다

    def start_slide(self):
        """SLIDE 를 시작만 한다(중지 시나리오용). 방향을 돌려준다."""
        direction = self.sm.snapshot().direction
        self._motion_id = self._begin_motion()
        axis, sign = AXIS[direction]
        self.tcp = [0.4, 0.0, BOX_TOP_Z - 0.001]
        self.tcp[axis] += sign * 0.01  # 밀다가 만 위치
        return direction

    def find_edge(self):
        direction = self.start_slide()
        axis, sign = AXIS[direction]
        if direction is self.no_edge_in:
            self.tcp[axis] += sign * 0.2
            self._write(self.store.record_attempt_failed, self.scan_id, direction,
                        int(Reason.NO_EDGE), 'max_distance', self._pose())
            self.sm.notify(Signal.FAILED, reason_code=Reason.NO_EDGE, detail='max_distance')
            self._write(self.store.record_failure, self.scan_id, self.sm.failure)
            return direction
        self.tcp[axis] = BOX[direction] + sign * BIAS_M
        detection = self._detection(EVENT_EDGE, self.tcp, self._motion_id, z_drop=Z_DROP_M)
        self.tcp[axis] += sign * 0.0005
        self._write(self.store.record_edge, self.scan_id, direction,
                    Measurement(detection, self._pose()))
        self.sm.set_motion_id(0)
        self.sm.notify(Signal.EDGE_FOUND)
        return direction

    def geometry(self):
        """store 에 남은 측정값만으로 형상을 만든다(재시작 뒤에도 같은 길로 계산된다)."""
        record = self._write(self.store.load, self.scan_id)
        corrected, corrections = {}, {}
        for direction, slot in record.edges.items():
            axis, sign = AXIS[direction]
            raw = slot.detection.pose.position_m[axis]
            corrections[direction] = BiasCorrection(
                raw, BIAS_M, True, {'z_drop_m': slot.detection.z_drop_m, 'detect_latency_s': None})
            corrected[direction] = raw - sign * BIAS_M - FIXTURE_ORIGIN[axis]
        z_top = record.top.detection.pose.position_m[2] - FIXTURE_ORIGIN[2]
        x_neg, x_pos = corrected[Direction.NEG_X], corrected[Direction.POS_X]
        y_neg, y_pos = corrected[Direction.NEG_Y], corrected[Direction.POS_Y]
        top = [
            (x_neg, y_neg, z_top), (x_pos, y_neg, z_top),
            (x_pos, y_pos, z_top), (x_neg, y_pos, z_top)]
        vertices = top + [(x, y, 0.0) for x, y, _z in top]

        def segment(i, j):
            length = sum((a - b) ** 2 for a, b in zip(vertices[i], vertices[j])) ** 0.5
            return SegmentRecord(vertices[i], vertices[j], length, True)

        edges = tuple(
            [segment(i, (i + 1) % 4) for i in range(4)]
            + [segment(i + 4, (i + 1) % 4 + 4) for i in range(4)]
            + [segment(i, i + 4) for i in range(4)])
        shape = ShapeResult(
            success=True, reason_code=0, detail='', frame_id=FRAMES.result,
            started_at=record.started_at, finished_at=self.clock(),
            z_top=Measured.of(z_top), x_pos=Measured.of(x_pos), x_neg=Measured.of(x_neg),
            y_pos=Measured.of(y_pos), y_neg=Measured.of(y_neg), support_z=Measured.of(0.0),
            width=x_pos - x_neg, length=y_pos - y_neg, height=z_top, dims_valid=True,
            vertices=tuple(vertices), edges=edges, path_candidates=edges[:4], box_valid=True)
        self._write(self.store.save_result, self.scan_id, shape, corrections)  # 발행보다 먼저 저장
        self.sm.notify(Signal.GEOMETRY_DONE)

    def finish_homing(self):
        self.tcp = [0.0, 0.0, 0.4]
        self.sm.notify(Signal.HOMING_DONE)

    def run_to_done(self):
        while self.sm.phase is Phase.EDGE_SEARCH:
            self.find_edge()
        if self.sm.phase is Phase.GEOMETRY:
            self.geometry()
            self.finish_homing()

    def stop(self, during_final_homing=False):
        """작업 중지: 접수 → 정지 완료 확인 → 중단 위치 기록. 홈 복귀 · 재시작은 부르지 않는다."""
        before = self.sm.snapshot()
        assert self.sm.request(Command.STOP).accepted
        # 중단 위치를 기록한 뒤에 STOPPED 로 보낸다. 그래야 뒤따르는 안전복귀가 기록에서도 중지 뒤에 온다
        self._write(self.store.record_stop, self.scan_id, Interruption(
            before.phase, before.direction, before.progress, pose=self._pose(),
            during_final_homing=during_final_homing))
        self.sm.notify(Signal.STOP_CONFIRMED)

    def begin_home(self):
        """안전복귀를 접수만 한다(복귀 도중의 중지 시나리오용)."""
        origin = self.sm.phase
        outcome = self.sm.request(Command.HOME, conditions=READY)
        assert outcome.accepted
        self._write(self.store.record_home_requested, self.scan_id, origin_phase=origin)
        self.tcp = [0.2, 0.0, 0.2]  # 홈으로 가는 길

    def home(self):
        self.begin_home()
        self.tcp = [0.0, 0.0, 0.4]
        self.sm.notify(Signal.HOMING_DONE)
        self._write(self.store.record_home_finished, self.scan_id, True, final_pose=self._pose())

    def resume(self, scan_id=''):
        outcome = self.sm.request(Command.RESUME, conditions=READY, scan_id=scan_id)
        if outcome.accepted:
            self._write(self.store.record_resume, self.scan_id)
            self.sm.notify(Signal.RESUME_READY)
        return outcome

    # -- 프로세스 재시작 뒤의 복원 (T26 의 몫. 여기서는 기록만으로 되는지 확인한다) --

    def restore(self, record):
        """기록에 남은 사실을 상태 기계에 다시 흘려 같은 상태로 만든다. 그동안은 기록하지 않는다."""
        self._recording = False
        self.scan_id = self._begun = record.scan_id
        self._motion_ids = itertools.count(record.last_motion_id + 1)  # motion_id 를 이어서 발급
        self.sm.request(Command.START, conditions=READY, scan_id=record.scan_id)
        last = record.resume_point
        if last.phase >= Phase.TOP_SEARCH:
            self.sm.notify(Signal.PREPARE_DONE)
        if record.top.valid and last.phase is not Phase.TOP_SEARCH:
            self.sm.notify(Signal.TOP_FOUND)
            for _ in range(last.progress):
                self.sm.notify(Signal.EDGE_FOUND)
        if last.phase is Phase.HOMING:
            self.sm.notify(Signal.GEOMETRY_DONE)
        self.sm.request(Command.STOP)
        self.sm.notify(Signal.STOP_CONFIRMED)
        if record.home_return_since_resume_point:
            self.sm.request(Command.HOME, conditions=READY)
            self.sm.notify(Signal.HOMING_DONE)
        self._recording = True
        assert self.sm.snapshot().phase is record.state.phase
        assert self.sm.snapshot().progress == record.state.progress


@pytest.fixture
def result_dir(tmp_path):
    return tmp_path / 'data'


@pytest.fixture
def clock():
    return FakeClock()


def fresh_store(result_dir):
    return ResultStore(result_dir, now_fn=FakeClock(start_sec=1_790_200_000))


# ---- 1. 정상 완료 ----

def test_full_scan_is_recorded_and_readable_after_restart(result_dir, clock):
    sim = SimScanManager(result_dir, clock)
    sim.start(SCAN_A)
    sim.find_top()
    sim.run_to_done()
    assert sim.sm.phase is Phase.DONE
    sim.kill()

    store = fresh_store(result_dir)
    record = store.load(SCAN_A)
    assert record.state.phase is Phase.DONE and record.state.progress == 4
    assert record.state.motion_id == 0
    assert record.top.status == STATUS_CONFIRMED
    assert record.confirmed_edges == DEFAULT_DIRECTION_ORDER
    assert record.config == CONFIG and record.frames == FRAMES
    assert record.interruptions == [] and record.failure is None
    assert record.result_saved and record.result_success is True

    shape = store.load_result(SCAN_A).shape
    assert shape.frame_id == 'workpiece_fixture'
    assert (shape.width, shape.length, shape.height) == pytest.approx((0.10, 0.06, 0.04))
    assert shape.x_pos.value == pytest.approx(0.05) and shape.x_neg.value == pytest.approx(-0.05)
    assert shape.vertices[0] == pytest.approx((-0.05, -0.03, 0.04))  # (x⁻, y⁻) 부터 반시계
    corrections = store.load_result(SCAN_A).bias_corrections
    assert corrections[Direction.POS_X].raw_coordinate_m == pytest.approx(0.45 + BIAS_M)
    assert corrections[Direction.POS_X].inputs['detect_latency_s'] is None
    # 판정 좌표는 보정 전 원값이고 base_link 기준이다
    assert record.edges[Direction.POS_X].detection.pose.position_m[0] == pytest.approx(0.4534)
    assert store.find_resume_candidate().record is None  # 끝난 작업은 재개 후보가 아니다


def test_state_is_written_in_the_order_it_changed(result_dir, clock):
    sim = SimScanManager(result_dir, clock)
    seen = []
    real = sim.store.record_state
    sim.store.record_state = lambda snap: (seen.append(snap), real(snap))[1]
    sim.start(SCAN_A)
    sim.find_top()
    sim.run_to_done()
    sim.flush()
    phases = [s.phase for s in seen]
    assert phases == sorted(phases, key=[
        Phase.PREPARING, Phase.TOP_SEARCH, Phase.EDGE_SEARCH, Phase.GEOMETRY, Phase.HOMING,
        Phase.DONE].index)
    assert [s.progress for s in seen] == sorted(s.progress for s in seen)


# ---- 2. +x 탐색 중 중지 → 재시작 → z_top 유지 (BRD US-12 · TR-08) ----

def test_stop_in_pos_x_then_resume_in_the_same_process_keeps_z_top(result_dir, clock):
    sim = SimScanManager(result_dir, clock)
    sim.start(SCAN_A)
    sim.find_top()
    top_before = sim.store.load(SCAN_A).top
    assert sim.start_slide() is Direction.POS_X
    sim.stop()
    sim.flush()

    stopped = sim.store.load(SCAN_A)
    assert stopped.state.phase is Phase.STOPPED and stopped.state.motion_id == 0
    last = stopped.last_interruption
    assert (last.phase, last.direction, last.progress) == (Phase.EDGE_SEARCH, Direction.POS_X, 0)
    assert last.pose.position_m == pytest.approx((0.41, 0.0, 0.039)) and last.resumed_at is None
    assert not stopped.home_return_requested  # 중지가 홈 복귀를 부르지 않았다
    assert sim.sm.phase is Phase.STOPPED       # 중지가 재시작을 부르지 않았다

    assert sim.resume().accepted
    assert sim.sm.snapshot().direction is Direction.POS_X  # 중단 방향부터
    sim.run_to_done()
    sim.kill()

    store = fresh_store(result_dir)
    record = store.load(SCAN_A)
    assert record.scan_id == SCAN_A and store.scan_ids() == (SCAN_A,)  # 새 작업이 아니다
    assert record.top == top_before                                    # 윗면을 다시 재지 않았다
    assert record.last_interruption.resumed_at is not None
    assert record.state.phase is Phase.DONE
    assert store.load_result(SCAN_A).shape.z_top.value == pytest.approx(BOX_TOP_Z)


def test_stop_then_process_restart_then_resume_from_the_record(result_dir, clock):
    first = SimScanManager(result_dir, clock)
    first.start(SCAN_A)
    first.find_top()
    first.find_edge()            # +x 확보
    assert first.start_slide() is Direction.NEG_X
    first.stop()
    top_before = first.store.load(SCAN_A).top
    first.kill()

    second = SimScanManager(result_dir, FakeClock(start_sec=1_790_300_000))
    candidate = second.store.find_resume_candidate('')
    record = candidate.record
    assert record.scan_id == SCAN_A and candidate.is_latest and candidate.skipped_errors == ()
    assert record.state.phase is Phase.STOPPED and record.state.progress == 1
    assert record.last_interruption.direction is Direction.NEG_X
    assert record.confirmed_edges == (Direction.POS_X,)
    assert record.edges[Direction.NEG_X].status == STATUS_NOT_ATTEMPTED
    assert not record.home_return_since_resume_point and not record.stopped_during_final_homing
    assert record.state.motion_id == 0 and record.last_motion_id == 3

    second.restore(record)
    assert second.resume(SCAN_A).accepted
    assert second.sm.snapshot().direction is Direction.NEG_X
    second.run_to_done()
    second.kill()

    final = fresh_store(result_dir).load(SCAN_A)
    # 하강 1 · +x 2 · 중단된 -x 3 에 이어 재개 뒤의 -x 4 · +y 5 · -y 6. 번호를 되돌려 쓰지 않았다
    assert final.last_motion_id == 6
    assert final.top == top_before
    assert final.edges[Direction.POS_X] == record.edges[Direction.POS_X]  # 기존 측정값 유지
    assert final.state.phase is Phase.DONE and len(final.interruptions) == 1
    shape = fresh_store(result_dir).load_result(SCAN_A).shape
    assert (shape.width, shape.length, shape.height) == pytest.approx((0.10, 0.06, 0.04))


# ---- 3. 안전복귀를 거친 작업 ----

def test_home_after_stop_is_visible_after_restart_and_resume_is_refused(result_dir, clock):
    first = SimScanManager(result_dir, clock)
    first.start(SCAN_A)
    first.find_top()
    first.start_slide()
    first.stop()
    first.home()
    assert first.resume().reason is Reason.NOT_SUPPORTED
    first.kill()

    second = SimScanManager(result_dir, FakeClock(start_sec=1_790_300_000))
    record = second.store.find_resume_candidate().record
    assert record.home_return_since_resume_point and record.home_return.completed is True
    assert record.home_return.origin_phase is Phase.STOPPED
    assert record.top.valid and record.state.phase is Phase.STOPPED  # 측정값 · 로그는 보존된다
    second.restore(record)
    assert second.resume().reason is Reason.NOT_SUPPORTED  # 메모리의 판정과 기록의 사실이 같다
    second.kill()
    assert fresh_store(result_dir).load(SCAN_A).last_interruption.resumed_at is None


def test_stop_during_safety_homing_still_refuses_resume_after_restart(result_dir, clock):
    first = SimScanManager(result_dir, clock)
    first.start(SCAN_A)
    first.find_top()
    first.find_edge()
    assert first.start_slide() is Direction.NEG_X
    first.stop()
    first.begin_home()
    first.stop()  # 복귀 도중에 다시 중지. 로봇은 중단 위치도 홈도 아닌 곳에 있다
    assert first.resume().reason is Reason.NOT_SUPPORTED
    first.kill()

    second = SimScanManager(result_dir, FakeClock(start_sec=1_790_300_000))
    record = second.store.find_resume_candidate().record
    assert record.last_interruption.phase is Phase.HOMING
    assert record.resume_point.direction is Direction.NEG_X and record.resume_point.progress == 1
    assert record.home_return_since_resume_point and record.home_return.completed is None
    second.restore(record)
    assert second.resume().reason is Reason.NOT_SUPPORTED
    second.kill()


# ---- 4. 마무리 HOMING 중 중지 ----

def test_stop_during_final_homing_keeps_the_result(result_dir, clock):
    sim = SimScanManager(result_dir, clock)
    sim.start(SCAN_A)
    sim.find_top()
    while sim.sm.phase is Phase.EDGE_SEARCH:
        sim.find_edge()
    sim.geometry()
    assert sim.sm.phase is Phase.HOMING
    sim.stop(during_final_homing=True)
    assert sim.resume().reason is Reason.NO_RESUMABLE_SCAN
    sim.kill()

    candidate = fresh_store(result_dir).find_resume_candidate()
    assert candidate.record.stopped_during_final_homing
    assert candidate.record.result_saved and candidate.result_file_exists
    assert candidate.record.state.phase is Phase.STOPPED
    assert fresh_store(result_dir).load_result(SCAN_A).shape.success


# ---- 5. 탐색 실패 ----

def test_no_edge_failure_is_recorded_without_fake_values(result_dir, clock):
    sim = SimScanManager(result_dir, clock, no_edge_in=Direction.NEG_X)
    sim.start(SCAN_A)
    sim.find_top()
    sim.run_to_done()
    assert sim.sm.phase is Phase.ERROR
    sim.kill()

    store = fresh_store(result_dir)
    record = store.load(SCAN_A)
    failed = record.edges[Direction.NEG_X]
    assert failed.status == STATUS_FAILED and failed.reason_code == int(Reason.NO_EDGE)
    assert failed.detection is None and failed.stop_pose is not None  # 값은 없고 위치는 있다
    assert record.edges[Direction.POS_X].status == STATUS_CONFIRMED
    assert record.edges[Direction.POS_Y].status == STATUS_NOT_ATTEMPTED
    assert record.failure.reason_code == int(Reason.NO_EDGE)
    assert record.failure.phase is Phase.EDGE_SEARCH
    assert record.state.phase is Phase.ERROR and record.state.progress == 1
    assert not record.result_saved and not store.has_result(SCAN_A)
    assert not record.home_return_requested  # 실패가 홈 복귀를 부르지 않았다
    assert record.slot(TOP).valid


# ---- 6. 새 작업과 재개의 구분 ----

def test_new_scan_gets_its_own_record_and_old_one_is_untouched(result_dir, clock):
    sim = SimScanManager(result_dir, clock)
    sim.start(SCAN_A)
    sim.find_top()
    sim.start_slide()
    sim.stop()
    sim.flush()
    old = sim.store.load(SCAN_A)

    sim.start(SCAN_B)  # 재시작이 아니라 새 작업
    sim.find_top()
    sim.run_to_done()
    sim.kill()

    store = fresh_store(result_dir)
    assert store.scan_ids() == (SCAN_B, SCAN_A)
    assert store.load(SCAN_A) == old
    assert store.load(SCAN_B).state.phase is Phase.DONE
    candidate = store.find_resume_candidate()
    assert candidate.record.scan_id == SCAN_A and candidate.newer_scan_ids == (SCAN_B,)


# ---- 7. 프로세스가 모션 도중에 죽었다 ----

def test_process_death_mid_motion_leaves_a_truthful_record(result_dir, clock):
    sim = SimScanManager(result_dir, clock)
    sim.start(SCAN_A)
    sim.find_top()
    sim.find_edge()
    sim.start_slide()
    sim.kill()  # 중지 명령 없이 죽었다

    record = fresh_store(result_dir).find_resume_candidate().record
    assert record.state.phase is Phase.EDGE_SEARCH and record.state.direction is Direction.NEG_X
    assert record.state.motion_id != 0            # 모션 도중이었다
    assert record.last_interruption is None       # 중단 위치는 모른다. 지어내지 않는다
    assert record.confirmed_edges == (Direction.POS_X,)


# ---- 8. 느린 디스크가 작업 중지를 막지 않는다 ----

def test_slow_disk_does_not_block_stop(result_dir, clock):
    sim = SimScanManager(result_dir, clock)
    sim.start(SCAN_A)
    sim.find_top()
    sim.start_slide()
    sim.flush()

    gate = threading.Event()
    sim.writer.submit(gate.wait)  # 쓰기 스레드가 디스크에서 멈춰 있다
    done = []

    def operator_stop():
        done.append(sim.sm.request(Command.STOP))
        sim.sm.notify(Signal.STOP_CONFIRMED)

    thread = threading.Thread(target=operator_stop)
    thread.start()
    thread.join(timeout=5.0)
    assert not thread.is_alive() and done[0].accepted  # 쓰기를 기다리지 않고 접수 · 확인됐다
    assert sim.sm.phase is Phase.STOPPED
    assert sim.store.load(SCAN_A).state.phase is Phase.EDGE_SEARCH  # 파일은 아직 옛 상태

    gate.set()
    sim.flush()
    assert sim.store.load(SCAN_A).state.phase is Phase.STOPPED  # 밀린 기록이 순서대로 들어갔다
    sim.kill()


# ---- 9. 무작위 명령열: 기록의 사실만으로 상태 기계의 RESUME 판정을 맞힐 수 있는가 ----

def verdict_from_facts(record):
    """T26 이 기록만 보고 내릴 판정. 여기서 쓰는 것은 store 가 돌려주는 사실뿐이다."""
    if record.failure is not None or record.resume_point is None:
        return Reason.NO_RESUMABLE_SCAN
    if record.result_saved or record.stopped_during_final_homing:
        return Reason.NO_RESUMABLE_SCAN  # 측정이 이미 끝난 작업이다(7.4절)
    if record.home_return_since_resume_point:
        return Reason.NOT_SUPPORTED
    return Reason.OK


ACTIONS = {
    Phase.PREPARING: ('top', 'stop'),
    Phase.EDGE_SEARCH: ('edge', 'edge', 'stop', 'fail'),
    Phase.GEOMETRY: ('geometry', 'stop'),
    Phase.HOMING: ('homed', 'stop_final'),
    Phase.STOPPED: ('resume', 'resume', 'home', 'home_then_stop'),
    Phase.ERROR: ('home', 'home_then_stop', 'end'),
    Phase.DONE: ('home', 'home_then_stop', 'end'),
}


@pytest.mark.parametrize('seed', range(40))
def test_recorded_facts_predict_the_resume_verdict(result_dir, seed):
    rng = random.Random(seed)
    sim = SimScanManager(result_dir, FakeClock())
    sim.start(SCAN_A)

    for _ in range(30):
        action = rng.choice(ACTIONS[sim.sm.phase])
        if action == 'top':
            sim.find_top()
        elif action == 'edge':
            sim.find_edge()
        elif action == 'geometry':
            sim.geometry()
        elif action == 'homed':
            sim.finish_homing()
        elif action == 'stop':
            sim.stop()
        elif action == 'stop_final':
            sim.stop(during_final_homing=True)
        elif action == 'fail':
            sim.sm.notify(Signal.FAILED, reason_code=Reason.NO_EDGE, detail='fuzz')
            sim._write(sim.store.record_failure, sim.scan_id, sim.sm.failure)
        elif action == 'home':
            sim.home()
        elif action == 'home_then_stop':
            sim.begin_home()
            sim.stop()
        elif action == 'resume':
            sim.flush()
            # 프로세스를 재시작한 것과 같은 조건: 새 인스턴스가 파일에서 읽은 사실만 쓴다
            expected = verdict_from_facts(fresh_store(result_dir).load(SCAN_A))
            assert sim.resume().reason is expected
        else:
            break
    sim.kill()
    record = fresh_store(result_dir).load(SCAN_A)
    assert record.state.phase is not Phase.STOPPING and record.revision > 1
