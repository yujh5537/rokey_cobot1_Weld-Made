import json
import os
import time

import paho.mqtt.client as mqtt


# =========================
# MQTT Broker 설정
# =========================

# 환경변수가 없으면 Web PC 자신의 Mosquitto를 사용한다.
MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

# 테스트용 scan ID
SCAN_ID = "20260918-172640-4821"


def now_ms():
    """현재 시간을 epoch millisecond로 반환한다."""
    return int(time.time() * 1000)


def publish_message(
        client,
        topic,
        message,
        qos=1,
        retain=False,
    ):
    
    """JSON 메시지를 MQTT로 발행한다."""

    payload = json.dumps(
        message,
        ensure_ascii=False,
    )

    result = client.publish(
        topic,
        payload,
        qos=qos,
        retain=retain,
    )

    result.wait_for_publish()

    print(f"[PUBLISH] {topic}")
    print(payload)
    print()


# =========================
# 1. scan/state
# =========================

def publish_scan_state(client):
    timestamp = now_ms()

    message = {
        "schema_version": "0.1",
        "stamp_ms": timestamp,
        "scan_id": SCAN_ID,
        "phase": "EDGE_SEARCH",
        "direction": "POS_X",
        "progress": 1,
        "progress_total": 4,
        "motion_id": 7,
        "published_at_ms": timestamp,
    }

    # 계약:
    # QoS 1
    # retain true
    publish_message(
        client,
        "scan/state",
        message,
        qos=1,
        retain=True,
    )


# =========================
# 2. robot/sample
# =========================

def publish_robot_sample(client):
    timestamp = now_ms()

    message = {
        "schema_version": "0.1",
        "sample_id": 48211,
        "frame_id": "base_link",
        "pose": {
            "x_mm": 412.35,
            "y_mm": -20.10,
            "z_mm": 85.02,
            "qx": 0.0,
            "qy": 1.0,
            "qz": 0.0,
            "qw": 0.0,
        },
        "pose_stamp_ms": timestamp,
        "wrench": {
            "fx_n": 0.4,
            "fy_n": -0.2,
            "fz_n": -3.9,
            "tx_nm": 0.01,
            "ty_nm": 0.0,
            "tz_nm": 0.0,
        },
        "force_stamp_ms": timestamp,
        "valid": True,
        "motion_id": 7,
        "operation": "SLIDE",
        "published_at_ms": timestamp,
    }

    # 계약:
    # QoS 0
    # retain false
    publish_message(
        client,
        "robot/sample",
        message,
        qos=0,
        retain=False,
    )


# =========================
# 3. contact/event
# =========================

def publish_contact_event(client):
    timestamp = now_ms()

    message = {
        "schema_version": "0.1",
        "event_id": 12,
        "scan_id": SCAN_ID,
        "motion_id": 7,
        "sample_id": 48230,
        "type": "EDGE",
        "source": "robot_force",
        "frame_id": "base_link",
        "pose": {
            "x_mm": 461.80,
            "y_mm": -20.11,
            "z_mm": 84.41,
            "qx": 0.0,
            "qy": 1.0,
            "qz": 0.0,
            "qw": 0.0,
        },
        "wrench": {
            "fx_n": 0.3,
            "fy_n": -0.1,
            "fz_n": -1.1,
            "tx_nm": 0.0,
            "ty_nm": 0.0,
            "tz_nm": 0.0,
        },
        "pose_stamp_ms": timestamp,
        "force_stamp_ms": timestamp,
        "detect_stamp_ms": timestamp,
        "force_delta_n": 1.2,
        "z_drop_mm": 0.61,
        "z_drop_valid": True,
        "debounce_count": 3,
        "published_at_ms": timestamp,
    }

    publish_message(
        client,
        "contact/event",
        message,
        qos=1,
        retain=False,
    )


# =========================
# 4. scan/result
# =========================

