"""safety_monitor 노드 (계약 2.1 · 2.2 · 3.7 · 4.4 · 7.1 ③ · 7.2).

    /robot/sample (SENSOR) · /robot/status (STATE) → 감시(safety_core)
      → /robot/stop (StopRobot, 웹을 거치지 않는다)  → /safety/status (SafetyStatus, STATE)
    /safety/reset (ResetSafety) → 래치 해제. 로봇을 움직이지 않는다

- 감시 로직은 safety_core 에 있다. 이 파일은 메시지 변환 · 서비스 호출 · 발행만 맡는다.
- **정지 요청은 비동기로 한다.** robot_manager 의 핸들러가 move_stop 을 동기로 부르므로, 응답을 기다리면
  감시 노드까지 같이 멈춘다(계약 1장 "다른 노드의 완료를 콜백 안에서 동기 대기하지 않는다").
- **접수 ≠ 정지 완료.** accepted 는 접수일 뿐이고, 완료는 /robot/status 의 connected && !moving 으로만 본다.
  제한 시간 안에 확인되지 않으면 UNCONFIRMED 로 올린다 — 그때 남는 수단은 물리 비상정지뿐이다.
- 파라미터에 코드 기본값을 두지 않는다(규칙 7). 값이 없으면 기동하지 않는다.
- 단일 스레드 executor 로 돈다. 콜백이 섞이지 않으므로 잠금이 없다.
"""
import math

import rclpy
from contact_scan_interfaces.msg import ReasonCode, RobotSample, RobotStatus, SafetyStatus
from contact_scan_interfaces.srv import ResetSafety, StopRobot
from contact_scan_qos import QOS_SENSOR, QOS_STATE
from rcl_interfaces.msg import SetParametersResult
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.parameter import Parameter

from safety_monitor.safety_core import (
    DROP_LIMIT,
    Level,
    OVER_FORCE,
    ROBOT_STATUS_LOST,
    SafetyLimits,
    SafetyState,
    SAMPLE_STALE,
    Sample,
    StopPhase,
    StopTracker,
)

NODE_NAME = 'safety_monitor'

PARAMS = {
    'over_force_n': Parameter.Type.DOUBLE,              # 계약 이름 (6.4). contact_detector 와 같은 값
    'drop_limit_m': Parameter.Type.DOUBLE,              # 계약 이름. robot_manager 와 같은 값
    # 계약 이름이 **아니다**(ScanConfig 에 없어 SetConfig 전파 대상도 아니다). 2차 감시만의 여유:
    # 실제 한계는 drop_limit_m + 이 값이다. SetConfig 가 두 노드의 drop_limit_m 을 같은 값으로
    # 덮어써도 여유는 남는다 (계약 7.2, #53)
    'drop_limit_margin_m': Parameter.Type.DOUBLE,
    'sample_stale_ms': Parameter.Type.INTEGER,
    'robot_status_timeout_ms': Parameter.Type.INTEGER,
    'confirm_n': Parameter.Type.INTEGER,
    'startup_grace_s': Parameter.Type.DOUBLE,
    'stop_confirm_timeout_s': Parameter.Type.DOUBLE,
    'stop_retry_period_s': Parameter.Type.DOUBLE,
    'status_publish_period_s': Parameter.Type.DOUBLE,
    'check_period_s': Parameter.Type.DOUBLE,
}

# 여러 조건이 같이 참일 때 SafetyStatus.reason_code 에 싣는 순서
REASON_OF = {
    OVER_FORCE: ReasonCode.OVER_FORCE,
    DROP_LIMIT: ReasonCode.DROP_LIMIT,
    SAMPLE_STALE: ReasonCode.SAMPLE_STALE,
    ROBOT_STATUS_LOST: ReasonCode.ROBOT_STATUS_LOST,
}
PRIORITY = (OVER_FORCE, DROP_LIMIT, SAMPLE_STALE, ROBOT_STATUS_LOST)


def stamp_s(stamp) -> float:
    return stamp.sec + stamp.nanosec * 1e-9


