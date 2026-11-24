"""0.103.0 사람 시나리오 — 연구원이 Claude 가 쓴 조사 문서 열두 개를 두고 하루 일하는 차례 (D195 사이드바의 Shift+→, D196 모아 보기 화면).

1. 아침: 모아 보기로 표를 훑는다 — 표 마흔두 개를 끝까지 스크롤, 목차 패널로 먼 곳에 뛰기
2. 숫자를 견준다 — '2분기'로 걸러 두 문서의 값이 다른 것을 찾고, 출처 줄로 가서 그 칸을 고치고 돌아온다
3. Claude 가 일하는 동안 — 읽는 중에 밖에서 문서 여럿이 잇따라 바뀐다 (스크롤·거르기·초점이 그대로)
4. 사이드바에서 파일 여럿을 AI 도구에 가리킨다 — Ctrl+Shift+→ 와 ↓ 를 섞어, 마지막은 Shift+→
5. 문서와 나란히 — 모두 펼치기에서 모아 보기와 문서를 함께
6. 거른 것을 새 문서로 — 그 문서가 생기고 모아 보기에 그 표가 더 잡힌다
7. 탭을 오간다 — 문서 탭·프로젝트 탭을 여러 번 바꿔도 거르기·읽던 자리가 그대로, 프로젝트마다 제 모아 보기
8. 이름 바꾸기·지우기 — 모아 보기를 연 채 문서의 이름이 바뀌고 지워진다
9. 그림 — 누르면 크게, 슬라이드 문서의 그림도
10. 할 일 — 한 줄 행에서 그 문서로 가서 체크하고 돌아오면 '한 것'으로
11. 스타일·글자 크기를 바꾼다 — 펼친 것이 따라 바뀐다
12. 사이드바·검색에서 문서를 열어도 모아 보기 탭은 남는다, 뒤로 두 번
13. 많이 넘기기 — 100개가 넘으면 좁히라고 알린다, 좁히면 넘어간다
14. 닫고 다시 — 마지막에 고른 종류로"""
import json
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-scen103-'))
proj = base / '구리 리서치'
other = base / '니켈'
for d in (proj / '1-계획', proj / '2-조사' / '원자료', proj / '3-보고', other):
    d.mkdir(parents=True)
(proj / '2-조사' / '그림.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="320" height="200" viewBox="0 0 320 200"><rect width="320" height="200" fill="#2b5c8a"/><circle cx="160" cy="100" r="60" fill="#fff"/></svg>', encoding='utf-8')


def put(rel, text, root=proj, newline='\n'):
    (root / rel).write_text(text, encoding='utf-8', newline=newline)


