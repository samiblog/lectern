"""0.113 사람 시나리오 — 연구원 B 가 Claude 가 그린 보고서의 그림을 고르기 창으로 다듬는다 (D214). 차례대로 한 사람이 할 법한 일:

1. 보고서를 연다 — Claude 가 '%% 스타일: 3' 처럼 번호만 적어 두었다. 우클릭 메뉴의 오른쪽 글이 '3 카드' 라 무엇인지 안다.
2. 가로 흐름도의 '도해 스타일…' — 그 그림을 열 가지로 그린 창. 키로 8 제목 띠까지 가 보고, 마우스로 2 보고서 선을 고른다 → '%% 스타일: 2 보고서 선'.
3. 묶음이 셋인 구성도는 End 로 10, ← 세 번으로 7 단계 색, Enter.
4. 수요 차트의 '색 조합…' — 여덟 가지 색의 같은 차트. 3 회색 + 강조 → '// 색: 3 회색 + 강조', 차트가 다시 그려진다.
5. 마음을 바꿔 창을 열었다 Esc — 파일은 그대로. Ctrl+Z 로 4 를 되돌리고 Ctrl+Y 로 다시.
6. 어두운 스타일에서 창을 연다 — 칸의 바탕이 문서 바탕(어두움), 그림이 칸 안에.
7. 좁은 창(900×640)에서 연다 — 창이 화면 안에, 칸이 칸 안에, 스크롤로 열 칸 모두.
8. 어떤 번호가 있는지 '모양 견본 모두 보기' → 예제의 견본 문서 — 이름이 붙은 줄이 그 번호로 그려진다.
9. 영어 화면에서 고르면 'style: 5 Line only' (안내처럼 소문자) — 한국어 화면으로 돌아와도 그 번호로 그린다.
10. 원문은 고른 것만 바뀌었다 (표시 줄뿐). 화면 스크립트 오류 없음."""
import json
import re
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop, until

FENCE = '```'
REPORT = f"""# 2분기 물류 거점 재배치

## 1. 흐름

그림 1. 재배치 검토 흐름

{FENCE}mermaid
flowchart LR
  %% 스타일: 3
  A[수요 자료<br>권역별 12개월] --> B[거점 후보<br>9곳] --> C[비용 모형]:::key --> D[민감도] --> E([권고안])
{FENCE}

## 2. 구성

{FENCE}mermaid
flowchart TD
  subgraph 수도권
    S1[이천] --> S2[평택]
  end
  subgraph 충청권
    C1[천안] --> C2[청주]
  end
  subgraph 영남권
    Y1[칠곡] --> Y2[양산]
  end
  S2 --> C1
  C2 --> Y1
{FENCE}

## 3. 수요

그림 2. 권역별 수요 (천 상자)

{FENCE}vega-lite
{{ "width": "container", "data": {{"values": [{{"권역": "수도권", "수요": 420}}, {{"권역": "충청권", "수요": 180}}, {{"권역": "영남권", "수요": 260}}, {{"권역": "호남권", "수요": 140}}]}},
  "mark": "bar", "encoding": {{"x": {{"field": "권역", "type": "nominal", "sort": null}}, "y": {{"field": "수요", "type": "quantitative"}}, "color": {{"field": "권역", "type": "nominal", "sort": null}}}} }}
{FENCE}

## 4. 의존

{FENCE}dot
digraph 의존 {{
  rankdir=LR
  수요 -> 비용; 비용 -> 권고 [class="key"]
}}
{FENCE}
"""
ALL = '#lec-view pre.mermaid, #lec-view pre.lec-chart'
MARKS = f"() => [...document.querySelectorAll('{ALL}')].map((n) => (n.dataset.diagramStyle || '-') + '/' + (n.dataset.diagramColors || '-'))"
CARDS = """() => [...document.querySelectorAll('#lec-dpick .dpick-card')].map((c) => { const pre = c.querySelector('.dpick-stage pre'); const svg = c.querySelector('.dpick-stage svg');
  const r = svg && svg.getBoundingClientRect(); const st = c.querySelector('.dpick-stage').getBoundingClientRect();
  return { n: c.dataset.n, on: c.classList.contains('on'), svg: !!svg, marks: pre ? (pre.dataset.diagramStyle || '-') + '/' + (pre.dataset.diagramColors || '-') : null,
    inside: !!r && r.width > 10 && r.right <= st.right + 1 && r.bottom <= st.bottom + 1 && r.left >= st.left - 1 && r.top >= st.top - 1 }; })"""
