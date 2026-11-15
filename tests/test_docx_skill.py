"""lectern-to-docx 스킬 (D146) — md 문서를 Word(docx)로. Word·Edge 없이 도는 것만 (그림은 그리지 못한 길로 시험한다)."""
import importlib
import json
import re
import struct
import subprocess
import sys
import zipfile
import zlib
from pathlib import Path
from xml.dom import minidom

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCX = ROOT / 'skills' / 'lectern-to-docx' / 'scripts'
PPTX = ROOT / 'skills' / 'lectern-to-pptx' / 'scripts'

DOC = r"""---
title: 3분기 구리 구매 전략
subtitle: 4분기 초 분할 매수
author: 김연구
date: 2026-11-15
---

# 3분기 구리 구매 전략

[목차]

<!-- box: 요약 -->
**박스 1. 핵심**

- 4분기 필요량의 60%를 나누어 산다.
<!-- /box -->

## 1. 가격과 재고

가격이 올랐다[^1]. ~~지운 글~~ <mark>노랑</mark> <mark class="green">초록</mark> <span style="color:red">빨강</span>.
자세한 값은 [표 1](#표-1), 뒤의 절은 [2절](#2-구매-전략), 박스는 [박스 1](#박스-1).

수식 $\Delta P = \frac{P_1 - P_0}{P_0}$ 과 \(\alpha + \beta = 1\). 달러 $105 와 $95~$110 은 그대로.

표 1. 분기별 가격

| 지표 | 2분기 | 3분기 |
|---|---|---|
| 가격 | 11,007 | 11,690 |
| 재고 | 230 | 198 |

> [!WARNING]
> 재고가 줄면 변동이 커진다.

```vega-lite
{"mark": "bar", "data": {"values": [{"a": 1}]}, "encoding": {"y": {"field": "a", "type": "quantitative"}}}
```

그림 1. 막대

<div style="page-break-after: always;"></div>

## 2. 구매 전략

1. 하나
2. 둘

다른 목록:

1. 다시 하나

- [ ] 할 일
- [x] 한 일

[^1]: LME 월평균. 수식 $x^2$ 도.
"""


def builder(monkeypatch):
    monkeypatch.syspath_prepend(str(DOCX))
    mod = importlib.import_module('build_docx')
    monkeypatch.setattr(mod.figure_png, 'draw', lambda *a, **k: False)   # Edge 없이 — 그리지 못한 길
    monkeypatch.setattr(mod, 'math_png', lambda *a, **k: False)
    return mod


def parts(path):
    with zipfile.ZipFile(path) as z:
        return {n: z.read(n).decode('utf-8') for n in z.namelist() if n.endswith(('.xml', '.rels'))}


@pytest.fixture()
def built(tmp_path, monkeypatch):
    md = tmp_path / 'doc.md'
    md.write_text(DOC, encoding='utf-8')
    out = tmp_path / 'doc.docx'
    report = builder(monkeypatch).build(md, out)
    return out, report, parts(out)


def test_package_is_well_formed(built):
    out, report, xml = built
    assert report['docx'] == str(out)
    for name, text in xml.items():
        minidom.parseString(text.encode('utf-8'))   # 잘 짜인 xml
    rels = xml['word/_rels/document.xml.rels']
    ids = set(re.findall(r'Id="([^"]+)"', rels))
    doc = xml['word/document.xml']
    assert set(re.findall(r'r:(?:id|embed)="([^"]+)"', doc)) <= ids
    for target in re.findall(r'Target="([^"]+)"(?! TargetMode)', rels):
        assert f'word/{target}' in xml or target.startswith('media/'), target
    styles = set(re.findall(r'w:styleId="([^"]+)"', xml['word/styles.xml']))
    assert set(re.findall(r'<w:(?:pStyle|rStyle|tblStyle) w:val="([^"]+)"', doc)) <= styles
    assert 'document.main+xml' in xml['[Content_Types].xml']


