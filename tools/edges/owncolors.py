"""원문이 정한 색·모양 (0.113.2 — 사용자 보고: 예전에 쓴 보고서의 차트는 '색 조합…' 여덟 칸이 같고 알림만 나왔다).
- 고르기 창의 알림이 원문의 몇째 줄 무엇인지 보인다 — 칸이 모두 같으면 '원문이 색을 정해 두어', 칸은 갈리지만 원문의 색이 남으면 옅은 알림.
- 원문의 색을 찾는 법: #rgb·#rrggbb·rgb()·색 이름(CSS 가 아는 것만 — Plotly 의 "fill": "tozeroy" 는 색이 아니다)·이름 붙은 색표(scheme),
  Mermaid 의 classDef·style·init 의 theme, Graphviz 의 node [style=…]. init 의 sequence 설정·node [shape=box] 는 아니다.
- 알림 옆의 'Claude 에 색 지정 빼기 요청' — 그 블록의 '@경로 줄' 과 작성 안내 4장을 적은 요청 글을 터미널에 (Enter 없이), 창은 닫힌다.
- 색 없이 나누는 법(작성 안내)으로 쓴 차트 — 막대와 선을 층마다 datum, 하나만 진하게(opacity) — 는 여덟 칸이 모두 다르고 알림이 없다.
- AI 요청 메뉴: 그림·차트가 있는 문서에 '그림·차트의 색 지정 빼기 요청' (문서 전체).
- 그림의 색 조합 창이 모두 같으면 '이 종류의 그림은 색 조합을' (캔들·폭포 문구는 차트만).
- 화면 스크립트 오류 없음."""
import json
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop, until

FENCE = '```'
V = '{"values": [{"k": "가", "v": 3, "s": 30}, {"k": "나", "v": 5, "s": 20}, {"k": "다", "v": 4, "s": 40}, {"k": "라", "v": 6, "s": 25}]}'
XY = '"encoding": {"x": {"field": "k", "type": "nominal"}, "y": {"field": "v", "type": "quantitative"}}'
BLOCKS = [   # (이름, 언어, 원문 줄들) — 원문의 색이 있는 줄은 OWN 에
    ('vl-own', 'vega-lite', ['{', f'"data": {V},', '"mark": {"type": "bar", "color": "#2f5d8a"},', XY, '}']),
    ('vl-scheme', 'vega-lite', ['{', f'"data": {V}, "mark": "bar",', '"encoding": {"x": {"field": "k", "type": "nominal"}, "y": {"field": "v", "type": "quantitative"},',
                                '  "color": {"field": "k", "type": "nominal", "scale": {"scheme": "tableau10"}}}', '}']),
    ('vl-partial', 'vega-lite', ['{', f'"data": {V}, "encoding": {{"x": {{"field": "k", "type": "nominal"}}}},', '"layer": [',
                                 '  {"mark": "bar", "encoding": {"y": {"field": "v", "type": "quantitative"}}},',
                                 '  {"mark": {"type": "line", "color": "#e45756"}, "encoding": {"y": {"field": "s", "type": "quantitative"}}}',
                                 '], "resolve": {"scale": {"y": "independent"}}', '}']),
    ('vl-datum', 'vega-lite', ['{', f'"data": {V}, "encoding": {{"x": {{"field": "k", "type": "nominal"}}}},', '"layer": [',
                               '  {"mark": "bar", "encoding": {"y": {"field": "v", "type": "quantitative"}, "color": {"datum": "물량"}}},',
                               '  {"mark": {"type": "line", "point": true}, "encoding": {"y": {"field": "s", "type": "quantitative"}, "color": {"datum": "단가"}}}',
                               '], "resolve": {"scale": {"y": "independent"}}', '}']),
    ('vl-opacity', 'vega-lite', ['{', f'"data": {V}, "mark": "bar",', '"encoding": {"x": {"field": "k", "type": "nominal"}, "y": {"field": "v", "type": "quantitative"},',
                                 '  "opacity": {"condition": {"test": "datum.k == \'라\'", "value": 1}, "value": 0.35}}', '}']),
    ('ec-named', 'echarts', ['{', '"xAxis": {"type": "category", "data": ["가", "나", "다"]}, "yAxis": {"type": "value"},',
                             '"series": [{"type": "bar", "data": [3, 5, 4], "itemStyle": {"color": "red"}}]', '}']),
    ('pl-fill', 'plotly', ['{', '"data": [{"type": "scatter", "x": [1, 2, 3], "y": [2, 4, 3], "fill": "tozeroy"}]', '}']),
    ('mm-own', 'mermaid', ['flowchart LR', '  A[수집] --> B[분석] --> C[보고]', '  classDef hot fill:#f96,stroke:#333', '  class A hot']),
    ('mm-seq', 'mermaid', ['%%{init: {"sequence": {"mirrorActors": false}}}%%', 'sequenceDiagram', '  participant U as 사람', '  participant C as Claude', '  U->>C: 요청']),
    ('dot-own', 'dot', ['digraph 흐름 {', '  node [style=filled, fillcolor="#dbe8f6"];', '  A -> B -> C', '}']),
    ('dot-shape', 'dot', ['digraph 흐름 {', '  node [shape=box];', '  A -> B -> C', '}']),
]
OWN = {'vl-own': 2, 'vl-scheme': 3, 'vl-partial': 4, 'ec-named': 2, 'mm-own': 2, 'dot-own': 1}   # 원문의 색이 든 줄 — 블록 안의 몇째(0부터)
LINES = ['# 원문의 색', '', '그림과 차트.', '']
SPANS = {}
for name, lang, body in BLOCKS:
    a = len(LINES) + 1   # 여는 줄의 번호 (1부터)
    LINES += [f'{FENCE}{lang}', *body, FENCE, '']
    SPANS[name] = (a, a + len(body) + 1)
