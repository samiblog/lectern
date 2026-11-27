"""색 조합·방향·문서의 기본 줄 (D213).
- 문서의 '<!-- 도해: 스타일 3 · 색 2 -->' 가 그 문서의 기본 — 블록의 표시 줄이 먼저, 코드 블록 안의 예시 줄은 건너뛴다, 화면에는 보이지 않는다.
- 색 조합이 Mermaid(상자·핵심·제목 띠)·Vega-Lite·ECharts·Plotly 의 계열 색을 바꾼다. 한 줄에 '스타일: 8 · 색: 6'.
- 우클릭 '색 조합…' 은 있는 표시 줄에 이어 적고 '문서의 기본 따르기' 는 그 조각만 지운다. 차트에는 블록 맨 앞에 '// 색: N'.
- 우클릭 '세로로 바꾸기'·'가로로 바꾸기' — Mermaid 는 flowchart 의 방향 글자, Graphviz 는 rankdir (없으면 더한다).
- 설정의 기본 색 조합은 문서의 줄이 없는 그림만. 어두운 스타일에서는 진한 색을 밝게. 화면 스크립트 오류 없음."""
import json
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop, until

DOC = """# 색

````md
<!-- 도해: 스타일 9 · 색 8 -->
````

<!-- 도해: 스타일 3 · 색 2 -->

## 문서 기본

```mermaid
flowchart LR
  A[가] --> B[나]:::key
```

## 블록이 먼저

```mermaid
flowchart LR
  %% 색: 5
  A[가] --> B[나]:::key
```

## 한 줄에 둘

```mermaid
flowchart LR
  %% 스타일: 8 · 색: 6
  A[가<br>내용] --> B[나]
```

## 방향

```mermaid
flowchart LR
  A[하나] --> B[둘]
```

## 차트

```vega-lite
// 색: 3
{ "data": {"values": [{"k": "a", "v": 3}, {"k": "b", "v": 2}, {"k": "c", "v": 1}]}, "mark": "bar",
  "encoding": {"x": {"field": "k", "type": "nominal"}, "y": {"field": "v", "type": "quantitative"}, "color": {"field": "k", "type": "nominal"}} }
```

```echarts
// 색: 4
{ "xAxis": {"type": "category", "data": ["a", "b"]}, "yAxis": {"type": "value"}, "series": [{"type": "bar", "data": [1, 2]}, {"type": "bar", "data": [2, 1]}] }
```

```plotly
// 색: 5
{ "data": [{"type": "bar", "x": ["a", "b"], "y": [1, 2]}, {"type": "bar", "x": ["a", "b"], "y": [2, 1]}], "layout": {} }
```

```vega-lite
{ "data": {"values": [{"k": "a", "v": 3}, {"k": "b", "v": 2}]}, "mark": "bar",
  "encoding": {"x": {"field": "k", "type": "nominal"}, "y": {"field": "v", "type": "quantitative"}, "color": {"field": "k", "type": "nominal"}} }
```

```dot
digraph g {
  A -> B
}
```
"""
RGB = lambda h: f'rgb({int(h[1:3], 16)}, {int(h[3:5], 16)}, {int(h[5:7], 16)})'   # noqa: E731
ALL = "#lec-view pre.mermaid, #lec-view pre.lec-chart"
MARKS = f"() => [...document.querySelectorAll('{ALL}')].map((n) => (n.dataset.diagramStyle || '-') + '/' + (n.dataset.diagramColors || '-'))"
KEYFILL = "(i) => { const n = [...document.querySelectorAll('#lec-view pre.mermaid')][i]; const r = n && n.querySelector('g.node.key rect'); return r ? getComputedStyle(r).fill : null; }"
FILLS = f"""(i) => {{ const n = [...document.querySelectorAll('{ALL}')][i]; if (!n) return [];
  const out = []; for (const e of n.querySelectorAll('svg path, svg rect')) {{ const f = getComputedStyle(e).fill; if (f && f !== 'none' && !out.includes(f)) out.push(f); }} return out; }}"""

base = Path(tempfile.mkdtemp(prefix='lec-dcolors-'))
proj = base / '과제'
proj.mkdir()
doc = proj / '색.md'
doc.write_text(DOC, encoding='utf-8', newline='\n')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False, 'theme': 'report', 'toc_visible': False}), encoding='utf-8')
src = lambda: doc.read_text(encoding='utf-8').replace('\r\n', '\n')   # noqa: E731

