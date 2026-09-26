"""용접 결과 원본 파일 (weld-ros-interfaces.md 3.3 · 3.4절). ROS 없이 돈다."""

from datetime import datetime
import json
import random

import pytest

from scan_manager.result_store import Stamp
from weld_manager.contract_enums import LineStatus
from weld_manager.weld_record import LineRecord
from weld_manager.weld_record import load_dict
from weld_manager.weld_record import new_weld_id
from weld_manager.weld_record import Pose
from weld_manager.weld_record import save
from weld_manager.weld_record import weld_path
from weld_manager.weld_record import WELD_ID_PATTERN
from weld_manager.weld_record import WeldRecord

SEAM = ((0.0, 0.0, 0.04), (0.1, 0.0, 0.04))
T0, T1 = Stamp(1_790_000_000), Stamp(1_790_000_100, 5)


def lines(statuses):
    out = []
    for i, status in enumerate(statuses):
        failed = status in (LineStatus.FAILED, LineStatus.STOPPED)
        out.append(LineRecord(
            i, SEAM, status, reason_code=400 if failed else 0, detail='x' if failed else '',
            stop_pose=Pose((0.01, 0.02, 0.05), (0.0, 0.92, 0.38, 0.0)) if failed else None,
            started_at=T0 if status is not LineStatus.SKIPPED else None,
            finished_at=T1 if status is not LineStatus.SKIPPED else None))
    return tuple(out)


def record(statuses, success, reason_code=0, start=0, end=7):
    return WeldRecord(
        weld_id='20260923-120000-0001', scan_id='20260923-110000-0001', success=success,
        reason_code=reason_code, detail='', frame_id='workpiece_fixture',
        base_to_fixture=(0.425, -0.184, 0.4), start_line=start, end_line=end, lines=lines(statuses),
        config={'weld_speed_mps': 0.01}, started_at=T0, finished_at=T1)


D, F, N, S = LineStatus.DONE, LineStatus.FAILED, LineStatus.NOT_ATTEMPTED, LineStatus.SKIPPED


def test_success_record_round_trips_as_json(tmp_path):
    path = save(tmp_path, record([D] * 8, True))
    assert path == tmp_path / '20260923-110000-0001' / 'weld' / '20260923-120000-0001.json'
    data = load_dict(path)
    assert data['schema_version'] == 1 and data['kind'] == 'weld.result'
    assert data['lines'][0]['stop_pose'] is None and data['lines'][0]['stop_pose_valid'] is False
    assert data['base_to_fixture'] == [0.425, -0.184, 0.4]
    assert data['finished_at'] == {'sec': 1_790_000_100, 'nanosec': 5}


def test_failed_line_keeps_stop_pose_and_nulls(tmp_path):
    data = record([D, F, N, N, N, N, N, N], False, reason_code=400).to_dict()
    assert data['lines'][1]['stop_pose']['position_m'] == [0.01, 0.02, 0.05]
    assert data['lines'][1]['stop_pose_valid'] is True
    assert data['lines'][2]['reason_code'] == 0 and data['lines'][2]['stop_pose'] is None


def test_skipped_lines_outside_range():
    rec = record([S, S, D, D, S, S, S, S], True, start=2, end=3)
    assert [line['status'] for line in rec.to_dict()['lines']][:3] == ['SKIPPED', 'SKIPPED', 'DONE']
    with pytest.raises(ValueError, match='SKIPPED'):
        record([D] * 8, True, start=2, end=3)          # 범위 밖인데 SKIPPED 가 아니다


@pytest.mark.parametrize('statuses, success, code', [
    ([D, F, N, N, N, N, N, N], True, 0),        # 실패한 선이 있는데 success
    ([D] * 8, False, 0),                        # success 와 reason_code 어긋남
    ([D] * 8, True, 400),
])
def test_inconsistent_records_are_refused(statuses, success, code):
    with pytest.raises(ValueError):
        record(statuses, success, reason_code=code)


def test_line_status_and_code_must_agree():
    with pytest.raises(ValueError):
        LineRecord(0, SEAM, LineStatus.FAILED)                     # 실패인데 사유 없음
    with pytest.raises(ValueError):
        LineRecord(0, SEAM, LineStatus.DONE, stop_pose=Pose((0, 0, 0), (0, 0, 0, 1)))


def test_nan_is_never_written(tmp_path):
    bad = record([D] * 8, True)
    object.__setattr__(bad, 'base_to_fixture', (float('nan'), 0.0, 0.0))
    with pytest.raises(ValueError):
        save(tmp_path, bad)
    assert not weld_path(tmp_path, bad.scan_id, bad.weld_id).exists()   # 반쯤 쓴 파일도 없다
    assert not list(tmp_path.rglob('*.tmp'))


def test_same_weld_id_is_not_overwritten(tmp_path):
    save(tmp_path, record([D] * 8, True))
    with pytest.raises(FileExistsError):
        save(tmp_path, record([D] * 8, True))


def test_weld_id_format():
    weld_id = new_weld_id(datetime(2026, 9, 24, 13, 5, 9), random.Random(1))
    assert WELD_ID_PATTERN.fullmatch(weld_id) and weld_id.startswith('20260924-130509-')
    with pytest.raises(ValueError):
        WeldRecord(**{**record([D] * 8, True).__dict__, 'weld_id': 'weld-1'})


def test_file_is_plain_json(tmp_path):
    path = save(tmp_path, record([D] * 8, True))
    json.loads(path.read_text(encoding='utf-8'))
