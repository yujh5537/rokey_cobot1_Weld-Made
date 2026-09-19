"""result_store 의 기록 자료형과 파일(dict) 변환 (순수 Python, rclpy 없음).

기준: docs/BRD.md 4.4.7, docs/contracts/ros-interfaces.md v0.1.1 의 1장(무효 값) · 3.3 · 3.5 · 3.9 · 6.2절.
파일 형식은 계약 9장의 TBD 이며 이 패키지의 result_store/README.md 에 적은 안을 따른다.

값 규칙 (CLAUDE.md 규칙 4)
- 미측정 · 실패 값은 Python 에서 ``None``, 파일에서 ``null`` 이고 짝이 되는 ``*_valid=false`` 를 둔다.
- ``valid=false`` 인데 숫자가 오면 ``ValueError`` 다. 0 을 끼워 넣을 수 없게 한다. NaN 만 ``None`` 으로 바꾼다
  (ROS msg 는 미측정을 NaN 으로 싣기 때문이다).
- ``valid=true`` 인데 ``None`` · NaN · inf 이면 ``ValueError`` 다.
- 같은 검사를 파일을 읽을 때도 한다. 그래서 ``null`` 이 0.0 이나 False 로 바뀌어 들어올 수 없다.

단위는 ROS 내부 단위(m · rad · N) 그대로다. mm 변환은 mqtt_bridge 에서만 한다.
계약 msg 를 옮긴 필드는 계약의 이름을 그대로 쓰고, 여기서 새로 만든 필드는 이름에 단위를 붙인다.
"""

from dataclasses import dataclass
from dataclasses import field
import math
import re
from typing import Dict, List, Mapping, Optional, Tuple

from ..contract_enums import Direction
from ..contract_enums import Phase

SCHEMA_VERSION = 1
KIND_PROGRESS = 'contact_scan.progress'
KIND_RESULT = 'contact_scan.result'
UNITS = {'length': 'm', 'angle': 'rad', 'force': 'N', 'torque': 'N*m', 'time': 's'}

# 계약 6.2절: YYYYMMDD-HHMMSS-xxxx. 디렉터리 이름으로 쓰므로 경로 문자를 허용하지 않는다.
SCAN_ID_PATTERN = re.compile(r'\d{8}-\d{6}-[0-9A-Za-z]{4}')

TOP = 'top'  # record_attempt_failed 의 target. 모서리는 Direction 으로 가리킨다
EDGE_DIRECTIONS = (Direction.POS_X, Direction.NEG_X, Direction.POS_Y, Direction.NEG_Y)

STATUS_NOT_ATTEMPTED = 'NOT_ATTEMPTED'  # 아직 탐색하지 않았다
STATUS_CONFIRMED = 'CONFIRMED'          # 확정 측정값이 있다
STATUS_FAILED = 'FAILED'                # 탐색했지만 실패했다
_STATUSES = (STATUS_NOT_ATTEMPTED, STATUS_CONFIRMED, STATUS_FAILED)

EVENT_CONTACT = 'CONTACT'  # ContactEvent.TYPE_CONTACT — 윗면
EVENT_EDGE = 'EDGE'        # ContactEvent.TYPE_EDGE — 모서리

# ScanConfig.msg (3.9절) 의 (값 필드, *_set 필드). 이름은 계약 그대로다.
CONFIG_FIELDS = (
    ('contact_threshold_n', 'contact_threshold_set'),
    ('edge_drop_m', 'edge_drop_set'),
    ('debounce_n', 'debounce_set'),
    ('over_force_n', 'over_force_set'),
    ('descend_speed_mps', 'descend_speed_set'),
    ('slide_speed_mps', 'slide_speed_set'),
    ('max_descend_m', 'max_descend_set'),
    ('max_slide_m', 'max_slide_set'),
    ('motion_timeout_s', 'motion_timeout_set'),
    ('lift_height_m', 'lift_height_set'),
    ('target_force_n', 'target_force_set'),
    ('drop_limit_m', 'drop_limit_set'),
)


# ---- 값 검사 ----

def check_scan_id(scan_id) -> str:
    if not isinstance(scan_id, str) or not SCAN_ID_PATTERN.fullmatch(scan_id):
        raise ValueError(f'scan_id 형식이 아니다(YYYYMMDD-HHMMSS-xxxx): {scan_id!r}')
    return scan_id


def _finite(value, name) -> float:
    # bool 은 int 의 하위형이라 따로 막는다. False 가 0.0 으로 저장되면 안 된다.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{name}: 숫자가 아니다({value!r})')
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f'{name}: 유한한 값이 아니다({value!r})')
    return value


def _optional(value, valid, name) -> Optional[float]:
    """(value, valid) 짝을 검사해 저장할 값을 돌려준다. 무효면 None."""
    _bool(valid, f'{name} 의 valid')
    if valid:
        return _finite(value, name)
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    raise ValueError(
        f'{name}: valid=false 인데 값이 있다({value!r}). 미측정 · 실패 값은 None 으로 둔다(0 금지)')


def _uint(value, name) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name}: 0 이상의 정수가 아니다({value!r})')
    return value


def _bool(value, name) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f'{name}: bool 이 아니다({value!r})')
    return value


