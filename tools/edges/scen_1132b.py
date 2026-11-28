"""0.113.2 사람 시나리오 둘 — 같은 기능을 다른 자리에서 (D217): 고친 예제·영어 화면·다른 AI 도구·좁은 창·차트가 없는 문서.

1. 예제의 경영 요약 슬라이드(색을 걷었다) — 월별 물량·투자 회수 차트의 '색 조합…' 여덟 칸이 모두 다르고 알림이 없다.
   막대 숫자는 Lectern 의 글자색이다 (흰 글자가 아니다). 능력을 넘은 달은 진하게, 나머지는 흐리게.
2. 예제의 시장 분석 슬라이드 — '진한 막대는 재고가 늘어난 달', 그 차트도 여덟 칸이 다르다.
3. 예제의 차트 가이드 — 모든 그림·차트에서 '빼기 요청' 단추가 없다 (원문이 색을 정한 곳이 없다). 막대와 선을 층마다 datum 으로 나눈 차트는
   범례에 가격·재고, Graphviz 의 강조 표시(class="key") 그림은 도해 스타일의 칸이 갈린다.
4. 동료가 보낸 예전 문서(원문에 색) — 영어 화면: 'the source sets its own colors (line N: …)', 'Ask Claude to remove the set colors', AI 요청 메뉴의 영어.
5. Codex 를 쓰는 사람 — 단추가 'Codex 에 색 지정 빼기 요청', 요청 글은 같다.
6. 좁은 창(900×640) — 긴 줄의 알림과 단추가 창 안에 있다.
7. 차트가 없는 문서 — AI 요청 메뉴에 색 빼기 요청이 없다.
8. 예제 파일은 그대로 (보기만 했다). 화면 스크립트 오류 없음."""
import json
import shutil
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import ROOT, check, fails, report, serve, stop, until

ALL = '#lec-view pre.lec-chart, #lec-view pre.mermaid'
FENCE = '```'
COLLEAGUE = f"""# 동료가 보낸 운임 메모

{FENCE}echarts
{{"xAxis": {{"type": "category", "data": ["1주", "2주", "3주"]}}, "yAxis": {{"type": "value"}}, "series": [{{"type": "bar", "data": [1010, 1045, 1032], "itemStyle": {{"color": "#2f5d8a", "borderRadius": 4}}, "label": {{"show": true, "position": "top"}}}}]}}
{FENCE}

{FENCE}mermaid
flowchart LR
  A[운임 조회] --> B[비교] --> C[계약]
  classDef hot fill:#f96,stroke:#333
  class C hot
{FENCE}
"""
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
SOURCES = f"() => [...document.querySelectorAll('{ALL}')].map((n) => n.dataset.source || '')"

base = Path(tempfile.mkdtemp(prefix='lec-scen1132b-'))
proj = base / 'samples'
shutil.copytree(ROOT / 'samples', proj)
(proj / '동료-메모.md').write_text(COLLEAGUE, encoding='utf-8', newline='\n')
before = {f: f.read_bytes() for f in proj.rglob('*.md')}
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False, 'theme': 'notion', 'toc_visible': False, 'language': 'ko'}), encoding='utf-8')

