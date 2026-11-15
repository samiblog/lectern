"""문장 속 서식 (D141): 칸 안에서 고른 글에 굵게·기울임·취소선·코드·형광펜·글자색 — 키와 우클릭 선택 상자, 다시 하면 풀기,
색은 차례로, 칸 안에서도 모양이 보인다(글자는 원문 그대로), 줄 전체의 한 글자 키(I·S·M·F), 저장한 화면의 색."""
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-inlinefmt-'))
proj = base / 'proj'
proj.mkdir(parents=True)
DOC = '# 서식 시험\n\n구리 가격은 크게 올랐다.\n\n- 항목 하나\n- 항목 둘\n\n| 품목 | 값 |\n|---|---|\n| 니켈 | 높다 |\n\n끝 문단이다.\n'
doc = proj / '서식.md'
doc.write_text(DOC, encoding='utf-8')
server, url, port = serve(proj, base / 'config')

CELL = "document.activeElement?.classList?.contains('lec-line-edit') ? document.activeElement.textContent : null"
# 칸의 글에서 word 를 고른다 (없으면 커서를 글 끝에)
PICK = """(word) => { const el = document.activeElement; const node = el.firstChild; const at = word ? node.data.indexOf(word) : -1;
  const r = document.createRange(); if (at < 0) { r.selectNodeContents(el); r.collapse(false); } else { r.setStart(node, at); r.setEnd(node, at + word.length); }
  const s = getSelection(); s.removeAllRanges(); s.addRange(r); return at; }"""
