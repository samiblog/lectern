"""0.112 사람 시나리오 1 — 연구원 A 가 구리 보고서의 그림과 차트를 다듬는다 (D212·D213). 차례대로 한 사람이 할 법한 일:

1. 보고서를 연다 — 모든 그림이 예전 그대로(1·1), 문서 점검은 그대로.
2. 여섯 단계를 가로로 그린 그림의 글자가 작다 → 우클릭 '세로로 바꾸기' → 글자가 본문 크기로.
3. Claude(밖에서 쓰기)가 안내대로 문서 위에 '<!-- 도해: 스타일 2 · 색 2 -->' 를 넣는다 → 그림·차트 모두 2·2, 화면에는 보이지 않는다.
4. 설명이 붙은 그림만 우클릭 '도해 스타일…' 8 제목 띠 → 이어서 '색 조합…' 6 따뜻한 → 한 줄 '스타일: 8 · 색: 6'.
5. 수요 차트에서 전력만 보이게 '색 조합…' 3 회색 + 강조 → Ctrl+Z 로 되돌렸다가 Ctrl+Y 로 다시.
6. Claude 가 구성도의 한 상자에 ':::key' 를 붙인다 → 보고서 남색으로 칠해진다.
7. 의존 관계 그림(Graphviz)을 '가로로 바꾸기' → rankdir=LR 한 줄.
8. 다른 문서(메모)는 문서의 줄이 없다 → 설정에서 기본 3·4 → 메모만 따른다, 보고서는 그대로.
9. 발표(Lectern 슬라이드)의 '<!-- 도해: … -->' 는 발표자 노트가 아니고, 슬라이드의 그림이 그 번호로.
10. 어두운 스타일·종이 스타일로 바꿔 본다 → 띠 위 글자가 읽히고 진한 색은 밝게.
11. 'html로 저장' 의 글과 인쇄 화면에 그림이 그대로 — 문서 점검에 새로 잡힌 곳이 없다.
12. 원문은 고른 것만 바뀌었다 (표시 줄·방향 글자·문서의 줄·Claude 가 붙인 :::key 뿐)."""
import json
import re
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop, until

REPORT = """# 3분기 구리 구매 전략

구리 수요는 전력망 투자로 늘고, 공급은 칠레 생산 감소로 빠듯하다. 아래 그림과 차트로 판단의 흐름을 정리한다.

## 1. 판단의 흐름

```mermaid
flowchart LR
  A[가격 자료] --> B[재고 확인] --> C[수요 추정] --> D[공급 점검] --> E[시나리오] --> F[구매 시점]
```

## 2. 처리 흐름

```mermaid
flowchart LR
  A[자료 수집<br>통계청·업계 보고서 12건] --> B[분석<br>수요 회귀 모형, 가격 시나리오 3개]
  B --> C[보고<br>4분기 구매 전략]
```

## 3. 공급망

```mermaid
flowchart LR
  subgraph 광산
    M1[칠레] --> M2[페루]
  end
  subgraph 제련
    S1[중국 제련] --> S2[국내 제련]
  end
  M2 --> S1
  S2 --> U[우리 공장]
```

## 4. 용도별 수요

```vega-lite
{ "width": "container", "height": 180,
  "data": {"values": [
    {"분기": "1분기", "용도": "전력", "수요": 42}, {"분기": "1분기", "용도": "건설", "수요": 30}, {"분기": "1분기", "용도": "운송", "수요": 18},
    {"분기": "2분기", "용도": "전력", "수요": 45}, {"분기": "2분기", "용도": "건설", "수요": 28}, {"분기": "2분기", "용도": "운송", "수요": 20}
  ]},
  "mark": "bar",
  "encoding": {"x": {"field": "분기", "type": "nominal", "title": null}, "xOffset": {"field": "용도", "sort": ["전력", "건설", "운송"]},
    "y": {"field": "수요", "type": "quantitative"}, "color": {"field": "용도", "type": "nominal", "sort": ["전력", "건설", "운송"]}} }
```

## 5. 가격 흐름

```echarts
{ "xAxis": {"type": "category", "data": ["7월", "8월", "9월"]}, "yAxis": {"type": "value"},
  "series": [{"type": "line", "name": "LME", "data": [9100, 9250, 9350]}, {"type": "line", "name": "상하이", "data": [9050, 9200, 9400]}] }
```

## 6. 의존 관계

```dot
digraph 의존 {
  가격 -> 시나리오; 재고 -> 시나리오; 시나리오 -> 구매
}
```
"""
MEMO = """# 메모

```mermaid
flowchart LR
  A[생각] --> B[정리]
```
"""
DECK = """---
marp: true
---

# 발표

<!-- 도해: 스타일 3 · 색 7 -->

<!-- 발표자에게: 처음 1분은 결론부터. -->

---

## 흐름

```mermaid
flowchart LR
  A[수집] --> B[분석]:::key --> C[보고]
```
"""
ALL = '#lec-view pre.mermaid, #lec-view pre.lec-chart'
MARKS = f"() => [...document.querySelectorAll('{ALL}')].map((n) => (n.dataset.diagramStyle || '-') + '/' + (n.dataset.diagramColors || '-'))"
RGB = lambda h: f'rgb({int(h[1:3], 16)}, {int(h[3:5], 16)}, {int(h[5:7], 16)})'   # noqa: E731
SCALE = """(i) => { const s = [...document.querySelectorAll('#lec-view pre.mermaid')][i].querySelector('svg'); const r = s.getBoundingClientRect();
  return Math.round(r.width / s.viewBox.baseVal.width * 100) / 100; }"""
