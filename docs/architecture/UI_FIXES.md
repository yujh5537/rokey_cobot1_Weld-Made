# 이번 수정

| 항목 | 수정 파일 | 검증 결과 |
| --- | --- | --- |
| Copy Diagram | viewer-fixes.patch: export.js | Export 메뉴 열기 시 PNG 미리 준비; 준비 완료 Blob을 클릭 중 전달. 거절 시 새 클릭 재시도/PNG 저장. 관련 단위 검사 통과, 실제 클립보드 미확인 |
| 패널 이동 흔들림 | reader-layout.js, viewer-camera.js 및 index.html | 부모 viewport 기준 높이; iframe 높이만 바뀌면 reader 재계산과 카메라 refocus를 모두 생략. 모의 이벤트 검사 통과, 실제 화면 미확인 |
| System 비율 | data/01_system.json | 참고 1563:1160과 정확히 동일, 노드/선 의미 변경 없음 |
| ROS 비율 | data/02_ros2.json | 참고 1789:932와 정확히 동일, 라벨/접점/경로 재배치, 의미 변경 없음 |
| ERD/Flow | 후보 JSON 유지 및 HTML 재생성 | 7개 테이블·71개 컬럼, 순서도 도형·분기·소스 링크 유지 |

System/ROS는 공식 architecture renderer, ERD/Flow는 기존 확장 renderer로 재생성했습니다. 동일한 원본 viewer에 UI 패치를 적용했습니다. 참고본에는 ERD/Flow가 없어 기존 비율을 유지했습니다. 다크 기본·라이트 전환·왼쪽 메뉴와 검색/Path/MAP/LENS/상세/발표/Live/Still/Export 코드는 유지했습니다.

실제 브라우저 접근은 이전 시도에서 ERR_BLOCKED_BY_CLIENT로 차단됐고 우회도 금지됐습니다. 새 ZIP의 실제 클립보드, 흔들림 해소, 메뉴 조작, 다운로드 완료는 미확인입니다. PNG 열기와 함수 단위 검사는 native Export 검사가 아닙니다. Chrome도 없어 browser-check/visual-check는 skipped입니다.
