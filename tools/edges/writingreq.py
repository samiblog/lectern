"""보고서 글쓰기의 요청 글 (D148): 문서 여백 우클릭의 '다듬기 점검 요청'·'내 문체 견본으로 보내기', 고른 줄의 '이 범위 다듬기 점검 요청',
설정 창의 '내 문체'. 요청 글이 안내 파일(review.md·voice.md)의 경로와 문서 위치를 담는지, Lectern 슬라이드·코드에는 무엇이 나오는지,
글쓰기 스타일 설치 요청이 '내 문체' 절을 옮기라고 하는지, 영어 화면. 앱은 요청 글만 터미널에 넣는다 (D51 — Enter 없이)"""
import json
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop

base = Path(tempfile.mkdtemp(prefix='lec-writingreq-'))
proj = base / 'proj'
config = base / 'config'
(proj / 'docs').mkdir(parents=True)
(proj / 'src').mkdir()
(proj / 'docs' / 'a.md').write_text('# 검토 보고서\n\n첫째 문단입니다. 결제를 받은 뒤 발주한다.\n\n둘째 문단입니다.\n', encoding='utf-8')
(proj / 'docs' / 'deck.md').write_text('---\nmarp: true\n---\n\n# 발표\n\n---\n\n## 둘째 장\n\n- 항목\n', encoding='utf-8')
(proj / 'src' / 'x.py').write_text('print(1)\n', encoding='utf-8')

OPEN = "(path) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path }))"
# 터미널에 넣는 글을 함께 받아 둔다 (터미널도 그대로 받는다 — Enter 없이)
HOOK = "() => import('/static/js/store.js').then((m) => { window.__pasted = []; m.on('term-paste', (d) => window.__pasted.push(typeof d === 'string' ? d : d.text)); })"
PASTED = '() => window.__pasted.slice()'


def menu(page, keep=False):
    """문서 여백을 우클릭한 메뉴의 항목들. keep 이면 메뉴를 닫지 않는다"""
    page.keyboard.press('Escape')
    box = page.evaluate("""() => { const v = document.querySelector('#lec-view'); const r = v.getBoundingClientRect();
      const left = Math.min(...[...v.children].map((c) => c.getBoundingClientRect().left));
      const c = document.querySelector('#lec-content').getBoundingClientRect();
      return { x: Math.max(r.left + 4, left - 14), y: c.top + Math.min(200, c.height / 3) }; }""")
    page.mouse.click(box['x'], box['y'], button='right')
    page.wait_for_selector('#lec-menu:not([hidden])', timeout=5000)
    items = page.evaluate("() => [...document.querySelectorAll('#lec-menu button')].map((b) => b.querySelector('span')?.textContent.trim() || b.textContent.trim())")
    if not keep:
        page.keyboard.press('Escape')
    return items


def lit_menu(page, keep=False):
    """첫 문단을 하이라이트하고 우클릭한 메뉴 (D139 — 고른 줄의 선택 상자)"""
    page.keyboard.press('Escape')
    page.locator('#lec-view p').nth(0).click()
    page.keyboard.press('Shift+Enter')
    box = page.locator('#lec-view p').nth(0).bounding_box()
    page.mouse.click(box['x'] + 20, box['y'] + box['height'] / 2, button='right')
    page.wait_for_selector('#lec-menu:not([hidden])')
    items = page.evaluate("() => [...document.querySelectorAll('#lec-menu button')].map((b) => b.querySelector('span')?.textContent || b.textContent)")
    if not keep:
        page.keyboard.press('Escape')
        page.keyboard.press('Escape')
    return items


def click_item(page, label):
    page.click(f'#lec-menu button:has-text("{label}")')
    page.wait_for_timeout(300)


def open_doc(page, path, sel='#lec-view h1, #lec-view h2, #lec-view .cv-line'):
    page.evaluate(OPEN, path)
    page.wait_for_selector(sel, timeout=20000)
    page.wait_for_timeout(300)


def open_settings(page):
    if page.evaluate("() => document.querySelector('#lec-settings').hidden"):
        page.keyboard.press('Control+,')
        page.wait_for_selector('#lec-settings:not([hidden])')


