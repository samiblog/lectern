"""0.113 임의 시나리오 — 내 도해 스타일 파일을 만들고 고치고 지우고 깨뜨리는 사람과, 그 사이에 고르기 창·표시 줄·설정으로 번호를 고르는 사람 (D214·D215).
시드마다 26걸음. 걸음마다 원문·폴더·설정에서 따로 계산한 번호(서버의 거르기 mydiagrams.load 를 그대로 쓴다)와 화면이 같아질 때까지 기다린다.
지킬 것: 그린 번호 = 블록의 줄(있는 번호면) → 설정(있는 번호면) → 1. 고르기 창의 칸 = 기본 + 걸러진 내 것. 그림 오류·화면 스크립트 오류 없음.
  python scen_113c.py [시드…]"""
import json
import random
import re
import sys
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import ROOT, check, fails, report, serve, stop, until

sys.path.insert(0, str(ROOT))
from lectern import mydiagrams   # noqa: E402

FENCE = '```'
DOC = f"""# 그림

{FENCE}mermaid
flowchart LR
  A[가<br>설명] --> B[나]:::key --> C[다]
{FENCE}

{FENCE}mermaid
flowchart TD
  subgraph 하나
    P --> Q
  end
  subgraph 둘
    R --> S
  end
  Q --> R
{FENCE}

{FENCE}dot
digraph g {{
  가 -> 나; 나 -> 다
}}
{FENCE}

{FENCE}vega-lite
{{ "data": {{"values": [{{"k": "a", "v": 3}}, {{"k": "b", "v": 2}}]}}, "mark": "bar",
  "encoding": {{"x": {{"field": "k", "type": "nominal"}}, "y": {{"field": "v", "type": "quantitative"}}, "color": {{"field": "k", "type": "nominal"}}}} }}
{FENCE}
"""
KINDS = ['mermaid', 'mermaid', 'dot', 'chart']
LEAD = {'mermaid': re.compile(r'^\s*%%(?!\{)\s*(.*)$'), 'dot': re.compile(r'^\s*(?://|#)\s*(.*)$'), 'chart': re.compile(r'^\s*//\s*(.*)$')}
TOKEN = re.compile(r'^(스타일|style|색|colou?rs?)\s*[:：=]?\s*(.+?)\s*$', re.I)   # i18n-ok
NAMES = ['회사', '팀 보고', '발표용', '논문 선', 'Blue', '초안']   # i18n-ok (파일 이름)
ALL = '#lec-view pre.mermaid, #lec-view pre.lec-chart, #lec-view .diagram-error'
MARKS = f"() => [...document.querySelectorAll('{ALL}')].map((n) => n.classList.contains('diagram-error') ? 'ERR' : (n.dataset.diagramStyle || '-') + '/' + (n.dataset.diagramColors || '-'))"
STEPS = 26


def blocks(text):
    """[(kind, 여는 줄 차례, 안의 줄들)]"""
    lines = text.split('\n')
    out, i, k = [], 0, 0
    while i < len(lines):
        m = re.match(r'^```(mermaid|dot|vega-lite)\s*$', lines[i])
        if m:
            j = i + 1
            while not lines[j].startswith('```'):
                j += 1
            out.append((KINDS[k], i, lines[i + 1:j]))
            k += 1
            i = j
        i += 1
    return out


def marks_of(kind, body):
    out = {'style': '', 'colors': ''}
    for ln in body:
        m = LEAD[kind].match(ln)
        if not m:
            continue
        for part in re.split(r'\s*[·,;]\s*', m.group(1)):
            t = TOKEN.match(part)
            if t:
                key = 'style' if t.group(1).lower() in ('스타일', 'style') else 'colors'   # i18n-ok
                out[key] = out[key] or t.group(2)
    return out


def lead_number(value):
    m = re.match(r'^(\d+)', value.strip())
    return int(m.group(1)) if m else 0


def expected(text, folder, setting):
    got = mydiagrams.load(folder)
    styles = set(range(1, 11)) | {s['n'] for s in got['styles']}
    colors = set(range(1, 9)) | {c['n'] for c in got['colors']}
    s_def = setting['style'] if setting['style'] in styles else 1
    c_def = setting['colors'] if setting['colors'] in colors else 1
    out = []
    for kind, _, body in blocks(text):
        mk = marks_of(kind, body)
        cs = lead_number(mk['colors'])
        c = cs if cs in colors else c_def
        if kind == 'chart':
            out.append(f'-/{c}')
            continue
        ss = lead_number(mk['style'])
        out.append(f'{ss if ss in styles else s_def}/{c}')
    return out, styles, colors


