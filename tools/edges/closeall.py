"""열린 문서 모두 닫기 (D133): 문서 탭·∨ 목록·프로젝트 탭의 우클릭, 저장하지 않은 편집은 한 번만 묻고 그만두면 그대로,
Ctrl+Shift+T 로 되살리기, 뒤에 있는 프로젝트 탭, 다시 열어도 문서 탭이 돌아오지 않음"""
import json
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-closeall-'))
proj = base / 'proj'
other = base / 'other'
config = base / 'config'
(proj / 'docs').mkdir(parents=True)
other.mkdir()
NAMES = ['가', '나', '다', '라', '마']
for n in NAMES:
    (proj / 'docs' / f'{n}.md').write_text(f'# 문서 {n}\n\n본문 {n}\n', encoding='utf-8')
(proj / 'src.py').write_text('x = 1\n', encoding='utf-8')
(other / '다른.md').write_text('# 다른 프로젝트\n\n글\n', encoding='utf-8')
(other / '둘째.md').write_text('# 둘째\n\n글\n', encoding='utf-8')
ORIGINAL = (proj / 'docs' / '나.md').read_bytes()

TABS = "() => [...document.querySelectorAll('#lec-doctab-list .doc-tab')].map((x) => x.dataset.path)"
OPEN = "([p, type]) => import('/static/js/store.js').then((m) => m.emit('open', { type, path: p, newTab: true }))"


def tabs(page):
    return page.evaluate(TABS)


def menu_at(page, selector, button='right', esc=True):
    if esc:   # 편집기에서 Esc 는 편집기를 닫는다 (기본 방식) — 편집 중에는 누르지 않는다
        page.keyboard.press('Escape')
    page.click(selector, button=button)
    page.wait_for_selector('#lec-menu:not([hidden])', timeout=5000)
    return page.evaluate("() => [...document.querySelectorAll('#lec-menu button')].map((b) => b.textContent.trim())")


def pick(page, label):
    page.click(f'#lec-menu button:has-text("{label}")')


