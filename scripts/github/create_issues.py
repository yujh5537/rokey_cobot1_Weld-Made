#!/usr/bin/env python3
"""T01~T42를 GitHub Issues로 만든다. 라벨·마일스톤(M1~M5)도 같이 만든다.

사전 조건: gh CLI 로그인(gh auth login), 레포 디렉터리 안에서 실행.
  python3 scripts/github/create_issues.py --dry-run   # 만들 내용만 출력
  python3 scripts/github/create_issues.py             # 실제 생성
다시 실행해도 같은 [Txx] 제목의 이슈는 건너뛴다.
"""
import argparse, json, pathlib, subprocess, sys

HERE = pathlib.Path(__file__).parent
LABELS = {
    "area:robot": ("1f77b4", "robot_manager, 모션·하드웨어"),
    "area:detect": ("2ca02c", "contact_detector, geometry_estimator, safety_monitor"),
    "area:scan": ("9467bd", "scan_manager, result_store"),
    "area:bridge": ("8c564b", "mqtt_bridge"),
    "area:web": ("ff7f0e", "FastAPI, Spring Boot, React, docker"),
    "area:contract": ("d62728", "인터페이스·스키마 계약"),
    "area:infra": ("7f7f7f", "저장소, CI, 통합 빌드"),
    "area:env": ("17becf", "환경 세팅, 좌표 기준"),
    "type:impl": ("c5def5", "구현"),
    "type:test": ("fef2c0", "TR 시험"),
    "type:meeting": ("e4e669", "회의·동결"),
    "hw:real-robot": ("b60205", "실기 로봇 점유 필요"),
    "safety": ("000000", "안전 요구사항(BRD 4.5) 관련"),
    "bug": ("d73a4a", "버그, 통합 깨짐"),
}


def gh(*args, check=True, capture=True):
    r = subprocess.run(["gh", *args], text=True, capture_output=capture)
    if check and r.returncode != 0:
        sys.exit(f"gh {' '.join(args)} 실패:\n{r.stderr}")
    return r.stdout if capture else ""


def body(t):
    lines = []
    if t["brd"]:
        lines += [f"**BRD 근거**: {t['brd']} (`docs/BRD.md`)", ""]
    lines += ["**담당**: " + " · ".join(t["owners"]), ""]
    lines += ["## 수정 범위 (Claude가 건드려도 되는 경로)"]
    lines += [f"- `{p}`" for p in t["scope"]] or ["- 코드 변경 없음"]
    lines += ["", "이 범위 밖의 파일이 필요하면 고치지 말고 PR 본문이나 새 이슈에 적는다.", ""]
    if t["docs"]:
        lines += ["## 먼저 읽을 문서"] + [f"- {d}" for d in t["docs"]] + [""]
    lines += ["## 완료 조건"]
    lines += [d if d.startswith("- [") else f"- [ ] {d}" for d in t["done"]]
    if "type:impl" in t["labels"]:
        lines += ["- [ ] 동작이 바뀐 부분의 docs를 같은 PR에서 고쳤다"]
    if t["note"]:
        lines += ["", f"> {t['note']}"]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    data = json.loads((HERE / "tasks.json").read_text(encoding="utf-8"))
    team = {k: v for k, v in json.loads((HERE / "team.json").read_text(encoding="utf-8")).items() if not k.startswith("_")}

    if a.dry_run:
        for t in data["tasks"]:
            who = [team.get(o) or f"({o}: 아이디 없음)" for o in t["owners"]]
            print(f"\n=== [{t['id']}] {t['title']}\n    milestone={t['milestone']} labels={t['labels']} assignees={who}\n{body(t)}")
        return

    repo = gh("repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner").strip()
    print("대상 레포:", repo)
    for name, (color, desc) in LABELS.items():
        gh("label", "create", name, "--color", color, "--description", desc, "--force")
    have = {m["title"] for m in json.loads(gh("api", f"repos/{repo}/milestones?state=all"))}
    for m in data["milestones"]:
        if m["title"] not in have:
            gh("api", f"repos/{repo}/milestones", "-f", f"title={m['title']}", "-f", f"due_on={m['due_on']}")
    existing = {i["title"] for i in json.loads(gh("issue", "list", "--state", "all", "--limit", "500", "--json", "title"))}

    for t in data["tasks"]:
        title = f"[{t['id']}] {t['title']}"
        if any(e.startswith(f"[{t['id']}]") for e in existing):
            print("건너뜀:", title)
            continue
        cmd = ["issue", "create", "--title", title, "--body", body(t), "--milestone", t["milestone"]]
        for l in t["labels"]:
            cmd += ["--label", l]
        for o in t["owners"]:
            if team.get(o) and "@" not in team[o]:
                cmd += ["--assignee", team[o]]
            else:
                print(f"  (담당자 미지정: {o}의 사용자명이 team.json에 없음)")
        print(gh(*cmd).strip())


if __name__ == "__main__":
    main()
