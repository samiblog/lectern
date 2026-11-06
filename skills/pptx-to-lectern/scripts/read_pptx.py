#!/usr/bin/env python3
"""pptx 를 읽어 Lectern 슬라이드로 옮길 재료를 뽑는다. 표준 라이브러리만 쓴다.

    python read_pptx.py 원본.pptx 출력폴더 [--pages 3,5-9]

출력:
    deck.json     쪽·도형·표·차트·SmartArt·노트·테마를 구조로
    outline.md    사람과 AI 가 읽는 요약 (좌표는 Lectern 쪽 크기로 맞춘 px)
    media/        쪽에 쓰인 그림 (원본 그대로)
    charts/       차트 값 CSV

원본은 읽기만 하고 인터넷에 나가지 않는다. 받은 파일을 믿지 않는다: DOCTYPE 이 든 XML 은 읽지 않고,
ZIP 안 이름을 출력 경로로 쓰지 않으며, 외부로 이어진 그림은 받지 않고 표시만 한다.
"""
import argparse
import colorsys
import csv
import json
import posixpath
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

MAX_XML = 64 * 1024 * 1024
MAX_MEDIA = 200 * 1024 * 1024
EMU_PT = 12700
PRESET = {
    'black': '000000', 'white': 'FFFFFF', 'red': 'FF0000', 'green': '008000', 'blue': '0000FF',
    'yellow': 'FFFF00', 'gray': '808080', 'grey': '808080', 'orange': 'FFA500', 'navy': '000080',
    'silver': 'C0C0C0', 'maroon': '800000', 'purple': '800080', 'teal': '008080',
}
SCHEME = ('dk1', 'lt1', 'dk2', 'lt2', 'accent1', 'accent2', 'accent3', 'accent4', 'accent5', 'accent6', 'hlink', 'folHlink')
WEB_IMAGE = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.bmp'}


def local(el):
    return el.tag.rsplit('}', 1)[-1] if isinstance(el.tag, str) else ''


def kid(el, *names):
    """이름공간을 보지 않고 자식을 찾는다 (p: 와 dsp: 를 같은 코드로 읽으려고)."""
    if el is None:
        return None
    for name in names:
        for c in el:
            if local(c) == name:
                return c
    return None


def percent(value, default=1):
    """62500 이나 62.5% 를 비율로. 구글 슬라이드가 내보낸 파일은 뒤의 꼴을 쓴다."""
    try:
        text = str(value).strip()
        return float(text[:-1]) / 100 if text.endswith('%') else int(text) / 100000
    except ValueError:
        return default


def iter_of(el):
    return [] if el is None else list(el)


def kids(el, name):
    return [] if el is None else [c for c in el if local(c) == name]


def deep(el, name):
    if el is None:
        return None
    for c in el.iter():
        if local(c) == name:
            return c
    return None


def attr(el, name):
    """이름공간이 붙은 속성(r:id 등)을 끝 이름으로 찾는다. p:sldId 처럼 id 와 r:id 가 함께 있으면 r:id 다."""
    if el is None:
        return None
    for k, v in el.attrib.items():
        if k.startswith('{') and k.rsplit('}', 1)[-1] == name:
            return v
    return el.get(name)


class Package:
    def __init__(self, path):
        self.zip = zipfile.ZipFile(path)
        self.names = set(self.zip.namelist())
        self._rels = {}

    def xml(self, name):
        if name not in self.names:
            return None
        if self.zip.getinfo(name).file_size > MAX_XML:
            raise ValueError(f'{name} 이 너무 큽니다')
        data = self.zip.read(name)
        if b'<!DOCTYPE' in data[:4096] or b'<!ENTITY' in data[:4096]:
            raise ValueError(f'{name} 에 DOCTYPE 이 있어 읽지 않습니다')
        return ET.fromstring(data)

    def rels(self, name):
        if name in self._rels:
            return self._rels[name]
        base = posixpath.dirname(name)
        path = f'{base}/_rels/{posixpath.basename(name)}.rels'
        out = {}
        root = self.xml(path)
        if root is not None:
            for r in root:
                target = r.get('Target', '')
                external = r.get('TargetMode') == 'External'
                if not external:
                    target = target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join(base, target))
                out[r.get('Id')] = {'type': r.get('Type', '').rsplit('/', 1)[-1], 'target': target, 'external': external}
        self._rels[name] = out
        return out

    def rel_of(self, name, kind):
        return next((r['target'] for r in self.rels(name).values() if r['type'] == kind and not r['external']), None)


def hex_rgb(value):
    value = (value or '000000').strip().lstrip('#')[:6].ljust(6, '0')
    return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))


def rgb_hex(rgb):
    return '#' + ''.join(f'{round(max(0, min(1, c)) * 255):02X}' for c in rgb)


def modify(base, el):
    r, g, b = hex_rgb(base)
    alpha = None
    for m in el:
        name = local(m)
        v = percent(m.get('val', '0'), None)
        if v is None:
            continue
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        if name == 'lumMod':
            r, g, b = colorsys.hls_to_rgb(h, l * v, s)
        elif name == 'lumOff':
            r, g, b = colorsys.hls_to_rgb(h, min(1, l + v), s)
        elif name == 'satMod':
            r, g, b = colorsys.hls_to_rgb(h, l, min(1, s * v))
        elif name == 'tint':
            r, g, b = (c + (1 - c) * (1 - v) for c in (r, g, b))
        elif name == 'shade':
            r, g, b = (c * v for c in (r, g, b))
        elif name == 'alpha':
            alpha = v
    out = rgb_hex((r, g, b))
    return out, alpha


class Colors:
    def __init__(self, theme, clr_map):
        self.theme = theme
        self.map = clr_map

    def scheme(self, name):
        name = self.map.get(name, name)
        return self.theme.get(name)

    def read(self, parent, ph=None):
        """parent 의 자식 색 요소를 #RRGGBB 로. 없으면 None."""
        if parent is None:
            return None
        for el in parent:
            n = local(el)
            base = None
            if n == 'srgbClr':
                base = el.get('val')
            elif n == 'schemeClr':
                v = el.get('val')
                base = ph if v == 'phClr' else self.scheme(v)
            elif n == 'sysClr':
                base = el.get('lastClr') or ('000000' if el.get('val') == 'windowText' else 'FFFFFF')
            elif n == 'prstClr':
                base = PRESET.get(el.get('val', '').lower())
            if base:
                return modify(base.lstrip('#'), el)[0]
        return None


