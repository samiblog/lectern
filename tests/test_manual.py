"""사용설명서 트리 (D182): web/help/manual/ 의 차례(index.json)와 문서들이 서로 맞는지.

- 차례의 파일이 모두 있고, 차례에 없는 문서가 없다. 번호가 트리를 이루고(4.1 이면 4 가 있다) 차례가 번호 차례대로다
- 문서마다 '# 제목'(차례의 제목과 같게)과 '> 요약' 한 줄. 하위 문서가 있는 장 문서에만 '<!-- 하위 문서 -->'
- 문서 사이의 링크는 차례에 있는 파일로, 예제(samples)로는 링크하지 않는다 (예제를 새로 짜는 중)
- 흐름도(mermaid)의 노드 글은 큰따옴표로 — 따옴표 없는 괄호·특수 문자가 흐름도를 깨뜨린다
- 단축키 문서에는 앱이 단축키 표를 넣는 자리 표시
- 영어판(index.en.json)이 있으면 같은 번호의 같은 트리
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote

import pytest

HELP = Path(__file__).resolve().parents[1] / 'web' / 'help' / 'manual'
LANGS = [name for name in ('index.json', 'index.en.json') if (HELP / name).exists()]
NUM = re.compile(r'^(\d+(?:\.\d+)*)-')
LINK = re.compile(r'\]\(([^)\s]+)\)')


def load(index: str) -> list[dict]:
    return json.loads((HELP / index).read_text(encoding='utf-8'))['docs']


def num_of(file: str) -> str:
    m = NUM.match(file)
    assert m, f'{file}: 이름 앞에 번호가 없다'
    return m.group(1)


def key(num: str) -> tuple[int, ...]:
    return tuple(int(x) for x in num.split('.'))


@pytest.mark.parametrize('index', LANGS)
def test_index_matches_files(index: str) -> None:
    docs = load(index)
    files = [d['file'] for d in docs]
    assert len(files) == len(set(files)), '차례에 같은 파일이 두 번'
    en = index == 'index.en.json'
    for f in files:
        assert f.endswith('.en.md') == en, f'{f}: 영어판 차례는 .en.md, 한국어는 .md'
        assert (HELP / f).is_file(), f'{f}: 차례에 있는데 파일이 없다'
    on_disk = {p.name for p in HELP.glob('*.md') if p.name.endswith('.en.md') == en}
    assert on_disk == set(files), f'차례에 없는 문서: {sorted(on_disk - set(files))}'
    nums = [num_of(f) for f in files]
    assert nums == sorted(nums, key=key), '차례가 번호 차례가 아니다'
    for n in nums:
        if '.' in n:
            assert n.rsplit('.', 1)[0] in nums, f'{n}: 위 문서가 없다'


@pytest.mark.parametrize('index', LANGS)
def test_each_doc_has_title_and_summary(index: str) -> None:
    for d in load(index):
        lines = [line for line in (HELP / d['file']).read_text(encoding='utf-8').split('\n') if line.strip()]
        assert lines[0] == f"# {d['title']}", f"{d['file']}: 첫 줄이 '# {d['title']}' 가 아니다 — {lines[0]!r}"
        assert lines[1].startswith('> ') and len(lines[1]) > 4, f"{d['file']}: 제목 다음 줄은 '> 요약' 한 줄"
        assert len(lines) <= 160, f"{d['file']}: {len(lines)}줄 — 나눌 때가 됐다"


@pytest.mark.parametrize('index', LANGS)
def test_children_placeholder_only_on_chapters(index: str) -> None:
    docs = load(index)
    nums = [num_of(d['file']) for d in docs]
    for d, n in zip(docs, nums):
        has_kids = any(m.rsplit('.', 1)[0] == n for m in nums if '.' in m)
        text = (HELP / d['file']).read_text(encoding='utf-8')
        assert ('<!-- 하위 문서 -->' in text) == has_kids, f"{d['file']}: 하위 문서 자리 표시는 하위 문서가 있는 장 문서에만"   # i18n-ok


def slug(text: str) -> str:
    """web/js/markdown.js 의 slugify 와 같게 — 글자·결합 표시·숫자·이음표(_)·빈칸·- 만 남기고 빈칸은 -"""
    text = re.sub(r'[*`]', '', text).strip().lower()
    text = ''.join(ch for ch in text if ch in ' -' or unicodedata.category(ch)[0] in 'LMN' or unicodedata.category(ch) == 'Pc')
    return text.replace(' ', '-')


def anchors(path: Path) -> set[str]:
    body = re.sub(r'```.*?```', '', path.read_text(encoding='utf-8'), flags=re.S)
    seen: dict[str, int] = {}
    out = set()
    for h in re.findall(r'^#{1,6}\s+(.+)$', body, re.M):
        s = slug(h)
        if s in seen:   # markdown-it-anchor 는 같은 슬러그에 -1, -2
            seen[s] += 1
            s = f'{s}-{seen[s]}'
        else:
            seen[s] = 0
        out.add(s)
    return out


@pytest.mark.parametrize('index', LANGS)
def test_links_stay_inside_the_manual(index: str) -> None:
    files = {d['file'] for d in load(index)}
    bad = []
    for f in files:
        text = re.sub(r'`[^`\n]*`', '', re.sub(r'```.*?```', '', (HELP / f).read_text(encoding='utf-8'), flags=re.S))
        for href in LINK.findall(text):
            if href.startswith(('http://', 'https://')):
                continue
            target, _, anchor = unquote(href).partition('#')
            target = target or f
            if 'samples' in target:
                bad.append(f'{f}: 예제로 가는 링크 {href}')
            elif target.endswith('.md') and target not in files:
                bad.append(f'{f}: 없는 문서 {href}')
            elif anchor and target in files and anchor not in anchors(HELP / target):
                bad.append(f'{f}: {target} 에 없는 절 #{anchor}')
    assert not bad, '\n'.join(bad)


@pytest.mark.parametrize('index', LANGS)
def test_mermaid_labels_are_quoted(index: str) -> None:
    bad = []
    for d in load(index):
        text = (HELP / d['file']).read_text(encoding='utf-8')
        for block in re.findall(r'```mermaid\n(.*?)```', text, re.S):
            for line in block.split('\n'):
                if re.search(r'\w[\[{](?!["\[{])', line) or re.search(r'-->\|(?!")', line):
                    bad.append(f"{d['file']}: {line.strip()}")
    assert not bad, '노드 글은 큰따옴표로:\n' + '\n'.join(bad)


@pytest.mark.parametrize('index', LANGS)
def test_shortcut_table_placeholder(index: str) -> None:
    docs = [d for d in load(index) if num_of(d['file']) == '10.1']
    assert docs and '<!-- 단축키 표 -->' in (HELP / docs[0]['file']).read_text(encoding='utf-8')   # i18n-ok


def test_english_docs_have_no_korean() -> None:
    """영어판에 한글이 남지 않는다 — 앱이 바꾸는 자리 표시와 코드 칸(파일 이름·문법 예) 밖에서"""
    if 'index.en.json' not in LANGS:
        pytest.skip('영어판 차례가 아직 없다')
    bad = []
    for d in load('index.en.json'):
        text = (HELP / d['file']).read_text(encoding='utf-8')
        text = text.replace('<!-- 하위 문서 -->', '').replace('<!-- 단축키 표 -->', '')   # i18n-ok
        text = re.sub(r'`[^`\n]*`', '', re.sub(r'```.*?```', '', text, flags=re.S))
        for line in text.split('\n'):
            if re.search(r'[가-힣]', line.replace('한국어', '')):
                bad.append(f"{d['file']}: {line.strip()[:90]}")
    assert not bad, '\n'.join(bad)


def test_english_tree_matches_korean() -> None:
    if 'index.en.json' not in LANGS:
        pytest.skip('영어판 차례가 아직 없다')
    ko = [num_of(d['file']) for d in load('index.json')]
    en = [num_of(d['file']) for d in load('index.en.json')]
    assert ko == en, '영어판과 한국어판의 트리가 다르다'
