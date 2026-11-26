"""구역별 만들기 (D177·D203): 사이드바 묶음마다 그 종류만 — '문서'는 md 문서·슬라이드, '코드'는 코드 파일, '자료'는 자료 파일,
'폴더'는 모두(폴더도), Ctrl+N 은 폴더를 뺀 넷. 코드·자료 파일은 빈 파일(CSV 는 BOM·머리행)을 만들어 편집 모드로 열고, 폴더는 만든 뒤 그 안에 만들 것을 정한다.
같은 이름은 덮어쓰지 않고, 받지 않는 확장자는 창이 알린다"""
import json
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop

base = Path(tempfile.mkdtemp(prefix='lec-newfiles-'))
proj = base / 'proj'
(proj / 'src').mkdir(parents=True)
(proj / 'data').mkdir()
(proj / 'README.md').write_text('# 프로젝트\n\n본문.\n', encoding='utf-8')
(proj / 'src' / 'a.js').write_bytes(b'let a = 1;\n')
(proj / 'src' / 'b.js').write_text('let b = 2;\n', encoding='utf-8')
(proj / 'src' / 'c.py').write_text('c = 3\n', encoding='utf-8')
(proj / 'data' / '원래.csv').write_bytes('원래,내용\r\n'.encode('utf-8'))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)

