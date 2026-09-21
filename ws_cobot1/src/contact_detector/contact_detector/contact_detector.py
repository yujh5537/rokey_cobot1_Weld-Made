"""contact_detector 노드 (계약: docs/contracts/ros-interfaces.md 2.1 · 3.3 · 4.2).

    /robot/sample (RobotSample, SENSOR) → 판정(detector_core) → /contact/event (ContactEvent, EVENT)
    /scan/state  (ScanState, STATE)     → scan_id 태깅에만 쓴다
    /contact/tare (TareForce)           → 무접촉 · 정지 구간의 외력 평균을 기준값 F0 로 저장

- 판정 로직은 detector_core 에 있다. 이 파일은 메시지 ↔ Sample 변환, 발행, 서비스만 맡는다.
- 이벤트에 싣는 값(3.3절 v0.1.5): 좌표 · 시각 · 외력 · sample_id · z_drop_m 은 조건이 처음 성립한 샘플,
  detect_stamp · force_delta_n 은 확정 샘플.
- 파라미터에 코드 기본값을 두지 않는다(CLAUDE.md 규칙 7). 값이 없으면 기동하지 않는다.
- 이 노드는 로봇을 움직이지 않는다. 두산 API 를 부르지 않는다.
- source = 'sim' 이면 샘플의 외력 · z 를 가상 직육면체 모델(sim_source)의 값으로 바꿔서 판정한다.
  x · y 는 실제 로봇 값을 그대로 쓴다. 이벤트에도 바꾼 값을 싣는다(sim 결과의 치수가 맞아야 한다).
"""
import math
import threading
import time
from collections import OrderedDict

import rclpy
from contact_scan_interfaces.msg import ContactEvent, ReasonCode, RobotSample, ScanState
from contact_scan_interfaces.srv import TareForce
from contact_scan_qos import QOS_EVENT, QOS_SENSOR, QOS_STATE
from rcl_interfaces.msg import SetParametersResult
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.task import Future

from contact_detector.sim_source import SimBox, SimSource
from contact_detector.detector_core import (
    ContactDetector,
    DescendTareConfig,
    DetectorConfig,
    EdgeConfig,
    OP_DESCEND,
    OP_SLIDE,
    Sample,
    TARE_NO_SAMPLE,
    TARE_TOO_FEW,
    TARE_TOOL_REG_SUSPECT,
    TARE_UNSTABLE,
    TareAccumulator,
    TareConfig,
    TYPE_EDGE,
)

SOURCES = ('sim', 'robot_force')
KEPT_MESSAGES = 256          # 판정 샘플의 원본 메시지를 찾으려고 들고 있는 최근 샘플 수 (약 6 s 분량)
WARN_PERIOD_S = 2.0          # 같은 경고를 되풀이하는 최소 간격

PARAMS = {
    'source': Parameter.Type.STRING,
    'contact_threshold_n': Parameter.Type.DOUBLE,      # 계약 이름 (6.4). SetConfig 가 실행 중에 바꾼다
    'edge_drop_m': Parameter.Type.DOUBLE,              # 계약 이름
    'debounce_n': Parameter.Type.INTEGER,              # 계약 이름
    'over_force_n': Parameter.Type.DOUBLE,             # 계약 이름
    'over_force_debounce_n': Parameter.Type.INTEGER,
    'edge_arm_force_n': Parameter.Type.DOUBLE,
    'edge_trend_window_s': Parameter.Type.DOUBLE,
    'edge_trend_min_samples': Parameter.Type.INTEGER,
    'stale_age_ms': Parameter.Type.INTEGER,
    'tare_duration_s': Parameter.Type.DOUBLE,
    'tare_min_samples': Parameter.Type.INTEGER,
    'tare_max_std_n': Parameter.Type.DOUBLE,
    'tare_max_force_n': Parameter.Type.DOUBLE,
    # 하강 · 밀기 기준 분리 (#109)
    'descend_tare_enabled': Parameter.Type.BOOL,       # DESCEND 중 이동 중 F0 를 자동으로 다시 잡는다
    'descend_tare_delay_s': Parameter.Type.DOUBLE,     # DESCEND 시작 뒤 이만큼 지나서 모은다. 길이는 tare_duration_s
    'edge_arm_still_window_s': Parameter.Type.DOUBLE,  # > 0 이면 EDGE 판정을 z 로 켠다(edge_arm_force_n 대신)
    'edge_arm_still_m': Parameter.Type.DOUBLE,
    'edge_arm_travel_m': Parameter.Type.DOUBLE,
}

