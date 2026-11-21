"""꺾인 긴 줄의 한 줄 편집과 끌어 고른 여러 줄 (D189 — 2026-11-22 사용자 보고).

① 화면에서 두 줄 넘게 꺾인 줄의 칸에서 ↑ 는 칸 안의 화면 줄을 먼저 오른다 — 둘째 화면 줄 맨 앞(Home·그 자리를 누름)에서도,
   빠르게 거듭 누른 ↑(넘어가는 사이에 모아 둔 것)도. 맨 윗줄·맨 아랫줄에서는 앞뒤 원문 줄로. 표의 칸도 같다.
② 읽는 화면에서 끌어 여러 줄에 걸쳐 고른 글에 Delete·Ctrl+X·Alt+↓ 는 그 글이 닿은 줄들에 한 번에 듣는다 — 전에는 끌기를 시작한
   줄만 잡아 두 번째 Delete 가 그 한 줄만 지웠다. 한 줄 안의 고른 글은 그대로 두 번, Shift+↑·↓ 로 고른 줄이 있으면 그 줄들이 먼저. 코드 화면도.
③ 문단부터 코드 블록의 끝 줄까지 고른 지우기는 블록째 — ``` 줄은 화면의 줄이 아니라 고를 수 없다 (전에는 '블록이 깨집니다').
④ 한 줄 지우기 뒤 위아래 줄의 종류·레벨이 그대로 (사용자 보고 '위 아래의 스타일 또는 레벨이 변경') — 둘째 문단이 있는 항목, 강조글의 첫 줄,
   두 목록 사이의 문단, 하위 항목이 있는 항목. 계산은 rules_check 의 delete_fuzz·lineops_cases 가 넓게 본다 — 여기는 화면에서 Delete 두 번의 길."""
import json
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

LONG = '인공지능의 확산은 노동 시장과 생산성에 동시에 영향을 미치며, 특히 서비스 산업에서는 업무 방식이 크게 바뀌고 있다. ' * 4
CELL = '표의 칸에 든 긴 글입니다. 칸의 너비가 좁아 여러 줄로 꺾여 보이는 설명입니다. ' * 3
WRAP_DOC = (f'# 꺾인 줄\n\n짧은 줄 A\n\n{LONG}\n\n짧은 줄 B\n\n| 설명 | 값 |\n|---|---|\n| {CELL} | 1 |\n\n끝 줄\n')
DRAG_DOC = ('# 끌기\n\n문단 A 의 글\n\n문단 B 의 글\n\n문단 C 의 글\n\n문단 D 의 글\n\n문단 E 의 글\n\n'
            '```\n코드 하나\n코드 둘\n```\n\n문단 F 의 글\n\n문단 G 의 글\n')

base = Path(tempfile.mkdtemp(prefix='lec-wrapdrag-'))
proj = base / 'proj'
proj.mkdir(parents=True)
wrap_doc = proj / '꺾인.md'
drag_doc = proj / '끌기.md'
wrap_doc.write_text(WRAP_DOC, encoding='utf-8')
drag_doc.write_text(DRAG_DOC, encoding='utf-8')
code_file = proj / '셈.py'
code_file.write_text('a = 1\nb = 2\nc = 3\nd = 4\ne = 5\n', encoding='utf-8')
KEEP_DOC = ('# 지우기\n\n- 가 항목\n  1. 나 항목\n  2. 다 항목\n\n     다 항목의 둘째 문단\n  3. 라 항목\n  4. 마 항목\n- 바 항목\n\n'
            '> [!TIP]\n> 사 첫 줄\n> 아 둘째 줄\n\n1. 자 하나\n2. 차 둘\n\n카 문단\n\n1. 타 하나\n2. 파 둘\n\n'
            '- 하 위\n- 거 항목\n  - 너 하위\n- 더 끝\n')
keep_doc = proj / '지우기.md'
keep_doc.write_text(KEEP_DOC, encoding='utf-8')
FRONT_DOC = '---\ntitle: 머리 시험\nstatus: 진행중\n---\n\n# 머리 문서\n\n본문 글\n\n- 가 항목\n- 나 항목\n- 다 항목\n\n1. 하나\n2. 둘\n3. 셋\n'
front_doc = proj / '머리.md'
front_doc.write_text(FRONT_DOC, encoding='utf-8')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)

