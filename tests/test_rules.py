"""규칙 시험: 화면이 없는 JS 모듈(lineops·tabledata)과 자료 모음을 Node 로 — tools/rules_check.mjs"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(shutil.which('node') is None, reason='Node 가 없음 — 같은 표 점검은 tools/ui_edges.py 의 structure·data 가 돌린다')
def test_rules():
    r = subprocess.run(['node', str(ROOT / 'tools' / 'rules_check.mjs')], capture_output=True, text=True, encoding='utf-8', cwd=ROOT)
    assert r.returncode == 0, r.stdout + r.stderr


def test_every_corpus_file_says_what_it_should_read_as():
    corpus = ROOT / 'tests' / 'corpus'
    tables = [p for p in corpus.iterdir() if p.suffix.lower() in ('.csv', '.tsv')]
    assert tables, '자료 모음이 비었습니다'
    for p in tables:
        assert p.with_suffix('.expect.json').exists(), f'{p.name} 의 .expect.json 이 없습니다'


def test_every_js_module_is_listed():
    # 모듈 표는 손으로 쓰므로 빠지거나 남은 행을 여기서 잡는다
    listed = {m for line in (ROOT / 'docs' / 'MODULES.md').read_text(encoding='utf-8').splitlines() if line.startswith('|')
              for m in re.findall(r'([a-z0-9]+)\.js', line.split('|')[1])}
    files = {p.stem for p in (ROOT / 'web' / 'js').glob('*.js')}
    assert files - listed == set(), f'docs/MODULES.md 에 없는 모듈: {sorted(files - listed)}'
    assert listed - files == set(), f'docs/MODULES.md 에 남은 모듈: {sorted(listed - files)}'
