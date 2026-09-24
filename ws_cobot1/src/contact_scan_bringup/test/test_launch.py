"""bringup.launch.py 가 문법 오류 없이 읽히고 source 인자를 선언하는지 검사한다. 노드는 띄우지 않는다."""
import importlib.util
from pathlib import Path

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument

LAUNCH_FILE = Path(__file__).resolve().parents[1] / 'launch' / 'bringup.launch.py'


def _load():
    spec = importlib.util.spec_from_file_location('bringup_launch', LAUNCH_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_declares_source_argument():
    description = _load().generate_launch_description()
    assert isinstance(description, LaunchDescription)
    args = [e for e in description.entities if isinstance(e, DeclareLaunchArgument)]
    source = next(a for a in args if a.name == 'source')
    assert set(source.choices) == {'sim', 'robot_force'}


def test_every_source_has_config_file():
    module = _load()
    config_dir = LAUNCH_FILE.parents[1] / 'config'
    for source, file_name in module.CONFIG_BY_SOURCE.items():
        assert (config_dir / file_name).is_file(), f'source={source} 의 {file_name} 이 없다'


def test_weld_manager_is_a_node():
    """phase 2: 자체 노드 6 개. 설치되지 않았으면 launch 가 건너뛴다."""
    nodes = _load().NODES
    assert 'weld_manager' in nodes and len(nodes) == len(set(nodes)) == 6
