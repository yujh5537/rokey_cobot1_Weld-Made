# 再生成 / 재생성 절차

공식 Archify 3.0.1 `bb6f126f1748a4079df1d263302466eb4333e3b0`를 두 작업 폴더에 checkout합니다. 프로젝트는 `8933b739ee43294605e57dca07625bad2f9e8ca4`를 checkout합니다. 아래 `<official>`, `<extended>`, `<project>`, `<output>`은 절대 경로로 대체하세요.

1. 두 Archify 폴더 각각의 `archify/`에서 `npm ci`를 실행합니다.
2. `<official>`의 architecture renderer는 수정하지 않습니다. 두 checkout 모두 `git apply <output>/renderer-extension/viewer-fixes.patch`를 적용하고 `node scripts/generate-viewer.mjs`를 실행합니다. 이 패치는 Copy/reader layout/camera resize만 변경하며 architecture renderer는 포함하지 않습니다. `<extended>`에서 `git apply <output>/renderer-extension/archify-extension.patch`를 실행합니다. `archify/`에서 `node scripts/generate-validators.mjs`를 실행합니다.
3. 다이어그램별로 아래 공식 CLI를 사용합니다. System/ROS에 확장 renderer를 적용하지 않습니다.

```sh
node <official>/archify/bin/archify.mjs finalize architecture <output>/data/01_system.json <output>/01_system.html --repo-root <project> --quality standard --json
node <official>/archify/bin/archify.mjs finalize architecture <output>/data/02_ros2.json <output>/02_ros2.html --repo-root <project> --quality standard --json
node <extended>/archify/bin/archify.mjs finalize architecture <output>/data/03_erd.json <output>/03_erd.html --repo-root <project> --quality standard --json
node <extended>/archify/bin/archify.mjs finalize architecture <output>/data/04_flow.json <output>/04_flow.html --repo-root <project> --quality standard --json
```

기존 browser-check sidecar가 다른 HTML SHA를 가리키면 그 파일을 작업 폴더 밖으로 옮긴 후 재실행합니다. unowned evidence 충돌을 pass로 처리하지 마세요. 로컬 Chrome이 없으면 browser/visual gate가 skipped입니다. `ARCHIFY_CHROME`에 실제 실행 파일을 지정하고 browser-check/visual-check를 다시 실행할 수 있습니다.

4. Python에 beautifulsoup4,lxml,cairosvg,tinycss2,cssselect2,pillow를 설치하고 시스템에 Noto Sans CJK KR을 설치합니다. `python renderer-extension/generate_assets.py`를 실행하면 최신 HTML의 원본 SVG 기하·텍스트에서 standalone SVG/PNG와 embedded preview를 다시 생성합니다. SVG geometry를 수작업 수정하지 않습니다. dark theme CSS 토큰과 export용 SVG attribute casing만 정규화합니다. PNG는 native viewer Export와 별개입니다.
5. candidate/HTML/receipt SHA와 embedded payload를 대조하고 manifest를 다시 작성합니다. 생성 후 직접 브라우저 기능/육안 검사를 별도로 수행합니다.

확장 renderer는 shape·fields가 없는 일반 component를 수정하지 않은 공식 renderComponent 함수에 위임합니다. START/END semantic kind, 도형 경계 접점, TYPE/NAME/KEY 및 컬럼/제약 텍스트 검사를 추가했습니다. 이번 UI 수정은 viewer export/reader-layout JS에 한정되며 검색·Path·LENS·MAP·발표·Export·Live/Still 효과를 유지합니다. 온라인 편집기 사용 기록으로 해석하지 마세요.


## PNG completion / 최종 포장 게이트

`generate_assets.py`는 추가 `png_integrity.py`를 사용합니다. PNG를 메모리에서 생성하고 chunk CRC/IEND/full Pillow load를 확인한 다음 fsync/atomic replace합니다. 생성이 끝난 뒤 `python renderer-extension/package_delivery.py /absolute/output.zip`을 실행하세요. 현재 candidate/HTML/receipt가 맞는 상태에서만 실행합니다. 스크립트는 manifest 작성→ZIP→별도 압축 해제→모든 해시/size/PNG decoding→기록 포함 재포장→FINAL ZIP 별도 압축 해제 재검사를 수행합니다. ZIP 무결성과 이미지 디코딩은 별도 검사입니다. Pillow dependency가 필요합니다.


Receipt의 input/output 절대 경로는 생성 당시 작업 폴더를 기록합니다. 다른 폴더로 ZIP을 풀고 공식 CLI 재검사를 하려면 새 경로에서 finalize해 receipt를 다시 생성하세요. 이전 delivery/browser/finalize sidecar를 별도 보관하고 실행하면 경로 소유권 충돌을 피할 수 있습니다. 배포 파일 해시 무결성과 CLI의 경로/파일 소유권 검사는 구분됩니다. 중단된 delivery lock은 소유 PID 종료와 내용을 먼저 확인한 뒤 외부 보관·복구해야 하며, 활성 lock을 지우지 마세요.

