#!/usr/bin/env python3
"""차트·다이어그램과 SVG 를 그림으로 그린다. pptx 에 그대로 넣지 못하는 것을 위한 길이다.

Lectern 에 든 라이브러리(web/vendor)를 Windows 기본 Edge 로 돌린다. 인터넷에 나가지 않는다.
Edge 나 라이브러리가 없거나 그리지 못하면 False 를 돌려주고 부른 쪽이 설정 글을 넣는다.
lectern-to-pptx 와 lectern-to-docx 가 같은 파일을 쓴다 — 고치면 둘 다 (tests/test_skills.py 가 같은지 본다).
"""
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIBS = {
    'vega-lite': ['vega/vega.min.js', 'vega/vega-lite.min.js'],
    'vega': ['vega/vega.min.js'],
    'echarts': ['echarts/echarts.min.js'],
    'plotly': ['plotly/plotly.min.js'],
    'mermaid': ['mermaid/mermaid.min.js'],
    'dot': ['viz/viz-global.js'],
}


def vendor_dir():
    roots = [HERE.parents[2] / 'web' / 'vendor']
    if getattr(sys, 'frozen', False):   # 스킬 실행기로 돌면 그 설치본의 것을 쓴다 (D99)
        roots.insert(0, Path(sys.executable).parent / '_internal' / 'web' / 'vendor')
    local = os.environ.get('LOCALAPPDATA')
    if local:
        roots.append(Path(local) / 'Programs' / 'Lectern' / '_internal' / 'web' / 'vendor')
    return next((r for r in roots if (r / 'vega').exists()), None)


def edge():
    for base in (os.environ.get('ProgramFiles(x86)'), os.environ.get('ProgramFiles')):
        if base:
            path = Path(base) / 'Microsoft' / 'Edge' / 'Application' / 'msedge.exe'
            if path.exists():
                return path
    return None


SCRIPT = """
const box = document.getElementById('box');
const W = %(w)d, H = %(h)d, kind = %(kind)s, source = %(source)s;
const done = () => { document.title = 'done'; };
async function draw() {
  if (kind === 'vega-lite' || kind === 'vega') {
    const spec = JSON.parse(source);
    if (kind === 'vega-lite') {
      spec.width = W - 16; spec.height = H - 16; spec.autosize = { type: 'fit', contains: 'padding' };
    }
    spec.background = null;
    const compiled = kind === 'vega-lite' ? vegaLite.compile(spec).spec : spec;
    const view = new vega.View(vega.parse(compiled), { renderer: 'svg', container: box, hover: false });
    await view.runAsync();
  } else if (kind === 'echarts') {
    const chart = echarts.init(box, null, { renderer: 'svg', width: W, height: H });
    const option = JSON.parse(source); option.animation = false;
    chart.setOption(option);
  } else if (kind === 'plotly') {
    const fig = JSON.parse(source);
    await Plotly.newPlot(box, fig.data, { ...(fig.layout || {}), width: W, height: H, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)' }, { staticPlot: true });
  } else if (kind === 'mermaid') {
    mermaid.initialize({ startOnLoad: false, securityLevel: 'strict' });
    const { svg } = await mermaid.render('fig', source);
    box.innerHTML = svg;
    const el = box.querySelector('svg'); el.style.width = W + 'px'; el.style.height = H + 'px'; el.style.maxWidth = 'none';
  } else {
    const viz = await Viz.instance();
    const el = viz.renderSVGElement(source);
    el.setAttribute('width', W); el.setAttribute('height', H);
    box.append(el);
  }
  done();
}
draw().catch(() => { document.body.replaceChildren(); document.title = 'failed'; });   // 빈 그림 — blank() 가 알아본다
"""


ZOOM = 1.7      # 앱이 슬라이드의 차트를 그리는 배율 (charts.js 의 SLIDE_ZOOM)


class SpecError(ValueError):
    pass


NAME = re.compile(r'[A-Za-z_$][\w$]*')
NUMBER = re.compile(r'[-+]?(?:0[xX][\da-fA-F]+|(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?|Infinity)|NaN')
ESC = {'n': '\n', 't': '\t', 'r': '\r', 'b': '\b', 'f': '\f', 'v': '\v', '0': '\0'}


