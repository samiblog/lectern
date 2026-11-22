"""0.101.0 사람 시나리오 — 개조식 보고서를 Lectern 에서 읽고 다듬는 하루 (D191 내어쓰기·D192 글머리 글자 목록).

1. 한글 문서(HWP)에서 붙여 넣은 개조식 — 전각 빈칸의 들여쓰기·머리 글자 뒤의 전각 빈칸·전각 붙임표
2. Claude 가 쓴 보고서 초안 — 번호 제목·굵게 쓴 머리 글자·강조글 안의 ①·Markdown 목록·표가 섞인 문서, 문서 점검에 거짓 경보가 없다
3. 사람이 항목을 다듬는다 — 글 고치기, 새 항목과 Tab, 항목 나누기·잇기, 옮기기, 머리 글자 바꾸기, 지우기와 Ctrl+Z
4. Claude 가 바깥에서 고치는 동안 — 새 차례(□)가 들어오면 수준이 다시 맞는다
5. 여러 스타일·글자 크기·좁은 칸(모두 펼치기)에서 읽기
6. 종이·html 로 저장
7. 큰 개조식 문서 — 항목 3000
8. 헷갈리는 글 — ○○ 기관·ㅇㅇ·머리 글자뿐인 줄·보통 목록·영어 문서"""
import json
import re
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

W = '　'
L = '인공지능 확산은 산업 전반의 생산성을 끌어올리지만 그 효과는 업종과 기업 규모에 따라 크게 다르게 나타나며 정책 대응도 달라져야 한다.'
HWP = (f'# 붙여 넣은 보고서\n\n□{W}추진 배경\n{W}○{W}{L}\n{W}{W}－{W}제조업: {L}\n{W}{W}{W}·{W}반도체 부문이 가장 먼저 영향을 받는다.\n'
       f'{W}○{W}고용은 직무 단위로 재편된다.\n□{W}정책 과제\n{W}○{W}{L}\n\n※{W}참고: {L}\n')
DRAFT = f"""---
title: AI 확산에 따른 세계 경제 영향
---

# AI 확산에 따른 세계 경제 영향

## 1. 요약 — 생산성 증가와 고용 재편이 동시에 나타나는 전환기에 정부와 기업이 함께 풀어야 할 정책 과제를 정리한다

**□ 추진 배경**
**ㅇ** 첫째 항목 {L}
- 제조업 {L}
- 서비스업

## 2. 분석

### 가. 생산성 — {L}

> [!NOTE]
> ① 수치는 잠정치다. {L}
> ② 나라별 자료의 기준 연도가 다르다.

분석의 큰 줄기는 다음과 같다.

- 수요 측면
- 공급 측면

| 구분 | 내용 |
|---|---|
| ㅇ 제조 | {L} |

자료: OECD
"""
EDIT = f'# 다듬기\n\nㅁ 추진 배경\nㅇ 첫째 내용이다. 둘째 내용이다.\n- 제조업\n · 반도체\n- 서비스업\nㅇ 셋째\nㅁ 정책 과제\nㅇ 넷째\n'
OUTER = f'# 바깥\n\nㅇ 첫째\n- 세부\nㅇ 둘째\n'
CONFUSE = f"""# 헷갈리는 글

○○ 기관의 보고서는 {L}

ㅇㅇ 표시는 그대로 둔다.

□

- 보통 목록
- 둘째

1. 번호 목록
2. 둘째

The report covers - not only trade but also labour. {L}

1.5배 늘었다. {L}
"""
BIG = '# 큰 개조식\n\n' + ''.join(f'□ {i}절\nㅇ {L}\n- 세부 {i}\n· 더 세부 {i}\n\n' for i in range(1, 751))

base = Path(tempfile.mkdtemp(prefix='lec-scen101-'))
proj = base / '연구'
proj.mkdir(parents=True)
files = {'붙여넣기.md': HWP, '초안.md': DRAFT, '다듬기.md': EDIT, '바깥.md': OUTER, '헷갈림.md': CONFUSE, '큰.md': BIG}
for name, body in files.items():
    (proj / name).write_text(body, encoding='utf-8')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False, 'theme': 'report'}), encoding='utf-8')
server, url, port = serve(proj, config)


def text(name):
    for _ in range(40):
        try:
            return (proj / name).read_text(encoding='utf-8')
        except OSError:
            time.sleep(0.02)
    return (proj / name).read_text(encoding='utf-8')


