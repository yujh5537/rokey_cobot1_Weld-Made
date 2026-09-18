Closes #

## 무엇을 / 왜
<!-- 2~3줄. 핵심 설계 선택이 있으면 같이 -->

## 확인한 것
- [ ] `colcon build` / `colcon test` 통과 (ROS 변경 시)
- [ ] 웹 빌드·테스트 통과 (웹 변경 시)
- [ ] sim 또는 Virtual Mode에서 동작 확인: <!-- 무엇을 어떻게 -->
- [ ] 실기 확인: <!-- 했음(날짜·조건) / 아직 안 함 / 해당 없음 -->

## 계약·문서
- [ ] 계약(`docs/contracts`, `contact_scan_interfaces`)을 바꾸지 않았다
- [ ] 바꿨다면 계약 문서 + 인터페이스 + `CHANGELOG.md` + 목업 발행기를 같이 고쳤다
- [ ] 동작이 바뀐 부분의 docs를 이 PR에서 같이 고쳤다

## 안전 (robot_manager / scan_manager / safety_monitor 변경 시)
- [ ] 순응·힘 제어가 모든 종료 경로에서 해제된다 (finally)
- [ ] 중지·안전복귀·재시작이 서로를 자동 호출하지 않는다

## 작성자 확인
- [ ] 이 PR의 코드를 Claude 없이 내가 설명할 수 있다
- [ ] 이슈의 수정 범위 밖 파일을 고치지 않았다 (고쳤다면 이유: )