def _text(value, name, allow_empty=True) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise ValueError(f'{name}: 문자열이 아니거나 비어 있다({value!r})')
    return value


def _vector(values, size, name) -> Tuple[float, ...]:
    if isinstance(values, (str, bytes)) or not hasattr(values, '__len__') or len(values) != size:
        raise ValueError(f'{name}: 길이 {size} 의 수열이 아니다({values!r})')
    return tuple(_finite(v, f'{name}[{i}]') for i, v in enumerate(values))


def _set(obj, **values):
    """frozen dataclass 의 __post_init__ 에서 정규화한 값을 넣는다."""
    for key, value in values.items():
        object.__setattr__(obj, key, value)


def edge_direction(value) -> Direction:
    direction = value if isinstance(value, Direction) else (
        Direction[value] if isinstance(value, str) else Direction(value))
    if direction not in EDGE_DIRECTIONS:
        raise ValueError(f'모서리 방향이 아니다({value!r})')
    return direction


def _phase(value) -> Phase:
    if isinstance(value, Phase):
        return value
    return Phase[value] if isinstance(value, str) else Phase(value)


def _direction(value) -> Direction:
    if isinstance(value, Direction):
        return value
    return Direction[value] if isinstance(value, str) else Direction(value)


def _dump(obj):
    return None if obj is None else obj.to_dict()


def _load(cls, data):
    return None if data is None else cls.from_dict(data)


# ---- 기본 자료형 ----

@dataclass(frozen=True)
class Stamp:
    """builtin_interfaces/Time. float 로 바꾸지 않고 정수 쌍으로 둔다."""

    sec: int
    nanosec: int = 0

    def __post_init__(self):
        _uint(self.sec, 'sec')
        if _uint(self.nanosec, 'nanosec') >= 1_000_000_000:
            raise ValueError(f'nanosec 이 1e9 이상이다({self.nanosec})')

    @classmethod
    def from_ns(cls, nanoseconds: int) -> 'Stamp':
        return cls(*divmod(_uint(nanoseconds, 'nanoseconds'), 1_000_000_000))

    @property
    def ns(self) -> int:
        return self.sec * 1_000_000_000 + self.nanosec

    def to_dict(self):
        return {'sec': self.sec, 'nanosec': self.nanosec}

    @classmethod
    def from_dict(cls, data):
        return cls(data['sec'], data['nanosec'])


@dataclass(frozen=True)
class Measured:
    """미측정일 수 있는 float 하나와 그 유효 플래그."""

    value: Optional[float]
    valid: bool

    def __post_init__(self):
        _set(self, value=_optional(self.value, self.valid, 'value'))

    @classmethod
    def of(cls, value) -> 'Measured':
        return cls(value, True)

    @classmethod
    def missing(cls) -> 'Measured':
        return cls(None, False)


@dataclass(frozen=True)
class PoseRecord:
    """좌표 하나. 어느 프레임 · 어느 시각의 값인지를 항상 같이 둔다."""

    position_m: Tuple[float, float, float]
    orientation_xyzw: Tuple[float, float, float, float]
    frame_id: str
    stamp: Stamp

    def __post_init__(self):
        _set(
            self,
            position_m=_vector(self.position_m, 3, 'position_m'),
            orientation_xyzw=_vector(self.orientation_xyzw, 4, 'orientation_xyzw'),
        )
        _text(self.frame_id, 'frame_id', allow_empty=False)
        if not isinstance(self.stamp, Stamp):
            raise ValueError('stamp 는 Stamp 여야 한다')

    def to_dict(self):
        return {
            'position_m': list(self.position_m),
            'orientation_xyzw': list(self.orientation_xyzw),
            'frame_id': self.frame_id,
            'stamp': self.stamp.to_dict(),
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            data['position_m'], data['orientation_xyzw'], data['frame_id'],
            Stamp.from_dict(data['stamp']))


@dataclass(frozen=True)
class WrenchRecord:
    """판정 샘플의 외력. frame 은 Detection.pose.frame_id 와 같다(units-frames.md)."""

    force_n: Tuple[float, float, float]
    torque_nm: Tuple[float, float, float]

    def __post_init__(self):
        _set(
            self,
            force_n=_vector(self.force_n, 3, 'force_n'),
            torque_nm=_vector(self.torque_nm, 3, 'torque_nm'),
        )

    def to_dict(self):
        return {'force_n': list(self.force_n), 'torque_nm': list(self.torque_nm)}

    @classmethod
    def from_dict(cls, data):
        return cls(data['force_n'], data['torque_nm'])


# ---- 측정값 ----

