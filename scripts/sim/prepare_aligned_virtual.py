#!/usr/bin/env python3
"""Build a Virtual-only fixture/config with the web table kept at world Z=400 mm.

The visible robot base is 94 mm below that table, at world Z=306 mm. ROS
base_link is therefore 306 mm above the old display origin. Translate only
Base-frame values; fixture-frame edges and dimensions must stay unchanged.
"""

import argparse
import json
from pathlib import Path

import yaml


SCAN_ID = '20260921-131938-1493'
TABLE_WORLD_Z_M = 0.400
TABLE_HEIGHT_M = 0.094
BASE_WORLD_Z_M = TABLE_WORLD_Z_M - TABLE_HEIGHT_M
REPO = Path(__file__).resolve().parents[2]


def prepare(output: Path):
    source = json.loads((REPO / 'docs/phase2/fixtures'
                         / f'sim_{SCAN_ID}.result.json').read_text())
    config = yaml.safe_load((REPO / 'ws_cobot1/src/contact_scan_bringup/config/sim.yaml').read_text())

    scan_params = config['scan_manager']['ros__parameters']
    detector_params = config['contact_detector']['ros__parameters']
    robot_params = config['robot_manager']['ros__parameters']
    fixture_z = TABLE_WORLD_Z_M - BASE_WORLD_Z_M
    assert abs(scan_params['base_to_fixture'][2] - TABLE_WORLD_Z_M) < 1e-9
    assert abs(detector_params['sim_box_origin_m'][2] - TABLE_WORLD_Z_M) < 1e-9
    assert abs(source['node_params']['base_to_fixture'][2] - TABLE_WORLD_Z_M) < 1e-9

    scan_params['base_to_fixture'][2] = fixture_z
    detector_params['sim_box_origin_m'][2] = fixture_z
    scan_params['search_origin_pose'][2] -= BASE_WORLD_Z_M
    robot_params['path_min_z_m'] -= BASE_WORLD_Z_M
    source['node_params']['base_to_fixture'][2] = fixture_z
    source['node_params']['search_origin_pose'][2] -= BASE_WORLD_Z_M

    result_dir = output / 'results'
    for name in ('scan_manager', 'weld_manager'):
        config[name]['ros__parameters']['result_dir'] = str(result_dir)
    config['mqtt_bridge'] = {'ros__parameters': {
        'broker_host': '127.0.0.1', 'broker_port': 1883}}

    result_path = result_dir / SCAN_ID / 'result.json'
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(source, indent=2) + '\n')
    (output / 'sim.yaml').write_text(yaml.safe_dump(config, sort_keys=False))
    (output / 'integration.launch.py').write_text('''from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(package=name, executable=name, name=name, output='screen',
             parameters=['%s'])
        for name in ('robot_manager', 'contact_detector', 'safety_monitor',
                     'scan_manager', 'weld_manager', 'mqtt_bridge')
    ])
''' % (output / 'sim.yaml'))
    print(f'base world z={BASE_WORLD_Z_M:.3f} m; fixture Base z={fixture_z:.3f} m')
    print(result_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('/tmp/weld-web-aligned-runtime'))
    args = parser.parse_args()
    prepare(args.output.resolve())
