"""Tab 이 문서 칸 밖으로 나가지 않는다 (D167): 터미널을 연 채 — 링크가 있는 md 문서(끝에서 첫 링크로, Shift+Tab 은 거꾸로),
링크가 없는 문서(초점 그대로), 코드 화면, 폴더 개요, html 문서(iframe 안에서 돈다), 찾기 막대에서 거듭 Tab. 칸 안의 Tab 은 그대로 칸의 것, 떠나는 것은 F6"""
import json
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-tabtrap-'))
proj = base / 'proj'
proj.mkdir(parents=True)
(proj / 'links.md').write_text('# 링크 문서\n\n첫 링크 [가](plain.md) 가 있다.\n\n둘째 [나](#링크-문서) 와 셋째 [다](plain.md).\n\n끝 문단.\n', encoding='utf-8')
(proj / 'plain.md').write_text('# 링크 없는 문서\n\n첫째 문단.\n\n둘째 문단.\n', encoding='utf-8')
(proj / 'page.html').write_text('<title>쪽</title><p><a href="#a">하나</a> <a href="#b">둘</a></p><p><button>단추</button></p>', encoding='utf-8')
(proj / 'tool.py').write_text('x = 1\ny = 2\n', encoding='utf-8')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)

WHERE = """() => { const a = document.activeElement;
  if (a?.closest('#lec-term')) return 'term';
  if (a?.closest('#lec-sidebar')) return 'side';
  if (a?.closest('#lec-toolbar, #lec-tabbar, #lec-doctabs, #lec-status')) return 'chrome';
  if (a?.tagName === 'IFRAME') return 'frame:' + (a.contentDocument.activeElement?.textContent || a.contentDocument.activeElement?.tagName);
  if (a?.closest('#lec-panes')) return 'doc:' + (a.textContent?.trim().slice(0, 6) || a.id || a.tagName);
  return a === document.body ? 'body' : (a?.id || a?.tagName || ''); }"""

try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(viewport={'width': 1400, 'height': 860}).new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')
        where = lambda: page.evaluate(WHERE)  # noqa: E731

        def open_doc(path, ready='#lec-view h1'):
            page.evaluate("(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: p.endsWith('.py') ? 'code' : 'doc', path: p }))", path)
            page.wait_for_selector(ready, timeout=8000)
            page.wait_for_timeout(400)

        def tabs(n, key='Tab'):
            seen = []
            for _ in range(n):
                page.keyboard.press(key)
                page.wait_for_timeout(120)
                seen.append(where())
            return seen

        page.keyboard.press('Control+`')   # 터미널을 열어 둔다 — Tab 이 거기로 가던 것
        page.wait_for_selector('#lec-term .term-box:not([hidden]) .xterm', timeout=15000)
        page.wait_for_timeout(800)

        print('[링크가 있는 md 문서]')
        open_doc('links.md')
        page.locator('#lec-view p', has_text='끝 문단').click()
        seen = tabs(7)
        check('Tab 일곱 번 — 늘 문서 안 (터미널·사이드바로 가지 않는다)', all(s.startswith('doc:') for s in seen), seen)
        check('— 마지막 링크 다음은 첫 링크로 돈다', [s for s in seen][:4] == ['doc:가', 'doc:나', 'doc:다', 'doc:가'], seen)
        seen = tabs(4, 'Shift+Tab')
        check('Shift+Tab — 거꾸로 돌고 문서 안', all(s.startswith('doc:') for s in seen) and seen[:2] == ['doc:다', 'doc:나'], seen)

        print('[링크가 없는 문서 · 코드 화면]')
        open_doc('plain.md')
        page.locator('#lec-view p', has_text='첫째').click()
        seen = tabs(4) + tabs(2, 'Shift+Tab')
        check('링크가 없으면 칸 안에서 — 문서 밖으로 나가지 않는다', all(s.startswith('doc:') for s in seen), seen)
        open_doc('tool.py', '#lec-view .cv-line')
        page.locator('#lec-view .cv-line').first.click()
        seen = tabs(5)
        check('코드 화면 — 머리줄 단추(편집·외부 편집기·전체 복사)를 돌고 문서 안', all(s.startswith('doc:') for s in seen) and 'doc:편집' in seen, seen)

        print('[폴더 개요]')
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open', { type: 'overview', path: '' }))")
        page.wait_for_selector('#lec-view.overview, #lec-view .overview', timeout=8000)
        page.wait_for_timeout(400)
        page.locator('#lec-content').focus()
        seen = tabs(12)
        check('폴더 개요 — 그 안의 단추를 돌고 밖으로 나가지 않는다', all(s.startswith('doc:') for s in seen) and len(set(seen)) > 2, seen)

        print('[html 문서]')
        open_doc('page.html', '#lec-view iframe')
        page.wait_for_timeout(600)
        page.frame_locator('#lec-view iframe').locator('p').first.click()
        seen = tabs(7)
        check('html 문서 — iframe 안에서 돌고 밖으로 나가지 않는다', all(s.startswith('frame:') for s in seen), seen)
        check('— 하나 → 둘 → 단추 → 하나', seen[:4] == ['frame:하나', 'frame:둘', 'frame:단추', 'frame:하나'], seen)

        print('[찾기 막대 · 칸 · F6]')
        open_doc('links.md')
        page.locator('#lec-view p', has_text='끝 문단').click()
        page.keyboard.press('Control+f')
        page.keyboard.type('링크')
        seen = tabs(12)
        check('찾기 막대에서 거듭 Tab — 막대와 문서 안만', all(s.startswith('doc:') or s in ('lec-find-input', 'INPUT') for s in seen), seen)
        page.keyboard.press('Escape')
        page.keyboard.press('Escape')
        page.locator('#lec-view p', has_text='끝 문단').click()
        page.keyboard.press('Enter')   # 한 줄 편집 (D166)
        page.wait_for_selector('#lec-view .lec-line-edit')
        page.keyboard.press('Tab')
        page.wait_for_timeout(200)
        check('칸 안의 Tab 은 칸의 것 — 초점은 칸에', page.evaluate("document.activeElement?.classList.contains('lec-line-edit')"))
        page.keyboard.press('Escape')
        page.wait_for_timeout(300)
        page.keyboard.press('F6')
        expect(page, '문서를 떠나는 것은 F6 — 터미널로', lambda: where() == 'term', where, ms=8000)
        check('화면 스크립트 오류 없음', not errors, errors[:3])
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