def test_headings_title_and_links(built):
    doc = built[2]['word/document.xml']
    assert '<w:pStyle w:val="Title"/>' in doc and '<w:pStyle w:val="Heading1"/>' in doc   # '# 제목' 하나는 Title, '##' 는 제목 1
    assert doc.count('<w:pStyle w:val="Heading1"/>') == 2 and '<w:pStyle w:val="Heading2"/>' not in doc
    assert '4분기 초 분할 매수' in doc and '김연구 · 2026-11-15' in doc   # 맨 앞 설정의 부제·작성자·날짜
    # 앞쪽 문단이 뒤쪽 절을 가리켜도 책갈피로 간다
    m = re.search(r'<w:hyperlink w:anchor="(lec_h_\d+)">(?:(?!</w:hyperlink>).)*2절', doc)
    assert m and f'w:name="{m[1]}"' in doc
    assert '<w:hyperlink w:anchor="lec_tbl_1">' in doc and 'w:name="lec_tbl_1"' in doc
    assert '<w:hyperlink w:anchor="lec_box_1">' in doc and 'w:name="lec_box_1"' in doc


def test_caption_is_a_seq_field(built):
    doc = built[2]['word/document.xml']
    assert ' SEQ 표 \\* ARABIC ' in doc and ' SEQ 그림 \\* ARABIC ' in doc
    assert '<w:pStyle w:val="Caption"/>' in doc


def test_footnotes_marks_and_colors(built):
    xml = built[2]
    assert '<w:footnoteReference w:id="1"/>' in xml['word/document.xml']
    assert 'LME 월평균' in xml['word/footnotes.xml'] and 'x' in xml['word/footnotes.xml']
    doc = xml['word/document.xml']
    assert '<w:strike/>' in doc and 'w:fill="FFF1A6"' in doc and 'w:fill="CDEFD0"' in doc and '<w:color w:val="C62828"/>' in doc
    assert '&lt;mark' not in doc and '&lt;span' not in doc and '~~' not in doc and '[^1]' not in doc


def test_math_becomes_text_and_dollars_stay(built):
    doc = built[2]['word/document.xml']
    text = ''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', doc))
    assert 'Δ' in text and 'α' in text and 'β' in text and '\\' not in text and '₩' not in text
    assert 'Cambria Math' in doc
    assert '$105' in text and '$95~$110' in text


def test_tables_boxes_breaks_toc_lists(built):
    xml = built[2]
    doc = xml['word/document.xml']
    assert '<w:tblHeader/>' in doc and '<w:cantSplit/>' in doc
    assert '<w:jc w:val="right"/>' in doc   # 숫자 열
    assert 'w:color="9B6304"' in doc   # 경고 강조글의 왼쪽 줄
    assert '<w:br w:type="page"/>' in doc
    assert ' TOC \\o &quot;1-3&quot; \\h \\z \\u ' in doc and '<w:updateFields w:val="true"/>' in xml['word/settings.xml']
    assert '☐ 할 일' in doc and '☑ 한 일' in doc
    nums = re.findall(r'<w:numId w:val="(\d+)"/>', doc)
    assert len({n for n in nums if int(n) >= 100}) == 2   # 번호 목록마다 1부터


def test_chart_that_cannot_be_drawn_is_kept_as_source(built):
    out, report, xml = built
    assert '"mark": "bar"' in xml['word/document.xml'].replace('&quot;', '"')
    assert any('vega-lite' in n for n in report['notes'])


