"""0.105.0 — 실제 창(WebView2)에서: PDF 보기 (D201) — pdf.js 가 앱의 CSP 아래 WebView2 에서 돌고(일꾼·글자표·디코더), 한글 PDF 를 그리고,
책갈피 목차·찾기·고른 글 담기(담은 곳은 그 쪽)가 되고, Shift+→ 가 실제 셸에 '@경로 N쪽' 을 넣는다 (Enter 없이). PDF 의 스크립트는 돌지 않는다.
  python tools/real/real105.py [--exe <Lectern.exe>]   (없으면 소스의 app.py)"""
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
base = Path(tempfile.mkdtemp(prefix='lec-real105-'))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'language': 'ko', 'work_alerts': False}), encoding='utf-8')
proj = base / '자료함'
(proj / '보고서').mkdir(parents=True)
for n in ('cid', 'script'):
    shutil.copy(EDGE_PDFS / f'{n}.pdf', proj / '보고서' / f'{n}.pdf')
(proj / '메모.md').write_text('# 메모\n\n글\n', encoding='utf-8', newline='\n')
CLIPS = proj / '.lectern' / 'clips'

with sync_playwright() as p:   # 40쪽 한글 보고서 — Chromium 의 PDF (책갈피)
    b = p.chromium.launch()
    pg = b.new_page()
    pg.set_content('<!doctype html><meta charset="utf-8"><style>body{font:11pt "Malgun Gothic"}</style>' + ''.join(
        f'<h1>{i}. 구리 시장 {i}절</h1><p>{i}절 본문입니다. 2분기 구리 가격은 LME 재고 감소와 함께 올랐다.</p><p>{"긴 문단을 이어 쓴다. " * 40}</p><div style="page-break-after:always"></div>' for i in range(1, 41)))
    pg.pdf(path=str(proj / '보고서' / '구리.pdf'), format='A4', outline=True, tagged=True)
    b.close()

ST = "() => import('/static/js/store.js').then(({ S }) => S.pane.pdf ? { cur: S.pane.pdf.cur, pages: S.pane.pdf.doc?.numPages || 0 } : null)"
LAYER = "(n) => [...document.querySelectorAll(`#lec-view .pdf-pg[data-n=\"${n}\"] .textLayer span`)].map((e) => e.textContent).join('')"
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
        errors, dialogs, csp = [], [], []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.on('dialog', lambda d: (dialogs.append(d.message), d.dismiss()))
        page.on('console', lambda m: csp.append(m.text[:200]) if 'Content Security Policy' in m.text else None)

        print('[PDF 열기]')
        t0 = time.monotonic()
        page.locator('#lec-tree .row[data-doc="보고서/구리.pdf"]').click()
        page.wait_for_selector('#lec-view.pdf-view .pdf-pg[data-n="1"].drawn', timeout=30000)
        took = time.monotonic() - t0
        R.check(f'WebView2 에서 pdf.js 가 돈다 — {took:.1f}초, 40쪽', (page.evaluate(ST) or {}).get('pages') == 40 and took < 8, (page.evaluate(ST), took))
        R.check('한글 글 층', '2분기 구리 가격은 LME 재고 감소와 함께 올랐다' in page.evaluate(LAYER, 1), page.evaluate(LAYER, 1)[:80])
        R.wait(lambda: page.locator('#lec-toc a[data-i]').count() == 40, 10)
        R.check('책갈피 목차', page.locator('#lec-toc a[data-i]').count() == 40)
        page.locator('#lec-toc a[data-i]').nth(11).click()
        R.wait(lambda: (page.evaluate(ST) or {}).get('cur') == 12 and '12절 본문입니다' in page.evaluate(LAYER, 12), 10)
        R.check('책갈피로 12쪽', page.evaluate(ST)['cur'] == 12, page.evaluate(ST))

        print('[찾기 · 담기]')
        page.keyboard.press('Control+f')
        page.keyboard.type('27절 본문')
        R.wait(lambda: page.inner_text('#lec-find-count') == '1/1' and page.evaluate(ST)['cur'] == 27, 15)
        R.check('Ctrl+F — 모든 쪽에서 찾아 그 쪽으로', page.inner_text('#lec-find-count') == '1/1' and page.evaluate(ST)['cur'] == 27, (page.inner_text('#lec-find-count'), page.evaluate(ST)))
        page.keyboard.press('Escape')
        span = page.locator('#lec-view .pdf-pg[data-n="27"] .textLayer span', has_text='27절 본문입니다').first
        box = span.bounding_box()
        page.mouse.move(box['x'] + 2, box['y'] + box['height'] / 2)
        page.mouse.down()
        page.mouse.move(box['x'] + box['width'] - 2, box['y'] + box['height'] / 2, steps=10)
        page.mouse.up()
        page.keyboard.press('Alt+c')
        R.wait(lambda: CLIPS.exists() and any('page=27' in f.read_text(encoding='utf-8') for f in CLIPS.glob('*.md')), 10)
        R.check('고른 글을 Alt+C — 담은 곳은 그 쪽', CLIPS.exists() and any('page=27' in f.read_text(encoding='utf-8') and '27절 본문입니다' in f.read_text(encoding='utf-8') for f in CLIPS.glob('*.md')))

        print('[Shift+→ — 실제 셸]')
        page.locator('#lec-content').focus()
        page.keyboard.press('Shift+ArrowRight')
        R.wait(lambda: '@보고서/구리.pdf27쪽' in page.evaluate(TEXT, 0).replace(' ', ''), 60)
        got = page.evaluate(TEXT, 0)
        R.check("'@보고서/구리.pdf 27쪽' 이 실제 셸에 — Enter 없이", '@보고서/구리.pdf27쪽' in got.replace(' ', '') and got.count('PS ') == 1, got[-160:])

        print('[글꼴을 넣지 않은 한글 · 스크립트]')
        page.locator('#lec-tree .row[data-doc="보고서/cid.pdf"]').click()
        page.wait_for_selector('#lec-view.pdf-view .pdf-pg[data-n="1"].drawn', timeout=30000)
        R.wait(lambda: '핵심 광물 공급망' in page.evaluate(LAYER, 1), 10)
        R.check('CMap 으로 한글 (앱 안의 글자표)', '핵심 광물 공급망' in page.evaluate(LAYER, 1), page.evaluate(LAYER, 1))
        page.locator('#lec-tree .row[data-doc="보고서/script.pdf"]').click()
        page.wait_for_selector('#lec-view.pdf-view .pdf-pg[data-n="1"].drawn', timeout=30000)
        page.wait_for_timeout(1500)
        R.check('PDF 의 스크립트는 돌지 않는다', not dialogs, dialogs)
        R.check('CSP 위반 없음 (일꾼·wasm·글자표)', not csp, csp[:3])
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
