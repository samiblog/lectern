"""문서 편집 (0.67): 전체 편집 없이 쓰기 — 문서 삭제, 새 문서, 이어 쓰기, 줄 종류, 넣기, 표, 주, 펼치기."""
import json
import sys
import tempfile
import traceback
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop

base = Path(tempfile.mkdtemp(prefix='lec-docedit-'))
proj = base / 'proj'
(proj / 'sub').mkdir(parents=True)
(proj / '지울.md').write_text('# 지울 문서\n\n글\n', encoding='utf-8')
(proj / '남길.md').write_text('# 남길 문서\n\n[지울](지울.md)\n', encoding='utf-8')
(proj / '한탭.md').write_text('# 한 탭 문서\n', encoding='utf-8')
(proj / 'sub' / '안쪽.md').write_text('# 안쪽\n', encoding='utf-8')
(proj / 'code.py').write_text('print(1)\n', encoding='utf-8')
(proj / 'data.csv').write_text('a,b\n1,2\n', encoding='utf-8')

server, url, port = serve(proj, base / 'config')
extra = []


def post(path, data):
    req = urllib.request.Request(url + path.lstrip('/'), data=json.dumps(data).encode(), headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1280, 'height': 820})
        page.on('pageerror', lambda e: extra.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        toast = lambda: page.text_content('#lec-toast') or ''
        tabs = lambda: page.locator('#lec-doctabs .doc-tab').count()
        tid = page.evaluate("fetch('/api/state').then((r) => r.json()).then((s) => s.tabs?.[0]?.id ?? s.projects?.[0]?.id ?? '')")

        def menu_of(selector):
            page.locator(selector).first.click(button='right')
            page.wait_for_selector('#lec-menu button', timeout=3000)
            labels = page.locator('#lec-menu button').all_inner_texts()
            return labels

        def open_doc(name):
            page.locator(f'#lec-tree .row.file[data-doc="{name}"]').click()
            page.wait_for_function("(n) => document.querySelector('#lec-st-path')?.textContent.includes(n)", arg=name, timeout=8000)
            page.wait_for_timeout(400)

        print('[문서 삭제]')
        labels = menu_of('#lec-tree .row.file[data-doc="지울.md"]')
        check('문서의 우클릭에 문서 삭제', any('문서 삭제' in x for x in labels), labels)
        page.keyboard.press('Escape')
        labels = menu_of('#lec-code-list .row, #lec-others [data-path="code.py"], .row[data-path="code.py"]')
        check('코드의 우클릭에는 없음', not any('삭제' in x for x in labels), labels)
        page.keyboard.press('Escape')
        labels = menu_of('.row[data-path="data.csv"]')
        check('자료의 우클릭에는 없음', not any('삭제' in x for x in labels), labels)
        page.keyboard.press('Escape')

        open_doc('지울.md')
        open_doc('남길.md')
        before = tabs()
        page.locator('#lec-tree .row.file[data-doc="지울.md"]').click(button='right')
        page.locator('#lec-menu button', has_text='문서 삭제').click()
        page.wait_for_selector('#lec-delete:not([hidden])', timeout=3000)
        check('늘 묻는다, 초점은 그만두기', page.evaluate("document.activeElement?.id") == 'lec-delete-no')
        page.keyboard.press('Enter')
        page.wait_for_timeout(300)
        check('Enter 는 그만두기', (proj / '지울.md').exists() and page.locator('#lec-delete').is_hidden())
        page.locator('#lec-tree .row.file[data-doc="지울.md"]').click(button='right')
        page.locator('#lec-menu button', has_text='문서 삭제').click()
        page.wait_for_selector('#lec-delete:not([hidden])', timeout=3000)
        page.keyboard.press('Escape')
        page.wait_for_timeout(200)
        check('Esc 도 그만두기', (proj / '지울.md').exists() and page.locator('#lec-delete').is_hidden())

        page.locator('#lec-tree .row.file[data-doc="지울.md"]').click(button='right')
        page.locator('#lec-menu button', has_text='문서 삭제').click()
        page.click('#lec-delete-yes')
        page.wait_for_function("!document.querySelector('#lec-tree .row.file[data-doc=\"지울.md\"]')", timeout=8000)
        check('휴지통으로 간다', not (proj / '지울.md').exists() and (base / 'config' / 'test-trash' / '지울.md').exists())
        check('그 문서의 탭이 닫힌다', tabs() == before - 1, (before, tabs()))
        check('알림', '휴지통으로 보냈습니다' in toast(), toast())

        # 하나뿐인 탭: 그 문서를 지우면 폴더 개요로
        open_doc('한탭.md')
        while tabs() > 1:
            page.locator('#lec-doctabs .doc-tab:not(.active)').first.click(button='middle')
            page.wait_for_timeout(200)
        page.locator('#lec-tree .row.file[data-doc="한탭.md"]').click(button='right')
        page.locator('#lec-menu button', has_text='문서 삭제').click()
        page.click('#lec-delete-yes')
        page.wait_for_function("!document.querySelector('#lec-tree .row.file[data-doc=\"한탭.md\"]')", timeout=8000)
        page.wait_for_timeout(400)
        check('하나뿐인 탭은 개요로', '폴더' in page.inner_text('#lec-view') and '한탭' not in page.inner_text('#lec-st-path'), page.inner_text('#lec-view')[:80])

        print('[새 문서]')
        page.click('#lec-docs-new')
        page.wait_for_selector('#lec-newdoc:not([hidden])', timeout=4000)
        check('만들기 버튼으로 창이 열린다', page.input_value('#lec-newdoc-title') == '새 문서')
        check('제목을 골라 두고 초점을 둔다', page.evaluate("document.activeElement?.id === 'lec-newdoc-title' && document.activeElement.selectionEnd === 4"))
        check('처음 스타일은 번호 없음', '번호 없음' in page.inner_text('#lec-newdoc-list li.sel'), page.inner_text('#lec-newdoc-list li.sel'))
        page.keyboard.type('첫 보고서')
        page.keyboard.press('Enter')
        page.wait_for_selector('#lec-view .lec-line-edit', timeout=8000)
        made = proj / '첫 보고서.md'
        check('제목이 파일 이름이 된다', made.read_text(encoding='utf-8') == '# 첫 보고서\n\n', made.exists() and made.read_text(encoding='utf-8'))
        check('편집기가 아니라 md 문서 화면', page.locator('.lec-pane.active .lec-editor').count() == 0 and page.locator('#lec-view h1').count() == 1)
        check('제목 아래 새 줄에서 바로 쓴다', page.evaluate("document.activeElement?.classList.contains('lec-line-edit')"))
        page.keyboard.type('첫 문단')
        page.keyboard.press('Enter')
        page.wait_for_timeout(600)
        check('쓴 글이 저장된다', '첫 문단' in made.read_text(encoding='utf-8'), made.read_text(encoding='utf-8'))
        page.keyboard.press('Escape')
        page.wait_for_timeout(200)

        page.keyboard.press('Control+n')
        page.wait_for_selector('#lec-newdoc:not([hidden])', timeout=4000)
        page.fill('#lec-newdoc-title', '개조식 보고')
        page.locator('#lec-newdoc-list li', has_text='보고서형').first.click()
        page.wait_for_timeout(100)
        check('미리보기에 번호 모양', 'Ⅰ. 첫째 절' in page.inner_text('#lec-newdoc-preview'), page.inner_text('#lec-newdoc-preview'))
        check('누른 뒤에도 초점은 제목', page.evaluate("document.activeElement?.id") == 'lec-newdoc-title')
        page.click('#lec-newdoc-go')
        page.wait_for_selector('#lec-view .lec-line-edit', timeout=8000)
        made2 = proj / '개조식 보고.md'
        check('번호 스타일은 보기 머리글을 넣는다', made2.read_text(encoding='utf-8').split('\n')[:5] == ['# 개조식 보고', '', '## Ⅰ. 첫째 절', '', '### 1. 세부 절'], made2.read_text(encoding='utf-8'))
        page.keyboard.press('Escape')
        page.wait_for_timeout(200)

        page.keyboard.press('Control+n')
        page.wait_for_selector('#lec-newdoc:not([hidden])', timeout=4000)
        check('최근 스타일이 처음 값', '보고서형' in page.inner_text('#lec-newdoc-list li.sel'), page.inner_text('#lec-newdoc-list li.sel'))
        check('최근 쓴 것 묶음', '최근 쓴 것' in page.inner_text('#lec-newdoc-list'))
        page.fill('#lec-newdoc-title', 'a/b:c?')
        page.keyboard.press('Enter')
        page.wait_for_selector('#lec-view .lec-line-edit', timeout=8000)
        check('쓸 수 없는 글자는 파일 이름에서 뺀다', (proj / 'a b c.md').exists() and (proj / 'a b c.md').read_text(encoding='utf-8').startswith('# a/b:c?'), [x.name for x in proj.iterdir()])
        page.keyboard.press('Escape')
        page.wait_for_timeout(200)

        page.locator('#lec-tree .row[data-dir="sub"]').click(button='right')
        page.locator('#lec-menu button', has_text='새 문서 만들기').click()
        page.wait_for_selector('#lec-newdoc:not([hidden])', timeout=4000)
        check('폴더 우클릭은 그 폴더에', page.text_content('#lec-newdoc-where') == '위치: sub/', page.text_content('#lec-newdoc-where'))
        page.keyboard.press('Escape')
        page.wait_for_timeout(150)
        check('Esc 로 닫는다', page.locator('#lec-newdoc').is_hidden())
        page.locator('#lec-tree .row.file[data-doc="sub/안쪽.md"]').click(button='right')
        page.locator('#lec-menu button', has_text='새 문서 만들기').click()
        page.wait_for_selector('#lec-newdoc:not([hidden])', timeout=4000)
        check('문서 우클릭은 그 문서의 폴더에', page.text_content('#lec-newdoc-where') == '위치: sub/')
        page.fill('#lec-newdoc-title', '   ')
        page.keyboard.press('Enter')
        page.wait_for_timeout(200)
        check('빈 제목은 만들지 않는다', '제목을 쓰세요' in page.inner_text('#lec-newdoc-msg'), page.inner_text('#lec-newdoc'))
        page.click('#lec-newdoc-no')
        page.wait_for_timeout(100)

        page.keyboard.press('Control+n')
        page.wait_for_selector('#lec-newdoc:not([hidden])', timeout=4000)
        page.fill('#lec-newdoc-title', '슬라이드')
        page.click('#lec-newdoc-deck')
        check('Lectern 슬라이드면 스타일 칸을 감춘다', page.locator('#lec-newdoc-styles').is_hidden())
        page.click('#lec-newdoc-go')
        page.wait_for_selector('#lec-gallery-list .lec-tpl', timeout=6000)
        page.keyboard.press('Enter')
        page.wait_for_selector('#lec-view.lec-deck', timeout=8000)
        check('슬라이드는 템플릿으로 시작', (proj / '슬라이드.md').read_text(encoding='utf-8').startswith('---\nmarp: true'))

        for rel, want in (('code.py', 400), ('data.csv', 400), ('없는.md', 404), ('../밖.md', 400)):
            got = post('/api/delete-doc', {'p': tid, 'path': rel})
            check(f'서버가 막는다: {rel}', got == want, got)
        check('코드와 자료는 그대로', (proj / 'code.py').exists() and (proj / 'data.csv').exists())
        b.close()
    check('페이지 오류 없음', not extra, extra)
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
