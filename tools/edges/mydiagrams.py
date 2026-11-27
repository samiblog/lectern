"""내 도해 스타일·내 색 조합 (D215) — 설정 폴더 diagram-styles 의 json 이 11번부터(모양)·9번부터(색)로 그려진다.
- 표시 줄 '%% 스타일: 11 우리 회사'·'// 색: 9 회사 색' 이 그 파일의 값으로 (바탕 번호 위에 모서리·선·점선·굵기·제목 띠·색). Graphviz·차트도.
- 없는 번호(파일이 없는 PC)는 기본으로. 고르기 창에 '내 것' 칸, 설정 창의 고르는 칸에 '내 것' 묶음과 고칠 것(틀린 파일·모르는 열쇠).
- 파일이 생기고 고쳐지고 지워지면 다시 불러오지 않아도 몇 초 안에 그림이 따른다. 설정의 기본 번호를 내 것으로 — 그 파일이 없어지면 1.
- '이 모양으로 내 도해 스타일 만들기…'·'이 색으로 내 색 조합 만들기…' 는 그 그림의 자리·안내·폴더·다음 번호를 담은 요청 글을 터미널에.
- 화면 스크립트 오류 없음."""
import json
import os
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop, until

FENCE = '```'
DOC = f"""# 내 스타일

{FENCE}mermaid
flowchart LR
  %% 스타일: 11 우리 회사
  A[자료 수집<br>통계 12건] --> B[분석]:::key
{FENCE}

{FENCE}mermaid
flowchart LR
  %% 스타일: 12 점선 · 색: 9 회사 색
  A[가] --> B[나]
{FENCE}

{FENCE}dot
digraph 가 {{
  // 스타일: 11
  A -> B
}}
{FENCE}

{FENCE}vega-lite
// 색: 9 회사 색
{{ "data": {{"values": [{{"k": "a", "v": 3}}, {{"k": "b", "v": 2}}]}}, "mark": "bar",
  "encoding": {{"x": {{"field": "k", "type": "nominal"}}, "y": {{"field": "v", "type": "quantitative"}}, "color": {{"field": "k", "type": "nominal"}}}} }}
{FENCE}

{FENCE}mermaid
flowchart LR
  %% 스타일: 14 아직 없음
  A[가] --> B[나]
{FENCE}

{FENCE}mermaid
flowchart LR
  A[줄 없음] --> B[나]
{FENCE}
"""
OURS = {'kind': 'style', 'number': 11, 'name': '우리 회사', 'tip': '남색 띠, 직각 선', 'base': 8, 'corner': 2, 'line': 'step', 'bold': True}
DASH = {'kind': 'style', 'number': 12, 'name': '점선', 'base': 2, 'dash': True, 'line_width': 2, 'line': 'straight'}
HALF = {'kind': 'style', 'number': 13, 'name': '반쯤', 'base': 3, 'css': '.node { fill: red }', 'shadow': False}
BAD = {'kind': 'style', 'number': 5, 'name': '틀린 번호'}
COLORS = {'kind': 'colors', 'number': 9, 'name': '회사 색', 'series': ['#0b5394', '#e69138', '#6aa84f'], 'strong': '#0b5394', 'accent': '#e69138'}
ALL = '#lec-view pre.mermaid, #lec-view pre.lec-chart'
MARKS = f"() => [...document.querySelectorAll('{ALL}')].map((n) => (n.dataset.diagramStyle || '-') + '/' + (n.dataset.diagramColors || '-'))"
SHOTS = os.environ.get('LEC_SHOTS')
RGB = lambda h: f'rgb({int(h[1:3], 16)}, {int(h[3:5], 16)}, {int(h[5:7], 16)})'   # noqa: E731

base = Path(tempfile.mkdtemp(prefix='lec-mydiag-'))
proj = base / '과제'
proj.mkdir()
doc = proj / '내스타일.md'
doc.write_text(DOC, encoding='utf-8', newline='\n')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False, 'theme': 'report', 'toc_visible': False}), encoding='utf-8')
folder = config / 'diagram-styles'
folder.mkdir()


def put(name, data):
    (folder / name).write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


for name, data in (('우리 회사.json', OURS), ('점선.json', DASH), ('반쯤.json', HALF), ('틀림.json', BAD), ('회사 색.json', COLORS)):
    put(name, data)

