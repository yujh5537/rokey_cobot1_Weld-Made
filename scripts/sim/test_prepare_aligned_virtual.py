"""Regression check for the Virtual-only table/robot frame translation."""

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from prepare_aligned_virtual import BASE_WORLD_Z_M, REPO, SCAN_ID, prepare


class AlignedVirtualTest(unittest.TestCase):
    def test_runtime_uses_one_world_frame_without_moving_fixture_geometry(self):
        original = json.loads((REPO / 'docs/phase2/fixtures'
                               / f'sim_{SCAN_ID}.result.json').read_text())
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            prepare(runtime)
            config = yaml.safe_load((runtime / 'sim.yaml').read_text())
            result = json.loads((runtime / 'results' / SCAN_ID / 'result.json').read_text())
            params = config['scan_manager']['ros__parameters']
            self.assertAlmostEqual(BASE_WORLD_Z_M, 0.306)
            self.assertAlmostEqual(params['base_to_fixture'][2], 0.094)
            self.assertAlmostEqual(BASE_WORLD_Z_M + params['base_to_fixture'][2], 0.400)
            self.assertAlmostEqual(config['contact_detector']['ros__parameters']['sim_box_origin_m'][2], 0.094)
            self.assertAlmostEqual(config['robot_manager']['ros__parameters']['path_min_z_m'], 0.097)
            self.assertAlmostEqual(params['search_origin_pose'][2], 0.194)
            self.assertAlmostEqual(result['node_params']['base_to_fixture'][2], 0.094)
            self.assertEqual(result['shape']['edges'], original['shape']['edges'])
            self.assertEqual(result['shape']['vertices'], original['shape']['vertices'])
            self.assertEqual(params['result_dir'], str(runtime / 'results'))
            self.assertEqual(config['weld_manager']['ros__parameters']['result_dir'], params['result_dir'])


if __name__ == '__main__':
    unittest.main()