server, url, port = serve(proj, config)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1300, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        page.click('#lec-tree .row[data-doc="색.md"]')

        def marks():
            return page.evaluate(MARKS)

        def drawn():
            until(page, lambda: page.locator('#lec-view pre.mermaid.mermaid-ok').count() == 4 and page.locator('#lec-view pre.lec-chart.chart-ok').count() == 5, ms=30000)

        def settle(i, want):
            until(page, lambda: len(marks()) == 9 and marks()[i] == want, ms=12000)

        drawn()
        print('[문서의 기본 줄과 블록의 줄]')
        m = marks()
        check("문서의 '<!-- 도해: 스타일 3 · 색 2 -->' 가 기본 (코드 블록 안의 예시 줄 9·8 은 건너뛴다)", m[0] == '3/2', m)
        check('블록의 색 줄이 먼저 (모양은 문서의 3)', m[1] == '3/5', m)
        check("한 줄에 '스타일: 8 · 색: 6'", m[2] == '8/6', m)
        check('차트: 블록의 // 색 줄, 없으면 문서의 2 (Graphviz 도 문서의 3·2)', m[4:] == ['-/3', '-/4', '-/5', '-/2', '3/2'], m)
        check('문서의 기본 줄은 화면에 보이지 않는다', '스타일 3 · 색 2' not in page.evaluate("() => document.querySelector('#lec-view').innerText"))

        print('[색이 바뀐다]')
        check('Mermaid 의 핵심 — 색 2 보고서 남색', page.evaluate(KEYFILL, 0) == RGB('#17304f'), page.evaluate(KEYFILL, 0))
        check('Mermaid 의 핵심 — 색 5 색약 친화', page.evaluate(KEYFILL, 1) == RGB('#0072b2'), page.evaluate(KEYFILL, 1))
        band = page.evaluate("() => { const b = [...document.querySelectorAll('#lec-view pre.mermaid')][2].querySelector('.lec-title-band'); return b && getComputedStyle(b).fill; }")
        check('제목 띠(8)는 색 6 따뜻한의 진한 색', band == RGB('#7c2d12'), band)
        vg = page.evaluate(FILLS, 4)
        check('Vega-Lite 색 3: 첫 계열만 주황, 다음은 회색', RGB('#c2410c') in vg and RGB('#6b7280') in vg, vg)
        ec = page.evaluate(FILLS, 5)
        check('ECharts 색 4: 선명한 구분의 두 색', RGB('#4e79a7') in ec and RGB('#f28e2b') in ec, ec)
        pl = page.evaluate(FILLS, 6)
        check('Plotly 색 5: 색약 친화의 두 색 (layout.colorway)', RGB('#0072b2') in pl and RGB('#e69f00') in pl, pl)
        nv = page.evaluate(FILLS, 7)
        check('줄 없는 차트는 문서의 색 2 — 남색', RGB('#17304f') in nv, nv)

        print('[우클릭 — 색 조합…]')
        def open_menu(i, item):
            page.locator(ALL).nth(i).click(button='right', position={'x': 5, 'y': 5})
            page.wait_for_selector('#lec-menu:not([hidden])', timeout=5000)
            page.locator('#lec-menu button', has_text=item).first.click()

        open_menu(2, '색 조합…')
        page.wait_for_selector('#lec-menu .menu-head:has-text("색 조합")', timeout=5000)
        page.locator('#lec-menu button', has_text='2. 보고서 남색').first.click()
        until(page, lambda: '%% 스타일: 8 · 색: 2\n' in src(), ms=8000)
        check('있는 표시 줄의 색만 바꾼다 (모양은 그대로)', '  %% 스타일: 8 · 색: 2\n' in src(), src()[src().find('한 줄에 둘'):][:120])
        settle(2, '8/2')
        open_menu(2, '색 조합…')
        follow = page.locator('#lec-menu button', has_text='문서의 기본 따르기')
        check("문서의 기본 줄이 있으면 '문서의 기본 따르기 (지금 2)'", follow.count() == 1 and '2' in follow.inner_text(), follow.count())
        follow.click()
        until(page, lambda: '%% 스타일: 8\n' in src(), ms=8000)
        check('그 조각만 지운다 — 모양 줄은 남는다', '  %% 스타일: 8\n  A[가<br>내용]' in src(), src()[src().find('한 줄에 둘'):][:120])
        settle(2, '8/2')
        open_menu(7, '색 조합…')
        page.locator('#lec-menu button', has_text='7. 차가운').first.click()
        until(page, lambda: '```vega-lite\n// 색: 7\n{ "data": {"values": [{"k": "a", "v": 3}, {"k": "b", "v": 2}]}' in src(), ms=8000)
        check('줄 없는 차트: 블록 맨 앞에 // 색 줄', '```vega-lite\n// 색: 7\n{ "data": {"values": [{"k": "a", "v": 3}, {"k": "b", "v": 2}]}' in src())
        settle(7, '-/7')
        check('그 차트는 다시 그려진다 (색 7 차가운)', RGB('#1e3a8a') in page.evaluate(FILLS, 7), page.evaluate(FILLS, 7))

        print('[방향 바꾸기]')
        open_menu(3, '세로로 바꾸기')
        until(page, lambda: '```mermaid\nflowchart TD\n  A[하나]' in src(), ms=8000)
        check("가로 흐름도의 '세로로 바꾸기' → flowchart TD", '```mermaid\nflowchart TD\n  A[하나]' in src())
        until(page, lambda: page.evaluate("() => { const s = [...document.querySelectorAll('#lec-view pre.mermaid')][3].querySelector('svg'); const v = s && s.viewBox.baseVal; return !!v && v.height > v.width; }"), ms=10000)
        open_menu(3, '가로로 바꾸기')
        until(page, lambda: '```mermaid\nflowchart LR\n  A[하나]' in src(), ms=8000)
        check("다시 '가로로 바꾸기' → flowchart LR", '```mermaid\nflowchart LR\n  A[하나]' in src())
        drawn()
        open_menu(8, '가로로 바꾸기')
        until(page, lambda: 'digraph g {\n  rankdir=LR\n  A -> B' in src(), ms=8000)
        check('Graphviz 에 rankdir 이 없으면(세로) 그래프 첫 줄 아래에 rankdir=LR', 'digraph g {\n  rankdir=LR\n  A -> B' in src(), src()[-60:])
        drawn()
        open_menu(8, '세로로 바꾸기')
        until(page, lambda: 'rankdir=TB' in src(), ms=8000)
        check('Graphviz 세로로 → rankdir=TB', 'digraph g {\n  rankdir=TB\n  A -> B' in src())
        drawn()
        page.locator('#lec-view pre.lec-chart').nth(0).click(button='right', position={'x': 5, 'y': 5})
        page.wait_for_selector('#lec-menu:not([hidden])', timeout=5000)
        items = page.evaluate("() => [...document.querySelectorAll('#lec-menu button')].map((b) => b.textContent.trim())")
        check("차트 메뉴에는 '색 조합…' 만 (도해 스타일·방향 없음)", any('색 조합' in x for x in items) and not any('도해 스타일' in x or '로 바꾸기' in x for x in items), items)
        page.keyboard.press('Escape')

        print('[설정 — 기본 색 조합]')
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open-settings', 'view'))")
        page.wait_for_selector('#lec-dstyle-preview pre.mermaid svg', timeout=15000)
        check('색 조합 여덟, 1 이 골라져 있고 견본 색이 보인다', page.eval_on_selector_all('#lec-dcolors option', 'os => os.length') == 8 and page.input_value('#lec-dcolors') == '1'
              and page.locator('#lec-dcolors-chips i').count() >= 5)
        page.select_option('#lec-dcolors', '4')
        until(page, lambda: json.loads((config / 'config.json').read_text(encoding='utf-8')).get('diagram_colors') == 4, ms=5000)
        check('고르면 설정 diagram_colors 에 숫자로', json.loads((config / 'config.json').read_text(encoding='utf-8')).get('diagram_colors') == 4)
        page.keyboard.press('Escape')
        drawn()
        check('문서의 기본 줄이 있는 문서는 그대로 (색 2)', marks()[0] == '3/2', marks())

        print('[어두운 스타일]')
        page.select_option('#lec-theme', 'dark')
        until(page, lambda: page.evaluate("() => document.documentElement.dataset.theme") == 'dark')
        until(page, lambda: page.evaluate(KEYFILL, 0) not in (None, RGB('#17304f')), ms=12000)
        fill = page.evaluate(KEYFILL, 0)
        rgb = [int(x) for x in fill[4:-1].split(',')] if fill and fill.startswith('rgb(') else [0, 0, 0]
        luma = (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) / 255
        check('어두운 스타일에서 남색은 밝게 (밝기 0.45 이상)', luma >= 0.44, (fill, round(luma, 2)))
        check('화면 스크립트 오류 없음', not errors, errors[:5])
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
