"""weld_manager 파라미터의 이름 · 필수 여부 · 범위 검사 (순수 Python, rclpy 없음).

- 이름은 계약이다(docs/phase2/weld-motion.md 6절 표). 값은 contact_scan_bringup/config/*.yaml 의 `weld_manager:` 절에만
  둔다. **모션 수치에는 코드 예비값이 없다**(CLAUDE.md 규칙 7). 빠지면 START 를 거절한다(노드는 기동해 IDLE 로 있다).
- "없음"은 None 이다. 0 은 값이다(weave_amplitude_m · weave_pitch_m 0 = 직선, tool_roll_deg 0 = 돌리지 않음).
- RunWeld.config_override(WeldConfig 의 *_set=true 항목)는 그 작업에만 덮어쓴다. 파라미터는 바꾸지 않는다(3.1절).
- 노드는 SPECS 를 돌며 파라미터를 선언하고, 읽은 값을 dict 로 모아 check() 에 넘긴다.
"""

from dataclasses import dataclass
import math
from typing import Callable, Dict, Mapping, Optional, Tuple

DOUBLE = 'double'
STRING = 'string'

# WeldConfig 의 항목 (weld-ros-interfaces.md 3.1절). 필드 이름 = 파라미터 이름
CONFIG_NAMES = (
    'weld_speed_mps', 'travel_speed_mps', 'standoff_m',
    'weave_amplitude_m', 'weave_pitch_m', 'tilt_deg',
)
# 3.1절: tilt 는 0~80° 밖이면 INVALID_VALUE
TILT_RANGE_DEG = (0.0, 80.0)


def _number(value) -> bool:
    return (
        isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value))


def positive(value) -> Optional[str]:
    return None if _number(value) and value > 0.0 else '0 보다 큰 유한한 수여야 한다'


def non_negative(value) -> Optional[str]:
    return None if _number(value) and value >= 0.0 else '0 이상의 유한한 수여야 한다'


def finite(value) -> Optional[str]:
    return None if _number(value) else '유한한 수여야 한다'


def tilt(value) -> Optional[str]:
    low, high = TILT_RANGE_DEG
    if _number(value) and low <= value <= high:
        return None
    return f'{low:g}~{high:g} 사이의 수여야 한다'


def non_empty_text(value) -> Optional[str]:
    return None if isinstance(value, str) and value else '빈 문자열이 아니어야 한다'


@dataclass(frozen=True)
class ParamSpec:
    name: str
    kind: str
    required: bool
    check: Callable
    doc: str
    default: object = None   # required=False 인 이름표(프레임 이름)만 쓴다. 수치에는 두지 않는다


SPECS: Tuple[ParamSpec, ...] = (
    ParamSpec('weld_speed_mps', DOUBLE, True, positive, '용접선 위 TCP 속도 [m/s]'),
    ParamSpec('travel_speed_mps', DOUBLE, True, positive, '선 사이(z_safe) 이동 속도 [m/s]'),
    ParamSpec('approach_speed_mps', DOUBLE, True, positive, '접근 2 · 후퇴 속도 [m/s]'),
    ParamSpec('standoff_m', DOUBLE, True, positive, '팁이 이음선에서 툴 축 뒤로 물러나는 거리 [m]. 0 은 접촉이라 받지 않는다'),
    ParamSpec('weave_amplitude_m', DOUBLE, True, non_negative, '위빙 진폭 [m]. 0 = 직선'),
    ParamSpec('weave_pitch_m', DOUBLE, True, non_negative, '위빙 반주기 [m]. 0 = 직선'),
    ParamSpec('tilt_deg', DOUBLE, True, tilt, '툴 축이 연직에서 바깥으로 기우는 각 [deg]'),
    ParamSpec('tool_roll_deg', DOUBLE, True, finite, '툴 축 둘레 회전 [deg] (도달성 조정)'),
    ParamSpec('approach_m', DOUBLE, True, positive, '접근 · 후퇴 거리 [m] (툴 축 뒤로)'),
    ParamSpec('travel_clearance_m', DOUBLE, True, positive, 'z_safe = z_top + 이 값 [m] (작업대 좌표)'),
    ParamSpec('bottom_margin_m', DOUBLE, True, non_negative, '세로선 끝 = support_z + 이 값 [m]'),
    ParamSpec('workspace_margin_m', DOUBLE, True, non_negative, '부재 밖 허용 범위 x · y [m]'),
    ParamSpec('path_tolerance_m', DOUBLE, True, positive, 'ExecutePath 마지막 점 도착 허용치 [m]'),
    ParamSpec('motion_timeout_s', DOUBLE, True, positive, '단위 goal 제한 시간 [s]'),
    # 3.1절의 속도 상한. robot_manager 파라미터와 같은 이름 · 같은 값이어야 한다(bringup 시험으로 대조, 병후 확인 대기 Q2)
    ParamSpec('path_max_speed_mps', DOUBLE, True, positive, 'WeldConfig 속도 상한 [m/s] (robot_manager 와 같은 값)'),
    ParamSpec('state_publish_period_s', DOUBLE, True, positive, '/weld/state 주기 발행 간격 [s]'),
    ParamSpec('scan_state_timeout_s', DOUBLE, True, positive, '/scan/state 가 이보다 오래됐으면 시작 거절 [s]'),
    ParamSpec('result_dir', STRING, True, non_empty_text, 'result_store 경로. scan_manager 와 같은 값'),
    ParamSpec('result_frame_id', STRING, False, non_empty_text,
              'ScanResult · WeldResult 의 프레임(가칭)', default='workpiece_fixture'),
    ParamSpec('motion_frame_id', STRING, False, non_empty_text,
              'ExecuteMotion · ExecutePath goal 의 프레임(가칭)', default='base_link'),
)
SPEC_BY_NAME: Dict[str, ParamSpec] = {spec.name: spec for spec in SPECS}


