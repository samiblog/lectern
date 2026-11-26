"""0.110.0 — 실제 창(WebView2)에서: '자료' 묶음의 종류별 하위 묶음 (D207)과 기본 자리 (D206) — PDF·오피스는 '자료', 하위 묶음 개수,
PDF 묶음에서 누르면 pdf.js 로 그린다, Excel·CSV 묶음에서 csv 를 누르면 표, 그림 묶음의 폴더는 펼친 채.
  python tools/real/real110.py [--exe <Lectern.exe>]   (없으면 소스의 app.py)"""
import json
import shutil
import subprocess
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

import realwin as R

EDGE_PDFS = Path(__file__).resolve().parents[1] / 'edges' / 'pdfs'
base = Path(tempfile.mkdtemp(prefix='lec-real110-'))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'language': 'ko', 'work_alerts': False}), encoding='utf-8')
proj = base / '과제'
(proj / '받은 자료' / '그림').mkdir(parents=True)
(proj / '보고서.md').write_text('# 보고서\n', encoding='utf-8', newline='\n')
shutil.copy(EDGE_PDFS / 'cid.pdf', proj / '받은 자료' / '기관 보고서.pdf')
(proj / '받은 자료' / '계약서.docx').write_bytes(b'PK\x03\x04 docx')
(proj / '받은 자료' / '가격.csv').write_text('월,가격\n1월,9100\n', encoding='utf-8')
(proj / '받은 자료' / '그림' / '도표.png').write_bytes(b'\x89PNG\r\n\x1a\n')

KINDS = "() => [...document.querySelectorAll('#lec-others .kind-head')].map((b) => b.dataset.kind + ':' + b.querySelector('.n').textContent)"
ROWS = "() => [...document.querySelectorAll('#lec-others-list .row')].map((r) => r.dataset.path)"
VIEW = "() => import('/static/js/store.js').then(({ S }) => S.view && S.view.type + ':' + S.view.path)"

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
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))

        print("['문서' 에는 md 만, '자료' 에 PDF·오피스]")
        R.check("'문서' 트리에 PDF 가 없다", page.locator('#lec-tree .row[data-doc$=".pdf"]').count() == 0)
        page.click('#lec-others-head')
        R.wait(lambda: len(page.evaluate(KINDS)) > 2, 15)
        R.check("'자료' 의 하위 묶음 — 전체 4 · PDF 1 · Word 1 · Excel·CSV 1 · 그림 1", page.evaluate(KINDS) == ['all:4', 'pdf:1', 'word:1', 'excel:1', 'image:1'], page.evaluate(KINDS))
        page.click('#lec-others .kind-head[data-kind="pdf"]')
        page.click('#lec-others-list .row[data-path="받은 자료/기관 보고서.pdf"]')
        page.wait_for_selector('#lec-view.pdf-view .pdf-pg[data-n="1"].drawn', timeout=30000)
        R.check('PDF 묶음에서 누르면 WebView2 에서 pdf.js 가 그린다', page.evaluate(VIEW) == 'doc:받은 자료/기관 보고서.pdf', page.evaluate(VIEW))
        page.click('#lec-others .kind-head[data-kind="excel"]')
        page.click('#lec-others-list .row[data-path="받은 자료/가격.csv"]')
        R.wait(lambda: page.evaluate(VIEW) == 'code:받은 자료/가격.csv' and '9100' in page.inner_text('#lec-view'), 15)
        R.check('Excel·CSV 묶음의 csv 는 표', '9100' in page.inner_text('#lec-view'), page.evaluate(VIEW))
        page.click('#lec-others .kind-head[data-kind="image"]')
        R.wait(lambda: '받은 자료/그림/도표.png' in page.evaluate(ROWS), 10)
        R.check('그림 묶음 — 폴더를 펼친 채 도표.png', page.evaluate(ROWS) == ['받은 자료', '받은 자료/그림', '받은 자료/그림/도표.png'], page.evaluate(ROWS))
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
