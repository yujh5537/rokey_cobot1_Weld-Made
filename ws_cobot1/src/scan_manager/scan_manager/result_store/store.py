"""result_store: 진행 기록과 최종 결과를 메인 PC 파일로 보존한다 (순수 Python, rclpy 없음).

파일 구조 (계약 9장 TBD 에 대한 안. result_store/README.md 참고)

    <result_dir>/<scan_id>/progress.json   진행 기록. 바뀔 때마다 통째로 원자적 교체
    <result_dir>/<scan_id>/result.json     최종 결과 원본. 한 번만 쓴다

- 모든 쓰기는 같은 디렉터리의 임시 파일에 쓰고 fsync 한 뒤 os.replace 로 바꾼다. 쓰는 도중에 프로세스가
  죽어도 이전 파일이 그대로 남는다.
- 인스턴스는 기록을 메모리에 들고 있지 않는다. 바꿀 때마다 파일을 읽어 고친 뒤 쓴다. 그래서 쓰기가
  실패해도 메모리와 파일이 어긋나지 않고, 프로세스를 재시작한 새 인스턴스도 같은 기록을 본다.
- 깨진 파일 · 모르는 schema_version 은 예외로 드러낸다. 다른 작업의 기록을 읽는 데는 영향이 없다.
- 이 모듈은 사실만 기록한다. 재시작을 허용할지는 판단하지 않는다(T26).
"""

from dataclasses import dataclass
from dataclasses import replace
import json
import os
from pathlib import Path
import threading
import time
from typing import Callable, Optional, Tuple

from .records import BiasCorrection
from .records import check_node_params
from .records import check_scan_id
from .records import ConfigSnapshot
from .records import edge_direction
from .records import EVENT_CONTACT
from .records import EVENT_EDGE
from .records import FailureRecord
from .records import Frames
from .records import Interruption
from .records import KIND_PROGRESS
from .records import KIND_RESULT
from .records import Measurement
from .records import MeasurementSlot
from .records import PoseRecord
from .records import ResultRecord
from .records import SCAN_ID_PATTERN
from .records import ScanRecord
from .records import SCHEMA_VERSION
from .records import ShapeResult
from .records import Stamp
from .records import StateRecord
from .records import STATUS_CONFIRMED
from .records import STATUS_FAILED
from .records import TOP
from ..contract_enums import Phase

PROGRESS_FILE = 'progress.json'
RESULT_FILE = 'result.json'


class ResultStoreError(Exception):
    """result_store 의 모든 오류."""


class RecordNotFound(ResultStoreError):
    """그 scan_id 의 기록(또는 결과)이 없다."""


class ScanAlreadyExists(ResultStoreError):
    """begin_scan 을 이미 기록이 있는 scan_id 로 불렀다."""


class ResultAlreadySaved(ResultStoreError):
    """result.json 은 한 번만 쓴다. 다시 계산하지 말고 load_result 로 읽는다."""


class MeasurementAlreadyConfirmed(ResultStoreError):
    """확정 측정값을 덮어쓰려 했다. 기존 측정값은 유지한다(BRD 4.4.8)."""


class RecordStateError(ResultStoreError):
    """기록의 현재 내용과 맞지 않는 호출 (예: 중지 기록 없이 record_resume)."""


class CorruptRecordError(ResultStoreError):
    """파일이 JSON 이 아니거나 스키마 · 값 규칙에 어긋난다."""

    def __init__(self, scan_id, path, why):
        super().__init__(f'{path}: {why}')
        self.scan_id = scan_id
        self.path = Path(path)


class UnsupportedSchemaError(ResultStoreError):
    """이 코드가 모르는 schema_version 이다. 조용히 읽지 않는다."""

    def __init__(self, scan_id, path, found):
        super().__init__(f'{path}: schema_version={found!r} 을 모른다(지원: {SCHEMA_VERSION})')
        self.scan_id = scan_id
        self.path = Path(path)
        self.found = found


