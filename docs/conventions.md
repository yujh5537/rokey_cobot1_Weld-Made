# 작업 규칙 (5일 MVP용)

## 브랜치
- `main`: 항상 빌드되는 상태. 직접 푸시 금지, PR로만 들어간다.
- 작업 브랜치: `t<이슈ID>-<설명>` (예: `t16-contact-detector`). 최신 main에서 만든다.
- 브랜치 수명은 하루 이내를 목표로 한다. 저녁 통합 전에 PR을 올린다.
- 실기 PC에서 튜닝한 파라미터도 같은 방식으로 PR한다(`tune-0920-threshold` 등). 실기 PC에만 남은 값은 없는 값이다.

## 머지 조건
| 변경 경로 | 조건 |
|---|---|
| 일반 (자기 패키지) | CI(ros, web) 통과 → 작성자가 squash merge |
| CODEOWNERS 경로 (계약, 인터페이스, geometry_estimator, CLAUDE.md, .github) | CI 통과 + 코드 오너 1명 승인 |
| 다른 사람 소유 패키지 | 소유자에게 리뷰 요청 (강제는 아니지만 지킨다) |

리뷰 요청을 받으면 2시간 안에 본다. 계약 PR은 스탠드업이나 메신저로 전원에게 알린다.

## PR
- 이슈 1개 = PR 1개. 변경 파일 15개 초과면 쪼갠다.
- 제목: `[T13] execute_motion Action 구현`. 본문에 `Closes #번호`.
- 작성자는 Claude가 쓴 코드라도 본인이 설명할 수 있어야 한다.
- 코드를 바꾸면 관련 docs를 같은 PR에서 고친다.

## 커밋
- 한국어 가능. `feat: `, `fix: `, `docs: `, `test: `, `tune: `(실기 파라미터), `chore: `.

## 하루 흐름
1. 아침 스탠드업 15분: 어제 머지된 것, 오늘 이슈, 계약 변경 예고, 실기 점유 확인
2. 작업: 이슈 → 브랜치 → 계획 → 구현 → PR
3. 저녁 통합(현지 주관): 머지 마감 → main 클린 빌드 → sim 종단 실행 → `docs/test-reports/daily/`에 기록 → `daily-MMDD` 태그
4. 통합이 깨지면 원인 패키지 담당자가 당일 고친다. 못 고치면 해당 PR을 revert한다.
5. 9/21(월) 저녁 기능 동결 이후에는 `bug` 라벨 이슈의 PR만 머지한다.

## 테스트
- 순수 계산(geometry_estimator, 편향 보정, 상태 기계 전이)은 ROS 없이 pytest로 돌린다.
- 실기·DSR이 필요한 테스트는 `@pytest.mark.hw`로 표시한다. CI는 이것을 제외한다.
- `ros2 pkg create`가 만드는 copyright/flake8/pep257 테스트는 지운다.

## Claude 사용
- Claude Code: 레포 안에서 구현·테스트·PR. 팀 공통 지시는 `CLAUDE.md`와 `.claude/`, 개인 역할은 `CLAUDE.local.md`.
- claude.ai: 설계 토론, 문서 초안, 시험 결과 분석. **채팅에서 내린 결정은 `docs/decisions/` 또는 `docs/contracts/`에 PR로 올라와야 결정이다.**
- 실기 로봇 명령은 Claude에게 시키지 않는다.