def theme_of(pkg, part):
    root = pkg.xml(part)
    out = {'name': '', 'colors': {}, 'fonts': {}}
    if root is None:
        return out
    out['name'] = root.get('name', '')
    scheme = deep(root, 'clrScheme')
    for el in scheme if scheme is not None else []:
        n = local(el)
        if n in SCHEME:
            c = el[0] if len(el) else None
            if c is not None:
                out['colors'][n] = c.get('val') if local(c) == 'srgbClr' else c.get('lastClr', '000000')
    fonts = deep(root, 'fontScheme')
    for key, name in (('major', 'majorFont'), ('minor', 'minorFont')):
        f = kid(fonts, name)
        if f is not None:
            latin, ea = kid(f, 'latin'), kid(f, 'ea')
            kor = next((x.get('typeface') for x in kids(f, 'font') if x.get('script') == 'Hang'), '')
            out['fonts'][key] = {'latin': latin.get('typeface', '') if latin is not None else '',
                                 'ea': (ea.get('typeface', '') if ea is not None else '') or kor}
    return out


class Deck:
    def __init__(self, path, out, pages=None):
        self.pkg = Package(path)
        self.out = Path(out)
        self.pages = pages
        self.media = {}
        self.charts = {}
        self.flags = Counter()
        self.masters = {}
        self.layouts = {}
        root = self.pkg.xml('ppt/presentation.xml')
        if root is None:
            raise ValueError('ppt/presentation.xml 이 없습니다. pptx 가 맞는지 보세요')
        self.pres = root
        size = kid(root, 'sldSz')
        self.cx = int(size.get('cx', 12192000)) if size is not None else 12192000
        self.cy = int(size.get('cy', 6858000)) if size is not None else 6858000
        ratio = self.cx / self.cy
        self.ratio = ratio
        self.target = (960, 720) if abs(ratio - 4 / 3) < abs(ratio - 16 / 9) else (1280, 720)
        self.fit = 'exact' if min(abs(ratio - 4 / 3), abs(ratio - 16 / 9)) < .02 else 'other'
        # 비율이 다르면 쪽 전체가 들어가게 줄인다
        self.k = min(self.target[0] / self.cx, self.target[1] / self.cy)
        self.default_text = kid(root, 'defaultTextStyle')

    def px(self, v):
        return round(v * self.k)

    # ---- 마스터·레이아웃
    def master(self, part):
        if part in self.masters:
            return self.masters[part]
        root = self.pkg.xml(part)
        theme = theme_of(self.pkg, self.pkg.rel_of(part, 'theme') or '')
        cmap = kid(root, 'clrMap')
        colors = Colors(theme['colors'], dict(cmap.attrib) if cmap is not None else {})
        info = {'part': part, 'root': root, 'theme': theme, 'colors': colors, 'tx': kid(root, 'txStyles')}
        tree = deep(kid(root, 'cSld'), 'spTree')
        info['ph'] = self.placeholders(tree)
        self.masters[part] = info
        ctx = Context(self, part, colors, master=info)
        info['bg'] = self.background(root, ctx)
        info['decor'] = self.decor(tree, ctx)
        return info

    def layout(self, part):
        if part in self.layouts:
            return self.layouts[part]
        root = self.pkg.xml(part)
        master = self.master(self.pkg.rel_of(part, 'slideMaster'))
        csld = kid(root, 'cSld')
        tree = deep(csld, 'spTree')
        info = {'part': part, 'root': root, 'master': master, 'name': csld.get('name', '') if csld is not None else '',
                'type': root.get('type', ''), 'ph': self.placeholders(tree), 'show_master': root.get('showMasterSp', '1') != '0'}
        self.layouts[part] = info
        over = deep(kid(root, 'clrMapOvr'), 'overrideClrMapping')
        info['colors'] = Colors(master['colors'].theme, dict(over.attrib)) if over is not None else master['colors']
        ctx = Context(self, part, info['colors'], master=master, layout=info)
        info['bg'] = self.background(root, ctx)
        info['decor'] = self.decor(tree, ctx)
        return info

    def placeholders(self, tree):
        out = []
        for sp in tree.iter() if tree is not None else []:
            if local(sp) != 'sp':
                continue
            ph = deep(kid(sp, 'nvSpPr'), 'ph')
            if ph is not None:
                out.append((ph.get('type', ''), ph.get('idx', ''), sp))
        return out

    def decor(self, tree, ctx):
        """마스터·레이아웃에 놓인, 자리 표시자가 아닌 것 — 로고·띠·선."""
        shapes = []
        walk(tree, ctx, (1, 1, 0, 0), shapes, None)
        return [s for s in shapes if not s.get('ph')]

    def background(self, root, ctx):
        bg = kid(kid(root, 'cSld'), 'bg')
        if bg is None:
            return None
        pr = kid(bg, 'bgPr')
        if pr is not None:
            return read_fill(pr, ctx)
        ref = kid(bg, 'bgRef')
        if ref is not None:
            c = ctx.colors.read(ref)
            return {'c': c} if c else None
        return None

    # ---- 그림
    def take_media(self, part):
        """그림 파일을 media/ 로 복사하고 상대 경로를 준다. ZIP 안 이름을 그대로 경로로 쓰지 않는다."""
        if part in self.media:
            return self.media[part]
        if part not in self.pkg.names:
            return None
        info = self.pkg.zip.getinfo(part)
        if info.file_size > MAX_MEDIA:
            self.flags['media-too-big'] += 1
            return None
        base = re.sub(r'[^\w.-]+', '_', posixpath.basename(part))[:80] or 'media.bin'
        rel = f'media/{base}'
        target = self.out / 'media' / base
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self.pkg.zip.read(part))
        self.media[part] = rel
        return rel

    # ---- 차트
    def chart(self, part):
        if part in self.charts:
            return self.charts[part]
        root = self.pkg.xml(part)
        if root is None:
            return None
        info = read_chart(root)
        name = f'charts/{posixpath.basename(part).rsplit(".", 1)[0]}.csv'
        rows = chart_rows(info)
        if rows:
            target = self.out / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, 'w', encoding='utf-8-sig', newline='') as f:
                csv.writer(f).writerows(rows)
            info['csv'] = name
        self.charts[part] = info
        return info

    # ---- 쪽
    def slides(self):
        rels = self.pkg.rels('ppt/presentation.xml')
        ids = kid(self.pres, 'sldIdLst')
        order = [rels[attr(s, 'id')]['target'] for s in ids if attr(s, 'id') in rels] if ids is not None else []
        self.order = {part: i + 1 for i, part in enumerate(order)}
        for i, part in enumerate(order, 1):
            if self.pages and i not in self.pages:
                continue
            yield i, part

    def slide(self, n, part):
        root = self.pkg.xml(part)
        layout = self.layout(self.pkg.rel_of(part, 'slideLayout'))
        master = layout['master']
        over = deep(kid(root, 'clrMapOvr'), 'overrideClrMapping')
        colors = Colors(master['colors'].theme, dict(over.attrib)) if over is not None else layout['colors']
        ctx = Context(self, part, colors, master=master, layout=layout, slide_map=self.order)
        tree = deep(kid(root, 'cSld'), 'spTree')
        shapes = []
        walk(tree, ctx, (1, 1, 0, 0), shapes, None)
        bg = self.background(root, ctx) or layout['bg'] or master['bg']
        has_timing = deep(kid(root, 'timing'), 'par') is not None
        out = {
            'n': n, 'part': posixpath.basename(part), 'hidden': root.get('show') == '0', 'layout': layout['name'],
            'layout_type': layout['type'], 'bg': bg, 'shapes': shapes, 'notes': notes_of(self.pkg, part),
            'animated': has_timing, 'transition': kid(root, 'transition') is not None,
            'comments': sum(1 for r in self.pkg.rels(part).values() if r['type'] in ('comments', 'comment')),
            'show_master': root.get('showMasterSp', '1') != '0' and layout['show_master'],
        }
        out['title'] = title_of(shapes)
        out['form'] = form_of(out)
        return out


