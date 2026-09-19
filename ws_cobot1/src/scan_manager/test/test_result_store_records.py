"""result_store 자료형의 값 규칙: 미측정 · 실패 값은 None 이고, 0 · NaN 이 새 나가지 않는다."""

import json
import math
from pathlib import Path
import subprocess
import sys

import pytest
from result_store_helpers import bias_corrections
from result_store_helpers import box_shape
from result_store_helpers import CONFIG
from result_store_helpers import edge_measurement
from result_store_helpers import failed_shape
from result_store_helpers import pose
from result_store_helpers import top_measurement
from scan_manager.contract_enums import Direction
from scan_manager.contract_enums import Phase
from scan_manager.result_store import BiasCorrection
from scan_manager.result_store import ConfigSnapshot
from scan_manager.result_store import Detection
from scan_manager.result_store import EVENT_EDGE
from scan_manager.result_store import FailureRecord
from scan_manager.result_store import HomeReturn
from scan_manager.result_store import Interruption
from scan_manager.result_store import Measured
from scan_manager.result_store import MeasurementSlot
from scan_manager.result_store import SegmentRecord
from scan_manager.result_store import ShapeResult
from scan_manager.result_store import Stamp
from scan_manager.result_store import StateRecord
from scan_manager.result_store import STATUS_CONFIRMED
from scan_manager.result_store import STATUS_FAILED
from scan_manager.result_store.records import check_node_params
from scan_manager.result_store.records import check_scan_id
from scan_manager.state_machine import Failure


def roundtrip(obj):
    """파일에 쓰는 것과 같은 조건(allow_nan=False)으로 JSON 을 거쳐 되읽는다."""
    text = json.dumps(obj.to_dict(), allow_nan=False)
    return type(obj).from_dict(json.loads(text))


def test_module_imports_neither_ros_nor_state_machine():
    code = (
        'import sys; import scan_manager.result_store; '
        "bad = [m for m in sys.modules if m.split('.')[0] in ('rclpy', 'contact_scan_interfaces')"
        " or m == 'scan_manager.state_machine']; "
        'assert not bad, bad'
    )
    package_root = str(Path(__file__).resolve().parents[1])
    subprocess.run([sys.executable, '-c', code], check=True, cwd=package_root)


# ---- Measured: 값과 valid 의 짝 ----

def test_measured_valid_value():
    assert Measured.of(0.0) == Measured(0.0, True)  # 실제로 잰 0.0 은 정상값이다
    assert Measured.of(3).value == 3.0


def test_measured_missing_is_none():
    assert Measured.missing().value is None
    assert Measured(float('nan'), False).value is None  # ROS msg 의 NaN → None


@pytest.mark.parametrize('value', [0, 0.0, 1.5, -2])
def test_invalid_with_number_is_rejected(value):
    with pytest.raises(ValueError, match='0 금지'):
        Measured(value, False)


@pytest.mark.parametrize('value', [None, float('nan'), float('inf'), -float('inf'), 'x', True])
def test_valid_needs_finite_number(value):
    with pytest.raises(ValueError):
        Measured(value, True)


def test_valid_flag_must_be_bool():
    with pytest.raises(ValueError):
        Measured(1.0, 1)


# ---- 기본 자료형 ----

def test_stamp_keeps_integers():
    stamp = Stamp.from_ns(1_790_000_000_123_456_789)
    assert (stamp.sec, stamp.nanosec) == (1_790_000_000, 123_456_789)
    assert roundtrip(stamp) == stamp
    assert stamp.ns == 1_790_000_000_123_456_789


@pytest.mark.parametrize('args', [(-1, 0), (1, 1_000_000_000), (1.0, 0), (True, 0)])
def test_stamp_rejects_bad_values(args):
    with pytest.raises(ValueError):
        Stamp(*args)


def test_pose_roundtrip_and_validation():
    assert roundtrip(pose()) == pose()
    with pytest.raises(ValueError):
        pose(x=float('nan'))
    with pytest.raises(ValueError):
        type(pose())((0, 0, 0), (0, 0, 0, 1), '', Stamp(1))  # frame_id 없이 좌표를 두지 않는다


@pytest.mark.parametrize('scan_id', [
    '', '20260919-100000', '../20260919-100000-0001', '20260919-100000-0001/..',
    '20260919-100000-00011', 20260919,
])
def test_scan_id_format(scan_id):
    with pytest.raises(ValueError):
        check_scan_id(scan_id)


# ---- 측정값 ----

def test_top_detection_has_no_z_drop():
    detection = top_measurement().detection
    assert detection.z_drop_m is None and detection.z_drop_valid is False
    again = roundtrip(detection)
    assert again == detection
    assert again.z_drop_m is None  # null 이 0.0 으로 바뀌지 않는다
    assert again.pose.stamp != again.force_stamp  # pose 와 힘의 취득 시각을 따로 둔다


