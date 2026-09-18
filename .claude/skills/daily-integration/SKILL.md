---
name: daily-integration
description: 저녁 통합 빌드 절차(현지 주관). main을 받아 전체 빌드와 sim 종단 실행을 하고 결과를 기록한다. "저녁 통합 돌리자" 요청에 사용한다.
---
1. `gh pr list --state open`으로 열린 PR을 확인한다. CI가 통과한 PR 중 오늘 머지할 것을 사람에게 묻는다.
2. `git switch main && git pull` 후 `ws_cobot1`을 클린 빌드한다(`rm -rf build install log` 후 `colcon build`).
3. `colcon test`를 돌린다.
4. sim 종단 실행은 Virtual Mode에서만 한다: 사람에게 `sodvir` 기동을 요청하고, bringup을 sim 입력원으로 띄워 시작→5점 탐색→직육면체 결과까지 확인한다.
5. 결과를 `docs/test-reports/daily/<날짜>.md`에 적는다: 머지된 PR, 빌드·테스트 결과, 종단 실행 결과, 깨진 곳과 담당자.
6. 깨졌으면 원인 패키지 담당자를 지정해 `bug` 이슈를 만든다. 통과했으면 `git tag daily-<MMDD>`를 제안한다.
