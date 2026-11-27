"""도해 스타일 (D212) — Mermaid·Graphviz 그림의 모양을 번호로 고른다.
- 그림 블록 안의 줄 '%% 스타일: N'(Graphviz '// 스타일: N')이 설정 diagram_style 보다 먼저. 이름('카드')·'style' 도. 모르는 값은 설정.
- 1 기본은 0.111 까지와 같다 (Mermaid 의 neo 모양, 띠 없음). 강조 표시 key·warn·muted 는 번호가 칠한다.
- 제목 상자(8·9·10): 줄을 바꾼 상자는 첫 줄이 제목 — 띠(또는 줄)가 제목과 내용 사이에서 끝난다. 한 줄 상자는 제목만.
- 단계 색(7): 묶음마다 다른 색, 안의 상자도 그 색. Graphviz 도 같은 번호.
- 우클릭 '도해 스타일…' 이 그 블록에 줄 하나를 쓰고 바꾸고 지운다 (머리 설정 '---' 아래, 들여쓰기 맞춤). 설정 창에서 기본 번호.
- 어두운 스타일에서도 강조 글자가 읽힌다. 화면 스크립트 오류 없음."""
import json
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop, until

DOC = """# 도해

## 줄 없음

```mermaid
flowchart LR
  A[시작] --> B[분석]:::key --> C[끝]
  B -.-> M[메모]:::muted
  C --> R[재조사]:::warn
```

## 카드

```mermaid
flowchart LR
  %% 스타일: 3
  A[시작] --> B[분석]:::key
```

## 이름으로

```mermaid
flowchart LR
  %% style: card
  A[시작] --> B[끝]
```

## 모르는 번호

```mermaid
flowchart LR
  %% 스타일: 99
  A[시작] --> B[끝]
```

## 제목 띠

```mermaid
flowchart LR
  %% 스타일: 8
  A[자료 수집<br>통계청·업계 보고서 12건] --> B[분석<br>수요 회귀 모형]:::key --> C[보고서]
```

## 제목 줄

```mermaid
flowchart LR
  %% 스타일: 10
  A[자료 수집<br>통계청·업계 보고서 12건] --> C[보고서]
```

## 단계 색

```mermaid
flowchart LR
  %% 스타일: 7
  subgraph 수집
    A[통계] --> B[보고서]
  end
  subgraph 분석
    C[수요] --> D[가격]
  end
  B --> C
```

## 머리 설정

```mermaid
---
title: 머리
---
flowchart LR
  A[가] --> B[나]
```

## Graphviz

```dot
digraph 가 {
  // 스타일: 8
  rankdir=LR
  A [label="자료 수집\\n통계 12건"]; B [label="분석\\n모형", class="key"]; C [label="끝"];
  A -> B -> C
}
```

```dot
digraph 나 {
  # style: 7
  subgraph cluster_a { label="수집"; A; B; A -> B }
  subgraph cluster_b { label="분석"; C; D; C -> D }
  B -> C
}
```

```dot
digraph 다 {
  A [class="key"]; A -> B
}
```
"""

STYLES = "() => [...document.querySelectorAll('#lec-view pre.mermaid, #lec-view pre.lec-chart')].map((n) => n.dataset.diagramStyle || '')"
FILL = """([i, sel]) => { const n = [...document.querySelectorAll('#lec-view pre.mermaid, #lec-view pre.lec-chart')][i]; const e = n && n.querySelector(sel);
  return e ? getComputedStyle(e).fill : null; }"""
RGB = lambda h: f'rgb({int(h[1:3], 16)}, {int(h[3:5], 16)}, {int(h[5:7], 16)})'   # noqa: E731
BAND = """(i) => { const n = [...document.querySelectorAll('#lec-view pre.mermaid')][i];
  return [...n.querySelectorAll('g.node')].map((g) => { const band = g.querySelector('.lec-title-band, .lec-title-rule'); const dt = g.querySelector('.lec-dt'); const p = dt && dt.parentElement;
    const br = p && p.querySelector('br'); let content = null;
    if (br) { const r = document.createRange(); r.setStartAfter(br); r.setEnd(p, p.childNodes.length); const rs = [...r.getClientRects()].filter((x) => x.height); content = rs.length ? Math.min(...rs.map((x) => x.top)) : null; }
    const tb = dt ? Math.max(...[...dt.getClientRects()].map((x) => x.bottom)) : null;
    const bb = band ? band.getBoundingClientRect().bottom : null;
    const shape = g.querySelector('rect.label-container, rect.basic');
    return { text: g.textContent.trim().slice(0, 8), band: !!band, bandBottom: bb, titleBottom: tb, contentTop: content, ink: dt ? getComputedStyle(dt).color : null,
      shapeFill: shape ? getComputedStyle(shape).fill : null, bandFill: band ? getComputedStyle(band).fill : null }; }); }"""

