"""이동 여부 판정 (T15). ROS도 두산 드라이버도 없이 돈다.

`get_robot_state`는 Virtual에서 이동 중에도 STANDBY(1)를 돌려줬다(2026-09-20, `docs/env/api-check-log.md`).
그래서 최근 창 안의 TCP 위치 변화로 이동 여부를 본다.
"""
import math


def trim(positions, now_s, window_s):
    """(시각, 위치) 목록에서 창을 벗어난 앞쪽을 버린다."""
    while positions and now_s - positions[0][0] > window_s:
        positions.popleft()
    return positions


def is_moving(positions, eps_m):
    """창 안의 첫 위치에서 `eps_m`보다 멀어진 적이 있으면 이동 중.

    위치를 모르면(점이 2개 미만) **True**를 돌려준다. 정지 완료의 유일한 근거가
    `connected && !moving`이라, 모르는 상태를 정지로 보고하면 scan_manager가
    움직이는 로봇을 멈춘 것으로 본다.
    """
    if len(positions) < 2:
        return True
    first = positions[0][1]
    return any(math.dist(first, pos) > eps_m for _, pos in positions)
