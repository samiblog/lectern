"""Lectern 슬라이드를 쪽·칸·블록으로 읽는다. 표준 라이브러리만 쓴다.

문법은 앱의 web/help/slides.md 를 따른다. 쪽을 나누는 규칙은 pptx-to-lectern 의 verify.py 와 같아야 한다.
지문(sha1)이 그 나눈 글로 만들어지기 때문이다.
"""
import csv
import hashlib
import json
import re
from pathlib import Path

LAYOUTS = {
    'two': ('t t / a b', '1fr 1fr', 'auto 1fr'),
    'two-left': ('t t / a b', '2fr 1fr', 'auto 1fr'),
    'two-right': ('t t / a b', '1fr 2fr', 'auto 1fr'),
    'three': ('t t t / a b c', '1fr 1fr 1fr', 'auto 1fr'),
    'quad': ('t t / a b / c d', '1fr 1fr', 'auto 1fr 1fr'),
    'left-stack': ('t t / a b / a c', '3fr 2fr', 'auto 1fr 1fr'),
    'right-stack': ('t t / a b / c b', '2fr 3fr', 'auto 1fr 1fr'),
    'kpi': ('t t t t / a b c d / e e e e', '1fr 1fr 1fr 1fr', 'auto auto 1fr'),
    'kpi-two': ('t t t / a b c / d d e', '1fr 1fr 1fr', 'auto auto 1fr'),
    'stack': ('t / a / b', '1fr', 'auto 1fr 1fr'),
}
DIRECTIVES = {'layout', 'grid', 'cols', 'rows', 'text', 'eyebrow', 'links', 'hidden', 'template', 'class', 'paginate', 'header', 'footer',
              'backgroundColor', 'backgroundImage', 'color'}
PER_SLIDE = {'layout', 'grid', 'cols', 'rows', 'text', 'eyebrow', 'links', 'hidden', 'template'}
CHARTS = {'vega-lite', 'echarts', 'plotly'}
DIAGRAMS = {'mermaid', 'dot'}
TEXT_WORDS = {'제목': 'title', '소제목': 'sub', '본문': 'body', '표': 'table', '강조글': 'box', '박스글': 'box', '코드': 'code',
              'title': 'title', 'sub': 'sub', 'body': 'body', 'table': 'table', 'box': 'box', 'code': 'code'}
SIZES = {'title': 30, 'sub': 20, 'body': 18, 'table': 14, 'box': 16, 'code': 14}


def split_front(md):
    """맨 앞 설정을 값과 CSS 로 나눈다."""
    md = md.lstrip('﻿')
    if not md.startswith('---'):
        return {}, '', md
    end = md.find('\n---', 3)
    if end < 0:
        return {}, '', md
    head, body = md[3:end], md[end + 4:]
    fm, css, block = {}, [], False
    for line in head.split('\n'):
        if block:
            if line.startswith((' ', '\t')) or not line.strip():
                css.append(line.strip('\r'))
                continue
            block = False
        m = re.match(r'^([A-Za-z_]+):\s*(.*)$', line.rstrip('\r'))
        if not m:
            continue
        key, value = m[1], m[2].strip()
        if key == 'style' and value in ('|', '|-', '>'):
            block = True
            continue
        fm[key] = clean_value(value)
    return fm, '\n'.join(css), body


def clean_value(value):
    if value in ('true', 'yes', 'on'):
        return True
    if value in ('false', 'no', 'off'):
        return False
    if len(value) >= 2 and value[0] == value[-1] and value[0] in '"\'':
        if value[0] == '"':
            try:
                return json.loads(value)
            except ValueError:
                pass
        return value[1:-1]
    return value


def split_slides(body):
    parts, buf, fence = [], [], None
    for line in body.split('\n'):
        m = re.match(r'^(`{3,}|~{3,})', line)
        if m:
            if fence is None:
                fence = m[1]
            elif line.strip().startswith(fence):
                fence = None
        if fence is None and re.fullmatch(r'---\s*', line) and (not buf or not buf[-1].strip()):
            parts.append('\n'.join(buf))
            buf = []
            continue
        buf.append(line)
    parts.append('\n'.join(buf))
    return parts


