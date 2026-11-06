#!/usr/bin/env python3
"""Lectern 발표 문서를 pptx 로 만든다. 표준 라이브러리만 쓴다 (SVG 그림만 PowerPoint 가 있어야 바꾼다).

    python build_pptx.py 문서.md [--out 결과.pptx] [--template 양식.pptx] [--style deck] [--force] [--rebuild-all]

- 변환기록이 있으면 원본 pptx 를 바탕으로 쓴다. 지문이 같은 쪽은 원본 쪽을 그대로 쓰고 고친 쪽만 새로 만든다.
- --template 을 주면 그 pptx 의 마스터와 레이아웃 위에 쪽을 만든다.
- 둘 다 없으면 Lectern 슬라이드 스타일을 살린 새 pptx 를 만든다.
"""
import argparse
import json
import math
import os
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import figure_png  # noqa: E402
import lectern_md as lm  # noqa: E402
import pptx_parts as pp  # noqa: E402
import text_patch  # noqa: E402
from pptx_parts import esc  # noqa: E402

EMU = 9525
PALETTE = ['4C78A8', 'F58518', 'E45756', '72B7B2', '54A24B', 'EECA3B', 'B279A2', 'FF9DA6']
DECK = {
    'bg': 'F6F3EC', 'fg': '1F2933', 'heading': '17293D', 'muted': '5C6773', 'border': 'DDD6C8', 'link': 'C2410C', 'code-bg': 'ECE7DC',
    'th-bg': '17293D', 'th-fg': 'FFFFFF', 'th-rule': 'C2410C', 'stripe': 'FBF9F4', 'strong': '17293D', 'quote-bar': 'C2410C',
    'alert-note': '1D4E89', 'alert-tip': '2F7D5B', 'alert-important': '5B3F9E', 'alert-warning': 'B45309', 'alert-caution': 'B3261E',
}
FIXED = {'h3': 'C2410C', 'kpi': 'C2410C', 'card': 'FFFFFF', 'accent-bg': 'FFF1E6', 'accent-bar': 'C2410C', 'lead-bg': '17293D', 'lead-fg': 'F6F3EC', 'lead-heading': 'FFFFFF',
         'lead-link': 'FDBA74', 'lead-muted': 'B8C2CF', 'lead-code': '22344A', 'invert-bg': '1F2329', 'invert-fg': 'EEF0F3', 'invert-heading': 'FFFFFF', 'invert-link': '8AB4FF',
         'invert-muted': 'B4BAC4', 'invert-code': '2B3038', 'note-bg': 'FDE68A', 'note-fg': '3B3216', 'table-bg': 'FFFFFF'}


def hex_of(value, over='FFFFFF'):
    """CSS 색을 RRGGBB 로. 반투명은 over 위에 섞는다. 모르면 None."""
    v = str(value or '').strip().lower()
    m = re.fullmatch(r'#([0-9a-f]{3})', v)
    if m:
        return ''.join(c * 2 for c in m[1]).upper()
    m = re.fullmatch(r'#([0-9a-f]{6})(?:[0-9a-f]{2})?', v)
    if m:
        return m[1].upper()
    m = re.fullmatch(r'rgba?\(\s*(\d+)[ ,]+(\d+)[ ,]+(\d+)(?:[ ,/]+([\d.]+%?))?\s*\)', v)
    if m:
        rgb = [int(m[i]) for i in (1, 2, 3)]
        alpha = m[4]
        a = 1 if alpha is None else float(alpha[:-1]) / 100 if alpha.endswith('%') else float(alpha)
        base = [int(over[i:i + 2], 16) for i in (0, 2, 4)]
        return ''.join(f'{round(c * a + b * (1 - a)):02X}' for c, b in zip(rgb, base))
    names = {'white': 'FFFFFF', 'black': '000000', 'red': 'FF0000', 'transparent': None}
    return names.get(v)


