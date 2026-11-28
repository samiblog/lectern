"""0.113.1 사람 시나리오 — 연구원 C 가 지난달 Claude 가 쓴 월간 보고서의 차트 색을 정리한다 (D216 — 사용자 보고: '색 조합…' 창이 여덟 칸 모두 같았다).
차례대로 한 사람이 할 법한 일:

1. 보고서를 연다 — 차트 일곱, 표시 줄 없음. 계열이 하나인 막대는 라이브러리의 기본 파랑.
2. 그 막대의 '색 조합…' — 여덟 칸이 저마다 다르다 (알림 없음). → Enter 로 2 보고서 남색 → 문서의 막대가 남색.
3. 선 하나짜리 운임 지수 — 마우스로 5 색약 친화 → 선이 그 색.
4. 막대 + 빨간 선(Claude 가 선 색을 적었다) — 막대만 바뀌는 칸들, 3 회색 + 강조 → 막대는 주황, 선은 빨강 그대로.
5. Ctrl+Z 로 4 를 되돌리고 Ctrl+Y 로 다시.
6. 항만별 처리량(ECharts, 막대 색을 적었다) — 칸이 모두 같고 창 위에 '원문이 색을 정해 두어'. Esc. Claude 에게 색을 빼 달라고 한다 (파일이 바뀜)
   → 다시 열면 여덟 칸이 갈리고 알림 없음, 6 따뜻한.
7. 열지도(Plotly) — 여덟 칸이 다르고, 문서의 색 막대(범례)가 검지 않다. 7 차가운 → 열지도가 다시 칠해진다.
8. 주간 가격(캔들) — 칸이 같고 '정해진 색을 써서'. 바깥을 눌러 닫는다 — 파일은 그대로.
9. 설정의 기본 색 조합을 4 로 — 표시 줄이 없는 차트(유형별 물동량)만 따른다.
10. 어두운 스타일 — 남색 막대는 읽히게 밝아지고, 색 막대는 그대로 그러데이션.
11. 'html로 저장' 의 글에도 남색 막대와 색 막대의 그러데이션, 표시 줄은 없다.
12. 원문은 표시 줄과 Claude 가 뺀 색뿐. 화면 스크립트 오류 없음."""
import json
import re
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop, until

