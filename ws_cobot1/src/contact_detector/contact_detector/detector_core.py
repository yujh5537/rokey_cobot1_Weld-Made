"""접촉 판정 로직. rclpy 를 import 하지 않는다 (ROS 없이 pytest · 오프라인 분석에서 같은 코드를 쓴다).

판정 흐름 (BRD 4.1.1 · 4.1.3 · 4.1.4, ros-interfaces.md 3.3):
  1. tare: 무접촉 · 정지 상태의 외력 평균을 기준값 F0 로 저장한다 (TareAccumulator)
  2. 접촉 발생(CONTACT): OP_DESCEND 중 |F - F0| 가 임계를 넘는 샘플이 연속 N 회면 확정한다
  3. 과대 외력(OVER_FORCE): 모든 동작에서 원시 |F| 로 판정한다. 영점에 의존하지 않는다
  4. 접촉 소실(EDGE): OP_SLIDE 중 누르는 힘이 확인된 뒤, TCP z 가 최근 구간의 추세선보다
     edge_drop_m 넘게 내려간 샘플이 연속 N 회면 확정한다 (BRD 4.1.2 의 주 신호)

EDGE 를 "밀기 시작 z 대비 누적 하강량"으로 재지 않는 이유 — 모서리가 아닌데도 z 가 내려가는 경우가 셋 있다:
  - SLIDE 는 접촉면 위 틈(recontact_margin_m)에서 시작해 목표 힘이 그 틈을 메운다 (계약 7.3)
  - 윗면이 기울어 있으면 미는 동안 z 가 단조로 내려간다 (0.87° 면 80 mm 에 1.2 mm, PR #75 리뷰)
  - 탐침이 홀더 안으로 서서히 밀려 들어가면 같은 힘을 유지하려고 로봇이 그만큼 더 내려간다 (PR #80)
그래서 (a) "누르고 있다"가 확인된 뒤부터만 판정하고,
(b) 기준을 최근 edge_trend_window_s 구간의 z 직선 맞춤으로 둔다. 천천히 내려가는 것은 추세에 흡수된다.

하강 기준과 밀기 기준을 나눈다 (#109, 2026-09-21 실기):
  외력 추정값은 마지막 이동 방향 · 자세에 따라 2~3 N 치우친다(실기 기록 1-1 · 5-2 · 5-11). 정지 상태에서 잡은
  F0 로 하강하면 허공에서 거짓 CONTACT 가 나고(큐브 45 mm 위), 하강용 F0 를 옆으로 미는 동안 쓰면 닿기 전에도
  |F - F0| 가 수 N 이 된다(+x 밀기 중 허공에서도 Fx -5 N).
  - 하강(CONTACT): DescendTareConfig 가 있으면 DESCEND 가 시작되고 delay_s 뒤부터 duration_s 동안 **이동 중
    F0 를 자동으로 다시 잡는다.** 그동안 CONTACT 는 보류한다(과대 외력은 원시 |F| 라 그대로 감시한다).
    잡지 못하면 /contact/tare 의 F0 로 판정한다(이전 동작).
  - 밀기(EDGE 판정 켜기): EdgeConfig 의 arm_still_* 가 있으면 |F - F0| 대신 **z 가 멈췄고(틈을 다 메움) x · y 는
    움직이는 중**일 때 켠다. F0 에 기대지 않는다. x · y 조건이 없으면 힘 제어를 켜는 동안(팁이 아직 떠 있고
    z 도 멈춰 있다) 너무 일찍 켜진다.
한 번에 툭 내려앉는 것(모서리, 그리고 탐침이 갑자기 미끄러지는 것)만 남는다. 뒤의 것은 소프트웨어로 가를 수 없다.
외력 감소(보조 신호)는 쓰지 않는다.

단위: m · N · s. 수치(임계 · 횟수)는 전부 DetectorConfig 로 받는다. 이 파일에 기본값을 두지 않는다.
"""
import math
from dataclasses import dataclass
from collections import deque
from typing import Deque, List, Optional, Tuple

