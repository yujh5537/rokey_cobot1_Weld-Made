"""이상 감시와 정지 요청의 상태. rclpy 를 import 하지 않는다 (ROS 없이 pytest 로 돈다).

감시하는 것 (BRD 4.5.3 · 4.5.4 · 4.6, 계약 7.2):
  - 과대 외력  : 원시 |F| > over_force_n. 2차 감시 (1차는 contact_detector → robot_manager)
  - 하강 제한  : SLIDE 중 z 가 기준보다 drop_limit_m + drop_limit_margin_m 넘게 내려감. 2차 감시 (1차는 robot_manager)
                 기준 z = operation 이 OP_SLIDE 로 바뀐 첫 샘플의 z (계약 7.2. 1차와 **기준 z 는 같다**)
                 한계만 여유(margin)만큼 뒤에 둔다: 값까지 같으면 잡음 한 샘플로도 2차가 먼저 걸려
                 1차가 정상 동작인데 래치부터 걸린다 (#53, 계약 v0.1.21 결정 2)
  - 데이터 최신성: /robot/sample · /robot/status 가 한계 시간 넘게 안 들어옴 (위험 10)

이 노드가 할 수 있는 것과 없는 것 (BRD 4.5 각주, 규칙 9):
  - 할 수 있는 것: /robot/stop 요청과 그 결과 보고. 래치를 걸어 다음 작업 시작을 막는 것
  - 할 수 없는 것: 실제 정지. 드라이버가 서비스에 응답하지 않으면 /robot/stop 도 /robot/status 도 같이 죽는다
    (docs/env/api-check-log.md). 그때 남는 수단은 티치펜던트의 물리 비상정지뿐이다.
    그래서 "요청 접수"와 "정지 완료 확인"을 구분하고, 확인되지 않으면 그 사실을 STOP 으로 계속 올린다.

수치는 전부 SafetyLimits 로 받는다. 이 파일에 기본값을 두지 않는다.
"""
import math
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

# RobotSample.OP_* (계약 3.1). 번호는 계약이다
OP_NONE = 0
OP_SLIDE = 3

# 감시 조건. 노드가 ReasonCode 로 옮긴다 (계약 6.1)
OVER_FORCE = 'OVER_FORCE'                    # → 400
DROP_LIMIT = 'DROP_LIMIT'                    # → 205
SAMPLE_STALE = 'SAMPLE_STALE'                # → 403
ROBOT_STATUS_LOST = 'ROBOT_STATUS_LOST'      # → 404

Vector3 = Tuple[float, float, float]


def norm(v: Vector3) -> float:
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


class Level(Enum):
    """SafetyStatus.LEVEL_* (계약 3.7)."""

    OK = 0
    WARN = 1
    STOP = 2


@dataclass(frozen=True)
class Sample:
    """RobotSample 에서 감시에 쓰는 부분."""

    stamp_s: float               # max(pose_stamp, force_stamp). 최신성은 더 오래된 쪽으로 본다
    position: Vector3            # m
    force: Vector3               # N. 원시 외력 (영점에 의존하지 않는다)
    valid: bool = True
    motion_id: int = 0
    operation: int = OP_NONE


