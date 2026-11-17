"""글쓰기 스타일 넷 (D161 — web/help/writing-styles.json, *.md·*.en.md): 목록과 파일이 맞는지, 공통 절이 리서치 글쓰기와 같은지,
Claude Code 출력 스타일로 쓸 수 있는 머리인지, 새 스타일 만들기 안내가 스타일 파일 이름을 맞게 말하는지"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from lectern import aistatus
from lectern.config import AI_STYLES, value_ok
from lectern.paths import web_dir

ROOT = Path(__file__).resolve().parent.parent
HELP = web_dir() / 'help'
META = json.loads((HELP / 'writing-styles.json').read_text(encoding='utf-8'))
sys.path.insert(0, str(ROOT / 'tools'))
import sync_writing_styles as sync  # noqa: E402


def head(text: str) -> dict[str, str]:
    m = re.match(r'---\n(.*?)\n---\n', text, re.S)
    assert m, '맨 앞 설정이 없다'
    return dict(line.split(': ', 1) for line in m.group(1).splitlines())


def test_list_matches_files_and_settings():
    ids = [s['id'] for s in META['styles']]
    assert tuple(ids) == AI_STYLES
    assert ids[0] == 'research' and META['styles'][0]['file'] == 'research-writing'   # 예전 판에서 설치한 스타일과 이어진다
    for s in META['styles']:
        for lang in ('ko', 'en'):
            assert s['use'][lang] and len(s['changes'][lang]) >= 3, (s['id'], lang)
        for suffix in ('', '.en'):
            assert (HELP / f"{s['file']}{suffix}.md").is_file()
    assert value_ok('ai_style', 'plain') and value_ok('ai_style', 'mine:weekly-brief.md')
    assert not value_ok('ai_style', 'mine:../x.md') and not value_ok('ai_style', 'mine:a\\b.md') and not value_ok('ai_style', 'other')


def test_style_heads_are_output_styles():
    names = set()
    for s in META['styles']:
        for suffix in ('', '.en'):
            text = (HELP / f"{s['file']}{suffix}.md").read_text(encoding='utf-8')
            h = head(text)
            assert set(h) == {'name', 'description'}, (s['file'], suffix, h)   # keep-coding-instructions 를 두지 않는다 — 글을 위한 스타일
            assert h['description'].endswith('(Lectern)')
            assert h['name'] not in names
            names.add(h['name'])
            assert '(공통 절' not in text and '(shared section' not in text


def test_shared_sections_are_the_same_as_research_writing():
    assert sync.main(check=True) == 0
    for suffix, heads in (('', sync.SHARED['']), ('.en', sync.SHARED['.en'])):
        src = sync.sections((HELP / f'research-writing{suffix}.md').read_text(encoding='utf-8'))
        for s in META['styles'][1:]:
            mine = sync.sections((HELP / f"{s['file']}{suffix}.md").read_text(encoding='utf-8'))
            for h in heads:
                assert mine[h] == src[h], (s['file'], suffix, h)


def test_every_style_reads_the_voice_note():
    for s in META['styles']:
        assert '~/.claude/rules/내-문체.md' in (HELP / f"{s['file']}.md").read_text(encoding='utf-8')
        assert '~/.claude/rules/my-voice.md' in (HELP / f"{s['file']}.en.md").read_text(encoding='utf-8')


def test_samples_when_present():
    """견본(tools/make_style_samples.py --apply)은 요청과 두 글의 앞부분 — 너무 길지 않게"""
    for s in META['styles']:
        sample = s.get('sample')
        if sample:
            assert sample['request'] and sample['default'] and sample['style']
            assert len(sample['default']) < 1200 and len(sample['style']) < 1200


def test_new_style_guide_names_the_files():
    for suffix in ('', '.en'):
        text = (HELP / f'new-style{suffix}.md').read_text(encoding='utf-8')
        for s in META['styles']:
            assert f"`{s['file']}{suffix}.md`" in text, (suffix, s['file'])


def test_lectern_styles_read_names():
    ko = aistatus.lectern_styles(HELP)
    en = aistatus.lectern_styles(HELP, en=True)
    assert [s['name'] for s in ko] == ['리서치 글쓰기', '업무 보고', '학술 글', '쉬운 설명']
    assert [s['name'] for s in en] == ['Research writing', 'Business report', 'Academic writing', 'Plain explanation']
    assert all(Path(s['path']).is_file() for s in ko + en)