def test_template_lends_styles_and_page(tmp_path, monkeypatch):
    # 회사 양식(.dotx): 스타일 id 가 영어가 아니어도 이름으로 찾고, '이름.styles.json' 이 다른 이름에 잇는다. 쪽 설정·머리글은 양식의 것
    styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
              '<w:style w:type="paragraph" w:default="1" w:styleId="a"><w:name w:val="Normal"/></w:style>'
              '<w:style w:type="paragraph" w:styleId="1"><w:name w:val="heading 1"/><w:rPr><w:color w:val="C00000"/></w:rPr></w:style>'
              '<w:style w:type="paragraph" w:styleId="ab"><w:name w:val="회사본문"/></w:style></w:styles>')
    W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    tpl = tmp_path / '회사.dotx'
    with zipfile.ZipFile(tpl, 'w') as z:
        z.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml"/>'
                   '<Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/></Types>')
        z.writestr('_rels/.rels', '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
                   '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>')
        z.writestr('docProps/app.xml', '<?xml version="1.0" encoding="UTF-8"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Template>회사.dotx</Template></Properties>')
        z.writestr('word/_rels/document.xml.rels', '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
                   '<Relationship Id="rId9" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/></Relationships>')
        z.writestr('word/styles.xml', styles)
        z.writestr('word/header1.xml', f'<?xml version="1.0" encoding="UTF-8"?><w:hdr {W}><w:p><w:r><w:t>회사 양식</w:t></w:r></w:p></w:hdr>')
        z.writestr('word/document.xml', f'<?xml version="1.0" encoding="UTF-8"?><w:document {W}><w:body><w:p/><w:sectPr><w:headerReference w:type="default" r:id="rId9"/>'
                   '<w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr></w:body></w:document>')
    (tmp_path / '회사.styles.json').write_text(json.dumps({'Normal': '회사본문'}, ensure_ascii=False), encoding='utf-8')
    md = tmp_path / 'doc.md'
    md.write_text(DOC, encoding='utf-8')
    out = tmp_path / 'doc.docx'
    builder(monkeypatch).build(md, out, tpl)
    xml = parts(out)
    doc = xml['word/document.xml']
    assert '<w:pStyle w:val="1"/>' in doc and '<w:pStyle w:val="Heading1"/>' not in doc   # 양식의 제목 1
    assert '<w:pStyle w:val="ab"/>' in doc   # styles.json — 본문은 '회사본문'
    assert '<w:pgSz w:w="12240" w:h="15840"/>' in doc and 'r:id="rId9"' in doc and 'word/header1.xml' in xml   # 양식의 쪽 설정·머리글
    assert 'template.main+xml' not in xml['[Content_Types].xml'] and 'document.main+xml' in xml['[Content_Types].xml']
    assert 'w:styleId="Caption"' in xml['word/styles.xml']   # 양식에 없는 스타일은 Lectern 의 정의를 더한다
    assert xml['word/styles.xml'].count('w:styleId="1"') == 1
    assert 'docProps/app.xml' in xml   # 양식의 관계가 가리키는 파일은 빠지지 않는다
    for text in xml.values():
        minidom.parseString(text.encode('utf-8'))


def test_cli_reports_json(tmp_path):
    md = tmp_path / 'a.md'
    md.write_text('# 제목\n\n본문 한 줄.\n', encoding='utf-8')
    r = subprocess.run([sys.executable, '-I', str(DOCX / 'build_docx.py'), str(md), '--out', str(tmp_path / 'a.docx')],
                       capture_output=True, text=True, encoding='utf-8', timeout=120)
    assert r.returncode == 0, r.stderr
    report = json.loads(r.stdout.strip().split('\n')[-1])
    assert report == {'docx': str(tmp_path / 'a.docx'), 'figures': 0, 'notes': []}


SCENARIO = r"""---
기관: 한국자원연구원
연구진: [김연구, "이분석"]
부제: 비축과 분할 구매
날짜: 2026-11-10
---

# 공급망 연구 <b>굵게</b>와 <em>기울임</em>

<!-- box: 요약 -->
- 비축을 늘린다.
- 셋으로 나눈다.
<!-- /box -->

<!-- box -->
한 줄뿐인 박스글.
<!-- /box -->

같은 각주를 두 번[^a] 부른다[^a].

<details><summary>펼치기</summary>

숨은 글.

</details>

모형은 $P_t = P_{t-1}(1 + g_t)$ 이다.

[^a]: 두 번 불린 각주.
"""


