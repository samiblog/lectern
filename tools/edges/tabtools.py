"""탭 막대의 단추들 (D193): 개요 · 바뀜 N · 업무 카드 │ 넣기 · 편집 · 목차 · 스타일 · 내보내기 │ AI 요청 · 메모 · 터미널.
이름은 적지 않고 아이콘만 — 마우스를 올리면 단추 아래에 이름과 설명이 뜬다.
사람이 쓰는 차례로 — 문서를 읽다가 개요로, Claude 가 문서 셋을 고친 뒤 '바뀜'을 거듭 눌러 다 보기, 업무 카드가 없을 때와 생긴 뒤,
문서·슬라이드·폴더 개요에서의 내보내기, md 문서 스타일, AI 요청(터미널에 넣는 글), 설명 풍선, 좁은 창, 영어 화면"""
import json
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-tabtools-'))
proj = base / 'proj'
(proj / 'sub').mkdir(parents=True)


def put(rel, text):
    (proj / rel).write_text(text, encoding='utf-8', newline='\n')


put('보고서.md', '# 보고서\n\n## 요약\n\n첫 문단입니다.\n\n## 본론\n\n둘째 문단입니다.\n\n## 결론\n\n셋째 문단입니다.\n')
put('조사.md', '# 조사\n\n조사한 내용입니다.\n')
put('sub/분석.md', '# 분석\n\n분석한 내용입니다.\n')
put('발표.md', '---\nmarp: true\n---\n\n# 발표\n\n---\n\n## 둘째 장\n\n- 하나\n')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)

OPEN = "(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: p }))"
ORDER = ['lec-btn-overview', 'lec-btn-changed', 'lec-btn-card', 'lec-btn-put', 'lec-btn-edit', 'lec-btn-toc', 'lec-btn-style', 'lec-btn-export',
         'lec-btn-ai', 'lec-btn-notes', 'lec-btn-term']
TIP = "() => { const b = document.querySelector('#lec-tabtip'); return b && !b.hidden ? { name: b.querySelector('b').textContent, more: b.querySelector('span').hidden ? '' : b.querySelector('span').textContent, top: b.getBoundingClientRect().top, left: b.getBoundingClientRect().left, right: b.getBoundingClientRect().right } : null; }"
PASTED = "() => window.__pasted || []"
VIEW = "() => import('/static/js/store.js').then((m) => ({ type: m.S.view?.type, path: m.S.view?.path || '' }))"
COUNT = "() => { const n = document.querySelector('#lec-btn-changed-n'); return n.hidden ? 0 : Number(n.textContent); }"
TOAST = "() => { const e = document.querySelector('#lec-toast'); return e && !e.hidden ? e.textContent : ''; }"
MENU = "() => { const m = document.querySelector('#lec-menu'); return m && !m.hidden ? [...m.querySelectorAll('button[data-i]')].map((e) => e.textContent.trim()) : null; }"
SHOWN = "(sel) => { const e = document.querySelector(sel); return !!e && getComputedStyle(e).display !== 'none'; }"


def view(page):
    return page.evaluate(VIEW)


def open_doc(page, path, heading):
    page.evaluate(OPEN, path)
    page.wait_for_selector(f'#lec-view h1:has-text("{heading}")', timeout=20000)


def touch(rel, text):
    """밖에서 고친다 — 감시가 알아보게 조금 띄워"""
    time.sleep(0.25)
    put(rel, text)


