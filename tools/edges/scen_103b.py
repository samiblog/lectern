"""0.103.0 사람 시나리오 2 — 모아 보기와 사이드바 보내기를 오래 쓰는 동안 생기는 일 (D195·D196).

1. 종류를 빠르게 바꾼다 — 다이어그램을 그리는 동안 표·코드로 바꿔도 기다리지 않는다
2. 뒤에 둔 모아 보기 탭 — 문서를 읽는 동안 Claude 가 표를 더하고, 돌아오면 반영돼 있다
3. 편집 중인 문서 — 저장하지 않은 편집이 있는 문서의 출처 줄을 누르면 편집기가 그 줄로 (편집을 버리지 않는다)
4. 순서 — 최근 수정 순으로 바꾸면 방금 고친 문서가 맨 위
5. 걸러서 아무것도 없을 때, 특수 글자, 한글 조합 중
6. 아주 많은 것 — 표 900개인 문서는 처음 800개만, 거르면 다 찾는다
7. 담기 — 덩어리 하나·보이는 것 모두를 담고 담기 탭에서 확인
8. 키보드만으로 — Ctrl+F, 낱말, Enter, Enter, Alt+←, Tab 으로 출처 줄
9. 범위 폴더가 사라진다 — 폴더를 지우면 '없습니다', 전체로
10. 창을 좁혔다 넓힌다 — 격자와 표가 따라 바뀐다
11. 사이드바 보내기 — 트리를 거른 채, 터미널을 둘 띄운 채(최근에 쓴 터미널로), 터미널을 닫은 채
12. 읽기 전용 프로젝트(Lectern 프로그램 폴더 안의 예제) — 볼 수는 있고 넘기기는 막힌다"""
import json
import shutil
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import ROOT, check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-scen103b-'))
proj = base / '리서치'
for d in (proj / '조사', proj / '보고', proj / '임시'):
    d.mkdir(parents=True)


def put(rel, text, newline='\n'):
    (proj / rel).write_text(text, encoding='utf-8', newline=newline)


def table(cap, rows):
    return '\n'.join([cap, '', '| 항목 | 값 |', '|---|---|'] + [f'| {a} | {b} |' for a, b in rows] + ['', '자료: 시험', ''])


DIAGRAMS = '# 그림 모음\n\n' + '\n'.join(f'그림 {i}. 흐름 {i}\n\n```mermaid\nflowchart LR\n  가{i} --> 나{i} --> 다{i}\n```\n' for i in range(1, 7))
put('조사/그림-모음.md', DIAGRAMS)
A = '# 가 문서\n\n## 첫 절\n\n' + table('표 1. 가의 표', [('구리', '1'), ('니켈', '2')]) + '\n```python\nprint("가")\n```\n\n## 둘째 절\n\n' + table('표 2. 가의 둘째 표', [('C++ (a.*b)', '3'), ('50%', '4')])
put('조사/가.md', A)
put('조사/나.md', '# 나 문서\n\n' + table('표 1. 나의 표', [('구리', '10')]) + '\n넓은 표.\n\n| ' + ' | '.join(f'열{i}' for i in range(1, 15)) + ' |\n|' + '---|' * 14 + '\n| ' + ' | '.join('아주 긴 칸 글자입니다' for _ in range(14)) + ' |\n')
put('보고/보고.md', '# 보고\n\n' + table('표 1. 보고의 표', [('구리', '100')]))
put('임시/임시.md', '# 임시\n\n' + table('표 1. 임시 표', [('임시', '0')]))
MANY = '# 많은 표\n\n' + '\n'.join(f'| 번호 {i} |\n|---|\n| 값{i} |\n\n글 {i}\n' for i in range(1, 901))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)

EMIT = "(d) => import('/static/js/store.js').then((m) => m.emit('parts', d))"
OPEN = "(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: p }))"
VIEW = "() => import('/static/js/store.js').then((m) => (m.S.view ? m.S.view.type + ':' + (m.S.view.path || '') : ''))"
TABS = "() => [...document.querySelectorAll('#lec-doctab-list .doc-tab')].map((e) => e.querySelector('.name').textContent + (e.classList.contains('active') ? '*' : ''))"
CHUNKS = """() => [...document.querySelectorAll('#lec-view .parts-list .pv-chunk')].map((e) => ({ doc: e.dataset.doc, n: +e.dataset.n, real: !!e.querySelector('.pv-body.md-body'),
  cap: e.querySelector('.pv-body .lec-caption')?.textContent.trim() || '', text: e.querySelector('.pv-body.md-body')?.innerText || '' }))"""
