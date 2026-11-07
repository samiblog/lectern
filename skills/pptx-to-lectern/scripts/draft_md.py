#!/usr/bin/env python3
"""deck.json 을 Lectern 슬라이드 초안으로 바꾼다. 글은 원문 그대로 옮기고 배치는 도형 좌표에서 뽑는다.

    python draft_md.py 읽은폴더 출력.md [--level 1|2|3] [--ref 쪽그림폴더]

level 1: 내용만 (제목·글·표·그림·노트, 한 단)
level 2: 구조까지 (좌표로 격자를 만들고 칸에 나눈다, 표지·장 구분)
level 3: 인상까지 (테마 색·글꼴·배경·칸 색·로고)
출력 옆에 <이름>-그림/ 과 <이름>-변환기록.json 을 둔다. 기록은 나중에 pptx 로 되돌릴 때 쓴다.
"""
import argparse
import base64
import json
import math
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # 없으면 도식을 그림으로 자르지 못하고 칸으로 둔다
    Image = None

FOOT = ('dt', 'ftr', 'sldNum')
TITLES = ('title', 'ctrTitle')
MONO = re.compile(r'courier|consolas|mono|code|코딩|d2coding|lucida console|menlo', re.I)
HAND_BULLET = re.compile(r'^\s*[•·▪●◦‣∙–—-]\s+')
NOTE_WORDS = re.compile(r'^\s*(_?(layout|grid|cols|rows|links|hidden|text|class|paginate|footer|header|backgroundColor|color|eyebrow))\b', re.I)
USABLE = {1280: (1168, 550), 960: (848, 550)}


