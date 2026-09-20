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
그래서 (a) |F - F0| 가 edge_arm_force_n 을 넘어 "누르고 있다"가 확인된 뒤부터만 판정하고,
(b) 기준을 최근 edge_trend_window_s 구간의 z 직선 맞춤으로 둔다. 천천히 내려가는 것은 추세에 흡수된다.
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

    def __post_init__(self):
        if not (self.edge_drop_m > 0 and self.arm_force_n > 0 and self.trend_window_s > 0):
            raise ValueError('edge_drop_m, arm_force_n, trend_window_s 는 0 보다 커야 한다')
        if self.debounce_n < 1 or self.trend_min_samples < 2:
            raise ValueError('debounce_n 은 1 이상, trend_min_samples 는 2 이상이어야 한다')


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

    def __init__(self, config: DetectorConfig, edge_config: Optional[EdgeConfig] = None):
        self.config = config
        self.edge_config = edge_config
        self.baseline: Optional[Vector3] = None      # F0. None = tare 전
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
        self._pending: Deque[Tuple[float, float]] = deque()   # 아직 추세선에 넣지 않은 최근 샘플
        self._trend = (_Trend(edge_config.trend_window_s, edge_config.trend_min_samples)
                       if edge_config else None)

    @property
    def edge_armed(self) -> bool:
        return self._edge_armed

    def _reset_edge(self):
        self._arm_run.reset()
        self._edge_run.reset()
        self._edge_armed = False
        self._edge_latched = False
        self._edge_first_drop = None
        self._pending.clear()
        if self._trend:
            self._trend.clear()

    def set_baseline(self, baseline: Optional[Vector3]):
        self.baseline = baseline
        self._contact_run.reset()

    def update(self, sample: Sample) -> List[Detection]:
        # 무효 샘플은 정보가 없다. 세지도 않고 연속 구간을 끊지도 않는다
        if not sample.valid:
            return []

        if sample.motion_id != self._motion_id:
            self._motion_id = sample.motion_id
            self._contact_run.reset()
            self._contact_latched = False
            self._reset_edge()

        detections = []
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
        if sample.operation != OP_DESCEND or self.baseline is None:
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
        if sample.operation != OP_SLIDE or self.baseline is None:
            self._reset_edge()
            return None

        t, z = sample.pose_stamp, sample.position[2]
        if not self._edge_armed:
            # 틈을 메우며 내려가는 동안에는 판정하지 않는다. 누르는 힘이 확인된 뒤의 z 만 기준선에 쓴다
            if self._arm_run.update(self.force_delta(sample) > cfg.arm_force_n, sample) >= cfg.debounce_n:
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

    def force_delta(self, sample: Sample) -> float:
        """|F - F0|. 성분별로 뺀 뒤 크기를 구한다 (크기끼리 빼지 않는다)."""
        f, b = sample.force, self.baseline
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
