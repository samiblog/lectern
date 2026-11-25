"""0.104.0 사람 시나리오 2 — 연구원의 하루: 문서를 읽으며 질문마다 나눠 담고, 훑고, 보고서에 옮긴다 (D198·D199).

1. 아침 — 담기함이 하나도 없는 프로젝트에서 키보드만으로 세 질문에 나눠 담는다
2. 담는 동안 사이드바는 다른 탭, 편집하는 칸, html 문서, Lectern 슬라이드, vi 키, 고르다 말고 다른 데로
3. 한글 이름을 치며 고른다 (조합 중의 Enter), 좁은 창
4. 펼친 화면을 열어 둔 채 문서로 돌아가 담고 이름을 바꾼다
5. 담는 곳(●)을 정해 두고 다른 담기함의 메모를 쓴 뒤 다시 켠다 — ● 가 그대로
6. 담기함 서른 개 — 거르기, 이름이 긴 것·비슷한 것, 사이드바를 좁혀도
7. 터미널을 연 채(목차가 숨는다) 목록에서 조각을 훑는다
8. 열어 둔 담기함을 지운다, 거르는 동안 담는다
9. 보고서를 편집하며 여러 담기함의 조각을 커서 자리에"""
import json
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-scen104b-'))
proj = base / '리서치'
other = base / '다른'
for d in (proj, other):
    d.mkdir(parents=True)
CLIPS = proj / '.lectern' / 'clips'
for name, head in (('가격', '가격 동향'), ('수급', '수급 전망'), ('위험', '위험 요인')):
    (proj / f'{name}.md').write_text(f'# {head}\n\n{name} 첫 문단입니다.\n\n표 1. {name} 표\n\n| 분기 | 값 |\n|---|---:|\n| 1Q | 10 |\n| 2Q | 20 |\n\n자료: LME\n\n## {name} 배경\n\n{name} 배경 문단입니다.\n\n- {name} 항목 하나\n- {name} 항목 둘\n',
                                     encoding='utf-8', newline='\n')
(proj / '발표.md').write_text('---\nmarp: true\n---\n\n# 발표 표지\n\n---\n\n## 둘째 장\n\n- 슬라이드 항목\n', encoding='utf-8', newline='\n')
(proj / '자료.html').write_text('<!doctype html><meta charset="utf-8"><title>자료</title><h1>자료</h1><p>html 문단</p>', encoding='utf-8')
(proj / '보고.md').write_text('# 보고\n\n## 결론\n\n끝 문단.\n', encoding='utf-8', newline='\n')
(other / '개요.md').write_text('# 다른 개요\n\n다른 글.\n', encoding='utf-8', newline='\n')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)

OPEN = "(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: p, newTab: true }))"
VIEW = "() => import('/static/js/store.js').then((m) => (m.S.view ? m.S.view.type + ':' + (m.S.view.path || '') : ''))"
TOAST = "() => { const e = document.querySelector('#lec-toast'); return e && !e.hidden ? e.textContent : ''; }"
ROWS = "() => [...document.querySelectorAll('#lec-boxpick-body button')].map((e) => e.querySelector('.bp-name').textContent + (e.classList.contains('sel') ? '*' : ''))"
BOXES = "() => [...document.querySelectorAll('#lec-basket-list .bk-box')].map((e) => e.querySelector('.label').textContent + ' ' + e.querySelector('.n')?.textContent + (e.classList.contains('cur') ? '*' : ''))"
CARDS = "() => [...document.querySelectorAll('#lec-view .cb-card')].map((e) => e.querySelector('.cb-name').value || e.querySelector('.cb-name').placeholder)"
ONSCREEN = "(s) => { const r = document.querySelector(s).getBoundingClientRect(); return r.left >= 0 && r.top >= 0 && r.right <= innerWidth && r.bottom <= innerHeight; }"
TEXT = "() => import('/static/js/store.js').then((m) => m.S.pane.editor ? m.S.pane.editor.cm.getValue() : '')"


def src(name):
    for _ in range(30):
        try:
            return (CLIPS / name).read_text(encoding='utf-8')
        except OSError:
            time.sleep(0.03)
    return ''


