"""ResultStore: 새 인스턴스로 다시 읽기, 원자적 쓰기, 재개 후보, 깨진 파일 처리. tmp_path 만 쓴다."""

import json
import os
from pathlib import Path
import random
import signal
import subprocess
import sys
import threading
import time

import pytest
from result_store_helpers import begin
from result_store_helpers import bias_corrections
from result_store_helpers import box_shape
from result_store_helpers import CONFIG
from result_store_helpers import edge_measurement
from result_store_helpers import failed_shape
from result_store_helpers import FakeClock
from result_store_helpers import FRAMES
from result_store_helpers import NODE_PARAMS
from result_store_helpers import ORDER
from result_store_helpers import pose
from result_store_helpers import SCAN_A
from result_store_helpers import SCAN_B
from result_store_helpers import SCAN_C
from result_store_helpers import snapshot
from result_store_helpers import top_measurement
from scan_manager.contract_enums import Direction
from scan_manager.contract_enums import Phase
from scan_manager.result_store import CorruptRecordError
from scan_manager.result_store import Interruption
from scan_manager.result_store import MeasurementAlreadyConfirmed
from scan_manager.result_store import PROGRESS_FILE
from scan_manager.result_store import RecordNotFound
from scan_manager.result_store import RecordStateError
from scan_manager.result_store import RESULT_FILE
from scan_manager.result_store import ResultAlreadySaved
from scan_manager.result_store import ResultStore
from scan_manager.result_store import ScanAlreadyExists
from scan_manager.result_store import Stamp
from scan_manager.result_store import STATUS_CONFIRMED
from scan_manager.result_store import STATUS_FAILED
from scan_manager.result_store import STATUS_NOT_ATTEMPTED
from scan_manager.result_store import TOP
from scan_manager.result_store import UnsupportedSchemaError
from scan_manager.result_store.store import _atomic_write
from scan_manager.state_machine import Failure


@pytest.fixture
def store(tmp_path):
    return ResultStore(tmp_path / 'data', now_fn=FakeClock())


def reopen(store):
    """프로세스를 재시작한 것처럼 같은 디렉터리에 새 인스턴스를 만든다."""
    return ResultStore(store.result_dir, now_fn=FakeClock(start_sec=1_790_100_000))


def progress_path(store, scan_id=SCAN_A):
    return store.result_dir / scan_id / PROGRESS_FILE


def stop_in_edge_search(store, scan_id=SCAN_A, progress=1, direction=Direction.NEG_X):
    store.record_stop(scan_id, Interruption(
        Phase.EDGE_SEARCH, direction, progress, pose=pose(0.2, 0.0, 0.048)))
    store.record_state(snapshot(scan_id, Phase.STOPPED, progress=progress))


# ---- 기록과 다시 읽기 ----

def test_constructor_takes_the_directory_and_creates_nothing(tmp_path):
    target = tmp_path / 'not-yet'
    fresh = ResultStore(target)
    assert fresh.scan_ids() == () and fresh.list_scans() == ([], [])
    assert fresh.find_resume_candidate().record is None
    assert not target.exists()  # 읽기만으로는 디렉터리를 만들지 않는다
    with pytest.raises(ValueError):
        ResultStore('')


def test_begin_scan_writes_the_whole_header(store):
    begin(store)
    record = reopen(store).load(SCAN_A)
    assert record.scan_id == SCAN_A
    assert record.started_at == Stamp(1_790_000_000, 0)
    assert record.state.phase is Phase.PREPARING
    assert record.frames == FRAMES and record.direction_order == ORDER
    assert record.config == CONFIG and record.config.drop_limit_m is None
    assert record.node_params == NODE_PARAMS
    assert record.top.status == STATUS_NOT_ATTEMPTED
    assert all(record.edges[d].status == STATUS_NOT_ATTEMPTED for d in ORDER)
    assert record.interruptions == [] and record.failure is None
    assert not record.home_return_requested and not record.result_saved
    assert record.result_success is None

    data = json.loads(progress_path(store).read_text(encoding='utf-8'))
    assert data['schema_version'] == 1 and data['kind'] == 'contact_scan.progress'
    assert data['units']['length'] == 'm'


def test_begin_scan_twice_is_rejected(store):
    begin(store)
    with pytest.raises(ScanAlreadyExists):
        begin(store)


def test_begin_scan_checks_inputs(store):
    with pytest.raises(ValueError):
        begin(store, scan_id='../escape')
    with pytest.raises(ValueError):
        begin(store, state=snapshot(SCAN_B))  # 다른 작업의 상태
    with pytest.raises(ValueError):
        begin(store, direction_order=ORDER[:3])
    assert store.scan_ids() == ()