class Context:
    def __init__(self, deck, part, colors, master=None, layout=None, slide_map=None):
        self.deck = deck
        self.part = part
        self.colors = colors
        self.master = master
        self.layout = layout
        self.slide_map = slide_map or {}
        self.rels = deck.pkg.rels(part)
        self.group_fill = None


def read_fill(el, ctx, style=None):
    """spPr 나 bgPr 의 채우기. 없으면 style 의 fillRef."""
    for c in el if el is not None else []:
        n = local(c)
        if n == 'noFill':
            return None
        if n == 'solidFill':
            col = ctx.colors.read(c)
            alpha = deep(c, 'alpha')
            out = {'c': col}
            if alpha is not None:
                out['alpha'] = round(percent(alpha.get('val', '100000')), 2)
            return out if col else None
        if n == 'gradFill':
            stops = [ctx.colors.read(g) for g in iter_of(deep(c, 'gsLst'))]
            lin = kid(c, 'lin')
            return {'grad': [s for s in stops if s], 'ang': round(int(lin.get('ang', '0')) / 60000) if lin is not None else None}
        if n == 'blipFill':
            return {'img': image_of(c, ctx)}
        if n == 'pattFill':
            col = ctx.colors.read(kid(c, 'fgClr'))
            return {'c': col, 'pattern': c.get('prst')} if col else None
        if n == 'grpFill':
            return ctx.group_fill
    if style is not None:
        ref = kid(style, 'fillRef')
        if ref is not None and ref.get('idx', '0') != '0':
            col = ctx.colors.read(ref)
            return {'c': col, 'style': True} if col else None
    return None


def read_line(sppr, ctx, style=None):
    ln = kid(sppr, 'ln')
    if ln is not None:
        if kid(ln, 'noFill') is not None:
            return None
        fill = kid(ln, 'solidFill')
        if fill is not None:
            out = {'c': ctx.colors.read(fill)}
            if ln.get('w'):
                out['w'] = round(int(ln.get('w')) / EMU_PT, 1)
            dash = kid(ln, 'prstDash')
            if dash is not None and dash.get('val') != 'solid':
                out['dash'] = dash.get('val')
            head, tail = kid(ln, 'headEnd'), kid(ln, 'tailEnd')
            if head is not None and head.get('type', 'none') != 'none':
                out['head'] = head.get('type')
            if tail is not None and tail.get('type', 'none') != 'none':
                out['tail'] = tail.get('type')
            return out
    if style is not None:
        ref = kid(style, 'lnRef')
        if ref is not None and ref.get('idx', '0') != '0':
            col = ctx.colors.read(ref)
            return {'c': col, 'style': True} if col else None
    return None


def image_of(fill, ctx):
    blip = deep(fill, 'blip')
    if blip is None:
        return None
    rid = attr(blip, 'embed')
    link = attr(blip, 'link')
    out = {}
    if rid and rid in ctx.rels:
        rel = ctx.rels[rid]
        if not rel['external']:
            out['src'] = ctx.deck.take_media(rel['target'])
            ext = posixpath.splitext(rel['target'])[1].lower()
            out['ext'] = ext
            if ext not in WEB_IMAGE:
                out['needs_convert'] = True
                ctx.deck.flags[f'image{ext}'] += 1
    if link and link in ctx.rels:
        out['linked'] = ctx.rels[link]['target']
        ctx.deck.flags['linked-image'] += 1
    for ext in blip.iter():
        if local(ext) == 'svgBlip':
            sid = attr(ext, 'embed')
            if sid in ctx.rels:
                out['svg'] = ctx.deck.take_media(ctx.rels[sid]['target'])
    src = kid(fill, 'srcRect')
    if src is not None:
        crop = {k: round(percent(src.get(k, '0'), 0) * 100, 1) for k in 'ltrb' if src.get(k, '0') != '0'}
        if crop:
            out['crop'] = crop
    return out or None


def box(sppr_or_xfrm, tf, deck):
    xfrm = sppr_or_xfrm if sppr_or_xfrm is not None and local(sppr_or_xfrm) == 'xfrm' else kid(sppr_or_xfrm, 'xfrm')
    if xfrm is None:
        return None
    off, ext = kid(xfrm, 'off'), kid(xfrm, 'ext')
    if off is None or ext is None:
        return None
    sx, sy, dx, dy = tf
    x, y = int(off.get('x', 0)) * sx + dx, int(off.get('y', 0)) * sy + dy
    w, h = int(ext.get('cx', 0)) * sx, int(ext.get('cy', 0)) * sy
    out = {'x': deck.px(x), 'y': deck.px(y), 'w': deck.px(w), 'h': deck.px(h)}
    rot = int(xfrm.get('rot', 0) or 0)
    if rot:
        out['rot'] = round(rot / 60000)
    if xfrm.get('flipH') == '1':
        out['flipH'] = True
    if xfrm.get('flipV') == '1':
        out['flipV'] = True
    return out


