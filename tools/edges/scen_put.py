"""시나리오 — 넣기 창과 설정 창을 여러 화면에서 (D154): 손으로 고친 설정 파일(없는 이름·없는 분류), 최근 넣은 것의 차례와 다섯 개,
마우스로 고르기, 맞는 것이 없을 때, 끝에 줄바꿈이 없는 문서, 좁은 창(목록으로), 어두운 스타일의 글자 대비, vi 키(/ 는 찾기 — 넣기는 단추와 Ctrl+Shift+/),
설정 창의 내리면 따라오는 분류·켜고 끄기·열려 있을 때 다른 분류로, 영어 화면."""
import json
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop

base = Path(tempfile.mkdtemp(prefix='lec-scenput-'))
proj = base / 'proj'
proj.mkdir(parents=True)
DOC = '# 보고서\n\n첫 문단이다.\n\n둘째 문단이다.\n'
doc = proj / 'a.md'
doc.write_text(DOC, encoding='utf-8')
tail = proj / 'b.md'
tail.write_bytes('# 끝\n\n끝 문단'.encode('utf-8'))   # 끝에 줄바꿈이 없다
config = base / 'config'
config.mkdir()
# 손으로 고친 설정: 최근 넣은 것에 없는 이름과 Lectern 슬라이드에만 있는 것 (설정 분류에 틀린 값을 적으면 앱이 저장을 멈춘다 — 그것은 config 의 시험이 본다)
(config / 'config.json').write_text(json.dumps({'work_alerts': False, 'recent_puts': ['speaker', '없는것', 'table']}), encoding='utf-8')
BREAK = '<div style="page-break-after: always;"></div>'
src = lambda: doc.read_text(encoding='utf-8')