def lum(c):
    c = c.lstrip('#')
    r, g, b = (int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda v: v / 12.92 if v <= .03928 else ((v + .055) / 1.055) ** 2.4
    return .2126 * f(r) + .7152 * f(g) + .0722 * f(b)


def contrast(a, b):
    x, y = sorted((lum(a), lum(b)), reverse=True)
    return (x + .05) / (y + .05)


PRIVATE = {0xF0E0: '→', 0xF0E8: '→', 0xF0DF: '←', 0xF0E7: '←', 0xF0A7: '▪', 0xF0B7: '•', 0xF0FC: '✓', 0xF0FB: '✗', 0xF0D8: '▶', 0xF075: '◆', 0xF06E: '■', 0xF0A8: '□', 0xF0F0: '⇨', 0xF0DC: '→'}


def esc(text, table=False):
    """Markdown 이 표시로 읽을 글자만 막는다. 한 줄 편집에서 원문이 지저분해지지 않게 꼭 필요한 곳만."""
    text = text.translate(PRIVATE)
    text = text.replace('\\', '\\\\').replace('*', '\\*').replace('`', '\\`')
    text = re.sub(r'<(?=[A-Za-z!/?])', '&lt;', text)
    text = re.sub(r'(?<![\w])_(?=\S)|(?<=\S)_(?![\w])', r'\\_', text)
    text = text.replace('[', '\\[')
    text = text.replace('~~', '\\~\\~')
    if re.search(r'\$\S[^$\n]*\S\$(?!\d)', text):
        text = text.replace('$', '\\$')
    if table:
        text = text.replace('|', '\\|')
    return text


def start_guard(line):
    """줄 맨 앞이 제목·목록·칸 표시로 읽히면 막는다."""
    m = re.match(r'^(\d+)([.)])(\s)', line)
    if m:
        return f'{m[1]}\\{m[2]}{m[3]}' + line[m.end():]
    if re.match(r'^(#{1,6}\s|>|[-+]\s|:::|---+\s*$|===+\s*$)', line):
        return '\\' + line
    return line


def main_color(sh):
    seen = Counter()
    for p in sh.get('paras', []):
        for r in p['runs']:
            c = r.get('c') or r.get('base_c')
            if c:
                seen[c] += len(r['t'])
    return seen.most_common(1)[0][0] if seen else None


def wrap_mark(text, mark):
    """표시는 글자에 바짝 붙고, 문장부호 끝 + 글자 시작이면 별표가 보이니 표시를 안쪽으로 당긴다."""
    lead = len(text) - len(text.lstrip())
    tail = len(text) - len(text.rstrip())
    core = text.strip()
    if not core:
        return text
    end = len(text) - tail if tail else len(text)
    return f'{text[:lead]}{mark}{core}{mark}{text[end:]}'


def inline(para, main, marks=True):
    parts = []
    for r in para['runs']:
        t = r['t']
        if r.get('field'):
            continue
        c = r.get('c') or r.get('base_c')
        strong = bool(r.get('b')) or bool(marks and main and c and c != main)
        key = (strong and marks, bool(r.get('i')) and marks, r.get('link') if marks else None, 'sup' if r.get('sup') else 'sub' if r.get('sub') else None)
        if parts and parts[-1][0] == key:
            parts[-1][1] += t
        else:
            parts.append([key, t])
    whole_bold = len(parts) == 1 and parts[0][0][0]
    out = []
    for (strong, italic, link, shift), t in parts:
        body = esc(t)
        if shift and marks and body.strip():
            body = f'<{shift}>{body.strip()}</{shift}>'
        before = ''.join(out)
        plain_mark = shift or not re.search(r'[\w가-힣]', body) or re.search(r'https?://\S*$', before)
        if strong and not whole_bold and not plain_mark:
            body = wrap_mark(body, '**')
        if italic:
            body = wrap_mark(body, '*')
        if link and link.startswith(('http://', 'https://', 'mailto:')):
            body = f'[{body.strip()}]({link})'
        out.append(body)
    text = ''.join(out)
    # 굵은 글이 문장부호로 끝나고 글자가 바로 이어지면 앱이 별표를 보인다 (안내서 2장)
    text = re.sub(r'([.,:;!?%)\]])\*\*(?=[\w가-힣])', r'**\1', text)
    return text.strip(), bool(whole_bold)


def is_code(sh):
    total = mono = 0
    for p in sh.get('paras', []):
        for r in p['runs']:
            n = len(r['t'].strip())
            total += n
            if r.get('font') and MONO.search(r['font']):
                mono += n
    return total >= 12 and mono / total > .8


def auto_label(kind, n):
    roman = ['i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix', 'x', 'xi', 'xii']
    if kind.startswith('alphaLc'):
        base = chr(96 + (n - 1) % 26 + 1)
    elif kind.startswith('alphaUc'):
        base = chr(64 + (n - 1) % 26 + 1)
    elif kind.startswith('romanLc'):
        base = roman[(n - 1) % 12]
    elif kind.startswith('romanUc'):
        base = roman[(n - 1) % 12].upper()
    else:
        base = str(n)
    if kind.endswith('ParenBoth'):
        return f'({base})'
    return f'{base})' if kind.endswith('ParenR') else f'{base}\\.'


def text_lines(sh, level):
    if is_code(sh):
        body = '\n'.join(''.join(r['t'] for r in p['runs']).rstrip() for p in sh['paras'])
        fence = '````' if '```' in body else '```'
        return [fence, *body.split('\n'), fence]
    main = main_color(sh)
    lines = []
    prev = None
    paras = sh['paras']
    count = 0
    for i, p in enumerate(paras):
        text, whole = inline(p, main)
        if not text:
            continue
        if str(p.get('bullet', '')).startswith('#'):
            count += 1
            lines.append(f"{auto_label(p['bullet'][1:], count)} {text}")
            prev = 'para-tight'
            continue
        count = 0
        hand = HAND_BULLET.match(p['text'])
        bullet = p.get('bullet') or ('•' if hand else None)
        if hand:
            text = HAND_BULLET.sub('', text, 1)
        lvl = p.get('lvl', 0)
        if bullet:
            marker = '1.' if bullet == '1.' else '-'
            pad = '   ' * lvl if marker == '1.' else '  ' * lvl
            if prev == 'para':
                lines.append('')
            rows = text.split('\n')
            lines.append(f'{pad}{marker} {rows[0]}')
            lines += [f'{pad}  {r.strip()}' for r in rows[1:] if r.strip()]
            prev = 'list'
        else:
            if prev:
                lines.append('')
            nxt = paras[i + 1] if i + 1 < len(paras) else None
            if whole and len(text) < 44 and '\n' not in text and nxt is not None and nxt.get('bullet') and level >= 2:
                lines.append(f'### {text}')
            else:
                rows = [start_guard(r.strip()) for r in text.split('\n') if r.strip()]
                lines += [f'**{r}**' for r in rows] if whole and len(paras) > 1 else rows
            prev = 'para'
    return lines


def table_lines(sh):
    rows = []
    for row in sh['rows']:
        cells = []
        last = None
        for c in row:
            text = c.get('text', '')
            if c.get('merged') or (c.get('mergedish') and text == last):
                cells.append('')
                continue
            last = text
            cells.append(esc(text, table=True).replace('\n', '<br>'))
        rows.append(cells)
    if not rows:
        return []
    width = max(len(r) for r in rows)
    rows = [r + [''] * (width - len(r)) for r in rows]
    out = ['| ' + ' | '.join(rows[0]) + ' |', '|' + '---|' * width]
    out += ['| ' + ' | '.join(r) + ' |' for r in rows[1:]]
    return out


def vega(info):
    plots = info.get('plots') or []
    if not plots or not plots[0].get('series'):
        return None
    p = plots[0]
    kind = p['type']
    series = [s for q in plots for s in q['series']]
    spec = {'width': 'container'}
    if kind in ('scatter', 'bubble'):
        vals = []
        for s in series:
            xs = s.get('x', [])
            numeric = all(isinstance(x, (int, float)) for x in xs if x is not None)
            for i, (x, y) in enumerate(zip(xs, s.get('y', []))):
                if y is not None:
                    vals.append({'계열': s['name'], 'x': x if numeric else i + 1, 'y': y})
        spec['data'] = {'values': vals}
        spec['mark'] = {'type': 'point', 'filled': True, 'size': 120}
        enc = {'x': {'field': 'x', 'type': 'quantitative', 'title': None}, 'y': {'field': 'y', 'type': 'quantitative', 'title': None}}
        if len(series) > 1:
            enc['color'] = {'field': '계열', 'type': 'nominal', 'title': None}
        spec['encoding'] = enc
        return spec
    vals = []
    for i, s in enumerate(series):
        name = s['name'] or f'계열{i + 1}'
        for c, v in zip(s.get('cats') or [], s.get('vals') or []):
            if v is not None:
                vals.append({'분류': str(c), '계열': name, '값': v})
    if not vals:
        return None
    order = list(dict.fromkeys(v['분류'] for v in vals))
    spec['data'] = {'values': vals}
    many = len(series) > 1
    if kind in ('pie', 'doughnut'):
        spec['mark'] = {'type': 'arc', **({'innerRadius': 60} if kind == 'doughnut' else {})}
        spec['encoding'] = {'theta': {'field': '값', 'type': 'quantitative'}, 'color': {'field': '분류', 'type': 'nominal', 'sort': order, 'title': None}}
        return spec
    mark = {'bar': 'bar', 'line': 'line', 'area': 'area'}.get(kind, 'bar')
    cat = {'field': '분류', 'type': 'ordinal', 'sort': order, 'title': None}
    num = {'field': '값', 'type': 'quantitative', 'title': None}
    if p.get('grouping') == 'percentStacked':
        num['stack'] = 'normalize'
    enc = {'x': num, 'y': cat} if p.get('barDir') == 'bar' else {'x': cat, 'y': num}
    if many:
        enc['color'] = {'field': '계열', 'type': 'nominal', 'title': None}
        if mark == 'bar' and p.get('grouping', 'clustered') in ('clustered', 'standard'):
            enc['yOffset' if p.get('barDir') == 'bar' else 'xOffset'] = {'field': '계열'}
    spec['mark'] = mark
    spec['encoding'] = enc
    return spec


def radar(info):
    """Vega-Lite 에는 레이더가 없다. 꺾은선으로 바꾸면 뜻이 달라지니 ECharts 로 옮긴다."""
    series = [s for q in info['plots'] for s in q['series']]
    cats = next((s['cats'] for s in series if s.get('cats')), [])
    top = max([v for s in series for v in s.get('vals', []) if isinstance(v, (int, float))] or [1])
    return {'legend': {'top': 0}, 'radar': {'indicator': [{'name': str(c), 'max': top * 1.2} for c in cats]},
            'series': [{'type': 'radar', 'data': [{'name': s['name'], 'value': s.get('vals', [])} for s in series]}]}


def chart_lines(sh):
    info = sh.get('chart') or {}
    out = []
    if info.get('title'):
        out += [f"### {esc(info['title'])}", '']
    if (info.get('plots') or [{}])[0].get('type') == 'radar':
        return out + ['```echarts', json.dumps(radar(info), ensure_ascii=False), '```']
    spec = vega(info)
    if spec is None:
        return out + ['(차트 값을 읽지 못했습니다)']
    return out + ['```vega-lite', json.dumps(spec, ensure_ascii=False), '```']


def smartart_lines(sh):
    nodes = sh.get('nodes') or []
    return [f"{'  ' * n['lvl']}- {esc(n['text'])}" for n in nodes]


def path_md(path):
    return f'<{path}>' if re.search(r'[\s()]', path) else path


class Builder:
    def __init__(self, data, src, out, level, ref):
        self.data = data
        self.src = Path(src)
        self.md = Path(out)
        self.level = level
        self.ref = Path(ref) if ref else None
        self.dir = self.md.with_name(self.md.stem + '-그림')
        self.target_w = int(data['size']['target'].split('×')[0])
        self.target_h = 720
        self.scale = data['size']['scale'] if 'scale' in data['size'] else 1
        self.record = []
        self.small = 0
        self.css = {}
        self.pt = float(data['size'].get('scale') or 1)
        self.shrink = 0
        self.outside = []
        self.title_shape = None
        self.current = None

    def use(self, rel):
        """쓰는 그림만 <이름>-그림/ 으로 복사한다."""
        if not rel:
            return None
        src = self.src / rel
        if not src.exists():
            return None
        self.dir.mkdir(parents=True, exist_ok=True)
        name = src.name
        if not (self.dir / name).exists():
            shutil.copyfile(src, self.dir / name)
        return f'{self.dir.name}/{name}'

    def picture_lines(self, sh):
        src = self.prepared(sh)
        if not src:
            return [f"<!-- 그림 {sh.get('src')} 은 브라우저가 못 보는 형식이라 뺐습니다 -->"] if sh.get('needs_convert') else []
        alt = re.sub(r'[\[\]\n]', ' ', sh.get('alt', ''))[:80].strip()
        size = f"w:{round(sh['w'])} " if sh.get('w') else ''
        line = f'![{size}{alt}]({path_md(src)})'.replace(' ]', ']')
        link = sh.get('link', '')
        return [f'[{line}]({link})' if link.startswith(('http://', 'https://', 'mailto:')) else line]

    def prepared(self, sh):
        """자른 그림은 잘라서, EMF·TIFF 는 쪽 그림의 그 자리를 오려서 쓴다."""
        rel = sh.get('src')
        if not rel or Image is None:
            return None if sh.get('needs_convert') else self.use(rel)
        n = self.current['n'] if self.current else 0
        self.dir.mkdir(parents=True, exist_ok=True)
        if sh.get('converted'):
            return self.use(sh['converted'])
        if sh.get('needs_convert') and Path(rel).suffix.lower() in ('.tif', '.tiff'):
            try:
                name = f'{Path(rel).stem}.png'
                Image.open(self.src / rel).convert('RGBA').save(self.dir / name)
                return f'{self.dir.name}/{name}'
            except Exception:  # noqa: BLE001 — 못 열면 쪽 그림에서 오린다
                pass
        if sh.get('needs_convert'):
            ref = self.ref / f'{n:03d}.png' if self.ref else None
            if ref is None or not ref.exists():
                return None
            img = Image.open(ref)
            k = img.width / self.target_w
            name = f"쪽{n:03d}-{sh.get('id')}.png"
            img.crop((max(0, round(sh['x'] * k)), max(0, round(sh['y'] * k)), round((sh['x'] + sh['w']) * k), round((sh['y'] + sh['h']) * k))).save(self.dir / name)
            return f'{self.dir.name}/{name}'
        crop = sh.get('crop')
        if crop and Path(rel).suffix.lower() in ('.png', '.jpg', '.jpeg', '.gif', '.bmp'):
            try:
                img = Image.open(self.src / rel)
                w, h = img.size
                box = (round(w * crop.get('l', 0) / 100), round(h * crop.get('t', 0) / 100), round(w * (1 - crop.get('r', 0) / 100)), round(h * (1 - crop.get('b', 0) / 100)))
                if box[2] > box[0] and box[3] > box[1]:
                    name = f"{Path(rel).stem}-쪽{n:03d}-{sh.get('id')}{Path(rel).suffix.lower()}"
                    out = img.crop(box)
                    if out.mode not in ('RGB', 'L') and Path(rel).suffix.lower() in ('.jpg', '.jpeg'):
                        out = out.convert('RGB')
                    out.save(self.dir / name)
                    return f'{self.dir.name}/{name}'
            except Exception:  # noqa: BLE001 — 자르지 못하면 원본을 쓴다
                pass
        return self.use(rel)

    def block_lines(self, sh):
        k = sh['kind']
        if k == 'text':
            return text_lines(sh, self.level)
        if k == 'table':
            return table_lines(sh)
        if k == 'chart':
            return chart_lines(sh)
        if k == 'smartart':
            return smartart_lines(sh)
        if k in ('picture', 'ole', 'media'):
            lines = self.picture_lines(sh)
            if sh.get('url'):
                lines.append(f"[영상 열기]({sh['url']})")
            return lines
        return []

    def blocks(self, slide):
        """쪽의 내용 덩이를 고른다. 빈 도형은 장식이니 뺀다."""
        shapes = [s for s in slide['shapes'] if s.get('ph') not in FOOT and not s.get('hidden') and s.get('ph') not in TITLES]
        out, dropped = [], 0
        for s in shapes:
            if s['kind'] in ('shape', 'line', 'unknown', 'group'):
                dropped += 1
                continue
            bg = (slide.get('bg') or {}).get('c')
            if s['kind'] == 'text' and bg and not s.get('fill') and main_color(s) and contrast(main_color(s), bg) < 1.15:
                dropped += 1
                self.outside += [p['text'].replace('\n', ' ') for p in s.get('paras', [])]
                continue
            if s['kind'] in ('picture', 'ole', 'media') and 'x' in s and s['w'] * s['h'] < .0006 * self.target_w * self.target_h:
                dropped += 1
                continue
            if 'x' not in s:
                s = {**s, 'x': 56, 'y': 120, 'w': 400, 'h': 200}
            if s['x'] >= self.target_w or s['y'] >= self.target_h or s['x'] + s['w'] <= 0 or s['y'] + s['h'] <= 0:
                dropped += 1
                self.outside += [p['text'].replace('\n', ' ') for p in s.get('paras', [])]
                continue
            out.append(s)
        return out, dropped

    def is_diagram(self, slide, blocks):
        """칸으로 다시 짜면 뜻이 깨지는 쪽을 고른다. 그런 쪽은 그림으로 남긴다."""
        shapes = [s for s in slide['shapes'] if s.get('ph') not in FOOT and not s.get('hidden') and s.get('ph') not in TITLES]
        if any(s['kind'] == 'chart' for s in shapes):
            return []
        area = self.target_w * self.target_h
        lines = sum(1 for s in shapes if s['kind'] == 'line')
        empty = sum(1 for s in shapes if s['kind'] == 'shape' and (s.get('fill') or s.get('line')) and s.get('w', 0) * s.get('h', 0) > .0008 * area)
        texts = [s for s in shapes if s['kind'] == 'text']
        odd = sum(1 for s in texts if s.get('geom') not in (None, 'rect', 'roundRect', 'mso5', 'custom') or s.get('rot'))
        small = sum(1 for s in shapes if s['kind'] == 'picture' and s.get('w', 0) * s.get('h', 0) < .03 * area)
        pics = sum(1 for s in shapes if s['kind'] == 'picture')
        over = 0
        for i, a in enumerate(blocks):
            for b in blocks[i + 1:]:
                ox = min(a['x'] + a['w'], b['x'] + b['w']) - max(a['x'], b['x'])
                oy = min(a['y'] + a['h'], b['y'] + b['h']) - max(a['y'], b['y'])
                if ox > 20 and oy > 20 and ox * oy > .15 * min(a['w'] * a['h'], b['w'] * b['h']):
                    over += 1
        reasons = []
        if lines >= 2 and len(texts) >= 2:
            reasons.append(f'선 {lines}')
        if empty >= 4:
            reasons.append(f'도형 {empty}')
        if odd >= 3:
            reasons.append(f'모양 글상자 {odd}')
        if small >= 3 and len(texts) >= 2:
            reasons.append(f'작은 그림 {small}')
        if pics >= 3 and over >= 2:
            reasons.append('겹친 그림')
        if over >= 3:
            reasons.append(f'겹침 {over}')
        if slide['form'] == 'smartart' and sum(len(s.get('nodes', [])) for s in shapes) >= 7:
            reasons.append('큰 SmartArt')
        return reasons

    def bleed(self, blocks):
        """쪽을 꽉 채우거나 한쪽을 가득 채운 사진을 배경으로 뺀다."""
        area = self.target_w * self.target_h
        for b in blocks:
            if b['kind'] != 'picture' or b.get('needs_convert'):
                continue
            full_h = b['h'] >= .92 * self.target_h and b['y'] <= .05 * self.target_h
            if b['w'] * b['h'] >= .85 * area:
                return b, 'full'
            if full_h and b['x'] <= 6 and b['w'] < .7 * self.target_w:
                return b, 'left'
            if full_h and b['x'] + b['w'] >= self.target_w - 6 and b['w'] < .7 * self.target_w:
                return b, 'right'
        return None, None

    def picture_slide(self, slide, title, blocks, reasons):
        """쪽의 도식 영역을 PowerPoint 그림에서 잘라 넣고 글은 노트에 남긴다."""
        ref = self.ref / f"{slide['n']:03d}.png" if self.ref else None
        if ref is None or not ref.exists() or Image is None:
            return None
        shapes = [s for s in slide['shapes'] if s.get('ph') not in FOOT and not s.get('hidden') and s.get('ph') not in TITLES and 'x' in s]
        guess = self.title_shape
        if guess is not None:
            shapes = [s for s in shapes if s.get('id') != guess.get('id')]
        if not shapes:
            return None
        x0 = max(0, min(s['x'] for s in shapes) - 8)
        y0 = max(0, min(s['y'] for s in shapes) - 8)
        x1 = min(self.target_w, max(s['x'] + s['w'] for s in shapes) + 8)
        y1 = min(self.target_h, max(s['y'] + s['h'] for s in shapes) + 8)
        title_box = guess or next((s for s in slide['shapes'] if s.get('ph') in TITLES and 'x' in s), None)
        if title and title_box:
            y0 = max(y0, min(title_box['y'] + title_box['h'], y1 - 80))
        img = Image.open(ref)
        k = img.width / self.target_w
        self.dir.mkdir(parents=True, exist_ok=True)
        name = f"쪽{slide['n']:03d}.png"
        img.crop((round(x0 * k), round(y0 * k), round(x1 * k), round(y1 * k))).save(self.dir / name, optimize=True)
        words = []
        for s in shapes:
            words += [p['text'].replace('\n', ' ') for p in s.get('paras', [])]
            words += [n['text'] for n in s.get('nodes', [])]
            words += [' | '.join(c.get('text', '').replace('\n', ' ') for c in row if not c.get('merged')) for row in s.get('rows', [])]
        body = [f'## {esc(title)}', ''] if title else []
        head = ['<!-- grid: t / a -->'] if title else ['<!-- grid: a -->']
        alt = re.sub(r'[\[\]\n]', ' ', title or '도식')[:60].strip()
        body += ['::: a center text-center', f'![{alt}]({path_md(f"{self.dir.name}/{name}")})', ':::']
        return head, body, words

    def title_of(self, slide, blocks):
        self.title_shape = None
        if slide['title']:
            return slide['title'], blocks
        top = [b for b in blocks if b['kind'] == 'text' and b['y'] < 170 and len(b['paras']) <= 2]
        top = [b for b in top if max((r.get('sz') or 0 for p in b['paras'] for r in p['runs']), default=0) >= 20 and sum(len(p['text']) for p in b['paras']) < 110]
        top = [b for b in top if len(re.findall(r'[A-Za-z가-힣]', ''.join(p['text'] for p in b['paras']))) >= 3]
        if top:
            best = min(top, key=lambda b: b['y'])
            self.title_shape = best
            return ' '.join(p['text'].replace('\n', ' ') for p in best['paras']), [b for b in blocks if b is not best]
        return '', blocks

    def fit_pictures(self, lines, w, h):
        """w: 를 준 그림이 칸보다 크면 앱이 높이만 줄여 찌그러진다. 칸 안에 들어가는 폭으로 쓴다."""
        texts = sum(1 for l in lines if l.strip() and not l.startswith('!['))
        room = max(60, h - texts * 34)
        pics = sum(1 for l in lines if l.startswith('!['))
        room /= max(1, pics)
        out = []
        for line in lines:
            m = re.match(r'^!\[w:(\d+)( [^\]]*)?\]\((<[^>]+>|[^)]+)\)$', line)
            if not m:
                out.append(line)
                continue
            width = int(m[1])
            aspect = None
            if Image is not None:
                try:
                    with Image.open(self.md.parent / m[3].strip('<>')) as img:
                        aspect = img.width / max(1, img.height)
                except Exception:  # noqa: BLE001
                    aspect = None
            limit = w - 34
            if aspect:
                limit = min(limit, room * aspect)
            elif width > limit:
                out.append(f'![{(m[2] or "").strip()}]({m[3]})')
                continue
            out.append(f"![w:{max(24, round(min(width, limit)))}{m[2] or ''}]({m[3]})")
        return out

    def source_size(self, parts):
        seen = Counter()
        for b in parts:
            for p in b.get('paras', []):
                for r in p['runs']:
                    if r.get('sz'):
                        seen[r['sz']] += len(r['t'])
        if not seen:
            return None
        return seen.most_common(1)[0][0] * self.pt

    def cell_size(self, lines, w, h, want=None):
        """바라는 크기부터 내려가며 들어가는 크기를 찾는다. 약값이다."""
        text = [re.sub(r'^\s*([-#>]+|\d+\.)\s*', '', l) for l in lines if l.strip()]
        if any(l.startswith('|') for l in lines):
            rows = sum(1 for l in lines if l.startswith('|')) - 1
            for size in (14, 13, 12):
                if rows * 40 * size / 14 <= h:
                    return None if size == 14 else size
            return 12
        if any(l.startswith(('![', '```')) for l in lines) and not any(not l.startswith(('![', '```')) for l in text):
            return None
        want = min(max(want or 18, 12), 32)
        sizes = sorted({round(want), 24, 20, 18, 16, 14, 12}, reverse=True)
        sizes = [s for s in sizes if s <= round(want)]
        pics = sum(float(m.group(1)) * .6 for l in lines for m in [re.match(r'!\[w:(\d+)', l)] if m)
        for size in sizes:
            need = 0
            for t in text:
                if t.startswith('!['):
                    continue
                ko = len(re.findall(r'[가-힣]', t))
                width = (ko * 1.28 + (len(t) - ko) * .72) * size
                need += max(1, math.ceil(width / max(w - 30, 60)))
            if need * 1.95 * size + pics <= h:
                return None if size == 18 else size
        return 12

    def grid(self, blocks):
        boxes = [(b['x'], b['y'], b['x'] + b['w'], b['y'] + b['h'], b) for b in blocks]
        leaves = []
        xycut(boxes, (0, 0, self.target_w, self.target_h), leaves)
        xs = snap(sorted({l[0][0] for l in leaves} | {l[0][2] for l in leaves}))
        ys = snap(sorted({l[0][1] for l in leaves} | {l[0][3] for l in leaves}))
        return leaves, xs, ys

    def slide_md(self, slide):
        lvl = self.level
        self.current = slide
        self.outside = []
        blocks, dropped = self.blocks(slide)
        title, blocks = self.title_of(slide, blocks)
        form = slide['form']
        rec = {'n': slide['n'], 'form': form, 'layout': slide['layout'], 'title': title, 'dropped_shapes': dropped, 'animated': slide['animated']}
        head, body = [], []
        if slide['hidden']:
            head.append('<!-- hidden: true -->')
            rec['hidden'] = True
        notes = slide['notes']
        if self.outside:
            notes = (notes + '\n\n' if notes else '') + '쪽 밖의 글\n' + '\n'.join(f'- {w}' for w in self.outside)
            rec['outside_text'] = self.outside
        if lvl >= 2 and form not in ('cover', 'section') and self.statement(slide, blocks):
            form = 'section'
            rec['statement'] = True
            if not title and blocks:
                ordered = sorted(blocks, key=lambda b: (round(b['y'] / 24), b['x']))
                title = ' '.join(p['text'].replace('\n', ' ') for b in ordered for p in b['paras'])
                blocks = []
        reasons = self.is_diagram(slide, blocks) if lvl >= 2 and form not in ('cover', 'section') else []
        made = self.picture_slide(slide, title, blocks, reasons) if reasons else None
        if form in ('cover', 'section') and lvl >= 2:
            head += self.cover_head(slide)
            pic, side = self.bleed(blocks) if lvl >= 3 else (None, None)
            if pic:
                src = self.use(pic.get('src'))
                if src:
                    body += [f"![bg{'' if side == 'full' else ' ' + side + ':' + str(round(100 * pic['w'] / self.target_w)) + '%'}]({path_md(src)})", '']
                blocks = [b for b in blocks if b is not pic]
            if lvl >= 3 and form == 'cover':
                body += self.cover_logo(slide)
            body.append(f"{'#' if form == 'cover' else '##'} {esc(title or ' ')}")
            for b in sorted(blocks, key=lambda b: (round(b['y'] / 24), b['x'])):
                if b['kind'] == 'text':
                    body += ['', *[l for l in text_lines(b, lvl) if l.strip()]]
                else:
                    body += ['', *self.block_lines(b)]
            if lvl >= 3 and form == 'cover':
                for line in self.layout_text(slide):
                    body += ['', line]
            rec['how'] = form
        elif form not in ('cover', 'section') and lvl >= 3 and self.rare_layout(slide) and self.layout_text(slide) and not made:
            more, grid_head, how = self.grid_md(slide, title, blocks) if blocks else ([f'## {esc(title)}'] if title else [], [], 'flat')
            head += grid_head
            body += more
            lines = self.layout_text(slide)
            rec['how'] = how
            rec['layout_text'] = lines
            notes = (notes + '\n\n' if notes else '') + '레이아웃의 글\n' + '\n'.join(f'- {w}' for w in lines)
        elif made:
            grid_head, grid_body, words = made
            head += grid_head
            body += grid_body
            rec['how'] = 'picture'
            rec['why'] = reasons
            rec['picture_text'] = words
            if words:
                joined = '\n'.join(f'- {w}' for w in words)
                notes = (notes + '\n\n' if notes else '') + '그림 속 글\n' + joined
        elif lvl == 1 or not blocks:
            if title:
                body.append(f'## {esc(title)}')
            for b in sorted(blocks, key=lambda b: (b['y'], b['x'])):
                body += ['', *self.block_lines(b)]
            rec['how'] = 'flat'
        else:
            pic, side = self.bleed(blocks)
            if pic and (side == 'full' or len(blocks) > 1):
                src = self.use(pic.get('src'))
                if src:
                    filt = ' brightness:.5' if side == 'full' and len(blocks) > 1 else ''
                    body += [f"![bg{filt}{'' if side == 'full' else ' ' + side + ':' + str(round(100 * pic['w'] / self.target_w)) + '%'}]({path_md(src)})", '']
                    blocks = [b for b in blocks if b is not pic]
                    rec['bg_picture'] = side
                    if side == 'full' and blocks:
                        head.append('<!-- _class: invert -->')
            if blocks or title:
                self.shrink = (pic['w'] / self.target_w) if pic and side != 'full' else 0
                more, grid_head, how = self.grid_md(slide, title, blocks)
                self.shrink = 0
                head += grid_head
                body += more
                rec['how'] = how
            else:
                rec['how'] = 'bg'
        if lvl >= 3:
            head += self.slide_colors(slide, form)
        if notes:
            clean = notes.replace('-->', '—>').replace('<!--', '')
            if NOTE_WORDS.match(clean):
                clean = '노트 · ' + clean
            body += ['', '<!--', clean, '-->']
        self.record.append(rec)
        return '\n'.join([*head, *([''] if head else []), *body])

    def statement(self, slide, blocks):
        """큰 글 몇 낱말만 있는 쪽. 작은 제목으로 두면 뜻이 사라진다."""
        if any(b['kind'] != 'text' for b in blocks) or len(blocks) > 2:
            return False
        shapes = [s for s in slide['shapes'] if s.get('kind') == 'text' and s.get('ph') not in FOOT]
        chars = sum(len(p['text']) for s in shapes for p in s['paras'])
        if any(p.get('bullet') for s in shapes for p in s['paras']) or sum(len(s['paras']) for s in shapes) > 3:
            return False
        big = max((r.get('sz') or 0 for s in shapes for p in s['paras'] for r in p['runs']), default=0) * self.pt
        return 0 < chars <= 70 and big >= 36

    def cover_head(self, slide):
        head = ['<!-- _paginate: false -->']
        bg = (slide.get('bg') or {}).get('c')
        light = self.level >= 3 and bg and lum(bg) > .6
        head.insert(0, '<!-- _class: lead paper -->' if light else '<!-- _class: lead -->')
        return head

    def cover_logo(self, slide):
        lay = next((l for l in self.data['layouts'] if l['name'] == slide['layout']), None)
        pics = [d for d in (lay['decor'] if lay else []) if d.get('kind') == 'picture' and d.get('src') and not d.get('needs_convert')]
        pics = [d for d in pics if d['w'] * d['h'] < .25 * self.target_w * self.target_h]
        if not pics:
            return []
        d = max(pics, key=lambda p: p['w'] * p['h'])
        src = self.use(d['src'])
        return [f"![w:{round(d['w'])}]({path_md(src)})", ''] if src else []

    def rare_layout(self, slide):
        lay = next((l for l in self.data['layouts'] if l['name'] == slide['layout']), None)
        return bool(lay) and lay['used'] <= 2

    def layout_text(self, slide):
        lay = next((l for l in self.data['layouts'] if l['name'] == slide['layout']), None)
        if not lay:
            return []
        return [esc(p['text'].replace('\n', ' ')) for d in lay['decor'] for p in d.get('paras', [])]

    def clusters(self, blocks):
        """붙어 있는 덩이를 한 칸으로 묶는다 — 아이콘과 설명, 소제목과 본문."""
        groups = [[b] for b in sorted(blocks, key=lambda b: (b['y'], b['x']))]
        changed = True
        while changed:
            changed = False
            for i, a in enumerate(groups):
                for j, b in enumerate(groups):
                    if i >= j or not near(bbox(a), bbox(b), self.target_w):
                        continue
                    if any(x['kind'] in ('table', 'chart', 'smartart') for x in a + b):
                        continue
                    groups[i] = a + b
                    del groups[j]
                    changed = True
                    break
                if changed:
                    break
        out = []
        for g in groups:
            x0, y0, x1, y1 = bbox(g)
            out.append({'x': x0, 'y': y0, 'w': x1 - x0, 'h': y1 - y0, 'parts': sorted(g, key=lambda b: (b['y'], b['x']))})
        return out

    def cell_lines(self, cl):
        parts = cl['parts']
        kpi = self.kpi_lines(parts)
        if kpi:
            return kpi, ['kpi']
        lines = []
        for b in parts:
            more = self.block_lines(b)
            if more:
                lines += ([''] if lines else []) + more
        return lines, []

    def kpi_lines(self, parts):
        if len(parts) != 1 or parts[0]['kind'] != 'text' or len(parts[0]['paras']) < 2:
            return None
        paras = parts[0]['paras']
        first = paras[0]['text']
        if len(first) > 9 or not re.search(r'\d', first):
            return None
        s0 = max((r.get('sz') or 0 for r in paras[0]['runs']), default=0)
        s1 = max((r.get('sz') or 0 for r in paras[1]['runs']), default=0)
        if s0 < 1.25 * s1:
            return None
        label = ' '.join(p['text'].replace('\n', ' ') for p in paras[1:])
        return [f'**{esc(first)}**', esc(label)]

    def grid(self, cells):
        boxes = [(b['x'], b['y'], b['x'] + b['w'], b['y'] + b['h'], b) for b in cells]
        leaves = []
        xycut(boxes, (0, 0, self.target_w, self.target_h), leaves)
        xs = snap(sorted({l[0][0] for l in leaves} | {l[0][2] for l in leaves}))
        ys = snap(sorted({l[0][1] for l in leaves} | {l[0][3] for l in leaves}))
        return leaves, xs, ys

    def grid_md(self, slide, title, blocks):
        cells_in = self.clusters(blocks)
        if not cells_in:
            return ([f'## {esc(title)}'] if title else []), [], 'title-only'
        leaves, xs, ys = self.grid(cells_in)
        ux, uy = USABLE[self.target_w]
        ux *= 1 - self.shrink
        ncol, nrow = len(xs) - 1, len(ys) - 1
        matrix = [['.'] * ncol for _ in range(nrow)]
        conflict = ncol < 1 or nrow < 1 or ncol * nrow > 36
        spots = []
        names = iter('abcdefghijklmnopqrsuvwxyz')
        for box, cl in sorted(leaves, key=lambda l: (l[1]['y'], l[1]['x'])):
            name = next(names, None) or f'k{len(spots)}'
            if conflict:
                spots.append((name, cl, None))
                continue
            c0, c1 = min(nearest(xs, box[0]), ncol - 1), min(nearest(xs, box[2]), ncol)
            r0, r1 = min(nearest(ys, box[1]), nrow - 1), min(nearest(ys, box[3]), nrow)
            c1, r1 = max(c1, c0 + 1), max(r1, r0 + 1)
            if any(matrix[r][c] != '.' for r in range(r0, r1) for c in range(c0, c1)):
                conflict = True
            for r in range(r0, r1):
                for c in range(c0, c1):
                    matrix[r][c] = name
            spots.append((name, cl, ((xs[c1] - xs[c0]) / (xs[-1] - xs[0]) * ux, (ys[r1] - ys[r0]) / (ys[-1] - ys[0]) * uy)))
        if conflict:
            return self.at_md(title, cells_in)
        cells = []
        for name, cl, (w, h) in spots:
            lines, words = self.cell_lines(cl)
            if not lines:
                continue
            lines = self.fit_pictures(lines, w, h)
            words = list(words)
            if 'kpi' not in words:
                size = self.cell_size(lines, w, h, self.source_size(cl['parts']))
                if size:
                    words.append(str(size))
                    self.small += size < 14
            words += self.cell_words(cl['parts'][0] if len(cl['parts']) == 1 else {})
            if all(l.startswith(('![', '[![')) or not l.strip() for l in lines):
                words += ['center', 'text-center']
            cells.append((name, words, lines))
        used = {c[0] for c in cells}
        matrix = [[v if v in used else '.' for v in row] for row in matrix]
        cols = [xs[i + 1] - xs[i] for i in range(ncol)]
        rows = [ys[i + 1] - ys[i] for i in range(nrow)]
        keep_r = [i for i, row in enumerate(matrix) if any(v != '.' for v in row)]
        keep_c = [i for i in range(ncol) if any(matrix[r][i] != '.' for r in range(nrow))]
        matrix = [[matrix[r][c] for c in keep_c] for r in keep_r]
        cols = [cols[i] for i in keep_c]
        rows = [rows[i] for i in keep_r]
        if not matrix or not matrix[0]:
            return ([f'## {esc(title)}'] if title else []), [], 'title-only'
        head = []
        rows_txt = ' / '.join(' '.join(r) for r in matrix)
        if title:
            rows_txt = ' '.join(['t'] * len(matrix[0])) + ' / ' + rows_txt
        head.append(f'<!-- grid: {rows_txt} -->')
        if len(cols) > 1 and max(cols) / max(1, min(cols)) > 1.2:
            head.append(f"<!-- cols: {' '.join(fr(c, sum(cols)) for c in cols)} -->")
        if len(rows) > 1 and max(rows) / max(1, min(rows)) > 1.2:
            head.append(f"<!-- rows: {'auto ' if title else ''}{' '.join(fr(r, sum(rows)) for r in rows)} -->")
        body = [f'## {esc(title)}', ''] if title else []
        for name, words, lines in cells:
            body += [f"::: {' '.join([name, *words])}", *lines, ':::', '']
        return body[:-1] if body and body[-1] == '' else body, head, 'grid'

    def at_md(self, title, cells):
        """격자로 못 나누는 배치는 원본 자리 그대로 놓는다."""
        top = 120
        ux, uy = USABLE[self.target_w]
        body = [f'## {esc(title)}', ''] if title else []
        low = min(c['y'] for c in cells)
        high = max(c['y'] + c['h'] for c in cells)
        ky = min(1, uy / max(1, high - low))
        kx = ux / self.target_w
        for i, cl in enumerate(sorted(cells, key=lambda c: (c['y'], c['x']))):
            x = round(56 + cl['x'] * kx)
            y = round(top + (cl['y'] - low) * ky)
            w = max(60, min(round(cl['w'] * kx), 56 + ux - x))
            h = max(40, min(round(cl['h'] * ky), 660 - y))
            lines, words = self.cell_lines(cl)
            if not lines:
                continue
            lines = self.fit_pictures(lines, w, h)
            words = [w_ for w_ in words if w_ != 'kpi']
            size = self.cell_size(lines, w, h, self.source_size(cl['parts']))
            if size:
                words.append(str(size))
                self.small += size < 14
            words += self.cell_words(cl['parts'][0] if len(cl['parts']) == 1 else {})
            body += [f"::: b{i + 1} {' '.join(words)} at {x} {y} {w} {h}".replace('  ', ' '), *lines, ':::', '']
        return body[:-1] if body and body[-1] == '' else body, [], 'at'

    def cell_words(self, b):
        fill = b.get('fill') or {}
        if self.level < 2 or not fill.get('c') or fill.get('alpha', 1) < .3:
            return []
        c = fill['c'].upper()
        if c in ('#FFFFFF', '#FEFEFE') or b['kind'] != 'text':
            return []
        if self.level >= 3:
            name = 'c' + c[1:].lower()
            main = main_color(b) or ('#000000' if lum(c) > .4 else '#FFFFFF')
            if contrast(main, c) < 3:
                main = '#000000' if lum(c) > .4 else '#FFFFFF'
            self.css[name] = f'.{name} {{ background: {c}; color: {main}; --md-fg: {main}; --md-strong: {main}; --md-heading: {main}; border-radius: 6px; padding: 12px 16px; }}'
            return [name]
        return ['dark'] if lum(c) < .2 else ['card']

    def slide_colors(self, slide, form):
        bg = (slide.get('bg') or {}).get('c')
        if not bg or (bg.upper() == self.base_bg and form not in ('cover', 'section')):
            return []
        fg = '#FFFFFF' if lum(bg) < .4 else '#17293D'
        return [f'<!-- _backgroundColor: {bg} -->', f'<!-- _color: {fg} -->']

    def front(self):
        d = self.data
        title = next((r['title'] for r in self.record if r['title']), Path(d['file']).stem)
        lines = ['---', 'marp: true', f'title: {json.dumps(title, ensure_ascii=False)}']
        if d.get('page_numbers'):
            lines.append('paginate: true')
        if d.get('footer'):
            lines.append(f"footer: {json.dumps(d['footer'], ensure_ascii=False)}")
        if self.target_w == 960:
            lines.append('size: 4:3')
        if self.small > .15 * max(1, len(self.record)):
            lines.append('reading: true')
        if self.level >= 3:
            css = self.theme_css()
            if css:
                lines.append('style: |')
                lines += ['  ' + l for l in css]
        lines.append('---')
        return '\n'.join(lines)

    def theme_css(self):
        d = self.data
        t = d['theme']['colors']
        pick = lambda k: '#' + t[k].lstrip('#') if t.get(k) else None
        dk2, a1, a2 = pick('dk2'), pick('accent1'), pick('accent2')
        bg = self.base_bg
        fg = '#FFFFFF' if lum(bg) < .4 else '#1F2933'
        titles = Counter()
        for sl in d['slides']:
            for sh in sl['shapes']:
                if sh.get('ph') in TITLES:
                    for p in sh.get('paras', []):
                        for r in p['runs']:
                            c = r.get('c') or r.get('base_c')
                            if c:
                                titles[c.upper()] += len(r['t'])
        from_title = next((c for c, _ in titles.most_common(3) if contrast(c, bg) >= 3), None)
        heading = from_title or next((c for c in (dk2, a1, a2) if c and contrast(c, bg) >= 3), fg)
        accent = next((c for c in (a1, a2, dk2) if c and contrast(c, '#FFFFFF') >= 3), heading)
        vars_ = [f'--md-bg: {bg};', f'--md-fg: {fg};', f'--md-heading: {heading};', f'--md-strong: {heading};', f'--md-link: {accent};',
                 f'--md-th-bg: {accent};', '--md-th-fg: #FFFFFF;', f'--md-th-rule: {accent};', f'--md-quote-bar: {accent};']
        out = ['section {', *['  ' + v for v in vars_], f'  background: {bg}; color: {fg};', '}']
        logo = self.logo()
        if logo:
            out += logo
        out += list(self.css.values())
        return out

    def logo(self):
        """가장 많이 쓰는 레이아웃의 작은 그림을 모든 쪽 구석에 놓는다. CSS 는 파일을 못 읽으니 data 그림으로."""
        lays = sorted(self.data['layouts'], key=lambda l: -l['used'])
        for lay in lays[:1]:
            for d in lay['decor'] + lay['master_decor']:
                src = d.get('src')
                if not src or d.get('kind') != 'picture' or d.get('needs_convert'):
                    continue
                if d['w'] * d['h'] > .06 * self.target_w * self.target_h:
                    continue
                path = self.src / src
                if not path.exists() or path.stat().st_size > 90_000:
                    continue
                kind = 'svg+xml' if path.suffix == '.svg' else 'jpeg' if path.suffix in ('.jpg', '.jpeg') else path.suffix.lstrip('.')
                data = base64.b64encode(path.read_bytes()).decode()
                right = d['x'] > self.target_w / 2
                bottom = d['y'] > self.target_h / 2
                side = f"right: {max(0, self.target_w - d['x'] - d['w'])}px" if right else f"left: {d['x']}px"
                edge = f"bottom: {max(0, self.target_h - d['y'] - d['h'])}px" if bottom else f"top: {d['y']}px"
                return ['section::before {', f"  content: ''; position: absolute; {side}; {edge}; width: {d['w']}px; height: {d['h']}px;",
                        f"  background: url(data:image/{kind};base64,{data}) center / contain no-repeat;", '}']
        return None

    def build(self):
        slides = self.data['slides']
        bgs = Counter((s.get('bg') or {}).get('c', '#FFFFFF').upper() for s in slides)
        self.base_bg = bgs.most_common(1)[0][0] if bgs else '#FFFFFF'
        parts = [self.slide_md(s) for s in slides]
        doc = self.front() + '\n\n' + '\n\n---\n\n'.join(p or '<!-- 빈 쪽 -->' for p in parts) + '\n'
        self.md.write_text(doc, encoding='utf-8', newline='\n')
        record = {'source': self.data['file'], 'level': self.level, 'size': self.data['size'], 'theme': self.data['theme'], 'slides': self.record}
        self.md.with_name(self.md.stem + '-변환기록.json').write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding='utf-8')
        return Counter(r['how'] for r in self.record)


