"""Lectern 의 Word 양식 18가지 (D147) — 생성 스크립트와 파일이 같은지, 지면 틀과 짝인지, 양식마다 자리 표시가 남지 않고 값·박스글·결재란이
들어가는지, 이름표 언어, 차례 쪽이 있으면 문서의 [목차] 를 빼는지. Word 없이 (그림은 그리지 못한 길로)."""
import importlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / 'skills' / 'lectern-to-docx' / 'scripts'
TEMPLATES = ROOT / 'skills' / 'lectern-to-docx' / 'templates'
INDEX = json.loads((TEMPLATES / 'index.json').read_text(encoding='utf-8'))


def builder(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    mod = importlib.import_module('build_docx')
    monkeypatch.setattr(mod.figure_png, 'draw', lambda *a, **k: False)
    monkeypatch.setattr(mod, 'math_png', lambda *a, **k: False)
    return mod


def texts(xml):
    return ''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', xml))


def test_templates_match_the_generator(tmp_path):
    # 양식은 tools/make_docx_templates.py 가 짓는다 — 고쳤으면 다시 돌려 둔다
    sys.path.insert(0, str(ROOT / 'tools'))
    try:
        gen = importlib.import_module('make_docx_templates')
        made = gen.build_all(tmp_path)
    finally:
        sys.path.pop(0)
    assert json.loads((tmp_path / 'index.json').read_text(encoding='utf-8')) == INDEX == made
    for t in INDEX:
        with zipfile.ZipFile(tmp_path / f"{t['id']}.dotx") as a, zipfile.ZipFile(TEMPLATES / f"{t['id']}.dotx") as b:
            assert sorted(a.namelist()) == sorted(b.namelist()), t['id']
            for n in a.namelist():
                assert a.read(n) == b.read(n), f"{t['id']} {n} — python tools/make_docx_templates.py 로 다시 만든다"


def test_one_template_per_layout():
    ids = {t['id'] for t in INDEX}
    layouts = {p.stem for p in (ROOT / 'web' / 'layouts').glob('*.html')}
    assert ids == layouts and len(ids) == 18
    for t in INDEX:
        assert t['name'] and t['name_en'] and t['group'] and t['description'] and t['description_en'], t['id']


FIELDS = {'title': '구리 공급망 점검', 'subtitle': '비축을 늘린다', 'author': '[김연구, 이분석]', 'org': '예제연구원', 'dept': '구매팀', 'number': '보고서 14',
          'series': '자원 브리프', 'client': '예제전선', 'affiliation': '예제대학교', 'keywords': '구리, 재고', 'short_title': '구리', 'version': '1.2',
          'company': '시험금속', 'ticker': '000000', 'sector': '비철금속', 'kicker': '원자재', 'book': '구리 이야기', 'chapter': '제3장', '결재': '[담당, 팀장, 본부장]',
          '수신': '수신자 참조', '발신': '예제연구원장', '기안자': '박담당', '검토자': '이검토', '결재권자': '김결재', '시행': '정책-1', '주소': '세종시',
          '전화': '044-0', '전자우편': 'a@b.kr', '보도일시': '11. 16. 조간', '배포일시': '11. 15. 10:00', '담당자': '박담당', '연락처': '044-0',
          '시간': '14:00', '장소': '회의실', '참석자': '김, 이', '투자의견': '매수', '목표가': '520,000원', '현재가': '431,500원', '상승여력': '20.5%'}
SLOTS = {'요약': '요약의 글', '결론': '결론의 글', '핵심': '핵심의 글', '초록': '초록의 글', '부제': '부제의 글', '핵심 수치': '핵심 수치의 글', '면책': '면책의 글'}


@pytest.mark.parametrize('t', INDEX, ids=[t['id'] for t in INDEX])
def test_each_template_fills(t, tmp_path, monkeypatch):
    b = builder(monkeypatch)
    fm = '\n'.join(f'{k}: {FIELDS[k]}' for k in t['fields'] if k in FIELDS)
    boxes = ''.join(f'<!-- box: {s} -->\n{SLOTS[s]}\n<!-- /box -->\n\n' for s in t['slots'])
    md = tmp_path / 'doc.md'
    md.write_text(f'---\n{fm}\ndate: 2026-11-15\n---\n\n# 구리 공급망 점검\n\n{boxes}[목차]\n\n## 1. 배경\n\n본문의 글[^1].\n\n표 1. 값\n\n| 가 | 나 |\n|---|---:|\n| 1 | 2 |\n\n[^1]: 각주.\n',
                  encoding='utf-8')
    out = tmp_path / 'doc.docx'
    b.build(md, out, t['id'])
    with zipfile.ZipFile(out) as z:
        parts = {n: z.read(n).decode('utf-8') for n in z.namelist() if n.endswith('.xml')}
    doc = parts['word/document.xml']
    every = ''.join(texts(x) for n, x in parts.items() if re.match(r'word/(document|header\d*|footer\d*)\.xml', n))
    assert '{{' not in every and '}}' not in every, t['id']
    assert '본문의 글' in texts(doc) and 'SEQ 표' in doc and '<w:footnoteReference' in doc
    for s in t['slots']:
        assert texts(doc).count(SLOTS[s]) == 1, (t['id'], s)   # 박스글은 자리로 — 본문에 또 남지 않는다
    for k in ('org', 'company', 'number', 'client'):
        if k in t['fields']:
            assert FIELDS[k] in every, (t['id'], k)
    if '결재' in t['fields']:
        assert all(r in texts(doc) for r in ('담당', '팀장', '본부장'))
    if '{{toc}}' in B_plain(TEMPLATES / f"{t['id']}.dotx"):
        assert doc.count(' TOC \\o') == 1, t['id']   # 양식의 차례 쪽만 — 문서의 [목차] 는 뺀다
    assert 'template.main+xml' not in parts['[Content_Types].xml']


def B_plain(path):
    with zipfile.ZipFile(path) as z:
        return re.sub(r'<[^>]+>', '', z.read('word/document.xml').decode('utf-8'))


def test_labels_follow_the_document_language(tmp_path, monkeypatch):
    b = builder(monkeypatch)
    for lang, want, not_want in (('ko', ('요   약', '차   례', '2026년 11월 15일'), ('Summary', 'Contents')),
                                 ('en', ('Summary', 'Contents', 'November 15, 2026'), ('요   약', '차   례'))):
        md = tmp_path / f'{lang}.md'
        md.write_text(f'---\nlang: {lang}\ndate: 2026-11-15\norg: ACME\n---\n\n# Title\n\n<!-- box: 요약 -->\nshort\n<!-- /box -->\n\n## One\n\nText.\n', encoding='utf-8')
        out = tmp_path / f'{lang}.docx'
        b.build(md, out, 'research-report')
        doc = texts(zipfile.ZipFile(out).read('word/document.xml').decode('utf-8'))
        assert all(w in doc for w in want) and not any(w in doc for w in not_want), (lang, doc[:300])


def test_empty_values_drop_their_lines(tmp_path, monkeypatch):
    # 맨 앞 설정이 비면 그 값만 쓴 줄과 {{if:}} 줄(표 안이면 그 행)이 빠진다 — '연구진:' 같은 이름표만 남지 않게
    b = builder(monkeypatch)
    md = tmp_path / 'a.md'
    md.write_text('# 제목만 있는 문서\n\n## 하나\n\n글.\n', encoding='utf-8')
    for tid in ('research-report', 'minutes', 'equity-research', 'one-page'):
        out = tmp_path / f'{tid}.docx'
        b.build(md, out, tid)
        doc = zipfile.ZipFile(out).read('word/document.xml').decode('utf-8')
        t = texts(doc)
        assert '{{' not in t and '연구진' not in t and '목표가' not in t and '장소' not in t, (tid, t[:200])
        assert '제목만 있는 문서' in t


def test_template_names_resolve(monkeypatch):
    b = builder(monkeypatch)
    assert b.resolve_template('research-report') == TEMPLATES / 'research-report.dotx'
    assert b.resolve_template('연구보고서') == TEMPLATES / 'research-report.dotx'   # 지면 틀과 같은 이름
    assert b.resolve_template('Research report') == TEMPLATES / 'research-report.dotx'
    assert b.resolve_template('없는 양식') is None


def test_two_column_templates_balance_and_short_tables_stay_whole(tmp_path, monkeypatch):
    # Word 로 연 실제 시험에서: 짧은 논문의 본문이 왼쪽 단에만 차고(문서 끝 구역은 단을 고르게 나누지 않는다), 첫 쪽에 쪽 번호가 없고,
    # 3행 표가 두 단에 갈라졌다. 본문 뒤의 이어지는 구역 나눔(2단), 첫 구역의 바닥글, 짧은 표의 '다음 단락과 함께'
    b = builder(monkeypatch)
    rows = '\n'.join(f'| {i} | {i} |' for i in range(30))
    md = tmp_path / 'a.md'
    md.write_text(f'# 논문\n\n## 1. 서론\n\n글.\n\n| 가 | 나 |\n|---|---:|\n| 1 | 2 |\n| 3 | 4 |\n\n## 2. 긴 표\n\n| 다 | 라 |\n|---|---:|\n{rows}\n', encoding='utf-8')
    for tid in ('paper-2col', 'magazine', 'newsletter'):
        out = tmp_path / f'{tid}.docx'
        b.build(md, out, tid)
        doc = zipfile.ZipFile(out).read('word/document.xml').decode('utf-8')
        sects = re.findall(r'<w:sectPr\b.*?</w:sectPr>', doc, re.S)
        assert len(sects) == 3 and 'w:num="2"' in sects[1] and 'w:num="2"' not in sects[2], tid   # 제목 부분 · 2단 본문 · 빈 끝 구역
        assert all('<w:footerReference' in s for s in sects), tid
        assert doc.index('글.') < doc.index(sects[1]), tid   # 본문은 2단 구역 안
        short, long_ = [t for t in re.findall(r'<w:tbl>.*?</w:tbl>', doc, re.S) if 'LecternTable' in t][:2]   # 본문의 표 (뉴스레터 머리의 표는 빼고)
        assert short.count('<w:keepNext/>') == 4 and long_.count('<w:keepNext/>') == 2, tid   # 짧은 표(3행)는 마지막 행 말고 두 행, 긴 표는 머리행만 — 행마다 두 칸
        assert f'<w:tblW w:w="{b.text_width_of(sects[1])}"' in short and b.text_width_of(sects[1]) < b.text_width_of(sects[2]) // 2 + 1, tid   # 표·그림 폭은 본문 구역의 한 단 폭


BULLET_DOC = """# 글머리 점검

<!-- box: 요약 -->
- 불릿 상자 항목
<!-- /box -->

## 1. 절 제목

문단 본문.

- 불릿 하나
  - 불릿 하위

1. 번호 하나
   1. 번호 하위
2. 번호 둘

- [ ] 할일 안 함
- [x] 할일 끝남

> [!NOTE]
> 문단 강조글.

표 1. 문단 캡션

| 가 | 나 |
|---|---:|
| 1 | 2 |
"""


def numbered_paras(docx):
    """문단마다 (글, 번호 매기기 종류 — 'bullet'·'decimal'…·None) — 직접 단 번호와 스타일에서 물려받은 번호 모두"""
    with zipfile.ZipFile(docx) as z:
        doc, styles = z.read('word/document.xml').decode('utf-8'), z.read('word/styles.xml').decode('utf-8')
        numbering = z.read('word/numbering.xml').decode('utf-8') if 'word/numbering.xml' in z.namelist() else ''
    absn = {m[1]: {int(l[1]): re.search(r'<w:numFmt w:val="([^"]+)"', l[0])[1] for l in re.finditer(r'<w:lvl [^>]*w:ilvl="(\d+)".*?</w:lvl>', m[0], re.S)}
            for m in re.finditer(r'<w:abstractNum [^>]*w:abstractNumId="(\d+)".*?</w:abstractNum>', numbering, re.S)}
    nums = {m[1]: absn.get(m[2], {}) for m in re.finditer(r'<w:num [^>]*w:numId="(\d+)"[^>]*>.*?<w:abstractNumId w:val="(\d+)"/>', numbering, re.S)}
    style_num = {m[1]: re.search(r'<w:numId w:val="(\d+)"', m[0])[1] for m in re.finditer(r'<w:style [^>]*w:styleId="([^"]+)".*?</w:style>', styles, re.S)
                 if '<w:numPr>' in m[0] and re.search(r'<w:numId w:val="(\d+)"', m[0])}
    out = []
    for m in re.finditer(r'<w:p\b[^>]*>.*?</w:p>', doc, re.S):
        p = m[0]
        nid = re.search(r'<w:numPr>.*?<w:numId w:val="(\d+)"', p, re.S)
        il = re.search(r'<w:numPr>.*?<w:ilvl w:val="(\d+)"', p, re.S)
        sty = re.search(r'<w:pStyle w:val="([^"]+)"', p)
        nid = nid[1] if nid else style_num.get(sty[1] if sty else 'Normal')
        out.append((texts(p).strip(), nums.get(nid, {}).get(int(il[1]) if il else 0) if nid and nid != '0' else None))
    return out


@pytest.mark.parametrize('tid', [None] + [t['id'] for t in INDEX], ids=['default'] + [t['id'] for t in INDEX])
def test_only_bullet_items_get_bullets(tid, tmp_path, monkeypatch):
    # 2026-11-18 사용자 요청 — 양식 18가지와 기본 양식 모두: 글머리는 글머리 목록에만, 번호 목록은 숫자, 제목·문단·캡션·강조글·할 일(체크 칸만)에는 없다
    b = builder(monkeypatch)
    md = tmp_path / 'doc.md'
    md.write_text(BULLET_DOC, encoding='utf-8')
    out = tmp_path / 'doc.docx'
    b.build(md, out, tid)
    paras = numbered_paras(out)
    for text, kind in paras:
        if text.startswith('불릿'):
            assert kind == 'bullet', (tid, text, kind)
        elif text.startswith('번호'):
            assert kind == 'decimal', (tid, text, kind)
        else:
            assert kind is None, (tid, text, kind)   # 제목·절 제목·문단·캡션·강조글·할 일(☐·☑)
    assert sum(t.startswith('불릿') for t, _ in paras) == 3 and sum(t.startswith('번호') for t, _ in paras) == 3
    assert any(t.startswith('☐ 할일') for t, _ in paras) and any(t.startswith('☑ 할일') for t, _ in paras)
    with zipfile.ZipFile(out) as z:
        styles = z.read('word/styles.xml').decode('utf-8')
    title = re.search(r'<w:style [^>]*w:styleId="Title".*?</w:style>', styles, re.S)
    assert title and '<w:keepNext/>' not in title[0], tid   # 문서 제목에 '다음 단락과 함께'를 걸지 않는다 — 단락 기호를 보이는 Word 에서 ▪ 가 붙었다