def parse_spec(text):
    """차트 설정을 읽는다 — 앱의 charts.js parseSpec 과 같다. JSON 이 아니면 JS 객체 글처럼: 주석, 따옴표 없는 키, 작은따옴표,
    끝 쉼표, 16진수, 맨 앞의 'option =' 과 끝의 ';'. 함수·식은 안 된다 (SpecError)."""
    try:
        return json.loads(text)
    except ValueError:
        pass
    src, pos = text, [0]

    def fail():
        raise SpecError(f'line {src[:pos[0]].count(chr(10)) + 1}')

    def skip():
        while True:
            while pos[0] < len(src) and src[pos[0]].isspace():
                pos[0] += 1
            if src.startswith('//', pos[0]):
                end = src.find('\n', pos[0])
                pos[0] = len(src) if end < 0 else end
            elif src.startswith('/*', pos[0]):
                end = src.find('*/', pos[0] + 2)
                if end < 0:
                    fail()
                pos[0] = end + 2
            else:
                return

    def string():
        quote = src[pos[0]]
        pos[0] += 1
        out = []
        while pos[0] < len(src) and src[pos[0]] != quote:
            c = src[pos[0]]
            pos[0] += 1
            if c == '\n':
                fail()
            if c != '\\':
                out.append(c)
                continue
            e = src[pos[0]] if pos[0] < len(src) else ''
            pos[0] += 1
            if e == 'u':
                out.append(chr(int(src[pos[0]:pos[0] + 4], 16)))
                pos[0] += 4
            elif e != '\n':
                out.append(ESC.get(e, e))
        if pos[0] >= len(src):
            fail()
        pos[0] += 1
        return ''.join(out)

    def number(word):
        if word.lstrip('+-').lower().startswith('0x'):
            return int(word, 16)
        if word.lstrip('+-') in ('Infinity', 'NaN'):
            return None   # JSON 에 없다 — 빈 값으로
        v = float(word)
        return int(v) if v.is_integer() and not re.search(r'[.eE]', word) else v

    def value():
        skip()
        c = src[pos[0]] if pos[0] < len(src) else ''
        if c in '{[':
            close = '}' if c == '{' else ']'
            out = {} if c == '{' else []
            pos[0] += 1
            while True:
                skip()
                if pos[0] < len(src) and src[pos[0]] == close:
                    pos[0] += 1
                    return out
                if c == '{':
                    if pos[0] < len(src) and src[pos[0]] in '"\'':
                        key = string()
                    else:
                        m = NAME.match(src, pos[0]) or NUMBER.match(src, pos[0])
                        if not m:
                            fail()
                        key = m[0]
                        pos[0] = m.end()
                    skip()
                    if pos[0] >= len(src) or src[pos[0]] != ':':
                        fail()
                    pos[0] += 1
                    out[key] = value()
                else:
                    out.append(value())
                skip()
                if pos[0] < len(src) and src[pos[0]] == ',':
                    pos[0] += 1
                elif pos[0] >= len(src) or src[pos[0]] != close:
                    fail()
        if c in ('"', "'"):
            return string()
        m = NUMBER.match(src, pos[0])
        if m:
            pos[0] = m.end()
            return number(m[0])
        m = NAME.match(src, pos[0])
        if m and m[0] in ('true', 'false', 'null'):
            pos[0] = m.end()
            return {'true': True, 'false': False, 'null': None}[m[0]]
        return fail()

    skip()
    head = re.compile(r'(?:(?:const|let|var)\s+)?[A-Za-z_$][\w$]*\s*=(?!=)').match(src, pos[0])
    if head:
        pos[0] = head.end()
    out = value()
    skip()
    if pos[0] < len(src) and src[pos[0]] == ';':
        pos[0] += 1
    skip()
    if pos[0] < len(src):
        fail()
    return out


def inline_data(spec, base):
    """Vega(-Lite) 의 data.url (문서 기준 상대경로의 CSV·TSV·JSON) 을 값으로 넣는다 — 그리는 창은 파일을 읽지 못한다.
    인터넷 주소는 그대로 둔다 (그리지 않는다)."""
    def walk(node):
        if isinstance(node, dict):
            data = node.get('data')
            if isinstance(data, dict) and isinstance(data.get('url'), str) and not re.match(r'^([a-z][\w+.-]*:|//)', data['url'], re.I):
                path = Path(base) / data['url']
                if path.is_file():
                    fmt = dict(data.get('format') or {})
                    ext = path.suffix.lower().lstrip('.')
                    text = path.read_text(encoding='utf-8-sig')
                    if ext == 'json':
                        node['data'] = {**{k: v for k, v in data.items() if k != 'url'}, 'values': json.loads(text), 'format': fmt} if fmt else {'values': json.loads(text)}
                    else:
                        fmt.setdefault('type', 'tsv' if ext == 'tsv' else 'csv')
                        node['data'] = {**{k: v for k, v in data.items() if k not in ('url', 'format')}, 'values': text, 'format': fmt}
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(spec)
    return spec


def blank(path):
    """그림이 통째로 투명한지 (그리다 실패하면 창을 비운다). PNG 를 표준 라이브러리로 푼다 — 모르는 형식이면 False"""
    try:
        data = Path(path).read_bytes()
        if data[:8] != b'\x89PNG\r\n\x1a\n':
            return False
        w, h, depth, ctype = struct.unpack('>IIBB', data[16:26])
        if depth != 8 or ctype not in (2, 6):
            return False
        idat, i = [], 8
        while i < len(data):
            n, kind = struct.unpack('>I4s', data[i:i + 8])
            if kind == b'IDAT':
                idat.append(data[i + 8:i + 8 + n])
            i += 12 + n
        if ctype == 2:   # 알파가 없다 — 투명할 수 없다
            return False
        raw = zlib.decompress(b''.join(idat))
        stride = 1 + w * 4
        for row in range(h):   # 모두 (0,0,0,0) 이면 어느 필터를 거쳐도 0 이다 — 줄 앞의 필터 바이트만 빼고 본다
            line = raw[row * stride + 1:(row + 1) * stride]
            if line.count(0) != len(line):
                return False
        return True
    except (OSError, ValueError, struct.error, zlib.error):
        return False


