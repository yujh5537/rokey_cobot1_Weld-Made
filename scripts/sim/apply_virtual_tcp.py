#!/usr/bin/env python3
"""Register the visual probe tip TCP on the local DRCF emulator.

Run after the M0609 virtual driver starts and before starting a scan. The
calibrated offset lives in contact_scan_bringup/config/sim.yaml.
"""

import argparse
import math
from pathlib import Path
import subprocess
import sys

import rclpy
import yaml
from dsr_msgs2.srv import (
    ConfigCreateTcp,
    ConfigDeleteTcp,
    GetCurrentPosx,
    GetCurrentTcp,
    GetCurrentToolFlangePosx,
    SetCurrentTcp,
    SetRobotMode,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "ws_cobot1/src/contact_scan_bringup/config/sim.yaml"
TCP_NAME = "rg2_probe_tip"
PREFIX = "/dsr01/dsr_controller2/"


def require_virtual_driver():
    """Refuse to change a controller unless the localhost virtual launch is running."""
    emulator = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", "dsr01_emulator"],
        capture_output=True, text=True, check=False,
    )
    if emulator.returncode or emulator.stdout.strip() != "true":
        raise RuntimeError("dsr01_emulator 컨테이너가 실행 중이지 않습니다")
    launches = subprocess.run(
        ["pgrep", "-af", "ros2 launch m0609_rg2_bringup bringup.launch.py"],
        capture_output=True, text=True, check=False,
    ).stdout.splitlines()
    if not any("mode:=virtual" in line and "host:=127.0.0.1" in line for line in launches):
        raise RuntimeError("localhost mode:=virtual M0609 드라이버를 확인할 수 없습니다")
    if any("mode:=real" in line for line in launches):
        raise RuntimeError("실기 드라이버가 함께 실행 중이므로 TCP를 변경하지 않습니다")


def call(node, service_type, name, request, *, required=True):
    client = node.create_client(service_type, PREFIX + name)
    if not client.wait_for_service(timeout_sec=5.0):
        raise RuntimeError(f"서비스 연결 실패: {name}")
    future = client.call_async(request)
    rclpy.spin_until_future_complete(node, future, timeout_sec=5.0)
    if not future.done():
        client.remove_pending_request(future)
        raise RuntimeError(f"서비스 응답 시간 초과: {name}")
    response = future.result()
    if required and (response is None or not response.success):
        raise RuntimeError(f"서비스 실패: {name}")
    return response


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    require_virtual_driver()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    z_mm = float(config["virtual_tcp"]["ros__parameters"]["z_mm"])
    if not math.isfinite(z_mm) or z_mm <= 0:
        raise ValueError("virtual_tcp.z_mm는 양수여야 합니다")

    rclpy.init()
    node = rclpy.create_node("apply_virtual_tcp")
    try:
        call(node, SetRobotMode, "system/set_robot_mode", SetRobotMode.Request(robot_mode=0))
        try:
            call(node, ConfigDeleteTcp, "tcp/config_delete_tcp",
                 ConfigDeleteTcp.Request(name=TCP_NAME), required=False)
            call(node, ConfigCreateTcp, "tcp/config_create_tcp",
                 ConfigCreateTcp.Request(name=TCP_NAME, pos=[0.0, 0.0, z_mm, 0.0, 0.0, 0.0]))
            call(node, SetCurrentTcp, "tcp/set_current_tcp", SetCurrentTcp.Request(name=TCP_NAME))
        finally:
            call(node, SetRobotMode, "system/set_robot_mode",
                 SetRobotMode.Request(robot_mode=1))
        tcp = call(node, GetCurrentTcp, "tcp/get_current_tcp", GetCurrentTcp.Request())
        posx = call(node, GetCurrentPosx, "aux_control/get_current_posx",
                    GetCurrentPosx.Request(ref=0))
        flange = call(node, GetCurrentToolFlangePosx,
                      "aux_control/get_current_tool_flange_posx",
                      GetCurrentToolFlangePosx.Request(ref=0))
        distance = math.dist(posx.task_pos_info[0].data[:3], flange.pos[:3])
        if tcp.info != TCP_NAME or abs(distance - z_mm) >= 0.2:
            raise RuntimeError(f"TCP 검증 실패: name={tcp.info!r}, 거리={distance:.2f} mm")
        print(f"OK: {TCP_NAME}, TCP−flange={distance:.2f} mm (설정 {z_mm:.2f} mm)")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    try:
        main()
    except (KeyError, ValueError, OSError, RuntimeError) as exc:
        print(f"Virtual TCP 등록 실패: {exc}", file=sys.stderr)
        sys.exit(1)