DOC = '\n'.join(LINES) + '\n'
NAMES = [b[0] for b in BLOCKS]
ALL = '#lec-view pre.lec-chart, #lec-view pre.mermaid'
LOOKS = """() => [...document.querySelectorAll('#lec-dpick .dpick-card')].map((c) => {
  const svg = c.querySelector('.dpick-stage svg');
  if (!svg) return '';
  const out = new Set();
  for (const el of svg.querySelectorAll('path, rect, circle, polygon, line, image')) {
    if (el.tagName === 'image') { const h = el.getAttribute('href') || el.getAttribute('xlink:href') || ''; out.add('img' + h.length + h.slice(-24)); continue; }
    const st = getComputedStyle(el);
    for (const a of ['fill', 'stroke']) {
      const v = (st[a] || '').toLowerCase().replace(/\\s+/g, '');
      if (v && v !== 'none' && !/^(transparent|rgba\\(0,0,0,0\\))$/.test(v) && !v.startsWith('url(')) out.add(a[0] + v);
    }
  }
  return [...out].sort().join(' ');
})"""
PASTED = '() => window.__pasted'
MENU = "() => { const m = document.querySelector('#lec-menu'); return m && !m.hidden ? [...m.querySelectorAll('button[data-i]')].map((b) => b.textContent) : null; }"

base = Path(tempfile.mkdtemp(prefix='lec-owncolors-'))
proj = base / '과제'
proj.mkdir()
doc = proj / '차트.md'
doc.write_text(DOC, encoding='utf-8', newline='\n')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False, 'theme': 'report', 'toc_visible': False}), encoding='utf-8')

