"""0.113.1 — 실제 창(WebView2)에서: 차트의 색 조합 (D216 — 사용자 보고: 보고서 차트의 '색 조합…' 창이 여덟 칸 모두 같았다).
계열이 하나인 Vega-Lite 막대가 칸마다 다른 색, 고르면 '// 색: 2 보고서 남색' 과 문서의 막대가 그 색, 원문이 색을 정한 차트·캔들은 창 위에 까닭,
Plotly 열지도의 색 막대가 검지 않다 (url('#…') 그러데이션이 남는다).
  python tools/real/real1131.py [--exe <Lectern.exe>]   (없으면 소스의 app.py)"""
import json
import shutil
import subprocess
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

import realwin as R

V = '{"values": [{"k": "가", "v": 3}, {"k": "나", "v": 5}, {"k": "다", "v": 4}, {"k": "라", "v": 6}]}'
X = '["가", "나", "다", "라"]'
base = Path(tempfile.mkdtemp(prefix='lec-real1131-'))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'language': 'ko', 'work_alerts': False, 'theme': 'notion', 'toc_visible': False}), encoding='utf-8')
proj = base / '과제'
proj.mkdir()
doc = proj / '보고서.md'
doc.write_text(f"""# 보고서

```vega-lite
{{"data": {V}, "mark": "bar", "encoding": {{"x": {{"field": "k", "type": "nominal"}}, "y": {{"field": "v", "type": "quantitative"}}}}}}
```

```vega-lite
{{"data": {V}, "mark": {{"type": "bar", "color": "#2f5d8a"}}, "encoding": {{"x": {{"field": "k", "type": "nominal"}}, "y": {{"field": "v", "type": "quantitative"}}}}}}
```

```echarts
{{"xAxis": {{"type": "category", "data": {X}}}, "yAxis": {{"type": "value", "scale": true}}, "series": [{{"type": "candlestick", "data": [[20, 34, 10, 38], [40, 35, 30, 50], [31, 38, 33, 44], [38, 15, 5, 42]]}}]}}
```

```plotly
{{"data": [{{"type": "heatmap", "z": [[1, 2, 3], [3, 2, 1]]}}]}}
```
""", encoding='utf-8', newline='\n')
src = lambda: doc.read_text(encoding='utf-8').replace('\r\n', '\n')   # noqa: E731
LOOKS = """() => [...document.querySelectorAll('#lec-dpick .dpick-card')].map((c) => {
  const svg = c.querySelector('.dpick-stage svg');
  if (!svg) return '';
  const out = new Set();
  for (const el of svg.querySelectorAll('path, rect')) {
    const v = (el.style.getPropertyValue('fill') || el.getAttribute('fill') || '').toLowerCase();
    if (v && v !== 'none' && !v.startsWith('url(')) out.add(v);
  }
  return [...out].sort().join(' ');
})"""

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
        R.open_doc(page, '보고서.md')
        R.wait(lambda: page.locator('#lec-view pre.lec-chart.chart-ok').count() == 4, 60)

        def pick(i):
            node = page.locator('#lec-view pre.lec-chart').nth(i)
            node.scroll_into_view_if_needed()
            node.click(button='right', position={'x': 20, 'y': 20})
            page.wait_for_selector('#lec-menu:not([hidden])', timeout=8000)
            page.locator('#lec-menu button', has_text='색 조합…').first.click()
            page.wait_for_selector('#lec-dpick:not([hidden])', timeout=8000)
            R.wait(lambda: page.locator('#lec-dpick-grid.dpick-done').count() == 1, 40)
            page.wait_for_timeout(200)
            note = page.locator('#lec-dpick-same')
            return page.evaluate(LOOKS), (note.inner_text() if note.is_visible() else '')

        print('[계열이 하나인 막대]')
        looks, note = pick(0)
        R.check('여덟 칸이 모두 다르다', len(looks) == 8 and len(set(looks)) == 8, looks)
        R.check('칸이 갈리면 알림 없음', not note, note)
        page.locator('#lec-dpick .dpick-card[data-n="2"]').click()
        R.wait(lambda: '```vega-lite\n// 색: 2 보고서 남색\n{' in src(), 10)
        R.check("고르면 '// 색: 2 보고서 남색'", '```vega-lite\n// 색: 2 보고서 남색\n{' in src(), src()[:120])
        R.wait(lambda: page.evaluate("() => document.querySelector('#lec-view pre.lec-chart')?.dataset.diagramColors") == '2', 15)
        R.wait(lambda: page.locator('#lec-view pre.lec-chart.chart-ok').count() == 4, 30)
        fill = page.evaluate("() => document.querySelector('#lec-view pre.lec-chart svg path[aria-roledescription=\"bar\"]')?.getAttribute('fill') || ''")
        R.check('문서의 막대가 보고서 남색(#17304f)', fill.lower() == '#17304f', fill)

        print('[따르지 않는 차트 — 까닭]')
        looks, note = pick(1)
        R.check("원문이 색을 정한 막대: 칸이 같고 '원문이 색을 정해 두어'", len(set(looks)) == 1 and note.startswith('칸이 모두 같습니다 — 원문이 색을 정해 두어'), note)
        page.keyboard.press('Escape')
        looks, note = pick(2)
        R.check("캔들: 칸이 같고 '정해진 색을 써서'", len(set(looks)) == 1 and '정해진 색을 써서' in note, note)
        page.keyboard.press('Escape')

        print('[Plotly 열지도의 색 막대]')
        bar = page.evaluate("() => document.querySelectorAll('#lec-view pre.lec-chart')[3].querySelector('svg rect.cbfill')?.getAttribute('style') || ''")
        R.check("색 막대의 그러데이션 url('#…') 이 남는다", "url('#" in bar or 'url("#' in bar, bar)
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
