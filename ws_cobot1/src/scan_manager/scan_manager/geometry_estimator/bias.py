"""판정 좌표의 편향 보정 (BRD 1.4 · 4.2.4). rclpy 를 import 하지 않는다.

모서리(EDGE) — 팁이 윗면을 누른 채 밀려가다 모서리에서 내려앉는다.
  반지름 r 의 구형 팁이 반지름 R 로 둥글려진 모서리를 타고 넘으면, 구 중심은 둥근 부분의 중심을 축으로
  반지름 (R + r) 의 호를 그린다. 둥근 부분이 시작되는 곳에서 d 만큼 더 갔을 때의 하강량은

      δ = (R + r) − √((R + r)² − d²)      →      d = √(2(R + r)δ − δ²)

  공칭 모서리(둥글리기 전의 모서리 = 외곽 엣지)는 둥근 부분의 시작점에서 R 만큼 바깥이므로,
  하강량 δ 로 판정한 좌표는 공칭 모서리를 (d − R) 만큼 지나쳐 있다. 여기에 판정이 늦은 만큼 더 간
  거리(속도 x 지연)와 실측 보정 상수를 더한 값을 진행 방향 반대로 뺀다.

      보정량 = d − R + v·t + offset

  R = 0 이면 BRD 1.4 의 식 √(2rδ − δ²) + v·t 와 같다.
  δ ≥ R + r 이면 구가 모서리를 완전히 벗어나 옆면을 따라 내려가는 중이다. 그 뒤로는 하강해도
  수평으로 더 나가지 않으므로 d = R + r 로 고정한다(보정량의 기하 항 = r).
  식을 그대로 쓰면 δ 가 (R + r) ~ 2(R + r) 에서는 d 가 도로 작아지고, 그보다 크면 제곱근 안이 음수가 된다.
  R + r < δ 인 구간에서 실제로 더 나간 거리는 속도와 내려앉는 빠르기에 달려 있어 식으로 알 수 없다.
  그 몫은 offset(기준 블록으로 실측, T30)에 들어간다.
  보정량은 음수일 수 있다(R 이 크고 δ 가 작으면 판정 좌표가 공칭 모서리 안쪽이다).
  모따기(C)는 다루지 않는다.

  δ 를 모르면(ContactEvent.z_drop_valid=false → None, 또는 NaN) d = 0 으로 둔다(#146).
  힘 꺾임 EDGE(#128)는 추세선 없이도 확정되는데, 그때 δ 가 없다. d 는 0 ~ (R + r) 이므로 이 가정의 오차는
  방향당 최대 (R + r)이다. 힘 꺾임은 구가 모서리를 막 넘기 시작할 때 나므로 d ≈ 0 이 실제에 가깝다.
  δ 자체를 0 으로 저장하는 것이 아니다. 음수 · inf 는 미측정이 아니라 잘못된 값이라 그대로 거절한다.

윗면(CONTACT) — 팁이 내려가다 닿는다. 판정이 늦은 만큼(속도 x 지연) 더 내려간 좌표가 기록되므로 그만큼 올린다.

단위: m · s · m/s. 수치는 전부 인자로 받는다. 이 파일에 기본값을 두지 않는다.
"""
import math
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class BiasParams:
    tip_radius_m: float           # r. 팁(구) 반지름
    detect_latency_s: float       # t. 실제 접촉 · 소실에서 판정 샘플의 좌표까지의 지연
    edge_round_radius_m: float    # R. 부재 모서리의 둥글림 반지름. 예리하면 0
    edge_bias_offset_m: float     # 기준 블록으로 실측한 나머지 편향(진행 방향 +). 없으면 0

    def __post_init__(self):
        for name in ('tip_radius_m', 'detect_latency_s', 'edge_round_radius_m'):
            _check(getattr(self, name), name, minimum=0.0)
        _check(self.edge_bias_offset_m, 'edge_bias_offset_m')


def _check(value, name, minimum=None):
    if value is None or isinstance(value, bool) or not math.isfinite(value):
        raise ValueError(f'{name} = {value!r}: 유한한 수가 아니다')
    if minimum is not None and value < minimum:
        raise ValueError(f'{name} = {value}: {minimum} 이상이어야 한다')
    return float(value)


def overshoot_m(z_drop_m: float, tip_radius_m: float, edge_round_radius_m: float) -> float:
    """하강량 δ 로 판정했을 때 구 중심이 둥근 부분의 시작점을 지나친 수평 거리 d."""
    delta = _check(z_drop_m, 'z_drop_m', minimum=0.0)
    reach = tip_radius_m + edge_round_radius_m
    if delta >= reach:
        return reach
    return math.sqrt(2.0 * reach * delta - delta * delta)


def _unmeasured(value) -> bool:
    """None 또는 NaN. 음수 · inf · bool 은 미측정이 아니라 잘못된 값이다(_check 가 거절한다)."""
    return value is None or (isinstance(value, float) and math.isnan(value))


def edge_correction_m(z_drop_m: Optional[float], slide_speed_mps: float, params: BiasParams) -> float:
    """모서리 판정 좌표에서 진행 방향 반대로 뺄 거리. 음수일 수 있다. δ 를 모르면 d = 0 이다(모듈 설명)."""
    speed = _check(slide_speed_mps, 'slide_speed_mps', minimum=0.0)
    if _unmeasured(z_drop_m):
        d = 0.0
    else:
        d = overshoot_m(z_drop_m, params.tip_radius_m, params.edge_round_radius_m)
    return d - params.edge_round_radius_m + speed * params.detect_latency_s + params.edge_bias_offset_m


def top_correction_m(descend_speed_mps: float, params: BiasParams) -> float:
    """윗면 판정 좌표의 z 에 더할 거리(0 이상)."""
    return _check(descend_speed_mps, 'descend_speed_mps', minimum=0.0) * params.detect_latency_s
