"""사용설명서를 새 창에서 (D181, 2026-11-19 사용자 요청 — '탭을 오른쪽 마우스로 눌러서 새창에서 열기'):
설명서의 머리줄·문서 트리 우클릭 '새 창에서 열기'(설명서를 보는 중의 Ctrl+Shift+N, 명령 찾기도) — 독립창이 설명서를 그 문서에서 연다, 메인 창의 설명서는 걷힌다.
그 창에서 우클릭은 '사용설명서 창 닫기' 하나, F1 은 창을 닫는다, 예제 링크는 메인 창이 예제 프로젝트를 열어 그 문서로"""
import json
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-helpwin-'))
proj = base / 'proj'
proj.mkdir()
(proj / '글.md').write_text('# 글\n\n본문\n', encoding='utf-8')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)

MENU = "() => [...document.querySelectorAll('#lec-menu:not([hidden]) button[data-i] .label, #lec-menu:not([hidden]) button[data-i]')].map((b) => b.textContent.trim()).filter(Boolean)"
CUR = "() => document.querySelector('#lec-help-toc li.doc.current a')?.textContent.trim() || ''"   # 지금 문서 (D182 — 설명서는 문서 트리)
OPEN = "() => !document.querySelector('#lec-help').hidden"

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 1300, 'height': 860})
        page = ctx.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        menu = lambda pg: pg.locator('#lec-menu:not([hidden]) button[data-i]')  # noqa: E731

        print('[머리줄 우클릭]')
        page.keyboard.press('F1')
        page.wait_for_selector('#lec-help-toc a', timeout=10000)
        page.click('#lec-help .help-title span', button='right')
        page.wait_for_selector('#lec-menu:not([hidden])')
        labels = [x.strip() for x in menu(page).all_inner_texts()]
        check("설명서 머리줄 우클릭 — '새 창에서 열기'·'사용설명서 닫기'", any('새 창에서 열기' in x for x in labels) and any('사용설명서 닫기' in x for x in labels), labels)
        page.keyboard.press('Escape')

        print('[문서 트리 우클릭 — 그 문서에서 새 창]')
        toc = page.locator('#lec-help-toc li.doc a')
        chapter = toc.nth(min(8, toc.count() - 1))
        name = chapter.inner_text().strip()
        chapter.click(button='right')
        page.wait_for_selector('#lec-menu:not([hidden])')
        with ctx.expect_page(timeout=15000) as info:
            menu(page).filter(has_text='새 창에서 열기').first.click()
        win = info.value
        win.on('pageerror', lambda e: errors.append('창: ' + str(e)[:300]))
        win.wait_for_selector('#lec-help-toc a', timeout=20000)
        expect(win, '새 창이 설명서를 덮고 연다 (사용설명서 창)', lambda: win.evaluate(OPEN) and win.evaluate("document.documentElement.classList.contains('lec-help-window')"))
        expect(win, f"— 우클릭한 문서에서 ('{name}')", lambda: win.evaluate(CUR) == name, lambda: win.evaluate(CUR))
        expect(win, '— 창 제목은 사용설명서', lambda: win.title().startswith('사용설명서'), lambda: win.title())
        expect(page, '메인 창의 설명서는 걷힌다', lambda: not page.evaluate(OPEN))
        check('주소는 지금 프로젝트의 독립창 (help=1)', 'solo=' in win.url and 'help=1' in win.url, win.url)

        print('[사용설명서 창에서]')
        win.click('#lec-help .help-title span', button='right')
        win.wait_for_selector('#lec-menu:not([hidden])')
        labels = [x.strip() for x in menu(win).all_inner_texts()]
        check("창 안의 우클릭은 '사용설명서 창 닫기' 하나 (새 창을 또 열지 않는다)", len(labels) == 1 and '사용설명서 창 닫기' in labels[0], labels)
        win.keyboard.press('Escape')
        # 지금 설명서에는 예제 링크가 없다 (예제를 새로 짜는 중 — D182). 예제로 가는 링크 하나를 넣어 길만 본다
        win.evaluate("""() => { const a = document.createElement('a'); a.href = '../../samples/guide/08-한-줄-편집.md'; a.id = 'probe-sample';
          a.textContent = '예제'; document.querySelector('#lec-help-view').prepend(a); }""")
        sample = win.locator('#probe-sample')
        if sample.count():
            win.locator('#lec-help-scroll').evaluate('(el) => { el.scrollTop = 0; }')
            sample.click()
            expect(win, '예제 링크 — 메인 창에 맡긴다고 알린다', lambda: '메인 창에서 예제를 엽니다' in (win.text_content('#lec-toast') or ''), lambda: win.text_content('#lec-toast'))
            expect(page, '— 메인 창이 예제 프로젝트 탭을 연다', lambda: page.evaluate("import('/static/js/store.js').then((m) => m.S.tabs.length)") >= 2,
                   lambda: page.evaluate("import('/static/js/store.js').then((m) => m.S.tabs.map((x) => x.name))"), ms=15000)
            check('— 사용설명서 창은 그대로 설명서', win.evaluate(OPEN))
        else:
            check('설명서에 예제 링크가 있다', False, '예제 링크 없음')
        win.locator('#lec-help-scroll').focus()
        try:
            win.keyboard.press('F1')
        except Exception:   # 키를 떼기 전에 창이 닫히면 Playwright 가 '닫힌 창'이라고 한다 — 닫힌 것이 맞는 동작
            pass
        check('창에서 F1 — 사용설명서 창을 닫는다', until(page, lambda: win.is_closed(), 5000))   # 닫히는 창에서는 기다리지 않는다

        print('[Ctrl+Shift+N·명령 찾기]')
        # 메인 창이 예제 문서로 다 넘어간 뒤에 — 넘어가는 화면이 설명서를 걷으면 Ctrl+Shift+N 은 그 문서 탭을 옮긴다
        until(page, lambda: page.evaluate("import('/static/js/store.js').then((m) => m.S.view?.type === 'doc' && !m.S.pane?.pending)"), 10000)
        page.wait_for_timeout(300)
        page.locator('#lec-content').focus()
        page.keyboard.press('F1')
        page.wait_for_selector('#lec-help:not([hidden]) #lec-help-toc a', timeout=10000)
        with ctx.expect_page(timeout=15000) as info:
            page.keyboard.press('Control+Shift+N')
        win2 = info.value
        win2.wait_for_selector('#lec-help-toc a', timeout=20000)
        expect(win2, '설명서를 보는 중의 Ctrl+Shift+N — 설명서가 새 창으로', lambda: win2.evaluate(OPEN))
        win2.close()
        page.locator('#lec-content').focus()
        page.keyboard.press('Control+Shift+P')
        page.keyboard.type('사용설명서를 새 창')
        page.wait_for_timeout(200)
        with ctx.expect_page(timeout=15000) as info:
            page.keyboard.press('Enter')
        win3 = info.value
        win3.wait_for_selector('#lec-help-toc a', timeout=20000)
        expect(win3, '명령 찾기 — 설명서 창이 맨 앞 장에서', lambda: win3.evaluate(OPEN) and win3.evaluate("document.querySelector('#lec-help-scroll').scrollTop") < 40)
        win3.close()

        check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
