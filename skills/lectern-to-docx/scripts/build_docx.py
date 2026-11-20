#!/usr/bin/env python3
"""Lectern 의 md 문서를 Word(docx)로 만든다 (D146). 표준 라이브러리만 쓴다 — Pillow 가 있으면 그림의 빈 여백을 자른다.

    build_docx.py 문서.md --out 문서.docx [--template 양식.dotx] [--lang ko|en]

- 양식(--template, .dotx·.docx)이 있으면 그 꾸러미를 바탕으로 본문(word/document.xml)만 새로 쓴다 — 스타일·번호 매기기·머리글·바닥글·
  쪽 크기·여백·글꼴은 양식의 것. 필요한 스타일이 양식에 없으면 Lectern 의 기본 정의를 더한다. 스타일은 이름으로 찾는다
  (Word 의 기본 스타일은 언어와 상관없이 파일 안에 'heading 1' 같은 영어 이름이다). 양식 옆의 '이름.styles.json' 이 이름을 바꿔 준다.
- 양식이 없으면 Lectern 의 기본 보고서 양식 (PDF 의 보고서 양식과 같은 모양 — A4, 명조 본문, 2쪽부터 머리에 제목, 바닥 가운데 쪽 번호).
- 쪽은 Word 가 나눈다. 넘어갈 때의 규칙만 심는다: 절 제목·캡션은 다음 단락과 함께(문서 제목·부제는 첫 쪽 맨 위라 걸지 않는다), 표의 머리행은 쪽마다, 행은 쪽에서 나누지 않음,
  외톨이 줄 막기, 쪽 나눔 줄은 쪽 나누기.
- 차트·Mermaid·Graphviz·블록 수식은 figure_png(Edge — Lectern 에 든 라이브러리)로 그린 PNG. 그리지 못하면 원문을 코드로 넣고 알린다.
- 결과 보고(마지막 줄): {"docx": 경로, "figures": 그림 수, "notes": [알릴 것]}
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import struct
import sys
import tempfile
import unicodedata
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import figure_png  # noqa: E402
import lectern_md as LM  # noqa: E402
import template_fill as TF  # noqa: E402

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
RELS = 'http://schemas.openxmlformats.org/package/2006/relationships'
REL = {k: f'{R}/{v}' for k, v in {
    'styles': 'styles', 'numbering': 'numbering', 'footnotes': 'footnotes', 'settings': 'settings', 'image': 'image', 'link': 'hyperlink',
    'header': 'header', 'footer': 'footer', 'font': 'fontTable', 'theme': 'theme', 'doc': 'officeDocument', 'core': 'metadata/core-properties',
}.items()}
REL['core'] = 'http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties'
CT = 'application/vnd.openxmlformats-officedocument.wordprocessingml'
NS = (f'xmlns:w="{W}" xmlns:r="{R}" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
      'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"')

A4 = (11906, 16838)                          # 쪽 크기 (twip — 1/20 pt)
MARGINS = (1417, 1247, 1247, 1247)           # 위·오른쪽·아래·왼쪽 = 25·22·22·22mm (PDF 의 보고서 양식과 같다)
EMU = 635                                     # twip 하나의 EMU
MARK_FILL = {'yellow': 'FFF1A6', 'green': 'CDEFD0', 'pink': 'FAD1E2', 'blue': 'CFE5FA'}
TEXT_COLOR = {'red': 'C62828', 'blue': '1565C0', 'green': '2E7D32', 'goldenrod': 'B8860B'}
ALERT = {'NOTE': '2F6FB3', 'TIP': '2E7D4F', 'IMPORTANT': '7149B8', 'WARNING': '9B6304', 'CAUTION': 'C0392B'}
# 표·그림 아래의 주·자료 줄 — Lectern 화면(web/js/toc.js 의 SOURCE)과 같게: '자료:' '출처:' '주:' '※ 자료:' 'Source:' 'Data source:' …
SOURCE = re.compile(r'^[\s※*·•\-]*[(\[]?\s*(?:자료|출처|원자료|원문|주|source|sources|data source|note)\s*[)\]]?\s*[:：]', re.I)
CAPTION = re.compile(r'^\s*(?:\*\*)?[〈<]?(표|그림|박스|Table|Figure|Box)[ \t]*(\d{1,4})(?:\.(?!\d)|:|[〉>]|\*\*)\s*(?:\*\*)?\s*')
CAP_KEY = {'표': 'tbl', 'table': 'tbl', '그림': 'fig', 'figure': 'fig', '박스': 'box', 'box': 'box'}
BOX_OPEN = re.compile(r'^ {0,3}<!--[ \t]*box(?:[ \t]*:[ \t]*([^\n]*?))?[ \t]*-->[ \t]*$', re.I)
BOX_CLOSE = re.compile(r'^ {0,3}<!--[ \t]*/box[ \t]*-->[ \t]*$', re.I)
PAGE_BREAK = re.compile(r'^<div\s+style\s*=\s*["\']\s*(?:page-break-after\s*:\s*always|break-after\s*:\s*page)\s*;?\s*["\']\s*>\s*</div>\s*$', re.I)
TOC_LINE = re.compile(r'^\[(목차|toc|표 목차|list of tables|그림 목차|list of figures)\]$', re.I)
FOOTREF = re.compile(r'\[\^([^\]\s]+)\]')
MATH_INLINE = re.compile(r'(?<![\\$\w])\$(?=\S)([^$\n]+?)(?<=\S)\$(?!\d)')
MATH_PAREN = re.compile(r'\\\((.+?)\\\)')
SENT = '\ue000'   # 각주·수식 자리를 run 글 안에 잠시 두는 표시

# ---- 문장 속 수식 → 글 (Word 수식으로 바꾸지 않는다 — 그리스 문자·기호·위첨자·아래첨자의 글) ------------------------------

TEX_SYM = {
    **{g: chr(c) for g, c in zip('alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma tau upsilon phi chi psi omega'.split(),
                                  range(0x3B1, 0x3CA)) if g != 'omicron'},
    'varepsilon': 'ε', 'epsilon': 'ϵ', 'varphi': 'φ', 'phi': 'ϕ', 'vartheta': 'ϑ', 'varsigma': 'ς', 'varrho': 'ϱ', 'varpi': 'ϖ',
    'Gamma': 'Γ', 'Delta': 'Δ', 'Theta': 'Θ', 'Lambda': 'Λ', 'Xi': 'Ξ', 'Pi': 'Π', 'Sigma': 'Σ', 'Upsilon': 'Υ', 'Phi': 'Φ', 'Psi': 'Ψ', 'Omega': 'Ω',
    'times': '×', 'cdot': '·', 'div': '÷', 'pm': '±', 'mp': '∓', 'le': '≤', 'leq': '≤', 'ge': '≥', 'geq': '≥', 'ne': '≠', 'neq': '≠', 'approx': '≈',
    'sim': '∼', 'simeq': '≃', 'equiv': '≡', 'propto': '∝', 'infty': '∞', 'sum': '∑', 'prod': '∏', 'int': '∫', 'partial': '∂', 'nabla': '∇',
    'to': '→', 'rightarrow': '→', 'leftarrow': '←', 'Rightarrow': '⇒', 'Leftarrow': '⇐', 'leftrightarrow': '↔', 'Leftrightarrow': '⇔', 'mapsto': '↦',
    'in': '∈', 'notin': '∉', 'subset': '⊂', 'subseteq': '⊆', 'cup': '∪', 'cap': '∩', 'forall': '∀', 'exists': '∃', 'emptyset': '∅',
    'ldots': '…', 'cdots': '⋯', 'dots': '…', 'prime': '′', 'circ': '∘', 'degree': '°', 'ell': 'ℓ', 'hbar': 'ℏ', 'neg': '¬', 'land': '∧', 'lor': '∨',
    'langle': '⟨', 'rangle': '⟩', 'lfloor': '⌊', 'rfloor': '⌋', 'lceil': '⌈', 'rceil': '⌉', 'mid': '|', 'vert': '|', 'Vert': '‖', 'cdotp': '·',
    'quad': ' ', 'qquad': '  ', ',': ' ', ';': ' ', ':': ' ', '!': '', ' ': ' ', '%': '%', '$': '$', '{': '{', '}': '}', '&': '&', '#': '#', '_': '_', '\\': ' ',
}
TEX_FUNC = {'ln', 'log', 'exp', 'sin', 'cos', 'tan', 'max', 'min', 'lim', 'det', 'arg', 'sup', 'inf', 'Pr', 'gcd', 'mod', 'sinh', 'cosh', 'tanh', 'arctan'}
TEX_ACCENT = {'bar': '\u0304', 'overline': '\u0305', 'hat': '\u0302', 'widehat': '\u0302', 'tilde': '\u0303', 'widetilde': '\u0303', 'dot': '\u0307',
              'ddot': '\u0308', 'vec': '\u20d7'}
TEX_REL = {'le', 'leq', 'ge', 'geq', 'ne', 'neq', 'approx', 'sim', 'simeq', 'equiv', 'propto', 'to', 'rightarrow', 'leftarrow', 'Rightarrow',
           'Leftarrow', 'leftrightarrow', 'Leftrightarrow', 'mapsto', 'in', 'notin', 'subset', 'subseteq', 'times', 'pm', 'mp', 'div'}
TEX_SKIP = {'left', 'right', 'big', 'Big', 'bigg', 'Bigg', 'bigl', 'bigr', 'Bigl', 'Bigr', 'displaystyle', 'textstyle', 'limits', 'nolimits'}


def tex_runs(tex, flags=None):
    """문장 속 수식 → run 목록 ({t, math, i, sub, sup, b}). 낱글자는 기울임, 함수 이름·숫자·기호는 바로"""
    flags = dict(flags or {})
    small = bool(flags.get('sub') or flags.get('sup'))   # 아래·위첨자 안 — 연산자를 띄우지 않는다
    out = []
    pos = [0]

    def emit(t, **extra):
        if not t:
            return
        run = {'math': True, **flags, **extra}
        if out and {k: v for k, v in out[-1].items() if k != 't'} == run:
            out[-1]['t'] += t
        else:
            out.append({**run, 't': t})

    def group():
        while pos[0] < len(tex) and tex[pos[0]] == ' ':
            pos[0] += 1
        if pos[0] >= len(tex):
            return ''
        if tex[pos[0]] == '{':
            depth, start = 0, pos[0]
            while pos[0] < len(tex):
                c = tex[pos[0]]
                if c == '\\':
                    pos[0] += 2
                    continue
                depth += c == '{'
                depth -= c == '}'
                pos[0] += 1
                if depth == 0:
                    return tex[start + 1:pos[0] - 1]
            return tex[start + 1:]
        m = re.match(r'\\[A-Za-z]+|\\.|.', tex[pos[0]:])
        pos[0] += len(m[0])
        return m[0]

    def sub(t, **extra):
        for r in tex_runs(t, {**flags, **extra}):
            emit(r['t'], **{k: v for k, v in r.items() if k not in ('t', 'math') and k not in flags})

    while pos[0] < len(tex):
        c = tex[pos[0]]
        if c == '\\':
            m = re.match(r'\\([A-Za-z]+|.)', tex[pos[0]:])
            name = m[1]
            pos[0] += len(m[0])
            if name in ('frac', 'dfrac', 'tfrac'):
                a, b = group(), group()
                wrap = [len(re.sub(r'[{}\s]', '', re.sub(r'\\[A-Za-z]+', 'x', re.sub(r'[_^](?:\{[^{}]*\}|\\[A-Za-z]+|.)', '', v)))) > 1 for v in (a, b)]
                emit('(') if wrap[0] else None
                sub(a)
                emit(')') if wrap[0] else None
                emit('/')
                emit('(') if wrap[1] else None
                sub(b)
                emit(')') if wrap[1] else None
            elif name == 'sqrt':
                emit('√(')
                sub(group())
                emit(')')
            elif name in ('text', 'mathrm', 'operatorname', 'textrm', 'mbox', 'textup', 'mathsf'):
                emit(group())
            elif name in ('mathbf', 'boldsymbol', 'bm', 'textbf'):
                sub(group(), b=True)
            elif name in ('mathit', 'textit'):
                sub(group(), i=True)
            elif name in TEX_ACCENT:
                inner = tex_runs(group(), flags)
                for r in inner:
                    emit(r['t'], **{k: v for k, v in r.items() if k not in ('t', 'math') and k not in flags})
                if out:
                    out[-1]['t'] += TEX_ACCENT[name]
            elif name in TEX_SKIP:
                if name in ('left', 'right') and pos[0] < len(tex) and tex[pos[0]] == '.':
                    pos[0] += 1
            elif name in TEX_REL:
                emit(TEX_SYM[name] if small else f' {TEX_SYM[name]} ')
            elif name in TEX_SYM:
                emit(TEX_SYM[name])
            elif name in TEX_FUNC:
                emit(name)
            else:
                emit(name)
        elif c in '^_':
            pos[0] += 1
            sub(group(), **({'sup': True} if c == '^' else {'sub': True}))
        elif c == '{':
            sub(group())
        elif c == '}' or c == ' ':
            pos[0] += 1
        elif c.isalpha() and c.isascii():
            emit(c, i=True)
            pos[0] += 1
        elif c in '=<>':
            emit(c if small else f' {c} ')
            pos[0] += 1
        elif c in '+-':   # 앞에 값이 있으면 이항 연산 — 띄운다 (아래·위첨자 안은 붙인다: t−1)
            sign = '−' if c == '-' else '+'
            last = out[-1]['t'].rstrip() if out else ''
            emit(f' {sign} ' if not small and last and last[-1] not in '(=<>+−×·/[{,' + ''.join(TEX_SYM[r] for r in TEX_REL) else sign)
            pos[0] += 1
        elif c == '~':
            emit(' ')
            pos[0] += 1
        else:
            emit(c)
            pos[0] += 1
    return out


def protect_math(line, store):
    """문장 속 수식($…$·\\(…\\))을 표시로 바꿔 둔다 — 마크다운 읽기가 \\·_·* 를 건드리지 않게. 코드 조각 안은 그대로"""
    def mark(m):
        store.append(m[1])
        return f'{SENT}m:{len(store) - 1}{SENT}'
    parts = re.split(r'(`+[^`]*`+)', line)
    for k in range(0, len(parts), 2):
        parts[k] = MATH_INLINE.sub(mark, MATH_PAREN.sub(mark, parts[k]))
    return ''.join(parts)

# ---- Lectern 의 기본 스타일 (양식에 없을 때 더한다) -------------------------------------------------------------------

FONTS_KO = {'body': '함초롬바탕', 'head': '맑은 고딕', 'mono': 'Consolas'}
FONTS_EN = {'body': 'Cambria', 'head': 'Calibri', 'mono': 'Consolas'}


def _font(name, east=None):
    east = east or name
    return f'<w:rFonts w:ascii="{name}" w:hAnsi="{name}" w:eastAsia="{east}" w:cs="{name}"/>'


THEME = {   # 기본 보고서 양식의 모양 — 양식(tools/make_docx_templates.py)이 이 중 몇을 바꾼다
    'body_font': None, 'body_east': None, 'head_font': None, 'head_east': '맑은 고딕', 'mono_east': 'D2Coding',
    'body_size': 21, 'line': 264, 'after': 120, 'jc': 'both', 'indent': 0,
    'head_color': '1B2A3A', 'head_sizes': {1: 30, 2: 26, 3: 23, 4: 22, 5: 21, 6: 21}, 'h1_page': False, 'h1_rule': None, 'h_center': False,
    'title_size': 40, 'title_color': '111111', 'title_jc': 'center', 'subtitle_size': 24, 'subtitle_color': '444444', 'subtitle_jc': 'center',
    'caption_color': '1B2A3A', 'caption_jc': 'center', 'caption_size': None, 'quote_rule': '999999',   # 캡션은 가운데, 본문보다 1pt 크게 (2026-11-20 — Lectern 화면과 같게)
    'th_fill': 'E9EDF2', 'th_color': '111111', 'rule': '333333', 'inner': 'BBBBBB', 'cell_size': 18,
    'header_color': '666666', 'footer_color': '333333', 'link': '1F5F9F',
}


def default_styles(lang, theme=None):
    th = {**THEME, **(theme or {})}
    f = FONTS_EN if lang == 'en' else FONTS_KO
    body = _font(th['body_font'] or (f['body'] if lang == 'en' else 'Times New Roman'), th['body_east'] or f['body'])
    head = _font(th['head_font'] or f['head'], th['head_east'])
    mono = _font(f['mono'], th['mono_east'])
    cap_size = th['caption_size'] or th['body_size'] + 2   # 본문보다 1pt 크게 — 반 포인트 단위

    def para(sid, name, ppr='', rpr='', based='Normal', nxt='Normal', extra=''):
        return (f'<w:style w:type="paragraph" w:styleId="{sid}"><w:name w:val="{name}"/>'
                + (f'<w:basedOn w:val="{based}"/>' if based else '') + (f'<w:next w:val="{nxt}"/>' if nxt else '')
                + f'<w:qFormat/>{extra}<w:pPr>{ppr}</w:pPr><w:rPr>{rpr}</w:rPr></w:style>')

    heads = []
    for n in range(1, 7):
        size = th['head_sizes'][n]
        page = '<w:pageBreakBefore/>' if n == 1 and th['h1_page'] else ''
        rule = f'<w:pBdr><w:bottom w:val="single" w:sz="8" w:space="4" w:color="{th["h1_rule"]}"/></w:pBdr>' if n == 1 and th['h1_rule'] else ''
        jc = '<w:jc w:val="center"/>' if th['h_center'] and n <= 2 else '<w:jc w:val="left"/>'
        heads.append(para(f'Heading{n}', f'heading {n}', f'<w:keepNext/><w:keepLines/>{page}{rule}<w:spacing w:before="{360 if n == 1 else 280}" w:after="120"/>{jc}<w:outlineLvl w:val="{n - 1}"/>',
                          f'{head}<w:b/><w:bCs/><w:color w:val="{th["head_color"]}"/><w:sz w:val="{size}"/><w:szCs w:val="{size}"/>'))
    indent = f'<w:ind w:firstLine="{th["indent"]}"/>' if th['indent'] else ''
    return [
        '<w:docDefaults><w:rPrDefault><w:rPr>' + body + f'<w:sz w:val="{th["body_size"]}"/><w:szCs w:val="{th["body_size"]}"/><w:lang w:val="{"en-US" if lang == "en" else "ko-KR"}" w:eastAsia="ko-KR"/></w:rPr></w:rPrDefault>'
        f'<w:pPrDefault><w:pPr><w:widowControl/><w:spacing w:after="{th["after"]}" w:line="{th["line"]}" w:lineRule="auto"/><w:jc w:val="{th["jc"]}"/></w:pPr></w:pPrDefault></w:docDefaults>',
        f'<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/><w:pPr><w:widowControl/>{indent}</w:pPr></w:style>',
        # 제목·부제에는 '다음 단락과 함께'를 걸지 않는다 — 첫 쪽 맨 위라 쓸모가 없고, '단락 기호'를 보이는 Word 에서 왼쪽에 ▪ 표시가 붙는다 (2026-11-18 사용자 결정)
        para('Title', 'Title', f'<w:spacing w:before="240" w:after="120"/><w:ind w:firstLine="0"/><w:jc w:val="{th["title_jc"]}"/>', f'{head}<w:b/><w:color w:val="{th["title_color"]}"/><w:sz w:val="{th["title_size"]}"/><w:szCs w:val="{th["title_size"]}"/>'),
        para('Subtitle', 'Subtitle', f'<w:spacing w:after="360"/><w:ind w:firstLine="0"/><w:jc w:val="{th["subtitle_jc"]}"/>', f'{head}<w:color w:val="{th["subtitle_color"]}"/><w:sz w:val="{th["subtitle_size"]}"/><w:szCs w:val="{th["subtitle_size"]}"/>'),
        *heads,
        para('Caption', 'caption', f'<w:keepNext/><w:spacing w:before="160" w:after="80"/><w:ind w:firstLine="0"/><w:jc w:val="{th["caption_jc"]}"/>', f'{head}<w:b/><w:color w:val="{th["caption_color"]}"/><w:sz w:val="{cap_size}"/><w:szCs w:val="{cap_size}"/>'),
        para('Source', 'Source', '<w:spacing w:before="40" w:after="200"/><w:ind w:firstLine="0"/><w:jc w:val="left"/>', f'{head}<w:color w:val="555555"/><w:sz w:val="16"/><w:szCs w:val="16"/>'),
        para('Quote', 'Quote', f'<w:pBdr><w:left w:val="single" w:sz="18" w:space="8" w:color="{th["quote_rule"]}"/></w:pBdr><w:ind w:left="340" w:firstLine="0"/>', '<w:color w:val="444444"/>'),
        para('ListParagraph', 'List Paragraph', '<w:spacing w:after="60"/><w:ind w:left="720" w:firstLine="0"/><w:contextualSpacing/>'),
        para('Code', 'Code', '<w:shd w:val="clear" w:color="auto" w:fill="F4F6F8"/><w:spacing w:before="60" w:after="180" w:line="240" w:lineRule="auto"/><w:ind w:firstLine="0"/><w:jc w:val="left"/>', f'{mono}<w:sz w:val="17"/><w:szCs w:val="17"/>'),
        para('TableText', 'Table Text', '<w:spacing w:after="0" w:line="240" w:lineRule="auto"/><w:ind w:firstLine="0"/><w:jc w:val="left"/>', f'<w:sz w:val="{th["cell_size"]}"/><w:szCs w:val="{th["cell_size"]}"/>'),
        para('FootnoteText', 'footnote text', '<w:spacing w:after="0" w:line="240" w:lineRule="auto"/><w:ind w:firstLine="0"/>', '<w:sz w:val="17"/><w:szCs w:val="17"/>'),
        para('TOC1', 'toc 1', '<w:spacing w:after="60"/><w:ind w:firstLine="0"/>', '<w:b/>'),
        para('TOC2', 'toc 2', '<w:spacing w:after="40"/><w:ind w:left="240" w:firstLine="0"/>'),
        para('TOC3', 'toc 3', '<w:spacing w:after="40"/><w:ind w:left="480" w:firstLine="0"/>'),
        para('Header', 'header', '<w:tabs><w:tab w:val="right" w:pos="9412"/></w:tabs><w:spacing w:after="0"/><w:ind w:firstLine="0"/>', f'{head}<w:color w:val="{th["header_color"]}"/><w:sz w:val="16"/><w:szCs w:val="16"/>'),
        para('Footer', 'footer', '<w:spacing w:after="0"/><w:ind w:firstLine="0"/><w:jc w:val="center"/>', f'{head}<w:color w:val="{th["footer_color"]}"/><w:sz w:val="18"/><w:szCs w:val="18"/>'),
        '<w:style w:type="character" w:styleId="FootnoteReference"><w:name w:val="footnote reference"/><w:rPr><w:vertAlign w:val="superscript"/></w:rPr></w:style>',
        f'<w:style w:type="character" w:styleId="Hyperlink"><w:name w:val="Hyperlink"/><w:rPr><w:color w:val="{th["link"]}"/><w:u w:val="single"/></w:rPr></w:style>',
        '<w:style w:type="table" w:default="1" w:styleId="TableNormal"><w:name w:val="Normal Table"/><w:tblPr><w:tblInd w:w="0" w:type="dxa"/>'
        '<w:tblCellMar><w:top w:w="0" w:type="dxa"/><w:left w:w="108" w:type="dxa"/><w:bottom w:w="0" w:type="dxa"/><w:right w:w="108" w:type="dxa"/></w:tblCellMar></w:tblPr></w:style>',
        '<w:style w:type="table" w:styleId="LecternTable"><w:name w:val="Lectern Table"/><w:basedOn w:val="TableNormal"/><w:tblPr>'
        f'<w:tblBorders><w:top w:val="single" w:sz="12" w:space="0" w:color="{th["rule"]}"/><w:bottom w:val="single" w:sz="12" w:space="0" w:color="{th["rule"]}"/>'
        f'<w:insideH w:val="single" w:sz="4" w:space="0" w:color="{th["inner"]}"/></w:tblBorders>'
        '<w:tblCellMar><w:top w:w="40" w:type="dxa"/><w:left w:w="100" w:type="dxa"/><w:bottom w:w="40" w:type="dxa"/><w:right w:w="100" w:type="dxa"/></w:tblCellMar></w:tblPr>'
        f'<w:tblStylePr w:type="firstRow"><w:rPr><w:b/><w:bCs/><w:color w:val="{th["th_color"]}"/></w:rPr><w:tcPr><w:shd w:val="clear" w:color="auto" w:fill="{th["th_fill"]}"/></w:tcPr></w:tblStylePr></w:style>',
    ]


# 문서가 쓰는 스타일: 역할 → (이름, 기본 정의의 styleId)
ROLES = {
    'title': ('Title', 'Title'), 'subtitle': ('Subtitle', 'Subtitle'), 'normal': ('Normal', 'Normal'),
    **{f'h{n}': (f'heading {n}', f'Heading{n}') for n in range(1, 7)},
    'caption': ('caption', 'Caption'), 'source': ('Source', 'Source'), 'quote': ('Quote', 'Quote'), 'list': ('List Paragraph', 'ListParagraph'),
    'code': ('Code', 'Code'), 'cell': ('Table Text', 'TableText'), 'fn': ('footnote text', 'FootnoteText'), 'fnref': ('footnote reference', 'FootnoteReference'),
    'link': ('Hyperlink', 'Hyperlink'), 'table': ('Lectern Table', 'LecternTable'), 'header': ('header', 'Header'), 'footer': ('footer', 'Footer'),
    'toc1': ('toc 1', 'TOC1'), 'toc2': ('toc 2', 'TOC2'), 'toc3': ('toc 3', 'TOC3'),
}


# ---- 문서 읽기 ----------------------------------------------------------------------------------------------------

def slugify(text):
    """Lectern 의 제목 앵커 (markdown.js 의 slugify) — 글자·숫자·밑줄·공백·- 만 남기고 공백은 -"""
    keep = ''.join(ch for ch in text.strip().lower() if unicodedata.category(ch)[0] in 'LMN' or unicodedata.category(ch) == 'Pc' or ch in ' -')
    return keep.replace(' ', '-')


def split_notes(lines):
    """각주 정의 '[^이름]: 글' 을 떼어 낸다 (코드 블록 안은 그대로). (남은 줄, {이름: 글})"""
    out, notes, fence, i = [], {}, None, 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        f = re.match(r'^(`{3,}|~{3,})', s)
        if fence:
            out.append(line)
            if s.startswith(fence):
                fence = None
            i += 1
            continue
        if f:
            fence = f[1]
            out.append(line)
            i += 1
            continue
        m = re.match(r'^\[\^([^\]]+)\]:\s?(.*)$', line)
        if m:
            text = [m[2]]
            i += 1
            while i < len(lines) and lines[i].startswith(('    ', '\t')):
                text.append(lines[i].strip())
                i += 1
            notes[m[1]] = ' '.join(x for x in text if x)
            continue
        out.append(line)
        i += 1
    return out, notes


def read_body(lines, store):
    """줄 → 블록. lectern_md.read_blocks 에 Lectern 문서의 줄(박스글·쪽 나눔·목차·$$ 수식·주석)을 더한다.
    문장 속 수식은 store 에 모으고 그 자리에 표시를 둔다 (protect_math)"""
    out, buf, fence, i = [], [], None, 0

    def flush():
        if buf:
            for b in LM.read_blocks(buf):
                if b['kind'] == 'code' and b.get('lang') in ('math', 'latex', 'tex'):
                    out.append({'kind': 'math', 'text': '\n'.join(b['lines'])})
                elif b['kind'] == 'code' and b.get('lang') in ('vega', 'graphviz'):   # lectern_md 는 슬라이드의 것만 안다
                    out.append({'kind': 'chart' if b['lang'] == 'vega' else 'diagram', 'lang': b['lang'], 'text': '\n'.join(b['lines'])})
                else:
                    out.append(b)
            buf.clear()

    while i < len(lines):
        line = lines[i]
        s = line.strip()
        f = re.match(r'^(`{3,}|~{3,})', s)
        if fence:
            buf.append(line)
            if s.startswith(fence):
                fence = None
            i += 1
            continue
        if f:
            fence = f[1]
            buf.append(line)
            i += 1
            continue
        box = BOX_OPEN.match(line)
        if box:
            flush()
            inner = []
            i += 1
            while i < len(lines) and not BOX_CLOSE.match(lines[i]) and not BOX_OPEN.match(lines[i]) and not re.match(r'^#{1,6}\s', lines[i].strip()):
                inner.append(lines[i])
                i += 1
            if i < len(lines) and BOX_CLOSE.match(lines[i]):
                i += 1
            out.append({'kind': 'box', 'name': (box[1] or '').strip(), 'blocks': read_body(inner, store)})
            continue
        if BOX_CLOSE.match(line):
            i += 1
            continue
        if PAGE_BREAK.match(s):
            flush()
            out.append({'kind': 'pagebreak'})
            i += 1
            continue
        toc = TOC_LINE.match(s)
        if toc:
            flush()
            word = toc[1].lower()
            out.append({'kind': 'toc', 'what': 'tables' if word in ('표 목차', 'list of tables') else 'figures' if word in ('그림 목차', 'list of figures') else 'toc'})
            i += 1
            continue
        if s.startswith(('$$', '\\[')):
            flush()
            close = '$$' if s.startswith('$$') else '\\]'
            if s.endswith(close) and len(s) > 3:
                text = [s[2:-2]]
            else:
                text = [s[2:]]
                i += 1
                while i < len(lines) and not lines[i].strip().endswith(close):
                    text.append(lines[i])
                    i += 1
                if i < len(lines):
                    text.append(lines[i].strip()[:-2])
            out.append({'kind': 'math', 'text': '\n'.join(text).strip()})
            i += 1
            continue
        if re.match(r'^</?details\b[^>]*>$', s, re.I):   # 접는 상자 — Word 에는 접기가 없으니 틀만 걷고 펴서 담는다
            i += 1
            continue
        if re.match(r'^<details\b[^>]*>\s*<summary>', s, re.I) or re.match(r'^<summary>', s, re.I):
            line = re.sub(r'^(?:<details\b[^>]*>)?\s*<summary>(.*?)</summary>\s*$', r'**\1**', s, flags=re.I)
        if s.startswith('<!--'):
            flush()
            while i < len(lines) and '-->' not in lines[i]:
                i += 1
            i += 1
            continue
        buf.append(protect_math(line, store))
        i += 1
    flush()
    return out


# ---- 그림 --------------------------------------------------------------------------------------------------------

def image_size(data):
    """PNG·JPEG·GIF·BMP 의 (가로, 세로) 픽셀 — 모르면 None"""
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return struct.unpack('>II', data[16:24])
    if data[:6] in (b'GIF87a', b'GIF89a'):
        return struct.unpack('<HH', data[6:10])
    if data[:2] == b'BM':
        w, h = struct.unpack('<ii', data[18:26])
        return w, abs(h)
    if data[:2] == b'\xff\xd8':
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack('>HH', data[i + 5:i + 9])
                return w, h
            size = struct.unpack('>H', data[i + 2:i + 4])[0]
            i += 2 + size
    return None


def trim(path):
    """Pillow 가 있으면 그림 둘레의 빈(투명) 여백을 잘라 낸다"""
    try:
        from PIL import Image  # type: ignore[import-not-found]
    except ImportError:
        return
    try:
        with Image.open(path) as im:
            box = im.getchannel('A').getbbox() if im.mode == 'RGBA' else None
            if box:
                pad = 12
                box = (max(0, box[0] - pad), max(0, box[1] - pad), min(im.width, box[2] + pad), min(im.height, box[3] + pad))
                im.crop(box).save(path)
    except Exception:   # noqa: BLE001 — 자르지 못하면 그대로
        pass


MATH_HTML = """<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="%(css)s"><script src="%(js)s"></script>
<style>html,body{margin:0;background:transparent}#box{display:inline-block;padding:8px 12px;font-size:%(size)dpx}</style></head>
<body><div id="box"></div><script>katex.render(%(tex)s, document.getElementById('box'), { displayMode: true, throwOnError: false });</script></body></html>"""


def math_png(tex, out):
    """블록 수식을 KaTeX 로 그린 PNG (Edge). 못 그리면 False"""
    root, browser = figure_png.vendor_dir(), figure_png.edge()
    if root is None or browser is None or not (root / 'katex' / 'katex.min.js').exists():
        return False
    html = MATH_HTML % {'css': (root / 'katex' / 'katex.min.css').as_uri(), 'js': (root / 'katex' / 'katex.min.js').as_uri(), 'size': 17,
                        'tex': json.dumps(tex, ensure_ascii=False).replace('</', '<\\/')}
    ok = figure_png.shoot(browser, html, 900, 220, 2, Path(out))
    if ok:
        trim(out)
    return ok and Path(out).stat().st_size > 300


# ---- docx 짓기 --------------------------------------------------------------------------------------------------

def x(text):
    return escape(text, {'"': '&quot;'})


class Builder:
    def __init__(self, md_path, lang, styles, text_width, notes, tmp):
        self.md = Path(md_path)
        self.lang = lang
        self.sid = styles            # 역할 → styleId
        self.width = text_width      # 글 폭 (twip)
        self.notes_src = notes       # 각주 이름 → 글
        self.tmp = Path(tmp)
        self.body: list[str] = []
        self.rels: list[tuple[str, str, str, bool]] = []   # (rId, 종류, 대상, 바깥)
        self.media: list[tuple[str, bytes]] = []
        self.footnotes: dict[str, int] = {}                # 이름 → Word 각주 번호
        self.fn_xml: list[str] = []
        self.in_note = False                                # 각주의 글을 짓는 중 — 링크의 관계를 footnotes.xml 쪽에
        self.note_rels: list[tuple[str, str]] = []          # (rId, 주소)
        self.list_nums: list[tuple[int, int, int]] = []     # 번호 목록마다 (numId, 단계, 첫 번호)
        self.figures = 0
        self.report_notes: list[str] = []
        self.bm = 1000                                      # 양식이 쓴 번호와 겹치지 않게
        self.heads: dict[str, str] = {}                     # 제목 앵커 → 책갈피
        self.drawing_id = 1000
        self.texts: list[str] = []                           # 문장 속 수식 (protect_math 가 모은 것)

    # -- 관계
    def rel(self, kind, target, external=False):
        rid = f'rIdLec{len(self.rels) + 1}'
        self.rels.append((rid, kind, target, external))
        return rid

    def bookmark(self, name, inner):
        self.bm += 1
        return f'<w:bookmarkStart w:id="{self.bm}" w:name="{x(name)}"/>{inner}<w:bookmarkEnd w:id="{self.bm}"/>'

    # -- 글자
    def runs(self, runs, base_rpr=''):
        out = []
        for r in runs:
            out.append(self.run(r, base_rpr))
        return ''.join(out)

    def run(self, r, base=''):
        text = r.get('t', '')
        if SENT in text:   # 각주·수식 자리
            parts = text.split(SENT)
            out = []
            for k, part in enumerate(parts):
                if k % 2 == 0:
                    if part:
                        out.append(self.run({**r, 't': part}, base))
                elif part.startswith('fn:'):
                    out.append(self.footnote_ref(part[3:]))
                elif part.startswith('m:') and part[2:].isdigit() and int(part[2:]) < len(self.texts):
                    out.append(self.runs(tex_runs(self.texts[int(part[2:])]), base))
            return ''.join(out)
        props = []
        if r.get('math'):
            props.append(_font('Cambria Math'))
        elif r.get('code'):
            props.append(_font('Consolas', 'D2Coding'))
        if r.get('b'):
            props.append('<w:b/><w:bCs/>')
        if r.get('i'):
            props.append('<w:i/><w:iCs/>')
        if r.get('s'):
            props.append('<w:strike/>')
        if r.get('color') in TEXT_COLOR:
            props.append(f'<w:color w:val="{TEXT_COLOR[r["color"]]}"/>')
        if r.get('u'):
            props.append('<w:u w:val="single"/>')
        if r.get('mark') in MARK_FILL:
            props.append(f'<w:shd w:val="clear" w:color="auto" w:fill="{MARK_FILL[r["mark"]]}"/>')
        elif r.get('code'):
            props.append('<w:shd w:val="clear" w:color="auto" w:fill="F1F3F5"/>')
        if r.get('sub') or r.get('sup'):
            props.append(f'<w:vertAlign w:val="{"subscript" if r.get("sub") else "superscript"}"/>')
        rpr = base + ''.join(props)
        pieces = []
        for k, line in enumerate(text.split('\n')):
            if k:
                pieces.append('<w:br/>')
            if line:
                pieces.append(f'<w:t xml:space="preserve">{x(line)}</w:t>')
        body = f'<w:r>{f"<w:rPr>{rpr}</w:rPr>" if rpr else ""}{"".join(pieces)}</w:r>'
        link = r.get('link')
        if link:
            style = f'<w:rStyle w:val="{self.sid["link"]}"/>'
            body = f'<w:r><w:rPr>{style}{rpr}</w:rPr>{"".join(pieces)}</w:r>'
            if re.match(r'^(https?:|mailto:)', link, re.I):
                rid = self.note_rel(link) if self.in_note else self.rel('link', link, True)
                return f'<w:hyperlink r:id="{rid}">{body}</w:hyperlink>'
            if link.startswith('#'):
                target = self.anchor(link[1:])
                if target:
                    return f'<w:hyperlink w:anchor="{x(target)}">{body}</w:hyperlink>'
            return f'<w:r>{f"<w:rPr>{rpr}</w:rPr>" if rpr else ""}{"".join(pieces)}</w:r>'   # 프로젝트 안 링크 — 글로
        return body

    def anchor(self, frag):
        """'#표-3'·'#table-3' → 캡션 책갈피, 제목 앵커 → 제목 책갈피"""
        from urllib.parse import unquote
        frag = unquote(frag)
        m = re.fullmatch(r'(표|그림|박스|table|figure|box)-(\d+)', frag, re.I)
        if m:
            return f'lec_{CAP_KEY[m[1].lower()]}_{m[2]}'
        return self.heads.get(frag)

    def note_rel(self, target):
        rid = f'rIdLecFn{len(self.note_rels) + 1}'
        self.note_rels.append((rid, target))
        return rid

    def footnote_ref(self, name):
        if name not in self.notes_src:
            return f'<w:r><w:t xml:space="preserve">[^{x(name)}]</w:t></w:r>'
        style = f'<w:rPr><w:rStyle w:val="{self.sid["fnref"]}"/></w:rPr>'
        if name in self.footnotes:
            # 같은 각주를 또 부르면 — Word 의 각주는 참조 표시가 하나뿐이어야 한다 (둘이면 '파일이 손상되었습니다').
            # 두 번째부터는 첫 참조의 책갈피를 가리키는 NOTEREF 필드 (Word 가 번호를 다시 매겨도 맞는다)
            n = self.footnotes[name]
            return (f'<w:r>{style}<w:fldChar w:fldCharType="begin"/></w:r><w:r>{style}<w:instrText xml:space="preserve"> NOTEREF _RefLecFn{n} \\f \\h </w:instrText></w:r>'
                    f'<w:r>{style}<w:fldChar w:fldCharType="separate"/></w:r><w:r>{style}<w:t>{n}</w:t></w:r><w:r>{style}<w:fldChar w:fldCharType="end"/></w:r>')
        n = len(self.footnotes) + 1
        self.footnotes[name] = n
        runs = LM.inline(protect_math(self.notes_src[name], self.texts))
        self.in_note = True
        note_runs = self.runs(runs)
        self.in_note = False
        self.fn_xml.append(f'<w:footnote w:id="{n}"><w:p><w:pPr><w:pStyle w:val="{self.sid["fn"]}"/></w:pPr>'
                           f'<w:r>{style}<w:footnoteRef/></w:r><w:r><w:t xml:space="preserve"> </w:t></w:r>{note_runs}</w:p></w:footnote>')
        return self.bookmark(f'_RefLecFn{n}', f'<w:r>{style}<w:footnoteReference w:id="{n}"/></w:r>')

    # -- 단락
    def para(self, inner, style=None, ppr=''):
        pst = f'<w:pStyle w:val="{style}"/>' if style else ''
        return f'<w:p><w:pPr>{pst}{ppr}</w:pPr>{inner}</w:p>'

    def inline_runs(self, text_runs):
        """run 글 속의 각주·문장 수식을 표시로 바꾼다 (run() 이 다시 나눈다)"""
        out = []
        for r in text_runs:
            if r.get('code'):
                out.append(r)
                continue
            out.append({**r, 't': FOOTREF.sub(lambda m: f'{SENT}fn:{m[1]}{SENT}', r['t'])})
        return out

    # -- 블록
    def blocks(self, blocks, in_cell=False):
        out = []
        i = 0
        while i < len(blocks):
            b = blocks[i]
            nxt = blocks[i + 1] if i + 1 < len(blocks) else None
            k = b['kind']
            if k == 'para':
                cap = CAPTION.match(LM.plain(b['runs']))
                if cap and not in_cell:
                    out.append(self.caption(b['runs'], cap))
                elif SOURCE.match(LM.plain(b['runs'])):
                    out.append(self.para(self.runs(self.inline_runs(b['runs'])), self.sid['source']))
                else:
                    out.append(self.para(self.runs(self.inline_runs(b['runs'])), self.sid['cell'] if in_cell else self.sid['normal']))
            elif k == 'heading':
                out.append(self.heading(b))
            elif k == 'list':
                out.extend(self.list_block(b))
            elif k == 'table':
                out.append(self.table(b))
                out.append(self.para('', None, '<w:spacing w:after="0" w:line="120" w:lineRule="exact"/>'))   # 표 뒤 숨 — 바로 뒤 표와 붙지 않게
            elif k == 'quote':
                out.append(self.alert(b) if b.get('alert') else self.quote(b))
            elif k == 'box':
                out.append(self.box(b))
            elif k == 'code':
                out.append(self.code(b['lines']))
            elif k in ('chart', 'diagram'):
                out.append(self.figure(b))
            elif k == 'math':
                out.append(self.math(b["text"]))
            elif k == 'image':
                out.append(self.image(b))
            elif k == 'pagebreak':
                out.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
            elif k == 'toc':
                out.append(self.toc(b['what']))
            i += 1
        return out

    def name_heads(self, blocks):
        """제목마다 책갈피 이름을 먼저 정한다 — 앞쪽 문단이 뒤쪽 절을 가리킬 수 있게. 같은 앵커는 -1, -2 (앱과 같다)"""
        for b in blocks:
            if b['kind'] == 'box':
                self.name_heads(b['blocks'])
            if b['kind'] != 'heading':
                continue
            text = re.sub(f'{SENT}m:(\\d+){SENT}', lambda m: self.texts[int(m[1])], LM.plain(b['runs']))
            slug = base = slugify(text)
            n = 1
            while slug in self.heads:
                slug = f'{base}-{n}'
                n += 1
            b['bm'] = self.heads[slug] = f'lec_h_{len(self.heads) + 1}'

    def heading(self, b):
        level = b['level']
        name = b.get('bm') or f'lec_h_x{id(b)}'
        if level == 0:
            style = self.sid['title']
        else:
            style = self.sid[f'h{min(level, 6)}']
        return self.para(self.bookmark(name, self.runs(self.inline_runs(b['runs']))), style)

    def caption(self, runs, cap):
        word, n = cap[1], cap[2]
        key = CAP_KEY[word.lower()]
        rest_runs = self.strip_caption(runs, cap.end())
        field = (f'<w:r><w:t xml:space="preserve">{x(word)} </w:t></w:r>'
                 f'<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> SEQ {x(word)} \\* ARABIC </w:instrText></w:r>'
                 f'<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>{n}</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r>'
                 '<w:r><w:t xml:space="preserve">. </w:t></w:r>')
        return self.para(self.bookmark(f'lec_{key}_{n}', field) + self.runs(self.inline_runs(rest_runs)), self.sid['caption'])

    @staticmethod
    def strip_caption(runs, cut):
        """캡션 꼬리표('표 3.')를 뗀 run 들 — 굵게 표시도"""
        out, pos = [], 0
        for r in runs:
            t = r['t']
            if pos + len(t) <= cut:
                pos += len(t)
                continue
            start = max(0, cut - pos)
            out.append({**{k: v for k, v in r.items() if k != 'b'}, 't': t[start:]})
            pos += len(t)
        if out:
            out[0]['t'] = out[0]['t'].lstrip()
        return [r for r in out if r['t']]

    def list_block(self, b):
        out = []
        num_ids = {}
        for it in b['items']:
            lvl = min(it['lvl'], 8)
            for deeper in [k for k in num_ids if k > lvl]:   # 윗 단계 항목이 나오면 그 아래 번호 목록은 끝 — 다음은 새 목록 (앱과 같다)
                del num_ids[deeper]
            if it.get('task') and not it['ordered']:   # 할 일: 체크 칸(☐·☑)만 — 글머리는 붙이지 않는다 (앱 화면과 같게, 2026-11-18 양식 18가지 점검). 들여쓰기는 그 단계의 글머리 목록과 같다
                out.append(self.para(self.runs(self.inline_runs(it['runs'])), self.sid['list'], f'<w:ind w:left="{360 + 360 * lvl}" w:hanging="300"/>'))
                continue
            if it['ordered']:
                if lvl not in num_ids:
                    num_ids[lvl] = self.new_list(lvl, it.get('start') or 1)
                num = num_ids[lvl]
            else:
                num = 1   # 글머리표 목록
            out.append(self.para(self.runs(self.inline_runs(it['runs'])), self.sid['list'],
                                 f'<w:numPr><w:ilvl w:val="{lvl}"/><w:numId w:val="{num}"/></w:numPr>'))
        return out

    def new_list(self, lvl=0, start=1):
        """번호 목록 하나 — 같은 번호 정의를 쓰는 새 num, 그 단계의 번호는 원문의 첫 번호부터 (3. 으로 시작하면 3)"""
        num_id = 100 + len(self.list_nums)
        self.list_nums.append((num_id, lvl, start))
        return num_id

    def cell(self, inner, fill=None, width=None, header=False):
        tcpr = (f'<w:tcW w:w="{width}" w:type="dxa"/>' if width else '') + (f'<w:shd w:val="clear" w:color="auto" w:fill="{fill}"/>' if fill else '')
        return f'<w:tc><w:tcPr>{tcpr}</w:tcPr>{inner or self.para("", self.sid["cell"])}</w:tc>'

    def table(self, b):
        rows = b['rows']
        if not rows:
            return ''
        cols = max(len(r) for r in rows)
        width = self.width
        col_w = width // cols
        aligns = (b.get('align') or []) + [None] * cols
        numeric = [all(re.fullmatch(r'[-+]?[\d,.]+%?p?|[-+]?[\d,.]+\s*[%배원톤t$]?', LM.plain(r[c]).strip() or '0') for r in rows[1:] if c < len(r)) for c in range(cols)]
        grid = ''.join(f'<w:gridCol w:w="{col_w}"/>' for _ in range(cols))
        out = [f'<w:tbl><w:tblPr><w:tblStyle w:val="{self.sid["table"]}"/><w:tblW w:w="{width}" w:type="dxa"/><w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="1" w:lastColumn="0" w:noHBand="0" w:noVBand="1"/></w:tblPr><w:tblGrid>{grid}</w:tblGrid>']
        whole = len(rows) <= 15   # 짧은 표는 쪽·단에서 가르지 않는다 (2단 양식에서 3행 표가 두 단에 갈라졌다). 머리행은 늘 첫 행과 함께
        for ri, row in enumerate(rows):
            head = ri == 0
            trpr = '<w:cantSplit/>' + ('<w:tblHeader/>' if head else '')
            keep = '<w:keepNext/>' if ri < len(rows) - 1 and (whole or head) else ''
            cells = []
            for c in range(cols):
                runs = row[c] if c < len(row) else []
                align = aligns[c] or ('right' if numeric[c] and not head else None)
                jc = f'<w:jc w:val="{ {"right": "right", "center": "center"}.get(align, "left")}"/>'
                inner = self.para(self.runs(self.inline_runs(runs)), self.sid['cell'], keep + jc)
                cells.append(self.cell(inner, None, col_w))
            out.append(f'<w:tr><w:trPr>{trpr}</w:trPr>{"".join(cells)}</w:tr>')
        out.append('</w:tbl>')
        return ''.join(out)

    def boxed(self, inner_blocks, color, fill, left_only=False, title=None, title_bm=None):
        """한 칸 표로 감싼 블록 — 강조글(왼쪽 색 줄)·박스글(테두리)"""
        width = self.width
        if left_only:
            borders = f'<w:tblBorders><w:left w:val="single" w:sz="24" w:space="0" w:color="{color}"/></w:tblBorders>'
        else:
            borders = (f'<w:tblBorders><w:top w:val="single" w:sz="18" w:space="0" w:color="{color}"/><w:left w:val="single" w:sz="4" w:space="0" w:color="BBBBBB"/>'
                       f'<w:bottom w:val="single" w:sz="4" w:space="0" w:color="BBBBBB"/><w:right w:val="single" w:sz="4" w:space="0" w:color="BBBBBB"/></w:tblBorders>')
        body = ''.join(self.blocks(inner_blocks, in_cell=True)) or self.para('', self.sid['cell'])
        rows = ''
        if title:
            head = self.runs(self.inline_runs(title), '<w:b/><w:bCs/>')
            if title_bm:
                head = self.bookmark(title_bm, head)
            rows += f'<w:tr><w:trPr><w:cantSplit/></w:trPr>{self.cell(self.para(head, self.sid["cell"], "<w:keepNext/>"), "E4E8EE", width)}</w:tr>'
        rows += f'<w:tr><w:trPr><w:cantSplit/></w:trPr>{self.cell(body, fill, width)}</w:tr>'
        tbl = (f'<w:tbl><w:tblPr><w:tblW w:w="{width}" w:type="dxa"/>{borders}'
               '<w:tblCellMar><w:top w:w="100" w:type="dxa"/><w:left w:w="160" w:type="dxa"/><w:bottom w:w="80" w:type="dxa"/><w:right w:w="160" w:type="dxa"/></w:tblCellMar>'
               f'</w:tblPr><w:tblGrid><w:gridCol w:w="{width}"/></w:tblGrid>{rows}</w:tbl>')
        return tbl + self.para('', None, '<w:spacing w:after="0" w:line="120" w:lineRule="exact"/>')

    def alert(self, b):
        color = ALERT.get(b['alert'], '2F6FB3')
        return self.boxed(b['blocks'], color, 'F6F8FA', left_only=True)

    def quote(self, b):
        out = []
        for blk in b['blocks']:
            if blk['kind'] == 'para':
                out.append(self.para(self.runs(self.inline_runs(blk['runs'])), self.sid['quote']))
            else:
                out.extend(self.blocks([blk]))
        return ''.join(out)

    def box(self, b):
        blocks = list(b['blocks'])
        title = None
        # 앱과 같다: 한 줄짜리 첫 문단이 제목 (markdown.js 의 lec-textbox-title). 그것뿐이면 본문으로 둔다 — 제목 띠만 남지 않게
        if len(blocks) > 1 and blocks[0]['kind'] == 'para' and '\n' not in LM.plain(blocks[0]['runs']):
            title = [{**r, 'b': False} for r in blocks[0]['runs']]
            blocks = blocks[1:]
        elif b.get('name'):   # 이름 있는 박스글 (<!-- box: 요약 -->) — Word 에는 틀의 자리가 없으니 이름을 제목으로
            title = [{'t': b['name']}]
        cap = CAPTION.match(LM.plain(title)) if title else None
        bm = f'lec_{CAP_KEY[cap[1].lower()]}_{cap[2]}' if cap else None   # '박스 1. 제목' — [박스 1](#박스-1) 이 여기로
        return self.boxed(blocks, '1B3A5C', 'FAFBFC', title=title, title_bm=bm)

    def code(self, lines):
        """코드 블록 — 문단 하나에 줄바꿈으로. 탭은 Word 의 탭 (w:t 안의 탭 글자는 빈칸으로 보일 수 있다)"""
        def line_xml(line):
            return '<w:tab/>'.join(f'<w:t xml:space="preserve">{x(bit)}</w:t>' for bit in line.split('\t'))
        inner = '<w:r>' + ''.join(('<w:br/>' if k else '') + line_xml(line) for k, line in enumerate(lines)) + '</w:r>'
        return self.para(inner, self.sid['code'])

    # -- 그림
    def picture(self, data, ext, alt='', width_frac=1.0, px_scale=1.0, want=(None, None)):
        size = image_size(data)
        if not size:
            self.report_notes.append(f'그림을 읽지 못했습니다: {alt or ext}')   # i18n-ok (스킬의 보고)
            return self.para(f'<w:r><w:t xml:space="preserve">[{x(alt or "그림")}]</w:t></w:r>')
        self.figures += 1
        name = f'lec{len(self.media) + 1}.{ext}'
        self.media.append((name, data))
        rid = self.rel('image', f'media/{name}')
        px_w, px_h = size
        max_w = int(self.width * EMU * width_frac)
        max_h = int((A4[1] - 3500) * EMU * 0.62)
        cx = min(max_w, int(px_w / px_scale * 9525))   # 96dpi 의 1px = 9525 EMU, px_scale 배로 그린 그림은 그만큼 줄여 제 크기로
        cy = int(cx * px_h / px_w)
        ww, wh = want   # 원문의 w:300·h:200 (화면 px) — 한쪽만 있으면 비율대로
        if ww or wh:
            cx = min(max_w, int((ww or wh * px_w / px_h) * 9525))
            cy = int(wh * 9525) if ww and wh else int(cx * px_h / px_w)
        if cy > max_h:
            cy = max_h
            cx = int(cy * px_w / px_h)
        self.drawing_id += 1
        did = self.drawing_id
        return self.para(
            f'<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/><wp:docPr id="{did}" name="그림 {did}" descr="{x(alt)}"/>'   # i18n-ok (Word 안의 이름)
            f'<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic><pic:nvPicPr><pic:cNvPr id="{did}" name="{x(name)}"/><pic:cNvPicPr/></pic:nvPicPr>'
            f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r>',
            None, '<w:keepNext/><w:jc w:val="center"/><w:spacing w:before="120" w:after="60"/>')

    def image(self, b):
        src = b['src']
        if re.match(r'^(https?:)?//', src, re.I):
            self.report_notes.append(f'인터넷 그림은 넣지 않았습니다: {src}')   # i18n-ok
            return self.para(self.runs([{'t': b.get('alt') or src, 'link': src}]))
        from urllib.parse import unquote
        path = (self.md.parent / unquote(src)).resolve()
        if not path.is_file():
            self.report_notes.append(f'그림 파일이 없습니다: {src}')   # i18n-ok
            return self.para(f'<w:r><w:t xml:space="preserve">[{x(b.get("alt") or src)}]</w:t></w:r>')
        ext = path.suffix.lower().lstrip('.')
        if ext == 'svg':
            out = self.tmp / f'svg{self.figures}.png'
            if figure_png.svg(path, out):
                data = out.read_bytes()
                natural = figure_png.svg_size(path)   # 그림의 제 크기 (viewBox) — 크게 그린 PNG 를 그만큼 줄인다
                scale = (image_size(data) or (1, 1))[0] / natural[0] if natural else 1.0
                return self.picture(data, 'png', b.get('alt', ''), px_scale=max(scale, 1.0), want=(b.get('w'), b.get('h')))
            self.report_notes.append(f'SVG 를 그림으로 바꾸지 못했습니다: {src}')   # i18n-ok
            return self.para(f'<w:r><w:t xml:space="preserve">[{x(b.get("alt") or src)}]</w:t></w:r>')
        if ext == 'jpg':
            ext = 'jpeg'
        if ext not in ('png', 'jpeg', 'gif', 'bmp'):
            return self.para(f'<w:r><w:t xml:space="preserve">[{x(b.get("alt") or src)}]</w:t></w:r>')
        return self.picture(path.read_bytes(), ext, b.get('alt', ''), want=(b.get('w'), b.get('h')))

    def figure(self, b):
        out = self.tmp / f'fig{self.figures + 1}.png'
        kind = {'graphviz': 'dot'}.get(b['lang'], b['lang'])
        ok = False
        try:
            ok = figure_png.draw(kind, b['text'], 1150, 640 if b['kind'] == 'chart' else 680, out, base=self.md.parent)
        except Exception:   # noqa: BLE001 — 그리지 못하면 원문으로
            ok = False
        if ok:
            trim(out)
            return self.picture(out.read_bytes(), 'png', kind)
        self.report_notes.append(f'{kind} 를 그리지 못해 원문을 넣었습니다 — 설정을 확인하세요 (Edge 가 있어야 그린다)')   # i18n-ok
        return self.code(b['text'].split('\n'))

    def math(self, tex):
        out = self.tmp / f'math{self.figures + 1}.png'
        if math_png(tex, out):
            return self.picture(out.read_bytes(), 'png', tex, width_frac=0.9, px_scale=2)
        self.report_notes.append('수식을 그림으로 그리지 못해 원문을 넣었습니다')   # i18n-ok
        return self.para(self.runs([{'t': tex, 'i': True, 'math': True}]), None, '<w:jc w:val="center"/>')

    def toc_field(self, what='toc'):
        """Word 목차 필드만 (양식의 {{toc}} — 이름 줄은 양식이 쓴다)"""
        en = self.lang == 'en'
        if what == 'toc':
            instr = ' TOC \\o "1-3" \\h \\z \\u '
        else:
            word = ('Table' if en else '표') if what == 'tables' else ('Figure' if en else '그림')   # i18n-ok
            instr = f' TOC \\h \\z \\c "{word}" '
        hint = 'Update the field (F9) to fill this in' if en else '필드 업데이트(F9)를 하면 채워집니다'   # i18n-ok
        return (f'<w:p><w:r><w:fldChar w:fldCharType="begin" w:dirty="true"/></w:r><w:r><w:instrText xml:space="preserve">{x(instr)}</w:instrText></w:r>'
                f'<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:rPr><w:color w:val="888888"/></w:rPr><w:t>{x(hint)}</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>')

    def signoff(self, roles):
        """결재란 — 맨 앞 설정의 목록(결재: [담당, 팀장, 본부장])으로 직위 줄과 서명 칸"""
        w = 1150
        grid = ''.join(f'<w:gridCol w:w="{w}"/>' for _ in roles)
        border = ''.join(f'<w:{side} w:val="single" w:sz="6" w:space="0" w:color="555555"/>' for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'))
        head = ''.join(self.cell(self.para(f'<w:r><w:rPr><w:sz w:val="17"/></w:rPr><w:t xml:space="preserve">{x(r)}</w:t></w:r>', self.sid['cell'], '<w:jc w:val="center"/>'), 'EEF1F5', w) for r in roles)
        sign = ''.join(self.cell(self.para('', self.sid['cell']), None, w) for _ in roles)
        return (f'<w:tbl><w:tblPr><w:tblW w:w="{w * len(roles)}" w:type="dxa"/><w:jc w:val="right"/><w:tblBorders>{border}</w:tblBorders></w:tblPr>'
                f'<w:tblGrid>{grid}</w:tblGrid><w:tr><w:trPr><w:cantSplit/></w:trPr>{head}</w:tr>'
                f'<w:tr><w:trPr><w:cantSplit/><w:trHeight w:val="760" w:hRule="exact"/></w:trPr>{sign}</w:tr></w:tbl>'
                + self.para('', None, '<w:spacing w:after="0" w:line="120" w:lineRule="exact"/>'))

    def slot(self, blocks):
        """양식의 박스글 자리({{slot:요약}})에 들어갈 글 — 박스 테두리 없이. '박스 1.'·굵은 글뿐인 제목 줄은 뺀다 (자리 이름은 양식이 쓴다)"""
        blocks = list(blocks)
        if blocks and blocks[0]['kind'] == 'para' and '\n' not in LM.plain(blocks[0]['runs']):
            first = blocks[0]['runs']
            bold_only = all(r.get('b') for r in first if r['t'].strip())
            if bold_only or CAPTION.match(LM.plain(first)):
                blocks = blocks[1:]
        out = ''.join(self.blocks(blocks))
        return out or self.para('')

    def toc(self, what):
        en = self.lang == 'en'
        if what == 'toc':
            instr = ' TOC \\o "1-3" \\h \\z \\u '
            label = 'Contents' if en else '목차'   # i18n-ok (문서 언어)
        else:
            word = ('Table' if en else '표') if what == 'tables' else ('Figure' if en else '그림')   # i18n-ok
            instr = f' TOC \\h \\z \\c "{word}" '
            label = ('List of tables' if what == 'tables' else 'List of figures') if en else ('표 목차' if what == 'tables' else '그림 목차')   # i18n-ok
        hint = 'Update the field (F9) to fill this in' if en else '필드 업데이트(F9)를 하면 채워집니다'   # i18n-ok
        return (self.para(f'<w:r><w:rPr><w:b/></w:rPr><w:t>{x(label)}</w:t></w:r>', None, '<w:keepNext/><w:spacing w:before="240" w:after="120"/>')
                + f'<w:p><w:r><w:fldChar w:fldCharType="begin" w:dirty="true"/></w:r><w:r><w:instrText xml:space="preserve">{x(instr)}</w:instrText></w:r>'
                f'<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:rPr><w:color w:val="888888"/></w:rPr><w:t>{x(hint)}</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>')


# ---- 꾸러미 -------------------------------------------------------------------------------------------------------

def style_ids(styles_xml, extra_map):
    """양식의 styles.xml 에서 이름 → styleId. extra_map 은 '이름.styles.json' (Lectern 이름 → 양식의 이름)"""
    found = {}
    for m in re.finditer(r'<w:style\b[^>]*w:styleId="([^"]+)"[^>]*>.*?<w:name w:val="([^"]+)"', styles_xml, re.S):
        found[m[2].lower()] = m[1]
    sid, missing = {}, []
    for role, (name, default_id) in ROLES.items():
        want = (extra_map.get(name) or extra_map.get(name.lower()) or name).lower()
        if want in found:
            sid[role] = found[want]
        else:
            sid[role] = default_id
            missing.append(role)
    return sid, missing


def add_missing_styles(styles_xml, missing, lang):
    """양식에 없는 스타일을 Lectern 의 기본 정의로 더한다 (같은 styleId 가 이미 있으면 그대로)"""
    defs = default_styles(lang)
    add = []
    for role in missing:
        default_id = ROLES[role][1]
        if re.search(rf'w:styleId="{re.escape(default_id)}"', styles_xml):
            continue
        for d in defs:
            if f'w:styleId="{default_id}"' in d:
                add.append(d)
    if 'w:styleId="TableNormal"' not in styles_xml and any(ROLES[r][1] == 'LecternTable' for r in missing):
        add = [d for d in defs if 'w:styleId="TableNormal"' in d] + add
    return styles_xml.replace('</w:styles>', ''.join(add) + '</w:styles>') if add else styles_xml


def numbering_xml(existing, nums):
    """글머리표(abstract 1 → num 1)와 번호(abstract 2 → 목록마다 num 100…). 양식의 numbering.xml 이 있으면 그 뒤에 이어 단다"""
    bullets = ['•', '◦', '▪', '•', '◦', '▪', '•', '◦', '▪']
    lv_b = ''.join(f'<w:lvl w:ilvl="{i}"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="{b}"/><w:lvlJc w:val="left"/>'
                   f'<w:pPr><w:ind w:left="{360 + 360 * i}" w:hanging="300"/></w:pPr></w:lvl>' for i, b in enumerate(bullets))
    fmts = ['decimal'] * 9   # 안쪽 단계도 1. 2. — 앱 화면과 같다
    lv_n = ''.join(f'<w:lvl w:ilvl="{i}"><w:start w:val="1"/><w:numFmt w:val="{f}"/><w:lvlText w:val="%{i + 1}."/><w:lvlJc w:val="left"/>'
                   f'<w:pPr><w:ind w:left="{400 + 360 * i}" w:hanging="360"/></w:pPr></w:lvl>' for i, f in enumerate(fmts))
    abstract = (f'<w:abstractNum w:abstractNumId="9101"><w:multiLevelType w:val="hybridMultilevel"/>{lv_b}</w:abstractNum>'
                f'<w:abstractNum w:abstractNumId="9102"><w:multiLevelType w:val="hybridMultilevel"/>{lv_n}</w:abstractNum>')
    num = '<w:num w:numId="1"><w:abstractNumId w:val="9101"/></w:num>' if not existing else ''
    num += ''.join(f'<w:num w:numId="{n}"><w:abstractNumId w:val="9102"/><w:lvlOverride w:ilvl="{lvl}"><w:startOverride w:val="{start}"/></w:lvlOverride></w:num>'
                   for n, lvl, start in nums)
    if existing:
        # 양식의 번호 정의를 지키고 우리 것을 더한다 — abstractNum 은 num 보다 앞에 와야 한다
        bullet_num = 9001
        num = f'<w:num w:numId="{bullet_num}"><w:abstractNumId w:val="9101"/></w:num>' + num
        first_num = existing.find('<w:num ')
        if first_num < 0:
            first_num = existing.find('</w:numbering>')
        merged = existing[:first_num] + abstract + existing[first_num:]
        return merged.replace('</w:numbering>', num + '</w:numbering>'), bullet_num
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:numbering {NS}>{abstract}{num}</w:numbering>', 1


def footnotes_xml(existing, items):
    sep = ('<w:footnote w:type="separator" w:id="-1"><w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr><w:r><w:separator/></w:r></w:p></w:footnote>'
           '<w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr><w:r><w:continuationSeparator/></w:r></w:p></w:footnote>')
    if existing:
        return existing.replace('</w:footnotes>', ''.join(items) + '</w:footnotes>')
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:footnotes {NS}>{sep}{"".join(items)}</w:footnotes>'


def header_footer(kind, title):
    if kind == 'header':
        inner = f'<w:p><w:pPr><w:pStyle w:val="Header"/></w:pPr><w:r><w:t xml:space="preserve">{x(title)}</w:t></w:r></w:p>'
        return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:hdr {NS}>{inner}</w:hdr>'
    field = ('<w:r><w:t xml:space="preserve">- </w:t></w:r><w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
             '<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>1</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r><w:r><w:t xml:space="preserve"> -</w:t></w:r>')
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:ftr {NS}><w:p><w:pPr><w:pStyle w:val="Footer"/></w:pPr>{field}</w:p></w:ftr>'


def text_width_of(sect):
    """그 구역의 글 폭 (twip) — 단이 여럿이면 한 단의 폭"""
    w = re.search(r'<w:pgSz\b[^>]*w:w="(\d+)"', sect or '')
    left = re.search(r'<w:pgMar\b[^>]*w:left="(\d+)"', sect or '')
    right = re.search(r'<w:pgMar\b[^>]*w:right="(\d+)"', sect or '')
    width = int(w[1]) - int(left[1]) - int(right[1]) if w and left and right else A4[0] - MARGINS[1] - MARGINS[3]
    cols = re.search(r'<w:cols\b[^>]*w:num="(\d+)"[^>]*>', sect or '')
    if cols and int(cols[1]) > 1:
        space = re.search(r'w:space="(\d+)"', cols[0])
        n = int(cols[1])
        width = (width - (n - 1) * (int(space[1]) if space else 425)) // n
    return width


TEMPLATES = HERE.parent / 'templates'   # Lectern 이 넣어 둔 Word 양식 (D147 — tools/make_docx_templates.py 가 만든다)


def template_index():
    try:
        return json.loads((TEMPLATES / 'index.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []


def resolve_template(name):
    """--template 의 값: 파일 경로, 또는 Lectern 양식의 id·이름 (research-report, 연구보고서). 못 찾으면 None"""
    if not name:
        return None
    path = Path(name)
    if path.is_file():
        return path
    for t in template_index():
        if name in (t['id'], t.get('name'), t.get('name_en')):
            found = TEMPLATES / f"{t['id']}.dotx"
            return found if found.is_file() else None
    return None


def core_xml(title, author):
    now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            f'<dc:title>{x(title)}</dc:title><dc:creator>{x(author)}</dc:creator><cp:lastModifiedBy>Lectern</cp:lastModifiedBy>'
            f'<dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified></cp:coreProperties>')


FM_ALIAS = {'제목': 'title', '부제': 'subtitle', '부제목': 'subtitle', '작성자': 'author', '저자': 'author', '지은이': 'author', '연구진': 'author',
            '날짜': 'date', '일자': 'date', '언어': 'lang', '기관': 'org', '기관명': 'org', '부서': 'dept', '담당부서': 'dept', '번호': 'number',
            '보고서번호': 'number', '호수': 'number', '시리즈': 'series', '고객': 'client', '발주처': 'client', '소속': 'affiliation', '주제어': 'keywords',
            '키워드': 'keywords', '판': 'version', '버전': 'version', '회사': 'company', '기업': 'company', '종목코드': 'ticker', '업종': 'sector',
            '장': 'chapter', '책': 'book', '꼬리표': 'kicker', '짧은제목': 'short_title'}   # 앱의 layout.js ALIAS 와 같다


def fm_text(value):
    """맨 앞 설정 값 → 글. '[가, 나]' 목록은 '가, 나', 참·거짓은 빈 글"""
    if value is None or isinstance(value, bool):
        return ''
    text = str(value).strip()
    if text.startswith('[') and text.endswith(']'):
        return ', '.join(p.strip().strip('\'"') for p in text[1:-1].split(',') if p.strip())
    return text


def build(md_path, out_path, template=None, lang=None):
    """md 문서 → docx. template 은 .dotx·.docx 경로나 Lectern 양식의 id·이름 (resolve_template).
    양식 본문에 {{body}} 문단이 있으면 양식의 본문(표지·요약 자리·차례…)을 두고 그 자리에 본문을 넣는다 (D147 — template_fill.py).
    없으면 양식의 스타일·머리글·바닥글·쪽 설정만 빌리고 본문은 새로 쓴다"""
    md_path = Path(md_path)
    raw_fm, _css, body = LM.split_front(md_path.read_text(encoding='utf-8-sig'))
    fm = {FM_ALIAS.get(k, k): v for k, v in raw_fm.items() if not (k in FM_ALIAS and FM_ALIAS[k] in raw_fm)}   # 영어 키가 있으면 그것
    lang = lang or ('en' if str(fm.get('lang', '')).lower().startswith('en') else 'ko')
    lines, notes = split_notes(body.replace('\r\n', '\n').split('\n'))
    math: list[str] = []
    blocks = read_body(lines, math)
    # 맨 앞 '# 제목' 하나는 문서 제목(Title) — 그 아래 단계를 하나씩 올린다 (## → 제목 1)
    h1 = [b for b in blocks if b['kind'] == 'heading' and b['level'] == 1]
    if len(h1) == 1 and blocks and blocks[0] is h1[0]:
        h1[0]['level'] = 0
        for b in blocks:
            if b['kind'] == 'heading' and b['level'] > 1:
                b['level'] -= 1
    title = fm_text(fm.get('title')) or (LM.plain(h1[0]['runs']) if h1 else md_path.stem)
    author = fm_text(fm.get('author'))
    if template and not Path(template).is_file():
        found = resolve_template(str(template))
        if found is None:
            raise SystemExit(f'양식을 찾지 못했습니다: {template} — 파일 경로나 Lectern 양식 이름(--templates 로 목록)을 주세요')   # i18n-ok
        template = found
    tpl = zipfile.ZipFile(template) if template else None
    names = set(tpl.namelist()) if tpl else set()

    def tpl_text(name):
        return tpl.read(name).decode('utf-8') if tpl and name in names else ''

    extra_map = {}
    if template:
        side = Path(template).with_name(Path(template).stem + '.styles.json')
        if side.is_file():
            try:
                extra_map = {k.lower(): v for k, v in json.loads(side.read_text(encoding='utf-8')).items()}
            except (OSError, ValueError):
                pass
    styles = tpl_text('word/styles.xml')
    if styles:
        sid, missing = style_ids(styles, extra_map)
        styles = add_missing_styles(styles, missing, lang)
    else:
        styles = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:styles {NS}>{"".join(default_styles(lang))}</w:styles>'
        sid, _ = style_ids(styles, {})
    doc_xml = tpl_text('word/document.xml')
    hf_parts = sorted(n for n in names if re.fullmatch(r'word/(header|footer)\d*\.xml', n))
    framed = '{{body}}' in TF.plain_text(doc_xml).replace(' ', '')
    parts_text = [doc_xml] + [tpl_text(n) for n in hf_parts]
    slot_names = TF.slots_in([doc_xml]) if framed else []
    slot_blocks = {}
    for name in slot_names:   # 양식에 자리가 있는 이름 있는 박스글은 본문에서 떼어 그 자리로 (같은 이름이 둘이면 첫째만)
        hit = next((b for b in blocks if b['kind'] == 'box' and b.get('name') == name), None)
        if hit is not None:
            slot_blocks[name] = hit['blocks']
            blocks.remove(hit)
    if framed and TF.uses([doc_xml], 'toc'):   # 양식이 차례 쪽을 쓰면 문서의 [목차] 줄은 뺀다 — 두 번 나오지 않게 (표 목차·그림 목차는 둔다)
        blocks = [b for b in blocks if not (b['kind'] == 'toc' and b['what'] == 'toc')]
    drop_title = framed and TF.uses(parts_text, 'title')   # 양식이 제목을 쓰면(표지) 본문의 '# 제목' 줄은 뺀다
    if drop_title and h1 and h1[0]['level'] == 0 and h1[0] in blocks:
        blocks.remove(h1[0])
    sects = re.findall(r'<w:sectPr\b.*?</w:sectPr>', doc_xml, re.S)
    sect = sects[-1] if sects else ''
    at = re.search(r'\{\{\s*body\s*\}\}', doc_xml) if framed else None
    after = re.search(r'<w:sectPr\b.*?</w:sectPr>', doc_xml[at.end():], re.S) if at else None
    width = text_width_of(after[0] if after else sect)   # 본문이 든 구역의 폭 — 2단 양식은 본문 뒤 구역 나눔이 2단이고 마지막 구역은 1단
    vals = {k: fm_text(v) for k, v in fm.items()}
    vals.update({'title': str(title), 'author': author, 'date': fm_text(fm.get('date')) or TF.today()})
    with tempfile.TemporaryDirectory() as tmp:
        bld = Builder(md_path, lang, sid, width, notes, tmp)
        bld.texts = math
        bld.name_heads(blocks)
        content = bld.blocks(blocks)
        if not drop_title:
            # 표지 머리: 제목 바로 뒤에 부제·작성자·날짜 (맨 앞 설정에 있을 때)
            meta = [v for v in (fm_text(fm.get('subtitle')), ' · '.join(v for v in (author, fm_text(fm.get('date'))) if v)) if v]
            sub = ''.join(bld.para(f'<w:r><w:t xml:space="preserve">{x(m)}</w:t></w:r>', sid['subtitle']) for m in meta)
            if h1 and h1[0]['level'] == 0:   # 문서의 '# 제목' 바로 뒤에 부제·작성자·날짜
                content.insert(1, sub)
            elif fm_text(fm.get('title')):   # 제목 줄이 없으면 맨 앞 설정의 제목을 맨 위에
                content.insert(0, bld.para(f'<w:r><w:t xml:space="preserve">{x(title)}</w:t></w:r>', sid['title']) + sub)
        slots = {name: bld.slot(b) for name, b in slot_blocks.items()}
        roles = {}
        for m in re.finditer(r'\{\{\s*signoff:\s*([^{}]+?)\s*\}\}', TF.plain_text(doc_xml)):
            key = FM_ALIAS.get(m[1], m[1])
            items = [v.strip() for v in fm_text(fm.get(key) or raw_fm.get(m[1])).split(',') if v.strip()]
            roles[m[1]] = bld.signoff(items) if items else None
        toc_used = any(b['kind'] == 'toc' for b in blocks) or (framed and TF.uses([doc_xml], 'toc'))
        frag = {'toc': bld.toc_field('toc') if framed else None}
        numbering, bullet = numbering_xml(tpl_text('word/numbering.xml'), bld.list_nums)

        def ours(xml):   # 우리 글머리표의 numId — 양식에 번호 정의가 있으면 다른 번호로
            return xml.replace('<w:numId w:val="1"/>', f'<w:numId w:val="{bullet}"/>') if bullet != 1 else xml
        body_xml = ours(''.join(content))

        def render(key):
            if key == 'body':
                return body_xml
            if key == 'toc':
                return frag['toc']
            if key.startswith('slot:'):
                got = slots.get(key[5:].strip())
                return ours(got) if got else None
            if key.startswith('signoff:'):
                return roles.get(key[8:].strip())
            return None
        filler = TF.Filler(vals, render, lang)
        filled_parts = {}
        if framed:
            document = filler.fill(doc_xml)
        else:
            # 쪽 설정 — 양식의 것, 없으면 Lectern 의 보고서 양식 (첫 쪽은 머리 없이)
            if not sect:
                hid = bld.rel('header', 'header1.xml')
                fid = bld.rel('footer', 'footer1.xml')
                sect = (f'<w:sectPr><w:headerReference w:type="default" r:id="{hid}"/><w:footerReference w:type="default" r:id="{fid}"/>'
                        f'<w:footerReference w:type="first" r:id="{fid}"/>'
                        f'<w:pgSz w:w="{A4[0]}" w:h="{A4[1]}"/><w:pgMar w:top="{MARGINS[0]}" w:right="{MARGINS[1]}" w:bottom="{MARGINS[2]}" w:left="{MARGINS[3]}" '
                        'w:header="709" w:footer="567" w:gutter="0"/><w:titlePg/><w:docGrid w:linePitch="360"/></w:sectPr>')
            document = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:document {NS}><w:body>{body_xml}{sect}</w:body></w:document>'
        for n in hf_parts:   # 머리글·바닥글의 {{title}}·{{org}} … — 양식이 쓰면
            filled_parts[n] = filler.fill(tpl_text(n))
        fn = footnotes_xml(tpl_text('word/footnotes.xml'), bld.fn_xml)
        fn_rels = tpl_text('word/_rels/footnotes.xml.rels')
        if bld.note_rels:
            items = ''.join(f'<Relationship Id="{rid}" Type="{REL["link"]}" Target="{x(t)}" TargetMode="External"/>' for rid, t in bld.note_rels)
            fn_rels = (fn_rels.replace('</Relationships>', items + '</Relationships>') if fn_rels
                       else f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="{RELS}">{items}</Relationships>')
        # 관계: 양식의 것을 지키고 우리 것을 더한다
        rels_xml = tpl_text('word/_rels/document.xml.rels')
        have = set(re.findall(r'Type="([^"]+)"', rels_xml))
        rel_list = list(bld.rels)
        for kind, target in (('styles', 'styles.xml'), ('numbering', 'numbering.xml'), ('footnotes', 'footnotes.xml'), ('settings', 'settings.xml')):
            if REL[kind] not in have:
                rel_list.append((f'rIdLecS{kind}', kind, target, False))
        rel_items = ''.join(f'<Relationship Id="{rid}" Type="{REL[kind]}" Target="{x(target)}"' + (' TargetMode="External"' if ext else '') + '/>'
                            for rid, kind, target, ext in rel_list)
        if rels_xml:
            rels_xml = rels_xml.replace('</Relationships>', rel_items + '</Relationships>')
        else:
            rels_xml = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="{RELS}">{rel_items}</Relationships>'
        settings = tpl_text('word/settings.xml') or (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:settings {NS}><w:defaultTabStop w:val="800"/>'
                                                      '<w:characterSpacingControl w:val="doNotCompress"/><w:compat><w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="15"/></w:compat></w:settings>')
        if toc_used and '<w:updateFields' not in settings:   # 목차 필드 — 열 때 Word 가 채우게
            settings = re.sub(r'(<w:settings\b[^>]*>)', r'\1<w:updateFields w:val="true"/>', settings, count=1)
        types = tpl_text('[Content_Types].xml')
        if not types:
            types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                     '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
                     f'<Override PartName="/word/document.xml" ContentType="{CT}.document.main+xml"/></Types>')
        types = types.replace(f'{CT}.template.main+xml', f'{CT}.document.main+xml')   # .dotx 양식 → 문서
        for ext, ctype in (('png', 'image/png'), ('jpeg', 'image/jpeg'), ('gif', 'image/gif'), ('bmp', 'image/bmp')):
            if f'Extension="{ext}"' not in types:
                types = types.replace('</Types>', f'<Default Extension="{ext}" ContentType="{ctype}"/></Types>')
        for part, ctype in (('/word/styles.xml', f'{CT}.styles+xml'), ('/word/numbering.xml', f'{CT}.numbering+xml'), ('/word/footnotes.xml', f'{CT}.footnotes+xml'),
                            ('/word/settings.xml', f'{CT}.settings+xml'), ('/word/header1.xml', f'{CT}.header+xml'), ('/word/footer1.xml', f'{CT}.footer+xml'),
                            ('/docProps/core.xml', 'application/vnd.openxmlformats-package.core-properties+xml')):
            if f'PartName="{part}"' not in types and (part not in ('/word/header1.xml', '/word/footer1.xml') or not tpl):
                types = types.replace('</Types>', f'<Override PartName="{part}" ContentType="{ctype}"/></Types>')
        root_rels = tpl_text('_rels/.rels') or (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="{RELS}">'
                                                 f'<Relationship Id="rId1" Type="{REL["doc"]}" Target="word/document.xml"/>'
                                                 f'<Relationship Id="rId2" Type="{REL["core"]}" Target="docProps/core.xml"/></Relationships>')
        out_path = Path(out_path)
        written = {'[Content_Types].xml', '_rels/.rels', 'word/document.xml', 'word/_rels/document.xml.rels', 'word/styles.xml', 'word/numbering.xml',
                   'word/footnotes.xml', 'word/settings.xml', 'docProps/core.xml', 'word/_rels/footnotes.xml.rels', *filled_parts}
        with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('[Content_Types].xml', types)
            z.writestr('_rels/.rels', root_rels)
            z.writestr('word/document.xml', document)
            z.writestr('word/_rels/document.xml.rels', rels_xml)
            z.writestr('word/styles.xml', styles)
            z.writestr('word/numbering.xml', numbering)
            z.writestr('word/footnotes.xml', fn)
            if fn_rels:
                z.writestr('word/_rels/footnotes.xml.rels', fn_rels)
            z.writestr('word/settings.xml', settings)
            z.writestr('docProps/core.xml', core_xml(str(title), author))
            for n, xml in filled_parts.items():
                z.writestr(n, xml)
            if not tpl:
                z.writestr('word/header1.xml', header_footer('header', str(title)))
                z.writestr('word/footer1.xml', header_footer('footer', str(title)))
            for name, data in bld.media:
                z.writestr(f'word/media/{name}', data)
            if tpl:   # 양식의 나머지 (테마·글꼴 표·그림·문서 정보 …) 그대로 — 관계가 가리키는 파일이 빠지지 않게
                for name in names:
                    if name not in written and not name.endswith('/'):
                        z.writestr(name, tpl.read(name))
        report = {'docx': str(out_path), 'figures': bld.figures, 'notes': bld.report_notes}
    if tpl:
        tpl.close()
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description='Lectern md → docx')
    ap.add_argument('md', nargs='?')
    ap.add_argument('--out')
    ap.add_argument('--template', help='양식 — .dotx·.docx 경로, 또는 Lectern 양식의 id·이름 (--templates 로 목록)')   # i18n-ok
    ap.add_argument('--lang', choices=['ko', 'en'])
    ap.add_argument('--templates', action='store_true', help='Lectern 양식 목록을 JSON 으로')   # i18n-ok
    a = ap.parse_args(argv)
    if a.templates:
        print(json.dumps(template_index(), ensure_ascii=False, indent=1))
        return 0
    if not a.md or not a.out:
        ap.error('md 와 --out 이 필요합니다')   # i18n-ok
    report = build(a.md, a.out, a.template, a.lang)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
