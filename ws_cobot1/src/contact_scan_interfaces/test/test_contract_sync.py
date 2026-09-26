"""docs/contracts/ros-interfaces.md 의 타입 전문과 .msg/.srv/.action 파일이 같은지 확인한다.

주석과 공백을 뺀 나머지(필드 이름 · 타입 · 순서 · 상수값 · '---')를 비교한다.
한쪽만 고치면 실패한다. 계약 문서와 파일은 같은 PR 에서 같이 고친다.
"""

from pathlib import Path
import re

import pytest

PACKAGE_DIR = Path(__file__).resolve().parents[1]
DOCS = Path(__file__).resolve().parents[4] / 'docs'
CONTRACT = DOCS / 'contracts' / 'ros-interfaces.md'
# phase 2(용접) 타입 전문. 같은 장 번호 규칙(3 msg · 4 srv · 5 action)으로 쓴다. ReasonCode 표는 ros-interfaces.md 6.1 에만 둔다.
CONTRACTS = (CONTRACT, DOCS / 'phase2' / 'weld-ros-interfaces.md')
TYPE_CHAPTERS = (3, 4, 5)       # msg · srv · action
REASON_CODE_SECTION = '### 6.1'
FILE_NAME = re.compile(r'(\w+)\.(msg|srv|action)')


def normalize(lines):
    """주석 · 공백 · 빈 줄을 뺀 정의 줄만 남긴다."""
    out = []
    for line in lines:
        code = ' '.join(line.split('#', 1)[0].split())
        if code:
            out.append(code)
    return out


def contract_lines(path=CONTRACT):
    # 문서를 못 찾으면 skip 하지 않고 실패시킨다. 조용히 꺼지는 검사는 검사가 아니다.
    assert path.is_file(), f'계약 문서를 찾지 못했다: {path}'
    return path.read_text(encoding='utf-8').splitlines()


def contract_types():
    """{'msg/RobotSample.msg': [정의 줄, ...]} — 계약 문서들의 3~5장 코드 블록을 합친 것."""
    types = {}
    for path in CONTRACTS:
        for name, block in _types_in(path).items():
            assert name not in types, f'{name} 이 두 문서에 다 있다: {path}'
            types[name] = block
    return types


def _types_in(path):
    """한 문서의 3~5장 코드 블록."""
    types = {}
    chapter, heading, block = 0, '', None
    for line in contract_lines(path):
        if block is None:
            chapter_match = re.match(r'## (\d+)\.', line)
            if chapter_match:
                chapter = int(chapter_match.group(1))
            elif line.startswith('### '):
                heading = line
        if not line.startswith('```'):      # ```python 같은 여는 울타리도 센다
            if block is not None:
                block.append(line)
            continue
        if block is None:
            block = []
            continue
        if chapter in TYPE_CHAPTERS:
            names = FILE_NAME.findall(heading)
            if len(names) != 1:
                # 한 절에 두 타입이 있으면 블록 첫 줄 주석의 파일 이름으로 고른다.
                names = FILE_NAME.findall(block[0])
            name, ext = names[0]
            types[f'{ext}/{name}.{ext}'] = normalize(block)
        block = None
    return types


def contract_reason_codes():
    """{'BUSY': 100, ...} — 계약 6.1절 표."""
    codes = {}
    in_section = False
    for line in contract_lines():
        if line.startswith('### '):
            in_section = line.startswith(REASON_CODE_SECTION)
        row = re.match(r'\|[^|]*\|\s*(\d+)\s*\|\s*`(\w+)`\s*\|', line)
        if in_section and row:
            codes[row.group(2)] = int(row.group(1))
    return codes


def package_files():
    return sorted(
        str(p.relative_to(PACKAGE_DIR))
        for ext in ('msg', 'srv', 'action')
        for p in (PACKAGE_DIR / ext).glob(f'*.{ext}')
    )


def test_every_type_in_contract_has_a_file_and_vice_versa():
    # ReasonCode 는 계약에 코드 블록이 없고 6.1절 표만 있다.
    assert sorted([*contract_types(), 'msg/ReasonCode.msg']) == package_files()


@pytest.mark.parametrize('rel_path', sorted(contract_types()))
def test_file_matches_contract_block(rel_path):
    actual = normalize((PACKAGE_DIR / rel_path).read_text(encoding='utf-8').splitlines())
    assert actual == contract_types()[rel_path]


def test_reason_code_file_matches_contract_table():
    lines = normalize((PACKAGE_DIR / 'msg' / 'ReasonCode.msg').read_text(encoding='utf-8').splitlines())
    actual = {}
    for line in lines:
        declaration = re.fullmatch(r'uint16 (\w+)=(\d+)', line)
        assert declaration, f'ReasonCode.msg 에는 uint16 상수만 둔다: {line!r}'
        actual[declaration.group(1)] = int(declaration.group(2))
    assert actual == contract_reason_codes()
    assert len(actual) == len(lines), '상수 이름이 중복됐다'


def test_cmake_lists_every_interface_file():
    cmake = (PACKAGE_DIR / 'CMakeLists.txt').read_text(encoding='utf-8')
    assert sorted(re.findall(r'"((?:msg|srv|action)/\w+\.\w+)"', cmake)) == package_files()