def publish_scan_result(client):
    timestamp = now_ms()

    message = {
        "schema_version": "0.1",
        "scan_id": SCAN_ID,
        "stamp_ms": timestamp,
        "success": True,
        "reason_code": 0,
        "reason": "OK",
        "detail": "",
        "frame_id": "workpiece_fixture",

        "z_top_mm": 50.0,
        "z_top_valid": True,

        "x_pos_mm": 100.0,
        "x_pos_valid": True,

        "x_neg_mm": 0.0,
        "x_neg_valid": True,

        "y_pos_mm": 60.0,
        "y_pos_valid": True,

        "y_neg_mm": 0.0,
        "y_neg_valid": True,

        "width_mm": 100.0,
        "length_mm": 60.0,
        "height_mm": 50.0,
        "dims_valid": True,

        "support_z_mm": 0.0,
        "support_z_valid": True,

        "vertices": [
            {"x_mm": 0.0, "y_mm": 0.0, "z_mm": 50.0},
            {"x_mm": 100.0, "y_mm": 0.0, "z_mm": 50.0},
            {"x_mm": 100.0, "y_mm": 60.0, "z_mm": 50.0},
            {"x_mm": 0.0, "y_mm": 60.0, "z_mm": 50.0},
            {"x_mm": 0.0, "y_mm": 0.0, "z_mm": 0.0},
            {"x_mm": 100.0, "y_mm": 0.0, "z_mm": 0.0},
            {"x_mm": 100.0, "y_mm": 60.0, "z_mm": 0.0},
            {"x_mm": 0.0, "y_mm": 60.0, "z_mm": 0.0},
        ],

        "box_valid": True,

        "edges": [
            # 윗면 4개
            {
                "start": {"x_mm": 0.0, "y_mm": 0.0, "z_mm": 50.0},
                "end": {"x_mm": 100.0, "y_mm": 0.0, "z_mm": 50.0},
                "length_mm": 100.0,
                "valid": True,
            },
            {
                "start": {"x_mm": 100.0, "y_mm": 0.0, "z_mm": 50.0},
                "end": {"x_mm": 100.0, "y_mm": 60.0, "z_mm": 50.0},
                "length_mm": 60.0,
                "valid": True,
            },
            {
                "start": {"x_mm": 100.0, "y_mm": 60.0, "z_mm": 50.0},
                "end": {"x_mm": 0.0, "y_mm": 60.0, "z_mm": 50.0},
                "length_mm": 100.0,
                "valid": True,
            },
            {
                "start": {"x_mm": 0.0, "y_mm": 60.0, "z_mm": 50.0},
                "end": {"x_mm": 0.0, "y_mm": 0.0, "z_mm": 50.0},
                "length_mm": 60.0,
                "valid": True,
            },

            # 아랫면 4개
            {
                "start": {"x_mm": 0.0, "y_mm": 0.0, "z_mm": 0.0},
                "end": {"x_mm": 100.0, "y_mm": 0.0, "z_mm": 0.0},
                "length_mm": 100.0,
                "valid": True,
            },
            {
                "start": {"x_mm": 100.0, "y_mm": 0.0, "z_mm": 0.0},
                "end": {"x_mm": 100.0, "y_mm": 60.0, "z_mm": 0.0},
                "length_mm": 60.0,
                "valid": True,
            },
            {
                "start": {"x_mm": 100.0, "y_mm": 60.0, "z_mm": 0.0},
                "end": {"x_mm": 0.0, "y_mm": 60.0, "z_mm": 0.0},
                "length_mm": 100.0,
                "valid": True,
            },
            {
                "start": {"x_mm": 0.0, "y_mm": 60.0, "z_mm": 0.0},
                "end": {"x_mm": 0.0, "y_mm": 0.0, "z_mm": 0.0},
                "length_mm": 60.0,
                "valid": True,
            },

            # 수직 방향 4개
            {
                "start": {"x_mm": 0.0, "y_mm": 0.0, "z_mm": 50.0},
                "end": {"x_mm": 0.0, "y_mm": 0.0, "z_mm": 0.0},
                "length_mm": 50.0,
                "valid": True,
            },
            {
                "start": {"x_mm": 100.0, "y_mm": 0.0, "z_mm": 50.0},
                "end": {"x_mm": 100.0, "y_mm": 0.0, "z_mm": 0.0},
                "length_mm": 50.0,
                "valid": True,
            },
            {
                "start": {"x_mm": 100.0, "y_mm": 60.0, "z_mm": 50.0},
                "end": {"x_mm": 100.0, "y_mm": 60.0, "z_mm": 0.0},
                "length_mm": 50.0,
                "valid": True,
            },
            {
                "start": {"x_mm": 0.0, "y_mm": 60.0, "z_mm": 50.0},
                "end": {"x_mm": 0.0, "y_mm": 60.0, "z_mm": 0.0},
                "length_mm": 50.0,
                "valid": True,
            },
        ],

        "path_candidates": [
            {
                "start": {"x_mm": 0.0, "y_mm": 0.0, "z_mm": 50.0},
                "end": {"x_mm": 100.0, "y_mm": 0.0, "z_mm": 50.0},
                "length_mm": 100.0,
                "valid": True,
            },
            {
                "start": {"x_mm": 100.0, "y_mm": 0.0, "z_mm": 50.0},
                "end": {"x_mm": 100.0, "y_mm": 60.0, "z_mm": 50.0},
                "length_mm": 60.0,
                "valid": True,
            },
            {
                "start": {"x_mm": 100.0, "y_mm": 60.0, "z_mm": 50.0},
                "end": {"x_mm": 0.0, "y_mm": 60.0, "z_mm": 50.0},
                "length_mm": 100.0,
                "valid": True,
            },
            {
                "start": {"x_mm": 0.0, "y_mm": 60.0, "z_mm": 50.0},
                "end": {"x_mm": 0.0, "y_mm": 0.0, "z_mm": 50.0},
                "length_mm": 60.0,
                "valid": True,
            },
        ],

        "config": {
            "contact_threshold_n": 4.0,
            "edge_drop_mm": 0.5,
            "debounce_n": 3,
            "over_force_n": 30.0,
            "descend_speed_mmps": 5.0,
            "slide_speed_mmps": 10.0,
            "max_descend_mm": 80.0,
            "max_slide_mm": 150.0,
            "motion_timeout_s": 30.0,
            "lift_height_mm": 50.0,
            "target_force_n": 5.0,
            "drop_limit_mm": 5.0,
        },

        "started_at_ms": timestamp - 60000,
        "finished_at_ms": timestamp,
        "published_at_ms": timestamp,
    }

    publish_message(
        client,
        "scan/result",
        message,
        qos=1,
        retain=False,
    )


