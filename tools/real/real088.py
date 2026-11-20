"""0.88.0 — 빌드본·설치본 실제 창(WebView2)에서: 바꾸기 창(.), 번호 잇기, 강조글 안, 알림 없는 받아 적기, 단축키 표의 탭과 찾기.
  python real088.py --exe <Lectern.exe>"""
import json
import shutil
import subprocess
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

import realwin as R

base = Path(tempfile.mkdtemp(prefix='lec-real088-'))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'language': 'ko', 'work_alerts': False}), encoding='utf-8')
proj = base / '리서치'
proj.mkdir()
DOC = ('# 보고서\n\n## 요약\n\n1. 가격\n2. 수요\n3. 재고\n\n> [!NOTE]\n> 참고 첫 줄\n> 참고 둘째 줄\n\n- 구리: 9,400달러\n- 니켈: 16,500달러\n\n## 끝\n\n끝 문단.\n')
doc = proj / '보고서.md'
doc.write_text(DOC, encoding='utf-8')


def src():
    for _ in range(40):
        try:
            return doc.read_text(encoding='utf-8')
        except OSError:
            time.sleep(0.05)
    return ''


proc, cdp = R.launch(proj, config)
try:
    with sync_playwright() as p:
        b = None
        for _ in range(120):
            try:
                b = p.chromium.connect_over_cdp(f'http://127.0.0.1:{cdp}')
                break
            except Exception:
                time.sleep(0.5)
        page = R.wait(lambda: R.app_page(b), 60)
        page.wait_for_selector('#lec-tree .row.file', timeout=40000)
        page.wait_for_timeout(1500)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        version = page.evaluate("() => document.querySelector('meta[name=lec-version]')?.content || ''")
        R.check(f'판 — {version}', version == R.VERSION, version)
        R.open_doc(page, '보고서.md')
        page.evaluate("""() => { window.__toasts = []; const t = document.querySelector('#lec-toast');
          new MutationObserver(() => { if (!t.hidden && t.textContent) window.__toasts.push(t.textContent); }).observe(t, { childList: true, characterData: true, subtree: true, attributes: true }); }""")
        toasts = lambda: page.evaluate('() => window.__toasts.slice()')
        until = lambda fn, sec=8: R.wait(fn, sec)
        line_of = lambda text: src().split('\n').index(text) + 1

        def go(n):
            page.locator('#lec-view h1').first.click()
            page.evaluate("(n) => import('/static/js/spotlight.js').then((m) => m.followLine(n))", n)
            page.wait_for_timeout(250)

        def change(n, name):
            go(n)
            page.keyboard.press('.')
            page.wait_for_selector('#lec-put:not([hidden])', timeout=5000)
            page.locator('#lec-put-list li[role=option]', has_text=name).first.click()

        def back():
            page.keyboard.press('Escape')
            for _ in range(6):
                if src() == DOC:
                    break
                page.keyboard.press('Control+z')
                page.wait_for_timeout(800)
            R.check('— Ctrl+Z 로 처음 그대로', src() == DOC, src()[:160])

        print('[바꾸기 창]')
        go(line_of('2. 수요'))
        page.keyboard.press('.')
        page.wait_for_selector('#lec-put:not([hidden])', timeout=5000)
        heads = page.locator('#lec-put-list.board > li.col > .head').all_inner_texts()
        sel = page.locator('#lec-put-list li.sel').inner_text()
        R.check('. — 판, 맨 앞은 이 줄에 맞는 것, 지금 종류(번호 목록)에서 시작', heads[:1] == ['이 줄에 맞는 것'] and sel.startswith('번호 목록') and '지금' in sel, (heads, sel))
        page.locator('#lec-put-list li[role=option]', has_text='문단').first.click()
        R.check('번호 항목을 문단으로 — 뒤 번호를 잇는다', until(lambda: '1. 가격\n\n수요\n\n2. 재고' in src()), src()[:120])
        R.check('— 알림은 번호 다시 매김 하나', until(lambda: toasts() == ['뒤 항목 1개의 번호를 다시 매겼습니다']), toasts())
        back()
        change(line_of('- 구리: 9,400달러'), '목록을 표로')
        R.check('목록을 표로', until(lambda: '| 항목 | 값 |\n| --- | --- |\n| 구리 | 9,400달러 |' in src()), src()[100:260])
        back()
        go(line_of('> 참고 둘째 줄'))
        page.keyboard.press('l')
        page.wait_for_timeout(200)
        page.keyboard.press('l')
        R.check('강조글 안의 줄을 목록으로 — 갈리지 않음', until(lambda: '> [!NOTE]\n> 참고 첫 줄\n>\n> - 참고 둘째 줄' in src()), src()[60:180])
        back()

        print('[받아 적기]')
        page.evaluate('() => { window.__toasts = []; }')
        go(line_of('3. 재고'))
        page.keyboard.press('Shift+Enter')   # 0.92 부터 아래에 새 줄은 Shift+Enter (Ctrl+Enter 는 줄 선택 — D163)
        page.wait_for_selector('#lec-view .lec-line-edit')
        page.keyboard.type('공급')
        page.keyboard.press('Enter')
        R.check('번호 항목 아래 새 줄 — 4.', until(lambda: '3. 재고\n4. 공급\n' in src()), src()[:140])
        page.wait_for_timeout(400)
        page.keyboard.press('Escape')
        go(line_of('## 끝'))
        page.keyboard.press('Shift+Enter')   # 0.92 부터 (D163)
        page.wait_for_selector('#lec-view .lec-line-edit')
        page.keyboard.type('끝 앞 문단')
        page.keyboard.press('Enter')
        R.check('제목 아래 새 줄 — 문단', until(lambda: '## 끝\n\n끝 앞 문단\n\n끝 문단.' in src()), src()[-60:])
        page.wait_for_timeout(400)
        page.keyboard.press('Escape')
        R.check('글을 쓰는 동안 알림 0번', toasts() == [], toasts())
        back()

        print('[단축키 표]')
        page.locator('#lec-view p').first.click()
        page.keyboard.press('Control+/')
        page.wait_for_selector('#lec-keys:not([hidden])')
        tabs = page.locator('#lec-keys-tabs button').all_inner_texts()
        rows = page.locator('#lec-keys-list tr:visible').count()
        R.check('탭 여덟, 첫 탭은 스무 가지', len(tabs) == 8 and tabs[0] == '자주 쓰는 것' and rows == 20, (tabs, rows))
        page.keyboard.type('표')
        page.wait_for_timeout(200)
        R.check('찾기 칸에 표 — 모든 탭에서', page.locator('#lec-keys-tabs button.on').count() == 0 and page.locator('#lec-keys-list tr:visible').count() >= 2)
        page.keyboard.press('Escape')
        R.check('Esc 로 닫힘', until(lambda: page.locator('#lec-keys').is_hidden(), 3))
        page.screenshot(path=str(R.HERE / 'real088.png'))
        R.check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:
    traceback.print_exc()
    R.fails.append('예외')
finally:
    subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], capture_output=True)
    time.sleep(1)
    shutil.rmtree(base, ignore_errors=True)
print(f'\n{R.count}개 중 실패 {len(R.fails)}개', R.fails)
