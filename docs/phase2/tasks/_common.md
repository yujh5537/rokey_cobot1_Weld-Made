# 공통 작업 절차 (P1~P4 지시서에 포함되는 내용)

## 시작
1. `git fetch --all --prune`, `origin/main` 에서 `p2-<주제>` 브랜치. 열린 PR · worktree 확인.
2. 읽을 것: `docs/phase2/README.md` → 자기 지시서 → `weld-motion.md` → `weld-ros-interfaces.md`(자기 절) → (웹) `weld-mqtt-schema.md`. 1차 문서는 지시서가 가리키는 절만.
3. 출력 맨 위에 "이 task 가 무엇인지" 2~4 문장 소개글.

## 작업 절차
1. **설계 → 확인 → 코드.** high-level design(모듈 · 책임 · 자료 흐름 · 바꾸지 않는 것) → detail design(함수 · 클래스 시그니처, 자료 구조, 스레드 · 락, 오류 · 경계, 테스트 목록) → pseudo code(핵심 경로) 를 먼저 브리핑하고 담당자 확인 뒤 real code. 지시서의 초기 설계는 출발점이다 — 더 나은 안이 있으면 이유와 함께 바꿔 제안한다.
2. **임의 판단 금지.** 계약 · 코드 · 지시서가 서로 다르거나 불분명하면 추측하지 말고 멈춰 묻는다(선택지 + 권고안). 질문은 모아서, 답과 무관한 부분은 계속 진행.
3. **시뮬레이션 검증 포함.** 실기 금지(규칙 1). sim 입력원 · Virtual Mode(`sodvir`, 에뮬레이터) · 가짜 상대 노드. 망 격리: `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST`, `ROS_DOMAIN_ID` 는 31~39 중 조용한 번호(30 은 실기 공용). 에뮬레이터는 PC 에 1 개, 끝나면 `docker rm -f dsr01_emulator`.
4. **머지 전 재검.** PR 은 draft 로. 맥락 없는 새 서브에이전트에게 diff 전체(코드 · 계약 일치 · 규칙 · 범위 밖 파일) 재검을 맡기고, 찾은 문제만 고친다. 클린 빌드(별도 `--build-base/--install-base`)에서 테스트를 다시 돌려 수치와 함께 보고.

## 완료 보고 양식
1. **검증 기록**(설계 확인에서 바뀐 것 / 물은 것과 답 / 재검에서 찾은 것 / 재실행 명령과 수치)
2. 바꾼 파일 · 계약과 다른 점(있으면 안 된다. 있으면 계약 PR 을 먼저)
3. 실기에서 확인해야 남는 것(9/29 목록)

## 계약을 고쳐야 할 때
`docs/phase2/*.md` + `contact_scan_interfaces` + `docs/contracts/CHANGELOG.md` 를 **한 PR** 에서. 병후(계약 담당)에게 먼저 알린다. `test_contract_sync` 가 문서와 파일의 일치를 검사한다.
