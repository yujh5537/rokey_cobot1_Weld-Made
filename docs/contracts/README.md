# 계약 (contracts)

모듈 사이의 약속이다. 네 명의 Claude가 같은 계약을 보고 구현해야 합칠 때 어긋나지 않는다. **코드와 계약이 다르면 계약이 맞고 코드가 버그다.** 계약이 틀렸으면 계약부터 PR로 고친다.

| 문서 | 내용 | 소유 |
|---|---|---|
| `ros-interfaces.md` | ROS Action/Service/Topic 이름, 타입, 필드 | 병후 |
| `mqtt-schema.md` | MQTT 토픽, JSON 스키마, 명령 ID, QoS | 병후·의석 |
| `units-frames.md` | 단위, 좌표계, TCP, 홈, 작업대 원점, z=0 | 학민 |
| `CHANGELOG.md` | 계약 변경 이력 | 바꾼 사람 |

## T01 동결 회의(9/18)에서 정할 것
BRD 4.7절이 "계약에서 확정할 사항"으로 남긴 항목이다. 회의에서 못 정한 것은 `TBD`로 남기고 담당과 기한을 적는다.

- [ ] msg/srv/action 필드와 타입 (`RobotSample`, `ContactEvent`, `ScanState`, `ScanResult`, `ExecuteMotion`, `RunScan`)
- [ ] 재시작 연결 방식 (BRD에서 이름·방식 TBD): 별도 Action인가, `/scan/run`의 모드인가
- [ ] 동작 식별자(motion_id)와 작업 식별자(job_id) 형식
- [ ] 명령 ID(command_id) 형식, 중복 처리, 접수 응답과 완료 응답의 구분 방법
- [ ] MQTT 토픽 트리, QoS, retain(명령은 retain=false 방향), JSON 필드
- [ ] 단위: ROS 내부 m·rad·N, 웹 mm (BRD 제안을 채택할지)
- [ ] 시각 표기: 취득 시각과 발행 시각, 시계 기준(메인 PC와 웹 PC 동기화)
- [ ] 미측정·실패 값 표기 (0 금지)
- [ ] 오류 코드 목록 초안
