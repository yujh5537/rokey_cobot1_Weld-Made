# mqtt_bridge

ROS 2 와 웹을 잇는 **단 하나의 통로**다. ROS 쪽 토픽 · 액션 · 서비스를 MQTT JSON 으로 바꾸고, 웹이 보낸 명령을 ROS 호출로 바꾼다. 담당은 의석이다.

기준은 `docs/contracts/mqtt-schema.md`(웹 쪽)와 `docs/contracts/ros-interfaces.md`(ROS 쪽)이고, **이 문서와 계약이 다르면 계약이 맞다.**

두 PC 사이의 연결은 이 노드가 브로커에 붙는 MQTT 하나뿐이다. 웹 PC 에는 ROS 가 없다(ADR-0002). 전체 구성은 `docs/deliverables/02-network.md`.

| 파일 | 내용 | rclpy |
|---|---|---|
| `mqtt_bridge/conversions.py` | 단위 · 시각 변환. m→mm, m/s→mm/s, ROS `Time`→epoch ms, NaN → `None`(`non_finite_to_none`), `*_valid=false` → `None`(`value_or_none`) | 쓰지 않음 |
| `mqtt_bridge/encoders.py` | **ROS → JSON.** 이름 표 7개(`ROBOT_OPERATION_NAMES` · `REASON_NAMES` · `SCAN_PHASE_NAMES` · `SCAN_DIRECTION_NAMES` · `CONTACT_EVENT_TYPE_NAMES` · `SCAN_LOG_LEVEL_NAMES` · `SAFETY_LEVEL_NAMES`)와 `encode_*` | 쓰지 않음 |
| `mqtt_bridge/decoders.py` | **JSON → ROS.** mm→m, `ScanConfig` 부분 적용(`*_set` 플래그), 모르는 키는 `ValueError` 로 거절 | 쓰지 않음 |
| `mqtt_bridge/command_guard.py` | 명령 관문: 필수 필드 → `schema_version` → `request_id` 형식 → 중복 → 만료 | 쓰지 않음 |
| `mqtt_bridge/mqtt_bridge.py` | 노드. 구독 8개 · 액션 클라이언트 3개 · 서비스 클라이언트 3개 · MQTT 연결 · 큐 · 종료 처리 | 씀 |

시험은 `test/test_encoders.py` · `test_enum_names.py` · `test_decoders.py` · `test_command_guard.py`(ROS 없이 돈다)와 `test_node.py`(생성된 msg 타입이 필요하다)에 있다.

---

## 1. 무엇을 하는가

### ROS → 웹 (구독 8개)

| ROS 토픽 | 타입 | MQTT 토픽 | QoS · retain | 비고 |
|---|---|---|---|---|
| `/robot/sample` | `RobotSample` | `robot/sample` | 0 · false | `sample_publish_hz`(10 Hz)로 다운샘플 |
| `/dsr01/joint_states` | `JointState` | `robot/joints` · `robot/gripper_joints` | 0 · false | **발행원 2개를 갈라 싣는다** — M0609 6축과 RG2 6축. `joint_publish_hz`(20 Hz) |
| `/robot/status` | `RobotStatus` | `robot/status` | 1 · **true** | 연결 · 동작 · 오류 · SLIDE 누름 목표 |
| `/scan/state` | `ScanState` | `scan/state` | 1 · **true** | 단계 · 방향 · 진행 n/4 |
| `/scan/result` | `ScanResult` | `scan/result` | 1 · false | 형상 결과 |
| `/scan/log` | `ScanLog` | `scan/log` | 1 · false | 시간순 로그 |
| `/contact/event` | `ContactEvent` | `contact/event` | 1 · false | 접촉 · 엣지 · 과대 외력 |
| `/safety/status` | `SafetyStatus` | `safety/status` | 1 · **true** | 안전 상태 · 래치 |

그 밖에 이 노드가 스스로 만드는 것: `cmd/ack`(접수 · 거절) · `scan/command_result`(완료 · 실패) · `hb/ros`(1 Hz) · `conn/ros`(LWT, retain).

### 웹 → ROS (MQTT 구독 4개)

| MQTT 토픽 | ROS 호출 |
|---|---|
| `cmd/scan/start` | `/scan/run` 액션 goal |
| `cmd/scan/stop` | `/scan/stop` 서비스 |
| `cmd/scan/home` | `/scan/home` 액션 goal |
| `cmd/scan/resume` | `/scan/resume` 액션 goal |
| `cmd/scan/set_config` | `/scan/set_config` 서비스 |
| `cmd/safety/reset` | `/safety/reset` 서비스 |
| `hb/web` | `/web/heartbeat` 발행 |
| `conn/web` | (연결 상태만 본다) |

