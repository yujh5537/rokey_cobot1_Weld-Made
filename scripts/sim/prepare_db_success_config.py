#!/usr/bin/env python3
"""Combine the current sim.yaml with the successful DB scan's scene settings."""

import argparse
from pathlib import Path

import yaml


HERE = Path(__file__).resolve().parent
BASE_CONFIG = HERE.parents[1] / "ws_cobot1/src/contact_scan_bringup/config/sim.yaml"
PROFILE = HERE / "db_success_20260923.yaml"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", required=True, type=Path, help="완성된 ROS 파라미터 YAML")
    parser.add_argument("--web-env-output", type=Path, help="Vite 환경 변수 파일")
    args = parser.parse_args()

    base = yaml.safe_load(BASE_CONFIG.read_text(encoding="utf-8"))
    profile = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    for node, parameters in profile["ros"].items():
        base[node]["ros__parameters"].update(parameters)
    base["scan_manager"]["ros__parameters"]["result_dir"] = str(
        (args.output.parent / "results").resolve()
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        f"# main sim.yaml + DB scan {profile['source_scan_id']}\n"
        + yaml.safe_dump(base, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    print(args.output)
    if args.web_env_output:
        args.web_env_output.parent.mkdir(parents=True, exist_ok=True)
        args.web_env_output.write_text(
            "".join(f"{key}={value}\n" for key, value in profile["web"].items()),
            encoding="utf-8",
        )
        print(args.web_env_output)


if __name__ == "__main__":
    main()
