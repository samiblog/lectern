"""터미널 글자 크기 (D130): 기본 14, 설정 창의 숫자·−·+·기본 크기, 열린 터미널에 바로, 범위 밖 값, 저장과 다시 열기, 터미널 모음"""
import json
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-termfont-'))
proj = base / 'proj'
config = base / 'config'
proj.mkdir()
(proj / '글.md').write_text('# 글\n\n본문\n', encoding='utf-8')
SIZE = "import('/static/js/store.js').then((m) => m.S.tab.term?.xterm.options.fontSize ?? null)"
COLS = "import('/static/js/store.js').then((m) => m.S.tab.term?.xterm.cols ?? 0)"
saved = lambda: json.loads((config / 'config.json').read_text(encoding='utf-8')).get('terminal_font_size')

server, url, port = serve(proj, config)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1400, 'height': 900})
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        page.keyboard.press('Control+`')
        page.wait_for_selector('#lec-term .term-box:not([hidden]) .xterm', timeout=15000)
        expect(page, '처음 터미널은 14', f'{SIZE}.then((n) => n === 14)')
        cols14 = page.evaluate(COLS)

        print('[설정 창]')
        page.keyboard.press('Control+,')
        page.wait_for_selector('#lec-settings:not([hidden])')
        check('숫자 칸에 지금 크기', page.input_value('#lec-termfont') == '14', page.input_value('#lec-termfont'))
        page.click('#lec-termfont-up')
        page.click('#lec-termfont-up')
        expect(page, '+ 두 번이면 열린 터미널이 16', f'{SIZE}.then((n) => n === 16)')
        check('칸에도 16', page.input_value('#lec-termfont') == '16')
        expect(page, '글자가 커지면 한 줄의 칸 수가 준다', f'{COLS}.then((n) => n > 0 && n < {cols14})')
        until(page, lambda: saved() == 16)
        check('설정 파일에 저장', saved() == 16, saved())
        page.fill('#lec-termfont', '30')
        page.keyboard.press('Tab')
        expect(page, '범위보다 크면 24', f'{SIZE}.then((n) => n === 24)')
        check('칸도 24 로 고친다', page.input_value('#lec-termfont') == '24')
        page.fill('#lec-termfont', '3')
        page.keyboard.press('Tab')
        expect(page, '범위보다 작으면 10', f'{SIZE}.then((n) => n === 10)')
        page.click('#lec-termfont-down')
        check('10 에서 − 는 그대로', page.input_value('#lec-termfont') == '10')
        page.fill('#lec-termfont', '')
        page.keyboard.press('Tab')
        check('비우면 지금 값으로 돌린다', page.input_value('#lec-termfont') == '10', page.input_value('#lec-termfont'))
        page.click('#lec-termfont-reset')
        expect(page, '기본 크기는 14', f'{SIZE}.then((n) => n === 14)')
        page.fill('#lec-termfont', '18')
        page.keyboard.press('Tab')
        expect(page, '18', f'{SIZE}.then((n) => n === 18)')
        page.keyboard.press('Escape')

        print('[새 터미널·다시 열기·터미널 모음]')
        page.click('#lec-term-new')
        until(page, "import('/static/js/store.js').then((m) => (m.S.tab.terms || []).length >= 2)", 10000)
        sizes = page.evaluate("import('/static/js/store.js').then((m) => (m.S.tab.terms || []).map((x) => x.xterm.options.fontSize))")
        check('바꾼 뒤 새로 연 터미널도, 원래 터미널도 18', len(sizes) >= 2 and all(s == 18 for s in sizes), sizes)
        page.reload()
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        page.keyboard.press('Control+`')
        page.wait_for_selector('#lec-term .term-box:not([hidden]) .xterm', timeout=15000)
        expect(page, '다시 열어도 18', f'{SIZE}.then((n) => n === 18)')
        page.keyboard.press('Control+Shift+`')
        page.wait_for_timeout(800)
        expect(page, '터미널 모음에서도 18', f'{SIZE}.then((n) => n === 18)')
        page.keyboard.press('Escape')
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
