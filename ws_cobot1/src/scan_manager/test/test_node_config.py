"""scan_manager 노드: /scan/set_config 의 전파(계약 2.4 P01~P03)를 가짜 상대 노드로 검증한다.

로봇 · 드라이버 · Virtual Mode 를 쓰지 않는다. 상대는 fake_peers.FakeParamPeer 3개다 —
계약 파라미터만 선언해 두면 rclpy 가 set_parameters · get_parameters 를 열어 주므로,
scan_manager 가 실제로 쓰는 경로 그대로 돈다. 수치는 테스트용 임의값이다.
"""

import os
import threading
import time

import pytest

rclpy = pytest.importorskip('rclpy')
pytest.importorskip('contact_scan_interfaces')

from sequence_helpers import isolated_ros_env  # noqa: E402

os.environ.update(isolated_ros_env())  # 조 범위의 도메인 + LOCALHOST. rclpy.init 전에 건다

from contact_scan_interfaces.action import Resume  # noqa: E402
from contact_scan_interfaces.action import ReturnHome  # noqa: E402
from contact_scan_interfaces.action import RunScan  # noqa: E402
from contact_scan_interfaces.msg import ScanConfig  # noqa: E402
from contact_scan_interfaces.srv import SetConfig  # noqa: E402
from contact_scan_interfaces.srv import StopScan  # noqa: E402
import fake_peers as F  # noqa: E402
from rclpy.action import ActionClient  # noqa: E402
from rclpy.executors import MultiThreadedExecutor  # noqa: E402
from rclpy.parameter import Parameter  # noqa: E402
from scan_manager import propagation as P  # noqa: E402
from scan_manager.contract_enums import Operation  # noqa: E402
from scan_manager.contract_enums import Reason  # noqa: E402
from scan_manager.result_store.records import CONFIG_FIELDS  # noqa: E402
from scan_manager.scan_manager import ScanManager  # noqa: E402
from sequence_helpers import VALUES  # noqa: E402

TIMEOUT_S = 20.0
SET_FLAG = dict(CONFIG_FIELDS)


def config_msg(**values) -> ScanConfig:
    """{이름: 값} → ScanConfig(*_set=true 인 항목만)."""
    msg = ScanConfig()
    for name, value in values.items():
        setattr(msg, name, value)
        setattr(msg, SET_FLAG[name], True)
    return msg


class Rig:
    """scan_manager + 전파 대상 가짜 노드 3개 + 관제 클라이언트를 한 executor 에서 돌린다."""

    def __init__(self, result_dir, peers=None, motion_peers=False, **changes):
        values = {**VALUES, 'result_dir': str(result_dir), **changes}
        self.node = ScanManager(parameter_overrides=[
            Parameter(name, value=value) for name, value in values.items() if value is not None])
        self.peers = F.param_peers(**(peers or {}))
        self.motion = F.FakePeers() if motion_peers else None
        self.client = rclpy.create_node('fake_bridge')
        self.config_client = self.client.create_client(SetConfig, '/scan/set_config')
        self.stop_client = self.client.create_client(StopScan, '/scan/stop')
        self.run_client = ActionClient(self.client, RunScan, '/scan/run')
        self.resume_client = ActionClient(self.client, Resume, '/scan/resume')
        self.home_client = ActionClient(self.client, ReturnHome, '/scan/home')
        self.executor = MultiThreadedExecutor(num_threads=8)
        for node in [self.node, self.client, self.motion, *self.peers.values()]:
            if node is not None:
                self.executor.add_node(node)
        self._stop_spin = threading.Event()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        assert self.config_client.wait_for_service(timeout_sec=TIMEOUT_S)
        if self.motion is not None:
            self.wait_ready()
            # 이 파일은 설정만 본다. START 가 접수되면 첫 모션에서 바로 실패하게 두어
            # 탐색 전체를 돌리지 않는다(거절 사유가 PARAM_SET_FAILED 인지만 보면 된다).
            self.motion.reject_operations = {int(Operation.MOVE_TO)}

    def _spin(self):
        while not self._stop_spin.is_set():
            self.executor.spin_once(timeout_sec=0.05)

    def close(self):
        self.node.close()
        self.node._state_timer.cancel()
        if self.motion is not None:
            self.motion.quiet()
        self._stop_spin.set()
        self._thread.join(timeout=10.0)
        self.executor.shutdown(timeout_sec=5.0)
        for node in [self.client, self.motion, *self.peers.values(), self.node]:
            if node is not None:
                node.destroy_node()

    # -- 명령 --

    def set_config_async(self, request_id='cfg', **values):
        return self.config_client.call_async(
            SetConfig.Request(request_id=request_id, config=config_msg(**values)))

    def set_config(self, request_id='cfg', **values):
        future = self.set_config_async(request_id, **values)
        assert self.wait(future.done), 'SetConfig 응답이 오지 않았다'
        return future.result()

    def run(self, request_id='run'):
        assert self.run_client.wait_for_server(timeout_sec=TIMEOUT_S)
        sent = self.run_client.send_goal_async(RunScan.Goal(request_id=request_id))
        assert self.wait(sent.done)
        handle = sent.result()
        assert handle.accepted
        result = handle.get_result_async()
        assert self.wait(result.done, timeout_s=60.0), 'RunScan Result 가 오지 않았다'
        return result.result().result

    def wait_ready(self):
        """가짜 상대 노드의 상태를 scan_manager 가 받을 때까지(못 받으면 START 가 103 으로 거절된다)."""
        conditions = self.node.conditions
        assert self.wait(lambda: None not in (
            conditions().robot_connected, conditions().safety_latched))

    def wait(self, condition, timeout_s=TIMEOUT_S):
        deadline = time.monotonic() + timeout_s
        while not condition() and time.monotonic() < deadline:
            time.sleep(0.01)
        return condition()


