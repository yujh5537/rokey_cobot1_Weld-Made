"""재시작의 판단 (순수 Python, rclpy 없음). 기준: ros-interfaces.md 5.3 · 7.4절, result_store/README.md "재개 후보".

result_store 는 사실만 준다. 그 사실로 두 가지를 만든다.

- restoration_from(): 프로세스가 재시작된 뒤 상태 기계를 되돌릴 값. 되돌린 뒤에는 같은 프로세스에서 중지한
  경우와 **같은 경로**로 판정한다(상태 기계의 _check). 그래서 두 경로의 거절 사유가 갈리지 않는다.
- plan_resume(): 상태 기계가 재시작을 받을 수 있다고 한 작업의 기록 → 이어 갈 계획(Resumption) 또는 거절(Refusal).
  RESUME 을 접수하기 **전에** 부른다. 거절될 요청이 RESUMING 에 들어가지 않는다.

기록이 기준이다. 측정값 · 첫 접촉 z · 중단 좌표 · 설정을 메모리에서 가져오지 않는다.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple, Union

from . import params as scan_params
from .contract_enums import Direction
from .contract_enums import Phase
from .contract_enums import Reason
from .geometry_adapter import EdgeMeasurement
from .geometry_adapter import TopMeasurement
from .params import ScanParams
from .result_store import PoseRecord
from .result_store import ResultStoreError
from .result_store import Stamp
from .result_store.records import CONFIG_FIELDS
from .sequence import ResumePlan
from .state_machine import Failure
from .state_machine import RESUMABLE_PHASES


@dataclass(frozen=True)
class Restoration:
    """ScanStateMachine.restore() 에 넘길 값 + 이어서 발급할 motion_id 의 기준."""

    scan_id: str
    phase: Phase                     # STOPPED · ERROR
    progress: int
    resume_phase: Optional[Phase]
    moved_since_stop: bool
    failure: Optional[Failure]
    last_motion_id: int


@dataclass(frozen=True)
class Refusal:
    reason: Reason
    detail: str


@dataclass(frozen=True)
class Resumption:
    """이어 갈 작업 하나. 전부 기록에서 읽은 값이다."""

    plan: ResumePlan
    params: ScanParams                           # 그 작업이 돌던 설정(기록의 config · node_params)
    config: Dict[str, object]                    # ScanConfig 12개 값. 모르는 값은 None
    top: Optional[TopMeasurement]                # 측정값 캐시(형상 계산의 입력)
    edges: Dict[Direction, EdgeMeasurement]
    stop_pose: Optional[PoseRecord]              # 중단 좌표의 원본. 모션 없이 다시 중지되면 그대로 이어 적는다
    started_at: Stamp
    last_motion_id: int


def latest_record(store):
    """가장 최근 작업의 기록 → (기록, 기록이 없는 이유). **그 하나만** 읽는다.

    명령 접수 락 안에서 불린다(/scan/stop 이 같은 락을 기다린다). 기록이 쌓여도 읽는 양이 늘지 않아야 한다.
    가장 최근 기록을 읽지 못하면 ResultStoreError 다. 그보다 오래된 작업으로 넘어가지 않는다(조용히 건너뛰지 않는다).
    "기록이 없다"(확실하다)와 "읽지 못했다"(모른다)를 호출 측이 구분해야 해서 예외로 나눈다.
    """
    scan_ids = store.scan_ids()
    if not scan_ids:
        return None, '이을 수 있는 작업의 기록이 없다'
    try:
        return store.load(scan_ids[0]), ''
    except ResultStoreError as error:
        raise ResultStoreError(
            f'가장 최근 작업 {scan_ids[0]} 의 기록을 읽을 수 없다: {error}') from error


def resume_point_consumed(record) -> bool:
    """재개 지점에서 시작한 재시작이 RESUME_READY 를 지났는가(상태 기계는 그때 재개 지점을 지운다).

    재시작을 접수하면 그때의 마지막 중지에 resumed_at 이 찍힌다. 준비(RESUMING) 중에 다시 중지됐다면 바로 뒤에
    RESUMING 중지가 이어진다. 이어지지 않았다면 그 재시작은 준비를 지나 측정 단계로 돌아갔다.
    그 뒤에 남을 수 있는 중지는 안전복귀 중의 중지뿐이다(예: 재시작 → DONE → 안전복귀 중 중지).
    """
    items = record.interruptions
    start = next((i for i, item in enumerate(items) if item is record.resume_point), None)
    if start is None:
        return False
    for index in range(start, len(items)):
        if items[index].resumed_at is None:
            continue
        if index + 1 == len(items) or items[index + 1].phase is not Phase.RESUMING:
            return True
    return False


def restoration_from(record) -> Tuple[Optional[Restoration], str]:
    """가장 최근 작업의 기록 → (되돌릴 값, 되돌리지 않는 이유).

    되돌리는 것은 **가장 최근 작업이 휴지 상태(STOPPED · ERROR)로 끝나 있을 때**뿐이다.
    기록이 동작 중인 phase 로 끝나 있으면 작업 도중에 프로세스가 죽은 것이다. 중지 기록이 없어
    로봇이 어디서 멈췄는지 모르므로 되돌리지 않는다(재시작은 NO_RESUMABLE_SCAN).
    """
    phase = record.state.phase
    if phase not in (Phase.STOPPED, Phase.ERROR):
        why = '끝난 작업이다' if phase is Phase.DONE else (
            '작업 도중에 프로세스가 끝났다. 로봇이 어디서 멈췄는지 모른다')
        return None, f'가장 최근 작업 {record.scan_id} 의 기록이 phase={phase.name} 이다({why})'

    # 상태 기계의 규칙 그대로: FAILED · 마무리 HOMING 중의 중지 · RESUME_READY 는 재개 지점을 지운다
    point = record.resume_point
    resumable = (
        phase is Phase.STOPPED and record.failure is None and point is not None
        and not point.during_final_homing and point.phase in RESUMABLE_PHASES
        and not resume_point_consumed(record))
    failure = record.failure
    return Restoration(
        scan_id=record.scan_id, phase=phase, progress=record.state.progress,
        resume_phase=point.phase if resumable else None,
        moved_since_stop=record.home_return_since_resume_point,
        failure=None if failure is None else Failure(
            failure.reason_code, failure.detail, failure.phase),
        last_motion_id=record.last_motion_id), ''


def config_values(config) -> Dict[str, object]:
    return {name: getattr(config, name) for name, _flag in CONFIG_FIELDS}


def _refuse(detail, reason=Reason.NO_RESUMABLE_SCAN) -> Refusal:
    return Refusal(reason, detail)


def plan_resume(record, *, result_file_exists: bool, direction_order) -> Union[Resumption, Refusal]:
    """기록 하나 → 이어 갈 계획.

    direction_order: 이 노드의 상태 기계가 들고 있는 탐색 순서. 기록의 순서와 같아야 한다
      (상태 기계가 progress 로 방향을 되찾는다).
    """
    scan_id = record.scan_id
    if record.state.phase is not Phase.STOPPED:
        return _refuse(f'{scan_id} 의 기록이 STOPPED 가 아니다(phase={record.state.phase.name})')
    last, point = record.last_interruption, record.resume_point
    if last is None or last.resumed_at is not None or point is None:
        return _refuse(f'{scan_id}: 재시작하지 않은 중지 기록이 없다')
    if resume_point_consumed(record):
        return _refuse(f'{scan_id}: 그 중지에서 시작한 재시작이 이미 측정 단계로 돌아갔다')
    # 아래 셋은 상태 기계가 먼저 거른다. 기록이 메모리와 어긋난 경우의 대비다
    if record.failure is not None:
        return _refuse(f'{scan_id}: 오류로 끝난 작업의 재시작 절차는 TBD', Reason.NOT_SUPPORTED)
    if record.home_return_since_resume_point:
        return _refuse(f'{scan_id}: 홈 안전복귀 뒤의 재접근 절차는 TBD', Reason.NOT_SUPPORTED)
    if point.during_final_homing:
        return _refuse(f'{scan_id}: 마무리 복귀 중에 중지된 작업이다. 측정은 끝났다(7.4절)')

    order = tuple(record.direction_order)
    if order != tuple(Direction(d) for d in direction_order):
        return _refuse(
            f'기록의 탐색 순서 {[d.name for d in order]} 가 이 노드의 direction_order 와 다르다',
            Reason.INVALID_VALUE)
    config = config_values(record.config)
    checked = scan_params.check({
        **record.node_params,
        **{name: config[name] for name in scan_params.MOTION_CONFIG_NAMES},
        'direction_order': [d.name for d in order]})
    if not checked.ok:
        return _refuse(f'기록의 설정으로 이을 수 없다. {checked.describe()}', Reason.INVALID_VALUE)
    params = checked.params

    confirmed = record.confirmed_edges
    if confirmed != order[:len(confirmed)]:
        return _refuse(
            f'{scan_id}: 확정된 방향 {[d.name for d in confirmed]} 가 탐색 순서의 앞부분이 아니다')
    poses = [record.edges[d].detection.pose for d in confirmed]
    if record.top.valid:
        poses.append(record.top.detection.pose)
    if last.pose is not None:
        poses.append(last.pose)
    for pose in poses:
        if pose.frame_id != params.motion_frame_id:
            return _refuse(
                f'{scan_id}: 기록된 좌표의 frame_id={pose.frame_id!r} 가 {params.motion_frame_id!r} 가 아니다')

    top = None
    if record.top.valid:
        top = TopMeasurement(
            tuple(record.top.detection.pose.position_m), params.descend_speed_mps)
    edges = {}
    for direction in confirmed:
        detection = record.edges[direction].detection
        edges[direction] = EdgeMeasurement(
            tuple(detection.pose.position_m), detection.z_drop_m, params.slide_speed_mps)
    try:
        plan = ResumePlan(
            phase=point.phase, progress=record.state.progress, confirmed=confirmed,
            first_contact_z=None if top is None else top.position_m[2],
            position=None if last.pose is None else tuple(last.pose.position_m),
            result_saved=record.result_saved or result_file_exists)
    except ValueError as error:
        return _refuse(f'{scan_id}: {error}')
    return Resumption(
        plan=plan, params=params, config=config, top=top, edges=edges, stop_pose=last.pose,
        started_at=record.started_at, last_motion_id=record.last_motion_id)