def test_everything_survives_a_new_instance(store):
    begin(store)
    store.record_state(snapshot(phase=Phase.TOP_SEARCH, motion_id=1))
    store.record_top(SCAN_A, top_measurement())
    store.record_state(snapshot(phase=Phase.EDGE_SEARCH, direction=Direction.POS_X, motion_id=2))
    store.record_edge(SCAN_A, Direction.POS_X, edge_measurement(Direction.POS_X))
    store.record_attempt_failed(SCAN_A, Direction.NEG_X, 301, 'max_distance', stop_pose=pose())
    store.record_failure(SCAN_A, Failure(301, 'max_distance', Phase.EDGE_SEARCH), pose(0.3))
    written = store.record_state(snapshot(phase=Phase.ERROR, progress=1))

    record = reopen(store).load(SCAN_A)
    assert record == written
    assert record.top.detection == top_measurement().detection
    assert record.top.stop_pose == top_measurement().stop_pose
    assert record.top.detection.pose != record.top.stop_pose  # 판정 좌표 ≠ 정지 좌표
    assert record.edges[Direction.POS_X].status == STATUS_CONFIRMED
    assert record.edges[Direction.NEG_X].status == STATUS_FAILED
    assert record.edges[Direction.NEG_X].reason_code == 301
    assert record.edges[Direction.POS_Y].status == STATUS_NOT_ATTEMPTED
    assert record.confirmed_edges == (Direction.POS_X,)
    assert record.failure.phase is Phase.EDGE_SEARCH and record.failure.reason_code == 301
    assert record.failure.pose == pose(0.3)      # 원인 · 단계 · 위치가 같이 남는다(BRD 4.2.5)
    assert record.revision == 8 and record.updated_at.ns > record.started_at.ns


def test_last_motion_id_survives_the_reset_to_zero(store):
    begin(store)
    store.record_state(snapshot(phase=Phase.EDGE_SEARCH, direction=Direction.POS_X, motion_id=7))
    store.record_state(snapshot(phase=Phase.STOPPED))  # 휴지 phase 에서는 motion_id 가 0 이다
    record = reopen(store).load(SCAN_A)
    assert record.state.motion_id == 0 and record.last_motion_id == 7


def test_missing_values_are_null_in_the_file(store):
    begin(store)
    store.record_top(SCAN_A, top_measurement())
    store.record_attempt_failed(SCAN_A, Direction.POS_X, 301)
    text = progress_path(store).read_text(encoding='utf-8')
    assert 'NaN' not in text and 'Infinity' not in text
    data = json.loads(text)
    top = data['measurements']['top']
    assert top['detection']['z_drop_m'] is None and top['detection']['z_drop_valid'] is False
    failed = data['measurements']['edges']['POS_X']
    assert failed['valid'] is False and failed['detection'] is None
    assert failed['stop_pose'] is None and failed['stop_pose_valid'] is False
    untouched = data['measurements']['edges']['NEG_Y']
    assert untouched['status'] == 'NOT_ATTEMPTED' and untouched['reason_code'] is None

    record = reopen(store).load(SCAN_A)
    assert record.top.detection.z_drop_m is None
    assert record.edges[Direction.POS_X].detection is None
    assert record.edges[Direction.NEG_Y].reason_code is None


def test_confirmed_measurement_is_not_overwritten(store):
    begin(store)
    store.record_top(SCAN_A, top_measurement(z=0.05))
    store.record_edge(SCAN_A, Direction.POS_X, edge_measurement(Direction.POS_X))
    with pytest.raises(MeasurementAlreadyConfirmed):
        store.record_top(SCAN_A, top_measurement(z=0.07))
    with pytest.raises(MeasurementAlreadyConfirmed):
        store.record_edge(SCAN_A, Direction.POS_X, edge_measurement(Direction.POS_X, 0.9))
    with pytest.raises(MeasurementAlreadyConfirmed):
        store.record_attempt_failed(SCAN_A, TOP, 300)
    record = store.load(SCAN_A)
    assert record.top.detection.pose.position_m[2] == pytest.approx(0.05)
    assert record.revision == 3  # 거절된 호출은 파일을 건드리지 않았다


def test_failed_attempt_can_be_confirmed_later(store):
    begin(store)
    store.record_attempt_failed(SCAN_A, Direction.POS_X, 301)
    store.record_edge(SCAN_A, Direction.POS_X, edge_measurement(Direction.POS_X))
    slot = store.load(SCAN_A).edges[Direction.POS_X]
    assert slot.status == STATUS_CONFIRMED and slot.reason_code is None


