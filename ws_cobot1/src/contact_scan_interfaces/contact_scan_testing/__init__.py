"""노드 테스트가 쓸 ROS_DOMAIN_ID 를 고른다 (#126).

rclpy 를 쓰는 테스트는 in-process 라도 DDS 로 나간다. 같은 도메인에 다른 테스트 프로세스나
사람이 띄운 Virtual · 실기가 있으면 서로의 토픽 · 서비스 · 액션을 발견한다. `LOCALHOST` 는
이 PC 밖으로 나가는 것만 막고, 같은 PC 안에서는 아무것도 막지 않는다.

**번호대를 나누는 방식(`PID % 9`)으로는 못 막는다.** 실행마다 약 1/9 로 겹치고, 실제로
2026-09-21 CI 에서 `safety_monitor` 와 `scan_manager` 가 7.2 초 겹쳤다(#126). 더 나쁜 것은
격리가 없는 패키지다. 2026-09-22 16:03 에 `ROS_DOMAIN_ID=30` · `SUBNET` 셸에서 돌린
`colcon test` 가 **실기의 `/contact/event` 에 가짜 이벤트를 넣었다**
(`docs/test-reports/data/20260922/` 의 t25 기록). 그래서 네 패키지 전부 이 헬퍼를 쓴다.

고르는 방법은 #126 이 정한 것이다.

1. `/proc/*/environ` 에서 **살아 있는 프로세스가 쓰는 번호를 뺀다.** DDS 에 물어보는 방법
   (`get_node_names()` · `ss -lun`)은 못 쓴다 — 노드를 띄워 놓고도 못 잡는다(#126 표).
   사람이 띄운 Virtual · 실기도 이 방법으로 잡힌다.
2. 남은 번호를 **락 파일로 점유한다.** 동시에 시작한 두 프로세스가 같은 순간에 "36 비었네"를
   보는 틈은 "확인"으로는 막을 수 없고 "점유"로만 막힌다.
3. 9 개가 다 차면 **조용히 공유하지 말고 에러로 멈춘다.** 겹친 실행의 결과는 버려야 하므로,
   조용히 도는 것보다 멈추는 것이 싸다.

`docs/env/versions.md` 의 `30 (조 내 분리 필요 시 31~39)` 는 그대로다. 이건 그 규칙을 어기는
게 아니라 지키는 방법이다. 30 은 조 공용(실기 · 팀원의 Virtual)이라 후보에 넣지 않는다.
"""

import fcntl
import os
from pathlib import Path
import tempfile

__all__ = [
    'CANDIDATE_DOMAIN_IDS',
    'DomainsExhausted',
    'ForcedDomainRejected',
    'apply_isolated_ros_env',
    'domains_in_use',
    'isolated_ros_env',
    'lock_dir',
    'pick_domain',
]

# 이 조에 배정된 ROS_DOMAIN_ID 는 30~39 다. 30 은 조 공용이라 쓰지 않는다.
# 범위 밖 번호는 같은 망의 다른 조와 섞인다.
CANDIDATE_DOMAIN_IDS = tuple(range(31, 40))

# 점유한 락의 파일 기술자. 프로세스가 끝날 때까지 들고 있어야 점유가 유지된다
# (닫으면 flock 이 풀린다). 커널이 프로세스 종료 시 알아서 풀어 주므로 치울 것이 없다.
_held_locks = []
_chosen_domain = None


class DomainsExhausted(RuntimeError):
    """후보 번호가 모두 쓰이고 있다. 겹쳐 돌리는 것보다 멈추는 것이 낫다."""


class ForcedDomainRejected(RuntimeError):
    """손으로 고정한 번호를 쓸 수 없다. #126 4 항: 눈대중으로 고르면 안 된다."""


def lock_dir() -> Path:
    """락 파일을 둘 디렉터리. 테스트에서 바꿀 수 있게 환경 변수를 본다."""
    override = os.environ.get('CONTACT_SCAN_TEST_LOCK_DIR')
    if override:
        return Path(override)
    # XDG_RUNTIME_DIR 은 사용자별이라 다른 사용자의 락을 못 본다. 같은 PC 의 다른 사용자가
    # 띄운 노드는 1 번(/proc 조회)에서 잡으므로, 락은 같은 사용자 안에서만 맞으면 된다.
    base = os.environ.get('XDG_RUNTIME_DIR') or tempfile.gettempdir()
    return Path(base) / 'contact_scan_test_domains'


def domains_in_use(proc_root=None) -> set:
    """살아 있는 프로세스가 쓰는 ROS_DOMAIN_ID 를 모은다.

    자기 프로세스는 뺀다. 셸이 `ROS_DOMAIN_ID=35` 를 내려 준 경우 그 값을 물려받고 있는데,
    그것까지 "쓰이는 중"으로 세면 자기 자신 때문에 후보가 하나 줄어든다. 그 셸에 노드가
    떠 있다면 그 노드 프로세스가 따로 잡힌다.

    읽을 수 없는 프로세스(다른 사용자 · 방금 끝난 것)는 건너뛴다. 못 읽은 프로세스가 쓰는
    번호는 못 뺀다 — 그래서 락 파일이 필요하다.
    """
    proc_root = proc_root or os.environ.get('CONTACT_SCAN_TEST_PROC_ROOT') or '/proc'
    mine = os.getpid()
    found = set()
    try:
        entries = os.listdir(proc_root)
    except OSError:
        return found
    for entry in entries:
        if not entry.isdigit() or int(entry) == mine:
            continue
        try:
            raw = Path(proc_root, entry, 'environ').read_bytes()
        except OSError:
            continue        # 권한 없음 · 이미 끝난 프로세스
        for item in raw.split(b'\0'):
            if item.startswith(b'ROS_DOMAIN_ID='):
                value = item[len(b'ROS_DOMAIN_ID='):].decode('utf-8', 'replace').strip()
                if value.isdigit():
                    found.add(int(value))
                break
    return found


