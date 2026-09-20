"""기록한 샘플 CSV 를 판정 로직(detector_core)에 그대로 통과시키는 오프라인 분석기. rclpy 를 import 하지 않는다.

용도 (T08 · T24, TR-01): 실기에서 기록한 힘 · 위치 열로
  - 실측 조회 주기
  - 무접촉 구간의 외력 평균 · 표준편차 (tare 구간)
  - 임계값 x 디바운스 조합마다: 확정 횟수, 첫 확정 시각, 검출 하중, 디바운스 지연, z 편향
을 계산해 마크다운 표로 출력한다. 결과는 docs/test-reports/ 에 붙인다.

    ros2 run contact_detector analyze_samples descend_01.csv \\
        --tare-seconds 1.5 --thresholds 2 3 4 5 --debounce 1 2 3 5 --over-force 30

CSV 형식 (머리줄 필수, 열 이름에 단위를 적는다):
    t_pose_s,t_force_s,x_mm,y_mm,z_mm,fx_n,fy_n,fz_n,valid
  - t_*_s: 각 조회의 응답을 받은 시각 [s]. 같은 시계면 기준점은 무엇이든 된다
  - 위치는 Base 기준 TCP. *_mm (두산 원시 단위) 또는 *_m. 읽을 때 m 로 바꾼다
  - 힘은 get_tool_force(ref=DR_BASE) 의 Fx, Fy, Fz [N]
  - valid: 1/0. 조회에 실패한 줄은 값을 0 으로 채우지 말고 valid=0 으로 남긴다
파일 앞부분 --tare-seconds 동안은 무접촉 · 정지 상태여야 한다.
"""
import argparse
import csv
import sys
from dataclasses import dataclass, replace
from typing import List, Optional, Sequence

from contact_detector.detector_core import (
    ContactDetector,
    DetectorConfig,
    norm,
    OP_DESCEND,
    Sample,
    TareAccumulator,
    TareConfig,
    TareResult,
    TYPE_CONTACT,
    TYPE_OVER_FORCE,
)

MM_PER_M = 1000.0


def _length_m(row: dict, axis: str) -> float:
    if f'{axis}_m' in row:
        return float(row[f'{axis}_m'])
    return float(row[f'{axis}_mm']) / MM_PER_M


def load_csv(path: str) -> List[Sample]:
    samples = []
    with open(path, newline='', encoding='utf-8') as f:
        for i, row in enumerate(csv.DictReader(f), start=1):
            valid = row.get('valid', '1').strip() not in ('0', '', 'false', 'False')
            if not valid:
                # 무효 줄의 수치는 믿지 않는다. 시각만 있으면 쓴다
                t = float(row.get('t_force_s') or row.get('t_pose_s') or 'nan')
                samples.append(Sample(i, t, t, (float('nan'),) * 3, (float('nan'),) * 3, valid=False))
                continue
            samples.append(Sample(
                sample_id=i,
                pose_stamp=float(row['t_pose_s']),
                force_stamp=float(row['t_force_s']),
                position=(_length_m(row, 'x'), _length_m(row, 'y'), _length_m(row, 'z')),
                force=(float(row['fx_n']), float(row['fy_n']), float(row['fz_n'])),
            ))
    return samples


@dataclass(frozen=True)
class PeriodStats:
    count: int
    invalid: int
    mean_s: float
    median_s: float
    p95_s: float
    max_s: float

    @property
    def mean_hz(self) -> float:
        return 1.0 / self.mean_s


