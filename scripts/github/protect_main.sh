#!/usr/bin/env bash
# main 브랜치 보호: PR 필수, CI(ros, web) 통과 필수, CODEOWNERS 경로만 승인 필수, 강제 푸시 금지.
# 공개 레포는 무료 플랜에서도 동작한다. 레포 admin이 실행한다. CI가 한 번 돈 뒤에 실행해야 체크 이름이 잡힌다.
set -euo pipefail
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)

gh api -X PUT "repos/$REPO/branches/main/protection" --input - <<JSON
{
  "required_status_checks": { "strict": false, "contexts": ["ros", "web"] },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 0,
    "require_code_owner_reviews": true,
    "dismiss_stale_reviews": false
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON

# squash merge만 허용, 머지된 브랜치 자동 삭제
gh api -X PATCH "repos/$REPO" -F allow_squash_merge=true -F allow_merge_commit=false -F allow_rebase_merge=false -F delete_branch_on_merge=true >/dev/null
echo "완료: $REPO main 보호 설정. 테스트 PR로 (1) CI 필수 (2) 계약 경로의 코드 오너 승인 필수 (3) 일반 경로 본인 머지를 확인하세요."
