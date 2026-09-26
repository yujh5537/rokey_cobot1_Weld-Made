"""ExecutePath 실행 (phase 2, P1). 계약 `docs/phase2/weld-ros-interfaces.md` 5.2.

경유점을 차례로 지난다. 접촉 판정 · 힘 제어는 없다. 방식은 `path_mode`(D31):

- `line`: 점마다 amovel(ASYNC) → 멈춤 · 도착 확인 → 다음 점. 점마다 선다(D8 허용).
- `spline`: 첫 점까지 amovel 직선으로 가서 선 뒤, 나머지를 amovesx 한 번으로 보낸다.
  spline 은 현재 위치에서 첫 점까지를 곡선으로 가므로, 계약의 "첫 점까지도 직선"을 지키려고 나눴다.

한 구간(leg)을 감시하는 규칙은 1차 `RobotManager.watch` 와 같다(같은 파라미터를 쓴다):
- "움직였는가"는 위치로 확인된 이동(`moved_min_m` 넘게)만, "지금 움직이는가"는 위치 창과 상태 둘 중 하나라도
- 명령 뒤 `arrival_grace_s` 가 지나도록 출발하지 않았고 목표가 허용치 밖이면 move_stop 뒤 다시 보낸다(#153)
- 멈췄다고 도착한 것이 아니다. 목표와의 거리가 `path_tolerance_m` 밖이면 ROBOT_ERROR(204)
- 취소 · 정지 요청 · 과대 외력 · 시간 초과는 `stop_robot` 으로 멈춤까지 확인한다. 확인 못 하면 ROBOT_ERROR

두산 호출은 전부 노드의 `call_sync`(= CallQueue) 를 탄다. 새 락을 만들지 않는다.
"""
import math
import time
from collections import deque

from contact_scan_interfaces.action import ExecutePath
from contact_scan_interfaces.msg import ContactEvent, ReasonCode

from robot_manager import dsr_client, motion_state, paths

LOOP_PERIOD_S = 0.02       # 감시 주기. robot_manager.watch 와 같다
R = ExecutePath.Result


