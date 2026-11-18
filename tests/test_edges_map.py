"""가장자리 점검의 목록과 영역표 (tools/ui_edges.py) — 묶음을 만들고 등록을 잊거나, 화면 모듈을 고쳐도 그 묶음이 돌지 않는 일이 없게.
2026-11-19 조사에서 JS 모듈 23개가 영역표에 없어 `--changed` 가 기본 세 묶음만 돌렸다 (notes.js 를 고쳐도 notes 묶음이 돌지 않음)."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))

import ui_edges  # noqa: E402


def test_every_suite_file_is_listed():
    files = sorted(p.stem for p in (ROOT / 'tools' / 'edges').glob('*.py') if p.stem != 'harness')
    assert sorted(ui_edges.SUITES) == files, set(files) ^ set(ui_edges.SUITES)
    assert len(set(ui_edges.SUITES)) == len(ui_edges.SUITES), '같은 묶음이 두 번'


def test_every_web_module_has_an_area():
    missing = [p.name for p in sorted((ROOT / 'web' / 'js').glob('*.js'))
               if not any(re.fullmatch(pattern, f'web/js/{p.name}') for pattern, _ in ui_edges.AREAS)]
    assert not missing, f'tools/ui_edges.py 의 AREAS 에 더하세요 (그 모듈을 실제로 쓰는 묶음으로): {missing}'


def test_every_suite_is_reachable_from_an_area():
    names = {n for _, ns in ui_edges.AREAS for n in (ns or [])}
    unknown = sorted(names - set(ui_edges.SUITES))
    assert not unknown, f'AREAS 에 없는 묶음 이름: {unknown}'
    orphans = [s for s in ui_edges.SUITES if s not in names]
    assert not orphans, f'어떤 파일을 고쳐도 --changed 가 돌리지 않는 묶음: {orphans}'


def test_a_file_on_two_lines_gets_both():
    """처음 맞는 줄에서 멈추지 않는다 — doc.js 는 문서 그리기 줄과 표 줄에 모두 걸린다"""
    got = ui_edges.suites_for(['web/js/doc.js'])
    assert {'textbox', 'tablewidth', 'tablealign'} <= set(got), got
    assert 'notes' in ui_edges.suites_for(['web/js/notes.js'])
    assert ui_edges.suites_for(['tools/edges/fastopen.py']) == ['fastopen']
    assert set(ui_edges.suites_for(['tools/edges/harness.py'])) == set(ui_edges.SUITES)
    assert ui_edges.suites_for(['docs/HISTORY.md']) == []


def test_jobs_option():
    assert ui_edges.jobs_of(['-j', '4', '--changed']) == (4, ['--changed'])
    assert ui_edges.jobs_of(['-j3', 'docedit']) == (3, ['docedit'])
    assert ui_edges.jobs_of(['docedit']) == (1, ['docedit'])
    assert ui_edges.jobs_of(['-j', '0']) == (1, [])
