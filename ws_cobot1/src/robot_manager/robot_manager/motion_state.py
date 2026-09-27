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


def is_moving(positions, eps_m, window_s=None, min_span_ratio=0.5):
    """창 안의 첫 위치에서 `eps_m`보다 멀어진 적이 있으면 이동 중.

    **모르면 True**다. 정지 완료의 유일한 근거가 `connected && !moving`이라,
    모르는 상태를 정지로 보고하면 scan_manager가 움직이는 로봇을 멈춘 것으로 본다.
    모르는 경우는 둘이다.

    1. 점이 2개 미만이다.
    2. 남은 점들이 창을 충분히 덮지 않는다(`window_s`를 주었을 때).
       샘플 공백 뒤에는 창에 갓 들어온 점 두어 개만 남는다. 그 점들 사이의 시간이
       몇십 ms뿐이라, 움직이는 중이어도 그 사이 변위가 `eps_m`에 못 미쳐 "정지"로
       읽힌다. `eps_m`은 창 전체(`window_s`)를 덮었을 때만 뜻이 있는 값이다.

       2026-09-21 실기: 359 ms 공백 뒤 창에 25 ms 짜리 두 점만 남았고, 3 mm/s로
       내려가는 중인데 그 사이 변위가 0.076 mm(< 0.2 mm)라 정지로 판정됐다.
       robot_manager가 동작을 완료로 보고한 뒤에도 로봇은 12 mm를 더 내려갔고,
       결과의 정지 좌표도 그만큼 틀렸다.
    """
    if len(positions) < 2:
        return True
    if window_s and positions[-1][0] - positions[0][0] < min_span_ratio * window_s:
        return True
    first = positions[0][1]
    return any(math.dist(first, pos) > eps_m for _, pos in positions)


def has_moved(positions, eps_m):
    """창 안에서 실제로 `eps_m`보다 움직인 것이 **위치로 확인됐는가**. 모르면 False.

    `is_moving`과 반대 방향으로 안전하다. 동작 감시가 "한 번이라도 움직였다"를 기록할 때 쓴다.
    `is_moving`의 "모르면 True"를 그대로 쓰면 샘플 공백 한 번이 "움직였다"로 남고, 로봇이 아직
    출발하기 전(힘 제어를 켜는 중 · 드라이버 지연)에 창이 다시 차면 "멈췄다"가 되어 도착으로 판정된다.

    2026-09-22 실기: 밀기 732 · 847 · 943 이 0.1~0.7 mm 만 가고 "최대 거리까지 접촉 소실 없음"으로
    끝났다. 하강 728 은 0.1 s 만에 끝났는데 로봇은 36 s 를 더 내려가 접촉 판정 없이
    과대 외력(15.6 N)으로 멈췄다.
    """
    points = list(positions)   # 다른 콜백이 덧붙이는 중에도 한 번에 복사한다
    if len(points) < 2:
        return False
    first = points[0][1]
    return any(math.dist(first, pos) > eps_m for _, pos in points)
