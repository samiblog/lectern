"""0.103.0 — 실제 창(WebView2)에서: 모아 보기가 문서 탭 하나의 화면 (D196) — 여러 문서의 표를 실제 모습으로 펼치고, 내용으로 거르고(맞은 낱말 표시),
출처 줄로 그 문서에 갔다가 Alt+← 로 돌아오고, 다이어그램을 그리고, 'Claude Code 에' 가 실제 셸에 위치 목록을 넣는다 (Enter 없이).
사이드바 목록의 행에서 Shift+→ · Ctrl+Shift+→ (D195) — 실제 셸에 '@경로' 가 들어가고 초점이 터미널로·목록에.
  python tools/real/real103.py [--exe <Lectern.exe>]   (없으면 소스의 app.py)"""
import json
import shutil
import subprocess
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

import realwin as R

base = Path(tempfile.mkdtemp(prefix='lec-real103-'))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'language': 'ko', 'work_alerts': False}), encoding='utf-8')
proj = base / '연구'
(proj / '조사').mkdir(parents=True)
(proj / '조사' / '가격.md').write_text('''# 가격

## 분기별 가격

표 1. 구리 분기별 가격

| 분기 | 가격 | 전기비 |
|---|---:|---:|
| 1Q | 9,210 | +3.1% |
| 2Q | 9,480 | +2.9% |

자료: LME

머리 문단입니다.
''', encoding='utf-8', newline='\n')
(proj / '조사' / '수급.md').write_text('''# 수급

## 공급

표 1. 광산별 생산량

| 광산 | 나라 | 생산량 |
|---|---|---:|
| 에스콘디다 | 칠레 | 1,050 |

자료: 각 사 보고서

그림 1. 공급 흐름

```mermaid
flowchart LR
  광산 --> 제련 --> 가공
```
''', encoding='utf-8', newline='\n')
(proj / '개요.md').write_text('# 개요\n\n표 1. 요약\n\n| 항목 | 값 |\n|---|---|\n| 니켈 | 하락 |\n', encoding='utf-8', newline='\n')

TABS = "() => [...document.querySelectorAll('#lec-doctab-list .doc-tab')].map((e) => e.querySelector('.name').textContent + (e.classList.contains('active') ? '*' : ''))"
CHUNKS = """() => [...document.querySelectorAll('#lec-view .parts-list .pv-chunk')].map((e) => ({ doc: e.dataset.doc, real: !!e.querySelector('.pv-body.md-body table'),
  cap: e.querySelector('.pv-body .lec-caption')?.textContent.trim() || '', lines: e.querySelector('.pv-lines')?.textContent || '' }))"""
SEEN = """(word) => { const t = [...document.querySelectorAll('#lec-view .table-wrap')].find((w) => w.textContent.includes(word));
  const r = t?.getBoundingClientRect(); const c = document.querySelector('#lec-content').getBoundingClientRect(); return !!r && r.bottom > c.top + 20 && r.top < c.bottom - 20; }"""
DONE = "() => { const g = [...document.querySelectorAll('#lec-view .pv-spread')]; return g.length > 0 && g.every((x) => x.classList.contains('pv-done')); }"
TEXT = """(n) => import('/static/js/store.js').then((m) => { const term = (m.S.tab.terms || []).find((x) => x.n === n); if (!term?.xterm) return '';
  const b = term.xterm.buffer.active; const out = []; for (let i = 0; i < b.length; i++) out.push(b.getLine(i).translateToString(true)); return out.join(''); })"""
