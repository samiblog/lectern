"""0.112 사람 시나리오 2 — 임의의 사용자 (D212·D213). 시드마다 동작을 마구 섞고 걸음마다 지켜야 할 것을 본다:

- 그려진 그림·차트마다 모양·색 번호 = 원문에서 따로 계산한 값 (블록의 표시 줄 > 코드 블록 밖의 '<!-- 도해: … -->' > 설정).
- 그림이 모두 그려진다 (원문을 보여 주는 오류 칸이 없다). 제목 상자(8·9)의 그림은 줄을 바꾼 상자마다 띠 하나.
- 블록마다 같은 열쇠(스타일·색)의 표시는 하나뿐. 원문에서 표시 줄·방향 글자·문서의 줄을 걷어 내면 처음 문서와 같다.
- 화면 스크립트 오류가 없다.

동작: 우클릭 도해 스타일·색 조합·기본 따르기·방향 바꾸기, Claude(밖에서)가 표시 줄을 쓰거나(번호·이름·영어·한 줄에 둘) 문서의 줄을 넣고 바꾸고 지우기,
설정의 기본 번호, 스타일 바꾸기, Ctrl+Z·Ctrl+Y. 시드를 주면 그것만 (python scen_112b.py 7)"""
import json
import random
import re
import sys
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop, until

STEPS = 30
DOC = """# 주간 그림

여러 그림과 차트가 있는 문서.

```mermaid
flowchart LR
  A[수집<br>통계 12건] --> B[분석<br>수요 모형]:::key --> C[보고]
```

```mermaid
flowchart LR
  subgraph 광산
    M1[칠레] --> M2[페루]
  end
  subgraph 제련
    S1[중국]:::warn --> S2[국내]
  end
  M2 --> S1
```

```mermaid
---
title: 머리 설정
---
flowchart TD
  X[시작] --> Y{충분한가}
  Y -- 예 --> Z[끝]
```

```mermaid
sequenceDiagram
  participant U as 사람
  participant C as Claude
  U->>C: 요청
```

```vega-lite
{ "data": {"values": [{"k": "a", "v": 3}, {"k": "b", "v": 2}, {"k": "c", "v": 1}]}, "mark": "bar",
  "encoding": {"x": {"field": "k", "type": "nominal"}, "y": {"field": "v", "type": "quantitative"}, "color": {"field": "k", "type": "nominal"}} }
```

```echarts
{ "xAxis": {"type": "category", "data": ["a", "b"]}, "yAxis": {"type": "value"}, "series": [{"type": "bar", "data": [1, 2]}] }
```

```dot
digraph g {
  가 -> 나 [label="다음"]; 나 -> 다
}
```
"""
BR_NODES = {0: 2}   # 제목 상자가 될 그림 — 블록 차례: 줄을 바꾼 상자 수
STYLE_NAMES = {'기본': 1, 'default': 1, '보고서선': 2, 'report': 2, '카드': 3, 'card': 3, '진한채움': 4, 'solid': 4, '선만': 5, '손그림': 6, 'sketch': 6,
               '단계색': 7, 'zones': 7, '제목띠': 8, 'band': 8, '옅은제목띠': 9, 'tint': 9, '제목줄': 10, 'rule': 10}   # i18n-ok
COLOR_NAMES = {'문서스타일': 1, '보고서남색': 2, 'navy': 2, '회색+강조': 3, 'gray': 3, '선명한구분': 4, 'vivid': 4, '색약친화': 5, 'safe': 5,
               '따뜻한': 6, 'warm': 6, '차가운': 7, 'cool': 7, '파스텔': 8, 'pastel': 8}   # i18n-ok
