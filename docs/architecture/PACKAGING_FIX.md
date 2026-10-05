# 패키징 규칙

임시 delivery-lock/pending 및 숨김 실행 상태·snapshot은 최종 ZIP에서 제외합니다. 완료 receipt는 유지합니다. manifest는 생성 완료 후 갱신하고 ZIP을 새 폴더에 실제 추출하여 PNG 디코딩·하단·SHA를 검사합니다. 이번 변경으로 System/ROS geometry와 모든 HTML viewer bytes는 달라졌습니다. 의미 및 ERD/Flow candidate만 이전 ui-fixed ZIP과 동일합니다. 현재 검증은 VALIDATION_SUMMARY.md, UI_FIXES.md와 최신 evidence를 따릅니다.

재생성 중 실행한 자식 CLI가 남기는 상태는 종료를 기다린 자식의 완료 receipt·현재 SHA·경로 소유권이 일치할 때만 외부 보관하고 최대 2회 재시도합니다. 외부/불일치 lock은 중단합니다.
