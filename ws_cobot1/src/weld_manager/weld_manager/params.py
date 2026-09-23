"""weld_manager 파라미터의 이름 · 필수 여부 · 범위 검사 (순수 Python, rclpy 없음).

- 이름은 계약이다(docs/phase2/weld-motion.md 6절 표, weld-ros-interfaces.md 6장). 값은
  contact_scan_bringup/config/*.yaml 의 `weld_manager:` 절에만 둔다. **모션 수치에는 코드 예비값이 없다**(CLAUDE.md 규칙 7).
  빠지면 START 를 거절한다(노드는 기동해 IDLE 로 있다).
- "없음"은 None 이다. 0 은 값이다(weave_amplitude_m · weave_pitch_m 0 = 직선, tool_roll_deg 0 = 돌리지 않음).
- RunWeld.config_override(WeldConfig 의 *_set=true 항목)는 그 작업에만 덮어쓴다. 파라미터는 바꾸지 않는다(3.1절).
- 속도는 하한(weld_speed_min_mps)만 본다. 상한은 robot_manager 의 path_max_speed_mps 가 거른다(D29).
- 노드는 SPECS 를 돌며 파라미터를 선언하고, 읽은 값을 dict 로 모아 check() 에 넘긴다.
"""

from dataclasses import dataclass
import math
from typing import Callable, Dict, Mapping, Optional, Tuple

from .contract_enums import LINE_COUNT

DOUBLE = 'double'
DOUBLE_ARRAY = 'double_array'
STRING = 'string'

# WeldConfig 의 항목 (weld-ros-interfaces.md 3.1절). 필드 이름 = 파라미터 이름
CONFIG_NAMES = (
    'weld_speed_mps', 'travel_speed_mps', 'standoff_m',
    'weave_amplitude_m', 'weave_pitch_m', 'tilt_deg',
)
# 3.1절: tilt 는 0~80° 밖이면 INVALID_VALUE
TILT_RANGE_DEG = (0.0, 80.0)
# weld_speed_min_mps 를 하한으로 보는 속도들 (3.1절 · 6절: 용접 · 접근. 선 사이 이동도 WeldConfig 속도라 같이 본다)
SPEED_NAMES = ('weld_speed_mps', 'travel_speed_mps', 'approach_speed_mps')


def _number(value) -> bool:
    return (
        isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value))


def positive(value) -> Optional[str]:
    return None if _number(value) and value > 0.0 else '0 보다 큰 유한한 수여야 한다'


def non_negative(value) -> Optional[str]:
    return None if _number(value) and value >= 0.0 else '0 이상의 유한한 수여야 한다'


def tilt(value) -> Optional[str]:
    low, high = TILT_RANGE_DEG
    if _number(value) and low <= value <= high:
        return None
    return f'{low:g}~{high:g} 사이의 수여야 한다'


def non_empty_text(value) -> Optional[str]:
    return None if isinstance(value, str) and value else '빈 문자열이 아니어야 한다'


def _array(element_check: Callable, size: Optional[int] = None, what='') -> Callable:
    def check(value) -> Optional[str]:
        if not isinstance(value, (list, tuple)) or not value:
            return '비어 있지 않은 배열이어야 한다'
        if size is not None and len(value) != size:
            return f'원소 {size} 개의 배열이어야 한다{what}'
        for item in value:
            why = element_check(item)
            if why:
                return f'모든 원소가 {why.removesuffix("여야 한다")}여야 한다'
        return None
    return check