def test_measurement_type_must_match_target(store):
    begin(store)
    with pytest.raises(ValueError):
        store.record_top(SCAN_A, edge_measurement(Direction.POS_X))
    with pytest.raises(ValueError):
        store.record_edge(SCAN_A, Direction.POS_X, top_measurement())
    with pytest.raises(ValueError):
        store.record_edge(SCAN_A, Direction.NONE, edge_measurement(Direction.POS_X))


def test_unknown_scan_is_an_error_not_a_silent_noop(store):
    with pytest.raises(RecordNotFound):
        store.record_state(snapshot(SCAN_B, Phase.TOP_SEARCH))
    with pytest.raises(ValueError):
        store.record_state(snapshot('', Phase.IDLE))  # IDLE 의 scan_id 는 ""
    with pytest.raises(RecordNotFound):
        store.load(SCAN_B)
    assert store.scan_ids() == ()


# ---- 중지 · 재시작 · 안전복귀 ----

def test_stop_and_resume_are_kept_as_a_list(store):
    begin(store)
    stop_in_edge_search(store, progress=0, direction=Direction.POS_X)
    with_stop = reopen(store).load(SCAN_A)
    last = with_stop.last_interruption
    assert (last.phase, last.direction, last.progress) == (Phase.EDGE_SEARCH, Direction.POS_X, 0)
    assert last.pose == pose(0.2, 0.0, 0.048) and last.pose.frame_id == 'base_link'
    assert last.stopped_at is not None and last.resumed_at is None
    assert not with_stop.stopped_during_final_homing

    store.record_resume(SCAN_A)
    assert store.load(SCAN_A).last_interruption.resumed_at is not None
    with pytest.raises(RecordStateError):
        store.record_resume(SCAN_A)  # 같은 중지를 두 번 재시작할 수 없다

    store.record_stop(SCAN_A, Interruption(Phase.EDGE_SEARCH, Direction.NEG_X, 1, pose=None))
    record = reopen(store).load(SCAN_A)
    assert len(record.interruptions) == 2
    assert record.interruptions[0].resumed_at is not None
    assert record.last_interruption.pose is None and record.last_interruption.resumed_at is None


def test_resume_without_stop_is_rejected(store):
    begin(store)
    with pytest.raises(RecordStateError):
        store.record_resume(SCAN_A)


def test_home_return_facts(store):
    begin(store)
    stop_in_edge_search(store)
    assert not store.load(SCAN_A).home_return_since_resume_point
    with pytest.raises(RecordStateError):
        store.record_home_finished(SCAN_A, True)

    store.record_home_requested(SCAN_A, origin_phase=Phase.STOPPED)
    requested = reopen(store).load(SCAN_A)
    assert requested.home_return_requested and requested.home_return_since_resume_point
    assert requested.home_return.completed is None  # 끝났는지 모른다. False 가 아니다
    assert requested.home_return.origin_phase is Phase.STOPPED

    store.record_home_finished(SCAN_A, True, final_pose=pose(0.0, 0.0, 0.4))
    finished = reopen(store).load(SCAN_A)
    assert finished.home_return.completed is True
    assert finished.home_return.final_pose == pose(0.0, 0.0, 0.4)
    assert finished.home_return_requested


def test_stop_during_safety_homing_does_not_move_the_resume_point(store):
    begin(store)
    stop_in_edge_search(store, progress=1, direction=Direction.NEG_X)
    store.record_home_requested(SCAN_A, origin_phase=Phase.STOPPED)
    store.record_stop(
        SCAN_A, Interruption(Phase.HOMING, Direction.NONE, 1, pose=pose(0.2, 0, 0.2)))
    record = reopen(store).load(SCAN_A)
    assert record.last_interruption.phase is Phase.HOMING     # 가장 최근 중지는 복귀 도중이다
    assert record.resume_point.phase is Phase.EDGE_SEARCH     # 재개 지점은 그대로 -x 다
    assert record.resume_point.direction is Direction.NEG_X
    assert record.home_return_since_resume_point              # 로봇은 이미 중단 위치를 떠났다
    assert record.home_return.completed is None
    assert not record.stopped_during_final_homing


def test_stop_during_resuming_does_not_move_the_resume_point(store):
    begin(store)
    stop_in_edge_search(store, progress=2, direction=Direction.POS_Y)
    store.record_resume(SCAN_A)
    store.record_stop(SCAN_A, Interruption(Phase.RESUMING, Direction.NONE, 2))
    record = reopen(store).load(SCAN_A)
    assert record.resume_point.direction is Direction.POS_Y and record.resume_point.progress == 2
    assert record.last_interruption.phase is Phase.RESUMING
    assert not record.home_return_since_resume_point