@dataclass(frozen=True)
class Detection:
    """측정값의 출처인 판정 좌표 (ContactEvent, 3.3절). 정지 완료 좌표와 섞지 않는다.

    pose.stamp 가 ContactEvent.pose_stamp 다. 힘의 취득 시각(force_stamp)은 따로 둔다.
    ID 는 계약대로 0 = 없음이다.
    """

    event_type: str
    event_id: int
    sample_id: int
    motion_id: int
    pose: PoseRecord
    force_stamp: Stamp
    detect_stamp: Stamp
    force_delta_n: float
    z_drop_m: Optional[float] = None
    z_drop_valid: bool = False
    source: str = ''
    debounce_count: Optional[int] = None
    wrench: Optional[WrenchRecord] = None

    def __post_init__(self):
        if self.event_type not in (EVENT_CONTACT, EVENT_EDGE):
            raise ValueError(f'event_type 은 CONTACT · EDGE 중 하나여야 한다({self.event_type!r})')
        for name in ('event_id', 'sample_id', 'motion_id'):
            _uint(getattr(self, name), name)
        if self.debounce_count is not None:
            _uint(self.debounce_count, 'debounce_count')
        _text(self.source, 'source')
        _set(
            self,
            force_delta_n=_finite(self.force_delta_n, 'force_delta_n'),
            z_drop_m=_optional(self.z_drop_m, self.z_drop_valid, 'z_drop_m'),
        )

    def to_dict(self):
        return {
            'event_type': self.event_type,
            'event_id': self.event_id,
            'sample_id': self.sample_id,
            'motion_id': self.motion_id,
            'source': self.source,
            'pose': self.pose.to_dict(),
            'force_stamp': self.force_stamp.to_dict(),
            'detect_stamp': self.detect_stamp.to_dict(),
            'force_delta_n': self.force_delta_n,
            'z_drop_m': self.z_drop_m,
            'z_drop_valid': self.z_drop_valid,
            'debounce_count': self.debounce_count,
            'wrench': _dump(self.wrench),
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            event_type=data['event_type'],
            event_id=data['event_id'],
            sample_id=data['sample_id'],
            motion_id=data['motion_id'],
            pose=PoseRecord.from_dict(data['pose']),
            force_stamp=Stamp.from_dict(data['force_stamp']),
            detect_stamp=Stamp.from_dict(data['detect_stamp']),
            force_delta_n=data['force_delta_n'],
            z_drop_m=data['z_drop_m'],
            z_drop_valid=data['z_drop_valid'],
            source=data['source'],
            debounce_count=data['debounce_count'],
            wrench=_load(WrenchRecord, data['wrench']),
        )


@dataclass(frozen=True)
class Measurement:
    """확정 측정값 1점. detection = 판정 좌표, stop_pose = ExecuteMotion.Result.pose(정지 좌표)."""

    detection: Detection
    stop_pose: Optional[PoseRecord] = None


@dataclass(frozen=True)
class MeasurementSlot:
    """윗면 또는 모서리 한 방향의 기록. status 로 미탐색과 실패를 구분한다."""

    status: str = STATUS_NOT_ATTEMPTED
    detection: Optional[Detection] = None
    stop_pose: Optional[PoseRecord] = None
    reason_code: Optional[int] = None
    detail: str = ''
    recorded_at: Optional[Stamp] = None

    def __post_init__(self):
        if self.status not in _STATUSES:
            raise ValueError(f'status 가 아니다({self.status!r})')
        if (self.status == STATUS_CONFIRMED) != (self.detection is not None):
            raise ValueError('detection 은 CONFIRMED 일 때만, 그리고 반드시 있어야 한다')
        if (self.status == STATUS_FAILED) != (self.reason_code is not None):
            raise ValueError('reason_code 는 FAILED 일 때만, 그리고 반드시 있어야 한다')
        if self.reason_code is not None and _uint(self.reason_code, 'reason_code') == 0:
            raise ValueError('실패의 reason_code 는 0 일 수 없다')
        if self.status == STATUS_NOT_ATTEMPTED and self.stop_pose is not None:
            raise ValueError('탐색하지 않은 항목에는 stop_pose 가 없다')
        _text(self.detail, 'detail')

    @property
    def valid(self) -> bool:
        return self.status == STATUS_CONFIRMED

    def to_dict(self):
        return {
            'status': self.status,
            'valid': self.valid,
            'detection': _dump(self.detection),
            'stop_pose': _dump(self.stop_pose),
            'stop_pose_valid': self.stop_pose is not None,
            'reason_code': self.reason_code,
            'detail': self.detail,
            'recorded_at': _dump(self.recorded_at),
        }

    @classmethod
    def from_dict(cls, data):
        slot = cls(
            status=data['status'],
            detection=_load(Detection, data['detection']),
            stop_pose=_load(PoseRecord, data['stop_pose']),
            reason_code=data['reason_code'],
            detail=data['detail'],
            recorded_at=_load(Stamp, data['recorded_at']),
        )
        if _bool(data['valid'], 'valid') != slot.valid:
            raise ValueError('valid 가 status 와 어긋난다')
        if _bool(data['stop_pose_valid'], 'stop_pose_valid') != (slot.stop_pose is not None):
            raise ValueError('stop_pose_valid 가 stop_pose 와 어긋난다')
        return slot


# ---- 설정 · 상태 ----