def _increasing(value) -> Optional[str]:
    problem = _array(non_negative)(value)
    if problem:
        return problem
    if any(b <= a for a, b in zip(value, value[1:])):
        return '작은 값부터 커지는 순서여야 한다(같은 값 없이)'
    return None


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
    ParamSpec('weld_speed_min_mps', DOUBLE, True, positive,
              '속도 하한 [m/s]. robot_manager 이동 판정(약 0.67 mm/s)보다 커야 한다(#152)'),
    ParamSpec('standoff_m', DOUBLE, True, positive,
              '팁 구 표면 ↔ 이음선 최단거리 [m] (D22). 0 은 접촉이라 받지 않는다'),
    ParamSpec('tip_radius_m', DOUBLE, True, positive, '팁 구 반지름 [m]. scan_manager 와 같은 값'),
    ParamSpec('weave_amplitude_m', DOUBLE, True, non_negative, '위빙 진폭 [m]. 0 = 직선'),
    ParamSpec('weave_pitch_m', DOUBLE, True, non_negative, '위빙 반주기 [m]. 0 = 직선'),
    ParamSpec('tilt_deg', DOUBLE, True, tilt, '툴 축이 연직에서 바깥으로 기우는 각 [deg]'),
    ParamSpec('tool_roll_deg', DOUBLE_ARRAY, True, _array(lambda v: None if _number(v) else '유한한 수여야 한다',
                                                          LINE_COUNT, ' (선 L0~L7 마다 하나)'),
              '선별 툴 축 둘레 회전 [deg] (D24, 도달성 · 핑거 방향 조정)'),
    ParamSpec('tool_profile_u_m', DOUBLE_ARRAY, True, _increasing,
              '툴 외형: 팁에서 축 방향 뒤 거리 u [m] (D23 · D28). tool_profile_r_m 과 같은 길이'),
    ParamSpec('tool_profile_r_m', DOUBLE_ARRAY, True, _array(positive),
              '툴 외형: u 부터 다음 u 전까지 축에서 가장 멀리 뻗은 반폭 R [m]'),
    ParamSpec('approach_m', DOUBLE, True, positive, '접근 · 후퇴 거리 [m] (툴 축 뒤로)'),
    ParamSpec('travel_clearance_m', DOUBLE, True, positive, 'z_safe = z_top + 이 값 [m] (작업대 좌표)'),
    ParamSpec('bottom_margin_m', DOUBLE, True, non_negative, '세로선 끝 = support_z + 이 값 [m]'),
    ParamSpec('workspace_margin_m', DOUBLE, True, non_negative, '부재 밖 허용 범위 x · y [m]'),
    ParamSpec('path_tolerance_m', DOUBLE, True, positive, 'ExecutePath 마지막 점 도착 허용치 [m]'),
    ParamSpec('motion_timeout_s', DOUBLE, True, positive, '단위 goal 제한 시간 [s]'),
    ParamSpec('tool_check_max_force_n', DOUBLE, True, positive,
              '시작 때 무접촉 |F| 가 이보다 크면 툴 미등록으로 본다 [N] (TOOL_REG_SUSPECT 302)'),
    # 노드가 기다리는 한도 (scan_manager 와 같은 이름 · 뜻, 6절 표 38b55e8)
    ParamSpec('server_wait_timeout_s', DOUBLE, True, positive,
              'robot_manager 의 액션 서버 · goal 응답을 기다리는 한도 [s]'),
    ParamSpec('stop_confirm_timeout_s', DOUBLE, True, positive,
              '정지 요청 뒤 /robot/status 로 connected && !moving 을 확인하는 한도 [s]'),
    ParamSpec('sample_timeout_s', DOUBLE, True, positive,
              '시작 · 안전복귀 때 /robot/sample 이 이보다 오래됐으면 없는 것으로 본다 [s] (NO_SAMPLE 307)'),
    # 도착 자세 대조 (6절 표 38b55e8). robot_manager 는 도착을 위치로만 본다. 0 = 끔
    ParamSpec('orientation_tolerance_deg', DOUBLE, True, non_negative,
              '각 이동 뒤 Result.pose 자세와 목표 자세의 허용 차이 [deg]. 넘으면 ROBOT_ERROR(204). 0 = 끔'),
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
    """검사를 통과한 파라미터 한 벌(덮어쓰기 적용 후). 단위는 ROS 내부 단위(m · s · m/s · N), 각도만 이름대로 deg."""

    weld_speed_mps: float
    travel_speed_mps: float
    approach_speed_mps: float
    weld_speed_min_mps: float
    standoff_m: float
    tip_radius_m: float
    weave_amplitude_m: float
    weave_pitch_m: float
    tilt_deg: float
    tool_roll_deg: Tuple[float, ...]       # 8 개, 선 L0~L7
    tool_profile_u_m: Tuple[float, ...]
    tool_profile_r_m: Tuple[float, ...]
    approach_m: float
    travel_clearance_m: float
    bottom_margin_m: float
    workspace_margin_m: float
    path_tolerance_m: float
    motion_timeout_s: float
    tool_check_max_force_n: float
    server_wait_timeout_s: float
    stop_confirm_timeout_s: float
    sample_timeout_s: float
    orientation_tolerance_deg: float     # 0 = 대조하지 않는다
    state_publish_period_s: float
    scan_state_timeout_s: float
    result_dir: str
    result_frame_id: str
    motion_frame_id: str

    @property
    def tilt_rad(self) -> float:
        return math.radians(self.tilt_deg)

    def tool_roll_rad(self, line_index: int) -> float:
        return math.radians(self.tool_roll_deg[line_index])

    @property
    def orientation_tolerance_rad(self) -> Optional[float]:
        deg = self.orientation_tolerance_deg
        return None if deg == 0.0 else math.radians(deg)

    @property
    def tool_profile(self) -> Tuple[Tuple[float, float], ...]:
        """(u, R) 쌍. u 부터 다음 u 전까지 반폭이 R 이하라는 계단 모양으로 읽는다."""
        return tuple(zip(self.tool_profile_u_m, self.tool_profile_r_m))

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
    """WeldConfig 덮어쓰기에서 온 값만 따로 본다. 모르는 이름도 거절한다. 문제 목록('이름 = 값: 이유').

    속도 하한(weld_speed_min_mps)과의 비교는 yaml 값이 있어야 하므로 check() 가 한다.
    """
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
        if spec.kind == DOUBLE:
            clean[spec.name] = float(value)
        elif spec.kind == DOUBLE_ARRAY:
            clean[spec.name] = tuple(float(v) for v in value)
        else:
            clean[spec.name] = value

    low = clean.get('weld_speed_min_mps')
    if low is not None:
        for name in SPEED_NAMES:
            if name in clean and clean[name] < low:
                invalid.append(f'{name} = {clean.pop(name)!r}: weld_speed_min_mps({low!r}) 보다 작다')
    u, r = clean.get('tool_profile_u_m'), clean.get('tool_profile_r_m')
    if u is not None and r is not None and len(u) != len(r):
        invalid.append(f'tool_profile_u_m({len(u)} 개) · tool_profile_r_m({len(r)} 개): 길이가 같아야 한다')

    if missing or invalid:
        return ParamCheck(None, tuple(missing), tuple(invalid))
    return ParamCheck(WeldParams(**clean), (), ())