# RobotSample.OP_* (ros-interfaces.md 3.1). 번호는 계약이다
OP_NONE = 0
OP_MOVE_TO = 1
OP_DESCEND = 2
OP_SLIDE = 3
OP_HOME = 4

# ContactEvent.TYPE_* (ros-interfaces.md 3.3)
TYPE_CONTACT = 0
TYPE_EDGE = 1
TYPE_OVER_FORCE = 2

Vector3 = Tuple[float, float, float]


def norm(v: Vector3) -> float:
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


@dataclass(frozen=True)
class Sample:
    """RobotSample 에서 판정에 쓰는 부분. TCP 와 힘의 취득 시각은 따로 보존한다."""

    sample_id: int
    pose_stamp: float        # s. get_current_posx 응답 시각
    force_stamp: float       # s. get_tool_force 응답 시각
    position: Vector3        # m. TCP = 팁 최하단점
    force: Vector3           # N. 원시 외력 (F0 를 빼지 않은 값)
    valid: bool = True
    motion_id: int = 0
    operation: int = OP_NONE


@dataclass(frozen=True)
class DetectorConfig:
    contact_threshold_n: float    # 접촉 임계 |F - F0|
    debounce_n: int               # CONTACT 를 확정하는 연속 횟수
    over_force_n: float           # 과대 외력 임계 (원시 |F|)
    over_force_debounce_n: int    # OVER_FORCE 를 확정하는 연속 횟수

    def __post_init__(self):
        if not (self.contact_threshold_n > 0 and self.over_force_n > 0):
            raise ValueError('contact_threshold_n, over_force_n 은 0 보다 커야 한다')
        if self.debounce_n < 1 or self.over_force_debounce_n < 1:
            raise ValueError('debounce_n, over_force_debounce_n 은 1 이상이어야 한다')


@dataclass(frozen=True)
class EdgeConfig:
    edge_drop_m: float              # 추세선 대비 이만큼 넘게 내려가면 접촉 소실 조건 성립
    debounce_n: int                 # EDGE 를 확정하는 연속 횟수. 누름 확인에도 같은 횟수를 쓴다
    arm_force_n: float              # |F - F0| 가 이 값을 넘으면 "누르고 있다"로 본다. 그 뒤부터 EDGE 를 판정한다
    trend_window_s: float           # 추세선을 맞추는 최근 구간의 길이
    trend_min_samples: int          # 구간 안의 샘플이 이보다 적으면 판정하지 않는다
    max_gap_s: float                # 샘플이 이보다 오래 끊기면 추세선을 버리고 다시 쌓는다
    # z 로 판정 켜기 (#109). 셋 다 있으면 arm_force_n 대신 쓴다. 최근 arm_still_window_s 동안
    # z 가 arm_still_m 안에 머물고 x · y 가 arm_travel_m 넘게 움직였으면 "누르고 있다"로 본다
    arm_still_window_s: Optional[float] = None
    arm_still_m: Optional[float] = None
    arm_travel_m: Optional[float] = None

    def __post_init__(self):
        if not (self.edge_drop_m > 0 and self.arm_force_n > 0 and self.trend_window_s > 0
                and self.max_gap_s > 0):
            raise ValueError('edge_drop_m, arm_force_n, trend_window_s, max_gap_s 는 0 보다 커야 한다')
        if self.debounce_n < 1 or self.trend_min_samples < 2:
            raise ValueError('debounce_n 은 1 이상, trend_min_samples 는 2 이상이어야 한다')
        still = (self.arm_still_window_s, self.arm_still_m, self.arm_travel_m)
        if any(v is not None for v in still):
            if not all(v is not None and math.isfinite(v) and v > 0 for v in still):
                raise ValueError('arm_still_window_s, arm_still_m, arm_travel_m 은 셋 다 0 보다 커야 한다')

    @property
    def arm_by_z(self) -> bool:
        return self.arm_still_window_s is not None


