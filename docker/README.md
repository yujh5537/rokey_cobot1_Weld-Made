# docker

Web PC에서 사용하는 Docker Compose 실행 환경이다.

구성 서비스:

- Mosquitto MQTT Broker
- PostgreSQL
- FastAPI
- Spring Boot

## 1. 환경 변수 준비

처음 실행할 때 `.env.example`을 복사한다.

```bash
cd docker
cp .env.example .env
```

`.env`의 PostgreSQL 비밀번호를 개발 환경에 맞게 수정한다.

`.env`는 Git에 커밋하지 않는다.

## 2. 전체 서비스 실행

```bash
cd docker
docker compose up -d --build
```

실행 상태 확인:

```bash
docker compose ps
```

정상적으로 다음 서비스가 실행되어야 한다.

```text
weld_made_mosquitto
weld_made_postgres
weld_made_fastapi
weld_made_spring
```

기본 포트:

```text
Mosquitto    1883
PostgreSQL   5432
FastAPI      8000
Spring Boot  8080
```

## 3. FastAPI 확인

Health Check:

```bash
curl http://127.0.0.1:8000/health
```

정상 예시:

```json
{"status":"ok"}
```

PostgreSQL 연결 확인:

```bash
curl http://127.0.0.1:8000/db/test
```

정상 예시:

```json
{"status":"ok","database":"contact_scan","user":"contact_scan"}
```

MQTT Publish 확인:

```bash
curl -X POST http://127.0.0.1:8000/mqtt/test
```

정상 예시:

```json
{
  "status": "published",
  "topic": "cobot/test",
  "message": "{\"message\":\"fastapi mqtt ok\"}"
}
```

## 4. Spring Boot 확인

```bash
curl http://127.0.0.1:8080/actuator/health
```

정상 상태에서는 `status`가 `UP`으로 나온다.

예시:

```json
{"status":"UP"}
```

## 5. Main PC에서 Web PC MQTT Broker 연결 확인

현재 테스트 환경:

```text
Main PC
172.24.3.240

Web PC
172.24.0.51
```

Web PC에서 테스트 토픽을 구독한다.

```bash
mosquitto_sub -h 127.0.0.1 -p 1883 -t 'cobot/network_test' -v
```

Main PC에서 Web PC의 MQTT Broker로 메시지를 발행한다.

```bash
mosquitto_pub -h 172.24.0.51 -p 1883 -t 'cobot/network_test' -m '{"message":"main pc to web pc ok"}'
```

Web PC subscriber에 다음 메시지가 표시되면 연결 성공이다.

```text
cobot/network_test {"message":"main pc to web pc ok"}
```

## 6. 서비스 종료

Docker Compose 서비스를 종료한다.

```bash
cd docker
docker compose down
```

데이터 볼륨은 유지된다.

볼륨까지 삭제하려면 다음 명령을 사용한다.

```bash
docker compose down -v
```

주의: `-v` 옵션을 사용하면 PostgreSQL과 Mosquitto의 Docker volume 데이터도 삭제된다.

## 주의

이 Repository는 공개 Repository이다.

실제 비밀번호가 들어 있는 `.env` 파일은 Git에 커밋하지 않는다.

Git에는 `.env.example`만 커밋한다.