LEAD = {'mermaid': re.compile(r'^(\s*)%%(?!\{)[ \t]*(.*)$'), 'dot': re.compile(r'^(\s*)(?://|#)[ \t]*(.*)$'), 'chart': re.compile(r'^(\s*)//[ \t]*(.*)$')}
TOKEN = re.compile(r'^(스타일|style|색\s*조합|색|colou?rs?|palette)(?:\s*[:：=]\s*|\s+)(.+?)\s*$', re.I)   # i18n-ok
DOCLINE = re.compile(r'^[ \t]*<!--[ \t]*(?:도해|diagrams?)[ \t]*[:：][ \t]*(.*?)[ \t]*-->[ \t]*$', re.I)   # i18n-ok
ALL = '#lec-view pre.mermaid, #lec-view pre.lec-chart, #lec-view .diagram-error'
MARKS = f"() => [...document.querySelectorAll('{ALL}')].map((n) => n.classList.contains('diagram-error') ? 'ERR' : (n.dataset.diagramStyle || '-') + '/' + (n.dataset.diagramColors || '-'))"


def number(value, names, top):
    v = value.strip()
    m = re.match(r'^(\d+)', v)
    if m:
        n = int(m.group(1))
        return n if 1 <= n <= top else 0
    return names.get(re.sub(r'[\s_-]+', '', v.lower()), 0)


def blocks(text):
    """[(kind, 여는 줄 차례, 안의 줄들)] — 펜스 블록 중 그림·차트"""
    lines = text.split('\n')
    out, i = [], 0
    while i < len(lines):
        m = re.match(r'^```(\w[\w-]*)', lines[i])
        if not m:
            i += 1
            continue
        j = i + 1
        while j < len(lines) and not lines[j].startswith('```'):
            j += 1
        lang = m.group(1)
        kind = 'mermaid' if lang == 'mermaid' else 'dot' if lang in ('dot', 'graphviz') else 'chart' if lang in ('vega-lite', 'echarts', 'plotly') else ''
        if kind:
            out.append((kind, i, lines[i + 1:j]))
        i = j + 1
    return out


def block_marks(kind, body):
    got = {'style': '', 'colors': ''}
    for line in body:
        m = LEAD[kind].match(line)
        if not m:
            continue
        for raw in re.split(r'\s*[·,;]\s*', m.group(2)):
            x = TOKEN.match(raw) if raw else None
            if x:
                key = 'style' if x.group(1).lower() in ('스타일', 'style') else 'colors'   # i18n-ok
                got[key] = got[key] or x.group(2)
    return got


def doc_marks(text):
    out = {'style': 0, 'colors': 0}
    fence = ''
    for line in text.split('\n'):
        f = re.match(r'^\s*(`{3,}|~{3,})', line)
        if f and (not fence or f.group(1)[0] == fence[0]):
            fence = '' if fence else f.group(1)
            continue
        if fence:
            continue
        m = DOCLINE.match(line)
        if m:
            for raw in re.split(r'\s*[·,;]\s*', m.group(1)):
                x = TOKEN.match(raw)
                if x:
                    key = 'style' if x.group(1).lower() in ('스타일', 'style') else 'colors'   # i18n-ok
                    out[key] = out[key] or (number(x.group(2), STYLE_NAMES, 10) if key == 'style' else number(x.group(2), COLOR_NAMES, 8))
            break
    return out


def expected(text, setting):
    d = doc_marks(text)
    out = []
    for kind, _, body in blocks(text):
        b = block_marks(kind, body)
        colors = number(b['colors'], COLOR_NAMES, 8) or d['colors'] or setting['colors']
        if kind == 'chart':
            out.append(f'-/{colors}')
        else:
            style = number(b['style'], STYLE_NAMES, 10) or d['style'] or setting['style']
            out.append(f'{style}/{colors}')
    return out


