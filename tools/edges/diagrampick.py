"""도해 고르기 창 (D214) — 우클릭 '도해 스타일…'·'색 조합…' 이 그 그림을 번호마다 작게 그려 보인다.
- 칸마다 그 번호로 그린다 (다른 쪽 번호는 그 그림의 것 그대로). 지금 번호에 표시, 창을 열기만 하면 파일은 그대로.
- 화살표 키로 옮기고 Enter·누르기로 고르면 그 블록에 '%% 스타일: 3 카드' 처럼 번호와 이름. 있는 줄은 그 조각만 바꾼다.
- 차트는 색 조합만, Graphviz 는 '//' 줄. '설정 따르기'·'문서의 기본 따르기' 는 그 조각만 지운다. Esc·바깥은 쓰지 않고 닫는다.
- 창을 연 뒤 그 그림이 바뀌었으면 쓰지 않는다. 메뉴의 오른쪽 글은 '1 기본' 처럼 번호와 이름. 견본 단추는 예제의 견본 문서.
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
DOC = f"""# 고르기

<!-- 도해: 색 2 -->

{FENCE}mermaid
flowchart LR
  A[자료 수집<br>통계 12건] --> B[분석]:::key --> C[보고서]
{FENCE}

{FENCE}mermaid
flowchart TD
  %% 스타일: 8 · 색: 6
  A[가<br>내용] --> B[나]
{FENCE}

{FENCE}dot
digraph 가 {{
  rankdir=LR
  A -> B; B [class="key"]
}}
{FENCE}

