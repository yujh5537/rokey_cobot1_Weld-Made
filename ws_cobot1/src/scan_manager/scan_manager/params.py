"""scan_manager 파라미터의 이름 · 필수 여부 · 범위 검사 (순수 Python, rclpy 없음).

- 값은 contact_scan_bringup/config/*.yaml 에만 둔다. **모션 · 보정 수치에는 코드 예비값이 없다**(CLAUDE.md 규칙 7).
  값이 없어도 노드는 기동해 IDLE 로 있고, 필수 항목이 비어 있으면 START 를 INVALID_VALUE 로 거절한다.
- "없음"은 None 이다. 0 은 값이다(support_z_m · edge_round_radius_m · edge_bias_offset_m · detect_latency_s 는
  0 이 정당하다). 없는 값을 0 으로 채우지 않는다(규칙 4).
- 계약 이름(ros-interfaces.md 6.4절)은 SetConfig 가 이름으로 다루므로 바꾸지 않는다.
- 노드는 SPECS 를 돌며 파라미터를 선언하고, 읽은 값을 dict 로 모아 check() 에 넘긴다.
"""

from dataclasses import dataclass
import math
from typing import Callable, Dict, Mapping, Optional, Tuple

from .contract_enums import Direction

DOUBLE = 'double'
DOUBLE_ARRAY = 'double_array'
STRING = 'string'
STRING_ARRAY = 'string_array'

# 단위 quaternion 인지 볼 때의 허용 오차. 튜닝 값이 아니라 입력 오타를 거르는 검사다.
_QUATERNION_NORM_TOLERANCE = 1e-3


def _number(value) -> bool:
    return (
        isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value))


def positive(value) -> Optional[str]:
    return None if _number(value) and value > 0.0 else '0 보다 큰 유한한 수여야 한다'


def non_negative(value) -> Optional[str]:
    return None if _number(value) and value >= 0.0 else '0 이상의 유한한 수여야 한다'


def finite(value) -> Optional[str]:
    return None if _number(value) else '유한한 수여야 한다'


def _vector(size) -> Callable:
    def check(value) -> Optional[str]:
        if not isinstance(value, (list, tuple)) or len(value) != size:
            return f'원소 {size} 개의 배열이어야 한다'
        if not all(_number(v) for v in value):
            return '모든 원소가 유한한 수여야 한다'
        return None
    return check


def _pose(value) -> Optional[str]:
    problem = _vector(7)(value)
    if problem:
        return problem + ' (x, y, z, qx, qy, qz, qw)'
    norm = math.sqrt(sum(q * q for q in value[3:]))
    if abs(norm - 1.0) > _QUATERNION_NORM_TOLERANCE:
        return f'quaternion 의 크기가 1 이 아니다({norm:.6f})'
    return None


def _non_empty_text(value) -> Optional[str]:
    return None if isinstance(value, str) and value else '빈 문자열이 아니어야 한다'


def _direction_order(value) -> Optional[str]:
    names = sorted(d.name for d in Direction if d is not Direction.NONE)
    if not isinstance(value, (list, tuple)) or sorted(value) != names:
        return f'{names} 를 한 번씩 담아야 한다'
    return None


@dataclass(frozen=True)
class ParamSpec:
    name: str
    kind: str
    required: bool
    check: Callable
    doc: str
    default: object = None  # 이름 · 프레임 같은 비수치 항목에만 둔다


# 계약 6.4절의 scan_manager 파라미터. SetConfig · RunScan.config_override 로 바꿀 수 있는 것은 이 6개뿐이다.
MOTION_CONFIG_NAMES = (
    'descend_speed_mps', 'slide_speed_mps', 'max_descend_m', 'max_slide_m',
    'motion_timeout_s', 'lift_height_m',
)