def draw(kind, source, width, height, out, base=None):
    """그림을 out 에 쓰고 True 를 준다. 앱과 같은 배율로 글자 크기를 맞추고 2배로 또렷하게.
    base 를 주면 Vega(-Lite) 의 data.url 을 그 폴더 기준으로 읽어 넣는다. 설정을 읽지 못하거나 그리다 실패하면 False."""
    kind = {'graphviz': 'dot'}.get(kind, kind)
    root, browser = vendor_dir(), edge()
    if root is None or browser is None or kind not in LIBS:
        return False
    if kind in ('vega-lite', 'vega', 'echarts', 'plotly'):
        try:
            spec = parse_spec(source)
        except SpecError:
            return False
        if base and kind in ('vega-lite', 'vega'):
            spec = inline_data(spec, base)
        source = json.dumps(spec, ensure_ascii=False)
    w, h = max(120, round(width / ZOOM)), max(90, round(height / ZOOM))
    scripts = ''.join(f'<script src="{(root / lib).as_uri()}"></script>' for lib in LIBS[kind])
    body = SCRIPT % {'w': w, 'h': h, 'kind': json.dumps(kind), 'source': json.dumps(source, ensure_ascii=False).replace('</', '<\\/')}
    html = (f'<!doctype html><html><head><meta charset="utf-8"><style>html,body{{margin:0;background:transparent;font-family:"Segoe UI","Malgun Gothic",sans-serif}}#box{{width:{w}px;height:{h}px}}</style>'
            f'{scripts}</head><body><div id="box"></div><script>{body}</script></body></html>')
    target = Path(out)
    return shoot(browser, html, w, h, ZOOM * 2, target) and target.stat().st_size > 800 and not blank(target)


def shoot(browser, html, w, h, scale, target):
    """html 을 창 크기 w×h 로 그려 target 에 쓴다."""
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / 'figure.html'
        page.write_text(html, encoding='utf-8')
        profile = Path(tmp) / 'profile'
        target.unlink(missing_ok=True)
        try:
            subprocess.run([str(browser), '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--disable-extensions', '--hide-scrollbars',
                            f'--user-data-dir={profile}', '--allow-file-access-from-files', f'--force-device-scale-factor={scale}', '--default-background-color=00000000',
                            '--virtual-time-budget=9000', f'--window-size={w},{h}', f'--screenshot={target}', page.as_uri()],
                           capture_output=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            return False
    return target.exists()


SVG_LONG = 1000     # 긴 변의 창 크기. 2배로 그려 슬라이드 폭을 채워도 또렷하다
SVG_NARROW = 520    # Edge 의 창은 이보다 좁아지지 않아 좁은 그림은 키워서 그린다


def svg_size(path):
    """SVG 의 가로세로. width·height 가 없거나 % 나 mm 면 viewBox 로 본다. 모르면 None."""
    tag = re.search(r'<svg\b[^>]*>', Path(path).read_text(encoding='utf-8', errors='replace')[:20000], re.S)
    if tag is None:
        return None

    def length(name):
        m = re.search(rf'\s{name}\s*=\s*["\']\s*([\d.]+)\s*(?:px)?\s*["\']', tag.group(0))
        return float(m.group(1)) if m else 0

    w, h = length('width'), length('height')
    if w and h:
        return w, h
    box = re.search(r'\sviewBox\s*=\s*["\']([^"\']+)["\']', tag.group(0))
    parts = re.findall(r'-?[\d.]+', box.group(1)) if box else []
    return (float(parts[2]), float(parts[3])) if len(parts) == 4 and float(parts[2]) and float(parts[3]) else None


def svg(path, out):
    """SVG 파일을 PNG 로 그려 True 를 준다. <img> 로 그려서 SVG 안의 스크립트는 돌지 않는다."""
    browser, size = edge(), svg_size(path)
    if browser is None or size is None:
        return False
    fit = SVG_LONG / max(size)
    w, h = size[0] * fit, size[1] * fit
    if w < SVG_NARROW:
        w, h = SVG_NARROW, h * SVG_NARROW / w
    w, h = round(w), round(h)
    html = (f'<!doctype html><html><head><meta charset="utf-8"><style>html,body{{margin:0;background:transparent}}img{{display:block;width:{w}px;height:{h}px}}</style></head>'
            f'<body><img src="{Path(path).resolve().as_uri()}"></body></html>')
    return shoot(browser, html, w, h, min(2, 2 * SVG_LONG / max(w, h)), Path(out))
