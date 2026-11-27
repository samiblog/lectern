"""0.111.0 — 실제 창(WebView2)에서: 목록의 수준 (D210 — 맨 위 항목은 진하게·1.05배)과 내 스타일 만들기 (D211 — 칸을 고르면 문서에 입혀 보고,
저장하면 설정 폴더 styles 에 CSS 하나가 생기고 그 스타일로 바뀐다. 다시 열면 값을 불러온다).
  python tools/real/real111.py [--exe <Lectern.exe>]   (없으면 소스의 app.py)"""
import json
import shutil
import subprocess
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

import realwin as R

base = Path(tempfile.mkdtemp(prefix='lec-real111-'))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'language': 'ko', 'work_alerts': False, 'theme': 'report'}), encoding='utf-8')
proj = base / '과제'
proj.mkdir()
(proj / '보고서.md').write_text('# 보고서\n\n## 수요\n\n□ 전기차 투자\n○ 한 대에 83kg\n□ 공급은 빠듯\n\n- 가격\n  - 재고\n- 전망\n', encoding='utf-8', newline='\n')

WEIGHT = "(t) => { const e = [...document.querySelectorAll('#lec-view .lec-mark, #lec-view li')].find((x) => x.textContent.trim().startsWith(t)); return e ? Number(getComputedStyle(e).fontWeight) : 0; }"
SIZE = "() => { const v = document.querySelector('#lec-view'); return Math.round(parseFloat(getComputedStyle(v).fontSize) / (parseFloat(getComputedStyle(v).getPropertyValue('--md-scale')) || 1) * 10) / 10; }"

proc = None
try:
    with sync_playwright() as p:
        proc, cdp = R.launch(proj, config)
        R.CONN.update(pw=p, cdp=cdp)
        b = None
        for _ in range(120):
            try:
                b = p.chromium.connect_over_cdp(f'http://127.0.0.1:{cdp}')
                break
            except Exception:   # noqa: BLE001
                time.sleep(0.5)
        page = R.wait(lambda: R.app_page(b), 60)
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=40000)
        page.wait_for_timeout(1200)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))

        print('[목록의 수준]')
        page.click('#lec-tree .row[data-doc="보고서.md"]')
        page.wait_for_selector('#lec-view .lec-marklist', timeout=15000)
        R.check('□ · Markdown 맨 위 항목은 진하게, ○ · 둘째는 보통', page.evaluate(WEIGHT, '□ 전기차') >= 600 and page.evaluate(WEIGHT, '가격') >= 600
                and page.evaluate(WEIGHT, '○ 한 대') < 600 and page.evaluate(WEIGHT, '재고') < 600)

        print('[내 스타일 만들기]')
        page.select_option('#lec-theme', '__make')
        page.wait_for_selector('#lec-stylemaker:not([hidden])', timeout=8000)
        f = page.locator('#lec-stylemaker [data-key="--md-size"]')
        f.fill('19')
        f.dispatch_event('input')
        R.wait(lambda: page.evaluate(SIZE) == 19, 5)
        R.check('칸을 고르면 WebView2 의 문서에 바로', page.evaluate(SIZE) == 19, page.evaluate(SIZE))
        page.fill('#lec-stylemaker-name', '실제 창 스타일')
        page.click('#lec-stylemaker-save')
        made = config / 'styles' / '실제 창 스타일.css'
        R.wait(lambda: made.exists() and page.evaluate("() => document.documentElement.dataset.theme") == 'user:실제 창 스타일', 10)
        R.check('저장 — 설정 폴더 styles 에 CSS 하나, 그 스타일로', made.exists() and '--md-size: 19px;' in made.read_text(encoding='utf-8')
                and page.evaluate("() => document.documentElement.dataset.theme") == 'user:실제 창 스타일')
        page.select_option('#lec-theme', '__make')
        page.wait_for_selector('#lec-stylemaker:not([hidden])', timeout=8000)
        R.check('다시 열면 저장한 값을 불러온다', page.input_value('#lec-stylemaker [data-key="--md-size"]') == '19' and page.input_value('#lec-stylemaker-name') == '실제 창 스타일')
        page.keyboard.press('Escape')
        R.check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    R.fails.append('예외')
finally:
    if proc:
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], capture_output=True)
    time.sleep(1)
    shutil.rmtree(base, ignore_errors=True)
print(f'\n{R.count}개 중 실패 {len(R.fails)}개', R.fails)
