"""판정 로직 단위 테스트. ROS 없이 돈다. 기대값은 '몇 번째 샘플에서 확정되는가'를 손으로 센 것이다."""
import math
from dataclasses import replace

import pytest
from conftest import BASELINE, DT, make_samples
from contact_detector.detector_core import (
    ContactDetector,
    DetectorConfig,
    OP_DESCEND,
    OP_HOME,
    OP_MOVE_TO,
    OP_NONE,
    OP_SLIDE,
    TARE_TOO_FEW,
    TARE_NO_SAMPLE,
    TARE_TOOL_REG_SUSPECT,
    TARE_UNSTABLE,
    TareAccumulator,
    TareConfig,
    TYPE_CONTACT,
    TYPE_OVER_FORCE,
)


def run(detector, samples):
    return [d for s in samples for d in detector.update(s)]


def tared(config):
    detector = ContactDetector(config)
    detector.set_baseline(BASELINE)
    return detector


# ---------------------------------------------------------------- CONTACT

def test_contact_confirms_on_nth_consecutive_sample(config):
    # 0,1 = 무접촉 / 2,3,4 = 임계 초과 → 3 번째 초과 샘플(인덱스 4)에서 확정
    samples = make_samples([0, 0, 4, 5, 6, 7])
    detections = run(tared(config), samples)
    assert [d.type for d in detections] == [TYPE_CONTACT]
    d = detections[0]
    assert d.sample.sample_id == samples[4].sample_id          # 판정 샘플 = 확정한 샘플
    assert d.first_sample.sample_id == samples[2].sample_id    # 연속 구간의 첫 샘플
    assert d.debounce_count == 3
    assert d.force_delta_n == pytest.approx(6.0)               # 검출 하중 = 확정 샘플의 |F - F0|
    assert d.debounce_delay_s == pytest.approx(2 * DT)


def test_spike_shorter_than_debounce_is_ignored(config):
    assert run(tared(config), make_samples([0, 5, 5, 0, 5, 5, 0])) == []


def test_force_below_threshold_is_ignored(config):
    assert run(tared(config), make_samples([2.9] * 20)) == []


def test_baseline_offset_alone_is_not_contact(config):
    # 잔류 외력 |F0| = 2.5 N 이 임계에 가까워도, 기준값 대비 변화가 없으면 접촉이 아니다
    assert math.hypot(*BASELINE[1:]) == pytest.approx(2.5)
    assert run(tared(config), make_samples([0] * 20)) == []


def test_delta_is_vector_difference_not_difference_of_norms(config):
    # 옆으로 4 N 밀리면 크기 차이는 작아도 성분 차이는 4 N 이다
    samples = [replace(s, force=(BASELINE[0] + 4.0, BASELINE[1], BASELINE[2])) for s in make_samples([0] * 3)]
    detections = run(tared(config), samples)
    assert [d.type for d in detections] == [TYPE_CONTACT]
    assert detections[0].force_delta_n == pytest.approx(4.0)


def test_no_contact_before_tare(config):
    assert run(ContactDetector(config), make_samples([10] * 10)) == []


@pytest.mark.parametrize('operation', [OP_NONE, OP_MOVE_TO, OP_SLIDE, OP_HOME])
def test_contact_only_during_descend(config, operation):
    assert run(tared(config), make_samples([10] * 10, operation=operation)) == []


def test_contact_once_per_motion_then_again_for_next_motion(config):
    detector = tared(config)
    assert len(run(detector, make_samples([10] * 10, motion_id=1))) == 1
    assert len(run(detector, make_samples([10] * 10, motion_id=2, start_id=100))) == 1


def test_run_does_not_carry_over_between_motions(config):
    detector = tared(config)
    assert run(detector, make_samples([10, 10], motion_id=1)) == []
    # 새 동작의 첫 샘플이 3 번째 연속으로 세어지면 안 된다
    assert run(detector, make_samples([10], motion_id=2, start_id=100)) == []


def test_invalid_sample_neither_counts_nor_breaks_run(config):
    samples = make_samples([4, 4, 99, 4])
    samples[2] = replace(samples[2], valid=False)
    detections = run(tared(config), samples)
    assert [d.sample.sample_id for d in detections] == [samples[3].sample_id]
    assert detections[0].debounce_count == 3


# ---------------------------------------------------------------- OVER_FORCE

@pytest.mark.parametrize('operation', [OP_NONE, OP_MOVE_TO, OP_DESCEND, OP_SLIDE, OP_HOME])
def test_over_force_in_every_operation_without_tare(config, operation):
    detections = run(ContactDetector(config), make_samples([0, -40, -40], operation=operation))
    assert [d.type for d in detections] == [TYPE_OVER_FORCE]      # 구간마다 1 회
    assert detections[0].force_delta_n == pytest.approx(math.sqrt(0.1**2 + 2.0**2 + 41.5**2))   # 원시 |F|


def test_over_force_rearms_after_force_drops(config):
    detections = run(ContactDetector(config), make_samples([-40, 0, -40]))
    assert [d.type for d in detections] == [TYPE_OVER_FORCE, TYPE_OVER_FORCE]


def test_over_force_comes_before_contact_in_same_sample(config):
    detections = run(tared(config), make_samples([-40, -40, -40]))
    assert [d.type for d in detections] == [TYPE_OVER_FORCE, TYPE_CONTACT]


def test_config_rejects_nonpositive_values():
    with pytest.raises(ValueError):
        DetectorConfig(contact_threshold_n=0.0, debounce_n=3, over_force_n=30.0, over_force_debounce_n=1)
    with pytest.raises(ValueError):
        DetectorConfig(contact_threshold_n=3.0, debounce_n=0, over_force_n=30.0, over_force_debounce_n=1)


# ---------------------------------------------------------------- tare

TARE = TareConfig(min_samples=10, max_std_n=0.3, max_force_n=5.0)


def tare(samples, config=TARE):
    acc = TareAccumulator(config)
    for s in samples:
        acc.add(s)
    return acc.result()


def test_tare_mean_is_baseline():
    result = tare(make_samples([0.1, -0.1] * 10, operation=OP_NONE))
    assert result.success and result.error == ''
    assert result.baseline == pytest.approx(BASELINE)
    assert result.baseline_norm_n == pytest.approx(math.sqrt(0.1**2 + 2.0**2 + 1.5**2))
    assert result.sample_count == 20


def test_tare_failures():
    assert tare([]).error == TARE_NO_SAMPLE
    assert tare(make_samples([0] * 9)).error == TARE_TOO_FEW
    assert tare(make_samples([0, -3] * 10)).error == TARE_UNSTABLE                # 구간 중에 닿았다
    assert tare(make_samples([-5] * 20)).error == TARE_TOOL_REG_SUSPECT           # |F0| 이 허용치 초과
    assert not tare(make_samples([-5] * 20)).success


def test_tare_unstable_even_when_force_magnitude_is_constant():
    # Fz 가 -1.5 ↔ +1.5 N 로 뒤집히면 |F| 는 그대로라 크기의 표준편차는 0 이다. 그래도 불안정으로 잡아야 한다
    result = tare(make_samples([0, 3] * 10))
    assert result.std_norm_n == pytest.approx(0.0)
    assert result.std_vector_n == pytest.approx(1.5)
    assert result.error == TARE_UNSTABLE


def test_tare_ignores_invalid_samples():
    samples = make_samples([0] * 12)
    samples[0] = replace(samples[0], valid=False, force=(999.0, 999.0, 999.0))
    result = tare(samples)
    assert result.success and result.sample_count == 11
    assert result.baseline == pytest.approx(BASELINE)
