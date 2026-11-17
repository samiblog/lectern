"""구성 요소 바꾸기와 알림 줄이기 (D155·D156): 바꾸기 창(. — 판, 이 줄에 맞는 것, 지금 종류, 바꿀 수 없는 것), 목록 전체를·표·코드·바꿔 쓰기 요청,
이웃 규칙(번호 잇기·강조글 안·캡션·없어진 제목 링크), 글을 쓰는 동안 알림 없음, 첫 누름 알림은 한 번, 위에 넣는 새 줄은 위 블록의 양식"""
import json
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-chkinds-'))
proj = base / 'proj'
proj.mkdir(parents=True)
DOC = ('# 보고서\n\n## 개요\n\n첫 문단이다. [개요](#개요)\n\n- 가\n- 나\n- 다\n\n1. 하나\n2. 둘\n3. 셋\n4. 넷\n\n목록 뒤 문단.\n\n'
       '> [!NOTE]\n> 참고 첫 줄\n> 참고 둘째 줄\n\n표 1. 가격\n\n| 품목 | 값 |\n|---|---|\n| 구리 | 9,800 |\n\n## 끝\n\n끝 문단이다.\n')
doc = proj / 'a.md'
doc.write_text(DOC, encoding='utf-8')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)


def src():
    for _ in range(40):
        try:
            return doc.read_text(encoding='utf-8')
        except OSError:
            time.sleep(0.05)
    return ''


line_of = lambda text: src().split('\n').index(text) + 1