@pytest.fixture
def ros():
    rclpy.init()
    yield
    rclpy.try_shutdown()


@pytest.fixture
def rig(ros, tmp_path):
    made = []

    def make(**kwargs):
        made.append(Rig(tmp_path / 'data', **kwargs))
        return made[-1]

    yield make
    for r in made:
        r.close()


def applied(response, name):
    return getattr(response.applied, name), getattr(response.applied, SET_FLAG[name])


# ---- 전파 ----

def test_세_노드에_계약_이름으로_전파한다(rig):
    r = rig()
    response = r.set_config(
        contact_threshold_n=4.0, edge_drop_m=0.0006, debounce_n=5,
        over_force_n=12.0, target_force_n=2.5, drop_limit_m=0.004)
    assert response.success, response.detail
    assert response.reason_code == int(Reason.OK)
    assert r.peers['contact_detector'].value('contact_threshold_n') == 4.0
    assert r.peers['contact_detector'].value('edge_drop_m') == 0.0006
    assert r.peers['contact_detector'].value('debounce_n') == 5
    assert r.peers['contact_detector'].value('over_force_n') == 12.0
    assert r.peers['safety_monitor'].value('over_force_n') == 12.0
    assert r.peers['safety_monitor'].value('drop_limit_m') == 0.004
    # 계약 6.4: ScanConfig.target_force_n → robot_manager.slide_target_force_n
    assert r.peers['robot_manager'].value('slide_target_force_n') == 2.5
    assert r.peers['robot_manager'].value('drop_limit_m') == 0.004


def test_감시_노드부터_보낸다(rig):
    """safety_monitor 가 먼저 받아야 부분 실패에서도 감시가 요청한 값에 가 있다 (계약 7.2)."""
    r = rig()
    r.set_config(over_force_n=11.0, drop_limit_m=0.003, target_force_n=2.0)
    called = {name: peer.first_set_s for name, peer in r.peers.items()}
    assert None not in called.values(), called
    assert sorted(called, key=called.get) == [
        'safety_monitor', 'contact_detector', 'robot_manager']


def test_주지_않은_항목은_그대로_둔다(rig):
    r = rig()
    r.set_config(over_force_n=12.0)
    assert r.peers['contact_detector'].value('contact_threshold_n') == 3.0
    assert r.peers['robot_manager'].value('slide_target_force_n') == 3.0


def test_모션_값만_보내면_전파하지_않는다(rig):
    r = rig()
    response = r.set_config(max_slide_m=0.07)
    assert response.success, response.detail
    assert all(not peer.set_calls for peer in r.peers.values())
    assert applied(response, 'max_slide_m') == (0.07, True)


# ---- applied 는 실제 값이다 ----