INFO = "() => document.querySelector('#lec-view .parts-info')?.textContent || ''"
READ = "() => { const t = document.querySelector('#lec-view .parts-info')?.textContent || ''; return !!t && !t.includes('읽는 중'); }"
KINDS = "() => Object.fromEntries([...document.querySelectorAll('#lec-view .parts-kinds button[data-kind]')].map((b) => [b.dataset.kind, +b.querySelector('.n').textContent]))"
SEEN = """(word) => { const t = [...document.querySelectorAll('#lec-view .table-wrap')].find((w) => w.textContent.includes(word));
  const r = t?.getBoundingClientRect(); const c = document.querySelector('#lec-content').getBoundingClientRect(); return !!r && r.bottom > c.top + 20 && r.top < c.bottom - 20; }"""
SENT = "() => window.__sent || []"
TOAST = "() => { const e = document.querySelector('#lec-toast'); return e && !e.hidden ? e.textContent : ''; }"
HEADS = "() => [...document.querySelectorAll('#lec-view .parts-list .pt-doc .label')].map((e) => e.textContent)"
FOCUS = """() => { const a = document.activeElement; if (a?.closest('#lec-term')) return 'term'; if (a?.closest('#lec-tree')) return 'tree:' + (a.dataset.doc ?? a.dataset.dir ?? '');
  if (a?.classList.contains('parts-filter')) return 'filter'; if (a?.classList.contains('pv-chunk')) return 'chunk:' + a.dataset.doc + '#' + a.dataset.n;
  if (a?.classList.contains('pv-go')) return 'go'; return a?.closest('#lec-panes') ? 'doc' : (a?.tagName || ''); }"""