def test_resume_point_is_none_without_a_measuring_stop(store):
    begin(store)
    assert store.load(SCAN_A).resume_point is None
    store.record_home_requested(SCAN_A, origin_phase=Phase.ERROR)
    store.record_stop(SCAN_A, Interruption(Phase.HOMING, Direction.NONE, 0))
    record = store.load(SCAN_A)
    assert record.resume_point is None and record.home_return_since_resume_point


def test_home_order_does_not_depend_on_the_clock(tmp_path):
    ticks = iter([Stamp(500), Stamp(400), Stamp(300), Stamp(200), Stamp(100), Stamp(50)])
    backwards = ResultStore(tmp_path / 'data', now_fn=lambda: next(ticks))  # 시계가 거꾸로 간다
    begin(backwards)
    backwards.record_stop(SCAN_A, Interruption(Phase.EDGE_SEARCH, Direction.POS_X, 0))
    backwards.record_home_requested(SCAN_A, origin_phase=Phase.STOPPED)
    assert backwards.load(SCAN_A).home_return_since_resume_point


def test_home_before_the_last_stop_is_told_apart(store):
    begin(store)
    stop_in_edge_search(store, progress=0, direction=Direction.POS_X)
    store.record_home_requested(SCAN_A, origin_phase=Phase.STOPPED)
    store.record_stop(SCAN_A, Interruption(Phase.EDGE_SEARCH, Direction.NEG_X, 1))
    record = store.load(SCAN_A)
    assert record.home_return_requested               # 접수한 적은 있다
    assert not record.home_return_since_resume_point  # 하지만 재개 지점(두 번째 중지)보다 앞이다


# ---- 최종 결과 ----

def test_result_is_saved_once_and_read_back(store):
    begin(store)
    saved = store.save_result(SCAN_A, box_shape(), bias_corrections())
    again = reopen(store)
    result = again.load_result(SCAN_A)
    assert result == saved
    assert result.shape == box_shape()
    assert result.bias_corrections[Direction.NEG_Y].correction_m == pytest.approx(0.0034)
    assert result.config == CONFIG and result.node_params == NODE_PARAMS
    record = again.load(SCAN_A)
    assert record.result_saved and record.result_success is True and again.has_result(SCAN_A)

    before = (store.result_dir / SCAN_A / RESULT_FILE).read_bytes()
    with pytest.raises(ResultAlreadySaved):
        again.save_result(SCAN_A, failed_shape())
    assert (store.result_dir / SCAN_A / RESULT_FILE).read_bytes() == before


def test_bias_corrections_are_only_in_the_result_file(store):
    begin(store)
    store.save_result(SCAN_A, box_shape(), bias_corrections())
    assert 'bias_corrections' not in progress_path(store).read_text(encoding='utf-8')
    data = json.loads((store.result_dir / SCAN_A / RESULT_FILE).read_text(encoding='utf-8'))
    assert sorted(data['bias_corrections']) == ['NEG_X', 'NEG_Y', 'POS_X', 'POS_Y']
    assert data['schema_version'] == 1 and data['kind'] == 'contact_scan.result'


def test_failed_shape_is_saved_with_nulls(store):
    begin(store)
    store.save_result(SCAN_A, failed_shape())
    result = reopen(store).load_result(SCAN_A)
    assert result.shape.success is False and result.shape.reason_code == 500
    assert result.shape.y_pos.value is None and result.shape.width is None
    assert all(not c.valid and c.correction_m is None for c in result.bias_corrections.values())
    record = store.load(SCAN_A)
    assert record.result_saved is True and record.result_success is False
    assert 'NaN' not in (store.result_dir / SCAN_A / RESULT_FILE).read_text(encoding='utf-8')


def test_result_needs_a_progress_record(store):
    with pytest.raises(RecordNotFound):
        store.save_result(SCAN_A, box_shape())
    with pytest.raises(RecordNotFound):
        store.load_result(SCAN_A)


def test_crash_between_result_and_progress_is_repaired(store, monkeypatch):
    begin(store)
    real_replace = os.replace

    def fail_on_progress(src, dst):
        if str(dst).endswith(PROGRESS_FILE):
            raise OSError('disk full')
        return real_replace(src, dst)

    monkeypatch.setattr(os, 'replace', fail_on_progress)
    with pytest.raises(OSError):
        store.save_result(SCAN_A, box_shape(), bias_corrections())
    monkeypatch.undo()

    again = reopen(store)
    assert again.has_result(SCAN_A) and not again.load(SCAN_A).result_saved
    assert again.find_resume_candidate().result_file_exists  # 사실이 드러난다
    with pytest.raises(ResultAlreadySaved):
        again.save_result(SCAN_A, failed_shape())
    record = again.load(SCAN_A)
    assert record.result_saved and record.result_success is True  # 있는 파일대로 고쳤다