def luminance(c):
    r, g, b = (int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda v: v / 12.92 if v <= .03928 else ((v + .055) / 1.055) ** 2.4
    return .2126 * f(r) + .7152 * f(g) + .0722 * f(b)


def theme_file(style):
    """스타일 css 를 찾는다: 이 스킬이 앱 안에 있을 때, 저장소, 설치본 차례."""
    roots = [HERE.parents[2] / 'web' / 'themes']
    if getattr(sys, 'frozen', False):   # 스킬 실행기로 돌면 그 설치본의 것을 쓴다 (D99)
        roots.insert(0, Path(sys.executable).parent / '_internal' / 'web' / 'themes')
    local = os.environ.get('LOCALAPPDATA')
    if local:
        roots.append(Path(local) / 'Programs' / 'Lectern' / '_internal' / 'web' / 'themes')
    for root in roots:
        if (root / f'{style}.css').exists():
            return root / f'{style}.css'
    return None


def chosen_style():
    """사용자가 슬라이드 창에서 고른 스타일. 읽기만 한다."""
    base = os.environ.get('APPDATA')
    try:
        return json.loads((Path(base) / 'Lectern' / 'config.json').read_text(encoding='utf-8')).get('slide_theme', 'deck') if base else 'deck'
    except (OSError, ValueError):
        return 'deck'


def css_vars(css):
    return {m[1]: m[2].strip() for m in re.finditer(r'--md-([\w-]+)\s*:\s*([^;}]+)', css)}


def family(value, korean=False):
    names = [n.strip().strip('"\'') for n in str(value or '').split(',')]
    names = [n for n in names if n and n not in ('sans-serif', 'serif', 'monospace', 'system-ui') and 'Variable' not in n]
    if korean:
        return next((n for n in names if re.search(r'Malgun|Gothic|Batang|Nanum|Noto Sans KR|Pretendard|맑은|바탕', n)), 'Malgun Gothic')
    return names[0] if names else 'Malgun Gothic'


class Style:
    """앱의 슬라이드 스타일과 문서 CSS 에서 pptx 에 쓸 색을 모은다."""

    def __init__(self, name, doc_css):
        self.name = name
        self.c = {**DECK, **FIXED}
        self.font, self.ea, self.mono = 'Segoe UI', 'Malgun Gothic', 'Consolas'
        self.used_theme = False
        self.dark_lead = True
        if name.startswith('user:'):
            name = 'deck'
        path = theme_file(name)
        if path:
            css = path.read_text(encoding='utf-8')
            self.used_theme = True
            self.apply_vars(css_vars(css.split('}', 1)[0]))
            if name != 'deck':
                # 상자 바탕과 어두운 표지는 deck 스타일의 것이다. 다른 스타일은 앱처럼 바탕 없이 테두리만
                self.dark_lead = False
                self.c.update({'h3': self.c['heading'], 'kpi': self.c['link'], 'accent-bar': self.c['link'], 'accent-bg': self.mix(self.c['link'], .1), 'card': None, 'table-bg': None})
            self.rule(css, r'\.md-body h3\s*\{[^}]*?color:\s*([^;}]+)', 'h3')
            self.rule(css, r'\.lec-cell\.kpi strong\s*\{[^}]*?color:\s*([^;}]+)', 'kpi')
            self.rule(css, r'\.lec-cell\.accent\s*\{[^}]*?background:\s*([^;}]+)', 'accent-bg')
            self.rule(css, r'\.lec-slide\.lead\s*\{[^}]*?background-color:\s*([^;}]+)', 'lead-bg')
        self.words = {}
        self.doc = {}
        self.read_doc(doc_css)

    def rule(self, css, pattern, key):
        m = re.search(pattern, css)
        value = hex_of(m[1]) if m else None
        if value:
            self.c[key] = value

    def mix(self, color, share):
        a = [int(color[i:i + 2], 16) for i in (0, 2, 4)]
        b = [int(self.c['bg'][i:i + 2], 16) for i in (0, 2, 4)]
        return ''.join(f'{round(x * share + y * (1 - share)):02X}' for x, y in zip(a, b))

    def apply_vars(self, found):
        for key, value in found.items():
            if key in ('font', 'heading-font'):
                self.font = family(value) if key == 'font' else self.font
                self.ea = family(value, True)
            elif key == 'mono':
                self.mono = family(value)
            else:
                color = hex_of(value, self.c['bg'])
                if color:
                    self.c[key] = color

    def read_doc(self, css):
        if not css:
            return
        for m in re.finditer(r'(^|[}\s,])section\s*\{([^}]*)\}', css):
            before = dict(self.c)
            self.apply_vars(css_vars(m[2]))
            self.doc.update({k: v for k, v in self.c.items() if before.get(k) != v})
            align = re.search(r'text-align\s*:\s*(left|right|center)', m[2])
            if align:
                self.doc['align'] = align[1]
            bg = re.search(r'(?<![\w-])background(?:-color)?\s*:\s*([^;}]+)', m[2])
            fg = re.search(r'(?<![\w-])color\s*:\s*([^;}]+)', m[2])
            if bg and hex_of(bg[1]):
                self.c['bg'] = hex_of(bg[1])
            if fg and hex_of(fg[1]):
                self.c['fg'] = hex_of(fg[1])
        for m in re.finditer(r'\.([A-Za-z][\w-]*)\s*\{([^}]*)\}', css):
            body = m[2]
            bg = re.search(r'(?<![\w-])background(?:-color)?\s*:\s*([^;}]+)', body)
            fg = re.search(r'(?<![\w-])color\s*:\s*([^;}]+)', body)
            word = self.words.setdefault(m[1], {})
            if bg and hex_of(bg[1], self.c['bg']):
                word['bg'] = hex_of(bg[1], self.c['bg'])
            if fg and hex_of(fg[1]):
                word['fg'] = hex_of(fg[1])
            border = re.search(r'(?<![\w-])border\s*:\s*([\d.]+)px\s+\w+\s+([^;}]+)', body)
            if border and hex_of(border[2]):
                word['line'], word['line_w'] = hex_of(border[2]), float(border[1])
            radius = re.search(r'border-radius\s*:\s*([\d.]+)(px)?\s*[;}]?', body)
            if radius and radius[2] != '%':
                word['radius'] = float(radius[1])
            clip = re.search(r'clip-path\s*:\s*polygon\(([^)]*)\)', body)
            if clip:
                word['polygon'] = [tuple(float(v.rstrip('%')) for v in pair.split()) for pair in clip[1].split(',') if len(pair.split()) == 2]
            if re.search(r'border-radius\s*:\s*50%', body):
                word['ellipse'] = True

    def read_strong(self, css):
        for m in re.finditer(r'\.([A-Za-z][\w-]*)(?:\s*,\s*\.([A-Za-z][\w-]*))?\s+strong\s*\{[^}]*?(?<![\w-])color\s*:\s*([^;}]+)', css or ''):
            for name in (m[1], m[2]):
                if name and hex_of(m[3]):
                    self.words.setdefault(name, {})['strong'] = hex_of(m[3])

    def logo(self, css):
        """section::before 의 data 그림 (pptx-to-lectern 이 넣은 로고)."""
        m = re.search(r'section::before\s*\{([^}]*)\}', css or '')
        if not m:
            return None
        body = m[1]
        data = re.search(r'url\(data:image/([\w+.-]+);base64,([A-Za-z0-9+/=\s]+)\)', body)
        if not data:
            return None
        num = lambda key: float(n[1]) if (n := re.search(rf'(?<![\w-]){key}\s*:\s*(-?[\d.]+)px', body)) else None
        return {'kind': data[1], 'data': data[2], 'left': num('left'), 'right': num('right'), 'top': num('top'), 'bottom': num('bottom'), 'w': num('width'), 'h': num('height')}


# ---- 그림

def image_size(path):
    data = Path(path).read_bytes()[:65536]
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return struct.unpack('>II', data[16:24])
    if data[:3] == b'GIF':
        return struct.unpack('<HH', data[6:10])
    if data[:2] == b'BM':
        w, h = struct.unpack('<ii', data[18:26])
        return w, abs(h)
    if data[:2] == b'\xff\xd8':
        i = 2
        whole = Path(path).read_bytes()
        while i + 9 < len(whole):
            if whole[i] != 0xFF:
                i += 1
                continue
            marker = whole[i + 1]
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                h, w = struct.unpack('>HH', whole[i + 5:i + 9])
                return w, h
            i += 2 + struct.unpack('>H', whole[i + 2:i + 4])[0]
    if data.lstrip()[:5] in (b'<?xml', b'<svg ') or b'<svg' in data[:600]:
        text = data.decode('utf-8', 'replace')
        box = re.search(r'viewBox="[\d.\s-]*?([\d.]+)\s+([\d.]+)"', text)
        if box:
            return float(box[1]), float(box[2])
        w, h = re.search(r'\bwidth="([\d.]+)', text), re.search(r'\bheight="([\d.]+)', text)
        if w and h:
            return float(w[1]), float(h[1])
    return 800, 600


def svg_to_png(paths, folder):
    """SVG 는 pptx 에 PNG 가 함께 있어야 한다. PowerPoint 로 바꾸고 못 바꾼 것은 Edge 로 그린다. {svg: png}

    결과는 folder(임시 폴더)에 쓴다. 사용자의 그림 폴더에 아무것도 남기지 않는다.
    """
    if not paths:
        return {}
    job = Path(folder) / 'svg-job.json'
    out = {}
    try:
        job.write_text(json.dumps({'folder': str(folder), 'paths': [str(p) for p in paths]}, ensure_ascii=False), encoding='utf-8')
        r = subprocess.run([sys.executable, '-I', str(HERE / 'svg_png.py'), str(job)], capture_output=True, text=True, encoding='utf-8', timeout=120 + 5 * len(paths))
        if r.returncode == 0:
            out = json.loads(r.stdout.strip().split('\n')[-1])
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    finally:
        job.unlink(missing_ok=True)
    for i, path in enumerate(paths):
        png = Path(folder) / f'svg-edge{i}.png'
        if str(path) not in out and figure_png.svg(path, png):
            out[str(path)] = str(png)
    return out


# ---- 글

def clr(color):
    """'RRGGBB', 'accent1', 'accent1+80'(밝게) 을 색 요소로."""
    if not color:
        return ''
    if re.fullmatch(r'[0-9A-Fa-f]{6}', color):
        return f'<a:srgbClr val="{color}"/>'
    name, _, light = color.partition('+')
    if light:
        off = int(light) * 1000
        return f'<a:schemeClr val="{name}"><a:lumMod val="{100000 - off}"/><a:lumOff val="{off}"/></a:schemeClr>'
    return f'<a:schemeClr val="{name}"/>'


def solid(color):
    return f'<a:solidFill>{clr(color)}</a:solidFill>' if color else ''


def text_units(text):
    ko = len(re.findall(r'[가-힣ㄱ-ㅎ一-龥]', text))
    return ko * 1.28 + (len(text) - ko) * .66


def lines_of(text, width, size):
    total = 0
    for row in text.split('\n'):
        total += max(1, math.ceil(text_units(row) * size / max(width, 40)))
    return total


LINE = 1.42     # 슬라이드 글의 줄 높이 (base.css line-height 1.45 에 가깝게, 단위는 글자 크기 px)


class Writer:
    """쪽 하나의 도형을 모은다."""

    def __init__(self, build, slide, part, layout):
        self.b = build
        self.deck = build.deck
        self.slide = slide
        self.part = part
        self.layout = layout
        self.pkg = build.pkg
        self.next_id = 2
        self.shapes = []
        self.anchors = {}
        self.kx = build.cx / self.deck['w']
        self.ky = build.cy / self.deck['h']
        self.fs = min(self.kx, self.ky) / EMU     # Lectern 쪽의 pt → 이 pptx 의 pt
        eff = slide['eff']
        self.classes = slide['classes']
        self.sizes = {**self.deck['sizes'], **lm.text_sizes(eff.get('text'))}
        self.style = Style.__new__(Style)
        self.style.__dict__.update(build.style.__dict__)
        self.style.c = dict(build.style.c)
        self.style.words = dict(build.style.words)
        self.style.doc = dict(build.style.doc)
        if slide['css']:
            self.style.read_doc(slide['css'])
        self.style.read_strong(self.deck['css'] + '\n' + slide['css'])
        self.palette()

    def palette(self):
        c = self.style.c
        cl = self.classes
        self.lead = 'lead' in cl
        self.lead_dark = self.lead and 'paper' not in cl and self.style.dark_lead
        self.dark_page = 'invert' in cl or self.lead_dark
        self.p = {'fg': c['fg'], 'heading': c['heading'], 'link': c['link'], 'muted': c['muted'], 'border': c['border'], 'code': c['code-bg'], 'bg': c['bg'], 'kpi': c['kpi'],
                  'h3': c['h3'], 'th-bg': c['th-bg'], 'th-fg': c['th-fg'], 'stripe': c['stripe'], 'table': c['table-bg'], 'card': c['card'], 'code-fg': c['fg'], 'strong': None}
        if 'invert' in cl:
            self.p.update({'fg': c['invert-fg'], 'heading': c['invert-heading'], 'link': c['invert-link'], 'muted': c['invert-muted'], 'code': c['invert-code'], 'bg': c['invert-bg'],
                           'kpi': c['invert-link'], 'h3': c['invert-heading'], 'code-fg': c['invert-fg']})
        elif self.lead_dark:
            self.p.update({'fg': c['lead-fg'], 'heading': c['lead-heading'], 'link': c['lead-link'], 'muted': c['lead-muted'], 'code': c['lead-code'], 'bg': c['lead-bg'],
                           'kpi': c['lead-link'], 'h3': c['lead-heading'], 'code-fg': c['invert-fg']})
        eff = self.slide['eff']
        bg = hex_of(eff.get('backgroundColor'))
        fg = hex_of(eff.get('color'))
        self.custom_bg = bg
        if bg:
            self.p['bg'] = bg
        if fg:
            self.p.update({'fg': fg, 'heading': fg, 'link': fg, 'h3': fg})
        if self.dark_page or (bg and luminance(bg) < .25):
            over = self.p['bg']
            self.p['card'] = hex_of('rgba(255,255,255,.1)', over)
            self.p['table'] = over
            self.p['stripe'] = hex_of('rgba(255,255,255,.06)', over)
            self.p['border'] = hex_of('rgba(255,255,255,.28)', over)
            self.p['th-bg'] = hex_of('rgba(255,255,255,.16)', over)
        if self.b.template:      # 양식의 색을 따른다. 강조색이 밝은 양식이 있어 흰 바탕에서 읽히는 색을 고른다
            strong = self.b.strong_color()
            self.p.update({'fg': None, 'heading': None, 'h3': None, 'link': strong, 'kpi': strong, 'muted': 'tx1+50', 'border': 'tx1+75', 'code': 'bg2', 'card': None,
                           'th-bg': strong, 'th-fg': 'bg1', 'stripe': 'tx1+95', 'table': None, 'code-fg': None})
            doc = self.style.doc
            for key in ('th-bg', 'th-fg', 'link', 'stripe'):
                if doc.get(key):
                    self.p[key] = doc[key]
            if doc.get('heading'):
                self.p['h3'] = doc['heading']
            if doc.get('fg'):
                self.p['fg'] = doc['fg']
            if doc.get('link'):
                self.p['kpi'] = doc['link']
            if fg:
                self.p.update({'fg': fg, 'heading': fg, 'h3': fg})

    def sid(self):
        n = self.next_id
        self.next_id += 1
        return n

    def box(self, x, y, w, h):
        return round(x * self.kx), round(y * self.ky), max(1, round(w * self.kx)), max(1, round(h * self.ky))

    def xfrm(self, x, y, w, h, extra=''):
        X, Y, W, H = self.box(x, y, w, h)
        return f'<a:xfrm{extra}><a:off x="{X}" y="{Y}"/><a:ext cx="{W}" cy="{H}"/></a:xfrm>'

    # 글
    def rpr(self, run, size, color, bold=False, tag='a:rPr'):
        attrs = 'lang="ko-KR" dirty="0"'
        if size:
            attrs += f' sz="{round(size * self.fs * 100)}"'
        if run.get('b') or bold:
            attrs += ' b="1"'
        if run.get('i'):
            attrs += ' i="1"'
        if run.get('u'):
            attrs += ' u="sng"'
        if run.get('sup'):
            attrs += ' baseline="30000"'
        if run.get('sub'):
            attrs += ' baseline="-25000"'
        kids = ''
        link = run.get('link')
        color = self.p['link'] if link and not self.b.template else color
        kids += solid(color)
        if run.get('code'):
            kids += f'<a:latin typeface="{esc(self.style.mono)}"/>'
        if link:
            if re.match(r'https?://|mailto:', link):
                rid = self.pkg.add_rel(self.part, 'hyperlink', link, external=True)
                kids += f'<a:hlinkClick r:id="{rid}"/>'
        return f'<{tag} {attrs}>{kids}</{tag}>' if kids else f'<{tag} {attrs}/>'

    def runs_xml(self, runs, size, color, bold=False):
        out = []
        for r in runs:
            parts = r['t'].split('\n')
            for i, t in enumerate(parts):
                if i:
                    out.append('<a:br/>')
                if t:
                    out.append(f'<a:r>{self.rpr(r, size, color, bold)}<a:t>{esc(t)}</a:t></a:r>')
        return ''.join(out)

    def para(self, runs, size, color, align='l', bullet=None, lvl=0, before=0, bold=False, ordered=False):
        mar = 0
        if bullet:
            mar = round((28 + lvl * 26) * self.kx)
        attrs = f'algn="{align}"'
        if bullet:
            attrs += f' marL="{mar}" indent="{-round(22 * self.kx)}"'
        else:
            attrs += ' marL="0" indent="0"'
        spacing = f'<a:lnSpc><a:spcPct val="108000"/></a:lnSpc><a:spcBef><a:spcPts val="{round(before * 100)}"/></a:spcBef>'
        if bullet and ordered:
            mark = '<a:buFont typeface="+mj-lt"/><a:buAutoNum type="arabicPeriod"/>'
        elif bullet:
            mark = f'<a:buFont typeface="Arial"/><a:buChar char="{"•" if lvl == 0 else "◦"}"/>'
        else:
            mark = '<a:buNone/>'
        end = f'<a:endParaRPr lang="ko-KR" sz="{round(size * self.fs * 100)}"/>' if size else ''
        return f'<a:p><a:pPr {attrs}>{spacing}{mark}</a:pPr>{self.runs_xml(runs, size, color, bold)}{end}</a:p>'

    def text_paras(self, blocks, size, color, align, h3=None):
        """글 블록을 문단으로. 칸 크기를 쓰면 소제목은 1.15배다."""
        out = []
        sub = size * 1.15 if size != self.sizes['body'] else self.sizes['sub']
        first = True
        for b in blocks:
            before = 0 if first else 6
            first = False
            if b['kind'] == 'heading':
                out.append(self.para(b['runs'], sub, h3 if h3 is not None else color, align, before=before + 2, bold=True))
            elif b['kind'] == 'para':
                out.append(self.para(b['runs'], size, color, align, before=before))
            elif b['kind'] == 'list':
                for i, it in enumerate(b['items']):
                    out.append(self.para(it['runs'], size, color, 'l' if align == 'ctr' else align, bullet=True, lvl=it['lvl'], before=before if i == 0 else 3, ordered=it['ordered']))
        return ''.join(out)

    def blocks_height(self, blocks, width, size):
        px = size / .75
        total = 0
        sub = (size * 1.15 if size != self.sizes['body'] else self.sizes['sub']) / .75
        for b in blocks:
            if b['kind'] == 'heading':
                total += lines_of(lm.plain(b['runs']), width, sub * .75) * sub * 1.3 + 8
            elif b['kind'] == 'para':
                total += lines_of(lm.plain(b['runs']), width, size) * px * LINE + 8
            elif b['kind'] == 'list':
                for it in b['items']:
                    total += lines_of(lm.plain(it['runs']), width - 30 - it['lvl'] * 26, size) * px * LINE + 4
        return total

    def bands(self):
        """section 의 줄무늬 linear-gradient 를 색 띠 도형으로. 앱에서는 CSS 지만 pptx 에는 도형이 필요하다."""
        m = re.search(r'section\s*\{[^}]*?background(?:-image)?\s*:\s*linear-gradient\(\s*to\s+(bottom|right)\s*,(.*?)\)\s*;', self.slide['css'], flags=re.S)
        if not m:
            return
        W, H = self.deck['w'], self.deck['h']
        for color, a, b in re.findall(r'(#[0-9a-fA-F]{3,8})\s+(-?[\d.]+)px\s+(-?[\d.]+)px', m[2]):
            c = hex_of(color)
            if not c:
                continue
            a, b = float(a), float(b)
            if m[1] == 'bottom':
                self.add_rect(0, a, W, b - a, c, name='띠')
            else:
                self.add_rect(a, 0, b - a, H, c, name='띠')

    def add_text(self, x, y, w, h, paras, fill=None, line=None, geom='rect', radius=None, anchor='t', inset=(0, 0, 0, 0), name='글', cols=0, wrap=True, fit=True, line_w=None):
        sid = self.sid()
        ins = ''.join(f' {k}="{round(v * EMU * self.kx / EMU)}"' for k, v in zip(('lIns', 'tIns', 'rIns', 'bIns'), inset))
        body = f'<a:bodyPr wrap="{"square" if wrap else "none"}"{ins} rtlCol="0" anchor="{anchor}"' + (f' numCol="{cols}" spcCol="{round(26 * self.kx)}"' if cols else '') + '>' + ('<a:normAutofit/>' if fit else '<a:noAutofit/>') + '</a:bodyPr>'
        self.shapes.append(
            f'<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="{esc(name)} {sid}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr>{self.xfrm(x, y, w, h)}{self.geom(geom, radius, w, h)}{solid(fill) if fill else "<a:noFill/>"}{self.line(line, round(line_w * 9525) if line_w else 9525)}</p:spPr>'
            f'<p:txBody>{body}<a:lstStyle/>{paras or "<a:p/>"}</p:txBody></p:sp>')
        return sid

    @staticmethod
    def line(color, width=9525):
        return f'<a:ln w="{width}">{solid(color)}</a:ln>' if color else '<a:ln><a:noFill/></a:ln>'

    @staticmethod
    def geom(name, radius, w, h):
        if isinstance(name, list):      # clip-path 의 꼭짓점 (%)
            big = 100000
            first, *rest = name
            pts = f'<a:moveTo><a:pt x="{round(first[0] * 1000)}" y="{round(first[1] * 1000)}"/></a:moveTo>'
            pts += ''.join(f'<a:lnTo><a:pt x="{round(p[0] * 1000)}" y="{round(p[1] * 1000)}"/></a:lnTo>' for p in rest)
            return (f'<a:custGeom><a:avLst/><a:gdLst/><a:ahLst/><a:cxnLst/><a:rect l="0" t="0" r="r" b="b"/><a:pathLst><a:path w="{big}" h="{big}">{pts}<a:close/></a:path></a:pathLst></a:custGeom>')
        if name == 'roundRect' and radius:
            adj = min(50000, round(radius / max(1, min(w, h)) * 100000))
            return f'<a:prstGeom prst="roundRect"><a:avLst><a:gd name="adj" fmla="val {adj}"/></a:avLst></a:prstGeom>'
        return f'<a:prstGeom prst="{name}"><a:avLst/></a:prstGeom>'

    def add_rect(self, x, y, w, h, fill, line=None, geom='rect', radius=None, name='상자'):
        sid = self.sid()
        self.shapes.append(
            f'<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="{esc(name)} {sid}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr>{self.xfrm(x, y, w, h)}{self.geom(geom, radius, w, h)}{solid(fill) if fill else "<a:noFill/>"}{self.line(line)}</p:spPr>'
            f'<p:txBody><a:bodyPr rtlCol="0" anchor="ctr"/><a:lstStyle/><a:p><a:endParaRPr lang="ko-KR"/></a:p></p:txBody></p:sp>')
        return sid

    # 그림
    def image_data(self, src):
        path = self.b.resolve(src)
        if path is None:
            self.b.note(self.slide, f'그림을 찾지 못했습니다: {src}')
            return None
        real = self.b.svg.get(str(path), path) if path.suffix.lower() == '.svg' else path
        real = Path(real)
        if real.suffix.lower() == '.svg':
            self.b.note(self.slide, f'SVG 를 PNG 로 바꾸지 못해 뺐습니다: {src}')
            return None
        media = self.pkg.add_media(real.read_bytes(), real.suffix)
        return self.pkg.add_rel(self.part, 'image', '../media/' + media.rsplit('/', 1)[-1]), image_size(real)

    def add_picture(self, x, y, w, h, block, align='ctr'):
        got = self.image_data(block['src'])
        if not got:
            return None
        rid, (iw, ih) = got
        aspect = iw / max(1, ih)
        want_w = block.get('w') or (block.get('h') * aspect if block.get('h') else iw)
        want_h = block.get('h') or want_w / aspect
        scale = min(1, w / max(1, want_w), h / max(1, want_h))
        pw, ph = want_w * scale, want_h * scale
        px = x + (w - pw) / 2 if align == 'ctr' else x + w - pw if align == 'r' else x
        py = y
        return self.picture_xml(rid, px, py, pw, ph, block.get('alt', ''), block.get('link'))

    def picture_xml(self, rid, x, y, w, h, alt='', link=None, crop='', effect=''):
        sid = self.sid()
        click = ''
        if link and re.match(r'https?://|mailto:', link):
            click = f'<a:hlinkClick r:id="{self.pkg.add_rel(self.part, "hyperlink", link, external=True)}"/>'
        self.shapes.append(
            f'<p:pic><p:nvPicPr><p:cNvPr id="{sid}" name="그림 {sid}" descr="{esc(alt)}">{click}</p:cNvPr><p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>'
            f'<p:blipFill><a:blip r:embed="{rid}">{effect}</a:blip>{crop}<a:stretch><a:fillRect/></a:stretch></p:blipFill>'
            f'<p:spPr>{self.xfrm(x, y, w, h)}<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>')
        return sid

    def add_background(self):
        bgs = self.slide['backgrounds']
        if not bgs:
            return (0, self.deck['w'])
        W, H = self.deck['w'], self.deck['h']
        split, side = None, None
        for b in bgs:
            for word in b['words']:
                m = re.fullmatch(r'(left|right)(?::([\d.]+)%)?', word)
                if m:
                    side, split = m[1], float(m[2] or 50) / 100
        x0, x1 = (0, W * split) if side == 'left' else (W * (1 - split), W) if side == 'right' else (0, W)
        vertical = any('vertical' in b['words'] for b in bgs)
        n = len(bgs)
        for i, b in enumerate(bgs):
            rx, ry, rw, rh = (x0, H / n * i, x1 - x0, H / n) if vertical else (x0 + (x1 - x0) / n * i, 0, (x1 - x0) / n, H)
            got = self.image_data(b['src'])
            if not got:
                continue
            rid, (iw, ih) = got
            effect = ''
            for word in b['words']:
                m = re.fullmatch(r'brightness:([\d.]+)', word)
                if m:
                    effect += f'<a:lum bright="{round((float(m[1]) - 1) * 100000)}"/>'
                elif word == 'grayscale':
                    effect += '<a:grayscl/>'
                elif re.match(r'(blur|contrast|hue-rotate|invert|opacity|saturate|sepia)\b', word):
                    self.b.note(self.slide, f'배경 필터 {word} 는 옮기지 못했습니다')
            crop = ''
            if 'contain' in b['words']:
                k = min(rw / iw, rh / ih)
                self.picture_xml(rid, rx + (rw - iw * k) / 2, ry + (rh - ih * k) / 2, iw * k, ih * k, effect=effect)
                continue
            box, img = rw / rh, iw / ih
            if img > box:
                cut = round((1 - box / img) / 2 * 100000)
                crop = f'<a:srcRect l="{cut}" r="{cut}"/>'
            elif img < box:
                cut = round((1 - img / box) / 2 * 100000)
                crop = f'<a:srcRect t="{cut}" b="{cut}"/>'
            self.picture_xml(rid, rx, ry, rw, rh, crop=crop, effect=effect)
        return (x1, W) if side == 'left' else (0, x0) if side == 'right' else (0, W)

    # 표
    def add_table(self, x, y, w, h, block, size):
        rows = block['rows']
        cols = max(len(r) for r in rows)
        rows = [r + [[]] * (cols - len(r)) for r in rows]
        weights = [max(4, max(text_units(lm.plain(r[c])) for r in rows)) for c in range(cols)]
        total = sum(weights)
        floor = w / cols * .45
        widths = [max(floor, w * v / total) for v in weights]
        scale = w / sum(widths)
        widths = [v * scale for v in widths]
        numeric = [sum(1 for r in rows[1:] if re.fullmatch(r'[-+₩$€]?[\d,.]+\s*[%A-Za-z가-힣]{0,3}', lm.plain(r[c]).strip())) >= .7 * max(1, len(rows) - 1) for c in range(cols)]
        px = size / .75
        heights = []
        rules = table_rules(self.deck['css'] + '\n' + self.slide['css'])
        for r in rows:
            need = max(lines_of(lm.plain(cell), widths[c] - 22, size) for c, cell in enumerate(r))
            heights.append(max(px * 1.9, need * px * 1.38 + 12))
        sid = self.sid()
        grid = ''.join(f'<a:gridCol w="{round(v * self.kx)}"/>' for v in widths)
        lines = []
        p = self.p
        for i, r in enumerate(rows):
            cells = []
            for c, cell in enumerate(r):
                head = i == 0
                color = p['th-fg'] if head else p['fg']
                fill = p['th-bg'] if head else (p['stripe'] if i % 2 == 0 else p['table'])
                strong_cell = head
                if not head:
                    for rule in rules:
                        if rule['row'](i, len(rows) - 1) and rule['col'](c + 1):
                            fill = rule.get('fill') or fill
                            color = rule.get('color') or color
                            strong_cell = strong_cell or rule.get('bold', False)
                align = block.get('align', [None] * cols)[c] if c < len(block.get('align', [])) else None
                algn = {'right': 'r', 'center': 'ctr'}.get(align) or ('r' if numeric[c] else 'l')
                paras = self.para(cell, size, color, algn, bold=strong_cell)
                border = ''.join(f'<a:{side} w="6350">{solid(p["border"])}</a:{side}>' if side == 'lnB' else f'<a:{side} w="0"><a:noFill/></a:{side}>' for side in ('lnL', 'lnR', 'lnT', 'lnB'))
                cells.append(f'<a:tc><a:txBody><a:bodyPr/><a:lstStyle/>{paras}</a:txBody><a:tcPr marL="{round(10 * self.kx)}" marR="{round(10 * self.kx)}" marT="{round(4 * self.ky)}" marB="{round(4 * self.ky)}" anchor="ctr">{border}{solid(fill) if fill else "<a:noFill/>"}</a:tcPr></a:tc>')
            lines.append(f'<a:tr h="{round(heights[i] * self.ky)}">{"".join(cells)}</a:tr>')
        total_h = sum(heights)
        X, Y, W, _ = self.box(x, y, w, h)
        self.shapes.append(
            f'<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{sid}" name="표 {sid}"/><p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr><p:nvPr/></p:nvGraphicFramePr>'
            f'<p:xfrm><a:off x="{X}" y="{Y}"/><a:ext cx="{W}" cy="{round(total_h * self.ky)}"/></p:xfrm>'
            f'<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table"><a:tbl><a:tblPr firstRow="1" bandRow="1"/><a:tblGrid>{grid}</a:tblGrid>{"".join(lines)}</a:tbl></a:graphicData></a:graphic></p:graphicFrame>')
        return sid, total_h

    # 차트
    def add_chart(self, x, y, w, h, block):
        model = chart_model(block, self.deck['dir'])
        if model is None:
            return self.add_figure(x, y, w, h, block)
        part = self.pkg.next_part('ppt/charts', 'chart')
        book = self.pkg.next_part('ppt/embeddings', 'Microsoft_Excel_Sheet', 'xlsx')
        series = model['series'] + model.get('lines', [])
        if model['type'] == 'scatter':
            header = ['x'] + [s['name'] for s in series]
            rows = [[s_x] + [s['vals'][i] for s in series] for i, s_x in enumerate(series[0]['x'])]
        else:
            header = ['분류'] + [s['name'] for s in series]
            rows = [[c] + [s['vals'][i] for s in series] for i, c in enumerate(model['cats'])]
        self.pkg.put(book, pp.workbook(header, rows))
        self.pkg.add_default('xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        rid = self.pkg.add_rel(part, 'package', f'../embeddings/{book.rsplit("/", 1)[-1]}')
        self.pkg.put(part, pp.chart_xml(model, rid, model.get('palette') or PALETTE))
        self.pkg.add_override(part, pp.CT_CHART)
        frame = self.pkg.add_rel(self.part, 'chart', f'../charts/{part.rsplit("/", 1)[-1]}')
        sid = self.sid()
        X, Y, W, H = self.box(x, y, w, h)
        self.shapes.append(
            f'<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{sid}" name="차트 {sid}"/><p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr>'
            f'<p:xfrm><a:off x="{X}" y="{Y}"/><a:ext cx="{W}" cy="{H}"/></p:xfrm>'
            f'<a:graphic><a:graphicData uri="{pp.NS_C}"><c:chart xmlns:c="{pp.NS_C}" r:id="{frame}"/></a:graphicData></a:graphic></p:graphicFrame>')
        return sid

    def add_figure(self, x, y, w, h, block):
        """네이티브로 못 옮긴 차트와 다이어그램은 Lectern 의 라이브러리로 그린 그림으로."""
        png = self.b.figure(block, w, h)
        if png is None:
            self.b.note(self.slide, f"{block['lang']} 을 그리지 못해 원문을 넣었습니다")
            return self.add_code(x, y, w, h, block['text'].split('\n'), min(11, self.sizes['code']))
        self.b.note(self.slide, f"{block['lang']} 은 그림으로 넣었습니다. 값은 PowerPoint 에서 고칠 수 없습니다")
        media = self.pkg.add_media(Path(png).read_bytes(), 'png')
        rid = self.pkg.add_rel(self.part, 'image', '../media/' + media.rsplit('/', 1)[-1])
        return self.picture_xml(rid, x, y, w, h, alt=f"{block['lang']} 차트")

    def add_code(self, x, y, w, h, lines, size):
        paras = ''.join(self.para([{'t': row or ' ', 'code': True}], size, self.p['code-fg']) for row in lines)
        return self.add_text(x, y, w, h, paras, fill=self.p['code'], geom='roundRect', radius=6, inset=(12, 8, 12, 8), name='코드', wrap=False, fit=False)

    def quote_height(self, block, width):
        size = self.sizes['box']
        return self.blocks_height(block['blocks'], width - 34, size) + 22 + (size / .75 * 1.5 if block['alert'] else 0)

    def add_quote(self, x, y, w, h, block):
        size = self.sizes['box']
        c = self.style.c
        bar = c.get(f"alert-{(block['alert'] or '').lower()}") or c['quote-bar']
        if self.b.template:
            bar = 'accent1'
        fill = self.p['card']
        paras = ''
        if block['alert']:
            label = {'NOTE': 'Note', 'TIP': 'Tip', 'IMPORTANT': 'Important', 'WARNING': 'Warning', 'CAUTION': 'Caution'}.get(block['alert'], block['alert'])
            paras = self.para([{'t': label}], size, bar, bold=True)
        paras += self.text_paras([b for b in block['blocks'] if b['kind'] in ('para', 'list', 'heading')], size, self.p['heading'] if not block['alert'] else self.p['fg'], 'l')
        sid = self.add_text(x, y, w, h, paras, fill=fill, inset=(18, 8, 12, 8), name='박스글')
        self.add_rect(x, y, 5, h, bar, name='박스글 띠')
        return sid

    # 칸
    def cell_look(self, cell):
        words = set(cell['words'])
        p = self.p
        c = self.style.c
        look = {'fill': None, 'line': None, 'pad': (0, 0), 'geom': 'rect', 'radius': None, 'fg': p['fg'], 'h3': p['h3'], 'bar': None}
        if words & {'card', 'kpi'}:
            look.update(fill=p['card'], line=p['border'], pad=(16, 12) if 'card' in words else (14, 10), geom='roundRect', radius=12)
        if 'accent' in words:
            over = self.dark_page
            look.update(fill=p['card'] if over else c['accent-bg'], line=p['border'] if over else None, pad=(16, 12), geom='rect', bar=None if over else c['accent-bar'])
            if self.b.template:
                look.update(fill='accent1+85', bar='accent1')
        if 'dark' in words:
            base = hex_of('rgba(0,0,0,.55)', p['bg']) if self.dark_page else c['heading']
            look.update(fill=base, pad=(16, 12), geom='roundRect', radius=12, fg=c['bg'] if not self.dark_page else p['fg'], h3=c['bg'] if not self.dark_page else p['fg'])
            if self.b.template:
                look.update(fill='tx2', fg='bg1', h3='bg1')
        if 'note' in words:
            look.update(fill=c['note-bg'], pad=(14, 10), fg=c['note-fg'], h3=c['note-fg'])
        for word in cell['words']:
            custom = self.style.words.get(word)
            if custom:
                if custom.get('bg'):
                    look.update(fill=custom['bg'], pad=(16, 12), geom='roundRect', radius=6)
                if custom.get('fg'):
                    look.update(fg=custom['fg'], h3=custom['fg'])
                if custom.get('line'):
                    look.update(line=custom['line'], line_w=custom['line_w'])
                if 'radius' in custom:
                    look.update(geom='roundRect' if custom['radius'] else 'rect', radius=custom['radius'] or None)
                if custom.get('polygon'):
                    look.update(geom=diamond_or(custom['polygon']), radius=None)
                elif custom.get('ellipse'):
                    look.update(geom='ellipse', radius=None)
        return look

    def segments(self, blocks):
        segs, text = [], []
        for b in blocks:
            if b['kind'] in ('para', 'list', 'heading'):
                text.append(b)
                continue
            if text:
                segs.append({'kind': 'text', 'blocks': text})
                text = []
            segs.append(b)
        if text:
            segs.append({'kind': 'text', 'blocks': text})
        return segs

    def render_cell(self, cell, rect):
        x, y, w, h = rect
        look = self.cell_look(cell)
        words = set(cell['words'])
        size = cell.get('size') or self.sizes['body']
        align = 'ctr' if 'text-center' in words or 'kpi' in words else 'r' if 'text-right' in words else 'l'
        anchor = 'ctr' if 'center' in words or 'kpi' in words else 't'
        px_pad, py_pad = look['pad']
        blocks = cell['blocks']
        if 'kpi' in words:
            return self.render_kpi(cell, rect, look, size)
        segs = self.segments(blocks)
        only_text = len(segs) <= 1 and (not segs or segs[0]['kind'] == 'text')
        if only_text:
            paras = self.text_paras(segs[0]['blocks'], size, look['fg'], align, look['h3']) if segs else ''
            cols = 2 if 'cols-2' in words else 3 if 'cols-3' in words else 0
            sid = self.add_text(x, y, w, h, paras, fill=look['fill'], line=look['line'], geom=look['geom'], radius=look['radius'], anchor=anchor,
                                inset=(px_pad, py_pad, px_pad, py_pad), name=f"칸 {cell['name']}", cols=cols, line_w=look.get('line_w'))
            if look['bar']:
                self.add_rect(x, y, 5, h, look['bar'], name='칸 띠')
            self.anchors[cell['name']] = (sid, rect)
            return
        back = None
        if look['fill'] or look['line']:
            back = self.add_rect(x, y, w, h, look['fill'], look['line'], look['geom'], look['radius'], name=f"칸 {cell['name']}")
            if look['bar']:
                self.add_rect(x, y, 5, h, look['bar'], name='칸 띠')
        ix, iy, iw, ih = x + px_pad, y + py_pad, w - 2 * px_pad, h - 2 * py_pad
        fixed = []
        flexible = 0
        for s in segs:
            k = s['kind']
            if k == 'text':
                need = self.blocks_height(s['blocks'], iw, size)
            elif k == 'table':
                tsize = cell.get('size') or self.sizes['table']
                need = len(s['rows']) * (tsize / .75 * 1.95)
            elif k == 'code':
                csize = cell.get('size') or self.sizes['code']
                need = len(s['lines']) * csize / .75 * 1.5 + 18
            elif k == 'quote':
                need = self.quote_height(s, iw)
            else:
                need = None
                flexible += 1
            fixed.append(need)
        gap = 10
        room = ih - sum(v for v in fixed if v) - gap * (len(segs) - 1)
        share = max(60, room / flexible) if flexible else 0
        used = sum(v if v is not None else 0 for v in fixed) + gap * (len(segs) - 1)
        if flexible:
            sizes = []
            for s, v in zip(segs, fixed):
                if v is not None:
                    sizes.append(v)
                elif s['kind'] == 'image':
                    got = self.b.resolve(s['src'])
                    iw0, ih0 = image_size(self.b.svg.get(str(got), got)) if got else (4, 3)
                    want = (s.get('w') or iw0) / max(1, iw0 / max(1, ih0)) if not s.get('h') else s['h']
                    sizes.append(min(share, want * min(1, iw / max(1, s.get('w') or iw0))))
                elif s['kind'] == 'diagram' or s['kind'] == 'chart':
                    sizes.append(share)
                else:
                    sizes.append(share)
            used = sum(sizes) + gap * (len(segs) - 1)
        else:
            sizes = fixed
        cy = iy + (ih - used) / 2 if anchor == 'ctr' and used < ih else iy
        first = None
        for s, need in zip(segs, sizes):
            k = s['kind']
            bottom = max(20, min(need, iy + ih - cy))
            sid = None
            if k == 'text':
                sid = self.add_text(ix, cy, iw, bottom, self.text_paras(s['blocks'], size, look['fg'], align, look['h3']), name=f"칸 {cell['name']}")
            elif k == 'image':
                sid = self.add_picture(ix, cy, iw, bottom, s, align if (align != 'l' or anchor == 'ctr') else 'l')
            elif k == 'table':
                sid, _ = self.add_table(ix, cy, iw, bottom, s, cell.get('size') or self.sizes['table'])
            elif k == 'code':
                sid = self.add_code(ix, cy, iw, bottom, s['lines'], cell.get('size') or self.sizes['code'])
            elif k == 'chart':
                sid = self.add_chart(ix, cy, iw, bottom, s)
            elif k == 'quote':
                sid = self.add_quote(ix, cy, iw, bottom, s)
            elif k == 'diagram':
                sid = self.add_figure(ix, cy, iw, bottom, s)
            first = first or sid
            cy += need + gap
        self.anchors[cell['name']] = (back or first or self.sid(), rect)

    def kpi_color(self, cell, look):
        """문서가 정한 색이 먼저다. 칸 바탕에서 안 읽히면 칸의 글자색을 쓴다."""
        for word in cell['words']:
            custom = self.style.words.get(word) or {}
            if custom.get('strong'):
                return custom['strong']
        color = self.p['kpi']
        fill = self.b.rgb(look['fill'])
        mine = self.b.rgb(color)
        if fill and mine and contrast(fill, mine) < 3:
            return look['fg']
        return color

    def render_kpi(self, cell, rect, look, size):
        x, y, w, h = rect
        paras = ''
        number = self.kpi_color(cell, look)
        for b in cell['blocks']:
            if b['kind'] == 'heading':
                paras += self.para(b['runs'], size * 1.15 if cell.get('size') else self.sizes['sub'], look['h3'], 'ctr', bold=True)
            elif b['kind'] == 'list':
                paras += self.text_paras([b], size, look['fg'], 'ctr')
            elif b['kind'] == 'para':
                rows, cur = [], []
                for r in b['runs']:
                    if r['t'] == '\n':
                        rows.append(cur)
                        cur = []
                    else:
                        cur.append(r)
                rows.append(cur)
                for row in rows:
                    big = [r for r in row if r.get('b')]
                    rest = [r for r in row if not r.get('b') and r['t'].strip()]
                    if big:
                        paras += self.para([{'t': lm.plain(big)}], size * 1.9, number, 'ctr', bold=True)
                    if rest:
                        paras += self.para(rest, size, look['fg'], 'ctr', before=2)
        sid = self.add_text(x, y, w, h, paras, fill=look['fill'], line=look['line'], geom=look['geom'], radius=look['radius'], anchor='ctr',
                            inset=(14, 10, 14, 10), name=f"칸 {cell['name']}", line_w=look.get('line_w'))
        self.anchors[cell['name']] = (sid, rect)

    # 배치
    def grid(self):
        eff = self.slide['eff']
        grid, cols, rows = eff.get('grid'), eff.get('cols'), eff.get('rows')
        layout = eff.get('layout')
        if not grid and layout in lm.LAYOUTS:
            grid, c, r = lm.LAYOUTS[layout]
            cols, rows = cols or c, rows or r
        if not isinstance(grid, str) or not grid.strip():
            return None
        table = [row.split() for row in grid.split('/')]
        return table, cols, rows

    def tracks(self, spec, count, total, gap, autos, fixed=()):
        items = []
        for bit in re.findall(r'repeat\(\s*(\d+)\s*,\s*([^)]+)\)|(\S+)', str(spec or '')):
            items += [bit[1].strip()] * int(bit[0]) if bit[0] else [bit[2]]
        if len(items) != count:      # 앱과 같다: 설정이 없으면 제목 줄만 글 높이, 나머지는 같은 높이
            items = ['auto' if i in fixed else '1fr' for i in range(count)]
        out = [0.0] * count
        room = total - gap * (count - 1)
        parts = 0
        for i, v in enumerate(items):
            if v.endswith('px'):
                out[i] = float(v[:-2])
                room -= out[i]
            elif v == 'auto':
                out[i] = autos.get(i, 40)
                room -= out[i]
            elif v.endswith('fr'):
                parts += float(v[:-2])
            else:
                parts += 1
        for i, v in enumerate(items):
            if v.endswith('fr'):
                out[i] = max(0, room * float(v[:-2]) / parts) if parts else 0
            elif not v.endswith('px') and v != 'auto':
                out[i] = max(0, room / parts) if parts else 0
        return out

    def title_height(self, width, level=2):
        title = self.slide['title']
        size = self.sizes['title'] * (1.2 if level == 1 else 1)
        px = size / .75
        return lines_of(lm.plain(title), width, size * 1.05) * px * 1.25 + 6 if title else 0

    def layout_cells(self, x0, x1):
        """격자에서 칸마다 자리를 낸다. 앱과 같은 여백과 틈이다."""
        got = self.grid()
        cells = {c['name']: c for c in self.slide['cells']}
        rects = {}
        title_rect = None
        pad_t, pad_b = 38, 46
        left = x0 + 56
        right = x1 - 56
        if got:
            table, cols, rows = got
            ncol, nrow = len(table[0]), len(table)
            autos = {}
            names = [set(r) for r in table]
            for i, row in enumerate(names):
                if 't' in row:
                    autos[i] = self.title_height(right - left, self.slide['title_level'])
                else:
                    tall = 0
                    for name in row - {'.'}:
                        if name in cells:
                            tall = max(tall, self.cell_height(cells[name], (right - left) / ncol))
                    autos[i] = tall or 40
            ws = self.tracks(cols, ncol, right - left, 18, {})
            hs = self.tracks(rows, nrow, self.deck['h'] - pad_t - pad_b, 14, autos, {i for i, row in enumerate(names) if 't' in row})
            xs = [left]
            for v in ws:
                xs.append(xs[-1] + v + 18)
            ys = [pad_t]
            for v in hs:
                ys.append(ys[-1] + v + 14)
            spots = {}
            for r, row in enumerate(table):
                for c, name in enumerate(row):
                    spots.setdefault(name, []).append((r, c))
            for name, where in spots.items():
                if name == '.':
                    continue
                r0, r1 = min(a for a, _ in where), max(a for a, _ in where)
                c0, c1 = min(b for _, b in where), max(b for _, b in where)
                rect = (xs[c0], ys[r0], xs[c1] + ws[c1] - xs[c0], ys[r1] + hs[r1] - ys[r0])
                if name == 't':
                    title_rect = rect
                else:
                    rects[name] = rect
        for c in self.slide['cells']:
            if c.get('at'):
                rects[c['name']] = c['at']
        return rects, title_rect

    def cell_height(self, cell, width):
        words = set(cell['words'])
        size = cell.get('size') or self.sizes['body']
        if 'kpi' in words:
            return size / .75 * 1.9 * 1.15 + size / .75 * LINE + 22
        pad = 24 if words & {'card', 'accent', 'dark', 'note'} else 0
        total = self.blocks_height([b for b in cell['blocks'] if b['kind'] in ('para', 'list', 'heading')], width - 32, size) + pad
        for b in cell['blocks']:
            if b['kind'] == 'table':
                total += len(b['rows']) * (cell.get('size') or self.sizes['table']) / .75 * 1.95
            elif b['kind'] == 'code':
                total += len(b['lines']) * (cell.get('size') or self.sizes['code']) / .75 * 1.5 + 18
            elif b['kind'] == 'quote':
                total += self.quote_height(b, width)
            elif b['kind'] == 'image' and (b.get('h') or b.get('w')):
                got = self.b.resolve(b['src'])
                iw, ih = image_size(self.b.svg.get(str(got), got)) if got else (4, 3)
                total += b.get('h') or b['w'] * ih / max(1, iw)
        return total

    def add_title(self, rect, runs, level, align='l', color=None, kind='title'):
        x, y, w, h = rect
        px_size = self.sizes['title'] * (1.2 if level == 1 else 1)
        if self.lead and level == 1:
            px_size = self.sizes['title'] * 1.45
        target = self.layout_ph(kind)
        sid = self.sid()
        if target is not None:
            paras = self.para(runs, px_size if not self.b.template else None, color, align, bold=False) if False else self.title_para(runs, px_size, color, align)
            self.shapes.append(
                f'<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="제목 {sid}"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph {target}/></p:nvPr></p:nvSpPr>'
                f'<p:spPr>{self.xfrm(x, y, w, h)}</p:spPr><p:txBody><a:bodyPr lIns="0" tIns="0" rIns="0" bIns="0" anchor="t"><a:normAutofit/></a:bodyPr><a:lstStyle/>{paras}</p:txBody></p:sp>')
        else:
            self.shapes.append(
                f'<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="제목 {sid}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
                f'<p:spPr>{self.xfrm(x, y, w, h)}<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>'
                f'<p:txBody><a:bodyPr wrap="square" lIns="0" tIns="0" rIns="0" bIns="0" anchor="t"><a:normAutofit/></a:bodyPr><a:lstStyle/>{self.title_para(runs, px_size, color, align)}</p:txBody></p:sp>')
        return sid

    def title_para(self, runs, size, color, align):
        keep = self.b.template and color is None
        fixed = None if keep and self.b.title_pt <= size * self.fs else size
        body = ''.join(f'<a:r>{self.rpr({**r, "b": True} if not keep else r, fixed, color)}<a:t>{esc(t)}</a:t></a:r>' for r in runs for t in [r['t'].replace('\n', ' ')] if t)
        return f'<a:p><a:pPr algn="{align}"/>{body}</a:p>'

    def layout_ph(self, kind):
        """레이아웃에 그 자리 표시자가 있으면 ph 속성 글을 준다."""
        for t, idx in self.layout['ph']:
            if t == kind or (kind == 'title' and t in ('title', 'ctrTitle')) or (kind == 'ctrTitle' and t == 'title'):
                return f'type="{t}"' + (f' idx="{idx}"' if idx else '')
        return None

    def render(self):
        s = self.slide
        eff = s['eff']
        W, H = self.deck['w'], self.deck['h']
        x0, x1 = self.add_background()
        self.bands()
        if self.lead and not s['cells']:
            self.render_lead(x0, x1)
        elif s['cells'] or self.grid():
            rects, title_rect = self.layout_cells(x0, x1)
            title = s['title']
            if title:
                if title_rect is None:
                    title_rect = (x0 + 56, 38, x1 - x0 - 112, self.title_height(x1 - x0 - 112, s['title_level']))
                self.add_title(title_rect, title, s['title_level'], color=self.title_color())
            for cell in s['cells']:
                rect = rects.get(cell['name'])
                if rect is None:
                    self.b.note(s, f"칸 {cell['name']} 의 자리를 찾지 못해 아래에 놓았습니다")
                    rect = (56, 560, 300, 100)
                self.render_cell(cell, rect)
            if s['body']:
                self.b.note(s, '칸 밖의 글을 맨 아래에 놓았습니다')
                self.render_cell({'name': 'body', 'words': [], 'size': None, 'at': None, 'blocks': s['body']}, (x0 + 56, H - 120, x1 - x0 - 112, 70))
            self.render_links(eff.get('links'))
        else:
            self.render_flow(x0, x1)
        self.render_edges(x0, x1)

    def title_color(self):
        return None if self.b.template and not hex_of(self.slide['eff'].get('color')) else self.p['heading']

    def render_flow(self, x0, x1):
        """칸이 없는 쪽: 제목과 글을 위아래로 놓고 가운데로 모은다."""
        s = self.slide
        H = self.deck['h']
        left, width = x0 + 84, x1 - x0 - 168
        size = self.sizes['body']
        th = self.title_height(width, s['title_level'])
        segs = self.segments(s['body'])
        heights = []
        room = H - 128 - th - 14
        fixed = 0
        for g in segs:
            if g['kind'] == 'text':
                v = self.blocks_height(g['blocks'], width, size)
            elif g['kind'] == 'table':
                v = len(g['rows']) * self.sizes['table'] / .75 * 1.95
            elif g['kind'] == 'code':
                v = len(g['lines']) * self.sizes['code'] / .75 * 1.5 + 18
            elif g['kind'] == 'quote':
                v = self.quote_height(g, width)
            else:
                v = None
            heights.append(v)
            fixed += v or 0
        flex = sum(1 for v in heights if v is None)
        share = max(120, (room - fixed - 12 * len(segs)) / flex) if flex else 0
        heights = [v if v is not None else share for v in heights]
        total = th + sum(heights) + 14 + 12 * max(0, len(segs) - 1)
        y = max(64, (H - total) / 2)
        if s['title']:
            self.add_title((left, y, width, th), s['title'], s['title_level'], color=self.title_color())
            y += th + 14
        for g, v in zip(segs, heights):
            self.render_cell({'name': 'body', 'words': [], 'size': None, 'at': None, 'blocks': g.get('blocks') if g['kind'] == 'text' else [g]}, (left, y, width, v))
            y += v + 12

    def render_lead(self, x0, x1):
        s = self.slide
        H = self.deck['h']
        left, width = x0 + 84, x1 - x0 - 168
        level = s['title_level']
        size = self.sizes['title'] * (1.45 if level == 1 else 1)
        px = size / .75
        th = (lines_of(lm.plain(s['title']), width, size * 1.05) * px * 1.25 + 8) if s['title'] else 0
        items = []
        before = s.get('before_title', 0)
        for b in s['body']:
            if b['kind'] == 'image':
                got = self.b.resolve(b['src'])
                iw, ih = image_size(self.b.svg.get(str(got), got)) if got else (4, 3)
                w = b.get('w') or iw
                items.append((b, (b.get('h') or w * ih / max(1, iw)) + 12))
            else:
                items.append((b, self.blocks_height([b], width, self.sizes['body']) + 6 if b['kind'] in ('para', 'list', 'heading') else 60))
        total = th + sum(v for _, v in items) + 12
        y = max(40, (H - total) / 2)
        split = before if before <= len(items) else 0
        for b, v in items[:split]:
            self.lead_item(b, left, y, width, v)
            y += v
        if s['title']:
            self.add_title((left, y, width, th), s['title'], level, self.lead_align(), self.lead_title_color(), 'ctrTitle' if level == 1 else 'title')
            y += th + 12
        for b, v in items[split:]:
            self.lead_item(b, left, y, width, v)
            y += v

    def lead_align(self):
        return {'left': 'l', 'right': 'r'}.get(self.style.doc.get('align'), 'ctr')

    def lead_title_color(self):
        return None if self.b.template and not self.custom_bg else self.p['heading']

    def in_layout(self, block):
        """이 레이아웃이 이미 보여 주는 그림이나 글이면 True."""
        if not self.b.template:
            return False
        names = [self.layout['part']] + [self.pkg.target(self.layout['part'], t) for _, k, t, _ in self.pkg.rels(self.layout['part']) if k.endswith('/slideMaster')]
        if block['kind'] == 'image':
            path = self.b.resolve(block['src'])
            if path is None:
                return False
            data = path.read_bytes()
            return any(self.pkg.files.get(self.pkg.target(n, t)) == data for n in names for _, k, t, _ in self.pkg.rels(n) if k.endswith('/image'))
        if block['kind'] == 'para':
            text = ' '.join(lm.plain(block['runs']).split())
            return bool(text) and any(text in ' '.join(' '.join(re.findall(r'<a:t>([^<]*)</a:t>', self.pkg.text(n))).split()) for n in names)
        return False

    def lead_item(self, b, x, y, w, h):
        if self.in_layout(b):
            return
        if b['kind'] == 'image':
            self.add_picture(x, y, w, h, b, self.lead_align())
        elif b['kind'] in ('para', 'list', 'heading'):
            self.add_text(x, y, w, h, self.text_paras([b], self.sizes['body'], self.p['fg'], self.lead_align(), self.p['heading']), name='글')
        else:
            self.render_cell({'name': 'body', 'words': [], 'size': None, 'at': None, 'blocks': [b]}, (x, y, w, h))

    def render_links(self, spec):
        if not isinstance(spec, str):
            return
        c = self.style.c
        color = self.p['muted']
        width = 19050
        doc = self.deck['css'] + '\n' + self.slide['css']
        m = re.search(r'--lec-link-color\s*:\s*([^;}]+)', doc)
        if m and hex_of(m[1]):
            color = hex_of(m[1])
        m = re.search(r'--lec-link-width\s*:\s*([\d.]+)', doc)
        if m:
            width = round(float(m[1]) * 9525)
        for bit in spec.split(','):
            m = re.match(r'^\s*([^\s<>-]+)\s*(<>|>|--)\s*([^\s<>-]+)\s*$', bit)
            if not m:
                continue
            a, kind, b = m[1], m[2], m[3]
            if a not in self.anchors or b not in self.anchors:
                self.b.note(self.slide, f'선의 칸 {a} 또는 {b} 를 찾지 못했습니다')
                continue
            ida, ra = self.anchors[a]
            idb, rb = self.anchors[b]
            p1, s1 = edge_point(ra, rb)
            p2, s2 = edge_point(rb, ra)
            x, y = min(p1[0], p2[0]), min(p1[1], p2[1])
            w, h = abs(p2[0] - p1[0]), abs(p2[1] - p1[1])
            flip = (' flipH="1"' if p2[0] < p1[0] else '') + (' flipV="1"' if p2[1] < p1[1] else '')
            sid = self.sid()
            head = '<a:headEnd type="triangle"/>' if kind == '<>' else ''
            tail = '<a:tailEnd type="triangle"/>' if kind in ('>', '<>') else ''
            self.shapes.append(
                f'<p:cxnSp><p:nvCxnSpPr><p:cNvPr id="{sid}" name="선 {sid}"/><p:cNvCxnSpPr><a:stCxn id="{ida}" idx="{s1}"/><a:endCxn id="{idb}" idx="{s2}"/></p:cNvCxnSpPr><p:nvPr/></p:nvCxnSpPr>'
                f'<p:spPr>{self.xfrm(x, y, w, h, flip)}<a:prstGeom prst="straightConnector1"><a:avLst/></a:prstGeom><a:ln w="{width}">{solid(color)}{head}{tail}</a:ln></p:spPr></p:cxnSp>')

    def render_edges(self, x0, x1):
        s = self.slide
        eff = s['eff']
        H = self.deck['h']
        small = 9.9
        if isinstance(eff.get('eyebrow'), str) and eff['eyebrow'].strip():
            self.add_text(x0 + 56, 14, x1 - x0 - 112, 22, self.para([{'t': eff['eyebrow'], 'b': True, 'code': True}], 11, self.p['link']), name='머리글', fit=False)
        if isinstance(eff.get('header'), str) and eff['header'].strip():
            self.add_text(x0 + 56, 22, x1 - x0 - 140, 18, self.para(lm.inline(eff['header']), small, self.p['muted']), name='머리말', fit=False)
        if isinstance(eff.get('footer'), str) and eff['footer'].strip():
            self.add_text(x0 + 56, H - 38, x1 - x0 - 140, 18, self.para(lm.inline(eff['footer']), small, self.p['muted'], 'ctr' if self.lead else 'l'), name='꼬리말', fit=False)
        if eff.get('paginate') is True:
            size = round(small * self.fs * 100)
            field = f'<a:fld id="{{B6F15528-21DE-4FAA-801E-634DDDAF4B2B}}" type="slidenum"><a:rPr lang="ko-KR" sz="{size}">{solid(self.p["muted"])}</a:rPr><a:t>‹#›</a:t></a:fld>'
            self.add_text(x1 - 136, H - 38, 80, 18, f'<a:p><a:pPr algn="r"/>{field}</a:p>', name='쪽 번호', fit=False)

    def xml(self):
        s = self.slide
        bg = ''
        color = self.custom_bg or (self.p['bg'] if (self.dark_page and not self.b.template) else None)
        if color:
            bg = f'<p:bg><p:bgPr>{solid(color)}<a:effectLst/></p:bgPr></p:bg>'
        hidden = ' show="0"' if s['eff'].get('hidden') is True else ''
        return (f'{pp.HEAD}<p:sld {pp.XMLNS}{hidden}><p:cSld>{bg}<p:spTree>{pp.EMPTY_TREE}{"".join(self.shapes)}</p:spTree></p:cSld>'
                '<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>')


def contrast(a, b):
    x, y = sorted((luminance(a), luminance(b)), reverse=True)
    return (x + .05) / (y + .05)


def table_rules(css):
    """표의 행·열 강조. tbody tr:last-child td, tr:nth-child(n+4) td, td:nth-child(4)"""
    out = []
    for m in re.finditer(r'(?:tbody\s+)?(tr:(?:last-child|nth-child\(([^)]*)\))\s+)?td(?::nth-child\((\d+)\))?\s*\{([^}]*)\}', css or ''):
        row, pick, col, body = m[1], m[2], m[3], m[4]
        if not row and not col:
            continue
        rule = {}
        if row and 'last-child' in row:
            rule['row'] = lambda i, last: i == last
        elif pick and re.fullmatch(r'n\s*\+\s*\d+', pick):
            k = int(pick.split('+')[1])
            rule['row'] = lambda i, last, k=k: i >= k
        elif pick and pick.isdigit():
            k = int(pick)
            rule['row'] = lambda i, last, k=k: i == k
        elif not row:
            rule['row'] = lambda i, last: True
        else:
            continue
        rule['col'] = (lambda c, k=int(col): c == k) if col else (lambda c: True)
        bg = re.search(r'(?<![\w-])background(?:-color)?\s*:\s*([^;}]+)', body)
        fg = re.search(r'(?<![\w-])color\s*:\s*([^;}]+)', body)
        if bg and hex_of(bg[1]):
            rule['fill'] = hex_of(bg[1])
        if fg and hex_of(fg[1]):
            rule['color'] = hex_of(fg[1])
        if re.search(r'font-weight\s*:\s*(bold|[6-9]00)', body):
            rule['bold'] = True
        out.append(rule)
    return out


def diamond_or(points):
    return 'diamond' if sorted(points) == sorted([(50, 0), (100, 50), (50, 100), (0, 50)]) else points


def edge_point(a, b):
    """칸 a 의 테두리에서 칸 b 쪽을 향한 점과 연결 자리(0 위, 1 왼쪽, 2 아래, 3 오른쪽)."""
    ax, ay = a[0] + a[2] / 2, a[1] + a[3] / 2
    bx, by = b[0] + b[2] / 2, b[1] + b[3] / 2
    dx, dy = bx - ax, by - ay
    if abs(dx) * a[3] >= abs(dy) * a[2]:
        return ((a[0] + a[2], ay), 3) if dx > 0 else ((a[0], ay), 1)
    return ((ax, a[1] + a[3]), 2) if dy > 0 else ((ax, a[1]), 0)


def number(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    try:
        return float(str(v).replace(',', ''))
    except ValueError:
        return None


def pivot(rows, cat, val, series):
    cats = list(dict.fromkeys(str(r.get(cat)) for r in rows))
    names = list(dict.fromkeys(str(r.get(series)) for r in rows)) if series else [val]
    table = {}
    for r in rows:
        table[(str(r.get(cat)), str(r.get(series)) if series else val)] = number(r.get(val))
    return cats, [{'name': n, 'vals': [table.get((c, n)) for c in cats]} for n in names]


def chart_model(block, base):
    try:
        spec = json.loads(block['text'])
    except ValueError:
        return None
    if block['lang'] == 'vega-lite':
        return vega_model(spec, base)
    if block['lang'] == 'echarts':
        return echarts_model(spec)
    return plotly_model(spec)


def inline_data(text, base):
    """그림으로 그릴 때는 CSV 를 문서 안 값으로 바꿔 넘긴다."""
    spec = json.loads(text)
    data = spec.get('data') or {}
    if data.get('url'):
        path = Path(base) / data['url']
        if path.exists():
            spec['data'] = {'values': lm.read_table_file(path)}
    return json.dumps(spec, ensure_ascii=False)


def mark_of(item):
    m = item.get('mark')
    return m.get('type') if isinstance(m, dict) else m


def fields_of(enc):
    return {v.get('field') for v in (enc or {}).values() if isinstance(v, dict) and v.get('field')}


def transformed(rows, steps, needed):
    """접기(fold)만 한다. 쓰지 않는 계산은 건너뛰고, 그 밖의 변환이면 None — 그림으로 그린다."""
    for step in steps or []:
        if 'fold' in step:
            key, value = (step.get('as') or ['key', 'value'])[:2]
            out = []
            for r in rows:
                for name in step['fold']:
                    item = {k: v for k, v in r.items() if k not in step['fold']}
                    item[key], item[value] = name, r.get(name)
                    out.append(item)
            rows = out
        elif 'calculate' in step and step.get('as') not in needed:
            continue
        else:
            return None
    return rows


def rule_value(layer):
    """가로 기준선의 값. 계산이 필요한 것은 None — 그림으로 그린다."""
    enc = layer.get('encoding') or {}
    y = enc.get('y') or {}
    value = number(y.get('datum'))
    if value is None:
        rows = (layer.get('data') or {}).get('values') or []
        if len(rows) == 1 and y.get('field'):
            value = number(rows[0].get(y['field']))
    if value is None:
        return None
    mark = layer.get('mark')
    color = hex_of(mark.get('color')) if isinstance(mark, dict) else None
    return (f'기준 {value:g}', value, color or '5C6773')


def condition_color(rows, color):
    """datum['값'] > 200 같은 간단한 조건 색을 쪽별 색으로."""
    test = (color.get('condition') or {})
    if isinstance(test, list):
        return None
    m = re.fullmatch(r"\s*datum(?:\['([^']+)'\]|\.(\w+))\s*(>=|<=|==|===|!=|>|<)\s*(-?[\d.]+)\s*", str(test.get('test') or ''))
    yes, no = hex_of(test.get('value')), hex_of(color.get('value'))
    if not m or not yes or not no:
        return None
    field, op, limit = m[1] or m[2], m[3], float(m[4])
    ops = {'>': lambda a: a > limit, '<': lambda a: a < limit, '>=': lambda a: a >= limit, '<=': lambda a: a <= limit, '==': lambda a: a == limit, '===': lambda a: a == limit, '!=': lambda a: a != limit}
    out = []
    for r in rows:
        v = number(r.get(field))
        out.append(yes if v is not None and ops[op](v) else no)
    return out


def vega_model(spec, base):
    layers = spec.get('layer') or [spec]
    first = next((l for l in layers if mark_of(l) in ('bar', 'line', 'area', 'arc', 'point', 'circle')), None)
    if first is None:
        return None
    rest = [mark_of(l) for l in layers if l is not first]
    if any(m not in ('text', 'line', 'point', 'rule') for m in rest):
        return None
    limits = [v for v in (rule_value(l) for l in layers if mark_of(l) == 'rule') if v]
    if 'rule' in rest and len(limits) != rest.count('rule'):
        return None
    layer = {**spec, **first, 'encoding': {**(spec.get('encoding') or {}), **(first.get('encoding') or {})}}
    data = first.get('data') or spec.get('data') or {}
    rows = data.get('values')
    if rows is None and data.get('url'):
        path = Path(base) / data['url']
        if not path.exists():
            return None
        rows = lm.read_table_file(path)
    if not rows:
        return None
    rows = transformed(rows, (spec.get('transform') or []) + (first.get('transform') or []), fields_of(layer['encoding']))
    if rows is None:
        return None
    mark = layer.get('mark')
    kind = mark.get('type') if isinstance(mark, dict) else mark
    if kind == 'point' and 'line' in rest:
        kind = 'line'
    enc = layer.get('encoding') or {}
    color = enc.get('color') or {}
    labels = 'text' in rest
    paint = condition_color(rows, color)
    series = color.get('field')
    palette = None
    rng = (color.get('scale') or {}).get('range')
    if isinstance(rng, list):
        palette = [hex_of(c) for c in rng if hex_of(c)] or None
    single = (mark.get('color') if isinstance(mark, dict) else None) or (color.get('value'))
    if single and hex_of(single):
        palette = [hex_of(single)]
    if kind == 'arc':
        theta = (enc.get('theta') or {}).get('field')
        if not theta or not series:
            return None
        cats, s = pivot(rows, series, theta, None)
        return {'type': 'doughnut' if isinstance(mark, dict) and mark.get('innerRadius') else 'pie', 'cats': cats, 'series': s, 'palette': palette, 'labels': labels}
    x, y = enc.get('x') or {}, enc.get('y') or {}
    if not x.get('field') or not y.get('field'):
        return None
    if kind in ('point', 'circle') and x.get('type') == 'quantitative' and y.get('type') == 'quantitative':
        names = list(dict.fromkeys(str(r.get(series)) for r in rows)) if series else [y['field']]
        xs = [number(r.get(x['field'])) for r in rows]
        return {'type': 'scatter', 'palette': palette,
                'series': [{'name': n, 'x': xs, 'vals': [number(r.get(y['field'])) if not series or str(r.get(series)) == n else None for r in rows]} for n in names]}
    if kind not in ('bar', 'line', 'area', 'point', 'circle'):
        return None
    horizontal = x.get('type') == 'quantitative' and y.get('type') != 'quantitative'
    cat, val = (y, x) if horizontal else (x, y)
    cats, s = pivot(rows, cat['field'], val['field'], series)
    order = cat.get('sort')
    if isinstance(order, list) and set(map(str, order)) >= set(cats):
        ranks = {str(v): i for i, v in enumerate(order)}
        idx = sorted(range(len(cats)), key=lambda i: ranks.get(cats[i], 0))
        cats = [cats[i] for i in idx]
        for item in s:
            item['vals'] = [item['vals'][i] for i in idx]
    if paint and len(s) == 1 and len(paint) == len(cats):
        s[0]['colors'] = paint
    if order in ('-y', '-x', 'y', 'x') and len(s) == 1:
        idx = sorted(range(len(cats)), key=lambda i: s[0]['vals'][i] or 0, reverse=order.startswith('-'))
        cats = [cats[i] for i in idx]
        s[0]['vals'] = [s[0]['vals'][i] for i in idx]
        if s[0].get('colors'):
            s[0]['colors'] = [s[0]['colors'][i] for i in idx]
    grouping = 'clustered'
    if kind in ('bar', 'area') and series and not (enc.get('xOffset') or enc.get('yOffset')):
        grouping = 'stacked'
    if val.get('stack') == 'normalize':
        grouping = 'percentStacked'
    if val.get('stack') in (False, None) and 'stack' in val:
        grouping = 'clustered'
    lines = [{'name': name, 'vals': [value] * len(cats), 'color': color} for name, value, color in limits]
    if lines and horizontal:
        return None      # 세로 기준선은 pptx 선 계열로 그릴 수 없다
    return {'type': {'bar': 'bar', 'area': 'area'}.get(kind, 'line'), 'dir': 'bar' if horizontal else 'col', 'grouping': grouping, 'cats': cats, 'series': s, 'palette': palette, 'labels': labels, 'lines': lines}


def echarts_model(spec):
    series = spec.get('series') or []
    if isinstance(series, dict):
        series = [series]
    if not series:
        return None
    first = series[0]
    kind = first.get('type')
    if kind == 'pie':
        data = first.get('data') or []
        hole = first.get('radius')
        return {'type': 'doughnut' if isinstance(hole, list) else 'pie', 'cats': [str(d.get('name')) for d in data],
                'series': [{'name': first.get('name') or '값', 'vals': [number(d.get('value')) for d in data]}]}
    if kind == 'radar':
        radar = spec.get('radar') or {}
        radar = radar[0] if isinstance(radar, list) else radar
        cats = [str(i.get('name')) for i in radar.get('indicator', [])]
        return {'type': 'radar', 'cats': cats, 'series': [{'name': str(d.get('name') or f'계열{i + 1}'), 'vals': [number(v) for v in d.get('value', [])]} for i, d in enumerate(first.get('data') or [])]}
    if kind not in ('bar', 'line'):
        return None
    xa, ya = spec.get('xAxis') or {}, spec.get('yAxis') or {}
    xa = xa[0] if isinstance(xa, list) else xa
    ya = ya[0] if isinstance(ya, list) else ya
    horizontal = ya.get('type') == 'category' or (ya.get('data') and not xa.get('data'))
    cats = [str(c) for c in ((ya if horizontal else xa).get('data') or [])]
    if not cats:
        return None
    out = []
    for i, s in enumerate(series):
        vals = [number(v.get('value') if isinstance(v, dict) else v) for v in s.get('data') or []]
        out.append({'name': str(s.get('name') or f'계열{i + 1}'), 'vals': vals + [None] * (len(cats) - len(vals))})
    stacked = any(s.get('stack') for s in series)
    return {'type': 'line' if kind == 'line' else 'bar', 'dir': 'bar' if horizontal else 'col', 'grouping': 'stacked' if stacked else 'clustered', 'cats': cats, 'series': out}


def plotly_model(spec):
    data = spec.get('data') or []
    if not data:
        return None
    first = data[0]
    kind = first.get('type', 'scatter')
    if kind == 'pie':
        return {'type': 'doughnut' if first.get('hole') else 'pie', 'cats': [str(c) for c in first.get('labels', [])], 'series': [{'name': '값', 'vals': [number(v) for v in first.get('values', [])]}]}
    if kind not in ('bar', 'scatter'):
        return None
    horizontal = first.get('orientation') == 'h'
    key_c, key_v = ('y', 'x') if horizontal else ('x', 'y')
    cats = [str(c) for c in first.get(key_c, [])]
    if not cats:
        return None
    mode = (spec.get('layout') or {}).get('barmode')
    return {'type': 'bar' if kind == 'bar' else 'line', 'dir': 'bar' if horizontal else 'col', 'grouping': 'stacked' if mode == 'stack' else 'clustered', 'cats': cats,
            'series': [{'name': str(t.get('name') or f'계열{i + 1}'), 'vals': [number(v) for v in t.get(key_v, [])]} for i, t in enumerate(data)]}


# ---- 패키지 조립

def layouts_of(pkg):
    out = []
    for name in sorted(pkg.files):
        if re.fullmatch(r'ppt/slideLayouts/slideLayout\d+\.xml', name):
            text = pkg.text(name)
            title = re.search(r'<p:cSld\s+name="([^"]*)"', text)
            kind = re.search(r'<p:sldLayout\b[^>]*\btype="(\w+)"', text)
            ph = []
            for tag in re.findall(r'<p:ph\b[^>]*/?>', text):
                attrs = dict(re.findall(r'(\w+)="([^"]*)"', tag))
                ph.append((attrs.get('type', 'body'), attrs.get('idx', '')))
            out.append({'part': name, 'name': title[1] if title else '', 'type': kind[1] if kind else '', 'ph': ph})
    return out


class Build:
    def __init__(self, md_path, out, template, style, force_all):
        self.md = Path(md_path).resolve()
        self.deck = lm.read_deck(self.md)
        self.out = Path(out).resolve()
        self.notes_log = []
        self.template = False
        self.reused = self.patched = self.rebuilt = self.added = 0
        self.old_parts = {}
        self.source_slides = {}
        record = self.md.with_name(self.md.stem + '-변환기록.json')
        self.record = json.loads(record.read_text(encoding='utf-8')) if record.exists() else None
        self.base = None
        if template:
            self.base = Path(template).resolve()
            self.template = True
        elif self.record and self.record.get('snapshot'):
            snap = self.md.parent / self.record['snapshot']
            if snap.exists():
                self.base = snap
                self.template = True
            else:
                self.notes_log.append('변환기록의 원본 사본이 없어 Lectern 스타일로 새로 만듭니다')
        self.reuse = bool(self.record and self.base and not template and not force_all)
        self.style = Style(style or chosen_style(), self.deck['css'])
        self.svg = {}
        self.figures = {}
        self.tmp = tempfile.TemporaryDirectory()

    def figure(self, block, w, h):
        key = (block['lang'], block['text'], round(w), round(h))
        if key not in self.figures:
            path = Path(self.tmp.name) / f'fig{len(self.figures)}.png'
            text = block['text']
            if block['lang'] == 'vega-lite':
                text = inline_data(text, self.deck['dir'])
            self.figures[key] = path if figure_png.draw(block['lang'], text, w, h, path) else None
        return self.figures[key]

    def note(self, slide, text):
        n = self.deck['slides'].index(slide) + 1
        self.notes_log.append(f'{n}쪽: {text}')

    def resolve(self, src):
        path = (self.deck['dir'] / src).resolve()
        return path if path.exists() else None

    def setup(self):
        d = self.deck
        c = self.style.c
        if self.base:
            self.pkg = pp.Package.read(self.base)
            pres = self.pkg.text('ppt/presentation.xml')
            size = re.search(r'<p:sldSz\b[^>]*\bcx="(\d+)"[^>]*\bcy="(\d+)"', pres)
            self.cx, self.cy = int(size[1]), int(size[2])
            self.old_slides = self.slide_map()
        else:
            self.cx, self.cy = d['w'] * EMU, d['h'] * EMU
            colors = {'dk1': c['fg'], 'lt1': 'FFFFFF', 'dk2': c['heading'], 'lt2': c['bg'], 'accent1': c['link'], 'accent2': c['th-bg'], 'accent3': PALETTE[0], 'accent4': PALETTE[1],
                      'accent5': PALETTE[3], 'accent6': PALETTE[4], 'hlink': c['link'], 'folHlink': c['muted']}
            self.pkg = pp.fresh(self.cx, self.cy, colors, title=str(d['fm'].get('title') or self.md.stem), major=self.style.font, minor=self.style.font, bg=c['bg'])
            self.old_slides = {}
            self.place_logo()
        self.layouts = layouts_of(self.pkg)
        self.theme = {}
        rels = [self.pkg.target('ppt/presentation.xml', t) for _, k, t, _ in self.pkg.rels('ppt/presentation.xml') if k.endswith('/theme')]
        master_part = next((n for n in sorted(self.pkg.files) if re.fullmatch(r'ppt/slideMasters/slideMaster\d+\.xml', n)), None)
        rels += [self.pkg.target(master_part, t) for _, k, t, _ in self.pkg.rels(master_part) if k.endswith('/theme')] if master_part else []
        for part in rels[::-1]:
            if part in self.pkg.files:
                for name, value in re.findall(r'<a:(dk1|lt1|dk2|lt2|accent[1-6])>\s*<a:\w+Clr\b[^>]*?(?:val|lastClr)="([0-9A-Fa-f]{6})"', self.pkg.text(part)):
                    self.theme[name] = value.upper()
                break
        self.title_pt = 44
        master = next((n for n in self.pkg.files if re.fullmatch(r'ppt/slideMasters/slideMaster\d+\.xml', n)), None)
        found = re.search(r'<p:titleStyle>.*?\bsz="(\d+)"', self.pkg.text(master), flags=re.S) if master else None
        if found:
            self.title_pt = int(found[1]) / 100

    def strong_color(self):
        """흰 바탕에서 읽히는 양식의 색. 강조색이 노랑이면 다음 색으로 간다."""
        base = self.theme.get('lt1', 'FFFFFF')
        for name in ('accent1', 'accent2', 'accent3', 'accent4', 'accent5', 'accent6', 'dk2'):
            value = self.theme.get(name)
            if value and contrast(value, base) >= 3:
                return name
        return 'tx1'

    def rgb(self, color):
        """색 이름을 RRGGBB 로. 모르면 None."""
        if not color:
            return None
        if re.fullmatch(r'[0-9A-Fa-f]{6}', color):
            return color
        name = color.split('+')[0]
        return self.theme.get({'tx1': 'dk1', 'tx2': 'dk2', 'bg1': 'lt1', 'bg2': 'lt2'}.get(name, name))

    def place_logo(self):
        import base64
        logo = self.style.logo(self.deck['css'])
        if not logo or not logo['w'] or not logo['h']:
            return
        ext = {'svg+xml': 'svg', 'jpeg': 'jpg'}.get(logo['kind'], logo['kind'])
        if ext == 'svg':
            return
        media = self.pkg.add_media(base64.b64decode(logo['data']), ext)
        part = 'ppt/slideMasters/slideMaster1.xml'
        rid = self.pkg.add_rel(part, 'image', '../media/' + media.rsplit('/', 1)[-1])
        W, H = self.deck['w'], self.deck['h']
        x = logo['left'] if logo['left'] is not None else W - (logo['right'] or 0) - logo['w']
        y = logo['top'] if logo['top'] is not None else H - (logo['bottom'] or 0) - logo['h']
        pic = (f'<p:pic><p:nvPicPr><p:cNvPr id="20" name="로고"/><p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr userDrawn="1"/></p:nvPicPr>'
               f'<p:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>'
               f'<p:spPr><a:xfrm><a:off x="{round(x * EMU)}" y="{round(y * EMU)}"/><a:ext cx="{round(logo["w"] * EMU)}" cy="{round(logo["h"] * EMU)}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>')
        text = self.pkg.text(part)
        self.pkg.put(part, text.replace('</p:spTree>', pic + '</p:spTree>', 1))

    def slide_map(self):
        """원본의 쪽: 차례 → 파트."""
        rels = {i: t for i, _, t, _ in self.pkg.rels('ppt/presentation.xml')}
        pres = self.pkg.text('ppt/presentation.xml')
        out = {}
        block = re.search(r'<p:sldIdLst>(.*?)</p:sldIdLst>', pres, flags=re.S)
        for n, tag in enumerate(re.findall(r'<p:sldId\b[^>]*>', block[1] if block else ''), 1):
            rid = re.search(r'r:id="([^"]+)"', tag)
            sid = re.search(r'\bid="(\d+)"', tag)
            out[n] = {'part': self.pkg.target('ppt/presentation.xml', rels[rid[1]]), 'id': sid[1], 'rid': rid[1]}
        return out

    def pick_layout(self, slide, wanted):
        by_name = {l['name']: l for l in self.layouts}
        if wanted and wanted in by_name:
            return by_name[wanted]
        lead = 'lead' in slide['classes'] and not slide['cells']
        content = lambda l: sum(1 for t, _ in l['ph'] if t not in ('title', 'ctrTitle', 'dt', 'ftr', 'sldNum'))
        titled = [l for l in self.layouts if any(t in ('title', 'ctrTitle') for t, _ in l['ph'])]
        if lead and slide['title_level'] == 1:
            cover = [l for l in self.layouts if any(t == 'ctrTitle' for t, _ in l['ph']) or l['type'] == 'title']
            if cover:
                return cover[0]
        if lead:
            section = [l for l in self.layouts if l['type'] == 'secHead' or re.search(r'section|구역|장\s*구분', l['name'], flags=re.I)]
            if section:
                return section[0]
        if slide['title'] and titled:
            plain_ones = [l for l in titled if not any(t == 'ctrTitle' for t, _ in l['ph'])] or titled
            return min(plain_ones, key=content)
        return min(self.layouts, key=lambda l: len(l['ph']))

    def new_slide(self, slide, wanted):
        layout = self.pick_layout(slide, wanted)
        part = self.pkg.next_part('ppt/slides', 'slide')
        self.pkg.put(part, '')
        self.pkg.add_rel(part, 'slideLayout', '../slideLayouts/' + layout['part'].rsplit('/', 1)[-1])
        w = Writer(self, slide, part, layout)
        w.render()
        self.pkg.put(part, w.xml())
        self.pkg.add_override(part, pp.CT_SLIDE)
        if slide['notes']:
            self.add_notes(part, slide['notes'])
        return part

    def add_notes(self, slide_part, text):
        if not any(t.endswith('/notesMaster') for _, t, _, _ in self.pkg.rels('ppt/presentation.xml')):
            self.add_notes_master()
        master = next(self.pkg.target('ppt/presentation.xml', g) for _, t, g, _ in self.pkg.rels('ppt/presentation.xml') if t.endswith('/notesMaster'))
        part = self.pkg.next_part('ppt/notesSlides', 'notesSlide')
        self.pkg.put(part, pp.notes_slide(text))
        self.pkg.add_override(part, pp.CT_NOTES)
        self.pkg.add_rel(part, 'notesMaster', '../notesMasters/' + master.rsplit('/', 1)[-1])
        self.pkg.add_rel(part, 'slide', '../slides/' + slide_part.rsplit('/', 1)[-1])
        self.pkg.add_rel(slide_part, 'notesSlide', '../notesSlides/' + part.rsplit('/', 1)[-1])

    def add_notes_master(self):
        pkg = self.pkg
        theme = pkg.next_part('ppt/theme', 'theme')
        master_theme = next(pkg.target('ppt/presentation.xml', g) for _, t, g, _ in pkg.rels('ppt/presentation.xml') if t.endswith('/theme'))
        pkg.put(theme, pkg.files[master_theme])
        pkg.add_override(theme, 'application/vnd.openxmlformats-officedocument.theme+xml')
        part = 'ppt/notesMasters/notesMaster1.xml'
        pkg.put(part, pp.notes_master())
        pkg.add_override(part, 'application/vnd.openxmlformats-officedocument.presentationml.notesMaster+xml')
        pkg.add_rel(part, 'theme', '../theme/' + theme.rsplit('/', 1)[-1])
        rid = pkg.add_rel('ppt/presentation.xml', 'notesMaster', 'notesMasters/notesMaster1.xml')
        pres = pkg.text('ppt/presentation.xml')
        pkg.put('ppt/presentation.xml', pres.replace('</p:sldMasterIdLst>', f'</p:sldMasterIdLst><p:notesMasterIdLst><p:notesMasterId r:id="{rid}"/></p:notesMasterIdLst>', 1))

    def known_slides(self):
        """지문 → 원본 쪽 번호. 변환기록의 지문으로만 안다 (봉하지 않았으면 초안으로 맞춘다)."""
        table = {}
        slides = self.record.get('slides', []) if self.record else []
        work = self.base.parent if self.base else None
        for name in ('sealed.md', 'draft.md'):
            path = work / name if work else None
            if path and path.exists():
                _, _, body = lm.split_front(path.read_text(encoding='utf-8'))
                parts = lm.split_slides(body)
                self.old_parts = {r['n']: part for r, part in zip(slides, parts)}
                if not any(r.get('sha1') for r in slides):
                    for r, part in zip(slides, parts):
                        r['sha1'] = lm.fingerprint(part)
                break
        for r in slides:
            if r.get('sha1'):
                table.setdefault(r['sha1'], []).append(r)
        return table

    def run(self):
        self.setup()
        paths = []
        for s in self.deck['slides']:
            for src in [b['src'] for b in s['backgrounds']] + [b['src'] for c in s['cells'] for b in c['blocks'] if b['kind'] == 'image'] + [b['src'] for b in s['body'] if b['kind'] == 'image']:
                p = self.resolve(src)
                if p and p.suffix.lower() == '.svg':
                    paths.append(str(p))
        self.svg = {k: Path(v) for k, v in svg_to_png(sorted(set(paths)), self.tmp.name).items()}
        known = self.known_slides() if self.reuse else {}
        # 지문이 같으면 원본 쪽이다. 나머지는 쓰이지 않은 원본 쪽과 차례로 짝지어 고친 쪽으로 보고, 짝이 없으면 새 쪽이다
        matched = {}
        for i, part_text in enumerate(self.deck['parts'], 1):
            found = known.get(lm.fingerprint(part_text))
            if found:
                matched[i] = found.pop(0)
        taken = {r['n'] for r in matched.values()}
        spare = [r for r in (self.record.get('slides', []) if self.reuse else []) if r['n'] not in taken]
        order = []       # (파트, 원래 id)
        result = []
        for i, slide in enumerate(self.deck['slides'], 1):
            r = matched.get(i)
            old = self.old_slides.get(r['n']) if r else None
            if old:
                order.append((old['part'], old['id']))
                self.reused += 1
                result.append({'n': i, 'how': 'reused', 'from': r['n']})
                continue
            prior = spare.pop(0) if spare else None
            if prior and self.patch_slide(prior, self.deck['parts'][i - 1]):
                old = self.old_slides[prior['n']]
                order.append((old['part'], old['id']))
                self.patched += 1
                result.append({'n': i, 'how': 'patched', 'from': prior['n']})
                continue
            part = self.new_slide(slide, prior.get('layout') if prior else None)
            order.append((part, None))
            if prior:
                self.rebuilt += 1
                result.append({'n': i, 'how': 'rebuilt', 'from': prior['n']})
            else:
                self.added += 1
                result.append({'n': i, 'how': 'new'})
        self.finish(order)
        self.pkg.prune()
        self.pkg.save(self.out)
        return result

    def patch_slide(self, prior, new_part):
        """글만 바뀐 쪽이면 원본 쪽의 글을 그 자리에서 고친다. 도형·서식·애니메이션이 그대로 남는다."""
        old_part = self.old_parts.get(prior['n'])
        target = self.old_slides.get(prior['n'])
        if old_part is None or target is None:
            return False
        changes = text_patch.text_changes(old_part, new_part)
        if changes is None:
            return False
        part = target['part']
        notes = next((self.pkg.target(part, t) for _, k, t, _ in self.pkg.rels(part) if k.endswith('/notesSlide')), None)
        got = text_patch.apply_changes(self.pkg.text(part), self.pkg.text(notes) if notes else None, changes)
        if got is None:
            return False
        self.pkg.put(part, got[0])
        if notes and got[1] is not None:
            self.pkg.put(notes, got[1])
        return True

    def finish(self, order):
        pkg = self.pkg
        pres = pkg.text('ppt/presentation.xml')
        rels = [r for r in pkg.rels('ppt/presentation.xml') if not r[1].endswith('/slide')]
        used = {int(m[1]) for i, *_ in rels if (m := re.match(r'rId(\d+)$', i))}
        n = max(used, default=0)
        ids = {int(s['id']) for s in self.old_slides.values()}
        next_id = max(ids | {255}) + 1
        tags = []
        keep = {}
        for part, old in order:
            n += 1
            rid = f'rId{n}'
            sid = old
            if sid is None:
                sid = str(next_id)
                next_id += 1
            keep[sid] = rid
            rels.append((rid, f'{pp.REL}/slide', part.replace('ppt/', '', 1), False))
            tags.append(f'<p:sldId id="{sid}" r:id="{rid}"/>')
        pkg.write_rels('ppt/presentation.xml', rels)
        joined = f'<p:sldIdLst>{"".join(tags)}</p:sldIdLst>'
        if re.search(r'<p:sldIdLst\s*/>', pres):
            pres = re.sub(r'<p:sldIdLst\s*/>', joined, pres, count=1)
        else:
            pres = re.sub(r'<p:sldIdLst>.*?</p:sldIdLst>', joined, pres, count=1, flags=re.S)
        pres = self.fix_sections(pres, keep, order)
        pkg.put('ppt/presentation.xml', pres)

    @staticmethod
    def fix_sections(pres, keep, order):
        """구역에 없는 쪽이 있거나 사라진 쪽이 남으면 PowerPoint 가 복구를 묻는다."""
        if 'sectionLst' not in pres:
            return pres

        def drop(m):
            return m[0] if m[1] in keep else ''

        pres = re.sub(r'<p14:sldId\s+id="(\d+)"\s*/>', drop, pres)
        listed = set(re.findall(r'<p14:sldId\s+id="(\d+)"', pres))
        missing = [sid for sid in keep if sid not in listed]
        if missing:
            add = ''.join(f'<p14:sldId id="{sid}"/>' for sid in missing)
            at = pres.rfind('</p14:sldIdLst>')
            if at >= 0:
                pres = pres[:at] + add + pres[at:]
            else:
                pres = re.sub(r'<p14:sldIdLst\s*/>(?![\s\S]*<p14:sldIdLst\s*/>)', f'<p14:sldIdLst>{add}</p14:sldIdLst>', pres, count=1)
        return pres


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('md')
    ap.add_argument('--out')
    ap.add_argument('--template', help='이 pptx 의 마스터와 레이아웃을 쓴다')
    ap.add_argument('--style', help='Lectern 슬라이드 스타일 id. 없으면 슬라이드 창에서 고른 것')
    ap.add_argument('--force', action='store_true', help='이미 있는 pptx 를 덮어쓴다')
    ap.add_argument('--rebuild-all', action='store_true', help='고치지 않은 쪽도 다시 만든다')
    args = ap.parse_args(argv)
    md = Path(args.md).resolve()
    out = Path(args.out).resolve() if args.out else md.with_suffix('.pptx')
    record = md.with_name(md.stem + '-변환기록.json')
    origin = None
    if record.exists():
        origin = json.loads(record.read_text(encoding='utf-8')).get('source')
    if origin and Path(origin).exists() and Path(origin).resolve() == out:
        out = out.with_name(out.stem + '-수정.pptx')       # 원본을 덮어쓰지 않는다
    if out.exists() and not args.force:
        print(json.dumps({'error': f'{out.name} 이 이미 있습니다. 덮어쓰려면 --force, 다른 이름은 --out 을 주세요'}, ensure_ascii=False))
        return 2
    try:
        b = Build(md, out, args.template, args.style, args.rebuild_all)
    except ValueError as e:
        print(json.dumps({'error': str(e)}, ensure_ascii=False))
        return 2
    result = b.run()
    print(json.dumps({'pptx': str(out), 'slides': len(result), 'reused': b.reused, 'patched': b.patched, 'rebuilt': b.rebuilt, 'new': b.added,
                      'base': str(b.base) if b.base else None, 'style': None if b.template else b.style.name, 'notes': b.notes_log[:40]}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