base = Path(tempfile.mkdtemp(prefix='lec-dstyles-'))
proj = base / '과제'
proj.mkdir()
doc = proj / '도해.md'
doc.write_text(DOC, encoding='utf-8', newline='\n')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False, 'theme': 'report', 'toc_visible': False}), encoding='utf-8')
src = lambda: doc.read_text(encoding='utf-8').replace('\r\n', '\n')   # noqa: E731

server, url, port = serve(proj, config)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1300, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        page.click('#lec-tree .row[data-doc="도해.md"]')

        def drawn():
            return until(page, lambda: page.locator('#lec-view pre.mermaid.mermaid-ok').count() == 8 and page.locator('#lec-view pre.lec-chart.chart-ok').count() == 3, ms=30000)

        drawn()
        print('[고른 번호]')
        st = page.evaluate(STYLES)
        check('줄 없음은 설정(1), 번호·이름(card → 3)·모르는 값(99 → 설정)', st[:4] == ['1', '3', '3', '1'], st)
        check('제목 띠 8·제목 줄 10·단계 색 7·머리 설정 아래 1, Graphviz 8·# style 7·줄 없음 1', st[4:] == ['8', '10', '7', '1', '8', '7', '1'], st)
        look = page.evaluate("() => [...document.querySelectorAll('#lec-view pre.mermaid')].slice(0, 2).map((n) => n.querySelector('g.node')?.dataset.look)")
        check('1 기본은 예전 모양 그대로 (Mermaid 의 neo), 3 카드는 classic', look == ['neo', 'classic'], look)
        check('1 기본에는 띠·줄을 더하지 않는다', page.locator('#lec-view pre.mermaid >> nth=0').locator('.lec-title-band, .lec-title-rule').count() == 0)

        print('[강조 표시]')
        key = page.evaluate(FILL, [0, 'g.node.key rect'])
        warn = page.evaluate(FILL, [0, 'g.node.warn rect'])
        muted = page.evaluate("() => getComputedStyle(document.querySelector('#lec-view pre.mermaid g.node.muted rect')).strokeDasharray")
        check('key 는 스타일의 진한 색(보고서 #17304f)으로 채운다', key == RGB('#17304f'), key)
        check('warn 은 옅은 주황, muted 는 점선', warn not in (None, key, 'rgb(255, 255, 255)') and muted not in (None, 'none'), (warn, muted))
        check('그림의 원문 파일은 그대로 (classDef 는 그릴 때만)', 'classDef' not in src())

        print('[제목 상자]')
        nodes = page.evaluate(BAND, 4)
        titled = [n for n in nodes if n['contentTop'] is not None]
        check('줄을 바꾼 상자마다 띠 하나', len(titled) == 2 and all(n['band'] for n in titled), nodes)
        check('띠는 제목 아래·내용 위에서 끝난다', all(n['titleBottom'] - 1 <= n['bandBottom'] <= n['contentTop'] + 1 for n in titled), titled)
        only = [n for n in nodes if n['contentTop'] is None]
        check('한 줄 상자(보고서)는 상자 전체가 띠 색', len(only) == 1 and only[0]['shapeFill'] == RGB('#17304f'), only)
        check('띠 위 제목 글자는 밝게 (진한 띠)', all(n['ink'] in ('rgb(245, 247, 250)',) for n in nodes), [n['ink'] for n in nodes])
        keyband = [n['bandFill'] for n in titled if n['text'].startswith('분석')]
        check('key 상자의 띠는 강조색 (다른 띠와 다르다)', keyband and keyband[0] != titled[0]['bandFill'], (keyband, titled[0]['bandFill']))
        rule = page.evaluate(BAND, 5)
        check('제목 줄(10): 띠 대신 가는 줄, 제목과 내용 사이', rule[0]['band'] and rule[0]['titleBottom'] - 1 <= rule[0]['bandBottom'] <= rule[0]['contentTop'] + 1, rule)

        print('[단계 색]')
        zones = page.evaluate("""() => { const n = [...document.querySelectorAll('#lec-view pre.mermaid')][6];
          return { frames: [...n.querySelectorAll('g.cluster > rect')].map((r) => getComputedStyle(r).fill), nodes: [...n.querySelectorAll('g.node')].map((g) => getComputedStyle(g.querySelector('rect')).stroke) }; }""")
        check('묶음마다 다른 색', len(set(zones['frames'])) == 2, zones)
        check('안의 상자는 그 묶음의 색 (묶음 둘 → 테두리 색 둘)', len(set(zones['nodes'])) == 2, zones)

        print('[Graphviz]')
        gv = page.evaluate("""() => { const [a, b2, c] = [...document.querySelectorAll('#lec-view pre.lec-chart svg')];
          const fill = (e) => e && getComputedStyle(e).fill;
          return { bands: a.querySelectorAll('.lec-title-band').length, key: fill(c.querySelector('g.node.key polygon, g.node.key ellipse')), styleScoped: (c.querySelector('style')?.textContent || '').startsWith('#' + c.id),
            clusters: [...b2.querySelectorAll('g.cluster > polygon')].map(fill), title: a.querySelector('g.node text')?.getAttribute('font-weight') }; }""")
        check('Graphviz 제목 띠: 줄을 바꾼 상자 둘에 띠, 제목은 굵게', gv['bands'] == 2 and gv['title'] == '700', gv)
        check('Graphviz key 도 진한 색, 그림의 CSS 는 그 그림 안으로 묶인다', gv['key'] == RGB('#17304f') and gv['styleScoped'], gv)
        check("Graphviz 단계 색('# style: 7'): 묶음마다 다른 색", len(set(gv['clusters'])) == 2, gv)
        bleed = page.evaluate("() => getComputedStyle(document.querySelector('#lec-view pre.mermaid g.node:not(.key) rect')).fill")
        check('Graphviz 의 CSS 가 다른 그림으로 번지지 않는다', bleed != RGB('#17304f'), bleed)

        print('[우클릭 — 줄 쓰기·바꾸기·지우기]')
        def styles_now():
            return page.evaluate(STYLES)

        def settle(i, want):
            """그 그림이 다시 그려져 그 번호가 될 때까지 (저장한 뒤 화면이 따라오기를)"""
            until(page, lambda: len(styles_now()) == 11 and styles_now()[i] == want, ms=12000)

        def open_styles(i):
            page.locator('#lec-view pre.mermaid, #lec-view pre.lec-chart').nth(i).click(button='right', position={'x': 5, 'y': 5})
            page.wait_for_selector('#lec-menu:not([hidden])', timeout=5000)
            page.locator('#lec-menu button', has_text='도해 스타일…').click()
            page.wait_for_selector('#lec-menu .menu-head:has-text("도해 스타일")', timeout=5000)

        def pick_style(i, label):
            open_styles(i)
            page.locator('#lec-menu button', has_text=label).first.click()

        pick_style(0, '8. 제목 띠')
        until(page, lambda: '```mermaid\nflowchart LR\n  %% 스타일: 8\n  A[시작]' in src(), ms=8000)
        check('줄이 없던 그림: 그림의 첫 줄(flowchart LR) 아래에, 다음 줄의 들여쓰기로 한 줄', '```mermaid\nflowchart LR\n  %% 스타일: 8\n  A[시작]' in src(), src()[:200])
        settle(0, '8')
        check('다시 그리면 그 번호', styles_now()[0] == '8', styles_now())
        pick_style(0, '2. 보고서 선')
        until(page, lambda: '%% 스타일: 2' in src(), ms=8000)
        check('있던 줄은 바꾼다 (줄은 하나), 다른 그림의 같은 줄(8)은 그대로', src().count('%% 스타일: 2') == 1 and src().count('%% 스타일: 8') == 1)
        settle(0, '2')
        open_styles(0)
        page.locator('#lec-menu button', has_text='설정 따르기').click()
        until(page, lambda: '%% 스타일: 2' not in src(), ms=8000)
        check("'설정 따르기' 는 그 줄만 지운다", '```mermaid\nflowchart LR\n  A[시작]' in src() and src().count('%% 스타일: 8') == 1)
        settle(0, '1')

        print('[메뉴를 연 뒤 원문이 바뀌면 쓰지 않는다]')
        open_styles(4)   # 제목 띠(8) 그림
        before = src()
        time.sleep(1.05)
        doc.write_text(before.replace('통계청·업계 보고서 12건', '통계청 보고서 12건'), encoding='utf-8', newline='\n')
        page.locator('#lec-menu button', has_text='3. 카드').first.click()
        until(page, lambda: page.locator('#lec-toast', has_text='저장하지 않았습니다').count() > 0, ms=8000)
        check('그 그림이 그사이 바뀌었으면 저장하지 않고 알린다 (다른 그림의 같은 줄도 건드리지 않는다)',
              page.locator('#lec-toast', has_text='저장하지 않았습니다').count() > 0 and src() == before.replace('통계청·업계 보고서 12건', '통계청 보고서 12건'), src()[:120])
        until(page, lambda: page.evaluate("() => document.querySelector('#lec-view').textContent.includes('통계청 보고서 12건')"), ms=10000)
        settle(4, '8')

        pick_style(7, '3. 카드')
        until(page, lambda: '---\ntitle: 머리\n---\nflowchart LR\n  %% 스타일: 3\n  A[가]' in src(), ms=8000)
        check("Mermaid 머리 설정('---')이 있으면 그 다음 첫 줄 아래에", '---\ntitle: 머리\n---\nflowchart LR\n  %% 스타일: 3\n  A[가]' in src(), src()[src().find('머리'):][:80])
        settle(7, '3')
        check('머리 설정과 함께 그려진다 (오류 없이 3)', styles_now()[7] == '3', styles_now())
        pick_style(10, '5. 선만')
        until(page, lambda: 'digraph 다 {\n  // 스타일: 5\n  A [class' in src(), ms=8000)
        check("Graphviz 는 '//' 줄", 'digraph 다 {\n  // 스타일: 5\n  A [class' in src(), src()[-80:])
        settle(10, '5')
        page.keyboard.press('Escape')
        page.locator('#lec-view h1').click()
        page.keyboard.press('Control+z')
        until(page, lambda: '// 스타일: 5' not in src(), ms=8000)
        check('Ctrl+Z 로 되돌린다', '// 스타일: 5' not in src())
        settle(10, '1')

        print('[설정 창 — 기본 번호]')
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open-settings', 'view'))")
        page.wait_for_selector('#lec-dstyle-preview pre.mermaid svg', timeout=15000)
        opts = page.eval_on_selector_all('#lec-dstyle option', 'os => os.map((o) => o.textContent)')
        check('번호 열 개, 1 기본이 골라져 있다', len(opts) == 10 and page.input_value('#lec-dstyle') == '1', opts)
        page.select_option('#lec-dstyle', '9')
        until(page, lambda: json.loads((config / 'config.json').read_text(encoding='utf-8')).get('diagram_style') == 9, ms=5000)
        check('고르면 설정 diagram_style 에 숫자로', json.loads((config / 'config.json').read_text(encoding='utf-8')).get('diagram_style') == 9)
        until(page, lambda: page.locator('#lec-dstyle-preview .lec-title-band').count() > 0, ms=8000)
        check('미리보기도 그 번호 (옅은 제목 띠)', page.locator('#lec-dstyle-preview .lec-title-band').count() > 0)
        page.keyboard.press('Escape')
        until(page, lambda: len(page.evaluate(STYLES)) == 11 and page.evaluate(STYLES)[0] == '9', ms=12000)
        st = page.evaluate(STYLES)
        check('줄 없는 그림은 새 기본으로 다시 그린다, 줄 있는 그림은 그대로', st[0] == '9' and st[1] == '3' and st[3] == '9' and st[4] == '8' and st[10] == '9', st)

        print('[어두운 스타일]')
        page.select_option('#lec-theme', 'dark')
        until(page, lambda: page.evaluate("() => document.documentElement.dataset.theme") == 'dark')
        drawn()
        until(page, lambda: page.evaluate(FILL, [0, 'g.node.key rect']) not in (None, RGB('#17304f')), ms=10000)
        dark = page.evaluate(BAND, 4)
        check('어두운 스타일: 진한 띠 위 글자가 띠와 대비된다', all(n['ink'] and n['bandFill'] != n['ink'] for n in dark if n['band']), dark)
        check('화면 스크립트 오류 없음', not errors, errors[:5])
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
