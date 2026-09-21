"""sim 입력원: 가상 직육면체와 TCP 위치로 접촉 상태를 만든다 (BRD 1.4 C, 4.1.6). rclpy 를 import 하지 않는다.

왜 필요한가 — Virtual Mode 에서는 힘 제어가 정상 동작하지 않고(BRD 위험 2, 매뉴얼 5.1.2 · 5.1.4),
외력 값도 0 근처다(`docs/env/api-check-log.md`). 실제 샘플만으로는 접촉도 소실도 절대 일어나지 않는다.
그래서 **샘플의 외력과 z 를 가상 모델의 값으로 바꿔서** 판정기에 넣는다. x · y 는 실제 로봇 값을 그대로 쓴다
(모서리 좌표는 x · y 에서 나오므로, 치수는 Virtual 로봇이 실제로 이동한 거리에서 나온다).

모델 — 팁(반지름 r 의 구, TCP = 최하단점)이 윗면을 따라가다 모서리에서 내려앉는다.
  팁이 박스 경계를 수평으로 d 만큼 지났을 때 "팁이 닿을 수 있는 높이" z_surface:
    d <= 0       윗면 위        z_surface = z_top
    0 < d < r    모서리에 얹힘   z_surface = z_top − (r − √(r² − d²))     ← geometry_estimator 보정식의 정방향
    d >= r       완전히 벗어남   z_surface = 박스 밑면(지지면). 팁이 옆면을 따라 내려간다

  OP_SLIDE 중에는 순응 제어가 팁을 표면에 붙여 둔다고 본다. 목표 침투(press_n / 강성)를 유지하되
  **내려가는 속도는 fall_speed_mps 로 제한한다.** 모서리에서 표면이 갑자기 사라져도 팁은 그 속도로만 내려간다.
  그 밖(OP_DESCEND 등)에서는 팁이 로봇이 지시한 z 에 그대로 있다.

  외력은 침투 깊이 x 강성이다. Base 기준 +z (누르면 반작용이 위로).

수치는 전부 SimBox 로 받는다. 이 파일에 기본값을 두지 않는다.
"""
import math
from dataclasses import dataclass, replace
from typing import Optional, Tuple

from contact_detector.detector_core import OP_SLIDE, Sample

Vector3 = Tuple[float, float, float]


@dataclass(frozen=True)
class SimBox:
    """가상 직육면체. 실제 부재와 무관한 가상값이다."""

    frame_id: str                # 이 좌표의 프레임. 샘플의 frame_id 와 다르면 판정하지 않는다
    origin_m: Vector3            # 밑면 중심 (x, y, z)
    size_m: Vector3              # 가로(x) · 세로(y) · 높이(z)
    stiffness_n_per_m: float     # 가상 외력 = 강성 x 침투 깊이
    tip_radius_m: float          # 팁(구) 반지름. scan_manager 의 tip_radius_m 과 같아야 치수가 복원된다
    fall_speed_mps: float        # 표면이 내려갈 때 팁이 따라 내려가는 속도 제한
    slide_press_n: float         # OP_SLIDE 중 유지하는 누름 힘. robot_manager 의 slide_target_force_n 에 해당

    def __post_init__(self):
        for name in ('stiffness_n_per_m', 'tip_radius_m', 'fall_speed_mps', 'slide_press_n'):
            value = getattr(self, name)
            if not (isinstance(value, (int, float)) and math.isfinite(value) and value > 0):
                raise ValueError(f'{name} = {value!r}: 0 보다 큰 유한한 수여야 한다')
        for name in ('origin_m', 'size_m'):
            values = getattr(self, name)
            if len(values) != 3 or not all(math.isfinite(v) for v in values):
                raise ValueError(f'{name} 은 유한한 수 3 개여야 한다')
        if not all(v > 0 for v in self.size_m):
            raise ValueError('size_m 의 세 변은 0 보다 커야 한다')
        if not self.frame_id:
            raise ValueError('frame_id 가 비어 있다')

    @property
    def top_z(self) -> float:
        return self.origin_m[2] + self.size_m[2]

    def overhang_m(self, x: float, y: float) -> float:
        """팁이 윗면 경계를 수평으로 지나친 거리. 0 이하면 윗면 위다."""
        return max(abs(x - self.origin_m[0]) - self.size_m[0] / 2.0,
                   abs(y - self.origin_m[1]) - self.size_m[1] / 2.0)

    def surface_z(self, x: float, y: float) -> float:
        """그 x · y 에서 팁 최하단점이 닿을 수 있는 높이."""
        d = self.overhang_m(x, y)
        if d <= 0.0:
            return self.top_z
        if d < self.tip_radius_m:
            r = self.tip_radius_m
            return self.top_z - (r - math.sqrt(r * r - d * d))
        return self.origin_m[2]          # 옆면을 따라 지지면까지


class SimSource:
    """실제 샘플의 외력 · z 를 가상 모델의 값으로 바꾼다. 상태는 이 객체 안에만 있다."""

    def __init__(self, box: SimBox):
        self.box = box
        self._z: Optional[float] = None          # 직전에 내보낸 가상 z
        self._t: Optional[float] = None

    def reset(self):
        self._z = self._t = None

    def apply(self, sample: Sample) -> Sample:
        """가상 외력 · z 로 바꾼 샘플. 무효 샘플과 다른 프레임은 그대로 돌려준다."""
        if not sample.valid:
            self.reset()
            return sample

        x, y, z_robot = sample.position
        surface = self.box.surface_z(x, y)
        press_depth = self.box.slide_press_n / self.box.stiffness_n_per_m

        if sample.operation == OP_SLIDE and self._z is not None and self._t is not None:
            # 순응 제어가 팁을 표면에 붙여 둔다. 내려가는 속도만 제한한다
            dt = max(0.0, sample.pose_stamp - self._t)
            z = max(surface - press_depth, self._z - self.box.fall_speed_mps * dt)
        else:
            z = z_robot                           # 로봇이 지시한 z 에 그대로 있다 (DESCEND 등)

        self._z, self._t = z, sample.pose_stamp
        force_z = self.box.stiffness_n_per_m * max(0.0, surface - z)
        return replace(sample, position=(x, y, z), force=(0.0, 0.0, force_z))
