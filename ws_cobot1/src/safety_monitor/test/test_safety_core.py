"""감시 로직 단위 테스트. ROS 없이 돈다."""
import pytest

from safety_monitor.safety_core import (
    Condition,
    ConditionWatch,
    DROP_LIMIT,
    Level,
    OP_NONE,
    OP_SLIDE,
    OVER_FORCE,
    ROBOT_STATUS_LOST,
    SafetyLimits,
    SafetyState,
    SAMPLE_STALE,
    Sample,
    StopPhase,
    StopTracker,
)

MM = 1e-3
# 테스트용 값이다. 실기 · sim 의 값은 contact_scan_bringup/config/*.yaml 에 있다
# startup_grace_s=0.0: 기동 유예 없음(유예는 전용 테스트에서 본다)
# drop_limit_margin_m=4 mm: 1차 5 mm · 2차 9 mm (계약 7.2, real.yaml · sim.yaml 과 같은 관계)
LIMITS = SafetyLimits(over_force_n=30.0, drop_limit_m=5 * MM, sample_stale_ms=200,
                      robot_status_timeout_ms=500, confirm_n=1, startup_grace_s=0.0,
                      drop_limit_margin_m=4 * MM)
FIRST_STAGE_M = LIMITS.drop_limit_m                     # robot_manager 의 1차 제한
SECOND_STAGE_M = LIMITS.effective_drop_limit_m          # safety_monitor 의 2차 제한
Z0 = 0.080


def sample(fz=0.0, z=Z0, operation=OP_SLIDE, motion_id=4, valid=True, t=0.0):
    return Sample(stamp_s=t, position=(0.4, 0.0, z), force=(0.1, 0.2, fz),
                  valid=valid, motion_id=motion_id, operation=operation)


def watch(limits=LIMITS):
    return ConditionWatch(limits)


# ---------------------------------------------------------------- 과대 외력

def test_over_force_uses_raw_magnitude():
    w = watch()
    assert w.on_sample(sample(fz=-29.0)) == []
    found = w.on_sample(sample(fz=-31.0))
    assert [c.code for c in found] == [OVER_FORCE]
    assert found[0].motion_id == 4 and found[0].position == (0.4, 0.0, Z0)
    assert '31.0 N > 30.0 N' in found[0].detail


def test_over_force_is_reported_once_until_it_clears():
    w = watch()
    assert len(w.on_sample(sample(fz=-40.0))) == 1
    assert w.on_sample(sample(fz=-40.0)) == []          # 같은 조건을 되풀이해 올리지 않는다
    assert OVER_FORCE in w.active
    assert w.on_sample(sample(fz=-10.0)) == []          # 해소
    assert OVER_FORCE not in w.active
    assert len(w.on_sample(sample(fz=-40.0))) == 1      # 다시 걸리면 다시 올린다


def test_over_force_in_every_operation_without_tare():
    for operation in (OP_NONE, 1, 2, OP_SLIDE, 4):
        assert [c.code for c in watch().on_sample(sample(fz=-40.0, operation=operation))] == [OVER_FORCE]


def test_confirm_n_requires_consecutive_samples():
    w = watch(SafetyLimits(30.0, 5 * MM, 200, 500, confirm_n=3, startup_grace_s=0.0,
                        drop_limit_margin_m=4 * MM))
    assert w.on_sample(sample(fz=-40.0)) == [] and w.on_sample(sample(fz=-40.0)) == []
    assert [c.code for c in w.on_sample(sample(fz=-40.0))] == [OVER_FORCE]
    # 한 샘플만 튀면 확정되지 않는다
    w2 = watch(SafetyLimits(30.0, 5 * MM, 200, 500, confirm_n=3, startup_grace_s=0.0,
                        drop_limit_margin_m=4 * MM))
    for fz in (-40.0, -40.0, -10.0, -40.0, -40.0):
        assert w2.on_sample(sample(fz=fz)) == []


def test_invalid_sample_is_not_judged():
    assert watch().on_sample(sample(fz=-99.0, valid=False)) == []


# ---------------------------------------------------------------- 하강 제한

def test_drop_limit_measured_from_first_slide_sample():
    w = watch()
    w.on_sample(sample(z=Z0, operation=OP_SLIDE))                       # 기준 z
    assert w.on_sample(sample(z=Z0 - 8.9 * MM, operation=OP_SLIDE)) == []
    found = w.on_sample(sample(z=Z0 - 9.1 * MM, operation=OP_SLIDE))
    assert [c.code for c in found] == [DROP_LIMIT]
    assert '9.1 mm > 9.0 mm' in found[0].detail and 'SLIDE 첫 샘플' in found[0].detail