class PathRunner:
    """goal 하나를 끝까지 실행한다. `run()` → (reason, reason_code, detail).

    끝난 뒤 `waypoints_done` · `distance_m` 가 Result 에 들어간다.
    """

    def __init__(self, node, goal_handle, motion, limits, waypoints):
        self.node = node
        self.goal_handle = goal_handle
        self.motion = motion
        self.limits = limits
        self.waypoints = list(waypoints)
        self.posx = paths.to_posx_list(self.waypoints)
        goal = goal_handle.request
        self.speed = float(goal.speed)
        self.tolerance = float(goal.path_tolerance_m)
        self.timeout_s = ((goal.timeout.sec + goal.timeout.nanosec / 1e9)
                          or float(node.param('motion_timeout_s')))
        self.feedback_period = float(node.param('feedback_period_s'))
        self.grace_s = float(node.param('arrival_grace_s'))
        self.restart_max = int(node.param('move_restart_max'))
        self.start = motion.start_position
        self.index = 0                 # 향하는 경유점
        self.waypoints_done = 0
        self.distance_m = 0.0
        self.next_feedback = 0.0

    # ---- 실행 --------------------------------------------------------------
    def run(self):
        if self.start is None:
            # 출발 위치를 모르면 진행도, 첫 구간 도착도 잴 수 없다. 움직이기 전에 끝낸다
            return (R.REASON_ROBOT_ERROR, ReasonCode.ROBOT_ERROR,
                    '출발 위치를 모른다(유효 샘플 없음). 경로를 보내지 않았다')
        n = len(self.waypoints)
        line = self.limits.mode == 'line'
        last_line_leg = n if line else 1          # spline 이면 첫 점만 직선
        for i in range(last_line_leg):
            failed = self._leg(i, lambda i=i: self._send_line(i), f'경유점 {i}')
            if failed:
                return failed
            self.waypoints_done = i + 1
        if not line and n > 1:
            failed = self._leg(n - 1, self._send_spline, f'spline 경유점 1~{n - 1}', spline=True)
            if failed:
                return failed
        self.waypoints_done = n
        self.index = n - 1
        self.distance_m = paths.path_length_m(self.start, self.waypoints)
        return (R.REASON_TARGET_REACHED, ReasonCode.OK, '')

    def _send_line(self, i):
        request = dsr_client.path_line_request(self.posx[i], self.speed, self.limits.acc_ratio)
        return self.node.call_sync(self.node.srv_clients['move_line'], request, 'move_line')

    def _send_spline(self):
        request = dsr_client.move_spline_request(self.posx[1:], self.speed, self.limits.acc_ratio)
        return self.node.call_sync(self.node.srv_clients['move_spline'], request, 'move_spline_task')

    def _leg(self, target, send, label, spline=False):
        """한 번의 이동 명령을 보내고 멈출 때까지 본다. 도착이면 None, 끝내야 하면 결과."""
        node, motion = self.node, self.motion
        if not send():
            return self._send_failed(label)
        motion.sent_s = node.now_s()
        motion.moved = False
        motion.restarts = 0
        leg_start = node.last_pose[2] if node.last_pose else self.start
        goal_point = self.waypoints[target].position
        if not spline:
            self.index = target
        while True:
            time.sleep(LOOP_PERIOD_S)
            now = node.now_s()
            elapsed = now - motion.started_s
            position = node.last_pose[2] if node.last_pose else None
            points = deque(node.positions)
            motion_state.trim(points, now, node.moving_window_s)
            motion.moving_now = motion_state.is_moving(points, node.moving_eps_m, node.moving_window_s)
            if (motion_state.has_moved(points, node.moving_eps_m) and position is not None
                    and math.dist(leg_start, position) > node.moved_min_m):
                motion.moved = True
            self._track(position, spline)
            if now >= self.next_feedback:
                self.next_feedback = now + self.feedback_period
                self._publish_feedback(elapsed)

            failed = self._check(elapsed)
            if failed:
                return failed
            gap = math.dist(position, goal_point) if position is not None else None
            since_sent = now - motion.sent_s
            still = not node.moving and not motion.moving_now
            if (still and not motion.moved and since_sent > self.grace_s
                    and gap is not None and gap > self.tolerance):
                failed = self._restart(send, label)
                if failed:
                    return failed
                continue
            if still and (motion.moved or since_sent > self.grace_s):
                if gap is None:
                    return (R.REASON_ROBOT_ERROR, ReasonCode.ROBOT_ERROR,
                            f'{label}: 멈췄지만 현재 위치를 몰라 도착을 확인하지 못했다')
                if gap > self.tolerance:
                    return (R.REASON_ROBOT_ERROR, ReasonCode.ROBOT_ERROR,
                            f'{label}: 멈췄지만 경유점 {target} 에서 {gap * 1000:.1f} mm 떨어져 있다 '
                            f'(허용 {self.tolerance * 1000:.1f} mm)')
                return None

    def _restart(self, send, label):
        """출발하지 않은 명령을 move_stop 뒤 다시 보낸다(1차 restart_move 와 같은 규칙, #153)."""
        node, motion = self.node, self.motion
        if motion.restarts >= self.restart_max:
            stopped, why = node.stop_robot(f'{label} 출발 실패', motion)
            return (R.REASON_ROBOT_ERROR, ReasonCode.ROBOT_ERROR,
                    f'{label}: 출발하지 않았다. 이동 명령 {motion.restarts + 1} 번 모두 '
                    f'{self.grace_s} s 안에 움직이지 않았다' + ('' if stopped else f'. {why}'))
        motion.restarts += 1
        node.get_logger().warning(
            f'{label}: {self.grace_s} s 안에 출발하지 않았다. 다시 보낸다 ({motion.restarts}/{self.restart_max})')
        if not node.call_sync(node.srv_clients['move_stop'], dsr_client.move_stop_request(), 'move_stop'):
            return (R.REASON_ROBOT_ERROR, ReasonCode.ROBOT_ERROR, f'{label}: 재출발 전 move_stop 응답 없음')
        if not send():
            return self._send_failed(f'{label} 재출발')
        motion.sent_s = node.now_s()
        return None

    def _send_failed(self, label):
        """이동 명령이 실패 · 응답 시간 초과였다. **컨트롤러는 받았을 수 있다** — 세우고 확인한 뒤 끝낸다.

        2026-09-24 Virtual(P1-3): amovesx 100 점의 응답이 3.2 s 뒤에 왔다. CallQueue 는 0.5 s 에 포기해
        "명령 실패"로 끝내고 goal 자리를 비웠는데, 컨트롤러는 spline 을 실행 중이었다(뒤이은 amovel 이
        `state[TASK_MOTION] rejected` 알람으로 거절됨). 세우지 않으면 감시 없는 이동이 남는다.
        """
        stopped, why = self.node.stop_robot(f'{label} 명령 실패 뒤 정지 확인', self.motion)
        return (R.REASON_ROBOT_ERROR, ReasonCode.ROBOT_ERROR,
                f'{label}: 이동 명령 실패(응답 없음 또는 거절)' + ('' if stopped else f'. {why}'))

    def _check(self, elapsed):
        """취소 · 정지 요청 · 과대 외력 · 시간 초과 · 연결. 1차 watch 와 같은 순서와 약속."""
        node, motion = self.node, self.motion
        if self.goal_handle.is_cancel_requested:
            stopped, why = node.stop_robot('Action 취소', motion)
            if not stopped:            # 취소를 접수했다고 멈춘 것이 아니다
                return (R.REASON_ROBOT_ERROR, ReasonCode.ROBOT_ERROR, f'Action 취소. {why}')
            return (R.REASON_CANCELED, ReasonCode.CANCELED, 'Action 취소')
        request = node.take_stop_request()
        if request is not None:
            reason_code, detail = request
            stopped, why = node.stop_robot(f'정지 요청 ({detail})', motion)
            if not stopped:
                node.restore_stop_request(request)   # 멈췄는지 모르는 로봇에 다음 goal 을 보내지 않는다(#113)
                return (R.REASON_ROBOT_ERROR, ReasonCode.ROBOT_ERROR, f'정지 요청 ({detail}). {why}')
            return (R.REASON_STOP_REQUESTED, reason_code or ReasonCode.STOP_REQUESTED, detail)
        event = motion.event
        if event is not None and event.type == ContactEvent.TYPE_OVER_FORCE:
            stopped, why = node.stop_robot('과대 외력', motion)
            if not stopped:
                return (R.REASON_ROBOT_ERROR, ReasonCode.ROBOT_ERROR,
                        f'과대 외력 {event.force_delta_n:.2f} N. {why}')
            return (R.REASON_OVER_FORCE, ReasonCode.OVER_FORCE, f'과대 외력 {event.force_delta_n:.2f} N')
        if elapsed > self.timeout_s:
            stopped, why = node.stop_robot('제한 시간 초과', motion)
            if not stopped:
                return (R.REASON_ROBOT_ERROR, ReasonCode.ROBOT_ERROR,
                        f'{self.timeout_s:.1f} s 안에 끝나지 않았다. {why}')
            return (R.REASON_TIMEOUT, ReasonCode.TIMEOUT, f'{self.timeout_s:.1f} s 안에 끝나지 않았다')
        if not node.connected:
            return (R.REASON_ROBOT_ERROR, ReasonCode.ROBOT_DISCONNECTED, '로봇 연결이 끊겼다')
        return None

    # ---- 진행 · feedback ----------------------------------------------------
    def _track(self, position, spline):
        """진행 거리와 향하는 점. line 은 보낸 점이 곧 향하는 점, spline 은 위치로 추정한다(계약 허용)."""
        if position is None:
            return
        p = paths.progress(position, self.start, self.waypoints, from_index=self.index)
        self.distance_m = max(self.distance_m, p.distance_m)
        if spline:
            self.index = max(self.index, p.waypoint_index)
            self.waypoints_done = max(self.waypoints_done, p.waypoints_done)

    def _publish_feedback(self, elapsed):
        node = self.node
        feedback = ExecutePath.Feedback()
        if node.last_pose:
            feedback.pose, feedback.pose_stamp = node.last_pose[0], node.last_pose[1]
        feedback.frame_id = node.frame_id
        feedback.distance_travelled = self.distance_m
        feedback.waypoint_index = self.index
        feedback.elapsed.sec = int(elapsed)
        feedback.elapsed.nanosec = int((elapsed % 1.0) * 1e9)
        self.goal_handle.publish_feedback(feedback)
