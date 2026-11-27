"""Word로 저장의 목록 (D210): 글머리 글자 목록(□ ○ - · — 앱의 D192)과 목록 수준 강조가 앱 화면과 같은지."""
import importlib
import json
import re
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCX = ROOT / 'skills' / 'lectern-to-docx' / 'scripts'

DOC = """# 보고

## 수요

□ 전기차 투자로 수요 증가
○ 한 대에 83kg
  이어 쓴 줄
- 충전 설비 포함
· 협회 추정
□ 공급은 빠듯
○ 칠레 감소
① 차례에 없는 머리 글자

□ 혼자인 묶음

- 가격은 9,350달러
  - 재고 감소
    - 상하이 포함
- 4분기 범위

- 평평한 목록
- 둘째

- [ ] 할 일
  - [ ] 하위 할 일
"""


@pytest.fixture()
def mod(monkeypatch):
    monkeypatch.syspath_prepend(str(DOCX))
    m = importlib.import_module('build_docx')
    monkeypatch.setattr(m.figure_png, 'draw', lambda *a, **k: False)
    monkeypatch.setattr(m, 'math_png', lambda *a, **k: False)
    return m


def paras(tmp_path, m, text=DOC):
    md = tmp_path / 'doc.md'
    md.write_text(text, encoding='utf-8')
    out = tmp_path / 'doc.docx'
    m.build(md, out)
    with zipfile.ZipFile(out) as z:
        xml = z.read('word/document.xml').decode('utf-8')
    got = []
    for p in re.findall(r'<w:p>.*?</w:p>', xml[xml.find('<w:body>'):]):
        got.append({'text': ''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', p)), 'xml': p})
    return got


def find(got, start):
    return next(p for p in got if p['text'].startswith(start))


def js_const(path, name):
    src = (ROOT / path).read_text(encoding='utf-8')
    m = re.search(rf'const {name} = (.*?);\s*(?://.*)?$', src, re.M)
    return m[1]


def test_constants_match_the_app(mod):
    """글머리 글자·차례·좁은 글자 폭이 앱(hang.js·marklist.js)과 같다 — 한쪽만 고치면 Word 와 화면이 달라진다"""
    assert json.loads(js_const('web/js/hang.js', 'BULLETS').replace("'", '"')) == mod.MARK_BULLETS
    assert json.loads(js_const('web/js/marklist.js', 'RANKS').replace("'", '"')) == mod.MARK_RANKS
    src = (ROOT / 'web/js/hang.js').read_text(encoding='utf-8')
    body = src[src.index('const NARROW = {') + len('const NARROW = {'):]
    body = body[:body.index('};')]
    pairs = dict(re.findall(r"'(.)': ([\d.]+)", body))
    pairs.update(dict(re.findall(r"\b([A-Z]): ([\d.]+)", body)))
    assert {k: float(v) for k, v in pairs.items()} == mod.MARK_NARROW


def test_marklist_items_are_paragraphs(tmp_path, mod):
    got = paras(tmp_path, mod)
    top = find(got, '□ 전기차')
    assert '<w:numPr>' not in top['xml'], '글머리 글자 목록은 Word 의 글머리표 목록이 아니다 (글자 그대로)'
    assert '- 충전 설비' in find(got, '- 충전')['text'], "묶음 안의 '-' 줄은 Markdown 목록이 아니다"
    assert '<w:br/>' in find(got, '○ 한 대에')['xml'], '이어 쓴 줄은 그 항목 안에서 줄바꿈'
    assert not any(p['text'].startswith('□ 전기차') and '○' in p['text'] for p in got), '항목마다 단락 하나'


def test_marklist_levels_and_emphasis(tmp_path, mod):
    got = paras(tmp_path, mod)
    left = lambda p: int(re.search(r'w:left="(\d+)"', p['xml'])[1])   # noqa: E731
    top, second, third, fourth = (find(got, s) for s in ('□ 전기차', '○ 한 대에', '- 충전', '· 협회'))
    assert left(top) < left(second) < left(third) < left(fourth), '수준마다 들여 쓴다'
    assert '<w:b/>' in top['xml'] and '<w:sz w:val="22"/>' in top['xml'], '○ 가 있는 묶음의 □ 는 진하게·1.05배 (21 → 22 반 포인트)'
    assert '<w:b/>' not in second['xml'] and '<w:sz ' not in second['xml'], '○ 는 본문 그대로'
    assert '<w:sz w:val="20"/>' in third['xml'] and '<w:sz w:val="19"/>' in fourth['xml'], '셋째 .96배, 넷째 .92배'
    assert 'w:before="126"' in find(got, '□ 공급은')['xml'] and 'w:before="0"' in top['xml'], '둘째 □ 앞만 띄운다 (.6em)'
    assert left(find(got, '① 차례에')) > left(find(got, '○ 칠레')), '차례에 없는 머리 글자는 위 항목의 한 수준 아래'
    alone = find(got, '□ 혼자인')
    assert '<w:b/>' not in alone['xml'], '□ 만 있는 묶음은 그대로'
    hang = int(re.search(r'w:hanging="(\d+)"', top['xml'])[1])
    assert hang == round((0.6 + 0.28) * 210 * 1.05), '꺾인 줄은 글머리 글자 뒤에 (글자 폭의 어림값 — 화면의 종이용과 같다)'


def test_markdown_list_emphasis(tmp_path, mod):
    got = paras(tmp_path, mod)
    top, sib, second, third = (find(got, s) for s in ('가격은', '4분기', '재고 감소', '상하이'))
    assert '<w:b/>' in top['xml'] and '<w:b/>' in sib['xml'], '하위가 있는 목록의 맨 위는 하위가 없는 형제도 진하게'
    assert 'w:before="126"' in sib['xml'] and '<w:contextualSpacing w:val="0"/>' in sib['xml'], '맨 위 항목 사이를 띄운다'
    assert '<w:b/>' not in second['xml'] and '<w:sz w:val="20"/>' in third['xml']
    assert '<w:b/>' not in find(got, '평평한')['xml'], '하위가 없는 목록은 그대로'
    assert '<w:b/>' not in find(got, '☐ 할 일')['xml'], '할 일 목록은 그대로'


def test_body_size_follows_the_template(mod):
    """양식의 본문 크기를 따른다 — 기본 단락 스타일, 없으면 문서 기본값, 그것도 없으면 10pt"""
    normal = '<w:style w:type="paragraph" w:default="1" w:styleId="a"><w:rPr><w:sz w:val="24"/></w:rPr></w:style>'
    defaults = '<w:docDefaults><w:rPrDefault><w:rPr><w:sz w:val="22"/></w:rPr></w:rPrDefault></w:docDefaults>'
    assert mod.body_size_of(defaults + normal) == 24
    assert mod.body_size_of(defaults + '<w:style w:type="paragraph" w:default="1" w:styleId="a"><w:rPr/></w:style>') == 22
    assert mod.body_size_of('<w:styles/>') == 20


def test_not_a_marklist(tmp_path, mod):
    """제목(setext)·코드 블록·들여 쓴 이어 쓴 줄은 글머리 글자 목록이 아니다"""
    got = paras(tmp_path, mod, '# 문서\n\n□ 제목처럼\n---\n\n```\n□ 코드 속\n○ 둘째\n```\n\n- 목록 항목\n  □ 이어 쓴 줄\n')
    assert not any(p['text'] == '□ 코드 속' for p in got)
    assert any('□ 이어 쓴 줄' in p['text'] and '목록 항목' in p['text'] for p in got), '목록 항목에 이어 쓴 줄'
