import asyncio
import json
import os
import time
from threading import Lock
from typing import Any
from uuid import uuid4

import paho.mqtt.client as mqtt
import psycopg
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field


# =========================================================
# FastAPI
# =========================================================

app = FastAPI(title="Weld-Made API")


# =========================================================
# MQTT
# =========================================================

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

MQTT_SUBSCRIPTIONS = [
    "robot/#",
    "scan/#",
    "contact/#",
    "safety/#",
    "cmd/ack",
    "hb/ros",
    "conn/ros",
]

mqtt_client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2
)


# =========================================================
# WebSocket
# =========================================================

websocket_clients: set[WebSocket] = set()
main_event_loop = None


async def broadcast_to_websocket(topic: str, payload):
    """
    WebSocket 클라이언트들에게 메시지를 전달한다.

    raw MQTT:
        topic = scan/state
        topic = cmd/ack
        ...

    T22 command lifecycle:
        topic = command/status
    """

    message = {
        "topic": topic,
        "payload": payload,
    }

    disconnected = []

    for websocket in list(websocket_clients):
        try:
            await websocket.send_json(message)
        except Exception:
            disconnected.append(websocket)

    for websocket in disconnected:
        websocket_clients.discard(websocket)


def schedule_websocket_broadcast(topic: str, payload):
    """
    Paho MQTT callback thread 등에서
    FastAPI asyncio loop로 WebSocket 전송을 넘긴다.
    """

    if main_event_loop is None:
        return

    asyncio.run_coroutine_threadsafe(
        broadcast_to_websocket(topic, payload),
        main_event_loop,
    )


# =========================================================
# Command 상태 저장
# =========================================================

pending_commands: dict[str, dict[str, Any]] = {}
command_lock = Lock()

# 이 두 명령은 ROS Service 기반이라
# cmd/ack 자체가 최종 결과다.
ACK_IS_FINAL_TOPICS = {
    "cmd/scan/set_config",
    "cmd/safety/reset",
}


def update_command_from_ack(payload: dict):
    """
    cmd/ack 수신 시:

    accepted=true
        일반 명령 -> ACCEPTED
        Service 명령 -> SUCCEEDED

    accepted=false
        -> REJECTED
    """

    request_id = payload.get("request_id")

    if not request_id:
        return None

    with command_lock:
        state = pending_commands.get(request_id)

        # 다른 클라이언트가 보낸 request_id라도
        # 수신 사실은 기록할 수 있게 한다.
        if state is None:
            state = {
                "request_id": request_id,
                "command_topic": None,
                "status": "UNKNOWN",
                "created_at_ms": None,
            }
            pending_commands[request_id] = state

        accepted = bool(payload.get("accepted"))

        if accepted:
            if state.get("command_topic") in ACK_IS_FINAL_TOPICS:
                state["status"] = "SUCCEEDED"
            else:
                state["status"] = "ACCEPTED"
        else:
            state["status"] = "REJECTED"

        state["ack"] = payload
        state["updated_at_ms"] = int(time.time() * 1000)

        return state.copy()


def update_command_from_result(payload: dict):
    """
    scan/command_result 수신 시:

    success=true  -> SUCCEEDED
    success=false -> FAILED
    """

    request_id = payload.get("request_id")

    if not request_id:
        return None

    with command_lock:
        state = pending_commands.get(request_id)

        if state is None:
            state = {
                "request_id": request_id,
                "command_topic": None,
                "status": "UNKNOWN",
                "created_at_ms": None,
            }
            pending_commands[request_id] = state

        if payload.get("success") is True:
            state["status"] = "SUCCEEDED"
        else:
            state["status"] = "FAILED"

        state["result"] = payload
        state["updated_at_ms"] = int(time.time() * 1000)

        return state.copy()


# =========================================================
# MQTT Callback
# =========================================================

def on_connect(client, userdata, flags, reason_code, properties):
    print(f"[MQTT] connected: {reason_code}")

    for topic in MQTT_SUBSCRIPTIONS:
        client.subscribe(topic, qos=1)
        print(f"[MQTT] subscribed: {topic}")


def on_message(client, userdata, message):
    try:
        payload_text = message.payload.decode("utf-8")
        payload = json.loads(payload_text)

    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(
            f"[MQTT] invalid JSON "
            f"topic={message.topic} error={exc}"
        )
        return

    print(
        f"[MQTT] received "
        f"topic={message.topic} payload={payload}"
    )

    # 1. MQTT 원본 메시지를 WebSocket으로 전달
    schedule_websocket_broadcast(
        message.topic,
        payload,
    )

    # 2. 명령 접수/거절 처리
    if message.topic == "cmd/ack":
        command_state = update_command_from_ack(payload)

        if command_state is not None:
            print(
                f"[COMMAND] request_id={command_state['request_id']} "
                f"status={command_state['status']}"
            )

            schedule_websocket_broadcast(
                "command/status",
                command_state,
            )

    # 3. 명령 완료/실패 처리
    elif message.topic == "scan/command_result":
        command_state = update_command_from_result(payload)

        if command_state is not None:
            print(
                f"[COMMAND] request_id={command_state['request_id']} "
                f"status={command_state['status']}"
            )

            schedule_websocket_broadcast(
                "command/status",
                command_state,
            )


mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message


# =========================================================
# PostgreSQL
# =========================================================

DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("POSTGRES_DB", "contact_scan")
DB_USER = os.getenv("POSTGRES_USER", "contact_scan")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")


# =========================================================
# Startup / Shutdown
# =========================================================

@app.on_event("startup")
async def startup_event():
    global main_event_loop

    main_event_loop = asyncio.get_running_loop()

    mqtt_client.connect(
        MQTT_HOST,
        MQTT_PORT,
        60,
    )

    mqtt_client.loop_start()


@app.on_event("shutdown")
def shutdown_event():
    mqtt_client.loop_stop()
    mqtt_client.disconnect()


# =========================================================
# Health
# =========================================================

@app.get("/health")
def health_check():
    return {
        "status": "ok"
    }


# =========================================================
# WebSocket
# =========================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    websocket_clients.add(websocket)

    print(
        f"[WS] connected "
        f"clients={len(websocket_clients)}"
    )

    try:
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        pass

    finally:
        websocket_clients.discard(websocket)

        print(
            f"[WS] disconnected "
            f"clients={len(websocket_clients)}"
        )


# =========================================================
# Command REST -> MQTT
# =========================================================

class CommandRequest(BaseModel):
    session_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    scan_id: str | None = None


def publish_command(
    topic: str,
    request: CommandRequest,
    include_scan_id: bool = False,
):
    request_id = str(uuid4())
    timestamp_ms = int(time.time() * 1000)

    message = {
        "schema_version": "0.1",
        "request_id": request_id,
        "timestamp_ms": timestamp_ms,
        "payload": request.payload,
    }

    if request.session_id is not None:
        message["session_id"] = request.session_id

    if include_scan_id:
        message["scan_id"] = request.scan_id or ""

    mqtt_info = mqtt_client.publish(
        topic,
        json.dumps(message),
        qos=1,
        retain=False,
    )

    if mqtt_info.rc == mqtt.MQTT_ERR_SUCCESS:
        status = "PUBLISHED"
    else:
        status = "PUBLISH_ERROR"

    command_state = {
        "request_id": request_id,
        "command_topic": topic,
        "status": status,
        "created_at_ms": timestamp_ms,
        "updated_at_ms": timestamp_ms,
        "request": message,
    }

    with command_lock:
        pending_commands[request_id] = command_state

    # REST 명령을 보낸 직후에도 React에 상태 전달
    schedule_websocket_broadcast(
        "command/status",
        command_state,
    )

    return {
        "status": status,
        "topic": topic,
        "request_id": request_id,
        "mqtt_rc": mqtt_info.rc,
        "message": message,
    }


@app.post("/commands/scan/start")
def command_scan_start(
    request: CommandRequest | None = None
):
    return publish_command(
        "cmd/scan/start",
        request or CommandRequest(),
    )


@app.post("/commands/scan/stop")
def command_scan_stop(
    request: CommandRequest | None = None
):
    return publish_command(
        "cmd/scan/stop",
        request or CommandRequest(),
    )


@app.post("/commands/scan/home")
def command_scan_home(
    request: CommandRequest | None = None
):
    return publish_command(
        "cmd/scan/home",
        request or CommandRequest(),
    )


@app.post("/commands/scan/resume")
def command_scan_resume(
    request: CommandRequest | None = None
):
    return publish_command(
        "cmd/scan/resume",
        request or CommandRequest(),
        include_scan_id=True,
    )


@app.post("/commands/scan/set_config")
def command_scan_set_config(
    request: CommandRequest | None = None
):
    return publish_command(
        "cmd/scan/set_config",
        request or CommandRequest(),
    )


@app.post("/commands/safety/reset")
def command_safety_reset(
    request: CommandRequest | None = None
):
    return publish_command(
        "cmd/safety/reset",
        request or CommandRequest(),
    )


# =========================================================
# Command 상태 조회
# =========================================================

@app.get("/commands/{request_id}")
def get_command_status(request_id: str):
    with command_lock:
        state = pending_commands.get(request_id)

        if state is None:
            return {
                "found": False,
                "request_id": request_id,
            }

        return {
            "found": True,
            **state,
        }


# =========================================================
# 기존 MQTT 테스트
# =========================================================

@app.post("/mqtt/test")
def publish_mqtt_test():
    test_message = '{"message":"fastapi mqtt ok"}'

    mqtt_client.publish(
        "cobot/test",
        test_message,
    )

    return {
        "status": "published",
        "topic": "cobot/test",
        "message": test_message,
    }


# =========================================================
# PostgreSQL 테스트
# =========================================================

@app.get("/db/test")
def database_test():

    with psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    ) as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                "SELECT current_database(), current_user;"
            )

            result = cursor.fetchone()

    return {
        "status": "ok",
        "database": result[0],
        "user": result[1],
    }
