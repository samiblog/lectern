"""md 문서 점검 (D190): 상태줄의 '점검 N곳'과 목록 — 묶음(깨진 틀·보고서의 틀·글버릇), 고르면 그 줄로, '고치기'(저장 — Ctrl+Z 로 되돌림),
목차의 표시, 없는 그림, 설정(글버릇 켜기·점검 끄기), 점검할 곳이 없는 문서·Lectern 슬라이드·업무 카드, 명령 찾기의 '문서 점검'.
계산은 rules_check 의 lint_cases.js 가 넓게 본다 — 여기는 화면의 길."""
import json
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

DOC = ('# 점검 문서\n\n## 가 절\n\n글 하나  \n둘째 줄\n\n- 가\n- 나\n* 다\n\n| a | b |\n|---|---|\n| 1 |\n\n> [!NOTES]\n> 강조글\n\n'
       '## 나 절\n\n설명 글\n2. 둘째\n\n![없는 그림](없는.png)\n\n## 다 절\n\n```js\nx = 1\n')
CLEAN = '# 깨끗한 문서\n\n## 하나\n\n글\n\n## 둘\n\n- 가\n- 나\n'
DECK = '---\nmarp: true\n---\n\n# 표지\n\n## 장\n\n## 장\n'
WORK = '---\nstatus: 진행\n---\n\n# 업무\n\n## 할 일\n\n## 일정\n'

base = Path(tempfile.mkdtemp(prefix='lec-doclint-'))
proj = base / 'proj'
proj.mkdir(parents=True)
doc = proj / '점검.md'
doc.write_text(DOC, encoding='utf-8')
(proj / '깨끗.md').write_text(CLEAN, encoding='utf-8')
(proj / '발표.md').write_text(DECK, encoding='utf-8')
(proj / '일' ).mkdir()
(proj / '일' / 'WORK.md').write_text(WORK, encoding='utf-8')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False, 'toc_visible': True}), encoding='utf-8')
server, url, port = serve(proj, config)

LINE = lambda text: next(i + 1 for i, s in enumerate(DOC.split('\n')) if s == text)
BTN = '#lec-st-lint'


def body():
    for _ in range(40):
        try:
            return doc.read_text(encoding='utf-8')
        except OSError:   # 앱이 파일을 바꿔 끼우는 순간 (ReplaceFileW)
            time.sleep(0.02)
    return doc.read_text(encoding='utf-8')


