"""이어 쓴 줄의 한 줄 편집 (2026-11-19 사용자 보고): 빈 줄 없이 줄마다 이어 쓴 문단(설정 md_breaks — 줄마다 <br>)에서 한 줄을 열어도
다음 줄이 편집 칸 옆으로 올라붙지 않는다 — 첫·가운데·끝 줄, 그만두면 원래 모양, 고쳐 저장하면 그 줄만, 목록 항목 안의 이어 쓴 줄,
설정을 끄면(표준 Markdown — 원래 한 줄로 이어 보임) 그대로"""
import json
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop

base = Path(tempfile.mkdtemp(prefix='lec-linebreaks-'))
proj = base / 'proj'
proj.mkdir(parents=True)
LINES = ['첫째 줄 문단입니다.', '둘째 줄 문단입니다.', '셋째 줄 문단입니다.', '넷째 줄 문단입니다.']
DOC = '# 이어 쓴 줄\n\n' + '\n'.join(LINES) + '\n\n- 목록 첫 줄\n  이어 쓴 둘째 줄\n- 다음 항목\n'
(proj / '이어.md').write_text(DOC, encoding='utf-8')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)

# 문단(또는 목록 항목)이 화면에 몇 줄로 보이나 — 글자 상자의 위치로 센다
ROWS = """(sel) => { const el = document.querySelector(sel); const r = document.createRange(); r.selectNodeContents(el);
  return new Set([...r.getClientRects()].filter((x) => x.width > 1).map((x) => Math.round(x.top / 4))).size; }"""
BRS = "(sel) => document.querySelector(sel).querySelectorAll('br').length"
P = '#lec-view p'
LI = '#lec-view li'


# 글자의 화면 자리 — 한 문단에 줄이 여럿이라 요소가 아니라 글 조각을 찾아 그 가운데를 누른다
SPOT = """(t) => { const w = document.createTreeWalker(document.querySelector('#lec-view'), NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) { const i = n.textContent.indexOf(t); if (i < 0) continue;
    const r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + t.length); const b = r.getBoundingClientRect();
    return { x: b.left + b.width / 2, y: b.top + b.height / 2 }; } return null; }"""


def click_text(page, text):
    at = page.evaluate(SPOT, text)
    page.mouse.click(at['x'], at['y'])


def read():
    for _ in range(40):
        try:
            return (proj / '이어.md').read_text(encoding='utf-8')
        except OSError:
            time.sleep(0.05)
    return ''


try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1200, 'height': 800})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        page.locator('#lec-tree .row.file[data-doc="이어.md"]').click()
        page.wait_for_selector('#lec-view h1')
        page.wait_for_timeout(300)
        rows = lambda sel=P: page.evaluate(ROWS, sel)  # noqa: E731
        check('읽을 때 네 줄 (줄마다 <br>)', rows() == 4 and page.evaluate(BRS, P) == 3, (rows(), page.evaluate(BRS, P)))

        print('[첫·가운데·끝 줄을 열어도 네 줄]')
        for i, text in enumerate(LINES):
            click_text(page, text)
            page.keyboard.press('F2')
            page.wait_for_selector('#lec-view .lec-line-edit', timeout=5000)
            page.wait_for_timeout(150)
            check(f'{i + 1}번째 줄을 열면 — 문단은 여전히 네 줄, 다음 줄이 칸 옆으로 올라붙지 않는다', rows() == 4, rows())
            page.keyboard.press('Escape')
            expect(page, f'— 그만두면 원래 모양 (<br> 셋, 네 줄)', lambda: page.locator('#lec-view .lec-line-edit').count() == 0
                   and page.evaluate(BRS, P) == 3 and rows() == 4, lambda: (page.evaluate(BRS, P), rows()))

        print('[고쳐 저장하면 그 줄만]')
        click_text(page, LINES[1])
        page.keyboard.press('F2')
        page.wait_for_selector('#lec-view .lec-line-edit', timeout=5000)
        page.keyboard.press('End')
        page.keyboard.type(' plus')
        check('치는 동안에도 네 줄', rows() == 4, rows())
        page.keyboard.press('Enter')
        expect(page, '저장 — 원문의 그 줄만 바뀌고 줄 수는 그대로', lambda: read().split('\n')[3] == LINES[1] + ' plus' and read().count('\n') == DOC.count('\n'),
               lambda: read().split('\n')[2:7])
        page.keyboard.press('Escape')
        expect(page, '— 다시 그려도 네 줄', lambda: page.locator('#lec-view .lec-line-edit').count() == 0 and rows() == 4, lambda: rows())

        print('[목록 항목 안의 이어 쓴 줄]')
        click_text(page, '목록 첫 줄')
        page.keyboard.press('F2')
        page.wait_for_selector('#lec-view .lec-line-edit', timeout=5000)
        page.wait_for_timeout(150)
        check('목록 항목의 첫 줄을 열어도 두 줄 그대로', rows(LI) == 2, rows(LI))
        page.keyboard.press('Escape')

        print('[문단 안의 줄바꿈 보이기를 끄면]')
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ md_breaks: false })).then(() => import('/static/js/store.js')).then((m) => m.emit('refresh-view'))")
        expect(page, '표준 Markdown — 원래 한 줄로 이어 보이고 <br> 없음', lambda: page.evaluate(BRS, P) == 0)
        click_text(page, '셋째 줄')
        page.keyboard.press('F2')
        page.wait_for_selector('#lec-view .lec-line-edit', timeout=5000)
        check('— 줄을 열어도 오류 없이 칸이 하나', page.locator('#lec-view .lec-line-edit').count() == 1)
        page.keyboard.press('Escape')

        check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