구독 필터는 `cmd/scan/+` · `cmd/safety/reset` · `hb/web` · `conn/web` 네 개다. **발행에 와일드카드를 쓰지 않는다**(계약 1장).

---

## 2. 지켜야 하는 규칙 4개

계약이 요구하는 것 중 **틀리면 조용히 잘못된 값이 웹에 가는** 것들이다.

### 2.1 단위는 여기서만 바꾼다
길이는 ROS 가 m, 웹이 **mm** 다. 변환은 이 노드에서만 한다(계약 1장). 키 이름 끝에 단위를 붙인다: `x_mm` · `fz_n` · `slide_speed_mmps`.

**예외**: `robot/joints.positions_rad` · `robot/gripper_joints.positions_rad` 는 원본 `JointState.position`(rad)을 그대로 싣는다. deg 가 필요하면 웹이 시각화 단계에서 바꾼다.

### 2.2 모르는 값은 `null` 이다. 0 이 아니다
ROS 의 `*_valid=false`(값 NaN)를 `null` 로 바꾸고 **짝이 되는 `*_valid` 키는 항상 남긴다**(키 생략 금지). `json.dumps(..., allow_nan=False)` 를 쓰므로 NaN 이 새면 직렬화가 실패한다 — 그게 마지막 방어선이다.