@dataclass(frozen=True)
class Detection:
    """확정된 판정 1건.

    first_sample 은 조건이 처음 성립한 샘플(연속 구간의 첫 샘플)이다. 측정 좌표의 출처로 쓴다:
    ContactEvent 의 pose · pose_stamp · wrench · force_stamp · sample_id 에 싣는다.
    sample 은 판정을 확정한 샘플(연속 N 번째)이다. detect_stamp 와 force_delta_n(검출 하중, BRD 9장
    '접촉으로 확정된 순간의 외력')의 출처다.
    확정 샘플의 좌표를 쓰면 디바운스 동안 더 움직인 만큼(50 Hz · 5 mm/s · N=3 이면 0.2 mm) 측정값이 밀린다.
    이 배정은 계약 3.3 의 '판정 샘플' 정의가 확정될 때까지 초안이다.
    """

    type: int
    sample: Sample
    first_sample: Sample
    force_delta_n: float          # 확정 샘플의 값. CONTACT · EDGE: |F - F0|, OVER_FORCE: 원시 |F|
    debounce_count: int
    z_drop_m: Optional[float] = None   # EDGE 만. first_sample 에서 추세선보다 내려간 양 (편향 보정의 δ)

    @property
    def debounce_delay_s(self) -> float:
        return self.sample.force_stamp - self.first_sample.force_stamp


class _Run:
    """조건이 연속으로 참인 구간을 센다."""

    def __init__(self):
        self.count = 0
        self.first: Optional[Sample] = None

    def update(self, condition: bool, sample: Sample) -> int:
        if not condition:
            self.reset()
            return 0
        if self.count == 0:
            self.first = sample
        self.count += 1
        return self.count

    def reset(self):
        self.count = 0
        self.first = None


class _Trend:
    """최근 구간의 (시각, z) 를 직선으로 맞춰 지금 시각의 z 를 예측한다."""

    def __init__(self, window_s: float, min_samples: int):
        self.window_s = window_s
        self.min_samples = min_samples
        self.points: Deque[Tuple[float, float]] = deque()

    def add(self, t: float, z: float):
        self.points.append((t, z))

    def clear(self):
        self.points.clear()

    def predict(self, t: float) -> Optional[float]:
        # 구간은 지금 시각이 아니라 마지막으로 들어온 점에서 거꾸로 잰다. 점이 들어오지 않는 동안(기준선을 얼린 동안,
        # 최근 샘플을 기다리게 하는 동안)에는 구간이 줄지 않는다. 지금 시각에서 재면 debounce_n 을 키울수록
        # 구간 안의 점이 모자라 EDGE 가 조용히 나오지 않게 된다
        while self.points and self.points[0][0] < self.points[-1][0] - self.window_s:
            self.points.popleft()
        n = len(self.points)
        if n < self.min_samples:
            return None
        mean_t = sum(p[0] for p in self.points) / n
        mean_z = sum(p[1] for p in self.points) / n
        var_t = sum((p[0] - mean_t) ** 2 for p in self.points)
        if var_t <= 0.0:
            return None
        slope = sum((p[0] - mean_t) * (p[1] - mean_z) for p in self.points) / var_t
        return mean_z + slope * (t - mean_t)


