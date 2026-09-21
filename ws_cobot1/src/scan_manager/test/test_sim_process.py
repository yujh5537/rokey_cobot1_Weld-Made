"""프로세스 수준 시뮬레이션: **실제 scan_manager 프로세스 + bringup 의 sim.yaml** 을 가짜 상대 노드와 붙여 전체 스캔을 돌린다.

test_node_scan.py 는 노드를 테스트 프로세스 안에서 만든다. 여기서는 설치된 진입점과 같은 main()
(MultiThreadedExecutor · 종료 처리)과 sim.yaml 의 값(기준점 · max_descend_m · max_slide_m · base_to_fixture ·
tip_radius_m)이 가상 직육면체에서 실제로 동작하는지 본다.

로봇 · 드라이버 · Virtual Mode 를 쓰지 않는다. 상대 노드는 fake_peers.FakePeers 다.
sim.yaml 의 detect_latency_s 는 TBD 라서 **테스트 전용 임의값**을 덮어쓴다. 실측값도 설계 출발값도 아니다.
"""

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

import pytest

rclpy = pytest.importorskip('rclpy')
pytest.importorskip('contact_scan_interfaces')
yaml = pytest.importorskip('yaml')

SIM_YAML = Path(__file__).resolve().parents[2] / 'contact_scan_bringup' / 'config' / 'sim.yaml'
if not SIM_YAML.exists():
    pytest.skip('contact_scan_bringup/config/sim.yaml 이 없다', allow_module_level=True)

from sequence_helpers import isolated_ros_env  # noqa: E402

os.environ.update(isolated_ros_env())  # 조 범위의 도메인 + LOCALHOST. rclpy.init 전에 건다

from contact_scan_interfaces.action import RunScan  # noqa: E402
from contact_scan_interfaces.msg import ScanResult  # noqa: E402
from contact_scan_interfaces.msg import ScanState  # noqa: E402
from contact_scan_interfaces.srv import StopScan  # noqa: E402
from contact_scan_qos import QOS_STATE  # noqa: E402
import fake_peers as F  # noqa: E402
from rclpy.action import ActionClient  # noqa: E402
from rclpy.executors import MultiThreadedExecutor  # noqa: E402
from scan_manager.contract_enums import Operation  # noqa: E402
from scan_manager.contract_enums import Reason  # noqa: E402
from sequence_helpers import BOX_SIZE  # noqa: E402

TEST_LATENCY_S = 0.02   # 테스트 전용 임의값
TIMEOUT_S = 60.0
DISCOVERY_SETTLE_S = 1.0


class SimProcess:

    def __init__(self, result_dir, with_latency=True):
        data = yaml.safe_load(SIM_YAML.read_text(encoding='utf-8'))
        params = data['scan_manager']['ros__parameters']
        self.yaml_params = params
        params_file = SIM_YAML
        if not with_latency:
            # sim.yaml 의 detect_latency_s 가 채워진 뒤(T07)로는, '없는 필수 값' 경로를 보려면
            # 그 키를 뺀 사본으로 띄워야 한다. ROS 파라미터는 '없음'으로 덮어쓸 수 없다
            params.pop('detect_latency_s', None)
            params_file = Path(result_dir).parent / 'sim_without_latency.yaml'
            params_file.write_text(yaml.safe_dump(data, allow_unicode=True), encoding='utf-8')
        command = [
            sys.executable, '-c', 'from scan_manager.scan_manager import main; main()',
            '--ros-args', '--params-file', str(params_file), '-p', f'result_dir:={result_dir}']
        if with_latency:
            command += ['-p', f'detect_latency_s:={TEST_LATENCY_S}']
        self.process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=dict(os.environ))
        self.lines, self._ready = [], threading.Event()
        self._closed = False
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()

        rclpy.init()
        self.peers = F.FakePeers(model={**params, 'detect_latency_s': TEST_LATENCY_S})
        self.client = rclpy.create_node('fake_bridge')
        self.results, self.states = [], []
        self.client.create_subscription(ScanResult, '/scan/result', self.results.append, QOS_STATE)
        self.client.create_subscription(ScanState, '/scan/state', self.states.append, QOS_STATE)
        self.run_client = ActionClient(self.client, RunScan, '/scan/run')
        self.stop_client = self.client.create_client(StopScan, '/scan/stop')
        self.executor = MultiThreadedExecutor(num_threads=4)
        self.executor.add_node(self.peers)
        self.executor.add_node(self.client)
        self._stop_spin = threading.Event()
        self._spin = threading.Thread(target=self._spin_loop, daemon=True)
        self._spin.start()

    def _spin_loop(self):
        while not self._stop_spin.is_set():
            self.executor.spin_once(timeout_sec=0.05)

    def _read(self):
        for line in self.process.stderr:
            self.lines.append(line)
            if 'scan_manager 준비' in line:
                self._ready.set()

    def log(self):
        return ''.join(self.lines)

    def wait(self, condition, timeout_s=TIMEOUT_S):
        deadline = time.monotonic() + timeout_s
        while not condition() and time.monotonic() < deadline:
            time.sleep(0.02)
        return condition()

    def run_scan(self):
        assert self._ready.wait(TIMEOUT_S), self.log()
        assert self.run_client.wait_for_server(timeout_sec=TIMEOUT_S)
        # 다른 프로세스와 막 발견된 직후에 goal 을 보내면 응답이 버려질 수 있다(rclpy: "failed to send response
        # (timeout): client will not receive response"). 서버 쪽의 응답 경로까지 맞물리기를 기다린다.
        assert self.wait(lambda: self.states), self.log()
        time.sleep(DISCOVERY_SETTLE_S)
        # scan_manager 가 가짜 상대 노드의 /robot/status · /safety/status 를 받을 때까지 START 는 거절된다
        deadline = time.monotonic() + TIMEOUT_S
        while True:
            sent = self.run_client.send_goal_async(RunScan.Goal(request_id='sim-run'))
            assert self.wait(sent.done), self.log()
            done = sent.result().get_result_async()
            assert self.wait(done.done), self.log()
            result = done.result().result
            waiting_for_status = result.reason_code in (
                Reason.SAFETY_LATCHED, Reason.ROBOT_DISCONNECTED) and '미수신' in result.detail
            if not waiting_for_status or time.monotonic() > deadline:
                return result
            time.sleep(0.1)

    def close(self):
        """SIGINT 두 번(launch 의 Ctrl-C). 종료 코드를 돌려준다."""
        if self._closed:
            return None
        self._closed = True
        code = None
        try:
            if self.process.poll() is None:
                self.process.send_signal(signal.SIGINT)
                time.sleep(0.05)
                self.process.send_signal(signal.SIGINT)
            code = self.process.wait(timeout=30.0)
        finally:
            self.process.kill()
            self.peers.quiet()
            self._stop_spin.set()
            self._spin.join(timeout=10.0)
            self.executor.shutdown(timeout_sec=5.0)
            self.client.destroy_node()
            self.peers.destroy_node()
            rclpy.try_shutdown()
        self._reader.join(timeout=5.0)
        return code


