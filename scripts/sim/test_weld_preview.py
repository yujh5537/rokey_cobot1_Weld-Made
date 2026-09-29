"""Geometry checks for the virtual top-loop runner (ROS environment sourced)."""
import unittest
import numpy as np
from weld_preview import plan


class WeavingTest(unittest.TestCase):
    def setUp(self):
        vertices = [[-.04, -.04, .08], [.04, -.04, .08], [.04, .04, .08], [-.04, .04, .08]]
        self.shape = dict(success=True, box_valid=True, frame_id='workpiece_fixture',
                          edges=[dict(start=vertices[i], end=vertices[(i+1)%4]) for i in range(4)])
        self.cfg = dict(tilt_deg=45, standoff_m=.003, pitch_m=.004, amplitude_m=.002)
        self.origin = np.array([.420255, -.156675, .095006])

    def test_all_four_edges_use_fixture_and_alternating_weave(self):
        lines = plan(self.shape, self.origin, self.cfg)
        self.assertEqual(len(lines), 4)
        for edge, line in zip(self.shape['edges'], lines):
            start = np.array(edge['start']) + self.origin
            end = np.array(edge['end']) + self.origin
            np.testing.assert_allclose(line['points'][0], start + line['offset'])
            np.testing.assert_allclose(line['points'][-1], end + line['offset'])
            residuals = [p - (start + (end-start) * (k/20) + line['offset'])
                         for k, p in enumerate(line['points'])]
            for k in range(1, 20):
                self.assertAlmostEqual(np.linalg.norm(residuals[k]), .002)
            self.assertLess(np.dot(residuals[1], residuals[2]), 0)
            self.assertAlmostEqual(np.linalg.norm(line['q']), 1)
            self.assertAlmostEqual(np.linalg.norm(line['offset']), .003)

    def test_vertical_preview_keeps_wrist_and_height_fixed(self):
        lines = plan(self.shape, self.origin, {**self.cfg, 'tilt_deg': 0})
        for line in lines:
            self.assertEqual(line['q'], [1, 0, 0, 0])
            for point in line['points']:
                self.assertAlmostEqual(point[2], .08 + self.origin[2] + .003)

    def test_rejects_invalid_weave_settings(self):
        for key, value in [('pitch_m', 0), ('pitch_m', .000001), ('amplitude_m', .01), ('tilt_deg', float('nan'))]:
            with self.assertRaises(ValueError):
                plan(self.shape, self.origin, {**self.cfg, key: value})

    def test_rejects_failed_or_wrong_frame_result(self):
        for key, value in [('success', False), ('box_valid', False), ('frame_id', 'base_link')]:
            with self.assertRaises(ValueError):
                plan({**self.shape, key: value}, self.origin, self.cfg)


if __name__ == '__main__':
    unittest.main()
