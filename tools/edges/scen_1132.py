"""0.113.2 사람 시나리오 — 연구원이 예전에 Claude 가 쓴 보고서의 그림·차트 색을 Claude 에게 빼게 한다 (D217).

0.111 시절의 요약을 넣은 폴더에서 Claude 가 쓴 보고서 — 여섯 라이브러리 모두 원문에 색을 적었다 (실제 Claude Code 의 결과와 같은 꼴).
FIXED 는 그 보고서에 'AI 요청 → 그림·차트의 색 지정 빼기 요청' 을 준 실제 Claude Code 가 고친 것 그대로다 (2026-11-28, D217 의 시험).
1. 보고서를 연다 — 여섯 그림이 모두 그려진다.
2. 항구별 열지도(Plotly) '색 조합…' — 여덟 칸이 같고, 알림이 원문의 몇째 줄('colorscale')인지 보이고, 'Claude 에 색 지정 빼기 요청' 단추.
3. 단추 — 그 블록의 '@보고서.md a~b행' 과 작성 안내 4장을 적은 요청 글이 터미널로 (Enter 없이). 창은 닫히고 파일은 그대로 (앱은 원문의 색을 지우지 않는다).
4. Claude 가 그 블록의 색을 뺐다 (터미널에서) — 다시 그려지고 여덟 칸이 다르다, 알림·단추 없음.
5. 2 보고서 남색을 고른다 — 그 블록에 '// 색: 2 보고서 남색'. Ctrl+Z 로 걷고 Ctrl+Y 로 다시.
6. 월별 수입량(막대+단가 선, 둘 다 색을 적었다) — 칸은 갈리지만 원문의 색이 남는다고 옅게 알린다.
7. AI 요청 메뉴 — '그림·차트의 색 지정 빼기 요청' (문서 전체).
8. Claude 가 문서 전체를 고쳤다 (실제 결과, 위에서 고른 표시 줄은 그대로) — 여섯 그림 모두 색 조합의 칸이 갈리고 알림이 없다.
   흐름도·구성도는 도해 스타일의 칸도 갈린다. 열지도는 고른 2 그대로.
9. 설정 창 'AI 도구' — 이 폴더의 CLAUDE.md 가 예전 판의 요약이라고 알린다. Claude 가 새 요약(판 표시)으로 바꾸면 그 알림이 없어진다.
10. 화면 스크립트 오류 없음."""
import json
import re
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop, until