def skeleton(text):
    """표시 줄·방향 글자·문서의 줄을 걷어 낸 원문 — 처음 문서와 같아야 한다"""
    out = []
    kinds = {i: k for k, i, _ in blocks(text)}
    kind = ''
    for n, line in enumerate(text.split('\n')):
        if n in kinds:
            kind = kinds[n]
        elif line.startswith('```'):
            kind = ''
        if DOCLINE.match(line):
            continue
        if kind and LEAD[kind].match(line) and any(TOKEN.match(r) for r in re.split(r'\s*[·,;]\s*', LEAD[kind].match(line).group(2)) if r):
            continue
        if re.match(r'^\s*rankdir\s*=', line):
            continue
        line = re.sub(r'^(\s*)(flowchart|graph)\s+(LR|RL|TD|TB|BT)\b', r'\1\2 *', line)
        out.append(line)
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(out))


def run(seed):
    rnd = random.Random(seed)
    base = Path(tempfile.mkdtemp(prefix=f'lec-scen112b-{seed}-'))
    proj = base / '과제'
    proj.mkdir()
    doc = proj / '그림.md'
    doc.write_text(DOC, encoding='utf-8', newline='\n')
    config = base / 'config'
    config.mkdir()
    (config / 'config.json').write_text(json.dumps({'work_alerts': False, 'theme': 'report', 'toc_visible': False}), encoding='utf-8')
    src = lambda: doc.read_text(encoding='utf-8').replace('\r\n', '\n')  # noqa: E731
    first = skeleton(DOC)
    server, url, port = serve(proj, config)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={'width': 1300, 'height': 900})
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)[:300]))
            page.goto(url)
            page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
            page.click('#lec-tree .row[data-doc="그림.md"]')
            until(page, lambda: page.locator('#lec-view pre.mermaid.mermaid-ok').count() == 4, ms=30000)

            def setting():
                """서버가 들고 있는 설정 — 파일을 자꾸 열어 읽으면 Windows 에서 서버가 바꿔 끼우지 못한다 (파일은 설정을 바꾼 걸음에서 따로 본다)"""
                c = page.evaluate("() => fetch('/api/config').then((r) => r.json())")
                return {'style': c.get('diagram_style', 1), 'colors': c.get('diagram_colors', 1)}

            def setting_file():
                for _ in range(20):
                    try:
                        c = json.loads((config / 'config.json').read_text(encoding='utf-8'))
                        return {'style': c.get('diagram_style', 1), 'colors': c.get('diagram_colors', 1)}
                    except (OSError, ValueError):   # 서버가 바꿔 끼우는 순간
                        time.sleep(0.1)
                return None

            def ext_write(text):
                time.sleep(1.05)
                doc.write_text(text, encoding='utf-8', newline='\n')

            def menu(i, item, pick=None):
                page.locator(ALL).nth(i).click(button='right', position={'x': 5, 'y': 5})
                page.wait_for_selector('#lec-menu:not([hidden])', timeout=5000)
                btn = page.locator('#lec-menu button', has_text=item)
                if not btn.count():
                    page.keyboard.press('Escape')
                    return False
                btn.first.click()
                if pick:   # 고르기 창 (D214) — 번호 칸
                    page.wait_for_selector('#lec-dpick:not([hidden]) .dpick-card', timeout=5000)
                    target = page.locator(f'#lec-dpick .dpick-card[data-n="{pick}"]')
                    if not target.count():
                        page.keyboard.press('Escape')
                        return False
                    target.first.click()
                return True

            def wait_file(before):
                until(page, lambda: src() != before, ms=6000)

            kinds = [k for k, _, _ in blocks(DOC)]
            ops = ['style', 'colors', 'follow', 'flip', 'ext_mark', 'ext_doc', 'setting', 'theme', 'undo']
            changed = 0
            for step in range(STEPS):
                op = rnd.choice(ops)
                did = op
                try:
                    before = src()
                    if op in ('style', 'colors'):
                        cand = [i for i, k in enumerate(kinds) if op == 'colors' or k != 'chart']
                        i = rnd.choice(cand)
                        n = rnd.randint(1, 10 if op == 'style' else 8)
                        did = f'{op} #{i} → {n}'
                        if menu(i, '도해 스타일…' if op == 'style' else '색 조합…', str(n)):
                            wait_file(before)
                    elif op == 'follow':
                        i = rnd.randrange(len(kinds))
                        key = rnd.choice(['도해 스타일…', '색 조합…']) if kinds[i] != 'chart' else '색 조합…'
                        did = f'follow #{i} {key}'
                        page.locator(ALL).nth(i).click(button='right', position={'x': 5, 'y': 5})
                        page.wait_for_selector('#lec-menu:not([hidden])', timeout=5000)
                        page.locator('#lec-menu button', has_text=key).first.click()
                        page.wait_for_selector('#lec-dpick:not([hidden]) .dpick-card', timeout=5000)
                        follow = page.locator('#lec-dpick-follow:visible')
                        if follow.count():
                            follow.first.click()
                            wait_file(before)
                        else:
                            page.keyboard.press('Escape')
                    elif op == 'flip':
                        i = rnd.choice([0, 1, 2, 6])
                        did = f'flip #{i}'
                        if menu(i, '로 바꾸기'):
                            wait_file(before)
                    elif op == 'ext_mark':
                        lines = before.split('\n')
                        bl = blocks(before)
                        k = rnd.randrange(len(bl))
                        kind, at, body = bl[k]
                        lead = '%%' if kind == 'mermaid' else '//'
                        style = rnd.choice(['3', '8', '카드', 'card', 'band', '10'])
                        colors = rnd.choice(['2', '5', 'warm', '보고서 남색', 'pastel'])
                        parts = [] if kind == 'chart' else [f'{rnd.choice(["스타일", "style"])}: {style}']   # i18n-ok
                        parts.append(f'{rnd.choice(["색", "colors"])}: {colors}')   # i18n-ok
                        if kind != 'chart' and rnd.random() < 0.4:
                            parts = parts[:1]
                        # 있는 표시 줄을 지우고 새로 한 줄 (Claude 가 안내대로)
                        start, end = at + 1, at + 1 + len(body)
                        inside = [ln for ln in lines[start:end] if not (LEAD[kind].match(ln) and any(TOKEN.match(r) for r in re.split(r'\s*[·,;]\s*', LEAD[kind].match(ln).group(2)) if r))]
                        if kind == 'chart':
                            inside = [f'{lead} {" · ".join(parts)}'] + inside
                        else:
                            head = 0
                            if inside and inside[0].strip() == '---':
                                head = next(j for j in range(1, len(inside)) if inside[j].strip() == '---') + 1
                            inside.insert(head + 1, f'  {lead} {" · ".join(parts)}')
                        lines[start:end] = inside
                        did = f'ext_mark #{k} {parts}'
                        ext_write('\n'.join(lines))
                    elif op == 'ext_doc':
                        text = '\n'.join(ln for ln in before.split('\n') if not DOCLINE.match(ln))
                        text = re.sub(r'\n{3,}', '\n\n', text)
                        if rnd.random() < 0.7:
                            line = f'<!-- {rnd.choice(["도해", "diagram"])}: {rnd.choice(["스타일 2 · 색 2", "색 7", "스타일 9", "style 3 · colors 4", "스타일 10 · 색 3"])} -->'   # i18n-ok
                            text = text.replace('# 주간 그림\n', f'# 주간 그림\n\n{line}\n', 1)
                            did = f'ext_doc {line}'
                        else:
                            did = 'ext_doc 지우기'   # i18n-ok
                        if text != before:
                            ext_write(text)
                    elif op == 'setting':
                        s, c = rnd.randint(1, 10), rnd.randint(1, 8)
                        did = f'setting {s}·{c}'
                        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open-settings', 'view'))")
                        page.wait_for_selector('#lec-dstyle', state='visible', timeout=8000)
                        page.select_option('#lec-dstyle', str(s))
                        page.select_option('#lec-dcolors', str(c))
                        until(page, lambda: setting() == {'style': s, 'colors': c}, ms=15000)   # 앞의 고르기가 문서를 다시 그리는 동안 뒤의 저장은 늦게 나간다
                        time.sleep(0.3)
                        if setting_file() != {'style': s, 'colors': c}:
                            check(f'[{seed}] {step} {did} — 설정 파일에 둘 다', False, (setting(), setting_file()))
                        page.keyboard.press('Escape')
                    elif op == 'theme':
                        want = rnd.choice(['report', 'dark', 'paper', 'github', 'nord'])
                        did = f'theme {want}'
                        page.select_option('#lec-theme', want)
                        until(page, lambda: page.evaluate('() => document.documentElement.dataset.theme') == want)
                    elif op == 'undo':
                        key = rnd.choice(['Control+z', 'Control+y'])
                        did = f'undo {key}'
                        page.locator('#lec-view h1').click()
                        page.keyboard.press(key)
                except Exception as exc:   # noqa: BLE001 — 한 걸음이 멈춰도 다음 걸음으로
                    check(f'[{seed}] {step} {did} — 멈추지 않는다', False, str(exc)[:200])
                    page.keyboard.press('Escape')
                page.wait_for_timeout(300)
                text = src()
                changed += text != before
                print(f'    {step:2} {did}{"  (원문 바뀜)" if text != before else ""}', flush=True)
                ok = until(page, lambda: page.evaluate(MARKS) == expected(src(), setting()), ms=15000)
                text = src()
                want = expected(text, setting())
                if not ok:
                    check(f'[{seed}] {step} {did} — 번호가 원문과 같다', False, (page.evaluate(MARKS), want))
                if 'ERR' in page.evaluate(MARKS):
                    check(f'[{seed}] {step} {did} — 모두 그려진다', False, page.evaluate(MARKS))
                bands = page.evaluate("() => { const n = document.querySelector('#lec-view pre.mermaid'); return n ? n.querySelectorAll('.lec-title-band, .lec-title-rule').length : -1; }")
                if want[0].split('/')[0] in ('8', '9', '10') and bands != BR_NODES[0]:
                    check(f'[{seed}] {step} {did} — 제목 상자의 띠', False, (want[0], bands))
                for kind, _, body in blocks(text):
                    for key in ('style', 'colors'):
                        cnt = sum(1 for ln in body if LEAD[kind].match(ln) and any(
                            (TOKEN.match(r) and (('style' if TOKEN.match(r).group(1).lower() in ('스타일', 'style') else 'colors') == key))   # i18n-ok
                            for r in re.split(r'\s*[·,;]\s*', LEAD[kind].match(ln).group(2)) if r))
                        if cnt > 1:
                            check(f'[{seed}] {step} {did} — 같은 열쇠의 표시는 하나', False, body)
                if skeleton(text) != first:
                    check(f'[{seed}] {step} {did} — 표시 줄·방향·문서의 줄 말고는 그대로', False, [ln for ln in skeleton(text).split('\n') if ln not in first.split('\n')][:4])
            check(f'[{seed}] {STEPS}걸음 — 지킬 것을 모두 지켰다 (원문이 바뀐 걸음 {changed})', not [f for f in fails if f.startswith(f'[{seed}]')])
            check(f'[{seed}] 화면 스크립트 오류 없음', not errors, errors[:5])
            browser.close()
    except Exception:   # noqa: BLE001
        traceback.print_exc()
        fails.append(f'[{seed}] 점검이 멈춤')
    finally:
        stop(server, base)


if __name__ == '__main__':   # real_claude 시험이 원문 읽기(blocks·expected)를 불러 쓴다
    for s in [int(x) for x in sys.argv[1:]] or [1, 2, 3]:
        print(f'[시드 {s}]')
        run(s)
    report()
