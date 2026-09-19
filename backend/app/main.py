import asyncio
import json
import os
from contextlib import asynccontextmanager, suppress
from typing import Literal

import paho.mqtt.client as mqtt
import psycopg
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

try:
    from .live import LiveHub, TOPICS, timeout_loop
except ImportError:
    from live import LiveHub, TOPICS, timeout_loop

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("POSTGRES_DB", "contact_scan")
DB_USER = os.getenv("POSTGRES_USER", "contact_scan")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
hub = LiveHub(float(os.getenv("ACK_TIMEOUT_S", "5")))
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)


@asynccontextmanager
async def lifespan(app):
    loop = asyncio.get_running_loop()

    def on_connect(client, userdata, flags, reason_code, properties):
        connected = not reason_code.is_failure
        if connected:
            client.subscribe([(topic, 1) for topic in TOPICS])
        loop.call_soon_threadsafe(hub.connection, connected)

    def on_disconnect(client, userdata, flags, reason_code, properties):
        loop.call_soon_threadsafe(hub.connection, False)

    def on_message(client, userdata, message):
        loop.call_soon_threadsafe(hub.receive, message.topic, bytes(message.payload), message.retain)

    mqtt_client.on_connect = on_connect
    mqtt_client.on_disconnect = on_disconnect
    mqtt_client.on_message = on_message
    mqtt_client.connect_async(MQTT_HOST, MQTT_PORT, 60)
    mqtt_client.loop_start()
    timer = asyncio.create_task(timeout_loop(hub))
    try:
        yield
    finally:
        timer.cancel()
        with suppress(asyncio.CancelledError):
            await timer
        mqtt_client.disconnect()
        await asyncio.to_thread(mqtt_client.loop_stop)


app = FastAPI(title="Weld-Made API", lifespan=lifespan)


class CommandBody(BaseModel):
    session_id: str = Field(default="", max_length=128)
    scan_id: str = Field(default="", max_length=128)
    detail: str = Field(default="operator stop", max_length=512)


@app.get("/health")
def health_check():
    return {"status": "ok", "mqtt_connected": hub.connected}


@app.post("/api/scan/{action}", status_code=202)
async def command(action: Literal['start', 'stop', 'home', 'resume'], body: CommandBody):
    if not hub.connected:
        raise HTTPException(503, 'MQTT broker disconnected; command not sent')
    try:
        message, record = hub.begin(action, body.session_id, body.scan_id,
                                    {'detail': body.detail} if action == 'stop' else {})
    except OverflowError as exc:
        raise HTTPException(503, str(exc)) from exc
    info = mqtt_client.publish('cmd/scan/' + action, json.dumps(message), qos=1, retain=False)
    if info.rc != mqtt.MQTT_ERR_SUCCESS:
        record['status'] = 'failed'
        hub.emit('web/command', dict(record))
        raise HTTPException(503, {'request_id': record['request_id'], 'reason': 'MQTT publish failed'})
    hub.emit('web/command', dict(record))
    return dict(record)  # 202/pending means queued locally, never robot accepted/completed.


@app.get("/api/commands/{request_id}")
async def command_status(request_id: str):
    if request_id not in hub.commands:
        raise HTTPException(404, 'Unknown request_id')
    return hub.commands[request_id]


@app.websocket("/ws/live")
async def live(websocket: WebSocket):
    await websocket.accept()
    queue = asyncio.Queue(maxsize=256)
    hub.clients.add(queue)

    async def send():
        while True:
            event = await queue.get()
            if event is None:
                await websocket.close(code=1013, reason='Client too slow; reconnect')
                return
            await websocket.send_json(event)

    async def receive():
        while True:
            await websocket.receive_text()

    tasks = []
    try:
        await websocket.send_json({'topic': 'web/snapshot', 'payload': {
            'mqtt_connected': hub.connected, 'latest': list(hub.latest.values()),
            'commands': list(hub.commands.values())[-100:]}})
        tasks = [asyncio.create_task(send()), asyncio.create_task(receive())]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        hub.clients.discard(queue)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


@app.post("/mqtt/test")
def publish_mqtt_test():
    if not hub.connected:
        raise HTTPException(503, 'MQTT broker disconnected')
    mqtt_client.publish('cobot/test', '{"message":"fastapi mqtt ok"}')
    return {'status': 'queued', 'topic': 'cobot/test'}


@app.get("/db/test")
def database_test():

    # PostgreSQL에 연결한다.
    with psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    ) as connection:

        # SQL을 실행하기 위한 cursor 생성
        with connection.cursor() as cursor:

            # 실제 테이블을 만들지 않고
            # DB 연결만 확인한다.
            cursor.execute(
                "SELECT current_database(), current_user;"
            )

            result = cursor.fetchone()

    return {
        "status": "ok",
        "database": result[0],
        "user": result[1]
    }