FILLS = """(i) => { const n = [...document.querySelectorAll('#lec-view pre.mermaid, #lec-view pre.lec-chart')][i]; return n ? [...n.querySelectorAll('g.mark-rect path')].map((e) => getComputedStyle(e).fill) : []; }"""
RGB = lambda h: f'rgb({int(h[1:3], 16)}, {int(h[3:5], 16)}, {int(h[5:7], 16)})'   # noqa: E731
MARK_LINE = re.compile(r'^\s*(%%|//)\s*(스타일|색|style|colou?rs?)\s*[:：]', re.I)

base = Path(tempfile.mkdtemp(prefix='lec-scen113-'))
proj = base / '과제'
proj.mkdir()
rep = proj / '보고서.md'
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
            return until(page, lambda: page.locator('#lec-view pre.mermaid.mermaid-ok').count() == 2 and page.locator('#lec-view pre.lec-chart.chart-ok').count() == 2, ms=30000)

        def marks():
            return page.evaluate(MARKS)

        def cards():
            return page.evaluate(CARDS)

        def menu(i):
            page.locator(ALL).nth(i).click(button='right', position={'x': 5, 'y': 5})
            page.wait_for_selector('#lec-menu:not([hidden])', timeout=5000)

        def picker(i, item, count):
            menu(i)
            page.locator('#lec-menu button', has_text=item).first.click()
            page.wait_for_selector('#lec-dpick:not([hidden])', timeout=5000)
            until(page, lambda: page.locator('#lec-dpick-grid.dpick-done').count() == 1 and len(cards()) == count, ms=30000)   # 다 그린 뒤 (번호는 그린 뒤에 적힌다)
            page.wait_for_timeout(150)

        def focused():
            return page.evaluate("() => document.activeElement?.dataset?.n || ''")

        print('[1. 보고서를 연다 — 번호만 적힌 줄]')
        page.click('#lec-tree .row[data-doc="보고서.md"]')
        drawn()
        check('Claude 가 적은 3 과 기본 1', marks() == ['3/1', '1/1', '-/1', '1/1'], marks())
        menu(0)
        hint = page.locator('#lec-menu button', has_text='도해 스타일…').first.inner_text()
        check("우클릭 메뉴의 오른쪽 글이 '3 카드' — 번호만 보고도 무엇인지", '3 카드' in hint, hint)
        page.keyboard.press('Escape')

        print('[2. 가로 흐름도 — 견주어 보고 2 보고서 선]')
        picker(0, '도해 스타일…', 10)
        cs = cards()
        check('열 칸 모두 그 그림, 지금 3 에 표시', [c['marks'] for c in cs] == [f'{n}/1' for n in range(1, 11)] and [c['n'] for c in cs if c['on']] == ['3'], cs)
        check('가로로 긴 그림 — 열은 다섯보다 적다 (넓은 칸)', page.evaluate("() => getComputedStyle(document.querySelector('#lec-dpick-grid')).gridTemplateColumns.split(' ').length") < 5)
        check('그림은 모두 칸 안에', all(c['inside'] for c in cs), [c for c in cs if not c['inside']])
        for _ in range(5):
            page.keyboard.press('ArrowRight')
        check('→ 다섯 번 — 8 제목 띠, 아래 줄에 그 설명', focused() == '8' and page.locator('#lec-dpick-tip').inner_text().startswith('8 제목 띠 — '), (focused(), page.locator('#lec-dpick-tip').inner_text()))
        check('옮기기만 해서는 파일이 그대로', src() == REPORT)
        page.locator('#lec-dpick .dpick-card[data-n="2"]').click()
        until(page, lambda: '%% 스타일: 2 보고서 선\n' in src(), ms=8000)
        check("마우스로 2 — 그 줄이 '%% 스타일: 2 보고서 선' 으로", '  %% 스타일: 2 보고서 선\n  A[수요 자료' in src() and src().count('스타일:') == 1, src()[:200])
        until(page, lambda: marks()[0] == '2/1', ms=12000)

        print('[3. 묶음이 셋인 구성도 — End, ← 세 번, Enter]')
        picker(1, '도해 스타일…', 10)
        page.keyboard.press('End')
        check('End — 마지막 칸 10', focused() == '10', focused())
        for _ in range(3):
            page.keyboard.press('ArrowLeft')
        page.keyboard.press('Enter')
        until(page, lambda: 'flowchart TD\n  %% 스타일: 7 단계 색\n  subgraph 수도권' in src(), ms=8000)
        check("Enter — 첫 줄 아래에 '%% 스타일: 7 단계 색'", 'flowchart TD\n  %% 스타일: 7 단계 색\n  subgraph 수도권' in src(), src()[src().find('flowchart TD'):][:80])
        until(page, lambda: marks()[1] == '7/1', ms=12000)
        zones = page.evaluate("() => [...[...document.querySelectorAll('#lec-view pre.mermaid')][1].querySelectorAll('g.cluster rect')].map((r) => getComputedStyle(r).fill)")
        check('묶음 셋이 다른 색', len(set(zones)) == 3, zones)

        print('[4. 수요 차트 — 색 조합 3]')
        menu(2)
        labels = page.evaluate("() => [...document.querySelectorAll('#lec-menu button')].map((b) => b.textContent.trim())")
        check("차트 메뉴는 '색 조합…' 하나 — 오른쪽 글 '1 문서 스타일'", not any(x.startswith('도해 스타일…') for x in labels) and any(x.startswith('색 조합…') and '1 문서 스타일' in x for x in labels), labels)
        page.keyboard.press('Escape')
        picker(2, '색 조합…', 8)
        fills = page.evaluate("() => [...document.querySelectorAll('#lec-dpick .dpick-card')].map((c) => [...c.querySelectorAll('g.mark-rect path')].map((e) => getComputedStyle(e).fill))")
        check('여덟 칸이 저마다 다른 색 (같은 차트)', len({tuple(f) for f in fills}) == 8 and all(len(f) == 4 for f in fills), fills)
        page.locator('#lec-dpick .dpick-card[data-n="3"]').click()
        until(page, lambda: '```vega-lite\n// 색: 3 회색 + 강조\n{' in src(), ms=8000)
        until(page, lambda: marks()[2] == '-/3', ms=12000)
        vg = page.evaluate(FILLS, 2)
        check("'// 색: 3 회색 + 강조' — 첫 권역만 주황, 나머지 회색", vg[:1] == [RGB('#c2410c')] and RGB('#6b7280') in vg, vg)

        print('[5. 열었다 Esc, Ctrl+Z·Ctrl+Y]')
        now = src()
        picker(3, '도해 스타일…', 10)
        page.keyboard.press('ArrowRight')
        page.keyboard.press('Escape')
        check('Esc — 창만 닫히고 파일은 그대로', page.locator('#lec-dpick').is_hidden() and src() == now)
        page.locator('#lec-view h1').click()
        page.keyboard.press('Control+z')
        until(page, lambda: '// 색: 3' not in src(), ms=8000)
        until(page, lambda: marks()[2] == '-/1', ms=12000)
        check('Ctrl+Z — 색 줄만 없어지고 차트는 원래 색', '// 색: 3' not in src() and marks()[2] == '-/1', marks())
        page.keyboard.press('Control+y')
        until(page, lambda: '// 색: 3 회색 + 강조' in src(), ms=8000)
        until(page, lambda: marks()[2] == '-/3', ms=12000)
        check('Ctrl+Y — 다시', marks()[2] == '-/3', marks())

        print('[6. 어두운 스타일에서]')
        page.select_option('#lec-theme', 'dark')
        until(page, lambda: page.evaluate("() => document.documentElement.dataset.theme") == 'dark')
        drawn()
        picker(0, '도해 스타일…', 10)
        bg = page.evaluate("() => getComputedStyle(document.querySelector('#lec-dpick .dpick-card')).backgroundColor")
        lum = [int(x) for x in re.findall(r'\d+', bg)[:3]]
        check('칸의 바탕이 문서 바탕 — 어둡다', sum(lum) / 3 < 80, bg)
        check('그림은 모두 칸 안에', all(c['inside'] for c in cards()), [c for c in cards() if not c['inside']])
        page.keyboard.press('Escape')
        page.select_option('#lec-theme', 'report')
        until(page, lambda: page.evaluate("() => document.documentElement.dataset.theme") == 'report')
        drawn()

        print('[7. 좁은 창]')
        page.set_viewport_size({'width': 900, 'height': 640})
        page.wait_for_timeout(400)
        picker(1, '도해 스타일…', 10)
        box = page.evaluate("() => { const r = document.querySelector('#lec-dpick .dialog-box').getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom, innerWidth, innerHeight]; }")
        check('창이 화면 안에', box[0] >= 0 and box[1] >= 0 and box[2] <= box[4] and box[3] <= box[5], box)
        check('그림은 모두 칸 안에', all(c['inside'] for c in cards()), [c for c in cards() if not c['inside']])
        page.locator('#lec-dpick .dpick-card[data-n="10"]').scroll_into_view_if_needed()
        last = page.evaluate("() => { const g = document.querySelector('#lec-dpick-grid').getBoundingClientRect(); const c = document.querySelector('#lec-dpick .dpick-card[data-n=\"10\"]').getBoundingClientRect(); return c.bottom <= g.bottom + 1 && c.top >= g.top - 1; }")
        check('칸이 넘치면 창 안에서 스크롤 — 열째 칸까지 닿는다', last)
        page.keyboard.press('Escape')
        page.set_viewport_size({'width': 1280, 'height': 900})
        page.wait_for_timeout(400)

        print('[8. 견본 모두 보기]')
        picker(0, '도해 스타일…', 10)
        page.locator('#lec-dpick-samples').click()
        until(page, lambda: page.locator('#lec-view h1', has_text='도해 스타일 견본').count() > 0, ms=20000)
        check('예제의 도해 스타일 견본이 열린다', page.locator('#lec-view h1', has_text='도해 스타일 견본').count() == 1)
        until(page, lambda: page.locator('#lec-view pre.mermaid.mermaid-ok').count() >= 12, ms=40000)
        sm = [x.split('/')[0] for x in marks()]
        check("견본의 '%% 스타일: 3 카드' 처럼 이름이 붙은 줄이 그 번호로", sm[:12] == ['1', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '8'], sm)
        page.locator('#lec-tablist .lec-tab', has_text='과제').first.click()   # 예제는 탭으로 열렸다 (브라우저에는 따로 창이 없다) — 보고서로 돌아온다
        page.wait_for_timeout(500)
        if not page.locator('#lec-view h1', has_text='물류 거점').count():
            page.click('#lec-tree .row[data-doc="보고서.md"]')
        drawn()

        print('[9. 영어 화면에서 고르기]')
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ language: 'en' }))")
        page.reload()
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        if not page.locator('#lec-view h1', has_text='물류 거점').count():
            page.click('#lec-tree .row[data-doc="보고서.md"]')
        drawn()
        picker(3, 'Diagram style…', 10)
        check('영어 창 — 칸 이름도 영어', page.locator('#lec-dpick .dpick-card[data-n="5"] .dpick-name').inner_text().startswith('5 Line only'),
              page.locator('#lec-dpick .dpick-card[data-n="5"] .dpick-name').inner_text())
        page.locator('#lec-dpick .dpick-card[data-n="5"]').click()
        until(page, lambda: '// style: 5 Line only\n' in src(), ms=8000)
        check("영어 화면에서 고르면 'style: 5 Line only'", 'digraph 의존 {\n  // style: 5 Line only\n  rankdir=LR' in src(), src()[src().find('digraph'):][:80])
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ language: 'ko' }))")
        page.reload()
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        if not page.locator('#lec-view h1', has_text='물류 거점').count():
            page.click('#lec-tree .row[data-doc="보고서.md"]')
        drawn()
        until(page, lambda: marks()[3] == '5/1', ms=12000)
        check('한국어 화면으로 돌아와도 5', marks() == ['2/1', '7/1', '-/3', '5/1'], marks())

        print('[10. 원문은 고른 것만]')
        final = src()
        strip = '\n'.join(ln for ln in final.split('\n') if not MARK_LINE.match(ln))
        want = '\n'.join(ln for ln in REPORT.split('\n') if not MARK_LINE.match(ln))
        check('표시 줄을 걷으면 처음 원문 그대로', strip == want, [ln for ln in strip.split('\n') if ln not in want.split('\n')][:5])
        check('표시 줄은 넷 — 모두 번호와 이름', [ln.strip() for ln in final.split('\n') if MARK_LINE.match(ln)] == ['%% 스타일: 2 보고서 선', '%% 스타일: 7 단계 색', '// 색: 3 회색 + 강조', '// style: 5 Line only'],
              [ln.strip() for ln in final.split('\n') if MARK_LINE.match(ln)])
        check('화면 스크립트 오류 없음', not errors, errors[:5])
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