def bbox(group):
    return (min(b['x'] for b in group), min(b['y'] for b in group),
            max(b['x'] + b['w'] for b in group), max(b['y'] + b['h'] for b in group))


def near(a, b, width):
    """위아래로 붙어 있고 가로로 겹치면 한 덩이다. 쪽의 절반이 넘는 넓은 덩이는 묶지 않는다."""
    if a[1] > b[1]:
        a, b = b, a
    gap = b[1] - a[3]
    overlap = min(a[2], b[2]) - max(a[0], b[0])
    narrow = min(a[2] - a[0], b[2] - b[0])
    return -14 <= gap <= 22 and overlap >= .5 * narrow and max(a[2] - a[0], b[2] - b[0]) < .55 * width


def xycut(boxes, region, out):
    """도형을 빈 틈으로 잘라 나간다 (XY-cut). 겹쳐서 못 자르면 읽는 차례로 위아래로 쌓는다."""
    if len(boxes) == 1:
        out.append((region, boxes[0][4]))
        return
    for axis in (0, 1):
        lo, hi = axis, axis + 2
        items = sorted(boxes, key=lambda b: b[lo])
        groups = [[items[0]]]
        edge = items[0][hi]
        for b in items[1:]:
            if b[lo] >= edge - 10:
                groups.append([b])
            else:
                groups[-1].append(b)
            edge = max(edge, b[hi])
        if len(groups) > 1:
            cuts = [region[lo]]
            for a, b in zip(groups, groups[1:]):
                cuts.append((max(x[hi] for x in a) + min(x[lo] for x in b)) / 2)
            cuts.append(region[hi])
            for i, g in enumerate(groups):
                sub = list(region)
                sub[lo], sub[hi] = cuts[i], cuts[i + 1]
                xycut(g, tuple(sub), out)
            return
    items = sorted(boxes, key=lambda b: (b[1], b[0]))
    step = (region[3] - region[1]) / len(items)
    for i, b in enumerate(items):
        out.append(((region[0], region[1] + i * step, region[2], region[1] + (i + 1) * step), b[4]))


def snap(values, gap=26):
    out = []
    for v in values:
        if out and v - out[-1] < gap:
            continue
        out.append(v)
    return out


def nearest(lines, v):
    return min(range(len(lines)), key=lambda i: abs(lines[i] - v))


def fr(v, total):
    return f'{max(1, round(v / total * 20))}fr'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('src')
    ap.add_argument('out')
    ap.add_argument('--level', type=int, default=2)
    ap.add_argument('--ref')
    args = ap.parse_args(argv)
    data = json.loads((Path(args.src) / 'deck.json').read_text(encoding='utf-8'))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    b = Builder(data, args.src, args.out, args.level, args.ref)
    print(json.dumps({'how': b.build()}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
