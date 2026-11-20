"""0.94.0 — 빌드본·설치본 실제 창(WebView2)에서: 엑셀 CP949 CSV 를 거르고 정렬한 뒤 그 행에서 Enter·편집 모드로 고쳐 CP949·CRLF 그대로 저장,
CP949 에 없는 글자 알림, UTF-16 '유니코드 텍스트'의 Tab, log 는 보기만, 통계 체크 칸이 다시 실행해도 꺼진 채.
시험용 설정 폴더·개인 폴더 — 실제 설정과 ~/.claude 는 건드리지 않는다.
  python real094.py --exe <Lectern.exe>"""
import json
import os
import shutil
import subprocess
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

import realwin as R

base = Path(tempfile.mkdtemp(prefix='lec-real094-'))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'language': 'ko', 'work_alerts': False}), encoding='utf-8')
os.environ['LECTERN_HOME'] = str(base / 'home')
proj = base / '보고서'
(proj / 'data').mkdir(parents=True)
(proj / 'a.md').write_text('# 가\n\n본문.\n', encoding='utf-8')
PRICES = '월,품목,가격\r\n2026-01,구리,9010\r\n2026-02,구리,90400\r\n2026-03,구리,9120\r\n2026-01,니켈,16500\r\n'
(proj / 'data' / '가격.csv').write_bytes(PRICES.encode('cp949'))
(proj / 'data' / '유니코드.txt').write_bytes(b'\xff\xfe' + '품목\t수량\r\n구리\t12\r\n'.encode('utf-16-le'))
(proj / 'data' / 'run.log').write_bytes('시작\n'.encode('utf-8'))
STORE = "import('/static/js/store.js')"


def raw(name):
    for _ in range(40):
        try:
            return (proj / 'data' / name).read_bytes()
        except OSError:
            time.sleep(0.05)
    return b''


def connect(p, cdp):
    b = None
    for _ in range(120):
        try:
            b = p.chromium.connect_over_cdp(f'http://127.0.0.1:{cdp}')
            break
        except Exception:
            time.sleep(0.5)
    page = R.wait(lambda: R.app_page(b), 60)
    page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=40000)
    page.wait_for_timeout(1500)
    return b, page


def open_file(page, name, ready='.code-view'):
    page.evaluate(f"(p) => {STORE}.then((m) => m.emit('open', {{ type: 'code', path: p }}))", f'data/{name}')
    page.wait_for_selector(f'#lec-view{ready}', timeout=15000)
    page.wait_for_timeout(600)


proc = None
try:
    with sync_playwright() as p:
        proc, cdp = R.launch(proj, config)
        R.CONN.update(pw=p, cdp=cdp)
        b, page = connect(p, cdp)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.on('dialog', lambda d: d.accept())
        version = page.evaluate("() => document.querySelector('meta[name=lec-version]')?.content || ''")
        R.check(f'판 — {version}', version == R.REPO.joinpath('lectern/__init__.py').read_text(encoding='utf-8').split("__version__ = '")[1].split("'")[0], version)
        toast = lambda: page.text_content('#lec-toast') or ''  # noqa: E731

        print('[엑셀 CP949 CSV — 거르고 정렬한 뒤 그 행에서 고치기]')
        open_file(page, '가격.csv', '.csv-view')
        page.fill('.csv-filter input[data-col="1"]', '구리')
        page.locator('.csv-head th[data-col="2"]').click()
        page.locator('.csv-head th[data-col="2"]').click()
        top = page.locator('#lec-view tbody.csv-rows tr.cv-line').first
        R.wait(lambda: '90400' in top.inner_text(), 4)
        line = int(top.get_attribute('data-line'))
        top.click()
        page.keyboard.press('Enter')
        R.check('Enter — 편집 모드가 정렬한 그 행의 줄에서, 머리에 CP949', R.wait(lambda: page.locator('.CodeMirror').count() == 1, 15)
                and page.evaluate("() => document.querySelector('.CodeMirror').CodeMirror.getCursor().line + 1") == line
                and page.inner_text('.lec-editor .ed-enc') == 'CP949')
        page.keyboard.press('End')
        page.keyboard.press('Backspace')
        page.keyboard.press('Control+s')
        R.check('저장 — CP949·CRLF 그대로', R.wait(lambda: raw('가격.csv') == PRICES.replace('90400', '9040').encode('cp949'), 8), raw('가격.csv'))
        page.keyboard.press('Control+End')
        page.keyboard.type('\r\n2026-04,구리 😀,9300')
        before = raw('가격.csv')
        page.keyboard.press('Control+s')
        R.check('CP949 에 없는 글자 — 저장하지 않고 알림', R.wait(lambda: '😀' in toast() and 'CP949' in toast(), 5) and raw('가격.csv') == before, toast())
        page.keyboard.press('Escape')   # 버리고 닫는다 (물음에 예)
        R.wait(lambda: page.locator('.CodeMirror').count() == 0, 8)
        R.check('표가 다시 그려지고 거르기는 그대로', R.wait(lambda: page.input_value('.csv-filter input[data-col="1"]') == '구리'
                and page.locator('#lec-view tr.cv-line', has_text='9040').count() == 1, 8))

        print("[UTF-16 '유니코드 텍스트'의 Tab · log]")
        open_file(page, '유니코드.txt')
        page.locator('#lec-view .cv-line').last.click()
        page.keyboard.press('Control+e')
        R.wait(lambda: page.locator('.CodeMirror').count() == 1, 15)
        page.keyboard.press('Control+End')
        page.keyboard.type('아연')
        page.keyboard.press('Tab')
        page.keyboard.type('7')
        page.keyboard.press('Control+s')
        R.check('UTF-16·BOM·CRLF 그대로, Tab 은 탭 글자', R.wait(lambda: raw('유니코드.txt') == b'\xff\xfe' + '품목\t수량\r\n구리\t12\r\n아연\t7'.encode('utf-16-le'), 8), raw('유니코드.txt')[:40])
        page.keyboard.press('Escape')
        R.wait(lambda: page.locator('.CodeMirror').count() == 0, 8)
        open_file(page, 'run.log')
        R.check('log — [편집] 이 꺼져 있다', page.is_disabled('#lec-btn-edit'))

        print('[통계 체크 칸]')
        open_file(page, '가격.csv', '.csv-view')
        page.locator('.csv-stats-toggle input').uncheck()
        R.check('끄면 통계 줄이 사라진다', R.wait(lambda: page.is_hidden('.csv-stats'), 3))
        page.wait_for_timeout(800)
        R.check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], capture_output=True)
        time.sleep(2)

        print('[다시 실행]')
        proc, cdp = R.launch(proj, config)
        R.CONN.update(cdp=cdp)
        b, page = connect(p, cdp)
        open_file(page, '가격.csv', '.csv-view')
        R.check('다시 실행해도 통계는 꺼진 채', not page.locator('.csv-stats-toggle input').is_checked() and page.is_hidden('.csv-stats'))
        b.close()
except Exception:
    traceback.print_exc()
    R.fails.append('예외')
finally:
    if proc:
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], capture_output=True)
    time.sleep(1)
    shutil.rmtree(base, ignore_errors=True)
print(f'\n{R.count}개 중 실패 {len(R.fails)}개', R.fails)