@dataclass(frozen=True)
class ConfigSnapshot:
    """적용 설정 스냅샷 (ScanConfig.msg 12개 값). None = 값을 모른다(*_set=false)."""

    contact_threshold_n: Optional[float] = None
    edge_drop_m: Optional[float] = None
    debounce_n: Optional[int] = None
    over_force_n: Optional[float] = None
    descend_speed_mps: Optional[float] = None
    slide_speed_mps: Optional[float] = None
    max_descend_m: Optional[float] = None
    max_slide_m: Optional[float] = None
    motion_timeout_s: Optional[float] = None
    lift_height_m: Optional[float] = None
    target_force_n: Optional[float] = None
    drop_limit_m: Optional[float] = None

    def __post_init__(self):
        for name, _flag in CONFIG_FIELDS:
            value = getattr(self, name)
            if value is None:
                continue
            if name == 'debounce_n':
                _uint(value, name)
            else:
                _set(self, **{name: _finite(value, name)})

    def to_dict(self):
        data = {}
        for name, flag in CONFIG_FIELDS:
            data[name] = getattr(self, name)
            data[flag] = getattr(self, name) is not None
        return data

    @classmethod
    def from_dict(cls, data):
        values = {}
        for name, flag in CONFIG_FIELDS:
            values[name] = data[name]
            if _bool(data[flag], flag) != (data[name] is not None):
                raise ValueError(f'{flag} 가 {name} 과 어긋난다')
        return cls(**values)


def check_node_params(params) -> dict:
    """scan_manager 자체 파라미터의 자유 형식 스냅샷. 값은 None · bool · 유한한 수 · 문자열 · 수의 배열."""
    checked = {}
    for name, value in dict(params or {}).items():
        _text(name, 'node_params 의 이름', allow_empty=False)
        if value is None or isinstance(value, (bool, str)):
            checked[name] = value
        elif isinstance(value, int):
            checked[name] = value
        elif isinstance(value, float):
            checked[name] = _finite(value, name)
        elif isinstance(value, (list, tuple)):
            checked[name] = [
                v if isinstance(v, int) and not isinstance(v, bool) else _finite(v, f'{name}[{i}]')
                for i, v in enumerate(value)
            ]
        else:
            raise ValueError(f'node_params[{name!r}]: 저장할 수 없는 자료형이다({value!r})')
    return checked


@dataclass(frozen=True)
class Frames:
    """좌표 기준. detection = 판정 · 정지 좌표의 프레임, result = ScanResult 의 프레임."""

    detection: str
    result: str

    def __post_init__(self):
        _text(self.detection, 'frames.detection', allow_empty=False)
        _text(self.result, 'frames.result', allow_empty=False)

    def to_dict(self):
        return {'detection': self.detection, 'result': self.result}

    @classmethod
    def from_dict(cls, data):
        return cls(data['detection'], data['result'])


@dataclass(frozen=True)
class StateRecord:
    """단계 · 방향 · 진행 n/4 (ScanState.msg, 3.4절). T10 의 Snapshot 과 필드 이름이 같다."""

    phase: Phase
    direction: Direction
    progress: int
    progress_total: int
    motion_id: int = 0

    def __post_init__(self):
        _set(self, phase=_phase(self.phase), direction=_direction(self.direction))
        _uint(self.progress, 'progress')
        _uint(self.progress_total, 'progress_total')
        _uint(self.motion_id, 'motion_id')
        if self.progress > self.progress_total:
            raise ValueError(f'progress({self.progress}) 가 progress_total 보다 크다')

    @classmethod
    def from_snapshot(cls, snapshot) -> 'StateRecord':
        """phase · direction · progress · progress_total · motion_id 속성이 있는 객체면 된다."""
        return cls(
            snapshot.phase, snapshot.direction, snapshot.progress,
            snapshot.progress_total, snapshot.motion_id)

    def to_dict(self):
        return {
            'phase': self.phase.name,
            'direction': self.direction.name,
            'progress': self.progress,
            'progress_total': self.progress_total,
            'motion_id': self.motion_id,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            _text(data['phase'], 'phase'), _text(data['direction'], 'direction'),
            data['progress'], data['progress_total'], data['motion_id'])


# ---- 중단 · 안전복귀 · 실패 ----

@dataclass(frozen=True)
class Interruption:
    """작업 중지 1건. phase · direction · progress 는 중지를 접수한 시점(STOPPING 으로 가기 전)의 값이다.

    pose 는 중단 위치(ExecuteMotion.Result.pose)다. 진행 중인 모션이 없어 얻지 못했으면 None.
    during_final_homing: 스캔 마무리 HOMING 중의 중지(계약 7.4절). 안전복귀 HOMING 과 구분한다.
    stopped_at · resumed_at 은 store 가 채운다.
    """

    phase: Phase
    direction: Direction
    progress: int
    pose: Optional[PoseRecord] = None
    during_final_homing: bool = False
    stopped_at: Optional[Stamp] = None
    resumed_at: Optional[Stamp] = None

    def __post_init__(self):
        _set(self, phase=_phase(self.phase), direction=_direction(self.direction))
        _uint(self.progress, 'progress')
        _bool(self.during_final_homing, 'during_final_homing')
        if self.during_final_homing and self.phase is not Phase.HOMING:
            raise ValueError('during_final_homing 은 phase=HOMING 일 때만 참일 수 있다')

    def to_dict(self):
        return {
            'phase': self.phase.name,
            'direction': self.direction.name,
            'progress': self.progress,
            'pose': _dump(self.pose),
            'pose_valid': self.pose is not None,
            'during_final_homing': self.during_final_homing,
            'stopped_at': _dump(self.stopped_at),
            'resumed_at': _dump(self.resumed_at),
        }

    @classmethod
    def from_dict(cls, data):
        item = cls(
            phase=_text(data['phase'], 'phase'),
            direction=_text(data['direction'], 'direction'),
            progress=data['progress'],
            pose=_load(PoseRecord, data['pose']),
            during_final_homing=data['during_final_homing'],
            stopped_at=_load(Stamp, data['stopped_at']),
            resumed_at=_load(Stamp, data['resumed_at']),
        )
        if _bool(data['pose_valid'], 'pose_valid') != (item.pose is not None):
            raise ValueError('pose_valid 가 pose 와 어긋난다')
        return item


