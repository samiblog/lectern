"""자료 파일 편집 (D171)·통계 체크 칸 (D172): 엑셀이 저장한 CP949 CSV 를 편집 모드로 고쳐 CP949·CRLF 그대로 저장(표가 다시 그려짐),
CP949 에 없는 글자는 저장하지 않고 알림, UTF-16 '유니코드 텍스트'와 TSV 의 Tab 은 탭 글자(→ 로 보임), 표에서 F2 는 그 줄에서 편집 모드,
log 는 보기만([편집] 꺼짐·Ctrl+E·F2 는 알림), 통계 체크 칸은 모든 열을 한꺼번에 — 다른 CSV 에도"""
import json
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-dataedit-'))
proj = base / 'proj'
(proj / 'data').mkdir(parents=True)
(proj / 'a.md').write_text('# 가\n\n본문.\n', encoding='utf-8')
EXCEL = '품목,가격\r\n구리,9400\r\n아연,2700\r\n'
(proj / 'data' / 'excel.csv').write_bytes(EXCEL.encode('cp949'))
(proj / 'data' / 'uni.txt').write_bytes(b'\xff\xfe' + '품목\t가격\r\n구리\t9400\r\n'.encode('utf-16-le'))
(proj / 'data' / '표.tsv').write_bytes('a\tb\n1\t2\n'.encode('utf-8'))   # LF 그대로 (write_text 는 Windows 에서 CRLF)
(proj / 'data' / 'run.log').write_text('시작\n끝\n', encoding='utf-8')
(proj / 'data' / 'other.csv').write_text('x,y\n1,2\n3,4\n', encoding='utf-8')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)

VALUE = "() => document.querySelector('.CodeMirror')?.CodeMirror.getValue() ?? null"


def raw(name):
    for _ in range(40):
        try:
            return (proj / 'data' / name).read_bytes()
        except OSError:
            time.sleep(0.05)
    return b''


