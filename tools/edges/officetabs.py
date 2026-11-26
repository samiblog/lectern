"""사이드바 '문서'의 하위 묶음 고르기와 오피스 하위 묶음 (D202), 목록의 이름은 파일 이름이 기본.
- 기본: Word·PowerPoint·Excel·CSV·HWP 는 보이고 업무·형광펜·할 일은 보이지 않는다. 설정 창 '일반' 과 머리줄의 우클릭으로 켜고 끈다.
- 오피스 묶음의 행은 '자료' 목록의 파일과 같다: 엑셀·csv 는 한 번 누르면 표, 두 번 누르면 그 프로그램 (기본 앱), Word·PowerPoint·한글은 두 번 누르면.
  우클릭은 '자료' 목록의 메뉴, Enter·F2·Shift+→ 도. '자료' 목록에도 그대로 남는다. 제외 폴더 안의 것은 넣지 않는다.
- 파일이 생기고 지워지면 묶음이 따른다. 거르기 칸. 영어 화면.
- 목록의 md 문서 이름: 사이드바·폴더 개요·담기의 문서 고르기는 기본이 파일 이름, '제목' 을 켜면 제목 (설정 창에도 같은 칸)."""
import json
import sys
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import ROOT, check, expect, fails, report, serve, stop, until

sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from test_sheet import make_xlsx  # noqa: E402

base = Path(tempfile.mkdtemp(prefix='lec-office-'))
proj = base / '사업'
(proj / '보고').mkdir(parents=True)
(proj / '자료' / '예산').mkdir(parents=True)
(proj / 'node_modules' / 'x').mkdir(parents=True)
(proj / '보고서.md').write_text('# 2026년 사업 보고서\n\n- [ ] 표 고치기\n\n==칠한 글==\n', encoding='utf-8', newline='\n')
(proj / '보고' / '초안.md').write_text('# 초안 제목\n\n글\n', encoding='utf-8', newline='\n')
(proj / 'WORK.md').write_text('# 업무\n\n상태: 진행\n', encoding='utf-8', newline='\n')
(proj / '보고' / '계획서.docx').write_bytes(b'PK\x03\x04 word')
(proj / '보고' / '옛 계획.doc').write_bytes(b'\xd0\xcf\x11\xe0 doc')
(proj / '보고' / '발표.pptx').write_bytes(b'PK\x03\x04 ppt')
(proj / '보고' / '공문.hwp').write_bytes(b'\xd0\xcf\x11\xe0 hwp')
(proj / '보고' / '공문2.hwpx').write_bytes(b'PK\x03\x04 hwpx')
(proj / '자료' / '예산' / '표.csv').write_text('항목,금액\n인건비,100\n', encoding='utf-8')
(proj / '자료' / '목록.tsv').write_text('a\tb\n1\t2\n', encoding='utf-8')
(proj / '자료' / '옛 예산.xls').write_bytes(b'\xd0\xcf\x11\xe0 xls')
make_xlsx(proj / '자료' / '예산' / '예산.xlsx', sheets=[('값', '<row r="1"><c r="A1" t="s"><v>0</v></c></row><row r="2"><c r="A2"><v>2026</v></c></row>', None)], shared=('연도',))
(proj / '자료' / '그림.png').write_bytes(b'\x89PNG\r\n')
(proj / 'node_modules' / 'x' / '숨은.docx').write_bytes(b'PK\x03\x04 x')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')

KINDS = "() => [...document.querySelectorAll('#lec-docs .kind-head')].map((b) => b.dataset.kind + ':' + b.querySelector('.n').textContent)"
ROWS = "() => [...document.querySelectorAll('#lec-tree .row')].map((r) => (r.dataset.file ? 'F:' : r.dataset.dir != null ? 'D:' : 'M:') + r.querySelector('.label').textContent)"
CONF = "() => import('/static/js/store.js').then(({ S }) => ({ kinds: S.config.doc_kinds, open: S.view && S.view.type + ':' + S.view.path }))"
MENU = "() => [...document.querySelectorAll('#lec-menu button, #lec-menu .menu-item')].map((b) => b.textContent.trim())"