# source = 'sim' 일 때만 필요한 파라미터
SIM_PARAMS = {
    'sim_box_frame_id': Parameter.Type.STRING,
    'sim_box_origin_m': Parameter.Type.DOUBLE_ARRAY,
    'sim_box_size_m': Parameter.Type.DOUBLE_ARRAY,
    'sim_stiffness_n_per_m': Parameter.Type.DOUBLE,
    'sim_tip_radius_m': Parameter.Type.DOUBLE,
    'sim_fall_speed_mps': Parameter.Type.DOUBLE,
    'sim_slide_press_n': Parameter.Type.DOUBLE,
}

TARE_REASON = {
    TARE_NO_SAMPLE: ReasonCode.NO_SAMPLE,
    TARE_TOO_FEW: ReasonCode.TARE_TIMEOUT,
    TARE_UNSTABLE: ReasonCode.TARE_UNSTABLE,
    TARE_TOOL_REG_SUSPECT: ReasonCode.TOOL_REG_SUSPECT,
}


def stamp_s(stamp) -> float:
    return stamp.sec + stamp.nanosec * 1e-9


def _nan_if_none(value) -> float:
    return math.nan if value is None else float(value)


class ContactDetectorNode(Node):

    def __init__(self, **kwargs):
        super().__init__('contact_detector', **kwargs)
        self.values = {name: self._required(name, kind) for name, kind in PARAMS.items()}
        self.source = self.values['source']
        if self.source not in SOURCES:
            raise ValueError(f"source='{self.source}' 는 지원하지 않는다. {' | '.join(SOURCES)} 중에서 고른다")

        self.sim = None
        if self.source == 'sim':
            v = {name: self._required(name, kind) for name, kind in SIM_PARAMS.items()}
            self.values.update(v)
            self.sim = SimSource(SimBox(
                frame_id=v['sim_box_frame_id'], origin_m=tuple(v['sim_box_origin_m']),
                size_m=tuple(v['sim_box_size_m']), stiffness_n_per_m=v['sim_stiffness_n_per_m'],
                tip_radius_m=v['sim_tip_radius_m'], fall_speed_mps=v['sim_fall_speed_mps'],
                slide_press_n=v['sim_slide_press_n']))

        self.lock = threading.Lock()                 # 다중 스레드 executor 에 올려도 판정 상태가 깨지지 않게 한다
        self.detector = ContactDetector(*self._configs(self.values))
        self.tare = None                             # 수집 중인 TareAccumulator. 평소에는 None
        self.messages = OrderedDict()                # sample_id → RobotSample
        self.scan_id = ''
        self.event_id = 0
        self.last_force_stamp = None
        self.last_warn = {}

        self.publisher = self.create_publisher(ContactEvent, '/contact/event', QOS_EVENT)
        self.create_subscription(RobotSample, '/robot/sample', self.on_sample, QOS_SENSOR)
        self.create_subscription(ScanState, '/scan/state', self.on_scan_state, QOS_STATE)
        # tare 는 구간이 끝날 때까지 기다리는 코루틴이다. 기다리는 동안 그 콜백 그룹은 '실행 중'으로 잡히므로,
        # 서비스와 그 타이머를 샘플 구독(기본 그룹)과 다른 그룹에 둔다. 같은 그룹이면 샘플도 타이머도 돌지 못한다
        self.tare_timer_group = MutuallyExclusiveCallbackGroup()
        self.create_service(TareForce, '/contact/tare', self.on_tare,
                            callback_group=MutuallyExclusiveCallbackGroup())
        self.add_on_set_parameters_callback(self.on_set_parameters)

        if self.sim is not None:
            box = self.sim.box
            self.get_logger().info(
                f'sim 가상 직육면체: 밑면 중심 {box.origin_m} m, 크기 {box.size_m} m, '
                f'윗면 z={box.top_z:.4f} m (frame_id={box.frame_id})')
        self.get_logger().info(' '.join(f'{k}={v}' for k, v in self.values.items()))

    # ---------------------------------------------------------------- 파라미터

    def _required(self, name, kind):
        value = self.declare_parameter(name, kind).value
        if value is None:
            raise ValueError(f"파라미터 '{name}' 값이 없다. contact_scan_bringup/config/*.yaml 의 contact_detector 절을 확인한다")
        return value

    @staticmethod
    def _configs(v):
        by_z = v['edge_arm_still_window_s'] > 0
        tare = TareConfig(v['tare_min_samples'], v['tare_max_std_n'], v['tare_max_force_n'])
        return (
            DetectorConfig(v['contact_threshold_n'], v['debounce_n'], v['over_force_n'], v['over_force_debounce_n']),
            EdgeConfig(v['edge_drop_m'], v['debounce_n'], v['edge_arm_force_n'],
                       v['edge_trend_window_s'], v['edge_trend_min_samples'],
                       max_gap_s=v['stale_age_ms'] * 1e-3,
                       arm_still_window_s=v['edge_arm_still_window_s'] if by_z else None,
                       arm_still_m=v['edge_arm_still_m'] if by_z else None,
                       arm_travel_m=v['edge_arm_travel_m'] if by_z else None),
            DescendTareConfig(v['descend_tare_delay_s'], v['tare_duration_s'], tare)
            if v['descend_tare_enabled'] else None,
        )

    def on_set_parameters(self, params):
        """SetConfig 전파(계약 2.4 P02). 범위를 벗어나면 거절한다. 기준값 F0 는 유지한다."""
        changed = dict(self.values)
        for p in params:
            if p.name == 'source':
                return SetParametersResult(successful=False, reason='source 는 실행 중에 바꾸지 않는다')
            if p.name in changed:
                changed[p.name] = p.value
        try:
            config, edge_config, descend_tare = self._configs(changed)
            if changed['stale_age_ms'] <= 0:
                raise ValueError('stale_age_ms 는 0 보다 커야 한다')
        except (TypeError, ValueError) as e:
            return SetParametersResult(successful=False, reason=str(e))
        with self.lock:
            baseline = self.detector.baseline
            # 하강 중 자동 영점 상태는 옮기지 않는다. 다음 샘플에서 하강이 새로 시작된 것으로 보고 다시 모은다
            # (그동안 CONTACT 를 보류한다 — 안전한 쪽)
            self.detector = ContactDetector(config, edge_config, descend_tare)
            self.detector.set_baseline(baseline)
            self.values = changed
        return SetParametersResult(successful=True)

    # ---------------------------------------------------------------- 구독

    def on_scan_state(self, msg):
        self.scan_id = msg.scan_id

    def on_sample(self, msg):
        now_s = self.get_clock().now().nanoseconds * 1e-9
        force_s, pose_s = stamp_s(msg.force_stamp), stamp_s(msg.pose_stamp)
        limit_s = self.values['stale_age_ms'] * 1e-3

        # 샘플 간격 감시. 판정은 바꾸지 않고 알리기만 한다 (샘플이 비는 동안에는 접촉도 하강도 볼 수 없다)
        if msg.valid and self.last_force_stamp is not None and force_s - self.last_force_stamp > limit_s:
            self.warn('gap', f'샘플 간격 {1000 * (force_s - self.last_force_stamp):.0f} ms > stale_age_ms')
        if msg.valid:
            self.last_force_stamp = force_s

        # 오래된 샘플은 버린다 (계약 3.1)
        if msg.valid and now_s - max(force_s, pose_s) > limit_s:
            self.warn('stale', f'샘플이 {1000 * (now_s - max(force_s, pose_s)):.0f} ms 묵었다. 버린다')
            return
        if msg.valid and msg.motion_id == 0 and msg.operation in (OP_DESCEND, OP_SLIDE):
            self.warn('motion_id', 'DESCEND · SLIDE 인데 motion_id 가 0 이다. robot_manager 는 이 이벤트로 정지하지 않는다')

        sample = Sample(
            sample_id=msg.sample_id, pose_stamp=pose_s, force_stamp=force_s,
            position=(msg.pose.position.x, msg.pose.position.y, msg.pose.position.z),
            force=(msg.wrench.force.x, msg.wrench.force.y, msg.wrench.force.z),
            valid=msg.valid, motion_id=msg.motion_id, operation=msg.operation)

        if self.sim is not None:
            if msg.frame_id != self.sim.box.frame_id:
                self.warn('sim_frame', f"샘플 frame_id='{msg.frame_id}' 가 "
                                       f"sim_box_frame_id='{self.sim.box.frame_id}' 와 다르다. 판정하지 않는다")
                return
            sample = self.sim.apply(sample)
            msg = self.sim_message(msg, sample)      # 이벤트에도 가상 값을 싣는다

        with self.lock:
            self.messages[msg.sample_id] = msg
            while len(self.messages) > KEPT_MESSAGES:
                self.messages.popitem(last=False)
            if self.tare is not None:
                self.tare.add(sample)
            detections = self.detector.update(sample)
            descend_tare = self.detector.descend_tare_result
            self.detector.descend_tare_result = None
            no_baseline = msg.valid and self.detector.active_baseline is None
            if no_baseline and msg.operation == OP_SLIDE:
                self.warn('no_tare', 'SLIDE 인데 기준값 F0 가 없다(tare 전). EDGE 를 판정하지 않는다')
            if no_baseline and msg.operation == OP_DESCEND and not self.detector.contact_withheld:
                self.warn('no_tare_descend', 'DESCEND 인데 기준값 F0 가 없다(tare 전 · 자동 영점 실패). '
                                             'CONTACT 를 판정하지 않는다 — 과대 외력만 멈춘다')
            events = [self.to_event(d) for d in detections]
            gap = self.detector.trend_gap
        if descend_tare is not None:
            if descend_tare.success:
                self.get_logger().info(
                    f'하강 중 자동 영점: {descend_tare.sample_count} samples, |F0| {descend_tare.baseline_norm_n:.2f} N, '
                    f'|F-F0| rms {descend_tare.std_vector_n:.3f} N')
            else:
                self.get_logger().warn(
                    f'하강 중 자동 영점 실패({descend_tare.error}). /contact/tare 의 F0 로 판정한다')
        if gap:
            self.warn('trend_gap', '샘플 공백으로 EDGE 추세선을 버리고 다시 쌓는다. '
                                   '그동안 접촉 소실을 볼 수 없다')
        for event in events:
            self.publisher.publish(event)

    @staticmethod
    def sim_message(msg, sample):
        """원본 메시지에 가상 외력 · z 를 덮어쓴 사본. 이벤트가 이 값을 싣는다."""
        out = RobotSample()
        out.sample_id, out.frame_id, out.valid = msg.sample_id, msg.frame_id, msg.valid
        out.motion_id, out.operation = msg.motion_id, msg.operation
        out.pose_stamp, out.force_stamp = msg.pose_stamp, msg.force_stamp
        out.pose = msg.pose
        out.pose.position.z = sample.position[2]
        out.wrench.force.x, out.wrench.force.y, out.wrench.force.z = sample.force
        return out

    def warn(self, key, text):
        now = time.monotonic()
        if now - self.last_warn.get(key, -math.inf) >= WARN_PERIOD_S:
            self.last_warn[key] = now
            self.get_logger().warn(text)

    def to_event(self, detection) -> ContactEvent:
        first = self.messages.get(detection.first_sample.sample_id)
        confirm = self.messages.get(detection.sample.sample_id)
        self.event_id += 1
        event = ContactEvent()
        event.event_id = self.event_id
        event.scan_id = self.scan_id
        event.type = detection.type
        event.source = self.source
        # 판정 샘플 = 조건이 처음 성립한 샘플
        event.motion_id = first.motion_id
        event.sample_id = first.sample_id
        event.frame_id = first.frame_id
        event.pose = first.pose
        event.wrench = first.wrench
        event.pose_stamp = first.pose_stamp
        event.force_stamp = first.force_stamp
        event.z_drop_valid = detection.type == TYPE_EDGE and detection.z_drop_m is not None
        event.z_drop_m = float(detection.z_drop_m) if event.z_drop_valid else math.nan
        # 확정 샘플
        event.detect_stamp = confirm.force_stamp
        event.force_delta_n = float(detection.force_delta_n)
        event.debounce_count = detection.debounce_count
        return event

    # ---------------------------------------------------------------- tare

    async def on_tare(self, request, response):
        duration_s = request.duration_s if request.duration_s > 0 else self.values['tare_duration_s']
        with self.lock:
            busy = self.tare is not None
            if not busy:
                self.tare = TareAccumulator(TareConfig(
                    self.values['tare_min_samples'], self.values['tare_max_std_n'], self.values['tare_max_force_n']))
        if busy:
            response.success = False
            response.error = ReasonCode.BUSY
            response.detail = 'tare 가 이미 진행 중이다'
            return response

        # 구간이 끝날 때까지 기다린다. sleep 으로 기다리면 그동안 샘플 콜백이 돌지 못해 모을 샘플이 없다.
        # 코루틴으로 기다리면 executor 가 그사이 다른 콜백을 돌린다
        finished = Future(executor=self.executor)
        timer = self.create_timer(duration_s, lambda: finished.done() or finished.set_result(True),
                                  callback_group=self.tare_timer_group)
        try:
            await finished
        finally:
            timer.cancel()
            self.destroy_timer(timer)
        with self.lock:
            result, self.tare = self.tare.result(), None
            if result.success:
                self.detector.set_baseline(result.baseline)

        response.success = result.success
        response.error = ReasonCode.OK if result.success else TARE_REASON.get(result.error, ReasonCode.TARE_FAILED)
        response.sample_count = result.sample_count
        response.baseline_norm_n = _nan_if_none(result.baseline_norm_n)
        response.std_norm_n = _nan_if_none(result.std_norm_n)
        for axis in 'xyz':                           # 토크 기준값은 쓰지 않는다. 0 이 아니라 NaN 으로 둔다
            setattr(response.offset.torque, axis, math.nan)
        if result.baseline is not None:
            response.offset.force.x, response.offset.force.y, response.offset.force.z = result.baseline
        else:
            for axis in 'xyz':
                setattr(response.offset.force, axis, math.nan)
        rms = _nan_if_none(result.std_vector_n)
        response.detail = (f'{result.error or "OK"}: {result.sample_count} samples / {duration_s:.2f} s, '
                           f'|F0| {response.baseline_norm_n:.2f} N, |F-F0| rms {rms:.3f} N')
        self.get_logger().info(f'tare {response.detail}' + ('' if result.success else ' → 기준값을 바꾸지 않았다'))
        return response


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = ContactDetectorNode()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
