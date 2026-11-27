"""0.113 사람 시나리오 2 — 연구원 C 가 Claude 와 함께 회사 양식의 도해 스타일·색 조합을 만들어 팀 보고서에 쓴다 (D215). 차례대로:

1. Claude 가 그린 그림 하나가 classDef·init 으로 손수 꾸며져 있다 (회사 양식). 우클릭 '이 모양으로 내 도해 스타일 만들기…' → 요청 글이 터미널에
   (그 그림의 자리·안내·다음 번호 11·폴더). 안내 파일이 그 경로에 있다.
2. Claude(밖에서 쓰기)가 안내대로 '우리 회사.json' 을 쓴다 → 다시 불러오지 않아도 고르기 창에 11 '내 것'. 그 그림을 11 로 고른다.
3. Claude 가 이제 필요 없는 classDef·init 줄을 뺀다 → 그림은 그대로 11 의 모양.
4. 차트의 '이 색으로 내 색 조합 만들기…' → 다음 색 번호 9. Claude 가 '회사 색.json' → 색 조합 창에서 9 를 고른다 → 계열 색이 회사 색.
5. 팀 보고서 전체를 맞춘다 — 설정의 기본 모양을 내 것 11 로 → 줄 없는 그림이 모두 11. 메모 문서(줄 없음)도 11.
6. Claude 의 실수 — 번호 11 을 또 쓰고 CSS 를 넣은 '실수.json' → 설정 창에 고칠 것 두 줄, 11 은 앞 파일 그대로.
7. 어두운 스타일 — 내 색 조합의 진한 색이 밝게, 띠 위 글자가 읽힌다. 인쇄 화면에도 그림이 그대로.
8. 동료의 PC (폴더가 없다) — 기본 모양·색으로 그리고 표시 줄의 이름은 남는다. 폴더를 돌려놓으면 다시 11·9.
9. 원문은 고른 것과 Claude 가 고친 것뿐. 화면 스크립트 오류 없음."""
import json
import re
import shutil
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import ROOT, check, fails, report, serve, stop, until

FENCE = '```'
REPORT = f"""# 3분기 물류비 점검

## 1. 점검 흐름

그림 1. 점검 흐름

{FENCE}mermaid
%%{{init: {{'flowchart': {{'curve': 'stepAfter'}}}}}}%%
flowchart LR
  A[운임 자료<br>12개월] --> B[항목 분류<br>운송·보관·포장] --> C[원인 분석]:::key --> D[개선안]
  classDef default fill:#ffffff,stroke:#0b3d6e,stroke-width:1.6px,rx:3px
  classDef key fill:#0b3d6e,stroke:#0b3d6e,color:#ffffff
{FENCE}

## 2. 비용 구성

{FENCE}vega-lite
{{ "width": "container", "data": {{"values": [{{"항목": "운송", "비용": 52}}, {{"항목": "보관", "비용": 28}}, {{"항목": "포장", "비용": 20}}]}}, "mark": "bar",
  "encoding": {{"x": {{"field": "항목", "type": "nominal", "sort": null}}, "y": {{"field": "비용", "type": "quantitative"}},
  "color": {{"field": "항목", "type": "nominal", "sort": null, "scale": {{"range": ["#0b3d6e", "#e07b00", "#8a9aa9"]}}}}}} }}
{FENCE}

## 3. 조직

{FENCE}mermaid
flowchart TD
  P[물류팀] --> Q[운송 파트]
  P --> R[창고 파트]
{FENCE}
"""
MEMO = f"""# 메모

{FENCE}mermaid
flowchart LR
  X[질문] --> Y[답]
{FENCE}
"""
OURS = {'kind': 'style', 'number': 11, 'name': '우리 회사', 'tip': '흰 상자·남색 테두리·직각 선 — 팀 보고서', 'base': 2, 'corner': 3, 'border': 1.6, 'line': 'step'}
COLORS = {'kind': 'colors', 'number': 9, 'name': '회사 색', 'tip': '로고의 남색·주황·회색', 'series': ['#0b3d6e', '#e07b00', '#8a9aa9'], 'strong': '#0b3d6e', 'accent': '#e07b00'}
ALL = '#lec-view pre.mermaid, #lec-view pre.lec-chart'
MARKS = f"() => [...document.querySelectorAll('{ALL}')].map((n) => (n.dataset.diagramStyle || '-') + '/' + (n.dataset.diagramColors || '-'))"
RGB = lambda h: f'rgb({int(h[1:3], 16)}, {int(h[3:5], 16)}, {int(h[5:7], 16)})'   # noqa: E731
FILLS = "(i) => { const n = [...document.querySelectorAll('#lec-view pre.mermaid, #lec-view pre.lec-chart')][i]; return n ? [...n.querySelectorAll('g.mark-rect path')].map((e) => getComputedStyle(e).fill) : []; }"

