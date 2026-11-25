"""0.104.0 — 실제 창(WebView2)에서: 인쇄·PDF 의 여백을 숫자로 (D200). 미리보기 PDF 를 받아 글의 자리를 잰다 (PyMuPDF — 없으면 건너뛴다).
  python tools/real/real104p.py [--exe <Lectern.exe>]"""
import base64
import json
import shutil
import subprocess
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

import realwin as R

try:
    import pymupdf
except ImportError:
    pymupdf = None

base = Path(tempfile.mkdtemp(prefix='lec-real104p-'))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'language': 'ko', 'work_alerts': False}), encoding='utf-8')
proj = base / '보고'
proj.mkdir()
(proj / '보고서.md').write_text('# 여백 시험\n\n' + '\n\n'.join('구리 가격이 오른 까닭을 여러 자료로 살핀 긴 문단입니다. ' * 8 for _ in range(24)) + '\n', encoding='utf-8')
(proj / '발표.md').write_text('---\nmarp: true\n---\n\n# 표지\n\n---\n\n## 둘째\n\n글\n', encoding='utf-8')
MM = 72 / 25.4


def measure(page):
    """미리보기 PDF 의 [쪽 크기 mm], 본문 글이 놓인 [위, 오른쪽, 아래, 왼쪽] 여백 mm (모든 쪽에서 가장 바깥), 머리·쪽 번호가 있는지"""
    src = page.evaluate("() => document.querySelector('#lec-print-frame').getAttribute('src').split('#')[0]")
    b64 = page.evaluate("(u) => fetch(u).then((r) => r.arrayBuffer()).then((b) => { let s = ''; const v = new Uint8Array(b); for (let i = 0; i < v.length; i += 8192) s += String.fromCharCode(...v.subarray(i, i + 8192)); return btoa(s); })", src)
    doc = pymupdf.open(stream=base64.b64decode(b64), filetype='pdf')
    rect = doc[0].rect
    edge = [9e9, 9e9, 9e9, 9e9]
    head = foot = False
    for n, pg in enumerate(doc):
        for x0, y0, x1, y1, text, *_ in pg.get_text('blocks'):
            t = text.strip()
            if not t:
                continue
            if t.startswith('- ') and t.endswith(' -'):
                foot = True
                continue
            if n and y1 < 120 and ('여백 시험' in t or '년' in t and len(t) < 30):
                head = True
                continue
            edge = [min(edge[0], y0) if n else edge[0], min(edge[1], rect.width - x1), min(edge[2], rect.height - y1), min(edge[3], x0)]
    return [round(rect.width / MM), round(rect.height / MM)], [round(e / MM, 1) for e in edge], head, foot


def ready(page, n=30):
    return R.wait(lambda: page.evaluate("() => document.querySelector('#lec-print-wait').hidden && !!document.querySelector('#lec-print-frame').getAttribute('src')"), n)


def numbers(page, values):
    before = page.evaluate("() => document.querySelector('#lec-print-frame').getAttribute('src')")
    for i, v in enumerate(values):
        page.locator('#lec-print .pp-mm input').nth(i).fill(str(v))
    R.wait(lambda: page.evaluate("() => document.querySelector('#lec-print-frame').getAttribute('src')") != before, 20)
    page.wait_for_timeout(900)
    ready(page)


proc = None
try:
    if pymupdf is None:
        print('PyMuPDF 가 없어 건너뜁니다')
        raise SystemExit(0)
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
        R.check('문서를 연다', R.open_doc(page, '보고서.md'))
        page.evaluate("() => import('/static/js/printdoc.js').then((m) => m.openPrint('print'))")
        page.wait_for_selector('#lec-print:not([hidden])')
        ready(page)
        page.wait_for_timeout(800)
        size, m, head, foot = measure(page)
        R.check('보통: A4, 위 25·좌우 22 (글은 그 안에서 시작)', size == [210, 297] and abs(m[3] - 22) < 1.5 and 21 < m[1] < 26 and 24 < m[0] < 28 and head and foot, (size, m, head, foot))
        numbers(page, [40, 50, 35, 10])
        R.check("숫자를 적으면 '직접' 으로", page.evaluate("() => document.querySelector('#lec-print input[name=pp_margin]:checked').value") == 'custom')
        size, m2, head, foot = measure(page)
        R.check('적은 숫자가 PDF 의 여백이 된다 (위 40·오른쪽 50·아래 35·왼쪽 10)', size == [210, 297] and abs(m2[3] - 10) < 1.5 and 49 < m2[1] < 55 and 39 < m2[0] < 43 and m2[2] >= 34.5 and head and foot, (m, m2, head, foot))
        numbers(page, [5, 5, 5, 5])
        _, m3, head, foot = measure(page)
        R.check('아주 좁게 5mm — 쪽 머리·쪽 번호는 빠진다고 알린다', abs(m3[3] - 5) < 1.5 and 4 < m3[0] < 9 and not head and not foot and '쪽 머리 · 쪽 번호' in page.inner_text('#lec-pp-mm-note'), (m3, head, foot, page.inner_text('#lec-pp-mm-note')))
        numbers(page, [12.5, 20, 12.5, 33])
        _, m4, head, foot = measure(page)
        R.check('소수도 (12.5·20·12.5·33)', abs(m4[3] - 33) < 1.5 and 19 < m4[1] < 25 and head and foot, (m4, head, foot))
        page.keyboard.press('Escape')
        page.evaluate("() => import('/static/js/printdoc.js').then((m) => m.openPrint('pdf'))")
        page.wait_for_selector('#lec-print:not([hidden])')
        ready(page)
        R.check('다시 열어도 그 숫자', page.evaluate("() => [...document.querySelectorAll('#lec-print .pp-mm input')].map((e) => Number(e.value))") == [12.5, 20, 12.5, 33])
        page.keyboard.press('Escape')
        R.check('슬라이드', R.open_doc(page, '발표.md'))
        page.evaluate("() => import('/static/js/printdoc.js').then((m) => m.openPrint('pdf'))")
        page.wait_for_selector('#lec-print:not([hidden])')
        ready(page)
        page.wait_for_timeout(600)
        src = page.evaluate("() => document.querySelector('#lec-print-frame').getAttribute('src')")
        size, *_ = measure(page)
        R.check('Lectern 슬라이드는 여백과 상관없이 슬라이드 크기', size[0] > size[1] and src, size)
        R.check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except SystemExit:
    pass
except Exception:   # noqa: BLE001
    traceback.print_exc()
    R.fails.append('예외')
finally:
    if proc:
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], capture_output=True)
    time.sleep(1)
    shutil.rmtree(base, ignore_errors=True)
print(f'\n{R.count}개 중 실패 {len(R.fails)}개', R.fails)