def test_applied_의_다른_노드_칸이_읽어_온_실제_값으로_찬다(rig):
    """전파한 적 없는 항목도 그 노드의 값이 실제 값이다(T19a 까지는 NaN 이었다)."""
    r = rig()
    response = r.set_config(max_slide_m=0.07)
    assert applied(response, 'contact_threshold_n') == (3.0, True)
    assert applied(response, 'over_force_n') == (30.0, True)
    assert applied(response, 'drop_limit_m') == (0.005, True)
    assert applied(response, 'target_force_n') == (3.0, True)
    assert applied(response, 'debounce_n') == (3, True)


def test_applied_가_요청값이_아니라_적용된_값이다(rig):
    r = rig()
    response = r.set_config(contact_threshold_n=4.5)
    assert applied(response, 'contact_threshold_n') == (4.5, True)


def test_노드가_안_떠_있으면_그_칸은_모름으로_남는다(rig):
    r = rig(peers={'names': ('safety_monitor', 'contact_detector')})
    response = r.set_config(max_slide_m=0.07)
    value, is_set = applied(response, 'target_force_n')
    assert not is_set and value != value, '모르는 값은 NaN + *_set=false 다(0 금지)'
    assert applied(response, 'contact_threshold_n') == (3.0, True)
    # drop_limit_m 은 robot_manager 쪽을 못 읽었다 → 같은지 확인할 수 없으므로 모름이다
    assert applied(response, 'drop_limit_m')[1] is False


# ---- 부분 실패 ----

def test_한_노드가_거절하면_PARAM_SET_FAILED(rig):
    r = rig(peers={'contact_detector': {'reject': ('debounce_n',)}})
    response = r.set_config(debounce_n=9, over_force_n=12.0, target_force_n=2.0)
    assert not response.success
    assert response.reason_code == int(Reason.PARAM_SET_FAILED)
    assert 'contact_detector' in response.detail and 'debounce_n' in response.detail


def test_거절된_파라미터만_옛_값이고_나머지는_되돌리지_않는다(rig):
    """SetParameters 는 파라미터마다 결과가 따로 온다 — 거절은 그 이름 하나에만 걸린다.

    되돌리지 않는 것이 규칙이다(되돌리기도 실패할 수 있다). 무엇이 어떻게 됐는지 detail 에 남긴다.
    """
    r = rig(peers={'contact_detector': {'reject': ('debounce_n',)}})
    response = r.set_config(debounce_n=9, over_force_n=12.0, target_force_n=2.0)
    assert r.peers['contact_detector'].value('debounce_n') == 3       # 거절됐다
    assert r.peers['contact_detector'].value('over_force_n') == 12.0  # 같은 요청의 나머지는 들어간다
    assert r.peers['safety_monitor'].value('over_force_n') == 12.0    # 먼저 간 것도 그대로 둔다
    assert r.peers['robot_manager'].value('slide_target_force_n') == 2.0
    assert 'debounce_n' in response.detail and 'over_force_n' not in response.detail.split('실패')[1]
    # 쌍은 맞으므로(12.0 = 12.0) 어긋남 사유는 붙지 않는다
    assert '7.2' not in response.detail
    assert applied(response, 'over_force_n') == (12.0, True)
    assert applied(response, 'debounce_n') == (3, True), '거절된 값은 옛 값이 실제 값이다'


def test_노드가_안_떠_있으면_미기동으로_실패한다(rig):
    r = rig(peers={'names': ('safety_monitor', 'contact_detector')},
            server_wait_timeout_s=0.3)
    response = r.set_config(target_force_n=2.0, over_force_n=12.0)
    assert not response.success
    assert response.reason_code == int(Reason.PARAM_SET_FAILED)
    assert 'robot_manager' in response.detail and '미기동' in response.detail
    assert r.peers['safety_monitor'].value('over_force_n') == 12.0, '나머지는 계속 보낸다'


def test_범위_밖이면_전파도_하지_않는다(rig):
    r = rig()
    response = r.set_config(over_force_n=-1.0, contact_threshold_n=4.0)
    assert not response.success
    assert response.reason_code == int(Reason.INVALID_VALUE)
    assert all(not peer.set_calls for peer in r.peers.values()), '같이 온 정상값도 적용하지 않는다'


# ---- 같은 값이어야 하는 쌍 (계약 7.2) ----

def test_쌍이_어긋나면_SetConfig_도_실패로_알린다(rig):
    r = rig(peers={'safety_monitor': {'reject': ('over_force_n',)}})
    response = r.set_config(over_force_n=12.0)
    assert not response.success
    assert response.reason_code == int(Reason.PARAM_SET_FAILED)
    assert 'over_force_n' in response.detail and '7.2' in response.detail
    assert applied(response, 'over_force_n')[1] is False, '대표값이 없으므로 모름이다'


