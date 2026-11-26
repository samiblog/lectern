"""0.110.1 — 실제 창(WebView2)에서: 사용자의 폭(사이드바 387·목차 376·터미널 722px)으로 목차 단추 (D208)와 그림 보기 (D209).
창이 좁아도(이 시험의 창은 1080px 보다 좁다) 목차 단추를 누르면 목차가 보이고 다시 누르면 감춘다, 오른쪽 터미널을 연 채로도 문서 칸이 남고 앱이 창보다 넓지 않다,
'자료 → 그림' 에서 누르면 그림 보기.
  python tools/real/real1101.py [--exe <Lectern.exe>]   (없으면 소스의 app.py)"""
import json
import shutil
import struct
import subprocess
import tempfile
import time
import traceback
import zlib
from pathlib import Path

from playwright.sync_api import sync_playwright

import realwin as R


def png(w, h, rgb):
    raw = b''.join(b'\x00' + bytes(rgb) * w for _ in range(h))

    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')


base = Path(tempfile.mkdtemp(prefix='lec-real1101-'))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'language': 'ko', 'work_alerts': False, 'sidebar_width': 387, 'toc_width': 376, 'terminal_width': 722,
                                                'terminal_position': 'side'}), encoding='utf-8')
proj = base / '과제'
(proj / '그림').mkdir(parents=True)
(proj / '보고서.md').write_text('# 보고서\n\n## 첫 절\n\n글\n\n## 둘째 절\n\n글\n', encoding='utf-8', newline='\n')
(proj / '그림' / '도표.png').write_bytes(png(40, 30, (30, 120, 200)))
(proj / '메모.txt').write_text('자료\n', encoding='utf-8')

ST = """() => { const toc = document.querySelector('#lec-toc'); const r = toc.getBoundingClientRect(); const p = document.querySelector('#lec-panes').getBoundingClientRect();
  return { shown: getComputedStyle(toc).display !== 'none' && r.width > 0, right: Math.round(r.right), panes: Math.round(p.width), body: document.body.scrollWidth, w: innerWidth }; }"""

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
        st = lambda: page.evaluate(ST)   # noqa: E731

        print('[목차 단추 — 사용자의 폭]')
        page.click('#lec-tree .row[data-doc="보고서.md"]')
        page.wait_for_selector('#lec-toc a', state='attached', timeout=15000)
        w = st()['w']
        if st()['shown']:
            page.click('#lec-btn-toc')
            R.wait(lambda: not st()['shown'], 5)
        page.click('#lec-btn-toc')
        R.wait(lambda: st()['shown'], 5)
        R.check(f'목차 단추를 누르면 목차가 보인다 (창 {w}px)', st()['shown'] and st()['right'] <= w + 1, st())
        page.click('#lec-btn-toc')
        R.wait(lambda: not st()['shown'], 5)
        R.check('다시 누르면 감춘다', not st()['shown'], st())

        print('[오른쪽 터미널을 연 채로]')
        page.click('#lec-btn-term')
        page.wait_for_timeout(2500)
        page.click('#lec-btn-toc')
        R.wait(lambda: st()['shown'] and st()['body'] <= st()['w'], 8)
        s = st()
        R.check('터미널을 연 채로 목차가 보이고, 문서 칸은 남고(300px 이상), 앱이 창보다 넓지 않다', s['shown'] and s['panes'] >= 300 and s['body'] <= s['w'], s)
        page.click('#lec-btn-toc')
        R.wait(lambda: not st()['shown'], 5)
        R.check('— 다시 누르면 감춘다', not st()['shown'], st())
        page.click('#lec-btn-term')
        page.wait_for_timeout(800)

        print("[그림 보기 — '자료 → 그림']")
        page.click('#lec-others-head')
        page.wait_for_selector('#lec-others .kind-head[data-kind="image"]', timeout=10000)
        page.click('#lec-others .kind-head[data-kind="image"]')
        page.click('#lec-others-list .row[data-path="그림/도표.png"]')
        R.wait(lambda: page.evaluate("() => { const i = document.querySelector('#lec-view .iv-img'); return !!i && i.complete && i.naturalWidth === 40; }"), 15)
        R.check('그림 파일을 누르면 WebView2 에서 그림 보기 (40×30)', page.evaluate("() => { const i = document.querySelector('#lec-view .iv-img'); return !!i && i.naturalWidth === 40 && i.naturalHeight === 30; }"))
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
