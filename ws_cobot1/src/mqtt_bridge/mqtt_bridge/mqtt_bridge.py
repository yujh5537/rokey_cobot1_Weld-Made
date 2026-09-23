"""ROS 2 <-> MQTT bridge node."""

import json
import os
import queue
import time
from functools import partial

import paho.mqtt.client as mqtt
import rclpy
from builtin_interfaces.msg import Time
from contact_scan_interfaces.action import Resume, ReturnHome, RunScan
from contact_scan_interfaces.msg import (
    ContactEvent, ReasonCode, RobotSample, RobotStatus, SafetyStatus,
    ScanConfig, ScanLog, ScanResult, ScanState, WebHeartbeat,
)
from contact_scan_interfaces.srv import ResetSafety, SetConfig, StopScan
from contact_scan_qos import QOS_EVENT, QOS_HEARTBEAT, QOS_LOG, QOS_SENSOR, QOS_STATE
from rclpy.action import ActionClient
from rclpy.node import Node

from mqtt_bridge.command_guard import CommandGuard
from mqtt_bridge.decoders import (
    decode_safety_reset, decode_scan_home, decode_scan_resume,
    decode_scan_set_config, decode_scan_start, decode_scan_stop,
    decode_web_connection, decode_web_heartbeat,
)
from mqtt_bridge.encoders import (
    encode_command_ack, encode_command_result, encode_contact_event,
    encode_robot_sample, encode_robot_status, encode_ros_connection,
    encode_ros_heartbeat, encode_safety_status, encode_scan_log,
    encode_scan_result, encode_scan_state,
)


def now_ms():
    return int(time.time() * 1000)


def normalize_topic_prefix(prefix):
    return prefix.strip("/")


def prefixed_topic(prefix, topic):
    prefix = normalize_topic_prefix(prefix)
    topic = topic.lstrip("/")
    return f"{prefix}/{topic}" if prefix else topic


def strip_topic_prefix(prefix, topic):
    prefix = normalize_topic_prefix(prefix)
    topic = topic.lstrip("/")
    marker = prefix + "/"
    return topic[len(marker):] if prefix and topic.startswith(marker) else topic


