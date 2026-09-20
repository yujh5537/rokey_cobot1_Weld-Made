"""ROS 를 source 하지 않은 셸에서도 `python3 -m pytest src/safety_monitor/test` 가 돌게 한다.

그리고 노드 테스트를 **다른 테스트 프로세스 · 떠 있는 노드 · 실기와 분리한다.** rclpy 를 쓰는 테스트는
in-process 라도 DDS 로 나가므로, 같은 도메인에서 동시에 돌면 서로의 토픽 · 서비스를 발견한다
(`/robot/stop` · `/robot/sample` 처럼 이름이 겹친다). colcon test 는 패키지를 **병렬로** 돌리므로
격리가 없으면 CI 와 저녁 통합에서 간헐 실패가 난다(2026-09-20 확인: 병렬 7 failures, 순차 0).

규칙은 scan_manager/test/sequence_helpers.py 의 것을 그대로 따른다.
rclpy.init() 전에 정해야 하므로 import 시점에 환경 변수를 세운다.
"""
import os
from pathlib import Path
import sys

# 이 조에 배정된 ROS_DOMAIN_ID 는 30~39 다. 30 은 조 공용(실기 · 팀원의 Virtual)이라 쓰지 않는다
TEST_DOMAIN_IDS = range(31, 40)

os.environ.setdefault('ROS_AUTOMATIC_DISCOVERY_RANGE', 'LOCALHOST')   # 이 PC 밖으로 나가지 않는다
os.environ['ROS_DOMAIN_ID'] = str(TEST_DOMAIN_IDS[os.getpid() % len(TEST_DOMAIN_IDS)])

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
