"""읽는 화면에서 글을 고르고 서식 (D142): 두 번 누르기는 낱말만 고르고 칸을 열지 않는다, 현재 줄의 → ← 는 첫·마지막 낱말,
고른 채 → ← 낱말 옮기기, Shift+→ ← 낱말 단위 넓히기, Home·End, ↑ 로 풀기, B·I·S·M·F·Ctrl 키로 서식(바로 저장·고른 채 남음),
아무것도 고르지 않은 현재 줄의 B·I·S·M·F 는 듣지 않음, F2 는 고른 글을 그대로 칸에, 우클릭 서식 상자, 표의 칸, 맞추지 못하는 줄."""
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-wordpick-'))
proj = base / 'proj'
proj.mkdir(parents=True)
DOC = ('# 낱말 시험\n\n구리 가격은 크게 올랐다 그리고 니켈도 올랐다.\n\n- 항목 **굵은 말** 과 끝\n\n| 품목 | 설명 |\n|---|---|\n| 니켈 | 값이 높다 |\n\n'
       '수식 $x^2$ 이 든 줄이다.\n\n마지막 문단이다.\n')
doc = proj / '낱말.md'
doc.write_text(DOC, encoding='utf-8')
server, url, port = serve(proj, base / 'config')

SEL = 'getSelection().toString()'
CELL = "document.querySelector('#lec-view .lec-line-edit')?.textContent ?? null"
# 문단의 글자 word 의 가운데 화면 좌표
WORD_AT = """([sel, word]) => { const el = [...document.querySelectorAll(sel)].find((x) => x.textContent.includes(word));
  const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT); for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const at = n.data.indexOf(word); if (at < 0) continue; const r = document.createRange(); r.setStart(n, at); r.setEnd(n, at + word.length);
    const b = r.getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2]; } return null; }"""


def read():
    return doc.read_text(encoding='utf-8').replace('\r\n', '\n')


