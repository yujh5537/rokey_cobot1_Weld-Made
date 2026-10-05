# 최신 변경 검증

Copy Diagram 메뉴를 네 native viewer 및 두 embedded HTML에서 제거했습니다. no-copy-audit.json에서 실제 생성 HTML DOM·payload, SVG 동일성과 candidate/SVG/PNG byte 동일성을 확인했습니다. 다른 Export 메뉴 항목은 유지됩니다. 최신 receipt/manifest는 현재 HTML SHA를 가리킵니다.

네 renderer의 실제 finalize validate/deliver/check 결과와 재생성 동일성은 relocated-regeneration.json, ZIP 실제 재추출 CRC/SHA/PNG 전체 디코딩 결과는 zip-roundtrip-validation.json을 따릅니다. browser-check/visual-check는 Chrome 없음으로 skipped이며 실제 Copy 메뉴 제거 육안 조작과 PNG/SVG 다운로드 완료는 미확인입니다. 이번 저영향 메뉴 제거에 새 단위 테스트는 추가하지 않았습니다. 과거 Copy 단위 테스트는 현재 제거된 기능의 정상 판정에 사용하지 않습니다.

모바일 내장 문서·카메라/reader 높이 가드 및 기존 기술 내용은 유지했습니다. 프로젝트 실행 코드·README 변경, push, 배포는 하지 않았습니다.

첫 실행은 browser-check의 CLI 잔류 provenance 상태로 실패했습니다. 종료한 자식의 완료 receipt 및 candidate/HTML SHA 소유권 확인 후 외부 보관했고, 재시도 조건을 전체 status까지 검사하도록 보완한 뒤 재실행 완료했습니다. no-copy-rebuild-attempts.json 참조.
