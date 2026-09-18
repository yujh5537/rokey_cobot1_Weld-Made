import os

import paho.mqtt.client as mqtt
import psycopg
from fastapi import FastAPI


# FastAPI 애플리케이션 생성
app = FastAPI(title="Weld-Made API")


# =========================
# MQTT 설정
# =========================

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))


# MQTT Client 생성
mqtt_client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2
)


# =========================
# PostgreSQL 설정
# =========================

DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("POSTGRES_DB", "contact_scan")
DB_USER = os.getenv("POSTGRES_USER", "contact_scan")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")


# =========================
# FastAPI 시작 / 종료
# =========================

@app.on_event("startup")
def startup_event():
    # FastAPI 시작 시 MQTT Broker에 연결한다.
    mqtt_client.connect(
        MQTT_HOST,
        MQTT_PORT,
        60
    )

    # MQTT 메시지 처리를 백그라운드에서 시작한다.
    mqtt_client.loop_start()


@app.on_event("shutdown")
def shutdown_event():
    # FastAPI 종료 시 MQTT 연결도 종료한다.
    mqtt_client.loop_stop()
    mqtt_client.disconnect()


# =========================
# 기본 Health Check
# =========================

@app.get("/health")
def health_check():
    return {
        "status": "ok"
    }


# =========================
# MQTT 테스트
# =========================

@app.post("/mqtt/test")
def publish_mqtt_test():
    test_message = '{"message":"fastapi mqtt ok"}'

    mqtt_client.publish(
        "cobot/test",
        test_message
    )

    return {
        "status": "published",
        "topic": "cobot/test",
        "message": test_message
    }


# =========================
# PostgreSQL 테스트
# =========================

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