OLD = """# 2026 상반기 철광석 수입 동향

상반기 수입량은 3,852만 t 으로 늘었고 6월 단가는 110달러까지 올랐다. 하반기 계약은 3분기 초에 앞당기는 것이 낫다.

그림 1. 월별 수입량과 평균 단가

```vega-lite
{
  "width": "container",
  "height": 240,
  "data": {"values": [
    {"월": "1월", "수입량": 610, "단가": 104}, {"월": "2월", "수입량": 585, "단가": 101}, {"월": "3월", "수입량": 640, "단가": 98},
    {"월": "4월", "수입량": 672, "단가": 103}, {"월": "5월", "수입량": 655, "단가": 107}, {"월": "6월", "수입량": 690, "단가": 110}
  ]},
  "encoding": {"x": {"field": "월", "type": "ordinal", "sort": null, "title": null}},
  "layer": [
    {"mark": {"type": "bar", "color": "#4c78a8"}, "encoding": {"y": {"field": "수입량", "type": "quantitative", "title": "수입량 (만 t)"}}},
    {"mark": {"type": "line", "point": true, "color": "#e45756"}, "encoding": {"y": {"field": "단가", "type": "quantitative", "title": "단가 (USD/t)"}}}
  ],
  "resolve": {"scale": {"y": "independent"}}
}
```

그림 2. 국가별 수입 비중 (%)

```vega-lite
{
  "width": "container",
  "height": 200,
  "data": {"values": [{"국가": "호주", "비중": 72}, {"국가": "브라질", "비중": 18}, {"국가": "남아공", "비중": 4}, {"국가": "캐나다", "비중": 3}, {"국가": "기타", "비중": 3}]},
  "mark": "bar",
  "encoding": {
    "y": {"field": "국가", "type": "nominal", "sort": "-x", "title": null},
    "x": {"field": "비중", "type": "quantitative", "title": "비중 (%)"},
    "color": {"condition": {"test": "datum.국가 == '호주'", "value": "#c8102e"}, "value": "#9aa5b1"}
  }
}
```

그림 3. 연간 수입량 — 실적과 전망

```echarts
{
  "height": 300,
  "color": ["#1f4e79", "#9dc3e6"],
  "legend": {"data": ["실적", "전망"]},
  "xAxis": {"type": "category", "data": ["2022", "2023", "2024", "2025", "2026", "2027"]},
  "yAxis": {"type": "value", "min": 7000},
  "series": [
    {"name": "실적", "type": "bar", "data": [7420, 7510, 7380, 7560, null, null]},
    {"name": "전망", "type": "bar", "data": [null, null, null, null, 7700, 7820], "itemStyle": {"color": "#9dc3e6", "borderColor": "#1f4e79", "borderType": "dashed"}},
    {"type": "line", "data": [7600, 7600, 7600, 7600, 7600, 7600], "lineStyle": {"color": "red", "type": "dashed"}, "symbol": "none", "name": "목표"}
  ]
}
```

그림 4. 항구별 월 하역량 (만 t)

```plotly
{
  "data": [{
    "type": "heatmap",
    "x": ["1월", "2월", "3월", "4월", "5월", "6월"],
    "y": ["광양", "포항", "당진"],
    "z": [[250, 240, 262, 270, 268, 281], [210, 200, 221, 232, 225, 238], [150, 145, 157, 170, 162, 171]],
    "colorscale": [[0, "#f7fbff"], [1, "#08306b"]]
  }],
  "layout": {"height": 300, "paper_bgcolor": "white", "plot_bgcolor": "white", "font": {"color": "#333"}}
}
```

그림 5. 수입 결정 과정

```mermaid
flowchart LR
  A[수요 전망] --> B[재고 점검] --> C{계약 판단}
  C -->|적정| D[선적] --> E[하역]
  B -->|부족| F[긴급 구매]
  style C fill:#1f4e79,color:#fff
  classDef danger fill:#f8d7da,stroke:#c8102e
  class F danger
```

그림 6. 자료 흐름

```dot
digraph 자료흐름 {
  rankdir=LR;
  node [shape=box, style="rounded,filled", fillcolor="#eaf1fb", color="#1f4e79", fontname="Malgun Gothic"];
  통계청 -> 자료정리; 관세청 -> 자료정리; 업계자료 -> 자료정리;
  자료정리 -> 수요모형; 자료정리 -> 가격모형;
  수요모형 -> 보고서; 가격모형 -> 보고서;
  보고서 [fillcolor="#1f4e79", fontcolor="white"];
}
```
"""
FIXED = """# 2026 상반기 철광석 수입 동향

상반기 수입량은 3,852만 t 으로 늘었고 6월 단가는 110달러까지 올랐다. 하반기 계약은 3분기 초에 앞당기는 것이 낫다.

그림 1. 월별 수입량과 평균 단가

```vega-lite
{
  "width": "container",
  "height": 240,
  "data": {"values": [
    {"월": "1월", "수입량": 610, "단가": 104}, {"월": "2월", "수입량": 585, "단가": 101}, {"월": "3월", "수입량": 640, "단가": 98},
    {"월": "4월", "수입량": 672, "단가": 103}, {"월": "5월", "수입량": 655, "단가": 107}, {"월": "6월", "수입량": 690, "단가": 110}
  ]},
  "encoding": {"x": {"field": "월", "type": "ordinal", "sort": null, "title": null}},
  "layer": [
    {"mark": {"type": "bar"}, "encoding": {"y": {"field": "수입량", "type": "quantitative", "title": "수입량 (만 t)"}, "color": {"datum": "수입량"}}},
    {"mark": {"type": "line", "point": true}, "encoding": {"y": {"field": "단가", "type": "quantitative", "title": "단가 (USD/t)"}, "color": {"datum": "단가"}}}
  ],
  "resolve": {"scale": {"y": "independent"}}
}
```

그림 2. 국가별 수입 비중 (%)

```vega-lite
{
  "width": "container",
  "height": 200,
  "data": {"values": [{"국가": "호주", "비중": 72}, {"국가": "브라질", "비중": 18}, {"국가": "남아공", "비중": 4}, {"국가": "캐나다", "비중": 3}, {"국가": "기타", "비중": 3}]},
  "mark": "bar",
  "encoding": {
    "y": {"field": "국가", "type": "nominal", "sort": "-x", "title": null},
    "x": {"field": "비중", "type": "quantitative", "title": "비중 (%)"},
    "opacity": {"condition": {"test": "datum.국가 == '호주'", "value": 1}, "value": 0.35}
  }
}
```

그림 3. 연간 수입량 — 실적과 전망

```echarts
{
  "height": 300,
  "legend": {"data": ["실적", "전망"]},
  "xAxis": {"type": "category", "data": ["2022", "2023", "2024", "2025", "2026", "2027"]},
  "yAxis": {"type": "value", "min": 7000},
  "series": [
    {"name": "실적", "type": "bar", "data": [7420, 7510, 7380, 7560, null, null]},
    {"name": "전망", "type": "bar", "data": [null, null, null, null, 7700, 7820], "itemStyle": {"borderType": "dashed"}},
    {"type": "line", "data": [7600, 7600, 7600, 7600, 7600, 7600], "lineStyle": {"type": "dashed"}, "symbol": "none", "name": "목표"}
  ]
}
```

그림 4. 항구별 월 하역량 (만 t)

```plotly
{
  "data": [{
    "type": "heatmap",
    "x": ["1월", "2월", "3월", "4월", "5월", "6월"],
    "y": ["광양", "포항", "당진"],
    "z": [[250, 240, 262, 270, 268, 281], [210, 200, 221, 232, 225, 238], [150, 145, 157, 170, 162, 171]]
  }],
  "layout": {"height": 300}
}
```

그림 5. 수입 결정 과정

```mermaid
flowchart LR
  A[수요 전망] --> B[재고 점검] --> C{계약 판단}:::key
  C -->|적정| D[선적] --> E[하역]
  B -->|부족| F[긴급 구매]:::warn
```

그림 6. 자료 흐름

```dot
digraph 자료흐름 {
  rankdir=LR;
  node [shape=box];
  통계청 -> 자료정리; 관세청 -> 자료정리; 업계자료 -> 자료정리;
  자료정리 -> 수요모형; 자료정리 -> 가격모형;
  수요모형 -> 보고서; 가격모형 -> 보고서;
  보고서 [class="key"];
}
```
"""
OLD_SUMMARY = """# 철광석 수입 동향 — 문서 규칙

구매팀의 자료 폴더다. 읽는 사람은 구매팀장이다.

## 문서 (Lectern 으로 읽음)
- 차트는 ```vega-lite·```echarts·```plotly·```dot, 다이어그램은 ```mermaid.
"""
FENCE = re.compile(r'^(`{3,}|~{3,})')
ALL = '#lec-view pre.lec-chart, #lec-view pre.mermaid'
KINDS = ['vega-lite', 'vega-lite', 'echarts', 'plotly', 'mermaid', 'dot']
LOOKS = """() => [...document.querySelectorAll('#lec-dpick .dpick-card')].map((c) => {
  const svg = c.querySelector('.dpick-stage svg');
  if (!svg) return '';
  const out = new Set();
  for (const el of svg.querySelectorAll('path, rect, circle, ellipse, polygon, line, image')) {
    if (el.tagName === 'image') { const h = el.getAttribute('href') || el.getAttribute('xlink:href') || ''; out.add('img' + h.length + h.slice(-24)); continue; }
    const st = getComputedStyle(el);
    for (const a of ['fill', 'stroke']) {
      const v = (st[a] || '').toLowerCase().replace(/\\s+/g, '');
      if (v && v !== 'none' && !/^(transparent|rgba\\(0,0,0,0\\))$/.test(v) && !v.startsWith('url(')) out.add(a[0] + v);
    }
    out.add('w' + st.strokeWidth + st.strokeDasharray);
  }
  return [...out].sort().join(' ');
})"""
PASTED = '() => window.__pasted'
MENU = "() => { const m = document.querySelector('#lec-menu'); return m && !m.hidden ? [...m.querySelectorAll('button[data-i]')].map((b) => b.textContent) : null; }"
ROWS = "(id) => [...document.querySelectorAll(id + ' li')].map((li) => [li.querySelector('.ai-act').textContent, li.querySelector('.ai-path').textContent, li.querySelector('small')?.textContent || ''])"
OLD_ROW = '예전 판의 요약 — 그림·차트의 색 규칙 등이 없습니다. 요청 글로 새 요약으로 바꿉니다'