@dataclass(frozen=True)
class SafetyLimits:
    over_force_n: float          # 계약 이름. contact_detector 와 같은 값
    drop_limit_m: float          # 계약 이름. robot_manager 와 같은 값 (쌍 검사 대상)
    sample_stale_ms: int
    robot_status_timeout_ms: int
    confirm_n: int               # 조건을 확정하는 연속 샘플 수
    startup_grace_s: float       # 기동 후 이 시간 동안은 최신성으로 정지 · 래치를 걸지 않는다
    drop_limit_margin_m: float   # 계약 이름이 **아니다**. 2차 감시만의 여유 (계약 7.2)

    def __post_init__(self):
        if not (self.over_force_n > 0 and self.drop_limit_m > 0):
            raise ValueError('over_force_n, drop_limit_m 은 0 보다 커야 한다')
        if not self.drop_limit_margin_m > 0:
            # 0 을 허용하면 "여유를 뒀다"고 적힌 설정이 조용히 1차와 같아진다. 여유가 필요 없다는
            # 결정이 나면 이 검사와 계약 7.2 를 같이 고친다 (CLAUDE.md 규칙 4 · 7)
            raise ValueError('drop_limit_margin_m 은 0 보다 커야 한다 (계약 7.2 의 2차 여유)')
        if self.sample_stale_ms <= 0 or self.robot_status_timeout_ms <= 0:
            raise ValueError('sample_stale_ms, robot_status_timeout_ms 는 0 보다 커야 한다')
        if self.startup_grace_s < 0:
            raise ValueError('startup_grace_s 는 0 이상이어야 한다')
        if self.confirm_n < 1:
            raise ValueError('confirm_n 은 1 이상이어야 한다')

    @property
    def effective_drop_limit_m(self) -> float:
        """2차 감시가 실제로 쓰는 한계. 1차(robot_manager)의 drop_limit_m 보다 여유만큼 뒤다.

        SetConfig(계약 2.4 P03)가 두 노드의 drop_limit_m 을 같은 값으로 덮어써도 여유는 남는다 —
        drop_limit_margin_m 은 계약 이름이 아니고 ScanConfig 에도 없어서 전파 대상이 아니다.
        """
        return self.drop_limit_m + self.drop_limit_margin_m


@dataclass(frozen=True)
class Condition:
    """참이 된 감시 조건 1건."""

    code: str
    detail: str
    motion_id: int = 0
    position: Optional[Vector3] = None

    @property
    def stops(self) -> bool:
        """정지를 요청해야 하는 조건인가. 최신성 조건은 움직이는 중일 때만 STOP 이다."""
        return self.code in (OVER_FORCE, DROP_LIMIT)


class _Run:
    """조건이 연속으로 참인 횟수를 센다."""

    def __init__(self):
        self.count = 0

    def update(self, condition: bool) -> int:
        self.count = self.count + 1 if condition else 0
        return self.count