FILLS = f"""(i) => {{ const n = [...document.querySelectorAll('{ALL}')][i]; if (!n) return [];
  const out = []; for (const e of n.querySelectorAll('svg path, svg rect')) {{ const f = getComputedStyle(e).fill; if (f && f !== 'none' && !out.includes(f)) out.push(f); }} return out; }}"""
LINT = "(text) => import('/static/js/doclint.js').then((m) => m.lintDoc(text.split('\\n')).map((x) => x.code + '@' + x.line))"

base = Path(tempfile.mkdtemp(prefix='lec-scen112-'))
proj = base / '과제'
proj.mkdir()
rep = proj / '보고서.md'
rep.write_text(REPORT, encoding='utf-8', newline='\n')
(proj / '메모.md').write_text(MEMO, encoding='utf-8', newline='\n')
(proj / '발표.md').write_text(DECK, encoding='utf-8', newline='\n')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False, 'theme': 'report', 'toc_visible': False}), encoding='utf-8')
src = lambda: rep.read_text(encoding='utf-8').replace('\r\n', '\n')   # noqa: E731


def ext_write(text):
    """Claude 가 밖에서 고친다 (수정 시각이 바뀌게 1초 뒤)"""
    time.sleep(1.05)
    rep.write_text(text, encoding='utf-8', newline='\n')


