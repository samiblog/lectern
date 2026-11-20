"""슬라이드의 넘침 맞춤 (D188): 넘친 글은 바닥 크기까지 줄이고, 차트는 그림을 줄이지 않고 그 자리 크기로 다시 그린다.
같은 줄의 같은 꾸밈 칸은 같은 배율, 바닥에서도 넓은 코드는 줄을 접는다, 줄여도 나아지지 않으면 그대로, 줄인 것은 점검 목록에만 (틀에 표시 없음)"""
import json
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-slidefit-'))
proj = base / 'proj'
proj.mkdir(parents=True)
F = '```'
HEAD = '---\nmarp: true\n---\n\n## 앞장\n\n앞장글\n\n---\n\n'
bul = lambda n, w='시장 점유율이 전년 대비 늘었고 신규 고객 유입이 이어졌다': '\n'.join(f'- {w} ({i + 1})' for i in range(n))
VL = ('{"width": %s, "height": 360, "data": {"values": [{"y": "2022", "k": "국내", "v": 30}, {"y": "2022", "k": "수출", "v": 45}, '
      '{"y": "2023", "k": "국내", "v": 34}, {"y": "2023", "k": "수출", "v": 41}]}, "mark": "line", '
      '"encoding": {"x": {"field": "y", "type": "ordinal", "title": "연도"}, "y": {"field": "v", "type": "quantitative", "title": "매출"}, '
      '"color": {"field": "k", "type": "nominal", "title": "구분"}}%s}')
PLOTLY = ('{"data": [{"x": ["2022", "2023"], "y": [30, 34], "name": "국내", "type": "bar"}, {"x": ["2022", "2023"], "y": [45, 41], "name": "수출", "type": "bar"}], '
          '"layout": {"yaxis": {"title": {"text": "매출"}}}}')
TINY = VL % ('"container"', ', "config": {"axis": {"labelFontSize": 5, "titleFontSize": 5}, "legend": {"labelFontSize": 5, "titleFontSize": 5}}')
FLUID = (VL % ('"container"', '')).replace(', "height": 360', '')
DOCS = {
    '두카드': f'<!-- layout: two -->\n\n## 제목\n\n::: a card\n### 성과\n{bul(8)}\n:::\n\n::: b card\n### 과제\n{bul(6)}\n:::\n',
    '많이넘침': f'<!-- layout: two -->\n\n## 제목\n\n::: a card\n{bul(14)}\n:::\n\n::: b card\n짧은 글\n:::\n',
    # 가운데 칸이 바닥에서도 넘친다 — 위아래로 갈려 맨 위 소제목이 잘리지 않게 (AI 시나리오에서 찾음)
    '가운데넘침': f'<!-- layout: quad -->\n\n## 제목\n\n::: a kpi\n**230천 t**\n기준\n:::\n\n::: b card center\n### 상단을 다시 본다\n{bul(9)}\n:::\n\n::: c\n글\n:::\n\n::: d\n글\n:::\n',
    '칸없는장':f'## 제목\n\n{bul(12, "보고서의 문장을 그대로 옮겨 와서 한 줄이 길어지고 줄 수도 많아진 경우")}\n',
    '긴코드': f'<!-- layout: two -->\n\n## 제목\n\n::: a\n글\n:::\n\n::: b\n{F}python\nresult = model.fit(train_features_with_lagged_variables, train_target_quarterly_growth, epochs=200, verbose=0)\n{F}\n:::\n',
    '넓은상자': '<!-- layout: three -->\n\n## 제목\n\n::: a\n짧은 글\n\n<div style="width:900px;height:20px;background:#ccd"></div>\n:::\n\n::: b\n글\n:::\n\n::: c\n글\n:::\n',
    '크기칸': f'<!-- layout: two -->\n\n## 제목\n\n::: a card 22\n{bul(7)}\n:::\n\n::: b\n글\n:::\n',
    '표첫열': ('<!-- grid: t t t / a b c -->\n\n## 제목\n\n::: a\n글\n:::\n\n::: b card\n| 항목 | 2023 | 2024 | 2025 | 2026E | 증감률 |\n|---|--:|--:|--:|--:|--:|\n'
             '| 매출액 | 12,345,678 | 13,456,789 | 14,567,890 | 15,678,901 | 7.6% |\n:::\n\n::: c\n글\n:::\n'),
    '숫자크기차트': f'<!-- layout: two -->\n\n## 제목\n\n::: a\n{F}vega-lite\n{VL % ("600", "")}\n{F}\n:::\n\n::: b\n- 글\n:::\n',
    '글아래차트': f'## 제목\n\n{bul(5, "설명 글이 위에 있고 차트가 아래에 이어지는 흔한 모양")}\n\n{F}vega-lite\n{VL % ("600", "")}\n{F}\n',
    # 캡션·자료가 있는 칸의 차트 — 전시물(D184)로 묶여 차트가 칸의 바로 아래가 아니다 (AI 시나리오에서 찾음: 80px 로 그려졌다)
    # 설정은 Claude 처럼 여러 줄로 — 그리기 전의 원문 블록이 높아야 그 잘못이 드러난다
    '캡션차트': f'<!-- layout: two-left -->\n\n## 제목\n\n::: a\n**월별 가격 (USD/t)**\n\n{F}vega-lite\n{json.dumps(json.loads(FLUID), ensure_ascii=False, indent=2)}\n{F}\n\n자료: 가상 거래소 (2026)\n:::\n\n::: b card\n글\n:::\n',
    '작은차트글자': f'## 제목\n\n{F}vega-lite\n{TINY}\n{F}\n',
    '좁은칸범례': (f'<!-- grid: t t t / a b c -->\n\n## 제목\n\n::: a\n{F}vega-lite\n{FLUID}\n{F}\n:::\n\n'
               f'::: b\n{F}plotly\n{PLOTLY}\n{F}\n:::\n\n::: c\n글\n:::\n'),
}
for name, body in DOCS.items():
    (proj / f'{name}.md').write_text(HEAD + body, encoding='utf-8', newline='\n')
