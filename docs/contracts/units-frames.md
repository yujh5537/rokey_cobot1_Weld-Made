# 단위·좌표 기준

상태: **v0.1** (2026-09-18, T01 1·2차 회의). 단위 · 기준 규칙은 확정, 좌표 **값**은 미확정이다. BRD 6장에 따라 물품 도착·환경 세팅 후 학민이 확정한다(T02, T03). 확정 전까지 아래 TBD 값을 코드에 상수로 넣지 않는다.

## 단위 (확정)
| 구간 | 길이 | 각도 · 자세 | 힘 · 토크 | 속도 |
|---|---|---|---|---|
| 두산 API (posx, get_tool_force) | mm | deg (ZYZ 오일러) | N · N·m | mm/s |
| ROS 내부 (자체 인터페이스) | **m** | **rad · 자세는 quaternion** | **N · N·m** | m/s |
| MQTT·웹 | **mm** | **각도 값을 싣지 않음. 자세는 quaternion** (화면에 deg가 필요하면 웹이 변환) | N · N·m | mm/s |

변환 위치: 두산↔ROS는 **robot_manager**, ROS↔웹은 **mqtt_bridge**. 그 외에서는 변환하지 않는다.

## 시각 (확정)
- ROS: `builtin_interfaces/Time`, 메인 PC ROS 시계. 취득 시각 = robot_manager가 조회 응답을 받은 시각. TCP와 힘의 취득 시각을 따로 보존한다.
- MQTT: epoch ms 정수(UTC). 상세는 `mqtt-schema.md`.
- 웹 PC ↔ 메인 PC 시계 동기는 chrony로 맞춘다(의석, 별도 PR). 관제 지연 측정(TR-05)의 선행조건이다.

## 프레임 (확정)
| 데이터 | 프레임 |
|---|---|
| `RobotSample` · `ContactEvent` · `ExecuteMotion` · `SafetyStatus.position` | **Base** (`base_link`, 가칭) |
| `ScanResult` | **작업대 좌표** (`workpiece_fixture`, 가칭) |

- 샘플 · 이벤트 · 모션은 T03 이후에도 **계속 Base로 발행**한다. 작업대 좌표로의 변환은 **scan_manager 한 곳**에서 결과에만 적용한다(파라미터 `base_to_fixture`).
- **조건: 배치 가이드를 Base 축과 평행하게 설치한다. `base_to_fixture`는 평행 이동만 다룬다.** 밀기 방향(`DIR_POS_X` 등)은 Base 축 기준이다. 평행 여부는 T03에서 확인한다. 회전이 필요해지면 계약을 고친다(`ExecuteMotion.frame_id`로 확장).
- BRD 4.7의 "프레임·단위 변환은 robot_manager에서 관리"는 **두산 좌표(mm·deg) → `base_link`(m·quaternion) 변환**을 가리키는 것으로 해석한다. 결과를 작업대 좌표로 나타내는 것은 형상 계산의 일부다.
- 좌표를 쓰는 쪽(safety_monitor 작업영역, sim 가상 직육면체 등)은 **`frame_id`를 확인하고** 쓴다.
- 프레임 이름은 가칭이다.

## TCP · 힘 기준 (확정)
| 항목 | 기준 |
|---|---|
| TCP 기준점 | **탐침 팁의 최하단점.** 접촉 시 TCP z가 곧 윗면 높이다(반지름을 빼지 않는다) |
| 탐색 중 자세 | **수직 고정.** 그래야 최하단점과 구 중심의 x·y가 같아 모서리 편향 보정식 √(2rδ−δ²)이 그대로 성립한다 |
| 힘 기준 좌표 | `get_tool_force(ref=DR_BASE)`. `RobotSample.wrench`는 `frame_id`(Base) 기준 성분이다 |
| 눌렀을 때 Fz의 부호 | **TBD.** T08에서 손으로 눌러 확인하고 여기와 `docs/env/api-check-log.md`에 적는다 |

## 좌표 값 (미확정)
| 항목 | 값 | 확정일 / 확인자 |
|---|---|---|
| 작업대 원점의 Base 좌표 (`base_to_fixture`) | TBD | |
| 배치 가이드와 Base 축의 평행 확인 | TBD | |
| z=0 기준 (작업대 표면인가 지그 지지면인가) | TBD | |
| 탐침 TCP 오프셋 (최하단점 기준) | TBD | |
| 툴 무게·무게중심 (RG2 + 탐침) | TBD | |
| 홈위치(시작위치) 관절각 | TBD | |
| 탐색 기준점(원점 상공) 높이 | TBD | |
| 팁 반지름 | TBD (설계 출발값 3 mm) | |

홈위치(로봇 시작위치)와 작업대 원점은 다른 것이다. 방향별 탐색 사이의 "원점 복귀"(`OP_MOVE_TO`)와 "홈 복귀"(`OP_HOME`: 관제자의 안전복귀, 스캔 정상 완료 뒤의 마무리)도 다른 동작이다.

## 미결정 (BRD 6장, 팀 확인 없이 정하지 않는다)
홈 복귀 경로·순서, 중단 위치 재접근 절차, 이상 상태별 재시작 허용 조건, 정지 우선순위, 데이터 최신성 한계, heartbeat 만료 정책.
(래치 해제 조건은 확정됐다: 관제자의 `/safety/reset` + 감시 조건 해소.)