# ---- 쓰기 도중의 실패 ----

@pytest.mark.parametrize('broken', ['replace', 'fsync'])
def test_failed_write_keeps_the_previous_record(store, monkeypatch, broken):
    begin(store)
    store.record_top(SCAN_A, top_measurement())
    before = progress_path(store).read_bytes()

    def boom(*_args, **_kwargs):
        raise OSError('power loss')

    monkeypatch.setattr(os, broken, boom)
    with pytest.raises(OSError):
        store.record_edge(SCAN_A, Direction.POS_X, edge_measurement(Direction.POS_X))
    monkeypatch.undo()

    assert progress_path(store).read_bytes() == before
    assert os.listdir(store.result_dir / SCAN_A) == [PROGRESS_FILE]  # 임시 파일을 남기지 않는다
    record = reopen(store).load(SCAN_A)
    assert record.top.valid and record.edges[Direction.POS_X].status == STATUS_NOT_ATTEMPTED
    # 같은 인스턴스도 파일과 어긋나지 않는다. 다시 기록하면 된다
    store.record_edge(SCAN_A, Direction.POS_X, edge_measurement(Direction.POS_X))
    assert store.load(SCAN_A).edges[Direction.POS_X].valid


def test_leftover_temp_file_from_a_killed_process_is_ignored(store):
    begin(store)
    leftover = store.result_dir / SCAN_A / f'.{PROGRESS_FILE}.999.1.tmp'
    leftover.write_text('{"schema_version": 1, "kind": "contact_scan.prog', encoding='utf-8')
    assert reopen(store).load(SCAN_A).scan_id == SCAN_A
    assert reopen(store).scan_ids() == (SCAN_A,)


def test_nan_never_reaches_the_disk(store):
    begin(store)
    before = progress_path(store).read_bytes()
    for leak in (float('nan'), float('inf')):
        with pytest.raises(ValueError):
            _atomic_write(progress_path(store), {'schema_version': 1, 'leak': leak})
    assert progress_path(store).read_bytes() == before
    assert os.listdir(store.result_dir / SCAN_A) == [PROGRESS_FILE]


def test_concurrent_writers_do_not_lose_updates(store):
    begin(store)
    errors = []

    def write(direction):
        try:
            store.record_edge(SCAN_A, direction, edge_measurement(direction))
        except Exception as error:  # noqa: B902
            errors.append(error)

    threads = [threading.Thread(target=write, args=(d,)) for d in ORDER]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert reopen(store).load(SCAN_A).confirmed_edges == ORDER


def test_reader_never_sees_a_half_written_file(store):
    begin(store)
    stop = threading.Event()
    problems = []

    def read_loop():
        reader = reopen(store)
        while not stop.is_set():
            try:
                reader.load(SCAN_A)
            except Exception as error:  # noqa: B902
                problems.append(error)

    thread = threading.Thread(target=read_loop, daemon=True)
    thread.start()
    try:
        for motion_id in range(1, 120):
            store.record_state(snapshot(phase=Phase.TOP_SEARCH, motion_id=motion_id))
    finally:
        stop.set()  # 쓰기가 실패해도 읽기 스레드를 남기지 않는다(남으면 pytest 가 끝나지 않는다)
        thread.join(timeout=10.0)
    assert problems == [] and not thread.is_alive()


def test_sigkill_in_the_middle_of_writes_leaves_a_readable_record(store):
    begin(store)
    code = (
        'import sys, itertools\n'
        'from scan_manager.result_store import ResultStore\n'
        'from scan_manager.state_machine import Snapshot\n'
        'from scan_manager.contract_enums import Phase, Direction\n'
        'store = ResultStore(sys.argv[1])\n'
        "print('ready', flush=True)\n"
        'for n in itertools.count(1):\n'
        '    state = Snapshot(sys.argv[2], Phase.TOP_SEARCH, Direction.NONE, 0, 4, n)\n'
        '    store.record_state(state)\n'
    )
    package_root = str(Path(__file__).resolve().parents[1])
    revision = store.load(SCAN_A).revision
    for _ in range(3):
        child = subprocess.Popen(
            [sys.executable, '-c', code, str(store.result_dir), SCAN_A],
            cwd=package_root, stdout=subprocess.PIPE)
        assert child.stdout.readline().strip() == b'ready'
        time.sleep(0.15)
        child.send_signal(signal.SIGKILL)  # 쓰는 도중에 죽인다
        child.wait()
        child.stdout.close()
        record = reopen(store).load(SCAN_A)  # 깨지지 않았다
        assert 0 < record.state.motion_id <= record.last_motion_id  # 자식은 매번 1부터 다시 센다
        assert record.revision > revision
        revision = record.revision
    reopen(store).record_state(snapshot(phase=Phase.EDGE_SEARCH, direction=Direction.POS_X))
    assert reopen(store).load(SCAN_A).state.phase is Phase.EDGE_SEARCH  # 이어서 쓸 수 있다


