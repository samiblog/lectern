"""도해 스타일 (D212)·색 조합 (D213) — 설정 diagram_style·diagram_colors 와 화면의 번호표(web/js/diagramstyles.js)·AI 용 안내(web/help/diagrams.md)가 서로 맞는지."""
import re
from pathlib import Path

from test_i18n import english

from lectern import config

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / 'web' / 'js' / 'diagramstyles.js').read_text(encoding='utf-8')
EN = english()


def table(name):
    """'const NAME = [' … '];' 안의 (key, 한국어 이름) — 번호 차례"""
    start = JS.index(f'const {name} = [')
    body = JS[start:JS.index('\n];', start)]
    return re.findall(r"\{ key: '([a-z]+)', name: t\('([^']+)'\)", body), body


def styles():
    return table('STYLES')[0]


def palettes():
    return table('PALETTES')[0]


def guide_rows(name):
    """안내의 번호표 두 개 — [(번호, 이름)] 를 차례대로 (모양 1~10, 그다음 색 조합 1~8)"""
    text = (ROOT / 'web' / 'help' / name).read_text(encoding='utf-8')
    return [(int(n), label.strip()) for n, label in re.findall(r'^\| (\d+) \| ([^|]+) \|', text, re.M)]


def test_counts_match_config():
    assert len(styles()) == config.DIAGRAM_STYLES == 10
    assert len(palettes()) == config.DIAGRAM_COLORS == 8


def test_setting_values():
    for key, top in (('diagram_style', config.DIAGRAM_STYLES), ('diagram_colors', config.DIAGRAM_COLORS)):
        assert config.DEFAULTS[key] == 1
        assert key in config.CLIENT_KEYS
        for ok in (1, top, top + 1, config.DIAGRAM_NUMBER_MAX):   # 기본 번호 뒤로 내 도해 스타일·내 색 조합 (D215 — 파일이 없으면 화면이 1 로)
            assert config.value_ok(key, ok)
        for bad in (0, config.DIAGRAM_NUMBER_MAX + 1, True, '3', 2.5, None):
            assert not config.value_ok(key, bad), (key, bad)


def test_numbers_never_move():
    """번호는 바꾸지 않는다 — 문서에 적힌 '%% 스타일: 3 · 색: 2' 가 다른 모양·색이 되면 안 된다. 새 것은 뒤에 붙인다"""
    assert [k for k, _ in styles()] == ['basic', 'report', 'card', 'solid', 'line', 'sketch', 'zones', 'band', 'tint', 'rule']
    assert [k for k, _ in palettes()] == ['doc', 'navy', 'gray', 'vivid', 'safe', 'warm', 'cool', 'pastel']


def test_guides_match_the_tables():
    both = styles() + palettes()
    numbered = [(i + 1, n) for i, (_, n) in enumerate(styles())] + [(i + 1, n) for i, (_, n) in enumerate(palettes())]
    assert guide_rows('diagrams.md') == numbered
    assert guide_rows('diagrams.en.md') == [(i, EN[n]) for i, n in numbered], '영어 안내의 이름은 화면(en.js)의 이름과 같게'
    assert len(both) == 18


def test_names_are_findable():
    """표시 줄의 값으로 이름도 읽힌다 ('%% style: card · colors: report navy') — 한국어·영어 이름을 붙여 쓴 꼴이 words 에 있어야 한다"""
    for name_of_table in ('STYLES', 'PALETTES'):
        rows, body = table(name_of_table)
        for key, name in rows:
            words = re.search(r"\{ key: '%s', name: t\('[^']+'\), words: \[([^\]]*)\]" % key, body).group(1)
            listed = re.findall(r"'([^']+)'", words)
            assert name.replace(' ', '') in listed, (key, name)
            assert EN[name].lower().replace(' ', '') in listed + [key], (key, EN[name])


def test_palette_colors_are_hex():
    _, body = table('PALETTES')
    for colors in re.findall(r"series: \[([^\]]*)\]", body):
        found = re.findall(r"'([^']+)'", colors)
        assert len(found) >= 5 and all(re.fullmatch(r'#[0-9a-f]{6}', c) for c in found), found


def test_writing_guide_points_to_it():
    assert 'diagrams.md' in (ROOT / 'web' / 'help' / 'writing.md').read_text(encoding='utf-8')
    assert 'diagrams.en.md' in (ROOT / 'web' / 'help' / 'writing.en.md').read_text(encoding='utf-8')
