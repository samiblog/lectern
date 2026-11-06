"""사이드바 목록의 차례 (D97): 폴더 먼저, 파일 다음 — 이름순·시간순·형식순, 문서·코드·자료·폴더 보기, 다시 켜도 그대로"""
import json
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop

base = Path(tempfile.mkdtemp(prefix='lec-side-'))
proj = base / 'proj'
(proj / '가폴더').mkdir(parents=True)
(proj / '나폴더').mkdir()
now = time.time()


def make(rel, age, text='# 글\n'):
    path = proj / rel
    path.write_text(text, encoding='utf-8')
    os.utime(path, (now - age, now - age))


make('다.md', 500)
make('가.md', 100)
make('나.html', 300, '<!doctype html><title>나</title><p>글</p>')
make('가폴더/안.md', 900)
make('나폴더/안.md', 50)
make('b.py', 700, 'print(1)\n')
make('a.js', 200, 'let a;\n')
make('z.css', 50, 'a{}\n')
make('b.csv', 100, 'a,b\n1,2\n')
make('a.txt', 800, '글\n')
make('c.png', 400, '')
config = base / 'config'
config.mkdir()
server, url, _ = serve(proj, config)
extra = []
DOCS = "[...document.querySelectorAll('#lec-tree > .row')].map((r) => r.dataset.doc || r.dataset.dir).filter((x) => !x.includes('/'))"
LIST = "(id) => [...document.querySelectorAll(id + ' .row')].map((r) => r.dataset.path).filter((x) => !x.includes('/'))"


def run():
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1300, 'height': 900})
        page.on('pageerror', lambda e: extra.append(str(e)[:200]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')
        page.wait_for_selector('#lec-code-list .row, #lec-others-list .row', timeout=8000)
        code = '#lec-code-list' if page.locator('#lec-code-list').count() else '#lec-others-code'
        docs = lambda: page.evaluate(DOCS)
        lst = lambda sel: page.evaluate(LIST, sel)

        def pick(name):
            page.locator('#lec-btn-sort').click()
            page.wait_for_timeout(100)
            page.locator('#lec-menu button', has_text=name).click()
            page.wait_for_timeout(300)

        check('처음은 이름순', docs() == ['가폴더', '나폴더', '가.md', '나.html', '다.md'], docs())
        check('이름순 버튼은 켜지지 않는다', 'on' not in (page.locator('#lec-btn-sort').get_attribute('class') or '').split())

        pick('시간순')
        check('시간순: 폴더는 안의 가장 새 파일로, 파일은 새것이 위로', docs() == ['나폴더', '가폴더', '가.md', '나.html', '다.md'], docs())
        check('코드 목록도 시간순', lst(code) == ['z.css', 'a.js', 'b.py'], lst(code))
        check('자료 목록도 시간순', lst('#lec-others-list') == ['b.csv', 'c.png', 'a.txt'], lst('#lec-others-list'))
        check('버튼에 표시', 'on' in (page.locator('#lec-btn-sort').get_attribute('class') or '').split())

        pick('형식순')
        check('형식순: 폴더는 이름순, 파일은 확장자 차례', docs() == ['가폴더', '나폴더', '나.html', '가.md', '다.md'], docs())
        check('코드 목록도 형식순', lst(code) == ['z.css', 'a.js', 'b.py'], lst(code))
        check('자료 목록도 형식순', lst('#lec-others-list') == ['b.csv', 'c.png', 'a.txt'], lst('#lec-others-list'))

        page.locator('#lec-btn-sort').click()
        page.wait_for_timeout(100)
        check('메뉴에 지금 고른 것이 표시된다', page.locator('#lec-menu button[aria-current="true"]').inner_text().strip() == '형식순')
        page.keyboard.press('Escape')

        pick('시간순')
        page.locator('#lec-btn-view').click()
        page.wait_for_timeout(500)
        folder = lst('#lec-others-list')
        check('폴더 보기도 폴더 먼저, 새것이 위로', folder[:2] == ['나폴더', '가폴더'] and folder[2] in ('z.css',) and folder.index('가.md') < folder.index('다.md') < folder.index('a.txt'), folder)
        page.locator('#lec-btn-view').click()
        page.wait_for_timeout(300)

        saved = json.loads((config / 'config.json').read_text(encoding='utf-8'))
        check('설정에 남는다', saved.get('side_sort') == 'time', saved.get('side_sort'))
        page.reload()
        page.wait_for_selector('#lec-tree .row.file')
        page.wait_for_timeout(500)
        check('다시 켜도 그대로', docs() == ['나폴더', '가폴더', '가.md', '나.html', '다.md'], docs())

        make('다.md', 1)
        page.wait_for_function(f"{DOCS}[2] === '다.md'", timeout=8000)
        check('고치면 위로 올라온다', True)
        pick('이름순')
        check('이름순으로 돌아온다', docs()[:2] == ['가폴더', '나폴더'] and docs()[-3:] == ['가.md', '나.html', '다.md'], docs())
        check('화면 오류 없음', not extra, extra[:3])
        b.close()


try:
    run()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