# ---- 깨진 파일 · 모르는 스키마 ----

def corrupt(store, scan_id, text):
    progress_path(store, scan_id).write_text(text, encoding='utf-8')


@pytest.mark.parametrize('text', [
    '', '{"schema_version": 1, "kind": "contact_scan.progr', '[]',
    '{"kind": "contact_scan.progress"}',
    '{"schema_version": "1", "kind": "contact_scan.progress"}',
    '{"schema_version": 1, "kind": "contact_scan.result"}',
    '{"schema_version": 1, "kind": "contact_scan.progress"}',
])
def test_broken_file_raises_corrupt(store, text):
    begin(store)
    corrupt(store, SCAN_A, text)
    with pytest.raises(CorruptRecordError) as caught:
        reopen(store).load(SCAN_A)
    assert caught.value.scan_id == SCAN_A and caught.value.path == progress_path(store)
    with pytest.raises(CorruptRecordError):
        store.record_state(snapshot(phase=Phase.TOP_SEARCH))  # 깨진 기록 위에 덮어쓰지 않는다


def test_random_damage_only_raises_store_errors(store):
    """파일의 아무 곳이나 망가뜨려도 CorruptRecordError · UnsupportedSchemaError 말고는 새지 않는다."""
    begin(store)
    store.record_top(SCAN_A, top_measurement())
    store.record_edge(SCAN_A, Direction.POS_X, edge_measurement(Direction.POS_X))
    store.record_attempt_failed(SCAN_A, Direction.NEG_X, 301, 'x', stop_pose=pose())
    stop_in_edge_search(store)
    store.record_home_requested(SCAN_A, origin_phase=Phase.STOPPED)
    store.save_result(SCAN_A, box_shape(), bias_corrections())
    rng = random.Random(20)
    junk = [None, True, False, 0, -1, 1.5, '', 'x', [], {}, [1, 2], {'a': 1}, 2 ** 70, 'NaN']

    def damage(node):
        """무작위로 고른 한 곳을 지우거나 다른 자료형으로 바꾼다."""
        paths = []

        def walk(value, path):
            if isinstance(value, dict):
                for key in value:
                    paths.append(path + [key])
                    walk(value[key], path + [key])
            elif isinstance(value, list):
                for index in range(len(value)):
                    paths.append(path + [index])
                    walk(value[index], path + [index])
        walk(node, [])
        target = rng.choice(paths)
        parent = node
        for key in target[:-1]:
            parent = parent[key]
        if rng.random() < 0.3:
            del parent[target[-1]]
        else:
            parent[target[-1]] = rng.choice(junk)

    for name, load in ((PROGRESS_FILE, store.load), (RESULT_FILE, store.load_result)):
        path = store.result_dir / SCAN_A / name
        original = path.read_text(encoding='utf-8')
        rejected = 0
        for _ in range(400):
            data = json.loads(original)
            damage(data)
            path.write_text(json.dumps(data), encoding='utf-8')
            try:
                load(SCAN_A)
            except (CorruptRecordError, UnsupportedSchemaError):
                rejected += 1
        path.write_text(original, encoding='utf-8')
        assert load(SCAN_A) is not None
        assert rejected > 300  # 대부분의 훼손은 거절된다(자유 형식인 node_params · detail 등은 예외)


def test_nan_literal_in_file_is_corrupt(store):
    begin(store)
    store.record_top(SCAN_A, top_measurement())
    text = progress_path(store).read_text(encoding='utf-8')
    corrupt(store, SCAN_A, text.replace('"force_delta_n": 3.4', '"force_delta_n": NaN'))
    with pytest.raises(CorruptRecordError):
        store.load(SCAN_A)


def test_nan_in_a_key_the_schema_does_not_read_is_still_corrupt(store):
    begin(store)
    text = progress_path(store).read_text(encoding='utf-8')
    corrupt(store, SCAN_A, text.replace('"schema_version": 1,', '"schema_version": 1, "x": NaN,'))
    with pytest.raises(CorruptRecordError, match='NaN'):
        store.load(SCAN_A)


