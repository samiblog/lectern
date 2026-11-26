"""사이드바 '폴더' 묶음의 모든 것과 복사·붙여 넣기 (D203), 묶음마다의 만들기.
- '폴더' 묶음만 숨긴 것을 모두: 점으로 시작하는 것, Windows 숨김 속성, 빈 폴더, 숨긴 것만 든 폴더, 바로가기 폴더(정션 — 따라가지 않음).
  숨긴 폴더·제외 폴더는 펼칠 때 안을 읽는다. 숨긴 파일은 보기만 (코드 화면, 편집은 막힘). 문서·코드·자료 목록과 검색에는 나오지 않는다.
- 복사·붙여 넣기는 '폴더' 묶음에서만: Ctrl+C → Windows 클립보드의 파일 목록(탐색기와 같은 모양), Ctrl+V → 고른 폴더에 복사,
  이름이 겹치면 '- 복사본', 탐색기에서 잘라내기 한 것도 복사만, 여럿 고르기(Ctrl·Shift+누르기), 폴더를 그 안으로는 안 됨, 우클릭·빈 곳.
  다른 묶음의 Ctrl+C·Ctrl+V 는 파일을 다루지 않는다.
- 만들기: 문서 묶음은 문서만, 코드는 코드만, 자료는 자료만, 폴더는 '폴더' 묶음에서만 (머리줄의 만들기·우클릭·Ctrl+N·프로젝트 탭)."""
import json
import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import ROOT, hold_clipboard, check, expect, fails, report, serve, stop, until

sys.path[:0] = [str(ROOT)]
from lectern import fileclip  # noqa: E402

if sys.platform != 'win32':
    print('Windows 에서만 (클립보드의 파일 목록·숨김 속성·정션)')
    report()
    raise SystemExit(0)
hold_clipboard()   # 클립보드를 쓰는 다른 묶음과 겹치지 않게

base = Path(tempfile.mkdtemp(prefix='lec-folderall-'))
proj = base / '사업'
(proj / '보고').mkdir(parents=True)
(proj / '자료').mkdir()
(proj / '빈 폴더').mkdir()
(proj / '숨김만').mkdir()
(proj / '.git').mkdir()
(proj / 'node_modules' / 'pkg').mkdir(parents=True)
(proj / '보고서.md').write_text('# 보고서\n\n글\n', encoding='utf-8', newline='\n')
(proj / '보고' / '초안.md').write_text('# 초안\n', encoding='utf-8', newline='\n')
(proj / '자료' / '표.csv').write_text('a,b\n1,2\n', encoding='utf-8')
(proj / 'calc.py').write_text('x = 1\n', encoding='utf-8')
(proj / '.env').write_text('KEY=secret-test\n', encoding='utf-8')
(proj / '.git' / 'HEAD').write_text('ref: refs/heads/master\n', encoding='utf-8')
(proj / '숨김만' / '.keep').write_text('', encoding='utf-8')
(proj / '감춘 메모.txt').write_text('감춘 글\n', encoding='utf-8')
subprocess.run(['attrib', '+h', str(proj / '감춘 메모.txt')], check=True)
(proj / 'node_modules' / 'pkg' / 'index.js').write_text('1\n', encoding='utf-8')
outside = base / '밖'
(outside / '받은 폴더').mkdir(parents=True)
(outside / '받은 폴더' / '안.txt').write_text('안\n', encoding='utf-8')
(outside / '계획서.docx').write_bytes(b'PK\x03\x04 docx')
(outside / '보고서.md').write_text('# 밖의 보고서\n', encoding='utf-8')
subprocess.run(['cmd', '/c', 'mklink', '/J', str(proj / '바로가기'), str(outside)], check=True, capture_output=True)
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False, 'files_open': 'folder'}), encoding='utf-8')

ROWS = "() => [...document.querySelectorAll('#lec-folder-list .row')].map((r) => r.dataset.path + (r.classList.contains('hidden') ? '~' : '') + (r.classList.contains('link') ? '@' : ''))"
VIEW = "() => import('/static/js/store.js').then(({ S }) => S.view && S.view.type + ':' + S.view.path)"
TOAST = "() => { const e = document.querySelector('#lec-toast'); return e && !e.hidden ? e.textContent : ''; }"
MENU = "() => [...document.querySelectorAll('#lec-menu button, #lec-menu .menu-item')].map((b) => b.textContent.trim())"


def clip_paths():
    paths, cut = fileclip.read()
    return [p.name for p in paths], cut