def period_stats(samples: Sequence[Sample]) -> PeriodStats:
    stamps = [s.force_stamp for s in samples if s.valid]
    dts = sorted(b - a for a, b in zip(stamps, stamps[1:]))
    if not dts:
        raise ValueError('유효 샘플이 2 개 미만이라 주기를 계산할 수 없다')
    return PeriodStats(
        count=len(samples),
        invalid=sum(1 for s in samples if not s.valid),
        mean_s=sum(dts) / len(dts),
        median_s=dts[len(dts) // 2],
        p95_s=dts[min(len(dts) - 1, int(len(dts) * 0.95))],
        max_s=dts[-1],
    )


def split_tare(samples: Sequence[Sample], tare_seconds: float):
    """앞의 tare_seconds 구간과 나머지로 나눈다."""
    valid = [s for s in samples if s.valid]
    if not valid:
        return [], list(samples)
    t_end = valid[0].force_stamp + tare_seconds
    head = [s for s in samples if s.valid and s.force_stamp <= t_end]
    tail = [s for s in samples if not (s.valid and s.force_stamp <= t_end)]
    return head, tail


def tare_stats(head: Sequence[Sample]) -> TareResult:
    """분석용이므로 합격 판정은 하지 않는다(한계를 걸지 않는다). 값만 본다."""
    acc = TareAccumulator(TareConfig(min_samples=1, max_std_n=float('inf'), max_force_n=float('inf')))
    for s in head:
        acc.add(s)
    return acc.result()


@dataclass(frozen=True)
class SweepRow:
    threshold_n: float
    debounce_n: int
    contact_count: int                 # 무접촉 기록이면 이 값이 거짓 접촉 횟수다
    first_time_s: Optional[float]      # tare 구간 끝에서 첫 확정까지
    detect_force_n: Optional[float]    # 검출 하중 = 확정 샘플의 |F - F0|
    debounce_delay_s: Optional[float]  # 연속 구간 첫 샘플 → 확정 샘플
    z_bias_m: Optional[float]          # 첫 샘플 z - 확정 샘플 z (하강이면 양수 = 더 내려간 양)
    over_force_count: int


def sweep(tail: Sequence[Sample], baseline, thresholds: Sequence[float], debounces: Sequence[int],
          over_force_n: float) -> List[SweepRow]:
    rows = []
    t0 = next((s.force_stamp for s in tail if s.valid), None)
    for threshold in thresholds:
        for debounce in debounces:
            detector = ContactDetector(DetectorConfig(
                contact_threshold_n=threshold, debounce_n=debounce,
                over_force_n=over_force_n, over_force_debounce_n=1))
            detector.set_baseline(baseline)
            motion_id, first, contacts, overs, rearm = 1, None, 0, 0, False
            for s in tail:
                if not s.valid:
                    continue
                # 확정 뒤 외력이 임계 아래로 내려오면 motion_id 를 바꿔 다시 판정하게 한다 (거짓 접촉 횟수를 세려고)
                if rearm and detector.force_delta(s) <= threshold:
                    motion_id, rearm = motion_id + 1, False
                for d in detector.update(replace(s, operation=OP_DESCEND, motion_id=motion_id)):
                    if d.type == TYPE_OVER_FORCE:
                        overs += 1
                    elif d.type == TYPE_CONTACT:
                        contacts += 1
                        rearm = True
                        first = first or d
            rows.append(SweepRow(
                threshold, debounce, contacts,
                first.sample.force_stamp - t0 if first else None,
                first.force_delta_n if first else None,
                first.debounce_delay_s if first else None,
                first.first_sample.position[2] - first.sample.position[2] if first else None,
                overs))
    return rows


def _fmt(value, scale=1.0, digits=3):
    return '-' if value is None else f'{value * scale:.{digits}f}'


def report(path: str, samples, tare_seconds, thresholds, debounces, over_force_n) -> str:
    period = period_stats(samples)
    head, tail = split_tare(samples, tare_seconds)
    tare = tare_stats(head)
    if tare.baseline is None:
        raise ValueError(f'앞 {tare_seconds} s 구간에 유효 샘플이 없다')
    peak = max((norm(s.force) for s in samples if s.valid), default=float('nan'))
    lines = [
        f'### {path}',
        '',
        f'- 샘플 {period.count}개 (무효 {period.invalid}개)',
        f'- 조회 주기: 평균 {period.mean_s * 1000:.1f} ms ({period.mean_hz:.1f} Hz) · 중앙값 {period.median_s * 1000:.1f} ms'
        f' · 95% {period.p95_s * 1000:.1f} ms · 최대 {period.max_s * 1000:.1f} ms',
        f'- 무접촉 구간(앞 {tare_seconds} s, {tare.sample_count}개): F0 = ({tare.baseline[0]:.2f}, {tare.baseline[1]:.2f},'
        f' {tare.baseline[2]:.2f}) N · |F0| = {tare.baseline_norm_n:.2f} N · 외력 크기 표준편차 {tare.std_norm_n:.3f} N'
        f' · 기준값 대비 흔들림(RMS) {tare.std_vector_n:.3f} N',
        f'- 전체 구간 원시 외력 크기 최대: {peak:.2f} N',
        '',
        '| 임계 [N] | 디바운스 N | CONTACT 확정 수 | 첫 확정 [s] | 검출 하중 [N] | 디바운스 지연 [ms] | z 편향 [mm] | OVER_FORCE 수 |',
        '|---|---|---|---|---|---|---|---|',
    ]
    for r in sweep(tail, tare.baseline, thresholds, debounces, over_force_n):
        lines.append(
            f'| {r.threshold_n:g} | {r.debounce_n} | {r.contact_count} | {_fmt(r.first_time_s)} | {_fmt(r.detect_force_n, digits=2)}'
            f' | {_fmt(r.debounce_delay_s, 1000, 1)} | {_fmt(r.z_bias_m, MM_PER_M)} | {r.over_force_count} |')
    return '\n'.join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description='샘플 CSV 를 접촉 판정 로직에 통과시켜 임계 · 디바운스 조합을 비교한다')
    p.add_argument('csv', nargs='+')
    p.add_argument('--tare-seconds', type=float, required=True, help='파일 앞부분의 무접촉 · 정지 구간 길이 [s]')
    p.add_argument('--thresholds', type=float, nargs='+', required=True, help='비교할 접촉 임계 [N]')
    p.add_argument('--debounce', type=int, nargs='+', required=True, help='비교할 연속 횟수')
    p.add_argument('--over-force', type=float, required=True, help='과대 외력 임계 [N]')
    args = p.parse_args(argv)
    for path in args.csv:
        print(report(path, load_csv(path), args.tare_seconds, args.thresholds, args.debounce, args.over_force))
        print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