server, url, port = serve(proj, config)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1300, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        page.evaluate("() => import('/static/js/store.js').then((m) => { window.__pasted = []; m.on('term-paste', (x) => window.__pasted.push(x)); })")
        page.click('#lec-tree .row[data-doc="내스타일.md"]')

        def marks():
            return page.evaluate(MARKS)

        def drawn():
            return until(page, lambda: page.locator('#lec-view pre.mermaid.mermaid-ok').count() == 4 and page.locator('#lec-view pre.lec-chart.chart-ok').count() == 2, ms=30000)

        def css(i, sel, prop):
            return page.evaluate("([i, sel, prop]) => { const n = [...document.querySelectorAll('#lec-view pre.mermaid, #lec-view pre.lec-chart')][i]; const e = n && n.querySelector(sel); return e ? getComputedStyle(e)[prop] : null; }", [i, sel, prop])

        drawn()
        print('[그린 번호]')
        check('11·12(색 9)·Graphviz 11·차트 색 9·없는 14 는 설정(1)·줄 없음 1', marks() == ['11/1', '12/9', '11/1', '-/9', '1/1', '1/1'], marks())

        print('[내 스타일의 값]')
        check('11 우리 회사: 바탕 8 의 제목 띠', page.locator('#lec-view pre.mermaid >> nth=0').locator('.lec-title-band').count() >= 1)
        check('— 모서리 2px', css(0, 'g.node:not(.key) rect.label-container, g.node:not(.key) rect', 'rx') == '2px', css(0, 'g.node rect', 'rx'))
        check('— 상자 글자 굵게', int(css(0, 'g.node .nodeLabel', 'fontWeight') or 0) >= 600, css(0, 'g.node .nodeLabel', 'fontWeight'))
        dash = css(1, '.flowchart-link', 'strokeDasharray')
        check('12 점선: 선이 점선, 굵기 2px', dash not in (None, 'none') and css(1, '.flowchart-link', 'strokeWidth') == '2px', (dash, css(1, '.flowchart-link', 'strokeWidth')))
        check('색 9 회사 색: 상자 테두리가 strong', css(1, 'g.node rect', 'stroke') == RGB('#0b5394'), css(1, 'g.node rect', 'stroke'))
        bars = page.evaluate("() => [...[...document.querySelectorAll('#lec-view pre.lec-chart')][1].querySelectorAll('g.mark-rect path')].map((e) => getComputedStyle(e).fill)")
        check('차트의 // 색: 9 — 계열 색이 회사 색', bars[:2] == [RGB('#0b5394'), RGB('#e69138')], bars)
        check('Graphviz 도 11 — 제목 상자(띠)로 칠한다', page.evaluate("() => { const n = [...document.querySelectorAll('#lec-view pre.lec-chart')][0]; return n.dataset.diagramStyle === '11' && !!n.querySelector('svg style'); }"))

        print('[고르기 창 — 내 것 칸]')
        page.locator(ALL).nth(4).click(button='right', position={'x': 5, 'y': 5})
        page.wait_for_selector('#lec-menu:not([hidden])', timeout=5000)
        labels = page.evaluate("() => [...document.querySelectorAll('#lec-menu button')].map((b) => b.textContent.trim())")
        check("메뉴에 '이 모양으로 내 도해 스타일 만들기…'", any(x.startswith('이 모양으로 내 도해 스타일 만들기…') for x in labels), labels)
        page.locator('#lec-menu button', has_text='도해 스타일…').first.click()
        until(page, lambda: page.locator('#lec-dpick-grid.dpick-done').count() == 1, ms=30000)
        cards = page.evaluate("() => [...document.querySelectorAll('#lec-dpick .dpick-card')].map((c) => [c.dataset.n, !!c.querySelector('.dpick-name em'), c.querySelector('.dpick-stage pre')?.dataset.diagramStyle || ''])")
        check('기본 열 뒤에 내 것 셋(11·12·13) — 칸 이름에 \'내 것\', 그 번호로 그린다',
              [c[0] for c in cards] == [str(n) for n in range(1, 14)] and [c[1] for c in cards] == [False] * 10 + [True] * 3 and [c[2] for c in cards][10:] == ['11', '12', '13'], cards)
        check("틀린 파일(번호 5)은 칸이 없다 — 기본 5 는 그대로 '선만'", page.locator('#lec-dpick .dpick-card[data-n="5"] .dpick-name').inner_text().startswith('5 선만'))
        if SHOTS:
            page.screenshot(path=str(Path(SHOTS) / 'mydiag-pick.png'))
        make = page.locator('#lec-dpick-make')
        check("창의 '이 모양으로 내 도해 스타일 만들기…' 단추", make.is_visible() and make.inner_text() == '이 모양으로 내 도해 스타일 만들기…', make.inner_text())
        make.click()
        until(page, lambda: page.evaluate("() => window.__pasted.length") > 0, ms=5000)
        ask = page.evaluate("() => window.__pasted.at(-1)")
        check('요청 글: 안내·그 그림의 자리·다음 번호 14·폴더', 'diagram-styles.md' in ask and '@내스타일.md 28~32행' in ask and '번호는 14' in ask and 'diagram-styles' in ask.split('폴더는')[1], ask)
        check('창은 닫힌다', page.locator('#lec-dpick').is_hidden())
        page.locator(ALL).nth(3).click(button='right', position={'x': 5, 'y': 5})
        page.wait_for_selector('#lec-menu:not([hidden])', timeout=5000)
        page.locator('#lec-menu button', has_text='이 색으로 내 색 조합 만들기…').first.click()
        until(page, lambda: page.evaluate("() => window.__pasted.length") > 1, ms=5000)
        ask = page.evaluate("() => window.__pasted.at(-1)")
        check("차트는 '이 색으로 내 색 조합 만들기…' — 다음 색 번호 10", '내 색 조합' in ask and '번호는 10' in ask and '@내스타일.md 22~26행' in ask, ask)

        print('[설정 창 — 내 것 묶음·고칠 것]')
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open-settings', 'view'))")
        page.wait_for_selector('#lec-mydiag', state='visible', timeout=8000)
        info = page.locator('#lec-mydiag').inner_text()
        if SHOTS:
            page.locator('#lec-mydiag').scroll_into_view_if_needed()
            page.screenshot(path=str(Path(SHOTS) / 'mydiag-settings.png'))
        check('내 도해 스타일 3개 · 내 색 조합 1개', '내 도해 스타일 3개 · 내 색 조합 1개' in info, info)
        check('고칠 것: 틀린 번호의 파일, 모르는 열쇠 css', '틀림.json' in info and 'number' in info and '반쯤.json' in info and 'css' in info, info)
        groups = page.evaluate("() => [...document.querySelectorAll('#lec-dstyle optgroup')].map((g) => [g.label, [...g.querySelectorAll('option')].map((o) => o.value)])")
        check("모양 고르는 칸에 '내 것' 묶음 11·12·13", groups == [['내 것', ['11', '12', '13']]], groups)
        page.select_option('#lec-dstyle', '12')
        until(page, lambda: marks()[5] == '12/1', ms=15000)
        check('기본 번호를 내 것 12 로 — 줄 없는 그림·없는 번호(14)의 그림이 12', marks()[4:] == ['12/1', '12/1'], marks())
        page.keyboard.press('Escape')

        print('[파일이 바뀌면 — 다시 불러오지 않고]')
        put('새것.json', {'kind': 'style', 'number': 14, 'name': '아직 없음', 'base': 2})
        until(page, lambda: marks()[4] == '14/1', ms=10000)
        check('새 파일 14 — 몇 초 안에 그 그림이 14', marks()[4] == '14/1', marks())
        put('우리 회사.json', {**OURS, 'corner': 12})
        until(page, lambda: css(0, 'g.node:not(.key) rect', 'rx') == '12px', ms=10000)
        check('고친 값(모서리 12) — 몇 초 안에', css(0, 'g.node:not(.key) rect', 'rx') == '12px', css(0, 'g.node:not(.key) rect', 'rx'))
        (folder / '우리 회사.json').unlink()
        until(page, lambda: marks()[0] == '12/1', ms=10000)
        check('파일을 지우면 그 번호를 모른다 — 기본(설정 12)으로, 표시 줄은 그대로', marks()[0] == '12/1' and marks()[2] == '12/1' and '스타일: 11 우리 회사' in doc.read_text(encoding='utf-8'), marks())
        (folder / '점선.json').unlink()
        until(page, lambda: marks()[5] == '1/1', ms=10000)
        check('기본 번호의 파일이 없어지면 1 (설정 값은 그대로 12)', marks()[5] == '1/1' and json.loads((config / 'config.json').read_text(encoding='utf-8'))['diagram_style'] == 12, marks())
        check('화면 스크립트 오류 없음', not errors, errors[:5])
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
