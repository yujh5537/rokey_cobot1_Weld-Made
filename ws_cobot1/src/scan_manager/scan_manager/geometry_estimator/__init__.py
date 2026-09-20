"""geometry_estimator: 5점 → 편향 보정 · 윗면 사각형 · 외곽 엣지·경로 후보 · 직육면체. 소유: 현지 (T17).

scan_manager 안의 모듈이며 노드가 아니다. rclpy 를 import 하지 않는다.
"""
from .bias import BiasParams, edge_correction_m, overshoot_m, top_correction_m
from .estimator import (
    BoxEstimate,
    Correction,
    EDGE_DIRECTIONS,
    EdgeObservation,
    estimate_box,
    GEOM_MISSING_POINT,
    GEOM_NEGATIVE_HEIGHT,
    GEOM_NONPOSITIVE_WIDTH,
    Segment,
    TopObservation,
)

__all__ = [
    'BiasParams', 'BoxEstimate', 'Correction', 'EDGE_DIRECTIONS', 'EdgeObservation', 'GEOM_MISSING_POINT',
    'GEOM_NEGATIVE_HEIGHT', 'GEOM_NONPOSITIVE_WIDTH', 'Segment', 'TopObservation', 'edge_correction_m',
    'estimate_box', 'overshoot_m', 'top_correction_m',
]
