# ADR-0003: 모노레포, 강사 제공 디렉터리 구조를 루트로 쓴다

- 날짜: 2026-09-18 / 상태: 채택

## 결정
`ws_cobot_pjt`를 레포 루트로 하고 `ws_cobot1/src`, `backend`, `frontend`, `docker`, `docs`를 한 레포에 둔다. `ws_dsr`(ahnisinc/cobot_rg2 클론)과 `DartPlatform`은 gitignore하고 설치 절차와 버전만 `docs/env/`에 기록한다.

## 근거
ROS와 웹의 계약(MQTT 스키마)이 같은 레포에 있어야 한 PR에서 양쪽을 같이 바꿀 수 있다. 서드파티 드라이버는 수정하지 않으며 공개 레포에 복사하지 않는다.

## geometry_estimator의 위치
BRD대로 scan_manager 내부 모듈(`scan_manager/scan_manager/geometry_estimator/`)로 둔다. 패키지 소유자(병후)와 모듈 소유자(현지)가 다르므로 CODEOWNERS에 경로 단위로 지정하고, rclpy에 의존하지 않게 해서 ROS 없이 테스트한다.
