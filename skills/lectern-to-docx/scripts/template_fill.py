"""Word 양식의 자리 표시를 채운다 (D147) — 지면 틀(html)의 {{…}} 와 같은 생각.

양식(.dotx)의 본문·머리글·바닥글 글 속에 쓰는 자리:

    {{title}} {{subtitle}} {{author}} {{org}} …   맨 앞 설정의 값 (한국어 키도 — 기관·작성자·부제 …)
    {{a|b|'글'}}                                  a 가 비면 b, 그것도 비면 '글'
    {{date:ko}} {{date:dot}} {{date:en}}          2026년 11월 15일 · 2026. 11. 15. · November 15, 2026
    {{date:long}}                                 문서 언어(lang)에 맞춰 date:ko 나 date:en
    {{t:한국어|English}}                           문서 언어에 맞는 이름표 (요약·차례·회의록 …)
    {{if:키}} …                                   문단 맨 앞에 — 키가 비면 그 문단을 뺀다. 행의 첫 칸 첫 문단이면 그 행(행이 다 빠지면 표)을
    {{body}}                                      문단 하나 — 본문이 들어간다
    {{toc}}                                       문단 하나 — Word 목차 필드
    {{slot:요약}}                                  문단 하나 — 이름 있는 박스글(<!-- box: 요약 -->)의 글. 없으면 {{if:}} 처럼 뺀다
    {{signoff:결재}}                               문단 하나 — 맨 앞 설정의 목록(결재: [담당, 팀장])으로 결재란 표

자리 하나는 run 하나 안에 둔다 (Lectern 이 만든 양식은 그렇다). Word 로 고친 양식에서 자리가 run 사이로 쪼개지면 그 문단의 글을
첫 run 으로 모아 채운다 (그 문단의 서식이 하나로 된다).
"""
from __future__ import annotations

import datetime
import re
from xml.dom import minidom

PH = re.compile(r'\{\{\s*([^{}]+?)\}\}')   # 끝 빈칸은 남긴다 — {{t:|To }} 의 'To ' (값의 이름은 value() 가 다듬는다)
WHOLE = re.compile(r'^\{\{\s*(body|toc|slot:[^{}]+?|signoff:[^{}]+?)\s*\}\}$')
IF = re.compile(r'^\s*\{\{\s*if:\s*([^{}]+?)\s*\}\}')
MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
NS_NEEDED = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'pic': 'http://schemas.openxmlformats.org/drawingml/2006/picture',
}


def plain_text(xml):
    """XML 의 글만 (자리 찾기용)"""
    return re.sub(r'<[^>]+>', '', xml)


def slots_in(xml_parts):
    """양식이 쓰는 박스글 자리 이름들"""
    names = []
    for xml in xml_parts:
        for m in re.finditer(r'\{\{\s*slot:\s*([^{}]+?)\s*\}\}', plain_text(xml)):
            if m[1] not in names:
                names.append(m[1])
    return names


def uses(xml_parts, word):
    return any(re.search(r'\{\{\s*' + word, plain_text(x)) for x in xml_parts)


def fmt_date(value, how):
    m = re.match(r'^\s*(\d{4})[-./ ]\s*(\d{1,2})[-./ ]\s*(\d{1,2})', value or '')
    if not m:
        return value
    y, mo, d = int(m[1]), int(m[2]), int(m[3])
    if how == 'ko':
        return f'{y}년 {mo}월 {d}일'
    if how == 'dot':
        return f'{y}. {mo}. {d}.'
    if how == 'en':
        return f'{MONTHS[mo - 1]} {d}, {y}' if 1 <= mo <= 12 else value
    return value


