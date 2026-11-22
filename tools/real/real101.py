"""0.101.0 — 실제 창(WebView2)에서: 번호·글머리 글자로 시작하는 블록의 내어쓰기(D191) — WebView2 가 `text-indent: … hanging each-line` 을 알고,
꺾인 줄이 머리 글자 뒤에 맞고, 줄바꿈 뒤의 줄은 들여 쓰지 않고, 한 줄 편집 중에도 같은 모양인지.
  python tools/real/real101.py [--exe <Lectern.exe>]   (없으면 소스의 app.py)"""
import json
import shutil
import subprocess
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

import realwin as R

base = Path(tempfile.mkdtemp(prefix='lec-real101-'))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'language': 'ko', 'work_alerts': False, 'theme': 'report'}), encoding='utf-8')
proj = base / '연구'
proj.mkdir(parents=True)
L = '인공지능 확산은 산업 전반의 생산성을 끌어올리지만 그 효과는 업종과 기업 규모에 따라 크게 다르게 나타나며 정책 대응도 달라져야 한다. ' * 2
DOC = f"""# 내어쓰기

## 1. 추진 배경 — 생산성 증가와 고용 재편이 동시에 나타나는 전환기에 정부와 기업이 함께 풀어야 할 정책 과제를 정리한다

□ {L}
○ {L}

- ① {L}
- ② {L}

※ 참고: {L}
"""
(proj / '보고서.md').write_text(DOC, encoding='utf-8', newline='\n')

# 블록의 첫 줄에서 머리 글자 뒤 글이 시작하는 x 와 꺾인 다음 화면 줄의 x 의 차이 (em)
GAP = """(el) => import('/static/js/hang.js').then(({ blockHang }) => {
  const own = el.tagName === 'LI' ? [...el.childNodes].filter((n) => n.nodeType === 3 || !/^(UL|OL|P)$/.test(n.tagName)).map((n) => n.textContent).join('') : el.textContent;
  const h = blockHang(own); if (!h) return null;
  const boxes = []; const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT); let at = 0;
  for (let n = w.nextNode(); n; n = w.nextNode()) { for (let i = 0; i < n.length; i++) { const r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + 1);
    const b = [...r.getClientRects()].find((x) => x.width); if (b && at + i >= h.at) boxes.push({ i: at + i, left: b.left, top: b.top }); } at += n.length; }
  const fs = parseFloat(getComputedStyle(el).fontSize); const start = boxes[0];
  const body = boxes.find((x) => x.i >= h.at + h.prefix.length); const next = boxes.find((x) => x.top > start.top + fs / 2);
  return next ? Math.round(((next.left - body.left) / fs) * 100) / 100 : null; })"""


def connect(p, cdp):
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
    return b, page


proc = None
try:
    with sync_playwright() as p:
        proc, cdp = R.launch(proj, config)
        R.CONN.update(pw=p, cdp=cdp)
        b, page = connect(p, cdp)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        version = page.evaluate("() => document.querySelector('meta[name=lec-version]')?.content || ''")
        R.check(f'판 {R.VERSION}', version == R.VERSION or not version, version)
        engine = page.evaluate("navigator.userAgent.match(/Edg\\/[\\d.]+/)?.[0] || navigator.userAgent")
        print('   WebView2:', engine)

        print('[내어쓰기 (D191)]')
        R.check('WebView2 가 text-indent 의 hanging each-line 을 안다', page.evaluate("CSS.supports('text-indent', '1em hanging each-line')"))
        R.check('보고서를 연다', R.open_doc(page, '보고서.md'))
        page.wait_for_timeout(800)
        R.check('머리 글자로 시작하는 블록 다섯이 내어 쓴다 (제목·□○ 문단·① ② 항목·※)', page.locator('#lec-view .lec-hang').count() == 5, page.locator('#lec-view .lec-hang').count())
        gaps = [page.evaluate(GAP, h) for h in page.locator('#lec-view .lec-hang').element_handles()]
        R.check('꺾인 줄이 모두 머리 글자 뒤에 (차이 0.05em 아래)', all(g is not None and abs(g) < 0.05 for g in gaps), gaps)
        starts = page.evaluate("""() => { const el = [...document.querySelectorAll('#lec-view p')].find((x) => x.textContent.startsWith('□'));
          const r = document.createRange(); const out = []; const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
          for (let n = w.nextNode(); n; n = w.nextNode()) { const i = n.data.search(/[□○] /); if (i < 0) continue; r.setStart(n, i); r.setEnd(n, i + 1); out.push(Math.round(r.getClientRects()[0].left)); }
          return out; }""")
        R.check('줄바꿈 뒤의 ○ 줄은 □ 줄과 같은 자리에서 시작', len(starts) == 2 and starts[0] == starts[1], starts)

        print('[한 줄 편집 중]')
        page.locator('#lec-view p', has_text='※ 참고').click(position={'x': 200, 'y': 8})
        page.keyboard.press('Enter')
        R.wait(lambda: page.evaluate("document.activeElement?.classList?.contains('lec-line-edit')"), 5)
        g = page.evaluate("""() => { const sp = document.activeElement; const node = sp.firstChild; const r = document.createRange();
          const box = (i) => { r.setStart(node, i); r.setEnd(node, i + 1); return r.getClientRects()[0]; };
          const fs = parseFloat(getComputedStyle(sp).fontSize); const body = box(2);
          for (let i = 3; i < node.length; i++) { const b = box(i); if (b && b.top > body.top + fs / 2) return Math.round(((b.left - body.left) / fs) * 100) / 100; } return null; }""")
        R.check('고치는 동안에도 꺾인 줄이 ※ 뒤에', g is not None and abs(g) < 0.05, g)
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