@dataclass(frozen=True)
class HomeReturn:
    """홈 안전복귀의 사실. requested 는 한 번 참이 되면 그 작업에서 다시 거짓이 되지 않는다.

    completed: None = 끝을 기록하지 않았다(진행 중 · 중지됨 · 프로세스 종료), True/False = 성공/실패.
    """

    requested: bool = False
    request_count: int = 0
    requested_at: Optional[Stamp] = None   # 가장 최근 접수 시각
    # 가장 최근 접수 때까지 기록돼 있던 중지의 수. "어느 중지 뒤의 복귀인가"를 시계에 기대지 않고 남긴다
    interruptions_at_request: int = 0
    origin_phase: Optional[Phase] = None   # 가장 최근 접수 때의 출발 phase
    completed: Optional[bool] = None       # 가장 최근 접수의 결과
    completed_at: Optional[Stamp] = None
    final_pose: Optional[PoseRecord] = None

    def __post_init__(self):
        _bool(self.requested, 'requested')
        _uint(self.request_count, 'request_count')
        _uint(self.interruptions_at_request, 'interruptions_at_request')
        if not self.requested and self.interruptions_at_request:
            raise ValueError('접수 기록 없이 interruptions_at_request 를 둘 수 없다')
        if self.requested != (self.request_count > 0) or self.requested != (
                self.requested_at is not None):
            raise ValueError('requested · request_count · requested_at 이 서로 어긋난다')
        if self.origin_phase is not None:
            _set(self, origin_phase=_phase(self.origin_phase))
        if self.completed is not None:
            _bool(self.completed, 'completed')
            if not self.requested:
                raise ValueError('접수 기록 없이 completed 를 둘 수 없다')

    def to_dict(self):
        return {
            'requested': self.requested,
            'request_count': self.request_count,
            'requested_at': _dump(self.requested_at),
            'interruptions_at_request': self.interruptions_at_request,
            'origin_phase': None if self.origin_phase is None else self.origin_phase.name,
            'completed': self.completed,
            'completed_at': _dump(self.completed_at),
            'final_pose': _dump(self.final_pose),
            'final_pose_valid': self.final_pose is not None,
        }

    @classmethod
    def from_dict(cls, data):
        item = cls(
            requested=data['requested'],
            request_count=data['request_count'],
            requested_at=_load(Stamp, data['requested_at']),
            interruptions_at_request=data['interruptions_at_request'],
            origin_phase=data['origin_phase'],
            completed=data['completed'],
            completed_at=_load(Stamp, data['completed_at']),
            final_pose=_load(PoseRecord, data['final_pose']),
        )
        if _bool(data['final_pose_valid'], 'final_pose_valid') != (item.final_pose is not None):
            raise ValueError('final_pose_valid 가 final_pose 와 어긋난다')
        return item


@dataclass(frozen=True)
class FailureRecord:
    """실패 사유. T10 의 Failure 와 필드 이름이 같다(reason_code · detail · phase)."""

    reason_code: int
    detail: str
    phase: Phase  # 실패가 난 phase
    recorded_at: Optional[Stamp] = None

    def __post_init__(self):
        if _uint(self.reason_code, 'reason_code') == 0:
            raise ValueError('실패의 reason_code 는 0 일 수 없다')
        _text(self.detail, 'detail')
        _set(self, phase=_phase(self.phase))

    @classmethod
    def from_failure(cls, failure, recorded_at=None) -> 'FailureRecord':
        return cls(int(failure.reason_code), failure.detail, failure.phase, recorded_at)

    def to_dict(self):
        return {
            'reason_code': self.reason_code,
            'detail': self.detail,
            'phase': self.phase.name,
            'recorded_at': _dump(self.recorded_at),
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            data['reason_code'], data['detail'], _text(data['phase'], 'phase'),
            _load(Stamp, data['recorded_at']))


# ---- 진행 기록 (progress.json) ----

