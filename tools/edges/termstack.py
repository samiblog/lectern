"""터미널 쌓기와 번호로 보내기 (D137): 오른쪽이면 위아래로(1번이 맨 아래, 균등, 경계 끌기·두 번 누르면 균등, 더하고 닫으면 균등),
칸 머리줄로 고르기·닫기, Shift+숫자·Ctrl+Shift+숫자·Shift+→, 없는 번호, 메뉴의 숫자+누르기, 아래 배치는 탭, 터미널 모음에서 돌아옴,
입력 칸과 터미널 안의 Shift+숫자는 글자"""
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-termstack-'))
proj = base / 'proj'
config = base / 'config'
(proj / 'docs').mkdir(parents=True)
(proj / 'docs' / '글.md').write_text('# 글\n\n첫째 문단입니다.\n\n둘째 문단입니다.\n\n셋째 문단입니다.\n', encoding='utf-8')

PANES = """() => [...document.querySelectorAll('#lec-term-body > .term-pane:not([hidden])')].map((p) => ({
  n: +p.dataset.n, h: Math.round(p.getBoundingClientRect().height), on: p.classList.contains('on'),
  box: !p.querySelector('.term-box').hidden, rows: p.querySelector('.xterm-rows')?.children.length || 0 }))"""
STACKED = "() => document.querySelector('#lec-term').classList.contains('stacked')"


def panes(page):
    return page.evaluate(PANES)


def text_of(page, n):
    return page.evaluate("""(n) => [...document.querySelectorAll(`#lec-term-body > .term-pane[data-n="${n}"] .xterm-rows > div`)]
      .map((r) => r.textContent).join('')""", n)


def prompt(page, n, ms=20000):
    return until(page, lambda: 'PS ' in text_of(page, n), ms=ms)


def doc_focus(page, which=0):
    page.locator('#lec-view p').nth(which).click()
    page.wait_for_timeout(150)


def toast(page):
    return page.evaluate("() => document.querySelector('#lec-toast')?.textContent || ''")


def in_term(page):
    return page.evaluate("() => !!document.activeElement?.closest?.('#lec-term')")


def pasted_count(page, n):
    # 줄 끝에 두 칸 글자가 들어가지 않으면 xterm 이 빈칸을 남기고 다음 줄로 감는다 — 빈칸을 빼고 센다
    return ''.join(text_of(page, n).split()).count('@docs/글.md')