## 새 폴더에 압축 해제한 배포본 재생성 (권장 실행 명령)

위의 checkout / npm ci / extension patch / Python 의존성 준비 후, ZIP을 새 폴더에 풀고 다음을 실행합니다. `regenerate.py`는 기존 완료 receipt를 패키지 밖의 새 보관 폴더로 이동한 뒤 위의 네 finalize 명령을 실제 실행하고 SVG·PNG·embedded preview를 재생성합니다. candidate와 모든 주요 산출물의 재생성 전후 SHA를 비교합니다. Chrome 미설치로 skipped인 browser gate를 pass로 바꾸지 않습니다.

```sh
python <output>/renderer-extension/regenerate.py --official <official> --extended <extended> --project <project>
python <output>/renderer-extension/package_delivery.py /absolute/final-output.zip
```

포장 제외 규칙: `*.delivery-lock.json`, `*.delivery-pending.json`, 숨김 파일/디렉터리(디렉터리 lock·임시 delivery snapshot 포함), `__pycache__`, `specification.snapshot.json`. 완료 `*.delivery.json`과 finalize/browser/visual 검사 기록은 유지합니다. ZIP 압축 해제 검사도 같은 제외 규칙을 적용하며 manifest의 파일 집합이 실제 추출 파일과 정확히 일치하는지 확인합니다. 실행 상태가 발견되면 재생성 스크립트는 자동 삭제하지 않고 소유권 확인을 위해 중단합니다.

## 현재 UI 패치 검증

두 checkout에 viewer-fixes.patch를 적용한 뒤 generate-viewer.mjs를 실행해야 합니다. Python은 동봉 requirements.txt의 버전으로 설치하고 Noto Sans CJK KR 폰트를 사용하면 현재 이미지 재생성 환경을 재현할 수 있습니다. `node --test <output>/renderer-extension/ui-regression.test.mjs`는 현재 cwd에 archify checkout이 있을 때 실행하거나 ARCHIFY_REPO 환경 변수로 checkout 경로를 지정하세요. 실제 클립보드/시각 안정성 검증과는 별개입니다.

재생성 초기 상태가 비어 있음을 확인한 뒤, 자신이 실행하고 종료를 기다린 CLI의 완료 receipt·candidate·HTML SHA 및 현재 경로와 일치하는 잔류 상태만 패키지 밖으로 보관합니다. 해당 조건의 provenance-locked/failure에 한해 최대 2회 재시도하며 모든 시도와 복구 내역을 relocated-regeneration.json에 기록합니다. 기존 또는 외부 실행 lock, 해시 불일치, 다른 오류는 자동 복구하지 않고 중단합니다.

## 첨부 Cobot3 비율 적용
System/ROS는 첨부 참고본과 동일한 standard 품질 프로필로 finalize합니다(위 명령에 명시). ERD/Flow는 showcase를 유지합니다. standard 통과는 showcase 제약 검사 통과를 의미하지 않습니다. System 1563:1160, ROS 1789:932 비율을 유지하면서 양쪽 캔버스 폭은 1240으로 잡아 기존 원본 글자 크기를 유지했습니다. ERD/Flow candidate는 바이트 단위 유지합니다.

## 첨부 Cobot3 비율 적용
System/ROS는 첨부 참고본과 동일한 standard 품질 프로필로 finalize합니다(위 명령에 명시). ERD/Flow는 showcase를 유지합니다. standard 통과는 showcase 제약 검사 통과를 의미하지 않습니다. System 1563:1160, ROS 1789:932 비율을 유지하면서 양쪽 캔버스 폭은 1240으로 잡아 기존 원본 글자 크기를 유지했습니다. ERD/Flow candidate는 바이트 단위 유지합니다.

모바일 수정: 외부 상대 iframe 의존성을 없애 index.html도 embedded preview와 같은 독립 HTML로 생성합니다. wrapper 수정은 site-wrapper.html에 적용한 뒤 generate_assets.py를 실행합니다. 도면 HTML을 직접 바꾸지 않습니다.

최신 변경: viewer-fixes.patch는 Copy Diagram 버튼과 Copy 사전 준비 호출을 제거합니다. 이전 Copy fallback 설명은 과거 변경 설명이며, 현재 사용자 메뉴에 Copy가 없습니다. 다른 Export 항목은 그대로 유지합니다.

최신 변경: viewer-fixes.patch는 Copy Diagram 버튼과 Copy 사전 준비 호출을 제거합니다. 이전 Copy fallback 설명은 과거 변경 설명이며, 현재 사용자 메뉴에 Copy가 없습니다. 다른 Export 항목은 그대로 유지합니다.
