"""0.104.0 — 실제 창(WebView2)에서: 담기함 (D197) — Alt+C 로 담고, 새 담기함, 문서 탭에 펼쳐 보기, 제목·메모, 원래 문서가 바뀐 것, 앱을 다시 켜도 남는지,
'Claude 에 맡기기' 가 실제 셸에 (Enter 없이).
  python tools/real/real104.py [--exe <Lectern.exe>]   (없으면 소스의 app.py)"""
import json
import shutil
import subprocess
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

import realwin as R

base = Path(tempfile.mkdtemp(prefix='lec-real104-'))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'language': 'ko', 'work_alerts': False}), encoding='utf-8')
proj = base / '연구'
proj.mkdir()
DOC = '# 가격\n\n머리 문단입니다.\n\n표 1. 구리 분기별 가격\n\n| 분기 | 가격 |\n|---|---:|\n| 1Q | 9,210 |\n| 2Q | 9,480 |\n\n자료: LME\n\n끝 문단입니다.\n'
(proj / '가격.md').write_text(DOC, encoding='utf-8', newline='\n')
CLIPS = proj / '.lectern' / 'clips'

TABS = "() => [...document.querySelectorAll('#lec-doctab-list .doc-tab')].map((e) => e.querySelector('.name').textContent + (e.classList.contains('active') ? '*' : ''))"
CARDS = "() => [...document.querySelectorAll('#lec-view .cb-card')].map((e) => ({ title: e.querySelector('.cb-name').value, memo: e.querySelector('.cb-memo').value, table: e.querySelectorAll('.pv-body table').length, state: e.querySelector('.cb-state').hidden ? '' : e.querySelector('.cb-state').textContent }))"
TEXT = """(n) => import('/static/js/store.js').then((m) => { const term = (m.S.tab.terms || []).find((x) => x.n === n); if (!term?.xterm) return '';
  const b = term.xterm.buffer.active; const out = []; for (let i = 0; i < b.length; i++) out.push(b.getLine(i).translateToString(true)); return out.join(''); })"""


def src(name='담기함.md'):
    for _ in range(30):
        try:
            return (CLIPS / name).read_text(encoding='utf-8')
        except OSError:
            time.sleep(0.03)
    return ''


def connect(p, cdp):
    b = None
    for _ in range(120):
        try:
            b = p.chromium.connect_over_cdp(f'http://127.0.0.1:{cdp}')
            break
        except Exception:   # noqa: BLE001
            time.sleep(0.5)
    page = R.wait(lambda: R.app_page(b), 60)
    page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=40000)
    page.wait_for_timeout(1500)
    return b, page


