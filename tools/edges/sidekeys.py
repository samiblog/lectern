"""사이드바 넷째 묶음 '폴더'와 키 (D169·D170): '폴더' 묶음(맨 아래·숫자 없음·폴더 구조 그대로·문서는 한 번 눌러 열기), Ctrl+Shift+E(펼친 묶음으로,
다시 누르면 다음 묶음, 감춘 사이드바·다른 사이드바 탭·한 줄 편집 칸에서도), 문서 트리의 키(↑↓·Home·End·→←·글자·Enter, Tab 은 한 번만),
F7·Shift+F7(바뀐 곳 다음·이전 — 현재 줄도), Alt+O(목차), Ctrl+Alt+[ ](모두 접기·펴기), Ctrl+Shift+P(명령 찾기 — 단축키가 옆에, Enter 로 실행)"""
import json
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-sidekeys-'))
proj = base / 'proj'
(proj / 'sub').mkdir(parents=True)
(proj / 'code').mkdir()
(proj / 'data').mkdir()
DOC = '# 가 문서\n\n머리 문단.\n\n## 첫 절\n\n첫 절 문단 하나.\n\n첫 절 문단 둘.\n\n## 둘째 절\n\n둘째 절 문단.\n\n### 둘째의 아래 절\n\n아래 절 문단.\n\n## 셋째 절\n\n셋째 절 문단.\n'
(proj / '가.md').write_text(DOC, encoding='utf-8')
(proj / 'sub' / '나.md').write_text('# 나 문서\n\n본문.\n', encoding='utf-8')
(proj / 'sub' / '다.md').write_text('# 다 문서\n\n본문.\n', encoding='utf-8')
(proj / 'code' / 'x.py').write_text('x = 1\n', encoding='utf-8')
(proj / 'data' / '표.csv').write_text('a,b\n1,2\n', encoding='utf-8')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)

SECS = "() => ['#lec-docs', '#lec-code', '#lec-others', '#lec-work', '#lec-folder'].map((s) => document.querySelector(s).classList.contains('grow') ? 'open' : 'closed')"
FOCUS = """() => { const a = document.activeElement;
  const sec = a?.closest('.side-sec');
  if (sec) return sec.id + ':' + (a.dataset.doc ?? a.dataset.dir ?? a.dataset.path ?? a.id ?? '');
  if (a?.closest('#lec-panes')) return 'doc';
  return a?.id || a?.tagName || ''; }"""
HERE = "() => import('/static/js/store.js').then(({ S }) => S.pane?.here?.line || 0)"
SRC = lambda: (proj / '가.md').read_text(encoding='utf-8').replace('\r\n', '\n')  # noqa: E731


def line_of(text):
    return SRC().split('\n').index(text) + 1