TERMTEXT = """(n) => import('/static/js/store.js').then((m) => { const term = (m.S.tab.terms || []).find((x) => x.n === n); if (!term?.xterm) return '';
  const b = term.xterm.buffer.active; const out = []; for (let i = 0; i < b.length; i++) out.push(b.getLine(i).translateToString(true)); return out.join('').replace(/\\s+/g, ''); })"""

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 1440, 'height': 900}, permissions=['clipboard-read', 'clipboard-write'])
        page = ctx.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.on('dialog', lambda d: d.accept())
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        page.evaluate("""() => import('/static/js/store.js').then((m) => { window.__sent = [];
          const note = (ev) => (d) => window.__sent.push({ ev, text: typeof d === 'string' ? d : d.text });
          m.on('term-paste', note('paste')); m.on('term-paste-stay', note('stay')); })""")

        def view():
            return page.evaluate(VIEW)

        def chunks():
            return page.evaluate(CHUNKS)

        def tabs():
            return page.evaluate(TABS)

        def kind(k):
            page.click(f'#lec-view .parts-kinds button[data-kind="{k}"]')

        def gather_tab():
            page.locator('#lec-doctab-list .doc-tab', has_text='모아 보기').click()
            page.wait_for_selector('#lec-view.parts-view .parts-list')

        def filt(text):
            page.fill('#lec-view .parts-filter', text)

        def sent():
            return [s['text'] for s in page.evaluate(SENT)]

        print('[1. 종류를 빠르게 바꾼다]')
        page.evaluate(OPEN, '보고/보고.md')
        page.wait_for_selector('#lec-view h1:has-text("보고")', timeout=20000)
        page.evaluate(EMIT, {'path': '', 'kind': 'diagram'})
        page.wait_for_selector('#lec-view.parts-view .pv-chunk', timeout=15000)
        t0 = time.monotonic()
        kind('table')   # 다이어그램 라이브러리를 불러오는 중에
        expect(page, '다이어그램을 그리는 동안 표로 바꿔도 표가 곧 그려진다', lambda: len(chunks()) == 6 and all(c['real'] for c in chunks()[:4]), chunks, ms=6000)
        quick = time.monotonic() - t0
        kind('code')
        expect(page, '코드로 바꿔도 곧', lambda: len(chunks()) == 1 and chunks()[0]['real'], chunks, ms=6000)
        kind('diagram')
        expect(page, '다이어그램으로 돌아오면 여섯 개가 모두 그려진다', "() => document.querySelectorAll('#lec-view .pv-chunk .pv-body pre.mermaid svg').length === 6", ms=60000)
        check('표로 바꾼 것이 기다리지 않았다 (6초 안)', quick < 6, round(quick, 1))
        for k in ('table', 'figure', 'box', 'math', 'task', 'link', 'source', 'chart', 'textbox', 'table'):   # 사람이 이것저것 눌러 본다
            kind(k)
            page.wait_for_timeout(60)
        expect(page, '아홉 종류를 잇따라 눌러도 마지막 것(표)이 맞게', lambda: len(chunks()) == 6 and all(c['real'] for c in chunks()[:4]) and page.evaluate(INFO) == '문서 4개, 표 6개', lambda: page.evaluate(INFO), ms=8000)

        print('[2. 뒤에 둔 모아 보기 탭]')
        page.locator('#lec-doctab-list .doc-tab', has_text='보고.md').click()
        page.wait_for_selector('#lec-view h1:has-text("보고")')
        put('보고/보고.md', '# 보고\n\n' + table('표 1. 보고의 표', [('구리', '100')]) + '\n' + table('표 2. Claude 가 더한 표', [('아연', '7')]))
        expect(page, '보던 문서가 먼저 바뀐다', lambda: page.locator('#lec-view table').count() == 2, ms=15000)
        gather_tab()
        expect(page, '모아 보기 탭으로 돌아오면 더한 표가 있다', lambda: page.evaluate(KINDS).get('table') == 7 and any(c['cap'] == '표 2. Claude 가 더한 표' for c in chunks()), lambda: (page.evaluate(KINDS), [c['cap'] for c in chunks()]), ms=15000)

        print('[3. 편집 중인 문서]')
        page.locator('#lec-tree .row.file[data-doc="조사/가.md"]').click()   # 트리에서 누르면 새 문서 탭 — 모아 보기 탭은 남는다
        page.wait_for_selector('#lec-view h1:has-text("가 문서")', timeout=15000)
        check('트리에서 연 문서는 새 탭에', tabs() == ['보고.md', '모아 보기', '가.md*'], tabs())
        page.locator('#lec-content').focus()
        page.keyboard.press('Control+e')
        page.wait_for_selector('.lec-pane.active .lec-editor .CodeMirror', timeout=20000)
        page.keyboard.type('저장하지 않은 글 ')
        gather_tab()
        page.click('#lec-view .pv-chunk[data-doc="조사/가.md"][data-n="2"] .pv-go')
        expect(page, '편집 중인 문서의 출처 줄 — 그 탭으로 가고 편집기가 그 표의 줄로', lambda: page.locator('.lec-pane.active .lec-editor .CodeMirror').count() == 1
               and page.evaluate("() => import('/static/js/store.js').then((m) => m.S.pane.editor?.cm.getCursor().line ?? -1)") >= 14, lambda: (tabs(), page.evaluate("() => import('/static/js/store.js').then((m) => m.S.pane.editor?.cm.getCursor().line ?? -1)")))
        check('— 저장하지 않은 글은 그대로 (버리지 않는다)', '저장하지 않은 글' in page.evaluate("() => import('/static/js/store.js').then((m) => m.S.pane.editor.cm.getValue())"))
        page.evaluate("() => import('/static/js/store.js').then((m) => import('/static/js/editor.js').then((e) => e.closeEditor(m.S.pane, { ask: false, sync: false })))")
        page.keyboard.press('Control+w')
        gather_tab()

        print('[4. 순서]')
        check('처음은 트리 순서', page.evaluate(HEADS) == ['보고.md', '임시.md', '가.md', '나.md'] or page.evaluate(HEADS)[-2:] == ['가.md', '나.md'], page.evaluate(HEADS))
        time.sleep(1.1)
        put('조사/나.md', (proj / '조사' / '나.md').read_text(encoding='utf-8') + '\n고침.\n')
        page.wait_for_timeout(1500)
        page.click('#lec-view .parts-order')
        expect(page, '최근 수정 순 — 방금 고친 문서가 맨 위', lambda: page.evaluate(HEADS)[0] == '나.md' and page.inner_text('#lec-view .parts-order') == '최근 수정 순', lambda: page.evaluate(HEADS), ms=10000)
        page.click('#lec-view .parts-order')
        expect(page, '다시 누르면 트리 순서', lambda: page.inner_text('#lec-view .parts-order') == '트리 순서' and page.evaluate(HEADS)[0] != '나.md', lambda: page.evaluate(HEADS))

        print('[5. 아무것도 없을 때·특수 글자·한글 조합]')
        filt('없는낱말xyz')
        expect(page, '맞는 것이 없으면 빈 목록과 개수', lambda: len(chunks()) == 0 and page.evaluate(INFO) == '거른 결과 0개 (모두 7개)', lambda: page.evaluate(INFO))
        check('— 넘기는 단추는 꺼진다', page.is_disabled('#lec-view .parts-send[data-act="ai"]') and page.is_disabled('#lec-view .parts-send[data-act="doc"]'))
        filt('C++ (a.*b)')
        expect(page, '정규식 글자가 든 낱말도 글자 그대로', lambda: [(c['doc'], c['n']) for c in chunks()] == [('조사/가.md', 2)], chunks)
        expect(page, '— 그 글자를 표시한다', lambda: sorted(page.evaluate("() => [...document.querySelectorAll('#lec-view mark.pv-hit')].map((m) => m.textContent)")) == ['(a.*b)', 'C++'],
               lambda: page.evaluate("() => [...document.querySelectorAll('#lec-view mark.pv-hit')].map((m) => m.textContent)"))
        filt('50%')
        expect(page, '% 도', lambda: len(chunks()) == 1, chunks)
        filt('<b>')
        expect(page, '태그처럼 생긴 글은 글자로만 (아무것도 없음, 오류 없음)', lambda: len(chunks()) == 0 and not errors, lambda: errors)
        filt('')
        page.focus('#lec-view .parts-filter')
        page.keyboard.insert_text('구')
        page.keyboard.insert_text('리')
        expect(page, '한 글자씩 들어오는 한글도 — 구리', lambda: page.input_value('#lec-view .parts-filter') == '구리' and len(chunks()) == 3, chunks)
        filt('')

        print('[6. 아주 많은 것]')
        put('조사/많은-표.md', MANY)
        expect(page, '표 907개', lambda: page.evaluate(KINDS).get('table') == 907, lambda: page.evaluate(KINDS), ms=40000)
        expect(page, '처음 800개만 보이고 좁히라고 알린다', lambda: '처음 800개만' in page.evaluate(INFO), lambda: page.evaluate(INFO), ms=15000)
        t0 = time.monotonic()
        filt('번호 899')
        expect(page, '거르면 800번 뒤의 것도 찾는다', lambda: len(chunks()) == 1 and '거른 결과 1개' in page.evaluate(INFO), lambda: page.evaluate(INFO), ms=15000)
        check('— 거르는 데 오래 걸리지 않는다 (5초 안)', time.monotonic() - t0 < 5, round(time.monotonic() - t0, 1))
        expect(page, '— 그 표가 실제로 그려진다', lambda: chunks()[0]['real'] and '값899' in chunks()[0]['text'], chunks, ms=15000)
        filt('')
        (proj / '조사' / '많은-표.md').unlink()
        expect(page, '지우면 일곱 개로', lambda: page.evaluate(KINDS).get('table') == 7 and len(chunks()) == 7, lambda: page.evaluate(KINDS), ms=20000)

        print('[7. 담기]')
        page.locator('#lec-view .pv-chunk[data-doc="조사/가.md"][data-n="1"] .pv-src').click(button='right')
        page.locator('#lec-menu button', has_text='담기').first.click()
        expect(page, '덩어리 하나를 담는다', lambda: page.inner_text('#lec-basket-count') == '1', lambda: page.inner_text('#lec-basket-count'))
        filt('구리')
        expect(page, '구리 셋', lambda: len(chunks()) == 3, chunks)
        page.locator('#lec-view .pv-chunk .pv-src').first.click(button='right')
        page.locator('#lec-menu button', has_text='보이는 것 모두 담기 (3개)').click()
        expect(page, '보이는 것 모두 담기 — 거른 셋', lambda: page.inner_text('#lec-basket-count') == '4', lambda: page.inner_text('#lec-basket-count'))
        page.click('.side-tabs button[data-tab="basket"]')
        page.locator('#lec-basket-list .bk-box .caret').first.click()
        expect(page, '담기 탭에 캡션이 이름으로', lambda: page.locator('#lec-basket-list .bk-item').count() == 4 and '가의 표' in page.inner_text('#lec-basket-list'), lambda: page.inner_text('#lec-basket-list')[:200])
        page.click('.side-tabs button[data-tab="files"]')
        filt('')

        print('[8. 키보드만으로]')
        page.locator('#lec-content').focus()
        page.keyboard.press('Control+f')
        page.keyboard.type('니켈')
        expect(page, 'Ctrl+F, 낱말', lambda: page.evaluate(FOCUS) == 'filter' and len(chunks()) == 1, chunks)
        page.keyboard.press('Enter')
        expect(page, 'Enter — 첫 덩어리에 초점 (문서 머리줄이 아니다)', lambda: page.evaluate(FOCUS) == 'chunk:조사/가.md#1', lambda: page.evaluate(FOCUS))
        page.keyboard.press('Tab')
        expect(page, 'Tab — 출처 줄 단추', lambda: page.evaluate(FOCUS) == 'go', lambda: page.evaluate(FOCUS))
        page.keyboard.press('Enter')
        page.wait_for_selector('#lec-view h1:has-text("가 문서")', timeout=15000)
        expect(page, 'Enter — 그 문서의 그 표로', lambda: page.evaluate(SEEN, '니켈'))
        page.keyboard.press('Alt+ArrowLeft')
        page.wait_for_selector('#lec-view.parts-view .pv-chunk', timeout=15000)
        page.keyboard.press('Control+f')
        page.keyboard.press('Escape')
        expect(page, 'Alt+←, Ctrl+F, Esc — 거르기를 지운다', lambda: page.input_value('#lec-view .parts-filter') == '' and len(chunks()) == 7, chunks)

        print('[9. 범위 폴더가 사라진다]')
        page.evaluate(EMIT, {'path': '임시', 'kind': 'table'})
        expect(page, '임시 폴더만', lambda: view() == 'parts:임시' and [c['doc'] for c in chunks()] == ['임시/임시.md'], chunks, ms=10000)
        shutil.rmtree(proj / '임시')
        expect(page, '폴더를 지우면 이 범위에 없다고 알린다 (오류 없이)', lambda: len(chunks()) == 0 and '없습니다' in page.evaluate(INFO) and not errors, lambda: (page.evaluate(INFO), errors), ms=20000)
        page.click('#lec-view .parts-all')
        expect(page, "'전체' 로 — 여섯 개", lambda: view() == 'parts:' and len(chunks()) == 6, chunks, ms=10000)

        print('[10. 창을 좁혔다 넓힌다]')
        kind('diagram')
        page.wait_for_selector('#lec-view .pv-chunks.pv-grid .pv-chunk')
        cols = lambda: page.evaluate("() => getComputedStyle(document.querySelector('#lec-view .pv-chunks.pv-grid')).gridTemplateColumns.split(' ').length")  # noqa: E731
        wide = cols()
        page.set_viewport_size({'width': 900, 'height': 800})
        page.wait_for_timeout(500)
        narrow = cols()
        check('좁히면 격자의 칸이 준다', narrow < wide and narrow >= 1, (wide, narrow))
        kind('table')
        over = page.evaluate("""() => { const v = document.querySelector('#lec-content'); const edge = v.getBoundingClientRect().right;
          return [...v.querySelectorAll('.pv-chunk, .pv-src, .parts-bar, .parts-head')].filter((e) => e.getBoundingClientRect().right > edge + 1).length; }""")
        check('열넷짜리 넓은 표가 있어도 덩어리가 칸 밖으로 넘치지 않는다 (표는 제 상자에서 민다)', over == 0, over)
        page.set_viewport_size({'width': 1440, 'height': 900})
        page.wait_for_timeout(400)
        kind('diagram')
        expect(page, '넓히면 돌아온다', lambda: cols() == wide, cols)
        kind('table')

        print('[11. 사이드바 보내기 — 거른 트리, 터미널 둘, 터미널을 닫은 채]')
        page.fill('#lec-filter', '가')
        page.wait_for_selector('#lec-tree .row.file[data-doc="조사/가.md"]')
        page.locator('#lec-tree .row.file[data-doc="조사/가.md"]').focus()
        page.keyboard.press('Shift+ArrowRight')
        expect(page, '거른 트리의 행에서도 — 1번 터미널을 열어 넣는다', lambda: sent()[-1] == '@조사/가.md ' and '1번 터미널에 넣었습니다' in page.evaluate(TOAST), lambda: (sent()[-1:], page.evaluate(TOAST)), ms=40000)
        page.fill('#lec-filter', '')
        page.click('#lec-term-new')
        expect(page, '2번 터미널을 연다', lambda: 'PS' in page.evaluate(TERMTEXT, 1), ms=40000)
        page.locator('#lec-tree .row.file[data-doc="보고/보고.md"]').focus()
        page.keyboard.press('Control+Shift+ArrowRight')
        expect(page, '최근에 쓴 2번 터미널로 간다 (1번이 아니다)', lambda: '@보고/보고.md' in page.evaluate(TERMTEXT, 1) and '@보고/보고.md' not in page.evaluate(TERMTEXT, 0), lambda: page.evaluate(TOAST), ms=15000)
        expect(page, '— 초점은 그 행에', lambda: page.evaluate(FOCUS) == 'tree:보고/보고.md', lambda: page.evaluate(FOCUS), ms=8000)
        page.keyboard.press('Shift+Digit1')
        expect(page, 'Shift+1 은 1번으로', lambda: '@보고/보고.md' in page.evaluate(TERMTEXT, 0), lambda: page.evaluate(TOAST), ms=15000)
        check('Enter 는 한 번도 누르지 않았다 (프롬프트가 터미널마다 하나)', page.evaluate("""() => import('/static/js/store.js').then((m) => m.S.tab.terms.map((term) => { const b = term.xterm.buffer.active; let n = 0;
          for (let i = 0; i < b.length; i++) if (/^PS .*>/.test(b.getLine(i).translateToString(true))) n += 1; return n; }))""") == [1, 1])
        page.click('#lec-btn-term')   # 패널을 닫는다
        page.locator('#lec-tree .row.file[data-doc="조사/나.md"]').focus()
        page.keyboard.press('Shift+ArrowRight')
        expect(page, '터미널을 닫아 두었어도 다시 열어 넣는다', lambda: sent()[-1] == '@조사/나.md ' and '@조사/나.md' in (page.evaluate(TERMTEXT, 0) + page.evaluate(TERMTEXT, 1)), lambda: page.evaluate(TOAST), ms=15000)
        page.click('#lec-btn-term')

        print('[12. 읽기 전용 프로젝트 — 프로그램 폴더 안의 예제]')
        page.evaluate("(dir) => import('/static/js/tabs.js').then((m) => m.openFolder(dir))", str(ROOT / 'samples'))
        until(page, lambda: page.evaluate("() => import('/static/js/store.js').then((m) => m.S.tab?.name)") == 'samples', 20000)
        ro = page.evaluate("() => import('/static/js/store.js').then((m) => !!m.S.tab?.readonly)")
        page.evaluate(EMIT, {'path': 'guide', 'kind': 'table'})
        page.wait_for_selector('#lec-view.parts-view .pv-chunk', timeout=30000)
        until(page, READ, 40000)
        expect(page, '예제의 표를 실제로 펼친다', lambda: len(chunks()) > 3 and chunks()[0]['real'], lambda: page.evaluate(INFO), ms=20000)
        if ro:
            n0 = len(sent())
            page.click('#lec-view .parts-send[data-act="ai"]')
            page.wait_for_timeout(700)
            check('읽기 전용이면 터미널을 열지 않고 까닭을 알린다 (D71)', not page.evaluate("() => document.documentElement.classList.contains('term-on')") and bool(page.evaluate(TOAST)), page.evaluate(TOAST))
            page.click('#lec-view .parts-send[data-act="doc"]')
            page.wait_for_timeout(500)
            check('— 새 문서도 만들지 않는다', page.evaluate("() => document.querySelector('#lec-insert').hidden"), page.evaluate(TOAST))
            check('— 까닭을 알린다', bool(page.evaluate(TOAST)), page.evaluate(TOAST))
            del n0
        else:
            check('(이 실행에서는 예제 폴더가 읽기 전용이 아니다 — 넘기기 막힘은 보지 않는다)', True)

        check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