def test_어긋난_채로는_START_를_거절한다(rig):
    r = rig(peers={'safety_monitor': {'values': {'over_force_n': 10.0, 'drop_limit_m': 0.005}}},
            motion_peers=True)
    result = r.run()
    assert not result.success
    assert result.reason_code == int(Reason.PARAM_SET_FAILED)
    assert 'over_force_n' in result.detail


def test_맞추면_START_가_다시_통과한다(rig):
    r = rig(peers={'safety_monitor': {'values': {'over_force_n': 10.0, 'drop_limit_m': 0.005}}},
            motion_peers=True)
    assert r.run('before').reason_code == int(Reason.PARAM_SET_FAILED)
    assert r.set_config(over_force_n=30.0).success
    result = r.run('after')
    assert result.reason_code != int(Reason.PARAM_SET_FAILED), result.detail
    assert result.reason_code != int(Reason.SAFETY_LATCHED), result.detail


def test_한쪽을_못_읽으면_START_를_막지_않는다(rig):
    """모른다고 막으면 노드 하나가 늦게 뜬 것만으로 모든 START 가 막힌다."""
    r = rig(peers={'names': ('contact_detector',)}, motion_peers=True,
            server_wait_timeout_s=0.3)
    result = r.run()
    assert result.reason_code != int(Reason.PARAM_SET_FAILED), result.detail
    assert result.reason_code != int(Reason.SAFETY_LATCHED), result.detail


def test_어긋난_채로는_RESUME_도_거절한다(rig):
    """재시작도 로봇을 다시 움직인다. START 와 같은 규칙이다 (계약 7.2)."""
    r = rig(peers={'safety_monitor': {'values': {'over_force_n': 10.0, 'drop_limit_m': 0.005}}},
            motion_peers=True)
    assert r.resume_client.wait_for_server(timeout_sec=TIMEOUT_S)
    sent = r.resume_client.send_goal_async(Resume.Goal(request_id='resume-mismatch'))
    assert r.wait(sent.done) and sent.result().accepted
    got = sent.result().get_result_async()
    assert r.wait(got.done, timeout_s=30.0)
    result = got.result().result
    assert not result.success
    assert result.reason_code == int(Reason.PARAM_SET_FAILED), result.detail
    assert 'over_force_n' in result.detail


def test_안전복귀는_어긋나도_막지_않는다(rig):
    """안전복귀는 독립된 명령이다(CLAUDE.md 규칙 3). 설정이 어긋났다고 못 돌아가면 안 된다."""
    r = rig(peers={'safety_monitor': {'values': {'over_force_n': 10.0, 'drop_limit_m': 0.005}}},
            motion_peers=True)
    r.motion.reject_operations = set()
    assert r.home_client.wait_for_server(timeout_sec=TIMEOUT_S)
    sent = r.home_client.send_goal_async(ReturnHome.Goal(request_id='home-mismatch'))
    assert r.wait(sent.done) and sent.result().accepted
    got = sent.result().get_result_async()
    assert r.wait(got.done, timeout_s=30.0)
    assert got.result().result.success, got.result().result.detail


def test_상대를_기다릴_한도가_없으면_전파하지_않고_알린다(rig):
    """server_wait_timeout_s 가 없으면 한도 없는 기다림을 만들지 않는다(CLAUDE.md 규칙 7: 예비값 없음)."""
    r = rig(server_wait_timeout_s=None)
    response = r.set_config(over_force_n=12.0)
    assert not response.success
    assert response.reason_code == int(Reason.PARAM_SET_FAILED)
    assert 'server_wait_timeout_s' in response.detail
    assert all(not peer.set_calls for peer in r.peers.values())
    assert applied(response, 'over_force_n')[1] is False


# ---- 다른 명령을 막지 않는다 ----

