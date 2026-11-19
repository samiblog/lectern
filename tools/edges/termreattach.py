"""터미널 화면 다시 붙기 (2026-11-19): 화면(xterm)만 새로 만들어 같은 셸에 붙는다 — 셸(PID·변수)은 그대로, 지난 출력이 다시 보이고,
새 화면에서 친 글(한글 포함)은 한 번씩만 들어간다. 머리줄·터미널 탭 우클릭과 명령 찾기, 감춘 터미널이면 보이게 한 뒤 셸 크기를 화면에 맞춘다"""
import json
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-reattach-'))
proj = base / 'proj'
config = base / 'config'
proj.mkdir()
(proj / '글.md').write_text('# 글\n\n본문\n', encoding='utf-8')
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)

TEXT = """import('/static/js/store.js').then((m) => { const b = m.S.tab.term.xterm.buffer.active; const out = [];
  for (let i = 0; i < b.length; i++) out.push(b.getLine(i).translateToString(true)); return out.join('\\n'); })"""
MARK = "import('/static/js/store.js').then((m) => { window.__lecOld = m.S.tab.term.xterm; return true; })"
NEW = "import('/static/js/store.js').then((m) => !!window.__lecOld && m.S.tab.term.xterm !== window.__lecOld && document.querySelectorAll('#lec-term .term-box:not([hidden]) .xterm').length === 1)"
COLS = "import('/static/js/store.js').then((m) => m.S.tab.term.xterm.cols)"

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1400, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        text = lambda: page.evaluate(TEXT)  # noqa: E731
        page.keyboard.press('Control+`')
        page.wait_for_selector('#lec-term .term-box:not([hidden]) .xterm', timeout=15000)
        until(page, lambda: 'PS ' in text(), 20000)

        def run(cmd, want, ms=10000):
            page.locator('#lec-term .term-box:not([hidden]) .xterm').click()
            page.keyboard.type(cmd)
            page.keyboard.press('Enter')
            return until(page, lambda: want in text(), ms)

        # 찾는 글은 출력에만 생기게 이어 붙인다 — 친 명령 줄에도 있으면 기다림이 바로 끝난다. 프롬프트는 짧게 (명령 줄이 접히지 않게)
        run('function prompt { "P" + "S> " }', 'PS> ')
        run('$x = 41; "pi" + "d=$PID"', 'pid=')
        pid = next(line[4:].strip() for line in text().split('\n') if line.startswith('pid='))
        run('"다시붙기" + "-앞"', '다시붙기-앞')
        run('1..150 | % { "li" + "ne-$_" }', 'line-150')   # 화면 밖(스크롤백)으로 밀려나는 줄들
        check('처음 셸 — PID 와 출력', pid.isdigit() and '다시붙기-앞' in text(), pid)

        print('[머리줄 우클릭 — 화면 다시 붙기]')
        page.evaluate(MARK)
        page.click('#lec-term-title', button='right')
        item = page.locator('#lec-menu').get_by_text('1번 터미널 화면 다시 붙기')
        expect(page, '머리줄 우클릭 메뉴에 1번 터미널 화면 다시 붙기', lambda: item.count() == 1)
        item.click()
        expect(page, '새 화면 하나 (옛 화면은 걷음)', NEW)
        expect(page, '— 지난 출력이 다시 보인다', lambda: '다시붙기-앞' in text(), lambda: text()[-300:])
        expect(page, '— 화면 밖으로 밀려났던 줄도 (서버가 든 출력을 맨 앞부터 다시 받는다)', lambda: '\nline-1\n' in text() and '\nline-150\n' in text(),
               lambda: text()[:300])
        check('— 알림', '다시 붙였습니다' in (page.text_content('#lec-toast') or ''), page.text_content('#lec-toast'))
        run('"pi" + "d=$PID x=$($x+1) once" + "-7"', 'once-7')
        check('같은 셸 — PID 같고 변수가 남아 있다', f'pid={pid} x=42 once-7' in text(), text()[-300:])
        check('친 글은 한 번씩만 (옛 화면이 셸에 보내지 않는다)', '"pi" + "d=$PID x=$($x+1) once" + "-7"' in text(), text()[-300:])
        run('"한글입력" + "-뒤"', '한글입력-뒤')
        check('새 화면에서 친 한글이 셸에 들어간다', '"한글입력" + "-뒤"' in text() and '한글입력-뒤' in text(), text()[-300:])

        print('[터미널 탭 우클릭]')
        page.evaluate(MARK)
        page.locator('#lec-term-tabs .term-tab').first.click(button='right')
        page.locator('#lec-menu').get_by_text('1번 터미널 화면 다시 붙기').click()
        expect(page, '탭 우클릭으로도 다시 붙는다', NEW)
        run('"pi" + "d=$PID again" + "-9"', 'again-9')
        check('— 같은 셸', f'pid={pid} again-9' in text(), text()[-200:])

        print('[감춘 터미널 — 명령 찾기]')
        page.keyboard.press('Control+`')
        expect(page, '터미널을 감춘다', "() => document.querySelector('#lec-term').hidden")
        page.locator('#lec-content').focus()
        page.evaluate(MARK)
        page.keyboard.press('Control+Shift+P')
        page.keyboard.type('화면 다시 붙기')
        page.wait_for_timeout(200)
        page.keyboard.press('Enter')
        expect(page, '명령 찾기 — 터미널이 보이고 새 화면으로', NEW)
        cols = page.evaluate(COLS)
        run('"w=$([Console]::WindowWidth) end" + "-3"', 'end-3')
        check('셸의 폭이 화면의 칸 수와 같다 (숨은 80칸으로 흔들지 않았다)', f'w={cols} end-3' in text(), (cols, text()[-200:]))

        print('[끝난 셸]')
        run('exit', '셸이 끝났습니다')
        page.click('#lec-term-title', button='right')
        page.locator('#lec-menu').get_by_text('1번 터미널 화면 다시 붙기').click()
        expect(page, '끝난 셸 — 다시 붙지 않고 Enter 로 다시 시작하라고 알린다', lambda: 'Enter' in (page.text_content('#lec-toast') or ''), lambda: page.text_content('#lec-toast'))

        check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