def table(cap, head, rows, src='LME'):
    lines = [cap, '', '| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)] + ['| ' + ' | '.join(r) + ' |' for r in rows] + ['', f'자료: {src}', '']
    return '\n'.join(lines)


PRICE = '# 가격 동향\n\n## 분기별 가격\n\n' + table('표 1. 구리 분기별 가격', ['분기', '가격', '전기비'], [['1분기', '9,210', '+3.1%'], ['2분기', '9,480', '+2.9%']]) \
    + '\n본문입니다.\n\n## 할 일\n\n- [ ] 재고 통계 확인\n- [ ] 3분기 전망 쓰기\n- [x] 가격 표 넣기\n\n## 그림\n\n그림 1. 가격 추이\n\n![가격 추이](그림.svg)\n'
put('2-조사/가격-동향.md', PRICE)
put('2-조사/수급-전망.md', '# 수급 전망\n\n## 요약\n\n' + table('표 1. 수급 요약', ['분기', '구리 가격', '재고'], [['1분기', '9,210', '120'], ['2분기', '9,840', '98']], '자체 집계')
    + '\n## 공급\n\n' + table('표 2. 광산별 생산량', ['광산', '나라', '생산량'], [['에스콘디다', '칠레', '1,050'], ['그라스버그', '인도네시아', '780']], '각 사 보고서')
    + '\n그림 1. 공급 흐름\n\n```mermaid\nflowchart LR\n  광산 --> 제련 --> 가공\n```\n\n![가격 추이](그림.svg)\n')
# 표가 서른 개인 긴 문서 — 끝까지 스크롤해야 다 그려진다
BIG = '# 원자료 모음\n\n' + '\n'.join(f'## {i}월 자료\n\n' + table(f'표 {i}. {i}월 지역별 수요', ['지역', '수요', '비고'], [['아시아', str(100 + i), f'{i}월'], ['유럽', str(50 + i), '추정'], ['미주', str(70 + i), '']], f'{i}월 통계')
                                  for i in range(1, 31))
put('2-조사/원자료/월별.md', BIG)
put('2-조사/원자료/메모.md', '# 메모\n\n캡션 없는 표.\n\n| 가 | 나 |\n|---|---|\n| 1 | 2 |\n\n> [!NOTE]\n> 2분기 값은 다시 확인.\n', newline='\r\n')
put('1-계획/계획.md', '---\nstatus: 진행\n---\n\n# 계획\n\n' + table('표 1. 일정', ['단계', '기한'], [['조사', '11월'], ['보고', '12월']], '내부') + '\n- [ ] 조사 끝내기\n')
put('3-보고/보고서.md', '---\nstatus: 초안\n---\n\n# 보고서\n\n## 결론\n\n' + table('표 1. 결론 요약', ['항목', '판단'], [['구리', '상승'], ['재고', '감소']], '2-조사') + '\n[가격 동향](../2-조사/가격-동향.md) 을 봅니다.\n')
put('3-보고/발표.md', '---\nmarp: true\n---\n\n# 발표\n\n---\n\n## 가격\n\n' + table('표 1. 발표용 가격', ['분기', '가격'], [['2분기', '9,480']]) + '\n---\n\n## 그림\n\n![가격 추이](../2-조사/그림.svg)\n')
put('3-보고/옛-자료.html', '<html><body><h1>옛 자료</h1><table><caption>표 1. 옛 가격</caption><tr><th>분기</th><th>가격</th></tr><tr><td>2분기</td><td>8,900</td></tr></table></body></html>')
for i in range(1, 5):
    put(f'2-조사/조사-{i}.md', f'# 조사 {i}\n\n' + table(f'표 1. 조사 {i} 요약', ['항목', '값'], [['구리', str(i)]], f'조사 {i}'))
put('개요.md', '# 니켈 개요\n\n' + table('표 1. 니켈 가격', ['분기', '가격'], [['2분기', '16,800']]), root=other)
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
TOP = "() => Math.round(document.querySelector('#lec-content').scrollTop)"
FILLED = "() => [document.querySelectorAll('#lec-view .pv-chunk .pv-body.md-body').length, document.querySelectorAll('#lec-view .pv-chunk').length]"
ROWS = "() => [...document.querySelectorAll('#lec-view .parts-list .pt-item')].map((e) => [e.dataset.doc, e.querySelector('.pt-name').textContent])"
FOCUS = """() => { const a = document.activeElement; if (a?.closest('#lec-term')) return 'term'; if (a?.closest('#lec-tree')) return 'tree:' + (a.dataset.doc ?? a.dataset.dir ?? '');
  if (a?.classList.contains('parts-filter')) return 'filter'; return a?.closest('#lec-panes') ? 'doc' : (a?.tagName || ''); }"""

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
            until(page, f"() => document.querySelector('#lec-view .parts-kinds button.active')?.dataset.kind === '{k}'")

        def gather_tab():
            page.locator('#lec-doctab-list .doc-tab', has_text='모아 보기').click()
            page.wait_for_selector('#lec-view.parts-view .parts-list')

        def filt(text):
            page.fill('#lec-view .parts-filter', text)

        def scroll_to(y):
            page.evaluate("(y) => { document.querySelector('#lec-content').scrollTop = y; }", y)

        print('[1. 아침 — 표를 끝까지 훑는다]')
        page.evaluate(OPEN, '3-보고/보고서.md')
        page.wait_for_selector('#lec-view h1:has-text("보고서")', timeout=20000)
        page.evaluate(EMIT, {'path': '', 'kind': 'table'})
        page.wait_for_selector('#lec-view.parts-view .pv-chunk', timeout=15000)
        until(page, READ, 30000)
        total = page.evaluate(KINDS).get('table')
        check('표 마흔두 개가 잡힌다 (긴 문서의 서른 개까지)', total == 42 and page.evaluate(INFO) == '문서 12개, 표 42개', (total, page.evaluate(INFO)))
        first = page.evaluate(FILLED)
        check('처음에는 화면 가까이의 것만 그린다', 0 < first[0] < first[1] == 42, first)
        # 사람처럼 한 화면씩 내려간다
        for _ in range(60):
            page.mouse.move(700, 500)
            page.mouse.wheel(0, 700)
            page.wait_for_timeout(120)
            if page.evaluate("() => { const c = document.querySelector('#lec-content'); return c.scrollTop + c.clientHeight >= c.scrollHeight - 4; }"):
                break
        expect(page, '끝까지 내려가면 마흔두 개가 다 실제 표로 — 멈춘 것이 없다', lambda: page.evaluate(FILLED) == [42, 42], lambda: page.evaluate(FILLED), ms=20000)
        check("끝의 html 문서 표도", any(c['doc'] == '3-보고/옛-자료.html' and '8,900' in c['text'] for c in chunks()))
        check('슬라이드 문서의 표도 보통 표로', any(c['doc'] == '3-보고/발표.md' and c['cap'] == '표 1. 발표용 가격' for c in chunks()))
        check('캡션 없는 CRLF 문서의 표도', any(c['doc'] == '2-조사/원자료/메모.md' and c['real'] and c['cap'] == '' for c in chunks()))
        scroll_to(0)
        page.locator('#lec-toc a[data-i]', has_text='표 17. 17월 지역별 수요').click()
        expect(page, '목차 패널로 먼 표에 뛴다 — 그 표가 화면에', """() => { const e = [...document.querySelectorAll('#lec-view .pv-chunk')].find((x) => x.textContent.includes('17월 지역별 수요'));
          const r = e?.getBoundingClientRect(); return !!r && r.top >= 0 && r.top < innerHeight - 100; }""")
        check('목차에서 지금 보는 곳이 표시된다', page.locator('#lec-toc a.active').count() >= 1)

        print('[2. 숫자를 견준다 — 걸러서 찾고, 고치고, 돌아온다]')
        filt('2분기')
        expect(page, "'2분기' 로 거르면 그 말이 든 표만", lambda: sorted(c['doc'] for c in chunks()) == ['2-조사/가격-동향.md', '2-조사/수급-전망.md', '3-보고/발표.md', '3-보고/옛-자료.html'], chunks)
        until(page, lambda: all(c['real'] for c in chunks()), 10000)
        texts = {c['doc']: c['text'] for c in chunks()}
        check('두 문서의 2분기 값이 다른 것이 한 화면에 보인다 (9,480 과 9,840)', '9,480' in texts['2-조사/가격-동향.md'] and '9,840' in texts['2-조사/수급-전망.md'], texts)
        y0 = page.evaluate(TOP)
        page.click('#lec-view .pv-chunk[data-doc="2-조사/수급-전망.md"] .pv-go')
        page.wait_for_selector('#lec-view h1:has-text("수급 전망")', timeout=15000)
        expect(page, '출처 줄로 그 표에', lambda: page.evaluate(SEEN, '9,840'))
        cell = page.locator('#lec-view td', has_text='9,840')
        cell.click()
        page.keyboard.press('F2')   # 그 행의 칸들이 열린다 — 누른 칸에 초점
        page.wait_for_selector('#lec-view .lec-line-edit', timeout=8000)
        page.locator('#lec-view .lec-line-edit', has_text='9,840').click()   # 그 칸으로
        page.keyboard.press('End')
        for _ in range(5):
            page.keyboard.press('Backspace')
        page.keyboard.type('9,480')
        page.keyboard.press('Enter')   # 저장하고 다음 줄로 (D168)
        until(page, lambda: '9,480' in (proj / '2-조사' / '수급-전망.md').read_text(encoding='utf-8') and '9,840' not in (proj / '2-조사' / '수급-전망.md').read_text(encoding='utf-8'), 8000)
        check('그 문서에서 칸을 고쳐 저장한다 (모아 보기에서는 고치지 않는다)', '| 2분기 | 9,480 | 98 |' in (proj / '2-조사' / '수급-전망.md').read_text(encoding='utf-8'), (proj / '2-조사' / '수급-전망.md').read_text(encoding='utf-8')[:260])
        page.keyboard.press('Escape')
        page.keyboard.press('Alt+ArrowLeft')
        page.wait_for_selector('#lec-view.parts-view .pv-chunk', timeout=15000)
        expect(page, 'Alt+← 로 돌아오면 거르기가 그대로이고 고친 값이 보인다', lambda: page.input_value('#lec-view .parts-filter') == '2분기' and '9,480' in next((c['text'] for c in chunks() if c['doc'] == '2-조사/수급-전망.md'), ''), chunks, ms=15000)
        check('돌아온 자리가 맨 끝을 넘지 않는다 (거른 것이 넷뿐이라 짧다)', page.evaluate(TOP) <= y0 + 5, (y0, page.evaluate(TOP)))
        filt('')

        print('[3. Claude 가 일하는 동안 — 읽는 중에 문서가 잇따라 바뀐다]')
        expect(page, '다 보인다', lambda: len(chunks()) == 42, lambda: len(chunks()))
        filt('수요')
        expect(page, "'수요' 로 거른 서른 개", lambda: len(chunks()) == 30, lambda: len(chunks()))
        scroll_to(2600)
        page.wait_for_timeout(600)
        page.focus('#lec-view .parts-filter')
        y1 = page.evaluate(TOP)
        for n in range(1, 6):   # 0.3초마다 다른 문서를 고친다 — 그 가운데 하나는 지금 거른 문서
            put(f'2-조사/조사-{(n % 4) + 1}.md', f'# 조사\n\n' + table(f'표 1. 조사 요약 (고침 {n})', ['항목', '값'], [['구리', str(n)], ['수요', str(n * 10)]], '고침'))
            if n == 3:
                put('2-조사/원자료/월별.md', BIG.replace('| 아시아 | 101 | 1월 |', '| 아시아 | 999 | 1월 |'))
            time.sleep(0.3)
        expect(page, '고친 것이 모두 반영된다 — 수요가 든 표가 서른넷', lambda: len(chunks()) == 34 and '거른 결과 34개' in page.evaluate(INFO), lambda: (len(chunks()), page.evaluate(INFO)), ms=20000)
        check('그동안 스크롤이 맨 위로 튀지 않는다', abs(page.evaluate(TOP) - y1) < 500, (y1, page.evaluate(TOP)))
        check('거르기 칸의 글과 초점도 그대로', page.input_value('#lec-view .parts-filter') == '수요' and page.evaluate(FOCUS) == 'filter', page.evaluate(FOCUS))
        scroll_to(0)
        expect(page, '긴 문서의 고친 칸(999)도 다시 그려진다', lambda: any('999' in c['text'] for c in chunks()), lambda: [c['text'][:40] for c in chunks()[:3]], ms=15000)
        filt('')

        print('[4. 사이드바에서 파일 여럿을 AI 도구에 가리킨다]')
        row = page.locator('#lec-tree .row.file[data-doc="2-조사/조사-1.md"]')
        if not row.count():
            page.locator('#lec-tree .row.dir[data-dir="2-조사"] [data-toggle]').click()
        page.wait_for_selector('#lec-tree .row.file[data-doc="2-조사/조사-1.md"]')
        row.focus()
        n0 = len(page.evaluate(SENT))
        for _ in range(3):
            page.keyboard.press('Control+Shift+ArrowRight')
            until(page, lambda: page.evaluate(FOCUS).startswith('tree:') and '터미널에 넣었습니다' in page.evaluate(TOAST), 40000)
            page.keyboard.press('ArrowDown')
            page.wait_for_timeout(150)
        page.keyboard.press('Shift+ArrowRight')
        got = [s['text'] for s in page.evaluate(SENT)[n0:]]
        expect(page, 'Ctrl+Shift+→ 와 ↓ 로 셋, Shift+→ 로 넷째 — 차례대로', lambda: [s['text'] for s in page.evaluate(SENT)[n0:]] == ['@2-조사/조사-1.md ', '@2-조사/조사-2.md ', '@2-조사/조사-3.md ', '@2-조사/조사-4.md '], lambda: got)
        expect(page, '마지막은 초점이 터미널로', lambda: page.evaluate(FOCUS) == 'term', lambda: page.evaluate(FOCUS), ms=15000)
        check('그동안 모아 보기 탭은 그대로 (문서를 열지 않는다)', view() == 'parts:' and tabs() == ['보고서.md', '모아 보기*'], (view(), tabs()))
        page.click('#lec-btn-term')   # 터미널을 닫아 둔다

        print('[5. 문서와 나란히 — 모두 펼치기]')
        page.click('#lec-doctab-spread')
        expect(page, '모아 보기와 문서가 함께 보인다', "() => document.documentElement.classList.contains('spread-on') && document.querySelectorAll('.lec-pane.sp-cell').length >= 2 && !!document.querySelector('.sp-cell .parts-view') && !!document.querySelector('.sp-cell .md-body h1')")
        check('칸 머리에 모아 보기', '모아 보기' in page.evaluate("() => [...document.querySelectorAll('.sp-head')].map((e) => e.textContent).join('|')"))
        expect(page, '펼친 칸에서도 표가 그려진다', lambda: page.evaluate("() => document.querySelectorAll('.sp-cell .parts-view .pv-chunk .pv-body.md-body table').length") > 0)
        page.click('#lec-doctab-spread')
        expect(page, '다시 누르면 원래대로', "() => !document.documentElement.classList.contains('spread-on')")
        gather_tab()

        print('[6. 거른 것을 새 문서로]')
        filt('구리 가격')
        expect(page, "'구리 가격' 낱말 둘 — 둘 다 든 표", lambda: 1 <= len(chunks()) <= 4 and all('구리' in c['text'] or '구리' in c['cap'] for c in chunks()), chunks)
        n_before = len(chunks())
        page.click('#lec-view .parts-send[data-act="doc"]')
        page.wait_for_selector('#lec-insert:not([hidden])')
        page.fill('#lec-insert-input', '3-보고/구리-가격-표.md')
        page.keyboard.press('Enter')
        made = proj / '3-보고' / '구리-가격-표.md'
        until(page, lambda: made.exists() and made.read_text(encoding='utf-8').count('자료:') >= n_before, 10000)
        text = made.read_text(encoding='utf-8') if made.exists() else ''
        check('새 문서에 거른 표가 캡션·자료 줄째 차례대로', sum(1 for s in text.split(chr(10)) if s.startswith('|---|')) == n_before and '구리' in text, text[:400])
        page.wait_for_selector('#lec-view h1', timeout=15000)
        check('새 문서는 새 탭에서 열리고 모아 보기 탭은 남는다', tabs()[:2] == ['보고서.md', '모아 보기'] and tabs()[-1].endswith('*'), tabs())
        page.evaluate("""async () => { const { S } = await import('/static/js/store.js'); const d = await import('/static/js/doctabs.js'); const e = await import('/static/js/editor.js');
          const pane = S.pane; if (pane?.editor) e.closeEditor(pane, { ask: false, sync: false }); d.closeDocTab(pane); }""")
        gather_tab()
        expect(page, '모아 보기에 새 문서의 표가 더 잡힌다 (같은 표가 두 곳)', lambda: len(chunks()) == n_before * 2, lambda: [c['doc'] for c in chunks()], ms=15000)
        made.unlink()
        expect(page, '지우면 돌아온다', lambda: len(chunks()) == n_before, lambda: [c['doc'] for c in chunks()], ms=15000)

        print('[7. 탭을 오간다]')
        filt('일정')
        expect(page, '거른 뒤 하나', lambda: len(chunks()) == 1, chunks)
        for _ in range(4):
            page.keyboard.press('Control+Tab')
            page.wait_for_timeout(120)
        expect(page, '문서 탭을 네 번 바꿔도 모아 보기로 돌아오면 거르기 그대로', lambda: view() == 'parts:' and page.input_value('#lec-view .parts-filter') == '일정' and len(chunks()) == 1, lambda: (view(), tabs()))
        page.evaluate("(dir) => import('/static/js/tabs.js').then((m) => (m.openProject || m.openFolder)(dir))", str(other))
        page.wait_for_selector('#lec-tablist .lec-tab:nth-child(2)', timeout=20000)
        until(page, lambda: page.evaluate("() => import('/static/js/store.js').then((m) => m.S.tab?.name)") == '니켈', 15000)
        page.evaluate(EMIT, {'path': '', 'kind': 'table'})
        page.wait_for_selector('#lec-view.parts-view .pv-chunk', timeout=15000)
        expect(page, '다른 프로젝트는 제 모아 보기 — 니켈의 표 하나', lambda: [c['doc'] for c in chunks()] == ['개요.md'] and page.input_value('#lec-view .parts-filter') == '', chunks)
        page.locator('#lec-tablist .lec-tab').first.click()
        expect(page, '구리 프로젝트로 돌아오면 그 탭의 거르기·표 그대로', lambda: view() == 'parts:' and page.input_value('#lec-view .parts-filter') == '일정' and [c['doc'] for c in chunks()] == ['1-계획/계획.md'], lambda: (view(), chunks()), ms=15000)
        filt('')

        print('[8. 이름 바꾸기·지우기]')
        expect(page, '다 보인다', lambda: len(chunks()) == 42, lambda: len(chunks()))
        heads = lambda: page.evaluate("() => [...document.querySelectorAll('#lec-view .parts-list .pt-doc .label')].map((e) => e.textContent)")  # noqa: E731
        (proj / '2-조사' / '조사-4.md').rename(proj / '2-조사' / '조사-끝.md')
        expect(page, '밖에서 이름이 바뀌면 문서 머리줄도', lambda: '조사-끝.md' in heads() and '조사-4.md' not in heads(), heads, ms=15000)
        (proj / '2-조사' / '조사-끝.md').unlink()
        expect(page, '지워지면 그 묶음이 사라진다', lambda: '조사-끝.md' not in heads() and len(chunks()) == 41, lambda: (heads()[-4:], len(chunks())), ms=15000)

        print('[9. 그림]')
        kind('figure')
        expect(page, '같은 그림을 세 문서가 쓴다 — 하나에 +2곳', lambda: page.locator('#lec-view .pv-grid .pv-chunk').count() == 1 and page.inner_text('#lec-view .pv-src .pt-more') == '+2곳', lambda: page.inner_text('#lec-view .parts-list')[:160])
        expect(page, '그림이 불러와진다', "() => { const i = document.querySelector('#lec-view .pv-chunk .pv-body img'); return !!i && i.complete && i.naturalWidth > 0; }", ms=10000)
        page.click('#lec-view .pv-chunk .pv-body img')
        expect(page, '누르면 크게', "() => !document.querySelector('#lec-lightbox').hidden")
        page.keyboard.press('Escape')
        expect(page, 'Esc 로 닫는다', "() => document.querySelector('#lec-lightbox').hidden")
        kind('diagram')
        expect(page, '다이어그램도 그려진다', "() => !!document.querySelector('#lec-view .pv-chunk .pv-body pre.mermaid svg')", ms=40000)
        kind('box')
        expect(page, 'CRLF 문서의 강조글', lambda: any('다시 확인' in c['text'] for c in chunks()), chunks)

        print('[10. 할 일 — 가서 체크하고 돌아온다]')
        kind('task')
        expect(page, '안 한 일 셋', lambda: page.evaluate(ROWS) == [['1-계획/계획.md', '조사 끝내기'], ['2-조사/가격-동향.md', '재고 통계 확인'], ['2-조사/가격-동향.md', '3분기 전망 쓰기']], lambda: page.evaluate(ROWS))
        page.locator('#lec-view .pt-item', has_text='재고 통계 확인').click()
        page.wait_for_selector('#lec-view h1:has-text("가격 동향")', timeout=15000)
        box = page.locator('#lec-view li', has_text='재고 통계 확인').locator('input[type=checkbox]')
        box.click()
        until(page, lambda: '- [x] 재고 통계 확인' in (proj / '2-조사' / '가격-동향.md').read_text(encoding='utf-8'), 8000)
        check('그 문서에서 체크하면 파일에 적힌다', '- [x] 재고 통계 확인' in (proj / '2-조사' / '가격-동향.md').read_text(encoding='utf-8'))
        page.keyboard.press('Alt+ArrowLeft')
        page.wait_for_selector('#lec-view.parts-view .parts-list', timeout=15000)
        expect(page, "돌아오면 그 일은 '안 한 것'에서 빠진다", lambda: page.evaluate(ROWS) == [['1-계획/계획.md', '조사 끝내기'], ['2-조사/가격-동향.md', '3분기 전망 쓰기']], lambda: page.evaluate(ROWS), ms=15000)
        check("— '한 것' 단추의 수가 는다", page.evaluate("() => document.querySelector('#lec-view .parts-sub button[data-sub=\"done\"]').textContent") == '한 것2', page.evaluate("() => document.querySelector('#lec-view .parts-sub').textContent"))

        print('[11. 스타일·글자 크기]')
        kind('table')
        until(page, "() => document.querySelectorAll('#lec-view .pv-done').length >= 2", 15000)
        size0 = page.evaluate("() => parseFloat(getComputedStyle(document.querySelector('#lec-view .pv-body.md-body table')).fontSize)")
        page.keyboard.press('Control+=')
        page.keyboard.press('Control+=')
        expect(page, '글자를 키우면 펼친 표도 커진다', lambda: page.evaluate("() => parseFloat(getComputedStyle(document.querySelector('#lec-view .pv-body.md-body table')).fontSize)") > size0, lambda: size0)
        page.keyboard.press('Control+0')
        themes = page.evaluate("() => [...document.querySelector('#lec-theme').options].map((o) => o.value)")
        bg0 = page.evaluate("() => getComputedStyle(document.querySelector('#lec-content')).backgroundColor")
        dark = next((v for v in themes if 'dark' in v or v in ('night', 'midnight')), themes[-1])
        page.select_option('#lec-theme', dark)
        expect(page, '스타일을 바꾸면 화면이 따라 바뀌고 표가 다시 그려진다', lambda: page.evaluate("() => document.querySelectorAll('#lec-view .pv-chunk .pv-body.md-body table').length") > 0
               and page.evaluate("() => document.documentElement.dataset.theme") == dark, lambda: (dark, bg0), ms=15000)
        check('붙어 있는 줄의 바탕이 화면 바탕과 같다 (비쳐 보이지 않는다)', page.evaluate("() => getComputedStyle(document.querySelector('#lec-view .parts-bar')).backgroundColor") not in ('rgba(0, 0, 0, 0)', 'transparent'))
        page.select_option('#lec-theme', themes[0])
        expect(page, '처음 스타일로 돌아온다', lambda: page.evaluate("() => document.documentElement.dataset.theme") != dark and page.evaluate("() => document.querySelectorAll('#lec-view .pv-chunk .pv-body.md-body table').length") > 0)

        print('[12. 사이드바·검색에서 문서를 열어도 모아 보기 탭은 남는다]')
        page.locator('#lec-tree .row.file[data-doc="2-조사/조사-2.md"]').click()
        page.wait_for_selector('#lec-view h1:has-text("조사")', timeout=15000)
        check('트리에서 문서를 누르면 새 문서 탭 — 모아 보기는 그대로', tabs() == ['보고서.md', '모아 보기', '조사-2.md*'], tabs())
        page.keyboard.press('Control+w')
        expect(page, '닫으면 왼쪽 탭', lambda: len(tabs()) == 2, tabs)
        gather_tab()
        page.click('#lec-view .pv-chunk[data-doc="3-보고/보고서.md"] .pv-go')
        expect(page, '다른 탭에 열려 있는 보고서로', lambda: tabs() == ['보고서.md*', '모아 보기'], tabs)
        gather_tab()
        scroll_to(3000)   # 긴 목록의 가운데 — 그 자리에서 보이는 표로 갔다가 돌아온다
        page.wait_for_timeout(900)
        y2 = page.evaluate(TOP)
        seen = page.evaluate("""() => { const e = [...document.querySelectorAll('#lec-view .pv-chunk')].find((x) => { const r = x.getBoundingClientRect(); return r.top > 120 && r.top < innerHeight - 200; });
          e.querySelector('.pv-go').click(); return e.dataset.doc + '#' + e.dataset.n; }""")
        page.wait_for_selector('#lec-view h1:has-text("원자료 모음")', timeout=15000)
        page.keyboard.press('Alt+ArrowLeft')
        page.wait_for_selector('#lec-view.parts-view .pv-chunk', timeout=15000)
        expect(page, '긴 목록의 가운데에서 갔다가 돌아오면 읽던 자리 그대로', lambda: abs(page.evaluate(TOP) - y2) <= 60, lambda: (seen, y2, page.evaluate(TOP)), ms=8000)
        page.wait_for_timeout(1200)   # 요소가 다시 그려진 뒤에도
        check('— 다시 그려진 뒤에도 그 자리', abs(page.evaluate(TOP) - y2) <= 60, (y2, page.evaluate(TOP)))
        scroll_to(0)
        page.click('#lec-view .pv-chunk[data-doc="1-계획/계획.md"] .pv-go')
        page.wait_for_selector('#lec-view h1:has-text("계획")', timeout=15000)
        page.evaluate(OPEN, '2-조사/수급-전망.md')
        page.wait_for_selector('#lec-view h1:has-text("수급 전망")', timeout=15000)
        page.keyboard.press('Alt+ArrowLeft')
        page.wait_for_selector('#lec-view h1:has-text("계획")', timeout=15000)
        page.keyboard.press('Alt+ArrowLeft')
        expect(page, '문서 둘을 거쳐 뒤로 두 번이면 모아 보기', lambda: view() == 'parts:' and len(chunks()) == 41, lambda: (view(), tabs()), ms=15000)
        page.keyboard.press('Alt+ArrowRight')
        page.wait_for_selector('#lec-view h1:has-text("계획")', timeout=15000)
        page.keyboard.press('Alt+ArrowLeft')
        page.wait_for_selector('#lec-view.parts-view .pv-chunk', timeout=15000)

        print('[13. 많이 넘기기]')
        n0 = len(page.evaluate(SENT))
        kind('source')
        until(page, lambda: len(page.evaluate(ROWS)) > 0, 8000)
        many = page.locator('#lec-view .pt-item').count()
        kind('table')
        page.click('#lec-view .parts-send[data-act="ai"]')
        expect(page, '마흔한 개는 그대로 넘어간다 — 한 줄', lambda: len(page.evaluate(SENT)) == n0 + 1 and page.evaluate(SENT)[-1]['text'].count('@') == 41 and '\n' not in page.evaluate(SENT)[-1]['text'], lambda: len(page.evaluate(SENT)))
        # 100개를 넘기려고 표가 많은 문서를 둘 더 둔다
        put('2-조사/원자료/월별-2.md', BIG.replace('# 원자료 모음', '# 원자료 모음 2'))
        put('2-조사/원자료/월별-3.md', BIG.replace('# 원자료 모음', '# 원자료 모음 3'))
        expect(page, '표가 101개가 된다', lambda: page.evaluate(KINDS).get('table') == 101, lambda: page.evaluate(KINDS), ms=20000)
        n1 = len(page.evaluate(SENT))
        page.click('#lec-view .parts-send[data-act="ai"]')
        expect(page, '100개가 넘으면 넣지 않고 좁히라고 알린다', lambda: '좁히세요' in page.evaluate(TOAST) and len(page.evaluate(SENT)) == n1, lambda: page.evaluate(TOAST))
        filt('7월')
        expect(page, "'7월' 로 좁히면", lambda: '거른 결과' in page.evaluate(INFO) and len(chunks()) <= 12, lambda: page.evaluate(INFO))
        page.click('#lec-view .parts-send[data-act="ai"]')
        expect(page, '— 넘어간다', lambda: len(page.evaluate(SENT)) == n1 + 1 and '7월 지역별 수요' in page.evaluate(SENT)[-1]['text'], lambda: len(page.evaluate(SENT)))
        check('출처는 한 줄 종류라 수가 따로다', many > 0)
        filt('')

        print('[14. 닫고 다시]')
        kind('code')
        page.keyboard.press('Control+w')
        expect(page, '닫는다', lambda: tabs() == ['보고서.md*'], tabs)
        page.keyboard.press('Control+Shift+p')
        page.wait_for_selector('#lec-palette:not([hidden])')
        page.keyboard.type('모아 보기')
        page.wait_for_timeout(300)
        page.keyboard.press('Enter')
        page.wait_for_selector('#lec-view.parts-view .parts-list', timeout=15000)
        expect(page, '다시 열면 마지막에 고른 종류가 없어도(코드 0) 있는 첫 종류로', lambda: page.evaluate("() => document.querySelector('#lec-view .parts-kinds button.active')?.dataset.kind") == 'table' and len(chunks()) > 0,
               lambda: page.evaluate("() => document.querySelector('#lec-view .parts-kinds button.active')?.dataset.kind"), ms=15000)

        check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