(proj / '읽는자료.md').write_text(f'---\nmarp: true\nreading: true\n---\n\n## 앞장\n\n앞장글\n\n---\n\n## 제목\n\n{bul(22)}\n', encoding='utf-8', newline='\n')
(proj / '문서차트.md').write_text(f'# 문서\n\n{F}vega-lite\n{VL % ("600", "")}\n{F}\n', encoding='utf-8', newline='\n')
config = base / 'config'
config.mkdir()
server, url, port = serve(proj, config)
extra = []
OPEN = "(path) => import('/static/js/store.js').then(({ emit }) => emit('open', { type: 'doc', path, force: true }))"
SLIDE = "document.querySelectorAll('#lec-view .lec-slide')[1]"
WRAP = "document.querySelectorAll('#lec-view > .lec-slide-wrap')[1]"
INFO = f"(() => {{ const w = {WRAP}; return {{ issues: JSON.parse(w.dataset.issues || '[]').map((x) => x.text), fitted: JSON.parse(w.dataset.fitted || '[]').map((x) => x.text), over: w.classList.contains('lec-over') }}; }})()"
PT = "(el) => Math.round(parseFloat(getComputedStyle(el).fontSize) * 0.75 * 10) / 10"
# 차트 글자의 장 위 크기(pt) — 가장 작은 것
CHART_PT = """(svg) => { const s = svg.closest('.lec-slide'); const scale = s.getBoundingClientRect().width / s.offsetWidth || 1;
  const vb = svg.getAttribute('viewBox').split(/[\\s,]+/).map(Number); const r = svg.getBoundingClientRect();
  const k = Math.min(r.width / scale / vb[2], r.height / scale / vb[3]);
  return Math.round(Math.min(...[...svg.querySelectorAll('text')].filter((t) => t.textContent.trim()).map((t) => parseFloat(getComputedStyle(t).fontSize))) * k * 0.75 * 10) / 10; }"""


