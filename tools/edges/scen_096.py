"""시나리오 — 0.96.0 작은 수정 여덟 가지를 한 연구 프로젝트에서 이어서 쓴다 (D177~D180):
1 노트북 폭(1000px) 창 — 툴바 단추가 겹치지 않는다
2 보고서의 좁은 차트 — [표]·[복사] 가 차트 제목을 가리지 않는다
3 줄마다 이어 쓴 문단의 가운데 줄을 한 줄 편집으로 고친다 — 다음 줄이 올라붙지 않고, 저장은 그 줄만
4 '자료'의 만들기 — 고른 폴더에 CSV(머리행)를 만들고 한 행을 적어 저장 — BOM·CRLF 그대로
5 '코드'의 만들기 — 이름만 쳐도 프로젝트의 확장자(.py)로, 편집 모드에서 적어 저장
6 '문서'의 만들기 — 폴더를 만들고 그 안에 이어서 md 문서
7 같은 이름의 README 두 개를 탭으로 — 폴더로 가리고, 제목을 켜면 제목·경로로
8 터미널 둘 — 2번을 쓰고 설정 창 ▣ 는 2번으로, 1번은 화면만 다시 붙어도 같은 셸"""
import json
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-scen096-'))
proj = base / 'proj'
for folder in ('보고', '자료', 'src'):
    (proj / folder).mkdir(parents=True)
LINES = ['구리 재고가 줄었다.', '니켈 값은 그대로다.', '리튬은 다시 올랐다.']
CHART = ('```vega-lite\n{"title": "월별 구리 가격과 재고 — 2026년 상반기 (USD/t)", "width": "container", "height": 140,\n'
         ' "data": {"values": [{"월": "1월", "가격": 9100}, {"월": "2월", "가격": 9350}]},\n'
         ' "mark": "line", "encoding": {"x": {"field": "월", "type": "ordinal"}, "y": {"field": "가격", "type": "quantitative"}}}\n```\n')
REPORT = '# 시장 점검\n\n' + '\n'.join(LINES) + '\n\n' + CHART
(proj / '보고' / '분석.md').write_bytes(REPORT.encode('utf-8'))
(proj / '보고' / 'README.md').write_bytes('# 개요\n\n보고 폴더.\n'.encode('utf-8'))
(proj / '자료' / 'README.md').write_bytes('# 개요\n\n자료 폴더.\n'.encode('utf-8'))
(proj / 'src' / 'load.py').write_bytes(b'x = 1\n')
(proj / 'src' / 'plot.py').write_bytes(b'y = 2\n')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False, 'settings_section': 'ai'}), encoding='utf-8')
server, url, port = serve(proj, config)

ROWS = "(sel) => { const el = document.querySelector(sel); const r = document.createRange(); r.selectNodeContents(el); return new Set([...r.getClientRects()].filter((x) => x.width > 1).map((x) => Math.round(x.top / 4))).size; }"
SPOT = """(t) => { const w = document.createTreeWalker(document.querySelector('#lec-view'), NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) { const i = n.textContent.indexOf(t); if (i < 0) continue;
    const r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + t.length); const b = r.getBoundingClientRect(); return { x: b.left + b.width / 2, y: b.top + b.height / 2 }; } return null; }"""
OVERLAP = """() => { const bar = document.querySelector('#lec-toolbar'); const items = [...bar.querySelectorAll(':scope > *, :scope > * > button')].filter((e) => e.offsetParent && e.getBoundingClientRect().width > 0);
  for (let i = 0; i < items.length; i++) for (let j = i + 1; j < items.length; j++) { if (items[i].contains(items[j]) || items[j].contains(items[i])) continue;
    const a = items[i].getBoundingClientRect(), b = items[j].getBoundingClientRect(); if (a.right - 1 > b.left && b.right - 1 > a.left) return (items[i].id || items[i].className) + ' × ' + (items[j].id || items[j].className); }
  return bar.scrollWidth > bar.clientWidth ? 'overflow' : ''; }"""
