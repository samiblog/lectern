"""담기함 (D197): 담기를 여러 개로 — 프로젝트의 .lectern/clips/ 에 남고, 조각마다 제목과 메모, 문서 탭에 실제 모습으로 펼쳐 보기, Alt+C.
처음 담기(담기함이 저절로 하나), 새 담기함·지금 담기함·다른 담기함에, Alt+C(고른 글·고른 줄·현재 줄의 블록·제목·캡션·모아 보기),
펼쳐 보기(실제 표·그림·다이어그램, 제목·메모 저장, 차례·빼기·되돌리기, 원래 자리로·Alt+←, 원래 문서가 바뀜·옮겨짐·없어짐, 이름 바꾸기),
옮기기·복사, 문서로 보내기(제목·메모), AI 에 맡기기, 밖에서 고친 파일과 합치기, 문서가 심은 것, 다시 켠 뒤, 지우기, 보기만 하는 프로젝트, 영어"""
import json
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import ROOT, check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-clipboxes-'))
proj = base / 'proj'
(proj / '조사').mkdir(parents=True)
CLIPS = proj / '.lectern' / 'clips'


def put(rel, text, newline='\n'):
    (proj / rel).write_text(text, encoding='utf-8', newline=newline)


(proj / '조사' / '그림.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="160" height="100" viewBox="0 0 160 100"><rect width="160" height="100" fill="#2b5c8a"/></svg>', encoding='utf-8')
PRICE = '''# 가격 동향

머리 문단입니다. **굵은 말**이 있습니다.

## 분기별 가격

표 1. 구리 분기별 가격

| 분기 | 가격 |
|---|---:|
| 1Q | 9,210 |
| 2Q | 9,480 |

자료: LME

본문 문단이고 주가 있습니다.[^1]

- 목록 하나
- 목록 둘

## 그림

그림 1. 아이콘

![아이콘](그림.svg)

[이 문서의 절](#분기별-가격) 과 [보고](../보고.md) 를 봅니다.

```mermaid
flowchart LR
  광산 --> 제련
```

[^1]: LME 2분기 자료.
'''
put('조사/가격.md', PRICE)
put('보고.md', '# 보고\n\n## 결론\n\n끝 문단.\n')
put('심은.md', '# 심은 문서\n\n<button class="parts-send" data-act="send">심은 단추</button> <i data-xss="1" onclick="window.__bad=1">x</i>\n\n<img src="x" onerror="window.__bad=1">\n')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)

OPEN = "(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: p }))"
VIEW = "() => import('/static/js/store.js').then((m) => (m.S.view ? m.S.view.type + ':' + (m.S.view.path || '') : ''))"
TABS = "() => [...document.querySelectorAll('#lec-doctab-list .doc-tab')].map((e) => e.querySelector('.name').textContent + (e.classList.contains('active') ? '*' : ''))"
TOAST = "() => { const e = document.querySelector('#lec-toast'); return e && !e.hidden ? e.textContent : ''; }"
BOXES = "() => [...document.querySelectorAll('#lec-basket-list .bk-box')].map((e) => e.querySelector('.label').textContent + ' ' + e.querySelector('.n')?.textContent + (e.classList.contains('cur') ? '*' : ''))"
ITEMS = "() => [...document.querySelectorAll('#lec-basket-list .bk-item .pt-name')].map((e) => e.textContent)"
CARDS = """() => [...document.querySelectorAll('#lec-view .cb-card')].map((e) => ({ n: e.querySelector('.cb-n').textContent, title: e.querySelector('.cb-name').value, hold: e.querySelector('.cb-name').placeholder,
  src: e.querySelector('.cb-go')?.textContent || '', state: e.querySelector('.cb-state').hidden ? '' : e.querySelector('.cb-state').textContent, memo: e.querySelector('.cb-memo').value,
  text: e.querySelector('.pv-body.md-body')?.innerText || '', table: e.querySelectorAll('.pv-body table').length }))"""
PASTED = "() => window.__pasted || []"


def files():
    return sorted(p.name for p in CLIPS.glob('*.md')) if CLIPS.exists() else []


def src(name):
    for _ in range(20):   # 저장은 파일을 바꿔 끼운다 — 그 순간에는 잠깐 없다
        try:
            return (CLIPS / name).read_text(encoding='utf-8')
        except OSError:
            time.sleep(0.03)
    return ''