def compose(tf, xfrm):
    off, ext, cho, che = kid(xfrm, 'off'), kid(xfrm, 'ext'), kid(xfrm, 'chOff'), kid(xfrm, 'chExt')
    if None in (off, ext, cho, che):
        return tf
    cw, ch = int(che.get('cx', 0)), int(che.get('cy', 0))
    gx = int(ext.get('cx', 0)) / cw if cw else 1
    gy = int(ext.get('cy', 0)) / ch if ch else 1
    ox = int(off.get('x', 0)) - int(cho.get('x', 0)) * gx
    oy = int(off.get('y', 0)) - int(cho.get('y', 0)) * gy
    sx, sy, dx, dy = tf
    return (sx * gx, sy * gy, dx + ox * sx, dy + oy * sy)


def nv(el):
    return deep(el, 'cNvPr')


def base_shape(el, kind, ctx):
    c = nv(el)
    out = {'kind': kind, 'id': c.get('id') if c is not None else None, 'name': c.get('name', '') if c is not None else ''}
    if c is not None:
        if c.get('descr'):
            out['alt'] = c.get('descr').strip()
        click = kid(c, 'hlinkClick')
        if click is not None:
            link = link_of(click, ctx)
            if link:
                out['link'] = link
        if c.get('hidden') == '1':
            out['hidden'] = True
    return out


def link_of(click, ctx):
    rid = attr(click, 'id')
    action = click.get('action', '')
    if rid and rid in ctx.rels:
        rel = ctx.rels[rid]
        if rel['external']:
            return rel['target']
        if rel['type'] == 'slide':
            n = ctx.slide_map.get(rel['target'])
            return f'#slide-{n}' if n else None
    if 'ppaction://' in action:
        return None
    return None


def style_chain(sp, ph, ctx):
    """글자 성질을 찾는 차례: 도형 → 레이아웃 자리 → 마스터 자리 → 마스터 글자 틀 → 문서 기본."""
    chain = [kid(kid(sp, 'txBody'), 'lstStyle')]
    kind = 'other'
    lay = ctx.layout['ph'] if ctx.layout else []
    mas = ctx.master['ph'] if ctx.master else []
    if ph is not None:
        ptype, idx = ph.get('type', ''), ph.get('idx', '')
        m = match_ph(lay, ptype, idx)
        if m is not None:
            chain.append(kid(kid(m, 'txBody'), 'lstStyle'))
        m2 = match_ph(mas, master_type(ptype), '')
        if m2 is not None:
            chain.append(kid(kid(m2, 'txBody'), 'lstStyle'))
        kind = 'title' if ptype in ('title', 'ctrTitle') else 'body' if ptype in ('body', 'subTitle', 'obj', '') else 'other'
    tx = ctx.master['tx'] if ctx.master else None
    chain.append(kid(tx, {'title': 'titleStyle', 'body': 'bodyStyle'}.get(kind, 'otherStyle')))
    chain.append(ctx.deck.default_text)
    return [c for c in chain if c is not None]


def master_type(ptype):
    return {'ctrTitle': 'title', 'subTitle': 'body', 'obj': 'body', '': 'body', 'pic': 'body', 'tbl': 'body', 'chart': 'body'}.get(ptype, ptype)


def match_ph(items, ptype, idx):
    if idx:
        for t, i, sp in items:
            if i == idx:
                return sp
    for t, i, sp in items:
        if t == ptype or master_type(t) == master_type(ptype):
            return sp
    return None


def level_of(style, lvl):
    return kid(style, f'lvl{lvl + 1}pPr')


def inherited(chain, lvl, pick):
    for style in chain:
        el = level_of(style, lvl)
        if el is None:
            continue
        v = pick(el)
        if v is not None:
            return v
    return None


def bullet_in(el):
    for c in el if el is not None else []:
        n = local(c)
        if n == 'buNone':
            return ''
        if n == 'buChar':
            return c.get('char', '•')
        if n == 'buAutoNum':
            kind = c.get('type', 'arabicPeriod')
            return '1.' if kind.startswith('arabic') else f'#{kind}'
        if n == 'buBlip':
            return '•'
    return None


def read_paras(body, chain, ctx, title=False):
    bp = kid(body, 'bodyPr')
    scale = 1
    fit = kid(bp, 'normAutofit')
    if fit is not None and fit.get('fontScale'):
        scale = percent(fit.get('fontScale'))
    out = []
    for p in kids(body, 'p'):
        ppr = kid(p, 'pPr')
        lvl = int(ppr.get('lvl', 0)) if ppr is not None else 0
        para = {'lvl': lvl} if lvl else {}
        bullet = bullet_in(ppr)
        if bullet is None:
            bullet = inherited(chain, lvl, bullet_in)
        if bullet and not title:
            para['bullet'] = bullet
        algn = (ppr.get('algn') if ppr is not None else None) or inherited(chain, lvl, lambda e: e.get('algn'))
        if algn and algn != 'l':
            para['align'] = algn
        runs = []
        base_sz = inherited(chain, lvl, lambda e: (kid(e, 'defRPr').get('sz') if kid(e, 'defRPr') is not None else None))
        base_b = inherited(chain, lvl, lambda e: (kid(e, 'defRPr').get('b') if kid(e, 'defRPr') is not None else None))
        base_c = inherited(chain, lvl, lambda e: (ctx.colors.read(kid(kid(e, 'defRPr'), 'solidFill')) if kid(e, 'defRPr') is not None else None))
        for c in p:
            n = local(c)
            if n == 'AlternateContent':
                pick = kid(c, 'Fallback', 'Choice')
                for r in iter_of(pick):
                    if local(r) == 'r':
                        text = deep(r, 't')
                        if text is not None and text.text:
                            runs.append({'t': text.text})
                ctx.deck.flags['math-or-alt-run'] += 1
                continue
            if n == 'br':
                runs.append({'t': '\n'})
                continue
            if n not in ('r', 'fld'):
                continue
            text = kid(c, 't')
            value = (text.text if text is not None else '') or ''
            if not value:
                continue
            if n == 'fld':
                ftype = c.get('type', '')
                if ftype.startswith('slidenum'):
                    runs.append({'t': value, 'field': 'page'})
                    continue
                if ftype.startswith('datetime'):
                    runs.append({'t': value, 'field': 'date'})
                    continue
            rpr = kid(c, 'rPr')
            run = {'t': value}
            sz = (rpr.get('sz') if rpr is not None else None) or base_sz
            if sz:
                run['sz'] = round(int(sz) / 100 * scale, 1)
            if rpr is not None:
                b = rpr.get('b')
                if b == '1':
                    run['b'] = True
                elif b is None and base_b == '1':
                    run['b'] = True
                if rpr.get('i') == '1':
                    run['i'] = True
                if rpr.get('u', 'none') not in ('none', ''):
                    run['u'] = True
                if rpr.get('strike', 'noStrike') not in ('noStrike', ''):
                    run['s'] = True
                if rpr.get('baseline', '0') not in ('0', ''):
                    run['sup' if int(rpr.get('baseline')) > 0 else 'sub'] = True
                col = ctx.colors.read(kid(rpr, 'solidFill'))
                if col:
                    run['c'] = col
                lat = kid(rpr, 'latin')
                if lat is not None and lat.get('typeface') and not lat.get('typeface').startswith('+'):
                    run['font'] = lat.get('typeface')
                    ctx.deck.flags['run-font'] += 1
                click = kid(rpr, 'hlinkClick')
                if click is not None:
                    link = link_of(click, ctx)
                    if link:
                        run['link'] = link
            elif base_b == '1':
                run['b'] = True
            if 'c' not in run and base_c:
                run['base_c'] = base_c
            runs.append(run)
        text = ''.join(r['t'] for r in runs).strip()
        if not text:
            continue
        para['runs'] = runs
        para['text'] = text
        out.append(para)
    return out