FENCE = '```'
OWN = ', "itemStyle": {"color": "#2f5d8a"}'
REPORT = f"""# 10월 항만 물동량 월간 보고

## 1. 물동량

{FENCE}vega-lite
{{ "title": "월별 물동량 (천 톤)", "width": "container", "height": 200,
  "data": {{"values": [{{"월": "7월", "물동량": 5120}}, {{"월": "8월", "물동량": 4870}}, {{"월": "9월", "물동량": 5390}}, {{"월": "10월", "물동량": 5610}}]}},
  "mark": "bar",
  "encoding": {{"x": {{"field": "월", "type": "ordinal", "title": null}}, "y": {{"field": "물동량", "type": "quantitative"}}}} }}
{FENCE}

{FENCE}vega-lite
{{ "title": "운임 지수", "width": "container", "height": 180,
  "data": {{"values": [{{"주": "1주", "지수": 1010}}, {{"주": "2주", "지수": 1045}}, {{"주": "3주", "지수": 1032}}, {{"주": "4주", "지수": 1080}}]}},
  "mark": {{"type": "line", "point": true}},
  "encoding": {{"x": {{"field": "주", "type": "ordinal", "title": null}}, "y": {{"field": "지수", "type": "quantitative", "scale": {{"zero": false}}}}}} }}
{FENCE}

## 2. 가격

{FENCE}vega-lite
{{ "title": "가격과 재고", "width": "container", "height": 200,
  "data": {{"values": [{{"분기": "1Q", "가격": 8950, "재고": 21.4}}, {{"분기": "2Q", "가격": 9420, "재고": 18.9}}, {{"분기": "3Q", "가격": 9100, "재고": 19.6}}]}},
  "encoding": {{"x": {{"field": "분기", "type": "ordinal", "title": null}}}},
  "layer": [
    {{"mark": {{"type": "bar", "opacity": 0.85}}, "encoding": {{"y": {{"field": "가격", "type": "quantitative"}}}}}},
    {{"mark": {{"type": "line", "point": true, "color": "#e45756"}}, "encoding": {{"y": {{"field": "재고", "type": "quantitative"}}}}}}
  ],
  "resolve": {{"scale": {{"y": "independent"}}}} }}
{FENCE}

## 3. 항만

{FENCE}echarts
{{ "title": {{"text": "항만별 처리량"}},
  "xAxis": {{"type": "category", "data": ["광양", "포항", "평택·당진"]}}, "yAxis": {{"type": "value"}},
  "series": [{{"type": "bar"{OWN}, "data": [120, 95, 80]}}] }}
{FENCE}

{FENCE}plotly
{{ "data": [{{"type": "heatmap", "x": ["7월", "8월", "9월"], "y": ["광양", "포항"], "z": [[5, 7, 6], [3, 4, 8]]}}],
  "layout": {{"title": {{"text": "항만·월별 지연 일수"}}, "height": 260}} }}
{FENCE}

## 4. 시장

{FENCE}echarts
{{ "title": {{"text": "주간 가격"}}, "xAxis": {{"type": "category", "data": ["1주", "2주", "3주", "4주"]}}, "yAxis": {{"type": "value", "scale": true}},
  "series": [{{"type": "candlestick", "data": [[9420, 9510, 9380, 9560], [9510, 9470, 9400, 9590], [9470, 9620, 9450, 9680], [9620, 9580, 9510, 9700]]}}] }}
{FENCE}

{FENCE}vega-lite
{{ "title": "유형별 물동량", "width": "container", "height": 200,
  "data": {{"values": [{{"월": "9월", "유형": "수입", "값": 50}}, {{"월": "9월", "유형": "수출", "값": 12}}, {{"월": "10월", "유형": "수입", "값": 48}}, {{"월": "10월", "유형": "수출", "값": 15}}]}},
  "mark": "bar",
  "encoding": {{"x": {{"field": "월", "type": "ordinal", "title": null}}, "y": {{"field": "값", "type": "quantitative"}}, "color": {{"field": "유형", "type": "nominal"}}}} }}
{FENCE}
"""
N = 7
CH = '#lec-view pre.lec-chart'
MARKS = f"() => [...document.querySelectorAll('{CH}')].map((n) => n.dataset.diagramColors || '-')"
# 차트 하나에 칠한 색 (속성·style 의 fill·stroke) — '#rrggbb' 나 'rgb(r,g,b)'
COLORS = f"""(i) => {{ const svg = [...document.querySelectorAll('{CH}')][i]?.querySelector('svg'); if (!svg) return [];
  const out = new Set(); for (const el of svg.querySelectorAll('path, rect, circle, line, polygon, polyline')) for (const a of ['fill', 'stroke']) {{
    const v = (el.style.getPropertyValue(a) || el.getAttribute(a) || '').toLowerCase().replace(/\\s+/g, ''); if (v && v !== 'none' && !v.startsWith('url(')) out.add(v); }}
  return [...out]; }}"""
IMAGE = f"(i) => {{ const im = [...document.querySelectorAll('{CH}')][i]?.querySelector('svg image'); return im ? (im.getAttribute('href') || im.getAttribute('xlink:href') || '') : ''; }}"
CBAR = f"(i) => [...document.querySelectorAll('{CH}')][i]?.querySelector('svg rect.cbfill')?.getAttribute('style') || ''"
LOOKS = """() => [...document.querySelectorAll('#lec-dpick .dpick-card')].map((c) => {
  const svg = c.querySelector('.dpick-stage svg'); if (!svg) return '';
  const out = new Set();
  for (const el of svg.querySelectorAll('path, rect, circle, polygon, line, image')) {
    if (el.tagName === 'image') { const h = el.getAttribute('href') || el.getAttribute('xlink:href') || ''; out.add('img' + h.length + h.slice(-24)); continue; }
    for (const a of ['fill', 'stroke']) { const v = (el.style.getPropertyValue(a) || el.getAttribute(a) || '').toLowerCase().replace(/\\s+/g, ''); if (v && v !== 'none' && !v.startsWith('url(')) out.add(a[0] + v); }
  }
  return [...out].sort().join(' '); })"""