def test_zero_in_place_of_null_is_corrupt(store):
    begin(store)
    store.record_top(SCAN_A, top_measurement())
    text = progress_path(store).read_text(encoding='utf-8')
    assert '"z_drop_m": null' in text
    corrupt(store, SCAN_A, text.replace('"z_drop_m": null', '"z_drop_m": 0.0'))
    with pytest.raises(CorruptRecordError, match='0 금지'):
        store.load(SCAN_A)


def test_a_failure_without_a_position_is_null_in_the_file(store):
    """위치를 모르는 실패. 0 · (0, 0, 0) 이 아니라 null + pose_valid=false 다(규칙 4)."""
    begin(store)
    store.record_failure(SCAN_A, Failure(300, '접촉이 없다', Phase.TOP_SEARCH))
    failure = json.loads(progress_path(store).read_text(encoding='utf-8'))['failure']
    assert failure['pose'] is None and failure['pose_valid'] is False
    assert reopen(store).load(SCAN_A).failure.pose is None


def test_a_failure_recorded_before_the_pose_field_still_loads(store):
    """pose 를 남기지 않던 옛 기록(같은 schema_version). 그대로 읽히고, 이어서 쓸 수 있다."""
    begin(store)
    store.record_failure(SCAN_A, Failure(300, '접촉이 없다', Phase.TOP_SEARCH), pose())
    data = json.loads(progress_path(store).read_text(encoding='utf-8'))
    assert data['failure'].pop('pose_valid') is True and data['failure'].pop('pose') is not None
    corrupt(store, SCAN_A, json.dumps(data))

    record = reopen(store).load(SCAN_A)
    assert (record.failure.reason_code, record.failure.phase) == (300, Phase.TOP_SEARCH)
    assert record.failure.pose is None            # 남기지 않은 좌표를 지어내지 않는다
    store.record_state(snapshot(phase=Phase.ERROR))
    again = json.loads(progress_path(store).read_text(encoding='utf-8'))['failure']
    assert again['pose'] is None and again['pose_valid'] is False


def test_scan_id_in_file_must_match_directory(store):
    begin(store)
    begin(store, SCAN_B)
    corrupt(store, SCAN_B, progress_path(store, SCAN_A).read_text(encoding='utf-8'))
    with pytest.raises(CorruptRecordError):
        store.load(SCAN_B)


def test_unknown_schema_version_is_not_read(store):
    begin(store)
    data = json.loads(progress_path(store).read_text(encoding='utf-8'))
    data['schema_version'] = 2
    corrupt(store, SCAN_A, json.dumps(data))
    with pytest.raises(UnsupportedSchemaError) as caught:
        store.load(SCAN_A)
    assert caught.value.found == 2 and caught.value.scan_id == SCAN_A
    with pytest.raises(UnsupportedSchemaError):
        store.record_state(snapshot(phase=Phase.TOP_SEARCH))
    assert json.loads(progress_path(store).read_text(encoding='utf-8'))['schema_version'] == 2


def test_broken_record_does_not_block_the_others(store):
    begin(store, SCAN_A)
    begin(store, SCAN_B)
    begin(store, SCAN_C)
    corrupt(store, SCAN_B, 'not json')
    again = reopen(store)
    assert again.load(SCAN_A).scan_id == SCAN_A
    assert again.load(SCAN_C).scan_id == SCAN_C
    again.record_state(snapshot(SCAN_A, Phase.TOP_SEARCH))  # 다른 작업은 계속 쓸 수 있다
    records, errors = again.list_scans()
    assert [r.scan_id for r in records] == [SCAN_C, SCAN_A]
    assert [e.scan_id for e in errors] == [SCAN_B]
    assert isinstance(errors[0], CorruptRecordError)


def test_foreign_entries_in_result_dir_are_not_records(store):
    begin(store)
    (store.result_dir / 'notes.txt').write_text('x', encoding='utf-8')
    (store.result_dir / 'tmp').mkdir()
    (store.result_dir / SCAN_B).mkdir()  # begin_scan 도중에 죽어 비어 있는 디렉터리
    assert store.scan_ids() == (SCAN_A,)


# ---- 재개 후보 ----

def finish(store, scan_id):
    store.save_result(scan_id, box_shape(), bias_corrections())
    store.record_state(snapshot(scan_id, Phase.DONE, progress=4))