server, url, port = serve(proj, config)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1400, 'height': 900})
        dialogs = []
        answer = {'accept': False}

        def on_dialog(d):
            dialogs.append(d.message)
            d.accept() if answer['accept'] else d.dismiss()
        page.on('dialog', on_dialog)
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)

        print('[문서 탭 다섯과 코드 하나]')
        for n in NAMES:
            page.evaluate(OPEN, [f'docs/{n}.md', 'doc'])
            until(page, f"() => document.querySelector('#lec-view h1')?.textContent === '문서 {n}'")
        page.evaluate(OPEN, ['src.py', 'code'])
        expect(page, '탭 여섯', f'() => ({TABS})().length === 6', lambda: tabs(page))
        page.click('#lec-doctab-list .doc-tab >> nth=1')   # '나' 를 고른다
        until(page, "() => document.querySelector('#lec-view h1')?.textContent === '문서 나'")

        items = menu_at(page, '#lec-doctab-list .doc-tab >> nth=3')
        check("문서 탭 우클릭에 '열린 문서 모두 닫기' ('다른 문서 탭 모두 닫기' 아래)",
              '열린 문서 모두 닫기' in items and items.index('열린 문서 모두 닫기') == items.index('다른 문서 탭 모두 닫기') + 1, items)
        items = menu_at(page, '#lec-doctab-all', button='left')
        check('∨ 목록에도', '열린 문서 모두 닫기' in items, items)
        page.keyboard.press('Escape')

        print('[저장하지 않은 편집 — 한 번만 묻고, 그만두면 그대로]')
        page.keyboard.press('Control+e')
        page.wait_for_selector('.CodeMirror', timeout=15000)
        page.click('.CodeMirror-code')
        page.keyboard.press('Control+End')
        page.keyboard.type(' 고친 글')
        expect(page, '편집 중 표시 ●', "() => !!document.querySelector('#lec-doctab-list .doc-tab.active .dirty')")
        menu_at(page, '#lec-doctab-list .doc-tab >> nth=4', esc=False)
        answer['accept'] = False
        pick(page, '열린 문서 모두 닫기')
        page.wait_for_timeout(500)
        check('한 번만 묻는다', len(dialogs) == 1 and '나.md' in dialogs[0], dialogs)
        check('그만두면 아무것도 닫지 않는다', len(tabs(page)) == 6, tabs(page))
        check('편집기와 고친 글이 그대로', page.evaluate("() => !!document.querySelector('.CodeMirror') && document.querySelector('.CodeMirror').CodeMirror.getValue().includes('고친 글')"))

        answer['accept'] = True
        menu_at(page, '#lec-tablist .lec-tab.active', esc=False)
        pick(page, '열린 문서 모두 닫기')
        expect(page, '프로젝트 탭 우클릭으로 닫으면 폴더 개요 하나', f"() => {{ const t = ({TABS})(); return t.length === 1 && t[0] === ''; }}", lambda: tabs(page))
        check('다시 한 번만 물었다', len(dialogs) == 2, dialogs)
        check('편집기가 닫혔다', page.evaluate("() => !document.querySelector('.CodeMirror')"))
        check('파일은 저장하지 않았다', (proj / 'docs' / '나.md').read_bytes() == ORIGINAL)
        check('폴더 개요가 보인다', page.evaluate("() => !!document.querySelector('#lec-view.overview, #lec-view .overview, .lec-overview') || document.querySelector('#lec-view')?.classList.contains('overview')"))

        print('[되살리기 — Ctrl+Shift+T]')
        page.click('#lec-view')
        page.keyboard.press('Control+Shift+T')
        expect(page, '보던 문서(나)가 먼저 돌아온다', "() => document.querySelector('#lec-view h1')?.textContent === '문서 나'", lambda: tabs(page))
        check('폴더 개요 탭을 남기지 않고 그 자리에', tabs(page) == ['docs/나.md'], tabs(page))
        page.keyboard.press('Control+Shift+T')
        expect(page, '그다음은 그 앞에 닫은 것 (코드) — 새 탭으로', f"() => JSON.stringify(({TABS})()) === JSON.stringify(['docs/나.md', 'src.py'])", lambda: tabs(page))

        print('[폴더 개요뿐이면 메뉴에 없다]')
        menu_at(page, '#lec-tablist .lec-tab.active')
        pick(page, '열린 문서 모두 닫기')
        expect(page, '다시 닫힘', f"() => ({TABS})().length === 1")
        items = menu_at(page, '#lec-tablist .lec-tab.active')
        check('프로젝트 탭 메뉴에 없음', '열린 문서 모두 닫기' not in items, items)
        items = menu_at(page, '#lec-doctab-list .doc-tab')
        check('문서 탭 메뉴에도 없음', '열린 문서 모두 닫기' not in items, items)
        page.keyboard.press('Escape')

        print('[뒤에 있는 프로젝트 탭]')
        for n in ('가', '다'):
            page.evaluate(OPEN, [f'docs/{n}.md', 'doc'])
            until(page, f"() => document.querySelector('#lec-view h1')?.textContent === '문서 {n}'")
        expect(page, '첫 프로젝트에 문서 탭 둘 (폴더 개요 자리에 첫 문서)', f'() => ({TABS})().length === 2', lambda: tabs(page))
        page.evaluate("(p) => import('/static/js/api.js').then((m) => m.postJSON('/api/open', { path: p }))", str(other))
        expect(page, '둘째 프로젝트 탭', "() => document.querySelectorAll('#lec-tablist .lec-tab').length === 2", ms=15000)
        page.wait_for_timeout(1500)
        page.click('#lec-tablist .lec-tab >> nth=1')
        page.wait_for_timeout(800)
        page.evaluate(OPEN, ['다른.md', 'doc'])
        until(page, "() => document.querySelector('#lec-view h1')?.textContent === '다른 프로젝트'")
        page.evaluate(OPEN, ['둘째.md', 'doc'])
        until(page, "() => document.querySelector('#lec-view h1')?.textContent === '둘째'")
        expect(page, '둘째 프로젝트에 문서 탭 둘', f'() => ({TABS})().length === 2', lambda: tabs(page))
        mine = tabs(page)
        items = menu_at(page, '#lec-tablist .lec-tab >> nth=0')
        check('뒤에 있는 탭의 메뉴에도', '열린 문서 모두 닫기' in items, items)
        pick(page, '열린 문서 모두 닫기')
        expect(page, '그 프로젝트를 고르고 그 문서만 닫는다', f"() => {{ const t = ({TABS})(); return t.length === 1 && t[0] === ''; }}", lambda: tabs(page))
        check('첫 프로젝트 탭이 골라졌다', page.evaluate("() => document.querySelectorAll('#lec-tablist .lec-tab')[0].classList.contains('active')"))
        page.click('#lec-tablist .lec-tab >> nth=1')
        check('둘째 프로젝트의 문서 탭은 그대로', until(page, lambda: tabs(page) == mine), (tabs(page), mine))

        print('[다시 열면 — 닫은 문서 탭이 돌아오지 않는다]')
        page.click('#lec-tablist .lec-tab >> nth=0')
        page.wait_for_timeout(1500)   # 문서 탭 목록 저장 (position.js)
        page.reload()
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        page.wait_for_timeout(2000)
        page.click('#lec-tablist .lec-tab >> nth=0')
        page.wait_for_timeout(1000)
        check('첫 프로젝트는 폴더 개요 하나', tabs(page) == [''], tabs(page))
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