SPECS: Tuple[ParamSpec, ...] = (
    ParamSpec('descend_speed_mps', DOUBLE, True, positive, 'OP_DESCEND 속도 (계약 이름)'),
    ParamSpec('slide_speed_mps', DOUBLE, True, positive, 'OP_SLIDE 속도 (계약 이름)'),
    ParamSpec('max_descend_m', DOUBLE, True, positive, '미접촉 실패 한계 (계약 이름)'),
    ParamSpec('max_slide_m', DOUBLE, True, positive, '미소실 실패 한계 (계약 이름)'),
    ParamSpec('motion_timeout_s', DOUBLE, True, positive, '단위 모션 제한 시간 (계약 이름)'),
    ParamSpec('lift_height_m', DOUBLE, True, positive, '방향 전환 · 마무리 때 팁 상승량 (계약 이름)'),
    ParamSpec('move_speed_mps', DOUBLE, True, positive,
              'OP_MOVE_TO 속도: 기준점 이동 · 방향 전환의 올림과 수평 이동 · 마무리 들어 올림'),
    ParamSpec('recontact_margin_m', DOUBLE, True, positive,
              '방향 전환 뒤 내림 목표 = 첫 접촉 z + 이 값 (계약 7.3절)'),
    ParamSpec('recontact_speed_mps', DOUBLE, True, positive, '방향 전환 뒤 내림 속도(저속)'),
    ParamSpec('search_origin_pose', DOUBLE_ARRAY, True, _pose,
              '탐색 기준점 상공의 pose. Base, x y z qx qy qz qw'),
    ParamSpec('base_to_fixture', DOUBLE_ARRAY, True, _vector(3),
              '작업대 원점의 Base 좌표 x y z. 평행 이동만 (units-frames.md)'),
    ParamSpec('support_z_m', DOUBLE, True, finite, '지지면 높이(작업대 좌표). 0 이 정당한 값이다'),
    ParamSpec('tip_radius_m', DOUBLE, True, positive, '편향 보정 r. 반지름이다'),
    ParamSpec('detect_latency_s', DOUBLE, True, non_negative, '편향 보정 지연 t'),
    ParamSpec('edge_round_radius_m', DOUBLE, True, non_negative, '부재 모서리 둥글림 R. 예리하면 0'),
    ParamSpec('edge_bias_offset_m', DOUBLE, True, finite, '실측 나머지 편향. 방향당 값, 진행 방향 +'),
    ParamSpec('result_dir', STRING, True, _non_empty_text, 'result_store 경로'),
    ParamSpec('event_wait_timeout_s', DOUBLE, True, positive, 'Result 와 ContactEvent 의 도착 순서 차이'),
    ParamSpec('stop_confirm_timeout_s', DOUBLE, True, positive, '정지 완료 확인을 기다리는 한도'),
    ParamSpec('server_wait_timeout_s', DOUBLE, True, positive, '상대 서버 미기동 판단'),
    ParamSpec('result_frame_id', STRING, False, _non_empty_text,
              'ScanResult 의 프레임(가칭)', default='workpiece_fixture'),
    ParamSpec('motion_frame_id', STRING, False, _non_empty_text,
              'ExecuteMotion goal 의 프레임(가칭)', default='base_link'),
    ParamSpec('direction_order', STRING_ARRAY, False, _direction_order, '모서리 탐색 순서',
              default=('POS_X', 'NEG_X', 'POS_Y', 'NEG_Y')),
)
SPEC_BY_NAME: Dict[str, ParamSpec] = {spec.name: spec for spec in SPECS}

# 다른 노드의 값이라 scan_manager 는 보관만 하는 ScanConfig 항목(계약 3.9절)의 범위 검사.
_FOREIGN_CONFIG_CHECKS = {
    'contact_threshold_n': positive,
    'edge_drop_m': positive,
    'debounce_n': lambda v: None if _number(v) and v >= 1 and float(v).is_integer()
    else '1 이상의 정수여야 한다',
    'over_force_n': positive,
    'target_force_n': positive,
    'drop_limit_m': positive,
}