def count(name):
    return src(name).count('<!-- /lectern-clip -->')


try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        errors = []
        page = b.new_page(viewport={'width': 1300, 'height': 850})
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.on('dialog', lambda d: d.accept())

        def start():
            page.goto(url)
            page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
            page.wait_for_timeout(600)

        def doc(path, head):
            page.evaluate(OPEN, path)
            page.wait_for_selector(f'#lec-view h1:has-text("{head}")', timeout=20000)
            page.wait_for_timeout(200)

        def on(sel, text):
            page.locator(f'#lec-view {sel}', has_text=text).first.click()

        def pick(text=''):
            page.keyboard.press('Alt+Shift+c')
            page.wait_for_selector('#lec-boxpick:not([hidden])')
            if text:
                page.keyboard.insert_text(text)
                page.wait_for_timeout(60)

        def basket():
            page.click('.side-tabs button[data-tab="basket"]')

        def boxes():
            return page.evaluate(BOXES)

        def row(name):
            return page.locator(f'#lec-basket-list .bk-box:has(.label:text-is("{name}"))')

        start()
        print('[1. 키보드만으로 세 질문에]')
        doc('가격.md', '가격 동향')
        on('p', '가격 첫 문단')
        page.keyboard.press('Alt+Shift+c')
        page.wait_for_selector('#lec-boxpick:not([hidden])')
        check('담기함이 없으면 새 담기함 줄만', page.evaluate(ROWS) == ['새 담기함…*'], page.evaluate(ROWS))
        page.keyboard.press('Enter')
        page.keyboard.press('Enter')   # 이름 없이 또 — 아무 일도 없다
        check('이름 없이 Enter 는 만들지 않는다', page.locator('#lec-boxpick').is_visible() and not CLIPS.exists())
        page.keyboard.insert_text('왜 올랐나')
        page.keyboard.press('Enter')
        expect(page, '첫 질문을 만들며 담는다', lambda: count('왜-올랐나.md') == 1)
        on('td', '20')
        pick('공급은 어떤가')
        page.keyboard.press('Enter')
        expect(page, '표를 둘째 질문에', lambda: count('공급은-어떤가.md') == 1 and '자료: LME' in src('공급은-어떤가.md'))
        doc('수급.md', '수급 전망')
        on('h2', '수급 배경')
        pick('반증')
        page.keyboard.press('Enter')
        expect(page, '절을 셋째 질문에', lambda: count('반증.md') == 1 and '수급 항목 둘' in src('반증.md'))
        on('td', '20')
        pick()
        check('최근에 담은 것부터 — 처음 고른 것은 지금 담기함이 아닌 것', page.evaluate(ROWS) == ['반증', '공급은 어떤가*', '왜 올랐나', '새 담기함…'], page.evaluate(ROWS))
        page.keyboard.press('Enter')
        expect(page, 'Enter 두 번이면 바로 앞의 담기함에', lambda: count('공급은-어떤가.md') == 2)
        page.keyboard.press('Alt+c')
        expect(page, 'Alt+C 는 여전히 지금 담기함(마지막에 만든 것)에', lambda: count('반증.md') == 2, lambda: src('반증.md')[-200:])
        check('알림에 어느 담기함인지', "'반증' (2개)" in page.evaluate(TOAST), page.evaluate(TOAST))

        print('[2. 담기 어려운 자리]')
        page.click('.side-tabs button[data-tab="search"]')
        on('p', '수급 첫 문단')
        pick('왜')
        page.keyboard.press('Enter')
        expect(page, '사이드바가 검색이어도 담기고 탭은 그대로', lambda: count('왜-올랐나.md') == 2 and page.locator('#lec-basket').is_hidden())
        on('p', '수급 첫 문단')
        page.keyboard.press('Enter')
        page.wait_for_timeout(300)
        page.keyboard.press('Alt+Shift+c')
        page.wait_for_timeout(300)
        check('글자 칸에서는 열리지 않는다', page.locator('#lec-boxpick').count() == 0 or page.locator('#lec-boxpick').is_hidden())
        page.keyboard.press('Escape')
        page.keyboard.press('Escape')
        page.evaluate(OPEN, '자료.html')
        page.wait_for_timeout(1200)
        page.locator('#lec-content').focus()
        page.keyboard.press('Alt+Shift+c')
        expect(page, 'html 문서에서는 담지 못한다고 알린다', lambda: 'md 문서를 읽는 화면에서' in page.evaluate(TOAST), lambda: page.evaluate(TOAST))
        page.evaluate(OPEN, '발표.md')
        page.wait_for_selector('#lec-view :text("둘째 장")', timeout=20000)
        page.wait_for_timeout(400)
        page.locator('#lec-view li', has_text='슬라이드 항목').click()
        pick('공급')
        page.keyboard.press('Enter')
        expect(page, 'Lectern 슬라이드의 줄도', lambda: count('공급은-어떤가.md') == 3 and '슬라이드 항목' in src('공급은-어떤가.md'), lambda: (page.evaluate(TOAST), count('공급은-어떤가.md')))
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ vi_keys: true }))")
        doc('위험.md', '위험 요인')
        on('p', '위험 첫 문단')
        page.keyboard.press('j')
        pick('반')
        check('vi 키를 켜도 글자는 거르기 칸에', page.input_value('#lec-boxpick-find') == '반' and page.evaluate(ROWS)[0] == '반증*', page.evaluate(ROWS))
        page.keyboard.press('Escape')
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ vi_keys: false }))")
        on('p', '위험 첫 문단')
        page.keyboard.press('Shift+ArrowDown')
        pick('반')
        page.keyboard.press('Enter')
        expect(page, '고른 줄도', lambda: count('반증.md') == 3 and '위험 첫 문단입니다.\n\n표 1. 위험 표\n<!-- /lectern-clip' in src('반증.md'), lambda: src('반증.md')[-260:])
        page.keyboard.press('Escape')
        on('p', '위험 첫 문단')
        pick('왜')
        page.evaluate("(dir) => import('/static/js/tabs.js').then((m) => m.openFolder(dir))", str(other))
        until(page, lambda: page.evaluate("() => import('/static/js/store.js').then((m) => m.S.tab?.name)") == '다른', 15000)
        page.wait_for_timeout(300)
        check('고르다 말고 다른 프로젝트로 가면 창이 남지 않는다', page.locator('#lec-boxpick').is_hidden())
        page.evaluate("() => import('/static/js/tabs.js').then((m) => m.selectTabAt(1))")
        page.wait_for_selector('#lec-view h1:has-text("위험 요인")')
        check('— 담지도 않았다', count('왜-올랐나.md') == 2)
        on('p', '위험 첫 문단')
        pick('왜')
        page.keyboard.press('Control+Tab')
        page.wait_for_timeout(400)
        check('고르다 말고 다른 문서 탭으로 가도', page.locator('#lec-boxpick').is_hidden() or page.evaluate(VIEW) == 'doc:위험.md', page.evaluate(VIEW))
        page.keyboard.press('Escape')

        print('[3. 한글 조합, 좁은 창]')
        doc('위험.md', '위험 요인')
        on('p', '위험 배경')
        page.keyboard.press('Alt+Shift+c')
        page.wait_for_selector('#lec-boxpick:not([hidden])')
        cdp = page.context.new_cdp_session(page)
        cdp.send('Input.imeSetComposition', {'text': '반', 'selectionStart': 1, 'selectionEnd': 1})
        page.wait_for_timeout(80)
        check('조합 중에도 거른다', page.evaluate(ROWS)[0] == '반증*', page.evaluate(ROWS))
        cdp.send('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': 'Process', 'code': 'Enter', 'windowsVirtualKeyCode': 229})
        page.wait_for_timeout(150)
        check('조합을 끝내는 Enter 는 고르지 않는다', page.locator('#lec-boxpick').is_visible() and count('반증.md') == 3)
        cdp.send('Input.insertText', {'text': '반증'})
        page.keyboard.press('Enter')
        expect(page, '다음 Enter 로 고른다', lambda: count('반증.md') == 4)
        page.set_viewport_size({'width': 720, 'height': 480})
        page.wait_for_timeout(400)
        page.locator('#lec-view li').last.scroll_into_view_if_needed()
        page.locator('#lec-view li').last.click()
        pick()
        check('좁은 창·맨 아래 줄에서도 창이 화면 안에', page.evaluate(ONSCREEN, '#lec-boxpick'))
        page.keyboard.press('Escape')
        page.set_viewport_size({'width': 1300, 'height': 850})
        page.wait_for_timeout(300)

        print('[4. 펼쳐 둔 채 담고 이름을 바꾼다]')
        basket()
        row('반증').click()
        page.wait_for_selector('#lec-view.clips-view .cb-card')
        check('조각 넷', len(page.evaluate(CARDS)) == 4, page.evaluate(CARDS))
        doc('가격.md', '가격 동향')
        on('p', '가격 배경')
        page.keyboard.press('Alt+c')
        check('이름이 짧은 탭도 닫기는 오른쪽 끝에 (가운데를 눌러도 닫히지 않는다)', page.evaluate("() => [...document.querySelectorAll('#lec-doctab-list .doc-tab')].every((e) => e.getBoundingClientRect().right - e.querySelector('.tab-close').getBoundingClientRect().right < 14)"))
        page.locator('#lec-doctab-list .doc-tab', has_text='반증').click()
        page.wait_for_selector('#lec-view.clips-view .cb-card')
        expect(page, '담은 것이 펼친 화면과 목차에', lambda: len(page.evaluate(CARDS)) == 5 and page.locator('#lec-toc a[data-i]').count() == 5, lambda: page.evaluate(CARDS))
        page.fill('#lec-view .cb-title', '반증과 반론')
        page.keyboard.press('Tab')
        expect(page, '이름을 바꾸면 목록과 탭에', lambda: any(x.startswith('반증과 반론 5') for x in boxes()) and page.locator('#lec-doctab-list .doc-tab.active .name').inner_text() == '반증과 반론', boxes)
        doc('가격.md', '가격 동향')
        on('p', '가격 배경')
        pick('반론')
        check('고르는 창에도 새 이름으로', page.evaluate(ROWS)[0] == '반증과 반론*', page.evaluate(ROWS))
        page.keyboard.press('Escape')
        page.locator('#lec-view p', has_text='가격 배경').click(button='right')
        check('우클릭 메뉴에도', "담기 — '반증과 반론'" in page.inner_text('#lec-menu'), page.inner_text('#lec-menu')[:200])
        page.keyboard.press('Escape')

        print('[5. 담는 곳을 정해 두고 다시 켠다]')
        row('왜 올랐나').hover()
        row('왜 올랐나').locator('.bk-here').click()
        row('공급은 어떤가').click()
        page.wait_for_selector('#lec-view.clips-view .cb-card')
        page.locator('#lec-view .cb-memo').first.fill('나중에 쓴 메모')
        page.keyboard.press('Tab')
        expect(page, '다른 담기함에 메모', lambda: '나중에 쓴 메모' in src('공급은-어떤가.md'))
        page.wait_for_timeout(1200)
        start()
        basket()
        expect(page, '다시 켜도 담는 곳은 정해 둔 그대로', lambda: '왜 올랐나 2*' in boxes(), boxes)

        second = b.new_page(viewport={'width': 1100, 'height': 800})
        second.on('pageerror', lambda e: errors.append(str(e)[:300]))
        second.goto(url)
        second.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        second.wait_for_timeout(600)
        second.click('.side-tabs button[data-tab="basket"]')
        expect(second, '다른 창도 같은 담는 곳', lambda: '왜 올랐나 2*' in second.evaluate(BOXES), lambda: second.evaluate(BOXES))
        second.locator('#lec-basket-list .bk-box:has(.label:text-is("공급은 어떤가"))').hover()
        second.locator('#lec-basket-list .bk-box:has(.label:text-is("공급은 어떤가")) .bk-here').click()
        second.wait_for_timeout(300)
        page.evaluate("() => window.dispatchEvent(new Event('focus'))")
        expect(page, '다른 창에서 바꾸면 이 창으로 돌아올 때 따른다', lambda: '공급은 어떤가 3*' in boxes(), boxes)
        row('왜 올랐나').hover()
        row('왜 올랐나').locator('.bk-here').click()
        page.evaluate("() => { for (let i = 0; i < 5; i += 1) window.dispatchEvent(new Event('focus')); }")
        page.wait_for_timeout(800)
        check('바꾸자마자 다시 읽어도 되돌아가지 않는다', '왜 올랐나 2*' in boxes(), boxes())
        second.close()

        print('[6. 담기함 서른 개]')
        for i in range(1, 26):
            (CLIPS / f'주제-{i}.md').write_text(f'# {"아주 긴 이름의 " * 6 if i == 7 else ""}주제 {i}\n', encoding='utf-8', newline='\n')
        page.evaluate("() => window.dispatchEvent(new Event('focus'))")
        expect(page, '스물여덟 개', lambda: len(boxes()) == 28, lambda: len(boxes()))
        check('이름순은 숫자 차례 (주제 2 다음 3)', [x.split()[1] for x in boxes() if x.startswith('주제')][:4] == ['1', '2', '3', '4'], boxes()[:8])
        check('담는 곳은 그대로', '왜 올랐나 2*' in boxes(), [x for x in boxes() if x.endswith('*')])
        page.evaluate("() => document.documentElement.style.setProperty('--sidebar-w', '180px')")
        page.wait_for_timeout(200)
        wide = page.evaluate("() => { const l = document.querySelector('#lec-basket-list'); return [l.scrollWidth - l.clientWidth, Math.max(...[...l.querySelectorAll('.row')].map((e) => e.offsetHeight))]; }")
        check('긴 이름도 한 줄, 옆으로 넘치지 않는다', wide[0] <= 0 and wide[1] <= 30, wide)
        page.evaluate("() => document.documentElement.style.removeProperty('--sidebar-w')")
        page.focus('#lec-basket-filter')
        page.keyboard.insert_text('주제 2')
        expect(page, '거른다', lambda: len(boxes()) == 8, boxes)
        page.keyboard.press('ArrowDown')
        page.keyboard.press('End')
        page.keyboard.press('Enter')
        page.wait_for_timeout(500)
        check('거른 채 Enter 로 연다 — 빈 담기함', page.evaluate(VIEW) == 'clips:주제-25.md', page.evaluate(VIEW))
        doc('수급.md', '수급 전망')
        on('p', '수급 배경')
        pick('주제 2')
        check('고르는 창도 거른다 — 창이 화면을 넘지 않는다', len(page.evaluate(ROWS)) == 8 and page.evaluate(ONSCREEN, '#lec-boxpick'), page.evaluate(ROWS))
        page.keyboard.press('Escape')
        pick()
        for _ in range(29):
            page.keyboard.press('ArrowDown')
        check('서른 줄을 내려가도 고른 줄이 보인다', page.evaluate("() => { const b = document.querySelector('#lec-boxpick-body').getBoundingClientRect(); const s = document.querySelector('#lec-boxpick .sel').getBoundingClientRect(); return s.top >= b.top - 1 && s.bottom <= b.bottom + 1; }"))
        page.keyboard.press('Escape')
        page.fill('#lec-basket-filter', '')
        for i in range(1, 26):
            (CLIPS / f'주제-{i}.md').unlink()
        page.evaluate("() => window.dispatchEvent(new Event('focus'))")
        expect(page, '밖에서 지우면 목록에서 사라진다', lambda: len(boxes()) == 3, boxes)

        print('[7. 터미널을 연 채 훑는다]')
        page.evaluate("() => import('/static/js/store.js').then((m) => { window.__pasted = []; m.on('term-paste', (d) => window.__pasted.push(typeof d === 'string' ? d : d.text)); })")
        row('공급은 어떤가').locator('.caret').click()
        expect(page, '펼치면 셋', lambda: page.locator('#lec-basket-list .bk-item').count() == 3)
        page.locator('#lec-basket-list .bk-item').first.focus()
        page.keyboard.press('Shift+ArrowRight')
        expect(page, '조각의 담은 곳이 터미널에', lambda: page.evaluate('() => window.__pasted.length') == 1 and page.evaluate('() => window.__pasted[0]').startswith('@가격.md '), lambda: page.evaluate('() => window.__pasted'))
        until(page, lambda: page.locator('#lec-term').is_visible(), 6000)
        check('터미널을 열어도 목록의 조각은 보인다', page.locator('#lec-basket-list .bk-item').count() == 3 and page.locator('#lec-basket-list .bk-item').first.is_visible())
        page.locator('#lec-basket-list .bk-item').nth(1).hover()
        tip = page.locator('#lec-basket-list .bk-item').first.get_attribute('title')
        check('마우스를 올리면 담은 곳과 메모', '가격.md' in tip and '나중에 쓴 메모' in tip, tip)
        page.click('#lec-btn-term')

        print('[8. 열어 둔 담기함을 지운다, 거르는 동안 담는다]')
        row('공급은 어떤가').click()
        page.wait_for_selector('#lec-view.clips-view .cb-card')
        doc('가격.md', '가격 동향')
        page.fill('#lec-basket-filter', '반론')
        on('p', '가격 첫 문단')
        page.keyboard.press('Alt+c')
        expect(page, '거르는 동안에도 정해 둔 곳에 담긴다', lambda: count('왜-올랐나.md') == 3 and len(boxes()) == 1, boxes)
        page.fill('#lec-basket-filter', '')
        row('공급은 어떤가').focus()
        page.keyboard.press('Delete')
        expect(page, '담기함을 지운다 (휴지통)', lambda: not (CLIPS / '공급은-어떤가.md').exists() and len(boxes()) == 2, boxes, ms=15000)
        page.locator('#lec-doctab-list .doc-tab', has_text='공급은').first.click() if page.locator('#lec-doctab-list .doc-tab', has_text='공급은').count() else page.locator('#lec-doctab-list .doc-tab').last.click()
        page.wait_for_timeout(500)
        check('열려 있던 탭은 없다고 말한다', '담기함이 없습니다' in page.inner_text('#lec-view') or page.evaluate(VIEW) != 'clips:공급은-어떤가.md', (page.evaluate(VIEW), page.inner_text('#lec-view')[:120]))
        check('담는 곳은 그대로', '왜 올랐나 3*' in boxes(), boxes())

        print('[9. 보고서에 옮긴다]')
        doc('보고.md', '보고')
        page.locator('#lec-content').focus()
        page.keyboard.press('Control+e')
        page.wait_for_selector('.lec-pane.active .lec-editor .CodeMirror', timeout=20000)
        page.keyboard.press('Control+End')
        for name in ('왜 올랐나', '반증과 반론'):
            row(name).locator('.caret').click()
            page.wait_for_timeout(150)
        check('편집하는 동안 조각마다 보내기', page.locator('#lec-basket-list .bk-put').count() == page.locator('#lec-basket-list .bk-item').count() == 8, page.locator('#lec-basket-list .bk-put').count())
        page.locator('#lec-basket-list .bk-item', has_text='가격 첫 문단').first.locator('.bk-put').click()
        page.wait_for_timeout(300)
        page.locator('#lec-basket-list .bk-item', has_text='수급 배경').first.locator('.bk-put').click()
        expect(page, '두 담기함의 조각이 차례로 커서 자리에', lambda: 0 < page.evaluate(TEXT).find('가격 첫 문단입니다') < page.evaluate(TEXT).find('수급 배경 문단입니다'), lambda: page.evaluate(TEXT))
        check('펼친 화면으로 떠나지 않았다', page.evaluate(VIEW) == 'doc:보고.md', page.evaluate(VIEW))
        page.evaluate("() => import('/static/js/store.js').then((m) => import('/static/js/editor.js').then((e) => e.closeEditor(m.S.pane, { ask: false, sync: false })))")
        check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