server, url, port = serve(proj, config)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1300, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        page.evaluate("() => import('/static/js/store.js').then((m) => { window.__pasted = []; m.on('term-paste', (d) => window.__pasted.push(typeof d === 'string' ? d : d.text)); })")
        page.click('#lec-tree .row[data-doc="차트.md"]')
        ok = until(page, lambda: page.evaluate(f"() => [...document.querySelectorAll('{ALL}')].filter((x) => x.classList.contains('chart-ok') || x.classList.contains('mermaid-ok')).length") == len(BLOCKS), ms=60000)
        check('그림·차트를 모두 그린다', ok, page.evaluate(f"() => [...document.querySelectorAll('{ALL}')].map((x) => x.className)"))

        def pick(name, item='색 조합…'):
            node = page.locator(ALL).nth(NAMES.index(name))
            node.scroll_into_view_if_needed()
            node.click(button='right', position={'x': 20, 'y': 20})
            page.wait_for_selector('#lec-menu:not([hidden])', timeout=5000)
            page.locator('#lec-menu button', has_text=item).first.click()
            page.wait_for_selector('#lec-dpick:not([hidden])', timeout=5000)
            until(page, lambda: page.locator('#lec-dpick-grid.dpick-done').count() == 1, ms=30000)
            page.wait_for_timeout(120)
            note = page.locator('#lec-dpick-same')
            shown = note.is_visible()
            return {'looks': page.evaluate(LOOKS), 'note': page.locator('#lec-dpick-same-text').inner_text() if shown else '',
                    'soft': shown and 'soft' in (note.get_attribute('class') or ''), 'ask': page.locator('#lec-dpick-uncolor').is_visible(),
                    'ask_text': page.locator('#lec-dpick-uncolor').inner_text() if page.locator('#lec-dpick-uncolor').is_visible() else ''}

        def close():
            page.keyboard.press('Escape')
            page.wait_for_timeout(80)

        def line_of(name):
            return SPANS[name][0] + 1 + OWN[name]

        print('[원문이 색을 정한 차트 — 몇째 줄의 무엇인지]')
        r = pick('vl-own')
        check('막대 색을 적은 차트: 여덟 칸이 같다', len(set(r['looks'])) == 1, r['looks'][:1])
        want = f'칸이 모두 같습니다 — 원문이 색을 정해 두어({line_of("vl-own")}째 줄 "mark": {{"type": "bar", "color": "#2f5d8a"}},) 색 조합을 따르지 않습니다'
        check('알림에 원문의 줄 번호와 그 줄', r['note'] == want, (r['note'], want))
        check("'Claude 에 색 지정 빼기 요청' 단추", r['ask'] and r['ask_text'] == 'Claude 에 색 지정 빼기 요청', r['ask_text'])
        page.locator('#lec-dpick-uncolor').click()
        until(page, lambda: len(page.evaluate(PASTED)) == 1, ms=5000)
        ask = (page.evaluate(PASTED) or [''])[-1]
        a, z = SPANS['vl-own']
        check('요청 글: 그 블록의 자리·작성 안내 4장의 색 없이 나누는 법·표시 줄은 그대로', f'@차트.md {a}~{z}행' in ask and "'색 없이 나누는 법'" in ask
              and 'writing.md' in ask and '표시 줄' in ask and '물어봐' in ask and not ask.endswith('\n'), ask)
        check('창은 닫힌다', page.locator('#lec-dpick').is_hidden())

        r = pick('vl-scheme')
        check("이름 붙은 색표(scheme)도 원문의 색 — 캔들 문구가 아니다", len(set(r['looks'])) == 1 and '원문이 색을 정해 두어' in r['note'] and 'scheme' in r['note'], r['note'])
        close()
        r = pick('ec-named')
        check('ECharts 의 색 이름("red")', len(set(r['looks'])) == 1 and f'{line_of("ec-named")}째 줄' in r['note'] and '"red"' in r['note'], r['note'])
        close()

        print('[칸은 갈리지만 원문의 색이 남는 차트 — 옅은 알림]')
        r = pick('vl-partial')
        check('막대는 색 조합을 따라 칸이 갈린다', len(set(r['looks'])) == 8, len(set(r['looks'])))
        check("옅은 알림: '원문이 정한 색은 그대로 남습니다 — N째 줄 …'", r['soft'] and r['note'].startswith(f'원문이 정한 색은 그대로 남습니다 — {line_of("vl-partial")}째 줄') and '#e45756' in r['note'], r)
        check('빼기 요청 단추도', r['ask'])
        close()

        print('[색 없이 나눈 차트 — 작성 안내대로]')
        for name, what in (('vl-datum', '막대와 선을 층마다 datum'), ('vl-opacity', '하나만 진하게 (opacity)'), ('pl-fill', 'Plotly 의 "fill": "tozeroy" (색이 아니다)')):
            r = pick(name)
            check(f'{what}: 여덟 칸이 모두 다르고 알림·단추 없음', len(set(r['looks'])) == 8 and not r['note'] and not r['ask'], (len(set(r['looks'])), r['note']))
            close()
        r = pick('vl-datum')
        layer = page.evaluate("""() => { const c = document.querySelector('#lec-dpick .dpick-card[data-n="2"] svg');
          return [...new Set([...c.querySelectorAll('path')].map((p) => (getComputedStyle(p).fill + '|' + getComputedStyle(p).stroke).replace(/\\s+/g, '')))]; }""")
        check('datum: 막대와 선이 색 조합 2 의 서로 다른 두 색', any('rgb(23,48,79)' in x for x in layer) and len([x for x in layer if 'none' not in x.split('|')[0] or 'none' not in x.split('|')[1]]) >= 2, layer[:6])
        close()

        print('[그림 — Mermaid·Graphviz]')
        r = pick('mm-own', '도해 스타일…')
        check("classDef 로 색을 정한 흐름도: '원문이 정한 모양·색은 그대로 남습니다' 와 그 줄", f'{line_of("mm-own")}째 줄 classDef hot' in r['note'] and r['ask']
              and r['ask_text'] == 'Claude 에 모양·색 지정 빼기 요청', r)
        page.locator('#lec-dpick-uncolor').click()
        until(page, lambda: len(page.evaluate(PASTED)) == 2, ms=5000)
        ask = page.evaluate(PASTED)[-1]
        check('모양 요청 글: classDef 를 빼고 강조 표시로', f'@차트.md {SPANS["mm-own"][0]}~{SPANS["mm-own"][1]}행' in ask and ':::key' in ask and '도해 스타일' in ask, ask)
        r = pick('mm-seq', '색 조합…')
        check("init 의 sequence 설정은 원문의 색이 아니다 — 단추 없음", not r['ask'] and '원문' not in r['note'], r)
        close()
        r = pick('mm-seq', '도해 스타일…')
        check('시퀀스의 도해 스타일: 원문 탓이 아니다', not r['ask'] and '원문' not in r['note'], r)
        close()
        r = pick('dot-own', '도해 스타일…')
        check('Graphviz node [style=filled, fillcolor=…]: 그 줄을 알린다', f'{line_of("dot-own")}째 줄 node [style=filled' in r['note'] and r['ask'], r['note'])
        close()
        r = pick('dot-shape', '도해 스타일…')
        check('node [shape=box] 만 적은 그림: 알림·단추 없음', not r['note'] and not r['ask'], r['note'])
        close()
        check('창을 닫으면 알림·단추도 감춘다', page.locator('#lec-dpick-same').is_hidden() and page.locator('#lec-dpick-uncolor').is_hidden())

        print('[AI 요청 메뉴 — 문서 전체]')
        page.click('#lec-btn-ai')
        until(page, lambda: page.evaluate(MENU) is not None)
        rows = page.evaluate(MENU) or []
        check("그림·차트가 있는 문서: '그림·차트의 색 지정 빼기 요청'", any(x.startswith('그림·차트의 색 지정 빼기 요청') for x in rows), rows)
        page.locator('#lec-menu button[data-i]', has_text='그림·차트의 색 지정 빼기 요청').click()
        until(page, lambda: len(page.evaluate(PASTED)) == 3, ms=5000)
        ask = page.evaluate(PASTED)[-1]
        check('요청 글: @차트.md 의 그림·차트 — 줄 범위 없이 문서 전체', '@차트.md 의 그림·차트' in ask and '행' not in ask.split('@차트.md')[1][:6], ask)
        check('화면 스크립트 오류 없음', not errors, errors[:5])
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
