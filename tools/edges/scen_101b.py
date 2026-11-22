"""0.101.0 사람 시나리오 2 — 개조식 보고서를 오래 다루는 동안 생기는 일 (D191 내어쓰기·D192 글머리 글자 목록).

1. 긴 항목을 칸에서 고친다 — 네 줄 넘게 꺾인 항목에서 ↑·↓·Home, 글을 넣고 저장
2. 끌어 고른 여러 항목 — Delete 로 그 줄들만, Alt+↓ 로 하위째 옮기기
3. 줄 번호 (Alt+L) — 항목마다 원문 줄 번호
4. 문서에서 찾기 (Ctrl+F) — 항목 안의 낱말
5. 절 접기 — 접은 채 스타일을 바꾸고 펴도 맞다
6. 편집 모드(Ctrl+E)에서 개조식을 더 쓴다
7. 박스글·강조글 안의 개조식
8. CRLF 파일 — 나누기·잇기·옮기기 뒤에도 줄 끝이 그대로
9. 창 크기를 여러 번 바꾼다 (양쪽 맞춤 보고서 스타일)
10. 문서 점검의 고치기 — 개조식은 그대로
11. 항목 복사"""
import json
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

L = '인공지능 확산은 산업 전반의 생산성을 끌어올리지만 그 효과는 업종과 기업 규모에 따라 크게 다르게 나타나며 정책 대응도 달라져야 한다.'
LONG = f'ㅇ 긴 항목 {L} {L} {L} {L}'
MAIN = f"""# 개조식 다듬기

## 1. 배경

ㅁ 추진 배경
{LONG}
- 제조업 {L}
 · 반도체 {L}
 · 자동차
- 서비스업 **금융**과 `물류` 를 함께 본다
ㅇ 셋째 [자료](https://example.com)

## 2. 과제

과제의 큰 줄기는 다음과 같다.

ㅁ 정책 과제
ㅇ 넷째 {L}
"""
BOXED = f"""# 상자 안

<!-- box -->
**요약**

ㅁ 요약 첫째 {L}
ㅇ 요약 세부 {L}
<!-- /box -->

> [!NOTE]
> ㅇ 강조글 안의 항목 {L}
> - 강조글 안의 세부 {L}
"""
CRLF = 'ㅁ 가 절\r\nㅇ 첫째 내용이다. 둘째 내용이다.\r\n- 세부 하나\r\n- 세부 둘\r\nㅇ 셋째\r\n'
LINT = f'# 점검\n\nㅁ 추진 배경\nㅇ 내용 {L}\n- 세부\n\n> [!NOTES]\n> 메모\n'

base = Path(tempfile.mkdtemp(prefix='lec-scen101b-'))
proj = base / '연구'
proj.mkdir(parents=True)
for name, body in {'다듬기.md': MAIN, '상자.md': BOXED, '점검.md': LINT}.items():
    (proj / name).write_text(body, encoding='utf-8', newline='\n')   # LF (Windows 의 write_text 는 CRLF 로 쓴다 — CRLF 는 crlf.md 가 따로 본다)
(proj / 'crlf.md').write_bytes(('# CRLF\r\n\r\n' + CRLF).encode('utf-8'))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False, 'theme': 'report'}), encoding='utf-8')
server, url, port = serve(proj, config)


def raw(name):
    for _ in range(40):
        try:
            return (proj / name).read_bytes()
        except OSError:
            time.sleep(0.02)
    return (proj / name).read_bytes()


def text(name):
    return raw(name).decode('utf-8')


