"""시나리오 — 0.94.0 을 실제로 쓰는 흐름 (D171·D172):
1 엑셀이 저장한 CP949 CSV 에서 틀린 값을 찾아 고치기 (거르기 → 그 행에서 Enter → 고쳐 저장 → 표·거르기 그대로, 엑셀이 다시 열 수 있게 CP949·CRLF)
2 고치는 사이 Claude Code 가 같은 CSV 에 행을 더함 → 저장하면 묻고, 취소하면 남의 글을 덮지 않음, 다시 열어 둘 다 살림
3 붙여 넣은 글에 이모지 → 저장하지 않고 알림 → 빼고 저장
4 엑셀 '유니코드 텍스트'(UTF-16, 탭) 에 행을 더하기 — 탭 글자, → 표시
5 큰 CSV (2MB 아래 3만 행) 는 열고 고치고, 2MB 가 넘으면 까닭을 알림
6 통계 체크 칸 — 끄면 CSV·엑셀 표 모두에서 감추고, 다시 불러와도 꺼진 채
7 예제처럼 보기만 하는 프로젝트의 CSV 는 고치지 않음
8 영어 화면 — 로그 알림·통계 체크 칸이 영어로"""
import json
import sys
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import ROOT, check, expect, fails, report, serve, stop, until

sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]   # 시험용 xlsx 를 만드는 도우미 (tests/test_sheet.py)
from test_sheet import make_xlsx  # noqa: E402

base = Path(tempfile.mkdtemp(prefix='lec-scen094-'))
proj = base / 'proj'
(proj / 'data').mkdir(parents=True)
(proj / '보고서.md').write_text('# 보고서\n\n본문.\n', encoding='utf-8')
PRICES = '월,품목,가격\r\n2026-01,구리,9010\r\n2026-02,구리,90400\r\n2026-03,구리,9120\r\n2026-01,니켈,16500\r\n'
(proj / 'data' / '가격.csv').write_bytes(PRICES.encode('cp949'))
(proj / 'data' / '유니코드.txt').write_bytes(b'\xff\xfe' + '품목\t수량\r\n구리\t12\r\n'.encode('utf-16-le'))
big = '번호,값\n' + ''.join(f'{i},{i * 7 % 1000}\n' for i in range(30000))
(proj / 'data' / '큰.csv').write_bytes(big.encode('utf-8'))
(proj / 'data' / '너무큰.csv').write_bytes(('번호,값\n' + 'x' * 70 + '\n').encode('utf-8') * 30000)   # 2.4MB
(proj / 'data' / 'run.log').write_bytes('시작\n'.encode('utf-8'))
rows = ('<row r="1"><c r="A1" t="inlineStr"><is><t>품목</t></is></c><c r="B1" t="inlineStr"><is><t>가격</t></is></c></row>'
        '<row r="2"><c r="A2" t="inlineStr"><is><t>구리</t></is></c><c r="B2"><v>9400</v></c></row>'
        '<row r="3"><c r="A3" t="inlineStr"><is><t>니켈</t></is></c><c r="B3"><v>16500</v></c></row>')
make_xlsx(proj / 'data' / '시세.xlsx', [('시트1', rows, None)])
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)

base2 = Path(tempfile.mkdtemp(prefix='lec-scen094b-'))
proj2 = base2 / 'proj'
(proj2 / 'data').mkdir(parents=True)
(proj2 / 'data' / 'a.csv').write_bytes('x,y\n1,2\n'.encode('utf-8'))
(proj2 / 'data' / 'run.log').write_bytes(b'start\n')
(proj2 / 'a.md').write_text('# a\n', encoding='utf-8')
config2 = base2 / 'config'
config2.mkdir()
(config2 / 'config.json').write_text(json.dumps({'work_alerts': False, 'language': 'en'}), encoding='utf-8')
server2, url2, port2 = serve(proj2, config2)

VALUE = "() => document.querySelector('.CodeMirror')?.CodeMirror.getValue() ?? null"
HERE = "() => import('/static/js/store.js').then(({ S }) => S.pane?.here?.line || 0)"


def raw(name, root=proj):
    for _ in range(40):
        try:
            return (root / 'data' / name).read_bytes()
        except OSError:
            time.sleep(0.05)
    return b''


