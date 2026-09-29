#!/usr/bin/env bash
# 용접선을 하나씩 — 선 하나가 끝나면(마무리 홈 복귀까지) 다음 선을 보낸다. 2026-09-29 시연 절차(#220 웹 선택기 전까지).
#
#   sod && source ws_cobot1/install_main/setup.bash
#   docs/env/weld_one_by_one.sh 20260923-183211-3702 0 1 2 3 4 6 7      # L5 제외
#   docs/env/weld_one_by_one.sh 20260923-183211-3702 1                  # L1 만
#
# - 각 선은 별도 /weld/run goal(start_line = end_line). weld_manager 는 한 goal 이 끝날 때 결과 → 홈 복귀(7.3) 순이라
#   Result 가 와도 로봇은 아직 움직인다. 그래서 /weld/state 의 phase 가 IDLE · DONE · ERROR · STOPPED 로 돌아올 때까지 기다린다.
# - 한 선이 실패(success=false)하면 멈춘다. 다음 선을 계속하려면 사람이 다시 부른다(D33 은 한 goal 안에서만 계속).
# - 실기 명령이다. 입회자(비상정지) 곁에서 사람이 실행한다(CLAUDE.md 규칙 1).
set -u
if [ $# -lt 2 ]; then echo "usage: $0 <scan_id> <line> [line ...]"; exit 2; fi
SCAN_ID=$1; shift
TAG=$(date +%H%M%S)
wait_idle() {
  # phase: 0 IDLE · 5 DONE · 6 ERROR · 8 STOPPED = 로봇이 섰다. 1~4 · 7 · 9 = 아직 움직인다
  for _ in $(seq 120); do
    p=$(timeout 3 ros2 topic echo /weld/state --once --field phase 2>/dev/null | head -1 | tr -d '[:space:]')
    case "$p" in 0|5|6|8) return 0;; esac
    sleep 1
  done
  echo "!! /weld/state 가 2 분 안에 멈춤 상태로 돌아오지 않았다 (phase=$p)"; return 1
}
for L in "$@"; do
  echo "=== L$L ($(date +%H:%M:%S))"
  OUT=$(ros2 action send_goal /weld/run contact_scan_interfaces/action/RunWeld \
    "{request_id: one-$TAG-L$L, scan_id: '$SCAN_ID', start_line: $L, end_line: $L}" 2>&1)
  echo "$OUT" | awk '/^Result:/{f=1} f&&/^(success|reason_code|detail):/{print "    "$0} /^Goal finished/{print "    "$0}'
  OK=$(echo "$OUT" | awk '/^Result:/{f=1} f&&/^success:/{print $2; exit}')
  echo "    홈 복귀를 기다린다…"; wait_idle || exit 1
  if [ "$OK" != "true" ]; then echo "!! L$L 실패 — 여기서 멈춘다. 나머지는 다시 부른다"; exit 1; fi
done
echo "=== 끝 ($(date +%H:%M:%S))"