VIEW = "() => import('/static/js/store.js').then((m) => (m.S.view ? m.S.view.type + ':' + (m.S.view.path || '') : ''))"
FOCUS = """() => { const a = document.activeElement; if (a?.closest('#lec-term')) return 'term'; if (a?.closest('#lec-tree')) return 'tree:' + (a.dataset.doc ?? a.dataset.dir ?? ''); return a?.closest('#lec-panes') ? 'doc' : (a?.tagName || ''); }"""


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
        text = lambda n: page.evaluate(TEXT, n)  # noqa: E731
        flat = lambda n: ''.join(text(n).split())  # noqa: E731

        print('[모아 보기 — 문서 탭 하나에 실제 표를 펼친다 (D196)]')
        R.check('가격 문서를 연다', R.open_doc(page, '조사/가격.md'))
        R.check("사이드바에 '모아 보기' 탭이 없다", page.evaluate("() => [...document.querySelectorAll('.side-tabs button')].map((x) => x.dataset.tab)") == ['files', 'recent', 'search', 'basket'])
        page.click('#lec-btn-overview')
        page.wait_for_selector('#lec-view.overview .ov-parts button[data-parts="table"]', timeout=15000)
        R.check('개요 단추는 보던 문서의 탭을 폴더 개요로 바꾼다 (전과 같다)', page.evaluate(TABS) == ['연구*'], page.evaluate(TABS))
        page.keyboard.press('Alt+ArrowLeft')
        R.wait(lambda: page.evaluate(VIEW) == 'doc:조사/가격.md', 10)
        page.hover('#lec-btn-parts')
        R.wait(lambda: page.evaluate("() => { const b = document.querySelector('#lec-tabtip'); return b && !b.hidden ? b.querySelector('b').textContent : ''; }") == '모아 보기', 5)
        R.check("탭 막대의 단추에 마우스를 올리면 '모아 보기'", page.evaluate("() => { const b = document.querySelector('#lec-tabtip'); return b && !b.hidden ? b.querySelector('b').textContent : ''; }") == '모아 보기')
        page.click('#lec-btn-parts')   # 탭 막대의 모아 보기 단추 — 프로젝트 전체, 처음은 표
        page.wait_for_selector('#lec-view.parts-view .pv-chunk', timeout=20000)
        R.check('보던 문서를 두고 새 문서 탭에 열린다 — 단추는 눌린 모양', page.evaluate(TABS) == ['가격.md', '모아 보기*'] and page.get_attribute('#lec-btn-parts', 'aria-pressed') == 'true', page.evaluate(TABS))
        R.wait(lambda: page.evaluate(DONE), 20)
        got = page.evaluate(CHUNKS)
        R.check('세 문서의 표 셋이 실제 표로', len(got) == 3 and all(c['real'] for c in got), got)
        R.check('캡션과 원문 줄이 함께', got[0]['cap'] == '표 1. 구리 분기별 가격' and got[0]['lines'].endswith('행'), got[0])
        R.check('목차 패널은 모은 것의 차례', page.evaluate("() => document.querySelector('#lec-toc .toc-head')?.textContent") == '모아 보기' and page.locator('#lec-toc a[data-i]').count() == 6,
                page.locator('#lec-toc a[data-i]').count())

        print('[내용으로 거르기, 출처 줄, Alt+←]')
        page.keyboard.press('Control+f')
        R.check('Ctrl+F 는 거르기 칸으로', page.evaluate("() => document.activeElement?.classList.contains('parts-filter')"))
        page.keyboard.type('칠레')
        R.wait(lambda: len(page.evaluate(CHUNKS)) == 1, 10)
        one = page.evaluate(CHUNKS)
        R.check("'칠레' — 칸에 그 글이 든 표만", [c['doc'] for c in one] == ['조사/수급.md'], one)
        R.wait(lambda: page.locator('#lec-view mark.pv-hit').count() > 0, 10)
        R.check('맞은 낱말을 표시한다', page.locator('#lec-view mark.pv-hit').count() == 1, page.locator('#lec-view mark.pv-hit').count())
        page.click('#lec-view .pv-chunk .pv-go')
        R.wait(lambda: page.evaluate(VIEW) == 'doc:조사/수급.md', 15)
        R.wait(lambda: page.evaluate(SEEN, '에스콘디다'), 10)
        R.check('출처 줄을 누르면 이 탭에서 그 문서의 그 표로', page.evaluate(VIEW) == 'doc:조사/수급.md' and page.evaluate(SEEN, '에스콘디다') and page.evaluate(TABS) == ['가격.md', '수급.md*'], page.evaluate(TABS))
        page.keyboard.press('Alt+ArrowLeft')
        page.wait_for_selector('#lec-view.parts-view .pv-chunk', timeout=15000)
        R.check('Alt+← 로 모아 보기에 — 거르기가 그대로', page.evaluate("() => document.querySelector('#lec-view .parts-filter').value") == '칠레' and len(page.evaluate(CHUNKS)) == 1, page.evaluate(CHUNKS))
        page.fill('#lec-view .parts-filter', '')
        R.wait(lambda: len(page.evaluate(CHUNKS)) == 3, 10)
        page.click('#lec-view .parts-kinds button[data-kind="diagram"]')
        ok = R.wait(lambda: page.locator('#lec-view .pv-chunk[data-kind="diagram"] .pv-body pre.mermaid svg').count() == 1, 60)
        R.check('다이어그램을 그려서 보인다 (Mermaid)', bool(ok))
        page.click('#lec-view .parts-kinds button[data-kind="table"]')
        R.wait(lambda: len(page.evaluate(CHUNKS)) == 3 and page.evaluate(DONE), 20)

        print("[넘기기 — 'Claude Code 에' 가 실제 셸에]")
        page.fill('#lec-view .parts-filter', '구리')
        R.wait(lambda: len(page.evaluate(CHUNKS)) == 1, 10)
        page.click('#lec-view .parts-send[data-act="ai"]')
        R.wait(lambda: '@조사/가격.md' in flat(0), 60)
        R.check('터미널을 열어 위치를 넣는다 — 캡션까지', "@조사/가격.md5~10행('표1.구리분기별가격')" in flat(0), text(0)[-160:])
        R.check('Enter 는 누르지 않는다 (새 프롬프트가 생기지 않는다)', text(0).count('PS ') == 1, text(0).count('PS '))
        page.keyboard.press('Control+c')
        page.wait_for_timeout(600)

        print('[사이드바 목록의 행에서 Shift+→ (D195)]')
        row = page.locator('#lec-tree .row.file[data-doc="개요.md"]')
        row.focus()
        before = flat(0).count('@개요.md')
        page.keyboard.press('Shift+ArrowRight')
        R.wait(lambda: flat(0).count('@개요.md') == before + 1, 20)
        R.check("Shift+→: '@경로' 가 터미널에", flat(0).count('@개요.md') == before + 1, text(0)[-120:])
        R.wait(lambda: page.evaluate(FOCUS) == 'term', 10)
        R.check('— 초점은 터미널로', page.evaluate(FOCUS) == 'term', page.evaluate(FOCUS))
        page.locator('#lec-tree .row.dir[data-dir="조사"]').focus()
        opened = "() => !!document.querySelector('#lec-tree .row[data-dir=\"조사\"] .caret')?.classList.contains('open')"
        was = page.evaluate(opened)
        page.keyboard.press('Control+Shift+ArrowRight')
        R.wait(lambda: '@조사' in flat(0).split('@개요.md')[-1], 20)
        R.check('Ctrl+Shift+→: 폴더도 @폴더 로 — 펼친 것은 그대로', '@조사' in flat(0).split('@개요.md')[-1] and page.evaluate(opened) == was, text(0)[-120:])
        R.wait(lambda: page.evaluate(FOCUS) == 'tree:조사', 10)
        R.check('— 초점은 그 행에 남는다', page.evaluate(FOCUS) == 'tree:조사', page.evaluate(FOCUS))
        R.check('여전히 Enter 는 누르지 않았다', text(0).count('PS ') <= 2, text(0).count('PS '))
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