class SafetyMonitorNode(Node):

    def __init__(self, **kwargs):
        super().__init__(NODE_NAME, **kwargs)
        self.values = {name: self._required(name, kind) for name, kind in PARAMS.items()}
        self.state = SafetyState(self._limits(self.values), StopTracker(
            self.values['stop_confirm_timeout_s'], self.values['stop_retry_period_s']))

        self.started_s = self.now_s()
        self.last_sample_s = None
        self.last_status_s = None
        self.last_published = None           # 직전에 발행한 내용. 바뀌면 바로 다시 발행한다
        self.stop_seq = 0

        self.publisher = self.create_publisher(SafetyStatus, '/safety/status', QOS_STATE)
        self.create_subscription(RobotSample, '/robot/sample', self.on_sample, QOS_SENSOR)
        self.create_subscription(RobotStatus, '/robot/status', self.on_status, QOS_STATE)
        self.stop_client = self.create_client(StopRobot, '/robot/stop')
        self.create_service(ResetSafety, '/safety/reset', self.on_reset)
        self.create_timer(self.values['check_period_s'], self.on_check)
        self.create_timer(self.values['status_publish_period_s'], lambda: self.publish(force=True))
        self.add_on_set_parameters_callback(self.on_set_parameters)

        self.get_logger().info(' '.join(f'{k}={v}' for k, v in self.values.items()))
        self.publish(force=True)             # 기동 직후 1회. STATE 는 TRANSIENT_LOCAL 이라 늦게 뜬 구독자도 받는다

    # ---------------------------------------------------------------- 파라미터

    def _required(self, name, kind):
        value = self.declare_parameter(name, kind).value
        if value is None:
            raise ValueError(f"파라미터 '{name}' 값이 없다. contact_scan_bringup/config/*.yaml 의 safety_monitor 절을 확인한다")
        return value

    @staticmethod
    def _limits(v) -> SafetyLimits:
        return SafetyLimits(v['over_force_n'], v['drop_limit_m'], v['sample_stale_ms'],
                            v['robot_status_timeout_ms'], v['confirm_n'], v['startup_grace_s'],
                            v['drop_limit_margin_m'])

    def on_set_parameters(self, params):
        """SetConfig 전파(계약 2.4 P03). 래치는 파라미터로 풀 수 없다 — /safety/reset 으로만 푼다."""
        changed = dict(self.values)
        for p in params:
            if p.name in changed:
                changed[p.name] = p.value
        try:
            limits = self._limits(changed)
            StopTracker(changed['stop_confirm_timeout_s'], changed['stop_retry_period_s'])
        except (TypeError, ValueError) as e:
            return SetParametersResult(successful=False, reason=str(e))
        self.state.watch.set_limits(limits)
        self.state.stop.confirm_timeout_s = changed['stop_confirm_timeout_s']
        self.state.stop.retry_period_s = changed['stop_retry_period_s']
        self.values = changed
        return SetParametersResult(successful=True)

    # ---------------------------------------------------------------- 구독 · 타이머

    def on_sample(self, msg):
        self.last_sample_s = self.now_s()
        found = self.state.watch.on_sample(Sample(
            stamp_s=max(stamp_s(msg.pose_stamp), stamp_s(msg.force_stamp)),
            position=(msg.pose.position.x, msg.pose.position.y, msg.pose.position.z),
            force=(msg.wrench.force.x, msg.wrench.force.y, msg.wrench.force.z),
            valid=msg.valid, motion_id=msg.motion_id, operation=msg.operation))
        self.react(found)

    def on_status(self, msg):
        self.last_status_s = self.now_s()
        self.state.connected, self.state.moving = msg.connected, msg.moving
        was_confirmed = self.state.stop.confirmed
        self.state.stop.on_status(msg.connected, msg.moving)
        if self.state.stop.confirmed and not was_confirmed:
            self.get_logger().info('정지 완료 확인 (connected && !moving)')
        self.publish()

    def on_check(self):
        """최신성 감시와 정지 확인 시간 초과. 샘플이 끊겨도 이 타이머는 돈다."""
        now = self.now_s()
        self.react(self.state.watch.check_freshness(
            now, self.last_sample_s, self.last_status_s, uptime_s=now - self.started_s))
        if self.state.stop.due_for_retry(now):
            self.get_logger().error(
                f'정지 요청이 {self.values["stop_confirm_timeout_s"]:.1f} s 안에 확인되지 않았다. 다시 요청한다. '
                f'드라이버가 응답하지 않으면 /robot/stop 도 통하지 않는다 — 물리 비상정지를 눌러야 한다')
            self.send_stop(self.state.cause)
        self.publish()

    def react(self, found):
        """새로 확정된 조건을 처리한다. 정지가 필요하면 요청하고 래치를 건다.

        error 와 warn 을 **다른 줄에서** 부른다. rclpy 의 RcutilsLogger 는 호출 위치(파일 · 함수 · 줄)마다
        severity 를 캐시해서, 같은 줄에서 severity 가 바뀌면 ValueError 를 던진다. 그 예외는 타이머 콜백
        안에서 나므로 아무도 잡지 않고 rclpy.spin 이 터져 **노드가 죽는다 — 2차 감시가 통째로 사라진다**
        (이슈 #102, 병후가 실제 노드 4개 + Virtual 에서 발견).
        """
        for condition in found:
            stops = condition.stops or self.state.moving
            if stops:
                self.get_logger().error(f'{condition.code}: {condition.detail}')
                self.state.note(condition)
                self.send_stop(condition)
            else:
                self.get_logger().warn(f'{condition.code}: {condition.detail} (정지 중이라 경고만 남긴다)')
        self.publish()

    # ---------------------------------------------------------------- 정지 요청

    def send_stop(self, condition):
        """/robot/stop 을 비동기로 부른다. 응답을 기다리지 않는다."""
        if not self.stop_client.service_is_ready():
            self.state.stop.request(self.now_s())
            self.state.stop.on_response(False, '/robot/stop 서버가 없다')
            self.get_logger().error('/robot/stop 서버가 없다. robot_manager 가 떠 있는지 확인한다')
            return
        self.stop_seq += 1
        request = StopRobot.Request(
            request_id=f'{NODE_NAME}-{self.stop_seq}', requester=NODE_NAME,
            reason=REASON_OF.get(condition.code, ReasonCode.OK) if condition else ReasonCode.OK,
            detail=condition.detail if condition else '')
        self.state.stop.request(self.now_s())
        self.stop_client.call_async(request).add_done_callback(self.on_stop_response)

    def on_stop_response(self, future):
        try:
            response = future.result()
        except Exception as e:                                   # noqa: BLE001 — 어떤 실패든 '접수 안 됨'이다
            self.state.stop.on_response(False, f'{type(e).__name__}: {e}')
            self.get_logger().error(f'/robot/stop 호출 실패: {e}')
        else:
            self.state.stop.on_response(response.accepted, response.detail)
            if not response.accepted:
                self.get_logger().error(f'/robot/stop 거절: code={response.reason_code} {response.detail}')
        self.publish()

    # ---------------------------------------------------------------- 서비스 · 발행

    def on_reset(self, request, response):
        """래치 해제. 조건이 해소됐을 때만 성공한다. 래치가 없어도 성공이다(멱등)."""
        success, detail = self.state.reset()
        response.success = success
        response.reason_code = ReasonCode.OK if success else ReasonCode.CONDITION_ACTIVE
        response.detail = detail
        self.get_logger().info(f'/safety/reset {"성공" if success else "거절"}: {detail or "래치 해제"}')
        self.publish()
        return response

    def now_s(self) -> float:
        return self.get_clock().now().nanoseconds * 1e-9

    def build(self) -> SafetyStatus:
        state, stop = self.state, self.state.stop
        msg = SafetyStatus()
        msg.stamp = self.get_clock().now().to_msg()
        msg.level = state.level().value
        msg.latched = state.latched
        msg.stop_required = stop.required
        msg.stop_confirmed = stop.confirmed

        # 래치를 건 원인을 우선 싣는다. 래치 전이면 지금 참인 조건 중 우선순위가 높은 것
        codes = [c for c in PRIORITY if c in state.watch.active]
        condition = state.cause or (state.watch.active[codes[0]] if codes else None)
        msg.reason_code = REASON_OF[condition.code] if condition else ReasonCode.OK
        msg.motion_id = condition.motion_id if condition else 0
        msg.position_valid = bool(condition and condition.position is not None)
        if msg.position_valid:
            msg.position.x, msg.position.y, msg.position.z = condition.position
        else:
            msg.position.x = msg.position.y = msg.position.z = math.nan   # 미측정은 0 이 아니다

        parts = []
        if condition:
            parts.append(f'{condition.code}: {condition.detail}')
        if codes and state.cause and state.cause.code not in codes:
            parts.append('지금 참인 조건: ' + ', '.join(codes))
        if stop.phase is StopPhase.UNCONFIRMED:
            parts.append(f'정지 확인 실패 {self.values["stop_confirm_timeout_s"]:.1f} s 초과 — 물리 비상정지가 필요할 수 있다')
            if stop.detail:
                # 거절 사유를 여기서 잃지 않는다. '왜 안 멈췄나'가 사람이 다음에 할 일을 정한다
                parts.append(f'마지막 응답: {stop.detail}')
        elif stop.phase is StopPhase.REJECTED:
            parts.append(f'정지 요청 거절: {stop.detail}')
        elif stop.required and not stop.confirmed:
            parts.append('정지 요청 접수. 완료 대기')
        msg.detail = ' / '.join(parts)
        return msg

    def publish(self, force=False):
        """변경 시 + 주기 발행(계약 2.1). stamp 는 비교에서 뺀다."""
        msg = self.build()
        key = (msg.level, msg.reason_code, msg.stop_required, msg.stop_confirmed, msg.latched,
               msg.motion_id, msg.position_valid, msg.detail)
        if force or key != self.last_published:
            self.last_published = key
            self.publisher.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = SafetyMonitorNode()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