# 칸의 커서 자리(글자 수)와 화면 줄마다의 첫 글자 자리 — 글자 상자의 높이로 센다 (커서의 상자는 꺾인 자리에서 윗줄 끝으로 재지므로 쓰지 않는다)
CARET = """() => { const sp = document.activeElement; if (!sp?.classList?.contains('lec-line-edit')) return null;
  const sel = getSelection(); const pre = document.createRange(); pre.selectNodeContents(sp); pre.setEnd(sel.focusNode, sel.focusOffset);
  const node = sp.firstChild; const text = sp.textContent; const starts = [0]; let prev = null;
  for (let i = 0; node && i < text.length; i++) { const r = document.createRange(); r.setStart(node, i); r.setEnd(node, i + 1);
    const b = [...r.getClientRects()].find((x) => x.width); if (!b) continue;
    if (prev != null && b.top - prev > b.height / 2) starts.push(i); prev = b.top; }
  return { text: text.slice(0, 10), offset: pre.toString().length, starts, len: text.length }; }"""
# 칸 안의 i 번째 글자의 왼쪽 끝 화면 자리
CHAR_AT = """(i) => { const sp = document.activeElement; const r = document.createRange(); r.setStart(sp.firstChild, i); r.setEnd(sp.firstChild, i + 1);
  const b = [...r.getClientRects()].find((x) => x.width); return { x: b.left + 1, y: b.top + b.height / 2 }; }"""
# 화면의 글 t1 의 k1 째 글자부터 t2 의 k2 째 글자까지 고른다 (끌기와 같은 브라우저의 고르기)
SELECT = """([t1, k1, t2, k2]) => { const find = (t) => { const w = document.createTreeWalker(document.querySelector('#lec-view'), NodeFilter.SHOW_TEXT);
    for (let n = w.nextNode(); n; n = w.nextNode()) { const i = n.data.indexOf(t); if (i >= 0) return [n, i]; } return null; };
  const [a, i] = find(t1); const [b, j] = find(t2); getSelection().setBaseAndExtent(a, i + k1, b, j + k2); return getSelection().toString(); }"""
EDITING = "document.activeElement?.classList?.contains('lec-line-edit') ? document.activeElement.textContent.slice(0, 10) : null"
TOAST = "document.querySelector('#lec-toast')?.textContent ?? ''"


def text_of(path):
    for _ in range(40):
        try:
            return path.read_text(encoding='utf-8')
        except OSError:   # 앱이 파일을 바꿔 끼우는 순간 (ReplaceFileW)
            time.sleep(0.02)
    return path.read_text(encoding='utf-8')


def paras(path):
    """파일의 글 줄 가운데 '문단'·'코드' 로 시작하는 것 — 차례째"""
    return [s.split(' ')[1] if s.startswith('문단') else s for s in text_of(path).split('\n') if s.startswith(('문단', '코드', '```'))]