ITEMS = """() => [...document.querySelectorAll('#lec-view .lec-mark')].filter((p) => p.getClientRects().length).map((p) => {
  const fs = parseFloat(getComputedStyle(p).fontSize); const view = document.querySelector('#lec-view').getBoundingClientRect();
  const boxes = []; const w = document.createTreeWalker(p, NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) for (let i = 0; i < n.length; i++) { if (/[\\s\\u3000]/.test(n.data[i])) continue; const r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + 1);
    const b = [...r.getClientRects()].find((x) => x.width); if (b) boxes.push({ left: b.left, top: b.top }); if (boxes.length > 600) break; }
  if (!boxes.length) return null;
  const body = boxes[1]; const next = boxes.find((x) => x.top > boxes[0].top + fs / 2);
  return { t: p.textContent.slice(0, 5), lv: Number((/lec-lv(\\d)/.exec(p.className) || [])[1]), x: (boxes[0].left - view.left) / fs, lines: p.dataset.lines,
    gap: next && body ? Math.round(((next.left - body.left) / fs) * 100) / 100 : null };
}).filter(Boolean)"""
CARET = """() => { const sp = document.activeElement; if (!sp?.classList?.contains('lec-line-edit')) return null;
  const sel = getSelection(); const pre = document.createRange(); pre.selectNodeContents(sp); pre.setEnd(sel.focusNode, sel.focusOffset);
  const node = sp.firstChild; const text = sp.textContent; const starts = [0]; let prev = null;
  for (let i = 0; node && i < text.length; i++) { const r = document.createRange(); r.setStart(node, i); r.setEnd(node, i + 1);
    const b = [...r.getClientRects()].find((x) => x.width); if (!b) continue; if (prev != null && b.top - prev > b.height / 2) starts.push(i); prev = b.top; }
  return { offset: pre.toString().length, starts, text: text.slice(0, 6) }; }"""

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
        editing = lambda: page.evaluate("document.activeElement?.classList?.contains('lec-line-edit') ? document.activeElement.textContent : null")   # noqa: E731
        label = lambda: page.evaluate("(() => { const b = document.querySelector('#lec-st-lint'); return b.hidden ? null : b.textContent.trim(); })()")   # noqa: E731

        def open_doc(name, sel='#lec-view h1'):
            page.locator(f'#lec-tree .row.file[data-doc="{name}"]').click()
            page.wait_for_selector(sel)
            page.wait_for_timeout(500)

        def items():
            return page.evaluate(ITEMS)

        def item(start):
            return page.locator('#lec-view .lec-mark', has_text=start).first

        def good(rows):
            xs = {}
            for r in rows:
                xs.setdefault(r['lv'], set()).add(round(r['x'], 1))
            return all(len(v) == 1 for v in xs.values()) and all(r['gap'] is None or abs(r['gap']) < 0.05 for r in rows)

        def quit_edit():
            page.keyboard.press('Escape')
            page.keyboard.press('Escape')
            page.wait_for_timeout(300)

        # ---- 1 ----------------------------------------------------------------------------------
        print('[1. 긴 항목을 칸에서 고친다]')
        open_doc('다듬기.md')
        item('ㅇ 긴 항목').click(position={'x': 60, 'y': 8})
        page.keyboard.press('Enter')
        until(page, lambda: editing(), 4000)
        c = page.evaluate(CARET)
        n = len(c['starts']) if c else 0
        check('긴 항목이 칸에서 네 줄 넘게 꺾인다 (시험의 전제)', n >= 4, c)
        page.keyboard.press('End')
        page.keyboard.press('ArrowUp')
        page.keyboard.press('ArrowUp')
        page.keyboard.press('Home')
        page.wait_for_timeout(150)
        c = page.evaluate(CARET)
        at = c['offset'] if c else -1
        check('↑ 두 번과 Home — 칸 안에서 위 화면 줄의 맨 앞 (내어 쓴 줄도)', bool(c) and at in c['starts'] and at > 0, c)
        page.keyboard.press('ArrowUp')
        page.wait_for_timeout(150)
        c2 = page.evaluate(CARET)
        check('— 거기서 ↑ 도 칸 안에서 (항목을 떠나지 않는다)', bool(c2) and c2['text'].startswith('ㅇ 긴') and c2['offset'] < at, c2)
        page.keyboard.press('ArrowDown')
        page.keyboard.press('Home')
        page.keyboard.type('[넣음]')
        page.keyboard.press('Enter')
        expect(page, '— 넣은 글이 그 화면 줄의 맨 앞에 저장', lambda: LONG[:at] + '[넣음]' + LONG[at:] in text('다듬기.md'), lambda: text('다듬기.md')[:300])
        quit_edit()
        check('— 고친 뒤에도 수준·꺾인 줄이 맞다', good(items()), items())

        # ---- 2 ----------------------------------------------------------------------------------
        print('[2. 끌어 고른 여러 항목]')

        def drag(a_text, z_text):
            a = item(a_text).bounding_box()
            z = item(z_text).bounding_box()
            page.mouse.move(a['x'] + a['width'] * 0.5, a['y'] + 10)
            page.mouse.down()
            page.mouse.move(z['x'] + 60, z['y'] + 10, steps=12)
            page.mouse.up()
            page.wait_for_timeout(200)

        before = text('다듬기.md')
        drag('· 반도체', '- 서비스업')
        page.keyboard.press('Delete')
        expect(page, "'· 반도체'~'- 서비스업' 을 끌어 Delete 한 번 — 그 세 줄만", lambda: text('다듬기.md') == before.replace(f' · 반도체 {L}\n · 자동차\n- 서비스업 **금융**과 `물류` 를 함께 본다\n', ''),
               lambda: text('다듬기.md')[-500:])
        page.keyboard.press('Control+z')
        expect(page, '— Ctrl+Z', lambda: text('다듬기.md') == before)
        until(page, lambda: page.locator('#lec-view .lec-mark', has_text='서비스업').count() == 1, 6000)   # 되돌린 글이 화면에 다시 그려진 뒤에 끈다 (사람도 그렇다)
        page.wait_for_timeout(800)
        drag('- 제조업', '· 자동차')
        page.keyboard.press('Alt+ArrowDown')
        expect(page, "'- 제조업'~'· 자동차' 를 끌어 Alt+↓ — 하위째 '- 서비스업' 아래로", lambda: f'\n- 서비스업 **금융**과 `물류` 를 함께 본다\n- 제조업 {L}\n · 반도체 {L}\n · 자동차\nㅇ 셋째' in text('다듬기.md'),
               lambda: text('다듬기.md')[-500:])
        page.keyboard.press('Control+z')
        expect(page, '— Ctrl+Z', lambda: text('다듬기.md') == before)
        page.keyboard.press('Escape')

        # ---- 3 ----------------------------------------------------------------------------------
        print('[3. 줄 번호]')
        page.keyboard.press('Alt+l')
        page.wait_for_timeout(500)
        nums = page.evaluate("""() => { const g = document.querySelector('.lec-gutter'); if (!g) return null;
          const spans = [...g.children].map((s) => [Number(s.textContent), s.getBoundingClientRect().top]);
          const off = (el) => { const n = Number(el.dataset.lines.split('-')[0]); const s = spans.find((x) => x[0] === n); return s ? Math.round(s[1] - el.getBoundingClientRect().top) : null; };
          const para = [...document.querySelectorAll('#lec-view > p')].find((p) => p.textContent.startsWith('과제의'));
          return { para: off(para), marks: [...document.querySelectorAll('#lec-view .lec-mark')].map(off) }; }""")
        check('항목마다 그 원문 줄 번호가 보통 문단과 같은 자리에 (2px 안)', nums and nums['para'] is not None and all(x is not None and abs(x - nums['para']) <= 2 for x in nums['marks']), nums)
        page.keyboard.press('Alt+l')

        # ---- 4 ----------------------------------------------------------------------------------
        print('[4. 문서에서 찾기]')
        page.locator('#lec-view h1').click()
        page.wait_for_timeout(300)
        page.keyboard.press('Control+f')
        until(page, "!document.querySelector('#lec-findbar').hidden", 3000)   # playwright 의 '보임' 판정은 이 막대를 숨은 것으로 볼 때가 있다 (화면에는 열려 있다)
        page.keyboard.type('자동차')
        page.wait_for_timeout(500)
        cnt = page.inner_text('#lec-find-count')
        hit = page.evaluate("(() => { const h = CSS.highlights.get('lec-find-current'); const r = h && [...h][0]; const el = r?.startContainer.parentElement; return el ? el.closest('.lec-mark')?.textContent.slice(0, 4) : null; })()")   # 찾기는 CSS 하이라이트 (DOM 을 바꾸지 않는다)
        check("'자동차' 를 찾으면 그 항목 안에", '1' in cnt and hit == '· 자동', (cnt, hit))
        page.keyboard.press('Escape')

        # ---- 5 ----------------------------------------------------------------------------------
        print('[5. 절 접기]')
        page.locator('#lec-view h2', has_text='1. 배경').click()
        page.keyboard.press('Control+Shift+BracketLeft')
        page.wait_for_timeout(400)
        hidden = page.evaluate("[...document.querySelectorAll('#lec-view .lec-mark')].filter((p) => !p.getClientRects().length).length")
        check("'1. 배경' 절을 접으면 그 항목들이 숨는다", hidden >= 6, hidden)
        page.evaluate("window.__old = document.querySelector('#lec-view').firstElementChild")
        page.select_option('#lec-theme', 'book')
        page.wait_for_function("document.documentElement.dataset.theme === 'book' && document.querySelector('#lec-view').firstElementChild !== window.__old", timeout=10000)
        page.wait_for_timeout(500)
        page.locator('#lec-view h2', has_text='1. 배경').click()
        page.keyboard.press('Control+Shift+BracketRight')
        page.wait_for_timeout(500)
        rows = items()
        check('접은 채 스타일을 바꾸고 펴도 수준·꺾인 줄이 맞다', len(rows) >= 8 and good(rows), [(r['t'], r['lv'], round(r['x'], 2), r['gap']) for r in rows])
        page.select_option('#lec-theme', 'report')
        page.wait_for_function("document.documentElement.dataset.theme === 'report'")
        page.wait_for_timeout(600)

        # ---- 6 ----------------------------------------------------------------------------------
        print('[6. 편집 모드에서 개조식을 더 쓴다]')
        page.locator('#lec-view h1').click()
        page.keyboard.press('Control+e')
        page.wait_for_selector('.CodeMirror, .cm-editor', timeout=8000)
        page.wait_for_timeout(400)
        page.keyboard.press('Control+End')
        page.keyboard.type('ㅇ 편집 모드에서 쓴 항목\n- 그 세부\n')
        page.keyboard.press('Control+s')
        expect(page, '저장 — 파일 끝에 두 줄', lambda: text('다듬기.md').endswith('ㅇ 편집 모드에서 쓴 항목\n- 그 세부\n'), lambda: text('다듬기.md')[-120:])
        page.keyboard.press('Escape')
        page.wait_for_timeout(300)
        if page.locator('.CodeMirror, .cm-editor').count():
            page.keyboard.press('Control+e')
        expect(page, "— 읽는 화면에 'ㅇ' 수준 1·'-' 수준 2 의 항목으로", lambda: [(r['t'][:3], r['lv']) for r in items()][-2:] == [('ㅇ 편', 1), ('- 그', 2)],
               lambda: [(r['t'], r['lv']) for r in items()][-3:], ms=8000)

        # ---- 7 ----------------------------------------------------------------------------------
        print('[7. 박스글·강조글 안의 개조식]')
        open_doc('상자.md')
        box = page.evaluate("[...document.querySelectorAll('#lec-view aside.lec-textbox .lec-mark')].map((p) => p.className)")
        note = page.evaluate("[...document.querySelectorAll('#lec-view blockquote .lec-mark')].map((p) => p.className)")
        check('박스글 안의 ㅁ·ㅇ — 수준 0·1', len(box) == 2 and 'lec-lv0' in box[0] and 'lec-lv1' in box[1], box)
        check('강조글 안의 ㅇ·- — 문서의 차례로 수준 1·2', len(note) == 2 and 'lec-lv1' in note[0] and 'lec-lv2' in note[1], note)
        rows = items()
        check('— 꺾인 줄은 머리 글자 뒤에 (박스글·강조글은 안쪽 여백이 달라 자리는 상자마다)', all(r['gap'] is None or abs(r['gap']) < 0.05 for r in rows) and sum(r['gap'] is not None for r in rows) >= 3, rows)

        # ---- 8 ----------------------------------------------------------------------------------
        print('[8. CRLF 파일]')
        open_doc('crlf.md')
        item('ㅇ 첫째').click(position={'x': 60, 'y': 8})
        page.keyboard.press('Enter')
        until(page, lambda: editing(), 4000)
        page.keyboard.press('Home')
        for _ in range(len('ㅇ 첫째 내용이다. ')):
            page.keyboard.press('ArrowRight')
        page.keyboard.press('Shift+Enter')
        expect(page, '나누기 — 두 항목, 줄 끝은 모두 CRLF', lambda: raw('crlf.md') == ('# CRLF\r\n\r\nㅁ 가 절\r\nㅇ 첫째 내용이다.\r\nㅇ 둘째 내용이다.\r\n- 세부 하나\r\n- 세부 둘\r\nㅇ 셋째\r\n').encode('utf-8'),
               lambda: raw('crlf.md'))
        until(page, lambda: editing() == 'ㅇ 둘째 내용이다.', 6000)   # 나눈 뒤 새 항목의 칸이 열릴 때까지
        page.keyboard.press('Home')
        page.keyboard.press('Backspace')
        expect(page, '잇기 — 원래 한 항목으로 (머리 글자는 떼고), CRLF 그대로', lambda: raw('crlf.md') == ('# CRLF\r\n\r\nㅁ 가 절\r\nㅇ 첫째 내용이다.둘째 내용이다.\r\n- 세부 하나\r\n- 세부 둘\r\nㅇ 셋째\r\n').encode('utf-8'),
               lambda: raw('crlf.md'))
        quit_edit()
        item('- 세부 하나').click(position={'x': 60, 'y': 8})
        page.keyboard.press('Alt+ArrowDown')
        page.keyboard.press('Alt+ArrowDown')
        expect(page, '옮기기 — CRLF 그대로', lambda: raw('crlf.md').endswith('- 세부 둘\r\n- 세부 하나\r\nㅇ 셋째\r\n'.encode('utf-8')) and b'\n' not in raw('crlf.md').replace(b'\r\n', b''),
               lambda: raw('crlf.md'))
        page.keyboard.press('Escape')

        # ---- 9 ----------------------------------------------------------------------------------
        print('[9. 창 크기를 여러 번 바꾼다]')
        open_doc('다듬기.md')
        bad = []
        for w in (1300, 980, 760, 1150, 1300):
            page.set_viewport_size({'width': w, 'height': 900})
            page.wait_for_timeout(500)
            rows = items()
            if not good(rows):
                bad.append((w, [(r['t'], r['gap']) for r in rows if r['gap'] is not None and abs(r['gap']) >= 0.05]))
        check('창 폭 1300·980·760·1150·1300 — 늘 수준·꺾인 줄이 맞다 (양쪽 맞춤)', not bad, bad)

        # ---- 10 ---------------------------------------------------------------------------------
        print('[10. 문서 점검의 고치기]')
        open_doc('점검.md')
        expect(page, "강조글 종류 오타 하나 — '점검 1곳' (개조식에는 경보가 없다)", lambda: label() == '점검 1곳', label)
        page.locator('#lec-st-lint').click()
        page.wait_for_selector('#lec-menu:not([hidden]) .menu-head', timeout=3000)
        page.locator('#lec-menu .menu-row', has_text='강조글 종류').locator('.menu-side').click()
        expect(page, '고치기 — 강조글만 바뀌고 개조식은 그대로', lambda: text('점검.md') == LINT.replace('[!NOTES]', '[!NOTE]'), lambda: text('점검.md'))
        expect(page, '— 점검이 사라진다', lambda: label() is None, label)

        # ---- 11 ---------------------------------------------------------------------------------
        print('[11. 항목 복사]')
        item('- 세부').click(position={'x': 40, 'y': 8})
        page.wait_for_timeout(200)
        page.evaluate("navigator.clipboard.writeText('')")
        page.keyboard.press('Control+c')
        clip = until(page, lambda: page.evaluate('navigator.clipboard.readText()'), 3000)
        check("현재 줄의 Ctrl+C — '- 세부' 그대로 (머리 글자까지)", (clip or '').strip() == '- 세부', clip)

        check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