def _acquire(domain: int) -> bool:
    """락 파일을 비차단으로 잡는다. 잡았으면 True."""
    directory = lock_dir()
    try:
        directory.mkdir(parents=True, exist_ok=True)
        fd = os.open(directory / f'{domain}.lock', os.O_CREAT | os.O_RDWR, 0o666)
    except OSError:
        return False
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:          # 다른 프로세스가 들고 있다
        os.close(fd)
        return False
    try:
        os.truncate(fd, 0)
        os.write(fd, f'{os.getpid()}\n'.encode())   # 누가 들고 있는지 사람이 보려고 적는다
    except OSError:
        pass
    _held_locks.append(fd)   # 프로세스가 끝날 때까지 닫지 않는다
    return True


def pick_domain(candidates=CANDIDATE_DOMAIN_IDS) -> int:
    """쓰이지 않는 번호를 골라 점유한다. 한 프로세스에서는 늘 같은 번호를 준다."""
    global _chosen_domain
    if _chosen_domain is not None:
        return _chosen_domain
    forced = os.environ.get('CONTACT_SCAN_TEST_DOMAIN_ID')
    if forced:
        # 재현성을 위해 번호를 고정해야 할 때가 있다(T107 반복 측정). 다만 #126 4 항대로
        # **눈대중으로 고르면 안 된다** — 41 은 현지의 9/20 통합용, 99 는 학민의 Virtual
        # 확인용이고, 30 은 조 공용(실기)이다. 그래서 고정값도 후보 범위 · /proc · 락을
        # 다 통과해야 쓴다. 통과 못 하면 조용히 다른 번호로 바꾸지 않고 멈춘다
        domain = int(forced)
        if domain not in candidates:
            raise ForcedDomainRejected(
                f'CONTACT_SCAN_TEST_DOMAIN_ID={domain} 은 후보 {list(candidates)} 밖이다. '
                f'30 은 조 공용(실기 · 팀원의 Virtual), 41 은 9/20 통합용, 99 는 Virtual '
                f'확인용이다(#126 4 항). 범위 안에서 고른다')
        if domain in domains_in_use():
            raise ForcedDomainRejected(
                f'CONTACT_SCAN_TEST_DOMAIN_ID={domain} 은 살아 있는 프로세스가 쓰고 있다. '
                f'그대로 쓰면 서로의 토픽이 섞인다(#126). 다른 번호를 고르거나 고정을 푼다')
        if not _acquire(domain):
            raise ForcedDomainRejected(
                f'CONTACT_SCAN_TEST_DOMAIN_ID={domain} 은 다른 테스트 프로세스가 락을 '
                f'들고 있다. 그 실행이 끝난 뒤 다시 돌린다. 락: {lock_dir()}')
        _chosen_domain = domain
        return domain
    in_use = domains_in_use()
    free = [d for d in candidates if d not in in_use]
    for domain in free:
        if _acquire(domain):
            _chosen_domain = domain
            return domain
    raise DomainsExhausted(
        f'테스트용 ROS_DOMAIN_ID 를 못 골랐다. 후보 {list(candidates)} 중 '
        f'{sorted(in_use & set(candidates))} 는 살아 있는 프로세스가 쓰고 있고, '
        f'남은 {free} 는 다른 테스트 프로세스가 락을 들고 있다. '
        f'같은 도메인을 공유하면 서로의 토픽이 섞여 결과를 못 쓰게 되므로 멈춘다(#126). '
        f'돌고 있는 테스트 · Virtual 이 끝난 뒤 다시 돌린다. '
        f'락: {lock_dir()}')


def isolated_ros_env(candidates=CANDIDATE_DOMAIN_IDS) -> dict:
    """노드 테스트가 쓸 ROS 환경 변수.

    - ROS_DOMAIN_ID: 위 규칙으로 고른 번호.
    - ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST: 이 PC 밖으로 나가지 않는다. 가짜 상대 노드에
      보내는 goal 이 같은 망의 다른 PC 의 robot_manager 로 갈 길을 막는 것은 이 설정이다
      (CLAUDE.md 규칙 1). 같은 PC 안에서 섞이는 것은 도메인 번호로 막는다.
    """
    return {
        'ROS_DOMAIN_ID': str(pick_domain(candidates)),
        'ROS_AUTOMATIC_DISCOVERY_RANGE': 'LOCALHOST',
    }


def apply_isolated_ros_env(candidates=CANDIDATE_DOMAIN_IDS) -> dict:
    """고른 값을 이 프로세스의 환경 변수에 세운다. **rclpy.init() 전에** 불러야 한다.

    conftest.py 의 import 시점에서 부르는 것을 전제로 한다.
    """
    env = isolated_ros_env(candidates)
    os.environ.update(env)
    return env