def spans(text):
    """그림·차트 블록마다 (여는 줄, 닫는 줄) — 1부터"""
    out, start = [], None
    for n, line in enumerate(text.split('\n'), 1):
        if FENCE.match(line):
            if start is None and line.strip('`~'):
                start = n
            elif start is not None:
                out.append((start, n))
                start = None
    return out


def block(text, i):
    a, z = spans(text)[i]
    return '\n'.join(text.split('\n')[a - 1:z])


def swap(text, i, new):
    lines = text.split('\n')
    a, z = spans(text)[i]
    return '\n'.join(lines[:a - 1] + new.split('\n') + lines[z:])


base = Path(tempfile.mkdtemp(prefix='lec-scen1132-'))
proj = base / '과제'
proj.mkdir()
rep = proj / '보고서.md'
rep.write_text(OLD, encoding='utf-8', newline='\n')
rules = proj / 'CLAUDE.md'
rules.write_text(OLD_SUMMARY, encoding='utf-8', newline='\n')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False, 'theme': 'report', 'toc_visible': False, 'language': 'ko'}), encoding='utf-8')
src = lambda: rep.read_text(encoding='utf-8').replace('\r\n', '\n')   # noqa: E731

server, url, port = serve(proj, config)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 1300, 'height': 920})
        ctx.grant_permissions(['clipboard-read', 'clipboard-write'], origin=url.rstrip('/'))
        page = ctx.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        page.evaluate("() => import('/static/js/store.js').then((m) => { window.__pasted = []; m.on('term-paste', (d) => window.__pasted.push(typeof d === 'string' ? d : d.text)); })")

        def drawn():
            return until(page, lambda: page.evaluate(f"() => [...document.querySelectorAll('{ALL}')].filter((x) => x.classList.contains('chart-ok') || x.classList.contains('mermaid-ok')).length") == 6, ms=60000)

        def kinds():
            return page.evaluate(f"() => [...document.querySelectorAll('{ALL}')].map((n) => n.matches('pre.mermaid') ? 'mermaid' : n.dataset.chart)")

        def pick(i, item='색 조합…'):
            node = page.locator(ALL).nth(i)
            node.scroll_into_view_if_needed()
            node.click(button='right', position={'x': 24, 'y': 24})
            page.wait_for_selector('#lec-menu:not([hidden])', timeout=5000)
            page.locator('#lec-menu button', has_text=item).first.click()
            page.wait_for_selector('#lec-dpick:not([hidden])', timeout=5000)
            until(page, lambda: page.locator('#lec-dpick-grid.dpick-done').count() == 1, ms=30000)
            page.wait_for_timeout(150)
            shown = page.locator('#lec-dpick-same').is_visible()
            ask = page.locator('#lec-dpick-uncolor')
            return {'looks': page.evaluate(LOOKS), 'note': page.locator('#lec-dpick-same-text').inner_text() if shown else '',
                    'soft': shown and 'soft' in (page.locator('#lec-dpick-same').get_attribute('class') or ''),
                    'ask': ask.inner_text() if ask.is_visible() else ''}

        def close():
            page.keyboard.press('Escape')
            page.wait_for_timeout(100)

        def redrawn(text_has):
            """파일이 바뀐 뒤 다시 그려질 때까지 — 그 블록의 원문(data-source)에 text_has 가 들 때"""
            until(page, lambda: page.evaluate(f"(t) => [...document.querySelectorAll('{ALL}')].some((n) => (n.dataset.source || '').includes(t))", text_has), ms=15000)
            drawn()
            page.wait_for_timeout(300)

        print('[1. 예전 보고서를 연다]')
        page.click('#lec-tree .row[data-doc="보고서.md"]')
        until(page, lambda: page.locator('#lec-view h1', has_text='철광석 수입 동향').count() > 0, ms=20000)
        check('여섯 그림을 모두 그린다 (Vega-Lite 둘·ECharts·Plotly·Mermaid·Graphviz)', drawn() and kinds() == KINDS, kinds())

        print('[2. 항구별 열지도 — 원문이 색을 정했다]')
        r = pick(3)
        a, z = spans(src())[3]
        line = next(n for n, x in enumerate(src().split('\n'), 1) if '"colorscale"' in x)
        check('여덟 칸이 같다', len(r['looks']) == 8 and len(set(r['looks'])) == 1, len(set(r['looks'])))
        check(f"알림: '칸이 모두 같습니다 — 원문이 색을 정해 두어({line}째 줄 \"colorscale\"…'", r['note'].startswith(f'칸이 모두 같습니다 — 원문이 색을 정해 두어({line}째 줄 "colorscale"'), r['note'])
        check("'Claude 에 색 지정 빼기 요청' 단추", r['ask'] == 'Claude 에 색 지정 빼기 요청', r['ask'])

        print('[3. 빼기 요청 — 터미널로, 파일은 그대로]')
        before = src()
        page.locator('#lec-dpick-uncolor').click()
        until(page, lambda: len(page.evaluate(PASTED)) == 1, ms=5000)
        ask = page.evaluate(PASTED)[0]
        check(f'요청 글에 그 블록의 자리 (@보고서.md {a}~{z}행)', f'@보고서.md {a}~{z}행' in ask, ask[:200])
        check("요청 글: 작성 안내의 '색 없이 나누는 법', 표시 줄은 그대로, 뜻이 있는 색은 묻기", 'writing.md' in ask and "'색 없이 나누는 법'" in ask and '표시 줄' in ask and '물어봐' in ask, ask)
        check('Enter 없이 (줄바꿈으로 끝나지 않는다)', not ask.endswith('\n'))
        check('창은 닫힌다', page.locator('#lec-dpick').is_hidden())
        page.wait_for_timeout(600)
        check('앱은 원문을 바꾸지 않는다', src() == before)

        print('[4. Claude 가 열지도의 색을 뺐다]')
        rep.write_text(swap(src(), 3, block(FIXED, 3)), encoding='utf-8', newline='\n')
        redrawn('"layout": {"height": 300}}')
        r = pick(3)
        check('열지도: 여덟 칸이 모두 다르다', len(set(r['looks'])) == 8, len(set(r['looks'])))
        check('알림·단추 없음', not r['note'] and not r['ask'], r)

        print('[5. 2 보고서 남색을 고른다 — 되돌리기]')
        fixed4 = src()
        page.locator('#lec-dpick .dpick-card[data-n="2"]').click()
        until(page, lambda: '```plotly\n// 색: 2 보고서 남색\n{' in src(), ms=8000)
        check("그 블록 맨 앞에 '// 색: 2 보고서 남색' — 다른 줄은 그대로", src() == fixed4.replace('```plotly\n{', '```plotly\n// 색: 2 보고서 남색\n{'), src()[:120])
        until(page, lambda: page.evaluate(f"() => [...document.querySelectorAll('{ALL}')][3]?.dataset.diagramColors") == '2', ms=15000)
        drawn()
        page.locator('#lec-view h1').click()
        page.keyboard.press('Control+z')
        until(page, lambda: src() == fixed4, ms=8000)
        check('Ctrl+Z — 표시 줄을 걷는다', src() == fixed4)
        page.keyboard.press('Control+y')
        until(page, lambda: '// 색: 2 보고서 남색' in src(), ms=8000)
        check('Ctrl+Y — 다시', '```plotly\n// 색: 2 보고서 남색\n{' in src())
        redrawn('// 색: 2 보고서 남색')

        print('[6. 월별 수입량 — 막대와 선 모두 원문이 색을 적었다]')
        r = pick(0)
        line0 = next(n for n, x in enumerate(src().split('\n'), 1) if '"color": "#4c78a8"' in x)
        check("칸은 갈리지만 옅은 알림: '원문이 정한 색은 그대로 남습니다 — N째 줄'", r['soft'] and r['note'].startswith(f'원문이 정한 색은 그대로 남습니다 — {line0}째 줄') and '#4c78a8' in r['note'], r['note'])
        check('빼기 요청 단추도 있다', r['ask'] == 'Claude 에 색 지정 빼기 요청', r['ask'])
        close()

        print('[7. AI 요청 메뉴 — 문서 전체]')
        page.click('#lec-btn-ai')
        until(page, lambda: page.evaluate(MENU) is not None)
        items = page.evaluate(MENU) or []
        check("'그림·차트의 색 지정 빼기 요청'", any(x.startswith('그림·차트의 색 지정 빼기 요청') for x in items), items)
        page.locator('#lec-menu button[data-i]', has_text='그림·차트의 색 지정 빼기 요청').click()
        until(page, lambda: len(page.evaluate(PASTED)) == 2, ms=5000)
        whole = page.evaluate(PASTED)[1]
        check('요청 글: @보고서.md 의 그림·차트 (줄 범위 없이)', '@보고서.md 의 그림·차트' in whole and 'writing.md' in whole, whole[:160])

        print('[8. Claude 가 문서 전체를 고쳤다 (실제 Claude Code 의 결과, 고른 표시 줄은 그대로)]')
        rep.write_text(FIXED.replace('```plotly\n{', '```plotly\n// 색: 2 보고서 남색\n{'), encoding='utf-8', newline='\n')
        redrawn('"color": {"datum": "수입량"}')
        for i, kind in enumerate(KINDS):
            r = pick(i)
            want = 8 if kind not in ('dot', 'mermaid') else 7
            check(f'{i + 1}. {kind}: 색 조합의 칸이 갈리고 ({len(set(r["looks"]))}/8) 알림·단추 없음', len(set(r['looks'])) >= want and not r['note'] and not r['ask'], (len(set(r['looks'])), r['note']))
            close()
        for i in (4, 5):
            r = pick(i, '도해 스타일…')
            check(f'{i + 1}. {KINDS[i]}: 도해 스타일의 칸도 갈린다 ({len(set(r["looks"]))}/10)', len(set(r['looks'])) >= 9 and not r['note'], (len(set(r['looks'])), r['note']))
            close()
        check('열지도는 고른 2 그대로', page.evaluate(f"() => [...document.querySelectorAll('{ALL}')][3]?.dataset.diagramColors") == '2')

        print("[9. 설정 창 'AI 도구' — 이 폴더의 예전 요약]")
        page.keyboard.press('Control+,')
        page.wait_for_selector('#lec-settings:not([hidden])')
        page.click('#lec-settings .set-nav button[data-set="ai"]')
        page.check('#lec-settings input[name="ai_scope_guide"][value="folder"]')
        until(page, lambda: '확인 중…' not in page.inner_text('#lec-aiguide-files'), ms=8000)
        rows = page.evaluate(ROWS, '#lec-aiguide-files')
        check('이 폴더의 CLAUDE.md: 바꿈 — 예전 판의 요약이라고', rows and rows[0][0] == '바꿈' and rows[0][1].endswith('CLAUDE.md') and rows[0][2] == OLD_ROW, rows)
        page.click('#lec-aiguide-prompt')
        page.wait_for_timeout(300)
        g = page.evaluate('() => navigator.clipboard.readText()')
        check('요청 글: 작성 안내를 읽고 이 프로젝트의 CLAUDE.md 에 — 요약도 함께', 'writing.md' in g and '이 프로젝트의 CLAUDE.md' in g and '요약도 이 프로젝트에 맞게' in g, g[-200:])
        page.keyboard.press('Escape')
        rules.write_text(OLD_SUMMARY.replace('## 문서 (Lectern 으로 읽음)\n', '## 문서 (Lectern 으로 읽음)\n<!-- lectern-summary: 2 -->\n- 그림·차트에 색을 적지 않는다.\n'), encoding='utf-8', newline='\n')
        page.keyboard.press('Control+,')
        page.wait_for_selector('#lec-settings:not([hidden])')
        until(page, lambda: '확인 중…' not in page.inner_text('#lec-aiguide-files'), ms=8000)
        rows = page.evaluate(ROWS, '#lec-aiguide-files')
        check('Claude 가 새 요약(판 표시)으로 바꾸자 — 예전 판 알림이 없어진다', rows and rows[0][2].startswith('이 폴더의 읽는 사람·목적'), rows)
        page.keyboard.press('Escape')

        print('[10. 끝]')
        check('보고서는 Claude 가 고친 것과 고른 표시 줄 하나', src() == FIXED.replace('```plotly\n{', '```plotly\n// 색: 2 보고서 남색\n{'))
        check('화면 스크립트 오류 없음', not errors, errors[:5])
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