server, url, port = serve(proj, config)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1300, 'height': 900})
        errors, opened = [], []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.on('request', lambda r: opened.append(json.loads(r.post_data or '{}').get('path')) if r.url.endswith('/api/open-external') else None)
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)

        def kinds():
            return page.evaluate(KINDS)

        def pick_kind(k):
            page.click(f'#lec-docs .kind-head[data-kind="{k}"]')
            page.wait_for_timeout(150)

        def rows():
            return page.evaluate(ROWS)

        print('[기본 — 오피스는 보이고 업무·형광펜·할 일은 없다]')
        got = until(page, lambda: (k := kinds()) and any(x.startswith('word:') for x in k) and k)
        check('하위 묶음: 전체·Word·PowerPoint·Excel·CSV·HWP', [x.split(':')[0] for x in got] == ['all', 'word', 'ppt', 'excel', 'hwp'], got)
        check('개수 — Word 2 (docx·doc), PowerPoint 1, Excel·CSV 4 (xlsx·xls·csv·tsv), HWP 2', got == ['all:3', 'word:2', 'ppt:1', 'excel:4', 'hwp:2'], got)
        check('설정 doc_kinds 의 기본은 오피스 넷', page.evaluate(CONF)['kinds'] == ['word', 'ppt', 'excel', 'hwp'])
        check('목록의 md 문서는 파일 이름 (제목 아님)', 'M:보고서.md' in rows() and 'M:2026년 사업 보고서' not in rows(), rows())
        start_view = page.evaluate(CONF)['open']

        print('[Word — 폴더는 펼친 채, 행은 파일]')
        pick_kind('word')
        r = rows()
        check('Word: 보고 폴더 아래 계획서.docx · 옛 계획.doc, 제외 폴더 안(node_modules)의 것은 없다', r == ['D:보고', 'F:계획서.docx', 'F:옛 계획.doc'], r)
        page.click('#lec-tree .row[data-file="보고/계획서.docx"]')
        page.wait_for_timeout(300)
        check('Word 파일을 한 번 누르면 열지 않는다', page.evaluate(CONF)['open'] == start_view and not opened, (page.evaluate(CONF), opened))
        page.dblclick('#lec-tree .row[data-file="보고/계획서.docx"]')
        check('두 번 누르면 그 프로그램으로 (기본 앱 — /api/open-external)', until(page, lambda: opened == ['보고/계획서.docx']), opened)
        page.click('#lec-tree .row[data-dir="보고"]')
        page.wait_for_timeout(200)
        check('폴더를 눌러도 접히지 않고 폴더 개요도 열지 않는다', rows() == r and page.evaluate(CONF)['open'] == start_view, (rows(), page.evaluate(CONF)))
        page.click('#lec-tree .row[data-file="보고/계획서.docx"]', button='right')
        menu = until(page, lambda: page.evaluate(MENU))
        check("우클릭은 '자료' 목록의 메뉴 (열기·탐색기에서 보기·이름 바꾸기)", any('탐색기에서 보기' in m for m in menu) and any('이름 바꾸기' in m for m in menu), menu)
        page.keyboard.press('Escape')

        print('[Excel·CSV — 한 번 누르면 표, 두 번 누르면 그 프로그램]')
        pick_kind('excel')
        r = rows()
        check('Excel·CSV: xlsx·xls·csv·tsv, 그림은 없다', sorted(x for x in r if x.startswith('F:')) == ['F:목록.tsv', 'F:예산.xlsx', 'F:옛 예산.xls', 'F:표.csv'], r)
        opened.clear()
        page.click('#lec-tree .row[data-file="자료/예산/표.csv"]')
        check('csv 를 누르면 표로 연다 (코드 화면)', until(page, lambda: page.evaluate(CONF)['open'] == 'code:자료/예산/표.csv'), page.evaluate(CONF))
        expect(page, '표가 보인다', "() => !!document.querySelector('#lec-view table') && document.querySelector('#lec-view').textContent.includes('인건비')")
        check('보고 있는 csv 의 행이 강조된다', until(page, "() => document.querySelector('#lec-tree .row.active')?.dataset.file === '자료/예산/표.csv'"))
        page.click('#lec-tree .row[data-file="자료/예산/예산.xlsx"]')
        check('xlsx 를 누르면 엑셀 보기', until(page, lambda: page.evaluate(CONF)['open'] == 'code:자료/예산/예산.xlsx'), page.evaluate(CONF))
        page.wait_for_timeout(500)
        page.dblclick('#lec-tree .row[data-file="자료/예산/예산.xlsx"]')
        check('xlsx 를 두 번 누르면 엑셀(기본 앱)로도', until(page, lambda: '자료/예산/예산.xlsx' in opened), opened)
        opened.clear()
        page.click('#lec-tree .row[data-file="자료/옛 예산.xls"]')
        page.wait_for_timeout(300)
        check('xls(옛 형식)는 한 번 누르면 열지 않는다', page.evaluate(CONF)['open'] == 'code:자료/예산/예산.xlsx' and not opened, (page.evaluate(CONF), opened))
        page.focus('#lec-tree .row[data-file="자료/옛 예산.xls"]')
        page.keyboard.press('Enter')
        check('Enter 는 두 번 누르기와 같게 (기본 앱)', until(page, lambda: opened == ['자료/옛 예산.xls']), opened)
        page.focus('#lec-tree .row[data-file="자료/목록.tsv"]')
        page.keyboard.press('Enter')
        check('tsv 에서 Enter 는 표로', until(page, lambda: page.evaluate(CONF)['open'] == 'code:자료/목록.tsv'), page.evaluate(CONF))
        page.focus('#lec-tree .row[data-file="자료/목록.tsv"]')
        page.keyboard.press('ArrowUp')
        check('↑ 로 옮겨 다닌다 (목록.tsv → 표.csv)', until(page, "() => document.activeElement?.closest?.('#lec-tree .row')?.dataset.file === '자료/예산/표.csv'"),
              page.evaluate("() => document.activeElement?.outerHTML?.slice(0, 120)"))
        page.evaluate("() => import('/static/js/store.js').then((m) => { window.__pasted = []; m.on('term-paste', (d) => window.__pasted.push(typeof d === 'string' ? d : d.text)); })")
        page.focus('#lec-tree .row[data-file="자료/목록.tsv"]')
        page.keyboard.press('Shift+ArrowRight')
        check("Shift+→ 는 '@경로' 를 터미널로", until(page, "() => (window.__pasted || []).some((x) => x.includes('@자료/목록.tsv'))"), page.evaluate('() => window.__pasted'))
        page.fill('#lec-filter', '예산')
        r = until(page, lambda: (x := rows()) and len(x) == 3 and x)
        check('거르기: 경로에 그 글이 있는 것만 (폴더 예산 안의 것도)', sorted(r or []) == ['F:예산.xlsx', 'F:옛 예산.xls', 'F:표.csv'], rows())
        check('거른 행 곁에 폴더', page.evaluate("() => document.querySelector('#lec-tree .row[data-file=\"자료/예산/표.csv\"] .sub')?.textContent") == '자료/예산')
        page.fill('#lec-filter', '')

        print("['자료' 목록에도 남는다]")
        page.click('#lec-others-head')
        page.click('#lec-others-list .row[data-path="보고"] [data-toggle]')
        page.click('#lec-others-list .row[data-path="자료"] [data-toggle]')
        page.click('#lec-others-list .row[data-path="자료/예산"] [data-toggle]')
        others = until(page, "() => [...document.querySelectorAll('#lec-others-list .row.file')].map((r) => r.dataset.path)")
        check("'자료' 목록에 계획서.docx·표.csv 도 그대로", others and '보고/계획서.docx' in others and '자료/예산/표.csv' in others, others)
        page.click('#lec-docs-head')
        page.wait_for_timeout(200)

        print('[파일이 생기고 지워지면]')
        (proj / '자료' / '새 발표.pptx').write_bytes(b'PK\x03\x04 new')
        check('새 pptx 가 PowerPoint 개수에', until(page, lambda: 'ppt:2' in kinds(), ms=10000), kinds())
        (proj / '보고' / '공문.hwp').unlink()
        (proj / '보고' / '공문2.hwpx').unlink()
        check('HWP 가 없어지면 그 묶음은 사라진다', until(page, lambda: not any(k.startswith('hwp:') for k in kinds()), ms=10000), kinds())

        print('[설정 창 — 하위 묶음 고르기]')
        page.keyboard.press('Control+Comma')
        page.wait_for_selector('#lec-set-kinds input', timeout=5000)
        boxes = page.evaluate("() => [...document.querySelectorAll('#lec-set-kinds input')].map((i) => i.dataset.kind + (i.checked ? '+' : '-'))")
        check('설정 창의 칸: Word·PowerPoint·Excel·CSV·한글은 켜짐, 업무·형광펜·할 일은 꺼짐', boxes == ['word+', 'ppt+', 'excel+', 'hwp+', 'work-', 'marks-', 'tasks-'], boxes)
        page.click('#lec-set-kinds input[data-kind="tasks"]')
        page.click('#lec-set-kinds input[data-kind="word"]')
        check('할 일을 켜고 Word 를 끄면 저장된다', until(page, lambda: page.evaluate(CONF)['kinds'] == ['ppt', 'excel', 'hwp', 'tasks']), page.evaluate(CONF))
        saved = json.loads((config / 'config.json').read_text(encoding='utf-8')).get('doc_kinds')
        check('config.json 에도 (HWP 는 파일이 없어 숨었어도 켜진 채)', saved == ['ppt', 'excel', 'hwp', 'tasks'], saved)
        check('사이드바: 할 일이 생기고 Word 는 사라진다', until(page, lambda: [x.split(':')[0] for x in kinds()] == ['all', 'ppt', 'excel', 'tasks']), kinds())
        page.keyboard.press('Escape')
        pick_kind('all')
        page.keyboard.press('Control+Comma')
        title_box = page.locator('#lec-settings input[data-key="show_titles"]')
        check("'목록에 문서 제목 보이기' 는 꺼져 있다", not title_box.is_checked())
        title_box.click()
        check('켜면 사이드바가 제목으로', until(page, lambda: any('2026년 사업 보고서' in x for x in rows())), rows())
        check("사이드바 '제목' 단추도 켜짐", page.evaluate("() => document.querySelector('#lec-btn-titles').classList.contains('on')"))
        title_box.click()
        check('끄면 다시 파일 이름', until(page, lambda: any(x.endswith('보고서.md') for x in rows()) and not any('2026년' in x for x in rows())), rows())
        page.keyboard.press('Escape')

        print('[머리줄 우클릭]')
        page.click('#lec-docs .kind-head[data-kind="all"]', button='right')
        menu = until(page, lambda: page.evaluate(MENU))
        check('우클릭 메뉴에 고를 수 있는 것 일곱', all(any(n in m for m in menu) for n in ('Word', 'PowerPoint', 'Excel·CSV', '한글(HWP)', '업무', '형광펜', '할 일')), menu)
        page.locator('#lec-menu').get_by_text('형광펜').click()
        check('형광펜을 켜면 생긴다', until(page, lambda: any(k.startswith('marks:') for k in kinds())), kinds())
        page.click('#lec-docs .kind-head[data-kind="all"]', button='right')
        page.locator('#lec-menu').get_by_text('업무').click()
        check('업무를 켜면 생긴다', until(page, lambda: any(k.startswith('work:') for k in kinds())), kinds())
        pick_kind('tasks')
        check('할 일 묶음이 그대로 돈다', until(page, lambda: any('표 고치기' in x for x in rows())), rows())
        page.click('#lec-docs .kind-head[data-kind="tasks"]', button='right')
        page.locator('#lec-menu').get_by_text('할 일').click()
        check('펼친 묶음을 끄면 전체로', until(page, lambda: not any(k.startswith('tasks:') for k in kinds()) and page.locator('#lec-docs .kind-head.open').get_attribute('data-kind') == 'all'), kinds())

        print('[폴더 개요·담기의 문서 고르기 — 파일 이름]')
        page.click('#lec-tree .row[data-dir="보고"]')
        expect(page, '폴더 개요의 문서는 파일 이름이 위, 제목은 아래', "() => { const b = document.querySelector('#lec-view .ov-files button'); return b && b.querySelector('.t').textContent.startsWith('초안.md') && b.querySelector('.fname')?.textContent === '초안 제목'; }",
               lambda: page.evaluate("() => document.querySelector('#lec-view .ov-files')?.innerText"))

        print('[다시 켜면 설정 그대로]')
        page.reload()
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        got = until(page, lambda: (k := kinds()) and any(x.startswith('ppt:') for k2 in [k] for x in k2) and k)
        check('다시 켜도 PowerPoint·Excel·CSV·업무·형광펜, Word 없음', [x.split(':')[0] for x in got] == ['all', 'ppt', 'excel', 'work', 'marks'], got)

        print('[영어 화면]')
        page2 = b.new_page(viewport={'width': 1200, 'height': 800})
        page2.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page2.goto(url)
        page2.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        page2.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ language: 'en' }))")
        page2.reload()
        page2.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        names = until(page2, "() => [...document.querySelectorAll('#lec-docs .kind-head span:nth-child(2)')].map((s) => s.textContent)")
        check('영어: All·PowerPoint·Excel·CSV·Work·Highlights', names and names[0] != '전체' and 'PowerPoint' in names and not any('업무' in n or '형광펜' in n for n in names), names)
        page2.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ language: 'ko' }))")
        page2.close()

        check('화면 스크립트 오류 없음', not errors, errors[:5])
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
