#!/usr/bin/env python3
"""team.json의 GitHub 사용자명을 검증하고 .github/CODEOWNERS의 자리표시자를 바꾼다.
  python3 scripts/github/apply_team.py
"""
import json, pathlib, re, shutil, subprocess, sys

if not shutil.which("gh"):
    sys.exit("gh CLI가 필요합니다: sudo apt install gh && gh auth login")

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLACEHOLDER = {"학민": "@HAKMIN_ID", "현지": "@HYEONJI_ID", "병후": "@BYEONGHU_ID", "의석": "@UISEOK_ID"}

team = {k: v.strip() for k, v in json.loads((ROOT / "scripts/github/team.json").read_text(encoding="utf-8")).items() if not k.startswith("_")}
bad = False
for name, login in team.items():
    if not login:
        print(f"[비어 있음] {name}: 사용자명을 채워주세요"); bad = True
    elif "@" in login or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})", login):
        print(f"[형식 오류] {name}: '{login}' 은 사용자명이 아닙니다 (이메일 불가, github.com/<사용자명>의 그 값)"); bad = True
    else:
        r = subprocess.run(["gh", "api", f"users/{login}", "-q", ".login"], text=True, capture_output=True)
        if r.returncode != 0:
            print(f"[없는 계정] {name}: '{login}' 을 GitHub에서 찾지 못했습니다"); bad = True
        else:
            print(f"[확인] {name}: {r.stdout.strip()}")
if bad:
    sys.exit("team.json을 고친 뒤 다시 실행하세요. CODEOWNERS는 바꾸지 않았습니다.")

p = ROOT / ".github/CODEOWNERS"
s = p.read_text(encoding="utf-8")
for name, ph in PLACEHOLDER.items():
    s = s.replace(ph, "@" + team[name])
p.write_text(s, encoding="utf-8")
print("CODEOWNERS 갱신 완료. git diff .github/CODEOWNERS 로 확인하세요.")