def test_scenario_findings(tmp_path, monkeypatch):
    # 시나리오 시험에서 찾은 것: 한국어 맨 앞 설정·목록 값, 같은 각주 두 번(Word 가 '손상된 파일'로 거절), html 굵게·기울임·접는 상자,
    # 이름 있는 박스글의 제목, 한 줄뿐인 박스글, 아래첨자 안의 연산자
    md = tmp_path / 'doc.md'
    md.write_text(SCENARIO, encoding='utf-8')
    out = tmp_path / 'doc.docx'
    builder(monkeypatch).build(md, out)
    xml = parts(out)
    doc = xml['word/document.xml']
    text = ''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', doc))
    assert '비축과 분할 구매' in text and '김연구, 이분석 · 2026-11-10' in text   # 부제·연구진·날짜 (한국어 키, 목록 값)
    assert doc.count('<w:footnoteReference') == 1 and ' NOTEREF _RefLecFn1 \\f \\h ' in doc and 'w:name="_RefLecFn1"' in doc
    assert '<b>' not in text and '<em>' not in text and '<w:b/><w:bCs/><w:t xml:space="preserve">굵게' in doc.replace('</w:rPr>', '')
    assert '펼치기' in text and '숨은 글' in text and 'details' not in text and 'summary' not in text
    assert '요약' in text   # 이름 있는 박스글 — 이름이 제목 줄
    one = re.search(r'<w:tbl>(?:(?!</w:tbl>).)*한 줄뿐인 박스글(?:(?!</w:tbl>).)*</w:tbl>', doc)
    assert one and one[0].count('<w:tr>') == 1   # 한 줄뿐이면 제목 띠 없이 본문 한 칸
    assert 'Pt = Pt−1(1 + gt)' in text


def test_second_scenario_findings(tmp_path, monkeypatch):
    # 두 번째 시나리오: 각주 안의 링크(관계는 footnotes.xml 쪽 — 아니면 Word 가 손상된 파일로 거절), 3. 으로 시작하는 목록,
    # 윗 항목이 바뀌면 안쪽 번호는 새로, 그림의 w: 크기
    (tmp_path / 'a.png').write_bytes(png(120, 80, b'\x10\x20\x30\xff'))
    md = tmp_path / 'doc.md'
    md.write_text('# 문서\n\n각주[^l].\n\n3. 셋\n4. 넷\n   1. 안쪽\n5. 다섯\n   1. 다시 안쪽\n\n![작은 w:300](a.png)\n\n![그대로](a.png)\n\n'
                  '[^l]: [LME](https://www.lme.com) 의 자료.\n', encoding='utf-8')
    out = tmp_path / 'doc.docx'
    builder(monkeypatch).build(md, out)
    xml = parts(out)
    note = xml['word/footnotes.xml']
    rid = re.search(r'<w:hyperlink r:id="([^"]+)"', note)[1]
    assert f'Id="{rid}"' in xml['word/_rels/footnotes.xml.rels'] and 'https://www.lme.com' in xml['word/_rels/footnotes.xml.rels']
    assert f'Id="{rid}"' not in xml['word/_rels/document.xml.rels']
    nums = re.findall(r'<w:num w:numId="(\d+)"><w:abstractNumId w:val="9102"/><w:lvlOverride w:ilvl="(\d)"><w:startOverride w:val="(\d+)"/>', xml['word/numbering.xml'])
    assert ('0', '3') in [(lvl, start) for _, lvl, start in nums]   # 3 부터
    assert len([n for n in nums if n[1] == '1']) == 2   # 안쪽 목록 둘 — 따로 1부터
    extents = re.findall(r'<wp:extent cx="(\d+)" cy="(\d+)"/>', xml['word/document.xml'])
    assert (str(300 * 9525), str(200 * 9525)) in extents and (str(120 * 9525), str(80 * 9525)) in extents