try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(viewport={'width': 1400, 'height': 900}).new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')
        page.locator('#lec-tree .row.file[data-doc="a.md"]').click()
        page.wait_for_selector('#lec-view h1')
        page.wait_for_timeout(600)
        page.evaluate("() => import('/static/js/store.js').then((m) => { window.__pasted = []; m.on('term-paste', (x) => window.__pasted.push(typeof x === 'string' ? x : x.text)); })")
        toast = lambda: (page.text_content('#lec-toast') or '') if page.locator('#lec-toast:not([hidden])').count() else ''
        clear_toast = lambda: page.evaluate("() => { const t = document.querySelector('#lec-toast'); t.textContent = ''; t.hidden = true; }")
        SRC = "() => import('/static/js/store.js').then(({ S }) => S.pane?.source?.lines?.join('\\n'))"
        heads = lambda: page.locator('#lec-put-list.board > li.col > .head').all_inner_texts()
        option = lambda name: page.locator('#lec-put-list li[role=option]', has_text=name).first

        def reset():
            page.keyboard.press('Escape')
            page.keyboard.press('Escape')
            if src() != DOC:
                doc.write_text(DOC, encoding='utf-8')
            until(page, lambda: (page.evaluate(SRC) or '').rstrip('\n') == DOC.rstrip('\n'), 10000)
            page.wait_for_timeout(300)

        def go(n):
            page.locator('#lec-view h1').first.click()
            page.evaluate("(n) => import('/static/js/spotlight.js').then((m) => m.followLine(n))", n)
            page.wait_for_timeout(200)

        def twice(n, key):
            """현재 줄에서 바꾸는 키 — 처음은 잡기만, 두 번째에 바꾼다 (D139)"""
            go(n)
            page.keyboard.press(key)
            page.wait_for_timeout(150)
            page.keyboard.press(key)

        def change_win(n):
            go(n)
            page.keyboard.press('.')
            page.wait_for_selector('#lec-put:not([hidden])', timeout=4000)
            page.wait_for_timeout(150)

        def undo():
            page.keyboard.press('Escape')
            page.keyboard.press('Control+z')
            expect(page, '— Ctrl+Z 한 번으로 처음 그대로', lambda: src() == DOC, lambda: src()[:240])

        def write_new(key, text):
            """새 줄을 열어 글을 쓰고 Enter 로 저장한 뒤 다음 빈 줄은 Esc 로 걷는다"""
            page.keyboard.press(key)
            page.wait_for_selector('#lec-view .lec-line-edit')
            page.keyboard.type(text)
            page.keyboard.press('Enter')
            until(page, lambda: text in src(), 6000)
            page.wait_for_timeout(300)
            page.keyboard.press('Escape')

        print('[바꾸기 창 — . ]')
        change_win(line_of('- 나'))
        check('판 — 맨 앞은 이 줄에 맞는 것, 그다음 글·강조글·줄 서식', heads()[:2] == ['이 줄에 맞는 것', '글'] and len(heads()) == 4, heads())
        fit = page.locator('#lec-put-list.board > li.fit li[role=option]').all_inner_texts()
        check('목록 줄에 맞는 것 — 번호·할 일로, 표로, 코드로, 바꿔 쓰기 요청', any('번호 목록으로' in x for x in fit) and any('할 일로' in x for x in fit) and not any('글머리' in x for x in fit)
              and any('표로' in x for x in fit) and any('바꿔 쓰기 요청' in x for x in fit), fit)
        sel = page.locator('#lec-put-list li.sel').inner_text()
        check("지금 종류(목록)에서 시작 — '지금' 표시", sel.startswith('목록') and '지금' in sel, sel)
        option('이 목록 전체를 번호 목록으로').click()
        expect(page, '목록 전체를 번호 목록으로', lambda: '1. 가\n2. 나\n3. 다\n' in src(), lambda: src()[60:140])
        undo()

        change_win(line_of('- 가'))
        option('목록을 표로').click()
        expect(page, '목록을 표로', lambda: '| 항목 |\n| --- |\n| 가 |\n| 나 |\n| 다 |\n' in src(), lambda: src()[60:200])
        undo()

        change_win(line_of('| 구리 | 9,800 |'))
        off = page.locator('#lec-put-list li.off').count()
        check('표 줄 — 글 종류·강조글은 흐리게', off >= 14, off)
        clear_toast()
        option('제목 2').click()
        expect(page, '— 흐린 것을 누르면 까닭을 알리고 창은 그대로', lambda: '표의 줄은 종류를 바꿀 수 없습니다' in toast() and page.locator('#lec-put:not([hidden])').count() == 1, toast)
        page.once('dialog', lambda d: d.accept())
        option('표를 목록으로').click()
        expect(page, '표를 목록으로 — 캡션도 지울지 묻고 지운다', lambda: '표 1. 가격' not in src() and '- 구리 — 9,800\n' in src(), lambda: src()[-120:])
        undo()

        change_win(line_of('첫 문단이다. [개요](#개요)'))
        option('코드로 감싸기').click()
        expect(page, '코드로 감싸기', lambda: '```\n첫 문단이다. [개요](#개요)\n```' in src(), lambda: src()[:120])
        change_win(line_of('첫 문단이다. [개요](#개요)'))
        fit = page.locator('#lec-put-list.board > li.fit li[role=option]').all_inner_texts()
        check('코드 줄에 맞는 것 — 코드 풀기', any('코드 풀기' in x for x in fit), fit)
        option('코드 풀기').click()
        expect(page, '코드 풀기 — 처음 그대로', lambda: src() == DOC, lambda: src()[:120])

        change_win(line_of('2. 둘'))
        option('바꿔 쓰기 요청').click()
        got = page.evaluate('() => window.__pasted.slice(-1)[0] || ""')
        check('바꿔 쓰기 요청 — 터미널에 줄 위치와 작성 안내, Enter 없이', '@a.md' in got and 'writing.md' in got and got.rstrip().endswith('바꿀 모양:') and '\n' not in got, got)

        print('[첫 누름 알림은 한 번]')
        reset()
        go(line_of('끝 문단이다.'))
        clear_toast()
        page.keyboard.press('q')
        check('바꾸는 키의 첫 누름 — 처음에는 알림', '한 번 더 누르면' in toast(), toast())
        page.keyboard.press('Escape')
        go(line_of('목록 뒤 문단.'))
        clear_toast()
        page.keyboard.press('q')
        page.wait_for_timeout(200)
        check('— 두 번째부터는 알리지 않음', '한 번 더 누르면' not in toast(), toast())
        page.keyboard.press('Escape')

        print('[이웃 규칙]')
        clear_toast()
        twice(line_of('2. 둘'), 'p')
        expect(page, '번호 항목을 문단으로 — 뒤 번호를 앞에 잇는다', lambda: '1. 하나\n\n둘\n\n2. 셋\n3. 넷\n' in src(), lambda: src()[90:180])
        expect(page, '— 알림은 고른 줄 밖의 변경만 (Ctrl+Z 꼬리 없음)', lambda: toast() == '뒤 항목 2개의 번호를 다시 매겼습니다', toast)
        undo()
        twice(line_of('> 참고 둘째 줄'), 'l')
        expect(page, '강조글 안의 줄을 목록으로 — 강조글이 갈리지 않음', lambda: '> [!NOTE]\n> 참고 첫 줄\n>\n> - 참고 둘째 줄\n' in src(), lambda: src()[130:240])
        undo()
        clear_toast()
        twice(line_of('표 1. 가격'), '2')
        expect(page, '캡션 줄은 바꾸지 않고 알림', lambda: '캡션 줄은 종류를 바꾸지 않습니다' in toast() and src() == DOC, toast)
        page.keyboard.press('Escape')
        clear_toast()
        twice(line_of('## 개요'), '2')   # 같은 수준이면 문단으로 (D152)
        expect(page, '제목을 문단으로 — 그 제목을 가리키던 링크를 알림', lambda: '\n개요\n' in src() and '없어진 제목을 가리키는 링크 1곳이 남았습니다' in toast(), toast)
        undo()

        print('[알림 줄이기]')
        reset()
        go(line_of('끝 문단이다.'))
        page.keyboard.press('F2')
        page.wait_for_selector('#lec-view .lec-line-edit')
        page.keyboard.press('End')
        page.keyboard.type(' 덧붙임')
        clear_toast()
        page.keyboard.press('Control+Enter')   # 저장하고 아래 새 줄
        until(page, lambda: '끝 문단이다. 덧붙임' in src(), 6000)
        page.wait_for_timeout(400)
        page.keyboard.type('새 문단')
        page.keyboard.press('Enter')   # 새 줄의 Enter — 저장하고 다음 새 줄 (D106)
        until(page, lambda: '새 문단' in src(), 6000)
        page.wait_for_timeout(300)
        check('글을 쓰며 줄을 이어 저장 — 저장 알림 없음', '저장했습니다' not in toast() and '끝 문단이다. 덧붙임\n\n새 문단\n' in src(), (toast(), src()[-60:]))
        page.keyboard.press('Escape')
        page.wait_for_timeout(300)
        page.keyboard.press('Escape')
        clear_toast()
        page.keyboard.press('Control+z')
        until(page, lambda: '새 문단' not in src(), 6000)
        page.wait_for_timeout(400)
        check('화면 안의 되돌리기 — 알림 없음', '되돌렸습니다' not in toast() and '새 문단' not in src(), toast())

        print('[새 줄의 양식]')
        reset()
        go(line_of('## 끝'))
        write_new('Control+Shift+Enter', '표 다음')
        expect(page, '제목 위 — 위 블록(표)이 목록·인용이 아니면 문단', lambda: '| 구리 | 9,800 |\n\n표 다음\n\n## 끝' in src(), lambda: src()[-80:])
        reset()
        go(line_of('목록 뒤 문단.'))
        write_new('Control+Shift+Enter', '다섯')
        expect(page, '문단 위 — 위 블록(번호 목록)을 잇는다', lambda: '3. 셋\n4. 넷\n5. 다섯\n\n목록 뒤 문단.' in src(), lambda: src()[90:200])
        reset()
        go(line_of('표 1. 가격'))
        write_new('Control+Shift+Enter', '강조글 끝에')
        expect(page, '캡션 위 — 위 블록(강조글) 안에', lambda: '> 참고 둘째 줄\n>\n> 강조글 끝에\n\n표 1. 가격' in src(), lambda: src()[150:260])
        reset()
        go(line_of('## 끝'))
        write_new('Control+Enter', '제목 아래 본문')
        expect(page, '제목 아래 — 문단', lambda: '## 끝\n\n제목 아래 본문\n\n끝 문단이다.' in src(), lambda: src()[-80:])
        reset()
        go(line_of('목록 뒤 문단.'))
        page.keyboard.press('Control+Shift+Enter')
        page.wait_for_selector('#lec-view .lec-line-edit')
        page.keyboard.press('Shift+Tab')   # 맨 바깥 항목 → 문단
        page.wait_for_timeout(200)
        page.keyboard.press('Control+Shift+/')
        page.wait_for_selector('#lec-put:not([hidden])')
        page.keyboard.type('번호 목록')
        page.wait_for_timeout(200)
        page.keyboard.press('Enter')
        page.wait_for_timeout(200)
        page.keyboard.type('다시 번호')
        page.keyboard.press('Enter')
        until(page, lambda: '다시 번호' in src(), 6000)
        page.wait_for_timeout(300)
        page.keyboard.press('Escape')
        expect(page, '빈 새 줄을 번호 목록으로 — 위 목록의 다음 번호로 붙는다', lambda: '3. 셋\n4. 넷\n5. 다시 번호\n' in src(), lambda: src()[90:200])

        print('[vi 키]')
        reset()
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ vi_keys: true })).then(() => import('/static/js/store.js')).then((m) => m.emit('vi-keys'))")
        page.wait_for_selector('#lec-st-vi:not([hidden])')
        go(line_of('- 다'))
        page.keyboard.press('.')
        check('vi 키에서도 . 은 바꾸기 창', page.locator('#lec-put:not([hidden])').count() == 1)
        page.keyboard.press('Escape')
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ vi_keys: false })).then(() => import('/static/js/store.js')).then((m) => m.emit('vi-keys'))")

        print('[좁은 창 — 목록]')
        page.set_viewport_size({'width': 700, 'height': 700})
        page.wait_for_timeout(300)
        change_win(line_of('- 다'))
        check('좁은 창에서는 목록 — 지금 종류에서 시작', page.locator('#lec-put-list.board').count() == 0 and page.locator('#lec-put-list li.sel').inner_text().startswith('목록'),
              page.locator('#lec-put-list li.sel').inner_text())
        page.keyboard.press('Escape')
        page.set_viewport_size({'width': 1400, 'height': 900})
        check('화면 스크립트 오류 없음', not errors, errors[:3])
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
