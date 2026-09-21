"""SetConfig 파라미터 전파(계약 2.4 P01~P03)의 순수 계산부. rclpy 없이 전수 시험한다.

scan_manager 는 자기 몫 6개(모션)만 직접 쓰고, 나머지 6개는 **이름으로** 다른 노드에 전파한다
(계약 6.4). 여기서는 "어느 노드에 어떤 이름으로 무엇을 보낼지"와 "돌아온 결과를 어떻게 응답으로
만들지"만 정한다. 서비스 호출 자체는 scan_manager.py 가 한다.

원칙
- **감시 쪽을 먼저 바꾼다**(P03 → P02 → P01). 도중에 실패해도 safety_monitor 는 늘 요청한 값에
  가 있고, 어긋남은 "1차 감시가 옛 값에 남았다"로만 남는다. 반대 순서면 2차가 옛 값에 남아
  관제자가 조인 줄 아는 임계가 감시에는 안 들어간 조합이 생긴다.
- **되돌리지 않는다.** 되돌리기도 실패할 수 있고, 실패한 되돌리기는 더 알기 어려운 상태를 만든다.
  대신 무엇이 어떻게 됐는지 detail 에 전부 적는다.
- `over_force_n` · `drop_limit_m` 은 두 노드가 **같은 값**이어야 한다(계약 7.2). 어긋난 채로
  남으면 다음 START 를 거절한다. 값 비교는 **정확히 같은지**로 본다 — 같은 요청을 두 노드에
  똑같이 보내므로 근사 비교가 필요하지 않고, 근사로 보면 진짜 어긋남을 덮는다.
- 모르는 값을 0 으로 적지 않는다(CLAUDE.md 규칙 4). 모르면 None 이다.
"""

from dataclasses import dataclass
from typing import Mapping, Optional, Tuple

ROBOT_MANAGER = 'robot_manager'
CONTACT_DETECTOR = 'contact_detector'
SAFETY_MONITOR = 'safety_monitor'

# 정수형으로 보내야 하는 항목. contact_detector 가 debounce_n 을 INTEGER 로 선언한다.
INTEGER_CONFIG = frozenset({'debounce_n'})

# 전파 계획. (노드, ((ScanConfig 이름, 그 노드의 파라미터 이름), ...)) 을 **보낼 순서대로** 둔다.
# 계약 2.4 의 P03 · P02 · P01 과 6.4 의 이름을 그대로 쓴다. 순서를 바꾸면 위 원칙이 깨진다.
TARGETS: Tuple[Tuple[str, Tuple[Tuple[str, str], ...]], ...] = (
    (SAFETY_MONITOR, (
        ('over_force_n', 'over_force_n'),
        ('drop_limit_m', 'drop_limit_m'),
    )),
    (CONTACT_DETECTOR, (
        ('contact_threshold_n', 'contact_threshold_n'),
        ('edge_drop_m', 'edge_drop_m'),
        ('debounce_n', 'debounce_n'),
        ('over_force_n', 'over_force_n'),
    )),
    (ROBOT_MANAGER, (
        ('target_force_n', 'slide_target_force_n'),
        ('drop_limit_m', 'drop_limit_m'),
    )),
)

# 두 노드가 같은 값을 들고 있어야 하는 항목 (계약 7.2). (ScanConfig 이름, ((노드, 파라미터 이름), ...))
PAIRS: Tuple[Tuple[str, Tuple[Tuple[str, str], ...]], ...] = (
    ('over_force_n', ((SAFETY_MONITOR, 'over_force_n'), (CONTACT_DETECTOR, 'over_force_n'))),
    ('drop_limit_m', ((SAFETY_MONITOR, 'drop_limit_m'), (ROBOT_MANAGER, 'drop_limit_m'))),
)

# scan_manager 가 직접 쓰지 않고 전파만 하는 6개 (계약 3.9 의 ScanConfig 중 모션 6개를 뺀 것).
PEER_CONFIG_NAMES: Tuple[str, ...] = tuple(
    dict.fromkeys(name for _node, items in TARGETS for name, _param in items))

# 어느 노드에서 읽은 값을 그 이름의 대표값으로 삼는지. 쌍은 PAIRS 가 따로 본다.
_SINGLE_SOURCE = {
    'contact_threshold_n': (CONTACT_DETECTOR, 'contact_threshold_n'),
    'edge_drop_m': (CONTACT_DETECTOR, 'edge_drop_m'),
    'debounce_n': (CONTACT_DETECTOR, 'debounce_n'),
    'target_force_n': (ROBOT_MANAGER, 'slide_target_force_n'),
}


@dataclass(frozen=True)
class Item:
    """한 노드에 보낼 파라미터 하나."""

    config_name: str     # ScanConfig 의 이름
    param_name: str      # 그 노드에서의 파라미터 이름
    value: object
    integer: bool        # True 면 PARAMETER_INTEGER, 아니면 PARAMETER_DOUBLE