class ConditionWatch:
    """샘플과 상태를 받아 참이 된 조건을 돌려준다. 정지 요청 · 래치는 다루지 않는다."""

    def __init__(self, limits: SafetyLimits):
        self.limits = limits
        self.slide_start_z: Optional[float] = None    # operation 이 SLIDE 로 바뀐 첫 샘플의 z
        self.last_operation = OP_NONE
        self.active: Dict[str, Condition] = {}        # 지금 참인 조건 (래치 해제 가능 여부의 근거)
        self._runs = {code: _Run() for code in (OVER_FORCE, DROP_LIMIT)}

    @property
    def startup_grace_s(self) -> float:
        return self.limits.startup_grace_s

    def set_limits(self, limits: SafetyLimits):
        """SetConfig 전파(계약 2.4 P03). 기준 z 와 진행 중인 연속 횟수는 유지한다."""
        self.limits = limits

    def on_sample(self, sample: Sample) -> List[Condition]:
        if not sample.valid:
            return []                                  # 무효 샘플로는 판정하지 않는다. 최신성이 따로 본다

        # 기준 z: operation 이 SLIDE 로 바뀐 첫 샘플 (계약 7.2). SLIDE 가 아니면 감시하지 않는다
        if sample.operation == OP_SLIDE:
            if self.last_operation != OP_SLIDE:
                self.slide_start_z = sample.position[2]
        else:
            self.slide_start_z = None
        self.last_operation = sample.operation

        found = []
        magnitude = norm(sample.force)
        if self._check(OVER_FORCE, magnitude > self.limits.over_force_n, sample,
                       f'force {magnitude:.1f} N > {self.limits.over_force_n:.1f} N') is not None:
            found.append(self.active[OVER_FORCE])

        # 경계는 초과다: 정확히 한계면 걸리지 않는다 (계약 7.2, 1차 robot_manager 와 같은 규칙)
        limit = self.limits.effective_drop_limit_m
        drop = None if self.slide_start_z is None else self.slide_start_z - sample.position[2]
        if self._check(DROP_LIMIT, drop is not None and drop > limit, sample,
                       f'drop {1000 * (drop or 0.0):.1f} mm > {1000 * limit:.1f} mm '
                       f'(2차 = 1차 {1000 * self.limits.drop_limit_m:.1f} + 여유 '
                       f'{1000 * self.limits.drop_limit_margin_m:.1f} mm, 기준 z = SLIDE 첫 샘플)') is not None:
            found.append(self.active[DROP_LIMIT])
        return found

    def _check(self, code: str, is_true: bool, sample: Sample, detail: str) -> Optional[Condition]:
        """연속 confirm_n 회면 확정한다. 돌려주는 값은 '이번에 새로 확정됐다'일 때만 not None."""
        was_active = code in self.active
        count = self._runs[code].update(is_true)
        if count == 0:
            self.active.pop(code, None)
            return None
        condition = Condition(code, detail, sample.motion_id, sample.position)
        if count < self.limits.confirm_n:
            return None
        self.active[code] = condition
        return None if was_active else condition       # 같은 조건을 되풀이해 올리지 않는다

    def check_freshness(self, now_s: float, last_sample_s: Optional[float],
                        last_status_s: Optional[float], uptime_s: float) -> List[Condition]:
        """한계 시간을 넘게 소식이 없는 입력을 찾는다.

        아직 한 번도 못 받았으면 감시하지 않는다. 그리고 기동 후 startup_grace_s 동안도 감시하지 않는다 —
        노드들이 순차로 준비되는 동안 샘플 주기가 불안정하고(2026-09-21 종단 실행에서 508 ms 공백),
        그때 robot_manager 는 '위치를 모르면 이동 중'이라 moving=true 를 낸다(PR #72). 두 보수적 기본값이
        겹쳐 기동하자마자 래치가 걸렸다. **과대 외력 · 하강 제한은 유예하지 않는다** — 기동과 무관한 실제 위험이다.
        """
        if uptime_s < self.startup_grace_s:
            self.active.pop(SAMPLE_STALE, None)
            self.active.pop(ROBOT_STATUS_LOST, None)
            return []
        found = []
        for code, last_s, limit_ms in (
                (SAMPLE_STALE, last_sample_s, self.limits.sample_stale_ms),
                (ROBOT_STATUS_LOST, last_status_s, self.limits.robot_status_timeout_ms)):
            missing = last_s is not None and now_s - last_s > limit_ms * 1e-3
            was_active = code in self.active
            if not missing:
                self.active.pop(code, None)
                continue
            condition = Condition(code, f'{1000 * (now_s - last_s):.0f} ms 동안 수신 없음 (> {limit_ms} ms)')
            self.active[code] = condition
            if not was_active:
                found.append(condition)
        return found


class StopPhase(Enum):
    """정지 요청의 진행. '접수'와 '정지 완료'를 구분한다 (계약 1장)."""

    NONE = 0
    REQUESTED = 1        # /robot/stop 을 보냈다. 응답 대기
    ACCEPTED = 2         # accepted=true 를 받았다. 정지 완료 대기
    CONFIRMED = 3        # /robot/status 가 connected && !moving
    REJECTED = 4         # accepted=false (드라이버 미연결 등)
    UNCONFIRMED = 5      # 제한 시간 안에 확인되지 않았다. 사람이 물리 비상정지를 눌러야 할 수 있다


