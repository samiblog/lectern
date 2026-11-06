#!/usr/bin/env python3
"""차트·다이어그램과 SVG 를 그림으로 그린다. pptx 에 그대로 넣지 못하는 것을 위한 길이다.

Lectern 에 든 라이브러리(web/vendor)를 Windows 기본 Edge 로 돌린다. 인터넷에 나가지 않는다.
Edge 나 라이브러리가 없으면 None 을 돌려주고 부른 쪽이 설정 글을 넣는다.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIBS = {
    'vega-lite': ['vega/vega.min.js', 'vega/vega-lite.min.js'],
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
  if (kind === 'vega-lite') {
    const spec = JSON.parse(source);
    spec.width = W - 16; spec.height = H - 16; spec.autosize = { type: 'fit', contains: 'padding' };
    spec.background = null;
    const compiled = vegaLite.compile(spec).spec;
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
draw().catch((e) => { document.body.textContent = 'FAILED ' + e; document.title = 'failed'; });
"""


ZOOM = 1.7      # 앱이 슬라이드의 차트를 그리는 배율 (charts.js 의 SLIDE_ZOOM)


def draw(kind, source, width, height, out):
    """그림을 out 에 쓰고 True 를 준다. 앱과 같은 배율로 글자 크기를 맞추고 2배로 또렷하게."""
    root, browser = vendor_dir(), edge()
    if root is None or browser is None or kind not in LIBS:
        return False
    w, h = max(120, round(width / ZOOM)), max(90, round(height / ZOOM))
    scripts = ''.join(f'<script src="{(root / lib).as_uri()}"></script>' for lib in LIBS[kind])
    body = SCRIPT % {'w': w, 'h': h, 'kind': json.dumps(kind), 'source': json.dumps(source, ensure_ascii=False).replace('</', '<\\/')}
    html = (f'<!doctype html><html><head><meta charset="utf-8"><style>html,body{{margin:0;background:transparent;font-family:"Segoe UI","Malgun Gothic",sans-serif}}#box{{width:{w}px;height:{h}px}}</style>'
            f'{scripts}</head><body><div id="box"></div><script>{body}</script></body></html>')
    target = Path(out)
    return shoot(browser, html, w, h, ZOOM * 2, target) and target.stat().st_size > 800


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
