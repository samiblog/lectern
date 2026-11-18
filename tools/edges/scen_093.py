"""시나리오 — 0.93.0 을 실제로 쓰는 흐름 (D169·D170):
1 키보드만으로 문서 찾아 열기 (Ctrl+Shift+E → 글자·→·↓ → Enter → F6 으로 문서)
2 AI 가 고친 세 곳을 F7 로 검토하다 한 곳을 F2 로 고친다 — 다음 F7 은 나머지로, 또 고쳐지면 그것까지 이어서, 다른 문서를 열면 비운다
3 '폴더' 묶음으로 자료 살피기 (글자·→·Enter 로 csv, 제외 폴더 펼치기, 거르기, 밖에서 파일이 생기면 따라옴, 다시 불러와도 펼친 묶음)
4 명령 찾기로 키 없는 기능 (모두 펼치기 켜고 끄기, 설정 원문 보기, 열린 문서 모두 닫기)
5 편집 중·터미널을 연 채 (전체 편집에서 Ctrl+Shift+E 로 사이드바·F6 으로 편집기, 터미널 옆에서 Alt+O)
6 vi 키를 켠 채 — 문서의 j 는 vi, 트리의 j 는 그 글자로
7 큰 프로젝트 (문서 400·파일 600) — '폴더' 묶음 펼치기와 트리의 ↓ 50번이 빠르다
8 영어 화면 — 명령 찾기·사이드바 이름이 영어로"""
import json
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-scen093-'))
proj = base / 'proj'
for d in ('research', 'reports', 'plans', 'data', 'src', 'node_modules/pkg'):
    (proj / d).mkdir(parents=True)
COPPER = ('# 구리 시장 동향\n\n요약 문단이다.\n\n## 가격\n\n가격 문단 하나.\n\n가격 문단 둘.\n\n## 수요\n\n수요 문단 하나.\n\n수요 문단 둘.\n\n'
          '## 재고\n\n재고 문단 하나.\n\n재고 문단 둘.\n\n## 전망\n\n전망 문단.\n')
files = {
    'research/구리-시장.md': COPPER,
    'research/니켈.md': '# 니켈\n\n니켈 문단.\n',
    'reports/주간-10월.md': '# 10월 주간\n\n본문.\n',
    'reports/주간-11월.md': '# 11월 주간\n\n본문.\n',
    'plans/계획.md': '# 계획\n\n본문.\n',
    'README.md': '# 읽어 보기\n\n본문.\n',
    'WORK.md': '# 업무\n\n## 할 일\n\n- [ ] 보고서\n',
    'data/가격.csv': '월,가격\n1,9000\n2,9400\n',
    'data/메모.txt': '메모\n',
    'src/collect.py': 'x = 1\n',
    'node_modules/pkg/index.js': 'module.exports = 1\n',
}
for name, text in files.items():
    (proj / name).write_text(text, encoding='utf-8')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)

# 7·8 — 큰 프로젝트를 영어 화면으로
base2 = Path(tempfile.mkdtemp(prefix='lec-scen093b-'))
big = base2 / 'big'
for i in range(40):
    d = big / f'part{i:02d}'
    d.mkdir(parents=True)
    for j in range(10):
        (d / f'doc{j:02d}.md').write_text(f'# Part {i} doc {j}\n\nText.\n', encoding='utf-8')
    for j in range(15):
        (d / f'data{j:02d}.csv').write_text('a,b\n1,2\n', encoding='utf-8')
config2 = base2 / 'config'
config2.mkdir()
(config2 / 'config.json').write_text(json.dumps({'work_alerts': False, 'language': 'en'}), encoding='utf-8')
server2, url2, port2 = serve(big, config2)

SRC = lambda: (proj / 'research/구리-시장.md').read_text(encoding='utf-8').replace('\r\n', '\n')  # noqa: E731
HERE = "() => import('/static/js/store.js').then(({ S }) => S.pane?.here?.line || 0)"
FOCUS = """() => { const a = document.activeElement;
  const sec = a?.closest('.side-sec');
  if (sec) return sec.id + ':' + (a.dataset.doc ?? a.dataset.dir ?? a.dataset.path ?? a.id ?? '');
  if (a?.closest('.CodeMirror')) return 'editor';
  if (a?.closest('#lec-panes')) return 'doc';
  if (a?.closest('#lec-term')) return 'term';
  return a?.id || a?.tagName || ''; }"""


