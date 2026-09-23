"""테스트용 ROS_DOMAIN_ID 고르기 (#126).

이 파일은 rclpy 를 쓰지 않는다. 헬퍼가 고르는 규칙만 본다 — /proc 조회, 락 점유, 고갈.
"""

import multiprocessing
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

import contact_scan_testing as ct  # noqa: E402


@pytest.fixture(autouse=True)
def fresh(tmp_path, monkeypatch):
    """모듈 수준 캐시와 락 디렉터리를 테스트마다 새로 만든다."""
    monkeypatch.setenv('CONTACT_SCAN_TEST_LOCK_DIR', str(tmp_path / 'locks'))
    monkeypatch.delenv('CONTACT_SCAN_TEST_DOMAIN_ID', raising=False)
    monkeypatch.setattr(ct, '_chosen_domain', None)
    monkeypatch.setattr(ct, '_held_locks', [])
    yield


def _fake_proc(root: Path, entries: dict) -> Path:
    """{pid: 환경 변수 문자열 또는 None} 으로 가짜 /proc 을 만든다."""
    root.mkdir(parents=True, exist_ok=True)
    for pid, value in entries.items():
        directory = root / str(pid)
        directory.mkdir()
        items = [b'PATH=/usr/bin']
        if value is not None:
            items.append(f'ROS_DOMAIN_ID={value}'.encode())
        (directory / 'environ').write_bytes(b'\0'.join(items) + b'\0')
    (root / 'cpuinfo').write_text('숫자가 아닌 항목은 건너뛴다')
    return root


def test_domains_in_use_reads_proc(tmp_path):
    root = _fake_proc(tmp_path / 'proc', {111: '30', 222: '35', 333: None, 444: '아니다'})
    assert ct.domains_in_use(str(root)) == {30, 35}


def test_domains_in_use_skips_own_pid(tmp_path):
    """자기 자신이 물려받은 번호 때문에 후보가 줄어들면 안 된다."""
    root = _fake_proc(tmp_path / 'proc', {os.getpid(): '33', 222: '34'})
    assert ct.domains_in_use(str(root)) == {34}


def test_domains_in_use_survives_unreadable_proc():
    """/proc 이 없어도 죽지 않는다(컨테이너). 못 뺀 번호는 락이 막는다."""
    assert ct.domains_in_use('/이런 경로는 없다') == set()


def test_pick_domain_avoids_live_processes(monkeypatch):
    monkeypatch.setattr(ct, 'domains_in_use', lambda *a, **k: {31, 32, 33})
    assert ct.pick_domain() == 34


def test_pick_domain_is_stable_within_process(monkeypatch):
    monkeypatch.setattr(ct, 'domains_in_use', lambda *a, **k: set())
    first = ct.pick_domain()
    assert ct.pick_domain() == first
    assert ct.isolated_ros_env()['ROS_DOMAIN_ID'] == str(first)


def test_isolated_ros_env_keeps_localhost(monkeypatch):
    monkeypatch.setattr(ct, 'domains_in_use', lambda *a, **k: set())
    env = ct.isolated_ros_env()
    assert env['ROS_AUTOMATIC_DISCOVERY_RANGE'] == 'LOCALHOST'
    assert int(env['ROS_DOMAIN_ID']) in ct.CANDIDATE_DOMAIN_IDS


def test_apply_sets_environment(monkeypatch):
    monkeypatch.setattr(ct, 'domains_in_use', lambda *a, **k: set())
    env = ct.apply_isolated_ros_env()
    assert os.environ['ROS_DOMAIN_ID'] == env['ROS_DOMAIN_ID']
    assert os.environ['ROS_AUTOMATIC_DISCOVERY_RANGE'] == 'LOCALHOST'


def test_forced_domain_wins(monkeypatch):
    """손으로 고정하는 구멍. #126 주의: 99 · 41 은 이미 쓰는 번호다."""
    monkeypatch.setenv('CONTACT_SCAN_TEST_DOMAIN_ID', '37')
    monkeypatch.setattr(ct, 'domains_in_use', lambda *a, **k: {37})
    assert ct.pick_domain() == 37


def test_exhausted_raises_instead_of_sharing(monkeypatch):
    """9 개가 다 차면 조용히 공유하지 않고 멈춘다."""
    monkeypatch.setattr(ct, 'domains_in_use', lambda *a, **k: set(ct.CANDIDATE_DOMAIN_IDS))
    with pytest.raises(ct.DomainsExhausted) as caught:
        ct.pick_domain()
    assert '#126' in str(caught.value)


def _child_pick(queue):
    """다른 프로세스에서 고르게 한다.

    fork 라 부모의 모듈 상태를 물려받으므로 캐시를 지운다. 부모가 잡아 둔 락의 파일 기술자도
    물려받지만, 락은 **열린 파일 서술자마다** 걸리므로 자식이 같은 파일에 새로 걸면 막힌다 —
    그게 이 테스트가 보려는 것이다.
    """
    ct._chosen_domain = None
    ct._held_locks = []
    try:
        queue.put(ct.pick_domain())
    except ct.DomainsExhausted:
        queue.put('exhausted')


def test_lock_stops_two_processes_from_sharing(tmp_path, monkeypatch):
    """확인만으로는 못 막는 틈을 락이 막는다. 두 프로세스는 다른 번호를 받아야 한다."""
    empty_proc = str(_fake_proc(tmp_path / 'proc', {}))
    monkeypatch.setenv('CONTACT_SCAN_TEST_PROC_ROOT', empty_proc)
    mine = ct.pick_domain()

    context = multiprocessing.get_context('fork')
    queue = context.Queue()
    child = context.Process(target=_child_pick, args=(queue,))
    child.start()
    theirs = queue.get(timeout=30)
    child.join(timeout=30)

    assert theirs != mine, '락을 들고 있는 번호를 다른 프로세스가 또 골랐다'
    assert theirs in ct.CANDIDATE_DOMAIN_IDS


def test_lock_is_released_when_process_ends(tmp_path, monkeypatch):
    """끝난 프로세스의 번호는 다시 쓸 수 있어야 한다(락 파일은 남아도 된다)."""
    empty_proc = str(_fake_proc(tmp_path / 'proc', {}))
    monkeypatch.setenv('CONTACT_SCAN_TEST_PROC_ROOT', empty_proc)

    context = multiprocessing.get_context('fork')
    queue = context.Queue()
    child = context.Process(target=_child_pick, args=(queue,))
    child.start()
    first = queue.get(timeout=30)
    child.join(timeout=30)

    assert ct.pick_domain() == first