CHART_GAP = """() => { const pre = document.querySelector('#lec-view pre.lec-chart.chart-ok'); const tools = pre.querySelector('.lec-chart-tools').getBoundingClientRect();
  const title = [...pre.querySelectorAll('svg text')].find((x) => x.textContent.includes('구리')); const b = title.getBoundingClientRect();
  return !(tools.right < b.left || tools.left > b.right || tools.bottom < b.top || tools.top > b.bottom); }"""
VALUE = "() => document.querySelector('.CodeMirror')?.CodeMirror.getValue() ?? null"
TEXT = """(n) => import('/static/js/store.js').then((m) => { const term = m.S.tab.terms.find((x) => x.n === n); if (!term) return '';
  const b = term.xterm.buffer.active; const out = []; for (let i = 0; i < b.length; i++) out.push(b.getLine(i).translateToString(true)); return out.join('\\n'); })"""
TAB_ROWS = """() => [...document.querySelectorAll('#lec-doctab-list .doc-tab .name')].map((el) => { const tell = el.querySelector('.tell');
  return [[...el.childNodes].filter((n) => n !== tell).map((n) => n.textContent).join('').trim(), tell ? tell.textContent : '']; })"""


def raw(rel):
    for _ in range(40):
        try:
            return (proj / rel).read_bytes()
        except OSError:
            time.sleep(0.05)
    return None