@dataclass(frozen=True)
class ResumeCandidate:
    """재개 후보 조회의 결과. 판단은 없고 사실만 있다.

    record: 후보 기록. 없으면 None.
    newer_scan_ids: 후보보다 나중에 시작된 작업들(완료된 것 · 읽지 못한 것 포함). 최신순.
    skipped_errors: 그중 읽지 못한 기록의 오류. 조용히 건너뛰지 않으려고 같이 돌려준다.
    result_file_exists: 후보의 result.json 이 디스크에 있는가. 저장 직후에 프로세스가 죽었다면
        record.result_saved 는 False 인데 이 값은 True 일 수 있다.
    """

    record: Optional[ScanRecord]
    newer_scan_ids: Tuple[str, ...] = ()
    skipped_errors: Tuple[ResultStoreError, ...] = ()
    result_file_exists: bool = False

    @property
    def is_latest(self) -> bool:
        return self.record is not None and not self.newer_scan_ids


def _wall_clock() -> Stamp:
    return Stamp.from_ns(time.time_ns())


def _reject_constant(name):
    raise ValueError(f'JSON 에 {name} 이 있다')


class ResultStore:
    """작업별 진행 기록 · 최종 결과의 저장소.

    result_dir: 저장 경로. ROS 파라미터 ``result_dir`` 로 받아 넘긴다(T19). 모듈 안에 경로를 두지 않는다.
    now_fn: 기록 시각을 주는 함수(-> Stamp). 기본은 벽시계다. 노드는 ROS 시계를 넘긴다.

    쓰기는 fsync 까지 하고 돌아온다(수 ms ~ 수십 ms). 상태 기계의 on_change 는 락을 쥔 채 불리므로
    그 안에서 이 클래스의 쓰기 메서드를 직접 부르지 않는다. README 의 "사용 주의"를 본다.
    한 프로세스(scan_manager) 안의 여러 스레드는 안전하다. 여러 프로세스가 같은 작업을 쓰는 것은 막지 않는다.
    """

    def __init__(self, result_dir, now_fn: Optional[Callable[[], Stamp]] = None):
        if not str(result_dir):
            raise ValueError('result_dir 가 비어 있다')
        self._dir = Path(result_dir)
        self._now = now_fn or _wall_clock
        self._lock = threading.RLock()

    @property
    def result_dir(self) -> Path:
        return self._dir

    # ---- 쓰기 ----

    def begin_scan(
        self,
        scan_id: str,
        *,
        state,
        config: ConfigSnapshot,
        frames: Frames,
        direction_order,
        started_at: Optional[Stamp] = None,
        node_params=None,
    ) -> ScanRecord:
        """새 작업의 기록을 만든다. START 가 접수된 뒤에 그 Outcome.state 와 함께 부른다."""
        check_scan_id(scan_id)
        self._check_state_owner(state, scan_id)
        with self._lock:
            path = self._path(scan_id, PROGRESS_FILE)
            if path.exists() or self._path(scan_id, RESULT_FILE).exists():
                raise ScanAlreadyExists(f'{scan_id} 의 기록이 이미 있다')
            now = self._now()
            record = ScanRecord(
                scan_id=scan_id,
                started_at=started_at or now,
                updated_at=now,
                state=StateRecord.from_snapshot(state),
                frames=frames,
                direction_order=tuple(direction_order),
                config=config,
                node_params=check_node_params(node_params),
                revision=1,
                last_motion_id=StateRecord.from_snapshot(state).motion_id,
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(path, record.to_dict())
            return record

    def record_state(self, snapshot) -> ScanRecord:
        """단계 · 방향 · 진행 n/4 · motion_id 를 갱신한다. T10 의 Snapshot 을 그대로 넣으면 된다."""
        state = StateRecord.from_snapshot(snapshot)

        def apply(record, _now):
            record.state = state
            record.last_motion_id = max(record.last_motion_id, state.motion_id)
        return self._mutate(check_scan_id(snapshot.scan_id), apply)

    def record_top(self, scan_id: str, measurement: Measurement) -> ScanRecord:
        """윗면 1점을 확정한다. 확정 기록이 끝난 뒤에 notify(TOP_FOUND) 를 보낸다."""
        return self._confirm(scan_id, TOP, measurement, EVENT_CONTACT)

    def record_edge(self, scan_id: str, direction, measurement: Measurement) -> ScanRecord:
        """모서리 1점을 확정한다. 확정 기록이 끝난 뒤에 notify(EDGE_FOUND) 를 보낸다."""
        return self._confirm(scan_id, direction, measurement, EVENT_EDGE)

    def record_attempt_failed(
        self,
        scan_id: str,
        target,
        reason_code: int,
        detail: str = '',
        stop_pose: Optional[PoseRecord] = None,
    ) -> ScanRecord:
        """target(TOP 또는 Direction)의 탐색이 실패했다. 값은 남기지 않고 사유 · 정지 위치만 남긴다."""
        def apply(record, now):
            self._check_not_confirmed(record, target)
            self._put_slot(record, target, MeasurementSlot(
                status=STATUS_FAILED, stop_pose=stop_pose,
                reason_code=int(reason_code), detail=detail, recorded_at=now))
        return self._mutate(scan_id, apply)

    def record_stop(self, scan_id: str, interruption: Interruption) -> ScanRecord:
        """작업 중지 1건을 기록한다. 마무리 HOMING 중이었는지는 호출 측이 밝힌다(추론하지 않는다).

        정지 완료를 확인하고 중단 위치를 얻은 뒤, notify(STOP_CONFIRMED) 를 보내기 **전에** 부른다.
        STOPPED 가 된 뒤에야 안전복귀가 접수되므로, 그래야 "중지 → 안전복귀"의 순서가 기록에서도 같다.
        """
        def apply(record, now):
            record.interruptions.append(replace(interruption, stopped_at=now, resumed_at=None))
        return self._mutate(scan_id, apply)

    def record_resume(self, scan_id: str) -> ScanRecord:
        """가장 최근 중지에서 재시작을 접수했다. scan_id 와 기존 측정값은 그대로다."""
        def apply(record, now):
            last = record.last_interruption
            if last is None or last.resumed_at is not None:
                raise RecordStateError(f'{scan_id}: 재시작할 중지 기록이 없다')
            record.interruptions[-1] = replace(last, resumed_at=now)
        return self._mutate(scan_id, apply)

    def record_home_requested(self, scan_id: str, origin_phase=None) -> ScanRecord:
        """홈 안전복귀를 접수했다. 끝까지 갔는지와 무관하게 남는다(계약 5.3절의 NOT_SUPPORTED 판정용)."""
        def apply(record, now):
            record.home_return = replace(
                record.home_return,
                requested=True,
                request_count=record.home_return.request_count + 1,
                requested_at=now,
                interruptions_at_request=len(record.interruptions),
                origin_phase=origin_phase,
                completed=None,
                completed_at=None,
                final_pose=None,
            )
        return self._mutate(scan_id, apply)

    def record_home_finished(
        self, scan_id: str, completed: bool, final_pose: Optional[PoseRecord] = None,
    ) -> ScanRecord:
        """접수한 홈 안전복귀가 끝났다(성공 · 실패). 마무리 복귀(7.4절)에는 쓰지 않는다."""
        def apply(record, now):
            if not record.home_return.requested:
                raise RecordStateError(f'{scan_id}: 홈 안전복귀 접수 기록이 없다')
            record.home_return = replace(
                record.home_return,
                completed=completed, completed_at=now, final_pose=final_pose)
        return self._mutate(scan_id, apply)

    def record_failure(self, scan_id: str, failure) -> ScanRecord:
        """실패 사유를 기록한다. reason_code · detail · phase 속성이 있는 객체(T10 의 Failure)면 된다."""
        def apply(record, now):
            record.failure = FailureRecord.from_failure(failure, recorded_at=now)
        return self._mutate(scan_id, apply)

    def save_result(self, scan_id: str, shape: ShapeResult, bias_corrections=None) -> ResultRecord:
        """최종 결과 원본을 쓴다(GEOMETRY 끝, /scan/result 발행 전). 실패한 형상도 저장한다.

        두 번째 호출은 ResultAlreadySaved 다. 재시작으로 GEOMETRY 에 돌아왔는데 result_saved 가 이미
        참이면 다시 계산하지 말고 load_result 로 읽는다.
        """
        if not isinstance(shape, ShapeResult):
            raise ValueError('shape 는 ShapeResult 여야 한다')
        corrections = dict(bias_corrections or {})
        if any(not isinstance(c, BiasCorrection) for c in corrections.values()):
            raise ValueError('bias_corrections 의 값은 BiasCorrection 이어야 한다')
        with self._lock:
            record = self.load(scan_id)
            path = self._path(scan_id, RESULT_FILE)
            if path.exists():
                if not record.result_saved:
                    # result.json 을 쓴 직후에 죽어 진행 기록에 표시가 빠진 경우. 있는 파일대로 고친다
                    self._mark_result_saved(scan_id, self.load_result(scan_id).shape.success)
                raise ResultAlreadySaved(f'{scan_id} 의 결과는 이미 저장됐다')
            result = ResultRecord(
                scan_id=scan_id, shape=shape, bias_corrections=corrections,
                config=record.config, node_params=record.node_params, saved_at=self._now())
            _atomic_write(path, result.to_dict())
            self._mark_result_saved(scan_id, shape.success)
            return result

    # ---- 읽기 ----

    def load(self, scan_id: str) -> ScanRecord:
        """지정한 작업의 진행 기록. 그 작업의 파일만 읽는다."""
        path = self._path(check_scan_id(scan_id), PROGRESS_FILE)
        return self._parse(scan_id, path, KIND_PROGRESS, ScanRecord)

    def load_result(self, scan_id: str) -> ResultRecord:
        path = self._path(check_scan_id(scan_id), RESULT_FILE)
        return self._parse(scan_id, path, KIND_RESULT, ResultRecord)

    def has_result(self, scan_id: str) -> bool:
        return self._path(check_scan_id(scan_id), RESULT_FILE).exists()

    def scan_ids(self) -> Tuple[str, ...]:
        """기록이 있는 작업들. 최신순(scan_id 의 앞부분이 시각이라 사전순이 곧 시간순이다)."""
        if not self._dir.is_dir():
            return ()
        found = []
        for entry in self._dir.iterdir():
            if not SCAN_ID_PATTERN.fullmatch(entry.name) or not entry.is_dir():
                continue
            # begin_scan 도중에 죽어 비어 있는 디렉터리는 기록이 아니다
            if (entry / PROGRESS_FILE).exists() or (entry / RESULT_FILE).exists():
                found.append(entry.name)
        return tuple(sorted(found, reverse=True))

    def list_scans(self):
        """(읽은 기록들, 읽지 못한 기록의 오류들). 둘 다 최신순이다."""
        records, errors = [], []
        for scan_id in self.scan_ids():
            try:
                records.append(self.load(scan_id))
            except ResultStoreError as error:
                errors.append(error)
        return records, errors

    def find_resume_candidate(self, scan_id: str = '') -> ResumeCandidate:
        """재개 후보를 찾는다 (Resume goal 의 scan_id 를 그대로 넣는다).

        "" 이면 phase 가 DONE 이 아닌 가장 최근 기록, 값이 있으면 그 기록이다(phase 와 무관).
        지정한 기록이 없으면 record=None 이고, 깨졌으면 예외다.
        재시작을 허용할지는 돌려준 사실로 호출 측이 판단한다.
        """
        ids = self.scan_ids()
        if scan_id:
            check_scan_id(scan_id)
            newer = tuple(i for i in ids if i > scan_id)
            try:
                record = self.load(scan_id)
            except RecordNotFound:
                record = None
            return self._candidate(record, newer)

        newer = []
        for current in ids:
            try:
                record = self.load(current)
            except ResultStoreError:
                newer.append(current)
                continue
            if record.state.phase is not Phase.DONE:
                return self._candidate(record, tuple(newer))
            newer.append(current)
        return self._candidate(None, tuple(newer))

    # ---- 내부 ----

    def _candidate(self, record, newer) -> ResumeCandidate:
        errors = []
        for scan_id in newer:
            try:
                self.load(scan_id)
            except ResultStoreError as error:
                errors.append(error)
        return ResumeCandidate(
            record=record,
            newer_scan_ids=newer,
            skipped_errors=tuple(errors),
            result_file_exists=record is not None and self.has_result(record.scan_id),
        )

    def _mark_result_saved(self, scan_id, success):
        def apply(record, _now):
            record.result_saved = True
            record.result_success = success
        self._mutate(scan_id, apply)

    def _path(self, scan_id, name) -> Path:
        return self._dir / scan_id / name

    @staticmethod
    def _check_state_owner(state, scan_id):
        if state.scan_id != scan_id:
            raise ValueError(f'state 의 scan_id({state.scan_id!r}) 가 {scan_id!r} 와 다르다')

    def _mutate(self, scan_id, apply) -> ScanRecord:
        with self._lock:
            record = self.load(scan_id)
            now = self._now()
            apply(record, now)
            record.updated_at = now
            record.revision += 1
            # 고친 내용이 값 규칙에 맞는지 파일에 쓰기 전에 다시 확인한다
            data = record.to_dict()
            ScanRecord.from_dict(data)
            _atomic_write(self._path(scan_id, PROGRESS_FILE), data)
            return record

    def _confirm(self, scan_id, target, measurement, event_type) -> ScanRecord:
        if not isinstance(measurement, Measurement):
            raise ValueError('measurement 는 Measurement 여야 한다')
        if measurement.detection.event_type != event_type:
            raise ValueError(
                f'{target!r} 의 측정값은 {event_type} 판정이어야 한다'
                f'({measurement.detection.event_type})')

        def apply(record, now):
            self._check_not_confirmed(record, target)
            self._put_slot(record, target, MeasurementSlot(
                status=STATUS_CONFIRMED, detection=measurement.detection,
                stop_pose=measurement.stop_pose, recorded_at=now))
        return self._mutate(scan_id, apply)

    @staticmethod
    def _check_not_confirmed(record, target):
        if record.slot(target).valid:
            raise MeasurementAlreadyConfirmed(
                f'{record.scan_id}: {target!r} 의 확정 측정값이 이미 있다')

    @staticmethod
    def _put_slot(record, target, slot):
        if target == TOP:
            record.top = slot
        else:
            record.edges[edge_direction(target)] = slot

    def _parse(self, scan_id, path, kind, cls):
        try:
            text = path.read_text(encoding='utf-8')
        except FileNotFoundError:
            raise RecordNotFound(f'{path} 가 없다') from None
        except (OSError, UnicodeDecodeError) as error:
            raise CorruptRecordError(scan_id, path, f'읽을 수 없다: {error}') from error
        try:
            data = json.loads(text, parse_constant=_reject_constant)
        except ValueError as error:
            raise CorruptRecordError(scan_id, path, f'JSON 이 아니다: {error}') from error
        if not isinstance(data, dict):
            raise CorruptRecordError(scan_id, path, '최상위가 객체가 아니다')

        version = data.get('schema_version')
        if isinstance(version, bool) or not isinstance(version, int):
            raise CorruptRecordError(scan_id, path, f'schema_version 이 없거나 정수가 아니다({version!r})')
        if version != SCHEMA_VERSION:
            raise UnsupportedSchemaError(scan_id, path, version)
        if data.get('kind') != kind:
            raise CorruptRecordError(scan_id, path, f'kind 가 {kind} 가 아니다({data.get("kind")!r})')
        try:
            record = cls.from_dict(data)
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            raise CorruptRecordError(scan_id, path, f'{type(error).__name__}: {error}') from error
        if record.scan_id != scan_id:
            raise CorruptRecordError(
                scan_id, path, f'파일의 scan_id({record.scan_id}) 가 디렉터리와 다르다')
        return record


def _atomic_write(path: Path, data: dict) -> None:
    """임시 파일 → fsync → os.replace → 디렉터리 fsync. 실패하면 이전 파일이 그대로 남는다."""
    # allow_nan=False: NaN · inf 가 남아 있으면 파일을 만들기 전에 ValueError 로 멈춘다
    text = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
    tmp = path.with_name(f'.{path.name}.{os.getpid()}.{threading.get_ident()}.tmp')
    try:
        with open(tmp, 'w', encoding='utf-8') as file:
            file.write(text)
            file.write('\n')
            file.flush()
            os.fsync(file.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    # rename 자체를 디스크에 남긴다 (POSIX)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
