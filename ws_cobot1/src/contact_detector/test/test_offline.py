"""오프라인 분석기 테스트. 답을 아는 합성 CSV 를 만들어 분석 결과와 맞춘다. ROS 없이 돈다."""
import pytest
from contact_detector import offline

DT = 0.02          # 50 Hz
SPEED_MM_S = 5.0   # 하강 속도
HEADER = 't_pose_s,t_force_s,x_mm,y_mm,z_mm,fx_n,fy_n,fz_n,valid\n'


def write_descend_csv(path, tare_samples=100, ramp_n_per_sample=2.0, ramp_samples=10):
    """2 s 정지(무접촉) 뒤 등속 하강하다가 닿아서 Fz 가 샘플마다 ramp 만큼 커지는 기록."""
    rows, z = [], 200.0
    for i in range(tare_samples + 20 + ramp_samples):
        t = i * DT
        moving = i >= tare_samples
        z -= SPEED_MM_S * DT if moving else 0.0
        push = max(0, i - (tare_samples + 20) + 1) * ramp_n_per_sample
        rows.append(f'{t:.3f},{t + 0.004:.3f},400.0,0.0,{z:.4f},0.1,2.0,{-1.5 - push:.3f},1\n')
    path.write_text(HEADER + ''.join(rows), encoding='utf-8')
    return path


def test_load_converts_mm_to_m(tmp_path):
    samples = offline.load_csv(write_descend_csv(tmp_path / 'a.csv'))
    assert samples[0].position == pytest.approx((0.4, 0.0, 0.2))
    assert samples[0].force == pytest.approx((0.1, 2.0, -1.5))


def test_period_stats(tmp_path):
    stats = offline.period_stats(offline.load_csv(write_descend_csv(tmp_path / 'a.csv')))
    assert stats.mean_s == pytest.approx(DT)
    assert stats.mean_hz == pytest.approx(50.0)
    assert stats.invalid == 0


def test_invalid_rows_are_kept_but_not_used(tmp_path):
    path = write_descend_csv(tmp_path / 'a.csv')
    lines = path.read_text().splitlines(keepends=True)
    lines[5] = '0.080,0.084,0,0,0,0,0,0,0\n'            # 조회 실패 줄. 0 은 값이 아니다
    path.write_text(''.join(lines))
    samples = offline.load_csv(path)
    assert offline.period_stats(samples).invalid == 1
    head, _ = offline.split_tare(samples, tare_seconds=1.5)
    assert offline.tare_stats(head).baseline == pytest.approx((0.1, 2.0, -1.5))


def test_sweep_detect_force_delay_and_z_bias(tmp_path):
    samples = offline.load_csv(write_descend_csv(tmp_path / 'a.csv'))
    head, tail = offline.split_tare(samples, tare_seconds=1.5)
    baseline = offline.tare_stats(head).baseline
    rows = offline.sweep(tail, baseline, thresholds=[3.0], debounces=[1, 3], over_force_n=30.0)

    # 접촉 뒤 |F - F0| = 2, 4, 6, 8 ... N. 임계 3 N 을 처음 넘는 것은 4 N 샘플
    n1, n3 = rows
    assert (n1.contact_count, n3.contact_count) == (1, 1)
    assert n1.detect_force_n == pytest.approx(4.0)
    assert n1.debounce_delay_s == pytest.approx(0.0)
    assert n3.detect_force_n == pytest.approx(8.0)                     # 4, 6, 8 → 3 번째
    assert n3.debounce_delay_s == pytest.approx(2 * DT)
    assert n3.z_bias_m == pytest.approx(2 * DT * SPEED_MM_S / 1000.0)   # 디바운스 동안 더 내려간 0.2 mm
    assert n3.over_force_count == 0


def test_sweep_counts_false_contacts_in_no_contact_record(tmp_path):
    # 무접촉 기록에 3 샘플짜리 튐이 두 번 있다 → 디바운스 3 이면 거짓 접촉 2 회, 5 면 0 회
    rows = []
    for i in range(300):
        t = i * DT
        spike = -4.0 if i in (150, 151, 152, 220, 221, 222) else 0.0
        rows.append(f'{t:.3f},{t:.3f},400.0,0.0,200.0,0.1,2.0,{-1.5 + spike:.3f},1\n')
    path = tmp_path / 'idle.csv'
    path.write_text(HEADER + ''.join(rows), encoding='utf-8')
    samples = offline.load_csv(path)
    head, tail = offline.split_tare(samples, tare_seconds=1.5)
    n3, n5 = offline.sweep(tail, offline.tare_stats(head).baseline, [3.0], [3, 5], over_force_n=30.0)
    assert n3.contact_count == 2
    assert n5.contact_count == 0 and n5.detect_force_n is None


def test_report_is_markdown_table(tmp_path, capsys):
    path = write_descend_csv(tmp_path / 'a.csv')
    assert offline.main([str(path), '--tare-seconds', '1.5', '--thresholds', '3', '5',
                         '--debounce', '3', '--over-force', '30']) == 0
    out = capsys.readouterr().out
    assert '20.0 ms (50.0 Hz)' in out
    assert '| 3 | 3 | 1 |' in out and '| 5 | 3 | 1 |' in out
