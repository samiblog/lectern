"""규칙 시험: 화면이 없는 JS 모듈(lineops·tabledata)과 자료 모음을 Node 로, JS 의 형 점검(tsc), 모듈 구조"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TYPESCRIPT = 'typescript@7.0.2'
# raw() 를 쓰는 곳 (D89): 이미 안전한 HTML 이라고 약속한 곳이다. DOMPurify 를 거친 것(charts·doc·help·parts),
# highlight.js 의 결과(codeview), 앱이 만든 단축키 표시(help), 앱이 그린 SVG(parts). 더할 때는 그 값이 정말 안전한지 본다
RAW_USES = {'slidegallery': 1, 'charts': 1, 'codeview': 1, 'doc': 1, 'help': 2, 'parts': 3, 'slides': 1}
# esc() 를 바로 쓰는 곳: 화면이 아니라 글을 만든다 — highlight.js 가 없을 때의 코드(codeview), 설명서의 Markdown(help),
# html 로 전환이 파일로 쓰는 발표 html(impressexport — D129)
ESC_USES = {'codeview', 'help', 'impressexport'}
# 이미 있는 import 순환. 풀면 여기서 지운다 — 새로 생기거나 커지면 test_no_new_import_cycle 이 실패한다 (D88)
KNOWN_CYCLES = [
    {'basket', 'codeview', 'csvview', 'doc', 'docmenu', 'doctabs', 'editor', 'htmldoc', 'lineedit', 'nav', 'newdoc', },
    {'gather', 'tabs'},
]


@pytest.mark.skipif(shutil.which('node') is None, reason='Node 가 없음 — 같은 표 점검은 tools/ui_edges.py 의 structure·data 가 돌린다')
def test_rules():
    r = subprocess.run(['node', str(ROOT / 'tools' / 'rules_check.mjs')], capture_output=True, text=True, encoding='utf-8', cwd=ROOT)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.skipif(shutil.which('npx') is None, reason='Node 가 없음 — 형 점검은 개발할 때만 쓴다')
def test_types():
    # 형 파일은 tools/types/lectern.d.ts, 설정은 tsconfig.json. 처음 한 번만 npx 가 typescript 를 받는다
    r = subprocess.run([shutil.which('npx'), '-y', '-p', TYPESCRIPT, 'tsc', '-p', 'tsconfig.json', '--pretty', 'false'],
                       capture_output=True, text=True, encoding='utf-8', cwd=ROOT)
    if r.returncode and 'error TS' not in r.stdout:
        pytest.skip(f'tsc 를 받거나 돌리지 못함: {r.stderr[:200]}')
    assert r.returncode == 0, r.stdout


def test_every_corpus_file_says_what_it_should_read_as():
    corpus = ROOT / 'tests' / 'corpus'
    tables = [p for p in corpus.iterdir() if p.suffix.lower() in ('.csv', '.tsv')]
    assert tables, '자료 모음이 비었습니다'
    for p in tables:
        assert p.with_suffix('.expect.json').exists(), f'{p.name} 의 .expect.json 이 없습니다'


def import_cycles() -> list[set[str]]:
    graph = {}
    for p in (ROOT / 'web' / 'js').glob('*.js'):
        text = p.read_text(encoding='utf-8')
        graph[p.stem] = re.findall(r"\bfrom\s+'\./([\w-]+)\.js'", text) + re.findall(r"^\s*import\s+'\./([\w-]+)\.js'", text, re.M)

    def reach(start: str) -> set[str]:
        seen: set[str] = set()
        todo = [start]
        while todo:
            for m in graph.get(todo.pop(), ()):
                if m not in seen:
                    seen.add(m)
                    todo.append(m)
        return seen

    reachable = {m: reach(m) for m in graph}
    groups = {frozenset(w for w in reachable[m] if m in reachable[w]) for m in graph}
    return [set(g) for g in groups if g]


def test_no_new_import_cycle():
    found = sorted(sorted(g) for g in import_cycles())
    known = sorted(sorted(g) for g in KNOWN_CYCLES)
    assert found == known, f'import 순환이 달라졌습니다 — 새 순환이면 풀고, 기존 순환을 풀었으면 KNOWN_CYCLES 를 줄입니다: {found}'


def code_of(path: Path) -> str:
    return '\n'.join(line for line in path.read_text(encoding='utf-8').splitlines() if not line.lstrip().startswith(('//', '*', '/*')))


def test_html_goes_through_html_js():
    # 값이 든 HTML 을 바로 넣으면 이스케이프를 빠뜨릴 수 있다. 비우기와 값 없는 글 상수만 둔다
    direct = re.compile(r"\.innerHTML\s*\+?=(?!=)(?!\s*'[^'$]*';)|\.outerHTML\s*=(?!=)|\.insertAdjacentHTML\(")
    modules = {p.stem: code_of(p) for p in (ROOT / 'web' / 'js').glob('*.js') if p.stem != 'html'}
    bad = {name: direct.findall(code) for name, code in modules.items() if direct.search(code)}
    assert not bad, f'html.js 의 setHtml·addHtml 을 씁니다: {bad}'
    raws = {name: n for name, code in modules.items() if (n := len(re.findall(r'\braw\(', code)))}
    assert raws == RAW_USES, 'raw() 가 달라졌습니다 — 그 값이 정말 안전한지 보고 RAW_USES 를 고칩니다'
    assert {name for name, code in modules.items() if re.search(r'\besc\(', code)} == ESC_USES


def test_every_js_module_is_listed():
    # 모듈 표는 손으로 쓰므로 빠지거나 남은 행을 여기서 잡는다
    listed = {m for line in (ROOT / 'docs' / 'MODULES.md').read_text(encoding='utf-8').splitlines() if line.startswith('|')
              for m in re.findall(r'([a-z0-9]+)\.js', line.split('|')[1])}
    files = {p.stem for p in (ROOT / 'web' / 'js').glob('*.js')}
    assert files - listed == set(), f'docs/MODULES.md 에 없는 모듈: {sorted(files - listed)}'
    assert listed - files == set(), f'docs/MODULES.md 에 남은 모듈: {sorted(listed - files)}'