def serialize_json(message):
    return json.dumps(message, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def epoch_ms_to_time(timestamp_ms):
    stamp = Time()
    stamp.sec = int(timestamp_ms // 1000)
    stamp.nanosec = int((timestamp_ms % 1000) * 1_000_000)
    return stamp


def _time_dict(stamp):
    return {"sec": int(stamp.sec), "nanosec": int(stamp.nanosec)}


def _point_dict(point):
    return {"x": point.x, "y": point.y, "z": point.z}


def _pose_dict(pose):
    return {
        "x": pose.position.x, "y": pose.position.y, "z": pose.position.z,
        "qx": pose.orientation.x, "qy": pose.orientation.y,
        "qz": pose.orientation.z, "qw": pose.orientation.w,
    }


def _wrench_dict(wrench):
    return {
        "fx": wrench.force.x, "fy": wrench.force.y, "fz": wrench.force.z,
        "tx": wrench.torque.x, "ty": wrench.torque.y, "tz": wrench.torque.z,
    }


def _scan_config_dict(config):
    return {
        "contact_threshold_n": config.contact_threshold_n,
        "edge_drop_m": config.edge_drop_m,
        "debounce_n": config.debounce_n,
        "debounce_set": config.debounce_set,
        "over_force_n": config.over_force_n,
        "descend_speed_mps": config.descend_speed_mps,
        "slide_speed_mps": config.slide_speed_mps,
        "max_descend_m": config.max_descend_m,
        "max_slide_m": config.max_slide_m,
        "motion_timeout_s": config.motion_timeout_s,
        "lift_height_m": config.lift_height_m,
        "target_force_n": config.target_force_n,
        "drop_limit_m": config.drop_limit_m,
    }


def _segment_dict(segment):
    return {
        "start": _point_dict(segment.start),
        "end": _point_dict(segment.end),
        "length": segment.length,
        "valid": segment.valid,
    }


def _scan_result_dict(msg):
    return {
        "scan_id": msg.scan_id,
        "stamp": _time_dict(msg.stamp),
        "success": msg.success,
        "reason_code": msg.reason_code,
        "detail": msg.detail,
        "frame_id": msg.frame_id,
        "z_top": msg.z_top, "z_top_valid": msg.z_top_valid,
        "x_pos": msg.x_pos, "x_pos_valid": msg.x_pos_valid,
        "x_neg": msg.x_neg, "x_neg_valid": msg.x_neg_valid,
        "y_pos": msg.y_pos, "y_pos_valid": msg.y_pos_valid,
        "y_neg": msg.y_neg, "y_neg_valid": msg.y_neg_valid,
        "width": msg.width, "length": msg.length, "height": msg.height,
        "dims_valid": msg.dims_valid,
        "support_z": msg.support_z, "support_z_valid": msg.support_z_valid,
        "vertices": [_point_dict(v) for v in msg.vertices],
        "box_valid": msg.box_valid,
        "edges": [_segment_dict(e) for e in msg.edges],
        "path_candidates": [_segment_dict(e) for e in msg.path_candidates],
        "config": _scan_config_dict(msg.config),
        "started_at": _time_dict(msg.started_at),
        "finished_at": _time_dict(msg.finished_at),
    }


def _scan_config_from_patch(patch):
    config = ScanConfig()
    for key, value in patch.items():
        if not hasattr(config, key):
            raise ValueError(f"ScanConfig has no field: {key}")
        setattr(config, key, value)
    return config


def _safe_ros_callback(logger, topic, callback):
    """구독 콜백 예외가 executor 밖으로 전파되어 노드를 죽이지 않게 한다."""
    def wrapped(msg):
        try:
            return callback(msg)
        except Exception as exc:
            logger.error(f"{topic} callback failed: {exc}")
            return None

    return wrapped


def _scan_result_dedup_key(msg):
    """같은 scan_id라도 서로 다른 종료 결과는 통과시키는 dedup 키."""
    return (msg.scan_id, int(msg.stamp.sec), int(msg.stamp.nanosec))


class MqttBridge(Node):
    def __init__(self):
        super().__init__("mqtt_bridge")

        for name, default in (
            ("broker_host", "127.0.0.1"), ("broker_port", 1883),
            ("topic_prefix", ""), ("dedup_cache_size", 100),
            ("cmd_expiry_s", 5.0), ("sample_publish_hz", 10.0),
            ("heartbeat_hz", 1.0), ("keepalive_s", 60),
        ):
            self.declare_parameter(name, default)

        self._host = str(self.get_parameter("broker_host").value)
        self._port = int(self.get_parameter("broker_port").value)
        self._prefix = normalize_topic_prefix(str(self.get_parameter("topic_prefix").value))
        self._sample_hz = float(self.get_parameter("sample_publish_hz").value)
        self._heartbeat_hz = float(self.get_parameter("heartbeat_hz").value)
        self._keepalive = int(self.get_parameter("keepalive_s").value)

        self._dedup_cache_size = int(self.get_parameter("dedup_cache_size").value)
        self._guard = CommandGuard(
            self._dedup_cache_size,
            float(self.get_parameter("cmd_expiry_s").value),
        )
        self._queue = queue.SimpleQueue()
        self._mqtt_connected = False
        self._heartbeat_seq = 0
        self._sample_period = 1.0 / self._sample_hz
        self._last_sample = 0.0
        self._last_scan_id = ""
        self._scan_phase = ScanState.PHASE_IDLE
        self._pending_stop = []

        self._last_error_scan_id = ""
        self._last_error_code = ReasonCode.ROBOT_ERROR
        self._last_error_detail = ""

        self._recent_results = []

        self.create_subscription(
            RobotSample, "/robot/sample",
            _safe_ros_callback(self.get_logger(), "/robot/sample", self._on_robot_sample),
            QOS_SENSOR,
        )
        self.create_subscription(
            RobotStatus, "/robot/status",
            _safe_ros_callback(self.get_logger(), "/robot/status", self._on_robot_status),
            QOS_STATE,
        )
        self.create_subscription(
            ScanState, "/scan/state",
            _safe_ros_callback(self.get_logger(), "/scan/state", self._on_scan_state),
            QOS_STATE,
        )
        self.create_subscription(
            ScanResult, "/scan/result",
            _safe_ros_callback(self.get_logger(), "/scan/result", self._on_scan_result),
            QOS_STATE,
        )
        self.create_subscription(
            ScanLog, "/scan/log",
            _safe_ros_callback(self.get_logger(), "/scan/log", self._on_scan_log),
            QOS_LOG,
        )
        self.create_subscription(
            ContactEvent, "/contact/event",
            _safe_ros_callback(self.get_logger(), "/contact/event", self._on_contact_event),
            QOS_EVENT,
        )
        self.create_subscription(
            SafetyStatus, "/safety/status",
            _safe_ros_callback(self.get_logger(), "/safety/status", self._on_safety_status),
            QOS_STATE,
        )

        self._heartbeat_pub = self.create_publisher(WebHeartbeat, "/web/heartbeat", QOS_HEARTBEAT)
        self._run_client = ActionClient(self, RunScan, "/scan/run")
        self._home_client = ActionClient(self, ReturnHome, "/scan/home")
        self._resume_client = ActionClient(self, Resume, "/scan/resume")
        self._stop_client = self.create_client(StopScan, "/scan/stop")
        self._set_config_client = self.create_client(SetConfig, "/scan/set_config")
        self._reset_client = self.create_client(ResetSafety, "/safety/reset")

        self.create_timer(0.02, self._drain_queue)
        self.create_timer(1.0 / self._heartbeat_hz, self._publish_heartbeat)

        self._mqtt = mqtt.Client(client_id=f"mqtt_bridge-{os.getpid()}", clean_session=True)
        self._mqtt.on_connect = self._on_mqtt_connect
        self._mqtt.on_disconnect = self._on_mqtt_disconnect
        self._mqtt.on_message = self._on_mqtt_message
        self._mqtt.reconnect_delay_set(min_delay=1, max_delay=10)
        self._mqtt.will_set(
            self._topic("conn/ros"),
            serialize_json(encode_ros_connection(False, now_ms())),
            qos=1,
            retain=True,
        )
        self._mqtt.connect_async(self._host, self._port, keepalive=self._keepalive)
        self._mqtt.loop_start()

    def _topic(self, topic):
        return prefixed_topic(self._prefix, topic)

    def _publish(self, topic, message, qos, retain):
        try:
            payload = serialize_json(message)
        except (TypeError, ValueError) as exc:
            self.get_logger().error(f"serialize {topic} failed: {exc}")
            return None
        return self._mqtt.publish(self._topic(topic), payload, qos=qos, retain=retain)

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        del userdata, flags
        if rc != 0:
            self.get_logger().error(f"MQTT connect failed: rc={rc}")
            return
        self._mqtt_connected = True
        client.subscribe([
            (self._topic("cmd/scan/+"), 1),
            (self._topic("cmd/safety/reset"), 1),
            (self._topic("hb/web"), 0),
            (self._topic("conn/web"), 1),
        ])
        self._publish("conn/ros", encode_ros_connection(True, now_ms()), 1, True)

    def _on_mqtt_disconnect(self, client, userdata, rc):
        del client, userdata, rc
        self._mqtt_connected = False

    def _on_mqtt_message(self, client, userdata, message):
        del client, userdata
        try:
            body = json.loads(message.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        self._queue.put((strip_topic_prefix(self._prefix, message.topic), body))

    def _drain_queue(self):
        while True:
            try:
                topic, body = self._queue.get_nowait()
            except queue.Empty:
                return
            self._handle_mqtt(topic, body)

    def _handle_mqtt(self, topic, body):
        request_id = body.get("request_id", "") if isinstance(body, dict) else ""
        try:
            if topic == "hb/web":
                data = decode_web_heartbeat(body)
                msg = WebHeartbeat()
                msg.session_id = data["session_id"]
                msg.seq = data["seq"]
                msg.stamp = epoch_ms_to_time(data["timestamp_ms"])
                msg.received_stamp = self.get_clock().now().to_msg()
                self._heartbeat_pub.publish(msg)
                return

            if topic == "conn/web":
                decode_web_connection(body)
                return

            if not topic.startswith("cmd/"):
                return

            guard = self._guard.validate(topic, body)
            if not guard.accepted:
                self._ack(request_id, False, guard.reason_code, guard.detail)
                return

            if topic == "cmd/scan/start":
                data = decode_scan_start(body)
                goal = RunScan.Goal()
                goal.request_id = data["request_id"]
                goal.use_override = data["use_override"]
                goal.config_override = _scan_config_from_patch(data["config_override"])
                self._send_action("start", self._run_client, goal, request_id)
            elif topic == "cmd/scan/home":
                data = decode_scan_home(body)
                goal = ReturnHome.Goal()
                goal.request_id = data["request_id"]
                self._send_action("home", self._home_client, goal, request_id)
            elif topic == "cmd/scan/resume":
                data = decode_scan_resume(body)
                goal = Resume.Goal()
                goal.request_id = data["request_id"]
                goal.scan_id = data["scan_id"]
                self._send_action("resume", self._resume_client, goal, request_id)
            elif topic == "cmd/scan/stop":
                self._dispatch_stop(body)
            elif topic == "cmd/scan/set_config":
                self._dispatch_set_config(body)
            elif topic == "cmd/safety/reset":
                self._dispatch_reset(body)
            else:
                self._ack(request_id, False, ReasonCode.NOT_SUPPORTED, "unsupported command")
        except Exception as exc:
            if topic.startswith("cmd/"):
                self._ack(request_id, False, ReasonCode.INVALID_REQUEST, str(exc))
            else:
                self.get_logger().error(f"MQTT {topic} handling failed: {exc}")

    def _send_action(self, kind, client, goal, request_id):
        if not client.server_is_ready():
            self._ack(request_id, False, ReasonCode.NOT_SUPPORTED, f"{kind} server unavailable")
            return
        future = client.send_goal_async(goal)
        future.add_done_callback(partial(self._on_goal_response, kind, request_id))

    def _on_goal_response(self, kind, request_id, future):
        try:
            handle = future.result()
        except Exception as exc:
            self._ack(request_id, False, ReasonCode.ROBOT_ERROR, str(exc))
            return
        if not handle.accepted:
            self._ack(
                request_id,
                False,
                ReasonCode.BUSY,
                f"{kind} goal rejected (reason not transported)",
            )
            return
        self._ack(request_id, True, ReasonCode.OK, "")
        result_future = handle.get_result_async()
        result_future.add_done_callback(partial(self._on_action_result, request_id))

    def _on_action_result(self, request_id, future):
        try:
            result = future.result().result
            self._command_result(
                request_id,
                getattr(result, "scan_id", ""),
                bool(result.success),
                int(result.reason_code),
                result.detail,
            )
        except Exception as exc:
            self._command_result(request_id, "", False, ReasonCode.ROBOT_ERROR, str(exc))

    def _dispatch_stop(self, body):
        data = decode_scan_stop(body)
        if not self._stop_client.service_is_ready():
            self._ack(data["request_id"], False, ReasonCode.NOT_SUPPORTED, "stop service unavailable")
            return
        req = StopScan.Request()
        req.request_id = data["request_id"]
        req.requester = data["requester"]
        req.reason = data["reason"]
        req.detail = data["detail"]
        future = self._stop_client.call_async(req)
        future.add_done_callback(partial(
            self._on_stop_response,
            data["request_id"],
            self._scan_phase,
            self._last_scan_id,
        ))

    def _on_stop_response(
        self,
        request_id,
        request_phase,
        request_scan_id,
        future,
    ):
        try:
            response = future.result()
        except Exception as exc:
            self._ack(request_id, False, ReasonCode.ROBOT_ERROR, str(exc))
            return

        self._ack(
            request_id,
            bool(response.accepted),
            int(response.reason_code),
            response.detail,
        )

        if not response.accepted:
            return

        idle_phases = (
            ScanState.PHASE_IDLE,
            ScanState.PHASE_DONE,
            ScanState.PHASE_ERROR,
            ScanState.PHASE_STOPPED,
        )

        if request_phase in idle_phases:
            self._command_result(
                request_id,
                request_scan_id,
                True,
                ReasonCode.STOP_REQUESTED,
                response.detail,
            )
            return

        self._pending_stop.append((request_id, request_scan_id))

        if self._last_scan_id != request_scan_id:
            return

        if self._scan_phase == ScanState.PHASE_STOPPED:
            self._finish_stops(
                request_scan_id,
                True,
                ReasonCode.STOP_REQUESTED,
                "",
            )
        elif self._scan_phase == ScanState.PHASE_ERROR:
            reason_code, detail = self._stop_error(request_scan_id)
            self._finish_stops(
                request_scan_id,
                False,
                reason_code,
                detail,
            )

    def _dispatch_set_config(self, body):
        data = decode_scan_set_config(body)
        if not self._set_config_client.service_is_ready():
            self._ack(data["request_id"], False, ReasonCode.NOT_SUPPORTED, "set_config unavailable")
            return
        req = SetConfig.Request()
        req.request_id = data["request_id"]
        req.config = _scan_config_from_patch(data["config"])
        future = self._set_config_client.call_async(req)
        future.add_done_callback(partial(self._on_set_config_response, data["request_id"]))

    def _on_set_config_response(self, request_id, future):
        try:
            response = future.result()
        except Exception as exc:
            self._ack(request_id, False, ReasonCode.ROBOT_ERROR, str(exc))
            return
        applied = _scan_config_dict(response.applied) if response.success else None
        self._ack(request_id, bool(response.success), int(response.reason_code), response.detail, applied)

    def _dispatch_reset(self, body):
        data = decode_safety_reset(body)
        if not self._reset_client.service_is_ready():
            self._ack(data["request_id"], False, ReasonCode.NOT_SUPPORTED, "safety reset unavailable")
            return
        req = ResetSafety.Request()
        req.request_id = data["request_id"]
        req.detail = data["detail"]
        future = self._reset_client.call_async(req)
        future.add_done_callback(partial(self._on_reset_response, data["request_id"]))

    def _on_reset_response(self, request_id, future):
        try:
            response = future.result()
        except Exception as exc:
            self._ack(request_id, False, ReasonCode.ROBOT_ERROR, str(exc))
            return
        self._ack(request_id, bool(response.success), int(response.reason_code), response.detail)

    def _on_robot_sample(self, msg):
        now = time.monotonic()
        if now - self._last_sample < self._sample_period:
            return
        self._last_sample = now
        data = {
            "sample_id": msg.sample_id, "frame_id": msg.frame_id,
            "pose": _pose_dict(msg.pose), "pose_stamp": _time_dict(msg.pose_stamp),
            "wrench": _wrench_dict(msg.wrench), "force_stamp": _time_dict(msg.force_stamp),
            "valid": msg.valid, "motion_id": msg.motion_id, "operation": msg.operation,
        }
        self._publish("robot/sample", encode_robot_sample(data, now_ms()), 0, False)

    def _on_robot_status(self, msg):
        data = {
            "stamp": _time_dict(msg.stamp), "connected": msg.connected,
            "moving": msg.moving, "error": msg.error, "error_code": msg.error_code,
            "compliance_active": msg.compliance_active,
            "force_ctrl_active": msg.force_ctrl_active,
            "motion_id": msg.motion_id, "operation": msg.operation, "detail": msg.detail,
            # SLIDE 누름 목표 (계약 3.2, v0.1.19). 셋은 서로 다른 값이라 합치지 않는다
            "slide_mode": msg.slide_mode,
            "slide_force_setpoint_n": msg.slide_force_setpoint_n,
            "slide_force_baseline_n": msg.slide_force_baseline_n,
            "slide_force_estimate_n": msg.slide_force_estimate_n,
            "step_press_lo_n": msg.step_press_lo_n,
            "step_press_hi_n": msg.step_press_hi_n,
        }
        self._publish("robot/status", encode_robot_status(data, now_ms()), 1, True)

    def _on_scan_state(self, msg):
        self._scan_phase = msg.phase
        self._last_scan_id = msg.scan_id

        data = {
            "stamp": _time_dict(msg.stamp),
            "scan_id": msg.scan_id,
            "phase": msg.phase,
            "direction": msg.direction,
            "progress": msg.progress,
            "progress_total": msg.progress_total,
            "motion_id": msg.motion_id,
        }

        self._publish(
            "scan/state",
            encode_scan_state(data, now_ms()),
            1,
            True,
        )

        if msg.phase == ScanState.PHASE_STOPPED:
            self._finish_stops(
                msg.scan_id,
                True,
                ReasonCode.STOP_REQUESTED,
                "",
            )

        elif msg.phase == ScanState.PHASE_ERROR:
            reason_code, detail = self._stop_error(msg.scan_id)

            self._finish_stops(
                msg.scan_id,
                False,
                reason_code,
                detail,
            )

    def _stop_error(self, scan_id):
        if self._last_error_scan_id == scan_id:
            return self._last_error_code, self._last_error_detail

        return ReasonCode.ROBOT_ERROR, ""

    def _finish_stops(self, scan_id, success, reason_code, detail):
        remaining = []

        for request_id, pending_scan_id in self._pending_stop:
            if pending_scan_id != scan_id:
                remaining.append((request_id, pending_scan_id))
                continue

            self._command_result(
                request_id,
                scan_id,
                success,
                reason_code,
                detail,
            )

        self._pending_stop = remaining

    def _on_scan_result(self, msg):
        result_key = _scan_result_dedup_key(msg)
        if msg.scan_id and result_key in self._recent_results:
            return
        if msg.scan_id:
            self._recent_results.append(result_key)
            self._recent_results = self._recent_results[-self._dedup_cache_size:]
        self._publish("scan/result", encode_scan_result(_scan_result_dict(msg), now_ms()), 1, False)

    def _on_scan_log(self, msg):
        if msg.level == ScanLog.LEVEL_ERROR and msg.scan_id:
            self._last_error_scan_id = msg.scan_id
            self._last_error_code = (
                int(msg.code)
                if int(msg.code) != ReasonCode.OK
                else ReasonCode.ROBOT_ERROR
            )
            self._last_error_detail = msg.message

        data = {
            "stamp": _time_dict(msg.stamp),
            "scan_id": msg.scan_id,
            "level": msg.level,
            "phase": msg.phase,
            "direction": msg.direction,
            "motion_id": msg.motion_id,
            "code": msg.code,
            "message": msg.message,
            "frame_id": msg.frame_id,
            "pose": _pose_dict(msg.pose),
            "pose_valid": msg.pose_valid,
        }

        self._publish(
            "scan/log",
            encode_scan_log(data, now_ms()),
            1,
            False,
        )

    def _on_contact_event(self, msg):
        data = {
            "event_id": msg.event_id, "scan_id": msg.scan_id,
            "motion_id": msg.motion_id, "sample_id": msg.sample_id,
            "type": msg.type, "source": msg.source, "frame_id": msg.frame_id,
            "pose": _pose_dict(msg.pose), "wrench": _wrench_dict(msg.wrench),
            "pose_stamp": _time_dict(msg.pose_stamp),
            "force_stamp": _time_dict(msg.force_stamp),
            "detect_stamp": _time_dict(msg.detect_stamp),
            "force_delta_n": msg.force_delta_n,
            "z_drop_m": msg.z_drop_m, "z_drop_valid": msg.z_drop_valid,
            "debounce_count": msg.debounce_count,
        }
        self._publish("contact/event", encode_contact_event(data, now_ms()), 1, False)

    def _on_safety_status(self, msg):
        data = {
            "stamp": _time_dict(msg.stamp), "level": msg.level,
            "reason_code": msg.reason_code, "stop_required": msg.stop_required,
            "stop_confirmed": msg.stop_confirmed, "latched": msg.latched,
            "motion_id": msg.motion_id, "position": _point_dict(msg.position),
            "position_valid": msg.position_valid, "detail": msg.detail,
        }
        self._publish("safety/status", encode_safety_status(data, now_ms()), 1, True)

    def _ack(self, request_id, accepted, code, detail, applied=None):
        self._publish(
            "cmd/ack",
            encode_command_ack(request_id, accepted, code, detail, now_ms(), applied),
            1,
            False,
        )

    def _command_result(self, request_id, scan_id, success, code, detail):
        self._publish(
            "scan/command_result",
            encode_command_result(request_id, scan_id, success, code, detail, now_ms()),
            1,
            False,
        )

    def _publish_heartbeat(self):
        self._heartbeat_seq = (self._heartbeat_seq + 1) % (2 ** 32)
        self._publish("hb/ros", encode_ros_heartbeat(self._heartbeat_seq, now_ms()), 0, False)

    def destroy_node(self):
        try:
            if hasattr(self, "_mqtt"):
                if self._mqtt_connected:
                    info = self._publish("conn/ros", encode_ros_connection(False, now_ms()), 1, True)
                    if info is not None:
                        try:
                            info.wait_for_publish(timeout=1.0)
                        except Exception:
                            pass
                self._mqtt.disconnect()
                self._mqtt.loop_stop()
        finally:
            super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = MqttBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