proc = None
try:
    with sync_playwright() as p:
        proc, cdp = R.launch(proj, config)
        R.CONN.update(pw=p, cdp=cdp)
        b, page = connect(p, cdp)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.on('dialog', lambda d: d.accept())

        print('[담기 — Alt+C]')
        R.check('문서를 연다', R.open_doc(page, '가격.md'))
        R.check('담기 전에는 파일이 없다', not (proj / '.lectern').exists())
        page.locator('#lec-view td', has_text='9,480').click()
        page.keyboard.press('Alt+c')
        R.wait(lambda: '| 2Q | 9,480 |' in src(), 10)
        R.check('표를 캡션·자료째 담는다 — 파일이 생긴다', '표 1. 구리 분기별 가격' in src() and '자료: LME' in src(), src()[:300])
        page.locator('#lec-view p', has_text='머리 문단').click()
        page.keyboard.press('Alt+c')
        R.wait(lambda: src().count('/lectern-clip') == 2, 10)
        R.check('문단도', src().count('/lectern-clip') == 2)
        R.check('메뉴가 열리지 않는다 (Alt 의 창 메뉴)', page.evaluate("() => document.querySelector('#lec-menu').hidden"))

        print('[펼쳐 보기 — 제목·메모]')
        page.click('.side-tabs button[data-tab="basket"]')
        page.locator('.bk-box').first.click()
        page.wait_for_selector('#lec-view.clips-view .cb-card', timeout=15000)
        R.wait(lambda: [c['table'] for c in page.evaluate(CARDS)] == [1, 0], 10)
        R.check('문서 탭에 실제 모습으로', page.evaluate(TABS) == ['가격.md', '담기함*'] and [c['table'] for c in page.evaluate(CARDS)] == [1, 0], (page.evaluate(TABS), page.evaluate(CARDS)))
        page.locator('#lec-view .cb-name').first.click()
        page.keyboard.type('재고가 줄었다')
        page.keyboard.press('Enter')
        page.keyboard.type('시점이 겹침')
        R.wait(lambda: '## 재고가 줄었다\n시점이 겹침\n' in src(), 10)
        R.check('쓰는 대로 저장된다', '## 재고가 줄었다\n시점이 겹침\n' in src(), src()[:400])
        page.keyboard.press('Escape')
        time.sleep(0.3)
        (proj / '가격.md').write_text(DOC.replace('9,480', '9,999'), encoding='utf-8', newline='\n')
        R.wait(lambda: page.evaluate(CARDS)[0]['state'] != '', 20)
        R.check('원래 문서가 바뀌면 그 조각에만 알린다', [c['state'] for c in page.evaluate(CARDS)] == ['원래 문서가 바뀌었습니다', ''], page.evaluate(CARDS))

        print('[새 담기함 · 맡기기]')
        page.click('#lec-basket-new')
        page.keyboard.type('둘째 질문')
        page.keyboard.press('Enter')
        R.wait(lambda: (CLIPS / '둘째-질문.md').exists(), 10)
        R.check('새 담기함 — 파일 이름은 제목에서', (CLIPS / '둘째-질문.md').exists())
        page.locator('.bk-box', has_text='담기함').first.locator('.caret').click()
        R.wait(lambda: page.locator('.bk-item').count() == 2, 5)
        row = page.locator('.bk-item').first
        R.check('펼치면 조각이 한 줄씩 — ✎ 와 ⚠', page.locator('.bk-item').count() == 2 and [x.strip() for x in row.locator('.bk-mark').all_inner_texts()] == ['✎', '⚠'] and row.bounding_box()['height'] <= 30, row.inner_text())
        page.locator('.bk-box', has_text='담기함').first.click()
        page.wait_for_timeout(300)
        R.check('문서로 돌아가 Alt+Shift+C', R.open_doc(page, '가격.md'))
        page.locator('#lec-view p', has_text='끝 문단').click()
        page.keyboard.press('Alt+Shift+c')
        R.wait(lambda: page.locator('#lec-boxpick:not([hidden])').count() > 0, 5)
        page.keyboard.insert_text('둘째')
        page.wait_for_timeout(200)
        page.keyboard.press('Enter')
        R.wait(lambda: '끝 문단입니다' in src('둘째-질문.md'), 8)
        R.check('고른 담기함에 담긴다', '끝 문단입니다' in src('둘째-질문.md') and '끝 문단입니다' not in src(), src('둘째-질문.md'))
        page.locator('.bk-box', has_text='담기함').first.click()
        page.wait_for_selector('#lec-view.clips-view .cb-card', timeout=15000)
        page.click('#lec-view [data-act="ai"]')
        R.wait(lambda: page.locator('#lec-menu .menu-term').count() > 0, 5)
        page.locator('#lec-menu .menu-term').first.click()
        R.wait(lambda: '@.lectern/clips/담기함.md' in page.evaluate(TEXT, 0).replace(' ', ''), 60)
        got = page.evaluate(TEXT, 0)
        R.check('요청 글이 실제 셸에 — 담기함 파일까지, Enter 없이', '@.lectern/clips/담기함.md' in got.replace(' ', '') and got.count('PS ') == 1, got[-200:])
        R.check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], capture_output=True)
        time.sleep(2)

        print('[다시 켜기]')
        proc, cdp = R.launch(proj, config)
        R.CONN.update(pw=p, cdp=cdp)
        b, page = connect(p, cdp)
        page.click('.side-tabs button[data-tab="basket"]')
        R.wait(lambda: page.locator('.bk-box').count() == 2, 10)
        heads = page.evaluate("() => [...document.querySelectorAll('.bk-box')].map((e) => e.querySelector('.label').textContent + ' ' + e.querySelector('.n').textContent)")
        R.check('담기함 둘이 그대로', sorted(heads) == ['담기함 2', '둘째 질문 1'], heads)
        page.locator('.bk-box', has_text='담기함').first.click()
        page.wait_for_selector('#lec-view.clips-view .cb-card', timeout=15000)
        R.check('제목과 메모도', page.evaluate(CARDS)[0]['title'] == '재고가 줄었다' and page.evaluate(CARDS)[0]['memo'] == '시점이 겹침', page.evaluate(CARDS))
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    R.fails.append('예외')
finally:
    if proc:
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], capture_output=True)
    time.sleep(1)
    shutil.rmtree(base, ignore_errors=True)
print(f'\n{R.count}개 중 실패 {len(R.fails)}개', R.fails)
