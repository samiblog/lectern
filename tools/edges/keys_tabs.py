"""단축키 표의 탭 (D157): 첫 탭은 처음 익힐 스무 가지, 탭 여덟, 누르기·←→·Ctrl+Tab, 찾기 칸(모든 탭에서), 열 때마다 첫 탭, 설명서의 단축키 장, 영어"""
import json
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop

base = Path(tempfile.mkdtemp(prefix='lec-keystabs-'))
proj = base / 'proj'
proj.mkdir(parents=True)
(proj / 'a.md').write_text('# 문서\n\n첫 문단이다.\n', encoding='utf-8')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)
try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(viewport={'width': 1366, 'height': 860}).new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')
        page.locator('#lec-tree .row.file[data-doc="a.md"]').click()
        page.wait_for_selector('#lec-view h1')
        on_tab = lambda: page.locator('#lec-keys-tabs button.on').inner_text()
        rows = lambda: page.locator('#lec-keys-list tr:visible').count()
        keys = lambda: page.evaluate("[...document.querySelectorAll('#lec-keys-list tr')].filter((tr) => tr.offsetParent).map((tr) => tr.querySelector('th').textContent.replace(/\\s/g, ''))")

        def open_keys():
            page.locator('#lec-view p').first.click()
            page.keyboard.press('Control+/')
            page.wait_for_selector('#lec-keys:not([hidden])')
            page.wait_for_timeout(150)

        print('[첫 탭]')
        page.click('#lec-btn-help')
        page.wait_for_selector('#lec-keys:not([hidden])')
        tabs = page.locator('#lec-keys-tabs button').all_inner_texts()
        check('탭 여덟 — 자주 쓰는 것부터 vi 키까지', tabs == ['자주 쓰는 것', '열기·화면', '고르기·복사', '쓰기·바꾸기', '한 줄 편집', '터미널', '편집 모드·슬라이드', 'vi 키'], tabs)
        check("툴바 '?' 로 열면 첫 탭", on_tab() == '자주 쓰는 것', on_tab())
        heads = page.locator('#lec-keys-list .keys-group:visible h3').all_inner_texts()
        check('첫 탭 — 읽고 고르기 열과 쓰고 고치기 열', heads == ['읽고 고르기', '쓰고 고치기'], heads)
        check('— 스무 가지', rows() == 20, rows())
        k = keys()
        check('— Ctrl+P · F2 · / · . · Ctrl+Z · Ctrl+/ 가 있다', {'Ctrl+P', 'F2', '/', '.', 'Ctrl+Z/Ctrl+Y', 'Ctrl+//F1'} <= set(k), k)
        check('찾기 칸에 초점', page.evaluate('document.activeElement?.id') == 'lec-keys-find')
        box = page.locator('#lec-keys .keys-box').bounding_box()
        check('한 화면에 — 표가 창 높이 안', box['y'] >= 0 and box['y'] + box['height'] <= 860, box)

        print('[탭 바꾸기]')
        page.locator('#lec-keys-tabs button', has_text='쓰기·바꾸기').click()
        check('누르면 그 탭 — 쓰기·넣기·바꾸기 묶음만', on_tab() == '쓰기·바꾸기' and page.locator('#lec-keys-list .keys-group:visible h3').all_inner_texts() == ['쓰기·넣기·바꾸기 (md 문서)'])
        check('— 바꾸기 창 . 과 두 번 누르는 키', {'.', 'Delete', 'Alt+↑/Alt+↓'} <= set(keys()), keys())
        page.keyboard.press('ArrowRight')
        check('탭 단추에서 → — 다음 탭 (한 줄 편집)', on_tab() == '한 줄 편집' and page.evaluate("document.activeElement?.dataset.tab") == 'cell', on_tab())
        page.keyboard.press('ArrowLeft')
        page.keyboard.press('ArrowLeft')
        check('← 두 번 — 고르기·복사', on_tab() == '고르기·복사', on_tab())
        page.locator('#lec-keys-find').focus()
        page.keyboard.press('Control+Tab')
        check('찾기 칸에서 Ctrl+Tab — 다음 탭', on_tab() == '쓰기·바꾸기', on_tab())
        page.keyboard.press('Control+Shift+Tab')
        check('Ctrl+Shift+Tab — 앞 탭', on_tab() == '고르기·복사', on_tab())
        check('— 뒤의 문서 탭은 그대로', page.locator('#lec-keys:not([hidden])').count() == 1)
        page.locator('#lec-keys-tabs button', has_text='터미널').click()
        check('터미널 탭 — 터미널과 터미널로 보내기', page.locator('#lec-keys-list .keys-group:visible h3').all_inner_texts() == ['터미널', '터미널로 보내기'])
        page.locator('#lec-keys-tabs button', has_text='vi 키').click()
        check('vi 키 탭', 'gg/G' in keys(), keys())

        print('[찾기]')
        page.fill('#lec-keys-find', '표')
        page.wait_for_timeout(150)
        found = page.locator('#lec-keys-list .keys-group:visible h3').all_inner_texts()
        check('찾기 — 모든 탭에서, 첫 탭의 요약은 빼고', len(found) >= 2 and '읽고 고르기' not in found and '쓰고 고치기' not in found, found)
        check('— 고른 탭 표시가 없다', page.locator('#lec-keys-tabs button.on').count() == 0)
        check('— 맞는 줄만', all('표' in t for t in page.locator('#lec-keys-list tr:visible').all_inner_texts()), page.locator('#lec-keys-list tr:visible').all_inner_texts()[:3])
        page.fill('#lec-keys-find', 'ctrl+k')
        page.wait_for_timeout(150)
        check('키로 찾기 — Ctrl+K', 'Ctrl+K' in keys(), keys())
        page.fill('#lec-keys-find', 'zzqq')
        page.wait_for_timeout(150)
        check('맞는 것이 없으면 알림', page.locator('#lec-keys-list .keys-none:visible').count() == 1 and rows() == 0)
        page.fill('#lec-keys-find', '')
        page.wait_for_timeout(150)
        check('찾기를 지우면 고르던 탭으로', on_tab() == 'vi 키', on_tab())
        page.keyboard.press('Escape')
        expect(page, 'Esc 로 닫힘 (찾기 칸에서)', lambda: page.locator('#lec-keys').is_hidden())

        print('[다시 열기]')
        open_keys()
        check('Ctrl+/ 로 다시 열면 첫 탭, 찾기 칸은 비움', on_tab() == '자주 쓰는 것' and page.input_value('#lec-keys-find') == '' and rows() == 20)
        page.keyboard.press('Control+/')
        expect(page, '찾기 칸에서 Ctrl+/ — 닫힘', lambda: page.locator('#lec-keys').is_hidden())

        print('[사용설명서의 단축키 장]')
        page.keyboard.press('F1')
        page.wait_for_selector('#lec-help:not([hidden])')
        page.wait_for_function("() => document.querySelectorAll('#lec-help-view h3').length > 10", timeout=15000)
        h3 = page.evaluate("[...document.querySelectorAll('#lec-help-view h3')].map((h) => h.textContent)")
        at = next((i for i, h in enumerate(h3) if h.startswith('자주 쓰는 것')), -1)
        check('설명서의 단축키 장은 자주 쓰는 것부터, 그다음 모든 묶음', at >= 0 and h3[at + 1].startswith('자주 쓰는 것') and h3[at + 2] == '열기·찾기', h3[max(0, at):at + 4])
        page.keyboard.press('F1')

        print('[영어 화면]')
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ language: 'en' }))")
        page.wait_for_timeout(400)
        page.reload()
        page.wait_for_selector('#lec-tree .row.file')
        page.locator('#lec-tree .row.file[data-doc="a.md"]').click()
        page.wait_for_selector('#lec-view h1')
        open_keys()
        tabs = page.locator('#lec-keys-tabs button').all_inner_texts()
        check('탭 이름이 영어', tabs[0] == 'Most used' and tabs[-1] == 'vi keys', tabs)
        left = page.evaluate("(s) => s.match(/[가-힣]+/g) || []", page.locator('#lec-keys .keys-box').inner_text() + page.get_attribute('#lec-keys-find', 'placeholder'))
        check('첫 탭과 찾기 칸에 남은 한글 없음', not left, left[:8])
        page.keyboard.press('Escape')
        check('화면 스크립트 오류 없음', not errors, errors[:3])
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