def ph_box(ph, ctx):
    """자리 표시자가 자기 좌표를 안 쓰면 레이아웃, 그다음 마스터의 자리를 따른다."""
    if ph is None:
        return None
    ptype, idx = ph.get('type', ''), ph.get('idx', '')
    for items, key, want in ((ctx.layout['ph'] if ctx.layout else [], idx, ptype),
                             (ctx.master['ph'] if ctx.master else [], '', master_type(ptype))):
        m = match_ph(items, want, key)
        if m is not None:
            pos = box(kid(m, 'spPr'), (1, 1, 0, 0), ctx.deck)
            if pos is not None:
                return pos
    return None


def read_sp(sp, ctx, tf, group):
    sppr = kid(sp, 'spPr')
    ph = deep(kid(sp, 'nvSpPr'), 'ph')
    pos = box(sppr, tf, ctx.deck) or ph_box(ph, ctx)
    style = kid(sp, 'style')
    out = base_shape(sp, 'shape', ctx)
    if pos:
        out.update(pos)
    if ph is not None:
        out['ph'] = ph.get('type', '') or 'body'
        if ph.get('idx'):
            out['ph_idx'] = ph.get('idx')
    geom = kid(sppr, 'prstGeom')
    if geom is not None:
        out['geom'] = geom.get('prst')
    elif kid(sppr, 'custGeom') is not None:
        out['geom'] = 'custom'
    fill = read_fill(sppr, ctx, style)
    if fill:
        out['fill'] = fill
    line = read_line(sppr, ctx, style)
    if line:
        out['line'] = line
    body = kid(sp, 'txBody')
    if body is not None:
        chain = style_chain(sp, ph, ctx)
        paras = read_paras(body, chain, ctx, title=out.get('ph') in ('title', 'ctrTitle'))
        if paras:
            out['paras'] = paras
            out['kind'] = 'text'
            bp = kid(body, 'bodyPr')
            if bp is not None:
                if bp.get('anchor') and bp.get('anchor') != 't':
                    out['anchor'] = bp.get('anchor')
                if bp.get('vert') and bp.get('vert') != 'horz':
                    out['vert'] = bp.get('vert')
                if int(bp.get('numCol', '1')) > 1:
                    out['cols'] = int(bp.get('numCol'))
            ref = kid(style, 'fontRef')
            if ref is not None:
                col = ctx.colors.read(ref)
                if col:
                    out['text_c'] = col
                    for p in paras:
                        for r in p['runs']:
                            if not r.get('c'):
                                r['base_c'] = col
    if group:
        out['group'] = group
    return out


def read_pic(el, ctx, tf, group):
    out = base_shape(el, 'picture', ctx)
    nvpr = kid(kid(el, 'nvPicPr'), 'nvPr')
    ph = kid(nvpr, 'ph')
    pos = box(kid(el, 'spPr'), tf, ctx.deck) or ph_box(ph, ctx)
    if pos:
        out.update(pos)
    img = image_of(kid(el, 'blipFill'), ctx)
    if img:
        out.update(img)
    if nvpr is not None:
        if ph is not None:
            out['ph'] = ph.get('type', 'pic')
        for c in nvpr.iter():
            if local(c) in ('videoFile', 'audioFile', 'media'):
                out['kind'] = 'media'
                out['media'] = 'video' if local(c) == 'videoFile' else 'audio' if local(c) == 'audioFile' else 'media'
                rid = attr(c, 'link') or attr(c, 'embed')
                if rid in ctx.rels and ctx.rels[rid]['external']:
                    out['url'] = ctx.rels[rid]['target']
                ctx.deck.flags['media'] += 1
                break
    if group:
        out['group'] = group
    return out


def read_connector(el, ctx, tf, group):
    out = base_shape(el, 'line', ctx)
    sppr = kid(el, 'spPr')
    pos = box(sppr, tf, ctx.deck)
    if pos:
        out.update(pos)
    geom = kid(sppr, 'prstGeom')
    if geom is not None:
        out['geom'] = geom.get('prst')
    line = read_line(sppr, ctx, kid(el, 'style'))
    if line:
        out['line'] = line
    nvc = deep(el, 'cNvCxnSpPr')
    if nvc is not None:
        st, en = kid(nvc, 'stCxn'), kid(nvc, 'endCxn')
        if st is not None:
            out['from'] = st.get('id')
        if en is not None:
            out['to'] = en.get('id')
    if group:
        out['group'] = group
    return out


def read_frame(el, ctx, tf, group):
    xfrm = kid(el, 'xfrm')
    pos = box(xfrm, tf, ctx.deck) if xfrm is not None else None
    pos = pos or ph_box(deep(kid(el, 'nvGraphicFramePr'), 'ph'), ctx)
    data = deep(el, 'graphicData')
    uri = data.get('uri', '') if data is not None else ''
    out = base_shape(el, 'frame', ctx)
    if pos:
        out.update(pos)
    if group:
        out['group'] = group
    if uri.endswith('/table'):
        out['kind'] = 'table'
        out.update(read_table(deep(data, 'tbl'), ctx))
    elif uri.endswith('/chart'):
        out['kind'] = 'chart'
        rid = attr(deep(data, 'chart'), 'id')
        rel = ctx.rels.get(rid)
        if rel:
            info = ctx.deck.chart(rel['target'])
            if info:
                out['chart'] = info
    elif uri.endswith('/diagram'):
        out['kind'] = 'smartart'
        out.update(read_diagram(deep(data, 'relIds'), ctx, xfrm, tf))
    elif uri.endswith('/ole'):
        out['kind'] = 'ole'
        ole = deep(data, 'oleObj')
        if ole is not None:
            out['prog'] = ole.get('progId', '')
        pic = deep(data, 'pic')
        if pic is not None:
            img = image_of(kid(pic, 'blipFill'), ctx)
            if img:
                out.update(img)
        ctx.deck.flags['ole'] += 1
    else:
        out['kind'] = 'unknown'
        out['uri'] = uri
        ctx.deck.flags['frame:' + uri.rsplit('/', 1)[-1]] += 1
    return out