try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1400, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        focus = lambda: page.evaluate(FOCUS)  # noqa: E731
        here = lambda: page.evaluate(HERE)  # noqa: E731
        toast = lambda: page.text_content('#lec-toast') or ''  # noqa: E731

        def open_doc(path):
            page.evaluate("(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: p }))", path)
            page.wait_for_selector('#lec-view h1', timeout=8000)
            page.wait_for_timeout(500)

        def to_doc():
            page.click('#lec-view p >> nth=0')
            page.wait_for_timeout(150)

        open_doc('가.md')

        print("['폴더' 묶음]")
        boxes = [page.locator(s).bounding_box() for s in ('#lec-docs', '#lec-code', '#lec-others', '#lec-folder')]
        check('맨 아래에 넷째 묶음 — 문서·코드·자료·폴더 차례', all(boxes[i]['y'] < boxes[i + 1]['y'] for i in range(3)), [round(x['y']) for x in boxes])
        check("머리줄 이름은 '폴더', 숫자는 없다", page.inner_text('#lec-folder-head').strip() == '폴더' and page.locator('#lec-folder-head .n').count() == 0, page.inner_text('#lec-folder-head'))
        check("거르기 칸 옆의 '폴더' 버튼은 없어졌다", page.locator('#lec-btn-view').count() == 0)
        page.click('#lec-folder-head')
        expect(page, '누르면 그것만 펼친다', lambda: page.evaluate(SECS) == ['closed', 'closed', 'closed', 'closed', 'open'], lambda: page.evaluate(SECS))
        labels = lambda: page.locator('#lec-folder-list .row .label').all_inner_texts()  # noqa: E731
        expect(page, '폴더 구조 그대로 — 폴더 먼저, 문서와 파일이 섞여', lambda: labels()[:3] == ['code', 'data', 'sub'] and '가.md' in labels(), labels)
        check('지금 보는 문서가 강조된다', page.locator('#lec-folder-list .row.active[data-path="가.md"]').count() == 1)
        if page.get_attribute('#lec-folder-list .row[data-path="sub"]', 'aria-expanded') != 'true':   # 처음에는 문서 트리에서 펼쳐 둔 대로
            page.locator('#lec-folder-list .row[data-path="sub"] [data-toggle]').click()
        page.locator('#lec-folder-list .row[data-path="sub/나.md"]').click(modifiers=['Alt'])
        expect(page, '문서는 한 번 눌러 연다', lambda: page.locator('#lec-view h1').first.inner_text() == '나 문서')
        check('설정에 남는다 (files_open: folder)', until(page, lambda: json.loads((config / 'config.json').read_text(encoding='utf-8')).get('files_open') == 'folder'))
        page.click('#lec-docs-head')
        open_doc('가.md')

        print('[Ctrl+Shift+E]')
        to_doc()
        page.keyboard.press('Control+Shift+E')
        expect(page, '펼친 묶음(문서)의 지금 보는 문서 행으로', lambda: focus() == 'lec-docs:가.md', focus)
        seen = []
        for _ in range(5):
            page.keyboard.press('Control+Shift+E')
            page.wait_for_timeout(400)
            seen.append(focus().split(':')[0])
        check('다시 누르면 다음 묶음 — 코드 → 자료 → 작업 → 폴더 → 문서', seen == ['lec-code', 'lec-others', 'lec-work', 'lec-folder', 'lec-docs'], seen)
        check('— 그 묶음이 펼쳐진다', page.evaluate(SECS) == ['open', 'closed', 'closed', 'closed', 'closed'], page.evaluate(SECS))
        page.keyboard.press('Control+b')
        expect(page, '사이드바를 감추면', lambda: page.evaluate("document.documentElement.classList.contains('sidebar-off')"))
        to_doc()
        page.keyboard.press('Control+Shift+E')
        expect(page, '감춘 사이드바도 보이면서 그리로', lambda: not page.evaluate("document.documentElement.classList.contains('sidebar-off')") and focus().startswith('lec-docs:'), focus)
        page.locator('.side-tabs button[data-tab="recent"]').click()
        to_doc()
        page.keyboard.press('Control+Shift+E')
        expect(page, "다른 사이드바 탭이면 '파일' 탭으로", lambda: not page.is_hidden('#lec-files') and focus().startswith('lec-docs:'), focus)
        to_doc()
        page.keyboard.press('F2')
        page.wait_for_selector('#lec-view .lec-line-edit', timeout=5000)
        page.keyboard.press('End')
        page.keyboard.type(' 덧붙임')
        page.keyboard.press('Control+Shift+E')
        expect(page, '한 줄 편집 칸에서도 — 칸을 저장하고 사이드바로', lambda: '머리 문단. 덧붙임' in SRC() and focus().startswith('lec-docs:') and page.locator('#lec-view .lec-line-edit').count() == 0,
               lambda: (focus(), SRC()[:40]))

        print('[문서 트리의 키]')
        page.click('#lec-docs-head')
        row = page.locator('#lec-tree .row[data-doc="가.md"]')
        row.focus()
        before = here()
        rows = lambda: page.evaluate("() => [...document.querySelectorAll('#lec-tree .row')].map((r) => r.dataset.doc ?? r.dataset.dir)")  # noqa: E731
        check('Tab 은 트리에 한 번만 들른다 (들어올 행 하나만 0)', page.locator('#lec-tree .row[tabindex="0"]').count() == 1)
        page.keyboard.press('Home')
        expect(page, 'Home — 첫 행', lambda: focus() == f'lec-docs:{rows()[0]}', focus)
        page.keyboard.press('ArrowDown')
        expect(page, '↓ — 다음 행', lambda: focus() == f'lec-docs:{rows()[1]}', (focus, rows()))
        page.keyboard.press('End')
        expect(page, 'End — 마지막 행', lambda: focus() == f'lec-docs:{rows()[-1]}', focus)
        check('— 문서의 현재 줄은 그대로', here() == before, (before, here()))
        page.keyboard.press('Home')
        sub_closed = page.locator('#lec-tree .row[data-dir="sub"] .caret.open').count() == 0
        while focus() != 'lec-docs:sub':
            page.keyboard.press('ArrowDown')
            page.wait_for_timeout(60)
            if focus().endswith(rows()[-1]):
                break
        if not sub_closed:
            page.keyboard.press('ArrowLeft')
        page.keyboard.press('ArrowRight')
        expect(page, '접힌 폴더에서 → — 펼친다 (초점은 그 폴더)', lambda: 'sub/나.md' in rows() and focus() == 'lec-docs:sub', (focus, rows()))
        page.keyboard.press('ArrowRight')
        expect(page, '펼친 폴더에서 → — 첫 항목', lambda: focus() == 'lec-docs:sub/나.md', focus)
        page.keyboard.press('ArrowLeft')
        expect(page, '문서에서 ← — 위 폴더', lambda: focus() == 'lec-docs:sub', focus)
        page.keyboard.press('ArrowLeft')
        expect(page, '펼친 폴더에서 ← — 접는다', lambda: 'sub/나.md' not in rows() and focus() == 'lec-docs:sub', (focus, rows()))
        page.keyboard.press('ArrowRight')
        page.keyboard.press('End')
        page.keyboard.press('s')   # 한글은 playwright 가 키 없이 넣으므로 영문 이름으로
        expect(page, '글자 — 그 글자로 시작하는 행', lambda: focus() == 'lec-docs:sub', focus)
        page.keyboard.press('ArrowRight')
        page.keyboard.press('ArrowDown')
        expect(page, '— 이어서 ↓', lambda: focus() == 'lec-docs:sub/다.md', focus)
        check('— 들어올 행도 따라온다', page.locator('#lec-tree .row[tabindex="0"]').get_attribute('data-doc') == 'sub/다.md')
        page.keyboard.press('Enter')
        expect(page, 'Enter — 연다', lambda: page.locator('#lec-view h1').first.inner_text() == '다 문서')
        open_doc('가.md')

        print('[Alt+O 목차]')
        to_doc()
        was = page.get_attribute('#lec-btn-toc', 'aria-pressed')
        page.keyboard.press('Alt+o')
        expect(page, '목차를 감춘다', lambda: page.get_attribute('#lec-btn-toc', 'aria-pressed') != was)
        page.keyboard.press('Alt+o')
        expect(page, '다시 누르면 보인다', lambda: page.get_attribute('#lec-btn-toc', 'aria-pressed') == was)

        print('[Ctrl+Alt+[ · ] 모두 접기·펴기]')
        to_doc()
        page.locator('#lec-view p', has_text='아래 절 문단').click()
        page.wait_for_timeout(200)
        page.keyboard.press('Control+Alt+BracketLeft')
        folded = lambda: page.evaluate("() => [...document.querySelectorAll('#lec-view > .lec-fold')].map((h) => h.classList.contains('lec-folded'))")  # noqa: E731
        expect(page, '접을 수 있는 제목이 모두 접힌다', lambda: folded() and all(folded()), folded)
        expect(page, '— 현재 줄은 그 줄이 든 맨 바깥 절의 제목으로', lambda: here() == line_of('## 둘째 절'), here)
        page.keyboard.press('Control+Alt+BracketRight')
        expect(page, '모두 편다', lambda: not any(folded()), folded)

        print('[F7 바뀐 곳]')
        to_doc()
        page.keyboard.press('F7')
        expect(page, '바뀐 곳이 없으면 알린다', lambda: '바뀐 곳이 없습니다' in toast(), toast)
        page.keyboard.press('Home')
        text = SRC().replace('첫 절 문단 둘.', '첫 절 문단 둘 — 고침.').replace('셋째 절 문단.', '셋째 절 문단 — 고침.')
        time.sleep(1.1)
        (proj / '가.md').write_text(text, encoding='utf-8')
        expect(page, '밖에서 고치면 자동으로 다시 그린다', lambda: page.locator('#lec-view p', has_text='셋째 절 문단 — 고침').count() == 1, ms=12000)
        page.wait_for_timeout(400)
        to_doc()
        page.keyboard.press('F7')
        expect(page, 'F7 — 첫 바뀐 곳으로, 현재 줄도', lambda: here() == line_of('첫 절 문단 둘 — 고침.'), here)
        page.keyboard.press('F7')
        expect(page, 'F7 — 다음 바뀐 곳', lambda: here() == line_of('셋째 절 문단 — 고침.'), here)
        page.keyboard.press('F7')
        expect(page, 'F7 — 끝에서는 처음으로', lambda: here() == line_of('첫 절 문단 둘 — 고침.'), here)
        page.keyboard.press('Shift+F7')
        expect(page, 'Shift+F7 — 앞 바뀐 곳 (처음에서는 끝으로)', lambda: here() == line_of('셋째 절 문단 — 고침.'), here)

        print('[Ctrl+Shift+P 명령 찾기]')
        to_doc()
        page.keyboard.press('Control+Shift+P')
        expect(page, "빠른 열기가 '>' 를 넣은 채 열린다", lambda: not page.is_hidden('#lec-palette') and page.input_value('#lec-palette-input') == '>')
        cmds = lambda: page.evaluate("() => [...document.querySelectorAll('#lec-palette-list li.cmd')].map((li) => li.querySelector('.t').textContent + '|' + li.querySelector('.when').textContent)")  # noqa: E731
        check('명령이 단축키와 함께 나온다', len(cmds()) > 20 and '다음 바뀐 곳|F7' in cmds() and '목차 보이기·숨기기|Alt+O' in cmds(), cmds()[:5])
        check('키가 없는 명령도 (인쇄·모두 펼치기)', any(c.startswith('인쇄·PDF|') for c in cmds()) and any(c.startswith('모두 펼치기') for c in cmds()))
        page.keyboard.type('모두 접기')
        expect(page, "'모두 접기'를 치면 그것이 맨 위", lambda: cmds()[:1] == ['모두 접기|Ctrl+Alt+['], cmds)
        page.keyboard.press('Enter')
        expect(page, 'Enter — 닫고 그 일을 한다', lambda: page.is_hidden('#lec-palette') and folded() and all(folded()), folded)
        page.keyboard.press('Control+Shift+P')
        page.keyboard.type('shift+f7')
        expect(page, '키로도 찾는다', lambda: cmds()[:1] == ['이전 바뀐 곳|Shift+F7'], cmds)
        page.keyboard.press('Control+a')
        page.keyboard.type('>없는명령')
        expect(page, '없으면 알린다', lambda: page.locator('#lec-palette-list li.empty').inner_text() == '일치하는 명령이 없습니다')
        page.keyboard.press('Escape')
        to_doc()
        page.keyboard.press('Control+Shift+P')
        page.keyboard.type('단축키 표')
        page.keyboard.press('Enter')
        page.keyboard.press('Escape')   # 바로 — 닫은 명령 찾기 칸에 초점이 남아 Esc 를 삼키던 것 (실제 창 시험에서 찾음)
        expect(page, '명령을 고른 바로 뒤의 Esc 는 연 창을 닫는다', lambda: page.is_hidden('#lec-keys') and page.is_hidden('#lec-palette'))
        check('— 초점은 감춘 칸에 남지 않는다', page.evaluate("document.activeElement?.id") != 'lec-palette-input', page.evaluate("document.activeElement?.id"))
        to_doc()
        was = page.get_attribute('#lec-btn-toc', 'aria-pressed')
        page.keyboard.press('Control+Shift+P')
        page.keyboard.type('목차 보이기')
        page.keyboard.press('Enter')
        page.keyboard.press('Enter')   # 거듭 — 같은 명령을 또 하지 않는다 (둘째 Enter 는 문서의 것)
        page.wait_for_timeout(400)
        check('Enter 를 거듭 눌러도 명령은 한 번', page.get_attribute('#lec-btn-toc', 'aria-pressed') != was, (was, page.get_attribute('#lec-btn-toc', 'aria-pressed')))
        page.keyboard.press('Escape')
        page.keyboard.press('Alt+o')   # 목차를 처음대로
        page.wait_for_timeout(200)
        page.keyboard.press('Control+p')
        check("Ctrl+P 칸은 '>' 와 ':' 를 알려 준다", '> 로 시작하면 명령' in (page.get_attribute('#lec-palette-input', 'placeholder') or ''))
        page.keyboard.type('>모두 펴기')
        page.keyboard.press('Enter')
        expect(page, "Ctrl+P 에서 '>' 를 쳐도 명령", lambda: page.is_hidden('#lec-palette') and not any(folded()), folded)

        real = [e for e in errors if 'addressunreachable' not in e]
        check('화면 스크립트 오류 없음', not real, real[:3])
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