class StopTracker:
    """정지 요청 1건의 상태. 서비스 호출은 노드가 한다 (여기서는 기다리지 않는다)."""

    def __init__(self, confirm_timeout_s: float, retry_period_s: float):
        if confirm_timeout_s <= 0 or retry_period_s <= 0:
            raise ValueError('stop_confirm_timeout_s, stop_retry_period_s 는 0 보다 커야 한다')
        self.confirm_timeout_s = confirm_timeout_s
        self.retry_period_s = retry_period_s
        self.phase = StopPhase.NONE
        self.requested_s: Optional[float] = None       # 첫 요청 시각. 제한 시간은 여기서 잰다
        self.last_sent_s: Optional[float] = None
        self.detail = ''

    @property
    def confirmed(self) -> bool:
        return self.phase is StopPhase.CONFIRMED

    @property
    def required(self) -> bool:
        return self.phase is not StopPhase.NONE

    def request(self, now_s: float):
        if self.phase in (StopPhase.NONE, StopPhase.CONFIRMED):
            self.requested_s = now_s
        self.phase = StopPhase.REQUESTED
        self.last_sent_s = now_s

    def on_response(self, accepted: bool, detail: str = ''):
        if self.phase is StopPhase.CONFIRMED:
            return                                     # 이미 멈춘 뒤 늦게 온 응답
        self.phase = StopPhase.ACCEPTED if accepted else StopPhase.REJECTED
        self.detail = detail

    def on_status(self, connected: bool, moving: bool):
        """정지 완료는 connected && !moving 으로만 확인한다 (계약 1장)."""
        if self.phase in (StopPhase.NONE, StopPhase.CONFIRMED):
            return
        if connected and not moving:
            self.phase = StopPhase.CONFIRMED

    def due_for_retry(self, now_s: float) -> bool:
        """제한 시간을 넘겼고 재시도 주기가 지났는가.

        재시도는 느리게 한다. 드라이버가 응답하지 않는 원인이 호출 과부하일 수 있다
        (docs/env/api-check-log.md). 세게 두드리면 더 나빠진다.
        """
        if self.phase in (StopPhase.NONE, StopPhase.CONFIRMED):
            return False
        if now_s - self.requested_s <= self.confirm_timeout_s:
            return False
        self.phase = StopPhase.UNCONFIRMED
        return now_s - self.last_sent_s >= self.retry_period_s

    def clear(self):
        self.phase = StopPhase.NONE
        self.requested_s = self.last_sent_s = None
        self.detail = ''


class SafetyState:
    """감시 조건 + 정지 요청 + 래치를 묶는다. level · reason_code 의 근거를 한 곳에서 만든다."""

    def __init__(self, limits: SafetyLimits, stop: StopTracker):
        self.watch = ConditionWatch(limits)
        self.stop = stop
        self.latched = False
        self.cause: Optional[Condition] = None         # 래치를 건 조건. 해제 전까지 유지한다
        self.moving = False                            # 마지막으로 알려진 /robot/status.moving
        self.connected = False

    def stopping_conditions(self) -> List[Condition]:
        """지금 정지가 필요한 조건. 최신성 조건은 움직이는 중일 때만 포함한다."""
        return [c for c in self.watch.active.values() if c.stops or self.moving]

    def level(self) -> Level:
        if self.latched or self.stopping_conditions():
            return Level.STOP
        if self.watch.active:
            return Level.WARN                          # 서 있는데 소식이 없다. 정지를 요청할 일은 아니다
        return Level.OK

    def note(self, condition: Condition):
        """래치를 건다. 먼저 걸린 원인을 덮어쓰지 않는다."""
        self.latched = True
        if self.cause is None:
            self.cause = condition

    def reset(self) -> Tuple[bool, str]:
        """관제자의 /safety/reset. 조건이 아직 참이면 거절한다. 로봇을 움직이지 않는다."""
        remaining = sorted(self.watch.active)
        if remaining:
            return False, '조건이 아직 참이다: ' + ', '.join(remaining)
        self.latched = False
        self.cause = None
        self.stop.clear()
        return True, ''