try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1680, 'height': 860})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)

        print('[차례와 묶음]')
        order = page.evaluate("() => [...document.querySelectorAll('#lec-tabbar .tabbar-btn')].map((b) => b.id)")
        check('개요·바뀜·업무 카드 │ 넣기·편집·목차·스타일·내보내기 │ AI 요청·메모·터미널', order == ORDER, order)
        seps = page.evaluate("() => [...document.querySelectorAll('#lec-tabbar .tabbar-btn.tb-sep')].map((b) => b.id)")
        check('묶음의 첫 단추 앞에 세로줄 — 넣기·AI 요청', seps == ['lec-btn-put', 'lec-btn-ai'], seps)
        names = page.evaluate("() => [...document.querySelectorAll('#lec-tabbar .tabbar-btn > span:not(.n)')].filter((e) => getComputedStyle(e).display !== 'none').map((e) => e.textContent)")
        check('이름은 화면에 적지 않는다 — 아이콘만', names == [], names)
        bare = page.evaluate("() => [...document.querySelectorAll('#lec-tabbar .tabbar-btn')].filter((b) => b.title || !(b.dataset.tip || '').trim() || b.getAttribute('aria-label') !== b.dataset.tip).map((b) => b.id)")
        check('단추마다 설명이 있고(읽어 주기에도) 브라우저의 title 은 없다 — 두 번 뜨지 않게', bare == [], bare)

        print('[설명 풍선 — 마우스를 올리면 무슨 단추인지]')
        page.hover('#lec-btn-put')
        until(page, lambda: page.evaluate(TIP) is not None)
        tip = page.evaluate(TIP) or {}
        check("넣기: 이름 줄 '넣기', 설명 줄에 하는 일과 키", tip.get('name') == '넣기' and '현재 줄 아래' in tip.get('more', '') and '(/)' in tip.get('more', ''), tip)
        geo = page.evaluate("() => { const b = document.querySelector('#lec-btn-put').getBoundingClientRect(), t = document.querySelector('#lec-tabtip').getBoundingClientRect(); return { below: t.top >= b.bottom, near: t.top - b.bottom < 14, over: t.left < b.right && t.right > b.left, inside: t.left >= 0 && t.right <= innerWidth }; }")
        check('단추 바로 아래, 단추에 걸쳐, 창 안에', all(geo.values()), geo)
        page.hover('#lec-btn-term')
        until(page, lambda: (page.evaluate(TIP) or {}).get('name', '').startswith('터미널'))
        tip = page.evaluate(TIP) or {}
        check('옆 단추로 옮기면 그 단추의 것으로 — 오른쪽 끝에서도 창 밖으로 나가지 않는다', tip.get('name', '').startswith('터미널') and tip.get('right', 9999) <= 1680 - 8 + 1, tip)
        page.hover('#lec-btn-toc')
        until(page, lambda: (page.evaluate(TIP) or {}).get('name', '').startswith('목차'))
        check('설명이 한 줄뿐인 단추는 이름 줄만', (page.evaluate(TIP) or {}).get('more') == '', page.evaluate(TIP))
        page.mouse.move(700, 500)
        until(page, lambda: page.evaluate(TIP) is None)
        check('마우스가 떠나면 사라진다', page.evaluate(TIP) is None)
        page.hover('#lec-btn-export')
        until(page, lambda: page.evaluate(TIP) is not None)
        page.click('#lec-btn-export')
        check('누르면 바로 걷힌다 (메뉴·알림을 가리지 않는다)', page.evaluate(TIP) is None, page.evaluate(TIP))
        page.keyboard.press('Escape')
        page.mouse.move(700, 500)
        page.focus('#lec-doctab-new')
        page.evaluate("() => document.querySelector('#lec-btn-overview').focus({ focusVisible: true })")
        until(page, lambda: page.evaluate(TIP) is not None, ms=2000)
        check('키보드로 가도 뜬다', (page.evaluate(TIP) or {}).get('name') == '프로젝트 개요', page.evaluate(TIP))
        page.keyboard.press('Escape')
        check('Esc 로 걷는다', page.evaluate(TIP) is None)
        page.evaluate('() => document.activeElement.blur()')
        right = page.evaluate("() => { const bar = document.querySelector('#lec-tabbar').getBoundingClientRect(), last = document.querySelector('#lec-btn-term').getBoundingClientRect(); return bar.right - last.right; }")
        check('단추들은 탭 막대 오른쪽 끝에', 0 <= right < 16, right)

        print('[개요 — 문서를 읽다가 프로젝트의 첫 화면으로]')
        check('처음(프로젝트 개요)에는 눌린 모양', page.get_attribute('#lec-btn-overview', 'aria-pressed') == 'true', view(page))
        open_doc(page, '보고서.md', '보고서')
        expect(page, '문서를 열면 풀린다', "() => document.querySelector('#lec-btn-overview').getAttribute('aria-pressed') === 'false'")
        page.click('#lec-btn-overview')
        until(page, lambda: view(page)['type'] == 'overview')
        check('누르면 프로젝트 개요', view(page) == {'type': 'overview', 'path': ''}, view(page))
        expect(page, '다시 눌린 모양', "() => document.querySelector('#lec-btn-overview').getAttribute('aria-pressed') === 'true'")
        tabs = page.locator('#lec-doctabs .doctab, .lec-doctab').count()
        page.click('#lec-btn-overview')
        page.wait_for_timeout(200)
        check('개요에서 또 눌러도 그대로 (탭이 늘지 않는다)', view(page) == {'type': 'overview', 'path': ''} and page.locator('#lec-doctabs .doctab, .lec-doctab').count() == tabs, view(page))
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open', { type: 'overview', path: 'sub' }))")
        until(page, lambda: view(page)['path'] == 'sub')
        check('하위 폴더의 개요에서는 눌린 모양이 아니다', page.get_attribute('#lec-btn-overview', 'aria-pressed') == 'false')
        page.click('#lec-btn-overview')
        until(page, lambda: view(page) == {'type': 'overview', 'path': ''})
        check('하위 폴더의 개요에서 누르면 맨 위로', view(page) == {'type': 'overview', 'path': ''}, view(page))

        print('[바뀜 — Claude 가 문서 셋을 고쳤다]')
        open_doc(page, '보고서.md', '보고서')
        check('바뀐 것이 없으면 수가 없고 흐리다', page.evaluate(COUNT) == 0 and 'none' in page.get_attribute('#lec-btn-changed', 'class'))
        page.click('#lec-btn-changed')
        until(page, lambda: '바뀐 문서가 없습니다' in page.evaluate(TOAST))
        check('없을 때 누르면 까닭을 알린다', '바뀐 문서가 없습니다' in page.evaluate(TOAST), page.evaluate(TOAST))
        touch('조사.md', '# 조사\n\n조사한 내용을 고쳤습니다.\n')
        until(page, lambda: page.evaluate(COUNT) == 1, ms=15000)
        touch('sub/분석.md', '# 분석\n\n분석한 내용을 고쳤습니다.\n')
        until(page, lambda: page.evaluate(COUNT) == 2, ms=15000)
        check('보지 않은 바뀐 문서의 수 2 — 흐리지 않다', page.evaluate(COUNT) == 2 and 'none' not in page.get_attribute('#lec-btn-changed', 'class'), page.evaluate(COUNT))
        side = page.evaluate("() => { const c = document.querySelector('#lec-changed-count'); return c.hidden ? 0 : Number(c.textContent); }")
        check("사이드바 '최근 변경'의 수와 같다", side == 2, side)
        touch('보고서.md', '# 보고서\n\n## 요약\n\n첫 문단을 고쳤습니다.\n\n## 본론\n\n둘째 문단입니다.\n\n## 결론\n\n셋째 문단도 고쳤습니다.\n')
        until(page, lambda: page.evaluate("() => document.querySelector('#lec-view')?.textContent.includes('셋째 문단도 고쳤습니다')"), ms=15000)
        marks = "() => import('/static/js/store.js').then((m) => ({ n: m.S.pane.marks.all.length, at: m.S.pane.marks.at }))"
        until(page, lambda: page.evaluate(marks)['n'] == 2)
        check('보고 있는 문서가 바뀌면 수는 그대로 2 (바뀐 곳은 그 문서 안에)', page.evaluate(COUNT) == 2 and page.evaluate(marks)['n'] == 2, page.evaluate(marks))
        page.click('#lec-btn-changed')
        until(page, lambda: page.evaluate(marks)['at'] == 0)
        check('첫 누르기: 이 문서의 첫 바뀐 곳으로', page.evaluate(marks)['at'] == 0 and view(page)['path'] == '보고서.md', page.evaluate(marks))
        page.click('#lec-btn-changed')
        until(page, lambda: page.evaluate(marks)['at'] == 1)
        check('둘째 누르기: 둘째 바뀐 곳으로 (아직 이 문서)', page.evaluate(marks)['at'] == 1 and view(page)['path'] == '보고서.md', page.evaluate(marks))
        page.click('#lec-btn-changed')
        until(page, lambda: view(page)['path'] == 'sub/분석.md')
        check('이 문서를 다 보면 가장 최근에 바뀐 안 본 문서를 연다', view(page)['path'] == 'sub/분석.md', view(page))
        until(page, lambda: page.evaluate(COUNT) == 1)
        check('연 문서는 수에서 빠진다 — 1', page.evaluate(COUNT) == 1, page.evaluate(COUNT))
        page.click('#lec-btn-changed')
        until(page, lambda: view(page)['path'] == '조사.md')
        until(page, lambda: page.evaluate(COUNT) == 0)
        check('다음 문서를 열고 수가 사라진다', view(page)['path'] == '조사.md' and page.evaluate(COUNT) == 0, [view(page), page.evaluate(COUNT)])
        expect(page, '다 보면 다시 흐리다', "() => document.querySelector('#lec-btn-changed').classList.contains('none')")
        names = page.evaluate("() => [...document.querySelectorAll('#lec-doctabs [role=tab], #lec-doctab-list [role=tab]')].map((e) => e.textContent.trim())")
        check('연 문서는 새 문서 탭에 — 보던 보고서는 탭에 남는다', any('보고서' in n for n in names) or page.evaluate("() => import('/static/js/store.js').then((m) => m.S.tab.panes.some((p) => p.current?.path === '보고서.md'))"), names)

        print('[업무 카드 — 없을 때와 생긴 뒤]')
        check('WORK.md 가 없으면 흐리다', 'none' in page.get_attribute('#lec-btn-card', 'class'))
        check('없을 때의 설명은 만들기', '만들기' in page.get_attribute('#lec-btn-card', 'data-tip'), page.get_attribute('#lec-btn-card', 'data-tip'))
        page.click('#lec-btn-card')
        page.wait_for_selector('#lec-workcard', timeout=5000)
        check("누르면 '업무 카드 만들기' 창 — 파일은 아직 없다", not (proj / 'WORK.md').exists())
        page.keyboard.press('Escape')
        until(page, lambda: page.locator('#lec-workcard').count() == 0)
        check('Esc 로 닫으면 만들지 않는다', not (proj / 'WORK.md').exists())
        touch('WORK.md', '---\nstatus: 진행\n---\n\n# 업무\n\n## 할 일\n\n- [ ] 초안\n')
        until(page, lambda: 'none' not in page.get_attribute('#lec-btn-card', 'class'), ms=15000)
        check('WORK.md 가 생기면 또렷해지고 설명은 열기', '열기' in page.get_attribute('#lec-btn-card', 'data-tip'), page.get_attribute('#lec-btn-card', 'data-tip'))
        page.click('#lec-btn-card')
        until(page, lambda: view(page)['path'] == 'WORK.md')
        check('누르면 업무 카드를 연다', view(page) == {'type': 'doc', 'path': 'WORK.md'}, view(page))
        expect(page, '업무 카드를 보는 동안 눌린 모양', "() => document.querySelector('#lec-btn-card').getAttribute('aria-pressed') === 'true'")

        print('[내보내기 — 문서·슬라이드·폴더 개요]')
        open_doc(page, '보고서.md', '보고서')
        page.click('#lec-btn-export')
        until(page, lambda: page.evaluate(MENU) is not None)
        rows = page.evaluate(MENU) or []
        check('md 문서: PDF·html·Word (브라우저 모드는 인쇄 창의 PDF)', len(rows) == 3 and 'PDF' in rows[0] and 'html로 저장' in rows[1] and 'Word로 저장' in rows[2], rows)
        box = page.evaluate("() => { const m = document.querySelector('#lec-menu').getBoundingClientRect(), b = document.querySelector('#lec-btn-export').getBoundingClientRect(); return { below: m.top >= b.bottom, inside: m.right <= innerWidth && m.bottom <= innerHeight }; }")
        check('메뉴는 단추 아래, 창 안에', box['below'] and box['inside'], box)
        page.locator('#lec-menu button[data-i]', has_text='html로 저장').click()
        expect(page, "'html로 저장…' 은 내보내기 창을 html 형식으로", "() => !document.querySelector('#lec-print').hidden")
        page.keyboard.press('Escape')
        expect(page, '창 닫기', "() => document.querySelector('#lec-print').hidden")
        page.click('#lec-btn-export')
        until(page, lambda: page.evaluate(MENU) is not None)
        page.keyboard.press('Escape')
        expect(page, 'Esc 로 메뉴 닫기 — 아무것도 열리지 않는다', "() => document.querySelector('#lec-menu').hidden && document.querySelector('#lec-print').hidden")
        check('[인쇄] 단추는 없다 — 내보내기 메뉴 안에', page.locator('#lec-btn-print').count() == 0)
        page.evaluate("""() => { window.pywebview = { api: {   // 내보내기 창의 PDF·인쇄는 창 모드의 것 — 가짜 창 API (printpdf 와 같게)
          pdf_preview: async () => ({ token: 'fake', pages: 1, size: 1024 }), save_pdf: async () => ({ path: 'C:/x/a.pdf' }) } }; }""")
        page.click('#lec-btn-export')
        until(page, lambda: page.evaluate(MENU) is not None)
        rows = page.evaluate(MENU) or []
        check('창 모드의 md 문서: PDF로 저장 · 인쇄 · html로 저장 · Word로 저장', [r.split('…')[0] for r in rows] == ['PDF로 저장', '인쇄', 'html로 저장', 'Word로 저장'], rows)
        page.locator('#lec-menu button[data-i]', has_text='인쇄…').click()
        expect(page, "'인쇄…' 는 내보내기 창을 인쇄가 기본 단추로 (전의 [인쇄] 와 같다)", "() => !document.querySelector('#lec-print').hidden && document.querySelector('#lec-print-paper').classList.contains('primary')")
        page.keyboard.press('Escape')
        expect(page, '창 닫기 (인쇄)', "() => document.querySelector('#lec-print').hidden")
        page.evaluate('() => { delete window.pywebview; }')

        open_doc(page, '발표.md', '발표')
        until(page, lambda: page.evaluate("() => !document.querySelector('#lec-st-pptx').hidden"))
        page.click('#lec-btn-export')
        until(page, lambda: page.evaluate(MENU) is not None)
        rows = page.evaluate(MENU) or []
        check('Lectern 슬라이드: pptx 로 전환·html 로 전환이 있고 html로 저장은 없다',
              any('pptx 로 전환' in r for r in rows) and any('html 로 전환' in r for r in rows) and not any('html로 저장' in r for r in rows), rows)
        page.locator('#lec-menu button[data-i]', has_text='pptx 로 전환').click()
        expect(page, "'pptx 로 전환…' 은 상태줄의 단추와 같은 창", "() => !document.querySelector('#lec-pptx').hidden")
        page.click('#lec-pptx-cancel')
        expect(page, 'pptx 창 닫기', "() => document.querySelector('#lec-pptx').hidden")

        page.click('#lec-btn-overview')
        until(page, lambda: view(page)['type'] == 'overview')
        page.click('#lec-btn-export')
        until(page, lambda: '내보낼 수 있습니다' in page.evaluate(TOAST))
        check('폴더 개요: 메뉴 없이 까닭을 알린다', page.evaluate(MENU) is None and '내보낼 수 있습니다' in page.evaluate(TOAST), page.evaluate(TOAST))

        print('[md 문서 스타일]')
        open_doc(page, '보고서.md', '보고서')
        until(page, lambda: page.evaluate("() => !document.querySelector('#lec-st-mdstyle').hidden"))
        page.click('#lec-btn-style')
        expect(page, 'md 문서: 스타일 창이 열린다 (상태줄의 그 단추와 같은 창)', "() => !document.querySelector('#lec-mdstyle').hidden")
        page.keyboard.press('Escape')
        expect(page, 'Esc 로 닫기 — 문서는 그대로', "() => document.querySelector('#lec-mdstyle').hidden")
        check('고르지 않으면 파일은 바뀌지 않는다', (proj / '보고서.md').read_text(encoding='utf-8').startswith('# 보고서\n\n## 요약\n\n첫 문단을 고쳤습니다.'))
        open_doc(page, '발표.md', '발표')
        page.click('#lec-btn-style')
        until(page, lambda: 'md 문서에서 고릅니다' in page.evaluate(TOAST))
        check('Lectern 슬라이드: 창 없이 까닭을 알린다', page.evaluate("() => document.querySelector('#lec-mdstyle').hidden") and 'md 문서에서 고릅니다' in page.evaluate(TOAST), page.evaluate(TOAST))

        print('[AI 요청 — 고르면 터미널에 넣는다, Enter 는 누르지 않는다]')
        page.evaluate("() => import('/static/js/store.js').then((m) => { window.__pasted = []; m.on('term-paste', (d) => window.__pasted.push(typeof d === 'string' ? d : d.text)); })")
        open_doc(page, '보고서.md', '보고서')
        page.click('#lec-btn-ai')
        until(page, lambda: page.evaluate(MENU) is not None)
        rows = page.evaluate(MENU) or []
        head = page.evaluate("() => document.querySelector('#lec-menu .menu-head')?.textContent || ''")
        check('메뉴 머리에 누구에게·어디에 — Enter 는 누르지 않음', 'Claude' in head and '터미널' in head and 'Enter' in head, head)
        check('md 문서: 가리키기 · 다듬기 점검 · 내 문체 견본 · 설정', len(rows) >= 4 and '@보고서.md' in rows[0] and '다듬기 점검' in rows[1] and '내 문체' in rows[2] and 'AI 도구 설정' in rows[-1]
              and not any('기획 메모' in r for r in rows), rows)
        page.locator('#lec-menu button[data-i]', has_text='이 문서 가리키기').click()
        until(page, lambda: len(page.evaluate(PASTED)) == 1)
        check("가리키기: '@보고서.md ' 를 넣는다 — 줄바꿈 없이", page.evaluate(PASTED) == ['@보고서.md '], page.evaluate(PASTED))
        page.keyboard.press('Escape')
        page.click('#lec-btn-ai')
        until(page, lambda: page.evaluate(MENU) is not None)
        page.locator('#lec-menu button[data-i]', has_text='다듬기 점검 요청').click()
        until(page, lambda: len(page.evaluate(PASTED)) == 2)
        got = page.evaluate(PASTED)[-1]
        check('다듬기 점검: 문서 우클릭의 것과 같은 요청 글 — @경로가 들고 줄바꿈으로 끝나지 않는다', '@보고서.md' in got and '다듬기 점검 안내' in got and not got.endswith('\n'), got[:120])
        page.keyboard.press('Escape')
        open_doc(page, 'WORK.md', '업무')
        page.click('#lec-btn-ai')
        until(page, lambda: page.evaluate(MENU) is not None)
        rows = page.evaluate(MENU) or []
        check('업무 카드: 기획 메모 반영 요청이 더 있다', any('기획 메모 반영 요청' in r for r in rows), rows)
        page.keyboard.press('Escape')
        open_doc(page, '발표.md', '발표')
        page.click('#lec-btn-ai')
        until(page, lambda: page.evaluate(MENU) is not None)
        rows = page.evaluate(MENU) or []
        check('Lectern 슬라이드: 내 문체 견본은 없다', '@발표.md' in rows[0] and not any('내 문체' in r for r in rows), rows)
        page.keyboard.press('Escape')
        page.click('#lec-btn-overview')
        until(page, lambda: view(page)['type'] == 'overview')
        page.click('#lec-btn-ai')
        until(page, lambda: page.evaluate(MENU) is not None)
        rows = page.evaluate(MENU) or []
        heads = page.evaluate("() => [...document.querySelectorAll('#lec-menu .menu-head')].map((e) => e.textContent)")
        check('폴더 개요: 문서를 열라는 안내와 설정만', rows == ['AI 도구 설정…'] and any('문서를 열면' in h for h in heads), [rows, heads])
        page.locator('#lec-menu button[data-i]', has_text='AI 도구 설정').click()
        expect(page, "'AI 도구 설정…' 은 설정 창의 그 분류", "() => { const s = document.querySelector('#lec-settings'); return !!s && !s.hidden; }")
        page.keyboard.press('Escape')
        check('요청은 넣은 둘뿐 — 메뉴를 열고 닫는 것만으로는 아무것도 가지 않는다', len(page.evaluate(PASTED)) == 2, page.evaluate(PASTED))

        print('[좁은 창 — 프로젝트 탭의 자리가 남는다]')
        open_doc(page, '보고서.md', '보고서')
        touch('조사.md', '# 조사\n\n한 번 더 고쳤습니다.\n')
        until(page, lambda: page.evaluate(COUNT) == 1, ms=15000)
        for w in (1360, 1040, 760):
            page.set_viewport_size({'width': w, 'height': 860})
            page.wait_for_timeout(120)
            fit = page.evaluate("() => { const bar = document.querySelector('#lec-tabbar'); const bs = [...bar.querySelectorAll('.tabbar-btn')].map((b) => b.getBoundingClientRect()); return { over: bar.scrollWidth - bar.clientWidth, row: new Set(bs.map((r) => Math.round(r.top))).size, tab: document.querySelector('#lec-tablist .lec-tab').getBoundingClientRect().width }; }")
            check(f'{w}: 단추 열하나가 한 줄에, 넘치지 않고, 프로젝트 탭은 96px 이상', fit['over'] <= 0 and fit['row'] == 1 and fit['tab'] >= 96, fit)
        check('좁아도 바뀜의 수는 보인다', page.evaluate(SHOWN, '#lec-btn-changed-n') and page.evaluate(COUNT) == 1)
        page.hover('#lec-btn-term')
        until(page, lambda: page.evaluate(TIP) is not None)
        tip = page.evaluate(TIP) or {}
        check('760: 설명 풍선이 창 안에', tip.get('left', -1) >= 0 and tip.get('right', 9999) <= 760, tip)
        page.mouse.move(300, 500)
        page.set_viewport_size({'width': 1680, 'height': 860})

        print('[영어 화면]')
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ language: 'en' }))")
        page.reload()
        page.wait_for_function("document.documentElement.lang === 'en'", timeout=15000)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        hangul = page.evaluate("() => [...document.querySelectorAll('#lec-tabbar .tabbar-btn')].filter((b) => /[가-힣]/.test((b.dataset.tip || '') + b.textContent) || !b.dataset.tip).map((b) => b.id)")
        check('설명에 한글이 남지 않는다', not hangul, hangul)
        page.evaluate(OPEN, '보고서.md')
        page.wait_for_selector('#lec-view h1', timeout=20000)
        page.click('#lec-btn-export')
        until(page, lambda: page.evaluate(MENU) is not None)
        rows = page.evaluate(MENU) or []
        check('내보내기 메뉴도 영어로', rows and not any(any('가' <= ch <= '힣' for ch in r) for r in rows), rows)
        page.keyboard.press('Escape')
        page.hover('#lec-btn-ai')
        until(page, lambda: page.evaluate(TIP) is not None)
        tip = page.evaluate(TIP) or {}
        check('설명 풍선도 영어로 — 이름 줄과 설명 줄', tip.get('name') == 'AI requests' and 'terminal' in tip.get('more', ''), tip)
        page.mouse.move(700, 500)
        page.click('#lec-btn-ai')
        until(page, lambda: page.evaluate(MENU) is not None)
        rows = page.evaluate(MENU) or []
        check('AI 요청 메뉴도 영어로', rows and not any(any('가' <= ch <= '힣' for ch in r.replace('보고서', '')) for r in rows), rows)
        page.keyboard.press('Escape')
        check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