try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 1360, 'height': 900}, permissions=['clipboard-read', 'clipboard-write'])
        page = ctx.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.on('dialog', lambda d: d.accept())

        def start():
            page.goto(url)
            page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
            page.evaluate("() => import('/static/js/store.js').then((m) => { window.__pasted = []; m.on('term-paste', (d) => window.__pasted.push(typeof d === 'string' ? d : d.text)); })")

        def view():
            return page.evaluate(VIEW)

        def tabs():
            return page.evaluate(TABS)

        def boxes():
            return page.evaluate(BOXES)

        def cards():
            return page.evaluate(CARDS)

        def open_doc(path, head):
            page.evaluate(OPEN, path)
            page.wait_for_selector(f'#lec-view h1:has-text("{head}")', timeout=20000)
            page.wait_for_timeout(150)

        def take(sel, label='담기'):
            page.locator(sel).first.click(button='right')
            page.wait_for_selector('#lec-menu:not([hidden])')
            page.locator('#lec-menu button[data-i]', has_text=label).first.click()

        def side(name):
            page.click(f'.side-tabs button[data-tab="{name}"]')

        start()
        print('[처음 담기]')
        side('basket')
        expect(page, '담은 것이 없다 — 파일도 폴더도 만들지 않는다', lambda: '담은 것이 없습니다' in page.inner_text('#lec-basket-info') and not (proj / '.lectern').exists(), lambda: page.inner_text('#lec-basket-info'))
        open_doc('조사/가격.md', '가격 동향')
        take('#lec-view table')
        expect(page, "담기함 '담기함' 이 저절로 하나 생기고 거기에", lambda: boxes() == ['담기함 1*'] and files() == ['담기함.md'], lambda: (boxes(), files()))
        check('알림에 담기함의 이름과 개수', "'담기함' (1개)" in page.evaluate(TOAST), page.evaluate(TOAST))
        expect(page, '파일에 캡션·표·자료 줄과 담은 곳', lambda: '표 1. 구리 분기별 가격\n\n| 분기 | 가격 |' in src('담기함.md') and '자료: LME' in src('담기함.md') and 'path=%EC%A1%B0%EC%82%AC%2F%EA%B0%80%EA%B2%A9.md line=7 end=14' in src('담기함.md'), lambda: src('담기함.md'))
        check('트리에는 나오지 않는다', '.lectern' not in page.inner_text('#lec-tree') and page.locator('#lec-tree [data-doc*=".lectern"]').count() == 0)

        print('[Alt+C]')
        page.locator('#lec-view p', has_text='머리 문단').click()
        page.keyboard.press('Alt+c')
        expect(page, '현재 줄의 블록 (문단)', lambda: page.evaluate(ITEMS)[-1].startswith('머리 문단입니다'), lambda: page.evaluate(ITEMS))
        page.locator('#lec-view .lec-caption', has_text='구리 분기별').click()
        page.keyboard.press('Alt+c')
        expect(page, '캡션 줄에서는 그 표를 캡션·자료째', lambda: page.evaluate(ITEMS)[2:] == ['표 1. 구리 분기별 가격'], lambda: page.evaluate(ITEMS))
        page.locator('#lec-view td', has_text='9,480').click()
        page.keyboard.press('Alt+c')
        expect(page, '표의 칸에서도 표 통째', lambda: len(page.evaluate(ITEMS)) == 4 and page.evaluate(ITEMS)[3] == '표 1. 구리 분기별 가격', lambda: page.evaluate(ITEMS))
        page.locator('#lec-view h2', has_text='분기별 가격').click()
        page.keyboard.press('Alt+c')
        expect(page, '제목에서는 그 절 (각주 정의까지)', lambda: page.evaluate(ITEMS)[4:] == ['분기별 가격'] and '<!-- lectern-clip-notes -->\n[^1]: LME 2분기 자료.' in src('담기함.md'), lambda: (page.evaluate(ITEMS), src('담기함.md')[-300:]))
        page.locator('#lec-view li', has_text='목록 하나').click()
        page.keyboard.press('Shift+ArrowDown')
        page.keyboard.press('Alt+c')
        expect(page, '고른 줄은 그 줄들', lambda: len(page.evaluate(ITEMS)) == 6 and '- 목록 하나\n- 목록 둘\n<!-- /lectern-clip -->' in src('담기함.md'), lambda: page.evaluate(ITEMS))
        page.keyboard.press('Escape')
        page.locator('#lec-view strong', has_text='굵은').dblclick(position={'x': 8, 'y': 8})
        page.keyboard.press('Alt+c')
        expect(page, '고른 글은 보이는 글 그대로', lambda: len(page.evaluate(ITEMS)) == 7 and 'plain=1' in src('담기함.md'), lambda: page.evaluate(ITEMS))
        page.keyboard.press('Escape')
        page.locator('#lec-view img').scroll_into_view_if_needed()
        n0 = len(page.evaluate(ITEMS))
        page.locator('#lec-filter').evaluate("e => e.closest('.side-filter').hidden")
        page.focus('#lec-basket-new')
        page.keyboard.press('Alt+c')
        page.wait_for_timeout(300)
        check('초점이 사이드바에 있으면 담지 않는다', len(page.evaluate(ITEMS)) == n0, page.evaluate(ITEMS))

        print('[담기함 여럿]')
        page.click('#lec-basket-new')
        check('이름을 묻는 칸에 초점', page.evaluate("() => document.activeElement.id") == 'lec-basket-name')
        page.keyboard.press('Escape')
        check('Esc 는 그만두기 — 만들지 않는다', page.locator('#lec-basket-ask').is_hidden() and files() == ['담기함.md'])
        page.click('#lec-basket-new')
        page.keyboard.type('구리 가격: 전망?')
        page.keyboard.press('Enter')
        expect(page, '새 담기함이 지금 담기함이 된다', lambda: sorted(boxes()) == ['구리 가격: 전망? 0*', '담기함 7'] and files() == ['구리-가격-전망.md', '담기함.md'], lambda: (boxes(), files()))
        take('#lec-view img[alt="아이콘"]')
        expect(page, '담으면 거기에', lambda: '구리 가격: 전망? 1*' in boxes() and page.inner_text('#lec-basket-count') == '1', boxes)
        take('#lec-view table', '다른 담기함에 담기')
        page.wait_for_selector('#lec-menu:not([hidden])')
        check('다른 담기함을 고르는 메뉴 — 지금 담기함 표시', page.evaluate("() => [...document.querySelectorAll('#lec-menu button[data-i] span')].map((e) => e.textContent)")[:1] == ['구리 가격: 전망?'] and '새 담기함…' in page.inner_text('#lec-menu'), page.inner_text('#lec-menu'))
        page.locator('#lec-menu button[data-i]').nth(1).click()   # 담기함
        expect(page, '고른 담기함에 담기고 지금 담기함은 그대로', lambda: sorted(boxes()) == ['구리 가격: 전망? 1*', '담기함 8'], boxes)
        take('#lec-view table', '다른 담기함에 담기')
        page.wait_for_selector('#lec-menu:not([hidden])')
        page.locator('#lec-menu button[data-i]', has_text='새 담기함').click()
        page.wait_for_selector('#lec-basket-ask:not([hidden])')
        page.keyboard.type('셋째')
        page.keyboard.press('Enter')
        expect(page, '메뉴에서 새 담기함을 만들어 담는다', lambda: '셋째 1*' in boxes(), boxes)
        page.locator('#lec-basket-list .bk-box', has_text='구리 가격').click()
        expect(page, '머리줄을 누르면 지금 담기함이 바뀌어 펼쳐진다', lambda: '구리 가격: 전망? 1*' in boxes() and page.evaluate(ITEMS) == ['그림 1. 아이콘'], lambda: (boxes(), page.evaluate(ITEMS)))

        print('[펼쳐 보기]')
        page.locator('#lec-basket-list .bk-box .label', has_text='담기함').last.click()
        page.click('#lec-basket-open')
        page.wait_for_selector('#lec-view.clips-view .cb-card', timeout=15000)
        expect(page, '보던 문서를 두고 새 문서 탭에 — 탭 이름은 담기함의 제목', lambda: tabs() == ['가격.md', '담기함*'] and view() == 'clips:담기함.md', lambda: (tabs(), view()))
        expect(page, '담은 여덟이 차례대로', lambda: [c['n'] for c in cards()] == [str(i) for i in range(1, 9)], cards)
        first = cards()[0]
        check('표가 실제 모습으로 — 캡션·자료, 담은 곳', first['table'] == 1 and '9,480' in first['text'] and '자료: LME' in first['text'] and first['src'] == '조사/가격.md 7~14행' and first['hold'] == '표 1. 구리 분기별 가격', first)
        check('문단의 서식도', page.locator('#lec-view .cb-card').nth(1).locator('.pv-body strong', has_text='굵은 말').count() == 1)
        check('목차 패널에 담은 것의 차례', page.locator('#lec-toc a[data-i]').count() == 8 and page.inner_text('#lec-toc .toc-head') == '담기함', page.inner_text('#lec-toc'))
        check('상태줄', page.inner_text('#lec-st-path') == '담기함 — 담기함', page.inner_text('#lec-st-path'))
        page.locator('#lec-view .cb-card').last.scroll_into_view_if_needed()
        page.locator('#lec-view .cb-card').nth(4).scroll_into_view_if_needed()
        expect(page, '절도 제목·표·각주째', lambda: cards()[4]['table'] == 1 and 'LME 2분기 자료' in cards()[4]['text'], lambda: cards()[4])
        check('모두 원래 문서 그대로 — 알림 없음', all(not c['state'] for c in cards()), [c['state'] for c in cards()])
        page.locator('#lec-view .cb-card').first.scroll_into_view_if_needed()

        print('[제목과 메모]')
        page.locator('#lec-view .cb-name').first.click()
        page.keyboard.type('재고가 줄었다')
        page.keyboard.press('Enter')
        check('제목에서 Enter 는 메모로', page.evaluate("() => document.activeElement.className") == 'cb-memo')
        page.keyboard.type('가격과 시점이 겹침')
        page.keyboard.press('Enter')
        page.keyboard.type('원인인지는 모름')
        expect(page, '쓰는 대로 저장된다 (초점은 그대로)', lambda: '## 재고가 줄었다\n가격과 시점이 겹침\n원인인지는 모름\n<!-- lectern-clip-text -->' in src('담기함.md') and page.evaluate("() => document.activeElement.className") == 'cb-memo', lambda: src('담기함.md')[:600])
        expect(page, '사이드바에도 제목과 메모', lambda: page.evaluate(ITEMS)[0] == '재고가 줄었다' and '가격과 시점' in page.inner_text('#lec-basket-list .bk-memo'), lambda: page.evaluate(ITEMS))
        page.keyboard.press('Escape')
        check('Esc 는 카드로 — 글은 남는다', page.evaluate("() => document.activeElement.classList.contains('cb-card')") and cards()[0]['memo'].startswith('가격과'))
        page.fill('#lec-view .cb-title', '첫 조사')
        page.fill('#lec-view .cb-note', '질문: 왜 올랐나\n둘째 줄')
        expect(page, '담기함의 제목과 설명 — 탭·사이드바도 (파일 이름은 그대로)', lambda: tabs()[-1] == '첫 조사*' and '첫 조사 8*' in boxes() and '# 첫 조사\n\n질문: 왜 올랐나\n둘째 줄\n' in src('담기함.md'), lambda: (tabs(), boxes(), src('담기함.md')[:260]))

        print('[차례·빼기·되돌리기]')
        ids = lambda: page.evaluate("() => [...document.querySelectorAll('#lec-view .cb-card')].map((e) => e.dataset.id)")  # noqa: E731
        was = ids()
        page.locator('#lec-view .cb-card').first.focus()
        page.keyboard.press('Alt+ArrowDown')
        expect(page, 'Alt+↓ 로 아래로 — 초점은 그 카드에', lambda: ids() == [was[1], was[0], *was[2:]] and page.evaluate("() => document.activeElement.dataset.id") == was[0], ids)
        page.locator('#lec-view .cb-card').nth(1).locator('[data-act="up"]').click()
        expect(page, '단추로 위로', lambda: ids() == was, ids)
        page.locator('#lec-view .cb-card').nth(6).focus()
        page.keyboard.press('Delete')
        expect(page, 'Delete 로 빼기 — 다음 카드에 초점', lambda: len(ids()) == 7 and page.evaluate("() => document.activeElement.dataset.id") == was[7], ids)
        page.click('#lec-view [data-act="undo"]')
        expect(page, '되돌리기는 그 자리로', lambda: ids() == was and page.locator('#lec-view .cb-undo').is_hidden(), ids)
        expect(page, '— 파일에도 그 차례로', lambda: [i for i in was if f'id={i}' in src('담기함.md')] == was and src('담기함.md').index(f'id={was[6]}') < src('담기함.md').index(f'id={was[7]}'))
        page.locator('#lec-view .cb-memo').first.focus()
        page.keyboard.press('End')
        page.keyboard.press('Delete')
        page.wait_for_timeout(200)
        check('글 칸의 Delete 는 글만', len(ids()) == 8)

        print('[원래 자리로]')
        page.locator('#lec-view .cb-go').first.click()
        page.wait_for_selector('#lec-view h1:has-text("가격 동향")', timeout=15000)
        expect(page, '출처 줄은 다른 탭에 열린 그 문서의 그 자리로', lambda: tabs() == ['가격.md*', '첫 조사'], tabs)
        page.locator('#lec-doctab-list .doc-tab', has_text='첫 조사').click()
        page.wait_for_selector('#lec-view.clips-view .cb-card')
        page.locator('#lec-doctab-list .doc-tab', has_text='가격.md').click(button='middle')
        expect(page, '가격 탭을 닫고', lambda: tabs() == ['첫 조사*'], tabs)
        page.locator('#lec-view .cb-card').nth(1).focus()
        page.keyboard.press('Enter')
        page.wait_for_selector('#lec-view h1:has-text("가격 동향")', timeout=15000)
        page.keyboard.press('Alt+ArrowLeft')
        page.wait_for_selector('#lec-view.clips-view .cb-card', timeout=15000)
        expect(page, 'Enter 로 이 탭에서 갔다가 Alt+← 로 돌아온다', lambda: tabs() == ['첫 조사*'] and len(ids()) == 8, tabs)
        page.locator('#lec-view .cb-go').first.click(modifiers=['Control'])
        expect(page, 'Ctrl+누르기는 뒤에서 새 문서 탭', lambda: tabs() == ['첫 조사*', '가격.md'], tabs)

        print('[원래 문서가 바뀜]')
        time.sleep(0.3)
        put('조사/가격.md', PRICE.replace('머리 문단입니다.', '새 문단을 더했습니다.\n\n머리 문단입니다.'))
        page.wait_for_timeout(2500)
        check('줄이 밀리기만 하면 알리지 않는다', all(not c['state'] for c in cards()), [c['state'] for c in cards()])
        put('조사/가격.md', PRICE.replace('9,480', '9,999').replace('머리 문단입니다.', '새 문단을 더했습니다.\n\n머리 문단입니다.'))
        expect(page, '표의 숫자가 바뀌면 그 표를 담은 조각들에 알린다', lambda: [i for i, c in enumerate(cards()) if c['state'] == '원래 문서가 바뀌었습니다'] == [0, 2, 3, 4, 7], lambda: [c['state'] for c in cards()], ms=15000)
        check('— 담은 내용은 담은 때 그대로', '9,480' in cards()[0]['text'] and '9,999' not in cards()[0]['text'])
        page.locator('#lec-view .cb-go').nth(1).click()
        page.wait_for_selector('#lec-view h1:has-text("가격 동향")', timeout=15000)
        expect(page, '밀린 줄도 지금 있는 자리로 간다', "() => [...document.querySelectorAll('#lec-view .lec-target')].some((e) => e.textContent.startsWith('머리 문단'))")
        page.locator('#lec-doctab-list .doc-tab', has_text='첫 조사').click()
        page.wait_for_selector('#lec-view.clips-view .cb-card')
        page.evaluate("""async () => { const { S } = await import('/static/js/store.js'); await fetch('/api/rename', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ p: S.tab.id, path: '보고.md', name: '보고2.md' }) }); }""")
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('rename', { path: '조사/가격.md' }))")
        page.wait_for_selector('#lec-rename:not([hidden])')
        page.fill('#lec-rename-input', '가격-동향.md')
        page.keyboard.press('Enter')
        expect(page, 'Lectern 에서 이름을 바꾸면 담은 곳도 따라간다', lambda: len(cards()) == 8 and all(c['src'].startswith('조사/가격-동향.md') for c in cards()) and src('담기함.md').count('%EA%B0%80%EA%B2%A9-') == 8, lambda: [c['src'] for c in cards()], ms=15000)
        (proj / '조사' / '가격-동향.md').rename(proj / '조사' / '옮김.md')
        expect(page, '밖에서 없어지면 없다고 알린다', lambda: all(c['state'] == '원래 문서가 없습니다' for c in cards()), lambda: [c['state'] for c in cards()], ms=15000)
        (proj / '조사' / '옮김.md').rename(proj / '조사' / '가격-동향.md')
        expect(page, '돌아오면 알림도 걷힌다', lambda: cards()[1]['state'] == '', lambda: [c['state'] for c in cards()], ms=15000)

        print('[옮기기·복사]')
        page.locator('#lec-view .cb-card').nth(1).locator('.cb-src').click(button='right', position={'x': 400, 'y': 6})
        page.locator('#lec-menu button[data-i]', has_text='다른 담기함으로 옮기기').click()
        page.wait_for_selector('#lec-menu:not([hidden])')
        page.locator('#lec-menu button[data-i]', has_text='셋째').click()
        expect(page, '옮기면 여기서 빠지고 거기에', lambda: len(ids()) == 7 and '셋째 2' in boxes() and was[1] not in src('담기함.md'), boxes)
        page.locator('#lec-view .cb-card').first.locator('.cb-src').click(button='right', position={'x': 400, 'y': 6})
        page.locator('#lec-menu button[data-i]', has_text='다른 담기함에 복사').click()
        page.wait_for_selector('#lec-menu:not([hidden])')
        page.locator('#lec-menu button[data-i]', has_text='셋째').click()
        expect(page, '복사하면 둘 다에 — 제목과 메모째', lambda: len(ids()) == 7 and '셋째 3' in boxes() and '## 재고가 줄었다' in src('셋째.md'), boxes)

        print('[AI 에 맡기기]')
        page.click('#lec-view [data-act="ai"]')
        page.wait_for_selector('#lec-menu:not([hidden]) .menu-term')
        page.locator('#lec-menu .menu-term').first.click()
        expect(page, '위치들과 담기함 파일을 한 줄로 — Enter 없이', lambda: len(page.evaluate(PASTED)) == 1 and "@조사/가격-동향.md 7~14행 ('재고가 줄었다')" in page.evaluate(PASTED)[0] and '@.lectern/clips/담기함.md' in page.evaluate(PASTED)[0] and '\n' not in page.evaluate(PASTED)[0], lambda: page.evaluate(PASTED))
        page.click('#lec-btn-term')

        print('[문서로 보내기]')
        page.click('#lec-view [data-act="send"]')
        page.wait_for_selector('#lec-insert:not([hidden]) li.ins-new')
        page.click('#lec-insert-list li.ins-new')
        check('새 문서의 이름은 담기함의 제목', page.input_value('#lec-insert-input') == '첫 조사.md', page.input_value('#lec-insert-input'))
        page.keyboard.press('Enter')
        sent = proj / '첫 조사.md'
        until(page, lambda: sent.exists() and '담은 곳' in sent.read_text(encoding='utf-8'), 10000)
        text = sent.read_text(encoding='utf-8') if sent.exists() else ''
        check('제목은 제목으로, 메모는 인용으로, 경로는 새 문서 기준', '## 재고가 줄었다\n\n표 1. 구리 분기별 가격' in text and '> 메모: 가격과 시점이 겹침\n> 원인인지는 모름' in text and '### 분기별 가격' not in text.split('## 재고가')[0], text[:600])
        check('제목을 달지 않은 절은 전처럼 문서 제목 아래 수준으로', '\n## 분기별 가격\n' in text, text[-700:])
        page.wait_for_selector('#lec-view h1:has-text("첫 조사")', timeout=15000)
        check('담은 것은 남는다', '첫 조사 7*' in boxes(), boxes())
        page.keyboard.press('Control+w')
        page.locator('#lec-doctab-list .doc-tab', has_text='첫 조사').first.click()
        page.wait_for_selector('#lec-view.clips-view .cb-card')

        print('[밖에서 고친 파일 — Claude Code·다른 창]')
        body = src('담기함.md')
        page.locator('#lec-view .cb-memo').nth(1).fill('내가 쓰는 중')
        (CLIPS / '담기함.md').write_text(body + '\n<!-- lectern-clip id=ai1 path=%EB%B3%B4%EA%B3%A02.md line=3 -->\n## AI 가 담음\n<!-- lectern-clip-text -->\n## 결론\n<!-- /lectern-clip -->\n', encoding='utf-8')
        expect(page, '쓰던 메모와 밖에서 더한 조각이 함께 남는다', lambda: '내가 쓰는 중' in src('담기함.md') and 'id=ai1' in src('담기함.md') and [c['title'] for c in cards()][-1] == 'AI 가 담음', lambda: ([c['title'] for c in cards()], src('담기함.md')[-400:]), ms=15000)
        (CLIPS / '담기함.md').write_text(src('담기함.md').replace('## AI 가 담음', '## AI 가 고침'), encoding='utf-8')
        page.evaluate("() => window.dispatchEvent(new Event('focus'))")
        expect(page, '고치지 않는 동안 밖에서 바뀌면 창으로 돌아올 때 보인다', lambda: [c['title'] for c in cards()][-1] == 'AI 가 고침', lambda: [c['title'] for c in cards()], ms=8000)
        (CLIPS / '나쁜.md').write_bytes(b'\xb0\xa1\xb3\xaa')
        (CLIPS / '손.md').write_text('# 손으로\n\n<!-- lectern-clip path=..%2F..%2Fx.md line=1 -->\n<!-- lectern-clip-text -->\n밖을 가리킴\n\n<img src="x" onerror="window.__bad=1"> <button class="parts-send" data-act="send">심음</button>\n<!-- /lectern-clip -->\n\n사이에 쓴 글\n', encoding='utf-8')
        side('files')
        side('basket')
        expect(page, '읽지 못한 담기함은 그렇다고 — 다른 것은 보인다', lambda: page.locator('.bk-box.bad', has_text='나쁜').count() == 1 and '손으로 2' in boxes(), boxes)
        page.locator('.bk-box', has_text='손으로').locator('.bk-open').click()
        page.wait_for_selector('#lec-view.clips-view .cb-card')
        expect(page, '손으로 쓴 파일: 프로젝트 밖을 가리킨 경로는 버리고, 사이의 글도 조각으로', lambda: [c['src'] for c in cards()] == ['', ''] and '사이에 쓴 글' in cards()[1]['text'], cards)
        page.locator('#lec-view .pv-body button').click()
        page.wait_for_timeout(400)
        check('담은 글이 심은 단추는 앱의 단추로 읽지 않고, 스크립트는 돌지 않는다', page.locator('#lec-insert').is_hidden() and not page.evaluate('() => window.__bad'))

        print('[문서가 심은 것]')
        open_doc('심은.md', '심은 문서')
        page.locator('#lec-view h1').click()
        page.keyboard.press('Alt+c')
        page.wait_for_timeout(500)
        page.click('#lec-basket-open')
        page.wait_for_selector('#lec-view.clips-view .cb-card')
        check('이벤트 속성은 남지 않는다', page.locator('#lec-view .pv-body [onclick], #lec-view .pv-body [onerror], #lec-view .pv-body script').count() == 0 and not page.evaluate('() => window.__bad'))

        print('[모아 보기에서]')
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('parts', { path: '조사', kind: 'table' }))")
        page.wait_for_selector('#lec-view.parts-view .pv-done', timeout=20000)
        before = page.inner_text('#lec-basket-count')
        page.locator('#lec-view .pv-chunk').first.focus()
        page.keyboard.press('Alt+c')
        expect(page, '초점이 있는 덩어리를 Alt+C 로', lambda: int(page.inner_text('#lec-basket-count')) == int(before) + 1, lambda: page.inner_text('#lec-basket-count'))
        page.locator('#lec-view .pv-chunk .pv-src').first.click(button='right')
        expect(page, '우클릭에 다른 담기함도', lambda: '다른 담기함에 담기…' in page.inner_text('#lec-menu'))
        page.keyboard.press('Escape')

        print('[다이어그램·그림·다시 켜기]')
        start()
        page.wait_for_timeout(800)
        side('basket')
        expect(page, '다시 켜도 담기함이 그대로', lambda: {'첫 조사 10', '셋째 3'} <= {b.rstrip('*') for b in boxes()}, boxes)
        page.locator('.bk-box', has_text='구리 가격').click()
        open_doc('조사/가격-동향.md', '가격 동향')
        take('#lec-view pre.mermaid')
        expect(page, '다이어그램을 담는다', lambda: '구리 가격: 전망? 2*' in boxes(), boxes)
        page.click('#lec-basket-open')
        page.wait_for_selector('#lec-view.clips-view .cb-card')
        expect(page, '그림이 불러와진다 (원래 문서 기준의 경로)', "() => { const i = document.querySelector('#lec-view .cb-card .pv-body img'); return !!i && i.complete && i.naturalWidth > 0; }", ms=10000)
        expect(page, '다이어그램도 그려진다', "() => !!document.querySelector('#lec-view .cb-card .pv-body pre.mermaid svg')", ms=40000)
        page.keyboard.press('Control+Shift+p')
        page.wait_for_selector('#lec-palette:not([hidden])')
        page.keyboard.type('담기함 펼쳐')
        page.wait_for_timeout(300)
        page.keyboard.press('Enter')
        expect(page, '명령 찾기로도 — 이미 열린 탭으로', lambda: view() == 'clips:구리-가격-전망.md' and tabs().count('구리 가격: 전망?*') == 1 and len([x for x in tabs() if '구리 가격' in x]) == 1, tabs)
        page.click('#lec-doctab-spread')
        expect(page, '모두 펼치기에서도 보인다', "() => document.documentElement.classList.contains('spread-on') && !!document.querySelector('.sp-cell .clips-view .cb-card')")
        page.click('#lec-doctab-spread')
        for width in (1040, 760):
            page.set_viewport_size({'width': width, 'height': 800})
            page.wait_for_timeout(350)
            wide = page.evaluate("""() => { const v = document.querySelector('#lec-content'); const edge = v.getBoundingClientRect().right;
              return [...v.querySelectorAll('*')].filter((e) => !e.closest('.pv-body') && e.getBoundingClientRect().right > edge + 1).map((e) => [e.tagName, String(e.className)]).slice(0, 5); }""")
            check(f'{width}px: 옆으로 넘치지 않는다', not wide, wide)
        page.set_viewport_size({'width': 1360, 'height': 900})

        print('[비우기·지우기]')
        page.locator('.bk-box', has_text='셋째').click(button='right')
        page.locator('#lec-menu button[data-i]', has_text='비우기').click()
        expect(page, '비우기', lambda: '셋째 0' in [x.rstrip('*') for x in boxes()], boxes)
        page.click('#lec-basket-undo button')
        expect(page, '— 되돌린다', lambda: '셋째 3' in [x.rstrip('*') for x in boxes()] and src('셋째.md').count('<!-- /lectern-clip -->') == 3, boxes)
        page.locator('.bk-box', has_text='셋째').click(button='right')
        page.locator('#lec-menu button[data-i]', has_text='담기함 지우기').click()
        expect(page, '담기함 지우기 — 휴지통으로 (이 드라이브에 휴지통이 있을 때)', lambda: '셋째.md' not in files() and not any('셋째' in x for x in boxes()), lambda: (files(), page.evaluate(TOAST)), ms=15000)
        page.locator('#lec-doctab-list .doc-tab.active .name').wait_for()

        print('[보기만 하는 프로젝트]')
        page.evaluate("(dir) => import('/static/js/tabs.js').then((m) => m.openFolder(dir))", str(ROOT / 'samples'))
        until(page, lambda: page.evaluate("() => import('/static/js/store.js').then((m) => m.S.tab?.name)") == 'samples', 20000)
        ro = page.evaluate("() => import('/static/js/store.js').then((m) => !!m.S.tab.readonly)")
        check('예제 폴더는 보기만 (시험의 전제)', ro)
        page.evaluate(OPEN, 'guide/02-읽기-기능.md')
        page.wait_for_selector('#lec-view h1', timeout=20000)
        page.locator('#lec-view p').first.click()
        page.keyboard.press('Alt+c')
        side('basket')
        expect(page, '담기는 되지만 저장하지 않는다고 알린다', lambda: page.inner_text('#lec-basket-count') == '1' and '저장하지 않습니다' in page.inner_text('#lec-basket-info'), lambda: page.inner_text('#lec-basket-info'))
        check('파일을 만들지 않는다', not (ROOT / 'samples' / '.lectern').exists())

        print('[영어]')
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ language: 'en' }))")
        start()
        page.evaluate("() => import('/static/js/tabs.js').then((m) => m.selectTabAt(1))")
        page.wait_for_timeout(800)
        side('basket')
        page.locator('.bk-box', has_text='첫 조사').locator('.bk-open').click()
        page.wait_for_selector('#lec-view.clips-view .cb-card')
        left = page.evaluate("() => (['.cb-kind', '.cb-bar', '.cb-at', '.cb-btns'].map((s) => [...document.querySelectorAll('#lec-view ' + s)].map((e) => e.innerText + [...e.querySelectorAll('[title]')].map((x) => x.title).join(' ')).join(' ')).join(' ') + document.querySelector('.basket-bar').innerText + [...document.querySelectorAll('#lec-view .cb-memo, #lec-view .cb-note')].map((e) => e.placeholder).join(' ')).match(/[가-힣]+/g) || []")
        check('담기함 화면과 사이드바에 남은 한글 없음', not left, left)
        check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