server, url, port = serve(proj, config)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 1400, 'height': 900})
        ctx.grant_permissions(['clipboard-read', 'clipboard-write'], origin=url.rstrip('/'))
        page = ctx.new_page()
        page.on('dialog', lambda d: d.accept())
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        page.evaluate(HOOK)
        guides = page.evaluate("() => import('/static/js/store.js').then((m) => [m.S.reviewGuide, m.S.voiceGuide])")
        check('안내 파일의 경로', guides[0].endswith('review.md') and guides[1].endswith('voice.md') and all(Path(g).is_file() for g in guides), guides)

        print('[md 문서의 여백 메뉴]')
        open_doc(page, 'docs/a.md')
        items = menu(page)
        check("'다듬기 점검 요청'·'내 문체 견본으로 보내기'", '다듬기 점검 요청' in items and '내 문체 견본으로 보내기' in items, items)
        pdf = next(i for i, x in enumerate(items) if 'PDF로 저장' in x)   # 브라우저 개발 모드는 '인쇄 / PDF로 저장…'
        check('편집 항목 뒤, PDF 항목 앞', items.index('이 문서 편집') < items.index('다듬기 점검 요청') < pdf, items)
        menu(page, keep=True)
        click_item(page, '다듬기 점검 요청')
        got = page.evaluate(PASTED)
        check('다듬기 요청 글: 안내 경로와 문서', len(got) == 1 and guides[0] in got[0] and '@docs/a.md' in got[0] and '표로 먼저' in got[0], got)
        menu(page, keep=True)
        click_item(page, '내 문체 견본으로 보내기')
        got = page.evaluate(PASTED)
        check('내 문체 요청 글: 안내 경로와 견본', len(got) == 2 and guides[1] in got[1] and '@docs/a.md' in got[1] and '먼저 보여 줘' in got[1], got[-1:])
        check('요청 글에 줄바꿈이 없다 (Enter 로 보내지지 않게)', all('\n' not in g and '\r' not in g for g in got), got)

        print('[고른 줄의 메뉴]')
        items = lit_menu(page, keep=True)
        check("'이 범위 다듬기 점검 요청'", '이 범위 다듬기 점검 요청' in items, items)
        click_item(page, '이 범위 다듬기 점검 요청')
        page.keyboard.press('Escape')
        got = page.evaluate(PASTED)
        check('범위 요청 글: @경로 와 행', len(got) == 3 and '@docs/a.md 3행' in got[2] and guides[0] in got[2], got[-1:])

        print('[Lectern 슬라이드·코드]')
        open_doc(page, 'docs/deck.md')
        items = menu(page)
        check('슬라이드는 다듬기만 (문체의 견본은 글)', '다듬기 점검 요청' in items and '내 문체 견본으로 보내기' not in items, items)
        page.evaluate("(p) => import('/static/js/store.js').then(({ emit }) => emit('open', { type: 'code', path: p }))", 'src/x.py')
        page.wait_for_selector('#lec-view .cv-line', timeout=20000)
        page.locator('#lec-view .cv-line').first.click(button='right')
        page.wait_for_selector('#lec-menu:not([hidden])')
        items = page.evaluate("() => [...document.querySelectorAll('#lec-menu button')].map((b) => b.textContent.trim())")
        page.keyboard.press('Escape')
        check('코드에는 없다', not any('다듬기' in x or '내 문체' in x for x in items), items)

        print('[설정 창의 내 문체]')
        open_doc(page, 'docs/a.md')
        open_settings(page)
        check('내 문체 칸과 두 버튼', page.is_visible('#lec-voice-prompt') and page.is_visible('#lec-voice-term'))
        check('설명', '내 문체 견본으로 보내기' in page.evaluate("() => document.querySelector('#lec-voice-desc').textContent"))
        page.click('#lec-voice-prompt')
        page.wait_for_timeout(250)
        clip = page.evaluate('() => navigator.clipboard.readText()')
        check('복사한 요청 글: 안내 경로, 끝은 견본을 이어 적을 자리', guides[1] in clip and clip.endswith('견본: '), clip)
        page.click('#lec-wstyle-prompt')
        page.wait_for_timeout(250)
        clip = page.evaluate('() => navigator.clipboard.readText()')
        check("글쓰기 스타일 설치 요청: '## 내 문체' 절은 새 파일로 옮긴다", "'## 내 문체'" in clip and '옮겨' in clip, clip[-250:])
        page.click('#lec-voice-term')
        expect(page, '터미널 버튼: 설정 창이 닫히고 같은 글을 터미널에', lambda: page.evaluate("() => document.querySelector('#lec-settings').hidden") and page.evaluate(PASTED)[-1].endswith('견본: '),
               lambda: page.evaluate(PASTED)[-1:])
        b.close()

    print('[영어 화면]')
    server.terminate()
    server.wait(10)
    cfg = json.loads((config / 'config.json').read_text(encoding='utf-8')) if (config / 'config.json').exists() else {}
    cfg.update(language='en')
    config.mkdir(exist_ok=True)
    (config / 'config.json').write_text(json.dumps(cfg), encoding='utf-8')
    server, url, port = serve(proj, config)
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1400, 'height': 900})
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        page.evaluate(HOOK)
        open_doc(page, 'docs/a.md')
        items = menu(page, keep=True)
        check('Ask for a polish check · Send as a style sample', 'Ask for a polish check' in items and 'Send as a style sample' in items, items)
        click_item(page, 'Ask for a polish check')
        got = page.evaluate(PASTED)
        check('영어 요청 글과 영어 안내', len(got) == 1 and got[0].startswith("Read Lectern's polish check guide") and 'review.en.md' in got[0], got)
        page.locator('#lec-view h1').click()   # 붙여 넣은 터미널에서 문서로 (Ctrl+, 는 터미널이 받는다)
        open_settings(page)
        check('My style', page.evaluate("() => document.querySelector('#lec-voice-title').textContent") == 'My style')
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