SEL = "getSelection().toString()"
# 칠해진 범위: 이름 → 그 범위의 글들
PAINT = """() => Object.fromEntries([...CSS.highlights.entries()].filter(([k]) => k.startsWith('lec-fmt-'))
  .map(([k, h]) => [k.slice(8), [...h].map((r) => r.toString())]))"""


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
        page.wait_for_selector('#lec-view h1:has-text("서식 시험")')
        cell = lambda: page.evaluate(CELL)
        paint = lambda: page.evaluate(PAINT)
        toast = lambda: page.text_content('#lec-toast') or ''

        def open_line(text):
            page.keyboard.press('Escape')
            page.locator('#lec-view :is(p, li, td)', has_text=text).first.click()
            page.keyboard.press('F2')
            return until(page, lambda: cell() is not None)

        def reset():
            page.keyboard.press('Escape')
            if read() != DOC:
                doc.write_text(DOC, encoding='utf-8')
            until(page, lambda: page.locator('#lec-view p', has_text='구리 가격은 크게 올랐다.').count() == 1)
            page.wait_for_timeout(300)

        print('[칸 안의 키]')
        check('칸을 연다', open_line('구리 가격은'))
        page.evaluate(PICK, '크게')
        page.keyboard.press('Control+b')
        check('Ctrl+B: 고른 글을 굵게', cell() == '구리 가격은 **크게** 올랐다.', cell())
        check('고른 글은 그대로 고른 채', page.evaluate(SEL) == '크게', page.evaluate(SEL))
        got = paint()
        check('칸 안에서 굵게로 보이고 표시는 흐리게', got.get('bold') == ['크게'] and got.get('marks') == ['**', '**'], got)
        page.keyboard.press('Control+b')
        check('다시 누르면 푼다', cell() == '구리 가격은 크게 올랐다.' and page.evaluate(SEL) == '크게', cell())
        check('풀면 칠한 것도 없어진다', 'bold' not in paint() and 'marks' not in paint(), paint())
        for key, want, name in [('Control+i', '*크게*', '기울임'), ('Control+Shift+x', '~~크게~~', '취소선'), ('Control+`', '`크게`', '코드')]:
            page.keyboard.press(key)
            on = cell() == f'구리 가격은 {want} 올랐다.'
            page.keyboard.press(key)
            check(f'{key}: {name} — 다시 누르면 푼다', on and cell() == '구리 가격은 크게 올랐다.', cell())

        print('[형광펜과 글자색 — 거듭 누르면 다음 색]')
        seen = []
        for _ in range(5):
            page.keyboard.press('Control+Shift+h')
            seen.append(cell())
        check('형광펜: 노랑 → 초록 → 분홍 → 하늘 → 없음', seen == [f'구리 가격은 {x} 올랐다.' for x in (
            '<mark>크게</mark>', '<mark class="green">크게</mark>', '<mark class="pink">크게</mark>', '<mark class="blue">크게</mark>', '크게')], seen)
        seen = []
        for _ in range(5):
            page.keyboard.press('Control+Shift+c')
            seen.append(cell())
        check('글자색: 빨강 → 파랑 → 초록 → 노랑 → 없음', seen == [f'구리 가격은 {x} 올랐다.' for x in (
            '<span style="color:red">크게</span>', '<span style="color:blue">크게</span>', '<span style="color:green">크게</span>', '<span style="color:goldenrod">크게</span>', '크게')], seen)
        page.keyboard.press('Control+Shift+h')
        page.keyboard.press('Control+Shift+h')
        got = paint()
        check('칸 안에서 형광펜의 색으로 보인다', got.get('mark-green') == ['크게'] and got.get('marks') == ['<mark class="green">', '</mark>'], got)
        page.keyboard.press('Control+Shift+c')
        got = paint()
        check('색을 겹쳐도 둘 다 보인다', got.get('color-red') == ['크게'] and got.get('mark-green') == ['<span style="color:red">크게</span>'], got)
        shade = page.evaluate("""() => { const el = document.activeElement; const probe = document.createElement('span'); document.body.append(probe);
          const css = (name, prop) => getComputedStyle(el, `::highlight(lec-fmt-${name})`)[prop]; const out = [css('mark-green', 'backgroundColor'), css('color-red', 'color'), css('marks', 'color'), getComputedStyle(el).color];
          probe.remove(); return out; }""")
        check('스타일이 칠할 색을 준다 (바탕·글자색·흐린 표시)', shade[0] not in ('rgba(0, 0, 0, 0)', '') and shade[1] != shade[3] and shade[2] != shade[3], shade)
        page.keyboard.press('Enter')
        want = DOC.replace('크게', '<mark class="green"><span style="color:red">크게</span></mark>')
        check('Enter 로 저장 — 원문에 그대로', until(page, lambda: read() == want), read())
        shown = page.evaluate("""() => { const m = document.querySelector('#lec-view mark.green'); const s = m?.querySelector('span'); const p = document.querySelector('#lec-view p');
          return m && s ? [getComputedStyle(m).backgroundColor, getComputedStyle(s).color, getComputedStyle(p).color, s.textContent] : null; }""")
        check('저장한 화면에 형광펜과 글자색', bool(shown) and shown[0] != 'rgba(0, 0, 0, 0)' and shown[1] != shown[2] and shown[3] == '크게', shown)
        check('칸을 닫으면 칠한 것이 남지 않는다', until(page, lambda: paint() == {}), paint())
        page.keyboard.press('Control+z')
        check('Ctrl+Z 로 되돌린다', until(page, lambda: read() == DOC), read())

        print('[커서만 있을 때]')
        reset()
        open_line('끝 문단이다')
        page.evaluate(PICK, '')
        page.keyboard.press('Control+b')
        page.keyboard.type('굵은 말')
        check('고른 글 없이 Ctrl+B: 빈 표시 사이에서 이어 쓴다', cell() == '끝 문단이다.**굵은 말**', cell())
        page.keyboard.press('Control+b')
        check('굵은 글 안에서 다시 누르면 푼다', cell() == '끝 문단이다.굵은 말', cell())
        page.keyboard.press('Escape')

        print('[우클릭 선택 상자]')
        reset()
        open_line('구리 가격은')
        page.evaluate(PICK, '가격은')
        page.locator('#lec-view .lec-line-edit').click(button='right')
        page.wait_for_selector('#lec-menu:not([hidden])')
        labels = page.evaluate("[...document.querySelectorAll('#lec-menu button[data-i] > span')].map((e) => e.textContent)")
        head = page.evaluate("document.querySelector('#lec-menu .menu-head')?.textContent")
        check('선택 상자: 서식들과 색, 링크·주, 서식 풀기', head == '고른 글의 서식' and labels[:4] == ['굵게', '기울임', '취소선', '코드'] and '형광펜 — 분홍' in labels
              and '글자색 — 파랑' in labels and '링크…' in labels and labels[-1] == '서식 풀기', (head, labels))
        hints = page.evaluate("Object.fromEntries([...document.querySelectorAll('#lec-menu button[data-i]')].map((b) => [b.querySelector('span').textContent, b.querySelector('small')?.textContent || '']))")
        check('항목 옆에 키', hints.get('굵게') == 'Ctrl+B' and hints.get('취소선') == 'Ctrl+Shift+X' and hints.get('형광펜 — 노랑') == 'Ctrl+Shift+H' and hints.get('글자색 — 빨강') == 'Ctrl+Shift+C', hints)
        page.locator('#lec-menu button', has_text='글자색 — 파랑').click()
        check('고르면 그 색으로 — 칸은 열린 채, 고른 글도 그대로', cell() == '구리 <span style="color:blue">가격은</span> 크게 올랐다.' and page.evaluate(SEL) == '가격은', (cell(), page.evaluate(SEL)))
        page.keyboard.type('값은')
        check('이어서 바로 친다', cell() == '구리 <span style="color:blue">값은</span> 크게 올랐다.', cell())
        page.evaluate(PICK, '')
        page.locator('#lec-view .lec-line-edit').click(button='right')
        page.wait_for_selector('#lec-menu:not([hidden])')
        head = page.evaluate("document.querySelector('#lec-menu .menu-head')?.textContent")
        page.locator('#lec-menu button', has_text='형광펜 — 노랑').click()
        check('고른 글이 없으면 줄 전체에', head == '이 줄의 서식' and cell() == '<mark>구리 <span style="color:blue">값은</span> 크게 올랐다.</mark>', (head, cell()))
        page.locator('#lec-view .lec-line-edit').click(button='right')
        page.wait_for_selector('#lec-menu:not([hidden])')
        page.keyboard.press('Escape')
        check('Esc 로 상자를 닫아도 칸은 열려 있다', cell() is not None, cell())
        page.evaluate("() => { const s = getSelection(); s.selectAllChildren(document.activeElement); }")
        page.locator('#lec-view .lec-line-edit').click(button='right')
        page.wait_for_selector('#lec-menu:not([hidden])')
        page.locator('#lec-menu button', has_text='서식 풀기').click()
        check('서식 풀기: 고른 곳의 서식을 모두', cell() == '구리 값은 크게 올랐다.', cell())
        page.keyboard.press('Escape')

        print('[표의 칸]')
        reset()
        page.keyboard.press('Escape')
        xy = page.evaluate("""() => { const td = [...document.querySelectorAll('#lec-view td')].find((x) => x.textContent.trim() === '높다');
          const r = document.createRange(); r.selectNodeContents(td); const b = r.getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2]; }""")
        page.mouse.dblclick(*xy)   # 그 낱말을 고르고 — 칸의 빈 곳이 아니라 글 위를 (빈 곳을 두 번 누르면 아무것도 고르지 않는다)
        page.keyboard.press('F2')   # 고른 채 그 칸을 연다 (D142)
        until(page, lambda: cell() == '높다')
        page.evaluate(PICK, '높다')
        page.keyboard.press('Control+b')
        page.keyboard.press('Enter')
        check('표의 칸에서도 굵게', until(page, lambda: '| 니켈 | **높다** |' in read()), read())

        print('[줄 전체 — 한 글자 키]')
        reset()
        page.locator('#lec-view li', has_text='항목 하나').click()
        page.evaluate("document.querySelector('#lec-toast').textContent = ''")
        page.keyboard.press('m')
        page.keyboard.press('m')
        page.wait_for_timeout(400)
        check('아무것도 고르지 않은 현재 줄의 M 은 듣지 않는다 (D142)', read() == DOC and toast() == '', toast())
        page.keyboard.press('Shift+Enter')   # 그 줄의 하이라이트 — 고른 줄이다
        page.keyboard.press('m')
        check('고른 줄의 M: 줄 전체에 형광펜 — 목록 표시는 그대로', until(page, lambda: '- <mark>항목 하나</mark>\n' in read()), read())
        page.keyboard.press('m')
        check('거듭 누르면 다음 색', until(page, lambda: '- <mark class="green">항목 하나</mark>\n' in read()), read())
        page.keyboard.press('f')
        check('F: 글자색', until(page, lambda: '- <span style="color:red"><mark class="green">항목 하나</mark></span>\n' in read()), read())
        page.keyboard.press('Control+z')
        page.keyboard.press('Control+z')
        page.keyboard.press('Control+z')
        until(page, lambda: read() == DOC)
        page.keyboard.press('Escape')
        page.locator('#lec-view li', has_text='항목 하나').click()
        page.keyboard.press('Shift+ArrowDown')
        page.keyboard.press('i')
        check('여러 줄을 고르면 한 번에 — I 기울임', until(page, lambda: '- *항목 하나*\n- *항목 둘*\n' in read()), read())
        page.keyboard.press('s')
        check('S 취소선', until(page, lambda: '- ~~*항목 하나*~~\n- ~~*항목 둘*~~\n' in read()), read())
        page.keyboard.press('s')
        page.keyboard.press('i')
        check('다시 누르면 푼다', until(page, lambda: read() == DOC), read())
        page.keyboard.press('Escape')
        page.locator('#lec-view li', has_text='항목 하나').click()
        page.keyboard.press('Shift+ArrowDown')
        page.locator('#lec-view li', has_text='항목 하나').click(button='right')
        page.wait_for_selector('#lec-menu:not([hidden])')
        page.locator('#lec-menu button', has_text='고른 줄 바꾸기').click()
        page.wait_for_selector('#lec-put:not([hidden])')
        hints = page.evaluate("Object.fromEntries([...document.querySelectorAll('#lec-put li[role=option]')].map((li) => [li.querySelector('.t')?.textContent, li.querySelector('kbd')?.textContent || '']))")
        check('고른 줄 바꾸기 창에 줄 전체의 서식과 키', hints.get('굵게') == 'B' and hints.get('기울임') == 'I' and hints.get('취소선') == 'S'
              and hints.get('형광펜 (다시 고르면 다음 색)') == 'M' and hints.get('글자색 (다시 고르면 다음 색)') == 'F', hints)
        page.locator('#lec-put li[role=option]', has_text='형광펜').click()
        check('창에서 골라도 된다', until(page, lambda: '- <mark>항목 하나</mark>\n- <mark>항목 둘</mark>\n' in read()), read())
        check('페이지 오류 없음', not errors, errors[:3])
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