@dataclass
class ScanRecord:
    """작업 1건의 진행 기록. 판단은 담지 않고 사실만 담는다(재시작 허용 판단은 T26)."""

    scan_id: str
    started_at: Stamp
    updated_at: Stamp
    state: StateRecord
    frames: Frames
    direction_order: Tuple[Direction, ...]
    config: ConfigSnapshot
    node_params: dict = field(default_factory=dict)
    top: MeasurementSlot = field(default_factory=MeasurementSlot)
    edges: Dict[Direction, MeasurementSlot] = field(
        default_factory=lambda: {d: MeasurementSlot() for d in EDGE_DIRECTIONS})
    interruptions: List[Interruption] = field(default_factory=list)
    home_return: HomeReturn = field(default_factory=HomeReturn)
    failure: Optional[FailureRecord] = None
    result_saved: bool = False
    result_success: Optional[bool] = None
    revision: int = 0  # 파일을 쓸 때마다 +1
    # 이 작업에서 기록된 가장 큰 motion_id. state.motion_id 는 휴지 phase 에서 0 으로 돌아가므로 따로 둔다.
    # 재시작 뒤에 motion_id 를 이어서 발급하는 데 쓴다(계약 6.2절: scan 안에서 증가).
    last_motion_id: int = 0

    def __post_init__(self):
        check_scan_id(self.scan_id)
        self.direction_order = tuple(edge_direction(d) for d in self.direction_order)
        if sorted(self.direction_order) != sorted(EDGE_DIRECTIONS):
            raise ValueError('direction_order 는 ±X · ±Y 네 방향을 한 번씩 담아야 한다')
        self.node_params = check_node_params(self.node_params)
        if sorted(self.edges) != sorted(EDGE_DIRECTIONS):
            raise ValueError('edges 는 네 방향을 모두 담아야 한다')
        if any(item.stopped_at is None for item in self.interruptions):
            raise ValueError('기록된 중지에는 stopped_at 이 있어야 한다')
        if self.home_return.interruptions_at_request > len(self.interruptions):
            raise ValueError('home_return.interruptions_at_request 가 중지 기록 수보다 크다')
        _bool(self.result_saved, 'result_saved')
        if self.result_success is not None:
            _bool(self.result_success, 'result_success')
        if self.result_saved != (self.result_success is not None):
            raise ValueError('result_success 는 result_saved 일 때만, 그리고 반드시 있어야 한다')
        _uint(self.revision, 'revision')
        if _uint(self.last_motion_id, 'last_motion_id') < self.state.motion_id:
            raise ValueError('last_motion_id 가 state.motion_id 보다 작다')

    # -- 재개 판단에 쓰는 사실 (판단 자체는 하지 않는다) --

    @property
    def last_interruption(self) -> Optional[Interruption]:
        return self.interruptions[-1] if self.interruptions else None

    @property
    def resume_point(self) -> Optional[Interruption]:
        """재개 지점이 되는 중지: 측정 단계 또는 마무리 HOMING 에서의 가장 최근 중지.

        RESUMING · 안전복귀 HOMING 중의 중지는 재개 지점을 바꾸지 않는다(T10 상태 기계와 같은 규칙).
        그래서 last_interruption 과 다를 수 있다. 없으면 None.
        """
        index = self._resume_point_index()
        return None if index is None else self.interruptions[index]

    def _resume_point_index(self) -> Optional[int]:
        for index in range(len(self.interruptions) - 1, -1, -1):
            item = self.interruptions[index]
            safety_homing = item.phase is Phase.HOMING and not item.during_final_homing
            if item.phase is not Phase.RESUMING and not safety_homing:
                return index
        return None

    @property
    def stopped_during_final_homing(self) -> bool:
        """재개 지점이 스캔 마무리 HOMING 중의 중지인가 (계약 7.4절 → NO_RESUMABLE_SCAN)."""
        point = self.resume_point
        return point is not None and point.during_final_homing

    @property
    def home_return_requested(self) -> bool:
        """이 작업에서 홈 안전복귀를 접수한 적이 있는가 (끝까지 갔는지와 무관)."""
        return self.home_return.requested

    @property
    def home_return_since_resume_point(self) -> bool:
        """재개 지점(resume_point) 뒤에 홈 안전복귀를 접수했는가 (계약 5.3절 → NOT_SUPPORTED).

        끝까지 갔는지와 무관하다. 안전복귀 도중에 다시 중지된 경우에도 참이다.
        재개 지점이 없으면 접수 여부 그대로다. 순서는 시각이 아니라 기록된 중지의 수로 본다.
        """
        if not self.home_return.requested:
            return False
        index = self._resume_point_index()
        return index is None or self.home_return.interruptions_at_request > index

    @property
    def confirmed_edges(self) -> Tuple[Direction, ...]:
        return tuple(d for d in self.direction_order if self.edges[d].valid)

    def slot(self, target) -> MeasurementSlot:
        return self.top if target == TOP else self.edges[edge_direction(target)]

    def to_dict(self):
        return {
            'schema_version': SCHEMA_VERSION,
            'kind': KIND_PROGRESS,
            'units': dict(UNITS),
            'scan_id': self.scan_id,
            'revision': self.revision,
            'started_at': self.started_at.to_dict(),
            'updated_at': self.updated_at.to_dict(),
            'state': self.state.to_dict(),
            'last_motion_id': self.last_motion_id,
            'frames': self.frames.to_dict(),
            'direction_order': [d.name for d in self.direction_order],
            'config': self.config.to_dict(),
            'node_params': dict(self.node_params),
            'measurements': {
                'top': self.top.to_dict(),
                'edges': {d.name: self.edges[d].to_dict() for d in EDGE_DIRECTIONS},
            },
            'interruptions': [item.to_dict() for item in self.interruptions],
            'home_return': self.home_return.to_dict(),
            'failure': _dump(self.failure),
            'result_saved': self.result_saved,
            'result_success': self.result_success,
        }

    @classmethod
    def from_dict(cls, data):
        edges = data['measurements']['edges']
        return cls(
            scan_id=data['scan_id'],
            started_at=Stamp.from_dict(data['started_at']),
            updated_at=Stamp.from_dict(data['updated_at']),
            state=StateRecord.from_dict(data['state']),
            frames=Frames.from_dict(data['frames']),
            direction_order=tuple(_text(d, 'direction_order') for d in data['direction_order']),
            config=ConfigSnapshot.from_dict(data['config']),
            node_params=data['node_params'],
            top=MeasurementSlot.from_dict(data['measurements']['top']),
            edges={
                edge_direction(_text(name, 'edges 의 방향')): MeasurementSlot.from_dict(slot)
                for name, slot in edges.items()
            },
            interruptions=[Interruption.from_dict(item) for item in data['interruptions']],
            home_return=HomeReturn.from_dict(data['home_return']),
            failure=_load(FailureRecord, data['failure']),
            result_saved=data['result_saved'],
            result_success=data['result_success'],
            revision=data['revision'],
            last_motion_id=data['last_motion_id'],
        )