def test_전파가_늦어도_STOP_은_기다리지_않는다(rig):
    """/scan/stop 은 _job_lock 만 잡고, SetConfig 와 다른 콜백 그룹에서 돈다 (규칙 3)."""
    r = rig(peers={'safety_monitor': {'delay_s': 2.0}}, server_wait_timeout_s=5.0)
    assert r.stop_client.wait_for_service(timeout_sec=TIMEOUT_S)
    pending = r.set_config_async(over_force_n=12.0)
    time.sleep(0.3)                      # 전파가 safety_monitor 에서 붙잡혀 있는 동안
    started = time.monotonic()
    stop = r.stop_client.call_async(StopScan.Request(request_id='stop-while-config'))
    assert r.wait(stop.done, timeout_s=1.5), 'SetConfig 가 도는 동안 /scan/stop 이 막혔다'
    assert time.monotonic() - started < 1.5
    assert r.wait(pending.done, timeout_s=TIMEOUT_S) and pending.result().success


def test_START_의_되읽기가_늦어도_STOP_은_기다리지_않는다(rig):
    """START 접수의 되읽기는 작업 락을 잡기 **전에** 끝낸다. 상대가 꺼져 있어도 정지는 받는다."""
    r = rig(peers={'names': ('contact_detector',)}, motion_peers=True,
            server_wait_timeout_s=3.0)
    assert r.stop_client.wait_for_service(timeout_sec=TIMEOUT_S)
    assert r.run_client.wait_for_server(timeout_sec=TIMEOUT_S)
    sent = r.run_client.send_goal_async(RunScan.Goal(request_id='run-while-reading'))
    assert r.wait(sent.done) and sent.result().accepted
    time.sleep(0.3)                      # 되읽기가 없는 노드 두 개를 기다리는 동안
    started = time.monotonic()
    stop = r.stop_client.call_async(StopScan.Request(request_id='stop-while-start'))
    assert r.wait(stop.done, timeout_s=2.0), 'START 접수가 도는 동안 /scan/stop 이 막혔다'
    assert time.monotonic() - started < 2.0
    r.wait(lambda: sent.result().get_result_async().done, timeout_s=30.0)


def test_기동_뒤에_다른_노드_값을_한_번_읽는다(rig):
    """announce_ready 가 거는 한 번짜리 타이머. SetConfig 없이도 기록의 config 가 찬다."""
    r = rig()
    assert r.node._peer_config == {}
    r.node.announce_ready()
    assert r.wait(lambda: r.node._peer_config.get('contact_detector', {}).get(
        'contact_threshold_n') == 3.0), r.node._peer_config
    config = r.node._effective_config()
    assert config['over_force_n'] == 30.0 and config['target_force_n'] == 3.0


def test_전파가_도는_동안_START_는_끝난_값을_쓴다(rig):
    """START 는 _config_lock 을 기다린다. 반쯤 전파된 값으로 재지 않는다."""
    r = rig(peers={'safety_monitor': {'delay_s': 1.0}}, motion_peers=True,
            server_wait_timeout_s=5.0)
    pending = r.set_config_async(over_force_n=12.0)
    time.sleep(0.2)
    result = r.run()
    assert r.wait(pending.done, timeout_s=TIMEOUT_S) and pending.result().success
    assert result.reason_code != int(Reason.PARAM_SET_FAILED), result.detail
    assert r.peers['contact_detector'].value('over_force_n') == 12.0


def test_동작_중에는_BUSY_로_거절하고_전파하지_않는다(rig):
    r = rig(motion_peers=True)
    r.motion.reject_operations = set()
    r.motion.behavior[F.key(Operation.MOVE_TO)] = F.HOLD   # 기준점 이동에서 붙잡는다
    assert r.run_client.wait_for_server(timeout_sec=TIMEOUT_S)
    sent = r.run_client.send_goal_async(RunScan.Goal(request_id='busy'))
    assert r.wait(sent.done) and sent.result().accepted
    assert r.wait(lambda: r.node.state_machine.is_busy)
    before = list(r.peers['contact_detector'].set_calls)
    response = r.set_config(over_force_n=12.0)
    assert not response.success and response.reason_code == int(Reason.BUSY)
    assert r.peers['contact_detector'].set_calls == before
    r.stop_client.wait_for_service(timeout_sec=TIMEOUT_S)
    r.stop_client.call_async(StopScan.Request(request_id='cleanup'))
    r.wait(lambda: not r.node.state_machine.is_busy)


# ---- 기록 ----

def test_전파_대상_이름이_계약_표와_같다():
    """가짜 노드가 선언한 이름 = propagation 이 보내는 이름 = 계약 6.4 절."""
    for node, items in P.TARGETS:
        assert set(F.PEER_PARAMS[node]) == {param for _name, param in items}
