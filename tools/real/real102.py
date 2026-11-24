"""0.102.0 — 실제 창(WebView2)에서: 탭 막대의 단추 열하나(D193) — 이름 없이 아이콘만, 마우스를 올리면 설명 풍선, 내보내기 메뉴의 '인쇄…' 가
실제 PDF 미리보기 창을 열고, '바뀜' 이 밖에서 고친 문서를 세고 연다. 터미널에 넣는 곳(D194) — 실제 셸 둘을 띄워 Shift+→ 와 AI 요청이
최근에 쓴 터미널로 가는지 (1번이 아니다).
  python tools/real/real102.py [--exe <Lectern.exe>]   (없으면 소스의 app.py)"""
import json
import shutil
import subprocess
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

import realwin as R

base = Path(tempfile.mkdtemp(prefix='lec-real102-'))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'language': 'ko', 'work_alerts': False}), encoding='utf-8')
proj = base / '연구'
proj.mkdir(parents=True)
(proj / '보고서.md').write_text('# 보고서\n\n## 요약\n\n첫 문단입니다.\n\n## 본론\n\n둘째 문단입니다.\n', encoding='utf-8', newline='\n')
(proj / '조사.md').write_text('# 조사\n\n조사한 내용입니다.\n', encoding='utf-8', newline='\n')

ORDER = ['lec-btn-overview', 'lec-btn-parts', 'lec-btn-changed', 'lec-btn-card', 'lec-btn-put', 'lec-btn-edit', 'lec-btn-toc', 'lec-btn-style', 'lec-btn-export',
         'lec-btn-ai', 'lec-btn-notes', 'lec-btn-term']
TIP = "() => { const b = document.querySelector('#lec-tabtip'); return b && !b.hidden ? b.querySelector('b').textContent : ''; }"
MENU = "() => { const m = document.querySelector('#lec-menu'); return m && !m.hidden ? [...m.querySelectorAll('button[data-i]')].map((e) => e.textContent.trim()) : null; }"
COUNT = "() => { const n = document.querySelector('#lec-btn-changed-n'); return n.hidden ? 0 : Number(n.textContent); }"
TEXT = """(n) => import('/static/js/store.js').then((m) => { const term = (m.S.tab.terms || []).find((x) => x.n === n); if (!term?.xterm) return '';
  const b = term.xterm.buffer.active; const out = []; for (let i = 0; i < b.length; i++) out.push(b.getLine(i).translateToString(true)); return out.join(''); })"""
