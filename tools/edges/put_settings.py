"""넣기 창의 판과 설정 창의 분류 (D154): 다섯 열의 판·←→ 열 옮기기·초성 거르기·최근 넣은 것('/ Enter' 두 번)·탭 막대의 [넣기],
설정 창의 왼쪽 분류(누르면 그 절로·강조·마지막 분류 기억)·한 줄 단추의 설명·고급의 값, 관련 화면에서 그 분류로 열기
(스타일 목록·vi 표시·업무 현황·내보내기 창·터미널 머리줄)"""
import json
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop

base = Path(tempfile.mkdtemp(prefix='lec-putset-'))
proj = base / 'proj'
proj.mkdir(parents=True)
DOC = '# 보고서\n\n첫 문단이다.\n\n둘째 문단이다.\n'
doc = proj / 'a.md'
doc.write_text(DOC, encoding='utf-8')
home = base / 'home'
home.mkdir()
(home / 'WORK.md').write_text('# 공통 업무\n\n## 일정\n', encoding='utf-8')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_home': str(home.resolve()), 'work_alerts': False}), encoding='utf-8')
BREAK = '<div style="page-break-after: always;"></div>'
src = lambda: doc.read_text(encoding='utf-8')
saved = lambda: json.loads((config / 'config.json').read_text(encoding='utf-8'))

