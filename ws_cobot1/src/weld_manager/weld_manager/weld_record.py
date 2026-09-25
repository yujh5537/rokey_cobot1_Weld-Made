"""용접 결과 원본 파일 (순수 Python, rclpy 없음). 기준: docs/phase2/weld-ros-interfaces.md 3.3 · 3.4절.

    <result_dir>/<scan_id>/weld/<weld_id>.json

- 값 규칙은 스캔 result.json 과 같다: 모르는 값은 null(파이썬 None), 0 으로 채우지 않는다(CLAUDE.md 규칙 4).
- 좌표(seam · stop_pose)는 작업대 좌표(`frame_id`, m) 다. stop_pose 는 Base 의 정지 좌표에서 base_to_fixture 를 뺀 값이다
  (평행 이동만이라 자세는 그대로).
- 쓰기는 같은 디렉터리의 임시 파일 → fsync → os.replace. 쓰는 도중에 죽어도 이전 파일이 남는다.
- 시각은 scan_manager.result_store.Stamp(정수 sec · nanosec)를 그대로 쓴다.
"""

from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import random
import re
import threading
from typing import Dict, Mapping, Optional, Tuple

from scan_manager.result_store import Stamp

from .contract_enums import LINE_COUNT
from .contract_enums import LineStatus

SCHEMA_VERSION = 1
KIND = 'weld.result'
UNITS = {'length': 'm', 'angle': 'rad', 'time': 's'}
WELD_DIR = 'weld'
# 6.2절: weld_id 는 scan_id 와 같은 형식 YYYYMMDD-HHMMSS-xxxx (벽시계)
WELD_ID_PATTERN = re.compile(r'\d{8}-\d{6}-[0-9A-Za-z]{4}')

Vec3 = Tuple[float, float, float]
Quat = Tuple[float, float, float, float]


def new_weld_id(now: datetime, rng: Optional[random.Random] = None) -> str:
    """벽시계(메인 PC 지역 시각) + 난수 4 자리. scan_manager 의 new_scan_id 와 같은 규칙이다."""
    return f'{now:%Y%m%d-%H%M%S}-{(rng or random).randrange(10_000):04d}'


@dataclass(frozen=True)
class Pose:
    position: Vec3
    orientation: Quat

    def to_dict(self):
        return {'position_m': list(self.position), 'orientation_xyzw': list(self.orientation)}


@dataclass(frozen=True)
class LineRecord:
    """WeldLine.msg 한 줄."""

    index: int
    seam: Tuple[Vec3, Vec3]                 # 작업대 좌표. 세로선은 bottom_margin 만큼 짧다
    status: LineStatus = LineStatus.NOT_ATTEMPTED
    reason_code: int = 0
    detail: str = ''
    stop_pose: Optional[Pose] = None        # FAILED · STOPPED 일 때 멈춘 자리. 모르면 None
    started_at: Optional[Stamp] = None
    finished_at: Optional[Stamp] = None

    def __post_init__(self):
        if (self.reason_code == 0) != (self.status in (
                LineStatus.DONE, LineStatus.NOT_ATTEMPTED, LineStatus.SKIPPED)):
            raise ValueError(f'L{self.index}: {self.status.name} 와 reason_code {self.reason_code} 가 어긋난다')
        if self.stop_pose is not None and self.status not in (LineStatus.FAILED, LineStatus.STOPPED):
            raise ValueError(f'L{self.index}: {self.status.name} 인데 stop_pose 가 있다')

    def to_dict(self):
        return {
            'index': self.index,
            'seam': {'start': list(self.seam[0]), 'end': list(self.seam[1])},
            'status': self.status.name,
            'reason_code': self.reason_code,
            'detail': self.detail,
            'stop_pose': None if self.stop_pose is None else self.stop_pose.to_dict(),
            'stop_pose_valid': self.stop_pose is not None,
            'started_at': None if self.started_at is None else self.started_at.to_dict(),
            'finished_at': None if self.finished_at is None else self.finished_at.to_dict(),
        }


@dataclass(frozen=True)
class WeldRecord:
    """WeldResult.msg 의 내용 = 파일 원본."""

    weld_id: str
    scan_id: str
    success: bool
    reason_code: int
    detail: str
    frame_id: str
    base_to_fixture: Vec3
    start_line: int
    end_line: int
    lines: Tuple[LineRecord, ...]
    config: Mapping[str, float]             # WeldConfig 스냅샷 (전부 적용된 값)
    started_at: Stamp
    finished_at: Stamp

    def __post_init__(self):
        if not WELD_ID_PATTERN.fullmatch(self.weld_id):
            raise ValueError(f'weld_id 형식이 아니다(YYYYMMDD-HHMMSS-xxxx): {self.weld_id!r}')
        if len(self.lines) != LINE_COUNT:
            raise ValueError(f'lines 는 {LINE_COUNT} 개여야 한다')
        if (self.reason_code == 0) != self.success:
            raise ValueError('success 와 reason_code 가 어긋난다(성공 = 0)')
        chosen = range(self.start_line, self.end_line + 1)
        all_done = all(self.lines[i].status is LineStatus.DONE for i in chosen)
        if self.success and not all_done:
            raise ValueError('success=true 인데 start_line..end_line 에 DONE 이 아닌 선이 있다')
        for line in self.lines:
            if (line.index in chosen) == (line.status is LineStatus.SKIPPED):
                raise ValueError(f'L{line.index}: 범위 {self.start_line}..{self.end_line} 와 SKIPPED 가 어긋난다')

    def to_dict(self):
        return {
            'schema_version': SCHEMA_VERSION,
            'kind': KIND,
            'units': dict(UNITS),
            'weld_id': self.weld_id,
            'scan_id': self.scan_id,
            'success': self.success,
            'reason_code': self.reason_code,
            'detail': self.detail,
            'frame_id': self.frame_id,
            'base_to_fixture': list(self.base_to_fixture),
            'start_line': self.start_line,
            'end_line': self.end_line,
            'lines': [line.to_dict() for line in self.lines],
            'config': dict(self.config),
            'started_at': self.started_at.to_dict(),
            'finished_at': self.finished_at.to_dict(),
        }


def weld_path(result_dir, scan_id: str, weld_id: str) -> Path:
    return Path(os.path.expanduser(str(result_dir))) / scan_id / WELD_DIR / f'{weld_id}.json'


def save(result_dir, record: WeldRecord) -> Path:
    """원본을 쓴다. 같은 weld_id 의 파일이 있으면 덮지 않는다(작업마다 한 번)."""
    path = weld_path(result_dir, record.scan_id, record.weld_id)
    if path.exists():
        raise FileExistsError(f'{path} 가 이미 있다')
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(path, record.to_dict())
    return path


def load_dict(path) -> Dict:
    """시험 · 조사용. NaN 등 JSON 밖의 값은 거절한다."""
    def reject(name):
        raise ValueError(f'JSON 에 {name} 이 있다')
    return json.loads(Path(path).read_text(encoding='utf-8'), parse_constant=reject)


def _atomic_write(path: Path, data: dict) -> None:
    # allow_nan=False: NaN · inf 가 남아 있으면 파일을 만들기 전에 멈춘다
    text = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
    tmp = path.with_name(f'.{path.name}.{os.getpid()}.{threading.get_ident()}.tmp')
    try:
        with open(tmp, 'w', encoding='utf-8') as file:
            file.write(text)
            file.write('\n')
            file.flush()
            os.fsync(file.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