def random_style(rnd, n):
    data = {'kind': 'style', 'number': n, 'name': f'{rnd.choice(NAMES)} {n}', 'base': rnd.randint(1, 10)}
    pool = {'corner': lambda: rnd.choice([0, 4, 12, 30]), 'border': lambda: rnd.choice([0.5, 2, 5]), 'line': lambda: rnd.choice(['curve', 'step', 'straight', 'wavy']),
            'line_width': lambda: rnd.choice([1, 3, 0]), 'dash': lambda: rnd.choice([True, False, 'yes']), 'shadow': lambda: rnd.choice([True, False]),
            'fill': lambda: rnd.choice(['none', 'light', 'solid', 'dark']), 'spacing': lambda: rnd.choice(['tight', 'normal', 'wide']), 'bold': lambda: rnd.choice([True, False]),
            'title': lambda: rnd.choice(['none', 'band', 'tint', 'rule']), 'zones': lambda: rnd.choice([True, False]), 'sketch': lambda: rnd.random() < 0.2,
            'css': lambda: '.node { display: none }'}
    for key in rnd.sample(sorted(pool), rnd.randint(1, 6)):
        data[key] = pool[key]()
    return data


def random_colors(rnd, n):
    hexes = ['#0b5394', '#e69138', '#6aa84f', '#cc0000', '#674ea7', '#999999', '#ffd966', 'red']
    return {'kind': 'colors', 'number': n, 'name': f'{rnd.choice(NAMES)} 색 {n}', 'series': rnd.sample(hexes, rnd.randint(1, 5)),
            **({'accent': rnd.choice(hexes)} if rnd.random() < 0.5 else {})}