try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_context(viewport={'width': 1300, 'height': 900}, locale='ko-KR').new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')
        label = lambda: page.evaluate(f"(() => {{ const b = document.querySelector('{BTN}'); return b.hidden ? null : b.textContent.trim(); }})()")
        here = lambda: page.evaluate("import('/static/js/store.js').then((m) => m.S.pane?.here?.line ?? null)")
        menu_rows = lambda: page.evaluate("[...document.querySelectorAll('#lec-menu .menu-head, #lec-menu button[data-i]')].map((e) => (e.classList.contains('menu-head') ? '# ' : '') + e.textContent.trim())")

        def open_doc(name, title):
            page.locator(f'#lec-tree .row.file[data-doc="{name}"]').click()
            page.wait_for_selector(f'#lec-view h1:has-text("{title}")')
            page.wait_for_timeout(400)

        def open_list():
            page.locator(BTN).click()
            page.wait_for_selector('#lec-menu:not([hidden]) .menu-head', timeout=3000)

        def set_config(values):
            page.evaluate("(v) => import('/static/js/api.js').then((m) => m.saveConfig(v)).then(() => import('/static/js/store.js')).then((m) => m.emit('doc-check'))", values)

        print('[점검할 곳이 있는 문서]')
        open_doc('점검.md', '점검 문서')
        expect(page, "상태줄에 '점검 6곳' (글머리표·칸 수·강조글 종류·문단에 붙은 번호·없는 그림·닫지 않은 코드 블록)", lambda: label() == '점검 6곳', label)
        open_list()
        rows = menu_rows()
        check('목록은 묶음 머리말 아래에 줄 차례로', rows[0] == '# 깨진 틀' and [r.split('행')[0] for r in rows[1:7]] == [str(n) for n in sorted([LINE('* 다'), LINE('| 1 |'), LINE('> [!NOTES]'), LINE('2. 둘째'), LINE('![없는 그림](없는.png)'), LINE('```js')])], rows)
        check('— 없는 그림도', any('그림 파일이 없습니다: 없는.png' in r for r in rows), rows)
        check('— 고칠 수 있는 곳에만 고치기 단추', page.locator('#lec-menu .menu-side').count() == 4, page.locator('#lec-menu .menu-side').count())
        check('— 목록을 터미널에 붙여 넣기·목록 복사', any('목록을 터미널에 붙여 넣기' in r for r in rows) and any('목록 복사' in r for r in rows), rows)
        page.locator('#lec-menu button[data-i]', has_text='강조글 종류').click()
        expect(page, '고르면 그 줄이 현재 줄', lambda: here() == LINE('> [!NOTES]'), here)
        warned = page.evaluate("[...document.querySelectorAll('#lec-toc .toc-list li.warn')].map((li) => li.textContent.trim())")
        check('목차에 점검할 곳이 든 절의 표시', warned == ['가 절', '나 절', '다 절'], warned)

        print('[고치기와 되돌리기]')
        open_list()
        page.locator('#lec-menu .menu-row', has_text='강조글 종류').locator('.menu-side').click()
        expect(page, '고치기 — [!NOTES] 를 [!NOTE] 로 저장', lambda: '> [!NOTE]\n> 강조글' in body(), lambda: body()[:300])
        expect(page, "— 점검이 하나 줄어 '점검 5곳'", lambda: label() == '점검 5곳', label)
        page.locator('#lec-view h2', has_text='가 절').click()
        page.keyboard.press('Control+z')
        expect(page, '— Ctrl+Z 로 되돌림', lambda: '> [!NOTES]' in body(), lambda: body()[:300])
        expect(page, "— 다시 '점검 6곳'", lambda: label() == '점검 6곳', label)
        open_list()
        page.locator('#lec-menu .menu-row', has_text='닫지 않은 코드 블록').locator('.menu-side').click()
        expect(page, '닫지 않은 코드 블록 — 문서 끝에 닫는 줄', lambda: body().endswith('```js\nx = 1\n```\n'), lambda: body()[-60:])
        open_list()
        page.locator('#lec-menu .menu-row', has_text='번호가 2.').locator('.menu-side').click()
        expect(page, '문단에 붙은 2. — 윗줄과 띄운다 (번호 그대로)', lambda: '설명 글\n\n2. 둘째' in body(), lambda: body()[:400])
        expect(page, '— 화면에서도 번호 목록', lambda: page.locator('#lec-view ol[start="2"] li', has_text='둘째').count() == 1)

        print('[설정]')
        set_config({'doc_check_style': True})
        expect(page, '글버릇을 켜면 줄 끝 공백 두 칸도 (점검 5곳)', lambda: label() == '점검 5곳', label)
        open_list()
        check("— '글버릇' 묶음", '# 글버릇' in menu_rows(), menu_rows())
        page.keyboard.press('Escape')
        set_config({'doc_check_style': False, 'doc_check': False})
        expect(page, '문서 점검을 끄면 상태줄에 없다', lambda: label() is None, label)
        check('— 목차의 표시도 없다', page.locator('#lec-toc .toc-list li.warn').count() == 0)
        set_config({'doc_check': True})
        expect(page, '— 다시 켜면 나온다', lambda: label() == '점검 4곳', label)

        print('[점검할 곳이 없는 문서·슬라이드·업무 카드]')
        open_doc('깨끗.md', '깨끗한 문서')
        expect(page, '점검할 곳이 없으면 상태줄에 없다', lambda: label() is None, label)
        open_doc('발표.md', '표지')
        expect(page, 'Lectern 슬라이드는 문서 점검을 하지 않는다 (슬라이드 점검이 따로)', lambda: label() is None, label)
        page.locator('#lec-tree .row.dir', has_text='일').first.click()
        page.locator('#lec-tree .row.file[data-doc="일/WORK.md"]').click()
        page.wait_for_selector('#lec-view h1:has-text("업무")')
        page.wait_for_timeout(400)
        expect(page, '업무 카드(WORK.md)의 빈 절은 점검하지 않는다', lambda: label() is None, label)

        print('[명령 찾기]')
        open_doc('점검.md', '점검 문서')
        until(page, lambda: label() is not None, 4000)
        page.keyboard.press('Control+Shift+P')
        page.keyboard.type('문서 점검')
        page.wait_for_timeout(300)
        page.keyboard.press('Enter')
        expect(page, "명령 찾기의 '문서 점검' 이 목록을 연다", lambda: page.locator('#lec-menu:not([hidden]) .menu-head', has_text='깨진 틀').count() == 1)
        page.keyboard.press('Escape')

        check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