def test_second_stage_does_not_latch_between_the_two_limits():
    """1차(5 mm)와 2차(9 mm) 사이는 2차가 걸지 않는다 (계약 7.2, 결정 2).

    이 구간은 robot_manager 가 SLIDE 를 실패로 끝내는 구간이다. 여기서 2차가 같이 걸면
    1차가 정상 동작했는데도 래치가 남아 다음 작업 시작이 막힌다(#53).
    """
    w = watch()
    w.on_sample(sample(z=Z0, operation=OP_SLIDE))
    for drop_mm in (5.0, 5.1, 6.0, 7.0, 8.0, 8.9, 9.0):
        assert w.on_sample(sample(z=Z0 - drop_mm * MM, operation=OP_SLIDE)) == [], drop_mm
        assert DROP_LIMIT not in w.active, drop_mm


def test_second_stage_catches_what_the_first_stage_did_not():
    """1차가 막지 못하고 9 mm 를 넘으면 2차가 잡는다."""
    w = watch()
    w.on_sample(sample(z=Z0, operation=OP_SLIDE))
    found = w.on_sample(sample(z=Z0 - 9.01 * MM, operation=OP_SLIDE))
    assert [c.code for c in found] == [DROP_LIMIT]


@pytest.mark.parametrize('drop_m, tripped', [
    (FIRST_STAGE_M, False),            # 정확히 1차 한계: 1차도 2차도 걸지 않는다
    (SECOND_STAGE_M, False),           # 정확히 2차 한계: 걸지 않는다 (경계는 초과다)
    (SECOND_STAGE_M + 1e-6, True),     # 한 눈금만 넘으면 걸린다
])
def test_drop_limit_boundary_is_exceeded_not_reached(drop_m, tripped):
    w = watch()
    w.on_sample(sample(z=Z0, operation=OP_SLIDE))
    found = w.on_sample(sample(z=Z0 - drop_m, operation=OP_SLIDE))
    assert bool(found) is tripped


def test_margin_survives_setconfig_overwriting_drop_limit():
    """SetConfig(P03)가 두 노드의 drop_limit_m 을 같은 값으로 덮어도 여유는 남는다.

    drop_limit_margin_m 은 계약 이름이 아니고 ScanConfig 에도 없어 전파 대상이 아니다.
    """
    w = watch()
    w.on_sample(sample(z=Z0, operation=OP_SLIDE))
    # scan_manager 가 두 노드에 drop_limit_m = 3 mm 를 보냈다고 하자
    w.set_limits(SafetyLimits(30.0, 3 * MM, 200, 500, 1, 0.0, drop_limit_margin_m=4 * MM))
    assert w.limits.effective_drop_limit_m == pytest.approx(7 * MM)
    assert w.on_sample(sample(z=Z0 - 6.9 * MM, operation=OP_SLIDE)) == []
    assert [c.code for c in w.on_sample(sample(z=Z0 - 7.1 * MM, operation=OP_SLIDE))] == [DROP_LIMIT]


def test_margin_must_be_positive():
    """0 을 허용하면 '여유를 뒀다'고 적힌 설정이 조용히 1차와 같아진다."""
    for bad in (0.0, -1 * MM):
        with pytest.raises(ValueError, match='drop_limit_margin_m'):
            SafetyLimits(30.0, 5 * MM, 200, 500, 1, 0.0, drop_limit_margin_m=bad)


def test_drop_limit_is_not_watched_outside_slide():
    w = watch()
    for operation in (OP_NONE, 1, 2, 4):
        w.on_sample(sample(z=Z0, operation=operation))
        assert w.on_sample(sample(z=Z0 - 50 * MM, operation=operation)) == []


def test_reference_z_resets_between_slides():
    w = watch()
    w.on_sample(sample(z=Z0, operation=OP_SLIDE))
    w.on_sample(sample(z=Z0 - 4.0 * MM, operation=OP_SLIDE))
    w.on_sample(sample(z=Z0 - 4.0 * MM, operation=1))                   # 방향 전환(OP_MOVE_TO)
    w.on_sample(sample(z=Z0 - 4.0 * MM, operation=OP_SLIDE))            # 새 기준 z
    assert w.on_sample(sample(z=Z0 - 12.0 * MM, operation=OP_SLIDE)) == []   # 새 기준에서 8 mm
    assert [c.code for c in w.on_sample(sample(z=Z0 - 13.2 * MM, operation=OP_SLIDE))] == [DROP_LIMIT]


