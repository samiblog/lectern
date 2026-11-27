"""0.113.0 — 실제 창(WebView2)에서: 도해 고르기 창 (D214 — 우클릭 '도해 스타일…'·'색 조합…' 이 그 그림을 번호마다 그려 보이고,
고르면 블록에 '%% 스타일: 3 카드' 처럼 번호와 이름을 쓴다. 메뉴의 오른쪽 글도 '1 기본'), 내 도해 스타일 (D215 — 설정 폴더 diagram-styles 의
파일이 11번으로 그려지고 고르기 창에 '내 것' 칸).
  python tools/real/real113.py [--exe <Lectern.exe>]   (없으면 소스의 app.py)"""
import json
import shutil
import subprocess
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

import realwin as R

base = Path(tempfile.mkdtemp(prefix='lec-real113-'))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'language': 'ko', 'work_alerts': False, 'theme': 'report', 'toc_visible': False}), encoding='utf-8')
(config / 'diagram-styles').mkdir()
(config / 'diagram-styles' / '회사.json').write_text(json.dumps({'kind': 'style', 'number': 11, 'name': '회사', 'base': 2, 'corner': 6, 'dash': True}, ensure_ascii=False), encoding='utf-8')
proj = base / '과제'
proj.mkdir()
doc = proj / '고르기.md'
doc.write_text("""# 고르기

```mermaid
flowchart LR
  A[자료 수집<br>통계 12건] --> B[분석]:::key --> C[보고서]
```

```vega-lite
{ "data": {"values": [{"k": "a", "v": 3}, {"k": "b", "v": 2}, {"k": "c", "v": 4}]}, "mark": "bar",
  "encoding": {"x": {"field": "k", "type": "nominal"}, "y": {"field": "v", "type": "quantitative"}, "color": {"field": "k", "type": "nominal"}} }
```

```mermaid
flowchart LR
  %% 스타일: 11 회사
  A[가] --> B[나]
```
""", encoding='utf-8', newline='\n')
src = lambda: doc.read_text(encoding='utf-8').replace('\r\n', '\n')   # noqa: E731
CARDS = """() => [...document.querySelectorAll('#lec-dpick .dpick-card')].map((c) => { const svg = c.querySelector('.dpick-stage svg'); const pre = c.querySelector('.dpick-stage pre');
  const r = svg && svg.getBoundingClientRect(); const st = c.querySelector('.dpick-stage').getBoundingClientRect();
  return { n: c.dataset.n, svg: !!svg, marks: pre ? (pre.dataset.diagramStyle || '-') + '/' + (pre.dataset.diagramColors || '-') : null,
    inside: !!r && r.width > 10 && r.right <= st.right + 1 && r.bottom <= st.bottom + 1 }; })"""

proc = None
try:
    with sync_playwright() as p:
        proc, cdp = R.launch(proj, config)
        R.CONN.update(pw=p, cdp=cdp)
        b = None
        for _ in range(120):
            try:
                b = p.chromium.connect_over_cdp(f'http://127.0.0.1:{cdp}')
                break
            except Exception:   # noqa: BLE001
                time.sleep(0.5)
        page = R.wait(lambda: R.app_page(b), 60)
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=40000)
        page.wait_for_timeout(1200)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.click('#lec-tree .row[data-doc="고르기.md"]')
        R.wait(lambda: page.locator('#lec-view pre.mermaid.mermaid-ok').count() == 2 and page.locator('#lec-view pre.lec-chart.chart-ok').count() == 1, 30)
        mine = page.evaluate("() => { const n = [...document.querySelectorAll('#lec-view pre.mermaid')][1]; const r = n.querySelector('g.node rect'); const l = n.querySelector('.flowchart-link');"
                             " return [n.dataset.diagramStyle, r && getComputedStyle(r).rx, l && getComputedStyle(l).strokeDasharray]; }")
        R.check('내 도해 스타일 11 — 설정 폴더의 파일대로 (모서리 6px, 점선)', mine[0] == '11' and mine[1] == '6px' and mine[2] not in (None, 'none'), mine)

        print('[메뉴 — 번호와 이름]')
        page.locator('#lec-view pre.mermaid').nth(0).click(button='right', position={'x': 5, 'y': 5})
        page.wait_for_selector('#lec-menu:not([hidden])', timeout=8000)
        hint = page.locator('#lec-menu button', has_text='도해 스타일…').first.inner_text()
        R.check("우클릭 메뉴의 오른쪽 글 '1 기본'", '1 기본' in hint, hint)

        print('[고르기 창 — 그 그림을 열 가지로]')
        page.locator('#lec-menu button', has_text='도해 스타일…').first.click()
        page.wait_for_selector('#lec-dpick:not([hidden])', timeout=8000)
        R.wait(lambda: page.locator('#lec-dpick-grid.dpick-done').count() == 1 and len(page.evaluate(CARDS)) == 11, 30)   # 다 그린 뒤 (번호는 그린 뒤에 적힌다)
        cs = page.evaluate(CARDS)
        R.check('WebView2 에서도 열 칸 + 내 것 11 이 저마다 그 번호로', [c['marks'] for c in cs] == [f'{n}/1' for n in range(1, 12)], cs)
        R.check('그림은 칸 안에', all(c['inside'] for c in cs), [c for c in cs if not c['inside']])
        page.keyboard.press('ArrowRight')
        page.keyboard.press('ArrowRight')
        page.keyboard.press('Enter')
        R.wait(lambda: 'flowchart LR\n  %% 스타일: 3 카드\n  A[자료 수집' in src(), 10)
        R.check("→ 두 번, Enter — '%% 스타일: 3 카드' 한 줄", 'flowchart LR\n  %% 스타일: 3 카드\n  A[자료 수집' in src(), src()[:120])
        R.wait(lambda: page.evaluate("() => document.querySelector('#lec-view pre.mermaid').dataset.diagramStyle") == '3', 15)

        print('[색 조합 — 차트]')
        page.locator('#lec-view pre.lec-chart').nth(0).click(button='right', position={'x': 5, 'y': 5})
        page.wait_for_selector('#lec-menu:not([hidden])', timeout=8000)
        page.locator('#lec-menu button', has_text='색 조합…').first.click()
        page.wait_for_selector('#lec-dpick:not([hidden])', timeout=8000)
        R.wait(lambda: page.locator('#lec-dpick-grid.dpick-done').count() == 1 and len(page.evaluate(CARDS)) == 8, 30)
        R.check('차트는 여덟 칸', len(page.evaluate(CARDS)) == 8)
        page.locator('#lec-dpick .dpick-card[data-n="5"]').click()
        R.wait(lambda: '```vega-lite\n// 색: 5 색약 친화\n{' in src(), 10)
        R.check("누르면 '// 색: 5 색약 친화'", '```vega-lite\n// 색: 5 색약 친화\n{' in src(), src()[-200:])
        page.locator('#lec-view pre.mermaid').nth(0).click(button='right', position={'x': 5, 'y': 5})
        page.wait_for_selector('#lec-menu:not([hidden])', timeout=8000)
        page.locator('#lec-menu button', has_text='색 조합…').first.click()
        page.wait_for_selector('#lec-dpick:not([hidden])', timeout=8000)
        before = src()
        page.keyboard.press('Escape')
        R.check('Esc — 쓰지 않고 닫는다', page.locator('#lec-dpick').is_hidden() and src() == before)
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
