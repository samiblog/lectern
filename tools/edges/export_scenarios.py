"""내보내기 시나리오 (D144·D145·D146) — 실제로 쓸 법한 문서들로 html·지면 틀·Word 를 한 흐름에서 (브라우저 개발 모드).

1 정책 연구원: 한국어 맨 앞 설정(기관·연구진·부제)과 한국어 틀 이름(layout: 연구보고서), 요약 박스글, CSV 를 가리키는 차트 → 틀 html·Word
2 공무원: 정부 보고서 틀의 □ ○ ※ 문단, 한 장 보고서의 결재란 (목록 값)
3 애널리스트: ECharts 예제 그대로(주석·따옴표 없는 키)·Plotly, 핵심 수치·면책 자리 → Word 의 그림 수
4 회사원: 틀과 같은 이름의 Word 양식 — layout 하나로 Word 양식이 골라진다, docxStyle 이 이긴다
5 짓궂은 문서: 제목·맨 앞 설정의 <script>, 같은 각주 두 번, 접는 상자 — html 에 스크립트가 없고 Word 가 만들어진다
6 창을 연 채: 형식을 빠르게 바꾸기, 문서가 바뀌면 Word 도 다시
7 보기만 하는 예제 폴더에서 Word·html (프로젝트에 쓰지 않는다)
8 영어 화면: 창·알림·Word 결과가 영어

창 모드의 PDF(숨은 창)와 저장 대화상자는 여기서 돌지 않는다 — docs/TESTING.md 의 LAY·DOCX 수동 점검."""
import io
import json
import re
import shutil
import tempfile
import traceback
import zipfile
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import ROOT, check, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-export-scen-'))
proj = base / 'proj'
config = base / 'config'
for d in ('data', '정책', '행정', '리서치', '회사', '짓궂은'):
    (proj / d).mkdir(parents=True)
(proj / 'data' / '가격.csv').write_text('월,가격\n2026-01,10620\n2026-02,10290\n2026-03,10870\n2026-04,11040\n', encoding='utf-8')


def w(rel, text):
    (proj / rel).write_text(text.lstrip('\n'), encoding='utf-8')


w('정책/공급망-연구.md', """
---
기관: 한국자원연구원
연구진: [김연구, 이분석]
보고서번호: 연구보고서 2026-14
부제: 비축과 분할 구매
날짜: 2026-11-10
layout: 연구보고서
---

# 구리 공급망 연구

<!-- box: 요약 -->
- 비축 목표를 90일분으로 늘린다.
- 분기 구매를 셋으로 나눈다.
<!-- /box -->

[목차]

## 1. 배경

수요가 늘었다[^1]. 값은 [표 1](#표-1)과 같다.

표 1. 수요

| 지역 | 2025 | 2026 |
|---|---:|---:|
| 중국 | 1,520 | 1,565 |

```vega-lite
{"data": {"url": "../data/가격.csv"}, "mark": "line", "encoding": {"x": {"field": "월", "type": "ordinal"}, "y": {"field": "가격", "type": "quantitative", "scale": {"zero": false}}}, "width": "container", "height": 200}
```

그림 1. 월평균 가격

## 2. 제언

비축을 늘린다[^1].

[^1]: 시험용 수치.
""")
w('행정/주간-동향.md', """
---
title: 원자재 주간 동향
부서: 산업자원정책과
작성자: 정사무관
date: 2026-11-14
layout: gov-report
---

# 원자재 주간 동향

<!-- box: 요약 -->
□ 구리 가격이 연중 최고
<!-- /box -->

## 1. 동향

□ **구리**: 11,690달러
  ○ 재고 감소
  ※ LME 기준
""")
w('행정/결재.md', """
---
title: 구매 일정 조정
dept: 구매팀
author: 박담당
date: 2026-11-15
결재: [담당, 팀장, 본부장]
layout: one-page
---

# 구매 일정 조정

<!-- box: 결론 -->
11월로 앞당긴다.
<!-- /box -->

## 배경

가격이 내려왔다.
""")
w('리서치/리포트.md', """
---
회사: 시험금속
투자의견: 매수
목표가: 520,000원
layout: equity-research
---

# 구리 강세의 수혜

<!-- box: 핵심 수치 -->
| 구분 | 2026E |
|---|---:|
| PER (배) | 8.6 |
<!-- /box -->

```echarts
option = {
  // 분기별 영업이익
  xAxis: { type: 'category', data: ['1Q', '2Q'] },
  yAxis: { type: 'value' },
  series: [{ type: 'bar', data: [210, 236], }],
};
```

그림 1. 영업이익

```plotly
{"data": [{"type": "pie", "labels": ["전선", "건설"], "values": [60, 40]}], "layout": {"height": 300}}
```

그림 2. 매출 구성

<!-- box: 면책 -->
투자 권유가 아니다.
<!-- /box -->
""")
w('회사/월간.md', '---\ntitle: 월간 보고\nlayout: consulting\n---\n\n# 월간 보고\n\n가격이 올랐다.\n')
w('회사/양식지정.md', '---\nlayout: consulting\ndocxStyle: 기관\n---\n\n# 양식을 정한 문서\n\n본문.\n')
w('짓궂은/특수.md', """
---
title: 따옴표 "와" <script>alert(1)</script>
author: <img src=x onerror=alert(2)>
---

# 특수 <b>굵은</b> & "따옴표"

같은 각주를 두 번[^a] 부른다[^a]. 코드 `<script>alert(3)</script>`.

<details><summary>펼치기</summary>

숨은 글.

</details>

[^a]: 두 번 불린 각주.
""")
w('발표.md', '---\nmarp: true\n---\n\n# 발표\n')