try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(viewport={'width': 1400, 'height': 900}).new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        answer = {'accept': True}
        dialogs = []

        def on_dialog(d):
            dialogs.append(d.message)
            d.accept() if answer['accept'] else d.dismiss()
        page.on('dialog', on_dialog)
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        toast = lambda: page.text_content('#lec-toast') or ''  # noqa: E731
        here = lambda: page.evaluate(HERE)  # noqa: E731

        def open_file(name, ready='.code-view'):
            page.evaluate("(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'code', path: p }))", f'data/{name}')
            page.wait_for_selector(f'#lec-view{ready}', timeout=15000)
            page.wait_for_timeout(500)

        def editor_open():
            page.wait_for_selector('.CodeMirror', timeout=15000)
            page.wait_for_timeout(200)

        def close_editor():
            page.keyboard.press('Escape')
            page.wait_for_selector('.CodeMirror', state='detached', timeout=8000)

        print('[1 엑셀 CSV 의 틀린 값 고치기]')
        open_file('가격.csv', '.csv-view')
        page.fill('.csv-filter input[data-col="1"]', '구리')
        expect(page, '거르기 — 구리 세 행', lambda: page.locator('#lec-view tbody.csv-rows tr.cv-line').count() == 3)
        page.locator('.csv-head th[data-col="2"]').click()   # 가격 오름차순 → 다시 눌러 내림차순 — 튀는 값이 맨 위
        page.locator('.csv-head th[data-col="2"]').click()
        top = page.locator('#lec-view tbody.csv-rows tr.cv-line').first
        expect(page, '내림차순 — 90400 이 맨 위', lambda: '90400' in top.inner_text())
        line = int(top.get_attribute('data-line'))
        top.click()
        page.keyboard.press('Enter')   # 읽는 화면의 Enter 는 편집 (D166) — 자료 파일은 그 줄에서 편집 모드 (D171)
        editor_open()
        at = page.evaluate("() => document.querySelector('.CodeMirror').CodeMirror.getCursor().line + 1")
        check('Enter — 그 행의 줄에서 편집 모드, 머리에 CP949', at == line and page.inner_text('.lec-editor .ed-enc') == 'CP949', (at, line))
        page.keyboard.press('End')
        page.keyboard.press('Backspace')   # 90400 → 9040
        page.keyboard.press('Control+s')
        want = PRICES.replace('90400', '9040').encode('cp949')
        expect(page, '저장 — CP949·CRLF 그대로 (엑셀이 다시 열 수 있게)', lambda: raw('가격.csv') == want, lambda: raw('가격.csv'))
        close_editor()
        expect(page, '표가 다시 그려지고 거르기·정렬은 그대로', lambda: page.input_value('.csv-filter input[data-col="1"]') == '구리'
               and page.locator('#lec-view tbody.csv-rows tr.cv-line').count() == 3 and '9120' in page.locator('#lec-view tbody.csv-rows tr.cv-line').first.inner_text(), ms=8000)

        print('[2 고치는 사이 Claude Code 가 같은 파일에 행을 더함]')
        page.locator('#lec-view tbody.csv-rows tr.cv-line').first.click()
        page.keyboard.press('Control+e')
        editor_open()
        page.keyboard.press('Control+End')
        page.keyboard.type('2026-02,니켈,16800')
        time.sleep(1.1)
        claude = raw('가격.csv').decode('cp949') + '2026-04,구리,9300\r\n'
        (proj / 'data' / '가격.csv').write_bytes(claude.encode('cp949'))
        time.sleep(0.6)
        answer['accept'] = False
        n = len(dialogs)
        page.keyboard.press('Control+s')
        expect(page, '저장하면 그사이 바뀌었다고 묻는다', lambda: len(dialogs) > n and '바뀌었습니다' in dialogs[-1], lambda: dialogs[-1:])
        page.wait_for_timeout(400)
        check('— 취소하면 Claude 가 쓴 글을 덮지 않는다', raw('가격.csv') == claude.encode('cp949'))
        check('— 내 편집은 편집기에 그대로', '2026-02,니켈,16800' in (page.evaluate(VALUE) or ''))
        answer['accept'] = True
        close_editor()   # 버리고 닫는다 (물으면 예)
        expect(page, '다시 열면 Claude 가 더한 행이 보인다', lambda: page.locator('#lec-view tr.cv-line', has_text='9300').count() == 1, ms=8000)
        page.locator('#lec-view tbody.csv-rows tr.cv-line').first.click()
        page.keyboard.press('Control+e')
        editor_open()
        page.keyboard.press('Control+End')
        page.keyboard.type('2026-02,니켈,16800')
        page.keyboard.press('Control+s')
        expect(page, '다시 고쳐 저장 — 둘 다 산다', lambda: raw('가격.csv') == (claude + '2026-02,니켈,16800').encode('cp949'), lambda: raw('가격.csv')[-40:])
        close_editor()

        print('[3 이모지를 붙여 넣으면]')
        page.locator('#lec-view tbody.csv-rows tr.cv-line').first.click()
        page.keyboard.press('Control+e')
        editor_open()
        page.keyboard.press('Control+End')
        page.keyboard.type('\r\n2026-05,구리 👍,9500')
        before = raw('가격.csv')
        page.keyboard.press('Control+s')
        expect(page, '저장하지 않고 그 글자를 알린다', lambda: '👍' in toast() and 'CP949' in toast(), toast)
        check('— 파일은 그대로', raw('가격.csv') == before)
        page.evaluate("() => { const cm = document.querySelector('.CodeMirror').CodeMirror; cm.setValue(cm.getValue().replace(' 👍', '')); }")
        page.keyboard.press('Control+s')
        expect(page, '빼고 저장하면 된다', lambda: raw('가격.csv').decode('cp949').endswith('2026-05,구리,9500'), lambda: raw('가격.csv')[-30:])
        close_editor()

        print("[4 엑셀 '유니코드 텍스트'에 행 더하기]")
        open_file('유니코드.txt')
        page.locator('#lec-view .cv-line').last.click()
        page.keyboard.press('Enter')
        editor_open()
        check('Enter — 편집 모드, UTF-16, 탭은 → 로', page.inner_text('.lec-editor .ed-enc') == 'UTF-16' and page.locator('.lec-editor.show-tabs .cm-tab').count() >= 2)
        page.keyboard.press('Control+End')
        page.keyboard.type('아연')
        page.keyboard.press('Tab')
        page.keyboard.type('7')
        page.keyboard.press('Control+s')
        expect(page, '저장 — UTF-16·BOM·CRLF, 탭 글자', lambda: raw('유니코드.txt') == b'\xff\xfe' + '품목\t수량\r\n구리\t12\r\n아연\t7'.encode('utf-16-le'), lambda: raw('유니코드.txt')[:50])
        close_editor()

        print('[5 큰 CSV]')
        open_file('큰.csv', '.csv-view')
        t0 = time.monotonic()
        page.locator('#lec-view tbody.csv-rows tr.cv-line').first.click()
        page.keyboard.press('Control+e')
        editor_open()
        took = time.monotonic() - t0
        check(f'3만 행 CSV 의 편집 모드 ({took:.1f}초)', took < 8 and page.evaluate("() => document.querySelector('.CodeMirror').CodeMirror.lineCount()") >= 30001, took)
        page.keyboard.press('Control+End')
        page.keyboard.type('30000,7')
        page.keyboard.press('Control+s')
        expect(page, '— 저장된다', lambda: raw('큰.csv').endswith(b'30000,7'), ms=10000)
        close_editor()
        open_file('너무큰.csv')
        page.locator('#lec-view').click()
        page.keyboard.press('Control+e')
        expect(page, '2MB 가 넘으면 까닭을 알린다', lambda: '2MB' in toast(), toast, ms=8000)
        check('— 편집기는 열리지 않는다', page.locator('.CodeMirror').count() == 0)

        print('[6 통계 체크 칸 — CSV·엑셀 표 모두]')
        open_file('가격.csv', '.csv-view')
        page.locator('.csv-stats-toggle input').uncheck()
        expect(page, 'CSV 에서 끄면', lambda: page.is_hidden('.csv-stats'))
        open_file('시세.xlsx', '.csv-view')
        check('엑셀 표도 꺼진 채', not page.locator('.csv-stats-toggle input').is_checked() and page.is_hidden('.csv-stats'))
        page.wait_for_timeout(600)
        page.reload()
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=20000)
        page.wait_for_timeout(800)
        open_file('시세.xlsx', '.csv-view')   # 다시 실행하면 문서 탭만 되살린다 — 엑셀은 다시 연다
        check('다시 불러와도 꺼진 채', not page.locator('.csv-stats-toggle input').is_checked() and page.is_hidden('.csv-stats'))
        page.locator('.csv-stats-toggle input').check()
        expect(page, '다시 켜면 보인다', lambda: page.is_visible('.csv-stats'))
        page.keyboard.press('Control+e')
        expect(page, '엑셀은 여전히 보기만', lambda: '엑셀' in toast() and page.locator('.CodeMirror').count() == 0, toast)

        print('[7 보기만 하는 프로젝트]')
        page.evaluate("() => import('/static/js/tabs.js').then((m) => m.openSamples())")
        page.wait_for_function("document.querySelectorAll('#lec-tablist .lec-tab').length === 2", timeout=15000)
        page.wait_for_timeout(1500)
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open', { type: 'code', path: 'data/월별-가격.csv' }))")
        page.wait_for_selector('#lec-view.csv-view', timeout=15000)
        page.wait_for_timeout(500)
        page.locator('#lec-view tbody.csv-rows tr.cv-line').first.click()
        page.keyboard.press('Control+e')
        expect(page, '예제의 CSV — 보기만이라 고치지 않는다', lambda: '보기만' in toast() and page.locator('.CodeMirror').count() == 0, toast)
        real = [e for e in errors if 'addressunreachable' not in e]
        check('화면 스크립트 오류 없음 (1~7)', not real, real[:3])

        print('[8 영어 화면]')
        page2 = browser.new_context(viewport={'width': 1300, 'height': 900}).new_page()
        page2.goto(url2)
        page2.wait_for_selector('#lec-tree .row.file', timeout=20000)
        page2.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open', { type: 'code', path: 'data/a.csv' }))")
        page2.wait_for_selector('#lec-view.csv-view', timeout=15000)
        label = page2.inner_text('.csv-stats-toggle').strip()
        check("통계 체크 칸이 영어로 ('Stats')", label == 'Stats', label)
        page2.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open', { type: 'code', path: 'data/run.log' }))")
        page2.wait_for_selector('#lec-view.code-view .cv-line', timeout=15000)
        page2.locator('#lec-view .cv-line').first.click()
        page2.keyboard.press('Control+e')
        expect(page2, '로그 알림이 영어로', lambda: 'Log files are view only' in (page2.text_content('#lec-toast') or ''), lambda: page2.text_content('#lec-toast'))
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server2, base2)
    stop(server, base)
report()
