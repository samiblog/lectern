"""0.106·0.107 사람 시나리오 1 — 받은 자료를 정리하는 하루 (D202·D203).
연구원이 메일로 받은 자료(워드·엑셀·csv·pptx·hwp, 맥에서 온 .DS_Store 와 숨긴 폴더 포함)를 탐색기에서 복사해 프로젝트에 붙이고,
'문서'의 오피스 묶음에서 찾아보고, 표를 보고, 이름을 바꾸고, 다시 받은 것을 또 붙이고('- 복사본'), 쓰지 않는 묶음은 끄고,
보고서 md 를 다른 폴더로 복사해 두고, 프로젝트 둘 사이에 붙이고, 원본이 사라진 클립보드를 붙이고, 같은 키를 연달아 누르고,
'폴더' 묶음에서 숨긴 것을 거르기로 찾고, 300개 든 폴더를 붙인다. 걸음마다: 원래 파일은 바뀌지 않고, 화면 오류가 없다."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import ROOT, hold_clipboard, check, expect, fails, report, serve, stop, until

sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from lectern import fileclip  # noqa: E402
from test_sheet import make_xlsx  # noqa: E402

if sys.platform != 'win32':
    print('Windows 에서만')
    report()
    raise SystemExit(0)
hold_clipboard()   # 클립보드를 쓰는 다른 묶음과 겹치지 않게

base = Path(tempfile.mkdtemp(prefix='lec-scen107-'))
proj = base / '구리 시장 조사'
(proj / '보고').mkdir(parents=True)
(proj / '받은 자료').mkdir()
(proj / '보고' / '중간 보고서.md').write_text('# 2026년 구리 시장 중간 보고서\n\n- [ ] 표 3 고치기\n\n<mark>재고가 줄었다</mark>\n', encoding='utf-8', newline='\n')
(proj / '보고' / '목차.md').write_text('# 목차\n', encoding='utf-8', newline='\n')
(proj / 'WORK.md').write_text('# 업무\n\n상태: 진행\n', encoding='utf-8', newline='\n')
mail = base / '메일 첨부'
(mail / '.hidden-mac').mkdir(parents=True)
(mail / '.DS_Store').write_bytes(b'\x00\x00\x00\x01Bud1')
(mail / '.hidden-mac' / 'x').write_text('x', encoding='utf-8')
(mail / '계약서 초안.docx').write_bytes(b'PK\x03\x04 docx')
(mail / '발표 자료.pptx').write_bytes(b'PK\x03\x04 pptx')
(mail / '공문.hwp').write_bytes(b'\xd0\xcf\x11\xe0 hwp')
(mail / 'LME 가격.csv').write_text('월,가격\n1월,9100\n2월,9350\n', encoding='utf-8')
make_xlsx(mail / '재고 현황.xlsx', sheets=[('재고', '<row r="1"><c r="A1" t="s"><v>0</v></c></row><row r="2"><c r="A2"><v>420</v></c></row>', None)], shared=('톤',))
big = base / '큰 묶음'
big.mkdir()
for i in range(300):
    (big / f'자료{i:03d}.txt').write_text(f'{i}\n', encoding='utf-8')
other = base / '다른 과제'
other.mkdir()
(other / '메모.md').write_text('# 다른 과제\n', encoding='utf-8', newline='\n')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'version': 4, 'doc_kinds': ['word', 'ppt', 'excel', 'hwp'], 'work_alerts': False}), encoding='utf-8')


def digest(folder):
    return {p.relative_to(folder).as_posix(): hashlib.md5(p.read_bytes()).hexdigest() for p in sorted(folder.rglob('*')) if p.is_file()}


ORIGINAL = {'mail': digest(mail), 'proj': digest(proj)}
KINDS = "() => [...document.querySelectorAll('#lec-docs .kind-head')].map((b) => b.dataset.kind + ':' + b.querySelector('.n').textContent)"
TREE = "() => [...document.querySelectorAll('#lec-tree .row')].map((r) => (r.dataset.file || r.dataset.doc || r.dataset.dir || ''))"
FOLDER = "() => [...document.querySelectorAll('#lec-folder-list .row')].map((r) => r.dataset.path)"
VIEW = "() => import('/static/js/store.js').then(({ S }) => S.view && S.view.type + ':' + S.view.path)"
TOAST = "() => { const e = document.querySelector('#lec-toast'); return e && !e.hidden ? e.textContent : ''; }"

server, url, port = serve(proj, config)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1360, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)

        def kinds():
            return page.evaluate(KINDS)

        def kind_n(k):
            return next((x.split(':')[1] for x in kinds() if x.startswith(k + ':')), None)

        def section(name):
            page.click(f'#lec-{name}-head')
            page.wait_for_timeout(150)

        def frow(path):
            return f'#lec-folder-list .row[data-path="{path}"]'

        def toast():
            return page.evaluate(TOAST)

        def no_errors(step):
            check(f'{step} — 화면 오류 없음', not errors, errors[:3])

        print('[아침 — 처음 연 프로젝트]')
        got = until(page, lambda: kinds())
        check('오피스 파일이 아직 없으니 오피스 묶음도, 업무·형광펜·할 일도 없다 (하위 묶음 줄 없음)', got == [], got)
        check('목록은 파일 이름 — 중간 보고서.md', until(page, lambda: '보고/중간 보고서.md' in page.evaluate(TREE) or '보고' in page.evaluate(TREE)))

        print('[메일 첨부를 탐색기에서 복사 → 받은 자료 폴더에 붙여 넣기]')
        fileclip.put(sorted(mail.iterdir()))
        section('folder')
        page.click(frow('받은 자료'))
        page.keyboard.press('Control+v')
        check('일곱 개가 붙는다 (숨긴 .DS_Store·.hidden-mac 도 그대로)', until(page, lambda: len(list((proj / '받은 자료').iterdir())) == 7, ms=15000), sorted(x.name for x in (proj / '받은 자료').iterdir()))
        check('알림 — 7개', until(page, lambda: '7개를 붙여 넣었습니다' in toast()), toast())
        page.click(f'{frow("받은 자료")} [data-toggle]') if page.locator(frow('받은 자료/공문.hwp')).count() == 0 else None
        check("'폴더' 묶음: 붙인 것이 보이고 .DS_Store 는 흐리게", until(page, lambda: page.locator(frow('받은 자료/.DS_Store')).count() == 1 and 'hidden' in (page.locator(frow('받은 자료/.DS_Store')).get_attribute('class') or ''), ms=10000), page.evaluate(FOLDER))
        no_errors('붙여 넣기')

        print("['문서' 의 오피스 묶음으로 찾아보기]")
        section('docs')
        got = until(page, lambda: (k := kinds()) and any(x.startswith('excel:') for x in k) and k, ms=10000)
        check('Word 1 · PowerPoint 1 · Excel·CSV 2 · HWP 1 (숨긴 것은 세지 않는다)', got and [x for x in got if not x.startswith('all')] == ['word:1', 'ppt:1', 'excel:2', 'hwp:1'], got)
        page.click('#lec-docs .kind-head[data-kind="excel"]')
        page.click('#lec-tree .row[data-file="받은 자료/LME 가격.csv"]')
        check('csv 를 누르면 표로 — 9350', until(page, lambda: page.evaluate(VIEW) == 'code:받은 자료/LME 가격.csv' and '9350' in page.inner_text('#lec-view')), page.evaluate(VIEW))
        page.click('#lec-tree .row[data-file="받은 자료/재고 현황.xlsx"]')
        check('xlsx 를 누르면 엑셀 보기 — 420', until(page, lambda: '420' in page.inner_text('#lec-view')), page.inner_text('#lec-view')[:80])
        page.click('#lec-docs .kind-head[data-kind="word"]')
        page.focus('#lec-tree .row[data-file="받은 자료/계약서 초안.docx"]')
        page.keyboard.press('F2')
        page.wait_for_selector('#lec-rename:not([hidden])', timeout=5000)
        page.fill('#lec-rename-input', '계약서 1차.docx')
        page.keyboard.press('Enter')
        check('Word 묶음에서 F2 로 이름 바꾸기', until(page, lambda: (proj / '받은 자료' / '계약서 1차.docx').exists(), ms=8000))
        check('Word 묶음이 새 이름으로', until(page, lambda: '받은 자료/계약서 1차.docx' in page.evaluate(TREE), ms=8000), page.evaluate(TREE))
        no_errors('오피스 묶음')

        print('[오후 — 고친 자료를 다시 받아 붙임 (- 복사본)]')
        fileclip.put([mail / '계약서 초안.docx', mail / 'LME 가격.csv'])
        section('folder')
        page.click(frow('받은 자료/공문.hwp'))
        page.keyboard.press('Control+v')
        check("겹친 csv 는 'LME 가격 - 복사본.csv', 이름을 바꾼 docx 는 원래 이름으로", until(page, lambda: (proj / '받은 자료' / 'LME 가격 - 복사본.csv').exists() and (proj / '받은 자료' / '계약서 초안.docx').exists(), ms=15000),
              sorted(x.name for x in (proj / '받은 자료').iterdir()))
        check('먼저 붙인 csv 는 그대로', (proj / '받은 자료' / 'LME 가격.csv').read_bytes() == (mail / 'LME 가격.csv').read_bytes())
        section('docs')
        check('Excel·CSV 3 · Word 2 로 따라온다', until(page, lambda: kind_n('excel') == '3' and kind_n('word') == '2', ms=10000), kinds())

        print("[쓰지 않는 묶음은 끄고, 할 일은 '작업' 묶음에서]")
        page.click('#lec-docs .kind-head[data-kind="all"]', button='right')
        page.locator('#lec-menu').get_by_text('한글(HWP)').click()
        check('HWP 는 사라진다', until(page, lambda: not kind_n('hwp')), kinds())
        section('work')
        page.click('#lec-work .kind-head[data-kind="tasks"]')
        check('할 일 — 표 3 고치기', until(page, lambda: '표 3 고치기' in page.inner_text('#lec-work-list')), page.inner_text('#lec-work-list')[:100])
        section('others')
        check("HWP 를 꺼도 '자료' 목록에는 공문.hwp", until(page, lambda: page.evaluate("() => import('/static/js/store.js').then(({ S }) => S.tab.others.index.files.has('받은 자료/공문.hwp'))")))
        check("'자료' 목록에 .DS_Store 는 없다", not page.evaluate("() => import('/static/js/store.js').then(({ S }) => [...S.tab.others.index.files.keys()].some((p) => p.includes('.DS_Store')))"))

        print('[보고서를 복사해 둔다 — 폴더째, 여럿 고르기]')
        section('folder')
        page.click(f'{frow("보고")} [data-toggle]') if page.locator(frow('보고/목차.md')).count() == 0 else None
        page.click(frow('보고/목차.md'))
        page.click(frow('보고/중간 보고서.md'), modifiers=['Shift'])
        check('Shift+누르기로 둘', until(page, lambda: page.locator('#lec-folder-list .row.picked').count() == 2))
        page.keyboard.press('Control+c')
        check('클립보드에 두 md', until(page, lambda: sorted(x.name for x in fileclip.read()[0]) == ['목차.md', '중간 보고서.md']), fileclip.read())
        page.click('#lec-folder-head')
        page.click('#lec-folder-new')
        page.wait_for_selector('#lec-newdoc:not([hidden])', timeout=5000)
        check("만들기의 처음 위치는 고른 파일의 폴더 '보고'", page.input_value('#lec-newdoc-folder') == '보고', page.input_value('#lec-newdoc-folder'))
        page.click('#lec-newdoc [data-kind="folder"]')
        page.select_option('#lec-newdoc-folder', '')   # 프로젝트 맨 위에
        page.fill('#lec-newdoc-title', '백업')
        page.keyboard.press('Enter')
        check("'폴더' 묶음의 만들기로 새 폴더 '백업'", until(page, lambda: (proj / '백업').is_dir(), ms=8000))
        page.keyboard.press('Escape')
        check('빈 폴더 백업이 보인다', until(page, lambda: '백업' in page.evaluate(FOLDER), ms=10000), page.evaluate(FOLDER))
        page.click(frow('백업'))
        page.keyboard.press('Control+v')
        check('백업에 두 md', until(page, lambda: (proj / '백업' / '중간 보고서.md').exists() and (proj / '백업' / '목차.md').exists(), ms=15000))
        section('docs')
        page.click('#lec-docs .kind-head[data-kind="all"]')
        check('문서 트리에도 백업/중간 보고서.md', until(page, lambda: page.evaluate("() => import('/static/js/store.js').then(({ S }) => S.fileMap.has('백업/중간 보고서.md'))"), ms=10000))
        page.click('#lec-btn-titles')
        check("'제목' 을 켜면 트리에 제목", until(page, lambda: '2026년 구리 시장 중간 보고서' in page.inner_text('#lec-tree')), page.inner_text('#lec-tree')[:200])
        page.click('#lec-btn-titles')
        check('끄면 다시 파일 이름', until(page, lambda: '2026년 구리' not in page.inner_text('#lec-tree')))
        no_errors('보고서 복사')

        print('[다른 프로젝트로 복사해 가기]')
        fileclip.put([proj / '받은 자료' / 'LME 가격.csv'])
        page.evaluate("(dir) => import('/static/js/tabs.js').then((m) => m.openFolder(dir))", str(other))
        until(page, lambda: page.evaluate("() => import('/static/js/store.js').then((m) => m.S.tab?.name)") == '다른 과제', 15000)
        page.wait_for_timeout(800)
        section('folder')
        page.wait_for_selector('#lec-folder-list .row', timeout=10000)
        page.click('#lec-folder-list .row[data-path="메모.md"]')
        page.keyboard.press('Control+v')
        check('다른 프로젝트 맨 위에 csv', until(page, lambda: (other / 'LME 가격.csv').exists(), ms=15000))
        section('docs')
        check('그 프로젝트에도 Excel·CSV 묶음이 생긴다', until(page, lambda: kind_n('excel') == '1', ms=10000), kinds())
        page.evaluate("() => import('/static/js/tabs.js').then((m) => m.selectTabAt(1))")
        page.wait_for_timeout(600)

        print('[엇갈림 — 원본이 사라진 클립보드, 연달아 누르기]')
        gone = base / '곧 지울 파일.txt'
        gone.write_text('x', encoding='utf-8')
        fileclip.put([gone])
        gone.unlink()
        section('folder')
        page.click(frow('받은 자료'))
        page.keyboard.press('Control+v')
        check('원본이 없어진 클립보드는 까닭을 알리고 아무것도 만들지 않는다', until(page, lambda: '붙여 넣을 수 있는 파일이 없습니다' in toast()), toast())
        fileclip.put([mail / '발표 자료.pptx'])
        before = len(list((proj / '받은 자료').glob('발표 자료*.pptx')))
        page.focus(frow('받은 자료'))
        page.keyboard.press('Control+v')
        page.keyboard.press('Control+v')
        check('Ctrl+V 를 연달아 두 번 — 둘 다 새 이름으로 (덮어쓰지 않음)', until(page, lambda: len(list((proj / '받은 자료').glob('발표 자료*.pptx'))) == before + 2, ms=20000),
              sorted(x.name for x in (proj / '받은 자료').glob('발표 자료*')))
        no_errors('엇갈림')

        print("['폴더' 묶음의 거르기로 숨긴 것 찾기]")
        page.fill('#lec-filter', 'DS_Store')
        check('거르기 칸에 DS_Store — 숨긴 파일도 찾는다', until(page, lambda: '받은 자료/.DS_Store' in page.evaluate(FOLDER)), page.evaluate(FOLDER))
        page.fill('#lec-filter', '')
        page.click(frow('받은 자료/.DS_Store')) if page.locator(frow('받은 자료/.DS_Store')).count() else None
        page.wait_for_timeout(300)
        check('글이 아닌 숨긴 파일(.DS_Store)은 누르면 글이 아니라고 알리거나 열지 않는다 — 오류 없이', not errors, errors[:2])

        print('[300개 든 폴더를 붙인다]')
        fileclip.put([big])
        page.click(frow('받은 자료'))
        t0 = time.monotonic()
        page.keyboard.press('Control+v')
        ok = until(page, lambda: (proj / '받은 자료' / '큰 묶음').is_dir() and len(list((proj / '받은 자료' / '큰 묶음').iterdir())) == 300, ms=60000)
        check(f'300개가 모두 붙는다 ({time.monotonic() - t0:.1f}초)', ok)
        page.click(f'{frow("받은 자료/큰 묶음")} [data-toggle]') if until(page, lambda: page.locator(frow('받은 자료/큰 묶음')).count() == 1, ms=10000) else None
        check('펼치면 300개', until(page, lambda: sum(1 for x in page.evaluate(FOLDER) if x.startswith('받은 자료/큰 묶음/')) == 300, ms=10000))

        print('[끝 — 원래 것은 그대로]')
        check('메일 첨부(원본)는 하나도 바뀌지 않았다', digest(mail) == ORIGINAL['mail'])
        now = digest(proj)
        changed = [k for k, v in ORIGINAL['proj'].items() if now.get(k) != v]
        check('프로젝트에 원래 있던 파일은 하나도 바뀌지 않았다', not changed, changed)
        no_errors('하루')
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