def read_table(tbl, ctx):
    pr = kid(tbl, 'tblPr')
    grid = [int(g.get('w', 0)) for g in kids(kid(tbl, 'tblGrid'), 'gridCol')]
    rows = []
    for tr in kids(tbl, 'tr'):
        row = []
        for tc in kids(tr, 'tc'):
            cell = {}
            if tc.get('gridSpan', '1') != '1':
                cell['span'] = int(tc.get('gridSpan'))
            if tc.get('rowSpan', '1') != '1':
                cell['rows'] = int(tc.get('rowSpan'))
            if tc.get('hMerge') == '1' or tc.get('vMerge') == '1':
                cell['merged'] = True
            body = kid(tc, 'txBody')
            paras = read_paras(body, [], ctx) if body is not None else []
            cell['text'] = '\n'.join(p['text'] for p in paras)
            if any(r.get('b') for p in paras for r in p['runs']):
                cell['b'] = True
            fill = read_fill(kid(tc, 'tcPr'), ctx)
            if fill and fill.get('c'):
                cell['fill'] = fill['c']
            row.append(cell)
        rows.append(row)
    return {'rows': rows, 'cols': [round(w * ctx.deck.k) for w in grid],
            'head': bool(pr is not None and pr.get('firstRow') == '1')}


def read_chart(root):
    plot = deep(root, 'plotArea')
    info = {'plots': []}
    title = kid(deep(root, 'chart'), 'title')
    if title is not None:
        info['title'] = ''.join(t.text or '' for t in title.iter() if local(t) == 't')
    for el in plot if plot is not None else []:
        n = local(el)
        if not n.endswith('Chart'):
            continue
        p = {'type': n.replace('3D', '').replace('Chart', '')}
        if '3D' in n:
            p['3d'] = True
        for key in ('barDir', 'grouping'):
            e = kid(el, key)
            if e is not None:
                p[key] = e.get('val')
        series = []
        for ser in kids(el, 'ser'):
            s = {'name': ''.join(v.text or '' for v in kid(ser, 'tx').iter() if local(v) == 'v') if kid(ser, 'tx') is not None else ''}
            for key, name in (('cat', 'cats'), ('val', 'vals'), ('xVal', 'x'), ('yVal', 'y'), ('bubbleSize', 'size')):
                e = kid(ser, key)
                if e is None:
                    continue
                pts = {}
                for pt in e.iter():
                    if local(pt) == 'pt':
                        v = kid(pt, 'v')
                        pts[int(pt.get('idx', 0))] = v.text if v is not None else ''
                count = deep(e, 'ptCount')
                size = int(count.get('val')) if count is not None else (max(pts) + 1 if pts else 0)
                values = [pts.get(i) for i in range(size)]
                s[name] = [to_number(v) for v in values] if key != 'cat' else values
            sppr = kid(ser, 'spPr')
            fill = kid(sppr, 'solidFill')
            if fill is not None:
                c = fill[0] if len(fill) else None
                if c is not None and local(c) == 'srgbClr':
                    s['color'] = '#' + c.get('val')
            series.append(s)
        p['series'] = series
        info['plots'].append(p)
    legend = deep(root, 'legend')
    if legend is not None:
        pos = kid(legend, 'legendPos')
        info['legend'] = pos.get('val') if pos is not None else 'r'
    axes = []
    for ax in plot if plot is not None else []:
        if local(ax) in ('catAx', 'valAx', 'dateAx'):
            t = kid(ax, 'title')
            if t is not None:
                axes.append({'axis': local(ax), 'title': ''.join(x.text or '' for x in t.iter() if local(x) == 't')})
    if axes:
        info['axes'] = axes
    return info


def to_number(v):
    try:
        return float(v) if v not in (None, '') else None
    except ValueError:
        return v


def chart_rows(info):
    series = [s for p in info['plots'] for s in p['series']]
    if not series:
        return []
    if any('x' in s for s in series):
        rows = [['series', 'x', 'y', 'size']]
        for s in series:
            for i, x in enumerate(s.get('x', [])):
                y = s.get('y', [])
                z = s.get('size', [])
                rows.append([s['name'], x, y[i] if i < len(y) else '', z[i] if i < len(z) else ''])
        return rows
    cats = next((s['cats'] for s in series if s.get('cats')), [])
    size = max([len(cats)] + [len(s.get('vals', [])) for s in series])
    rows = [['category'] + [s['name'] or f'계열{i + 1}' for i, s in enumerate(series)]]
    for i in range(size):
        rows.append([cats[i] if i < len(cats) else i + 1] + [(s.get('vals') or [])[i] if i < len(s.get('vals') or []) else '' for s in series])
    return rows


