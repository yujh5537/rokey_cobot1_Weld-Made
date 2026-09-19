"""result_store 테스트의 공용 입력. 수치는 테스트용 임의값이며 설계 출발값이 아니다."""

import itertools

from scan_manager.contract_enums import Direction
from scan_manager.contract_enums import Phase
from scan_manager.result_store import BiasCorrection
from scan_manager.result_store import ConfigSnapshot
from scan_manager.result_store import Detection
from scan_manager.result_store import EVENT_CONTACT
from scan_manager.result_store import EVENT_EDGE
from scan_manager.result_store import Frames
from scan_manager.result_store import Measured
from scan_manager.result_store import Measurement
from scan_manager.result_store import PoseRecord
from scan_manager.result_store import SegmentRecord
from scan_manager.result_store import ShapeResult
from scan_manager.result_store import Stamp
from scan_manager.result_store import WrenchRecord
from scan_manager.state_machine import Snapshot

SCAN_A = '20260919-100000-0001'
SCAN_B = '20260919-110000-0002'
SCAN_C = '20260919-120000-0003'
ORDER = (Direction.POS_X, Direction.NEG_X, Direction.POS_Y, Direction.NEG_Y)
FRAMES = Frames(detection='base_link', result='workpiece_fixture')
CONFIG = ConfigSnapshot(
    contact_threshold_n=3.0, edge_drop_m=0.002, debounce_n=3, over_force_n=30.0,
    descend_speed_mps=0.005, slide_speed_mps=0.01, max_descend_m=0.1, max_slide_m=0.2,
    motion_timeout_s=30.0, lift_height_m=0.05, target_force_n=5.0,
    drop_limit_m=None,  # 일부러 비워 둔다: 모르는 설정값도 None 으로 왕복해야 한다
)
NODE_PARAMS = {
    'tip_radius_m': 0.003,
    'search_origin_pose': [0.4, 0.0, 0.3, 0.0, 3.14, 0.0],
    'result_frame_id': 'workpiece_fixture',
    'recontact_speed_mps': None,
}


class FakeClock:
    """부를 때마다 1 ms 씩 가는 시계. 기록 시각의 순서를 결정적으로 만든다."""

    def __init__(self, start_sec=1_790_000_000):
        self._ns = itertools.count(start_sec * 1_000_000_000, 1_000_000)

    def __call__(self):
        return Stamp.from_ns(next(self._ns))


def snapshot(scan_id=SCAN_A, phase=Phase.PREPARING, direction=Direction.NONE, progress=0,
             motion_id=0):
    return Snapshot(scan_id, phase, direction, progress, 4, motion_id)


def pose(x=0.4, y=0.0, z=0.05, sec=100):
    return PoseRecord((x, y, z), (0.0, 1.0, 0.0, 0.0), 'base_link', Stamp(sec, 5))


def top_measurement(z=0.05):
    detection = Detection(
        event_type=EVENT_CONTACT, event_id=11, sample_id=1001, motion_id=1,
        pose=pose(z=z, sec=100), force_stamp=Stamp(100, 7), detect_stamp=Stamp(100, 9),
        force_delta_n=3.4, source='sim', debounce_count=3,
        wrench=WrenchRecord((0.1, -0.2, 3.4), (0.0, 0.01, 0.0)),
    )
    return Measurement(detection, stop_pose=pose(z=z - 0.0004, sec=101))


def edge_measurement(direction, coordinate=0.45, z_drop=0.0021, event_id=20):
    x, y = {
        Direction.POS_X: (coordinate, 0.0), Direction.NEG_X: (-coordinate, 0.0),
        Direction.POS_Y: (0.0, coordinate), Direction.NEG_Y: (0.0, -coordinate),
    }[direction]
    detection = Detection(
        event_type=EVENT_EDGE, event_id=event_id + int(direction), sample_id=2000 + int(direction),
        motion_id=1 + int(direction), pose=pose(x, y, 0.048, sec=200 + int(direction)),
        force_stamp=Stamp(200 + int(direction), 3), detect_stamp=Stamp(200 + int(direction), 8),
        force_delta_n=0.4, z_drop_m=z_drop, z_drop_valid=True, source='sim', debounce_count=3,
    )
    return Measurement(detection, stop_pose=pose(x * 1.01, y * 1.01, 0.046, sec=201))


def begin(store, scan_id=SCAN_A, **overrides):
    arguments = {
        'state': snapshot(scan_id), 'config': CONFIG, 'frames': FRAMES,
        'direction_order': ORDER, 'started_at': Stamp(1_790_000_000, 0),
        'node_params': NODE_PARAMS,
    }
    arguments.update(overrides)
    return store.begin_scan(scan_id, **arguments)


def _segment(start, end):
    length = sum((a - b) ** 2 for a, b in zip(start, end)) ** 0.5
    return SegmentRecord(start, end, length, True)


def box_shape(x_neg=-0.05, x_pos=0.05, y_neg=-0.03, y_pos=0.03, z_top=0.04, support_z=0.0):
    """계약 3.5절의 순서 규약대로 만든 성공 결과."""
    top = [
        (x_neg, y_neg, z_top), (x_pos, y_neg, z_top),
        (x_pos, y_pos, z_top), (x_neg, y_pos, z_top)]
    vertices = top + [(x, y, support_z) for x, y, _z in top]
    edges = (
        [_segment(vertices[i], vertices[(i + 1) % 4]) for i in range(4)]
        + [_segment(vertices[i + 4], vertices[(i + 1) % 4 + 4]) for i in range(4)]
        + [_segment(vertices[i], vertices[i + 4]) for i in range(4)]
    )
    return ShapeResult(
        success=True, reason_code=0, detail='', frame_id='workpiece_fixture',
        started_at=Stamp(1_790_000_000, 0), finished_at=Stamp(1_790_000_060, 0),
        z_top=Measured.of(z_top), x_pos=Measured.of(x_pos), x_neg=Measured.of(x_neg),
        y_pos=Measured.of(y_pos), y_neg=Measured.of(y_neg), support_z=Measured.of(support_z),
        width=x_pos - x_neg, length=y_pos - y_neg, height=z_top - support_z, dims_valid=True,
        vertices=tuple(vertices), edges=tuple(edges), path_candidates=tuple(edges[:4]),
        box_valid=True,
    )


def failed_shape(reason_code=500, detail='GEOM_NONPOSITIVE_WIDTH'):
    """형상 계산 실패. 얻은 값만 채우고 나머지는 기본값(미측정)으로 둔다."""
    return ShapeResult(
        success=False, reason_code=reason_code, detail=detail, frame_id='workpiece_fixture',
        started_at=Stamp(1_790_000_000, 0), finished_at=Stamp(1_790_000_060, 0),
        z_top=Measured.of(0.04), x_pos=Measured.of(0.05), x_neg=Measured.of(0.06),
    )


def bias_corrections():
    inputs = {
        'z_drop_m': 0.0021, 'tip_radius_m': 0.003, 'slide_speed_mps': 0.01,
        'detect_latency_s': None,  # 아직 실측하지 않은 입력
    }
    return {d: BiasCorrection(0.45, 0.0034, True, inputs) for d in ORDER}
