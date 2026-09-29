"""ExecutePath 가 두산 드라이버에 보내는 요청 (phase 2, P1).

요청 메시지만 만든다. 노드도 드라이버도 띄우지 않는다. dsr_msgs2 가 없는 PC 에서는 건너뛰고,
CI 에서는 test_node.py 와 같이 실패로 만든다.
"""
import importlib.util
import math
import os

import pytest

if importlib.util.find_spec('dsr_msgs2') is None:
    if os.environ.get('CI'):
        raise AssertionError('CI 인데 dsr_msgs2 가 없다. .github/workflows/ci.yml 의 "dsr_msgs2 빌드" 단계를 확인한다')
    pytest.skip('두산 드라이버가 없는 환경에서는 건너뛴다', allow_module_level=True)

from robot_manager import dsr_client  # noqa: E402
from robot_manager.paths import SPLINE_MAX_POINTS  # noqa: E402

POSX = [423.56, -186.06, 150.6, 20.0, 180.0, 20.0]


def test_spline_service_name_matches_driver():
    """dsr_controller2.cpp 2424행: svc_prefix_ + "motion/move_spline_task"."""
    srv_type, path = dsr_client.SERVICES['move_spline']
    assert path == 'motion/move_spline_task'
    assert srv_type.__name__ == 'MoveSplineTask'


def test_path_line_request_is_async_absolute_without_radius():
    r = dsr_client.path_line_request(POSX, 0.01, 2.5)
    assert list(r.pos) == POSX
    assert list(r.vel) == pytest.approx([10.0, 10.0])
    assert list(r.acc) == pytest.approx([25.0, 25.0])        # path_acc_ratio × 속도
    assert r.sync_type == dsr_client.ASYNC
    assert r.mode == dsr_client.DR_MV_MOD_ABS
    assert r.ref == dsr_client.DR_BASE
    assert r.radius == 0.0                                   # ASYNC 에서는 어차피 버려진다(D31)


def test_existing_move_line_request_is_unchanged():
    """1차 ExecuteMotion 의 요청(가속 4 배)은 그대로다."""
    r = dsr_client.move_line_request(POSX, 0.01, relative=False)
    assert list(r.acc) == pytest.approx([40.0, 40.0])


def test_spline_request_fills_count_and_points_together():
    """드라이버는 pos.at(i) 를 pos_cnt 번 읽는다. 둘이 다르면 드라이버에서 예외가 난다."""
    points = [[x, -186.0, 150.0, 20.0, 180.0, 20.0] for x in (420.0, 421.0, 422.0)]
    r = dsr_client.move_spline_request(points, 0.01, 4.0)
    assert r.pos_cnt == len(r.pos) == 3
    assert [list(p.data) for p in r.pos] == points
    assert list(r.vel) == pytest.approx([10.0, 10.0])
    assert list(r.acc) == pytest.approx([40.0, 40.0])
    assert r.opt == dsr_client.SPLINE_VEL_CONST == 1
    assert r.sync_type == dsr_client.ASYNC
    assert r.mode == dsr_client.DR_MV_MOD_ABS
    assert r.ref == dsr_client.DR_BASE
    assert r.time == 0.0


def test_spline_request_count_boundary():
    """100 점은 되고 101 점은 드라이버 배열을 넘치므로 보내지 않는다."""
    assert dsr_client.move_spline_request([POSX] * SPLINE_MAX_POINTS, 0.01, 4.0).pos_cnt == 100
    with pytest.raises(ValueError):
        dsr_client.move_spline_request([POSX] * (SPLINE_MAX_POINTS + 1), 0.01, 4.0)
    with pytest.raises(ValueError):
        dsr_client.move_spline_request([], 0.01, 4.0)


@pytest.mark.parametrize('bad', [POSX[:5], POSX + [0.0], POSX[:5] + [math.nan]])
def test_spline_request_rejects_point_without_six_values(bad):
    """드라이버는 data[0..5] 를 범위 검사 없이 읽는다."""
    with pytest.raises(ValueError, match='경유점 1'):
        dsr_client.move_spline_request([POSX, bad], 0.01, 4.0)


@pytest.mark.parametrize('speed, ratio', [(0.0, 4.0), (-0.01, 4.0), (math.nan, 4.0),
                                          (0.01, 0.0), (0.01, math.nan)])
def test_path_requests_refuse_zero_speed_or_acc(speed, ratio):
    with pytest.raises(ValueError):
        dsr_client.path_line_request(POSX, speed, ratio)
    with pytest.raises(ValueError):
        dsr_client.move_spline_request([POSX], speed, ratio)


def test_path_line_request_rejects_bad_posx():
    with pytest.raises(ValueError):
        dsr_client.path_line_request(POSX[:5], 0.01, 4.0)