> 과거 사고: `debounce_n` 을 모를 때 0 으로 실어 보냈다. 웹은 "디바운스 0회"로 읽었다(#133 → PR #145).

### 2.3 표에 없는 값도 버리지 않는다
`_enum_name` 은 이름 표에 없는 값을 만나면 **`"UNKNOWN_<값>"`** 을 돌려준다(#90, 계약 v0.1.22).

예전에는 `ValueError` 를 냈고, 그러면 구독 보호막(`_safe_ros_callback`)이 **그 메시지를 통째로 버렸다.** 정작 알려야 할 코드일수록 웹이 못 받는 구조였다.

**`UNKNOWN_<값>` 이 표를 안 고쳐도 된다는 뜻은 아니다.** 표가 계약과 어긋나지 않게 막는 것은 `test/test_enum_tables.py` 의 표 대조 시험이다(계약에 상수가 늘면 CI 가 실패한다).

**웹 → ROS 방향은 반대다.** 웹이 보낸 모르는 이름 · 모르는 키는 그대로 `INVALID_VALUE` 로 거절한다. 모르는 명령을 짐작해 실행하지 않는다.

### 2.4 `cmd/ack` 는 접수이고 완료가 아니다
- `cmd/ack` = goal 수락 · 거절, 서비스 응답. **접수**다
- `scan/command_result` = 액션 Result · `STOPPED` 전이. **완료 · 실패**다

둘을 섞으면 화면이 "끝났다"를 먼저 띄운다.

---

## 3. 명령 관문 (`command_guard.py`)

웹이 보낸 명령을 **이 순서로** 본다. 앞에서 걸리면 뒤는 보지 않는다.

| 순서 | 검사 | 거절 사유 |
|---|---|---|
| 1 | 필수 필드 | `INVALID_REQUEST(101)` |
| 2 | `schema_version` | `INVALID_REQUEST(101)` |
| 3 | `request_id` 형식 (UUID v4) | `INVALID_REQUEST(101)` |
| 4 | 최근 `dedup_cache_size`(100) 개 안의 중복 | `DUPLICATE_REQUEST(106)` |
| 5 | `cmd_expiry_s`(5 s) 초과 | `INVALID_REQUEST(101)` |

**`cmd/scan/stop` 은 5번(만료)을 건너뛴다.** 중지는 늦게 도착해도 실행해야 한다.

---

## 4. 파라미터

| 이름 | 출발값 | 실기 값 | 근거 |
|---|---|---|---|
| `broker_host` | `127.0.0.1` | 실행 시 launch 인자로 준다 | 주소를 레포에 두지 않는다. `bringup.launch.py` 의 `broker_host:=` |
| `broker_port` | `1883` | 1883 | `docker/.env`(`MQTT_PORT`) |
| `topic_prefix` | `""` | `""` | 한 브로커에 여러 조가 붙을 때만 쓴다 |
| `dedup_cache_size` | `100` | 100 | 최근 `request_id` 보관 수 |
| `cmd_expiry_s` | `5.0` | 5.0 | 명령 유효 시간. **stop 은 제외** |
| `sample_publish_hz` | `10.0` | 10.0 | `robot/sample` 다운샘플. 계약 2장 설계 목표 |
| `joint_publish_hz` | `20.0` | 20.0 | 관절 표시용. 0 이하 · 비유한수면 기동 실패 |
| `joint_state_topic` | `/dsr01/joint_states` | 같음 | `joint_state_broadcaster` · `joint_state_publisher` 둘이 발행한다 |
| `heartbeat_hz` | `1.0` | 1.0 | `hb/ros` 주기 |
| `keepalive_s` | `60` | 60 | MQTT keepalive |

기본값은 `config/mqtt_bridge.yaml` 에, 실행 값은 `contact_scan_bringup/config/real.yaml` · `sim.yaml` 의 `mqtt_bridge:` 절에 있다. **`broker_host` 만 launch 인자로 따로 받는다** — 웹 PC 주소가 사람마다 다르기 때문이다.

---

## 5. 실행

```bash
# 메인 PC. broker_host 는 웹 PC 주소로 바꾼다
source ~/ws_cobot_pjt/ws_cobot1/install/setup.bash
export ROS_DOMAIN_ID=30
ros2 launch contact_scan_bringup bringup.launch.py \
  source:=robot_force broker_host:=<웹 PC 주소>
```

이 노드만 따로 띄우려면:

```bash
ros2 run mqtt_bridge mqtt_bridge --ros-args \
  -p broker_host:=<웹 PC 주소> -p broker_port:=1883
```

**같은 브로커에 mqtt_bridge 를 두 개 띄우지 않는다.** 두 인스턴스가 같은 명령을 각각 실행한다.

### 연결 확인

```bash
nc -vz <웹 PC 주소> 1883                       # 포트
mosquitto_sub -h <웹 PC 주소> -p 1883 -t 'conn/ros' -v   # retain 된 연결 상태
```

`conn/ros` 가 `{"connected": true, ...}` 면 붙은 것이다. 노드가 죽으면 브로커가 LWT 로 `false` 를 대신 알린다.

---

## 6. 시험

```bash
# ROS 없이 (encoders · decoders · command_guard · enum 이름)
cd ws_cobot1/src/mqtt_bridge
PYTHONPATH=. python3 -m pytest test/ -q --ignore=test/test_node.py

# 전체 (contact_scan_interfaces 가 필요하다)
cd ws_cobot1 && colcon build --packages-select mqtt_bridge && colcon test --packages-select mqtt_bridge
colcon test-result --verbose
```

`test_node.py` 는 생성된 msg 타입을 import 하므로 ROS 를 source 하지 않은 셸에서는 collect 단계에서 멈춘다. `--ignore` 로 빼고, **"통과했다"고 쓰지 않는다.**

---

## 7. 알려진 문제 · 열린 이슈

| 번호 | 내용 | 상태 |
|---|---|---|
| [#90](../../../issues/90) | 표에 없는 ReasonCode 가 오면 메시지를 조용히 버린다 | **PR #200 이 닫는다** (`UNKNOWN_<n>`) |
| [#150](../../../issues/150) | 실기 없이 가능한 종단 확인 — 중복 106 · 만료 101 · 거절 사유 화면 · 래치 → reset | 열림 (의석 · 병후). **106 · 101 은 화면에서 재현할 수 없다** — FastAPI 가 클릭마다 새 `uuid4` 를 만든다. `mosquitto_pub` 로 해야 한다 |
| [#130](../../../issues/130) | 정지 중 300~360 ms 샘플 공백 | 열림. 브리지가 원인은 아니지만 `robot/sample` 끊김으로 화면에 보인다 |
| — | **`test_enum_tables.py` 의 `TABLES` 에 `ROBOT_OPERATION_NAMES` 가 없다.** 그래서 `OP_WELD_PATH=5` 가 빠진 것을 CI 가 잡지 못했다 | 후속 한 줄 PR 예정 (의석) |
| — | phase 2 `weld/*` 인코더(`WELD_PHASE_NAMES` · `encode_weld_*`) 미구현 | P4 (권장 9/28) |

---

## 8. 고칠 때 같이 봐야 하는 것

이 노드를 고치면 **거의 언제나** 다음이 같이 바뀐다.

1. `docs/contracts/mqtt-schema.md` — 웹이 받는 JSON 이 바뀌면
2. `docs/contracts/CHANGELOG.md` — 계약이 바뀌면 (레포 규칙)
3. `backend/mock_publisher/mock_publisher.py` — 계약 4장 예시를 그대로 쓴다
4. `backend/app/main.py` — 구독 필터가 바뀌면
5. `frontend/src/App.jsx` — 화면에 새 값을 보이려면

`docs/contracts/mqtt-schema.md` 는 **의석 · 병후 공동 코드오너**다. 고치면 PR 리뷰가 필수다.
