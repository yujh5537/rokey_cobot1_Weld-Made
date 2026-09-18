---
paths:
  - "ws_cobot1/**"
---
# ROS 2 노드 규칙

- 자체 실행 노드는 5개뿐이다: scan_manager, robot_manager, contact_detector, safety_monitor, mqtt_bridge. geometry_estimator와 result_store는 scan_manager 안의 모듈이며 새 노드를 만들지 않는다.
- DSR_ROBOT2·dsr_msgs2·RG2 드라이버를 부르는 코드는 **robot_manager에만** 둔다. 다른 패키지는 `contact_scan_interfaces`의 타입만 쓴다.
- `scan_manager/geometry_estimator/`는 rclpy를 import하지 않는 순수 Python으로 유지한다(ROS 없이 pytest 실행).
- 장시간 모션은 비동기(amovel)로 실행하고 콜백을 막지 않는다. 모션 중에도 정지 요청과 샘플 수신이 처리되어야 한다(BRD 4.2.3). Action 취소 접수와 실제 정지 완료를 구분한다.
- 두산 API를 새로 쓰기 전에 `docs/env/api-check-log.md`에서 실제 PC 호출 확인 여부를 본다. 미확인이면 "미확인"이라고 PR에 적는다. DRL 매뉴얼에 있다고 ROS 2 Python 래퍼에 있다는 뜻이 아니다(예: `stop()`, `set_external_force_reset()`).
- 판정에 쓴 샘플의 좌표·시각과 정지 완료 후 좌표를 구분해서 기록한다. TCP와 힘은 한 메시지에 묶여 있어도 취득 시각이 다르다.
- 이벤트는 현재 동작 식별자(motion id)와 대조한 뒤에만 처리한다.
- `ros2 pkg create`가 만든 test_copyright/test_flake8/test_pep257은 지운다. 테스트는 동작 검증만 쓴다.
