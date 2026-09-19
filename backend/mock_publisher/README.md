# MQTT Mock Publisher

`docs/contracts/mqtt-schema.md` v0.1 계약에 맞춘 테스트 MQTT 발행기이다.

실제 ROS `mqtt_bridge`가 완성되기 전에 Web PC에서 MQTT 데이터 흐름을 테스트하기 위해 사용한다.

## 발행 토픽

- `scan/state`
- `robot/sample`
- `contact/event`
- `scan/result`
- `scan/log`

## 설치

```bash
cd backend/mock_publisher

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

## 실행

기본적으로 Web PC 자신의 Mosquitto Broker를 사용한다.

```bash
python3 mock_publisher.py
```

기본 Broker:

```text
127.0.0.1:1883
```

다른 Broker를 사용할 경우:

```bash
MQTT_HOST=172.24.0.51 \
MQTT_PORT=1883 \
python3 mock_publisher.py
```

## MQTT 수신 확인

다른 터미널에서 다음 명령을 실행한다.

```bash
mosquitto_sub \
  -h 127.0.0.1 \
  -p 1883 \
  -t 'scan/#' \
  -t 'robot/#' \
  -t 'contact/#' \
  -v
```

그 다음 `mock_publisher.py`를 실행한다.

정상적으로 다음 토픽들이 출력되어야 한다.

```text
scan/state
robot/sample
contact/event
scan/result
scan/log
```

`scan/state`는 MQTT 계약에 따라 QoS 1, retain=true로 발행한다.

나머지 테스트 메시지는 계약에 정의된 QoS와 retain 설정을 사용한다.