# Word 양식: 틀 이름(consulting)과 같은 것 하나, 다른 이름 하나 — Word 없이 짠 가장 작은 .dotx
W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'


def dotx(path, width, header):
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml"/>'
                   '<Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/></Types>')
        z.writestr('_rels/.rels', '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        z.writestr('word/_rels/document.xml.rels', '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId9" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/></Relationships>')
        z.writestr('word/header1.xml', f'<?xml version="1.0" encoding="UTF-8"?><w:hdr {W}><w:p><w:r><w:t>{header}</w:t></w:r></w:p></w:hdr>')
        z.writestr('word/document.xml', f'<?xml version="1.0" encoding="UTF-8"?><w:document {W}><w:body><w:p/><w:sectPr><w:headerReference w:type="default" r:id="rId9"/>'
                   f'<w:pgSz w:w="{width}" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr></w:body></w:document>')


(config / 'docx-styles').mkdir(parents=True)
dotx(config / 'docx-styles' / 'consulting.dotx', 12240, '컨설팅 양식')
dotx(config / 'docx-styles' / '기관.dotx', 11000, '기관 양식')
server, url, port = serve(proj, config)
servers = []


def part(data, name='word/document.xml'):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return z.read(name).decode('utf-8') if name in z.namelist() else ''


def text_of(xml):
    return ''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', xml))


try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 1300, 'height': 900}, accept_downloads=True)
        page = ctx.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))

        def setup(pg, u):
            pg.goto(u)
            pg.wait_for_selector('#lec-tree .row.file', timeout=20000)

        def open_doc(pg, path):
            pg.evaluate("(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: p }))", path)
            pg.wait_for_function("(p) => document.querySelector('#lec-view')?.dataset.docPath === p", arg=path)
            pg.wait_for_timeout(300)

        def export(pg, label):
            pg.keyboard.press('Escape')
            pg.locator('#lec-view').click(button='right', position={'x': 6, 'y': 6})
            pg.wait_for_selector('#lec-menu:not([hidden])')
            pg.locator('#lec-menu button', has_text=label).click()
            pg.wait_for_selector('#lec-print:not([hidden])')

        def html_ready(pg):
            return until(pg, lambda: (pg.get_attribute('#lec-print-frame', 'src') or '').startswith('/export-preview/') and pg.is_enabled('#lec-print-html'), 30000)

        def html_text(pg):
            return pg.evaluate('(u) => fetch(u).then((r) => r.text())', pg.get_attribute('#lec-print-frame', 'src'))

        def docx_ready(pg):
            return until(pg, lambda: pg.is_enabled('#lec-print-docx') and pg.is_hidden('#lec-print-wait'), 90000)

        def download(pg, button='#lec-print-docx'):
            with pg.expect_download() as dl:
                pg.click(button)
            return dl.value.suggested_filename, Path(dl.value.path()).read_bytes()

        setup(page, url)

        print('[1. 정책 연구원 — 한국어 맨 앞 설정과 한국어 틀 이름]')
        open_doc(page, '정책/공급망-연구.md')
        export(page, 'html로 저장…')
        check('맨 앞 설정의 layout: 연구보고서 (이름) 로 틀이 골라진다', until(page, lambda: page.input_value('#lec-pp-layout') == 'research-report'), page.input_value('#lec-pp-layout'))
        check('틀 html 이 뜬다', html_ready(page))
        h = html_text(page)
        check('표지에 기관·연구진·보고서 번호·부제 (한국어 키)', all(s in h for s in ('한국자원연구원', '김연구', '연구보고서 2026-14', '비축과 분할 구매')), [s for s in ('한국자원연구원', '김연구', '연구보고서 2026-14', '비축과 분할 구매') if s not in h])
        check('요약 박스글이 자리로', '비축 목표를 90일분으로' in h and h.index('비축 목표를 90일분으로') < h.index('1. 배경'))
        check('CSV 를 가리키는 차트도 그림으로 담긴다', h.count('<svg') >= 1 and '../data/가격.csv' not in h)
        check('html 에 스크립트가 없다', '<script' not in h.lower())
        check('본문은 .md-body 한 겹 (두 겹이면 2단 틀이 종이에서 4단)', h.count('class="md-body"') == 1, h.count('class="md-body"'))
        page.click('#lec-print input[name="pp_format"][value="docx"]')
        check('Word 로 바꾸면 만든다', docx_ready(page))
        info = page.inner_text('#lec-print-docx-info')
        check('그림 1개 (CSV 차트)', '그림 1개' in info, info)
        check('틀 이름과 같은 Word 양식이 없으면 기본 양식', page.input_value('#lec-pp-docx') == '' and '양식: Lectern 기본 양식' in info)
        name, data = download(page)
        doc = text_of(part(data))
        check('Word: 문서 이름·제목·부제·연구진·요약 박스 이름', name == '공급망-연구.docx' and all(s in doc for s in ('구리 공급망 연구', '비축과 분할 구매', '김연구, 이분석', '요약', '시험용 수치') if s != '시험용 수치')
              and '시험용 수치' in text_of(part(data, 'word/footnotes.xml')), (name, doc[:200]))
        check('Word: 같은 각주를 두 번 — 두 번째는 NOTEREF', part(data).count('<w:footnoteReference') == 1 and 'NOTEREF _RefLecFn1' in part(data))

        print('[2. 공무원 — 정부 보고서와 한 장 보고서]')
        open_doc(page, '행정/주간-동향.md')
        export(page, 'html로 저장…')
        html_ready(page)
        h = html_text(page)
        check('정부 보고서: 부서·작성자(한국어 키)와 □ ○ ※ 문단', '산업자원정책과' in h and '정사무관' in h and '□' in h and '○ 재고 감소' in h and '※ LME 기준' in h)
        open_doc(page, '행정/결재.md')
        export(page, 'html로 저장…')
        check('한 장 보고서가 골라진다', until(page, lambda: page.input_value('#lec-pp-layout') == 'one-page'))
        html_ready(page)
        h = html_text(page)
        check('결재란 세 칸 (목록 값)', all(f'>{s}<' in h for s in ('담당', '팀장', '본부장')), re.findall(r'lay-sign[\s\S]{0,300}', h)[:1])
        check('결론 박스글이 자리로', '11월로 앞당긴다' in h)
        page.click('#lec-print input[name="pp_format"][value="docx"]')
        docx_ready(page)
        _, data = download(page)
        check('Word: 결론 박스의 이름이 제목, 작성자', '결론' in text_of(part(data)) and '박담당' in text_of(part(data)))

        print('[3. 애널리스트 — ECharts 예제 그대로와 Plotly]')
        open_doc(page, '리서치/리포트.md')
        until(page, lambda: page.locator('#lec-view .lec-chart svg, #lec-view .lec-chart canvas').count() >= 2, 20000)
        export(page, 'Word로 저장…')
        check('Word 가 만들어진다', docx_ready(page))
        info = page.inner_text('#lec-print-docx-info')
        check('주석이 든 ECharts·Plotly 모두 그림 (2개, 알림 없음)', '그림 2개' in info and '그리지 못해' not in info, info)
        page.click('#lec-print input[name="pp_format"][value="html"]')
        html_ready(page)
        h = html_text(page)
        check('html 은 증권사 리포트 틀 — 투자의견·목표가·면책', '매수' in h and '520,000원' in h and '투자 권유가 아니다' in h)

        print('[4. 회사원 — 틀과 같은 이름의 Word 양식]')
        open_doc(page, '회사/월간.md')
        export(page, 'Word로 저장…')
        check('layout: consulting 이면 같은 이름의 Word 양식이 골라진다', until(page, lambda: page.input_value('#lec-pp-docx') == 'consulting'), page.input_value('#lec-pp-docx'))
        docx_ready(page)
        _, data = download(page)
        check('그 양식의 쪽 크기·머리글', '<w:pgSz w:w="12240" w:h="15840"/>' in part(data) and '컨설팅 양식' in part(data, 'word/header1.xml'))
        open_doc(page, '회사/양식지정.md')
        export(page, 'Word로 저장…')
        check('docxStyle 이 layout 보다 먼저', until(page, lambda: page.input_value('#lec-pp-docx') == '기관'), page.input_value('#lec-pp-docx'))
        docx_ready(page)
        page.click('#lec-print-close')

        print('[5. 짓궂은 문서]')
        open_doc(page, '짓궂은/특수.md')
        export(page, 'html로 저장…')
        html_ready(page)
        h = html_text(page)
        body = h[h.index('<body'):] if '<body' in h else h
        check('html: 제목·맨 앞 설정의 <script>·onerror 는 글로만', '<script' not in h.lower() and 'onerror=' not in body.replace('onerror=alert(2)&gt;', ''), re.findall(r'.{30}onerror.{30}', h)[:2])
        page.click('#lec-print input[name="pp_format"][value="docx"]')
        check('Word 가 만들어진다', docx_ready(page))
        _, data = download(page)
        xml = part(data)
        t = text_of(xml)
        check('Word: <b> 는 굵게, 펼친 상자, 두 번 부른 각주', '굵은' in t and '<b>' not in t and '펼치기' in t and '숨은 글' in t and '<details' not in t and 'NOTEREF' in xml)
        check('Word: 코드 속 <script> 는 글로 (이스케이프)', '&lt;script&gt;alert(3)' in xml)

        print('[6. 창을 연 채]')
        open_doc(page, '회사/월간.md')
        export(page, 'Word로 저장…')
        for fmt in ('html', 'docx', 'html', 'docx'):
            page.click(f'#lec-print input[name="pp_format"][value="{fmt}"]')
            page.wait_for_timeout(120)
        check('형식을 빠르게 바꿔도 마지막 것(Word)이 남는다', docx_ready(page) and page.is_visible('#lec-print-docx-info') and page.is_hidden('#lec-print-frame')
              and page.is_hidden('#lec-print-wait'))
        page.evaluate("() => { document.querySelector('#lec-print-docx-info').textContent = 'OLD'; }")   # 다시 만들면 비웠다가 새로 채운다
        (proj / '회사' / '월간.md').write_text('---\ntitle: 월간 보고\nlayout: consulting\n---\n\n# 월간 보고\n\n' + '고친 문단이다. ' * 400 + '\n', encoding='utf-8')
        check('문서가 바뀌면 Word 도 다시 만든다', until(page, lambda: page.is_enabled('#lec-print-docx') and page.inner_text('#lec-print-docx-info') not in ('', 'OLD'), 60000),
              page.inner_text('#lec-print-docx-info'))
        _, data = download(page)
        check('저장한 것은 고친 글', '고친 문단이다' in text_of(part(data)))

        print('[7. 슬라이드]')
        open_doc(page, '발표.md')
        page.wait_for_timeout(500)
        page.locator('#lec-view').click(button='right', position={'x': 6, 'y': 6})
        page.wait_for_selector('#lec-menu:not([hidden])')
        labels = page.evaluate("[...document.querySelectorAll('#lec-menu button[data-i] > span')].map((e) => e.textContent)")
        check("Lectern 슬라이드에는 html·Word 저장이 없다", 'Word로 저장…' not in labels and 'html로 저장…' not in labels, labels)
        page.keyboard.press('Escape')
        check('페이지 오류 없음', not errors, errors[:3])

        print('[8. 보기만 하는 예제 폴더]')
        shipped = sorted(p.name for p in (ROOT / 'samples').rglob('*.docx'))
        s2, url2, _ = serve(ROOT / 'samples', base / 'c2')
        servers.append(s2)
        ro = ctx.new_page()
        setup(ro, url2)
        open_doc(ro, 'reports/3분기-구리-구매-전략.md')
        export(ro, 'Word로 저장…')
        check('예제 문서도 Word 로 (그림 1개)', docx_ready(ro) and '그림 1개' in ro.inner_text('#lec-print-docx-info'), ro.inner_text('#lec-print-docx-info'))
        name, data = download(ro)
        check('내려받은 파일', name == '3분기-구리-구매-전략.docx' and '3분기 구리 구매 전략' in text_of(part(data)), name)
        check('예제 폴더에 docx 가 생기지 않았다', sorted(p.name for p in (ROOT / 'samples').rglob('*.docx')) == shipped)
        ro.close()

        print('[9. 영어 화면]')
        (base / 'c3').mkdir()
        (base / 'c3' / 'config.json').write_text(json.dumps({'language': 'en'}), encoding='utf-8')
        en_proj = base / 'en'
        en_proj.mkdir()
        (en_proj / 'report.md').write_text('---\nlang: en\n---\n\n# Report\n\n[toc]\n\n## Prices\n\nTable 1. Prices\n\n| Month | Price |\n|---|---:|\n| Oct | 11,220 |\n\nSee [Table 1](#table-1).\n', encoding='utf-8')
        s3, url3, _ = serve(en_proj, base / 'c3')
        servers.append(s3)
        en = ctx.new_page()
        setup(en, url3)
        open_doc(en, 'report.md')
        export(en, 'Save as Word…')
        docx_ready(en)
        hangul = en.evaluate("[...document.querySelectorAll('#lec-print :is(p, label, button, span, b, small, option, div)')].filter((e) => e.offsetParent && /[가-힣]/.test(e.textContent)).map((e) => e.textContent.trim()).slice(0, 4)")
        check('창에 한국어가 남지 않는다', not hangul, hangul)
        check('알림이 영어', 'Made the Word file' in en.inner_text('#lec-print-docx-info'), en.inner_text('#lec-print-docx-info'))
        _, data = download(en)
        xml = part(data)
        check('Word 의 목차 이름·캡션 필드·링크가 영어', 'Contents' in text_of(xml) and ' SEQ Table ' in xml and 'w:anchor="lec_tbl_1"' in xml)
        en.close()
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    for s in servers:
        s.terminate()
    stop(server, base)
report()