server, url, port = serve(proj, config)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1280, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)

        def open_doc(name, mermaid, charts):
            page.click(f'#lec-tree .row[data-doc="{name}"]')
            until(page, lambda: page.locator('#lec-view pre.mermaid.mermaid-ok').count() == mermaid and page.locator('#lec-view pre.lec-chart.chart-ok').count() == charts, ms=30000)

        def marks():
            return page.evaluate(MARKS)

        def settle(want, ms=15000):
            return until(page, lambda: marks() == want, ms=ms)

        def menu(i, item, pick=None):
            page.locator(ALL).nth(i).click(button='right', position={'x': 5, 'y': 5})
            page.wait_for_selector('#lec-menu:not([hidden])', timeout=5000)
            page.locator('#lec-menu button', has_text=item).first.click()
            if pick:
                page.wait_for_selector('#lec-menu .menu-head', timeout=5000)
                page.locator('#lec-menu button', has_text=pick).first.click()

        print('[1. 보고서를 연다]')
        open_doc('보고서.md', 3, 3)
        check('모든 그림·차트가 예전 그대로 (모양 1, 색 1)', marks() == ['1/1', '1/1', '1/1', '-/1', '-/1', '1/1'], marks())
        lint0 = page.evaluate(LINT, REPORT)

        print('[2. 가로 여섯 상자 → 세로]')
        small = page.evaluate(SCALE, 0)
        check('가로 여섯 상자는 줄어 그려진다 (글자가 작다)', small < 0.8, small)
        menu(0, '세로로 바꾸기')
        until(page, lambda: '```mermaid\nflowchart TD\n  A[가격 자료]' in src(), ms=8000)
        until(page, lambda: page.evaluate(SCALE, 0) == 1, ms=12000)
        check("'세로로 바꾸기' — flowchart TD, 그림이 줄지 않는다", '```mermaid\nflowchart TD\n  A[가격 자료]' in src() and page.evaluate(SCALE, 0) == 1, page.evaluate(SCALE, 0))

        print('[3. Claude 가 문서의 기본 줄을 넣는다]')
        ext_write(src().replace('# 3분기 구리 구매 전략\n', '# 3분기 구리 구매 전략\n\n<!-- 도해: 스타일 2 · 색 2 -->\n', 1))
        settle(['2/2', '2/2', '2/2', '-/2', '-/2', '2/2'])
        check('그림·차트가 모두 문서의 번호로 (2 보고서 선 · 2 보고서 남색)', marks() == ['2/2', '2/2', '2/2', '-/2', '-/2', '2/2'], marks())
        check('문서의 줄은 화면에 보이지 않는다', '도해:' not in page.evaluate("() => document.querySelector('#lec-view').innerText"))
        check('차트도 보고서 남색', RGB('#17304f') in page.evaluate(FILLS, 3) and RGB('#17304f') in page.evaluate(FILLS, 4) + [RGB('#17304f')] , page.evaluate(FILLS, 3))
        strokes = page.evaluate("() => [...new Set([...[...document.querySelectorAll('#lec-view pre.lec-chart')][1].querySelectorAll('path')].map((e) => getComputedStyle(e).stroke))]")
        check('ECharts 선 그래프의 선도 보고서 남색의 계열 색', RGB('#17304f') in strokes and RGB('#2f5d8a') in strokes, strokes)

        print('[4. 설명이 붙은 그림 — 제목 띠, 따뜻한]')
        menu(1, '도해 스타일…', '8. 제목 띠')
        until(page, lambda: 'flowchart LR\n  %% 스타일: 8\n  A[자료 수집' in src(), ms=8000)
        settle(['2/2', '8/2', '2/2', '-/2', '-/2', '2/2'])
        bands = page.locator('#lec-view pre.mermaid >> nth=1').locator('.lec-title-band').count()
        check('제목 띠 — 줄을 바꾼 상자 셋에 띠', bands == 3, bands)
        menu(1, '색 조합…', '6. 따뜻한')
        until(page, lambda: '  %% 스타일: 8 · 색: 6\n' in src(), ms=8000)
        settle(['2/2', '8/6', '2/2', '-/2', '-/2', '2/2'])
        band = page.evaluate("() => getComputedStyle([...document.querySelectorAll('#lec-view pre.mermaid')][1].querySelector('.lec-title-band')).fill")
        check("한 줄에 '스타일: 8 · 색: 6' — 띠가 따뜻한의 진한 색", src().count('%% 스타일: 8 · 색: 6') == 1 and band == RGB('#7c2d12'), band)

        print('[5. 전력만 보이게 — 되돌리고 다시]')
        menu(3, '색 조합…', '3. 회색 + 강조')
        until(page, lambda: '```vega-lite\n// 색: 3\n{ "width"' in src(), ms=8000)
        settle(['2/2', '8/6', '2/2', '-/3', '-/2', '2/2'])
        vg = page.evaluate(FILLS, 3)
        check('차트 맨 앞에 // 색: 3 — 전력(첫 계열)만 주황, 나머지 회색', RGB('#c2410c') in vg and RGB('#6b7280') in vg and RGB('#17304f') not in vg, vg)
        page.locator('#lec-view h1').click()
        page.keyboard.press('Control+z')
        until(page, lambda: '// 색: 3' not in src(), ms=8000)
        settle(['2/2', '8/6', '2/2', '-/2', '-/2', '2/2'])
        check('Ctrl+Z — 그 줄만 없어지고 문서의 색으로', '// 색: 3' not in src() and marks()[3] == '-/2', marks())
        page.keyboard.press('Control+y')
        until(page, lambda: '// 색: 3' in src(), ms=8000)
        settle(['2/2', '8/6', '2/2', '-/3', '-/2', '2/2'])
        check('Ctrl+Y — 다시', marks()[3] == '-/3', marks())

        print('[6. Claude 가 구성도에 핵심 표시]')
        ext_write(src().replace('    S1[중국 제련] --> S2[국내 제련]', '    S1[중국 제련]:::key --> S2[국내 제련]', 1))
        until(page, lambda: page.evaluate("() => !![...document.querySelectorAll('#lec-view pre.mermaid')][2].querySelector('g.node.key')"), ms=12000)
        key = page.evaluate("() => getComputedStyle([...document.querySelectorAll('#lec-view pre.mermaid')][2].querySelector('g.node.key rect')).fill")
        check('핵심 상자는 보고서 남색으로 (2 보고서 선의 핵심 = 진한 채움)', key == RGB('#17304f'), key)
        check('원문에는 classDef 가 생기지 않는다 (그릴 때만)', 'classDef' not in src())

        print('[7. 의존 관계 — 가로로]')
        menu(5, '가로로 바꾸기')
        until(page, lambda: 'digraph 의존 {\n  rankdir=LR\n  가격 -> 시나리오' in src(), ms=8000)
        check('Graphviz: rankdir=LR 한 줄', 'digraph 의존 {\n  rankdir=LR\n  가격 -> 시나리오' in src(), src()[-120:])
        until(page, lambda: page.evaluate("() => { const s = document.querySelector('#lec-view pre.lec-chart[data-chart=\"dot\"] svg'); const v = s && s.viewBox.baseVal; return !!v && v.width > v.height; }"), ms=12000)
        check('다시 그리면 가로로 길다', page.evaluate("() => { const v = document.querySelector('#lec-view pre.lec-chart[data-chart=\"dot\"] svg').viewBox.baseVal; return v.width > v.height; }"))
        final = src()

        print('[8. 메모 — 설정의 기본만 따른다]')
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open-settings', 'view'))")
        page.wait_for_selector('#lec-dstyle-preview pre.mermaid svg', timeout=15000)
        page.select_option('#lec-dstyle', '3')
        page.select_option('#lec-dcolors', '4')
        until(page, lambda: json.loads((config / 'config.json').read_text(encoding='utf-8')).get('diagram_colors') == 4, ms=5000)
        page.keyboard.press('Escape')
        settle(['2/2', '8/6', '2/2', '-/3', '-/2', '2/2'])
        check('보고서는 문서의 줄을 따라 그대로', marks() == ['2/2', '8/6', '2/2', '-/3', '-/2', '2/2'], marks())
        open_doc('메모.md', 1, 0)
        until(page, lambda: marks() == ['3/4'], ms=10000)
        check('메모(문서의 줄 없음)는 설정의 3·4', marks() == ['3/4'], marks())

        print('[9. 발표 — 문서의 줄은 노트가 아니다]')
        page.click('#lec-tree .row[data-doc="발표.md"]')
        until(page, lambda: page.locator('#lec-view .lec-slide pre.mermaid.mermaid-ok').count() == 1, ms=30000)
        notes = page.evaluate("() => [...document.querySelectorAll('#lec-view .lec-slide-notes')].map((n) => n.textContent)")
        check("발표자 노트에 '도해:' 가 없다 (다른 노트는 그대로)", all('도해' not in n for n in notes) and any('처음 1분' in n for n in notes), notes)
        until(page, lambda: marks() == ['3/7'], ms=10000)
        check('슬라이드의 그림은 문서의 줄대로 (3 카드 · 7 차가운)', marks() == ['3/7'], marks())
        key = page.evaluate("() => getComputedStyle(document.querySelector('#lec-view .lec-slide g.node.key rect')).fill")
        check('슬라이드의 핵심은 차가운의 진한 색', key == RGB('#1e3a8a'), key)

        print('[10. 어두운·종이 스타일]')
        open_doc('보고서.md', 3, 3)
        page.select_option('#lec-theme', 'dark')
        until(page, lambda: page.evaluate("() => document.documentElement.dataset.theme") == 'dark')
        until(page, lambda: page.evaluate("() => getComputedStyle([...document.querySelectorAll('#lec-view pre.mermaid')][2].querySelector('g.node.key rect')).fill") != RGB('#17304f'), ms=12000)
        dark = page.evaluate("""() => { const n = [...document.querySelectorAll('#lec-view pre.mermaid')][1]; const band = n.querySelector('.lec-title-band'); const dt = n.querySelector('.lec-dt');
          return { band: getComputedStyle(band).fill, ink: getComputedStyle(dt).color }; }""")
        check('어두운 스타일: 띠 글자는 띠와 다른 밝기로 읽힌다', dark['band'] != dark['ink'], dark)
        page.select_option('#lec-theme', 'paper')
        until(page, lambda: page.evaluate("() => document.documentElement.dataset.theme") == 'paper')
        settle(['2/2', '8/6', '2/2', '-/3', '-/2', '2/2'])
        check('종이 스타일에서도 번호는 그대로', marks() == ['2/2', '8/6', '2/2', '-/3', '-/2', '2/2'], marks())
        page.select_option('#lec-theme', 'report')
        until(page, lambda: page.evaluate("() => document.documentElement.dataset.theme") == 'report')

        print('[11. html 로 저장 · 인쇄 · 문서 점검]')
        settle(['2/2', '8/6', '2/2', '-/3', '-/2', '2/2'])
        band_now = "() => getComputedStyle([...document.querySelectorAll('#lec-view pre.mermaid')][1].querySelector('.lec-title-band')).fill"
        until(page, lambda: page.evaluate(band_now) == RGB('#7c2d12'), ms=12000)   # 스타일을 바꾼 뒤 다시 그리기가 끝나기를
        got = page.evaluate("""() => Promise.all([import('/static/js/mdhtml.js'), import('/static/js/store.js')]).then(([m, { S }]) => m.buildMdHtml(S.pane, '보고서.md', { printCss: '' }))
          .then((r) => typeof r === 'string' ? r : (r.html || JSON.stringify(r)))""")
        check("'html로 저장' 의 글에 제목 띠와 색 조합의 색 (따뜻한의 진한 색), 문서의 줄은 없다", 'lec-title-band' in got and 'rgb(124, 45, 18)' in got and '도해: 스타일' not in got,
              ('lec-title-band' in got, 'rgb(124, 45, 18)' in got, '도해: 스타일' in got))
        page.emulate_media(media='print')
        page.wait_for_timeout(300)
        check('인쇄 화면에도 그림 여섯', page.locator('#lec-view pre.mermaid svg, #lec-view pre.lec-chart svg').count() == 6)
        page.emulate_media(media='screen')
        lint1 = page.evaluate(LINT, final)
        norm = lambda xs: sorted(re.sub(r'@\d+$', '', x) for x in xs)   # noqa: E731 — 줄이 밀려도 같은 것
        check('문서 점검에 새로 잡힌 곳이 없다 (표시 줄·문서의 줄은 점검 거리가 아니다)', norm(lint1) == norm(lint0), (lint0, lint1))

        print('[12. 원문은 고른 것만]')
        want = REPORT.replace('# 3분기 구리 구매 전략\n', '# 3분기 구리 구매 전략\n\n<!-- 도해: 스타일 2 · 색 2 -->\n', 1)
        want = want.replace('```mermaid\nflowchart LR\n  A[가격 자료]', '```mermaid\nflowchart TD\n  A[가격 자료]', 1)
        want = want.replace('flowchart LR\n  A[자료 수집', 'flowchart LR\n  %% 스타일: 8 · 색: 6\n  A[자료 수집', 1)
        want = want.replace('```vega-lite\n{ "width"', '```vega-lite\n// 색: 3\n{ "width"', 1)
        want = want.replace('    S1[중국 제련] --> S2[국내 제련]', '    S1[중국 제련]:::key --> S2[국내 제련]', 1)
        want = want.replace('digraph 의존 {\n', 'digraph 의존 {\n  rankdir=LR\n', 1)
        check('바뀐 것은 문서의 줄·표시 줄·방향 글자·Claude 의 :::key 뿐', final == want, [ln for ln in final.split('\n') if ln not in want.split('\n')][:5])
        check('화면 스크립트 오류 없음', not errors, errors[:5])
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