def write(rel, text):
    time.sleep(1.1)   # 수정 시각이 바뀌게
    (proj / rel).write_text(text, encoding='utf-8')


def line_of(text):
    return SRC().split('\n').index(text) + 1


try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(viewport={'width': 1400, 'height': 900}).new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        focus = lambda: page.evaluate(FOCUS)  # noqa: E731
        here = lambda: page.evaluate(HERE)  # noqa: E731
        toast = lambda: page.text_content('#lec-toast') or ''  # noqa: E731
        h1 = lambda: page.locator('#lec-view h1').first.inner_text() if page.locator('#lec-view h1').count() else ''  # noqa: E731

        def open_doc(path, new_tab=False):
            page.evaluate("([p, n]) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: p, newTab: n }))", [path, new_tab])
            page.wait_for_timeout(600)

        def to_doc():
            page.locator('#lec-view p').first.click()
            page.wait_for_timeout(150)

        print('[1 키보드만으로 문서 찾아 열기]')
        tabs_before = page.locator('#lec-doctab-list .doc-tab').count()
        page.keyboard.press('Control+Shift+E')
        expect(page, 'Ctrl+Shift+E — 문서 트리로', lambda: focus().startswith('lec-docs:'), focus)
        page.keyboard.press('Home')
        page.keyboard.press('r')
        expect(page, "글자 r — 'reports' 폴더", lambda: focus() == 'lec-docs:reports', focus)
        for _ in range(2):
            if focus() == 'lec-docs:reports':
                page.keyboard.press('ArrowRight')
                page.wait_for_timeout(150)
        expect(page, '→ — 펼치고 첫 문서로', lambda: focus() == 'lec-docs:reports/주간-10월.md', focus)
        page.keyboard.press('ArrowDown')
        page.keyboard.press('Enter')
        expect(page, 'Enter — 연다 (지금 탭이 폴더 개요라 그 자리에)', lambda: h1() == '11월 주간' and page.locator('#lec-doctab-list .doc-tab').count() == tabs_before, h1)
        page.keyboard.press('F6')
        expect(page, 'F6 — 문서로 (바로 ↓ 로 읽는다)', lambda: focus() == 'doc', focus)
        page.keyboard.press('ArrowDown')
        expect(page, '— 현재 줄이 움직인다', lambda: here() > 1, here)

        print('[2 AI 가 고친 세 곳을 F7 로 검토하며 고치기]')
        open_doc('research/구리-시장.md')
        to_doc()
        write('research/구리-시장.md', COPPER.replace('가격 문단 둘.', '가격 문단 둘 — 9,400달러로 올랐다.')
              .replace('수요 문단 하나.', '수요 문단 하나 — 전력망 투자.').replace('재고 문단 둘.', '재고 문단 둘 — 2주치.'))
        expect(page, 'AI 가 고친 것이 자동으로 그려진다', lambda: page.locator('#lec-view p', has_text='2주치').count() == 1, ms=12000)
        page.wait_for_timeout(300)
        page.keyboard.press('F7')
        expect(page, 'F7 — 첫째 (가격)', lambda: here() == line_of('가격 문단 둘 — 9,400달러로 올랐다.'), here)
        page.keyboard.press('F7')
        expect(page, 'F7 — 둘째 (수요)', lambda: here() == line_of('수요 문단 하나 — 전력망 투자.'), here)
        page.keyboard.press('F2')
        page.wait_for_selector('#lec-view .lec-line-edit', timeout=5000)
        page.keyboard.press('End')
        page.keyboard.type(' (확인)')
        page.keyboard.press('Enter')
        expect(page, '— 그 줄을 F2 로 고치고 Enter (저장, 칸은 닫힘)', lambda: '전력망 투자. (확인)' in SRC() and page.locator('#lec-view .lec-line-edit').count() == 0, SRC)
        page.wait_for_timeout(700)
        page.keyboard.press('F7')
        expect(page, '고친 뒤의 F7 — 나머지 셋째로 (내가 고친 곳이나 처음으로 가지 않는다)', lambda: here() == line_of('재고 문단 둘 — 2주치.'), here)
        page.keyboard.press('Shift+F7')
        expect(page, 'Shift+F7 — 앞의 것 (내가 고친 줄)', lambda: here() == line_of('수요 문단 하나 — 전력망 투자. (확인)'), here)
        write('research/구리-시장.md', SRC().replace('전망 문단.', '전망 문단 — 상승.').replace('요약 문단이다.', '요약 문단이다 (갱신).'))
        expect(page, 'AI 가 또 고친다', lambda: page.locator('#lec-view p', has_text='상승').count() == 1, ms=12000)
        page.wait_for_timeout(300)
        seen = []
        for _ in range(3):
            page.keyboard.press('F7')
            page.wait_for_timeout(250)
            seen.append(here())
        want = [line_of('재고 문단 둘 — 2주치.'), line_of('전망 문단 — 상승.'), line_of('요약 문단이다 (갱신).')]
        check('— 앞서 바뀐 곳과 새로 바뀐 곳을 이어서, 보던 자리 다음부터 (재고 → 전망 → 처음의 요약)', seen == want, (seen, want))
        count = page.evaluate("() => import('/static/js/store.js').then(({ S }) => S.pane.marks.all.length)")
        check('— 이 문서를 연 뒤 바뀐 곳은 다섯', count == 5, count)
        open_doc('research/니켈.md')
        to_doc()
        page.keyboard.press('F7')
        expect(page, '다른 문서를 열면 비운다 (알림)', lambda: '바뀐 곳이 없습니다' in toast(), toast)
        page.keyboard.press('Alt+ArrowLeft')
        expect(page, '뒤로 와서 다시 그린 구리 문서도 새로 시작', lambda: h1() == '구리 시장 동향')
        page.wait_for_timeout(400)
        to_doc()
        page.keyboard.press('F7')
        expect(page, '— 바뀐 곳이 없다고 알린다', lambda: '바뀐 곳이 없습니다' in toast(), toast)

        print("[3 '폴더' 묶음으로 자료 살피기]")
        page.click('#lec-folder-head')
        flabels = lambda: page.locator('#lec-folder-list .row .label').all_inner_texts()  # noqa: E731
        top = lambda: page.evaluate("() => [...document.querySelectorAll('#lec-folder-list .row')].map((r) => r.dataset.path).filter((x) => !x.includes('/'))")  # noqa: E731
        expect(page, '폴더 먼저 — 문서·코드·자료·제외 폴더가 한 트리에', lambda: top() == ['data', 'node_modules', 'plans', 'reports', 'research', 'src', 'README.md', 'WORK.md'], top)
        page.keyboard.press('Control+Shift+E')
        expect(page, '머리줄을 누른 뒤의 Ctrl+Shift+E — 다음 묶음이 아니라 그 목록으로', lambda: focus().startswith('lec-folder:') and focus() != 'lec-folder:lec-folder-head', focus)
        page.keyboard.press('Home')
        page.keyboard.press('d')
        expect(page, '글자 d — data', lambda: focus() == 'lec-folder:data', focus)
        for _ in range(2):
            if focus() == 'lec-folder:data':
                page.keyboard.press('ArrowRight')
                page.wait_for_timeout(200)
        expect(page, '→ — 펼치고 첫 항목', lambda: focus() == 'lec-folder:data/가격.csv', focus)
        page.keyboard.press('Enter')
        expect(page, 'Enter — csv 를 표로', lambda: page.locator('#lec-view .csv-view, #lec-view table').count() > 0, ms=8000)
        page.keyboard.press('F6')
        page.keyboard.press('Control+Shift+E')
        expect(page, '— 표에서 Ctrl+Shift+E 는 그 묶음 안의 지금 보는 csv 로', lambda: focus() == 'lec-folder:data/가격.csv', focus)
        page.locator('#lec-folder-list .row[data-path="node_modules"]').click()
        page.keyboard.press('ArrowRight')
        expect(page, '제외 폴더(흐린)도 → 로 펼치면 읽는다', lambda: page.locator('#lec-folder-list .row[data-path="node_modules/pkg"]').count() == 1, ms=8000)
        page.fill('#lec-filter', '주간')
        expect(page, '거르면 맞는 문서가 평평하게', lambda: sorted(flabels()) == ['주간-10월.md', '주간-11월.md'], flabels)
        page.fill('#lec-filter', '')
        (proj / 'data' / '새자료.pdf').write_bytes(b'%PDF-1.4\n')
        (proj / 'research' / '새-문서.md').write_text('# 새 문서\n\n글.\n', encoding='utf-8')
        expect(page, '밖에서 생긴 자료와 문서가 따라온다', lambda: page.locator('#lec-folder-list .row[data-path="data/새자료.pdf"]').count() == 1
               and page.locator('#lec-folder-list .row[data-path="research/새-문서.md"]').count() == 1, ms=12000)
        page.wait_for_timeout(800)
        page.reload()
        page.wait_for_selector('#lec-doctab-list .doc-tab', timeout=20000)
        expect(page, "다시 불러와도 '폴더' 묶음이 펼쳐져 있다", lambda: page.evaluate("document.querySelector('#lec-folder').classList.contains('grow')")
               and page.locator('#lec-folder-list .row').count() > 5, ms=10000)

        print('[4 명령 찾기로 키 없는 기능]')
        open_doc('research/구리-시장.md', True)
        open_doc('research/니켈.md', True)
        to_doc()
        page.keyboard.press('Control+Shift+P')
        page.keyboard.type('모두 펼치기')
        page.keyboard.press('Enter')
        expect(page, "'모두 펼치기' — 열린 문서 탭들을 창 전체에", lambda: page.evaluate("document.documentElement.classList.contains('spread-on')"),
               lambda: page.evaluate("document.documentElement.className"))
        page.keyboard.press('Control+Shift+P')
        page.keyboard.type('모두 펼치기')
        page.keyboard.press('Enter')
        expect(page, '— 다시 고르면 원래대로', lambda: not page.evaluate("document.documentElement.classList.contains('spread-on')"))
        page.keyboard.press('Control+Shift+P')
        page.keyboard.type('원문')
        page.keyboard.press('Enter')
        expect(page, "'설정 원문 보기' — 창이 열린다", lambda: not page.is_hidden('#lec-raw'))
        page.keyboard.press('Escape')
        expect(page, '— Esc 로 닫힌다', lambda: page.is_hidden('#lec-raw'))
        to_doc()
        page.keyboard.press('Control+Shift+P')
        page.keyboard.type('열린 문서 모두')
        page.keyboard.press('Enter')
        expect(page, "'열린 문서 모두 닫기' — 폴더 개요 하나만", lambda: page.locator('#lec-doctab-list .doc-tab').count() == 1 and page.locator('#lec-view .ov-head').count() == 1, ms=8000)

        print('[5 편집 중·터미널을 연 채]')
        open_doc('research/니켈.md')
        to_doc()
        page.keyboard.press('Control+e')
        page.wait_for_selector('.CodeMirror', timeout=15000)
        page.click('.CodeMirror-code')
        page.wait_for_timeout(200)
        page.keyboard.press('Control+Shift+E')
        expect(page, '전체 편집 중 Ctrl+Shift+E — 사이드바로 (편집기는 그대로)', lambda: focus().startswith('lec-') and page.locator('.CodeMirror').count() == 1, focus)
        page.keyboard.press('F6')
        expect(page, 'F6 — 편집기로 돌아온다', lambda: focus() == 'editor', focus)
        page.keyboard.press('Escape')
        page.wait_for_selector('.CodeMirror', state='detached', timeout=8000)
        page.keyboard.press('Control+`')
        page.wait_for_selector('#lec-term .term-box:not([hidden]) .xterm', timeout=15000)
        page.wait_for_timeout(600)
        to_doc()
        side = page.evaluate("document.documentElement.classList.contains('toc-with-term')")
        page.keyboard.press('Alt+o')
        expect(page, '터미널 옆에서 Alt+O — 목차를 함께 보기', lambda: page.evaluate("document.documentElement.classList.contains('toc-with-term')") != side)
        page.keyboard.press('Alt+o')
        expect(page, '— 다시 누르면 원래대로', lambda: page.evaluate("document.documentElement.classList.contains('toc-with-term')") == side)
        page.keyboard.press('Control+`')
        page.wait_for_timeout(400)

        print('[6 vi 키를 켠 채]')
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ vi_keys: true }))")
        page.wait_for_timeout(300)
        open_doc('research/구리-시장.md')
        to_doc()
        page.keyboard.press('g')
        page.keyboard.press('g')
        page.keyboard.press('j')
        expect(page, '문서의 j — vi 의 아래 줄', lambda: here() > 1, here)
        at = here()
        page.keyboard.press('Control+Shift+E')
        if not focus().startswith('lec-docs:'):
            page.click('#lec-docs-head')
            page.keyboard.press('Control+Shift+E')
        page.keyboard.press('Home')
        page.keyboard.press('r')
        expect(page, '트리의 r — 그 글자로 시작하는 행 (vi 키가 아님)', lambda: focus() == 'lec-docs:reports', focus)
        check('— 문서의 현재 줄은 그대로', here() == at, (at, here()))
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ vi_keys: false }))")

        real = [e for e in errors if 'addressunreachable' not in e]
        check('화면 스크립트 오류 없음 (1~6)', not real, real[:3])

        print('[7·8 큰 프로젝트 · 영어 화면]')
        page2 = browser.new_context(viewport={'width': 1400, 'height': 900}).new_page()
        errors2 = []
        page2.on('pageerror', lambda e: errors2.append(str(e)[:300]))
        page2.goto(url2)
        page2.wait_for_selector('#lec-tree .row.file', timeout=30000)
        check("영어 화면의 넷째 묶음 이름 — 'Folders'", page2.inner_text('#lec-folder-head').strip() == 'Folders', page2.inner_text('#lec-folder-head'))
        t0 = time.monotonic()
        page2.click('#lec-folder-head')
        page2.wait_for_function("document.querySelectorAll('#lec-folder-list .row').length >= 40", timeout=15000)
        took = time.monotonic() - t0
        check(f"'폴더' 묶음 펼치기 — 문서 400·파일 600 ({took:.2f}초)", took < 3, took)
        page2.click('#lec-docs-head')
        page2.locator('#lec-tree .row').first.focus()
        t0 = time.monotonic()
        for _ in range(50):
            page2.keyboard.press('ArrowDown')
        page2.wait_for_timeout(100)
        took = time.monotonic() - t0
        rows = page2.evaluate("() => [...document.querySelectorAll('#lec-tree .row')].map((r) => r.dataset.doc ?? r.dataset.dir)")
        now = page2.evaluate("document.activeElement?.dataset.doc ?? document.activeElement?.dataset.dir")
        check(f'트리의 ↓ 50번 ({took:.2f}초) — 50번째 행', now == rows[min(50, len(rows) - 1)] and took < 5, (now, took))
        page2.keyboard.press('Control+Shift+P')
        cmds = page2.evaluate("() => [...document.querySelectorAll('#lec-palette-list li.cmd')].map((li) => li.querySelector('.t').textContent + '|' + li.querySelector('.when').textContent + '|' + li.querySelector('.p').textContent)")
        check('명령 찾기가 영어로 — 이름·묶음', 'Next change|F7|Find & move' in cmds and any(c.startswith('Show or hide the contents|Alt+O') for c in cmds), cmds[:4])
        hangul = [c for c in cmds if any('가' <= ch <= '힣' for ch in c)]
        check('— 한글이 남지 않음', not hangul, hangul[:3])
        page2.keyboard.type('fold all')
        page2.wait_for_timeout(200)
        first = page2.evaluate("() => document.querySelector('#lec-palette-list li.cmd .t')?.textContent")
        check("— 'fold all' 을 치면 'Fold all' 이 맨 위", first == 'Fold all', first)
        page2.keyboard.press('Escape')
        check('화면 스크립트 오류 없음 (7·8)', not errors2, errors2[:3])
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server2, base2)
    stop(server, base)
report()