# 칸의 항목마다: 글 앞, 수준, 머리 글자의 x(em), 꺾였으면 다음 화면 줄과 머리 글자 뒤 글의 차이(em), 이어 쓴 줄의 차이
ITEMS = """() => [...document.querySelectorAll('#lec-view .lec-mark')].map((p) => {
  const fs = parseFloat(getComputedStyle(p).fontSize); const view = document.querySelector('#lec-view').getBoundingClientRect();
  const boxes = []; const w = document.createTreeWalker(p, NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) for (let i = 0; i < n.length; i++) { if (/[\\s\\u3000]/.test(n.data[i])) continue; const r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + 1);
    const b = [...r.getClientRects()].find((x) => x.width); if (b) boxes.push({ left: b.left, top: b.top }); if (boxes.length > 400) break; }
  if (!boxes.length) return null;
  const body = boxes[1]; const next = boxes.find((x) => x.top > boxes[0].top + fs / 2);
  return { t: p.textContent.slice(0, 5), lv: Number((/lec-lv(\\d)/.exec(p.className) || [])[1]), x: (boxes[0].left - view.left) / fs,
    gap: next && body ? Math.round(((next.left - body.left) / fs) * 100) / 100 : null };
}).filter(Boolean)"""

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 1300, 'height': 900}, locale='ko-KR', permissions=['clipboard-read', 'clipboard-write'])
        page = ctx.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('dialog', lambda d: d.accept())
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')
        label = lambda: page.evaluate("(() => { const b = document.querySelector('#lec-st-lint'); return b.hidden ? null : b.textContent.trim(); })()")   # noqa: E731
        editing = lambda: page.evaluate("document.activeElement?.classList?.contains('lec-line-edit') ? document.activeElement.textContent : null")   # noqa: E731

        def open_doc(name, sel='#lec-view h1'):
            page.locator(f'#lec-tree .row.file[data-doc="{name}"]').click()
            page.wait_for_selector(sel)
            page.wait_for_timeout(500)

        def items():
            return page.evaluate(ITEMS)

        def item(start):
            return page.locator('#lec-view .lec-mark', has_text=start).first

        def edit(start, x=200):
            item(start).click(position={'x': x, 'y': 8})
            page.keyboard.press('Enter')
            return until(page, lambda: editing(), 4000)

        def aligned(rows):
            return [r for r in rows if r['gap'] is not None and abs(r['gap']) >= 0.05]

        def levels_ok(rows):   # 같은 수준은 같은 자리, 수준이 하나 깊으면 오른쪽
            xs = {}
            for r in rows:
                xs.setdefault(r['lv'], set()).add(round(r['x'], 1))
            return all(len(v) == 1 for v in xs.values()) and all(min(xs[a]) < min(xs[a + 1]) for a in xs if a + 1 in xs)

        # ---- 1 ----------------------------------------------------------------------------------
        print('[1. 한글 문서에서 붙여 넣은 개조식]')
        open_doc('붙여넣기.md')
        rows = items()
        check('□ ○ － · 가 수준 0·1·2·3 (전각 빈칸의 들여쓰기와 상관없이)', [r['lv'] for r in rows] == [0, 1, 2, 3, 1, 0, 1], [(r['t'], r['lv']) for r in rows])
        check('— 같은 수준은 같은 자리, 하위는 들여 쓴다 (전각 빈칸만큼 더 밀리지 않는다)', levels_ok(rows), [(r['t'], round(r['x'], 2)) for r in rows])
        check('— 꺾인 줄은 머리 글자 뒤에 (머리 글자 뒤의 전각 빈칸까지)', not aligned(rows) and sum(r['gap'] is not None for r in rows) >= 3, aligned(rows))
        g = page.locator('#lec-view p', has_text='참고:').first.evaluate("(p) => [p.classList.contains('lec-hang'), p.classList.contains('lec-mark')]")
        check('※ 참고 문단은 목록이 아니라 내어 쓴 문단', g == [True, False], g)
        check('문서 점검 — 붙여 넣은 개조식에 거짓 경보가 없다', label() is None, label())

        # ---- 2 ----------------------------------------------------------------------------------
        print('[2. Claude 가 쓴 보고서 초안]')
        open_doc('초안.md', '#lec-view h1:has-text("AI 확산")')
        rows = items()
        check("굵게 쓴 '**□ 추진 배경**'·'**ㅇ** 첫째' 도 글머리 글자 목록 — 수준 0·1, '-' 줄은 2", [(r['t'][:1], r['lv']) for r in rows][:4] == [('□', 0), ('ㅇ', 1), ('-', 2), ('-', 2)],
              [(r['t'], r['lv']) for r in rows])
        check('— 꺾인 줄은 머리 글자 뒤에', not aligned(rows), aligned(rows))
        heads = page.evaluate("[...document.querySelectorAll('#lec-view h2, #lec-view h3')].map((h) => h.classList.contains('lec-hang'))")
        check("번호 제목 '1.'·'2.'·'가.' 은 내어 쓴다", heads == [True, True, True], heads)
        note = page.evaluate("[...document.querySelectorAll('#lec-view blockquote p')].map((p) => [p.classList.contains('lec-hang'), p.classList.contains('lec-mark')])")
        check('강조글 안의 ①·② 줄은 내어 쓴 문단 (목록이 아니다)', note and all(x == [True, False] for x in note), note)
        check("'다음과 같다' 뒤의 보통 Markdown 목록은 그대로", page.locator('#lec-view ul > li', has_text='수요 측면').count() == 1)
        check('표의 칸은 그대로', page.locator('#lec-view table .lec-mark, #lec-view table .lec-hang').count() == 0)
        check('머리 설정은 목록이 아니다', page.locator('#lec-view .front-matter .lec-mark').count() == 0)
        check('문서 점검 — 거짓 경보가 없다', label() is None, label())

        # ---- 3 ----------------------------------------------------------------------------------
        print('[3. 사람이 항목을 다듬는다]')
        open_doc('다듬기.md')
        got = edit('- 제조업', 120)
        check("'- 제조업' 을 고치는 칸에는 '- ' 도 (화면 그대로)", got == '- 제조업', got)
        page.keyboard.press('End')
        page.keyboard.type(' 부문')
        page.keyboard.press('Enter')
        expect(page, '글 고치기 — 머리 글자·앞 빈칸은 그대로', lambda: '\n- 제조업 부문\n · 반도체\n' in text('다듬기.md'), lambda: text('다듬기.md'))
        page.keyboard.press('Escape')
        page.keyboard.press('Escape')
        page.wait_for_timeout(300)

        edit('ㅇ 첫째', 60)
        page.keyboard.press('Home')
        for _ in range(len('ㅇ 첫째 내용이다. ')):
            page.keyboard.press('ArrowRight')
        page.keyboard.press('Shift+Enter')
        expect(page, "항목 나누기 — 'ㅇ 첫째 내용이다.' / 'ㅇ 둘째 내용이다.' (뒤 글도 같은 머리 글자, 빈 줄 없이)",
               lambda: '\nㅇ 첫째 내용이다.\nㅇ 둘째 내용이다.\n- 제조업' in text('다듬기.md'), lambda: text('다듬기.md'))
        expect(page, '— 커서는 새 항목의 머리 글자 뒤', lambda: editing() == 'ㅇ 둘째 내용이다.' and page.evaluate("getSelection().focusOffset") == 2,
               lambda: (editing(), page.evaluate("getSelection().focusOffset")))
        page.keyboard.press('Home')
        page.keyboard.press('Backspace')
        expect(page, "항목 잇기 — 줄 맨 앞의 Backspace 로 'ㅇ 첫째 내용이다.둘째 내용이다.' (뒤 항목의 머리 글자는 뗀다)",
               lambda: '\nㅇ 첫째 내용이다.둘째 내용이다.\n- 제조업' in text('다듬기.md'), lambda: text('다듬기.md'))
        expect(page, '— 커서는 이은 자리', lambda: (editing() or '').startswith('ㅇ 첫째') and page.evaluate("getSelection().focusOffset") == len('ㅇ 첫째 내용이다.'),
               lambda: (editing(), page.evaluate("getSelection().focusOffset")))
        page.keyboard.press('Escape')
        page.keyboard.press('Escape')
        page.wait_for_timeout(300)

        item('ㅇ 셋째').click(position={'x': 60, 'y': 8})
        page.keyboard.press('Shift+Enter')
        until(page, lambda: page.locator('#lec-view .lec-new-line .lec-line-edit').count() == 1, 4000)
        page.keyboard.press('Tab')
        page.keyboard.type('새 세부')
        page.keyboard.press('Enter')
        expect(page, "새 항목 + Tab — 'ㅇ 셋째' 아래에 '- 새 세부'", lambda: '\nㅇ 셋째\n- 새 세부\nㅁ 정책 과제' in text('다듬기.md'), lambda: text('다듬기.md'))
        page.keyboard.press('Escape')
        page.keyboard.press('Escape')
        page.wait_for_timeout(300)

        before = text('다듬기.md')
        item('- 제조업').click(position={'x': 60, 'y': 8})
        page.keyboard.press('Alt+ArrowDown')
        page.keyboard.press('Alt+ArrowDown')
        expect(page, "'- 제조업 부문' 을 Alt+↓ — 하위 ' · 반도체' 와 함께 '- 서비스업' 아래로",
               lambda: '\n- 서비스업\n- 제조업 부문\n · 반도체\nㅇ 셋째' in text('다듬기.md'), lambda: text('다듬기.md'))
        page.keyboard.press('Control+z')
        expect(page, '— Ctrl+Z', lambda: text('다듬기.md') == before, lambda: text('다듬기.md'))
        page.keyboard.press('Escape')

        got = edit('ㅇ 넷째', 60)
        page.keyboard.press('Home')
        page.keyboard.press('Delete')
        page.keyboard.type('-')
        page.keyboard.press('Enter')
        expect(page, "머리 글자 'ㅇ' 을 '-' 로 바꾸면 한 수준 아래", lambda: '\n- 넷째\n' in text('다듬기.md') and any(r['t'].startswith('- 넷째') and r['lv'] == 2 for r in items()),
               lambda: [(r['t'], r['lv']) for r in items()])
        page.keyboard.press('Escape')
        page.keyboard.press('Escape')
        page.wait_for_timeout(300)

        before = text('다듬기.md')
        item('ㅁ 정책').click(position={'x': 60, 'y': 8})
        page.keyboard.press('Delete')
        page.keyboard.press('Delete')
        expect(page, "'ㅁ 정책 과제' 줄만 지운다 — 아래 '- 넷째' 는 그대로", lambda: text('다듬기.md') == before.replace('ㅁ 정책 과제\n', ''), lambda: text('다듬기.md'))
        page.keyboard.press('Control+z')
        expect(page, '— Ctrl+Z', lambda: text('다듬기.md') == before)
        check('다듬는 동안 꺾인 줄·수준이 늘 맞다', levels_ok(items()) and not aligned(items()), [(r['t'], r['lv'], round(r['x'], 2)) for r in items()])

        # ---- 4 ----------------------------------------------------------------------------------
        print('[4. Claude 가 바깥에서 고치는 동안]')
        open_doc('바깥.md')
        check("ㅇ·- 만 쓴 문서 — ㅇ 이 맨 위(수준 0)", [r['lv'] for r in items()] == [0, 1, 0], [(r['t'], r['lv']) for r in items()])
        (proj / '바깥.md').write_text('# 바깥\n\n□ 새 절\nㅇ 첫째\n- 세부\nㅇ 둘째\n', encoding='utf-8')
        expect(page, 'Claude 가 □ 를 더하면 ㅇ 은 수준 1, - 는 2 로 다시 맞는다', lambda: [r['lv'] for r in items()] == [0, 1, 2, 1], lambda: [(r['t'], r['lv']) for r in items()], ms=8000)

        # ---- 5 ----------------------------------------------------------------------------------
        print('[5. 여러 스타일·글자 크기·좁은 칸]')
        open_doc('붙여넣기.md')
        for th in ['default', 'book', 'dark', 'manuscript']:
            page.evaluate("window.__old = document.querySelector('#lec-view').firstElementChild")
            page.select_option('#lec-theme', th)
            page.wait_for_function(f"document.documentElement.dataset.theme === '{th}' && document.querySelector('#lec-view').firstElementChild !== window.__old", timeout=10000)
            page.wait_for_timeout(300)
            rows = items()
            check(f'{th} — 수준과 꺾인 줄이 맞다', levels_ok(rows) and not aligned(rows), [(r['t'], r['lv'], round(r['x'], 2), r['gap']) for r in rows])
        page.select_option('#lec-theme', 'report')
        page.wait_for_function("document.documentElement.dataset.theme === 'report'")
        page.wait_for_timeout(500)
        page.keyboard.press('Control+=')
        page.keyboard.press('Control+=')
        page.wait_for_timeout(500)
        rows = items()
        check('글자를 키워도 (Ctrl+= 두 번) 맞다', levels_ok(rows) and not aligned(rows), [(r['t'], r['gap']) for r in rows])
        page.keyboard.press('Control+0')
        page.wait_for_timeout(300)
        open_doc('초안.md', '#lec-view h1:has-text("AI 확산")')
        page.evaluate("() => import('/static/js/spread.js').then((m) => m.toggleSpread())")
        page.wait_for_timeout(1200)
        narrow = page.evaluate(f"""() => [...document.querySelectorAll('.lec-pane')].filter((p) => p.querySelector('.lec-mark')).map((pane) => {{
          const view = pane.querySelector('.md-body'); const out = [];
          for (const p of view.querySelectorAll('.lec-mark.lec-hang, .lec-hang')) {{
            const fs = parseFloat(getComputedStyle(p).fontSize); const w = document.createTreeWalker(p, NodeFilter.SHOW_TEXT); const boxes = [];
            for (let n = w.nextNode(); n; n = w.nextNode()) for (let i = 0; i < n.length; i++) {{ if (/\\s/.test(n.data[i])) continue; const r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + 1);
              const b = [...r.getClientRects()].find((x) => x.width); if (b) boxes.push(b); if (boxes.length > 300) break; }}
            const next = boxes.find((x) => x.top > boxes[0].top + fs / 2);
            if (next && p.matches('.lec-mark')) out.push(Math.round(((next.left - boxes[1].left) / fs) * 100) / 100);
          }} return out; }})""")
        page.evaluate("() => import('/static/js/spread.js').then((m) => m.toggleSpread())")
        page.wait_for_timeout(500)
        flat = [g for pane in narrow for g in pane]
        check('모두 펼치기의 좁은 칸에서도 꺾인 줄이 머리 글자 뒤에', len(flat) >= 2 and all(abs(g) < 0.05 for g in flat), narrow)

        # ---- 6 ----------------------------------------------------------------------------------
        print('[6. 종이·html 로 저장]')
        open_doc('붙여넣기.md')
        page.emulate_media(media='print')
        pr = page.evaluate("""() => [...document.querySelectorAll('#lec-view .lec-mark')].map((p) => [getComputedStyle(p).paddingLeft, getComputedStyle(p).textIndent])""")
        page.emulate_media(media='screen')
        pads = [float(x[0][:-2]) for x in pr]
        check('종이에도 수준의 들여쓰기와 내어쓰기 (어림값)', len(set(pads)) == 4 and all('hanging' in x[1] for x in pr), pr)
        out = page.evaluate("""async () => { const { S } = await import('/static/js/store.js'); const m = await import('/static/js/mdhtml.js');
          return (await m.buildMdHtml(S.pane, '붙여넣기.md', { printCss: '' })).text; }""")
        check('html 로 저장 — 묶음·수준·내어쓰기가 그대로 (화면에서 잰 값은 뺀다)',
              out.count('class="lec-mark lec-lv') == 7 and 'lec-marklist' in out and not re.search(r'style="[^"]*--lec-hang-fit', out) and '--lec-mark-step' in out)

        # ---- 7 ----------------------------------------------------------------------------------
        print('[7. 큰 개조식 문서]')
        t0 = time.time()
        open_doc('큰.md')
        until(page, "document.querySelectorAll('#lec-view .lec-mark').length === 3000", 15000)
        took = time.time() - t0
        n = page.locator('#lec-view .lec-mark').count()
        check(f'항목 3000 — 모두 그리고 {took:.1f}초 (6초 아래)', n == 3000 and took < 6, (n, took))
        rows = page.evaluate(ITEMS.replace("document.querySelectorAll('#lec-view .lec-mark')", "[...document.querySelectorAll('#lec-view .lec-mark')].slice(0, 40)"))
        check('— 수준과 꺾인 줄이 맞다 (앞의 40 항목)', levels_ok(rows) and not aligned(rows))
        item('ㅇ 인공').click(position={'x': 60, 'y': 8})
        t0 = time.time()
        page.keyboard.press('Enter')
        until(page, lambda: editing(), 6000)
        check(f'— 한 줄 편집이 바로 열린다 ({time.time() - t0:.1f}초)', time.time() - t0 < 3)
        page.keyboard.press('Escape')

        # ---- 8 ----------------------------------------------------------------------------------
        print('[8. 헷갈리는 글]')
        open_doc('헷갈림.md')
        check("'○○ 기관'·'ㅇㅇ 표시'·머리 글자뿐인 '□' 줄은 목록이 아니다", page.locator('#lec-view .lec-mark').count() == 0)
        check("— '○○ 기관' 은 내어 쓰지도 않는다", page.locator('#lec-view p', has_text='○○ 기관').first.evaluate("(p) => !p.classList.contains('lec-hang')"))
        check('보통 목록·번호 목록은 그대로', page.locator('#lec-view ul > li').count() == 2 and page.locator('#lec-view ol > li').count() == 2)
        check("영어 문장 속 '-'·'1.5배' 는 그대로", page.locator('#lec-view .lec-hang').count() == 0, page.locator('#lec-view .lec-hang').count())

        check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