try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1300, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        page.locator('#lec-tree .row.file').first.click()
        page.wait_for_selector('#lec-view h1:has-text("낱말 시험")')
        sel = lambda: page.evaluate(SEL)
        cell = lambda: page.evaluate(CELL)
        toast = lambda: page.text_content('#lec-toast') or ''

        def dbl(selector, word):
            page.keyboard.press('Escape')
            page.keyboard.press('Escape')
            xy = page.evaluate(WORD_AT, [selector, word])
            page.mouse.dblclick(*xy)
            page.wait_for_timeout(350)

        shown_src = "import('/static/js/store.js').then(({ S }) => S.pane?.source?.lines?.join('\\n'))"

        def reset():
            page.keyboard.press('Escape')
            page.keyboard.press('Escape')
            if read() != DOC:
                doc.write_text(DOC, encoding='utf-8')
            until(page, lambda: page.evaluate(shown_src) == DOC, 10000)   # 화면이 그 원문으로 다시 그려질 때까지
            page.wait_for_timeout(300)

        print('[두 번 누르기]')
        dbl('#lec-view p', '크게')
        check('두 번 누르면 낱말을 고른다', sel().strip() == '크게', sel())
        page.wait_for_timeout(400)
        check('한 줄 편집 칸은 열리지 않는다', cell() is None and read() == DOC, cell())

        print('[낱말 옮기기·넓히기]')
        page.keyboard.press('ArrowRight')
        check('→: 오른쪽 낱말', sel() == '올랐다', sel())
        page.keyboard.press('ArrowLeft')
        page.keyboard.press('ArrowLeft')
        check('←: 왼쪽 낱말 (두 번)', sel() == '가격은', sel())
        page.keyboard.press('Shift+ArrowRight')
        check('Shift+→: 낱말 단위로 넓힌다', sel() == '가격은 크게', sel())
        page.keyboard.press('Shift+ArrowRight')
        check('Shift+→ 한 번 더', sel() == '가격은 크게 올랐다', sel())
        page.keyboard.press('Shift+ArrowLeft')
        check('Shift+←: 줄인다', sel() == '가격은 크게', sel())
        page.keyboard.press('Shift+ArrowLeft')
        page.keyboard.press('Shift+ArrowLeft')
        check('처음 낱말을 넘으면 반대쪽으로', sel() == '구리 가격은', sel())
        page.keyboard.press('Home')
        check('Home: 첫 낱말', sel() == '구리', sel())
        page.keyboard.press('End')
        check('End: 마지막 낱말', sel() == '올랐다.', sel())
        page.keyboard.press('ArrowRight')
        check('끝에서 → 는 다음 줄로 넘어가지 않는다', sel() == '올랐다.', sel())
        page.keyboard.press('Shift+Home')
        check('Shift+Home: 첫 낱말까지 넓힌다', sel() == '구리 가격은 크게 올랐다 그리고 니켈도 올랐다.', sel())
        terms = page.evaluate("document.querySelectorAll('#lec-term .xterm').length")
        check('고른 동안 Shift+→ 는 터미널로 보내지 않는다', terms == 0 and '보냈' not in toast(), toast())
        page.keyboard.press('Escape')
        check('Esc 로 푼다', sel() == '', sel())

        print('[현재 줄에서 → ←]')
        page.locator('#lec-view li', has_text='항목').click(position={'x': 5, 'y': 8})
        page.evaluate('getSelection().removeAllRanges()')
        page.keyboard.press('ArrowRight')
        check('현재 줄의 →: 첫 낱말', sel() == '항목', sel())
        page.keyboard.press('Escape')
        page.keyboard.press('ArrowLeft')
        check('현재 줄의 ←: 마지막 낱말', sel() == '끝', sel())
        page.keyboard.press('ArrowDown')
        page.wait_for_timeout(200)
        check('↓ 는 풀고 현재 줄을 옮긴다', sel() == '' and page.inner_text('#lec-st-here').startswith('현재 줄'), (sel(), page.inner_text('#lec-st-here')))

        print('[고른 글의 서식 — 한 글자 키]')
        reset()
        dbl('#lec-view p', '크게')
        page.keyboard.press('b')
        check('B: 고른 낱말을 굵게 — 바로 저장', until(page, lambda: '구리 가격은 **크게** 올랐다' in read()), read())
        check('고른 낱말은 그대로 고른 채', until(page, lambda: sel() == '크게'), sel())
        check('화면에 굵게 보인다', page.locator('#lec-view p strong', has_text='크게').count() == 1)
        page.keyboard.press('b')
        check('다시 누르면 푼다', until(page, lambda: read() == DOC), read())
        check('풀어도 고른 채', until(page, lambda: sel() == '크게'), sel())
        page.keyboard.press('m')
        check('M: 형광펜(노랑)', until(page, lambda: '<mark>크게</mark>' in read()), read())
        page.keyboard.press('m')
        check('M 다시: 다음 색', until(page, lambda: '<mark class="green">크게</mark>' in read()), read())
        page.keyboard.press('f')
        check('F: 글자색', until(page, lambda: '<mark class="green"><span style="color:red">크게</span></mark>' in read()), read())
        page.keyboard.press('Control+z')
        page.keyboard.press('Control+z')
        page.keyboard.press('Control+z')
        check('Ctrl+Z 로 하나씩 되돌린다', until(page, lambda: read() == DOC), read())
        dbl('#lec-view p', '가격은')
        page.keyboard.press('Shift+ArrowRight')
        page.keyboard.press('i')
        check('I: 넓혀 고른 글을 기울임', until(page, lambda: '구리 *가격은 크게* 올랐다' in read()), read())
        page.keyboard.press('s')
        check('S: 취소선', until(page, lambda: '구리 ~~*가격은 크게*~~ 올랐다' in read() or '구리 *~~가격은 크게~~* 올랐다' in read()), read())

        print('[Ctrl 키]')
        reset()
        dbl('#lec-view p', '니켈도')
        page.keyboard.press('Control+b')
        check('Ctrl+B: 굵게 (사이드바를 숨기지 않는다)', until(page, lambda: '**니켈도**' in read()) and page.is_visible('#lec-sidebar'), read())
        page.keyboard.press('Control+Shift+h')
        check('Ctrl+Shift+H: 형광펜', until(page, lambda: '**<mark>니켈도</mark>**' in read()), read())
        page.keyboard.press('Escape')
        page.keyboard.press('Escape')
        page.evaluate('getSelection().removeAllRanges()')
        page.keyboard.press('Control+b')
        page.wait_for_timeout(300)
        hidden = not page.is_visible('#lec-sidebar')
        page.keyboard.press('Control+b')
        page.wait_for_timeout(300)
        check('고른 글이 없으면 Ctrl+B 는 사이드바 그대로', hidden and page.is_visible('#lec-sidebar'))

        print('[복사 알림 (D151)]')
        reset()
        page.evaluate("() => { document.querySelector('#lec-toast').hidden = true; }")
        dbl('#lec-view p', '니켈도')
        page.keyboard.press('Control+c')
        check('고른 낱말의 Ctrl+C — 복사했습니다 알림', until(page, lambda: page.is_visible('#lec-toast') and '복사했습니다: 니켈도' in toast()), toast())
        page.keyboard.press('Escape')
        page.keyboard.press('Escape')
        page.evaluate("() => { document.querySelector('#lec-toast').hidden = true; }")
        page.keyboard.press('Control+f')
        page.wait_for_selector('#lec-find-input:visible')
        page.fill('#lec-find-input', '구리')
        page.locator('#lec-find-input').select_text()
        page.keyboard.press('Control+c')
        page.wait_for_timeout(300)
        check('찾기 칸의 Ctrl+C 는 알리지 않음', not page.is_visible('#lec-toast'))
        page.keyboard.press('Escape')

        print('[아무것도 고르지 않은 현재 줄]')
        reset()
        page.locator('#lec-view p', has_text='구리 가격은').click(position={'x': 5, 'y': 8})
        page.evaluate('getSelection().removeAllRanges()')
        page.evaluate("document.querySelector('#lec-toast').textContent = ''")
        for key in ['b', 'i', 's', 'm', 'f', 'b']:
            page.keyboard.press(key)
        page.wait_for_timeout(500)
        st = page.inner_text('#lec-st-lit') if page.locator('#lec-st-lit').is_visible() else ''
        check('현재 줄의 B·I·S·M·F 는 듣지 않는다 — 잡지도 않는다', read() == DOC and st == '' and toast() == '', (st, toast()))
        page.keyboard.press('Shift+ArrowDown')
        page.keyboard.press('i')
        check('줄을 고르면 I 는 줄 전체에', until(page, lambda: '*구리 가격은 크게 올랐다 그리고 니켈도 올랐다.*' in read()), read())
        page.keyboard.press('Control+i')
        check('고른 줄의 Ctrl+I 도 — 다시 하면 푼다', until(page, lambda: read() == DOC), read())

        print('[F2 는 고른 글 그대로]')
        reset()
        dbl('#lec-view li', '굵은')
        page.keyboard.press('Shift+ArrowRight')
        check('굵은 글을 골라 넓힌다', sel() == '굵은 말', sel())
        page.keyboard.press('F2')
        check('F2: 칸이 열리고 같은 글이 골라져 있다', until(page, lambda: cell() == '항목 **굵은 말** 과 끝') and sel() == '굵은 말', (cell(), sel()))
        page.keyboard.press('Control+Shift+c')
        check('칸 안에서 이어서 서식', cell() == '항목 **<span style="color:red">굵은 말</span>** 과 끝', cell())
        page.keyboard.press('Escape')

        print('[우클릭 서식 상자]')
        reset()
        dbl('#lec-view p', '올랐다')
        xy = page.evaluate(WORD_AT, ['#lec-view p', '올랐다'])
        page.mouse.click(*xy, button='right')
        page.wait_for_selector('#lec-menu:not([hidden])')
        labels = page.evaluate("[...document.querySelectorAll('#lec-menu button[data-i] > span')].map((e) => e.textContent)")
        head = page.evaluate("document.querySelector('#lec-menu .menu-head')?.textContent")
        check('고른 글의 선택 상자', head.startswith('고른 글') and labels[:4] == ['고른 글 복사', '굵게', '기울임', '취소선'] and '형광펜 — 분홍' in labels and '여기서 편집' in labels
              and '이 블록의 메뉴…' in labels, (head, labels))
        page.locator('#lec-menu button', has_text='형광펜 — 분홍').click()
        check('고르면 그 색으로', until(page, lambda: '<mark class="pink">올랐다</mark>' in read()), read())
        check('고른 채 남는다', until(page, lambda: sel() == '올랐다'), sel())

        print('[표의 칸]')
        reset()
        dbl('#lec-view td', '높다')
        page.keyboard.press('ArrowLeft')
        check('표의 칸 안에서 낱말 옮기기', sel() == '값이', sel())
        page.keyboard.press('Shift+ArrowRight')
        page.keyboard.press('b')
        check('칸 안의 글에 굵게', until(page, lambda: '| 니켈 | **값이 높다** |' in read()), read())
        page.keyboard.press('Home')
        page.keyboard.press('Shift+End')
        page.keyboard.press('b')
        check('칸을 넘어 고르면 하지 않고 알린다', until(page, lambda: '한 칸 안에서' in toast()) and '| 니켈 | **값이 높다** |' in read(), (toast(), read()))
        reset()
        dbl('#lec-view td', '높다')
        page.keyboard.press('F2')
        focused = "document.activeElement?.classList?.contains('lec-line-edit') ? document.activeElement.textContent : null"
        check('표의 칸 끝 낱말을 두 번 눌러 F2 — 그 칸이 열리고 그 낱말이 골라져 있다', until(page, lambda: page.evaluate(focused) == '값이 높다') and sel() == '높다', (page.evaluate(focused), sel()))
        page.keyboard.press('Escape')

        print('[맞추지 못하는 줄·경계]')
        reset()
        dbl('#lec-view p', '든')
        page.keyboard.press('b')
        check('수식이 든 줄은 하지 않고 F2 를 안내', until(page, lambda: 'F2' in toast()) and read() == DOC, toast())
        reset()
        doc.write_text(DOC.replace('구리 가격은 크게', '구리 **가격은 크게**'), encoding='utf-8')
        until(page, lambda: page.locator('#lec-view p strong').count() == 1)
        page.wait_for_timeout(300)
        dbl('#lec-view p', '크게')
        page.keyboard.press('Shift+ArrowRight')
        before = read()
        page.keyboard.press('m')
        check('서식의 경계를 걸치면 하지 않고 알린다', until(page, lambda: '경계' in toast()) and read() == before, (toast(), read()))
        page.keyboard.press('Escape')

        print('[여러 줄에 걸친 고르기]')
        reset()
        page.locator('#lec-view p', has_text='구리').click(position={'x': 5, 'y': 8}, click_count=1)
        a = page.evaluate(WORD_AT, ['#lec-view p', '구리'])
        z = page.evaluate(WORD_AT, ['#lec-view li', '항목'])
        page.mouse.move(*a)
        page.mouse.down()
        page.mouse.move(*z, steps=6)
        page.mouse.up()
        page.keyboard.press('b')
        check('여러 줄에 걸치면 하지 않고 알린다', until(page, lambda: '한 줄 안에서만' in toast()) and read() == DOC, toast())
        check('페이지 오류 없음', not errors, errors[:3])
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