@dataclass(frozen=True)
class WeldParams:
    """검사를 통과한 파라미터 한 벌(덮어쓰기 적용 후). 단위는 ROS 내부 단위(m · s · m/s), 각도만 이름대로 deg."""

    weld_speed_mps: float
    travel_speed_mps: float
    approach_speed_mps: float
    standoff_m: float
    weave_amplitude_m: float
    weave_pitch_m: float
    tilt_deg: float
    tool_roll_deg: float
    approach_m: float
    travel_clearance_m: float
    bottom_margin_m: float
    workspace_margin_m: float
    path_tolerance_m: float
    motion_timeout_s: float
    path_max_speed_mps: float
    state_publish_period_s: float
    scan_state_timeout_s: float
    result_dir: str
    result_frame_id: str
    motion_frame_id: str

    @property
    def tilt_rad(self) -> float:
        return math.radians(self.tilt_deg)

    @property
    def tool_roll_rad(self) -> float:
        return math.radians(self.tool_roll_deg)

    def config_values(self) -> Dict[str, float]:
        """WeldResult.config(적용 설정 스냅샷, 전부 *_set=true)에 실을 값."""
        return {name: getattr(self, name) for name in CONFIG_NAMES}


@dataclass(frozen=True)
class ParamCheck:
    """check() 의 결과. params 는 missing · invalid 가 모두 비었을 때만 있다."""

    params: Optional[WeldParams]
    missing: Tuple[str, ...]
    invalid: Tuple[str, ...]  # '이름 = 값: 이유'

    @property
    def ok(self) -> bool:
        return self.params is not None

    def describe(self) -> str:
        parts = []
        if self.missing:
            parts.append('없음: ' + ', '.join(self.missing))
        if self.invalid:
            parts.append('범위 밖: ' + '; '.join(self.invalid))
        return ' / '.join(parts)


def check_override(override: Mapping[str, object]) -> Tuple[str, ...]:
    """WeldConfig 덮어쓰기에서 온 값만 따로 본다. 모르는 이름도 거절한다. 문제 목록('이름 = 값: 이유')."""
    problems = []
    for name, value in override.items():
        if name not in CONFIG_NAMES:
            problems.append(f'{name} = {value!r}: WeldConfig 항목이 아니다')
            continue
        why = SPEC_BY_NAME[name].check(value)
        if why:
            problems.append(f'{name} = {value!r}: {why}')
    return tuple(problems)


def check(values: Mapping[str, object], override: Optional[Mapping[str, object]] = None) -> ParamCheck:
    """파라미터 값(+ 이번 작업의 덮어쓰기)을 검사한다. values · override 는 바꾸지 않는다.

    values 에서 None 은 "yaml 에 없음"이다. override 는 WeldConfig 의 *_set=true 항목만 담는다.
    """
    merged = dict(values)
    merged.update(override or {})
    missing, invalid, clean = [], [], {}
    for spec in SPECS:
        value = merged.get(spec.name)
        if value is None:
            if spec.required:
                missing.append(spec.name)
                continue
            value = spec.default
        why = spec.check(value)
        if why:
            invalid.append(f'{spec.name} = {value!r}: {why}')
            continue
        clean[spec.name] = float(value) if spec.kind == DOUBLE else value
    # 3.1절: 속도는 path_max_speed_mps 를 넘을 수 없다
    limit = clean.get('path_max_speed_mps')
    if limit is not None:
        for name in ('weld_speed_mps', 'travel_speed_mps', 'approach_speed_mps'):
            if name in clean and clean[name] > limit:
                invalid.append(f'{name} = {clean[name]!r}: path_max_speed_mps({limit!r}) 를 넘는다')
                del clean[name]
    if missing or invalid:
        return ParamCheck(None, tuple(missing), tuple(invalid))
    return ParamCheck(WeldParams(**clean), (), ())