{FENCE}vega-lite
{{ "data": {{"values": [{{"k": "a", "v": 3}}, {{"k": "b", "v": 2}}, {{"k": "c", "v": 4}}]}}, "mark": "bar",
  "encoding": {{"x": {{"field": "k", "type": "nominal"}}, "y": {{"field": "v", "type": "quantitative"}}, "color": {{"field": "k", "type": "nominal"}}}} }}
{FENCE}
"""
ALL = '#lec-view pre.mermaid, #lec-view pre.lec-chart'
MARKS = "() => [...document.querySelectorAll('#lec-view pre.mermaid, #lec-view pre.lec-chart')].map((n) => (n.dataset.diagramStyle || '-') + '/' + (n.dataset.diagramColors || '-'))"
CARDS = """() => [...document.querySelectorAll('#lec-dpick .dpick-card')].map((c) => { const pre = c.querySelector('.dpick-stage pre'); const svg = c.querySelector('.dpick-stage svg');
  const r = svg && svg.getBoundingClientRect(); const st = c.querySelector('.dpick-stage').getBoundingClientRect();
  return { n: c.dataset.n, on: c.classList.contains('on'), name: c.querySelector('.dpick-name').textContent.trim(), svg: !!svg,
    marks: pre ? (pre.dataset.diagramStyle || '-') + '/' + (pre.dataset.diagramColors || '-') : null,
    inside: !!r && r.width > 20 && r.height > 10 && r.right <= st.right + 1 && r.bottom <= st.bottom + 1 }; })"""
RGB = lambda h: f'rgb({int(h[1:3], 16)}, {int(h[3:5], 16)}, {int(h[5:7], 16)})'   # noqa: E731
SHOTS = os.environ.get('LEC_SHOTS')

base = Path(tempfile.mkdtemp(prefix='lec-dpick-'))
proj = base / '과제'
proj.mkdir()
doc = proj / '고르기.md'
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
        page.click('#lec-tree .row[data-doc="고르기.md"]')

        def drawn():
            return until(page, lambda: page.locator('#lec-view pre.mermaid.mermaid-ok').count() == 2 and page.locator('#lec-view pre.lec-chart.chart-ok').count() == 2, ms=30000)

        def marks():
            return page.evaluate(MARKS)

        def cards():
            return page.evaluate(CARDS)

        def menu(i):
            page.locator(ALL).nth(i).click(button='right', position={'x': 5, 'y': 5})
            page.wait_for_selector('#lec-menu:not([hidden])', timeout=5000)

        def pick(i, item, count):
            menu(i)
            page.locator('#lec-menu button', has_text=item).first.click()
            page.wait_for_selector('#lec-dpick:not([hidden])', timeout=5000)
            until(page, lambda: page.locator('#lec-dpick-grid.dpick-done').count() == 1 and len(cards()) == count, ms=30000)   # 다 그린 뒤 (번호는 그린 뒤에 적힌다)
            page.wait_for_timeout(150)

        drawn()
        print('[메뉴의 번호와 이름]')
        menu(0)
        hint = page.evaluate("""() => [...document.querySelectorAll('#lec-menu button')].filter((b) => /도해 스타일…|색 조합…/.test(b.textContent)).map((b) => b.textContent.trim())""")
        check("메뉴 오른쪽 글은 '1 기본'·'2 보고서 남색' (번호만이 아니라)", any('1 기본' in h for h in hint) and any('2 보고서 남색' in h for h in hint), hint)
        page.keyboard.press('Escape')

        print('[도해 스타일 — 이 그림을 열 가지로]')
        before = src()
        pick(0, '도해 스타일…', 10)
        cs = cards()
        check('칸 열 개, 칸마다 그 번호로 그린다 (색은 문서의 기본 2 그대로)', [c['marks'] for c in cs] == [f'{n}/2' for n in range(1, 11)], cs)
        check('지금 번호(1)에 표시, 칸 이름은 번호와 이름', [c['n'] for c in cs if c['on']] == ['1'] and cs[2]['name'].startswith('3 카드'), cs[:3])
        check('그림은 칸 안에 맞춰 줄인다', all(c['inside'] for c in cs), [c for c in cs if not c['inside']])
        check('창의 제목, 줄이 없으면 따르기 단추 없음', page.locator('#lec-dpick-title').inner_text() == '도해 스타일 — 이 그림' and page.locator('#lec-dpick-follow').is_hidden())
        check('창을 열기만 해서는 파일이 그대로', src() == before)
        if SHOTS:
            page.screenshot(path=str(Path(SHOTS) / 'dpick-style.png'))
        focus = page.evaluate("() => document.activeElement?.dataset?.n || ''")
        check('처음 초점은 지금 번호의 칸', focus == '1', focus)
        page.keyboard.press('ArrowRight')
        page.keyboard.press('ArrowRight')
        tip = page.locator('#lec-dpick-tip').inner_text()
        check('→ 로 옮기면 아래 줄에 그 번호의 설명', tip.startswith('3 카드 — '), tip)
        page.keyboard.press('ArrowDown')
        cols = page.evaluate("() => getComputedStyle(document.querySelector('#lec-dpick-grid')).gridTemplateColumns.split(' ').length")
        down = page.evaluate("() => document.activeElement?.dataset?.n || ''")
        check('↓ 는 한 줄 아래 (격자의 열 수만큼)', down == str(min(10, 3 + cols)), (down, cols))
        page.keyboard.press('ArrowUp')
        page.keyboard.press('Enter')
        until(page, lambda: 'flowchart LR\n  %% 스타일: 3 카드\n  A[자료 수집' in src(), ms=8000)
        check("Enter 로 고르면 그 블록에 '%% 스타일: 3 카드' 한 줄 (번호와 이름)", 'flowchart LR\n  %% 스타일: 3 카드\n  A[자료 수집' in src(), src()[:160])
        check('고르면 창을 닫는다', page.locator('#lec-dpick').is_hidden())
        until(page, lambda: marks()[0] == '3/2', ms=12000)
        check('이름이 붙은 줄도 그 번호로 그린다', marks()[0] == '3/2', marks())

        print('[있는 줄 — 따르기·다른 번호]')
        pick(0, '도해 스타일…', 10)
        cs = cards()
        follow = page.locator('#lec-dpick-follow')
        check("지금 3 에 표시, '설정 따르기 (지금 1 기본)'", [c['n'] for c in cs if c['on']] == ['3'] and follow.is_visible() and '1 기본' in follow.inner_text(), (follow.inner_text(), [c['n'] for c in cs if c['on']]))
        page.locator('#lec-dpick .dpick-card[data-n="5"]').click()
        until(page, lambda: '%% 스타일: 5 선만' in src(), ms=8000)
        check('누르면 있는 줄을 바꾼다 (줄은 하나)', src().count('스타일: ') == 2 and '%% 스타일: 5 선만' in src(), src()[:160])
        until(page, lambda: marks()[0] == '5/2', ms=12000)
        pick(0, '도해 스타일…', 10)
        page.locator('#lec-dpick-follow').click()
        until(page, lambda: '스타일: 5' not in src(), ms=8000)
        check("'설정 따르기' 는 그 줄만 지운다", 'flowchart LR\n  A[자료 수집' in src() and '%% 스타일: 8 · 색: 6' in src(), src()[:200])
        until(page, lambda: marks()[0] == '1/2', ms=12000)

        print('[색 조합 — 모양은 그 그림의 것 그대로]')
        pick(1, '색 조합…', 8)
        cs = cards()
        if SHOTS:
            page.screenshot(path=str(Path(SHOTS) / 'dpick-td.png'))
        check('칸 여덟 개, 모양은 8 그대로, 색만 번호마다', [c['marks'] for c in cs] == [f'8/{n}' for n in range(1, 9)], cs)
        check("지금 6 에 표시, 줄이 있으니 '문서의 기본 따르기 (지금 2 보고서 남색)'", [c['n'] for c in cs if c['on']] == ['6'] and '2 보고서 남색' in page.locator('#lec-dpick-follow').inner_text(),
              page.locator('#lec-dpick-follow').inner_text())
        page.locator('#lec-dpick .dpick-card[data-n="2"]').click()
        until(page, lambda: '%% 스타일: 8 · 색: 2 보고서 남색\n' in src(), ms=8000)
        check('있는 표시 줄의 색 조각만 바꾼다 (손으로 쓴 모양 조각은 그대로)', '  %% 스타일: 8 · 색: 2 보고서 남색\n' in src(), src()[src().find('flowchart TD'):][:80])

        print('[차트 — 색 조합만]')
        menu(3)
        labels = page.evaluate("() => [...document.querySelectorAll('#lec-menu button')].map((b) => b.textContent.trim())")
        check("차트 메뉴에는 '도해 스타일…' 이 없다", not any(x.startswith('도해 스타일…') for x in labels) and any(x.startswith('색 조합…') for x in labels), labels)
        page.keyboard.press('Escape')
        pick(3, '색 조합…', 8)
        cs = cards()
        fills = page.evaluate("""() => [...document.querySelectorAll('#lec-dpick .dpick-card')].map((c) => [...c.querySelectorAll('g.mark-rect path')].map((e) => getComputedStyle(e).fill))""")
        check('차트 칸도 여덟, 칸마다 다른 계열 색 (3 회색 + 강조는 첫 계열 주황)', len(cs) == 8 and fills[2][:1] == [RGB('#c2410c')] and fills[1] != fills[2], fills[:3])
        check('차트도 칸 안에', all(c['inside'] for c in cs), [c for c in cs if not c['inside']])
        if SHOTS:
            page.screenshot(path=str(Path(SHOTS) / 'dpick-chart.png'))
        page.locator('#lec-dpick .dpick-card[data-n="5"]').click()
        until(page, lambda: '```vega-lite\n// 색: 5 색약 친화\n{' in src(), ms=8000)
        check("차트는 블록 맨 앞에 '// 색: 5 색약 친화'", '```vega-lite\n// 색: 5 색약 친화\n{' in src(), src()[-260:])
        until(page, lambda: marks()[3] == '-/5', ms=12000)
        check('이름이 붙은 // 줄도 차트가 읽는다 (JSON 오류 없이 다시 그림)', marks()[3] == '-/5' and page.locator('#lec-view .diagram-error').count() == 0, marks())

        print('[Graphviz]')
        pick(2, '도해 스타일…', 10)
        cs = cards()
        check('Graphviz 도 열 칸, 칸마다 그 번호', [c['marks'].split('/')[0] for c in cs] == [str(n) for n in range(1, 11)], cs)
        if SHOTS:
            page.screenshot(path=str(Path(SHOTS) / 'dpick-dot.png'))
        page.locator('#lec-dpick .dpick-card[data-n="9"]').click()
        until(page, lambda: 'digraph 가 {\n  // 스타일: 9 옅은 제목 띠\n  rankdir=LR' in src(), ms=8000)
        check("Graphviz 는 '// 스타일: 9 옅은 제목 띠'", 'digraph 가 {\n  // 스타일: 9 옅은 제목 띠\n  rankdir=LR' in src(), src()[src().find('digraph'):][:80])

        print('[쓰지 않고 닫기]')
        now = src()
        pick(0, '도해 스타일…', 10)
        page.keyboard.press('Escape')
        check('Esc 는 쓰지 않고 닫는다', page.locator('#lec-dpick').is_hidden() and src() == now)
        pick(0, '색 조합…', 8)
        page.mouse.click(5, 5)
        check('바깥을 누르면 쓰지 않고 닫는다', page.locator('#lec-dpick').is_hidden() and src() == now)
        check('닫힌 창에 그림을 남기지 않는다', page.locator('#lec-dpick-grid > *').count() == 0)

        print('[창을 연 뒤 그 그림이 바뀌면 쓰지 않는다]')
        pick(0, '도해 스타일…', 10)
        time.sleep(1.05)
        changed = src().replace('통계 12건', '통계 13건')
        doc.write_text(changed, encoding='utf-8', newline='\n')
        page.locator('#lec-dpick .dpick-card[data-n="4"]').click()
        until(page, lambda: page.locator('#lec-toast', has_text='저장하지 않았습니다').count() > 0, ms=8000)
        check('그사이 바뀌었으면 저장하지 않고 알린다', page.locator('#lec-toast', has_text='저장하지 않았습니다').count() > 0 and src() == changed, src()[:120])

        print('[견본 단추]')
        until(page, lambda: page.evaluate("() => document.querySelector('#lec-view').textContent.includes('통계 13건')"), ms=10000)
        drawn()
        pick(0, '도해 스타일…', 10)
        check("견본 단추 '모양 견본 모두 보기'", page.locator('#lec-dpick-samples').inner_text() == '모양 견본 모두 보기')
        page.evaluate("() => import('/static/js/store.js').then((m) => { window.__samples = []; m.on('open-sample', (x) => window.__samples.push(x)); })")
        page.locator('#lec-dpick-samples').click()
        until(page, lambda: page.evaluate("() => (window.__samples || []).length") > 0, ms=5000)
        check('예제의 도해 스타일 견본을 연다 (창은 닫는다)', page.evaluate("() => window.__samples[0]") == 'guide/도해-스타일-예제/도해-스타일-견본.md' and page.locator('#lec-dpick').is_hidden(),
              page.evaluate("() => window.__samples"))
        page.keyboard.press('Escape')
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open-settings', 'view'))")
        page.wait_for_selector('#lec-dcolors-samples', state='visible', timeout=8000)
        page.locator('#lec-dcolors-samples').click()
        until(page, lambda: len(page.evaluate("() => window.__samples")) > 1, ms=5000)
        check("설정 창의 '색 조합 견본' 은 색 조합 견본", page.evaluate("() => window.__samples.at(-1)") == 'guide/도해-스타일-예제/색-조합-견본.md', page.evaluate("() => window.__samples"))
        check('화면 스크립트 오류 없음', not errors, errors[:5])
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
