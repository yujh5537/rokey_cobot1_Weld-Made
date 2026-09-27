# M0609 웹 시각화 보완 검증 — 2026-09-22

대상 브랜치: `euiseok/20260922-t41`. 기준 커밋: `bab3c00`.
기존 OrbitControls, M0609/RG2 visual mesh, 고정 탐침, `robot/joints` 중계를 유지하면서 좌표 변환과 입력 처리를 보완했다.

## 수정

- URDF RPY를 Three.js intrinsic `ZYX`로 적용한다. 기존 `XYZ`는 J2의 pitch/yaw 결합에서 잘못된 자세를 만든다.
- Z_UP DAE를 읽을 때 ColladaLoader가 추가한 Y-up 회전을 해제한다. 로봇 root가 축 변환을 한 번 수행한다.
- Doosan asset은 `6c5f3ba622bfa9d6f9cffebf21fa44f57db55b48`로 고정했다.
- 관절 이름으로 유효한 J1~J6 완전 스냅샷을 적용한다. 3초 미수신 및 WebSocket 종료를 표시한다.
- mesh 로딩 완료 전 컴포넌트가 해제되면 늦게 도착한 리소스를 정리한다.
- mqtt_bridge는 비유한 관절값·중복 이름을 거부한다. 잘못된 메시지는 정상 메시지의 발행 간격을 소비하지 않는다.

## 수행 결과

| 검증 | 결과 |
|---|---|
| `node --test test/robot.test.mjs` | 6개 통과 |
| `npm run lint` | 통과 |
| `npm run build` | 통과, 기존 대용량 bundle 경고 있음 |
| Python 구문 검사 | 통과 |
| ROS 없이 실제 `_on_joint_state` 콜백 본문 실행 | 잘못된 값 거부, timestamp, QoS 0 / retain false, rate limit 통과 |
| `git diff --check` | 통과 |

독립적인 행렬 계산은 공식 M0609 URDF의 origin/axis와 flange에서 `[0,0,0.25212]` m TCP를 사용한다.
영점 자세 및 서로 다른 2개 6축 자세에서 웹 탐침 끝점과 비교했다.
브리지 회귀 테스트는 기존 `test_node.py`에도 추가했지만, 이 환경에는 ROS 2가 없어 전체 ROS 패키지 테스트는 실행하지 않았다.

## 남은 확인

- 실제 `/dsr01/joint_states` → MQTT → FastAPI → 브라우저 종단 검증.
- 브라우저에서 실제 mesh 표시·마우스 조작 확인. 테스트 브라우저 설치 파일 다운로드가 실패하여 여기서는 화면 검증을 수행하지 못했다.
- 실기 관절 자세와 TCP 샘플이 모델 탐침 끝점에 맞는지 확인.
- mesh는 공개 GitHub raw URL에서 가져오므로 웹 PC의 외부 asset 접근이 필요하다.
- RG2는 고정 시각화 자세다. 실제 파지 폭·개폐 피드백은 미반영이다.

이 결과는 TR-05 지연 200 ms 및 중지 1초, TR-10 저장·조회 연동 시험의 완료 증거가 아니다. 실제 로봇 모션 명령은 실행하지 않았다.