def test_edge_detection_roundtrip():
    detection = edge_measurement(Direction.POS_X).detection
    assert roundtrip(detection) == detection
    assert detection.z_drop_valid and detection.z_drop_m == pytest.approx(0.0021)


def test_detection_rejects_zero_for_missing_z_drop():
    kwargs = {
        'event_type': EVENT_EDGE, 'event_id': 1, 'sample_id': 1, 'motion_id': 1, 'pose': pose(),
        'force_stamp': Stamp(1), 'detect_stamp': Stamp(1), 'force_delta_n': 0.1}
    with pytest.raises(ValueError, match='0 금지'):
        Detection(z_drop_m=0.0, z_drop_valid=False, **kwargs)
    assert Detection(z_drop_m=float('nan'), z_drop_valid=False, **kwargs).z_drop_m is None


def test_slot_distinguishes_not_attempted_from_failed():
    untouched = MeasurementSlot()
    failed = MeasurementSlot(status=STATUS_FAILED, reason_code=301, detail='max_distance',
                             stop_pose=pose())
    confirmed = MeasurementSlot(status=STATUS_CONFIRMED,
                                detection=edge_measurement(Direction.POS_X).detection)
    assert [s.valid for s in (untouched, failed, confirmed)] == [False, False, True]
    assert untouched.status != failed.status
    for slot in (untouched, failed, confirmed):
        assert roundtrip(slot) == slot
    assert roundtrip(failed).detection is None
    assert failed.to_dict()['detection'] is None


def test_slot_consistency():
    with pytest.raises(ValueError):
        MeasurementSlot(status=STATUS_CONFIRMED)                      # 값 없는 확정
    with pytest.raises(ValueError):
        MeasurementSlot(status=STATUS_FAILED)                         # 사유 없는 실패
    with pytest.raises(ValueError):
        MeasurementSlot(status=STATUS_FAILED, reason_code=0)          # 0 은 사유가 아니다
    with pytest.raises(ValueError):
        MeasurementSlot(detection=top_measurement().detection)        # 미탐색인데 값


def test_slot_file_flags_must_agree():
    data = MeasurementSlot().to_dict()
    data['valid'] = True
    with pytest.raises(ValueError):
        MeasurementSlot.from_dict(data)


# ---- 설정 · 상태 ----

def test_config_roundtrip_keeps_unknown_as_none():
    again = roundtrip(CONFIG)
    assert again == CONFIG
    assert again.drop_limit_m is None
    data = CONFIG.to_dict()
    assert data['drop_limit_m'] is None and data['drop_limit_set'] is False
    assert data['contact_threshold_set'] is True
    assert isinstance(again.debounce_n, int)


def test_config_rejects_nan_and_flag_mismatch():
    with pytest.raises(ValueError):
        ConfigSnapshot(over_force_n=float('nan'))
    data = CONFIG.to_dict()
    data['drop_limit_set'] = True
    with pytest.raises(ValueError):
        ConfigSnapshot.from_dict(data)


def test_node_params():
    checked = check_node_params({'a': 1, 'b': 0.5, 'c': [1, 2.5], 'd': None, 'e': 'x', 'f': True})
    assert checked == {'a': 1, 'b': 0.5, 'c': [1, 2.5], 'd': None, 'e': 'x', 'f': True}
    for bad in ({'a': float('nan')}, {'a': [float('inf')]}, {'a': {'nested': 1}}, {'': 1}):
        with pytest.raises(ValueError):
            check_node_params(bad)


def test_state_record_from_snapshot_like_object():
    class Like:
        phase, direction, progress, progress_total, motion_id = 3, 2, 1, 4, 7

    state = StateRecord.from_snapshot(Like())
    assert state.phase is Phase.EDGE_SEARCH and state.direction is Direction.NEG_X
    assert state.to_dict()['phase'] == 'EDGE_SEARCH'
    assert roundtrip(state) == state
    with pytest.raises(ValueError):
        StateRecord(Phase.EDGE_SEARCH, Direction.POS_X, 5, 4)


# ---- 중단 · 안전복귀 · 실패 ----

def test_interruption_roundtrip_without_pose():
    item = Interruption(Phase.EDGE_SEARCH, Direction.POS_X, 0, pose=None, stopped_at=Stamp(5))
    again = roundtrip(item)
    assert again == item and again.pose is None and again.resumed_at is None
    assert item.to_dict()['pose_valid'] is False


