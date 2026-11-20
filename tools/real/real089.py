"""0.89.0 — 빌드본·설치본 실제 창(WebView2)에서: 읽는 화면의 Home·End·PageDown·Ctrl+↓·Ctrl+A·Enter·Tab,
끝 줄의 ↓ 는 멈추고 키를 알림, Ctrl+Enter·Shift+Enter 로 줄 더하기, Enter 는 저장하고 닫기, 초점은 문서 칸, 단축키 표.
  python real089.py --exe <Lectern.exe>"""
import json
import shutil
import subprocess
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

import realwin as R

base = Path(tempfile.mkdtemp(prefix='lec-real089-'))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'language': 'ko', 'work_alerts': False}), encoding='utf-8')
proj = base / '리서치'
proj.mkdir()
parts = ['# 보고서', '']
for s in range(1, 5):
    parts += [f'## {s}장', '']
    for i in range(1, 9):
        if s == 2 and i == 2:
            parts += ['참고: [다른 문서](b.md) 를 본다.', '']
        else:
            parts += [f'{s}장 {i}번째 문단.', '']
DOC = '\n'.join(parts)
LAST = len(parts) - 1
doc = proj / '보고서.md'
doc.write_text(DOC, encoding='utf-8')
(proj / 'b.md').write_text('# 다른 문서\n\n다른 글.\n', encoding='utf-8')


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
        page.wait_for_timeout(600)
        until = lambda fn, sec=8: R.wait(fn, sec)
        here = lambda: page.evaluate("() => import('/static/js/store.js').then(({ S }) => S.pane?.here?.line || 0)")
        lit = lambda: (page.text_content('#lec-st-lit') or '') if page.locator('#lec-st-lit:not([hidden])').count() else ''
        toast = lambda: page.text_content('#lec-toast') or ''
        clear_toast = lambda: page.evaluate("document.querySelector('#lec-toast').textContent = ''")
        cells = lambda: page.locator('#lec-view .lec-line-edit').count()
        focus_id = lambda: page.evaluate('document.activeElement?.id')
        line_of = lambda text: src().split('\n').index(text) + 1

        def at(text):
            page.keyboard.press('Escape')
            page.keyboard.press('Escape')
            page.locator('#lec-view p, #lec-view h2', has_text=text).first.click()
            page.wait_for_timeout(250)

        print('[읽는 화면의 키]')
        at('2장 4번째 문단.')
        page.keyboard.press('End')
        R.check('End — 끝 줄', until(lambda: here() == LAST), (here(), LAST))
        page.keyboard.press('Home')
        R.check('Home — 첫 줄', until(lambda: here() == 1), here())
        page.keyboard.press('PageDown')
        R.check('PageDown — 한 화면 아래로', until(lambda: here() > 8), here())
        at('1장 3번째 문단.')
        page.keyboard.press('Control+ArrowDown')
        R.check('Ctrl+↓ — 다음 제목', until(lambda: here() == line_of('## 2장')), here())
        page.keyboard.press('Alt+Enter')   # 0.92.1 부터 접기는 Alt+Enter (Enter 는 한 줄 편집 — D166)
        R.check('제목 줄의 Alt+Enter — 절 접기 (파일은 그대로)', until(lambda: page.evaluate("() => !!document.querySelector('#lec-view h2.lec-folded')")) and src() == DOC)
        page.keyboard.press('Alt+Enter')
        R.check('— 다시 Alt+Enter — 펴기', until(lambda: not page.evaluate("() => !!document.querySelector('#lec-view h2.lec-folded')")))
        page.keyboard.press('Tab')
        R.check('Tab — 다음 링크로', until(lambda: page.evaluate("document.activeElement?.textContent") == '다른 문서'), page.evaluate("document.activeElement?.textContent"))
        at('3장 1번째 문단.')
        page.keyboard.press('Control+a')
        R.check('Ctrl+A — 모든 줄', until(lambda: lit().startswith(f'고른 줄 1~{LAST}행')), lit())
        page.keyboard.press('Escape')

        print('[문서 끝 — 중간과 같은 키]')
        at('4장 8번째 문단.')
        clear_toast()
        page.keyboard.press('ArrowDown')
        R.check('끝 줄의 ↓ — 새 줄을 열지 않고 Shift+Enter 를 알림', until(lambda: 'Shift+Enter' in toast()) and cells() == 0 and here() == LAST, (toast(), cells(), here()))
        page.keyboard.press('Shift+Enter')   # 0.92 부터 아래에 새 줄은 Shift+Enter (D163)
        page.wait_for_selector('#lec-view .lec-line-edit')
        page.keyboard.type('덧붙인 글')
        page.keyboard.press('Shift+Enter')
        R.check('Shift+Enter — 저장하고 아래에 새 줄', until(lambda: src().endswith('4장 8번째 문단.\n\n덧붙인 글\n') and cells() == 1), (src()[-50:], cells()))
        page.keyboard.type('마지막 글')
        page.keyboard.press('Enter')
        R.check('Enter — 저장하고 닫기', until(lambda: src().endswith('덧붙인 글\n\n마지막 글\n') and cells() == 0), (src()[-50:], cells()))
        R.check('— 현재 줄은 방금 쓴 줄, 초점은 문서 칸', until(lambda: here() == line_of('마지막 글') and focus_id() == 'lec-content'), (here(), focus_id()))
        page.keyboard.press('F2')
        page.wait_for_selector('#lec-view .lec-line-edit')
        clear_toast()
        page.keyboard.press('ArrowDown')
        R.check('칸에서 끝 줄의 ↓ — 칸은 그대로, Shift+Enter 를 알림', until(lambda: 'Shift+Enter' in toast()) and cells() == 1, (toast(), cells()))
        page.keyboard.press('Escape')
        for _ in range(4):
            if src() == DOC:
                break
            page.keyboard.press('Control+z')
            page.wait_for_timeout(800)
        R.check('Ctrl+Z 로 처음 그대로', src() == DOC, src()[-60:])

        print('[단축키 표]')
        page.keyboard.press('Control+/')
        page.wait_for_selector('#lec-keys:not([hidden])')
        tabs = page.locator('#lec-keys-tabs button').all_inner_texts()
        R.check('첫 탭은 스무 가지', tabs[:1] == ['자주 쓰는 것'] and page.locator('#lec-keys-list tr:visible').count() == 20, tabs)
        page.keyboard.type('PageUp')
        page.wait_for_timeout(250)
        R.check('찾기 PageUp — 읽는 화면의 줄이 나온다', '한 화면 위' in page.inner_text('#lec-keys-list'), page.inner_text('#lec-keys-list')[:200])
        page.keyboard.press('Escape')
        R.check('Esc 로 닫힘', until(lambda: page.locator('#lec-keys').is_hidden(), 3))
        page.screenshot(path=str(R.HERE / 'real089.png'))
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