line_of = lambda c: max(i for i, s in enumerate(c['starts']) if s <= c['offset'])   # 꺾인 자리는 아랫줄로 센다

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_context(viewport={'width': 1100, 'height': 900}, locale='ko-KR').new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('dialog', lambda d: d.accept())
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')
        caret = lambda: page.evaluate(CARET)
        editing = lambda: page.evaluate(EDITING)

        def open_doc(name, title):
            page.locator(f'#lec-tree .row.file[data-doc="{name}"]').click()
            page.wait_for_selector(f'#lec-view h1:has-text("{title}")')
            page.wait_for_timeout(300)

        def edit(sel, text):
            loc = page.locator(sel, has_text=text).first
            loc.scroll_into_view_if_needed()
            loc.click(position={'x': 30, 'y': 8})
            page.keyboard.press('Enter')
            until(page, lambda: editing() is not None, 5000)
            page.wait_for_timeout(100)

        def settle_on(prefix, ms=5000):
            """칸이 prefix 로 시작하는 줄에서 열리고 커서가 멈출 때까지"""
            got = until(page, lambda: (editing() or '').startswith(prefix), ms)
            page.wait_for_timeout(300)
            return got

        open_doc('꺾인.md', '꺾인 줄')
        print('[꺾인 줄의 ↑ — 둘째 화면 줄 맨 앞]')
        edit('#lec-view p', '인공지능')
        c = caret()
        n = len(c['starts'])
        check('긴 줄이 화면에서 다섯 줄 넘게 꺾인다 (시험의 전제)', n >= 5, c)
        check('칸을 열면 커서는 글 끝 (맨 아랫줄)', c['offset'] == c['len'] and line_of(c) == n - 1, c)
        for _ in range(n - 2):
            page.keyboard.press('ArrowUp')
        page.keyboard.press('Home')
        page.wait_for_timeout(150)
        c = caret()
        check('↑ 로 둘째 화면 줄까지 오르고 Home 은 그 줄 맨 앞 (꺾인 자리)', c and c['offset'] == c['starts'][1], c)
        page.keyboard.press('ArrowUp')
        page.wait_for_timeout(300)
        c = caret()
        check('그 자리의 ↑ 는 칸 안에서 맨 윗줄로 — 윗줄로 넘어가지 않는다', c and c['text'].startswith('인공지능') and c['offset'] < c['starts'][1], c)
        page.keyboard.press('ArrowUp')
        check('맨 윗줄의 ↑ 는 앞 원문 줄로', settle_on('짧은 줄 A'), editing())
        page.keyboard.press('Escape')

        print('[꺾인 줄의 ↑ — 둘째 화면 줄 맨 앞을 누르고]')
        edit('#lec-view p', '인공지능')
        at = page.evaluate(CHAR_AT, caret()['starts'][1])
        page.mouse.click(at['x'], at['y'])
        page.wait_for_timeout(150)
        c = caret()
        check('둘째 화면 줄의 첫 글자 앞을 누르면 커서가 꺾인 자리', c and c['offset'] == c['starts'][1], c)
        page.keyboard.press('ArrowUp')
        page.wait_for_timeout(300)
        c = caret()
        check('— 그 ↑ 는 칸 안에서 오른다', c and c['text'].startswith('인공지능') and c['offset'] < c['starts'][1], c)
        page.keyboard.press('Escape')

        print('[꺾인 줄의 ↓ — 끝에서 둘째 화면 줄의 끝]')
        edit('#lec-view p', '인공지능')
        page.keyboard.press('ArrowUp')
        page.keyboard.press('End')
        page.wait_for_timeout(150)
        before = caret()
        page.keyboard.press('ArrowDown')
        page.wait_for_timeout(300)
        c = caret()
        check('끝에서 둘째 줄 끝의 ↓ 는 칸 안의 맨 아랫줄로', c and c['text'].startswith('인공지능') and line_of(c) == n - 1, [before, c])
        page.keyboard.press('ArrowDown')
        check('맨 아랫줄의 ↓ 는 다음 원문 줄로', settle_on('짧은 줄 B'), editing())
        page.keyboard.press('Escape')

        print('[빠르게 거듭 누른 ↑ — 넘어가는 사이에 모아 둔 것도 칸 안부터]')
        for presses in (2, 4):
            edit('#lec-view p', '짧은 줄 B')
            for _ in range(presses):
                page.keyboard.press('ArrowUp')
            settle_on('인공지능')
            page.wait_for_timeout(500)
            c = caret()
            want = n - presses   # 첫 ↑ 는 긴 줄의 맨 아랫줄(n - 1)로 들어가고 나머지는 한 화면 줄씩
            check(f'짧은 줄 B 에서 ↑ {presses}번 — 긴 줄의 {want + 1}째 화면 줄 (건너뛰지 않음)', c and c['text'].startswith('인공지능') and line_of(c) == want, c)
            page.keyboard.press('Escape')
            page.wait_for_timeout(200)

        print('[표의 칸의 꺾인 글]')
        edit('#lec-view td', '표의 칸')
        c = caret()
        rows = len(c['starts']) if c else 0
        check('표의 칸이 여러 줄로 꺾인다 (시험의 전제)', rows >= 3, c)
        for _ in range(rows - 2):
            page.keyboard.press('ArrowUp')
        page.keyboard.press('Home')
        page.keyboard.press('ArrowUp')
        page.wait_for_timeout(300)
        c = caret()
        check('칸의 둘째 화면 줄 맨 앞의 ↑ 는 칸 안에서', c and c['text'].startswith('표의 칸') and c['offset'] < c['starts'][1], c)
        page.keyboard.press('Escape')

        print('[끌어 여러 줄에 걸쳐 고른 글 — Delete 한 번]')
        open_doc('끌기.md', '끌기')

        def reset():
            page.keyboard.press('Escape')   # 고른 글
            page.keyboard.press('Escape')   # 잡아 둔 줄·고른 줄
            page.evaluate('getSelection().removeAllRanges()')
            drag_doc.write_text(DRAG_DOC, encoding='utf-8')
            until(page, lambda: page.locator('#lec-view p', has_text='문단 B').count() == 1 and page.locator('#lec-view p', has_text='문단 C').count() == 1, 6000)
            page.wait_for_timeout(500)

        def drag(t1, t2):
            """t1 문단의 왼쪽에서 t2 문단의 가운데까지 마우스로 끈다"""
            a = page.locator('#lec-view p', has_text=t1).bounding_box()
            z = page.locator('#lec-view p', has_text=t2).bounding_box()
            page.mouse.move(a['x'] + 3, a['y'] + a['height'] / 2)
            page.mouse.down()
            page.mouse.move(z['x'] + 30, z['y'] + z['height'] / 2, steps=8)
            page.mouse.up()
            page.wait_for_timeout(200)

        reset()
        drag('문단 B', '문단 D')
        check('끌어서 문단 B~D 의 글을 고름 (시험의 전제)', '문단 C' in page.evaluate('getSelection().toString()'))
        page.keyboard.press('Delete')
        expect(page, 'Delete 한 번에 끌어 고른 문단 B·C·D 를 지운다', lambda: paras(drag_doc)[:2] == ['A', 'E'], lambda: paras(drag_doc))
        expect(page, '— 지웠다고 알림 (되돌리는 키와)', lambda: '지웠습니다' in page.evaluate(TOAST))
        page.keyboard.press('Control+z')
        expect(page, '— Ctrl+Z 로 되돌림', lambda: paras(drag_doc)[:5] == ['A', 'B', 'C', 'D', 'E'], lambda: paras(drag_doc))

        print('[끌어 고른 글 — Ctrl+X·Alt+↓]')
        reset()
        drag('문단 B', '문단 D')
        page.keyboard.press('Control+x')
        expect(page, 'Ctrl+X 는 끌어 고른 줄들을 잘라 낸다', lambda: paras(drag_doc)[:2] == ['A', 'E'], lambda: paras(drag_doc))
        expect(page, '— 잘라 냈다고 알림', lambda: '잘라 냈습니다' in page.evaluate(TOAST))
        reset()
        drag('문단 B', '문단 C')
        page.keyboard.press('Alt+ArrowDown')
        expect(page, 'Alt+↓ 는 끌어 고른 문단 B·C 를 함께 아래로', lambda: paras(drag_doc)[:5] == ['A', 'D', 'B', 'C', 'E'], lambda: paras(drag_doc))

        print('[한 줄 안의 고른 글·끝에서 멈춘 고르기·고른 줄이 먼저]')
        reset()
        page.locator('#lec-view p', has_text='문단 B').click()
        page.evaluate(SELECT, ['문단 B', 3, '문단 B', 6])
        page.keyboard.press('Delete')
        page.wait_for_timeout(800)
        check('한 줄 안의 고른 글은 Delete 한 번에 바뀌지 않는다 (한 줄은 두 번 — D139)', paras(drag_doc)[:3] == ['A', 'B', 'C'], paras(drag_doc))
        reset()
        page.locator('#lec-view p', has_text='문단 B').click()
        page.evaluate(SELECT, ['문단 B', 2, '문단 D', 0])
        page.keyboard.press('Delete')
        expect(page, '문단 D 의 맨 앞에서 멈춘 고르기는 D 를 지우지 않는다 (B·C 만)', lambda: paras(drag_doc)[:3] == ['A', 'D', 'E'], lambda: paras(drag_doc))
        reset()
        page.locator('#lec-view p', has_text='문단 A').click()
        page.keyboard.press('Shift+ArrowDown')
        page.evaluate(SELECT, ['문단 D', 0, '문단 E', 3])
        page.keyboard.press('Delete')
        expect(page, 'Shift+↓ 로 고른 줄이 있으면 남아 있던 고른 글보다 그 줄들이 먼저 (A·B)', lambda: paras(drag_doc)[:3] == ['C', 'D', 'E'], lambda: paras(drag_doc))
        reset()
        page.locator('#lec-view p', has_text='문단 A').click()
        page.keyboard.press('Shift+ArrowDown')
        drag('문단 D', '문단 E')
        page.keyboard.press('Delete')
        expect(page, '고른 줄(A·B) 밖에서 새로 끌어 고르면 그 끌기의 줄 (D·E)', lambda: paras(drag_doc)[:4] == ['A', 'B', 'C', '```'], lambda: paras(drag_doc))
        reset()
        page.locator('#lec-view p', has_text='문단 A').click()
        page.keyboard.press('Delete')   # 현재 줄 A 를 잡기만 한다
        page.evaluate(SELECT, ['문단 B', 0, '문단 C', 3])   # 잡아 둔 줄을 누르지 않고 고른 글 — 끌기를 A 안에서 시작한 것과 같다
        page.keyboard.press('Delete')
        expect(page, '잡아 둔 한 줄(A)보다 끌어 고른 여러 줄(B·C)이 먼저', lambda: paras(drag_doc)[:3] == ['A', 'D', 'E'], lambda: paras(drag_doc))

        print('[코드 블록을 함께 고른 지우기]')
        reset()
        page.locator('#lec-view p', has_text='문단 E').click()
        page.evaluate(SELECT, ['문단 E', 0, '코드 둘', 3])
        page.keyboard.press('Delete')
        expect(page, '문단 E 부터 코드의 끝 줄까지 끌어 고르면 코드 블록째 지운다', lambda: paras(drag_doc)[4:] == ['F', 'G'], lambda: paras(drag_doc))
        reset()
        page.locator('#lec-view p', has_text='문단 E').click()
        page.keyboard.press('Shift+ArrowDown')
        page.keyboard.press('Shift+ArrowDown')
        page.keyboard.press('Delete')
        expect(page, 'Shift+↓ 로 문단 E 부터 코드의 끝 줄까지 고른 것도 블록째', lambda: paras(drag_doc)[4:] == ['F', 'G'], lambda: paras(drag_doc))
        expect(page, '— 블록이 깨진다는 알림은 없다', lambda: '깨집니다' not in page.evaluate(TOAST))

        print('[한 줄 지우기 — 위아래 줄의 종류·레벨이 그대로]')
        open_doc('지우기.md', '지우기')

        def delete_here(sel, text):
            page.keyboard.press('Escape')
            page.keyboard.press('Escape')
            keep_doc.write_text(KEEP_DOC, encoding='utf-8')
            until(page, lambda: page.locator(sel, has_text=text).count() >= 1 and page.locator('#lec-view p', has_text='카 문단').count() == 1, 6000)
            page.wait_for_timeout(400)
            page.locator(sel, has_text=text).first.click(position={'x': 30, 'y': 8})
            page.keyboard.press('Delete')   # 현재 줄을 잡기만 한다 (D139)
            page.keyboard.press('Delete')

        body = lambda: text_of(keep_doc)
        delete_here('#lec-view li li', '다 항목')   # 바깥 항목('가 항목')도 이 글을 담는다 — 안쪽 항목으로
        expect(page, '둘째 문단이 있는 항목을 지우면 둘째 문단이 그 번호를 넘겨받고 아래 항목은 목록에 남는다',
               lambda: '  2. 다 항목의 둘째 문단\n  3. 라 항목\n  4. 마 항목\n- 바 항목' in body() and '다 항목\n' not in body(), body)
        delete_here('#lec-view p', '사 첫 줄')
        expect(page, '강조글의 첫 줄을 지워도 강조글 그대로 (머리 줄이 남는다)', lambda: '> [!TIP]\n> 아 둘째 줄\n' in body() and '사 첫 줄' not in body(), body)
        expect(page, '— 화면도 강조글', lambda: page.locator('#lec-view blockquote.alert', has_text='아 둘째 줄').count() == 1)
        delete_here('#lec-view p', '카 문단')
        expect(page, '두 붙은 목록 사이의 문단을 지우면 붙은 목록 하나로 — 번호는 이어서', lambda: '1. 자 하나\n2. 차 둘\n3. 타 하나\n4. 파 둘\n' in body(), body)
        delete_here('#lec-view li', '거 항목')
        expect(page, '하위 항목이 있는 항목을 지우면 하위 항목은 레벨 그대로 앞 항목 아래로', lambda: '- 하 위\n  - 너 하위\n- 더 끝\n' in body(), body)
        expect(page, '— 화면도 둘째 레벨', lambda: page.locator('#lec-view li li', has_text='너 하위').count() == 1)

        print('[머리 설정은 접힌 채로]')
        open_doc('머리.md', '머리 문서')
        fm_open = "document.querySelector('#lec-view details.front-matter')?.open"
        check('문서 맨 위의 머리 설정은 처음에 접혀 있다', page.evaluate(fm_open) is False, page.evaluate(fm_open))
        check('— 접혀 있어도 값은 문서에 있다 (인쇄·제목이 읽는다)', '머리 시험' in (page.locator('#lec-view .front-matter').text_content() or ''))
        page.locator('#lec-view .front-matter summary').click()
        expect(page, '누르면 펼친다', fm_open)
        front_doc.write_text(FRONT_DOC.replace('본문 글', '본문 글 고침'), encoding='utf-8')
        expect(page, '— 편 문서는 자동 새로고침에도 편 채', lambda: page.locator('#lec-view p', has_text='본문 글 고침').count() == 1 and page.evaluate(fm_open))
        page.locator('#lec-view .front-matter summary').click()
        front_doc.write_text(FRONT_DOC, encoding='utf-8')
        expect(page, '— 다시 접으면 새로고침에도 접힌 채', lambda: page.locator('#lec-view p', has_text='본문 글 고침').count() == 0 and page.evaluate(fm_open) is False)
        page.locator('#lec-view p', has_text='본문 글').click()
        page.keyboard.press('Control+f')
        page.keyboard.type('진행중')
        expect(page, '— 찾기가 머리 설정 안을 찾으면 펼친다', fm_open)
        page.keyboard.press('Escape')

        print('[새 항목의 레벨을 바꾸면 글머리표가 바로]')
        BULLET = """() => { const li = document.querySelector('#lec-view .lec-new-line .lec-line-edit')?.closest('li'); if (!li) return null;
          let depth = 0; for (let e = li.parentElement; e && e.id !== 'lec-view'; e = e.parentElement) if (/^(UL|OL)$/.test(e.tagName)) depth += 1;
          return [getComputedStyle(li).listStyleType, depth, [...li.parentElement.children].indexOf(li) + 1]; }"""
        for item, top, sub, at in (('나 항목', 'disc', 'circle', 3), ('둘', 'decimal', 'decimal', 3)):
            page.locator('#lec-view li', has_text=item).click()
            page.keyboard.press('Shift+Enter')
            until(page, "!!document.querySelector('#lec-view .lec-new-line .lec-line-edit')", 4000)
            first = page.evaluate(BULLET)
            page.keyboard.press('Tab')
            page.wait_for_timeout(200)
            inner = page.evaluate(BULLET)
            page.keyboard.press('Shift+Tab')
            page.wait_for_timeout(200)
            outer = page.evaluate(BULLET)
            check(f'{item} 아래 빈 새 항목의 Tab — 하위 목록의 첫 항목 모양 그대로 ({sub}, 1번째), Shift+Tab 으로 되돌아옴',
                  first == [top, 1, at] and inner == [sub, 2, 1] and outer == [top, 1, at], [first, inner, outer])
            page.keyboard.press('Tab')
            page.keyboard.press('Escape')   # 쓰지 않고 그만두기
            page.wait_for_timeout(300)
            check(f'— 그만두면 레벨을 바꾸며 만든 하위 목록도 남지 않는다 ({item})', page.evaluate("document.querySelectorAll('#lec-view li > :is(ul, ol):empty').length") == 0)

        print('[코드 화면에서 끌어 고른 줄]')
        page.keyboard.press('Escape')
        page.keyboard.press('Control+p')
        page.keyboard.type('셈.py')
        page.locator('#lec-palette-list li.code', has_text='셈.py').click(modifiers=['Alt'])
        page.wait_for_selector('#lec-view.code-view .cv-line[data-line="4"]')
        page.wait_for_timeout(300)
        a = page.locator('#lec-view .cv-line[data-line="2"]').bounding_box()
        z = page.locator('#lec-view .cv-line[data-line="4"]').bounding_box()
        page.mouse.move(a['x'] + 60, a['y'] + a['height'] / 2)
        page.mouse.down()
        page.mouse.move(a['x'] + 70, z['y'] + z['height'] / 2, steps=8)
        page.mouse.up()
        page.wait_for_timeout(200)
        page.keyboard.press('Delete')
        expect(page, '코드 화면에서 끌어 고른 2~4행을 Delete 한 번에', lambda: text_of(code_file) == 'a = 1\ne = 5\n', lambda: text_of(code_file))

        check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