server, url, port = serve(proj, config)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1500, 'height': 950})
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: 'docs/글.md' }))")
        page.wait_for_selector('#lec-view h1')
        page.keyboard.press('Control+`')
        prompt(page, 0)

        print('[하나면 지금처럼]')
        check('쌓지 않는다 — 터미널 탭 줄이 보인다', not page.evaluate(STACKED) and page.is_visible('#lec-term-tabs .term-tab'))

        print('[둘 — 위아래로, 1번이 아래]')
        page.click('#lec-term-new')
        expect(page, '쌓는다', STACKED)
        prompt(page, 1)
        ps = panes(page)
        check('차례: 위가 2번, 아래가 1번', [x['n'] for x in ps] == [1, 0], ps)
        check('둘 다 보이고 높이가 같다', all(x['box'] for x in ps) and abs(ps[0]['h'] - ps[1]['h']) <= 2, ps)
        check('터미널 탭 줄은 감춘다', not page.is_visible('#lec-term-tabs'))
        check('새 터미널을 고른다', [x['on'] for x in ps] == [True, False], ps)
        heads = page.evaluate("() => [...document.querySelectorAll('#lec-term-body > .term-pane:not([hidden]) .term-pane-head .n')].map((x) => x.textContent)")
        check('칸 머리줄에 번호', heads == ['2', '1'], heads)

        print('[다섯까지 — 균등]')
        for _ in range(3):
            page.click('#lec-term-new')
        expect(page, '다섯 칸', lambda: len(panes(page)) == 5, lambda: panes(page), ms=15000)
        for n in range(5):
            prompt(page, n)
        ps = panes(page)
        hs = [x['h'] for x in ps]
        check('차례 5·4·3·2·1', [x['n'] for x in ps] == [4, 3, 2, 1, 0], ps)
        check('높이가 같다 (±2px)', max(hs) - min(hs) <= 2 and min(hs) >= 72, hs)
        check('칸마다 셸 화면이 칸 높이에 맞는다', all(x['rows'] >= 3 for x in ps), ps)
        check('+ 가 꺼진다', page.evaluate("() => document.querySelector('#lec-term-new').disabled"))

        print('[경계 끌기]')
        split = page.locator('#lec-term-body > .term-split').first
        box = split.bounding_box()
        rows_before = panes(page)
        page.mouse.move(box['x'] + box['width'] / 2, box['y'] + 2)
        page.mouse.down()
        page.mouse.move(box['x'] + box['width'] / 2, box['y'] + 80, steps=8)
        page.mouse.up()
        page.wait_for_timeout(400)
        ps = panes(page)
        check('위 칸이 80px 커지고 바로 아래 칸이 그만큼 준다',
              abs(ps[0]['h'] - rows_before[0]['h'] - 80) <= 3 and abs(rows_before[1]['h'] - ps[1]['h'] - 80) <= 3, (rows_before, ps))
        check('나머지 칸은 그대로', all(abs(a['h'] - b['h']) <= 2 for a, b in zip(ps[2:], rows_before[2:])), ps)
        check('커진 칸의 셸 줄 수도 늘어난다', ps[0]['rows'] > rows_before[0]['rows'], (rows_before[0], ps[0]))
        page.mouse.move(box['x'] + box['width'] / 2, box['y'] + 2)
        page.mouse.down()
        page.mouse.move(box['x'] + box['width'] / 2, box['y'] + 2000, steps=6)
        page.mouse.up()
        page.wait_for_timeout(300)
        ps = panes(page)
        check('끝까지 끌어도 아래 칸은 최소 높이', ps[1]['h'] >= 70, ps)
        page.locator('#lec-term-body > .term-split').nth(2).dblclick()
        page.wait_for_timeout(300)
        hs = [x['h'] for x in panes(page)]
        check('경계를 두 번 누르면 균등', max(hs) - min(hs) <= 2, hs)

        print('[도는 프로그램이 있는 칸의 × 는 묻는다]')
        asked = []
        answer = {'ok': False}
        page.on('dialog', lambda d: (asked.append(d.message), d.accept() if answer['ok'] else d.dismiss()))
        page.locator('#lec-term-body > .term-pane[data-n="4"] .term-pane-head').click(position={'x': 60, 'y': 10})
        page.keyboard.type('ping -t 127.0.0.1')
        page.keyboard.press('Enter')
        until(page, lambda: '127.0.0.1' in text_of(page, 4)[-300:] and ('Reply' in text_of(page, 4) or '응답' in text_of(page, 4)), ms=15000)
        page.wait_for_timeout(1200)
        page.locator('#lec-term-body > .term-pane[data-n="4"] .term-pane-head [data-close]').click()
        expect(page, '묻는다 (5번 터미널에서 프로그램이 실행 중)', lambda: any('5번 터미널' in m and '실행 중' in m for m in asked), lambda: asked)
        page.wait_for_timeout(500)
        check('그만두면 칸이 그대로', len(panes(page)) == 5, panes(page))
        answer['ok'] = True
        page.locator('#lec-term-body > .term-pane[data-n="4"] .term-pane-head [data-close]').click()
        expect(page, '끝내면 넷', lambda: len(panes(page)) == 4, ms=8000)
        page.click('#lec-term-new')
        expect(page, '다시 다섯', lambda: len(panes(page)) == 5, ms=8000)
        prompt(page, 4)

        print('[칸 머리줄 — 고르기·닫기, 닫으면 균등, 빈 번호로 다시]')
        page.locator('#lec-term-body > .term-pane[data-n="2"] .term-pane-head').click(position={'x': 60, 'y': 10})
        on = [x['n'] for x in panes(page) if x['on']]
        check('머리줄을 누르면 그 터미널을 고른다', on == [2] and in_term(page), on)
        split = page.locator('#lec-term-body > .term-split').first
        box = split.bounding_box()
        page.mouse.move(box['x'] + 30, box['y'] + 2)
        page.mouse.down()
        page.mouse.move(box['x'] + 30, box['y'] + 60, steps=4)
        page.mouse.up()
        page.hover('#lec-term-body > .term-pane[data-n="2"] .term-pane-head')
        page.locator('#lec-term-body > .term-pane[data-n="2"] .term-pane-head [data-close]').click()
        expect(page, '3번을 닫으면 넷', lambda: len(panes(page)) == 4, ms=8000)
        ps = panes(page)
        hs = [x['h'] for x in ps]
        check('닫으면 균등, 차례 5·4·2·1', [x['n'] for x in ps] == [4, 3, 1, 0] and max(hs) - min(hs) <= 2, ps)
        page.click('#lec-term-new')
        expect(page, '다시 + 하면 3번이 가운데로', lambda: [x['n'] for x in panes(page)] == [4, 3, 2, 1, 0], lambda: panes(page), ms=8000)
        prompt(page, 2)

        print('[Shift+숫자로 보내기]')
        doc_focus(page, 1)
        page.keyboard.press('Shift+Digit3')
        expect(page, 'Shift+3 → 3번 터미널에 위치', lambda: pasted_count(page, 2) == 1, lambda: [pasted_count(page, n) for n in range(5)])
        check('다른 터미널에는 없다', [pasted_count(page, n) for n in (0, 1, 3, 4)] == [0, 0, 0, 0])
        check("알림 '3번 터미널에 넣었습니다'", '3번 터미널에 넣었습니다' in toast(page), toast(page))
        check('초점은 터미널로', in_term(page))
        check('넣은 터미널을 고른다', [x['n'] for x in panes(page) if x['on']] == [2])
        doc_focus(page, 2)
        page.keyboard.press('Control+Shift+Digit2')
        expect(page, 'Ctrl+Shift+2 → 2번 터미널', lambda: pasted_count(page, 1) == 1)
        check('초점은 문서에 남는다', not in_term(page))
        page.keyboard.press('Control+Shift+Digit5')
        expect(page, '이어서 Ctrl+Shift+5 → 5번', lambda: pasted_count(page, 4) == 1)
        doc_focus(page, 0)
        page.keyboard.press('Shift+ArrowRight')
        expect(page, 'Shift+→ 는 1번(맨 아래)', lambda: pasted_count(page, 0) == 1)
        check('지금까지 각 터미널에 하나씩', [pasted_count(page, n) for n in range(5)] == [1, 1, 1, 0, 1], [pasted_count(page, n) for n in range(5)])

        print('[없는 번호]')
        page.hover('#lec-term-body > .term-pane[data-n="3"] .term-pane-head')   # 고르지 않은 칸의 × 는 마우스를 올릴 때 보인다
        page.locator('#lec-term-body > .term-pane[data-n="3"] .term-pane-head [data-close]').click()
        expect(page, '4번을 닫음', lambda: len(panes(page)) == 4, ms=8000)
        doc_focus(page, 0)
        page.keyboard.press('Shift+Digit4')
        expect(page, "'4번 터미널이 없습니다' 알림", lambda: '4번 터미널이 없습니다' in toast(page))
        check('아무 데도 넣지 않는다', [pasted_count(page, n) for n in (0, 1, 2, 4)] == [1, 1, 1, 1])
        page.click('#lec-term-close')
        doc_focus(page, 0)
        page.keyboard.press('Shift+Digit4')
        page.wait_for_timeout(500)
        check('패널이 닫혀 있으면 없는 번호로 열지 않는다', page.evaluate("() => document.querySelector('#lec-term').hidden"))
        page.keyboard.press('Shift+Digit2')
        expect(page, '있는 번호면 패널을 열고 넣는다', lambda: not page.evaluate("() => document.querySelector('#lec-term').hidden") and pasted_count(page, 1) == 2)

        print('[메뉴의 숫자+누르기]')
        page.locator('#lec-view p').nth(1).click(button='right')
        page.wait_for_selector('#lec-menu:not([hidden])')
        has_term = page.locator('#lec-menu .menu-term').count()
        check('메뉴에 터미널 단추', has_term > 0, has_term)
        page.keyboard.down('Digit5')
        expect(page, "숫자를 누르고 있으면 '→ 5번 터미널'", "() => document.querySelector('#lec-menu').classList.contains('term-held') && document.querySelector('#lec-menu').dataset.termHeld.includes('5')")
        page.locator('#lec-menu .menu-term').first.click()
        page.keyboard.up('Digit5')
        expect(page, '5 를 누른 채 누르면 5번 터미널로', lambda: '둘째 문단입니다.' in text_of(page, 4))
        check('1번에는 없다', '둘째 문단입니다.' not in text_of(page, 0))
        page.locator('#lec-view p').nth(2).click(button='right')
        page.wait_for_selector('#lec-menu:not([hidden])')
        check('숫자를 떼면 표시가 없다', not page.evaluate("() => document.querySelector('#lec-menu').classList.contains('term-held')"))
        page.locator('#lec-menu .menu-term').first.click()
        expect(page, '그냥 누르면 1번(맨 앞)', lambda: '셋째 문단입니다.' in text_of(page, 0))
        # 고른 줄의 'Claude로 보내기' (메뉴 항목이 곧바로 보내는 글도 숫자를 따른다)
        doc_focus(page, 2)
        page.keyboard.press('Insert')
        box = page.locator('#lec-view p').nth(2).bounding_box()
        page.mouse.click(box['x'] + 20, box['y'] + box['height'] / 2, button='right')
        page.wait_for_selector('#lec-menu:not([hidden])')
        page.keyboard.down('Digit2')
        before2 = pasted_count(page, 1)
        page.locator('#lec-menu button', has_text='Claude로 보내기').first.click()
        page.keyboard.up('Digit2')
        expect(page, "'Claude로 보내기'도 숫자를 누른 채면 2번으로", lambda: pasted_count(page, 1) == before2 + 1)
        page.keyboard.press('Escape')
        doc_focus(page, 0)
        page.keyboard.press('Shift+ArrowRight')
        expect(page, '다음 Shift+→ 는 다시 1번 (숫자는 한 번만)', lambda: pasted_count(page, 0) == 2, lambda: [pasted_count(page, n) for n in range(5)])

        print('[아래에 두면 탭]')
        page.click('#lec-term-place')
        expect(page, '아래 — 쌓지 않는다', f"() => document.documentElement.classList.contains('term-bottom') && !({STACKED})()")
        ps = panes(page)
        check('보이는 칸은 하나, 탭 줄이 보인다', len(ps) == 1 and page.is_visible('#lec-term-tabs'), ps)
        check('보이는 상자도 하나', page.evaluate("() => document.querySelectorAll('#lec-term .term-box:not([hidden])').length") == 1)
        doc_focus(page, 1)
        page.keyboard.press('Shift+Digit5')
        expect(page, 'Shift+5 → 5번 탭으로 바꿔 넣는다', lambda: [x['n'] for x in panes(page)] == [4] and text_of(page, 4).count('@docs/') == 2,
               lambda: (panes(page), text_of(page, 4)[-200:]))
        check('탭 줄의 5번이 골라짐', page.evaluate("() => document.querySelector('#lec-term-tabs .term-tab.on')?.dataset.n") == '4')
        page.click('#lec-term-place')
        expect(page, '오른쪽으로 — 다시 쌓는다', lambda: page.evaluate(STACKED) and len(panes(page)) == 4)
        hs = [x['h'] for x in panes(page)]
        check('균등 그대로', max(hs) - min(hs) <= 2, hs)

        print('[터미널 모음에서 돌아옴]')
        page.keyboard.press('Control+Shift+`')
        page.wait_for_selector('#lec-gather:not([hidden]) .g-tile .term-box:not([hidden])', timeout=10000)
        page.keyboard.press('Control+Shift+`')
        expect(page, '닫으면 제 칸으로 — 넷이 모두 보이고 차례 그대로',
               lambda: [x['n'] for x in panes(page)] == [4, 2, 1, 0] and all(x['box'] for x in panes(page)), lambda: panes(page), ms=8000)
        check('모든 상자가 제 칸 안에', page.evaluate("() => [...document.querySelectorAll('#lec-term-body > .term-pane')].every((p) => p.querySelector(':scope > .term-pane-body > .term-box'))"))

        print('[입력 칸과 터미널 안의 Shift+숫자는 글자]')
        # 화면 글자는 칸 크기가 바뀔 때 다시 감겨 세기가 흔들린다 — 보내기 이벤트 자체를 센다
        page.evaluate('''() => import('/static/js/store.js').then((m) => { window.__sent = 0;
          m.on('term-paste', () => { window.__sent += 1; }); m.on('term-paste-stay', () => { window.__sent += 1; }); })''')
        sent = lambda: page.evaluate('() => window.__sent')
        doc_focus(page, 0)
        page.keyboard.press('F2')
        page.wait_for_selector('#lec-view .lec-line-edit', timeout=5000)
        page.keyboard.press('End')
        page.keyboard.press('Shift+Digit1')
        typed = page.evaluate("() => document.querySelector('#lec-view .lec-line-edit')?.textContent || ''")
        check("한 줄 편집 칸에서는 '!'", typed.endswith('!'), typed)
        page.keyboard.press('Escape')
        page.wait_for_timeout(300)
        check('터미널에 보내지 않는다', sent() == 0, sent())
        page.locator('#lec-term-body > .term-pane[data-n="1"] .term-pane-head').click(position={'x': 60, 'y': 10})
        page.keyboard.press('Control+c')
        page.wait_for_timeout(300)
        page.keyboard.type('#')
        page.keyboard.press('Shift+Digit1')
        expect(page, "터미널 안에서는 셸에 '!'", lambda: '#!' in text_of(page, 1))
        check('보낸 것은 없다', sent() == 0, sent())
        check('저장 안 됨 — 문서 그대로', (proj / 'docs' / '글.md').read_text(encoding='utf-8').count('!') == 0)
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