def fingerprint(part):
    return hashlib.sha1(part.strip().encode('utf-8')).hexdigest()


# ---- 글 안의 표시

INLINE = re.compile(r'(\\[\\`*_{}\[\]()#+\-.!|>~$])|(\*\*)|(\*)|(`[^`]*`)|(<br\s*/?>)|(</?(?:sub|sup|u)>)|(!?\[(?:[^\]\\]|\\.)*\]\((?:<[^>]*>|[^)\s]*)\))|(&lt;|&gt;|&amp;|&nbsp;)')
ENTITIES = {'&lt;': '<', '&gt;': '>', '&amp;': '&', '&nbsp;': ' '}


def inline(text, base=None):
    """글을 run 목록으로. run 은 {t, b, i, code, u, sub, sup, link}."""
    state = dict(base or {})
    runs = []

    def add(t, **extra):
        if not t:
            return
        run = {'t': t, **{k: v for k, v in state.items() if v}, **extra}
        if runs and {k: v for k, v in runs[-1].items() if k != 't'} == {k: v for k, v in run.items() if k != 't'}:
            runs[-1]['t'] += t
        else:
            runs.append(run)

    pos = 0
    for m in INLINE.finditer(text):
        add(text[pos:m.start()])
        pos = m.end()
        esc, bold, ital, code, br, tag, link, ent = m.groups()
        if esc:
            add(esc[1])
        elif bold:
            state['b'] = not state.get('b')
        elif ital:
            state['i'] = not state.get('i')
        elif code:
            add(code[1:-1], code=True)
        elif br:
            add('\n')
        elif tag:
            name = tag.strip('</>')
            state[name] = not tag.startswith('</')
        elif link:
            lm = re.match(r'!?\[((?:[^\]\\]|\\.)*)\]\((<[^>]*>|[^)\s]*)\)', link)
            for run in inline(lm[1], state):
                run['link'] = lm[2].strip('<>')
                runs.append(run)
        elif ent:
            add(ENTITIES[ent])
    add(text[pos:])
    return runs


def plain(runs):
    return ''.join(r['t'] for r in runs)


# ---- 블록

IMG = re.compile(r'^(?:\[)?!\[([^\]]*)\]\((<[^>]+>|[^)\s]+)\)(?:\]\(([^)]+)\))?\s*$')
LIST = re.compile(r'^(\s*)([-*+]|\d+[.)])\s+(.*)$')


def image_block(m):
    words = m[1].split()
    width = height = None
    alt = []
    for w in words:
        s = re.fullmatch(r'(w|h|width|height):(\d+)(?:px)?', w)
        if s:
            if s[1][0] == 'w':
                width = int(s[2])
            else:
                height = int(s[2])
        else:
            alt.append(w)
    return {'kind': 'image', 'src': m[2].strip('<>'), 'w': width, 'h': height, 'alt': ' '.join(alt), 'link': m[3]}


