"""자체 노드 6개(1차 5개 + phase 2 weld_manager)를 입력원(source)에 맞는 파라미터 파일로 띄운다 (US-07).

  ros2 launch contact_scan_bringup bringup.launch.py source:=sim
  ros2 launch contact_scan_bringup bringup.launch.py source:=robot_force broker_host:=<웹 PC 주소>

- 두산 드라이버(sodvir / sodreal)는 여기서 띄우지 않는다. 별도 터미널에서 사람이 띄운다.
- MQTT 브로커 주소는 환경별 값이므로 yaml 에 고정하지 않고 broker_host 실행 인자로 전달한다.
- 아직 설치되지 않은 노드 패키지는 건너뛴다. 골격 단계와 저녁 통합에서 일부 패키지만 있어도 실행된다.
- 노드 이름은 계약(ros-interfaces.md 1장)의 이름으로 고정한다. yaml 의 최상위 키와 같아야 파라미터가 들어간다.
"""
import os

from ament_index_python.packages import PackageNotFoundError, get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

# 입력원 → 파라미터 파일
CONFIG_BY_SOURCE = {
    'sim': 'sim.yaml',
    'robot_force': 'real.yaml',
}

# 자체 실행 노드. 패키지 이름 = 실행 파일 이름 = 노드 이름 (ws_cobot1/src/README.md 의 pkg create 명령 기준)
# weld_manager 는 phase 2(docs/phase2/weld-ros-interfaces.md 1장 "자체 노드는 6 개"). 설치되지 않았으면 건너뛴다
NODES = [
    'robot_manager',
    'contact_detector',
    'safety_monitor',
    'scan_manager',
    'mqtt_bridge',
    'weld_manager',
]


def _is_installed(package):
    try:
        get_package_share_directory(package)
        return True
    except PackageNotFoundError:
        return False


def _launch_nodes(context):
    source = LaunchConfiguration('source').perform(context)
    broker_host = LaunchConfiguration('broker_host').perform(context)
    if source not in CONFIG_BY_SOURCE:
        raise RuntimeError(
            f"source:={source} 는 지원하지 않는다. {' | '.join(CONFIG_BY_SOURCE)} 중에서 고른다")

    config = os.path.join(
        get_package_share_directory('contact_scan_bringup'), 'config', CONFIG_BY_SOURCE[source])

    actions = [LogInfo(msg=f'[bringup] source={source}, 파라미터 파일={config}')]
    for name in NODES:
        if not _is_installed(name):
            actions.append(LogInfo(msg=f'[bringup] {name}: 패키지가 설치되지 않아 건너뜀'))
            continue
        parameters = [config]
        if name == 'mqtt_bridge':
            parameters.append({'broker_host': broker_host})
        actions.append(Node(
            package=name,
            executable=name,
            name=name,
            output='screen',
            emulate_tty=True,
            parameters=parameters,
        ))
    return actions


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'source',
            default_value='sim',
            choices=list(CONFIG_BY_SOURCE),
            description='접촉 판정 입력원. sim = 가상 직육면체(Virtual Mode), robot_force = 로봇 내장 힘 감지(실기)'),
        DeclareLaunchArgument(
            'broker_host',
            default_value='127.0.0.1',
            description='MQTT broker host. 환경별 주소는 실행 인자로 전달한다'),
        OpaqueFunction(function=_launch_nodes),
    ])
