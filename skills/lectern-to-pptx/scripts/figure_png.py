#!/usr/bin/env python3
"""차트·다이어그램을 그림으로 그린다. 네이티브 차트로 옮기지 못한 것을 위한 길이다.

Lectern 에 든 라이브러리(web/vendor)를 Windows 기본 Edge 로 돌린다. 인터넷에 나가지 않는다.
Edge 나 라이브러리가 없으면 None 을 돌려주고 부른 쪽이 설정 글을 넣는다.
"""
import json
import os
import subprocess
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
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / 'figure.html'
        page.write_text(f'<!doctype html><html><head><meta charset="utf-8"><style>html,body{{margin:0;background:transparent;font-family:"Segoe UI","Malgun Gothic",sans-serif}}#box{{width:{w}px;height:{h}px}}</style>'
                        f'{scripts}</head><body><div id="box"></div><script>{body}</script></body></html>', encoding='utf-8')
        profile = Path(tmp) / 'profile'
        target = Path(out)
        target.unlink(missing_ok=True)
        try:
            subprocess.run([str(browser), '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--disable-extensions', '--hide-scrollbars',
                            f'--user-data-dir={profile}', '--allow-file-access-from-files', f'--force-device-scale-factor={ZOOM * 2}', '--default-background-color=00000000',
                            '--virtual-time-budget=9000', f'--window-size={w},{h}', f'--screenshot={target}', page.as_uri()],
                           capture_output=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            return False
    return target.exists() and target.stat().st_size > 800
