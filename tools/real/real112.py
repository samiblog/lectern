"""0.112.0 — 실제 창(WebView2)에서: 도해 스타일 (D212 — 그림 블록의 '%% 스타일: N' 줄로 Mermaid·Graphviz 의 모양을 고른다.
제목 상자는 줄을 바꾼 상자의 첫 줄이 제목 — 띠가 제목과 내용 사이에서 끝난다. 우클릭 '도해 스타일…' 이 그 블록에 줄을 쓴다. 설정 창의 기본 번호).
  python tools/real/real112.py [--exe <Lectern.exe>]   (없으면 소스의 app.py)"""
import json
import shutil
import subprocess
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

import realwin as R

base = Path(tempfile.mkdtemp(prefix='lec-real112-'))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'language': 'ko', 'work_alerts': False, 'theme': 'report', 'toc_visible': False}), encoding='utf-8')
proj = base / '과제'
proj.mkdir()
doc = proj / '도해.md'
doc.write_text("""# 도해

<!-- 도해: 색 2 -->

```mermaid
flowchart LR
  A[시작] --> B[분석]:::key --> C[끝]
```

```mermaid
flowchart LR
  %% 스타일: 8
  A[자료 수집<br>통계청·업계 보고서 12건] --> B[분석<br>수요 회귀 모형]:::key --> C[보고서]
```

```dot
digraph 가 {
  // 스타일: 9
  rankdir=LR
  A [label="자료 수집\\n통계 12건"]; B [label="분석", class="key"];
  A -> B
}
```

```vega-lite
// 색: 3
{ "data": {"values": [{"k": "a", "v": 3}, {"k": "b", "v": 2}]}, "mark": "bar",
  "encoding": {"x": {"field": "k", "type": "nominal"}, "y": {"field": "v", "type": "quantitative"}, "color": {"field": "k", "type": "nominal"}} }
```
""", encoding='utf-8', newline='\n')
src = lambda: doc.read_text(encoding='utf-8').replace('\r\n', '\n')   # noqa: E731
STYLES = "() => [...document.querySelectorAll('#lec-view pre.mermaid, #lec-view pre.lec-chart')].map((n) => n.dataset.diagramStyle || '')"
BAND = """() => [...document.querySelectorAll('#lec-view pre.mermaid')][1] && [...[...document.querySelectorAll('#lec-view pre.mermaid')][1].querySelectorAll('g.node')].map((g) => {
  const band = g.querySelector('.lec-title-band'); const dt = g.querySelector('.lec-dt'); const p = dt && dt.parentElement; const br = p && p.querySelector('br');
  if (!band || !br) return null;
  const r = document.createRange(); r.setStartAfter(br); r.setEnd(p, p.childNodes.length);
  const top = Math.min(...[...r.getClientRects()].filter((x) => x.height).map((x) => x.top));
  return { bottom: band.getBoundingClientRect().bottom, title: Math.max(...[...dt.getClientRects()].map((x) => x.bottom)), content: top }; }).filter(Boolean)"""

def saved_style():
    """설정 파일의 diagram_style — 앱이 파일을 바꿔 끼우는 순간에는 Windows 가 읽기를 막는다 (그때는 None, 다시 기다린다)"""
    try:
        return json.loads((config / 'config.json').read_text(encoding='utf-8')).get('diagram_style')
    except (OSError, ValueError):
        return None


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

        print('[그림의 번호]')
        page.click('#lec-tree .row[data-doc="도해.md"]')
        R.wait(lambda: page.locator('#lec-view pre.mermaid.mermaid-ok').count() == 2 and page.locator('#lec-view pre.lec-chart.chart-ok').count() == 2, 30)
        R.check('줄 없음은 1, Mermaid 8, Graphviz 9', page.evaluate(STYLES)[:3] == ['1', '8', '9'], page.evaluate(STYLES))
        bands = page.evaluate(BAND) or []
        R.check('WebView2 에서도 제목 띠는 제목 아래·내용 위에서 끝난다', len(bands) == 2 and all(x['title'] - 1 <= x['bottom'] <= x['content'] + 1 for x in bands), bands)
        R.check('Graphviz 도 옅은 제목 띠', page.locator('#lec-view pre.lec-chart .lec-title-band').count() == 1)

        print('[색 조합 (D213)]')
        key = page.evaluate("() => getComputedStyle(document.querySelector('#lec-view pre.mermaid g.node.key rect')).fill")
        R.check("문서의 '<!-- 도해: 색 2 -->' — 핵심 상자가 보고서 남색", key == 'rgb(23, 48, 79)', key)
        fills = page.evaluate("() => [...document.querySelectorAll('#lec-view pre.lec-chart')][1].querySelectorAll('g.mark-rect path').length && [...[...document.querySelectorAll('#lec-view pre.lec-chart')][1].querySelectorAll('g.mark-rect path')].map((e) => getComputedStyle(e).fill)")
        R.check("차트의 '// 색: 3' — 첫 계열 주황, 다음 회색", bool(fills) and fills[0] == 'rgb(194, 65, 12)' and 'rgb(107, 114, 128)' in fills, fills)

        print('[우클릭 — 줄 쓰기]')
        page.locator('#lec-view pre.mermaid').nth(0).click(button='right', position={'x': 5, 'y': 5})
        page.wait_for_selector('#lec-menu:not([hidden])', timeout=8000)
        page.locator('#lec-menu button', has_text='도해 스타일…').click()
        page.wait_for_selector('#lec-dpick:not([hidden]) .dpick-card', timeout=8000)   # 고르기 창 (D214)
        page.locator('#lec-dpick .dpick-card[data-n="3"]').click()
        R.wait(lambda: '```mermaid\nflowchart LR\n  %% 스타일: 3 카드\n  A[시작]' in src(), 10)
        R.check("'도해 스타일…' 이 그 블록의 첫 줄 아래에 한 줄을 쓴다", '```mermaid\nflowchart LR\n  %% 스타일: 3 카드\n  A[시작]' in src(), src()[:120])
        R.wait(lambda: page.evaluate(STYLES)[:1] == ['3'], 15)
        R.check('다시 그리면 3 카드', page.evaluate(STYLES)[:1] == ['3'], page.evaluate(STYLES))

        print('[설정 창]')
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open-settings', 'view'))")
        page.wait_for_selector('#lec-dstyle-preview pre.mermaid svg', timeout=15000)
        page.select_option('#lec-dstyle', '2')
        R.wait(lambda: saved_style() == 2, 8)
        page.keyboard.press('Escape')
        R.wait(lambda: page.evaluate(STYLES)[:3] == ['3', '8', '9'], 15)
        R.check('설정의 기본 번호는 줄 없는 그림만 — 줄 있는 그림은 그대로', page.evaluate(STYLES)[:3] == ['3', '8', '9'] and saved_style() == 2,
                page.evaluate(STYLES))
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
