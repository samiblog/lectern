"""설정 창의 ▣ (D180): 요청 글을 마지막에 쓴 터미널(탭의 고른 터미널)에 넣는다 — 늘 1번이 아니다. 숫자 키(1~5)를 누른 채 누르면 그 번호의
터미널에, 단추에 번호가 뜬다. 없는 번호면 알리고, 글 칸에 초점이 있으면 숫자는 그 칸의 글이다"""
import json
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-setterm-'))
proj = base / 'proj'
config = base / 'config'
proj.mkdir()
(proj / '글.md').write_text('# 글\n\n본문\n', encoding='utf-8')
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False, 'settings_section': 'ai'}), encoding='utf-8')
server, url, port = serve(proj, config)

TEXT = """(n) => import('/static/js/store.js').then((m) => { const term = m.S.tab.terms.find((x) => x.n === n); if (!term) return '';
  const b = term.xterm.buffer.active; const out = []; for (let i = 0; i < b.length; i++) out.push(b.getLine(i).translateToString(true)); return out.join('\\n'); })"""
LEN = """(n) => import('/static/js/store.js').then((m) => { const term = m.S.tab.terms.find((x) => x.n === n); if (!term) return 0;
  const b = term.xterm.buffer.active; let s = 0; for (let i = 0; i < b.length; i++) s += b.getLine(i).translateToString(true).length; return s; })"""

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1400, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.on('dialog', lambda d: d.accept())
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        text = lambda n: page.evaluate(TEXT, n)  # noqa: E731
        size = lambda n: page.evaluate(LEN, n)  # noqa: E731
        toast = lambda: page.text_content('#lec-toast') or ''  # noqa: E731
        page.keyboard.press('Control+`')
        page.wait_for_selector('#lec-term .term-box:not([hidden]) .xterm', timeout=15000)
        until(page, lambda: 'PS ' in text(0), 20000)
        page.click('#lec-term-new')
        until(page, lambda: 'PS ' in text(1), 20000)
        boxes = page.locator('#lec-term .term-pane')

        def settings():
            page.locator('#lec-content').focus()
            page.keyboard.press('Control+,')
            page.wait_for_selector('#lec-settings:not([hidden])')
            page.click('#lec-settings .set-nav button[data-set="ai"]')
            page.wait_for_selector('#lec-aiguide-term', state='visible')

        def use(n):   # 그 터미널을 눌러 쓴다 — 탭의 고른 터미널
            page.locator(f'#lec-term .term-pane[data-n="{n}"] .term-box').click()
            expect(page, f'{n + 1}번 터미널을 누르면 고른 터미널', f"import('/static/js/store.js').then((m) => m.S.tab.term?.n === {n})")

        print('[마지막에 쓴 터미널]')
        use(1)
        before = (size(0), size(1))
        settings()
        page.click('#lec-aiguide-term')
        expect(page, '2번을 쓰고 ▣ — 2번 터미널에 넣는다', lambda: "2번 터미널에 넣었습니다" in toast(), toast)
        expect(page, '— 2번의 글이 늘고 1번은 그대로', lambda: size(1) > before[1] + 20 and size(0) == before[0], lambda: (before, size(0), size(1)))
        page.keyboard.press('Escape')   # 넣은 글은 Enter 없이 셸의 입력 줄에 — Esc 로 지운다 (PowerShell)
        use(0)
        settings()
        page.click('#lec-skills-term')
        expect(page, '1번을 쓰고 ▣ — 1번 터미널에', lambda: "1번 터미널에 넣었습니다" in toast(), toast)
        page.keyboard.press('Escape')

        print('[숫자 키를 누른 채]')
        settings()
        page.keyboard.down('2')
        expect(page, '2 를 누르고 있으면 ▣ 에 2', "() => [...document.querySelectorAll('#lec-settings button[id$=\"-term\"]')].every((b) => b.classList.contains('term-held') && b.dataset.held === '2')")
        page.click('#lec-aiguide-term')
        page.keyboard.up('2')
        expect(page, '— 누르면 1번을 썼어도 2번 터미널에', lambda: "2번 터미널에 넣었습니다" in toast(), toast)
        page.keyboard.press('Escape')
        settings()
        check('떼면 번호가 사라진다', page.evaluate("() => !document.querySelector('#lec-settings button.term-held')"))
        page.keyboard.down('4')
        page.click('#lec-aiguide-term')
        page.keyboard.up('4')
        expect(page, '없는 번호(4) — 넣지 않고 알린다', lambda: '4번 터미널이 없습니다' in toast(), toast)

        print('[글 칸의 숫자]')
        settings()
        page.click('#lec-settings .set-nav button[data-set="term"]')
        page.locator('#lec-termfont').click()
        page.keyboard.down('2')
        check('글 칸에 초점이 있으면 숫자는 글 — ▣ 에 번호가 뜨지 않는다', page.evaluate("() => !document.querySelector('#lec-settings button.term-held')"))
        page.keyboard.up('2')
        page.keyboard.press('Escape')

        check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