class Filler:
    """vals: 키 → 글 (맨 앞 설정을 고른 것), render: 'body'·'toc'·'slot:이름'·'signoff:키' → XML 조각 (없으면 None)"""

    def __init__(self, vals, render, lang='ko'):
        self.vals = vals
        self.render = render
        self.lang = lang
        self.frags: list[str] = []

    def value(self, expr):
        """a|b|'글' — 차례로 첫 값. date:ko·date:dot·date:en·date:long 은 맨 앞 설정의 날짜(없으면 오늘)를 그 꼴로.
        t:한국어|English 는 문서 언어에 맞는 쪽 (대체 값의 끝에도 — series|t:이슈 브리프|Issue brief). 한쪽이 비어도 그 쪽"""
        raw = expr.split('|')
        alts = [a.strip() for a in raw]
        for k, alt in enumerate(alts):
            if alt.startswith('t:'):   # 이름표는 빈칸까지 그대로 ('{{t:|To }}' — 'To 고객')
                ko, en = raw[k].lstrip()[2:], ('|'.join(raw[k + 1:]) if k + 1 < len(raw) else None)
                return en if self.lang == 'en' and en is not None else ko
            if len(alt) >= 2 and alt[0] == alt[-1] and alt[0] in '\'"':
                return alt[1:-1]
            how = alt[5:].strip()
            if how == 'long':
                how = 'en' if self.lang == 'en' else 'ko'
            v = fmt_date(self.vals.get('date', ''), how) if alt.startswith('date:') else self.vals.get(alt, '')
            if v:
                return v
        return ''

    def truthy(self, expr):
        expr = expr.strip()
        if expr.startswith('slot:'):
            return self.render(expr) is not None
        return bool(self.value(expr))

    # ---- XML
    def fill(self, xml):
        """양식 부분(document·header·footer) 하나를 채운 XML. 큰 조각(본문·표)은 표시 문단으로 두었다가 글자로 바꿔 넣는다"""
        if '{{' not in plain_text(xml):
            return xml
        doc = minidom.parseString(xml.encode('utf-8'))
        root = doc.documentElement
        for prefix, uri in NS_NEEDED.items():   # 넣을 조각이 쓰는 이름표 — Word 가 만든 양식은 a·pic 을 뿌리에 두지 않는다
            if not root.hasAttribute(f'xmlns:{prefix}'):
                root.setAttribute(f'xmlns:{prefix}', uri)
        for p in list(doc.getElementsByTagName('w:p')):
            if not attached(p):
                continue
            ts = own_texts(p)
            text = ''.join(t.data for t in ts)
            if '{{' not in text:
                continue
            m = IF.match(text)
            if m:
                if not self.truthy(m[1]):
                    remove_scope(p)
                    continue
                strip_prefix(ts, m.group(0))
                ts = own_texts(p)
                text = ''.join(t.data for t in ts)
            whole = WHOLE.match(text.strip())
            if whole:
                frag = self.render(whole[1].strip())
                if frag is None:
                    remove_scope(p)
                    continue
                self.frags.append(frag)
                mark = doc.createElement('w:p')
                r = doc.createElement('w:r')
                t = doc.createElement('w:t')
                t.appendChild(doc.createTextNode(f'@@LECFRAG{len(self.frags) - 1}@@'))
                r.appendChild(t)
                mark.appendChild(r)
                p.parentNode.replaceChild(mark, p)
                continue
            only_marks = not PH.sub('', text).strip()
            if all(t.data.count('{{') == t.data.count('}}') for t in ts):
                for t in ts:
                    if '{{' in t.data:
                        set_text(t, PH.sub(lambda mm: self.value(mm[1]), t.data))
            else:   # 자리가 run 사이로 쪼개졌다 — 글을 첫 run 에 모은다
                new = PH.sub(lambda mm: self.value(mm[1]), text)
                set_text(ts[0], new)
                for t in ts[1:]:
                    set_text(t, '')
            if only_marks and not ''.join(t.data for t in own_texts(p)).strip() and removable(p):
                remove_scope(p, row=False)
        out = doc.toxml()
        out = re.sub(r'^<\?xml[^>]*\?>', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n', out)

        def put(m):
            return self.frags[int(m[1])]
        return re.sub(r'<w:p><w:r><w:t>@@LECFRAG(\d+)@@</w:t></w:r></w:p>', put, out)


def attached(node):
    while node is not None:
        if node.nodeType == node.DOCUMENT_NODE:
            return True
        node = node.parentNode
    return False


def own_texts(p):
    """그 문단에 속한 글 노드 (글 상자 속 문단의 글은 뺀다)"""
    out = []
    for t in p.getElementsByTagName('w:t'):
        a = t.parentNode
        while a is not None and a.nodeName != 'w:p':
            a = a.parentNode
        if a is p:
            if t.firstChild is None:
                t.appendChild(p.ownerDocument.createTextNode(''))
            out.append(t.firstChild)
    return out


def set_text(node, text):
    node.data = text
    t = node.parentNode
    if text != text.strip() or '  ' in text:
        t.setAttribute('xml:space', 'preserve')


def strip_prefix(ts, marker):
    """문단 글에서 marker 를 지운다 — 여러 글 노드에 걸쳐 있어도"""
    lens = [len(t.data) for t in ts]
    text = ''.join(t.data for t in ts)
    start = text.find(marker)
    if start < 0:
        return
    end = start + len(marker)
    pos = 0
    for t, n in zip(ts, lens):
        a, b = pos, pos + n
        if b > start and a < end:
            s0, e0 = max(start, a) - a, min(end, b) - a
            set_text(t, t.data[:s0] + t.data[e0:])
        pos = b


def removable(p):
    """비었으면 지워도 되는 문단 — 구역 나눔·그림·필드를 품지 않고, 표 칸의 마지막 문단이 아닌 것"""
    if p.getElementsByTagName('w:sectPr') or p.getElementsByTagName('w:drawing') or p.getElementsByTagName('w:fldChar') or p.getElementsByTagName('w:fldSimple'):
        return False
    parent = p.parentNode
    if parent is not None and parent.nodeName == 'w:tc':
        return len([c for c in parent.childNodes if c.nodeName in ('w:p', 'w:tbl')]) > 1
    return True


def leads_row(p):
    """표 행의 첫 칸 첫 문단인가 — 그 자리의 {{if:}} 는 행을 통째로 뺀다 (회의 정보 표의 한 줄, 상자의 이름 줄)"""
    tc = p.parentNode
    if tc is None or tc.nodeName != 'w:tc':
        return False
    first_block = next((c for c in tc.childNodes if c.nodeName in ('w:p', 'w:tbl')), None)
    first_cell = next((c for c in tc.parentNode.childNodes if c.nodeName == 'w:tc'), None)
    return first_block is p and first_cell is tc


def remove_scope(p, row=True):
    """{{if:}} 가 거짓이거나 자리가 비었을 때: 행의 첫 칸 첫 문단이면 그 행(행이 다 빠지면 표), 아니면 그 문단 (칸의 마지막 문단이면 글만).
    구역 나눔을 품은 문단은 글만 지운다"""
    if p.getElementsByTagName('w:sectPr'):
        for r in [c for c in p.childNodes if c.nodeName != 'w:pPr']:
            p.removeChild(r)
        return
    node = p.parentNode
    if row and node is not None and node.nodeName == 'w:tc' and leads_row(p):
        tr = node.parentNode
        tbl = tr.parentNode
        tbl.removeChild(tr)
        if not [c for c in tbl.childNodes if c.nodeName == 'w:tr']:
            holder = tbl.parentNode
            holder.removeChild(tbl)
            if holder.nodeName == 'w:tc' and not [c for c in holder.childNodes if c.nodeName in ('w:p', 'w:tbl')]:
                holder.appendChild(p.ownerDocument.createElement('w:p'))
        return
    if node is not None and node.nodeName == 'w:tc' and not removable(p):
        for r in [c for c in p.childNodes if c.nodeName != 'w:pPr']:
            p.removeChild(r)
        return
    if node is not None:
        node.removeChild(p)


def today():
    return datetime.date.today().isoformat()