base = Path(tempfile.mkdtemp(prefix='lec-scen113b-'))
proj = base / '과제'
proj.mkdir()
rep = proj / '보고서.md'
rep.write_text(REPORT, encoding='utf-8', newline='\n')
(proj / '메모.md').write_text(MEMO, encoding='utf-8', newline='\n')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False, 'theme': 'report', 'toc_visible': False}), encoding='utf-8')
folder = config / 'diagram-styles'
src = lambda: rep.read_text(encoding='utf-8').replace('\r\n', '\n')   # noqa: E731


def ext_write(text):
    """Claude 가 밖에서 고친다 (수정 시각이 바뀌게 1초 뒤)"""
    time.sleep(1.05)
    rep.write_text(text, encoding='utf-8', newline='\n')


def claude_writes(name, data):
    """Claude 가 안내대로 폴더에 파일 하나 (폴더가 없으면 만든다)"""
    folder.mkdir(exist_ok=True)
    (folder / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


server, url, port = serve(proj, config)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1280, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        page.evaluate("() => import('/static/js/store.js').then((m) => { window.__pasted = []; m.on('term-paste', (x) => window.__pasted.push(x)); })")

        def marks():
            return page.evaluate(MARKS)

        def open_doc(name, mermaid, charts):
            page.click(f'#lec-tree .row[data-doc="{name}"]')
            until(page, lambda: page.locator('#lec-view pre.mermaid.mermaid-ok').count() == mermaid and page.locator('#lec-view pre.lec-chart.chart-ok').count() == charts, ms=30000)

        def picker(i, item, count):
            page.locator(ALL).nth(i).click(button='right', position={'x': 5, 'y': 5})
            page.wait_for_selector('#lec-menu:not([hidden])', timeout=5000)
            page.locator('#lec-menu button', has_text=item).first.click()
            page.wait_for_selector('#lec-dpick:not([hidden])', timeout=5000)
            until(page, lambda: page.locator('#lec-dpick-grid.dpick-done').count() == 1 and page.locator('#lec-dpick .dpick-card').count() == count, ms=30000)

        def ask(i, item):
            n = page.evaluate("() => window.__pasted.length")
            page.locator(ALL).nth(i).click(button='right', position={'x': 5, 'y': 5})
            page.wait_for_selector('#lec-menu:not([hidden])', timeout=5000)
            page.locator('#lec-menu button', has_text=item).first.click()
            until(page, lambda: page.evaluate("() => window.__pasted.length") > n, ms=5000)
            return page.evaluate("() => window.__pasted.at(-1)")

        print('[1. 손수 꾸민 그림 — 내 도해 스타일 만들기 요청]')
        open_doc('보고서.md', 2, 1)
        check('처음은 모두 기본 (손수 꾸민 classDef 가 보인다)', marks() == ['1/1', '-/1', '1/1'], marks())
        text = ask(0, '이 모양으로 내 도해 스타일 만들기…')
        guide = re.search(r'안내\((.+?)\)', text)
        check('요청 글: 그 그림의 자리(7~13행)·다음 번호 11·폴더', '@보고서.md 7~13행' in text and '번호는 11' in text and str(folder) in text, text)
        check('요청 글의 안내 파일이 그 경로에 있다 (Claude 가 읽을 수 있다)', bool(guide) and Path(guide.group(1)).is_file() and 'diagram-styles' in guide.group(1), guide and guide.group(1))
        check('요청만 했다 — 파일·문서는 그대로', not folder.exists() and src() == REPORT)

        print('[2. Claude 가 만든 11 — 다시 불러오지 않고 고르기 창에]')
        claude_writes('우리 회사.json', OURS)
        picker(0, '도해 스타일…', 11)
        card = page.locator('#lec-dpick .dpick-card[data-n="11"]')
        check("고르기 창에 11 '우리 회사' 내 것", card.count() == 1 and '우리 회사' in card.inner_text() and '내 것' in card.inner_text(), card.inner_text() if card.count() else '')
        card.click()
        until(page, lambda: '%% 스타일: 11 우리 회사\n' in src(), ms=8000)
        check("그 그림에 '%% 스타일: 11 우리 회사'", 'flowchart LR\n  %% 스타일: 11 우리 회사\n  A[운임 자료' in src(), src()[src().find('init'):][:160])
        until(page, lambda: marks()[0] == '11/1', ms=12000)

        print('[3. Claude 가 classDef·init 을 뺀다]')
        cleaned = src().replace("%%{init: {'flowchart': {'curve': 'stepAfter'}}}%%\n", '').replace('  classDef default fill:#ffffff,stroke:#0b3d6e,stroke-width:1.6px,rx:3px\n  classDef key fill:#0b3d6e,stroke:#0b3d6e,color:#ffffff\n', '')
        ext_write(cleaned)
        until(page, lambda: page.evaluate("() => import('/static/js/store.js').then((m) => !(m.S.pane.source?.lines || ['classDef']).join(' ').includes('classDef'))") and page.locator('#lec-view pre.mermaid.mermaid-ok').count() == 2, ms=15000)   # 화면이 새 원문을 읽은 뒤
        until(page, lambda: marks()[0] == '11/1', ms=12000)
        rx = page.evaluate("() => getComputedStyle(document.querySelector('#lec-view pre.mermaid g.node:not(.key) rect')).rx")
        check('classDef 없이도 11 의 모양 (모서리 3px, 테두리 1.6px)', rx == '3px' and page.evaluate("() => getComputedStyle(document.querySelector('#lec-view pre.mermaid g.node:not(.key) rect')).strokeWidth") == '1.6px', rx)

        print('[4. 차트의 색 — 내 색 조합 9]')
        text = ask(1, '이 색으로 내 색 조합 만들기…')
        check('요청 글: 내 색 조합, 다음 색 번호 9', '내 색 조합' in text and '번호는 9' in text and '@보고서.md 15~19행' in text, text)
        claude_writes('회사 색.json', COLORS)
        picker(1, '색 조합…', 9)
        page.locator('#lec-dpick .dpick-card[data-n="9"]').click()
        until(page, lambda: '```vega-lite\n// 색: 9 회사 색\n{' in src(), ms=8000)
        check("차트 맨 앞에 '// 색: 9 회사 색'", '```vega-lite\n// 색: 9 회사 색\n{' in src())
        until(page, lambda: marks()[1] == '-/9', ms=12000)
        check('차트는 자기 range 를 두었으니 그 색 그대로 (색 조합보다 먼저)', page.evaluate(FILLS, 1)[:1] == [RGB('#0b3d6e')], page.evaluate(FILLS, 1))
        ext_write(src().replace(', "scale": {"range": ["#0b3d6e", "#e07b00", "#8a9aa9"]}', ''))
        until(page, lambda: page.evaluate(FILLS, 1)[:3] == [RGB('#0b3d6e'), RGB('#e07b00'), RGB('#8a9aa9')] and '"range"' not in src(), ms=15000)
        check('Claude 가 range 를 빼도 같은 색 — 내 색 조합 9 가 칠한다', page.evaluate(FILLS, 1)[:3] == [RGB('#0b3d6e'), RGB('#e07b00'), RGB('#8a9aa9')], page.evaluate(FILLS, 1))

        print('[5. 팀 보고서 전체 — 기본 모양을 11 로]')
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open-settings', 'view'))")
        page.wait_for_selector('#lec-dstyle', state='visible', timeout=8000)
        page.select_option('#lec-dstyle', '11')
        page.keyboard.press('Escape')
        until(page, lambda: marks()[2] == '11/1', ms=15000)
        check('줄 없는 조직도도 11', marks() == ['11/1', '-/9', '11/1'], marks())
        open_doc('메모.md', 1, 0)
        check('다른 문서(메모)도 11', marks() == ['11/1'], marks())
        open_doc('보고서.md', 2, 1)

        print('[6. Claude 의 실수 — 같은 번호, CSS]')
        claude_writes('실수.json', {'kind': 'style', 'number': 11, 'name': '두 번째', 'css': 'body { display: none }'})
        claude_writes('넘침.json', {'kind': 'style', 'number': 12, 'name': '넘침', 'corner': 300, 'line': 'zigzag'})
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open-settings', 'view'))")
        page.wait_for_selector('#lec-mydiag', state='visible', timeout=8000)
        until(page, lambda: '실수.json' in page.locator('#lec-mydiag').inner_text(), ms=10000)
        info = page.locator('#lec-mydiag').inner_text()
        check('설정 창의 고칠 것 — 겹친 번호, 범위 밖의 값·모르는 값', '실수.json' in info and '11' in info and '넘침.json' in info and 'corner' in info and 'line' in info, info)
        check('11 은 앞 파일(우리 회사) 그대로, 12 는 값을 빼고 남는다', page.evaluate("() => [...document.querySelectorAll('#lec-dstyle optgroup option')].map((o) => o.textContent)") == ['11. 우리 회사', '12. 넘침'],
              page.evaluate("() => [...document.querySelectorAll('#lec-dstyle optgroup option')].map((o) => o.textContent)"))
        page.keyboard.press('Escape')
        check('본문은 그대로 보인다 (CSS 가 듣지 않는다)', page.locator('#lec-view h1').is_visible())

        print('[7. 어두운 스타일·인쇄]')
        page.select_option('#lec-theme', 'dark')
        until(page, lambda: page.evaluate("() => document.documentElement.dataset.theme") == 'dark')
        until(page, lambda: page.locator('#lec-view pre.mermaid.mermaid-ok').count() == 2 and page.locator('#lec-view pre.lec-chart.chart-ok').count() == 1, ms=30000)
        until(page, lambda: page.evaluate(FILLS, 1)[:1] not in ([], [RGB('#0b3d6e')]), ms=12000)
        dark = page.evaluate(FILLS, 1)
        lum = [sum(int(x) for x in re.findall(r'\d+', c)[:3]) / 3 for c in dark]
        check('어두운 스타일 — 내 색 조합의 진한 남색이 밝게', dark and lum[0] > 0x3d, dark)
        page.emulate_media(media='print')
        page.wait_for_timeout(300)
        check('인쇄 화면에도 그림·차트 셋', page.locator('#lec-view pre.mermaid svg, #lec-view pre.lec-chart svg').count() == 3)
        page.emulate_media(media='screen')
        page.select_option('#lec-theme', 'report')
        until(page, lambda: page.evaluate("() => document.documentElement.dataset.theme") == 'report')

        print('[8. 동료의 PC — 폴더가 없다]')
        hold = base / '옮겨 둠'
        shutil.move(str(folder), str(hold))
        until(page, lambda: marks() == ['1/1', '-/1', '1/1'], ms=15000)
        check('모르는 11·9 — 기본 모양·색 (설정 11 도 1 로)', marks() == ['1/1', '-/1', '1/1'], marks())
        check('표시 줄의 이름은 남아 무엇이었는지 안다', '%% 스타일: 11 우리 회사' in src() and '// 색: 9 회사 색' in src())
        shutil.move(str(hold), str(folder))
        until(page, lambda: marks() == ['11/1', '-/9', '11/1'], ms=15000)
        check('폴더를 돌려놓으면 다시 11·9', marks() == ['11/1', '-/9', '11/1'], marks())

        print('[9. 원문]')
        final = src()
        want = REPORT.replace("%%{init: {'flowchart': {'curve': 'stepAfter'}}}%%\n", '')
        want = want.replace('  classDef default fill:#ffffff,stroke:#0b3d6e,stroke-width:1.6px,rx:3px\n  classDef key fill:#0b3d6e,stroke:#0b3d6e,color:#ffffff\n', '')
        want = want.replace('flowchart LR\n  A[운임 자료', 'flowchart LR\n  %% 스타일: 11 우리 회사\n  A[운임 자료', 1)
        want = want.replace('```vega-lite\n{', '```vega-lite\n// 색: 9 회사 색\n{', 1).replace(', "scale": {"range": ["#0b3d6e", "#e07b00", "#8a9aa9"]}', '')
        check('바뀐 것은 고른 표시 줄 둘과 Claude 가 뺀 줄뿐', final == want, [ln for ln in final.split('\n') if ln not in want.split('\n')][:5])
        check('Lectern 은 폴더의 파일을 고치지 않았다', json.loads((folder / '우리 회사.json').read_text(encoding='utf-8')) == OURS and len(list(folder.iterdir())) == 4)
        check('화면 스크립트 오류 없음', not errors, errors[:5])
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