def read_diagram(rel_ids, ctx, xfrm, tf):
    out = {'nodes': [], 'layout': ''}
    if rel_ids is None:
        return out
    dm = ctx.rels.get(attr(rel_ids, 'dm'))
    root = ctx.deck.pkg.xml(dm['target']) if dm else None
    drawing = None
    if root is not None:
        pts = {}
        kinds = {}
        for pt in iter_of(deep(root, 'ptLst')):
            mid = pt.get('modelId')
            kinds[mid] = pt.get('type', 'node')
            t = kid(pt, 't')
            pts[mid] = ' '.join(''.join(x.text or '' for x in p.iter() if local(x) == 't') for p in kids(t, 'p')).strip() if t is not None else ''
            if pt.get('type') == 'doc':
                pr = kid(pt, 'prSet')
                if pr is not None:
                    out['layout'] = (pr.get('loTypeId') or '').rsplit('/', 1)[-1]
        children = {}
        for c in iter_of(deep(root, 'cxnLst')):
            if c.get('type', 'parOf') == 'parOf':
                children.setdefault(c.get('srcId'), []).append((int(c.get('srcOrd', 0)), c.get('destId')))

        def tree(mid, depth, seen):
            if mid in seen:
                return
            seen.add(mid)
            for _, child in sorted(children.get(mid, [])):
                if kinds.get(child) in ('node', None, 'asst'):
                    if pts.get(child):
                        out['nodes'].append({'lvl': depth, 'text': pts[child]})
                    tree(child, depth + 1, seen)

        doc = next((m for m, k in kinds.items() if k == 'doc'), None)
        if doc:
            tree(doc, 0, set())
        ext = deep(root, 'dataModelExt')
        if ext is not None:
            rid = ext.get('relId')
            if rid in ctx.rels:
                drawing = ctx.rels[rid]['target']
    if drawing is None:
        drawing = next((r['target'] for r in ctx.rels.values() if r['type'] == 'diagramDrawing'), None)
    if drawing:
        d = ctx.deck.pkg.xml(drawing)
        if d is not None:
            sub = Context(ctx.deck, drawing, ctx.colors, master=ctx.master, layout=ctx.layout, slide_map=ctx.slide_map)
            shapes = []
            off = kid(xfrm, 'off')
            base = (tf[0], tf[1], tf[2] + int(off.get('x', 0)) * tf[0], tf[3] + int(off.get('y', 0)) * tf[1]) if off is not None else tf
            walk(deep(d, 'spTree'), sub, base, shapes, 'smartart')
            out['shape_count'] = len(shapes)
            if not out['nodes']:
                out['nodes'] = [{'lvl': 0, 'text': p['text']} for s in shapes for p in s.get('paras', [])]
    return out


def walk(tree, ctx, tf, out, group):
    for el in tree if tree is not None else []:
        n = local(el)
        if n == 'AlternateContent':
            pick = kid(el, 'Fallback')
            if pick is None or not len(pick):
                pick = kid(el, 'Choice')
            walk(pick, ctx, tf, out, group)
        elif n == 'sp':
            out.append(read_sp(el, ctx, tf, group))
        elif n == 'pic':
            out.append(read_pic(el, ctx, tf, group))
        elif n == 'cxnSp':
            out.append(read_connector(el, ctx, tf, group))
        elif n == 'graphicFrame':
            out.append(read_frame(el, ctx, tf, group))
        elif n == 'grpSp':
            c = nv(el)
            gid = f"g{c.get('id')}" if c is not None else 'g'
            pr = kid(el, 'grpSpPr')
            xfrm = kid(pr, 'xfrm')
            saved = ctx.group_fill
            ctx.group_fill = read_fill(pr, ctx) or saved
            walk(el, ctx, compose(tf, xfrm) if xfrm is not None else tf, out, group or gid)
            ctx.group_fill = saved
        elif n == 'contentPart':
            ctx.deck.flags['ink'] += 1


def notes_of(pkg, part):
    target = pkg.rel_of(part, 'notesSlide')
    root = pkg.xml(target) if target else None
    if root is None:
        return ''
    lines = []
    for sp in root.iter():
        if local(sp) != 'sp':
            continue
        ph = deep(kid(sp, 'nvSpPr'), 'ph')
        if ph is None or ph.get('type') not in ('body', None):
            continue
        for p in kids(kid(sp, 'txBody'), 'p'):
            text = ''.join(t.text or '' for t in p.iter() if local(t) == 't').strip()
            if text:
                lines.append(text)
    return '\n'.join(lines)


def title_of(shapes):
    for s in shapes:
        if s.get('ph') in ('title', 'ctrTitle') and s.get('paras'):
            return ' '.join(p['text'].replace('\n', ' ') for p in s['paras']).strip()
    return ''


FOOT = ('dt', 'ftr', 'sldNum')


def form_of(slide):
    """쪽의 성격을 거칠게 나눈다 — 집계와 옮기는 방법을 고르는 데 쓴다."""
    shapes = [s for s in slide['shapes'] if s.get('ph') not in FOOT and not s.get('hidden')]
    c = Counter(s['kind'] for s in shapes)
    body = [s for s in shapes if s['kind'] == 'text' and s.get('ph') not in ('title', 'ctrTitle', 'subTitle')]
    chars = sum(len(p['text']) for s in body for p in s['paras'])
    drawn = c['shape'] + c['line'] + sum(1 for s in body if s.get('fill') or s.get('geom', 'rect') not in ('rect',))
    if not shapes:
        return 'blank'
    if slide['layout_type'] in ('title', 'titleOnly') and not body and not c['picture'] and any(s.get('ph') == 'ctrTitle' for s in shapes):
        return 'cover'
    if any(s.get('ph') == 'ctrTitle' for s in shapes) and not c['table'] and not c['chart'] and c['picture'] < 3:
        return 'cover'
    if slide['layout_type'] == 'secHead':
        return 'section'
    if c['chart']:
        return 'chart'
    if c['smartart']:
        return 'smartart'
    if c['table']:
        return 'table'
    if drawn >= 8 or c['line'] >= 3 or (len(body) >= 6 and drawn >= 4):
        return 'diagram'
    if c['picture'] + c['ole'] + c['media'] and chars < 40:
        return 'picture'
    if c['picture'] + c['ole'] + c['media']:
        return 'text+picture'
    if len(body) >= 3:
        return 'cards'
    if body:
        return 'bullets'
    return 'title-only'


def clean(obj):
    """deck.json 에 넣을 때 ElementTree 잔여물이 없게 내부 키를 뺀다."""
    return obj


def px_box(s):
    if 'x' not in s:
        return '(자리 없음)'
    extra = f" rot{s['rot']}" if s.get('rot') else ''
    return f"({s['x']},{s['y']} {s['w']}×{s['h']}{extra})"


def run_md(run):
    t = run['t']
    if t == '\n':
        return ' / '
    core = t
    if run.get('b'):
        core = f'**{core.strip()}**' if core.strip() else core
    if run.get('i'):
        core = f'*{core.strip()}*' if core.strip() else core
    if run.get('c'):
        core = f'{{{run["c"]}|{core}}}'
    if run.get('link'):
        core = f'[{core}]({run["link"]})'
    return core


def para_md(p):
    head = '  ' * p.get('lvl', 0)
    bullet = p.get('bullet')
    head += (f'{bullet} ' if bullet else '')
    sizes = [r['sz'] for r in p['runs'] if r.get('sz')]
    size = f' [{max(sizes):g}pt]' if sizes else ''
    return f"{head}{''.join(run_md(r) for r in p['runs']).strip()}{size}"