NOTE = "() => { const n = document.querySelector('#lec-dpick-same'); return n && !n.hidden ? n.textContent : ''; }"
MARK_LINE = re.compile(r'^\s*//\s*색\s*:')


def rgb(h):
    return f'rgb({int(h[1:3], 16)},{int(h[3:5], 16)},{int(h[5:7], 16)})'


def has(colors, h):
    return h.lower() in colors or rgb(h) in colors


def luma(c):
    m = re.match(r'#([\da-f]{2})([\da-f]{2})([\da-f]{2})$', c) or re.match(r'rgb\((\d+),(\d+),(\d+)\)$', c)
    if not m:
        return None
    v = [int(x, 16) if c.startswith('#') else int(x) for x in m.groups()]
    return (0.299 * v[0] + 0.587 * v[1] + 0.114 * v[2]) / 255


base = Path(tempfile.mkdtemp(prefix='lec-scen1131-'))
proj = base / '과제'
proj.mkdir()
rep = proj / '월간-보고.md'
rep.write_text(REPORT, encoding='utf-8', newline='\n')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False, 'theme': 'report', 'toc_visible': False, 'language': 'ko'}), encoding='utf-8')
src = lambda: rep.read_text(encoding='utf-8').replace('\r\n', '\n')   # noqa: E731

