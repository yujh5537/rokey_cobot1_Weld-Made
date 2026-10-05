# 모바일 도면 표시 수정

기존 index.html은 별도 HTML 파일을 상대 경로 iframe src로 요청했습니다. 모바일 로컬 파일/첨부 미리보기에서는 이 요청이 제한될 수 있습니다. 실제 사용자 단말의 근본 원인을 확인했다고 주장하지 않습니다.

이번에는 네 원본 Archify HTML을 index.html 및 Weld-Made-preview.html에 byte 그대로 포함하고 srcdoc로 지연 로딩합니다. 별도 도면 HTML 다운로드가 없어도 페이지 내 메뉴 전환이 가능합니다. 원본 viewer의 효과·메뉴는 유지합니다. 모바일 shell 폭을 부모 화면에 맞추고 도면 로딩 상태 및 제한 안내를 추가했습니다. 입력 템플릿은 site-wrapper.html이며 generate_assets.py로 두 embedded HTML을 재생성합니다.

기술 candidate/원본 HTML/SVG/PNG는 이전 ZIP과 그대로 유지합니다. 브라우저 정책이 iframe 또는 JavaScript 자체를 막는 환경은 해결을 보장할 수 없습니다. 실제 모바일/브라우저 UI 검사는 미확인입니다. 첨부를 HTML 미리보기 앱에서 여는 대신 ZIP을 압축 해제한 뒤 index.html을 Chrome/Safari에서 여세요. 공개 배포는 하지 않았습니다.
