"""propagation.py: 전파 계획 · 부분 실패 요약 · 쌍 검사 · applied 역매핑 (ROS 없이 전수).

수치는 테스트용 임의값이다. 이름은 계약(ros-interfaces.md 2.4 · 6.4절)의 이름이다.
"""

import itertools

import pytest
from scan_manager import propagation as P
from scan_manager.result_store.records import CONFIG_FIELDS

ALL = {
    'contact_threshold_n': 4.0,
    'edge_drop_m': 0.0006,
    'debounce_n': 5,
    'over_force_n': 12.0,
    'target_force_n': 2.5,
    'drop_limit_m': 0.004,
}
MOTION = {
    'descend_speed_mps': 0.004, 'slide_speed_mps': 0.009, 'max_descend_m': 0.07,
    'max_slide_m': 0.07, 'motion_timeout_s': 25.0, 'lift_height_m': 0.04,
}


def names_of(plans):
    return {plan.node: list(plan.names) for plan in plans}


# ---- 계획 ----

def test_전파_대상과_이름이_계약과_같다():
    plans = P.plan(ALL)
    assert names_of(plans) == {
        'safety_monitor': ['over_force_n', 'drop_limit_m'],
        'contact_detector': [
            'contact_threshold_n', 'edge_drop_m', 'debounce_n', 'over_force_n'],
        'robot_manager': ['slide_target_force_n', 'drop_limit_m'],
    }


def test_감시_노드부터_보낸다():
    """부분 실패에도 safety_monitor 가 요청한 값에 가 있게 한다 (계약 7.2)."""
    assert [plan.node for plan in P.plan(ALL)] == [
        'safety_monitor', 'contact_detector', 'robot_manager']


def test_target_force_n_은_slide_target_force_n_으로_간다():
    (plan,) = P.plan({'target_force_n': 7.0})
    assert plan.node == 'robot_manager'
    assert [(i.config_name, i.param_name, i.value) for i in plan.items] == [
        ('target_force_n', 'slide_target_force_n', 7.0)]


def test_debounce_n_만_정수로_보낸다():
    items = {i.param_name: i.integer for plan in P.plan(ALL) for i in plan.items}
    assert items['debounce_n'] is True
    assert set(v for k, v in items.items() if k != 'debounce_n') == {False}


def test_모션_6개는_전파하지_않는다():
    assert P.plan(MOTION) == ()


def test_주지_않은_항목은_보내지_않는다():
    assert names_of(P.plan({'over_force_n': 9.0})) == {
        'safety_monitor': ['over_force_n'], 'contact_detector': ['over_force_n']}


def test_None_은_주지_않은_것으로_본다():
    assert P.plan({'over_force_n': None, 'debounce_n': None}) == ()


def test_빈_요청이면_계획이_없다():
    assert P.plan({}) == ()


@pytest.mark.parametrize('chosen', [
    combo
    for size in range(1, len(ALL) + 1)
    for combo in itertools.combinations(sorted(ALL), size)
])
def test_모든_조합에서_보낸_이름이_계약_표와_맞는다(chosen):
    values = {name: ALL[name] for name in chosen}
    plans = P.plan(values)
    sent = {(plan.node, item.config_name) for plan in plans for item in plan.items}
    expected = {
        (node, name)
        for node, items in P.TARGETS for name, _param in items if name in values}
    assert sent == expected
    # 보내는 값은 요청값 그대로다
    for plan in plans:
        for item in plan.items:
            assert item.value == values[item.config_name]


def test_전파_대상_6개가_ScanConfig_의_나머지다():
    motion = set(MOTION)
    assert set(P.PEER_CONFIG_NAMES) | motion == {name for name, _flag in CONFIG_FIELDS}
    assert not set(P.PEER_CONFIG_NAMES) & motion


# ---- 결과 요약 ----

def ok(node):
    return P.NodeResult(node, True)


def bad(node, detail='범위 밖'):
    return P.NodeResult(node, False, detail)


def test_전부_성공하면_success():
    plans = P.plan(ALL)
    outcome = P.summarize(plans, {plan.node: ok(plan.node) for plan in plans}, ('max_slide_m',))
    assert outcome.success and outcome.failed == ()
    assert '자기 적용: max_slide_m' in outcome.detail
    assert outcome.detail.count(': 적용') == 3


def test_한_노드가_거절하면_실패하고_사유가_남는다():
    plans = P.plan(ALL)
    outcome = P.summarize(plans, {
        'safety_monitor': ok('safety_monitor'),
        'contact_detector': bad('contact_detector', 'debounce_n 가 범위 밖이다'),
        'robot_manager': ok('robot_manager'),
    })
    assert not outcome.success
    assert outcome.failed == ('contact_detector',)
    assert 'debounce_n 가 범위 밖이다' in outcome.detail
    assert 'safety_monitor(over_force_n, drop_limit_m): 적용' in outcome.detail