def run():
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1400, 'height': 900})
        page.on('pageerror', lambda e: extra.append(str(e)[:200]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row')

        def show(name):
            page.evaluate(OPEN, f'{name}.md')
            page.wait_for_function("(n) => document.querySelector('#lec-st-path')?.textContent.includes(n) && document.querySelector('#lec-view .lec-slide, #lec-view h1')", arg=f'{name}.md', timeout=20000)
            until(page, "() => [...document.querySelectorAll('#lec-view pre.lec-chart')].every((p) => p.querySelector(':scope > svg'))", 20000)
            page.wait_for_timeout(500)

        info = lambda: page.evaluate(INFO)

        print('[조금 넘친 두 카드는 함께 줄여 맞춘다]')
        show('두카드')
        got = info()
        check('넘침이 남지 않는다', not got['issues'] and not got['over'], got)
        check('줄인 것을 알린다 — 두 칸을 한 줄로', any('칸 a·b 의 글을' in x for x in got['fitted']), got['fitted'])
        sizes = page.evaluate(f"(() => [...{SLIDE}.querySelectorAll('.lec-cell li:first-child')].map({PT}))()")
        check('두 카드의 글자 크기가 같다', len(sizes) == 2 and sizes[0] == sizes[1], sizes)
        check('바닥(14pt)과 처음(18pt) 사이', sizes and 14 <= sizes[0] < 18, sizes)
        title = page.evaluate(f"({PT})({SLIDE}.querySelector('h2'))")
        check('장 제목은 줄지 않는다', title == 30, title)
        sub = page.evaluate(f"(() => [...{SLIDE}.querySelectorAll('.lec-cell h3')].map({PT}))()")
        check('소제목도 같은 비율로', sub and 16 <= sub[0] < 20 and sub[0] > sizes[0], (sub, sizes))
        check('글을 줄인 장은 틀에 표시하지 않는다', page.evaluate(f"!{WRAP}.querySelector('.lec-slide-frame').dataset.over"))
        check('상태줄은 줄인 글을 센다', '줄인 글 1장' in page.locator('#lec-st-check').inner_text() and page.locator('#lec-st-check').is_visible(), page.locator('#lec-st-check').inner_text())
        page.locator('#lec-st-check').click()
        page.wait_for_timeout(200)
        menu = page.locator('#lec-menu').inner_text()
        check('목록에 줄인 곳이 따로 나온다', '넘쳐서 글을 줄인 곳' in menu and '2장' in menu, menu[:200])
        check('고칠 것이 없으면 터미널로 보내는 줄이 없다', '터미널에 붙여 넣기' not in menu, menu[:200])
        page.keyboard.press('Escape')

        print('[많이 넘치면 바닥 크기에서 멈추고 점검에 남는다]')
        show('많이넘침')
        got = info()
        check('넘침이 점검에 남는다', any('칸 a 이(가)' in x and '넘칩니다' in x for x in got['issues']) and got['over'], got)
        sizes = page.evaluate(f"(() => [...{SLIDE}.querySelectorAll('.lec-cell')].map((c) => ({PT})(c.querySelector('li, p'))))()")
        check('바닥 14pt 에서 멈춘다', sizes and sizes[0] == 14, sizes)
        check('같은 줄의 같은 꾸밈 칸도 같은 크기', len(sizes) == 2 and sizes[1] == 14, sizes)
        check('상태줄은 고칠 것을 먼저 센다', '점검 1장' in page.locator('#lec-st-check').inner_text(), page.locator('#lec-st-check').inner_text())
        page.locator('#lec-st-check').click()
        page.wait_for_timeout(200)
        menu = page.locator('#lec-menu').inner_text()
        check('두 묶음과 보내는 줄이 함께', '넘치거나 잘못 쓴 곳' in menu and '넘쳐서 글을 줄인 곳' in menu and '터미널에 붙여 넣기' in menu, menu[:240])
        page.keyboard.press('Escape')

        show('가운데넘침')
        got = info()
        r = page.evaluate(f"""(() => {{ const c = {SLIDE}.querySelector('.lec-cell[data-cell=b]'); const h = c.querySelector('h3');
          return [h.getBoundingClientRect().top - c.getBoundingClientRect().top, c.scrollHeight - c.clientHeight]; }})()""")
        check('가운데 칸이 넘쳐도 맨 위 소제목은 보인다 (아래만 잘린다)', r[0] >= 0, r)
        said = [x for x in got['issues'] if '칸 b' in x]
        check('— 알리는 넘침 px 는 실제 넘친 만큼', said and f'{r[1]}px' in said[0], (said, r))

        print('[칸 없는 장·읽는 자료]')
        show('칸없는장')
        got = info()
        check('칸 없는 장도 줄여 맞춘다', not got['issues'] and any(x.startswith('글을') for x in got['fitted']), got)
        li, h2 = page.evaluate(f"(() => [({PT})({SLIDE}.querySelector('li')), ({PT})({SLIDE}.querySelector('h2'))])()")
        check('목록은 줄고 제목은 그대로', 14 <= li < 18 and h2 == 30, (li, h2))
        show('읽는자료')
        got = info()
        li = page.evaluate(f"({PT})({SLIDE}.querySelector('li'))")
        check('읽는 자료의 바닥은 12pt', li == 12, li)
        check('읽는 자료도 넘침은 남는다', any('아래가' in x for x in got['issues']), got)

        print('[코드·넓은 상자·크기 낱말·표]')
        show('긴코드')
        got = info()
        check('바닥에서도 넓은 코드는 줄을 접는다', page.evaluate(f"!!{SLIDE}.querySelector('pre.lec-wrap')") and any('코드 줄을 접었습니다' in x for x in got['fitted']), got)
        check('접은 코드는 잘리지 않는다', not any('코드가 옆으로' in x for x in got['issues']), got)
        show('넓은상자')
        got = info()
        check('줄여도 나아지지 않으면 줄이지 않는다', not got['fitted'] and page.evaluate(f"!{SLIDE}.querySelector('.lec-shrunk')"), got)
        check('그 넘침은 점검에 남는다', any('옆으로' in x for x in got['issues']), got)
        show('크기칸')
        got = info()
        r = page.evaluate(f"(() => {{ const c = {SLIDE}.querySelector('.lec-cell'); return [({PT})(c.querySelector('li')), c.getAttribute('style')]; }})()")
        check('칸 머리의 크기(22pt)에서 줄인다', 14 <= r[0] < 22 and any('칸 a' in x for x in got['fitted']), (r, got))
        check('칸의 자리(grid-area)는 그대로', 'grid-area:a' in r[1].replace(' ', ''), r[1])
        said = [x for x in got['fitted'] if '칸 a' in x]
        want = f'{round(r[0] / 22 * 100)}%'
        check(f'알리는 비율은 칸에 있는 글의 것 ({want} — 없는 표·코드의 바닥이 아니라)', said and want in said[0], (said, r[0]))
        show('표첫열')
        lines = page.evaluate(f"""(() => {{ const td = {SLIDE}.querySelector('tbody td'); const range = document.createRange(); range.selectNodeContents(td);
          return new Set([...range.getClientRects()].map((x) => Math.round(x.top))).size; }})()""")
        check('표의 첫 열은 글자마다 끊지 않는다 (매출액 한 줄)', lines == 1, lines)

        print('[차트는 그림을 줄이지 않고 다시 그린다]')
        show('숫자크기차트')
        pt = expect(page, '숫자로 적은 크기(600×360)도 칸 폭에 맞춰 그린다 — 14pt 이상', f"() => ({CHART_PT})({SLIDE}.querySelector('pre.lec-chart > svg')) >= 14",
                    lambda: page.evaluate(f"({CHART_PT})({SLIDE}.querySelector('pre.lec-chart > svg'))"))
        show('글아래차트')
        expect(page, '넘쳐서 낮춘 차트를 그 높이로 다시 그린다', f"() => !!{SLIDE}.querySelector('pre.lec-chart[data-fit-height]') && ({CHART_PT})({SLIDE}.querySelector('pre.lec-chart > svg')) >= 14",
               lambda: page.evaluate(f"[{SLIDE}.querySelector('pre.lec-chart')?.dataset.fitHeight, ({CHART_PT})({SLIDE}.querySelector('pre.lec-chart > svg'))]"), ms=10000)
        expect(page, '다시 그린 뒤 넘침·점검이 남지 않는다', f"() => {{ const w = {WRAP}; return !w.dataset.issues; }}", lambda: info())
        show('캡션차트')
        fill = page.evaluate(f"""(() => {{ const cell = {SLIDE}.querySelector('.lec-cell[data-cell=a]'); const svg = cell.querySelector('pre.lec-chart > svg');
          const s = cell.closest('.lec-slide'); const scale = s.getBoundingClientRect().width / s.offsetWidth || 1;
          return [Math.round(svg.getBoundingClientRect().height / scale), cell.clientHeight, !!cell.querySelector('.lec-exhibit pre.lec-chart')]; }})()""")
        check('캡션·자료와 묶인 칸의 차트도 칸의 남은 높이를 채운다', fill[2] and fill[0] > fill[1] * 0.6, fill)
        check('— 넘치지 않는다', not info()['issues'], info())
        show('작은차트글자')
        expect(page, '차트 글자가 작으면 점검에 나온다', f"() => JSON.parse({WRAP}.dataset.issues || '[]').some((x) => x.text.includes('차트 글자가'))", lambda: info())
        show('좁은칸범례')
        legend = page.evaluate(f"""(() => {{ const s = {SLIDE}; const out = {{}};
          const vl = s.querySelector('.lec-cell[data-cell=a] svg'); const lg = vl.querySelector('.role-legend'); const vb = vl.getAttribute('viewBox').split(/[\\s,]+/).map(Number);
          const a = lg.getBoundingClientRect(), r = vl.getBoundingClientRect(); out.vega = [(a.left - r.left) / r.width, (a.top - r.top) / r.height];
          const pl = s.querySelector('.lec-cell[data-cell=b] svg'); const pg = pl.querySelector('.legend').getBoundingClientRect(), pr = pl.getBoundingClientRect();
          out.plotly = [(pg.left - pr.left) / pr.width, (pg.top - pr.top) / pr.height];
          out.pt = [({CHART_PT})(vl), ({CHART_PT})(pl)]; return out; }})()""")
        check('좁은 칸의 Vega-Lite 범례는 아래로', legend['vega'][0] < 0.3 and legend['vega'][1] > 0.6, legend)
        check('좁은 칸의 Plotly 범례는 아래로', legend['plotly'][0] < 0.3 and legend['plotly'][1] > 0.6, legend)
        check('좁은 칸 차트의 글자도 14pt 이상', all(x >= 14 for x in legend['pt']), legend)

        print('[md 문서의 차트는 그대로]')
        show('문서차트')
        w = page.evaluate("parseFloat(document.querySelector('#lec-view pre.lec-chart > svg').getAttribute('width'))")
        check('문서에서는 적은 폭(600)대로 그린다', 600 <= w < 760, w)

        check('화면 오류 없음', not extra, extra[:3])
        b.close()


try:
    run()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