server, url, port = serve(proj, config)
try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(viewport={'width': 1366, 'height': 860}).new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')
        page.locator('#lec-tree .row.file[data-doc="a.md"]').click()
        page.wait_for_selector('#lec-view h1')
        page.wait_for_timeout(500)
        sel = lambda: page.locator('#lec-put-list li.sel').first.inner_text()
        heads = lambda: page.locator('#lec-put-list.board > li.col > .head').all_inner_texts()

        def open_put():
            page.keyboard.press('Escape')
            page.locator('#lec-view p', has_text='첫 문단이다').click()
            page.keyboard.press('/')
            page.wait_for_selector('#lec-put:not([hidden])')
            page.wait_for_timeout(200)

        print('[넣기 판]')
        open_put()
        check('다섯 열의 판 — 글·강조글·자료·주·참조·쪽', heads() == ['글', '강조글', '자료', '주·참조', '쪽'], heads())
        check('판은 넓게', page.locator('#lec-put.board').count() == 1 and page.locator('#lec-put').bounding_box()['width'] > 600)
        check('강조글 열은 묶음 이름을 뺀 이름', '참고' in page.locator('#lec-put-list.board > li.col').nth(1).inner_text().split('\n'))
        page.keyboard.press('ArrowRight')
        check('→ 는 옆 열의 같은 줄', sel() == '참고', sel())
        page.keyboard.press('ArrowDown')
        check('↓ 는 열 안에서', sel() == '팁', sel())
        page.keyboard.type('ㅉㄴ')
        page.wait_for_timeout(300)
        check('초성 ㅉㄴ → 쪽 나눔 (거르면 목록)', page.locator('#lec-put-list.board').count() == 0 and sel() == '쪽 나눔', sel())
        page.keyboard.press('Enter')
        expect(page, '쪽 나눔이 들어감', lambda: BREAK in src(), lambda: src())
        expect(page, '— 최근 넣은 것에 기억', lambda: saved().get('recent_puts') == ['pagebreak'], lambda: saved().get('recent_puts'))
        page.keyboard.press('Escape')
        page.keyboard.press('Control+z')
        expect(page, 'Ctrl+Z 로 뺌', lambda: src() == DOC, lambda: src())
        open_put()
        check("다시 열면 맨 앞에 '최근' 열, 골라진 것은 쪽 나눔", heads()[:1] == ['최근'] and sel() == '쪽 나눔', (heads(), sel()))
        page.keyboard.press('Enter')
        expect(page, "'/ Enter' 두 번으로 같은 것을 다시", lambda: BREAK in src(), lambda: src())
        page.keyboard.press('Escape')
        page.keyboard.press('Control+z')
        expect(page, '— 되돌림', lambda: src() == DOC)
        page.keyboard.press('Escape')
        page.locator('#lec-view p', has_text='둘째 문단이다').click()
        page.click('#lec-btn-put')
        page.wait_for_selector('#lec-put:not([hidden])')
        check("탭 막대의 [넣기] — 넣기 창", page.locator('#lec-put.board').count() == 1)
        page.keyboard.press('Escape')
        page.keyboard.press('Escape')

        print('[설정 창]')
        page.keyboard.press('Control+,')
        page.wait_for_selector('#lec-settings:not([hidden])')
        on = lambda: page.locator('#lec-settings .set-nav button.on').inner_text()
        check('분류 여덟, 처음은 일반', page.locator('#lec-settings .set-nav button').count() == 8 and on() == '일반', on())
        check('고른 것의 설명만 아래에 (언어 — 자동)', page.locator('#lec-settings .opt-choice .seg-desc').first.inner_text() == 'Windows 표시 언어')
        page.locator('#lec-settings .set-nav button[data-set="term"]').click()
        expect(page, '터미널을 누르면 그 절로 — 강조', lambda: on() == '터미널' and page.evaluate("() => document.querySelector('#lec-set-content').scrollTop") > 100)
        expect(page, '— 마지막 분류를 기억', lambda: saved().get('settings_section') == 'term')
        check('고급의 값 — 편집기 경로', '편집기 경로' in page.locator('#lec-set-values').inner_text())
        page.keyboard.press('Escape')
        page.keyboard.press('Control+,')
        page.wait_for_selector('#lec-settings:not([hidden])')
        expect(page, '다시 열면 터미널에서', lambda: on() == '터미널')
        page.keyboard.press('Escape')

        print('[그 분류에서 열기]')
        page.select_option('#lec-theme', '__settings')
        expect(page, "스타일 목록의 '스타일 설정…' → 보기", lambda: page.locator('#lec-settings:not([hidden])').count() == 1 and on() == '보기')
        check('— 고른 스타일은 그대로', page.input_value('#lec-theme') != '__settings', page.input_value('#lec-theme'))
        page.keyboard.press('Escape')
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ vi_keys: true })).then(() => import('/static/js/store.js')).then((m) => m.emit('vi-keys'))")
        page.wait_for_selector('#lec-st-vi:not([hidden])')
        page.click('#lec-st-vi')
        expect(page, '상태줄의 vi 표시 → 편집', lambda: page.locator('#lec-settings:not([hidden])').count() == 1 and on() == '편집')
        page.keyboard.press('Escape')
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ vi_keys: false })).then(() => import('/static/js/store.js')).then((m) => m.emit('vi-keys'))")
        page.locator('#lec-tree .row.file[data-doc="a.md"]').click()
        page.wait_for_selector('#lec-view h1')
        page.evaluate("""() => { window.pywebview = { api: {   // 내보내기 창은 창 모드의 것 — 가짜 창 API (printpdf 와 같게)
          pdf_preview: async () => ({ token: 'fake', pages: 1, size: 1024 }), save_pdf: async () => ({ path: 'C:/x/a.pdf' }) } }; }""")
        page.click('#lec-btn-print')
        page.wait_for_selector('#lec-print:not([hidden])')
        page.click('#lec-print-settings')
        expect(page, '내보내기 창의 글꼴·틀 설정… → 인쇄·내보내기 (내보내기 창은 닫힘)', lambda: on() == '인쇄·내보내기' and page.locator('#lec-print').is_hidden())
        page.keyboard.press('Escape')
        page.keyboard.press('Alt+w')
        page.wait_for_selector('.wk-board:visible button[data-wk="settings"]', timeout=10000)
        page.locator('.wk-board:visible button[data-wk="settings"]').click()
        expect(page, '업무 현황의 업무 설정… → 업무', lambda: on() == '업무')
        page.keyboard.press('Escape')
        check('화면 스크립트 오류 없음', not errors, errors[:3])
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