server, url, port = serve(proj, config)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1280, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)

        def drawn():
            return until(page, lambda: page.locator(f'{CH}.chart-ok').count() == N, ms=60000)

        def marks():
            return page.evaluate(MARKS)

        def colors(i):
            return page.evaluate(COLORS, i)

        def settle(want):
            until(page, lambda: marks() == want, ms=15000)
            drawn()
            page.wait_for_timeout(150)

        def picker(i):
            node = page.locator(CH).nth(i)
            node.scroll_into_view_if_needed()
            node.click(button='right', position={'x': 30, 'y': 30})
            page.wait_for_selector('#lec-menu:not([hidden])', timeout=5000)
            page.locator('#lec-menu button', has_text='색 조합…').first.click()
            page.wait_for_selector('#lec-dpick:not([hidden])', timeout=5000)
            until(page, lambda: page.locator('#lec-dpick-grid.dpick-done').count() == 1, ms=30000)
            page.wait_for_timeout(150)
            return page.evaluate(LOOKS), page.evaluate(NOTE)

        print('[1. 보고서를 연다]')
        page.click('#lec-tree .row[data-doc="월간-보고.md"]')
        check('차트 일곱을 모두 그린다', drawn())
        check('표시 줄이 없어 모두 1 (설정)', marks() == ['1'] * N, marks())
        check('계열이 하나인 막대는 Vega 의 기본 파랑 (#4c78a8)', has(colors(0), '#4c78a8'), colors(0))

        print('[2. 월별 물동량 — 키로 2 보고서 남색]')
        looks, note = picker(0)
        check('여덟 칸이 저마다 다르다 — 0.113.0 에서는 모두 같았다', len(looks) == 8 and len(set(looks)) == 8, looks)
        check('칸이 갈리면 알림이 없다', not note, note)
        check('처음 초점은 지금 번호 1', page.evaluate("() => document.activeElement?.dataset?.n || ''") == '1')
        page.keyboard.press('ArrowRight')
        page.keyboard.press('Enter')
        until(page, lambda: '```vega-lite\n// 색: 2 보고서 남색\n{ "title": "월별' in src(), ms=8000)
        check("Enter — 블록 맨 앞에 '// 색: 2 보고서 남색'", '```vega-lite\n// 색: 2 보고서 남색\n{ "title": "월별' in src(), src()[:200])
        settle(['2'] + ['1'] * 6)
        check('문서의 막대가 남색 (#17304f)', has(colors(0), '#17304f') and not has(colors(0), '#4c78a8'), colors(0))

        print('[3. 운임 지수 — 선 하나, 5 색약 친화]')
        looks, note = picker(1)
        check('선 하나도 여덟 칸이 다르다', len(set(looks)) == 8 and not note, (len(set(looks)), note))
        page.locator('#lec-dpick .dpick-card[data-n="5"]').click()
        settle(['2', '5'] + ['1'] * 5)
        check('선과 점이 색약 친화의 첫 색 (#0072b2)', has(colors(1), '#0072b2'), colors(1))

        print('[4. 가격과 재고 — 막대만 바뀌고 Claude 가 적은 빨간 선은 그대로]')
        looks, note = picker(2)
        check('막대가 바뀌니 여덟 칸이 다르다 — Claude 가 적은 선의 색은 남는다고 옅게 알린다 (0.113.2)', len(set(looks)) == 8 and note.startswith('원문이 정한 색은 그대로 남습니다 — ') and '째 줄' in note, (len(set(looks)), note))
        check('모든 칸에 빨간 선 (#e45756)', all('#e45756' in x for x in looks), [x[:80] for x in looks[:2]])
        page.locator('#lec-dpick .dpick-card[data-n="3"]').click()
        settle(['2', '5', '3'] + ['1'] * 4)
        c2 = colors(2)
        check('막대는 회색 + 강조의 첫 색(주황 #c2410c), 선은 빨강', has(c2, '#c2410c') and has(c2, '#e45756'), c2)

        print('[5. Ctrl+Z · Ctrl+Y]')
        page.locator('#lec-view h1').click()
        page.keyboard.press('Control+z')
        until(page, lambda: '// 색: 3' not in src(), ms=8000)
        settle(['2', '5'] + ['1'] * 5)
        check('Ctrl+Z — 그 줄만 없어지고 막대는 기본 파랑', '// 색: 3' not in src() and has(colors(2), '#4c78a8'), colors(2))
        page.keyboard.press('Control+y')
        until(page, lambda: '// 색: 3 회색 + 강조' in src(), ms=8000)
        settle(['2', '5', '3'] + ['1'] * 4)
        check('Ctrl+Y — 다시 주황', has(colors(2), '#c2410c'), colors(2))

        print('[6. 항만별 처리량 — 원문이 색을 정했다]')
        looks, note = picker(3)
        check('여덟 칸이 같다 (원문의 #2f5d8a)', len(set(looks)) == 1 and '#2f5d8a' in looks[0], looks[0][:80])
        check("창 위에 '원문이 색을 정해 두어(N째 줄 …)' 와 빼기 요청 단추", note.startswith('칸이 모두 같습니다 — 원문이 색을 정해 두어(') and '째 줄' in note and '#2f5d8a' in note
              and page.locator('#lec-dpick-uncolor').is_visible(), note)
        before = src()
        page.keyboard.press('Escape')
        check('Esc — 파일은 그대로', src() == before and page.locator('#lec-dpick').is_hidden())
        rep.write_text(src().replace(OWN, ''), encoding='utf-8', newline='\n')   # Claude 가 막대 색을 뺐다 (터미널에서)
        until(page, lambda: not has(colors(3), '#2f5d8a') and len(colors(3)) > 0, ms=15000)
        drawn()
        check('색을 빼자 ECharts 의 기본색으로', not has(colors(3), '#2f5d8a'), colors(3))
        looks, note = picker(3)
        check('이제 여덟 칸이 다르고 알림이 없다', len(set(looks)) == 8 and not note, (len(set(looks)), note))
        page.locator('#lec-dpick .dpick-card[data-n="6"]').click()
        settle(['2', '5', '3', '6', '1', '1', '1'])
        check('막대가 따뜻한의 첫 색 (#7c2d12)', has(colors(3), '#7c2d12'), colors(3))

        print('[7. 지연 일수 — 열지도]')
        bar0 = page.evaluate(CBAR, 4)
        check("문서의 색 막대가 그러데이션 (url('#…') 이 남았다 — 검은 막대가 아니게)", "url('#" in bar0 or 'url("#' in bar0, bar0)
        img0 = page.evaluate(IMAGE, 4)
        looks, note = picker(4)
        check('열지도도 여덟 칸이 다르다', len(set(looks)) == 8 and not note, (len(set(looks)), note))
        page.locator('#lec-dpick .dpick-card[data-n="7"]').click()
        settle(['2', '5', '3', '6', '7', '1', '1'])
        until(page, lambda: page.evaluate(IMAGE, 4) not in ('', img0), ms=12000)
        check('열지도가 다시 칠해진다 (그림이 바뀜)', page.evaluate(IMAGE, 4) not in ('', img0))

        print('[8. 주간 가격 — 캔들]')
        before = src()
        looks, note = picker(5)
        check('캔들은 여덟 칸이 같다', len(set(looks)) == 1, looks[0][:80])
        check("창 위에 '정해진 색을 써서 (캔들·폭포의 오름·내림 색 등)'", '정해진 색을 써서' in note and '캔들' in note, note)
        page.mouse.click(8, 450)   # 창 바깥
        until(page, lambda: page.locator('#lec-dpick').is_hidden(), ms=3000)
        check('바깥을 누르면 닫고 파일은 그대로', page.locator('#lec-dpick').is_hidden() and src() == before)
        check('닫으면 알림도 감춘다', page.locator('#lec-dpick-same').is_hidden())

        print('[9. 설정의 기본 색 조합 4]')
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open-settings', 'view'))")
        page.wait_for_selector('#lec-dcolors', state='visible', timeout=15000)
        page.select_option('#lec-dcolors', '4')
        until(page, lambda: json.loads((config / 'config.json').read_text(encoding='utf-8')).get('diagram_colors') == 4, ms=5000)
        page.keyboard.press('Escape')
        settle(['2', '5', '3', '6', '7', '4', '4'])
        check('표시 줄이 있는 차트는 그 번호 그대로, 없는 둘은 4', marks() == ['2', '5', '3', '6', '7', '4', '4'], marks())
        check('유형별 물동량은 선명한 구분의 두 색 (#4e79a7·#f28e2b)', has(colors(6), '#4e79a7') and has(colors(6), '#f28e2b'), colors(6))

        print('[10. 어두운 스타일]')
        page.select_option('#lec-theme', 'dark')
        until(page, lambda: page.evaluate("() => document.documentElement.dataset.theme") == 'dark')
        until(page, lambda: not has(colors(0), '#17304f') and len(colors(0)) > 0, ms=15000)
        drawn()
        bars = [c for c in colors(0) if luma(c) is not None and c not in ('#ffffff', 'rgb(255,255,255)')]
        check('남색 막대는 어두운 바탕에서 읽히게 밝아진다', not has(colors(0), '#17304f') and any((luma(c) or 0) >= 0.4 for c in bars), colors(0))
        bar = page.evaluate(CBAR, 4)
        check('어두운 스타일에서도 색 막대는 그러데이션', "url('#" in bar or 'url("#' in bar, bar)
        page.select_option('#lec-theme', 'report')
        until(page, lambda: page.evaluate("() => document.documentElement.dataset.theme") == 'report')
        until(page, lambda: has(colors(0), '#17304f'), ms=15000)
        drawn()

        print("[11. 'html로 저장' 의 글]")
        got = page.evaluate("""() => Promise.all([import('/static/js/mdhtml.js'), import('/static/js/store.js')]).then(([m, { S }]) => m.buildMdHtml(S.pane, '월간-보고.md', { printCss: '' }))
          .then((r) => typeof r === 'string' ? r : (r.html || JSON.stringify(r)))""")
        check('남색 막대가 그대로 (#17304f)', '#17304f' in got.lower(), len(got))
        check("Plotly 색 막대의 그러데이션 참조가 남는다", "url('#" in got or 'url(&quot;#' in got or 'url("#' in got, re.findall(r'cbfill[^>]{0,120}', got)[:1])
        check('표시 줄(// 색:)은 글에 없다', '// 색:' not in got)

        print('[12. 원문]')
        final = src()
        want = REPORT.replace(OWN, '')
        for i, line in enumerate(['// 색: 2 보고서 남색', '// 색: 5 색약 친화', '// 색: 3 회색 + 강조', '// 색: 6 따뜻한', '// 색: 7 차가운']):
            check(f'표시 줄 {i + 1}: {line}', line in final.split('\n'), '')
        strip = '\n'.join(ln for ln in final.split('\n') if not MARK_LINE.match(ln))
        check('표시 줄을 걷으면 Claude 가 뺀 색 말고는 처음 원문 그대로', strip == want, [ln for ln in strip.split('\n') if ln not in want.split('\n')][:5])
        check('화면 스크립트 오류 없음', not errors, errors[:5])
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