def saved():
    try:
        return json.loads((config / 'config.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1300, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        dialogs = []
        page.on('dialog', lambda d: (dialogs.append(d.message), d.accept()))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        toast = lambda: page.text_content('#lec-toast') or ''  # noqa: E731

        def open_file(name, ready='.code-view'):
            page.evaluate("(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'code', path: p }))", f'data/{name}')
            page.wait_for_selector(f'#lec-view{ready}', timeout=10000)
            page.wait_for_timeout(500)

        def close_editor():
            page.keyboard.press('Escape')
            page.wait_for_selector('.CodeMirror', state='detached', timeout=8000)

        print('[엑셀이 저장한 CP949 CSV]')
        open_file('excel.csv', '.csv-view')
        check('[편집] 단추가 켜져 있다', page.is_enabled('#lec-btn-edit'))
        page.locator('#lec-view tbody.csv-rows tr.cv-line').first.click()
        page.keyboard.press('Control+e')
        page.wait_for_selector('.CodeMirror', timeout=15000)
        check('편집 모드 — 한글이 그대로, 머리에 CP949', '구리,9400' in (page.evaluate(VALUE) or '') and page.inner_text('.lec-editor .ed-enc') == 'CP949', page.evaluate(VALUE))
        page.keyboard.press('Control+End')
        page.keyboard.type('니켈,16500')
        page.keyboard.press('Control+s')
        expect(page, '저장 — CP949·CRLF 그대로', lambda: raw('excel.csv') == (EXCEL + '니켈,16500').encode('cp949'), lambda: raw('excel.csv'))
        close_editor()
        expect(page, '표가 다시 그려져 새 행이 보인다', lambda: page.locator('#lec-view tr.cv-line', has_text='니켈').count() == 1, ms=8000)
        page.keyboard.press('Control+e')
        page.wait_for_selector('.CodeMirror', timeout=15000)
        page.keyboard.press('Control+End')
        page.keyboard.type(' 😀')
        before = raw('excel.csv')
        page.keyboard.press('Control+s')
        expect(page, 'CP949 에 없는 글자 — 저장하지 않고 그 글자를 알린다', lambda: '😀' in toast() and 'CP949' in toast(), toast)
        check('— 파일은 그대로', raw('excel.csv') == before)
        close_editor()   # 저장하지 않은 것을 버릴지 묻는다 — 버린다
        check('— 닫을 때 저장하지 않은 것을 물었다', any('저장' in d for d in dialogs), dialogs)

        print('[표에서 F2]')
        rows = page.locator('#lec-view tbody.csv-rows tr.cv-line')
        rows.nth(1).click()
        want = int(rows.nth(1).get_attribute('data-line'))
        page.keyboard.press('F2')
        page.wait_for_selector('.CodeMirror', timeout=15000)
        at = page.evaluate("() => document.querySelector('.CodeMirror').CodeMirror.getCursor().line + 1")
        check('F2 — 그 행의 줄에서 편집 모드', at == want and page.locator('#lec-view .lec-line-edit').count() == 0, (at, want))
        close_editor()

        print("[UTF-16 '유니코드 텍스트'와 TSV 의 Tab]")
        open_file('uni.txt')
        page.locator('#lec-view .cv-line').first.click()
        page.keyboard.press('Control+e')
        page.wait_for_selector('.CodeMirror', timeout=15000)
        check('머리에 UTF-16, 탭은 → 로 보인다', page.inner_text('.lec-editor .ed-enc') == 'UTF-16' and page.locator('.lec-editor.show-tabs .cm-tab').count() >= 2)
        page.keyboard.press('Control+End')
        page.keyboard.type('아연')
        page.keyboard.press('Tab')
        page.keyboard.type('2700')
        page.keyboard.press('Control+s')
        want16 = b'\xff\xfe' + '품목\t가격\r\n구리\t9400\r\n아연\t2700'.encode('utf-16-le')
        expect(page, '저장 — UTF-16·BOM·CRLF 그대로, Tab 은 탭 글자', lambda: raw('uni.txt') == want16, lambda: raw('uni.txt')[:60])
        close_editor()
        open_file('표.tsv', '.csv-view')
        page.locator('#lec-view tbody.csv-rows tr.cv-line').first.click()
        page.keyboard.press('Control+e')
        page.wait_for_selector('.CodeMirror', timeout=15000)
        check('UTF-8 은 인코딩 표시가 없다', page.locator('.lec-editor .ed-enc').count() == 0)
        page.keyboard.press('Control+End')   # 마지막 줄바꿈 뒤의 빈 줄
        page.keyboard.type('3')
        page.keyboard.press('Tab')
        page.keyboard.type('4')
        page.keyboard.press('Control+s')
        expect(page, 'TSV — Tab 은 탭 글자 (빈칸 넷이 아님)', lambda: raw('표.tsv') == 'a\tb\n1\t2\n3\t4'.encode('utf-8'), lambda: raw('표.tsv'))
        close_editor()
        expect(page, '— 표의 새 행이 두 열로', lambda: page.locator('#lec-view tr.cv-line', has_text='3').locator('td').count() >= 3, ms=8000)

        print('[log 는 보기만]')
        open_file('run.log')
        check('[편집] 단추가 꺼져 있다', page.is_disabled('#lec-btn-edit'))
        page.locator('#lec-view .cv-line').first.click()
        page.keyboard.press('Control+e')
        expect(page, 'Ctrl+E — 보기만이라고 알린다', lambda: '로그 파일은 보기만' in toast(), toast)
        check('— 편집기가 열리지 않는다', page.locator('.CodeMirror').count() == 0)
        page.keyboard.press('F2')
        expect(page, 'F2 도 알린다', lambda: '로그 파일은 보기만' in toast(), toast)

        print('[통계 체크 칸 — 모든 열을 한꺼번에]')
        open_file('excel.csv', '.csv-view')
        box = page.locator('.csv-stats-toggle input')
        check('체크 칸이 켜져 있고 통계 줄이 보인다', box.is_checked() and page.is_visible('.csv-stats'))
        box.uncheck()
        expect(page, '끄면 모든 열의 통계 줄이 사라진다', lambda: page.is_hidden('.csv-stats'))
        check('— 설정에 남는다 (csv_stats: false)', until(page, lambda: saved().get('csv_stats') is False), saved().get('csv_stats'))
        open_file('other.csv', '.csv-view')
        check('다른 CSV 도 꺼진 채로', not page.locator('.csv-stats-toggle input').is_checked() and page.is_hidden('.csv-stats'))
        page.locator('.csv-stats-toggle').click()
        expect(page, '이름(통계)을 눌러도 켜진다', lambda: page.locator('.csv-stats-toggle input').is_checked() and page.is_visible('.csv-stats'))
        check('— 설정에 남는다 (csv_stats: true)', until(page, lambda: saved().get('csv_stats') is True), saved().get('csv_stats'))

        check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
