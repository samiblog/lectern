"""0.100.0 — 실제 창(WebView2)에서: md 문서 점검(D190) — 상태줄 '점검 N곳'·목록·고치기·Ctrl+Z, 있는 그림과 없는 그림(자기 서버에 HEAD),
설정 창의 '문서 점검에 글버릇도', 그리고 한 줄 편집(D189) — 꺾인 긴 줄의 화면 줄 맨 앞에서 ↑, 새 항목 Tab 의 글머리표, 끌어 고른 여러 줄의 Delete,
접힌 머리 설정.
  python tools/real/real100.py [--exe <Lectern.exe>]   (없으면 소스의 app.py)"""
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

base = Path(tempfile.mkdtemp(prefix='lec-real100-'))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'language': 'ko', 'work_alerts': False, 'toc_visible': True}), encoding='utf-8')
proj = base / '연구'
proj.mkdir(parents=True)
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')
(proj / '있는.png').write_bytes(PNG)
F = '```'
LONG = ('인공지능의 확산은 노동 시장과 생산성에 동시에 영향을 미치며, 특히 서비스 산업에서는 업무 방식이 크게 바뀌고 있다. ' * 4).rstrip()
REPORT = f"""---
title: 실제 창 시험
---

# 실제 창 보고서

## 가

- 하나
- 둘
* 셋

> [!NOTES]
> 메모

![있는 그림](있는.png)

![없는 그림](없는.png)

## 나

{LONG}

짧은 줄  
이어지는 줄

## 다

{F}python
x = 1
"""
DOC = proj / '보고서.md'
DOC.write_text(REPORT, encoding='utf-8', newline='\n')
PARAS = '# 끌기\n\n문단 하나\n\n문단 둘\n\n문단 셋\n\n문단 넷\n'
(proj / '끌기.md').write_text(PARAS, encoding='utf-8', newline='\n')
CARET = """() => { const sp = document.activeElement; if (!sp?.classList?.contains('lec-line-edit')) return null;
  const sel = getSelection(); const pre = document.createRange(); pre.selectNodeContents(sp); pre.setEnd(sel.focusNode, sel.focusOffset);
  const node = sp.firstChild; const text = sp.textContent; const starts = [0]; let prev = null;
  for (let i = 0; node && i < text.length; i++) { const r = document.createRange(); r.setStart(node, i); r.setEnd(node, i + 1);
    const b = [...r.getClientRects()].find((x) => x.width); if (!b) continue; if (prev != null && b.top - prev > b.height / 2) starts.push(i); prev = b.top; }
  return { text: text.slice(0, 8), offset: pre.toString().length, starts }; }"""