VIEW = "() => import('/static/js/store.js').then((m) => m.S.view?.path || '')"
PICKED = "() => import('/static/js/store.js').then((m) => m.S.tab.term?.n ?? -1)"


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
        version = page.evaluate("() => document.querySelector('meta[name=lec-version]')?.content || ''")
        R.check(f'판 {R.VERSION}', version == R.VERSION or not version, version)
        text = lambda n: page.evaluate(TEXT, n)  # noqa: E731
        sent = lambda n: ''.join(text(n).split()).count('@보고서.md')  # noqa: E731
        menu = lambda: page.evaluate(MENU)  # noqa: E731

        print('[탭 막대 — 아이콘 단추 열하나와 설명 풍선 (D193)]')
        R.check('보고서를 연다', R.open_doc(page, '보고서.md'))
        order = page.evaluate("() => [...document.querySelectorAll('#lec-tabbar .tabbar-btn')].map((b) => b.id)")
        R.check('개요·바뀜·업무 카드 │ 넣기·편집·목차·스타일·내보내기 │ AI 요청·메모·터미널 (인쇄 단추는 없다)', order == ORDER, order)
        names = page.evaluate("() => [...document.querySelectorAll('#lec-tabbar .tabbar-btn > span:not(.n)')].filter((e) => getComputedStyle(e).display !== 'none').length")
        R.check('이름은 보이지 않는다', names == 0, names)
        page.hover('#lec-btn-export')
        R.wait(lambda: page.evaluate(TIP), 5)
        R.check("마우스를 올리면 단추 아래에 '내보내기'", page.evaluate(TIP) == '내보내기', page.evaluate(TIP))
        geo = page.evaluate("() => { const b = document.querySelector('#lec-btn-export').getBoundingClientRect(), t = document.querySelector('#lec-tabtip').getBoundingClientRect(); return t.top >= b.bottom && t.right <= innerWidth && t.left >= 0; }")
        R.check('— 단추 아래, 창 안에', geo)
        page.click('#lec-btn-export')
        R.wait(lambda: menu() is not None, 5)
        rows = menu() or []
        R.check('내보내기 메뉴: PDF로 저장 · 인쇄 · html로 저장 · Word로 저장', [r.split('…')[0] for r in rows] == ['PDF로 저장', '인쇄', 'html로 저장', 'Word로 저장'], rows)
        R.check('메뉴를 열면 설명 풍선은 걷힌다', page.evaluate(TIP) == '')
        page.locator('#lec-menu button[data-i]', has_text='인쇄…').click()
        R.wait(lambda: page.evaluate("() => !document.querySelector('#lec-print').hidden"), 10)
        R.check("'인쇄…' 는 내보내기 창을 인쇄가 처음 단추로", page.evaluate("() => !document.querySelector('#lec-print').hidden && document.querySelector('#lec-print-paper').classList.contains('primary')"))
        ok = R.wait(lambda: page.evaluate("() => document.querySelector('#lec-print-wait').hidden"), 40)
        R.check('— 실제 PDF 미리보기가 만들어진다', bool(ok))
        page.keyboard.press('Escape')
        R.wait(lambda: page.evaluate("() => document.querySelector('#lec-print').hidden"), 5)
        R.check('Esc 로 닫힌다', page.evaluate("() => document.querySelector('#lec-print').hidden"))

        print('[바뀜 — 밖에서 고친 문서]')
        R.check('처음에는 수가 없다', page.evaluate(COUNT) == 0, page.evaluate(COUNT))
        (proj / '조사.md').write_text('# 조사\n\n조사한 내용을 고쳤습니다.\n', encoding='utf-8', newline='\n')
        R.wait(lambda: page.evaluate(COUNT) == 1, 20)
        R.check('밖에서 고치면 수 1', page.evaluate(COUNT) == 1, page.evaluate(COUNT))
        page.click('#lec-btn-changed')
        R.wait(lambda: page.evaluate(VIEW) == '조사.md', 10)
        R.check('누르면 그 문서를 연다', page.evaluate(VIEW) == '조사.md', page.evaluate(VIEW))
        R.wait(lambda: page.evaluate(COUNT) == 0, 10)
        R.check('연 뒤에는 수가 사라진다', page.evaluate(COUNT) == 0, page.evaluate(COUNT))

        print('[터미널에 넣는 곳 — 최근에 쓴 터미널 (D194)]')
        R.check('보고서로 돌아간다', R.open_doc(page, '보고서.md'))
        page.click('#lec-btn-term')
        R.wait(lambda: 'PS ' in text(0), 40)
        R.check('1번 터미널의 셸이 뜬다', 'PS ' in text(0), text(0)[-80:])
        page.click('#lec-term-new')
        R.wait(lambda: 'PS ' in text(1), 40)
        R.check('2번 터미널의 셸이 뜬다 — 방금 연 2번이 고른 터미널', 'PS ' in text(1) and page.evaluate(PICKED) == 1, page.evaluate(PICKED))
        page.locator('#lec-view p').first.click()
        page.wait_for_timeout(200)
        page.keyboard.press('Shift+ArrowRight')
        R.wait(lambda: sent(1) == 1, 10)
        R.check('Shift+→ 는 최근에 쓴 2번 터미널로 — 1번이 아니다', sent(1) == 1 and sent(0) == 0, [sent(0), sent(1)])
        toast = page.evaluate("() => document.querySelector('#lec-toast')?.textContent || ''")
        R.check("알림 '2번 터미널에 넣었습니다'", '2번 터미널에 넣었습니다' in toast, toast)
        page.locator('#lec-term .term-pane[data-n="0"] .term-box').click()   # 1번 터미널을 눌러 쓴다
        R.wait(lambda: page.evaluate(PICKED) == 0, 5)
        page.locator('#lec-view p').first.click()
        page.wait_for_timeout(200)
        page.keyboard.press('Control+Shift+ArrowRight')
        R.wait(lambda: sent(0) == 1, 10)
        R.check('1번 터미널을 누른 뒤 Ctrl+Shift+→ 는 1번으로, 초점은 문서에', sent(0) == 1 and sent(1) == 1 and not page.evaluate("() => !!document.activeElement?.closest?.('#lec-term')"), [sent(0), sent(1)])
        page.locator('#lec-term .term-pane[data-n="1"] .term-box').click()   # 다시 2번
        R.wait(lambda: page.evaluate(PICKED) == 1, 5)
        page.click('#lec-btn-ai')
        R.wait(lambda: menu() is not None, 5)
        rows = menu() or []
        R.check('AI 요청 메뉴: 가리키기 · 다듬기 점검 · 내 문체 견본 · 설정', len(rows) >= 4 and '@보고서.md' in rows[0] and '다듬기 점검' in rows[1] and 'AI 도구 설정' in rows[-1], rows)
        page.locator('#lec-menu button[data-i]', has_text='이 문서 가리키기').click()
        R.wait(lambda: sent(1) == 2, 10)
        R.check('AI 요청도 최근에 쓴 2번 터미널로 — Enter 는 누르지 않는다 (새 프롬프트가 생기지 않는다)', sent(1) == 2 and sent(0) == 1 and text(1).count('PS ') == 1, [sent(0), sent(1), text(1).count('PS ')])
        R.check('화면 스크립트 오류 없음', not errors, errors[:3])
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