def test_latest_interrupted_scan_is_chosen(store):
    begin(store, SCAN_A)
    stop_in_edge_search(store, SCAN_A, progress=1)
    begin(store, SCAN_B)
    stop_in_edge_search(store, SCAN_B, progress=2, direction=Direction.POS_Y)
    candidate = reopen(store).find_resume_candidate()
    assert candidate.record.scan_id == SCAN_B and candidate.is_latest
    assert candidate.record.state.progress == 2
    assert candidate.record.last_interruption.direction is Direction.POS_Y
    assert candidate.skipped_errors == () and not candidate.result_file_exists


def test_done_scans_are_excluded(store):
    begin(store, SCAN_A)
    stop_in_edge_search(store, SCAN_A)
    begin(store, SCAN_B)
    finish(store, SCAN_B)
    candidate = reopen(store).find_resume_candidate()
    assert candidate.record.scan_id == SCAN_A
    assert candidate.newer_scan_ids == (SCAN_B,) and not candidate.is_latest  # 사실만 알린다
    assert candidate.skipped_errors == ()


def test_no_candidate_when_everything_is_done(store):
    begin(store, SCAN_A)
    finish(store, SCAN_A)
    candidate = reopen(store).find_resume_candidate()
    assert candidate.record is None and not candidate.is_latest
    assert candidate.newer_scan_ids == (SCAN_A,)


def test_latest_error_scan_is_the_candidate_not_an_older_stop(store):
    begin(store, SCAN_A)
    stop_in_edge_search(store, SCAN_A)
    begin(store, SCAN_B)
    store.record_failure(SCAN_B, Failure(400, 'over force', Phase.EDGE_SEARCH))
    store.record_state(snapshot(SCAN_B, Phase.ERROR))
    candidate = reopen(store).find_resume_candidate()
    assert candidate.record.scan_id == SCAN_B
    assert candidate.record.failure.reason_code == 400
    assert candidate.record.last_interruption is None


def test_scan_killed_mid_motion_is_still_found(store):
    begin(store)
    store.record_state(snapshot(phase=Phase.EDGE_SEARCH, direction=Direction.POS_X, motion_id=3))
    candidate = reopen(store).find_resume_candidate()
    assert candidate.record.state.phase is Phase.EDGE_SEARCH
    assert candidate.record.last_interruption is None  # 중지 기록이 없다는 사실이 남는다


def test_home_return_and_final_homing_flags_are_preserved(store):
    begin(store, SCAN_A)
    stop_in_edge_search(store, SCAN_A)
    store.record_home_requested(SCAN_A, origin_phase=Phase.STOPPED)
    homed = reopen(store).find_resume_candidate(SCAN_A)
    assert homed.record.home_return_requested and homed.record.home_return_since_resume_point
    assert not homed.record.stopped_during_final_homing

    begin(store, SCAN_B)
    store.save_result(SCAN_B, box_shape(), bias_corrections())
    store.record_stop(SCAN_B, Interruption(
        Phase.HOMING, Direction.NONE, 4, pose=pose(0.1, 0.1, 0.2), during_final_homing=True))
    store.record_state(snapshot(SCAN_B, Phase.STOPPED, progress=4))
    final = reopen(store).find_resume_candidate()
    assert final.record.scan_id == SCAN_B
    assert final.record.stopped_during_final_homing
    assert final.record.result_saved and final.result_file_exists
    assert not final.record.home_return_requested


def test_candidate_by_scan_id(store):
    begin(store, SCAN_A)
    stop_in_edge_search(store, SCAN_A)
    begin(store, SCAN_B)
    finish(store, SCAN_B)
    again = reopen(store)
    chosen = again.find_resume_candidate(SCAN_A)
    assert chosen.record.scan_id == SCAN_A and chosen.newer_scan_ids == (SCAN_B,)
    done = again.find_resume_candidate(SCAN_B)
    assert done.record.state.phase is Phase.DONE and done.is_latest  # 판단은 호출 측이 한다
    assert again.find_resume_candidate(SCAN_C).record is None
    with pytest.raises(ValueError):
        again.find_resume_candidate('../x')


def test_unreadable_newer_record_is_reported_not_hidden(store):
    begin(store, SCAN_A)
    stop_in_edge_search(store, SCAN_A)
    begin(store, SCAN_B)
    corrupt(store, SCAN_B, '{')
    candidate = reopen(store).find_resume_candidate()
    assert candidate.record.scan_id == SCAN_A and not candidate.is_latest
    assert [e.scan_id for e in candidate.skipped_errors] == [SCAN_B]
    with pytest.raises(CorruptRecordError):
        reopen(store).find_resume_candidate(SCAN_B)  # 지정한 기록이 깨졌으면 예외다
