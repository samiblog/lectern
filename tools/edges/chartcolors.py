"""차트의 색 조합 (0.113.1 — 사용자 보고: 보고서 차트의 '색 조합…' 창이 여덟 칸 모두 같았다).
- Vega-Lite 의 색으로 나누지 않은 차트(막대 하나·선 하나·넓이·점)도 색 조합을 따른다 — 그 색 조합의 첫 색. 1 은 라이브러리의 기본색 그대로.
- 열지도도: Vega-Lite(전부터)·ECharts(visualMap)·Plotly(colorscale) 가 색 조합의 두 끝으로. 원문이 색을 정했으면 그것.
- 고르기 창의 칸이 모두 같으면 까닭을 창 위에 — 원문이 색을 정한 차트, 오름·내림 색이 정해진 차트(캔들·폭포). 칸이 갈리면 알리지 않는다.
- 고르면 블록에 '// 색: 2 보고서 남색' 이 적히고 문서의 차트가 그 색으로 다시 그려진다.
- 정화: 따옴표를 붙인 그림 안 참조 url('#id') 는 남기고 (Plotly 의 색 막대가 검게 나왔다), 바깥 주소 url('http…') 는 따옴표가 있든 없든 지운다.
- 화면 스크립트 오류 없음."""
import json
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop, until

FENCE = '```'
V = '{"values": [{"k": "가", "v": 3, "g": "A"}, {"k": "나", "v": 5, "g": "B"}, {"k": "다", "v": 4, "g": "A"}, {"k": "라", "v": 6, "g": "B"}]}'
X = '["가", "나", "다", "라"]'
CHARTS = [
    ('vl-bar', 'vega-lite', '{"data": %s, "mark": "bar", "encoding": {"x": {"field": "k", "type": "nominal"}, "y": {"field": "v", "type": "quantitative"}}}' % V),
    ('vl-line', 'vega-lite', '{"data": %s, "mark": {"type": "line", "point": true}, "encoding": {"x": {"field": "k", "type": "ordinal"}, "y": {"field": "v", "type": "quantitative"}}}' % V),
    ('vl-own', 'vega-lite', '{"data": %s, "mark": {"type": "bar", "color": "#2f5d8a"}, "encoding": {"x": {"field": "k", "type": "nominal"}, "y": {"field": "v", "type": "quantitative"}}}' % V),
    ('vl-split', 'vega-lite', '{"data": %s, "mark": "bar", "encoding": {"x": {"field": "k", "type": "nominal"}, "y": {"field": "v", "type": "quantitative"}, "color": {"field": "g", "type": "nominal"}}}' % V),
    ('ec-heat', 'echarts', '{"xAxis": {"type": "category", "data": %s}, "yAxis": {"type": "category", "data": ["A", "B"]}, "visualMap": {"min": 0, "max": 6, "show": false}, "series": [{"type": "heatmap", "data": [[0, 0, 1], [1, 0, 5], [2, 1, 3], [3, 1, 6]]}]}' % X),
    ('ec-candle', 'echarts', '{"xAxis": {"type": "category", "data": %s}, "yAxis": {"type": "value", "scale": true}, "series": [{"type": "candlestick", "data": [[20, 34, 10, 38], [40, 35, 30, 50], [31, 38, 33, 44], [38, 15, 5, 42]]}]}' % X),
    ('pl-heat', 'plotly', '{"data": [{"type": "heatmap", "z": [[1, 2, 3], [3, 2, 1]]}]}'),
]
SVG_REFS = """<svg width="120" height="30"><defs><linearGradient id="lg1"><stop offset="0" stop-color="#2b5c8a"/><stop offset="1" stop-color="#c2410c"/></linearGradient></defs>\
<rect id="r-quoted" width="40" height="30" style="fill: url('#lg1')"/><rect id="r-double" x="40" width="40" height="30" fill='url("#lg1")'/>\
<rect id="r-far" x="80" width="40" height="30" style="fill: url('http://127.0.0.1:9/leak.svg#g')"/><rect id="r-far2" x="80" width="40" height="30" style="fill: url( 'leak.svg#g')"/></svg>"""
DOC = '# 차트 색\n\n' + ''.join(f'{FENCE}{kind}\n{body}\n{FENCE}\n\n' for _, kind, body in CHARTS) + f'{FENCE}mermaid\nflowchart LR\n  A --> B:::key\n{FENCE}\n\n{SVG_REFS}\n'
NAMES = [c[0] for c in CHARTS]
ALL = '#lec-view pre.lec-chart, #lec-view pre.mermaid'
# 칸마다 칠한 색 (속성·style 의 fill·stroke, Plotly 열지도의 PNG 주소) — 정렬한 글자
LOOKS = """() => [...document.querySelectorAll('#lec-dpick .dpick-card')].map((c) => {
  const svg = c.querySelector('.dpick-stage svg');
  if (!svg) return '';
  const out = new Set();
  for (const el of svg.querySelectorAll('path, rect, circle, polygon, line, image')) {
    if (el.tagName === 'image') { const h = el.getAttribute('href') || el.getAttribute('xlink:href') || ''; out.add('img' + h.length + h.slice(-24)); continue; }
    for (const a of ['fill', 'stroke']) {
      const v = (el.style.getPropertyValue(a) || el.getAttribute(a) || '').toLowerCase().replace(/\\s+/g, '');
      if (v && v !== 'none' && !/^(transparent|rgba\\(0,0,0,0\\))$/.test(v) && !v.startsWith('url(')) out.add(a[0] + v);
    }
  }
  return [...out].sort().join(' ');
})"""
HEX = lambda h: f'rgb({int(h[1:3], 16)},{int(h[3:5], 16)},{int(h[5:7], 16)})'   # noqa: E731