class ContactDetector:
    """샘플을 하나씩 받아 확정된 판정을 돌려준다. 상태는 이 객체 안에만 있다.

    edge_config 가 None 이면 EDGE 를 판정하지 않는다.
    """

    def __init__(self, config: DetectorConfig, edge_config: Optional[EdgeConfig] = None,
                 descend_tare: Optional['DescendTareConfig'] = None):
        self.config = config
        self.edge_config = edge_config
        self.descend_tare = descend_tare
        self.baseline: Optional[Vector3] = None      # /contact/tare 의 F0. None = tare 전
        self.descend_baseline: Optional[Vector3] = None   # 이번 하강에서 자동으로 잡은 F0 (#109)
        self.descend_tare_result: Optional['TareResult'] = None   # 방금 끝난 자동 영점. 노드가 읽고 지운다
        self._dt_state = 'idle'                      # idle · waiting · collecting · done · failed
        self._dt_start: Optional[float] = None
        self._dt_acc: Optional['TareAccumulator'] = None
        self.descend_tare_attempt = 0                 # 이번 하강에서 몇 번째 구간을 모으는 중인가 (0 = 아직)
        self._prev_operation = OP_NONE
        self._arm_points: Deque[Tuple[float, Vector3]] = deque()   # z 로 켜기: 최근 (시각, 위치)
        self._contact_run = _Run()
        self._over_run = _Run()
        self._motion_id = 0
        self._contact_latched = False                # 한 motion_id 에서 CONTACT 는 1 회만
        self._over_latched = False                   # 과대 외력 구간마다 1 회만
        self._arm_run = _Run()
        self._edge_run = _Run()
        self._edge_armed = False                     # 이 동작에서 누름이 확인됐다
        self._edge_latched = False                   # 한 motion_id 에서 EDGE 는 1 회만
        self._edge_first_drop: Optional[float] = None
        self._last_edge_t: Optional[float] = None
        self._pending: Deque[Tuple[float, float]] = deque()   # 아직 추세선에 넣지 않은 최근 샘플
        self._trend = (_Trend(edge_config.trend_window_s, edge_config.trend_min_samples)
                       if edge_config else None)
        self.trend_gap = False                       # 직전 update 에서 공백 때문에 추세선을 버렸다

    @property
    def edge_armed(self) -> bool:
        return self._edge_armed

    def _reset_edge(self):
        self._arm_run.reset()
        self._arm_points.clear()
        self._edge_run.reset()
        self._edge_armed = False
        self._edge_latched = False
        self._edge_first_drop = None
        self._last_edge_t = None
        self._pending.clear()
        if self._trend:
            self._trend.clear()

    def set_baseline(self, baseline: Optional[Vector3]):
        self.baseline = baseline
        self._contact_run.reset()

    @property
    def descend_tare_state(self) -> str:
        return self._dt_state

    @property
    def active_baseline(self) -> Optional[Vector3]:
        """지금 판정 · 보고에 쓰는 F0 (노드의 경고 · 로그용)."""
        return self._judge_baseline()

    @property
    def contact_withheld(self) -> bool:
        """이동 중 F0 를 모으는 중이라 CONTACT 를 보류하고 있다."""
        return self.descend_tare is not None and self._dt_state in ('waiting', 'collecting')

    def _judge_baseline(self) -> Optional[Vector3]:
        """판정 · 보고에 쓰는 F0. 이번 하강에서 자동으로 잡았으면 그것, 아니면 /contact/tare 의 값."""
        if self.descend_tare is not None and self._dt_state == 'done':
            return self.descend_baseline
        return self.baseline

    def _update_descend_tare(self, sample: Sample, motion_changed: bool):
        cfg = self.descend_tare
        starting = sample.operation == OP_DESCEND and (
            motion_changed or self._prev_operation != OP_DESCEND)
        self._prev_operation = sample.operation
        if cfg is None or sample.operation != OP_DESCEND:
            return
        t = sample.force_stamp
        if starting:
            self._dt_state, self._dt_start = 'waiting', t
            self._dt_acc = TareAccumulator(cfg.tare)
            self.descend_baseline = None
            self.descend_tare_attempt = 0
        if self._dt_state not in ('waiting', 'collecting'):
            return
        elapsed = t - self._dt_start
        if self._dt_state == 'waiting' and elapsed >= cfg.delay_s:
            self._dt_state = 'collecting'
            self.descend_tare_attempt = 1
        if self._dt_state == 'collecting':
            self._dt_acc.add(sample)
            if elapsed >= cfg.delay_s + self.descend_tare_attempt * cfg.duration_s:
                result = self._dt_acc.result()
                self.descend_tare_result = result
                if result.success:
                    self.descend_baseline, self._dt_state = result.baseline, 'done'
                elif self.descend_tare_attempt < cfg.max_attempts:
                    # 정지 F0 로 돌아가지 않고 다음 구간을 다시 모은다. 9/21 실기에서 한 번 실패(모으는 동안 Fz 가
                    # 2.6 → 1.5 N 으로 흘렀다)한 하강이 정지 F0 로 판정해 윗면 3.8 mm 위에서 거짓 접촉을 냈다.
                    # 같은 하강의 다음 구간은 성공했다
                    self.descend_tare_attempt += 1
                    self._dt_acc = TareAccumulator(cfg.tare)
                else:
                    # 모두 실패하면 /contact/tare 의 F0 로 판정한다. 판정하지 않으면 과대 외력까지 눌러 버린다
                    self._dt_state = 'failed'
                self._contact_run.reset()

    def update(self, sample: Sample) -> List[Detection]:
        # 무효 샘플은 정보가 없다. 세지도 않고 연속 구간을 끊지도 않는다
        if not sample.valid:
            return []

        motion_changed = sample.motion_id != self._motion_id
        if motion_changed:
            self._motion_id = sample.motion_id
            self._contact_run.reset()
            self._contact_latched = False
            self._reset_edge()
        self._update_descend_tare(sample, motion_changed)

        detections = []
        self.trend_gap = False
        over = self._update_over_force(sample)
        if over:
            detections.append(over)
        contact = self._update_contact(sample)
        if contact:
            detections.append(contact)
        edge = self._update_edge(sample)
        if edge:
            detections.append(edge)
        return detections

    def _update_over_force(self, sample: Sample) -> Optional[Detection]:
        magnitude = norm(sample.force)
        count = self._over_run.update(magnitude > self.config.over_force_n, sample)
        if count == 0:
            self._over_latched = False
            return None
        if self._over_latched or count < self.config.over_force_debounce_n:
            return None
        self._over_latched = True
        return Detection(TYPE_OVER_FORCE, sample, self._over_run.first, magnitude, count)

    def _update_contact(self, sample: Sample) -> Optional[Detection]:
        if sample.operation != OP_DESCEND:
            self._contact_run.reset()
            return None
        if self.descend_tare is not None and self._dt_state in ('waiting', 'collecting'):
            # 이동 중 F0 를 잡는 동안은 판정을 보류한다. 정지 F0 로 판정하면 이 구간에서 거짓 접촉이 날 수 있다.
            # 이 구간(delay_s + duration_s)에 하강하는 거리보다 부재 윗면이 충분히 아래에 있어야 한다(계약 3.3)
            self._contact_run.reset()
            return None
        if self._judge_baseline() is None:
            self._contact_run.reset()
            return None
        delta = self.force_delta(sample)
        count = self._contact_run.update(delta > self.config.contact_threshold_n, sample)
        if count == 0 and self._motion_id == 0:
            # motion_id 0 = 없음. 동작의 경계를 알 수 없으므로 외력이 임계 아래로 내려오면 다시 판정한다.
            # 이렇게 하지 않으면 motion_id 가 0 으로만 오는 동안 첫 접촉 뒤로 이벤트가 영영 나가지 않는다
            self._contact_latched = False
        if self._contact_latched or count < self.config.debounce_n:
            return None
        self._contact_latched = True
        return Detection(TYPE_CONTACT, sample, self._contact_run.first, delta, count)

    def _update_edge(self, sample: Sample) -> Optional[Detection]:
        cfg = self.edge_config
        if cfg is None:
            return None
        if sample.operation != OP_SLIDE or self._judge_baseline() is None:
            self._reset_edge()
            return None

        t, z = sample.pose_stamp, sample.position[2]
        # 공백이면 추세선 · 대기 버퍼 · 연속 횟수를 즉시 버린다. 대기 버퍼를 지난 뒤에 알아차리면
        # 그사이 공백 이전의 추세로 판정하게 되고, 공백 동안 일어난 하강을 한 번에 EDGE 로 확정한다
        # (Virtual 실측 342 ms 공백, 2026-09-20). 판정이 몇 샘플 늦어지는 대신 틀린 좌표를 내지 않는다
        if self._last_edge_t is not None and t - self._last_edge_t > cfg.max_gap_s:
            self._trend.clear()
            self._pending.clear()
            self._edge_run.reset()
            self._arm_points.clear()
            self.trend_gap = True
        self._last_edge_t = t

        if not self._edge_armed:
            # 틈을 메우며 내려가는 동안에는 판정하지 않는다. 누르는 것이 확인된 뒤의 z 만 기준선에 쓴다
            if self._pressing(sample, cfg):
                self._edge_armed = True
                self._pending.append((t, z))
            return None

        predicted = self._trend.predict(t)
        drop = None if predicted is None else predicted - z
        count = self._edge_run.update(drop is not None and drop > cfg.edge_drop_m, sample)
        if count == 0:
            # 최근 debounce_n 개는 추세선에 넣지 않고 기다리게 한다. 임계에 못 미친 채 내려앉기 시작한 샘플이
            # 기준선을 끌고 내려가면 하강량이 작게 나온다. 조건이 성립한 동안에는 아무것도 넣지 않는다(기준선을 얼린다)
            self._pending.append((t, z))
            while len(self._pending) > cfg.debounce_n:
                self._trend.add(*self._pending.popleft())
            if self._motion_id == 0:
                self._edge_latched = False           # CONTACT 와 같은 이유 (motion_id 0 = 동작 경계를 모른다)
        elif count == 1:
            self._edge_first_drop = drop
        if self._edge_latched or count < cfg.debounce_n:
            return None
        self._edge_latched = True
        return Detection(TYPE_EDGE, sample, self._edge_run.first, self.force_delta(sample), count,
                         z_drop_m=self._edge_first_drop)

    def _pressing(self, sample: Sample, cfg: EdgeConfig) -> bool:
        """EDGE 판정을 켤지. 힘(|F - F0|) 또는 z(멈춤 + x · y 이동)로 본다."""
        if not cfg.arm_by_z:
            return self._arm_run.update(self.force_delta(sample) > cfg.arm_force_n, sample) >= cfg.debounce_n
        # z 로 켜기(#109): 하강용 F0 를 밀기에 쓰면 옆 이동 이력 때문에 닿기 전에도 |F - F0| 가 수 N 이라 힘 조건이
        # 곧바로 켜진다. 틈을 다 메우면 z 가 멈추므로 그것을 본다. 힘 제어를 켜는 동안에는 팁이 떠 있는데 z 도
        # 멈춰 있어서, x · y 가 실제로 움직이고 있는지도 같이 본다
        t = sample.pose_stamp
        self._arm_points.append((t, sample.position))
        while self._arm_points and self._arm_points[0][0] < t - cfg.arm_still_window_s:
            self._arm_points.popleft()
        first_t, first_p = self._arm_points[0]
        if len(self._arm_points) < cfg.debounce_n or t - first_t < 0.75 * cfg.arm_still_window_s:
            return False
        zs = [p[2] for _, p in self._arm_points]
        travel = math.hypot(sample.position[0] - first_p[0], sample.position[1] - first_p[1])
        return max(zs) - min(zs) <= cfg.arm_still_m and travel >= cfg.arm_travel_m

    def force_delta(self, sample: Sample) -> float:
        """|F - F0|. 성분별로 뺀 뒤 크기를 구한다 (크기끼리 빼지 않는다). F0 는 _judge_baseline()."""
        f, b = sample.force, self._judge_baseline()
        return norm((f[0] - b[0], f[1] - b[1], f[2] - b[2]))


