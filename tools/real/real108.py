"""0.108.0 — 실제 창(WebView2)에서: 사이드바 '작업' 묶음 (D204) — 문서 → 코드 → 자료 → 작업 → 폴더, 업무 카드·형광펜·할 일,
접힌 동안 읽지 않고 펼치면 읽는다, Ctrl+Shift+E 로 들어가 할 일 줄에 초점, 할 일 줄의 Shift+→ 가 실제 셸에 '@경로 N행' (Enter 없이).
  python tools/real/real108.py [--exe <Lectern.exe>]   (없으면 소스의 app.py)"""
import json
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

import realwin as R

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from test_sheet import make_xlsx  # noqa: E402

base = Path(tempfile.mkdtemp(prefix='lec-real108-'))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'language': 'ko', 'work_alerts': False}), encoding='utf-8')
proj = base / '사업'
(proj / '보고').mkdir(parents=True)
(proj / '자료').mkdir()
(proj / '보고서.md').write_text('# 2026년 사업 보고서\n\n- [ ] 표 고치기\n', encoding='utf-8', newline='\n')
(proj / '보고' / '계획서.docx').write_bytes(b'PK\x03\x04 word')
(proj / '보고' / '발표.pptx').write_bytes(b'PK\x03\x04 ppt')
(proj / '보고' / '공문.hwp').write_bytes(b'\xd0\xcf\x11\xe0 hwp')
(proj / '자료' / '표.csv').write_text('항목,금액\n인건비,100\n', encoding='utf-8')
make_xlsx(proj / '자료' / '예산.xlsx', sheets=[('값', '<row r="1"><c r="A1" t="s"><v>0</v></c></row><row r="2"><c r="A2"><v>2026</v></c></row>', None)], shared=('연도',))

SECS = "() => ['#lec-docs', '#lec-code', '#lec-others', '#lec-work', '#lec-folder'].map((s) => document.querySelector(s).classList.contains('grow') ? 'open' : '-')"
ITEMS = "() => [...document.querySelectorAll('#lec-work-list .row.item')].map((r) => r.dataset.itemDoc + '#' + r.dataset.line)"
TEXT = """(n) => import('/static/js/store.js').then((m) => { const term = (m.S.tab.terms || []).find((x) => x.n === n); if (!term?.xterm) return '';
  const b = term.xterm.buffer.active; const out = []; for (let i = 0; i < b.length; i++) out.push(b.getLine(i).translateToString(true)); return out.join(''); })"""

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
        page.wait_for_timeout(1500)
        errors, marks = [], []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.on('request', lambda r: marks.append(r.url) if '/api/marks' in r.url else None)

        print("['작업' 묶음]")
        R.check('다섯 묶음, 작업은 접혀 있고 읽지 않았다', page.evaluate(SECS) == ['open', '-', '-', '-', '-'] and not marks, (page.evaluate(SECS), marks))
        page.locator('#lec-tree .row.file').first.focus()
        for _ in range(3):
            page.keyboard.press('Control+Shift+e')
            page.wait_for_timeout(400)
        R.wait(lambda: page.evaluate(SECS)[3] == 'open' and page.evaluate("() => !!document.activeElement?.closest?.('#lec-work-list .row')"), 15)
        R.check('Ctrl+Shift+E 로 작업에 들어가 목록의 행에 초점', page.evaluate("() => !!document.activeElement?.closest?.('#lec-work-list .row')"), page.evaluate("() => document.activeElement?.outerHTML?.slice(0, 120)"))
        R.wait(lambda: page.evaluate(ITEMS) == ['보고서.md#3'], 15)
        R.check('할 일 — 보고서.md 3행', page.evaluate(ITEMS) == ['보고서.md#3'], page.evaluate(ITEMS))
        page.locator('#lec-work-list .row.item').first.focus()
        page.keyboard.press('Shift+ArrowRight')
        R.wait(lambda: '@보고서.md' in page.evaluate(TEXT, 0), 60)
        got = page.evaluate(TEXT, 0)
        R.check("할 일 줄의 Shift+→ — '@보고서.md 3행' 이 실제 셸에, Enter 없이", '@보고서.md' in got and '3' in got and got.count('PS ') == 1, got[-160:])
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
