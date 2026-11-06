"""글만 고친 쪽은 다시 만들지 않고 원본 쪽의 글을 그 자리에서 바꾼다.

쪽을 다시 만들면 원본의 도형, 서식, 애니메이션을 잃는다. 문서의 옛 글과 새 글을 줄마다 견주어
바뀐 글자만 원본 XML 의 run 안에서 고친다. 칸·배치·그림·차트가 바뀌었거나 옛 글을 원본에서 찾지 못하면
None 을 주고 부른 쪽이 다시 만든다.
"""
import re
from xml.sax.saxutils import unescape

import lectern_md as lm
from pptx_parts import esc

HEADING = re.compile(r'^\s*#{1,6}\s+')
LIST = re.compile(r'^\s*(?:[-*+]|\d+[.)])\s+')
TEXT_TAG = re.compile(r'<a:t>([^<]*)</a:t>')
BREAK = '\x00'


def plain_line(line):
    return lm.plain(lm.inline(line)).replace('\n', ' ').strip()


def cells_of(line):
    return [lm.plain(c).strip() for c in lm.table_row(line)]


def text_changes(old, new):
    """[(옛 글, 새 글, 노트 줄인가)]. 글이 아닌 것이 바뀌었으면 None."""
    a, b = old.strip().split('\n'), new.strip().split('\n')
    if len(a) != len(b):
        return None
    out = []
    fence = None
    comment = False
    for x, y in zip(a, b):
        s = x.strip()
        if fence is None and comment is False and s.startswith('<!--') and '-->' not in s:
            comment = True
            if x != y:
                return None
            continue
        if comment:
            if s.endswith('-->') or s == '-->':
                comment = False
                if x != y:
                    return None
                continue
            if x != y:
                out.append((LIST.sub('', x).strip(), LIST.sub('', y).strip(), True))
            continue
        m = re.match(r'^(`{3,}|~{3,})\s*(\S*)', s)
        if m:
            if x != y:
                return None
            if fence is None:
                fence = (m[1], m[2].lower())
            elif s.startswith(fence[0]):
                fence = None
            continue
        if fence:
            if x != y:
                if fence[1] in lm.CHARTS or fence[1] in lm.DIAGRAMS:
                    return None
                out.append((x.rstrip(), y.rstrip(), False))
            continue
        if x == y:
            continue
        structural = ('<!--', ':::', '![', '[![', '<style', '</style', '---')
        if s.startswith(structural) or y.strip().startswith(structural):
            return None
        if s.startswith('|'):
            p, q = cells_of(x), cells_of(y)
            if len(p) != len(q) or re.match(r'^\|?[\s:|-]+\|?$', s):
                return None
            out += [(c, d, False) for c, d in zip(p, q) if c != d]
            continue
        for pattern in (HEADING, LIST):
            if bool(pattern.match(x)) != bool(pattern.match(y)):
                return None
        out.append((plain_line(HEADING.sub('', LIST.sub('', x))), plain_line(HEADING.sub('', LIST.sub('', y))), False))
    return out


def squeeze(text):
    """공백을 하나로 줄이고 원래 자리를 함께 준다."""
    out, where, gap = [], [], False
    for i, ch in enumerate(text):
        if ch == BREAK or ch.isspace() or ch == '\xa0':
            if out and not gap:
                out.append(' ')
                where.append(i)
            gap = True
        else:
            out.append(ch)
            where.append(i)
            gap = False
    return ''.join(out), where


def patch_paragraph(xml, old, new):
    """문단 하나에서 old 를 찾아 바꾼다. 못 찾으면 None."""
    pieces = []        # (시작, 끝, 글)
    stream = ''
    owner = []         # 글자마다 (조각 번호, 조각 안 자리)
    for m in re.finditer(r'<a:br\b[^>]*?(?:/>|>.*?</a:br>)|<a:t>([^<]*)</a:t>', xml, flags=re.S):
        if m[1] is None:
            stream += BREAK
            owner.append((None, 0))
            continue
        text = unescape(m[1], {'&quot;': '"', '&apos;': "'"})
        n = len(pieces)
        pieces.append([m.start(1), m.end(1), text])
        for k in range(len(text)):
            owner.append((n, k))
        stream += text
    flat, where = squeeze(stream)
    target = ' '.join(old.split())
    at = flat.find(target)
    if at < 0 or not target:
        return None
    goal = ' '.join(new.split())
    p = 0
    while p < min(len(target), len(goal)) and target[p] == goal[p]:
        p += 1
    q = 0
    while q < min(len(target), len(goal)) - p and target[-1 - q] == goal[-1 - q]:
        q += 1
    insert = goal[p:len(goal) - q]
    a = at + p
    b = at + len(target) - q
    # 지울 글자
    gone = set()
    for i in range(a, b):
        start = where[i]
        stop = where[i + 1] if i + 1 < len(where) else len(stream)
        gone.update(range(start, stop))
    drops = {}
    for i in sorted(gone):
        n, k = owner[i]
        if n is not None:
            drops.setdefault(n, set()).add(k)
    # 넣을 자리: 바꾸는 첫 글자의 조각, 끝에 더하면 앞 글자의 조각
    if a < b:
        n, k = owner[where[a]]
        if n is None:
            n, k = next(((x, y) for x, y in owner[where[a]:] if x is not None), (len(pieces) - 1, len(pieces[-1][2])))
    else:
        i = where[a - 1] if a else 0
        n, k = owner[i]
        k = k + 1 if a else 0
        if n is None:
            n, k = next(((x, y + 1) for x, y in reversed(owner[:i]) if x is not None), (0, 0))
    texts = []
    for i, (_, _, text) in enumerate(pieces):
        cut = drops.get(i, set())
        kept = [c for j, c in enumerate(text) if j not in cut] if cut else list(text)
        if i == n:
            shift = sum(1 for j in cut if j < k)
            kept[k - shift:k - shift] = list(insert)
        texts.append(''.join(kept))
    out = xml
    for (start, end, _), text in zip(reversed(pieces), reversed(texts)):
        out = out[:start] + esc(text) + out[end:]
    return out


def apply_one(xml, old, new):
    for m in re.finditer(r'<a:p>.*?</a:p>|<a:p\s[^>]*>.*?</a:p>', xml, flags=re.S):
        got = patch_paragraph(m[0], old, new)
        if got is not None:
            return xml[:m.start()] + got + xml[m.end():]
    return None


def apply_changes(slide_xml, notes_xml, changes):
    """바꾼 (쪽, 노트) 를 준다. 하나라도 못 찾으면 None."""
    for old, new, note in changes:
        got = None if note else apply_one(slide_xml, old, new)
        if got is not None:
            slide_xml = got
            continue
        if note:
            got = apply_one(slide_xml, old, new)     # '그림 속 글' 은 노트에 있지만 원본에서는 쪽의 글이다
            if got is not None:
                slide_xml = got
                continue
        got = apply_one(notes_xml, old, new) if notes_xml else None
        if got is None:
            return None
        notes_xml = got
    return slide_xml, notes_xml