# =========================
# 5. scan/log
# =========================

def publish_scan_log(client):
    timestamp = now_ms()

    message = {
        "schema_version": "0.1",
        "stamp_ms": timestamp,
        "scan_id": SCAN_ID,
        "level": "INFO",
        "phase": "EDGE_SEARCH",
        "direction": "POS_X",
        "motion_id": 7,
        "code": 0,
        "code_name": "OK",
        "message": "edge +x 판정 좌표 기록",
        "frame_id": "base_link",
        "pose": {
            "x_mm": 461.80,
            "y_mm": -20.11,
            "z_mm": 84.41,
            "qx": 0.0,
            "qy": 1.0,
            "qz": 0.0,
            "qw": 0.0,
        },
        "pose_valid": True,
        "published_at_ms": timestamp,
    }

    publish_message(
        client,
        "scan/log",
        message,
        qos=1,
        retain=False,
    )


# =========================
# 프로그램 시작
# =========================

def main():
    print("MQTT Mock Publisher 시작")
    print(f"Broker: {MQTT_HOST}:{MQTT_PORT}")
    print()

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2
    )

    client.connect(
        MQTT_HOST,
        MQTT_PORT,
        60,
    )

    client.loop_start()

    # 연결 직후 잠깐 기다린다.
    time.sleep(0.5)

    # T12 요구사항 5종 발행
    publish_scan_state(client)
    time.sleep(0.3)

    publish_robot_sample(client)
    time.sleep(0.3)

    publish_contact_event(client)
    time.sleep(0.3)

    publish_scan_result(client)
    time.sleep(0.3)

    publish_scan_log(client)

    client.loop_stop()
    client.disconnect()

    print("5개 MQTT 테스트 메시지 발행 완료")


if __name__ == "__main__":
    main()