@dataclass(frozen=True)
class ScanParams:
    """검사를 통과한 파라미터 한 벌. 단위는 ROS 내부 단위(m · s · m/s)."""

    descend_speed_mps: float
    slide_speed_mps: float
    max_descend_m: float
    max_slide_m: float
    motion_timeout_s: float
    lift_height_m: float
    move_speed_mps: float
    recontact_margin_m: float
    recontact_speed_mps: float
    search_origin_pose: Tuple[float, ...]
    base_to_fixture: Tuple[float, float, float]
    support_z_m: float
    tip_radius_m: float
    detect_latency_s: float
    edge_round_radius_m: float
    edge_bias_offset_m: float
    result_dir: str
    event_wait_timeout_s: float
    stop_confirm_timeout_s: float
    server_wait_timeout_s: float
    result_frame_id: str
    motion_frame_id: str
    direction_order: Tuple[Direction, ...]

    @property
    def origin_position(self) -> Tuple[float, float, float]:
        return tuple(self.search_origin_pose[:3])

    @property
    def origin_orientation(self) -> Tuple[float, float, float, float]:
        return tuple(self.search_origin_pose[3:])

    def node_params(self) -> dict:
        """result_store 의 node_params 에 남길 스냅숏(재현 조건). 계약 6개는 config 쪽에 있다."""
        skip = set(MOTION_CONFIG_NAMES) | {'direction_order'}
        return {
            spec.name: _plain(getattr(self, spec.name))
            for spec in SPECS if spec.name not in skip
        }


def _plain(value):
    return list(value) if isinstance(value, tuple) else value


@dataclass(frozen=True)
class ParamCheck:
    """check() 의 결과. params 는 missing · invalid 가 모두 비었을 때만 있다."""

    params: Optional[ScanParams]
    missing: Tuple[str, ...]
    invalid: Tuple[str, ...]  # '이름 = 값: 이유'

    @property
    def ok(self) -> bool:
        return self.params is not None

    def describe(self) -> str:
        parts = []
        if self.missing:
            parts.append('없는 필수 파라미터: ' + ', '.join(self.missing))
        if self.invalid:
            parts.append('범위 밖: ' + '; '.join(self.invalid))
        return ' / '.join(parts)


def check_values(values: Mapping[str, object], names=None) -> Tuple[str, ...]:
    """값이 있는 항목의 범위 검사. '이름 = 값: 이유' 목록을 돌려준다."""
    problems = []
    for name in (names if names is not None else values):
        value = values.get(name)
        if value is None:
            continue
        checker = SPEC_BY_NAME[name].check if name in SPEC_BY_NAME else _FOREIGN_CONFIG_CHECKS[name]
        problem = checker(value)
        if problem:
            problems.append(f'{name} = {value!r}: {problem}')
    return tuple(problems)


def check(values: Mapping[str, object]) -> ParamCheck:
    """yaml · SetConfig · override 를 합친 값으로 ScanParams 를 만든다.

    values 에 없는 이름과 None 은 "없음"이다. 필수가 아닌 항목은 비어 있으면 spec.default 를 쓴다.
    """
    merged = {}
    missing = []
    for spec in SPECS:
        value = values.get(spec.name)
        if value is None:
            if spec.required:
                missing.append(spec.name)
                continue
            value = spec.default
        merged[spec.name] = value
    invalid = list(check_values(merged))
    if not invalid and not missing:
        margin, lift = merged['recontact_margin_m'], merged['lift_height_m']
        if margin >= lift:
            invalid.append(
                f'recontact_margin_m = {margin!r}: lift_height_m({lift!r}) 보다 작아야 한다')
    if missing or invalid:
        return ParamCheck(None, tuple(missing), tuple(invalid))

    for spec in SPECS:
        if spec.kind == DOUBLE:
            merged[spec.name] = float(merged[spec.name])
        elif spec.kind == DOUBLE_ARRAY:
            merged[spec.name] = tuple(float(v) for v in merged[spec.name])
    merged['direction_order'] = tuple(Direction[name] for name in merged['direction_order'])
    return ParamCheck(ScanParams(**merged), (), ())
