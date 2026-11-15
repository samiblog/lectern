"""사이드바 '파일' 탭 (D143): 문서·코드·자료를 한 번에 하나만 펼친다, 접힌 머리줄의 개수(거르는 중이면 맞는 수), '문서'의 하위 묶음
(전체·문서·슬라이드·HTML·업무·형광펜·할 일 — 없는 종류는 감춤), 형광펜 하위 묶음에서 그 자리로·메모 달기·지우기, 문서 안의 F8·Shift+F8."""
import json
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-sidekinds-'))
proj = base / 'proj'
config = base / 'config'
(proj / 'report').mkdir(parents=True)
(proj / 'slides').mkdir()
(proj / 'code').mkdir()
(proj / 'data').mkdir()
MARKED = ('# 시장 점검\n\n구리 가격은 <mark>크게 올랐다</mark> 그리고 니켈도.\n\n'
          '- [ ] 공급 자료 받기\n- [x] 끝낸 일\n\n둘째 문단의 <mark class="green">초록 말</mark> 과 <mark>노랑 말</mark>.\n\n끝 문단.\n')
(proj / 'report' / '점검.md').write_text(MARKED, encoding='utf-8')
(proj / 'report' / '메모.md').write_text('# 메모\n\n칠하지 않은 글.\n', encoding='utf-8')
(proj / 'slides' / '발표.md').write_text('---\nmarp: true\n---\n\n# 발표\n\n---\n\n## 둘째 장\n', encoding='utf-8')
(proj / 'WORK.md').write_text('# 업무\n\n## 할 일\n\n- [ ] 보고서 마감\n', encoding='utf-8')
(proj / 'code' / 'calc.py').write_text('x = 1\n', encoding='utf-8')
(proj / 'data' / '표.csv').write_text('a,b\n1,2\n', encoding='utf-8')
doc = proj / 'report' / '점검.md'
server, url, port = serve(proj, config)

KINDS = "() => [...document.querySelectorAll('#lec-docs .kind-head')].map((b) => b.dataset.kind + ':' + (b.querySelector('.n')?.textContent || ''))"
OPEN_KIND = "() => document.querySelector('#lec-docs .kind-head.open')?.dataset.kind ?? null"
TREE_DOCS = "() => [...document.querySelectorAll('#lec-tree .row.file')].map((r) => r.dataset.doc)"
ITEMS = "() => [...document.querySelectorAll('#lec-tree .row.item')].map((r) => r.dataset.itemDoc + '#' + r.dataset.line + ':' + r.querySelector('.label').textContent)"
SECS = "() => ['#lec-docs', '#lec-code', '#lec-others'].map((s) => document.querySelector(s).classList.contains('grow') ? 'open' : 'closed')"


def read():
    return doc.read_text(encoding='utf-8').replace('\r\n', '\n')