def read_blocks(lines):
    out = []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        text = line.strip()
        if not text:
            i += 1
            continue
        fence = re.match(r'^(`{3,}|~{3,})\s*(\S*)', text)
        if fence:
            body = []
            i += 1
            while i < n and not lines[i].strip().startswith(fence[1]):
                body.append(lines[i])
                i += 1
            i += 1
            lang = fence[2].lower()
            if lang in CHARTS:
                out.append({'kind': 'chart', 'lang': lang, 'text': '\n'.join(body)})
            elif lang in DIAGRAMS:
                out.append({'kind': 'diagram', 'lang': lang, 'text': '\n'.join(body)})
            else:
                out.append({'kind': 'code', 'lang': lang, 'lines': body})
            continue
        h = re.match(r'^(#{1,6})\s+(.*)$', text)
        if h:
            out.append({'kind': 'heading', 'level': len(h[1]), 'runs': inline(h[2])})
            i += 1
            continue
        if text.startswith('|') and i + 1 < n and re.match(r'^\|?[\s:|-]+\|?$', lines[i + 1].strip()) and '-' in lines[i + 1]:
            rows = []
            aligns = []
            for bit in lines[i + 1].strip().strip('|').split('|'):
                bit = bit.strip()
                aligns.append('center' if bit.startswith(':') and bit.endswith(':') else 'right' if bit.endswith(':') else None)
            while i < n and lines[i].strip().startswith('|'):
                if not re.match(r'^\|?[\s:|-]+\|?$', lines[i].strip()) or not rows:
                    rows.append(table_row(lines[i]))
                i += 1
            out.append({'kind': 'table', 'rows': rows, 'align': aligns})
            continue
        if text.startswith('>'):
            quote = []
            while i < n and lines[i].strip().startswith('>'):
                quote.append(re.sub(r'^\s*>\s?', '', lines[i]))
                i += 1
            kind = None
            if quote and re.match(r'^\[!(\w+)\]', quote[0].strip()):
                kind = re.match(r'^\[!(\w+)\]', quote[0].strip())[1].upper()
                quote[0] = re.sub(r'^\s*\[!\w+\]\s*', '', quote[0])
            out.append({'kind': 'quote', 'alert': kind, 'blocks': read_blocks(quote)})
            continue
        m = IMG.match(text)
        if m:
            out.append(image_block(m))
            i += 1
            continue
        if LIST.match(line):
            items = []
            while i < n:
                lm = LIST.match(lines[i])
                if lm:
                    body = lm[3]
                    check = re.match(r'^\[( |x|X)\]\s+(.*)$', body)
                    prefix = ''
                    if check:
                        prefix = '☑ ' if check[1].lower() == 'x' else '☐ '
                        body = check[2]
                    items.append({'lvl': len(lm[1].expandtabs(2)) // 2, 'ordered': lm[2][0].isdigit(), 'runs': inline(prefix + body)})
                    i += 1
                    continue
                if lines[i].strip() and lines[i].startswith((' ', '\t')) and items:
                    items[-1]['runs'] += [{'t': '\n'}] + inline(lines[i].strip())
                    i += 1
                    continue
                break
            out.append({'kind': 'list', 'items': items})
            continue
        para = []
        while i < n and lines[i].strip() and not LIST.match(lines[i]) and not IMG.match(lines[i].strip()) \
                and not re.match(r'^(#{1,6}\s|`{3,}|~{3,}|>|\|)', lines[i].strip()):
            para.append(lines[i].strip())
            i += 1
        if para:
            runs = []
            for k, row in enumerate(para):
                if k:
                    runs.append({'t': '\n'})
                runs += inline(row)
            out.append({'kind': 'para', 'runs': runs})
        else:
            i += 1      # 어디에도 안 맞는 줄에서 멈추지 않게
    return out


def table_row(line):
    text = line.strip().strip('|')
    cells, buf, esc = [], '', False
    for ch in text:
        if esc:
            buf += ch
            esc = False
        elif ch == '\\':
            buf += ch
            esc = True
        elif ch == '|':
            cells.append(buf.strip())
            buf = ''
        else:
            buf += ch
    cells.append(buf.strip())
    return [inline(c) for c in cells]


# ---- 쪽

def read_head(head):
    """칸 머리: 이름, 낱말, 크기, at."""
    parts = head.split()
    name, rest = parts[0], parts[1:]
    words, size, at = [], None, None
    i = 0
    while i < len(rest):
        w = rest[i]
        if w == 'at' and i + 4 < len(rest) + 0 and all(re.fullmatch(r'-?\d+(\.\d+)?', x) for x in rest[i + 1:i + 5]):
            at = tuple(float(x) for x in rest[i + 1:i + 5])
            i += 5
            continue
        if re.fullmatch(r'\d{1,3}(\.\d)?', w):
            size = float(w)
        else:
            words.append(w)
        i += 1
    return {'name': name, 'words': words, 'size': size, 'at': at}


def text_sizes(*values):
    out = {}
    for value in values:
        for bit in str(value or '').split(','):
            m = re.match(r'^\s*(\S+)\s+(\d{1,3}(?:\.\d)?)\s*$', bit)
            if m and m[1] in TEXT_WORDS:
                out[TEXT_WORDS[m[1]]] = float(m[2])
    return out


def read_slide(text, inherited):
    """쪽 하나. inherited 는 앞 쪽에서 이어지는 지시어이고 고쳐서 돌려준다."""
    local, spot, notes, css = {}, {}, [], []
    title, title_level, backgrounds, title_at = None, 2, [], 0
    body, cells = [], []
    cell = None
    fence = None
    lines = text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        m = re.match(r'^(`{3,}|~{3,})', stripped)
        if m:
            if fence is None:
                fence = m[1]
            elif stripped.startswith(fence):
                fence = None
            (cell['lines'] if cell else body).append(line)
            i += 1
            continue
        if fence:
            (cell['lines'] if cell else body).append(line)
            i += 1
            continue
        if stripped.startswith('<style'):
            block = [stripped]
            while '</style>' not in block[-1] and i + 1 < len(lines):
                i += 1
                block.append(lines[i])
            css.append(re.sub(r'</?style[^>]*>', '', '\n'.join(block)))
            i += 1
            continue
        if stripped.startswith('<!--'):
            block = stripped
            while '-->' not in block and i + 1 < len(lines):
                i += 1
                block += '\n' + lines[i]
            for comment in re.findall(r'<!--(.*?)-->', block, flags=re.S):
                d = re.match(r'^\s*(_?)([A-Za-z]+)\s*:\s*(.*?)\s*$', comment, flags=re.S)
                if d and d[2] in DIRECTIVES:
                    (spot if d[1] else local)[d[2]] = clean_value(d[3].strip())
                elif comment.strip():
                    notes.append(comment.strip())
            i += 1
            continue
        head = re.match(r'^:::\s*(\S.*)$', stripped)
        if head and cell is None:
            cell = {**read_head(head[1]), 'lines': []}
            i += 1
            continue
        if stripped == ':::' and cell is not None:
            cell['blocks'] = read_blocks(cell.pop('lines'))
            cells.append(cell)
            cell = None
            i += 1
            continue
        if cell is not None:
            cell['lines'].append(line)
            i += 1
            continue
        t = re.match(r'^(#{1,2})\s+(.*)$', stripped)
        if t and title is None:
            title, title_level = inline(t[2]), len(t[1])
            title_at = len(body)
            i += 1
            continue
        bg = re.match(r'^!\[bg\b([^\]]*)\]\((<[^>]+>|[^)\s]+)\)\s*$', stripped)
        if bg:
            backgrounds.append({'src': bg[2].strip('<>'), 'words': bg[1].split()})
            i += 1
            continue
        body.append(line)
        i += 1
    if cell is not None:
        cell['blocks'] = read_blocks(cell.pop('lines'))
        cells.append(cell)
    inherited.update(local)
    eff = {**inherited, **spot}
    for key in PER_SLIDE:
        inherited.pop(key, None)
    classes = str(eff.get('class') or '').split()
    return {'title': title, 'title_level': title_level, 'cells': cells, 'body': read_blocks(body), 'before_title': len(read_blocks(body[:title_at])), 'notes': '\n\n'.join(notes),
            'backgrounds': backgrounds, 'eff': eff, 'classes': classes, 'css': '\n'.join(css), 'text': text}


def read_deck(path):
    path = Path(path)
    md = path.read_text(encoding='utf-8')
    fm, css, body = split_front(md)
    if fm.get('marp') is not True:
        raise ValueError('맨 앞 설정에 marp: true 가 없습니다. Lectern 슬라이드가 아닙니다')
    parts = split_slides(body)
    inherited = {k: fm[k] for k in DIRECTIVES if k in fm and k not in PER_SLIDE}
    slides = [read_slide(p, inherited) for p in parts]
    wide = str(fm.get('size', '16:9')).strip() != '4:3'
    return {'fm': fm, 'css': css, 'slides': slides, 'parts': parts, 'w': 1280 if wide else 960, 'h': 720, 'dir': path.parent,
            'sizes': {**SIZES, **text_sizes(fm.get('text'))}}


def read_table_file(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))
