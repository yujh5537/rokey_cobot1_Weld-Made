---
name: open-pr
description: 현재 브랜치의 변경으로 PR을 만든다. 로컬 빌드·테스트를 확인하고 PR 템플릿을 채운다. "PR 올려줘" 요청에 사용한다.
---
1. `git diff --stat origin/main`으로 변경 파일을 확인한다. 15개를 넘거나 이슈 범위 밖 파일이 있으면 멈추고 나누는 방법을 제안한다.
2. ROS 변경이면 `colcon build`와 `colcon test`, 웹 변경이면 해당 빌드·테스트를 돌려 결과를 확인한다.
3. 계약·인터페이스를 건드렸으면 `docs/contracts/CHANGELOG.md`가 갱신됐는지 확인한다.
4. `gh pr create`로 `.github/pull_request_template.md` 형식을 채운다. 본문에 `Closes #번호`를 넣는다.
5. "sim에서 확인한 것"과 "실기에서 아직 확인하지 않은 것"을 나눠 적는다. 확인하지 않은 것을 확인했다고 적지 않는다.
6. 작성자가 설명할 수 있도록, 핵심 설계 선택 2~3개를 PR 본문에 짧게 요약한다.