base = Path(tempfile.mkdtemp(prefix='lec-chartcolors-'))
proj = base / '과제'
proj.mkdir()
doc = proj / '차트.md'
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
        page.click('#lec-tree .row[data-doc="차트.md"]')

        def drawn():
            return until(page, lambda: page.locator('#lec-view pre.lec-chart.chart-ok').count() == len(CHARTS) and page.locator('#lec-view pre.mermaid.mermaid-ok').count() == 1, ms=60000)

        def pick(name, item='색 조합…'):
            i = NAMES.index(name) if name in NAMES else len(NAMES)
            node = page.locator(ALL).nth(i)
            node.scroll_into_view_if_needed()
            node.click(button='right', position={'x': 20, 'y': 20})
            page.wait_for_selector('#lec-menu:not([hidden])', timeout=5000)
            page.locator('#lec-menu button', has_text=item).first.click()
            page.wait_for_selector('#lec-dpick:not([hidden])', timeout=5000)
            until(page, lambda: page.locator('#lec-dpick-grid.dpick-done').count() == 1, ms=30000)
            page.wait_for_timeout(120)
            looks = page.evaluate(LOOKS)
            note = page.locator('#lec-dpick-same')
            return looks, (note.inner_text() if note.is_visible() else '')

        def close():
            page.keyboard.press('Escape')
            page.wait_for_timeout(80)

        check('차트·그림을 모두 그린다', drawn())

        print('[색으로 나누지 않은 Vega-Lite — 막대 하나·선 하나]')
        looks, note = pick('vl-bar')
        check('막대 하나: 여덟 칸이 모두 다르다', len(looks) == 8 and len(set(looks)) == 8, looks)
        check("1 은 Vega 의 기본색(#4c78a8), 2 는 보고서 남색의 첫 색(#17304f)", 'f#4c78a8' in looks[0] and 'f#17304f' in looks[1], looks[:2])
        check('칸이 갈리면 알리지 않는다', not note, note)
        page.locator('#lec-dpick .dpick-card[data-n="2"]').click()
        until(page, lambda: '```vega-lite\n// 색: 2 보고서 남색\n{' in src(), ms=8000)
        check("고르면 '// 색: 2 보고서 남색' 이 블록 맨 앞에", '```vega-lite\n// 색: 2 보고서 남색\n{' in src(), src()[:200])
        until(page, lambda: page.evaluate("() => document.querySelector('#lec-view pre.lec-chart').dataset.diagramColors") == '2', ms=12000)
        fill = page.evaluate("() => [...document.querySelectorAll('#lec-view pre.lec-chart')][0].querySelector('svg path[aria-roledescription=\"bar\"], svg .mark-rect path')?.getAttribute('fill') || ''")
        check('문서의 막대가 그 색으로 다시 그려진다', fill.lower() == '#17304f', fill)
        looks, note = pick('vl-line')
        check('선 하나: 여덟 칸이 모두 다르고 5 는 색약 친화의 첫 색(#0072b2)', len(set(looks)) == 8 and 's#0072b2' in looks[4], looks[4])
        close()

        print('[원문이 색을 정한 차트 — 원문의 색이 먼저, 창이 까닭을 알린다]')
        looks, note = pick('vl-own')
        check('막대 색을 적은 차트: 여덟 칸이 같다 (원문의 #2f5d8a)', len(set(looks)) == 1 and 'f#2f5d8a' in looks[0], looks[0])
        check("창 위에 '원문이 색을 정해 두어' 알림", note.startswith('칸이 모두 같습니다 — 원문이 색을 정해 두어'), note)
        before = src()
        page.locator('#lec-dpick .dpick-card[data-n="3"]').click()
        until(page, lambda: src() != before, ms=8000)
        check("그래도 고를 수는 있다 (표시 줄만 — 원문의 색은 그대로)", '// 색: 3 회색 + 강조\n{"data"' in src() and '"color": "#2f5d8a"' in src(), src()[-900:-600])
        until(page, lambda: page.evaluate("() => [...document.querySelectorAll('#lec-view pre.lec-chart')][2]?.dataset.diagramColors") == '3', ms=12000)
        drawn()
        looks, note = pick('vl-split')
        check('색으로 나눈 막대: 여덟 칸이 다르고 알림 없음', len(set(looks)) == 8 and not note, (len(set(looks)), note))
        close()

        print('[열지도 — 연속 값의 색]')
        looks, note = pick('ec-heat')
        check('ECharts 열지도: 여덟 칸이 모두 다르다 (visualMap 이 색 조합의 두 끝)', len(set(looks)) == 8, looks[:2])
        check('ECharts 열지도 2 의 진한 끝은 보고서 남색(#17304f)', 'f#17304f' in looks[1] or 'frgb(23,48,79)' in looks[1], looks[1])
        close()
        looks, note = pick('pl-heat')
        check('Plotly 열지도: 여덟 칸이 모두 다르다 (colorscale)', len(set(looks)) == 8, [x[:60] for x in looks[:2]])
        close()
        bar = page.evaluate("""() => { const svg = [...document.querySelectorAll('#lec-view pre.lec-chart')][6].querySelector('svg');
          const r = svg.querySelector('.cbfill, rect.cbfill'); return r ? (r.getAttribute('style') || '') : 'none'; }""")
        check("Plotly 의 색 막대: url('#…') 그러데이션이 남는다 (검은 막대가 아니게)", "url('#" in bar or 'url("#' in bar, bar)

        print('[오름·내림 색이 정해진 차트]')
        looks, note = pick('ec-candle')
        check('캔들: 여덟 칸이 같다', len(set(looks)) == 1, looks[0][:80])
        check("창 위에 '정해진 색을 써서' 알림", note.startswith('칸이 모두 같습니다 — 이 종류의 차트는 정해진 색을 써서'), note)
        close()
        check('창을 닫으면 알림도 감춘다', page.locator('#lec-dpick-same').is_hidden())

        print('[도해 — 알림 없음]')
        looks, note = pick('mermaid', '도해 스타일…')
        check('흐름도의 도해 스타일 창에는 알림이 없다', not note, note)
        close()
        looks, note = pick('mermaid', '색 조합…')
        check('흐름도의 색 조합 창에도 알림이 없다', not note, note)
        close()

        print('[정화 — 그림 안 참조와 바깥 주소]')
        refs = page.evaluate("""() => Object.fromEntries(['r-quoted', 'r-double', 'r-far', 'r-far2'].map((id) => {
          const el = document.querySelector('#lec-view svg #' + id); return [id, el ? (el.getAttribute('style') || '') + '|' + (el.getAttribute('fill') || '') : null]; }))""")
        check("url('#lg1') 은 남는다", "url('#lg1')" in (refs['r-quoted'] or '') or 'url("#lg1")' in (refs['r-quoted'] or ''), refs)
        check('url("#lg1") 속성도 남는다', '#lg1' in (refs['r-double'] or ''), refs)
        check("바깥 주소 url('http…') 는 지운다", refs['r-far'] is not None and 'url(' not in refs['r-far'], refs)
        check("따옴표와 빈칸을 둔 url( 'leak.svg#g') 도 지운다", refs['r-far2'] is not None and 'url(' not in refs['r-far2'], refs)
        check('화면 스크립트 오류 없음', not errors, errors[:5])
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
