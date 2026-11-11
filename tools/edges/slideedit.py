"""슬라이드 편집 (0.68): 넣기 창, 칸, 차트 값 표, 장 옆 패널, 넘친 칸. 앱이 쓰는 것은 지금의 md 문법 그대로다."""
import base64
import json
import re
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop

DOC = '''---
marp: true
title: 시험
---

<!-- layout: two -->

## 첫 장 제목

::: a
첫 문단

- 항목 하나
:::

::: b card center
| 품목 | 값 |
|---|---|
| 가 | 1 |
| 나 | 2 |
:::

---

<!-- layout: two -->

## 둘째 장 제목

::: a
```vega-lite
{
  "width": "container",
  "data": {"values": [{"항목": "가", "값": 3}, {"항목": "나", "값": 5}]},
  "mark": "bar",
  "encoding": {
    "x": {"field": "항목", "type": "nominal"},
    "y": {"field": "값", "type": "quantitative"}
  }
}
```
:::

::: b
$$
x^2
$$

> [!NOTE]
> 박스 글
:::

---

## 끝 장

끝 문단
'''

base = Path(tempfile.mkdtemp(prefix='lec-slideedit-'))
proj = base / 'proj'
proj.mkdir()
doc = proj / '장.md'
doc.write_text(DOC, encoding='utf-8')
(proj / 'i.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="80"><rect width="200" height="80" fill="#ccd"/></svg>', encoding='utf-8')
server, url, port = serve(proj, base / 'config')
extra = []

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_context(viewport={'width': 1400, 'height': 900}, permissions=['clipboard-read', 'clipboard-write']).new_page()
        page.on('pageerror', lambda e: extra.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        page.locator('#lec-tree .row.file[data-doc="장.md"]').click(modifiers=['Alt'])
        page.wait_for_selector('#lec-view.lec-deck', timeout=8000)
        page.wait_for_timeout(1500)
        cells = lambda: page.evaluate("[...document.querySelectorAll('#lec-view .lec-line-edit')].map((e) => e.textContent)")
        toast = lambda: page.text_content('#lec-toast') or ''
        src = lambda: doc.read_text(encoding='utf-8')
        marks = lambda: [s for s in src().split('\n') if s.startswith(':::') or s == '---']
        MARKS = [s for s in DOC.split('\n') if s.startswith(':::') or s == '---']
        walls = lambda name: check(f'{name} — 칸과 장이 그대로', marks() == MARKS, marks())

        def reset():
            for _ in range(4):
                page.keyboard.press('Escape')
                page.wait_for_timeout(60)
            if src() != DOC:
                doc.write_text(DOC, encoding='utf-8')
                page.wait_for_timeout(1500)

        def open_cell(sel, text=None):
            el = page.locator(sel, has_text=text).first if text else page.locator(sel).first
            el.scroll_into_view_if_needed()
            el.dblclick()
            page.wait_for_timeout(450)

        def fresh_after(sel, text=None):
            open_cell(sel, text)
            page.keyboard.press('End')
            page.keyboard.press('Control+Enter')
            page.wait_for_timeout(450)

        def choose(word):
            page.keyboard.press('/')
            page.wait_for_selector('#lec-put:not([hidden])', timeout=3000)
            page.keyboard.type(word)
            page.wait_for_timeout(130)
            page.keyboard.press('Enter')
            page.wait_for_timeout(600)

        def menu(sel, word, text=None):
            el = page.locator(sel, has_text=text).first if text else page.locator(sel).first
            el.scroll_into_view_if_needed()
            el.click(button='right')
            page.wait_for_selector('#lec-menu button', timeout=3000)
            page.locator('#lec-menu button', has_text=word).first.click()
            page.wait_for_timeout(700)

        print('[넣기 창]')
        fresh_after('#lec-view .lec-cell p', '첫 문단')
        page.keyboard.press('/')
        page.wait_for_selector('#lec-put:not([hidden])', timeout=3000)
        items = page.inner_text('#lec-put-list')
        check('칸의 빈 줄에서 넣기 창이 열린다', all(w in items for w in ('제목 2', '표', '강조글 — 참고', '그림', '차트', '발표자 노트')), items[:120])
        check('슬라이드에 맞지 않는 것은 뺀다', not any(w in items for w in ('구분선', '첨부', '부록', '표 주')), items)
        page.keyboard.press('Escape')
        page.wait_for_timeout(150)
        choose('참고')
        page.keyboard.type('칸 안의 박스')
        page.keyboard.press('Enter')
        page.wait_for_timeout(900)
        check('강조글이 칸 안에 들어간다', '> [!NOTE]\n> 칸 안의 박스\n' in src(), src()[:300])
        walls('강조글')
        reset()

        fresh_after('#lec-view .lec-cell p', '첫 문단')
        choose('표')
        page.wait_for_selector('#lec-put:not([hidden])', timeout=3000)
        page.keyboard.type('2x1')
        page.keyboard.press('Enter')
        page.wait_for_timeout(900)
        check('슬라이드의 표는 캡션 없이', '표 1.' not in src() and '|  |  |\n| --- | --- |\n|  |  |' in src(), src()[:300])
        walls('표')
        reset()

        print('[서식과 붙여 넣기]')
        open_cell('#lec-view .lec-cell p', '첫 문단')
        page.keyboard.press('Control+a')
        page.keyboard.press('Control+b')
        page.keyboard.press('Enter')
        page.wait_for_timeout(800)
        check('Ctrl+B', '**첫 문단**' in src(), src()[:200])
        reset()

        open_cell('#lec-view .lec-cell p', '첫 문단')
        page.keyboard.press('End')
        page.evaluate("navigator.clipboard.writeText('가\\n\\n나\\n')")
        page.keyboard.press('Control+v')
        page.wait_for_timeout(1000)
        check('여러 줄은 칸 안에 줄마다', '::: a\n첫 문단가\n\n나\n' in src(), src()[:220])
        walls('붙여 넣기')
        reset()

        fresh_after('#lec-view .lec-cell p', '첫 문단')
        page.evaluate("navigator.clipboard.writeText('이름\\t값\\n가\\t1\\n')")
        page.keyboard.press('Control+v')
        page.wait_for_timeout(1000)
        check('엑셀 범위는 칸 안의 표로', '| 이름 | 값 |\n| --- | --- |\n| 가 | 1 |' in src(), src()[:260])
        walls('엑셀')
        reset()

        print('[그림]')
        png = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
        paste = '''(b) => { const bytes = Uint8Array.from(atob(b), (c) => c.charCodeAt(0));
          const dt = new DataTransfer(); dt.items.add(new File([bytes], 'x.png', { type: 'image/png' }));
          document.activeElement.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true })); }'''
        fresh_after('#lec-view .lec-cell p', '첫 문단')
        page.evaluate(paste, png)
        page.wait_for_timeout(1400)
        check('그림을 칸에 붙여 넣는다', '![w:400 그림](<장-그림/그림 1.png>)' in src() and (proj / '장-그림' / '그림 1.png').exists(), src()[:260])
        walls('그림')
        at = next(i for i, s in enumerate(src().split('\n')) if s.startswith('![w:400')) + 1
        page.keyboard.press('Escape')
        page.wait_for_timeout(300)
        page.evaluate("(n) => import('/static/js/spotlight.js').then((m) => m.followLine(n))", at)
        page.locator('#lec-view .lec-cell p').first.click()
        page.evaluate("(n) => import('/static/js/spotlight.js').then((m) => m.followLine(n))", at)
        page.wait_for_timeout(200)
        page.keyboard.press('Control+Shift+Period')
        page.wait_for_timeout(800)
        check('그림 폭을 키운다', '![w:420 그림]' in src(), src()[:240])
        reset()

        print('[표의 메뉴]')
        menu('#lec-view .lec-cell td', '오른쪽에 열 더하기')
        check('칸의 표에 열을 더한다', '| 품목 |  | 값 |' in src(), src()[:260])
        walls('열')
        reset()
        menu('#lec-view .lec-cell td', '이 표를 차트로')
        page.wait_for_timeout(600)
        check('표를 같은 값의 차트로', src().find('```vega-lite') < src().find('## 둘째 장 제목') and '{"품목":"가","값":1}' in src().replace(' ', ''), src()[:400])
        check('차트가 그려진다', page.locator('#lec-view .lec-slide pre.lec-chart').count() == 2)
        walls('표를 차트로')
        reset()

        print('[차트 값 표]')
        chart_line = next(i for i, s in enumerate(DOC.split('\n')) if s.startswith('```vega-lite')) + 1
        page.locator('#lec-view .lec-cell p').first.click()
        page.evaluate("(n) => import('/static/js/spotlight.js').then((m) => m.followLine(n))", chart_line)
        page.wait_for_timeout(200)
        page.keyboard.press('F2')
        page.wait_for_selector('.lec-values input', timeout=4000)
        page.wait_for_timeout(300)
        box = page.evaluate("""() => { const u = document.querySelector('.lec-unfold').getBoundingClientRect(); return [u.left, u.top, u.right, u.bottom, innerWidth, innerHeight]; }""")
        check('패널이 화면 안에 있다', box[0] >= 0 and box[1] >= 0 and box[2] <= box[4] and box[3] <= box[5], box)
        check('값이 표로 나온다', page.evaluate("[...document.querySelectorAll('.lec-values input')].map((i) => i.value)") == ['가', '3', '나', '5'])
        check('차트는 칸에 그대로 보인다', page.locator('#lec-view .lec-cell pre.lec-chart svg').count() == 1)
        check('초점은 첫 칸', page.evaluate("document.activeElement?.dataset.r") == '0')
        page.locator('.lec-values input[data-r="0"][data-c="1"]').fill('30')
        page.keyboard.press('Tab')
        page.wait_for_timeout(900)
        spec = json.loads('\n'.join(src().split('\n')[chart_line:chart_line + 9]))
        check('값을 고치면 수로 저장한다', spec['data']['values'][0] == {'항목': '가', '값': 30}, spec['data'])
        check('나머지 글은 그대로', '"width": "container",' in src() and '    "x": {"field": "항목", "type": "nominal"},' in src(), src()[300:520])
        check('패널이 그대로', page.locator('.lec-values').count() == 1)
        page.locator('.lec-values input[data-r="1"][data-c="1"]').click()
        page.keyboard.press('Control+Enter')
        page.wait_for_timeout(900)
        check('Ctrl+Enter 로 새 행', page.locator('.lec-values tbody tr').count() == 3, page.locator('.lec-values tbody tr').count())
        check('새 행으로 초점이 간다', page.evaluate("document.activeElement?.dataset.r") == '2')
        page.keyboard.type('다')
        page.keyboard.press('Tab')
        page.keyboard.type('7')
        page.keyboard.press('Tab')
        page.wait_for_timeout(900)
        check('새 행의 값', '"항목":"다","값":7' in src().replace(' ', ''), src()[300:480])
        page.locator('.lec-values input[data-r="2"][data-c="0"]').click()
        page.keyboard.press('Control+Shift+K')
        page.wait_for_timeout(900)
        check('Ctrl+Shift+K 로 행 지우기', page.locator('.lec-values tbody tr').count() == 2)
        page.locator('.lec-unfold-foot button', has_text='선').click()
        page.wait_for_timeout(900)
        check('차트 종류를 바꾼다', '"mark": "line"' in src(), src()[280:520])
        check('패널에 지금 종류가 표시된다', page.inner_text('.lec-unfold-foot button.on') == '선')
        page.locator('.lec-unfold-bar button', has_text='원문 보기').click()
        page.wait_for_timeout(300)
        check('원문 보기', page.locator('.lec-unfold pre code').count() == 1 and page.locator('.lec-values').count() == 0)
        page.locator('.lec-unfold-bar button', has_text='값 표로 보기').click()
        page.wait_for_timeout(300)
        check('값 표로 돌아온다', page.locator('.lec-values').count() == 1)
        page.keyboard.press('Escape')
        page.wait_for_timeout(600)
        check('Esc 로 접는다', page.locator('.lec-unfold').count() == 0)
        page.keyboard.press('Control+z')
        page.wait_for_timeout(700)
        check('되돌린다', '"mark": "bar"' in src(), src()[280:420])
        reset()

        print('[수식 패널]')
        math_line = next(i for i, s in enumerate(DOC.split('\n')) if s == '$$') + 1
        page.locator('#lec-view .lec-cell p').first.click()
        page.evaluate("(n) => import('/static/js/spotlight.js').then((m) => m.followLine(n))", math_line)
        page.wait_for_timeout(200)
        page.keyboard.press('F2')
        page.wait_for_timeout(800)
        check('수식은 원문 줄로', cells() == ['x^2'], cells())
        check('수식이 칸에 남는다', page.locator('#lec-view .lec-cell .math-block').count() == 1)
        page.keyboard.press('Control+a')
        page.keyboard.type('y^2')
        page.keyboard.press('Enter')
        page.wait_for_timeout(900)
        check('줄을 고친다', '$$\ny^2\n$$' in src(), src()[-140:])
        walls('수식')
        reset()

        print('[안내 글]')
        page.locator('#lec-view .lec-cell p').first.click()
        page.keyboard.press('Control+m')
        page.wait_for_selector('#lec-gallery-list .lec-tpl', timeout=6000)
        page.locator('#lec-gallery-list .lec-tpl').nth(4).click()
        page.wait_for_timeout(1800)
        check('새 장의 제목은 골라 둔다', page.evaluate("getSelection().toString()") == cells()[0] != '', (cells(), page.evaluate("getSelection().toString()")))
        page.keyboard.type('새 제목')
        page.keyboard.press('ArrowDown')
        page.wait_for_timeout(900)
        check('치면 바뀐다', '## 새 제목' in src(), [s for s in src().split('\n') if s.startswith('##')])
        check('다음 안내 글도 골라 둔다', page.evaluate("getSelection().toString()") == cells()[0] != '', (cells(), page.evaluate("getSelection().toString()")))
        reset()

        print('[칸]')
        menu('#lec-view .lec-cell p', '칸 꾸밈', '첫 문단')
        page.wait_for_selector('#lec-put:not([hidden])', timeout=3000)
        page.keyboard.type('메모')
        page.wait_for_timeout(130)
        page.keyboard.press('Enter')
        page.wait_for_timeout(800)
        check('칸 꾸밈을 메뉴로', '::: a note\n' in src(), src()[:200])
        menu('#lec-view .lec-cell td', '칸 꾸밈')
        page.wait_for_selector('#lec-put:not([hidden])', timeout=3000)
        page.keyboard.type('없음')
        page.wait_for_timeout(130)
        page.keyboard.press('Enter')
        page.wait_for_timeout(800)
        check('꾸밈을 떼도 다른 낱말은 남는다', '::: b center\n' in src(), src()[:260])
        reset()
        menu('#lec-view .lec-cell p', '이 칸을 뒤로', '첫 문단')
        check('칸의 글을 맞바꾼다', '::: a\n| 품목 | 값 |' in src() and '::: b card center\n첫 문단' in src(), src()[:320])
        reset()
        page.once('dialog', lambda d: d.accept())
        menu('#lec-view .lec-cell p', '칸 비우기', '첫 문단')
        check('칸을 비운다', '::: a\n:::\n' in src(), src()[:200])
        reset()

        print('[넘친 칸]')
        long = DOC.replace('첫 문단\n', '\n\n'.join(f'줄 {i}' for i in range(14)) + '\n', 1)
        doc.write_text(long, encoding='utf-8')
        page.wait_for_timeout(1700)
        check('칸이 넘쳤다', page.locator('#lec-view .lec-cell-over').count() == 1)
        menu('#lec-view .lec-cell-over p', '넘친 줄을 다음 장으로')
        page.wait_for_timeout(600)
        check('같은 배치의 새 장으로 옮긴다', src().count('<!-- layout: two -->') == 3 and '## 첫 장 제목 (이어서)' in src(), src()[:500])
        check('넘침이 풀린다', page.locator('#lec-view .lec-cell-over').count() == 0, page.locator('#lec-view .lec-cell-over').count())
        page.keyboard.press('Control+z')
        page.wait_for_timeout(800)
        check('되돌리기 한 걸음', src() == long, src()[:200])
        reset()

        print('[장과 노트]')
        open_cell('#lec-view .lec-slide h2', '둘째 장 제목')
        page.keyboard.press('Alt+ArrowUp')
        page.wait_for_timeout(1000)
        heads = [s for s in src().split('\n') if s.startswith('## ')]
        check('제목 줄의 Alt+↑ 로 장을 옮긴다', heads == ['## 둘째 장 제목', '## 첫 장 제목', '## 끝 장'], heads)
        check('제목 줄을 이어서 연다', cells() == ['둘째 장 제목'], cells())
        reset()

        menu('#lec-view .lec-cell p', '발표자 노트 쓰기', '첫 문단')
        page.wait_for_selector('#lec-put:not([hidden])', timeout=3000)
        page.keyboard.type('여기서 잠깐 멈춘다')
        page.keyboard.press('Enter')
        page.wait_for_timeout(800)
        check('노트를 장 끝에 쓴다', 0 < src().find('<!-- 여기서 잠깐 멈춘다 -->') < src().find('## 둘째 장 제목') and src().find('::: b card') < src().find('<!-- 여기서'), src()[:360])
        walls('노트')
        reset()

        print('[칸 없이 새 줄]')
        page.locator('#lec-view .lec-cell p', has_text='첫 문단').click()
        page.wait_for_timeout(250)
        page.keyboard.press('Control+Enter')
        page.wait_for_timeout(450)
        page.keyboard.type('아래 글')
        page.keyboard.press('Enter')
        page.wait_for_timeout(900)
        check('칸의 현재 줄에서 Ctrl+Enter', '::: a\n첫 문단\n\n아래 글\n' in src(), src()[:200])
        walls('Ctrl+Enter')
        reset()
        page.locator('#lec-view .lec-cell p', has_text='첫 문단').click()
        page.wait_for_timeout(250)
        page.keyboard.press('Control+l')
        page.wait_for_timeout(250)
        page.keyboard.press('Control+Shift+Enter')
        page.wait_for_timeout(450)
        page.keyboard.type('위 글')
        page.keyboard.press('Enter')
        page.wait_for_timeout(900)
        check('고른 줄의 Ctrl+Shift+Enter 는 칸 안에', '위 글\n\n첫 문단\n' in src() and src().index('::: a') < src().index('위 글'), src()[:200])
        walls('위 줄')
        reset()
        chart_line2 = next(i for i, s in enumerate(DOC.split('\n')) if s.startswith('```vega-lite')) + 1
        page.locator('#lec-view .lec-cell p').first.click()
        page.evaluate("(n) => import('/static/js/spotlight.js').then((m) => m.followLine(n))", chart_line2)
        page.wait_for_timeout(250)
        page.keyboard.press('Control+Enter')
        page.wait_for_timeout(450)
        page.keyboard.type('차트 설명')
        page.keyboard.press('Enter')
        page.wait_for_timeout(900)
        check('차트 아래는 칸 안의 문단', '```\n\n차트 설명\n' in src() and src().index('차트 설명') < src().index('::: b\n'), src()[300:640])
        walls('차트 아래')
        reset()

        print('[이어 쓰기와 찾아 바꾸기]')
        page.locator('#lec-view .lec-slide p', has_text='끝 문단').last.click()
        page.wait_for_timeout(250)
        page.keyboard.press('ArrowDown')
        page.wait_for_timeout(450)
        check('끝 장의 끝 줄 ↓ 는 새 줄', cells() == [''] and src() == DOC, cells())
        page.keyboard.type('덧붙인 글')
        page.keyboard.press('Enter')
        page.wait_for_timeout(900)
        check('장 끝에 들어간다', src().rstrip().endswith('끝 문단\n\n덧붙인 글'), src()[-60:])
        reset()

        doc.write_text(DOC.replace('첫 문단', 'layout 글'), encoding='utf-8')
        page.wait_for_timeout(1600)
        page.locator('#lec-view .lec-cell p').first.click()
        page.wait_for_timeout(200)
        page.keyboard.press('Control+h')
        page.wait_for_selector('#lec-replace:not([hidden])', timeout=3000)
        page.keyboard.type('layout')
        page.fill('#lec-replace-input', '바뀐')
        page.click('#lec-replace-all')
        page.wait_for_timeout(900)
        check('지시어 줄은 건너뛴다', '<!-- layout: two -->' in src() and '바뀐 글' in src(), src()[:200])
        page.click('#lec-find-close')
        reset()
        b.close()
    check('페이지 오류 없음', not extra, extra)
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