def text(path=DOC):
    for _ in range(40):
        try:
            return path.read_text(encoding='utf-8')
        except OSError:
            time.sleep(0.05)
    return path.read_text(encoding='utf-8')


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
        label = lambda: page.evaluate("(() => { const b = document.querySelector('#lec-st-lint'); return b.hidden ? null : b.textContent.trim(); })()")   # noqa: E731

        print('[문서 점검 (D190)]')
        R.check('보고서를 연다', R.open_doc(page, '보고서.md'))
        got = R.wait(lambda: label() == '점검 4곳', 15)
        R.check("상태줄 '점검 4곳' — 글머리표·강조글 종류·없는 그림·닫지 않은 코드 블록 (있는 그림은 아니다)", bool(got), label())
        page.locator('#lec-st-lint').click()
        page.wait_for_selector('#lec-menu:not([hidden]) .menu-head', timeout=5000)
        rows = page.evaluate("[...document.querySelectorAll('#lec-menu button[data-i]')].map((e) => e.textContent.trim())")
        R.check('— 목록에 없는 그림 (자기 서버에 물음), 있는 그림은 없다', any('없는.png' in r for r in rows) and not any('있는.png' in r for r in rows), rows)
        page.locator('#lec-menu .menu-row', has_text='강조글 종류').locator('.menu-side').click()
        R.check('고치기 — [!NOTE] 로 저장', bool(R.wait(lambda: '> [!NOTE]\n> 메모' in text(), 10)), text()[:300])
        R.check("— '점검 3곳'", bool(R.wait(lambda: label() == '점검 3곳', 10)), label())
        page.locator('#lec-view h2', has_text='가').click()
        page.keyboard.press('Control+z')
        R.check('— Ctrl+Z 로 되돌림', bool(R.wait(lambda: '> [!NOTES]' in text() and label() == '점검 4곳', 10)), (label(), text()[:200]))
        warned = page.evaluate("[...document.querySelectorAll('#lec-toc .toc-list li.warn')].map((li) => li.textContent.trim())")
        R.check('목차에 점검할 곳이 든 절의 ●', warned == ['가', '다'], warned)
        R.check('머리 설정은 접혀 있다', page.evaluate("document.querySelector('#lec-view details.front-matter')?.open") is False)

        print('[설정 창의 글버릇]')
        page.keyboard.press('Control+,')
        page.wait_for_selector('#lec-settings:not([hidden])', timeout=5000)
        page.click('#lec-settings .set-nav button[data-set="view"]')
        box = page.locator('#lec-settings input[data-key="doc_check_style"]')
        R.check('설정 창에 두 체크 칸 — 문서 점검(켬)·글버릇(끔)', page.locator('#lec-settings input[data-key="doc_check"]').is_checked() and not box.is_checked())
        box.check()
        page.keyboard.press('Escape')
        R.check('글버릇을 켜면 줄 끝 공백 두 칸도 (점검 5곳)', bool(R.wait(lambda: label() == '점검 5곳', 10)), label())
        page.keyboard.press('Control+,')
        page.wait_for_selector('#lec-settings:not([hidden])', timeout=5000)
        page.click('#lec-settings .set-nav button[data-set="view"]')
        page.locator('#lec-settings input[data-key="doc_check_style"]').uncheck()
        page.keyboard.press('Escape')
        R.check('— 끄면 4곳', bool(R.wait(lambda: label() == '점검 4곳', 10)), label())

        print('[한 줄 편집 (D189)]')
        page.locator('#lec-view p', has_text='인공지능').click(position={'x': 30, 'y': 8})
        page.keyboard.press('Enter')
        R.wait(lambda: page.evaluate(CARET), 5)
        c = page.evaluate(CARET)
        n = len(c['starts']) if c else 0
        R.check('긴 문단이 창에서 네 줄 넘게 꺾인다 (시험의 전제)', n >= 4, c)
        for _ in range(n - 2):
            page.keyboard.press('ArrowUp')
        page.keyboard.press('Home')
        page.wait_for_timeout(150)
        c = page.evaluate(CARET)
        R.check('둘째 화면 줄 맨 앞 (꺾인 자리)', bool(c) and c['offset'] == c['starts'][1], c)
        page.keyboard.press('ArrowUp')
        page.wait_for_timeout(300)
        c = page.evaluate(CARET)
        R.check('— 그 자리의 ↑ 는 칸 안에서 맨 윗줄로 (WebView2)', bool(c) and c['text'].startswith('인공지능') and c['offset'] < c['starts'][1], c)
        page.keyboard.press('Escape')
        page.locator('#lec-view li', has_text='둘').first.click()
        page.keyboard.press('Shift+Enter')
        R.wait(lambda: page.locator('#lec-view .lec-new-line .lec-line-edit').count() == 1, 5)
        page.keyboard.press('Tab')
        page.wait_for_timeout(200)
        mark = page.evaluate("(() => { const li = document.querySelector('#lec-view .lec-new-line'); return li ? getComputedStyle(li).listStyleType : null; })()")
        R.check('빈 새 항목의 Tab — 글머리표가 바로 ○ (circle)', mark == 'circle', mark)
        page.keyboard.press('Escape')
        page.wait_for_timeout(300)
        R.check('— 그만두면 남는 것이 없다', page.evaluate("document.querySelectorAll('#lec-view li > ul:empty, #lec-view .lec-new-line').length") == 0)

        print('[끌어 고른 여러 줄 (D189)]')
        R.check('끌기 문서를 연다', R.open_doc(page, '끌기.md'))
        a = page.locator('#lec-view p', has_text='문단 둘').bounding_box()
        z = page.locator('#lec-view p', has_text='문단 셋').bounding_box()
        page.mouse.move(a['x'] + 20, a['y'] + a['height'] / 2)
        page.mouse.down()
        page.mouse.move(z['x'] + 30, z['y'] + z['height'] / 2, steps=10)
        page.mouse.up()
        page.wait_for_timeout(300)
        page.keyboard.press('Delete')
        R.check('Delete 한 번에 끌어 고른 문단 둘·셋', bool(R.wait(lambda: text(proj / '끌기.md') == '# 끌기\n\n문단 하나\n\n문단 넷\n', 10)), text(proj / '끌기.md'))
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