try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1000, 'height': 820})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.on('dialog', lambda d: d.accept())
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        toast = lambda: page.text_content('#lec-toast') or ''  # noqa: E731
        msg = lambda: page.evaluate("() => { const m = document.querySelector('#lec-newdoc-msg'); return m.hidden ? '' : m.textContent; }")  # noqa: E731
        term_text = lambda n: page.evaluate(TEXT, n)  # noqa: E731

        def close_editor():
            page.keyboard.press('Escape')
            page.wait_for_selector('.CodeMirror', state='detached', timeout=8000)

        def section(name):
            page.click(f'#lec-{name}-head')
            page.wait_for_function("(n) => !document.querySelector(`#lec-${n}`).classList.contains('closed')", arg=name)

        print('[1 노트북 폭 창]')
        check('1000px — 툴바 단추가 겹치거나 넘치지 않는다', page.evaluate(OVERLAP) == '', page.evaluate(OVERLAP))

        print('[2 보고서의 좁은 차트]')
        page.locator('#lec-tree .row.dir[data-dir="보고"]').click()
        page.locator('#lec-tree .row.file[data-doc="보고/분석.md"]').click()
        page.wait_for_selector('#lec-view pre.lec-chart.chart-ok svg', timeout=20000)
        page.wait_for_timeout(500)
        page.locator('#lec-view pre.lec-chart').hover()
        expect(page, '차트 단추가 차트 제목과 겹치지 않는다', lambda: page.evaluate(CHART_GAP) is False)

        print('[3 이어 쓴 문단의 가운데 줄]')
        p_sel = '#lec-view p'
        rows = lambda: page.evaluate(ROWS, p_sel)  # noqa: E731
        check('문단은 세 줄로 보인다', rows() == 3, rows())
        at = page.evaluate(SPOT, LINES[1])
        page.mouse.click(at['x'], at['y'])
        page.keyboard.press('F2')
        page.wait_for_selector('#lec-view .lec-line-edit', timeout=5000)
        check('가운데 줄을 열어도 세 줄 — 다음 줄이 올라붙지 않는다', rows() == 3, rows())
        page.keyboard.press('End')
        page.keyboard.type(' (확인)')
        page.keyboard.press('Enter')
        want = REPORT.replace(LINES[1], LINES[1] + ' (확인)').encode('utf-8')
        expect(page, '저장 — 그 줄만 바뀐다', lambda: raw('보고/분석.md') == want, lambda: raw('보고/분석.md')[:120])
        page.keyboard.press('Escape')

        print("[4 '자료'의 만들기 — CSV]")
        section('others')
        check("'자료' 목록은 비어 있다 — 자료 파일이 아직 없다 (문서만 든 폴더는 나오지 않는다)", page.locator('#lec-others-list .row').count() == 0)
        page.click('#lec-others-new')
        page.wait_for_selector('#lec-newdoc:not([hidden])')
        check('고른 것이 없으면 위치는 프로젝트 맨 위, 이름은 새 자료.csv', page.input_value('#lec-newdoc-folder') == '' and page.input_value('#lec-newdoc-title') == '새 자료.csv',
              (page.input_value('#lec-newdoc-folder'), page.input_value('#lec-newdoc-title')))
        page.select_option('#lec-newdoc-folder', '자료')   # 위치에서 폴더를 고른다 — 비어 있는 폴더도 나온다
        page.keyboard.type('측정값')
        page.fill('#lec-newdoc-header', '날짜, 값')
        page.keyboard.press('Enter')
        page.wait_for_selector('.CodeMirror', timeout=15000)
        page.evaluate("() => { const cm = document.querySelector('.CodeMirror').CodeMirror; cm.setCursor(cm.lineCount() - 1, 0); }")
        page.keyboard.type('2026-11-19,42')
        page.keyboard.press('Control+s')
        expect(page, '자료/측정값.csv — BOM·머리행·CRLF 로 저장', lambda: raw('자료/측정값.csv') == b'\xef\xbb\xbf' + '날짜,값\r\n2026-11-19,42'.encode('utf-8'),
               lambda: raw('자료/측정값.csv'))
        close_editor()

        print("[5 '코드'의 만들기]")
        section('code')
        page.locator('#lec-code-list .row', has_text='src').first.click()
        page.click('#lec-code-new')
        page.wait_for_selector('#lec-newdoc:not([hidden])')
        check('처음 확장자는 프로젝트의 .py', page.input_value('#lec-newdoc-title') == '새 파일.py', page.input_value('#lec-newdoc-title'))
        page.fill('#lec-newdoc-title', '정리')
        page.keyboard.press('Enter')
        page.wait_for_selector('.CodeMirror', timeout=15000)
        page.keyboard.type('print(1)')
        page.keyboard.press('Control+s')
        expect(page, 'src/정리.py — 편집 모드에서 적어 저장', lambda: raw('src/정리.py') == b'print(1)', lambda: raw('src/정리.py'))
        close_editor()
        page.click('#lec-code-new')
        page.wait_for_selector('#lec-newdoc:not([hidden])')
        page.fill('#lec-newdoc-title', 'load.py')
        page.keyboard.press('Enter')
        expect(page, '같은 이름 — 덮어쓰지 않고 창이 알린다', lambda: '같은 이름' in msg() and raw('src/load.py') == b'x = 1\n', msg)
        page.keyboard.press('Escape')

        print("[6 '폴더' 묶음의 만들기 — 폴더 다음 문서 (폴더는 '폴더' 묶음에서만 — D203)]")
        section('folder')
        page.click('#lec-folder-new')
        page.wait_for_selector('#lec-newdoc:not([hidden])')
        page.click('#lec-newdoc-dir')
        page.select_option('#lec-newdoc-folder', '보고')
        page.fill('#lec-newdoc-title', '2026')
        page.keyboard.press('Enter')
        expect(page, '폴더를 만들고 md 문서로 이어서 — 위치는 새 폴더', lambda: (proj / '보고' / '2026').is_dir() and page.evaluate(
            "() => document.querySelector('#lec-newdoc .mdstyle-kinds button.on')?.dataset.kind") == 'md' and page.input_value('#lec-newdoc-folder') == '보고/2026', msg)
        page.fill('#lec-newdoc-title', '회의')
        page.keyboard.press('Enter')
        expect(page, '보고/2026/회의.md 가 생기고 열린다', lambda: raw('보고/2026/회의.md') is not None and page.locator('#lec-view h1', has_text='회의').count() == 1)
        page.keyboard.press('Escape')

        print('[7 같은 이름의 README 탭]')
        section('docs')
        page.locator('#lec-tree .row.file[data-doc="보고/README.md"]').click(modifiers=['Control'])
        page.locator('#lec-tree .row.dir[data-dir="자료"]').click()
        page.locator('#lec-tree .row.file[data-doc="자료/README.md"]').click(modifiers=['Control'])
        tabs = lambda: sorted(r for r in page.evaluate(TAB_ROWS) if r[0] in ('README.md', '개요'))  # noqa: E731
        expect(page, '탭 — README.md · 보고 / README.md · 자료', lambda: tabs() == [['README.md', '보고'], ['README.md', '자료']], tabs)
        page.click('#lec-btn-titles')
        expect(page, "'제목'을 켜면 개요 · 경로", lambda: tabs() == [['개요', '보고/README.md'], ['개요', '자료/README.md']], tabs)
        page.locator('#lec-content').focus()
        page.keyboard.press('Control+p')
        page.wait_for_selector('#lec-palette:not([hidden]) #lec-palette-list li')
        names = page.evaluate("() => [...document.querySelectorAll('#lec-palette-list li .t')].map((el) => el.textContent.trim())")
        check('문서 열기도 제목으로', '시장 점검' in names and '개요' in names, names)
        page.keyboard.press('Escape')
        page.click('#lec-btn-titles')

        print('[8 터미널 둘 — 설정 ▣ 와 화면 다시 붙기]')
        page.set_viewport_size({'width': 1300, 'height': 820})
        page.keyboard.press('Control+`')
        page.wait_for_selector('#lec-term .term-box:not([hidden]) .xterm', timeout=15000)
        until(page, lambda: 'PS ' in term_text(0), 20000)
        page.locator('#lec-term .term-pane[data-n="0"] .term-box').click()
        page.keyboard.type('function prompt { "P" + "S> " }; $mark = 7; "pi" + "d=$PID"')
        page.keyboard.press('Enter')
        until(page, lambda: any(line.startswith('pid=') for line in term_text(0).split('\n')), 10000)
        pid = next(line[4:].strip() for line in term_text(0).split('\n') if line.startswith('pid='))
        page.click('#lec-term-new')
        until(page, lambda: 'PS ' in term_text(1), 20000)
        page.locator('#lec-term .term-pane[data-n="1"] .term-box').click()
        expect(page, '2번을 눌러 고른다', "import('/static/js/store.js').then((m) => m.S.tab.term?.n === 1)")
        page.locator('#lec-content').focus()
        page.keyboard.press('Control+,')
        page.wait_for_selector('#lec-settings:not([hidden])')
        page.click('#lec-settings .set-nav button[data-set="ai"]')
        page.click('#lec-aiguide-term')
        expect(page, '설정 창 ▣ — 2번 터미널로', lambda: '2번 터미널에 넣었습니다' in toast(), toast)
        page.keyboard.press('Escape')
        page.locator('#lec-term .term-pane[data-n="0"] .term-pane-head').click(button='right')   # 둘이면 쌓여 탭 줄 대신 칸 머리줄
        page.locator('#lec-menu').get_by_text('1번 터미널 화면 다시 붙기').click()
        expect(page, '1번 화면 다시 붙기 — 지난 출력이 다시 보인다', lambda: f'pid={pid}' in term_text(0), lambda: term_text(0)[-200:])
        page.locator('#lec-term .term-pane[data-n="0"] .term-box').click()
        page.keyboard.type('"pi" + "d=$PID mark=$mark end" + "-1"')
        page.keyboard.press('Enter')
        expect(page, '— 같은 셸 (PID 와 변수가 그대로)', lambda: f'pid={pid} mark=7 end-1' in term_text(0), lambda: term_text(0)[-200:])

        check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