@dataclass(frozen=True)
class NodePlan:
    node: str
    items: Tuple[Item, ...]

    @property
    def names(self) -> Tuple[str, ...]:
        return tuple(item.param_name for item in self.items)


@dataclass(frozen=True)
class NodeResult:
    """한 노드에 대한 전파 결과. ok=False 면 detail 에 사유가 있다."""

    node: str
    ok: bool
    detail: str = ''


@dataclass(frozen=True)
class Outcome:
    success: bool
    detail: str
    failed: Tuple[str, ...]      # 실패한 노드 이름


def plan(values: Mapping[str, object]) -> Tuple[NodePlan, ...]:
    """SetConfig 로 받은 {이름: 값} → 노드별 전파 계획. 보낼 순서대로 돌려준다.

    values 에 없는 이름(= *_set=false)은 보내지 않는다. 값이 None 인 것도 "주지 않음"이다.
    """
    plans = []
    for node, items in TARGETS:
        chosen = tuple(
            Item(name, param, values[name], name in INTEGER_CONFIG)
            for name, param in items
            if values.get(name) is not None)
        if chosen:
            plans.append(NodePlan(node, chosen))
    return tuple(plans)


def summarize(plans, results: Mapping[str, NodeResult], applied_own=()) -> Outcome:
    """노드별 결과 → SetConfig 응답의 success · detail.

    부분 실패에도 성공한 노드를 되돌리지 않는다. 어디가 되고 어디가 안 됐는지 detail 에 남긴다.
    """
    parts = []
    if applied_own:
        parts.append('자기 적용: ' + ', '.join(applied_own))
    failed = []
    for node_plan in plans:
        result = results.get(node_plan.node)
        names = ', '.join(node_plan.names)
        if result is None:
            failed.append(node_plan.node)
            parts.append(f'{node_plan.node}({names}): 결과 없음')
        elif result.ok:
            parts.append(f'{node_plan.node}({names}): 적용')
        else:
            failed.append(node_plan.node)
            parts.append(f'{node_plan.node}({names}): 실패 — {result.detail}')
    if not plans and not applied_own:
        parts.append('바꿀 항목이 없다')
    return Outcome(not failed, ' / '.join(parts), tuple(failed))


def applied_from_readback(readback: Mapping[str, Mapping[str, object]]) -> dict:
    """세 노드에서 읽은 실제 값 → {ScanConfig 이름: 값 | None}.

    readback 은 {노드: {파라미터 이름: 값}} 이다. 읽지 못한 칸은 없거나 None 이다.
    쌍(over_force_n · drop_limit_m)은 **두 노드의 값이 모두 있고 같을 때만** 그 값이다.
    한쪽을 못 읽었거나 서로 다르면 "지금 값이 무엇인지 말할 수 없다" → None (NaN + *_set=false 로 나간다).
    """
    values = {}
    for name, (node, param) in _SINGLE_SOURCE.items():
        values[name] = readback.get(node, {}).get(param)
    for name, holders in PAIRS:
        seen = [readback.get(node, {}).get(param) for node, param in holders]
        values[name] = seen[0] if all(v is not None for v in seen) and _all_same(seen) else None
    return values


def pair_mismatches(readback: Mapping[str, Mapping[str, object]]) -> Tuple[str, ...]:
    """같은 값이어야 하는 쌍이 **실제로 다른** 것만 설명 문자열로 돌려준다 (계약 7.2).

    못 읽은 칸은 어긋남으로 보지 않는다 — 다르다는 것을 본 적이 없기 때문이다. 모른다고 막으면
    노드 하나가 늦게 뜬 것만으로 모든 START 가 막힌다.
    """
    problems = []
    for name, holders in PAIRS:
        seen = [(node, readback.get(node, {}).get(param)) for node, param in holders]
        known = [(node, value) for node, value in seen if value is not None]
        if len(known) < len(holders) or _all_same([value for _node, value in known]):
            continue
        shown = ', '.join(f'{node}={value}' for node, value in known)
        problems.append(f'{name}({shown})')
    return tuple(problems)


def unread_names(readback: Mapping[str, Mapping[str, object]]) -> Tuple[str, ...]:
    """읽지 못해 '<노드>.<파라미터>' 로 남은 칸. WARN 로그에 쓴다."""
    missing = []
    for node, items in TARGETS:
        for _name, param in items:
            if readback.get(node, {}).get(param) is None:
                missing.append(f'{node}.{param}')
    return tuple(missing)


def read_names(node: str) -> Tuple[str, ...]:
    """그 노드에서 읽어야 하는 파라미터 이름."""
    for name, items in TARGETS:
        if name == node:
            return tuple(param for _config, param in items)
    return ()


def _all_same(values) -> bool:
    first = values[0] if values else None
    return all(value == first for value in values)


def mismatch_detail(problems) -> Optional[str]:
    if not problems:
        return None
    return (
        '두 노드가 같은 값이어야 하는 항목이 어긋나 있다(계약 7.2): ' + '; '.join(problems)
        + '. /scan/set_config 로 다시 보내 양쪽을 맞춘 뒤 시작한다')