def test_final_homing_flag_needs_homing_phase():
    assert Interruption(Phase.HOMING, Direction.NONE, 4, during_final_homing=True)
    with pytest.raises(ValueError):
        Interruption(Phase.EDGE_SEARCH, Direction.POS_X, 1, during_final_homing=True)


def test_home_return_roundtrip():
    empty = HomeReturn()
    assert roundtrip(empty) == empty and empty.completed is None
    done = HomeReturn(True, 1, Stamp(9), Phase.STOPPED, True, Stamp(12), pose())
    assert roundtrip(done) == done
    unfinished = HomeReturn(True, 1, Stamp(9), Phase.STOPPED)
    assert roundtrip(unfinished).completed is None  # None 이 False 로 바뀌지 않는다
    with pytest.raises(ValueError):
        HomeReturn(completed=True)


def test_failure_from_state_machine_failure():
    record = FailureRecord.from_failure(Failure(301, 'max_distance', Phase.EDGE_SEARCH), Stamp(3))
    assert (record.reason_code, record.detail) == (301, 'max_distance')
    assert record.phase is Phase.EDGE_SEARCH
    assert roundtrip(record) == record
    with pytest.raises(ValueError):
        FailureRecord(0, '', Phase.ERROR)


# ---- 최종 결과 ----

def test_box_shape_roundtrip_follows_contract_names():
    shape = box_shape()
    assert roundtrip(shape) == shape
    data = shape.to_dict()
    for name in ('z_top', 'x_pos', 'x_neg', 'y_pos', 'y_neg', 'support_z'):
        assert data[f'{name}_valid'] is True
    assert (len(data['vertices']), len(data['edges']), len(data['path_candidates'])) == (8, 12, 4)
    assert data['path_candidates'] == data['edges'][:4]


def test_failed_shape_keeps_missing_as_null_and_array_lengths():
    shape = failed_shape()
    data = json.loads(json.dumps(shape.to_dict(), allow_nan=False))
    assert data['y_pos'] is None and data['y_pos_valid'] is False
    assert data['width'] is None and data['dims_valid'] is False
    assert data['vertices'] == [None] * 8
    assert all(s == {'start': None, 'end': None, 'length': None, 'valid': False}
               for s in data['edges'] + data['path_candidates'])
    again = ShapeResult.from_dict(data)
    assert again == shape
    assert again.y_pos.value is None and again.width is None


def test_no_zero_or_nan_leaks_into_failed_shape_file():
    text = json.dumps(failed_shape().to_dict(), allow_nan=False)
    assert 'NaN' not in text

    def numbers(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key not in ('sec', 'nanosec', 'reason_code'):
                    yield from numbers(value)
        elif isinstance(node, list):
            for value in node:
                yield from numbers(value)
        elif isinstance(node, (int, float)) and not isinstance(node, bool):
            yield node

    found = list(numbers(json.loads(text)))
    assert sorted(found) == [0.04, 0.05, 0.06]  # 실제로 잰 세 값뿐이다. 채움값 0 이 없다
    assert not any(math.isnan(v) for v in found)


def test_shape_rejects_filler_values():
    base = {
        'success': False, 'reason_code': 501, 'detail': '', 'frame_id': 'workpiece_fixture',
        'started_at': Stamp(1), 'finished_at': Stamp(2)}
    with pytest.raises(ValueError, match='0 금지'):
        ShapeResult(width=0.0, **base)
    with pytest.raises(ValueError, match='0 금지'):
        ShapeResult(vertices=((0.0, 0.0, 0.0),) * 8, **base)
    with pytest.raises(ValueError):
        ShapeResult(vertices=(None,) * 7, **base)  # 무효여도 길이를 유지한다
    with pytest.raises(ValueError):
        ShapeResult(**{**base, 'success': True})   # 성공인데 reason_code != 0
    with pytest.raises(ValueError, match='0 금지'):
        SegmentRecord((0, 0, 0), (0, 0, 0), 0.0, False)


def test_tampered_file_with_zero_for_missing_is_rejected_on_read():
    data = failed_shape().to_dict()
    data['y_pos'] = 0.0  # valid=false 인데 누군가 0 을 채워 넣은 파일
    with pytest.raises(ValueError, match='0 금지'):
        ShapeResult.from_dict(data)


def test_bias_correction_roundtrip():
    correction = bias_corrections()[Direction.POS_X]
    again = roundtrip(correction)
    assert again == correction
    assert again.inputs['detect_latency_s'] is None
    missing = BiasCorrection()
    assert roundtrip(missing) == missing and missing.correction_m is None
    with pytest.raises(ValueError, match='0 금지'):
        BiasCorrection(0.45, 0.0, False)
    assert BiasCorrection(inputs={'z_drop_m': float('nan')}).inputs['z_drop_m'] is None
