# 레포 구축 순서

## A. 현지 (T05, 약 40분)

### 1. 레포 만들기
기존 `~/ws_cobot_pjt`가 레포 루트가 된다. 이 스캐폴드의 내용을 그 위에 풀고 시작한다.

```bash
cd ~/ws_cobot_pjt
unzip -o ~/Downloads/ws_cobot_pjt_scaffold.zip -d .     # 숨김 폴더(.claude, .github) 포함
mv docs/setup_sudo.sh docs/upgrade_apt.sh docs/env/ 2>/dev/null || true   # 기존 설치 스크립트를 env로
git init -b main
git add -A && git status                                  # ws_dsr, DartPlatform, *.pdf, .env가 목록에 없는지 확인
git commit -m "chore: 레포 골격, 계약 초안, Claude 설정"
gh repo create <레포이름> --public --source=. --push
```

공개 레포이므로 첫 커밋 전에 확인한다: 강의안 PDF·두산 매뉴얼 없음, `ws_dsr` 소스 없음, `.env`·토큰 없음. `docs/env/setup-record-20260916.md`에는 PC 호스트명과 사설 IP가 적혀 있다. 신경 쓰이면 지우고 올린다.

### 2. 팀원 초대와 아이디 반영
필요한 것은 이메일이 아니라 **GitHub 사용자명**(`github.com/<사용자명>`의 그 값)이다. 이메일을 CODEOWNERS나 team.json에 적으면 담당자 지정이 실패하고, 공개 레포에 개인 이메일이 노출된다.

1. GitHub → Settings → Collaborators → Add people. 여기서는 이메일로 초대해도 된다(Write 권한).
2. 세 명이 초대를 수락하면 사용자명을 확인한다.
   ```bash
   gh api repos/{owner}/{repo}/collaborators -q '.[].login'
   ```
3. `scripts/github/team.json`에 사용자명을 적고 반영한다. 계정 존재 여부를 검사한 뒤 CODEOWNERS를 바꾼다.
   ```bash
   python3 scripts/github/apply_team.py
   ```
초대 수락 전에는 담당자 지정과 CODEOWNERS가 동작하지 않는다. 급하면 3번(이슈 생성)을 먼저 하고, 담당자는 나중에 `gh issue edit <번호> --add-assignee <사용자명>`으로 붙인다.

### 3. 이슈·마일스톤 생성
```bash
python3 scripts/github/create_issues.py --dry-run | less   # 내용 확인
python3 scripts/github/create_issues.py                    # 라벨 14개, 마일스톤 M1~M5, 이슈 42개
```
진행률은 Milestones 화면의 막대가 엑셀 "진행 현황" 표를 대신한다. 실기 점유는 `label:hw:real-robot`으로 거른다. 칸반이 필요하면 Projects에서 보드를 만들고 "Auto-add"를 켠다(선택).

### 4. 브랜치 보호
2번의 변경을 커밋·푸시해서 CI가 한 번 돈 다음에 실행한다.
```bash
git add -A && git commit -m "chore: 팀 아이디 반영" && git push
bash scripts/github/protect_main.sh
```
설정 뒤 테스트 PR 두 개로 확인한다: README 한 줄 수정 PR은 CI 통과 후 본인이 머지할 수 있어야 하고, `docs/contracts/` 수정 PR은 코드 오너 승인 전까지 막혀야 한다. 두 번째가 막히지 않으면 Settings → Branches에서 "Require review from Code Owners"를 확인한다.

### 5. (선택) PR에서 @claude 쓰기
Claude Code에서 `/install-github-app`을 실행하면 GitHub 앱 설치, 시크릿 등록, 워크플로 PR 생성까지 안내한다. 5일 일정에서는 모든 PR 자동 리뷰보다 **계약 PR과 안전 관련 PR에서만 `@claude review`를 멘션**하는 방식을 권한다. 공개 레포이므로 API 키·토큰은 반드시 Actions secrets에만 둔다.

### 6. Claude Code 설정 확인
레포 루트에서 `claude`를 실행하고 `/memory`로 CLAUDE.md와 rules가 잡히는지, `/permissions`로 deny 규칙(`sodreal`, `mode:=real`)이 보이는지 확인한다. deny 규칙은 보조 수단이다. 실기 PC에서는 Claude에게 터미널 실행을 맡기지 않는 것이 원칙이다.

## B. 팀원 (각 10분)
```bash
cd ~ && mv ws_cobot_pjt ws_cobot_pjt.bak                 # 기존 폴더가 있으면
git clone https://github.com/<소유자>/<레포이름>.git ws_cobot_pjt
mv ws_cobot_pjt.bak/ws_dsr ws_cobot_pjt.bak/DartPlatform ws_cobot_pjt/   # 빌드해 둔 것을 옮긴다 (gitignore 대상)
cd ws_cobot_pjt
cp CLAUDE.local.md.example CLAUDE.local.md                # 본인 이름·담당 패키지를 적는다
gh auth login
```
`ws_dsr`을 옮긴 뒤에는 `install/` 안의 절대 경로가 그대로인지(같은 `~/ws_cobot_pjt/ws_dsr`) 확인하고 `sod`가 동작하는지 본다.

작업 시작은 Claude Code에서 `이슈 #13 작업해줘`라고 하면 된다(`start-issue` 스킬). 규칙은 `docs/conventions.md` 한 장이다.

## C. 오늘(M1) 안에 레포에 들어와야 하는 것
| 담당 | 내용 | 이슈 |
|---|---|---|
| 전원 | `docs/contracts/` v0.1 동결 (회의 결과를 한 PR로) | T01 |
| 병후 | `contact_scan_interfaces` 빌드 → **가장 먼저 머지**. 나머지 세 명이 이것을 기다린다 | T09 |
| 학민 | `units-frames.md`, `api-check-log.md`, `versions.md` 채우기 | T02~T04 |
| 현지 | `contact_scan_bringup`, contact_detector 골격, 저녁 첫 통합 기록 | T05~T07 |
| 의석 | compose 골격, 프런트 골격, 목업 발행기 | T11, T12 |