def saved():
    """설정 파일 — 앱이 바꿔 끼우는 순간에는 못 읽거나 비어 있다. 다시 읽는다"""
    for _ in range(40):
        try:
            return json.loads((config / 'config.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            time.sleep(0.05)
    return {}


HANGUL = "(s) => (s.match(/[가-힣]+/g) || [])"
CONTRAST = """(sel) => { const lum = (c) => { const [r, g, b] = c.match(/[\\d.]+/g).slice(0, 3).map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const el = document.querySelector(sel); let bg = el; let back = 'rgba(0, 0, 0, 0)';
  while (bg && /rgba\\(0, 0, 0, 0\\)|transparent/.test(back = getComputedStyle(bg).backgroundColor)) bg = bg.parentElement;
  const a = lum(getComputedStyle(el).color); const b = lum(back); return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05); }"""

server, url, port = serve(proj, config)
try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(viewport={'width': 1366, 'height': 860}).new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')
        settle = lambda ms=250: page.wait_for_timeout(ms)
        sel = lambda: page.locator('#lec-put-list li.sel').first.inner_text()
        heads = lambda: page.locator('#lec-put-list.board > li.col > .head').all_inner_texts()
        on = lambda: page.locator('#lec-settings .set-nav button.on').inner_text()

        def open_doc(name='a.md'):
            page.keyboard.press('Escape')
            page.locator(f'#lec-tree .row.file[data-doc="{name}"]').click()
            page.wait_for_selector('#lec-view h1')
            settle(500)

        def open_put(text='첫 문단이다', key='/'):
            page.keyboard.press('Escape')
            page.locator('#lec-view p', has_text=text).click()
            page.keyboard.press(key)
            page.wait_for_selector('#lec-put:not([hidden])')
            settle(200)

        def undo(label):
            page.keyboard.press('Escape')
            page.keyboard.press('Control+z')
            expect(page, f'{label} — Ctrl+Z 로 처음 그대로', lambda: src() == DOC, lambda: src())

        print('[손으로 고친 설정 파일]')
        open_doc()
        open_put()
        check("최근 열에는 이 문서에서 넣을 수 있는 것만 (표)", heads()[0] == '최근' and page.locator('#lec-put-list.board > li.recent ul li').all_inner_texts() == ['표'],
              page.locator('#lec-put-list.board > li.col').first.inner_text())
        page.keyboard.press('Escape')
        page.keyboard.press('Escape')
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open-settings', '없는분류'))")
        page.wait_for_selector('#lec-settings:not([hidden])')
        check('없는 분류로 부르면 일반에서', on() == '일반', on())
        page.keyboard.press('Escape')

        print('[최근 넣은 것 — 차례와 다섯 개]')
        for word, name in (('쪽 나눔', 'pagebreak'), ('구분선', 'rule'), ('표 목차', 'tables'), ('그림 목차', 'figures'), ('ㅉㄴ', 'pagebreak')):
            open_put()
            page.keyboard.type(word)
            settle(300)
            page.keyboard.press('Enter')
            expect(page, f'{word} 을 넣음', lambda: src() != DOC, lambda: src())
            expect(page, f'— 최근의 맨 앞에 {name}', lambda: (saved().get('recent_puts') or [''])[0] == name, lambda: saved().get('recent_puts'))
            undo(word)
        recent = saved().get('recent_puts')
        check('같은 것을 다시 넣으면 앞으로 옮기기만 (겹치지 않음), 다섯 개까지 — 오래된 것부터 밀려남', recent == ['pagebreak', 'figures', 'tables', 'rule', 'speaker'], recent)
        open_put()
        check('판의 최근 열 — 넣은 차례 (이 문서에 없는 발표자 노트는 빠짐)', page.locator('#lec-put-list.board > li.recent ul li').all_inner_texts() == ['쪽 나눔', '그림 목차', '표 목차', '구분선'],
              page.locator('#lec-put-list.board > li.recent ul li').all_inner_texts())

        print('[마우스 · 맞는 것이 없을 때]')
        page.locator('#lec-put-list.board > li.col:not(.recent) ul li', has_text='구분선').click()
        expect(page, '판의 항목을 누르면 넣는다', lambda: '\n---\n' in src(), lambda: src())
        undo('마우스')
        open_put()
        page.keyboard.type('zzqq')
        settle(300)
        check('맞는 것이 없으면 알림', '맞는 것이 없습니다' in page.locator('#lec-put-list').inner_text(), page.locator('#lec-put-list').inner_text())
        page.keyboard.press('Enter')
        settle(300)
        check('— Enter 를 눌러도 아무것도 넣지 않는다', src() == DOC, src())
        if page.locator('#lec-put:not([hidden])').count():
            for _ in range(4):
                page.keyboard.press('Backspace')
            settle(300)
            check('거르는 글을 지우면 다시 판', page.locator('#lec-put-list.board').count() == 1)
        page.keyboard.press('Escape')
        page.keyboard.press('Escape')
        check('Esc 로 닫으면 문서는 그대로', src() == DOC and page.locator('#lec-put').is_hidden(), src())

        print('[끝에 줄바꿈이 없는 문서]')
        open_doc('b.md')
        open_put('끝 문단')
        page.keyboard.type('ㅉㄴ')
        settle(300)
        page.keyboard.press('Enter')
        expect(page, '마지막 줄 아래에 쪽 나눔 — 줄을 띄우고', lambda: tail.read_text(encoding='utf-8').startswith(f'# 끝\n\n끝 문단\n\n{BREAK}'), lambda: tail.read_bytes()[:120])
        page.keyboard.press('Escape')

        print('[좁은 창]')
        open_doc()
        page.set_viewport_size({'width': 700, 'height': 640})
        settle(400)
        open_put()
        box = page.locator('#lec-put').bounding_box()
        check('좁은 창에서는 판이 아니라 목록', page.locator('#lec-put-list.board').count() == 0 and page.locator('#lec-put-list li.head').count() >= 5, page.locator('#lec-put-list').inner_text()[:80])
        check('— 창 안에 들어온다', box['x'] >= 0 and box['x'] + box['width'] <= 700 and box['y'] + box['height'] <= 640, box)
        page.keyboard.press('Escape')
        page.keyboard.press('Escape')
        page.keyboard.press('Control+,')
        page.wait_for_selector('#lec-settings:not([hidden])')
        sbox = page.locator('#lec-settings .set-box').bounding_box()
        check('설정 창도 좁은 창 안에', sbox['x'] >= 0 and sbox['x'] + sbox['width'] <= 700 and sbox['y'] >= 0 and sbox['y'] + sbox['height'] <= 640, sbox)
        check('— 분류 여덟이 모두 보이고 내용은 가로로 넘치지 않는다', page.locator('#lec-settings .set-nav button:visible').count() == 8
              and page.evaluate("() => { const c = document.querySelector('#lec-set-content'); return c.scrollWidth <= c.clientWidth + 1; }"))
        page.keyboard.press('Escape')
        page.set_viewport_size({'width': 1366, 'height': 860})
        settle(400)

        print('[어두운 스타일]')
        page.select_option('#lec-theme', 'dark')
        settle(500)
        open_put()
        ratio = page.evaluate(CONTRAST, '#lec-put-list.board ul li:not(.sel) .t')
        check(f'판의 글자 대비 {ratio:.1f}', ratio >= 4.5, ratio)
        ratio = page.evaluate(CONTRAST, '#lec-put-list.board ul li.sel .t')
        check(f'골라진 것의 글자 대비 {ratio:.1f}', ratio >= 4.5, ratio)
        check('골라진 것은 바탕과 다른 색', page.evaluate("() => getComputedStyle(document.querySelector('#lec-put-list.board ul li.sel')).backgroundColor !== getComputedStyle(document.querySelector('#lec-put')).backgroundColor"))
        page.keyboard.press('Escape')
        page.keyboard.press('Escape')
        page.keyboard.press('Control+,')
        page.wait_for_selector('#lec-settings:not([hidden])')
        for name, css in (('분류', '#lec-settings .set-nav button:not(.on)'), ('고른 분류', '#lec-settings .set-nav button.on'), ('고른 단추의 설명', '#lec-settings .seg-desc')):
            ratio = page.evaluate(CONTRAST, css)
            check(f'설정 창 — {name}의 글자 대비 {ratio:.1f}', ratio >= 4.5, ratio)
        page.keyboard.press('Escape')
        page.select_option('#lec-theme', 'default')
        settle(400)

        print('[vi 키]')
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ vi_keys: true })).then(() => import('/static/js/store.js')).then((m) => m.emit('vi-keys'))")
        page.wait_for_selector('#lec-st-vi:not([hidden])')
        page.locator('#lec-view p', has_text='첫 문단이다').click()
        page.keyboard.press('/')
        settle(400)
        check('vi 키에서 / 는 문서에서 찾기 — 넣기 창이 아니다', page.locator('#lec-put').is_hidden() and page.locator('#lec-findbar:not([hidden])').count() == 1)
        page.keyboard.press('Escape')
        page.locator('#lec-view p', has_text='첫 문단이다').click()
        page.click('#lec-btn-put')
        page.wait_for_selector('#lec-put.board:not([hidden])')
        check('탭 막대의 [넣기] 로 판', page.evaluate('document.activeElement?.id') == 'lec-put-find')
        page.keyboard.press('Escape')
        page.keyboard.press('Escape')
        open_put(key='Control+Shift+/')
        check('Ctrl+Shift+/ 로도 판', page.locator('#lec-put.board').count() == 1)
        page.keyboard.press('Enter')   # 최근의 맨 앞 — 쪽 나눔
        expect(page, 'Enter — 최근의 맨 앞(쪽 나눔)', lambda: BREAK in src(), lambda: src())
        page.keyboard.press('Escape')
        page.keyboard.press('u')
        expect(page, 'u 로 되돌림', lambda: src() == DOC, lambda: src())
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ vi_keys: false })).then(() => import('/static/js/store.js')).then((m) => m.emit('vi-keys'))")
        settle(300)

        print('[설정 창 — 내리기 · 켜고 끄기 · 열린 채 다른 분류로]')
        page.keyboard.press('Escape')
        page.keyboard.press('Control+,')
        page.wait_for_selector('#lec-settings:not([hidden])')
        page.locator('#lec-settings .set-nav button[data-set="general"]').click()
        expect(page, '일반으로', lambda: on() == '일반')
        page.evaluate("() => { const c = document.querySelector('#lec-set-content'); c.scrollTop = c.scrollHeight; }")
        expect(page, '끝까지 내리면 분류의 강조는 고급', lambda: on() == '고급', on)
        page.evaluate("() => { document.querySelector('#lec-set-content').scrollTop = 0; }")
        expect(page, '맨 위로 올리면 일반', lambda: on() == '일반', on)
        check('내리기만 한 것은 기억하지 않는다 (누른 분류만)', saved().get('settings_section') == 'general', saved().get('settings_section'))
        was = saved().get('math', True)
        page.locator('#lec-settings label:has(input[data-key="math"])').first.click()
        expect(page, '수식 스위치를 누르면 설정 파일에', lambda: saved().get('math') == (not was), lambda: saved().get('math'))
        page.locator('#lec-settings label:has(input[data-key="math"])').first.click()
        expect(page, '— 다시 누르면 되돌아옴', lambda: saved().get('math') == was, lambda: saved().get('math'))
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open-settings', 'work'))")
        expect(page, '열려 있을 때 다른 화면이 부르면 그 분류로 (창은 하나)', lambda: on() == '업무' and page.locator('#lec-settings:not([hidden])').count() == 1, on)
        page.keyboard.press('Escape')
        check('Esc 로 닫힘', page.locator('#lec-settings').is_hidden())

        print('[영어 화면]')
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ language: 'en' }))")
        settle(500)
        page.reload()
        page.wait_for_selector('#lec-tree .row.file')
        open_doc()
        open_put()
        check('판의 열 이름이 영어 — 자료 묶음은 사이드바의 Other files 와 다른 말', heads() == ['Recent', 'Text', 'Callout', 'Tables and figures', 'Notes and references', 'Page'], heads())
        left = page.evaluate(HANGUL, page.locator('#lec-put').inner_text() + page.get_attribute('#lec-put-find', 'placeholder'))
        check('판에 남은 한글 없음', not left, left)
        page.keyboard.type('page b')
        settle(300)
        check("'page b' → Page break", sel().startswith('Page break'), sel())
        page.keyboard.press('Enter')
        expect(page, '영어 화면에서도 넣는다', lambda: BREAK in src(), lambda: src())
        undo('영어 화면')
        page.keyboard.press('Control+,')
        page.wait_for_selector('#lec-settings:not([hidden])')
        names = page.locator('#lec-settings .set-nav button').all_inner_texts()
        check('설정 분류가 영어', names[0] == 'General' and names[-1] == 'Advanced' and not page.evaluate(HANGUL, ' '.join(names)), names)
        left = [w for w in page.evaluate(HANGUL, page.locator('#lec-settings').inner_text()) if w not in ('언어', '한국어')]   # 언어 칸은 두 말로 적는다
        check('설정 창에 남은 한글 없음', not left, left[:12])
        over = page.evaluate("""() => [...document.querySelectorAll('#lec-settings .set-nav button, #lec-settings .seg label, #lec-settings .seg button')]
          .filter((e) => e.offsetParent && e.scrollWidth > e.clientWidth + 1).map((e) => e.textContent.trim())""")
        check('영어 이름이 단추에서 잘리지 않는다', not over, over[:6])
        page.keyboard.press('Escape')
        check('화면 스크립트 오류 없음', not errors, errors[:3])
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