def test_rising_z_is_not_a_drop():
    w = watch()
    w.on_sample(sample(z=Z0))
    assert w.on_sample(sample(z=Z0 + 50 * MM)) == []


def test_both_conditions_in_one_sample():
    w = watch()
    w.on_sample(sample(z=Z0))
    found = w.on_sample(sample(fz=-40.0, z=Z0 - 10 * MM))
    assert [c.code for c in found] == [OVER_FORCE, DROP_LIMIT]


def test_limits_reject_bad_values():
    M = 4 * MM
    for args in ((0.0, 5 * MM, 200, 500, 1, 0.0, M), (30.0, 0.0, 200, 500, 1, 0.0, M),
                 (30.0, 5 * MM, 0, 500, 1, 0.0, M), (30.0, 5 * MM, 200, 0, 1, 0.0, M),
                 (30.0, 5 * MM, 200, 500, 0, 0.0, M), (30.0, 5 * MM, 200, 500, 1, -1.0, M),
                 (30.0, 5 * MM, 200, 500, 1, 0.0, 0.0)):
        with pytest.raises(ValueError):
            SafetyLimits(*args)


def test_set_limits_keeps_reference_z():
    w = watch()
    w.on_sample(sample(z=Z0, operation=OP_SLIDE))
    w.set_limits(SafetyLimits(30.0, 3 * MM, 200, 500, 1, 0.0, 4 * MM))       # SetConfig 로 더 엄하게
    # 2차의 실제 한계는 3 + 4 = 7 mm 다 (여유는 전파 대상이 아니라 그대로 남는다)
    assert [c.code for c in w.on_sample(sample(z=Z0 - 7.5 * MM, operation=OP_SLIDE))] == [DROP_LIMIT]


# ---------------------------------------------------------------- 최신성

def test_freshness_not_watched_before_first_message():
    # 기동 직후. 아직 한 번도 못 받았으면 감시하지 않는다(그러지 않으면 뜨자마자 래치가 걸린다)
    assert watch().check_freshness(now_s=100.0, last_sample_s=None, last_status_s=None, uptime_s=99.0) == []


def test_sample_and_status_timeouts():
    w = watch()
    assert w.check_freshness(10.0, last_sample_s=9.9, last_status_s=9.9, uptime_s=99.0) == []
    found = w.check_freshness(10.0, last_sample_s=9.7, last_status_s=9.9, uptime_s=99.0)
    assert [c.code for c in found] == [SAMPLE_STALE] and '300 ms 동안 수신 없음' in found[0].detail
    assert w.check_freshness(10.0, 9.7, 9.9, uptime_s=99.0) == []                      # 되풀이하지 않는다
    assert [c.code for c in w.check_freshness(10.0, 9.7, 9.4, uptime_s=99.0)] == [ROBOT_STATUS_LOST]
    assert w.check_freshness(10.0, 10.0, 10.0, uptime_s=99.0) == []                    # 다시 들어오면 해소
    assert w.active == {}


# real.yaml 의 값 (계약 v0.1.16 결정 3, #130). 여기서 고정해 두면 yaml 을 되돌릴 때 시험이 알려 준다
REAL_SAMPLE_STALE_MS = 500


def real_freshness_watch():
    return watch(SafetyLimits(30.0, 5 * MM, REAL_SAMPLE_STALE_MS, 500, 1, 0.0,
                              drop_limit_margin_m=4 * MM))


@pytest.mark.parametrize('gap_ms, stale', [
    (499, False),
    (500, False),      # 경계는 **초과**다. 정확히 한계면 걸리지 않는다
    (501, True),
])
def test_sample_stale_boundary_at_500ms(gap_ms, stale):
    w = real_freshness_watch()
    found = w.check_freshness(10.0, 10.0 - gap_ms / 1000, 10.0, uptime_s=99.0)
    assert bool(found) is stale
    assert (SAMPLE_STALE in w.active) is stale