# ---------------------------------------------------------------- tare

# 실패 사유. 노드가 ReasonCode 로 옮긴다 (ros-interfaces.md 4.2)
TARE_NO_SAMPLE = 'NO_SAMPLE'
TARE_TOO_FEW = 'TARE_TIMEOUT'
TARE_UNSTABLE = 'TARE_UNSTABLE'
TARE_TOOL_REG_SUSPECT = 'TOOL_REG_SUSPECT'


@dataclass(frozen=True)
class TareConfig:
    min_samples: int              # 이보다 적으면 실패
    max_std_n: float              # 구간 중 외력 흔들림(std_vector_n)의 한계. 넘으면 정지 · 무접촉이 아니었다고 본다
    max_force_n: float            # 무접촉 외력 크기 |F0| 의 한계. 넘으면 툴 무게 등록을 의심한다 (BRD 4.1.5)


@dataclass(frozen=True)
class DescendTareConfig:
    """하강 중 자동 영점 (#109). 하강과 같은 운동 상태 · 같은 자세 근처에서 F0 를 잡는다(실기 기록 5-11)."""

    delay_s: float                # DESCEND 가 시작되고 이만큼 지난 뒤 모으기 시작한다(출발 약 4 s 뒤 치우침이 계단식으로 생긴다)
    duration_s: float             # 모으는 길이
    tare: TareConfig              # 샘플 수 · 불안정 · 툴 등록 판정은 /contact/tare 와 같은 기준을 쓴다
    max_attempts: int = 1         # 실패하면 바로 다음 duration_s 구간으로 다시 모은다. 이 횟수까지. CONTACT 보류는 그만큼 길어진다

    def __post_init__(self):
        if not (math.isfinite(self.delay_s) and self.delay_s >= 0
                and math.isfinite(self.duration_s) and self.duration_s > 0):
            raise ValueError('delay_s 는 0 이상, duration_s 는 0 보다 커야 한다')
        if self.max_attempts < 1:
            raise ValueError('max_attempts 는 1 이상이어야 한다')

    @property
    def withheld_s(self) -> float:
        """CONTACT 를 보류할 수 있는 가장 긴 시간. 이 동안 내려가는 거리보다 부재 윗면이 아래에 있어야 한다."""
        return self.delay_s + self.max_attempts * self.duration_s