@pytest.fixture
def sim(tmp_path):
    rigs = []

    def make(**kwargs):
        rig = SimProcess(tmp_path / 'data', **kwargs)
        rigs.append(rig)
        return rig
    yield make
    for rig in rigs:
        rig.close()   # 이미 닫았으면 아무 일도 하지 않는다


def test_full_scan_with_sim_yaml_in_a_real_process(sim, tmp_path):
    rig = sim()
    result = rig.run_scan()

    assert result.success, (result.reason_code, result.detail, rig.log())
    shape = result.result
    assert shape.success and shape.frame_id == 'workpiece_fixture'
    # sim.yaml 의 base_to_fixture · tip_radius_m 으로 가상 직육면체(0.10 x 0.06 x 0.04)가 복원된다
    assert (shape.x_pos, shape.x_neg) == pytest.approx((0.05, -0.05))
    assert (shape.y_pos, shape.y_neg) == pytest.approx((0.03, -0.03))
    assert (shape.width, shape.length, shape.height) == pytest.approx(BOX_SIZE)

    # goal 에 실린 값은 sim.yaml 의 값이다(코드 예비값이 아니다)
    params = rig.yaml_params
    by_op = {}
    for goal in rig.peers.goals:
        by_op.setdefault(Operation(goal.operation), []).append(goal)
    assert {g.speed for g in by_op[Operation.DESCEND]} == {params['descend_speed_mps']}
    assert {g.max_distance for g in by_op[Operation.DESCEND]} == {params['max_descend_m']}
    assert {g.speed for g in by_op[Operation.SLIDE]} == {params['slide_speed_mps']}
    assert {g.max_distance for g in by_op[Operation.SLIDE]} == {params['max_slide_m']}
    assert {g.speed for g in by_op[Operation.MOVE_TO]} == {
        params['move_speed_mps'], params['recontact_speed_mps']}
    first = by_op[Operation.MOVE_TO][0].target
    assert [first.position.x, first.position.y, first.position.z] == params['search_origin_pose'][:3]
    assert rig.peers.goals[-1].operation == Operation.HOME
    timeout = rig.peers.goals[0].timeout
    assert timeout.sec + timeout.nanosec * 1e-9 == pytest.approx(params['motion_timeout_s'])

    # 원본이 디스크에 있다
    files = sorted(p.name for p in (tmp_path / 'data' / result.scan_id).iterdir())
    assert files == ['progress.json', 'result.json']
    saved = json.loads((tmp_path / 'data' / result.scan_id / 'result.json').read_text())
    assert saved['shape']['success'] is True and saved['shape']['width'] == pytest.approx(0.10)
    assert saved['node_params']['detect_latency_s'] == TEST_LATENCY_S
    progress = json.loads((tmp_path / 'data' / result.scan_id / 'progress.json').read_text())
    assert progress['state']['phase'] == 'DONE'
    assert rig.wait(lambda: rig.results) and rig.results[-1].scan_id == result.scan_id

    assert rig.close() == 0, rig.log()
    assert 'Traceback' not in rig.log() and '[ERROR]' not in rig.log(), rig.log()


def test_sim_yaml_as_is_refuses_start_and_names_the_missing_value(sim):
    """필수 파라미터가 하나라도 없으면 sim 에서도 START 가 거절되고 빠진 이름이 나온다.

    sim.yaml 은 T07 에서 detect_latency_s 까지 채워졌으므로, 이 경로를 보려면 그 키를 뺀 사본으로 띄운다.
    """
    rig = sim(with_latency=False)
    result = rig.run_scan()
    assert not result.success and result.reason_code == Reason.INVALID_VALUE
    assert 'detect_latency_s' in result.detail
    assert rig.peers.goals == []
    assert rig.close() == 0, rig.log()
