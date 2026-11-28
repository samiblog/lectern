"""0.113.2 — 실제 창(WebView2)에서: 원문이 정한 색 (D217 — 예전에 쓴 보고서는 원문의 색 때문에 색 조합이 듣지 않았다).
고르기 창의 알림이 원문의 몇째 줄인지 보이고 'Claude 에 색 지정 빼기 요청' 단추가 있다, 칸은 갈리지만 원문의 색이 남으면 옅은 알림,
색 없이 나눈 차트(층마다 datum)는 여덟 칸이 다르고 알림 없음, AI 요청 메뉴의 문서 전체 요청, 설정 창의 '예전 판의 요약',
설치된 작성 안내에 요약의 판 표시. 단추는 누르지 않는다 (실제 터미널에 들어간다 — 요청 글은 가장자리 점검 owncolors·scen_1132 가 본다).
  python tools/real/real1132.py [--exe <Lectern.exe>]   (없으면 소스의 app.py)"""
import json
import shutil
import subprocess
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

import realwin as R

V = '{"values": [{"k": "가", "v": 3, "s": 30}, {"k": "나", "v": 5, "s": 20}, {"k": "다", "v": 4, "s": 40}]}'
base = Path(tempfile.mkdtemp(prefix='lec-real1132-'))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'language': 'ko', 'work_alerts': False, 'theme': 'notion', 'toc_visible': False}), encoding='utf-8')
proj = base / '과제'
proj.mkdir()
(proj / 'CLAUDE.md').write_text('# 규칙\n\n## 문서 (Lectern 으로 읽음)\n- 차트는 ```vega-lite.\n', encoding='utf-8')   # 판 표시가 없는 예전 요약
doc = proj / '보고서.md'
doc.write_text(f"""# 보고서

```vega-lite
{{"data": {V}, "mark": {{"type": "bar", "color": "#2f5d8a"}}, "encoding": {{"x": {{"field": "k", "type": "nominal"}}, "y": {{"field": "v", "type": "quantitative"}}}}}}
```

```vega-lite
{{"data": {V}, "encoding": {{"x": {{"field": "k", "type": "nominal"}}}}, "layer": [
  {{"mark": "bar", "encoding": {{"y": {{"field": "v", "type": "quantitative"}}}}}},
  {{"mark": {{"type": "line", "color": "#e45756"}}, "encoding": {{"y": {{"field": "s", "type": "quantitative"}}}}}}
], "resolve": {{"scale": {{"y": "independent"}}}}}}
```

```vega-lite
{{"data": {V}, "encoding": {{"x": {{"field": "k", "type": "nominal"}}}}, "layer": [
  {{"mark": "bar", "encoding": {{"y": {{"field": "v", "type": "quantitative"}}, "color": {{"datum": "물량"}}}}}},
  {{"mark": "line", "encoding": {{"y": {{"field": "s", "type": "quantitative"}}, "color": {{"datum": "단가"}}}}}}
], "resolve": {{"scale": {{"y": "independent"}}}}}}
```
""", encoding='utf-8', newline='\n')
src = lambda: doc.read_text(encoding='utf-8').replace('\r\n', '\n')   # noqa: E731
LOOKS = """() => [...document.querySelectorAll('#lec-dpick .dpick-card')].map((c) => {
  const svg = c.querySelector('.dpick-stage svg');
  if (!svg) return '';
  const out = new Set();
  for (const el of svg.querySelectorAll('path, rect')) {
    const st = getComputedStyle(el);
    for (const v of [st.fill, st.stroke]) if (v && v !== 'none' && !v.startsWith('url(')) out.add(v);
  }
  return [...out].sort().join(' ');
})"""
MENU = "() => { const m = document.querySelector('#lec-menu'); return m && !m.hidden ? [...m.querySelectorAll('button[data-i]')].map((b) => b.textContent) : null; }"
ROWS = "(id) => [...document.querySelectorAll(id + ' li')].map((li) => li.querySelector('small')?.textContent || '')"

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
        R.wait(lambda: page.locator('#lec-view pre.lec-chart.chart-ok').count() == 3, 60)
        before = src()

        def pick(i):
            node = page.locator('#lec-view pre.lec-chart').nth(i)
            node.scroll_into_view_if_needed()
            node.click(button='right', position={'x': 20, 'y': 20})
            page.wait_for_selector('#lec-menu:not([hidden])', timeout=8000)
            page.locator('#lec-menu button', has_text='색 조합…').first.click()
            page.wait_for_selector('#lec-dpick:not([hidden])', timeout=8000)
            R.wait(lambda: page.locator('#lec-dpick-grid.dpick-done').count() == 1, 40)
            page.wait_for_timeout(200)
            shown = page.locator('#lec-dpick-same').is_visible()
            ask = page.locator('#lec-dpick-uncolor')
            return (page.evaluate(LOOKS), page.locator('#lec-dpick-same-text').inner_text() if shown else '',
                    shown and 'soft' in (page.locator('#lec-dpick-same').get_attribute('class') or ''), ask.inner_text() if ask.is_visible() else '')

        print('[원문이 색을 정한 막대 — 몇째 줄]')
        looks, note, soft, ask = pick(0)
        R.check("여덟 칸이 같고 알림이 '4째 줄 … #2f5d8a'", len(set(looks)) == 1 and note.startswith('칸이 모두 같습니다 — 원문이 색을 정해 두어(4째 줄') and '#2f5d8a' in note, note)
        R.check("'Claude 에 색 지정 빼기 요청' 단추", ask == 'Claude 에 색 지정 빼기 요청', ask)
        page.keyboard.press('Escape')

        print('[막대는 바뀌고 선의 색만 남는 차트 — 옅은 알림]')
        looks, note, soft, ask = pick(1)
        R.check('칸은 갈리고 옅은 알림 (선의 #e45756)', len(set(looks)) > 1 and soft and note.startswith('원문이 정한 색은 그대로 남습니다 — ') and '#e45756' in note, (len(set(looks)), note))
        page.keyboard.press('Escape')

        print('[색 없이 나눈 차트 — 층마다 datum]')
        looks, note, soft, ask = pick(2)
        R.check('여덟 칸이 모두 다르고 알림·단추 없음', len(set(looks)) == 8 and not note and not ask, (len(set(looks)), note))
        page.keyboard.press('Escape')

        print('[AI 요청 메뉴]')
        page.click('#lec-btn-ai')
        R.wait(lambda: page.evaluate(MENU) is not None, 10)
        items = page.evaluate(MENU) or []
        R.check("'그림·차트의 색 지정 빼기 요청'", any(x.startswith('그림·차트의 색 지정 빼기 요청') for x in items), items)
        page.keyboard.press('Escape')

        print("[설정 창 'AI 도구' — 이 폴더의 예전 요약]")
        page.keyboard.press('Control+,')
        page.wait_for_selector('#lec-settings:not([hidden])', timeout=10000)
        page.click('#lec-settings .set-nav button[data-set="ai"]')
        page.check('#lec-settings input[name="ai_scope_guide"][value="folder"]')
        R.wait(lambda: '확인 중…' not in page.inner_text('#lec-aiguide-files'), 15)
        notes = page.evaluate(ROWS, '#lec-aiguide-files')
        R.check("이 폴더의 CLAUDE.md: '예전 판의 요약'", bool(notes) and notes[0].startswith('예전 판의 요약'), notes)
        page.keyboard.press('Escape')

        print('[설치된 작성 안내 — 요약의 판]')
        guide = page.evaluate("() => fetch('/static/help/writing.md').then((r) => r.text())")
        R.check('작성 안내의 요약 맨 위에 lectern-summary: 2, 4장에 색 없이 나누는 법', '<!-- lectern-summary: 2 -->' in guide and '색 없이 나누는 법' in guide)
        R.check('보고서는 그대로 (보기만 했다)', src() == before)
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