@dataclass(frozen=True)
class TareResult:
    success: bool
    error: str                    # '' = 성공
    baseline: Optional[Vector3]   # 실패해도 계산은 돌려준다. 채택 여부는 success 로만 판단한다
    baseline_norm_n: Optional[float]
    std_norm_n: Optional[float]   # 외력 크기 |F| 의 표준편차. TareForce 응답 필드(보고용)
    std_vector_n: Optional[float] # 기준값에서 벗어난 거리 |F - F0| 의 RMS. 불안정 판정은 이 값으로 한다
    sample_count: int


class TareAccumulator:
    """무접촉 · 정지 구간의 샘플을 모아 기준값 F0 를 계산한다."""

    def __init__(self, config: TareConfig):
        self.config = config
        self._forces: List[Vector3] = []

    def add(self, sample: Sample):
        if sample.valid:
            self._forces.append(sample.force)

    def result(self) -> TareResult:
        n = len(self._forces)
        if n == 0:
            return TareResult(False, TARE_NO_SAMPLE, None, None, None, None, 0)

        baseline = tuple(sum(f[i] for f in self._forces) / n for i in range(3))
        norms = [norm(f) for f in self._forces]
        mean_norm = sum(norms) / n
        std_norm = math.sqrt(sum((v - mean_norm) ** 2 for v in norms) / n)
        # 크기의 표준편차만 보면 크기가 같은 채 방향이 바뀌는 흔들림(예: Fz -1.5 → +1.5 N)을 놓친다
        std_vector = math.sqrt(sum(
            sum((f[i] - baseline[i]) ** 2 for i in range(3)) for f in self._forces) / n)
        baseline_norm = norm(baseline)

        if n < self.config.min_samples:
            error = TARE_TOO_FEW
        elif std_vector > self.config.max_std_n:
            error = TARE_UNSTABLE
        elif baseline_norm > self.config.max_force_n:
            error = TARE_TOOL_REG_SUSPECT
        else:
            error = ''
        return TareResult(error == '', error, baseline, baseline_norm, std_norm, std_vector, n)