server, url, port = serve(proj, config)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1300, 'height': 920})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))

        def boot():
            page.goto(url)
            page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
            page.evaluate("() => import('/static/js/store.js').then((m) => { window.__pasted = []; m.on('term-paste', (d) => window.__pasted.push(typeof d === 'string' ? d : d.text)); })")

        def open_doc(path, has):
            page.evaluate("(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: p }))", path)
            until(page, lambda: any(has in s for s in page.evaluate(SOURCES)), ms=20000)
            page.wait_for_timeout(400)

        def index(has):
            return next(i for i, s in enumerate(page.evaluate(SOURCES)) if has in s)

        def ready(i):
            node = page.locator(ALL).nth(i)
            node.scroll_into_view_if_needed()
            until(page, lambda: page.evaluate(f"(i) => {{ const n = [...document.querySelectorAll('{ALL}')][i]; return !!n && (n.classList.contains('chart-ok') || n.classList.contains('mermaid-ok')); }}", i), ms=30000)
            return node

        def pick(i, item='색 조합…'):
            node = ready(i)
            node.click(button='right', position={'x': 24, 'y': 24})
            page.wait_for_selector('#lec-menu:not([hidden])', timeout=5000)
            page.locator('#lec-menu button', has_text=item).first.click()
            page.wait_for_selector('#lec-dpick:not([hidden])', timeout=5000)
            until(page, lambda: page.locator('#lec-dpick-grid.dpick-done').count() == 1, ms=30000)
            page.wait_for_timeout(150)
            shown = page.locator('#lec-dpick-same').is_visible()
            ask = page.locator('#lec-dpick-uncolor')
            return {'looks': page.evaluate(LOOKS), 'note': page.locator('#lec-dpick-same-text').inner_text() if shown else '', 'ask': ask.inner_text() if ask.is_visible() else ''}

        def close():
            page.keyboard.press('Escape')
            page.wait_for_timeout(100)

        boot()
        print('[1. 예제의 경영 요약 슬라이드 — 색을 걷은 차트]')
        open_doc('slides/상황별/01-경영-요약.md', '01-월별-물량.csv')
        i = index('01-월별-물량.csv')
        ready(i)
        texts = page.evaluate(f"""(i) => [...[...document.querySelectorAll('{ALL}')][i].querySelectorAll('svg text')]
          .filter((t) => /^(180|205|222)$/.test(t.textContent.trim())).map((t) => getComputedStyle(t).fill)""", i)
        check('막대 숫자 셋이 보이고 흰 글자가 아니다 (Lectern 의 글자색)', len(texts) == 3 and all(x not in ('rgb(255, 255, 255)', 'white') for x in texts), texts)
        op = page.evaluate(f"""(i) => [...new Set([...[...document.querySelectorAll('{ALL}')][i].querySelectorAll('svg path[aria-roledescription="bar"], svg .mark-rect path')]
          .map((p) => p.getAttribute('fill-opacity') || p.getAttribute('opacity') || getComputedStyle(p).fillOpacity))]""", i)
        check('넘은 달은 진하게, 나머지는 흐리게 (투명도 두 가지)', len(op) == 2, op)
        r = pick(i)
        check('월별 물량: 여덟 칸이 모두 다르고 알림·단추 없음', len(set(r['looks'])) == 8 and not r['note'] and not r['ask'], (len(set(r['looks'])), r['note']))
        close()
        r = pick(index('01-투자-회수.csv'))
        check('투자 회수: 여덟 칸이 모두 다르고 알림 없음', len(set(r['looks'])) == 8 and not r['note'], (len(set(r['looks'])), r['note']))
        close()

        print('[2. 예제의 시장 분석 슬라이드]')
        open_doc('slides/상황별/03-시장-분석.md', '재고가 늘어난 달')
        check("소제목: '진한 막대는 재고가 늘어난 달'", page.locator('#lec-view', has_text='진한 막대는 재고가 늘어난 달').count() == 1)
        r = pick(index('재고가 늘어난 달'))
        check('그 차트도 여덟 칸이 다르고 알림 없음', len(set(r['looks'])) == 8 and not r['note'], (len(set(r['looks'])), r['note']))
        close()

        print('[3. 예제의 차트 가이드 — 원문이 색을 정한 곳이 없다]')
        open_doc('guide/07-차트.md', '"datum": "재고"')
        n = page.locator(ALL).count()
        asks = []
        for k in range(n):
            r = pick(k)
            if r['ask']:
                asks.append((k, r['note']))
            close()
        check(f'그림·차트 {n}개 모두 빼기 요청 단추가 없다', n >= 10 and not asks, asks)
        k = index('"datum": "재고"')
        legend = page.evaluate(f"(i) => [...[...document.querySelectorAll('{ALL}')][i].querySelectorAll('svg text')].map((t) => t.textContent.trim())", k)
        check('막대와 선을 층마다 datum 으로: 범례에 가격·재고', '가격' in legend and '재고' in legend, legend[-6:])
        r = pick(k)
        check('그 차트: 여덟 칸이 모두 다르다', len(set(r['looks'])) == 8, len(set(r['looks'])))
        close()
        r = pick(index('class="key"'), '도해 스타일…')
        check('Graphviz 의 강조 표시 그림: 도해 스타일의 칸이 갈리고 알림 없음', len(set(r['looks'])) >= 9 and not r['note'], (len(set(r['looks'])), r['note']))
        close()

        print('[4. 동료가 보낸 예전 문서 — 영어 화면]')
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ language: 'en' }))")
        boot()
        open_doc('동료-메모.md', 'itemStyle')
        r = pick(0, 'Color set…')
        check("영어 알림: 'the source sets its own colors (line 4: …'", r['note'].startswith('All tiles look the same — the source sets its own colors (line 4:') and '#2f5d8a' in r['note'], r['note'])
        check("'Ask Claude to remove the set colors'", r['ask'] == 'Ask Claude to remove the set colors', r['ask'])
        close()
        r = pick(1, 'Diagram style…')
        check("Mermaid classDef: 'The look and colors set in the source stay…', 'Ask Claude to remove the set look and colors'",
              r['note'].startswith('The look and colors set in the source stay as they are — line ') and r['ask'] == 'Ask Claude to remove the set look and colors', r)
        close()
        page.click('#lec-btn-ai')
        until(page, lambda: page.evaluate(MENU) is not None)
        items = page.evaluate(MENU) or []
        check("AI 요청 메뉴: 'Ask to remove colors set in diagrams and charts'", any(x.startswith('Ask to remove colors set in diagrams and charts') for x in items), items)
        page.keyboard.press('Escape')

        print('[5. Codex 를 쓰는 사람]')
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ language: 'ko', ai_tool: 'codex' }))")
        boot()
        open_doc('동료-메모.md', 'itemStyle')
        r = pick(0)
        check("단추가 'Codex 에 색 지정 빼기 요청'", r['ask'] == 'Codex 에 색 지정 빼기 요청', r['ask'])
        page.locator('#lec-dpick-uncolor').click()
        until(page, lambda: len(page.evaluate(PASTED)) == 1, ms=5000)
        ask = page.evaluate(PASTED)[0]
        check('요청 글은 같다 — 그 블록의 자리와 작성 안내', '@동료-메모.md 3~5행' in ask and "'색 없이 나누는 법'" in ask, ask[:160])

        print('[6. 좁은 창 — 긴 줄의 알림]')
        page.set_viewport_size({'width': 900, 'height': 640})
        page.wait_for_timeout(300)
        r = pick(0)
        boxes = page.evaluate("""() => ['#lec-dpick-same', '#lec-dpick-uncolor', '#lec-dpick .dialog-box'].map((s) => { const r = document.querySelector(s).getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; })""")
        check('알림·단추·창이 화면 안 (900×640)', all(x[0] >= 0 and x[1] >= 0 and x[2] <= 900 and x[3] <= 640 for x in boxes), boxes)
        check('긴 줄은 그 자리를 가운데에 — 색이 보인다', '#2f5d8a' in r['note'] and len(r['note']) < 200, r['note'])
        close()
        page.set_viewport_size({'width': 1300, 'height': 920})

        print('[7. 차트가 없는 문서]')
        page.evaluate("(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: p }))", 'guide/05-수식.md')
        until(page, lambda: page.locator('#lec-view h1', has_text='수식').count() > 0, ms=20000)
        page.wait_for_timeout(500)
        none = page.locator(ALL).count() == 0
        page.click('#lec-btn-ai')
        until(page, lambda: page.evaluate(MENU) is not None)
        items = page.evaluate(MENU) or []
        check('그림·차트가 없는 문서: 색 빼기 요청이 없다 (다듬기 점검은 있다)', none and not any('색 지정 빼기' in x for x in items) and any('다듬기 점검' in x for x in items), items)
        page.keyboard.press('Escape')

        print('[8. 끝]')
        changed = [str(f.relative_to(proj)) for f, data in before.items() if f.read_bytes() != data]
        check('예제 파일은 그대로 (보기만 했다)', not changed, changed)
        check('화면 스크립트 오류 없음', not errors, errors[:5])
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