def test_recorded_gaps_at_500ms():
    """#130 에 기록된 공백 14개 중 500 ms 에서 걸리는 것은 687 하나뿐이다.

    300 ms 에서는 14개 전부 걸렸고, 그 때문에 goal 의 약 40 %가 SAMPLE_STALE 로 멈췄다.
    687 이 남는다는 사실이 "500 도 완전하지 않다"는 근거다 — 그래도 700 으로 올리지는 않는다.
    """
    gaps_ms = [316, 338, 344, 347, 347, 349, 352, 353, 357, 358, 360, 365, 464, 687]
    caught = []
    for gap in gaps_ms:
        w = real_freshness_watch()
        if w.check_freshness(10.0, 10.0 - gap / 1000, 10.0, uptime_s=99.0):
            caught.append(gap)
    assert caught == [687]
    # 옛 값 300 에서는 전부 걸렸다
    old_caught = []
    for gap in gaps_ms:
        w = watch(SafetyLimits(30.0, 5 * MM, 300, 500, 1, 0.0, drop_limit_margin_m=4 * MM))
        if w.check_freshness(10.0, 10.0 - gap / 1000, 10.0, uptime_s=99.0):
            old_caught.append(gap)
    assert old_caught == gaps_ms


def test_startup_grace_skips_freshness_watch():
    """기동 직후에는 노드들이 순차로 준비되어 샘플 주기가 불안정하다. 그 공백으로 래치를 걸지 않는다."""
    w = watch(SafetyLimits(30.0, 5 * MM, 200, 500, 1, startup_grace_s=3.0,
                           drop_limit_margin_m=4 * MM))
    assert w.check_freshness(10.0, last_sample_s=9.0, last_status_s=9.0, uptime_s=1.0) == []
    assert w.active == {}
    # 유예가 지나면 감시한다
    found = w.check_freshness(10.0, last_sample_s=9.0, last_status_s=9.0, uptime_s=3.1)
    assert sorted(c.code for c in found) == [ROBOT_STATUS_LOST, SAMPLE_STALE]


def test_startup_grace_does_not_delay_force_or_drop():
    """과대 외력 · 하강 제한은 기동과 무관한 실제 위험이라 유예하지 않는다."""
    w = watch(SafetyLimits(30.0, 5 * MM, 200, 500, 1, startup_grace_s=3.0,
                           drop_limit_margin_m=4 * MM))
    assert [c.code for c in w.on_sample(sample(fz=-40.0))] == [OVER_FORCE]


# ---------------------------------------------------------------- 정지 요청

def tracker(confirm_timeout_s=0.6, retry_period_s=1.0):
    return StopTracker(confirm_timeout_s, retry_period_s)


def test_stop_request_accept_confirm():
    s = tracker()
    assert s.phase is StopPhase.NONE and not s.required
    s.request(now_s=0.0)
    assert s.phase is StopPhase.REQUESTED and s.required and not s.confirmed
    s.on_response(True)
    assert s.phase is StopPhase.ACCEPTED and not s.confirmed            # 접수 ≠ 정지 완료
    s.on_status(connected=True, moving=True)
    assert not s.confirmed                                              # 아직 움직인다
    s.on_status(connected=True, moving=False)
    assert s.confirmed


def test_disconnected_robot_never_confirms():
    s = tracker()
    s.request(0.0)
    s.on_response(True)
    s.on_status(connected=False, moving=False)                          # 연결이 끊기면 판단할 수 없다
    assert not s.confirmed


def test_rejected_stop():
    s = tracker()
    s.request(0.0)
    s.on_response(False, 'ROBOT_DISCONNECTED')
    assert s.phase is StopPhase.REJECTED and s.required and not s.confirmed


def test_unconfirmed_after_timeout_then_slow_retry():
    s = tracker(confirm_timeout_s=0.6, retry_period_s=1.0)
    s.request(0.0)
    s.on_response(True)
    assert not s.due_for_retry(0.5) and s.phase is StopPhase.ACCEPTED
    assert not s.due_for_retry(0.7)                                     # 제한 시간은 넘겼지만 재시도 주기 전
    assert s.phase is StopPhase.UNCONFIRMED                             # 상태는 바로 올라간다
    assert s.due_for_retry(1.2)
    s.request(1.2)
    assert s.requested_s == 0.0                                         # 제한 시간은 첫 요청부터 잰다
    assert not s.due_for_retry(1.5) and s.due_for_retry(2.3)


def test_confirmed_stop_ignores_late_response_and_retry():
    s = tracker()
    s.request(0.0)
    s.on_status(True, False)
    assert s.confirmed
    s.on_response(False, '늦게 온 거절')
    assert s.confirmed and not s.due_for_retry(99.0)


def test_tracker_rejects_bad_values():
    for args in ((0.0, 1.0), (0.6, 0.0)):
        with pytest.raises(ValueError):
            StopTracker(*args)