server, url, port = serve(proj, config)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1300, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-folder-list .row', state='attached', timeout=30000)

        def rows():
            return page.evaluate(ROWS)

        def row(path):
            return f'#lec-folder-list .row[data-path="{path}"]'

        def toast():
            return page.evaluate(TOAST)

        print("['폴더' 묶음 — 모든 것]")
        r = until(page, lambda: (x := rows()) and '.env~' in x and x)
        for want in ('.env~', '.git~', '감춘 메모.txt~', '빈 폴더', '숨김만', '바로가기@', 'node_modules', '보고서.md', 'calc.py', '자료'):
            check(f'보인다: {want}', want in (r or []), r)
        check('숨긴 것은 흐리게(hidden), 바로가기는 링크로', page.locator(row('.env')).get_attribute('class').count('hidden') == 1 and page.locator(row('바로가기')).get_attribute('class').count('link') == 1)
        page.click(f'{row("숨김만")} [data-toggle]')
        check('숨긴 것만 든 폴더를 펼치면 .keep', until(page, lambda: '숨김만/.keep~' in rows()), rows())
        page.click(f'{row(".git")} [data-toggle]')
        check('숨긴 폴더를 펼치면 안을 읽는다 (.git/HEAD — 숨김)', until(page, lambda: '.git/HEAD~' in rows()), rows())
        page.click(f'{row("빈 폴더")} [data-toggle]')
        expect(page, '빈 폴더를 펼치면 \'빈 폴더\'', "() => [...document.querySelectorAll('#lec-folder-list .side-note')].some((p) => p.textContent === '빈 폴더')")
        page.click(f'{row("node_modules")} [data-toggle]')
        check('제외 폴더도 펼치면 안을 읽는다', until(page, lambda: 'node_modules/pkg' in rows()), rows())
        page.click(row('바로가기'))
        page.dblclick(row('바로가기'))
        check('바로가기 폴더는 따라가지 않는다 (펼칠 수 없고, 두 번 누르면 알림)', until(page, lambda: '따라가지 않습니다' in toast()) and not any(x.startswith('바로가기/') for x in rows()), (toast(), rows()))

        print('[숨긴 파일 — 보기만]')
        page.click(row('.env'))
        check('숨긴 파일을 누르면 코드 화면에서 본다', until(page, lambda: page.evaluate(VIEW) == 'code:.env' and 'secret-test' in page.inner_text('#lec-view')), page.evaluate(VIEW))
        page.keyboard.press('Control+e')
        check('편집은 막힌다 (보기만)', until(page, lambda: '숨긴 파일은 보기만' in toast()), toast())
        check('편집 상자가 열리지 않는다', page.locator('#lec-view .CodeMirror, #lec-view .cm-editor').count() == 0)
        page.click(row('감춘 메모.txt'))
        check('숨김 속성 파일도 본다', until(page, lambda: '감춘 글' in page.inner_text('#lec-view')), page.inner_text('#lec-view')[:80])
        status = page.evaluate("(u) => fetch(u + 'doc/' + encodeURIComponent('x') + '/.env').then((r) => r.status)", url)
        tab_id = page.evaluate("() => import('/static/js/store.js').then(({ S }) => S.tab.id)")
        plain = page.evaluate("(u) => fetch(u).then((r) => r.status)", f'{url}doc/{tab_id}/.env')
        token = page.evaluate("(u) => fetch(u).then((r) => r.status)", f'{url}doc/{tab_id}/.env?hidden=1')
        check('숨긴 파일은 토큰 없는 주소로는 받지 못한다 (문서 속 그림·링크)', plain == 404 and token == 200, (plain, token))
        save = page.evaluate("""(id) => fetch('/api/save', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ p: id, path: '.env', text: 'X', hash: '' }) }).then((r) => r.status)""", tab_id)
        check('서버도 숨긴 파일은 저장하지 않는다', save in (403, 404), save)
        check('.env 는 그대로', (proj / '.env').read_text(encoding='utf-8') == 'KEY=secret-test\n')

        print('[다른 묶음에는 숨긴 것이 없다]')
        others = page.evaluate("() => import('/static/js/store.js').then(({ S }) => [...S.tab.others.index.files.keys(), ...S.tab.others.index.code.keys()])")
        check("코드·자료 목록에 .env·감춘 메모·.git 이 없다", not any(x.startswith('.') or '감춘' in x for x in others), others)
        page.keyboard.press('Control+Shift+f')
        page.keyboard.type('secret-test')
        page.wait_for_timeout(1200)
        check('검색에도 숨긴 파일은 없다', 'secret-test' not in page.inner_text('#lec-search-results') or '.env' not in page.inner_text('#lec-search-results'), page.inner_text('#lec-search-results')[:120])
        page.keyboard.press('Escape')
        page.click('.side-tabs button[data-tab="files"]')

        print('[복사 — Lectern → 탐색기]')
        page.click(row('보고서.md'))
        page.click(row('calc.py'), modifiers=['Control'])
        check('Ctrl+누르기로 여럿 고르기', until(page, lambda: page.locator('#lec-folder-list .row.picked').count() == 2), page.locator('#lec-folder-list .row.picked').count())
        page.focus(row('calc.py'))
        page.keyboard.press('Control+c')
        check('Ctrl+C — 클립보드에 두 파일 (탐색기 모양 — 복사)', until(page, lambda: sorted(clip_paths()[0]) == ['calc.py', '보고서.md'] and not clip_paths()[1]), clip_paths())
        check('알림', until(page, lambda: '2개를 복사했습니다' in toast()), toast())
        page.click(row('자료'))
        check('그냥 누르면 하나로', page.locator('#lec-folder-list .row.picked').count() == 0)

        print('[붙여 넣기 — 탐색기 → Lectern]')
        fileclip.put([outside / '받은 폴더', outside / '계획서.docx', outside / '보고서.md'])
        page.focus(row('자료'))
        page.keyboard.press('Control+v')
        check('Ctrl+V — 고른 폴더(자료) 안에', until(page, lambda: (proj / '자료' / '계획서.docx').exists() and (proj / '자료' / '받은 폴더' / '안.txt').exists() and (proj / '자료' / '보고서.md').exists(), ms=15000),
              sorted(x.name for x in (proj / '자료').iterdir()))
        check('알림 — 3개', until(page, lambda: '3개를 붙여 넣었습니다' in toast()), toast())
        check('목록에 나타난다', until(page, lambda: '자료/계획서.docx' in rows() and '자료/받은 폴더' in rows(), ms=10000), rows())
        check('새 md 문서는 문서 트리에도', until(page, lambda: page.evaluate("() => import('/static/js/store.js').then(({ S }) => S.fileMap.has('자료/보고서.md'))"), ms=10000))
        fileclip.put([outside / '보고서.md'])
        page.click(row('보고서.md'))
        page.keyboard.press('Control+v')
        check("이름이 겹치면 '- 복사본' (덮어쓰지 않음)", until(page, lambda: (proj / '보고서 - 복사본.md').exists(), ms=15000) and (proj / '보고서.md').read_text(encoding='utf-8') == '# 보고서\n\n글\n',
              sorted(x.name for x in proj.iterdir()))
        fileclip.put([proj / '보고'])
        page.click(f'{row("보고")} [data-toggle]')
        page.wait_for_timeout(300)
        page.click(row('보고/초안.md'))
        page.keyboard.press('Control+v')
        check('폴더를 그 안으로는 붙이지 않는다', until(page, lambda: '그 폴더 안으로' in toast()) and not (proj / '보고' / '보고').exists(), toast())

        print('[잘라내기는 복사만]')
        cut_src = outside / '잘라낸.txt'
        cut_src.write_text('원본\n', encoding='utf-8')
        page.evaluate('() => 0')
        import ctypes  # noqa: E402
        fileclip.put([cut_src])
        user, kernel, _ = fileclip._win()   # 'Preferred DropEffect' 를 옮기기(2)로 — 탐색기의 잘라내기와 같게
        fmt = user.RegisterClipboardFormatW('Preferred DropEffect')
        hwnd = user.CreateWindowExW(0, 'STATIC', None, 0, 0, 0, 0, 0, fileclip.HWND_MESSAGE, None, None, None)
        fileclip._open(user, hwnd)
        h = fileclip._global(kernel, (2).to_bytes(4, 'little'))
        user.SetClipboardData(fmt, h)
        user.CloseClipboard()
        user.DestroyWindow(hwnd)
        check('준비: 클립보드가 잘라내기', clip_paths() == (['잘라낸.txt'], True), clip_paths())
        page.click(row('calc.py'))
        page.keyboard.press('Control+v')
        check('잘라낸 것도 복사만 — 원본은 남는다', until(page, lambda: (proj / '잘라낸.txt').exists(), ms=15000) and cut_src.exists(), (cut_src.exists(), (proj / '잘라낸.txt').exists()))
        check('알림 — 옮기지 않음', until(page, lambda: '복사만 했습니다' in toast()), toast())

        print('[우클릭 · 빈 곳]')
        page.click(row('calc.py'), button='right')
        menu = until(page, lambda: page.evaluate(MENU))
        check("파일 우클릭에 '복사'·'붙여 넣기'", any(m.startswith('복사') for m in menu) and any(m.startswith('붙여 넣기') for m in menu), menu)
        page.keyboard.press('Escape')
        page.click(row('자료'), button='right')
        menu = until(page, lambda: page.evaluate(MENU))
        check("폴더 우클릭: 새로 만들기·새 폴더·복사·붙여 넣기", all(any(m.startswith(w) for m in menu) for w in ('새로 만들기', '새 폴더 만들기', '복사', '붙여 넣기')), menu)
        page.keyboard.press('Escape')
        fileclip.put([outside / '계획서.docx'])
        page.dispatch_event('#lec-folder-list', 'contextmenu', {'clientX': 60, 'clientY': 300, 'bubbles': True, 'cancelable': True})
        menu = until(page, lambda: page.evaluate(MENU))
        check('빈 곳 우클릭: 붙여 넣기(맨 위)·새로 만들기·새 폴더', all(any(m.startswith(w) for m in menu) for w in ('붙여 넣기', '새로 만들기', '새 폴더 만들기')), menu)
        page.locator('#lec-menu').get_by_text('붙여 넣기').first.click()
        check('맨 위에 붙는다', until(page, lambda: (proj / '계획서.docx').exists(), ms=15000))

        print('[다른 묶음에서는 파일 복사·붙여 넣기가 없다]')
        fileclip.put([outside / '계획서.docx'])
        before = sorted(x.name for x in (proj / '보고').iterdir())
        page.click('#lec-docs-head')
        page.click('#lec-tree .row[data-dir="보고"]')
        page.focus('#lec-tree .row[data-dir="보고"]')
        page.keyboard.press('Control+v')
        page.keyboard.press('Control+c')
        page.wait_for_timeout(800)
        check('문서 묶음의 Ctrl+V 는 붙이지 않는다', sorted(x.name for x in (proj / '보고').iterdir()) == before)
        check('문서 묶음의 Ctrl+C 는 파일을 클립보드에 놓지 않는다', clip_paths()[0] == ['계획서.docx'], clip_paths())
        page.click('#lec-tree .row[data-dir="보고"]', button='right')
        menu = until(page, lambda: page.evaluate(MENU))
        check("문서 묶음 우클릭: 새 문서는 있고 새 폴더·붙여 넣기는 없다", any('새 문서 만들기' in m for m in menu) and not any('새 폴더' in m or m.startswith('붙여 넣기') for m in menu), menu)
        page.keyboard.press('Escape')

        print('[만들기 — 묶음마다 그 종류만]')
        def kinds_of_dialog():
            page.wait_for_selector('#lec-newdoc:not([hidden])', timeout=5000)
            got = page.evaluate("() => [...document.querySelectorAll('#lec-newdoc [data-kind]')].filter((b) => !b.hidden && b.offsetParent).map((b) => b.dataset.kind)")
            mk = page.locator('#lec-newdoc-mkdir').is_visible()
            page.keyboard.press('Escape')
            page.wait_for_timeout(200)
            return got, mk
        page.click('#lec-docs-new')
        check('문서 묶음의 만들기: md·슬라이드만, 창 안의 새 폴더 없음', kinds_of_dialog() == (['md', 'deck'], False))
        page.click('#lec-code-head')
        page.click('#lec-code-new')
        check('코드 묶음의 만들기: 코드만', kinds_of_dialog() == (['code'], False))
        page.click('#lec-others-head')
        page.click('#lec-others-new')
        check('자료 묶음의 만들기: 자료만', kinds_of_dialog() == (['data'], False))
        page.click('#lec-folder-head')
        page.click('#lec-folder-new')
        check("'폴더' 묶음의 만들기: 모두와 폴더, 창 안의 새 폴더도", kinds_of_dialog() == (['md', 'deck', 'code', 'data', 'folder'], True))
        page.click('#lec-content')
        page.keyboard.press('Control+n')
        got = kinds_of_dialog()
        check('Ctrl+N: 폴더는 없다', 'folder' not in got[0] and not got[1], got)
        page.click('.lec-tab.active', button='right')
        menu = until(page, lambda: page.evaluate(MENU))
        check('프로젝트 탭 우클릭: 새 폴더 없음', not any('새 폴더' in m for m in menu), menu)
        page.keyboard.press('Escape')

        check('화면 스크립트 오류 없음', not errors, errors[:5])
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
