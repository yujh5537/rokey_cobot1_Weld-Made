#!/usr/bin/env bash
# 제출용 소스 zip 을 만든다 (docs/deliverables/README.md "소스코드 (.zip)").
#
#   docs/deliverables/make-source-zip.sh [REF] [OUT_DIR]
#     REF     zip 에 담을 커밋 · 브랜치 (기본 origin/main). 제출 전에는 최종 머지 커밋으로 만든다
#     OUT_DIR zip 을 둘 디렉터리 (기본 현재 디렉터리)
#
# - git archive 로 REF 의 **추적 파일만** 담는다. build · install · log · node_modules · data · .coverage 같은
#   작업 부산물은 추적하지 않으므로 구조적으로 빠진다(로컬 작업 트리의 상태와 무관).
# - 담는 경로: ws_cobot1/src · ws_cobot1/requirements.txt · backend · frontend · docker · docs/env/*.py
#   · README.md(실행 순서 runbook). 그 밖의 docs 는 제외한다.
# - zip 안의 최상위 폴더는 ASCII(weld-made/)다. **경로에 한글이 있으면 contact_scan_interfaces 빌드가 실패한다**
#   (rosidl_generate_interfaces 의 CMake list 오류, 2026-09-24 확인). 파일 이름만 제출 양식(한글)을 따른다.
#   받는 쪽 안내: 한글이 없는 경로에서 `unzip <파일>.zip` → weld-made/ws_cobot1 에서 colcon build
# - 만든 뒤 임시 디렉터리에 풀어 제외 목록 검사와 파일 수를 출력한다. colcon build 확인은 --build 를 세 번째 인자로 준다
#   (ws_dsr 를 먼저 source 해야 한다: `sod`).
set -euo pipefail

REF="${1:-origin/main}"
OUT_DIR="${2:-.}"
BUILD="${3:-}"
NAME="C-3_협동1_박병후_김학민_남현지_정의석"   # zip 파일 이름(제출 양식)
PREFIX="weld-made"                                  # zip 안의 최상위 폴더. ASCII 여야 한다(위 설명)
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

PATHS=(ws_cobot1/src backend frontend docker README.md)
[ -n "$(git ls-tree --name-only "$REF" -- ws_cobot1/requirements.txt)" ] && PATHS+=(ws_cobot1/requirements.txt)
mapfile -t ENV_PY < <(git ls-tree --name-only "$REF" -- docs/env/ | grep '\.py$')
PATHS+=("${ENV_PY[@]}")

mkdir -p "$OUT_DIR"
ZIP="$(cd "$OUT_DIR" && pwd)/$NAME.zip"
git archive --format=zip --prefix="$PREFIX/" -o "$ZIP" "$REF" -- "${PATHS[@]}"
echo "[zip] $ZIP  (REF $REF = $(git rev-parse --short "$REF"))"

CHECK="$(mktemp -d)"
trap 'rm -rf "$CHECK"' EXIT
unzip -q "$ZIP" -d "$CHECK"
BAD=$(cd "$CHECK/$PREFIX" && find . \( -name build -o -name install -o -name log -o -name node_modules -o -name data \
      -o -name .coverage -o -name __pycache__ -o -name '*.bag' -o -name '*.db3' \) -print | head -5)
if [ -n "$BAD" ]; then
    echo "[zip] 제외해야 할 것이 들어 있다:"; echo "$BAD"; exit 1
fi
echo "[zip] 파일 $(find "$CHECK/$PREFIX" -type f | wc -l) 개 · $(du -sh "$ZIP" | cut -f1) · 제외 목록 검사 통과"
echo "[zip] 최상위: $(ls "$CHECK/$PREFIX" | tr '\n' ' ')"

if [ "$BUILD" = "--build" ]; then
    (cd "$CHECK/$PREFIX/ws_cobot1" && colcon build --event-handlers console_cohesion- 2>&1 | tail -3)
fi
