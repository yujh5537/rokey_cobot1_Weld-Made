# Copy Diagram 제거

viewer/template.source.html의 Copy Diagram 메뉴 버튼을 제거하고 export.js의 메뉴 open 시 Copy용 PNG 사전 준비 호출을 제거했습니다. 원본 viewer를 실제 재생성한 뒤 네 candidate를 각각 renderer로 HTML 생성했습니다. SVG/PNG 도면 기하·내용은 변경하지 않았습니다. PNG/SVG/그 외 Export 메뉴 항목은 유지합니다.

두 Archify checkout에 갱신한 viewer-fixes.patch를 적용하여 재생성하세요. renderer별 분리는 기존 README와 같습니다. 실제 브라우저 UI·다운로드 검증은 미확인입니다. 이전 Copy 관련 검사 로그는 현재 메뉴의 존재/동작 근거가 아닙니다. 최신 no-copy-audit.json을 따릅니다.
