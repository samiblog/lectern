"""사용설명서·예제 가이드를 따로 창에서가 기본 (D181 2판, 2026-11-19 사용자 — '설명서와 가이드는 독립창으로 뜨는 것을 기본으로, 수정 불가능하고'):
F1·명령 찾기·단축키 표의 '사용설명서' 는 곧바로 설명서 창, Shift+F1·예제 열기·설명서의 예제 링크는 예제 가이드 창 — 메인 창은 보던 프로젝트 그대로.
두 창은 보기만 (편집·한 줄 편집·새 문서 없음). 브라우저 개발 모드는 설정 ref_windows 가 on 일 때만 창 (앱 창은 기본)"""
import json
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-refwin-'))
proj = base / 'proj'
proj.mkdir()
(proj / '글.md').write_text('# 글\n\n본문입니다.\n', encoding='utf-8')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False, 'ref_windows': 'on'}), encoding='utf-8')
server, url, port = serve(proj, config)

OPEN = "() => !document.querySelector('#lec-help').hidden"
STORE = "import('/static/js/store.js')"

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 1300, 'height': 860})
        page = ctx.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        page.locator('#lec-tree .row.file[data-doc="글.md"]').click()
        page.wait_for_selector('#lec-view h1')
        toast = lambda pg: pg.text_content('#lec-toast') or ''  # noqa: E731

        print('[F1 — 곧바로 사용설명서 창]')
        page.locator('#lec-content').focus()
        with ctx.expect_page(timeout=15000) as info:
            page.keyboard.press('F1')
        help_win = info.value
        help_win.on('pageerror', lambda e: errors.append('설명서 창: ' + str(e)[:300]))
        help_win.wait_for_selector('#lec-help-toc a', timeout=20000)
        expect(help_win, 'F1 — 설명서가 따로 창에 (help=1)', lambda: help_win.evaluate(OPEN) and 'help=1' in help_win.url)
        check('— 메인 창에는 설명서를 덮지 않는다, 보던 문서 그대로', not page.evaluate(OPEN) and page.locator('#lec-view h1', has_text='글').count() == 1)
        check('— 설명서 창의 탭은 보기만', help_win.evaluate(f"{STORE}.then((m) => m.S.tab?.readonly === true)"))
        help_win.close()

        print('[단축키 표의 사용설명서·명령 찾기도 창]')
        page.locator('#lec-content').focus()
        page.keyboard.press('Control+/')
        page.wait_for_selector('#lec-keys:not([hidden])')
        with ctx.expect_page(timeout=15000) as info:
            page.click('#lec-keys-manual')
        w2 = info.value
        w2.wait_for_selector('#lec-help-toc a', timeout=20000)
        check("단축키 표의 '사용설명서' — 설명서 창, 단축키 표는 닫힌다", w2.evaluate(OPEN) and page.evaluate("document.querySelector('#lec-keys').hidden"))
        w2.close()

        print('[Shift+F1 — 예제 가이드 창]')
        page.locator('#lec-content').focus()
        with ctx.expect_page(timeout=20000) as info:
            page.keyboard.press('Shift+F1')
        guide = info.value
        guide.on('pageerror', lambda e: errors.append('가이드 창: ' + str(e)[:300]))
        guide.wait_for_selector('#lec-view h1', timeout=30000)
        check('Shift+F1 — 예제의 README 가 가이드 창에 (guide=1)', 'guide=1' in guide.url and 'README.md' in guide.url, guide.url)
        tabs = page.evaluate(f"{STORE}.then((m) => [m.S.tabs.length, m.S.tab?.name])")
        check('— 메인 창은 보던 프로젝트 그대로 (예제 탭은 뒤에)', tabs[0] == 2 and tabs[1] == 'proj', tabs)
        check('— 메인 창은 보던 문서 그대로', page.locator('#lec-view h1', has_text='글').count() == 1)
        expect(guide, '— 가이드 창은 예제를 둘러보게 트리를 보인다', lambda: guide.locator('#lec-sidebar').is_visible() and guide.locator('#lec-tree .row.file').count() > 3)

        print('[가이드 창은 보기만]')
        guide.locator('#lec-view p').first.click()
        guide.keyboard.press('Control+e')
        expect(guide, 'Ctrl+E — 편집 모드를 열지 않고 보기만이라고 알린다', lambda: '보기만' in toast(guide), lambda: toast(guide))
        check('— 편집기가 없다', guide.locator('.CodeMirror').count() == 0)
        guide.locator('#lec-view p').first.click()
        guide.keyboard.press('F2')
        guide.wait_for_timeout(400)
        check('F2 — 한 줄 편집 칸도 열지 않는다', guide.locator('#lec-view .lec-line-edit').count() == 0)
        guide.keyboard.press('Control+n')
        guide.wait_for_timeout(300)
        check('Ctrl+N — 만들기 창을 열지 않는다', guide.evaluate("document.querySelector('#lec-newdoc').hidden"))

        print('[설명서의 예제 링크 — 가이드 창으로]')
        page.locator('#lec-content').focus()
        with ctx.expect_page(timeout=15000) as info:
            page.keyboard.press('F1')
        help_win = info.value
        help_win.wait_for_selector('#lec-help-toc a', timeout=20000)
        # 지금 설명서에는 예제 링크가 없다 (예제를 새로 짜는 중 — D182). 예제로 가는 링크 하나를 넣어 길만 본다
        help_win.evaluate("""() => { const a = document.createElement('a'); a.href = '../../samples/guide/08-한-줄-편집.md'; a.id = 'probe-sample';
          a.textContent = '예제'; document.querySelector('#lec-help-view').prepend(a); document.querySelector('#lec-help-scroll').scrollTop = 0; }""")
        link = help_win.locator('#probe-sample')
        href = link.get_attribute('href') or ''
        with ctx.expect_page(timeout=20000) as info:
            link.click()
        guide2 = info.value
        guide2.wait_for_selector('#lec-view h1', timeout=30000)
        name = href.split('samples/')[-1]
        check(f'설명서 창의 예제 링크 — 메인 창을 거쳐 가이드 창에서 그 문서 ({name})', 'guide=1' in guide2.url, guide2.url)
        check('— 메인 창은 여전히 보던 프로젝트', page.evaluate(f"{STORE}.then((m) => m.S.tab?.name)") == 'proj')

        check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