def saved():
    try:
        return json.loads((config / 'config.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1300, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        dialogs = []
        page.on('dialog', lambda d: (dialogs.append(d.message), d.accept()))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        toast = lambda: page.text_content('#lec-toast') or ''

        print('[한 번에 한 묶음]')
        check('처음은 문서만 펼쳐져 있다', page.evaluate(SECS) == ['open', 'closed', 'closed'], page.evaluate(SECS))
        tree_h = page.locator('#lec-tree').bounding_box()['height']
        check('펼친 문서 목록이 남은 높이를 쓴다', tree_h > 400, tree_h)
        check('접힌 머리줄에도 개수', until(page, lambda: page.inner_text('#lec-code-count') == '1' and page.inner_text('#lec-others-count') == '1'),
              [page.inner_text('#lec-code-count'), page.inner_text('#lec-others-count')])
        page.click('#lec-code-head')
        check('코드를 누르면 코드만 펼친다', page.evaluate(SECS) == ['closed', 'open', 'closed'], page.evaluate(SECS))
        check('코드 목록이 보인다', until(page, lambda: page.locator('#lec-code-list .row').count() > 0))
        check('설정에 남는다', until(page, lambda: saved().get('files_open') == 'code'), saved().get('files_open'))
        page.click('#lec-code-head')
        check('펼친 것을 다시 눌러도 그대로', page.evaluate(SECS) == ['closed', 'open', 'closed'], page.evaluate(SECS))
        page.fill('#lec-filter', 'calc')
        check('거르는 중이면 접힌 머리줄에 맞는 수', until(page, lambda: page.inner_text('#lec-docs-count') == '0' and page.inner_text('#lec-others-count') == '0' and page.inner_text('#lec-code-count') == '1'),
              [page.inner_text('#lec-docs-count'), page.inner_text('#lec-code-count'), page.inner_text('#lec-others-count')])
        page.fill('#lec-filter', '')
        page.click('#lec-docs-head')
        check('문서로 돌아온다', page.evaluate(SECS) == ['open', 'closed', 'closed'], page.evaluate(SECS))

        print('[문서의 하위 묶음]')
        until(page, lambda: page.locator('#lec-docs .kind-head').count() > 0)
        kinds = page.evaluate(KINDS)
        check('하위 묶음: 전체·문서·슬라이드·업무·형광펜·할 일 (HTML 은 없어서 감춤)', [k.split(':')[0] for k in kinds] == ['all', 'md', 'deck', 'work', 'marks', 'tasks'], kinds)
        check('개수 — 형광펜·할 일은 아직 읽지 않아 비어 있다', kinds[:4] == ['all:4', 'md:3', 'deck:1', 'work:1'] and kinds[4:] == ['marks:', 'tasks:'], kinds)
        check('처음은 전체', page.evaluate(OPEN_KIND) == 'all')
        page.click('#lec-docs .kind-head[data-kind="deck"]')
        check('슬라이드만', until(page, lambda: page.evaluate(TREE_DOCS) == ['slides/발표.md']), page.evaluate(TREE_DOCS))
        order = page.evaluate("() => [...document.querySelector('#lec-docs').children].map((e) => e.id || e.className)")
        check('펼친 하위 묶음 바로 아래에 트리, 나머지는 그 아래', order.index('lec-doc-kinds-top') < order.index('lec-tree') < order.index('lec-doc-kinds-bottom')
              and page.evaluate("document.querySelector('#lec-doc-kinds-top').lastElementChild.dataset.kind") == 'deck', order)
        check('설정에 남는다', until(page, lambda: saved().get('docs_kind') == 'deck'), saved().get('docs_kind'))
        page.click('#lec-docs .kind-head[data-kind="work"]')
        check('업무: WORK.md', until(page, lambda: page.evaluate(TREE_DOCS) == ['WORK.md']), page.evaluate(TREE_DOCS))
        page.click('#lec-docs .kind-head[data-kind="md"]')
        check('문서: 슬라이드를 뺀 Markdown', until(page, lambda: sorted(page.evaluate(TREE_DOCS)) == ['WORK.md', 'report/메모.md', 'report/점검.md']), page.evaluate(TREE_DOCS))

        print('[형광펜·할 일]')
        page.click('#lec-docs .kind-head[data-kind="tasks"]')
        check('할 일: 열린 할 일이 있는 문서와 그 할 일', until(page, lambda: page.evaluate(ITEMS) == ['report/점검.md#5:공급 자료 받기', 'WORK.md#5:보고서 마감']), page.evaluate(ITEMS))
        page.click('#lec-docs .kind-head[data-kind="marks"]')
        check('형광펜: 칠한 곳이 문서 아래에', until(page, lambda: page.evaluate(ITEMS) == ['report/점검.md#3:크게 올랐다', 'report/점검.md#8:초록 말', 'report/점검.md#8:노랑 말']), page.evaluate(ITEMS))
        kinds = page.evaluate(KINDS)
        check('읽은 뒤에는 형광펜·할 일에도 개수', 'marks:3' in kinds and 'tasks:2' in kinds, kinds)
        swatches = page.evaluate("() => [...document.querySelectorAll('#lec-tree .row.item .swatch')].map((s) => s.className)")
        check('색 표시', swatches == ['swatch mark-yellow', 'swatch mark-green', 'swatch mark-yellow'], swatches)
        page.locator('#lec-tree .row.item', has_text='초록 말').click()
        check('누르면 그 문서의 그 줄로', until(page, lambda: page.evaluate("import('/static/js/store.js').then(({ S }) => S.pane?.here?.path === 'report/점검.md' && S.pane.here.line)") == 8),
              page.evaluate("import('/static/js/store.js').then(({ S }) => S.pane?.here)"))
        page.fill('#lec-filter', '노랑')
        check('거르면 글이 맞는 칠한 곳만', until(page, lambda: page.evaluate(ITEMS) == ['report/점검.md#8:노랑 말']), page.evaluate(ITEMS))
        page.fill('#lec-filter', '')

        print('[메모 달기]')
        page.locator('#lec-tree .row.item', has_text='크게 올랐다').click(button='right')
        page.wait_for_selector('#lec-menu:not([hidden])')
        labels = page.evaluate("[...document.querySelectorAll('#lec-menu button[data-i] > span')].map((e) => e.textContent)")
        check('칠한 곳의 우클릭: 그 자리로·메모 달기·이것만 지우기·모두 지우기', labels == ['그 자리로 가기', '메모 달기', '이 형광펜 지우기', '이 문서의 형광펜 모두 지우기…'], labels)
        page.locator('#lec-menu button', has_text='메모 달기').click()
        notes = proj / '.lectern' / 'notes.md'
        page.wait_for_selector('.note-card')
        page.keyboard.type('나중에 다시 볼 것')
        check('메모가 생기고 칠한 글이 제목, 그 자리와 찾을 글이 남는다', until(page, lambda: notes.exists() and '## 크게 올랐다' in notes.read_text(encoding='utf-8')
              and 'line=3' in notes.read_text(encoding='utf-8') and 'find=' in notes.read_text(encoding='utf-8'), 8000), notes.read_text(encoding='utf-8')[:300] if notes.exists() else None)
        doc.write_text('# 시장 점검\n\n새로 넣은 문단.\n\n또 넣은 문단.\n\n' + MARKED.split('\n', 2)[2], encoding='utf-8')
        until(page, lambda: page.evaluate("import('/static/js/store.js').then(({ S }) => S.tab.files.length)") > 0)
        page.wait_for_timeout(1500)
        page.locator('.note-card .note-from').first.click()
        check('줄이 밀려도 메모의 그 자리로 가면 그 글의 줄', until(page, lambda: page.evaluate("import('/static/js/store.js').then(({ S }) => S.pane?.here?.line)") == 7),
              page.evaluate("import('/static/js/store.js').then(({ S }) => S.pane?.here)"))
        page.keyboard.press('Alt+m')   # 메모 닫기
        doc.write_text(MARKED, encoding='utf-8')
        until(page, lambda: page.evaluate("import('/static/js/store.js').then(({ S }) => S.pane?.source?.lines?.join('\\n'))") == MARKED, 10000)

        print('[지우기]')
        until(page, lambda: page.evaluate(ITEMS) == ['report/점검.md#3:크게 올랐다', 'report/점검.md#8:초록 말', 'report/점검.md#8:노랑 말'], 10000)
        page.locator('#lec-tree .row.item', has_text='초록 말').click(button='right')
        page.wait_for_selector('#lec-menu:not([hidden])')
        page.locator('#lec-menu button', has_text='이 형광펜 지우기').click()
        check('이 형광펜 지우기: 그것만, 글은 그대로', until(page, lambda: '둘째 문단의 초록 말 과 <mark>노랑 말</mark>.' in read()), read())
        check('목록에서도 빠진다', until(page, lambda: page.evaluate(ITEMS) == ['report/점검.md#3:크게 올랐다', 'report/점검.md#8:노랑 말']), page.evaluate(ITEMS))
        page.locator('#lec-view h1').click()
        page.keyboard.press('Control+z')
        check('Ctrl+Z 로 되돌린다', until(page, lambda: read() == MARKED), read())
        until(page, lambda: len(page.evaluate(ITEMS)) == 3, 10000)
        page.locator('#lec-tree .row.file[data-doc="report/점검.md"]').click(button='right')
        page.wait_for_selector('#lec-menu:not([hidden])')
        labels = page.evaluate("[...document.querySelectorAll('#lec-menu button[data-i] > span')].map((e) => e.textContent)")
        check('문서 행의 우클릭: 모두·색마다 지우기', '이 문서의 형광펜 모두 지우기…' in labels and '이 문서의 초록 형광펜만 지우기…' in labels and '이 문서의 노랑 형광펜만 지우기…' in labels, labels)
        page.locator('#lec-menu button', has_text='이 문서의 노랑 형광펜만 지우기').click()
        check('색 하나만 — 몇 곳인지 묻고 지운다', until(page, lambda: '<mark' in read() and read().count('<mark') == 1 and 'class="green"' in read()) and any('2곳' in d for d in dialogs), (read(), dialogs))
        page.locator('#lec-tree .row.file[data-doc="report/점검.md"]').click(button='right')
        page.wait_for_selector('#lec-menu:not([hidden])')
        page.locator('#lec-menu button', has_text='이 문서의 형광펜 모두 지우기').click()
        check('모두 지우기', until(page, lambda: '<mark' not in read()) and '크게 올랐다' in read(), read())
        check('칠한 곳이 없으면 그렇게 알린다', until(page, lambda: page.evaluate(ITEMS) == [] and '칠한 곳이 없습니다' in page.inner_text('#lec-tree')), page.inner_text('#lec-tree'))
        page.locator('#lec-view h1').click()
        page.keyboard.press('Control+z')
        page.keyboard.press('Control+z')
        check('되돌리기 두 걸음', until(page, lambda: read() == MARKED), read())

        print('[F8 · Shift+F8]')
        until(page, lambda: page.evaluate("import('/static/js/store.js').then(({ S }) => S.pane?.source?.lines?.join('\\n'))") == MARKED, 10000)
        page.wait_for_timeout(400)
        page.locator('#lec-view h1').click()
        sel = lambda: page.evaluate('getSelection().toString()')
        page.keyboard.press('F8')
        check('F8: 첫 형광펜을 고른다', sel() == '크게 올랐다', sel())
        page.keyboard.press('F8')
        check('F8: 다음', sel() == '초록 말', sel())
        page.keyboard.press('F8')
        page.keyboard.press('F8')
        check('끝에서는 돌지 않고 알린다', sel() == '노랑 말' and '마지막 형광펜' in toast(), (sel(), toast()))
        page.keyboard.press('Shift+F8')
        check('Shift+F8: 앞의 것', sel() == '초록 말', sel())
        page.keyboard.press('m')
        check('고른 채라 M 으로 색을 바꾼다', until(page, lambda: '<mark class="pink">초록 말</mark>' in read()), read())

        print('[문서 안의 칠한 글을 우클릭]')
        page.keyboard.press('Control+z')
        until(page, lambda: read() == MARKED)
        until(page, lambda: page.evaluate("import('/static/js/store.js').then(({ S }) => S.pane?.source?.lines?.join('\\n'))") == MARKED, 10000)
        page.wait_for_timeout(400)
        labels = lambda: page.evaluate("[...document.querySelectorAll('#lec-menu button[data-i] > span')].map((e) => e.textContent)")

        def menu_at(text):
            page.locator('#lec-view mark', has_text=text).click(button='right')
            page.wait_for_selector('#lec-menu:not([hidden])')
            return labels()

        page.locator('#lec-view h1').click()
        page.keyboard.press('F8')
        got = menu_at('크게 올랐다')
        check('F8 로 고른 칠한 글: 서식 뒤에 담기·보내기·메모 달기, 이 형광펜 지우기, 블록의 메뉴',
              got[0] == '고른 글 복사' and got.index('서식 풀기') < got.index('고른 글 담기') < got.index('메모 달기') < got.index('이 형광펜 지우기') < got.index('이 블록의 메뉴…')
              and '새 메모로 보내기' not in got, got)
        check('고른 글 복사 옆에 터미널 버튼', page.locator('#lec-menu .menu-row', has=page.locator('button[data-i]', has_text='고른 글 복사')).locator('.menu-term').count() == 1)
        page.locator('#lec-menu button', has_text='이 형광펜 지우기').click()
        check('문서에서 이 형광펜 지우기: 그것만, 글은 그대로', until(page, lambda: '구리 가격은 크게 올랐다 그리고' in read() and read().count('<mark') == 2), read())
        page.locator('#lec-view h1').click()
        page.keyboard.press('Control+z')
        check('되돌린다', until(page, lambda: read() == MARKED), read())
        until(page, lambda: page.evaluate("import('/static/js/store.js').then(({ S }) => S.pane?.source?.lines?.join('\\n'))") == MARKED, 10000)
        page.wait_for_timeout(400)
        word = page.locator('#lec-view mark', has_text='노랑 말')
        word.dblclick()   # 칠한 글 안의 낱말을 두 번 눌러 고른다
        page.wait_for_timeout(200)
        menu_at('노랑 말')
        page.locator('#lec-menu button', has_text='메모 달기').click()
        page.wait_for_selector('.note-card')
        check('칠한 글 안의 낱말에서도 메모 달기 — 칠한 글 통째가 제목', until(page, lambda: '## 노랑 말' in notes.read_text(encoding='utf-8'), 8000), notes.read_text(encoding='utf-8')[-200:])
        page.keyboard.press('Alt+m')
        end_p = page.locator('#lec-view p', has_text='끝 문단')
        end_p.dblclick(position={'x': 8, 'y': 8})   # 글 위를 — 문단 가운데는 빈 곳이라 아무것도 고르지 않는다
        page.wait_for_timeout(200)
        end_p.click(button='right', position={'x': 8, 'y': 8})
        page.wait_for_selector('#lec-menu:not([hidden])')
        got = labels()
        check('칠하지 않은 글: 담기·문서로 보내기·새 메모로 보내기, 형광펜 항목은 없음',
              '고른 글 담기' in got and '고른 글을 문서로 보내기…' in got and '새 메모로 보내기' in got and '메모 달기' not in got and '이 형광펜 지우기' not in got, got)
        page.locator('#lec-menu button', has_text='새 메모로 보내기').click()
        check('고른 글의 새 메모는 그 글로 다시 찾는다 (find)', until(page, lambda: 'find=' in notes.read_text(encoding='utf-8').split('lectern-note')[-1], 8000), notes.read_text(encoding='utf-8')[-200:])
        page.keyboard.press('Alt+m')
        check('페이지 오류 없음', not errors, errors[:3])
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