# ---------------------------------------------------------------- 래치 · level

def state(limits=LIMITS):
    return SafetyState(limits, tracker())


def test_level_and_latch():
    st = state()
    assert st.level() is Level.OK and not st.latched
    found = st.watch.on_sample(sample(fz=-40.0))
    st.note(found[0])
    assert st.level() is Level.STOP and st.cause.code == OVER_FORCE
    # 조건이 사라져도 래치는 풀리지 않는다 (계약 3.7)
    st.watch.on_sample(sample(fz=0.0))
    assert st.watch.active == {} and st.latched and st.level() is Level.STOP


def test_latch_keeps_the_first_cause():
    st = state()
    st.note(Condition(OVER_FORCE, '첫 원인'))
    st.note(Condition(DROP_LIMIT, '나중 원인'))
    assert st.cause.code == OVER_FORCE


def test_reset_refuses_while_condition_is_true():
    st = state()
    st.note(st.watch.on_sample(sample(fz=-40.0))[0])
    st.stop.request(0.0)
    ok, detail = st.reset()
    assert not ok and OVER_FORCE in detail and st.latched
    st.watch.on_sample(sample(fz=0.0))                                  # 해소
    ok, detail = st.reset()
    assert ok and not st.latched and st.cause is None
    assert st.stop.phase is StopPhase.NONE                              # 정지 요청 상태도 같이 지운다


def test_reset_is_idempotent_without_latch():
    assert state().reset() == (True, '')


def test_freshness_stops_only_while_moving():
    st = state()
    st.moving = False
    found = st.watch.check_freshness(10.0, last_sample_s=9.0, last_status_s=10.0, uptime_s=99.0)
    assert [c.code for c in found] == [SAMPLE_STALE]
    assert not found[0].stops and st.stopping_conditions() == []
    assert st.level() is Level.WARN                                     # 서 있으면 경고만
    st.moving = True
    assert [c.code for c in st.stopping_conditions()] == [SAMPLE_STALE]
    assert st.level() is Level.STOP


def test_over_force_always_stops_even_when_not_moving():
    st = state()
    st.moving = False
    st.watch.on_sample(sample(fz=-40.0))
    assert [c.code for c in st.stopping_conditions()] == [OVER_FORCE]
    assert st.level() is Level.STOP


# ---------------------------------------------------------------- 이슈 #53

def test_issue_53_first_stage_window_is_free_of_the_second_latch():
    """#53 결정(계약 7.2, v0.1.17): 2차는 여유만큼 뒤에 있어 1차의 동작 구간을 덮지 않는다.

    옛 규칙("값도 기준도 같게")에서는 DROP_LIMIT 마다 2차 래치가 같이 걸려, 1차가 정상 동작해
    SLIDE 를 끝냈을 뿐인데 래치가 남아 다음 작업 시작이 막혔다. 여유가 그 구간을 비운다.
    """
    w = watch()
    w.on_sample(sample(z=Z0))
    # 1차가 멈추는 구간(5 mm 초과 ~ 9 mm). 2차는 조용하다
    assert w.on_sample(sample(z=Z0 - 5.1 * MM)) == []
    assert w.on_sample(sample(z=Z0 - 8.9 * MM)) == []
    assert w.active == {}
    # 1차가 제때 멈춰 하강이 멎으면 2차는 끝까지 걸리지 않는다
    assert w.on_sample(sample(z=Z0 - 8.9 * MM)) == []
    assert w.active == {}


def test_issue_53_second_stage_still_latches_when_the_first_fails():
    """여유를 둔다고 2차가 사라지는 것은 아니다. 1차가 막지 못하면 여전히 정지 + 래치다."""
    state = SafetyState(LIMITS, StopTracker(0.6, 2.0))
    state.moving = True
    state.watch.on_sample(sample(z=Z0))
    found = state.watch.on_sample(sample(z=Z0 - 9.5 * MM))
    assert [c.code for c in found] == [DROP_LIMIT]
    state.note(found[0])
    assert state.latched and state.level() is Level.STOP


def test_module_does_not_import_rclpy():
    import ast
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / 'safety_monitor' / 'safety_core.py'
    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
        names = [a.name for a in node.names] if isinstance(node, ast.Import) else (
            [node.module or ''] if isinstance(node, ast.ImportFrom) else [])
        assert not any(n.split('.')[0] in ('rclpy', 'contact_scan_interfaces') for n in names)