# ---- 최종 결과 (result.json) ----

Point = Tuple[float, float, float]


@dataclass(frozen=True)
class SegmentRecord:
    """Segment.msg. 무효면 start · end · length 가 모두 None."""

    start: Optional[Point] = None
    end: Optional[Point] = None
    length: Optional[float] = None
    valid: bool = False

    def __post_init__(self):
        _bool(self.valid, 'valid')
        if not self.valid:
            if (self.start, self.end) != (None, None):
                raise ValueError('valid=false 인 선분에 좌표가 있다. None 으로 둔다(0 금지)')
            _set(self, length=_optional(self.length, False, 'length'))
            return
        _set(
            self,
            start=_vector(self.start, 3, 'start'),
            end=_vector(self.end, 3, 'end'),
            length=_finite(self.length, 'length'),
        )

    def to_dict(self):
        return {
            'start': None if self.start is None else list(self.start),
            'end': None if self.end is None else list(self.end),
            'length': self.length,
            'valid': self.valid,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(data['start'], data['end'], data['length'], data['valid'])


def _missing_segments(count):
    return tuple(SegmentRecord() for _ in range(count))


_SHAPE_SCALARS = ('z_top', 'x_pos', 'x_neg', 'y_pos', 'y_neg', 'support_z')
_SHAPE_DIMS = ('width', 'length', 'height')


@dataclass(frozen=True)
class ShapeResult:
    """ScanResult.msg (3.5절) 의 형상. 필드 이름 · 순서 규약은 계약 그대로다. 좌표는 frame_id 기준.

    기본값은 전부 "미측정"이다. 그래서 실패한 결과는 얻은 값만 채우면 된다.
    """

    success: bool
    reason_code: int
    detail: str
    frame_id: str
    started_at: Stamp
    finished_at: Stamp  # GEOMETRY 가 끝난 시각 (7.4절)
    z_top: Measured = field(default_factory=Measured.missing)
    x_pos: Measured = field(default_factory=Measured.missing)
    x_neg: Measured = field(default_factory=Measured.missing)
    y_pos: Measured = field(default_factory=Measured.missing)
    y_neg: Measured = field(default_factory=Measured.missing)
    support_z: Measured = field(default_factory=Measured.missing)
    width: Optional[float] = None
    length: Optional[float] = None
    height: Optional[float] = None
    dims_valid: bool = False
    vertices: Tuple[Optional[Point], ...] = (None,) * 8
    edges: Tuple[SegmentRecord, ...] = field(default_factory=lambda: _missing_segments(12))
    path_candidates: Tuple[SegmentRecord, ...] = field(
        default_factory=lambda: _missing_segments(4))
    box_valid: bool = False

    def __post_init__(self):
        _bool(self.success, 'success')
        if (_uint(self.reason_code, 'reason_code') == 0) != self.success:
            raise ValueError('success 와 reason_code 가 어긋난다(성공 = 0)')
        _text(self.detail, 'detail')
        _text(self.frame_id, 'frame_id', allow_empty=False)
        for name in _SHAPE_SCALARS:
            if not isinstance(getattr(self, name), Measured):
                raise ValueError(f'{name} 은 Measured 여야 한다')
        for name in _SHAPE_DIMS:
            _set(self, **{name: _optional(getattr(self, name), self.dims_valid, name)})

        _bool(self.box_valid, 'box_valid')
        sizes = (('vertices', 8), ('edges', 12), ('path_candidates', 4))
        for name, size in sizes:
            if len(getattr(self, name)) != size:
                raise ValueError(f'{name} 의 길이는 {size} 여야 한다(무효여도 길이를 유지한다)')
        if self.box_valid:
            vertices = tuple(_vector(v, 3, f'vertices[{i}]') for i, v in enumerate(self.vertices))
        elif any(v is not None for v in self.vertices):
            raise ValueError('box_valid=false 인데 꼭짓점 좌표가 있다. None 으로 둔다(0 금지)')
        else:
            vertices = (None,) * 8
        segments = tuple(self.edges) + tuple(self.path_candidates)
        if any(not isinstance(s, SegmentRecord) or s.valid != self.box_valid for s in segments):
            raise ValueError('edges · path_candidates 의 valid 는 box_valid 와 같아야 한다')
        _set(
            self, vertices=vertices,
            edges=tuple(self.edges), path_candidates=tuple(self.path_candidates))
        if self.success:
            scalars_valid = all(getattr(self, name).valid for name in _SHAPE_SCALARS)
            if not (scalars_valid and self.dims_valid and self.box_valid):
                raise ValueError('success=true 인데 무효인 값이 있다. 5점 미확보 · 비정상 형상은 실패다')

    def to_dict(self):
        data = {
            'success': self.success,
            'reason_code': self.reason_code,
            'detail': self.detail,
            'frame_id': self.frame_id,
        }
        for name in _SHAPE_SCALARS[:5]:
            data[name] = getattr(self, name).value
            data[f'{name}_valid'] = getattr(self, name).valid
        for name in _SHAPE_DIMS:
            data[name] = getattr(self, name)
        data.update({
            'dims_valid': self.dims_valid,
            'support_z': self.support_z.value,
            'support_z_valid': self.support_z.valid,
            'vertices': [None if v is None else list(v) for v in self.vertices],
            'box_valid': self.box_valid,
            'edges': [s.to_dict() for s in self.edges],
            'path_candidates': [s.to_dict() for s in self.path_candidates],
            'started_at': self.started_at.to_dict(),
            'finished_at': self.finished_at.to_dict(),
        })
        return data

    @classmethod
    def from_dict(cls, data):
        scalars = {
            name: Measured(data[name], data[f'{name}_valid']) for name in _SHAPE_SCALARS}
        return cls(
            success=data['success'],
            reason_code=data['reason_code'],
            detail=data['detail'],
            frame_id=data['frame_id'],
            started_at=Stamp.from_dict(data['started_at']),
            finished_at=Stamp.from_dict(data['finished_at']),
            width=data['width'],
            length=data['length'],
            height=data['height'],
            dims_valid=data['dims_valid'],
            vertices=tuple(data['vertices']),
            edges=tuple(SegmentRecord.from_dict(s) for s in data['edges']),
            path_candidates=tuple(SegmentRecord.from_dict(s) for s in data['path_candidates']),
            box_valid=data['box_valid'],
            **scalars,
        )


@dataclass(frozen=True)
class BiasCorrection:
    """한 방향의 편향 보정량. result_store 원본에만 기록한다(계약 3.5절).

    raw_coordinate_m: 보정 전 판정 좌표에서 그 방향 축의 값(판정 좌표의 프레임).
    correction_m: 진행 방향 반대로 적용한 보정 크기 √(2rδ−δ²) + v·지연.
    inputs: 보정에 쓴 값(예: z_drop_m · tip_radius_m · slide_speed_mps · detect_latency_s). 모르면 None.
    """

    raw_coordinate_m: Optional[float] = None
    correction_m: Optional[float] = None
    valid: bool = False
    inputs: Mapping[str, Optional[float]] = field(default_factory=dict)

    def __post_init__(self):
        _set(
            self,
            raw_coordinate_m=_optional(self.raw_coordinate_m, self.valid, 'raw_coordinate_m'),
            correction_m=_optional(self.correction_m, self.valid, 'correction_m'),
            inputs={
                _text(name, 'inputs 의 이름', allow_empty=False):
                    _optional(value, value is not None and value == value, name)
                for name, value in dict(self.inputs).items()
            },
        )

    def to_dict(self):
        return {
            'raw_coordinate_m': self.raw_coordinate_m,
            'correction_m': self.correction_m,
            'valid': self.valid,
            'inputs': dict(self.inputs),
        }

    @classmethod
    def from_dict(cls, data):
        return cls(data['raw_coordinate_m'], data['correction_m'], data['valid'], data['inputs'])


@dataclass(frozen=True)
class ResultRecord:
    """최종 결과 원본 (result.json). config · node_params 는 store 가 진행 기록에서 옮겨 적는다."""

    scan_id: str
    shape: ShapeResult
    bias_corrections: Mapping[Direction, BiasCorrection]
    config: ConfigSnapshot
    node_params: dict
    saved_at: Stamp

    def __post_init__(self):
        check_scan_id(self.scan_id)
        corrections = {edge_direction(d): c for d, c in dict(self.bias_corrections).items()}
        for direction in EDGE_DIRECTIONS:
            corrections.setdefault(direction, BiasCorrection())
        if any(not isinstance(c, BiasCorrection) for c in corrections.values()):
            raise ValueError('bias_corrections 의 값은 BiasCorrection 이어야 한다')
        _set(self, bias_corrections=corrections, node_params=check_node_params(self.node_params))

    def to_dict(self):
        return {
            'schema_version': SCHEMA_VERSION,
            'kind': KIND_RESULT,
            'units': dict(UNITS),
            'scan_id': self.scan_id,
            'saved_at': self.saved_at.to_dict(),
            'shape': self.shape.to_dict(),
            'bias_corrections': {
                d.name: self.bias_corrections[d].to_dict() for d in EDGE_DIRECTIONS},
            'config': self.config.to_dict(),
            'node_params': dict(self.node_params),
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            scan_id=data['scan_id'],
            shape=ShapeResult.from_dict(data['shape']),
            bias_corrections={
                _text(name, 'bias_corrections 의 방향'): BiasCorrection.from_dict(item)
                for name, item in data['bias_corrections'].items()
            },
            config=ConfigSnapshot.from_dict(data['config']),
            node_params=data['node_params'],
            saved_at=Stamp.from_dict(data['saved_at']),
        )
