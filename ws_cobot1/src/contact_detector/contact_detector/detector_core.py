"""접촉 판정 로직. rclpy 를 import 하지 않는다 (ROS 없이 pytest · 오프라인 분석에서 같은 코드를 쓴다).

판정 흐름 (BRD 4.1.1 · 4.1.3 · 4.1.4, ros-interfaces.md 3.3):
  1. tare: 무접촉 · 정지 상태의 외력 평균을 기준값 F0 로 저장한다 (TareAccumulator)
  2. 접촉 발생(CONTACT): OP_DESCEND 중 |F - F0| 가 임계를 넘는 샘플이 연속 N 회면 확정한다
  3. 과대 외력(OVER_FORCE): 모든 동작에서 원시 |F| 로 판정한다. 영점에 의존하지 않는다

접촉 소실(EDGE) 판정은 아직 없다.

단위: m · N · s. 수치(임계 · 횟수)는 전부 DetectorConfig 로 받는다. 이 파일에 기본값을 두지 않는다.
"""
import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

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
    force_delta_n: float          # CONTACT: |F - F0|, OVER_FORCE: 원시 |F|
    debounce_count: int

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


class ContactDetector:
    """샘플을 하나씩 받아 확정된 판정을 돌려준다. 상태는 이 객체 안에만 있다."""

    def __init__(self, config: DetectorConfig):
        self.config = config
        self.baseline: Optional[Vector3] = None      # F0. None = tare 전
        self._contact_run = _Run()
        self._over_run = _Run()
        self._motion_id = 0
        self._contact_latched = False                # 한 motion_id 에서 CONTACT 는 1 회만
        self._over_latched = False                   # 과대 외력 구간마다 1 회만

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

        detections = []
        over = self._update_over_force(sample)
        if over:
            detections.append(over)
        contact = self._update_contact(sample)
        if contact:
            detections.append(contact)
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