def fill_md(f):
    if not f:
        return ''
    if f.get('c'):
        return f" fill={f['c']}"
    if f.get('grad'):
        return f" grad={'→'.join(f['grad'][:3])}"
    if f.get('img'):
        return f" fill=그림 {(f['img'] or {}).get('src', '')}"
    return ''


def outline(deck, slides, data):
    lines = [f"# {Path(data['file']).name}", '',
             f"쪽 {data['slides_total']} · 원본 {data['size']['px']} · Lectern {data['size']['target']} ({data['size']['fit']}) · 테마 {data['theme']['name']}",
             f"색 {' '.join(f'{k}=#{v}' for k, v in data['theme']['colors'].items())}",
             f"글꼴 {data['theme']['fonts']}", '']
    if data['footer']:
        lines += [f"꼬리말 후보: {data['footer']}", '']
    for lay in data['layouts']:
        if lay['decor'] or lay['bg']:
            bits = [f"{d['kind']}{px_box(d)}{fill_md(d.get('fill'))} {d.get('src', '')} {' '.join(p['text'] for p in d.get('paras', []))[:40]}" for d in lay['decor'][:8]]
            lines.append(f"레이아웃 '{lay['name']}' ({lay['used']}쪽) 배경={lay['bg']} 장식={bits}")
    lines.append('')
    for s in slides:
        tags = [s['form'], f"레이아웃 {s['layout']}"]
        if s['hidden']:
            tags.append('숨김')
        if s['animated']:
            tags.append('움직임')
        if s['bg']:
            tags.append('배경' + fill_md(s['bg']))
        lines.append(f"## {s['n']} · {s['title'] or '(제목 없음)'} [{' · '.join(tags)}]")
        for sh in s['shapes']:
            if sh.get('hidden'):
                continue
            if sh.get('ph') in FOOT:
                continue
            k = sh['kind']
            group = f" grp={sh['group']}" if sh.get('group') else ''
            head = f"- {k} #{sh.get('id')} {px_box(sh)}{group}"
            if sh.get('ph'):
                head += f" ph={sh['ph']}"
            if sh.get('geom') and sh['geom'] not in ('rect',):
                head += f" {sh['geom']}"
            head += fill_md(sh.get('fill'))
            if sh.get('line') and sh['line'].get('c'):
                head += f" line={sh['line']['c']}"
            if k == 'text':
                if sh.get('ph') in ('title', 'ctrTitle'):
                    continue
                lines.append(head)
                lines += ['    ' + para_md(p) for p in sh['paras']]
            elif k in ('picture', 'ole', 'media'):
                head += f" {sh.get('src', '')}"
                for key in ('alt', 'crop', 'needs_convert', 'linked', 'svg', 'prog', 'media', 'url'):
                    if sh.get(key):
                        head += f" {key}={sh[key]}"
                lines.append(head)
            elif k == 'table':
                lines.append(head + f" 표 {len(sh['rows'])}×{len(sh['cols'])}")
                for row in sh['rows'][:30]:
                    lines.append('    | ' + ' | '.join(c.get('text', '').replace('\n', ' / ') for c in row if not c.get('merged')) + ' |')
            elif k == 'chart':
                info = sh.get('chart') or {}
                kinds = ','.join(f"{p['type']}/{p.get('grouping', '')}/{p.get('barDir', '')}" for p in info.get('plots', []))
                lines.append(head + f" 차트 {kinds} 제목={info.get('title', '')} csv={info.get('csv', '')}")
            elif k == 'smartart':
                lines.append(head + f" SmartArt {sh.get('layout')} 도형 {sh.get('shape_count', 0)}")
                lines += ['    ' + '  ' * n['lvl'] + '- ' + n['text'] for n in sh.get('nodes', [])]
            elif k == 'line':
                ends = f" {sh.get('from', '')}→{sh.get('to', '')}" if sh.get('from') or sh.get('to') else ''
                lines.append(head + ends)
            else:
                lines.append(head)
        if s['notes']:
            lines.append('- 노트: ' + s['notes'].replace('\n', ' / '))
        lines.append('')
    return '\n'.join(lines)


def common_footer(feet, total):
    if not feet:
        return ''
    text, count = feet.most_common(1)[0]
    return text if count >= max(2, .3 * total) else ''


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('deck')
    ap.add_argument('out')
    ap.add_argument('--pages', help='3,5-9 처럼 일부 쪽만')
    args = ap.parse_args(argv)
    pages = None
    if args.pages:
        pages = set()
        for bit in args.pages.split(','):
            a, _, b = bit.partition('-')
            pages.update(range(int(a), int(b or a) + 1))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    deck = Deck(args.deck, out, pages)
    slides = [deck.slide(n, part) for n, part in deck.slides()]
    used = Counter(s['layout'] for s in slides)
    layouts = []
    for lay in deck.layouts.values():
        if used[lay['name']]:
            layouts.append({'name': lay['name'], 'type': lay['type'], 'used': used[lay['name']], 'bg': lay['bg'],
                            'decor': lay['decor'], 'master_decor': lay['master']['decor'] if lay['show_master'] else []})
    feet = Counter(p['text'] for s in slides for sh in s['shapes'] if sh.get('ph') == 'ftr' for p in sh.get('paras', []))
    pages_shown = sum(1 for s in slides for sh in s['shapes'] if sh.get('ph') == 'sldNum')
    master = next(iter(deck.masters.values()), None)
    sections = []
    for el in deck.pres.iter():
        if local(el) == 'section':
            ids = [i.get('id') for i in el.iter() if local(i) == 'sldId']
            sections.append({'name': el.get('name', ''), 'slides': len(ids)})
    data = {
        'file': str(args.deck), 'slides_total': len(deck.order),
        'size': {'px': f'{round(deck.cx / 9525)}×{round(deck.cy / 9525)}', 'target': f'{deck.target[0]}×{deck.target[1]}',
                 'ratio': round(deck.ratio, 3), 'fit': deck.fit, 'scale': round(deck.k * 9525, 4)},
        'theme': master['theme'] if master else {'name': '', 'colors': {}, 'fonts': {}},
        'masters': len(deck.masters), 'footer': common_footer(feet, len(slides)),
        'page_numbers': pages_shown, 'sections': sections, 'layouts': layouts,
        'flags': dict(deck.flags), 'media': sorted(deck.media.values()), 'slides': slides,
    }
    (out / 'deck.json').write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    (out / 'outline.md').write_text(outline(deck, slides, data), encoding='utf-8')
    forms = Counter(s['form'] for s in slides)
    print(json.dumps({'slides': len(slides), 'forms': forms, 'flags': deck.flags, 'media': len(deck.media)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