def test_split_front_reads_korean_keys():
    sys.path.insert(0, str(DOCX))
    try:
        lm = importlib.import_module('lectern_md')
    finally:
        sys.path.pop(0)
    fm = lm.split_front('---\n기관: 한국자원연구원\nWord 양식: 회사\nurl: https://a.b/c\n  - 목록 줄\nmarp: true\n---\n본문')[0]
    assert fm == {'기관': '한국자원연구원', 'Word 양식': '회사', 'url': 'https://a.b/c', 'marp': True}


def test_tex_runs(monkeypatch):
    mod = builder(monkeypatch)

    def text(tex):
        return ''.join(r['t'] for r in mod.tex_runs(tex))
    assert text(r'\Delta P = \frac{P_1 - P_0}{P_0}') == 'ΔP = (P1 − P0)/P0'
    assert text(r'\alpha + \beta = 1') == 'α + β = 1'
    assert text(r'x_i \in S') == 'xi ∈ S'
    runs = mod.tex_runs('x^{2}_t')
    assert {'t': '2', 'math': True, 'sup': True} in runs and {'t': 't', 'math': True, 'sub': True, 'i': True} in runs


def test_copied_helpers_match_the_pptx_skill():
    # 두 스킬이 같은 파일을 쓴다 — 한쪽만 고치면 시험이 잡는다
    for name in ('lectern_md.py', 'figure_png.py'):
        assert (DOCX / name).read_bytes() == (PPTX / name).read_bytes(), name


def test_skill_file_is_complete():
    text = (ROOT / 'skills' / 'lectern-to-docx' / 'SKILL.md').read_text(encoding='utf-8')
    assert text.startswith('---\nname: lectern-to-docx\n')
    for script in re.findall(r'scripts/(\w+\.py)', text):
        assert (DOCX / script).exists(), script


# ---- figure_png (두 스킬이 함께 쓴다) -----------------------------------------------------------------------

def figure_png(monkeypatch):
    monkeypatch.syspath_prepend(str(DOCX))
    return importlib.import_module('figure_png')


def test_parse_spec_reads_echarts_examples_but_no_functions(monkeypatch):
    f = figure_png(monkeypatch)
    spec = f.parse_spec("option = {\n  // 주석\n  title: { text: '용도', left: 'center' }, series: [{ type: 'pie', data: [{value: 0x10, name: \"a\"},], }],\n};")
    assert spec == {'title': {'text': '용도', 'left': 'center'}, 'series': [{'type': 'pie', 'data': [{'value': 16, 'name': 'a'}]}]}
    with pytest.raises(f.SpecError):
        f.parse_spec('{ formatter: function (p) { return 1 } }')
    assert f.parse_spec('{"a": [1, 2.5]}') == {'a': [1, 2.5]}


def test_inline_data_reads_project_files_only(tmp_path, monkeypatch):
    f = figure_png(monkeypatch)
    (tmp_path / 'p.csv').write_text('월,가격\n1,10\n', encoding='utf-8')
    spec = f.inline_data({'data': {'url': 'p.csv'}, 'layer': [{'data': {'url': 'https://x.test/a.csv'}}]}, tmp_path)
    assert spec['data'] == {'values': '월,가격\n1,10\n', 'format': {'type': 'csv'}}
    assert spec['layer'][0]['data'] == {'url': 'https://x.test/a.csv'}   # 인터넷 주소는 그대로 (그리지 않는다)


def png(w, h, pixel):
    raw = b''.join(b'\x00' + pixel * w for _ in range(h))
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')


def test_blank_png_is_a_failed_drawing(tmp_path, monkeypatch):
    f = figure_png(monkeypatch)
    empty, drawn = tmp_path / 'e.png', tmp_path / 'd.png'
    empty.write_bytes(png(40, 30, b'\x00\x00\x00\x00'))
    drawn.write_bytes(png(40, 30, b'\x10\x20\x30\xff'))
    assert f.blank(empty) and not f.blank(drawn)