def run(seed):
    rnd = random.Random(seed)
    base = Path(tempfile.mkdtemp(prefix=f'lec-scen113c-{seed}-'))
    proj = base / '과제'
    proj.mkdir()
    doc = proj / '그림.md'
    doc.write_text(DOC, encoding='utf-8', newline='\n')
    config = base / 'config'
    config.mkdir()
    (config / 'config.json').write_text(json.dumps({'work_alerts': False, 'theme': 'report', 'toc_visible': False}), encoding='utf-8')
    folder = config / 'diagram-styles'
    folder.mkdir()
    src = lambda: doc.read_text(encoding='utf-8').replace('\r\n', '\n')   # noqa: E731
    server, url, port = serve(proj, config)
    log = []
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page(viewport={'width': 1280, 'height': 900})
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)[:300]))
            page.goto(url)
            page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
            page.click('#lec-tree .row[data-doc="그림.md"]')
            until(page, lambda: page.locator('#lec-view pre.mermaid.mermaid-ok').count() == 2 and page.locator('#lec-view pre.lec-chart.chart-ok').count() == 2, ms=30000)

            def setting():
                c = page.evaluate("() => import('/static/js/store.js').then((m) => [m.S.config.diagram_style || 1, m.S.config.diagram_colors || 1])")
                return {'style': c[0], 'colors': c[1]}

            def marks():
                return page.evaluate(MARKS)

            def ext_write(text):
                time.sleep(1.05)
                doc.write_text(text, encoding='utf-8', newline='\n')

            bad_steps = []
            pick_bad = []
            for step in range(STEPS):
                op = rnd.choice(['write', 'write', 'colors', 'break', 'delete', 'pick', 'pick', 'mark', 'setting'])
                did = op
                before = src()
                files = sorted(folder.glob('*.json'))
                if op == 'write':
                    n = rnd.randint(11, 15)
                    data = random_style(rnd, n)
                    name = f'{rnd.choice(NAMES)}.json'
                    (folder / name).write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
                    did = f'write {name} #{n}'
                elif op == 'colors':
                    n = rnd.randint(9, 11)
                    name = f'색{rnd.randint(1, 3)}.json'
                    (folder / name).write_text(json.dumps(random_colors(rnd, n), ensure_ascii=False), encoding='utf-8')
                    did = f'colors {name} #{n}'
                elif op == 'break':
                    name = rnd.choice([f.name for f in files]) if files and rnd.random() < 0.6 else '깨짐.json'
                    (folder / name).write_text(rnd.choice(['{ "kind": "style", "number": 11, ', '[]', '{"kind": "other"}', '']), encoding='utf-8')
                    did = f'break {name}'
                elif op == 'delete' and files:
                    f = rnd.choice(files)
                    f.unlink()
                    did = f'delete {f.name}'
                elif op == 'pick':
                    bl = blocks(before)
                    i = rnd.randrange(len(bl))
                    key = 'colors' if bl[i][0] == 'chart' or rnd.random() < 0.4 else 'style'
                    page.locator('#lec-view pre.mermaid, #lec-view pre.lec-chart').nth(i).click(button='right', position={'x': 5, 'y': 5})
                    page.wait_for_selector('#lec-menu:not([hidden])', timeout=5000)
                    page.locator('#lec-menu button', has_text='도해 스타일…' if key == 'style' else '색 조합…').first.click()
                    page.wait_for_selector('#lec-dpick:not([hidden])', timeout=5000)
                    until(page, lambda: page.locator('#lec-dpick-grid.dpick-done').count() == 1, ms=30000)
                    _, styles, colors = expected(before, folder, setting())
                    shown = page.evaluate("() => [...document.querySelectorAll('#lec-dpick .dpick-card')].map((c) => Number(c.dataset.n))")
                    want = sorted(styles if key == 'style' else colors)
                    if shown != want:
                        pick_bad.append((step, key, shown, want))
                    n = rnd.choice(shown)
                    page.locator(f'#lec-dpick .dpick-card[data-n="{n}"]').click()
                    did = f'pick #{i} {key} → {n}'
                    until(page, lambda: src() != before, ms=4000)
                elif op == 'mark':
                    bl = blocks(before)
                    i = rnd.randrange(len(bl))
                    kind, at, body = bl[i]
                    lead = '%%' if kind == 'mermaid' else '//'
                    parts = [] if kind == 'chart' else [f'스타일: {rnd.randint(1, 16)}']   # i18n-ok
                    if kind == 'chart' or rnd.random() < 0.5:
                        parts.append(f'색: {rnd.randint(1, 12)}')   # i18n-ok
                    lines = before.split('\n')
                    inner = [ln for ln in lines[at + 1:at + 1 + len(body)] if not (LEAD[kind].match(ln) and TOKEN.match(LEAD[kind].match(ln).group(1)))]
                    line = f'{lead} {" · ".join(parts)}'
                    if kind == 'chart':
                        inner = [line] + inner
                    else:
                        pad = re.match(r'^\s*', inner[1] if len(inner) > 1 else '  ').group(0)
                        inner = inner[:1] + [pad + line] + inner[1:]
                    ext_write('\n'.join(lines[:at + 1] + inner + lines[at + 1 + len(body):]))
                    did = f'mark #{i} {parts}'
                elif op == 'setting':
                    _, styles, colors = expected(before, folder, setting())
                    s_n = rnd.choice(sorted(styles) + [rnd.randint(11, 16)])   # 없는 내 번호를 기본으로 두는 일도 (파일이 지워진 뒤처럼)
                    c_n = rnd.choice(sorted(colors))
                    page.evaluate("([s, c]) => import('/static/js/api.js').then((m) => m.saveConfig({ diagram_style: s, diagram_colors: c }))", [s_n, c_n])
                    page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('refresh-view'))")
                    did = f'setting {s_n}·{c_n}'
                want, _, _ = expected(src(), folder, setting())
                ok = until(page, lambda: marks() == want, ms=14000)
                log.append(f'{step:3} {did}{"" if ok else f"  ✗ {marks()} ≠ {want}"}')
                if not ok:
                    bad_steps.append(step)
            for line in log:
                print('   ', line)
            check(f'[{seed}] {STEPS}걸음 — 걸음마다 그린 번호가 원문·폴더·설정에서 계산한 것과 같다', not bad_steps, bad_steps)
            check(f'[{seed}] 고르기 창의 칸 = 기본 + 걸러진 내 것', not pick_bad, pick_bad)
            check(f'[{seed}] 그림 오류 없음', page.locator('#lec-view .diagram-error').count() == 0)
            check(f'[{seed}] 화면 스크립트 오류 없음', not errors, errors[:3])
            b.close()
    except Exception:   # noqa: BLE001
        traceback.print_exc()
        fails.append(f'[{seed}] 점검이 멈춤')
    finally:
        stop(server, base)


seeds = [int(x) for x in sys.argv[1:]] or [113, 7]
for s in seeds:
    print(f'[시드 {s}]')
    run(s)
report()
