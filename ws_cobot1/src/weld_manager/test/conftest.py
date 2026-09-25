"""ROS 를 source 하지 않은 셸에서도 `python3 -m pytest src/weld_manager/test` 가 돌게 한다.

weld_manager 는 scan_manager.result_store(순수 Python)를 import 하므로 두 패키지 소스 경로를 앞에 넣는다.
colcon test 에서는 설치된 패키지가 같은 모듈을 준다.
"""

import json
from pathlib import Path
import sys

import pytest

_SRC = Path(__file__).resolve().parents[2]
for package in ('weld_manager', 'scan_manager'):
    sys.path.insert(0, str(_SRC / package))

# 레포에 커밋된 sim 스캔 결과 (docs/phase2/fixtures). 이 파일 하나로 여러 경우를 만든다
FIXTURE = (_SRC.parents[1] / 'docs' / 'phase2' / 'fixtures'
           / 'sim_20260921-131938-1493.result.json')
FIXTURE_SCAN_ID = '20260921-131938-1493'

# weld-motion.md 6절 출발값 (시험용 입력. 제품 값은 yaml 에 있다)
# 툴 외형은 M2 실측 전이라 시험용 임의값이다: 팁 구 · 탐침 몸통 · 핑거(팁 뒤 12 mm 부터)
PARAM_VALUES = dict(
    weld_speed_mps=0.010, travel_speed_mps=0.050, approach_speed_mps=0.020,
    weld_speed_min_mps=0.002, standoff_m=0.003, tip_radius_m=0.002,
    weave_amplitude_m=0.002, weave_pitch_m=0.004, tilt_deg=45.0, tool_roll_deg=[0.0] * 8,
    tool_profile_u_m=[0.0, 0.003, 0.012], tool_profile_r_m=[0.002, 0.006, 0.015],
    approach_m=0.030, travel_clearance_m=0.050, bottom_margin_m=0.005, workspace_margin_m=0.100,
    path_tolerance_m=0.003, motion_timeout_s=120.0, tool_check_max_force_n=6.0,
    server_wait_timeout_s=2.0, stop_confirm_timeout_s=3.0, sample_timeout_s=1.0,
    orientation_tolerance_deg=15.0, continue_on_line_failure=True,
    state_publish_period_s=1.0, scan_state_timeout_s=5.0, result_dir='data',
)


@pytest.fixture
def param_values():
    return dict(PARAM_VALUES)


@pytest.fixture
def params():
    from weld_manager.params import check
    result = check(PARAM_VALUES)
    assert result.ok, result.describe()
    return result.params


def write_result(root: Path, scan_id: str, edit=None) -> Path:
    """픽스처를 root/<scan_id>/result.json 으로 복사한다. edit(dict) 로 내용을 바꿀 수 있다."""
    data = json.loads(FIXTURE.read_text(encoding='utf-8'))
    data['scan_id'] = scan_id
    if edit:
        edit(data)
    path = root / scan_id / 'result.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    return path


@pytest.fixture
def store(tmp_path):
    from scan_manager.result_store import ResultStore
    return ResultStore(tmp_path)


@pytest.fixture
def fixture_store(tmp_path):
    """픽스처 하나만 든 저장소."""
    from scan_manager.result_store import ResultStore
    write_result(tmp_path, FIXTURE_SCAN_ID)
    return ResultStore(tmp_path)