def test_결과가_없는_노드도_실패다():
    plans = P.plan({'over_force_n': 9.0})
    outcome = P.summarize(plans, {'safety_monitor': ok('safety_monitor')})
    assert not outcome.success and outcome.failed == ('contact_detector',)
    assert '결과 없음' in outcome.detail


def test_바꿀_것이_없으면_성공이다():
    outcome = P.summarize((), {}, ())
    assert outcome.success and '바꿀 항목이 없다' in outcome.detail


@pytest.mark.parametrize('failed', [
    combo
    for size in range(0, 4)
    for combo in itertools.combinations(
        ('safety_monitor', 'contact_detector', 'robot_manager'), size)
])
def test_부분_실패의_모든_조합(failed):
    plans = P.plan(ALL)
    results = {
        plan.node: (bad(plan.node) if plan.node in failed else ok(plan.node))
        for plan in plans}
    outcome = P.summarize(plans, results)
    assert outcome.success is (not failed)
    assert set(outcome.failed) == set(failed)
    for node in failed:
        assert f'{node}(' in outcome.detail


# ---- 되읽기 → applied ----

MATCHED = {
    'safety_monitor': {'over_force_n': 12.0, 'drop_limit_m': 0.004},
    'contact_detector': {
        'contact_threshold_n': 4.0, 'edge_drop_m': 0.0006, 'debounce_n': 5, 'over_force_n': 12.0},
    'robot_manager': {'slide_target_force_n': 2.5, 'drop_limit_m': 0.004},
}


def test_읽은_값이_그대로_applied_가_된다():
    assert P.applied_from_readback(MATCHED) == ALL


def test_아무것도_못_읽으면_전부_모름():
    assert P.applied_from_readback({}) == {name: None for name in ALL}


def test_한_칸만_못_읽으면_그_칸만_모름():
    readback = {node: dict(values) for node, values in MATCHED.items()}
    del readback['contact_detector']['edge_drop_m']
    applied = P.applied_from_readback(readback)
    assert applied['edge_drop_m'] is None
    assert applied['contact_threshold_n'] == 4.0


@pytest.mark.parametrize('name, node, other', [
    ('over_force_n', 'safety_monitor', 'contact_detector'),
    ('drop_limit_m', 'safety_monitor', 'robot_manager'),
])
def test_쌍이_어긋나면_대표값이_없다(name, node, other):
    readback = {n: dict(v) for n, v in MATCHED.items()}
    readback[other][name] = MATCHED[other][name] + 1.0
    applied = P.applied_from_readback(readback)
    assert applied[name] is None, '어긋난 쌍에 한쪽 값을 대표로 싣지 않는다'
    problems = P.pair_mismatches(readback)
    assert len(problems) == 1 and problems[0].startswith(name)
    assert node in problems[0] and other in problems[0]


def test_쌍의_한쪽을_못_읽으면_어긋남이_아니다():
    """다르다는 것을 본 적이 없다. 모른다고 START 를 막지 않는다."""
    readback = {n: dict(v) for n, v in MATCHED.items()}
    del readback['contact_detector']['over_force_n']
    assert P.pair_mismatches(readback) == ()
    assert P.applied_from_readback(readback)['over_force_n'] is None


def test_맞으면_어긋남이_없다():
    assert P.pair_mismatches(MATCHED) == ()
    assert P.mismatch_detail(()) is None


def test_어긋남_설명에_이름과_값이_들어간다():
    readback = {n: dict(v) for n, v in MATCHED.items()}
    readback['contact_detector']['over_force_n'] = 30.0
    detail = P.mismatch_detail(P.pair_mismatches(readback))
    assert 'over_force_n' in detail and '30.0' in detail and '12.0' in detail
    assert '7.2' in detail


def test_못_읽은_칸을_이름으로_알려_준다():
    readback = {n: dict(v) for n, v in MATCHED.items()}
    del readback['robot_manager']['drop_limit_m']
    del readback['safety_monitor']
    assert P.unread_names(readback) == (
        'safety_monitor.over_force_n', 'safety_monitor.drop_limit_m',
        'robot_manager.drop_limit_m')
    assert P.unread_names(MATCHED) == ()


def test_읽을_이름이_보낼_이름과_같다():
    for node, items in P.TARGETS:
        assert P.read_names(node) == tuple(param for _name, param in items)
    assert P.read_names('없는노드') == ()