VALUE = "() => document.querySelector('.CodeMirror')?.CodeMirror.getValue() ?? null"
KINDS = "() => [...document.querySelectorAll('#lec-newdoc .mdstyle-kinds button')].filter((b) => !b.hidden).map((b) => b.dataset.kind)"
ON = "() => document.querySelector('#lec-newdoc .mdstyle-kinds button.on')?.dataset.kind"
SHOWN = "(sel) => { const el = document.querySelector(sel); return !!el && !el.hidden && getComputedStyle(el).display !== 'none' && el.getBoundingClientRect().width > 0; }"


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
        page = b.new_page(viewport={'width': 1300, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.on('dialog', lambda d: d.accept())
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        shown = lambda sel: page.evaluate(SHOWN, sel)  # noqa: E731
        is_open = lambda: not page.evaluate("document.querySelector('#lec-newdoc').hidden")  # noqa: E731
        msg = lambda: page.evaluate("() => { const m = document.querySelector('#lec-newdoc-msg'); return m.hidden ? '' : m.textContent; }")  # noqa: E731

        def section(name):
            page.click(f'#lec-{name}-head')
            page.wait_for_function("(n) => !document.querySelector(`#lec-${n}`).classList.contains('closed')", arg=name)

        def close_editor():
            page.keyboard.press('Escape')
            page.wait_for_selector('.CodeMirror', state='detached', timeout=8000)

        print('[묶음마다 만들기 단추 — 펼친 묶음에만]')
        check("'문서'를 펼치면 그 머리줄에만 만들기", shown('#lec-docs-new') and not shown('#lec-code-new') and not shown('#lec-others-new'))
        page.click('#lec-docs-new')
        page.wait_for_selector('#lec-newdoc:not([hidden])')
        check("'문서'의 만들기 — md 문서·슬라이드 (폴더는 '폴더' 묶음에서만), 처음은 md 문서", page.evaluate(KINDS) == ['md', 'deck'] and page.evaluate(ON) == 'md',
              (page.evaluate(KINDS), page.evaluate(ON)))
        check('— 이름 칸은 제목, 스타일 목록이 보인다', page.inner_text('#lec-newdoc-title-label') == '제목' and shown('#lec-newdoc-styles'))
        page.keyboard.press('Escape')

        print("['코드' — 코드 파일·폴더, 처음 확장자는 프로젝트에 가장 많은 것]")
        section('code')
        check("'코드'를 펼치면 '코드' 머리줄에 만들기, '문서'의 것은 숨는다", shown('#lec-code-new') and not shown('#lec-docs-new'))
        page.click('#lec-code-new')
        page.wait_for_selector('#lec-newdoc:not([hidden])')
        check('코드 파일만, 처음은 코드 파일', page.evaluate(KINDS) == ['code'] and page.evaluate(ON) == 'code', page.evaluate(KINDS))
        check('— 이름의 처음 값은 .js (js 둘·py 하나), 확장자 앞까지 골라 둔다', page.input_value('#lec-newdoc-title') == '새 파일.js'
              and page.evaluate("() => { const el = document.activeElement; return el.id === 'lec-newdoc-title' && el.selectionStart === 0 && el.selectionEnd === 4; }"),
              page.input_value('#lec-newdoc-title'))
        check('— 이름 칸은 이름, 스타일 목록 없음, 확장자 안내', page.inner_text('#lec-newdoc-title-label') == '이름' and not shown('#lec-newdoc-styles')
              and '.py' in page.inner_text('#lec-newdoc-hint'))
        page.keyboard.type('정리')
        page.keyboard.press('Enter')
        page.wait_for_selector('.CodeMirror', timeout=15000)
        check('만들기 — 빈 파일, 새 탭의 편집 모드로', raw('정리.js') == b'' and page.evaluate(VALUE) == '', (raw('정리.js'), page.evaluate(VALUE)))
        close_editor()

        print('[목록에서 고른 폴더에]')
        page.locator('#lec-code-list .row', has_text='src').first.click()
        page.click('#lec-code-new')
        page.wait_for_selector('#lec-newdoc:not([hidden])')
        check("고른 폴더 'src' 가 위치", page.input_value('#lec-newdoc-folder') == 'src', page.input_value('#lec-newdoc-folder'))
        page.fill('#lec-newdoc-title', 'a.js')
        page.keyboard.press('Enter')
        expect(page, '같은 이름 — 창이 알리고 원래 파일은 그대로', lambda: '같은 이름' in msg() and is_open() and raw('src/a.js') == 'let a = 1;\n'.encode('utf-8'), msg)
        page.fill('#lec-newdoc-title', 'tool')
        page.keyboard.press('Enter')
        page.wait_for_selector('.CodeMirror', timeout=15000)
        check('확장자를 빼먹으면 처음 값의 것으로 (src/tool.js)', raw('src/tool.js') == b'', sorted(x.name for x in (proj / 'src').iterdir()))
        close_editor()
        page.click('#lec-code-new')
        page.wait_for_selector('#lec-newdoc:not([hidden])')
        page.fill('#lec-newdoc-title', '보고.md')
        page.keyboard.press('Enter')
        expect(page, '코드 파일이 아닌 확장자 — 창이 알리고 만들지 않는다', lambda: '확장자' in msg() and is_open(), msg)
        check('— 만들지 않았다', not (proj / 'src' / '보고.md').exists() and not (proj / '보고.md').exists())
        page.keyboard.press('Escape')

        print("['자료' — 자료 파일·폴더, CSV 는 BOM 과 머리행]")
        section('others')
        page.click('#lec-others-new')
        page.wait_for_selector('#lec-newdoc:not([hidden])')
        check('자료 파일만, 처음은 새 자료.csv, 머리행 칸이 보인다', page.evaluate(KINDS) == ['data'] and page.input_value('#lec-newdoc-title') == '새 자료.csv'
              and shown('#lec-newdoc-header-row'), (page.evaluate(KINDS), page.input_value('#lec-newdoc-title')))
        page.fill('#lec-newdoc-title', '메모.txt')
        check('— .txt 면 머리행 칸이 숨는다', not shown('#lec-newdoc-header-row'))
        page.fill('#lec-newdoc-title', '판매.csv')
        page.fill('#lec-newdoc-header', '날짜, 품목, 금액')
        page.keyboard.press('Enter')
        page.wait_for_selector('.CodeMirror', timeout=15000)
        want = b'\xef\xbb\xbf' + '날짜,품목,금액\r\n'.encode('utf-8')
        check('CSV — UTF-8 BOM 과 머리행 한 줄 (CRLF), 편집 모드로', raw('판매.csv') == want and page.evaluate(VALUE) == '날짜,품목,금액\n', (raw('판매.csv'), page.evaluate(VALUE)))
        cm = page.locator('.CodeMirror')
        page.evaluate("() => { const cm = document.querySelector('.CodeMirror').CodeMirror; cm.setCursor(cm.lineCount() - 1, 0); }")
        page.keyboard.type('2026-11-19,구리,100')
        page.keyboard.press('Control+s')
        expect(page, '— 고쳐 저장해도 BOM 과 CRLF 가 남는다', lambda: raw('판매.csv') == b'\xef\xbb\xbf' + '날짜,품목,금액\r\n2026-11-19,구리,100'.encode('utf-8'),
               lambda: raw('판매.csv'))
        close_editor()
        page.click('#lec-others-new')
        page.wait_for_selector('#lec-newdoc:not([hidden])')
        page.fill('#lec-newdoc-title', 'x.py')
        page.keyboard.press('Enter')
        expect(page, '자료가 아닌 확장자 — 창이 알린다', lambda: '.csv' in msg() and is_open(), msg)
        check('— 만들지 않았다', not (proj / 'x.py').exists())
        page.fill('#lec-newdoc-title', '원래.csv')
        page.select_option('#lec-newdoc-folder', 'data')
        check('위치를 바꾸면 그 폴더에 없는 이름으로', page.input_value('#lec-newdoc-title') == '새 자료.csv', page.input_value('#lec-newdoc-title'))
        page.fill('#lec-newdoc-title', '원래.csv')
        page.keyboard.press('Enter')
        expect(page, '같은 이름 — 덮어쓰지 않는다', lambda: '같은 이름' in msg() and raw('data/원래.csv') == '원래,내용\r\n'.encode('utf-8'), msg)
        page.keyboard.press('Escape')

        print("[폴더 — '폴더' 묶음에서만, 만든 뒤 그 안에 만들 것을 정한다]")
        section('folder')
        page.click('#lec-folder-new')
        page.wait_for_selector('#lec-newdoc:not([hidden])')
        page.click('#lec-newdoc-dir')
        check('폴더 종류 — 이름 처음 값 새 폴더, 창 속 새 폴더 단추는 숨는다', page.input_value('#lec-newdoc-title') == '새 폴더' and not shown('#lec-newdoc-mkdir')
              and page.inner_text('#lec-newdoc-head') == '새 폴더 만들기', page.input_value('#lec-newdoc-title'))
        page.fill('#lec-newdoc-title', '2026 자료')
        page.keyboard.press('Enter')
        expect(page, '폴더를 만들고 창은 남아 — md 문서 종류로, 위치는 새 폴더', lambda: (proj / '2026 자료').is_dir() and is_open() and page.evaluate(ON) == 'md'
               and page.input_value('#lec-newdoc-folder') == '2026 자료' and '그 안에' in msg(),
               lambda: (page.evaluate(ON), page.input_value('#lec-newdoc-folder'), msg()))
        page.click('#lec-newdoc-data')
        expect(page, '— 자료 파일로 바꾸면 새 자료.csv', lambda: page.input_value('#lec-newdoc-title') == '새 자료.csv', lambda: page.input_value('#lec-newdoc-title'))
        page.keyboard.press('Enter')
        page.wait_for_selector('.CodeMirror', timeout=15000)
        check('— 이어서 그 폴더에 새 자료.csv (머리행 없으면 BOM 만)', raw('2026 자료/새 자료.csv') == b'\xef\xbb\xbf', raw('2026 자료/새 자료.csv'))
        close_editor()

        print("['폴더' 묶음·Ctrl+N — 모두, 종류를 바꿔도 쓴 이름은 이어서]")
        section('folder')
        page.click('#lec-folder-new')
        page.wait_for_selector('#lec-newdoc:not([hidden])')
        check("'폴더'의 만들기 — 다섯 종류 모두", page.evaluate(KINDS) == ['md', 'deck', 'code', 'data', 'folder'], page.evaluate(KINDS))
        page.keyboard.press('Escape')
        section('docs')
        page.locator('#lec-view').click()
        page.keyboard.press('Control+n')
        page.wait_for_selector('#lec-newdoc:not([hidden])')
        check('Ctrl+N — 폴더를 뺀 넷, 처음은 md 문서', page.evaluate(KINDS) == ['md', 'deck', 'code', 'data'] and page.evaluate(ON) == 'md', page.evaluate(KINDS))
        page.fill('#lec-newdoc-title', '분석 메모')
        page.click('#lec-newdoc-code')
        check('md 문서 → 코드 파일: 쓴 이름에 확장자만', page.input_value('#lec-newdoc-title') == '분석 메모.js', page.input_value('#lec-newdoc-title'))
        page.click('#lec-newdoc-data')
        check('코드 → 자료: 확장자를 자료의 것으로', page.input_value('#lec-newdoc-title') == '분석 메모.csv', page.input_value('#lec-newdoc-title'))
        page.click('#lec-newdoc-md')
        check('자료 → md 문서: 확장자를 뗀다, 스타일 목록이 돌아온다', page.input_value('#lec-newdoc-title') == '분석 메모' and shown('#lec-newdoc-styles'),
              page.input_value('#lec-newdoc-title'))
        page.keyboard.press('Escape')

        print('[우클릭·명령 찾기]')
        section('code')
        page.locator('#lec-code-list .row', has_text='src').first.click(button='right')
        check("'코드' 목록의 폴더 우클릭 — 새 코드 파일 만들기…", page.locator('.ctx-menu, #lec-menu').get_by_text('새 코드 파일 만들기…').count() >= 1)
        page.keyboard.press('Escape')
        page.keyboard.press('Control+Shift+P')
        page.keyboard.type('새 자료 파일')
        page.wait_for_timeout(200)
        page.keyboard.press('Enter')
        page.wait_for_selector('#lec-newdoc:not([hidden])')
        check('명령 찾기 — 새 자료 파일 만들기… 는 자료 파일 종류로 연다', page.evaluate(ON) == 'data', page.evaluate(ON))
        page.keyboard.press('Escape')

        check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
