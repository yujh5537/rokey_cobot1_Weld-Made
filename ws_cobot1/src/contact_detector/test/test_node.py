"""노드 골격: 파라미터를 받아 기동하고, 값이 없거나 틀리면 기동하지 않는다 (로봇 · 드라이버 연결 없음)."""
import pytest

rclpy = pytest.importorskip('rclpy')

from contact_detector.contact_detector import ContactDetectorNode  # noqa: E402
from rclpy.parameter import Parameter  # noqa: E402

PARAMS = {
    'source': 'sim',
    'contact_threshold_n': 3.0,
    'edge_drop_m': 0.0005,
    'debounce_n': 3,
    'over_force_n': 30.0,
    'over_force_debounce_n': 1,
}


def overrides(**changes):
    values = {**PARAMS, **changes}
    return [Parameter(k, value=v) for k, v in values.items() if v is not None]


@pytest.fixture
def ros():
    rclpy.init()
    yield
    rclpy.try_shutdown()


@pytest.mark.parametrize('source', ['sim', 'robot_force'])
def test_starts_with_each_source(ros, source):
    node = ContactDetectorNode(parameter_overrides=overrides(source=source))
    assert node.source == source
    assert node.detector.config.contact_threshold_n == 3.0
    assert node.detector.baseline is None          # tare 전에는 기준값이 없다 (0 이 아니다)
    node.destroy_node()


def test_rejects_unknown_source(ros):
    with pytest.raises(ValueError, match='rg2'):
        ContactDetectorNode(parameter_overrides=overrides(source='rg2'))


@pytest.mark.parametrize('missing', list(PARAMS))
def test_does_not_start_when_a_parameter_is_missing(ros, missing):
    with pytest.raises(Exception, match=missing):
        ContactDetectorNode(parameter_overrides=overrides(**{missing: None}))
