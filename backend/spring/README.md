## Backend 역할

웹 백엔드는 FastAPI와 Spring Boot의 책임을 분리한다.

- **FastAPI**
  - MQTT 실시간 메시지 수신
  - 로봇 제어 명령 전달
  - 측정 결과 및 이벤트 PostgreSQL 저장

- **Spring Boot**
  - 공작물(Workpiece) 관리
  - 작업(WorkOrder) 관리
  - 작업과 실제 Scan 결과 연결
  - 측정 이력 조회

### 데이터 흐름

```text
ROS 2
  ↓
mqtt_bridge
  ↓
Mosquitto
  ↓
FastAPI
  ↓
PostgreSQL
  ↑
Spring Boot
  ↓
React
```

측정 데이터는 FastAPI가 저장하고 Spring Boot는 측정 이력을 조회한다.
공작물·작업과 같은 업무 데이터는 Spring Boot가 직접 관리한다.

### PostgreSQL 주요 테이블

```text
측정 데이터

scan_jobs
├── measurements
├── scan_configs
└── contact_events

업무 데이터

workpieces
  ↓
work_orders
  ↓
work_order_scans
  ↓
scan_jobs
```

`work_order_scans`를 통해 특정 작업과 실제 측정 결과(`scan_id`)를 연결한다.

### Spring Boot API

| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/api/history/scans` | 측정 이력 목록 조회 |
| GET | `/api/history/scans/{scanId}` | 측정 결과 상세 조회 |
| POST | `/api/workpieces` | 공작물 등록 |
| GET | `/api/workpieces` | 공작물 목록 조회 |
| GET | `/api/workpieces/{workpieceId}` | 공작물 상세 조회 |
| PUT | `/api/workpieces/{workpieceId}` | 공작물 수정 |
| POST | `/api/work-orders` | 작업 등록 |
| GET | `/api/work-orders` | 작업 목록 조회 |
| GET | `/api/work-orders/{workOrderId}` | 작업 상세 조회 |
| GET | `/api/work-orders/by-workpiece/{workpieceId}` | 공작물별 작업 조회 |
| PUT | `/api/work-orders/{workOrderId}` | 작업 수정 |
| GET | `/api/work-orders/{workOrderId}/scans` | 작업에 연결된 Scan 조회 |
| POST | `/api/work-orders/{workOrderId}/scans/{scanId}` | 작업과 Scan 연결 |

### Backend 데이터 책임

```text
FastAPI
├── 측정 데이터 WRITE
├── scan_jobs 저장
├── measurements 저장
├── scan_configs 저장
└── contact_events 저장

Spring Boot
├── 측정 데이터 READ
├── Workpiece WRITE / READ
├── WorkOrder WRITE / READ
└── WorkOrder ↔ Scan 연결 관리
```

### PostgreSQL 스키마 적용

신규 PostgreSQL 볼륨에서는 `docker/postgres/init/` 아래 SQL이 초기화 과정에서 자동 적용된다.

```text
001_schema.sql
→ 측정 결과·이벤트 스키마

002_business_schema.sql
→ Workpiece·WorkOrder·WorkOrder-Scan 연결 스키마
```

이미 초기화된 PostgreSQL 볼륨에는 Docker init SQL이 다시 실행되지 않는다.

기존 개발 환경에서 `002_business_schema.sql`을 추가한 경우 다음 명령으로 한 번 수동 적용한다.

```bash
docker exec -i weld_made_postgres \
  psql -U contact_scan -d contact_scan \
  < docker/postgres/init/002_business_schema.sql
```

적용 확인:

```bash
docker exec weld_made_postgres \
  psql -U contact_scan -d contact_scan \
  -c "\dt"
```

다음 업무 테이블이 보이면 정상이다.

```text
workpieces
work_orders
work_order_scans
```

> `docker compose up`만 다시 실행해도 기존 PostgreSQL 볼륨에는 `002_business_schema.sql`이 자동 적용되지 않는다.

`ws_dsr/`(두산·RG2 드라이버)와 `DartPlatform/`은 이 레포에 없다. `docs/env/`를 따라 각자 구축한다.
