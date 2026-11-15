"""Lectern 의 Word 양식 18가지를 만든다 (D147) — skills/lectern-to-docx/templates/<id>.dotx 와 index.json.

    python tools/make_docx_templates.py

지면 틀(web/layouts/<id>.html)과 같은 id·이름·묶음으로, 같은 문서를 Word 로 내도 같은 꼴이 되게 한다. 양식은 손으로 만든 파일이 아니라
이 스크립트가 짓는다 — 고칠 때는 여기를 고치고 다시 돌린다 (tests/test_docx_templates.py 가 파일과 이 스크립트가 같은지 본다).
양식 안의 자리({{title}}·{{body}}·{{slot:요약}}·{{signoff:결재}}·{{toc}}·{{if:키}})는 build_docx 가 채운다 (template_fill.py).
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills' / 'lectern-to-docx' / 'scripts'
OUT = ROOT / 'skills' / 'lectern-to-docx' / 'templates'
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))
import build_docx as B  # noqa: E402
from lectern import layouts  # noqa: E402

CT = 'application/vnd.openxmlformats-officedocument.wordprocessingml'
NS = B.NS
A4, LETTER, BOOK = (11906, 16838), (12240, 15840), (8617, 12756)
PAGE_NAMES = {A4: 'A4', LETTER: 'Letter', BOOK: '152×225mm'}   # index.json 의 쪽 — 틀의 것(웹 장문은 쪽 없이)이 아니라 이 양식의 종이


def mm(v):
    return round(v * 56.6929)


def esc(t):
    return B.x(t)


# ---- 문단과 표 (Word 의 요소 차례를 지킨다: pPr — keepNext, pageBreakBefore, pBdr, shd, tabs, spacing, ind, jc / rPr — rFonts, b, i, caps, color, sz, shd)

def r(text, b=False, i=False, size=None, color=None, font=None, caps=False, spacing=None):
    props = ''
    if font:
        props += f'<w:rFonts w:ascii="{font}" w:hAnsi="{font}" w:eastAsia="{font}" w:cs="{font}"/>'
    if b:
        props += '<w:b/><w:bCs/>'
    if i:
        props += '<w:i/><w:iCs/>'
    if caps:
        props += '<w:caps/>'
    if color:
        props += f'<w:color w:val="{color}"/>'
    if spacing:
        props += f'<w:spacing w:val="{spacing}"/>'
    if size:
        props += f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>'
    rpr = f'<w:rPr>{props}</w:rPr>' if props else ''
    parts = text.split('\t')
    inner = '<w:tab/>'.join(f'<w:t xml:space="preserve">{esc(t)}</w:t>' for t in parts)
    return f'<w:r>{rpr}{inner}</w:r>'


def field(instr, shown='1', **kw):
    rr = r('', **kw).replace('<w:t xml:space="preserve"></w:t>', '')
    rpr = re.search(r'<w:rPr>.*?</w:rPr>', rr)
    rpr = rpr[0] if rpr else ''
    return (f'<w:r>{rpr}<w:fldChar w:fldCharType="begin"/></w:r><w:r>{rpr}<w:instrText xml:space="preserve"> {instr} </w:instrText></w:r>'
            f'<w:r>{rpr}<w:fldChar w:fldCharType="separate"/></w:r><w:r>{rpr}<w:t>{shown}</w:t></w:r><w:r>{rpr}<w:fldChar w:fldCharType="end"/></w:r>')


def p(*runs, style=None, keep=False, page=False, border=None, shd=None, tabs=None, before=None, after=None, line=None, ind=None, jc=None, sect=None):
    pp = ''
    if style:
        pp += f'<w:pStyle w:val="{style}"/>'
    if keep:
        pp += '<w:keepNext/>'
    if page:
        pp += '<w:pageBreakBefore/>'
    if border:
        pp += f'<w:pBdr>{border}</w:pBdr>'
    if shd:
        pp += f'<w:shd w:val="clear" w:color="auto" w:fill="{shd}"/>'
    if tabs:
        pp += '<w:tabs>' + ''.join(f'<w:tab w:val="{k}" w:pos="{v}"/>' for k, v in tabs) + '</w:tabs>'
    if before is not None or after is not None or line is not None:
        sp = ''
        if before is not None:
            sp += f' w:before="{before}"'
        if after is not None:
            sp += f' w:after="{after}"'
        if line is not None:
            sp += f' w:line="{line}" w:lineRule="auto"'
        pp += f'<w:spacing{sp}/>'
    pp += f'<w:ind {ind}/>' if ind else '<w:ind w:firstLine="0"/>'
    if jc:
        pp += f'<w:jc w:val="{jc}"/>'
    if sect:
        pp += sect
    return f'<w:p><w:pPr>{pp}</w:pPr>{"".join(runs)}</w:p>'


def rule(color='333333', sz=8, space=4, side='bottom'):
    return f'<w:{side} w:val="single" w:sz="{sz}" w:space="{space}" w:color="{color}"/>'


def cell(content, width, fill=None, borders=None, valign=None, margins=None):
    tc = f'<w:tcW w:w="{width}" w:type="dxa"/>'
    if borders is not None:
        tc += f'<w:tcBorders>{borders}</w:tcBorders>'
    if fill:
        tc += f'<w:shd w:val="clear" w:color="auto" w:fill="{fill}"/>'
    if margins:
        tc += '<w:tcMar>' + ''.join(f'<w:{k} w:w="{v}" w:type="dxa"/>' for k, v in margins.items()) + '</w:tcMar>'
    if valign:
        tc += f'<w:vAlign w:val="{valign}"/>'
    return f'<w:tc><w:tcPr>{tc}</w:tcPr>{content}</w:tc>'


def table(rows, widths, borders='', jc=None, height=None, cant_split=True):
    """rows: [[셀 XML …]] — 셀은 cell() 로"""
    total = sum(widths)
    tp = f'<w:tblW w:w="{total}" w:type="dxa"/>'
    if jc:
        tp += f'<w:jc w:val="{jc}"/>'
    tp += f'<w:tblBorders>{borders}</w:tblBorders>' if borders else '<w:tblBorders><w:top w:val="nil"/><w:left w:val="nil"/><w:bottom w:val="nil"/><w:right w:val="nil"/><w:insideH w:val="nil"/><w:insideV w:val="nil"/></w:tblBorders>'
    tp += '<w:tblLayout w:type="fixed"/><w:tblCellMar><w:top w:w="60" w:type="dxa"/><w:left w:w="120" w:type="dxa"/><w:bottom w:w="60" w:type="dxa"/><w:right w:w="120" w:type="dxa"/></w:tblCellMar>'
    grid = ''.join(f'<w:gridCol w:w="{w}"/>' for w in widths)
    trs = ''
    for row in rows:
        trpr = ('<w:cantSplit/>' if cant_split else '') + (f'<w:trHeight w:val="{height}"/>' if height else '')
        trs += f'<w:tr><w:trPr>{trpr}</w:trPr>{"".join(row)}</w:tr>'
    return f'<w:tbl><w:tblPr>{tp}</w:tblPr><w:tblGrid>{grid}</w:tblGrid>{trs}</w:tbl>'


def box(paras, width, color='1B3A5C', fill='F6F8FA', label=None, label_fill=None, top=True, left=False):
    """한 칸 상자 — 자리({{slot:…}})를 담는다. label 이 있으면 이름 줄"""
    if left:
        b = f'<w:top w:val="nil"/><w:left w:val="single" w:sz="24" w:space="0" w:color="{color}"/><w:bottom w:val="nil"/><w:right w:val="nil"/>'
    else:
        b = (f'<w:top w:val="single" w:sz="{18 if top else 6}" w:space="0" w:color="{color}"/><w:left w:val="single" w:sz="4" w:space="0" w:color="C8CDD3"/>'
             f'<w:bottom w:val="single" w:sz="4" w:space="0" w:color="C8CDD3"/><w:right w:val="single" w:sz="4" w:space="0" w:color="C8CDD3"/>')
    rows = []
    if label:
        rows.append([cell(label, width, fill=label_fill or fill, borders=b)])
    rows.append([cell(paras, width, fill=fill, borders=b, margins={'top': 120, 'left': 200, 'bottom': 120, 'right': 200})])
    return table(rows, [width], cant_split=False) + p(after=0, line=120)


def page_break():
    return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


def sect_xml(spec, refs, kind=None, cols=1, title_pg=False, restart=False):
    """구역 설정 — refs: [('header'|'footer', 'default'|'first'|'even', rId)]"""
    w, h = spec['page']
    t, rt, bt, lt = spec['margins']
    hd, ft = spec.get('hf', (mm(12), mm(10)))
    x = ''.join(f'<w:{k}Reference w:type="{typ}" r:id="{rid}"/>' for k, typ, rid in refs if k == 'header')
    x += ''.join(f'<w:{k}Reference w:type="{typ}" r:id="{rid}"/>' for k, typ, rid in refs if k == 'footer')
    if kind:
        x += f'<w:type w:val="{kind}"/>'
    x += f'<w:pgSz w:w="{w}" w:h="{h}"/><w:pgMar w:top="{t}" w:right="{rt}" w:bottom="{bt}" w:left="{lt}" w:header="{hd}" w:footer="{ft}" w:gutter="0"/>'
    if restart:
        x += '<w:pgNumType w:start="1"/>'
    x += f'<w:cols w:num="{cols}" w:space="{mm(7)}"/>' if cols > 1 else '<w:cols w:space="425"/>'
    if title_pg:
        x += '<w:titlePg/>'
    x += '<w:docGrid w:linePitch="360"/>'
    return f'<w:sectPr>{x}</w:sectPr>'


def text_w(spec):
    return spec['page'][0] - spec['margins'][1] - spec['margins'][3]


def v(key):
    return '{{' + key + '}}'


# ---- 머리글·바닥글

def hf_xml(kind, paras):
    tag = 'hdr' if kind == 'header' else 'ftr'
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:{tag} {NS}>{paras}</w:{tag}>'


def page_no(style='Footer', fmt='- {} -', jc='center', **kw):
    a, b = fmt.split('{}')
    return p(r(a, **kw), field('PAGE', **kw), r(b, **kw), style=style, jc=jc)


# ---- 양식 18가지 ---------------------------------------------------------------------------------------------

SPECS = {}


def spec(fn):
    SPECS[fn.__name__.replace('_', '-')] = fn
    return fn


@spec
def gov_report():
    s = {'page': A4, 'margins': (mm(20), mm(20), mm(15), mm(20)),
         'theme': {'body_font': '함초롬바탕', 'body_east': '함초롬바탕', 'body_size': 26, 'line': 360, 'head_color': '000000',
                   'head_sizes': {1: 30, 2: 28, 3: 26, 4: 26, 5: 26, 6: 26}, 'th_fill': 'D9E1F2', 'rule': '000000', 'cell_size': 22, 'caption_jc': 'center'},
         'desc': '정부·공공기관 보고서 — 위에 굵은 두 줄 사이의 제목 상자, 오른쪽에 날짜·부서·작성자, 요약 상자, 함초롬바탕 13pt 본문(□ ○ - ※ 문단). 바닥에 쪽 번호',
         'desc_en': 'A government report — a title box between heavy double rules, date, department and author on the right, a summary box, 13 pt serif body. Page numbers at the foot'}
    w = text_w(s)
    dbl = '<w:top w:val="double" w:sz="12" w:space="0" w:color="000000"/><w:bottom w:val="double" w:sz="12" w:space="0" w:color="000000"/><w:left w:val="nil"/><w:right w:val="nil"/>'
    title = table([[cell(p(r(v('title'), b=True, size=36, font='맑은 고딕'), jc='center', before=120, after=120), w, borders=dbl, valign='center')]], [w])
    s['body'] = (title + p(r(v('date:dot')), jc='right', before=120, after=0)
                 + p(r('{{if:dept}}' + v('dept') + ' ' + v('author')), jc='right', after=240)
                 + box(p(r('{{if:slot:요약}}{{t:요 약|Summary}}', b=True, size=22, font='맑은 고딕'), after=60) + p(r(v('slot:요약'))), w, color='000000', fill='FFFFFF')
                 + p(r(v('body'))))
    s['footer'] = {'default': page_no()}
    return s


@spec
def one_page():
    s = {'page': A4, 'margins': (mm(15), mm(16), mm(14), mm(16)),
         'theme': {'body_font': '맑은 고딕', 'body_east': '맑은 고딕', 'body_size': 20, 'line': 276, 'after': 80, 'jc': 'left', 'head_color': '0B2E59',
                   'head_sizes': {1: 24, 2: 22, 3: 21, 4: 20, 5: 20, 6: 20}, 'th_fill': '0B2E59', 'th_color': 'FFFFFF', 'rule': '0B2E59', 'cell_size': 18},
         'desc': '경영진 보고용 한 장 — 위에 제목과 결재란(맨 앞 설정 결재: [담당, 팀장, 본부장]), 결론 상자, 촘촘한 맑은 고딕 10pt 본문',
         'desc_en': 'A one-page brief for executives — title and sign-off boxes on top (front matter 결재: [...]), a conclusion box, a compact 10 pt sans body'}
    w = text_w(s)
    left = (p(r(v('title'), b=True, size=32, color='0B2E59'), after=60)
            + p(r(v('date:dot'), color='555555', size=18), r('  ' + v('dept') + '  ' + v('author'), color='555555', size=18), after=0))
    top = table([[cell(left, w - mm(62), valign='bottom'), cell(p(r(v('signoff:결재'))), mm(62), valign='top')]], [w - mm(62), mm(62)],
                borders='<w:top w:val="nil"/><w:left w:val="nil"/><w:bottom w:val="single" w:sz="18" w:space="0" w:color="0B2E59"/><w:right w:val="nil"/><w:insideH w:val="nil"/><w:insideV w:val="nil"/>')
    s['body'] = (top + p(after=120)
                 + box(p(r('{{if:slot:결론}}{{t:결론|Conclusion}}', b=True, color='0B2E59'), after=40) + p(r(v('slot:결론'))), w, color='0B2E59', fill='EEF3FA', left=True)
                 + p(r(v('body'))))
    s['footer'] = {}
    return s


@spec
def official_letter():
    s = {'page': A4, 'margins': (mm(30), mm(15), mm(15), mm(20)),
         'theme': {'body_font': '함초롬바탕', 'body_east': '함초롬바탕', 'body_size': 24, 'line': 336, 'jc': 'both', 'head_color': '000000',
                   'head_sizes': {1: 24, 2: 24, 3: 24, 4: 24, 5: 24, 6: 24}, 'th_fill': 'EDEDED', 'rule': '000000'},
         'desc': '공문(기안문) — 위에 기관 이름, 수신·(경유)·제목 줄, 본문 끝의 "끝.", 가운데 발신 명의, 아래에 기안자·검토자·결재권자와 시행·접수·주소·전화. 여백 위 30·아래 15·왼쪽 20·오른쪽 15mm',
         'desc_en': 'An official letter — organisation name on top, recipient, via and subject lines, "끝." after the body, the sender in the centre, and drafter, reviewer, approver, enforcement, receipt and contact at the bottom'}
    w = text_w(s)
    lab = lambda t: r(t, b=True)   # noqa: E731
    s['body'] = (p(r(v('org'), b=True, size=40, font='맑은 고딕'), jc='center', after=240)
                 + p(lab('수신  '), r(v("수신|'수신자 참조'")), after=40)
                 + p(r('{{if:경유}}'), lab('(경유)  '), r(v('경유')), after=40)
                 + p(lab('제목  '), r(v('title'), b=True), after=120, border=rule('000000', 12, 6))
                 + p(r(v('body')))
                 + p(r('끝.'), after=480)
                 + p(r(v('발신|org'), b=True, size=36, font='맑은 고딕'), jc='center', after=360, keep=True)
                 + table([[cell(p(r('기안자 ' + v('기안자') + '    검토자 ' + v('검토자') + '    결재권자 ' + v('결재권자'), size=20), keep=True), w)],
                          [cell(p(r('시행 ' + v('시행') + '    접수 ' + v('접수'), size=20), keep=True), w)],
                          [cell(p(r('우 ' + v('주소') + '  /  전화 ' + v('전화') + '  /  전자우편 ' + v('전자우편') + '  /  ' + v("공개구분|'공개'"), size=18)), w)]],
                         [w], borders=f'<w:top w:val="single" w:sz="12" w:space="0" w:color="000000"/><w:left w:val="nil"/><w:bottom w:val="single" w:sz="12" w:space="0" w:color="000000"/><w:right w:val="nil"/><w:insideH w:val="single" w:sz="4" w:space="0" w:color="999999"/><w:insideV w:val="nil"/>'))
    s['footer'] = {}
    return s


@spec
def press_release():
    s = {'page': A4, 'margins': (mm(18), mm(20), mm(18), mm(20)),
         'theme': {'body_font': '맑은 고딕', 'body_east': '맑은 고딕', 'body_size': 22, 'line': 312, 'head_color': '1F4E79', 'th_fill': '1F4E79', 'th_color': 'FFFFFF'},
         'desc': '보도자료 — 위에 "보도자료" 띠와 기관, 보도·배포 일시 표, 큰 제목과 부제(박스글 자리 부제), 본문, 끝에 담당 부서·담당자·연락처',
         'desc_en': 'A press release — a "press release" banner with the organisation, embargo and release times, a large title and subhead, the body, and the contact at the end'}
    w = text_w(s)
    banner = table([[cell(p(r('{{t:보도자료|Press release}}', b=True, size=44, color='FFFFFF', font='맑은 고딕')), w // 2, fill='1F4E79', valign='center'),
                     cell(p(r(v('org'), b=True, size=24, color='FFFFFF'), jc='right'), w - w // 2, fill='1F4E79', valign='center')]], [w // 2, w - w // 2], height=900)
    info = table([[cell(p(r('{{t:보도 일시|Embargo}}', b=True, size=18)), mm(30), fill='EAF0F7'), cell(p(r(v('보도일시|date:dot'), size=18)), w - mm(30))],
                  [cell(p(r('{{t:배포 일시|Released}}', b=True, size=18)), mm(30), fill='EAF0F7'), cell(p(r(v('배포일시|date:dot'), size=18)), w - mm(30))]],
                 [mm(30), w - mm(30)], borders='<w:top w:val="single" w:sz="4" w:space="0" w:color="9DB2CC"/><w:left w:val="nil"/><w:bottom w:val="single" w:sz="4" w:space="0" w:color="9DB2CC"/><w:right w:val="nil"/><w:insideH w:val="single" w:sz="4" w:space="0" w:color="9DB2CC"/><w:insideV w:val="nil"/>')
    s['body'] = (banner + p(after=80) + info
                 + p(r(v('title'), b=True, size=40, color='111111'), jc='center', before=360, after=120)
                 + p(r('{{if:subtitle}}- ' + v('subtitle') + ' -', size=24, color='1F4E79'), jc='center', after=240)
                 + box(p(r('{{if:slot:부제}}' + v('slot:부제'))), w, color='1F4E79', fill='EAF0F7', left=True)
                 + p(r(v('body')))
                 + table([[cell(p(r('{{t:담당 부서|Department}} ' + v('dept') + '   {{t:담당자|Contact}} ' + v('담당자|author') + '   {{t:연락처|Phone}} ' + v('연락처'), size=18, color='333333')), w, fill='F2F4F7')]], [w]))
    s['footer'] = {'default': page_no()}
    return s


@spec
def minutes():
    s = {'page': A4, 'margins': (mm(20), mm(20), mm(18), mm(20)),
         'theme': {'body_font': '맑은 고딕', 'body_east': '맑은 고딕', 'body_size': 21, 'line': 300, 'jc': 'left', 'head_color': '333333',
                   'head_sizes': {1: 24, 2: 22, 3: 21, 4: 21, 5: 21, 6: 21}, 'th_fill': 'EDEFF2'},
         'desc': '회의록 — "회 의 록" 제목, 회의명·일시·장소·참석자·작성자 표, 그 아래 안건과 결정. 맑은 고딕 10.5pt',
         'desc_en': 'Minutes — a "minutes" heading, a table of meeting, date and time, place, attendees and recorder, then agenda and decisions'}
    w = text_w(s)
    k = mm(28)
    grid = '<w:top w:val="single" w:sz="12" w:space="0" w:color="333333"/><w:left w:val="nil"/><w:bottom w:val="single" w:sz="12" w:space="0" w:color="333333"/><w:right w:val="nil"/><w:insideH w:val="single" w:sz="4" w:space="0" w:color="BBBBBB"/><w:insideV w:val="single" w:sz="4" w:space="0" w:color="BBBBBB"/>'

    def row(label, value, cond=None):
        lead = '{{if:%s}}' % cond if cond else ''
        return [cell(p(r(lead + label, b=True)), k, fill='F3F4F6'), cell(p(r(value)), w - k)]
    info = table([row('{{t:회의명|Meeting}}', v('title')), row('{{t:일시|Date}}', v('date:long') + ' ' + v('시간')), row('{{t:장소|Place}}', v('장소'), '장소'),
                  row('{{t:참석자|Attendees}}', v('참석자'), '참석자'), row('{{t:작성자|Recorder}}', v('author'), 'author')], [k, w - k], borders=grid)
    s['body'] = (p(r('{{t:회 의 록|Minutes}}', b=True, size=40, spacing=40), jc='center', after=240) + info + p(after=200) + p(r(v('body'))))
    s['footer'] = {'default': page_no()}
    return s


@spec
def research_report():
    s = {'page': A4, 'margins': (mm(25), mm(22), mm(22), mm(25)),
         'theme': {'body_font': '함초롬바탕', 'body_east': '함초롬바탕', 'body_size': 21, 'line': 300, 'head_color': '0F2D52', 'h1_page': True,
                   'h1_rule': '0F2D52', 'head_sizes': {1: 32, 2: 26, 3: 23, 4: 21, 5: 21, 6: 21}, 'th_fill': '0F2D52', 'th_color': 'FFFFFF', 'rule': '0F2D52'},
         'desc': '연구기관 보고서 — 표지(보고서 번호·제목·부제·연구진·기관·날짜), 요약 쪽(박스글 자리 요약), 차례 쪽, 큰 절마다 새 쪽, 쪽 머리에 보고서 제목',
         'desc_en': 'A research report — a cover (number, title, subtitle, authors, organisation, date), a summary page, a contents page, each chapter on a new page, the title in the header'}
    w = text_w(s)
    cover = (p(before=mm(40) * 1, after=0)
             + p(r('{{if:number}}' + v('number'), b=True, size=22, color='0F2D52'), after=600)
             + p(r(v('title'), b=True, size=56, color='0F2D52', font='맑은 고딕'), after=200, line=280)
             + p(r('{{if:subtitle}}' + v('subtitle'), size=28, color='333333'), after=mm(60) * 1)
             + p(r('{{if:author}}{{t:연구진|Authors}}  ' + v('author'), size=22), after=120, border=rule('0F2D52', 8, 8, 'top'))
             + p(r(v('org'), b=True, size=28, color='0F2D52'), after=60)
             + p(r(v('date:long'), size=22, color='555555'), sect=sect_xml(s, [], title_pg=False)))
    front = (p(r('{{if:slot:요약}}{{t:요   약|Summary}}', b=True, size=32, color='0F2D52', font='맑은 고딕'), jc='center', after=240, border=rule('0F2D52', 12, 6))
             + p(r('{{if:slot:요약}}' + v('slot:요약')))
             + p(r('{{t:차   례|Contents}}', b=True, size=32, color='0F2D52', font='맑은 고딕'), page=True, jc='center', after=240, border=rule('0F2D52', 12, 6))
             + p(r(v('toc')))
             + p(sect=sect_xml(s, [], kind='nextPage')))
    s['body'] = cover + front + p(r(v('body')))
    s['header'] = {'default': p(r(v('title'), size=16, color='0F2D52'), r('\t' + v('org'), size=16, color='777777'), style='Header', tabs=[('right', w)], border=rule('0F2D52', 4, 4))}
    s['footer'] = {'default': page_no()}
    s['last_sect'] = {'restart': True}
    return s


@spec
def issue_brief():
    s = {'page': A4, 'margins': (mm(18), mm(20), mm(18), mm(20)),
         'theme': {'body_font': '맑은 고딕', 'body_east': '맑은 고딕', 'body_size': 20, 'line': 300, 'jc': 'left', 'head_color': '0E6E6E',
                   'head_sizes': {1: 26, 2: 23, 3: 21, 4: 20, 5: 20, 6: 20}, 'th_fill': '0E6E6E', 'th_color': 'FFFFFF', 'rule': '0E6E6E'},
         'desc': '정책·이슈 브리프 — 위에 기관·시리즈·호수 띠, 제목·부제·작성자, 왼쪽 줄이 있는 핵심 상자(박스글 자리 핵심), 2~4쪽에 맞춘 촘촘한 본문',
         'desc_en': 'An issue brief — an organisation, series and number band, title, subtitle and author, a key points box, a compact body for two to four pages'}
    w = text_w(s)
    band = table([[cell(p(r(v('org'), b=True, color='FFFFFF', size=20)), w // 2, fill='0E6E6E', valign='center'),
                   cell(p(r(v("series|t:이슈 브리프|Issue brief") + ' ' + v('number'), color='FFFFFF', size=20), jc='right'), w - w // 2, fill='0E6E6E', valign='center')]], [w // 2, w - w // 2], height=520)
    s['body'] = (band + p(r(v('title'), b=True, size=44, color='0E3B3B'), before=240, after=80)
                 + p(r('{{if:subtitle}}' + v('subtitle'), size=24, color='0E6E6E'), after=80)
                 + p(r(v('author') + '  ' + v('date:dot'), size=18, color='666666'), after=200, border=rule('0E6E6E', 8, 6))
                 + box(p(r('{{if:slot:핵심}}{{t:핵심|Key points}}', b=True, color='0E6E6E'), after=40) + p(r(v('slot:핵심'))), w, color='0E6E6E', fill='EEF7F7', left=True)
                 + p(r(v('body'))))
    s['footer'] = {'default': page_no(fmt='{}', jc='right')}
    return s


@spec
def paper_2col():
    s = {'page': A4, 'margins': (mm(20), mm(18), mm(20), mm(18)),
         'theme': {'body_font': 'Times New Roman', 'body_east': '바탕', 'body_size': 19, 'line': 252, 'after': 60, 'head_color': '000000', 'h_center': True,
                   'head_sizes': {1: 21, 2: 20, 3: 19, 4: 19, 5: 19, 6: 19}, 'title_size': 34, 'th_fill': 'FFFFFF', 'rule': '000000', 'cell_size': 16,
                   'caption_jc': 'center', 'head_font': 'Times New Roman', 'head_east': '바탕', 'indent': 200},
         'desc': '학술 논문 2단 — 가운데 제목·저자·소속, 한 단의 초록(박스글 자리 초록)과 주제어, 그 아래 두 단의 10pt 본문, 가운데 맞춘 작은 캡션',
         'desc_en': 'A two-column journal paper — centred title, authors and affiliation, a full-width abstract and keywords, then a two-column 10 pt body'}
    w = text_w(s)
    s['body'] = (p(r(v('title'), b=True, size=34), jc='center', after=160)
                 + p(r(v('author'), size=22), jc='center', after=40)
                 + p(r('{{if:affiliation}}' + v('affiliation'), i=True, size=20), jc='center', after=240)
                 + p(r('{{if:slot:초록}}{{t:초록|Abstract}}', b=True, size=19), after=40, ind=f'w:left="{mm(8)}" w:right="{mm(8)}" w:firstLine="0"')
                 + p(r('{{if:slot:초록}}' + v('slot:초록')), ind=f'w:left="{mm(8)}" w:right="{mm(8)}" w:firstLine="0"')
                 + p(r('{{if:keywords}}'), r('{{t:주제어|Keywords}} — ', b=True, size=18), r(v('keywords'), size=18), after=240, ind=f'w:left="{mm(8)}" w:right="{mm(8)}" w:firstLine="0"',
                     sect=sect_xml(s, [], kind='continuous'))
                 + p(r(v('body'))))
    s['footer'] = {'default': page_no(fmt='{}')}
    s['last_sect'] = {'kind': 'continuous', 'cols': 2}
    return s


@spec
def manuscript():
    s = {'page': LETTER, 'margins': (1440, 1440, 1440, 1440),
         'theme': {'body_font': 'Times New Roman', 'body_east': '바탕', 'body_size': 24, 'line': 480, 'after': 0, 'jc': 'left', 'indent': 720,
                   'head_color': '000000', 'head_sizes': {1: 24, 2: 24, 3: 24, 4: 24, 5: 24, 6: 24}, 'h_center': True, 'head_font': 'Times New Roman',
                   'head_east': '바탕', 'title_size': 24, 'th_fill': 'FFFFFF', 'rule': '000000', 'cell_size': 22},
         'desc': '투고 원고 — Letter, 12pt 두 줄 간격, 첫 줄 들여쓰기, 머리에 짧은 제목과 쪽 번호, 제목 쪽(제목·저자·소속), 초록 쪽, 본문',
         'desc_en': 'A manuscript for submission — Letter, 12 pt double spacing, first-line indents, a running head with page numbers, a title page, an abstract page, then the body'}
    s['body'] = (p(before=2880, after=0) + p(r(v('title'), b=True), jc='center', after=240)
                 + p(r(v('author')), jc='center') + p(r('{{if:affiliation}}' + v('affiliation')), jc='center') + p(r(v('date:en')), jc='center')
                 + p(r('{{if:slot:초록}}{{t:초록|Abstract}}', b=True), jc='center', page=True)
                 + p(r('{{if:slot:초록}}' + v('slot:초록')))
                 + p(r(v('title'), b=True), jc='center', page=True)
                 + p(r(v('body'))))
    w = text_w(s)
    s['header'] = {'default': p(r(v('short_title|title'), caps=True, size=20), r('\t'), field('PAGE', size=20), style='Header', tabs=[('right', w)])}
    s['footer'] = {}
    return s


@spec
def white_paper():
    s = {'page': A4, 'margins': (mm(22), mm(22), mm(20), mm(22)),
         'theme': {'body_font': 'Georgia', 'body_east': '맑은 고딕', 'body_size': 21, 'line': 312, 'jc': 'left', 'head_color': '0B5345', 'h1_rule': '0B5345',
                   'head_sizes': {1: 30, 2: 25, 3: 22, 4: 21, 5: 21, 6: 21}, 'th_fill': '0B5345', 'th_color': 'FFFFFF', 'rule': '0B5345'},
         'desc': '백서 — 표지(기관·제목·부제·작성자·날짜, 짙은 초록 띠), 요약 상자(박스글 자리 요약), 쪽 머리에 제목과 기관',
         'desc_en': 'A white paper — a cover with a dark green band (organisation, title, subtitle, author, date), a summary box, the title and organisation in the header'}
    w = text_w(s)
    cover = (table([[cell(p(r(v('org'), b=True, color='FFFFFF', size=22, caps=True)), w, fill='0B5345', valign='center')]], [w], height=700)
             + p(before=mm(50) * 1, after=0)
             + p(r(v('title'), b=True, size=60, color='0B5345'), after=200, line=280)
             + p(r('{{if:subtitle}}' + v('subtitle'), size=28, color='444444'), after=mm(70) * 1)
             + p(r(v('author'), b=True, size=22), after=40, border=rule('0B5345', 12, 8, 'top'))
             + p(r(v('date:long'), size=20, color='666666'), sect=sect_xml(s, [])))
    s['body'] = (cover + box(p(r('{{if:slot:요약}}{{t:요약|Summary}}', b=True, color='0B5345', size=24), after=80) + p(r(v('slot:요약'))), w, color='0B5345', fill='EFF6F4')
                 + p(r(v('body'))))
    s['header'] = {'default': p(r(v('title'), size=16, color='0B5345'), r('\t' + v('org'), size=16, color='777777'), style='Header', tabs=[('right', w)])}
    s['footer'] = {'default': page_no(fmt='{}', jc='right')}
    s['last_sect'] = {'restart': True}
    return s


@spec
def equity_research():
    s = {'page': A4, 'margins': (mm(15), mm(16), mm(15), mm(16)),
         'theme': {'body_font': '맑은 고딕', 'body_east': '맑은 고딕', 'body_size': 19, 'line': 276, 'after': 80, 'jc': 'left', 'head_color': 'B71C1C',
                   'head_sizes': {1: 22, 2: 21, 3: 20, 4: 19, 5: 19, 6: 19}, 'th_fill': 'B71C1C', 'th_color': 'FFFFFF', 'rule': 'B71C1C', 'cell_size': 17},
         'desc': '증권사 리포트 — 위에 회사·종목코드·업종과 리서치센터, 왼쪽 칸에 투자의견·목표가·현재가·상승여력과 애널리스트, 오른쪽에 제목과 핵심 수치(박스글 자리), 끝에 면책(박스글 자리)',
         'desc_en': 'An equity research note — company, ticker and sector with the research house on top, a left panel of rating, target and current price, upside and analysts, the title and key figures on the right, a disclaimer at the end'}
    w = text_w(s)
    head = table([[cell(p(r(v('company'), b=True, size=34), r('  ' + v('ticker') + '  ' + v('sector'), size=18, color='666666')), w - mm(60), valign='bottom'),
                   cell(p(r(v('org'), b=True, size=18, color='B71C1C'), jc='right'), mm(60), valign='bottom')]], [w - mm(60), mm(60)],
                 borders='<w:top w:val="nil"/><w:left w:val="nil"/><w:bottom w:val="single" w:sz="18" w:space="0" w:color="B71C1C"/><w:right w:val="nil"/><w:insideH w:val="nil"/><w:insideV w:val="nil"/>')
    lw = mm(52)
    panel = (p(r('{{t:투자의견|Rating}}', size=16, color='FFFFFF'), shd='B71C1C', after=0) + p(r(v("투자의견|'—'"), b=True, size=36, color='FFFFFF'), shd='B71C1C', after=120)
             + p(r('{{if:목표가}}{{t:목표가|Target}}\t' + v('목표가'), size=17), tabs=[('right', lw - 240)], after=20)
             + p(r('{{if:현재가}}{{t:현재가|Price}}\t' + v('현재가'), size=17), tabs=[('right', lw - 240)], after=20)
             + p(r('{{if:상승여력}}{{t:상승여력|Upside}}\t' + v('상승여력'), size=17), tabs=[('right', lw - 240)], after=160)
             + p(r('{{if:author}}{{t:애널리스트|Analysts}}', size=15, color='777777'), after=0) + p(r('{{if:author}}' + v('author'), size=17), after=120)
             + p(r(v('date:dot'), size=15, color='777777')))
    right = p(r(v('title'), b=True, size=34), after=120) + p(r('{{if:slot:핵심 수치}}' + v('slot:핵심 수치')))
    grid = table([[cell(panel, lw, fill='F7F2F2', valign='top'), cell(right, w - lw, valign='top', margins={'left': 300})]], [lw, w - lw])
    s['body'] = (head + p(after=120) + grid + p(after=120) + p(r(v('body')))
                 + box(p(r('{{if:slot:면책}}' + v('slot:면책'), size=15, color='555555')), w, color='999999', fill='F5F5F5', top=False))
    s['footer'] = {'default': page_no(fmt='{}', jc='right', size=16)}
    return s


@spec
def consulting():
    s = {'page': A4, 'margins': (mm(22), mm(22), mm(20), mm(22)),
         'theme': {'body_font': 'Calibri', 'body_east': '맑은 고딕', 'body_size': 21, 'line': 288, 'jc': 'left', 'head_color': '1F3864', 'h1_rule': '1F3864',
                   'head_sizes': {1: 30, 2: 24, 3: 22, 4: 21, 5: 21, 6: 21}, 'th_fill': '1F3864', 'th_color': 'FFFFFF', 'rule': '1F3864'},
         'desc': '컨설팅 보고서 — 표지(고객·제목·부제·회사·날짜), 요약 쪽(박스글 자리 요약), 결론 문장으로 쓰는 제목, 쪽 머리에 회사와 제목',
         'desc_en': 'A consulting report — a cover (client, title, subtitle, firm, date), an executive summary page, action titles, the firm and title in the header'}
    w = text_w(s)
    cover = (p(before=mm(45) * 1, after=0)
             + p(r('{{if:client}}{{t:고객|Prepared for}} ' + v('client'), size=22, color='1F3864', caps=True), after=400)
             + p(r(v('title'), b=True, size=56, color='1F3864'), after=200, line=270)
             + p(r('{{if:subtitle}}' + v('subtitle'), size=28, color='555555'), after=mm(70) * 1, border=rule('1F3864', 24, 12))
             + p(r(v('org'), b=True, size=24), after=40) + p(r(v('date:long'), size=20, color='666666'), sect=sect_xml(s, [])))
    summary = (p(r('{{if:slot:요약}}{{t:요약|Executive summary}}', b=True, size=32, color='1F3864'), after=200, border=rule('1F3864', 8, 4))
               + p(r('{{if:slot:요약}}' + v('slot:요약'))))
    s['body'] = cover + summary + p(r(v('body')))
    s['header'] = {'default': p(r(v('org'), b=True, size=16, color='1F3864'), r('\t' + v('title'), size=16, color='777777'), style='Header', tabs=[('right', w)], border=rule('1F3864', 4, 4))}
    s['footer'] = {'default': page_no(fmt='{}', jc='right')}
    s['last_sect'] = {'restart': True}
    return s


@spec
def proposal():
    s = {'page': A4, 'margins': (mm(22), mm(22), mm(20), mm(22)),
         'theme': {'body_font': '맑은 고딕', 'body_east': '맑은 고딕', 'body_size': 21, 'line': 300, 'jc': 'left', 'head_color': '4A2E7A', 'h1_rule': '4A2E7A',
                   'head_sizes': {1: 30, 2: 25, 3: 22, 4: 21, 5: 21, 6: 21}, 'th_fill': '4A2E7A', 'th_color': 'FFFFFF', 'rule': '4A2E7A'},
         'desc': '제안서 — 표지(고객 귀중·제목·부제·제안사·날짜), 제안 요약(박스글 자리 요약), 목차 쪽, 쪽 머리에 제목',
         'desc_en': 'A proposal — a cover (to the client, title, subtitle, proposer, date), a proposal summary, a contents page, the title in the header'}
    w = text_w(s)
    cover = (p(before=mm(40) * 1, after=0)
             + p(r('{{if:client}}{{t:|To }}' + v('client') + '{{t: 귀중|}}', b=True, size=26, color='4A2E7A'), after=480)
             + p(r(v('title'), b=True, size=56, color='2B1A47'), after=200, line=270)
             + p(r('{{if:subtitle}}' + v('subtitle'), size=28, color='555555'), after=mm(75) * 1)
             + p(r(v('date:long'), size=22), jc='right', after=60) + p(r(v('org'), b=True, size=30, color='4A2E7A'), jc='right', sect=sect_xml(s, [])))
    front = (p(r('{{if:slot:요약}}{{t:제안 요약|Proposal summary}}', b=True, size=30, color='4A2E7A'), after=200, border=rule('4A2E7A', 8, 4))
             + p(r('{{if:slot:요약}}' + v('slot:요약')))
             + p(r('{{t:목   차|Contents}}', b=True, size=30, color='4A2E7A'), page=True, after=200, border=rule('4A2E7A', 8, 4))
             + p(r(v('toc'))) + p(sect=sect_xml(s, [], kind='nextPage')))
    s['body'] = cover + front + p(r(v('body')))
    s['header'] = {'default': p(r(v('title'), size=16, color='4A2E7A'), r('\t' + v('org'), size=16, color='777777'), style='Header', tabs=[('right', w)])}
    s['footer'] = {'default': page_no()}
    s['last_sect'] = {'restart': True}
    return s


@spec
def magazine():
    s = {'page': A4, 'margins': (mm(18), mm(18), mm(18), mm(18)),
         'theme': {'body_font': 'Georgia', 'body_east': '바탕', 'body_size': 20, 'line': 288, 'after': 100, 'head_color': '111111', 'head_font': 'Georgia', 'head_east': '맑은 고딕',
                   'head_sizes': {1: 26, 2: 23, 3: 21, 4: 20, 5: 20, 6: 20}, 'th_fill': 'F1ECE4', 'rule': '8A1C1C', 'caption_color': '8A1C1C', 'quote_rule': '8A1C1C'},
         'desc': '잡지 기사 — 꼬리표(작은 빨간 대문자), 큰 제목과 기울인 부제, 글쓴이·날짜, 굵은 줄 아래 두 단의 본문',
         'desc_en': 'A magazine feature — a small red kicker, a large title and italic standfirst, byline and date, then a two-column body under a heavy rule'}
    s['body'] = (p(r('{{if:kicker}}' + v('kicker'), b=True, caps=True, size=18, color='8A1C1C'), after=80)
                 + p(r(v('title'), b=True, size=64, font='Georgia'), after=120, line=260)
                 + p(r('{{if:subtitle}}' + v('subtitle'), i=True, size=28, color='555555'), after=160)
                 + p(r('{{t:글|By}} ' + v('author') + '  ·  ' + v('date:long'), size=18, color='777777'), after=240, border=rule('111111', 24, 8),
                     sect=sect_xml(s, [], kind='continuous'))
                 + p(r(v('body'))))
    s['footer'] = {'default': page_no(fmt='{}', size=16)}
    s['last_sect'] = {'kind': 'continuous', 'cols': 2}
    return s


@spec
def newsletter():
    s = {'page': A4, 'margins': (mm(15), mm(16), mm(15), mm(16)),
         'theme': {'body_font': '맑은 고딕', 'body_east': '맑은 고딕', 'body_size': 19, 'line': 276, 'after': 80, 'jc': 'left', 'head_color': 'D35400',
                   'head_sizes': {1: 24, 2: 22, 3: 20, 4: 19, 5: 19, 6: 19}, 'th_fill': 'FBEEE6', 'rule': 'D35400', 'cell_size': 17},
         'desc': '뉴스레터 — 위에 시리즈 이름(굵은 주황)과 호수·날짜·기관, 굵은 주황 줄, 제목, 두 단의 촘촘한 본문',
         'desc_en': 'A newsletter — a masthead with the series name in bold orange and the issue, date and organisation, a heavy orange rule, the title, then a compact two-column body'}
    w = text_w(s)
    mast = table([[cell(p(r(v('series|org'), b=True, size=48, color='D35400')), w - mm(60), valign='bottom'),
                   cell(p(r(v('number'), b=True, size=20), jc='right', after=0) + p(r(v('date:dot') + '  ' + v('org'), size=16, color='777777'), jc='right'), mm(60), valign='bottom')]],
                 [w - mm(60), mm(60)], borders='<w:top w:val="nil"/><w:left w:val="nil"/><w:bottom w:val="single" w:sz="36" w:space="0" w:color="D35400"/><w:right w:val="nil"/><w:insideH w:val="nil"/><w:insideV w:val="nil"/>')
    s['body'] = (mast + p(r(v('title'), b=True, size=36), before=200, after=200, sect=sect_xml(s, [], kind='continuous')) + p(r(v('body'))))
    s['footer'] = {'default': page_no(fmt='{}', size=16)}
    s['last_sect'] = {'kind': 'continuous', 'cols': 2}
    return s


@spec
def book():
    s = {'page': BOOK, 'margins': (mm(20), mm(15), mm(20), mm(20)), 'hf': (mm(10), mm(10)),
         'theme': {'body_font': 'Georgia', 'body_east': '바탕', 'body_size': 20, 'line': 324, 'after': 0, 'indent': 400, 'head_color': '222222',
                   'head_font': 'Georgia', 'head_east': '바탕', 'head_sizes': {1: 24, 2: 22, 3: 20, 4: 20, 5: 20, 6: 20}, 'th_fill': 'F3F0EA', 'rule': '555555', 'cell_size': 16},
         'desc': '책 — 152×225mm, 마주 보는 쪽(안쪽 여백이 넓다), 장 시작 쪽(장·제목·부제), 짝수 쪽 머리에 책 이름·홀수 쪽 머리에 장 제목, 첫 줄 들여쓰기',
         'desc_en': 'A book — 152 × 225 mm, facing pages, a chapter opener (chapter, title, subtitle), the book title on even pages and the chapter title on odd pages, first-line indents'}
    s['body'] = (p(before=mm(45) * 1, after=0) + p(r('{{if:chapter}}' + v('chapter'), caps=True, size=20, color='777777', spacing=40), jc='center', after=200)
                 + p(r(v('title'), b=True, size=44, font='Georgia'), jc='center', after=160)
                 + p(r('{{if:subtitle}}' + v('subtitle'), i=True, size=24, color='555555'), jc='center', after=mm(25) * 1)
                 + p(r(v('body'))))
    s['header'] = {'default': p(r(v('chapter|title'), i=True, size=16, color='777777'), style='Header', jc='right'),
                   'even': p(r(v('book|title'), i=True, size=16, color='777777'), style='Header', jc='left')}
    s['footer'] = {'default': page_no(fmt='{}', jc='right', size=16), 'even': page_no(fmt='{}', jc='left', size=16)}
    s['settings'] = '<w:mirrorMargins/><w:evenAndOddHeaders/>'
    s['last_sect'] = {'title_pg': True}
    return s


@spec
def longform():
    s = {'page': A4, 'margins': (mm(25), mm(28), mm(22), mm(28)),
         'theme': {'body_font': 'Georgia', 'body_east': '맑은 고딕', 'body_size': 23, 'line': 360, 'after': 200, 'jc': 'left', 'head_color': '111111',
                   'head_sizes': {1: 30, 2: 26, 3: 24, 4: 23, 5: 23, 6: 23}, 'th_fill': 'F2F2F2', 'rule': '222222'},
         'desc': '웹 장문 — 꼬리표, 큰 제목과 부제, 글쓴이·날짜, 넉넉한 11.5pt 본문과 줄 간격 — 화면에서 오래 읽는 긴 글',
         'desc_en': 'A long-form article — kicker, large title and standfirst, byline and date, a roomy 11.5 pt body for long reading'}
    s['body'] = (p(r('{{if:kicker}}' + v('kicker'), b=True, caps=True, size=18, color='B03A2E'), after=120)
                 + p(r(v('title'), b=True, size=60), after=160, line=260)
                 + p(r('{{if:subtitle}}' + v('subtitle'), size=30, color='555555'), after=200, line=300)
                 + p(r(v('author') + '  ·  ' + v('date:long'), size=18, color='777777'), after=360, border=rule('DDDDDD', 8, 12))
                 + p(r(v('body'))))
    s['footer'] = {'default': page_no(fmt='{}', size=16, color='999999')}
    return s


@spec
def manual():
    s = {'page': A4, 'margins': (mm(22), mm(20), mm(20), mm(22)),
         'theme': {'body_font': '맑은 고딕', 'body_east': '맑은 고딕', 'body_size': 21, 'line': 300, 'jc': 'left', 'head_color': '0B5394', 'h1_rule': '0B5394',
                   'head_sizes': {1: 30, 2: 25, 3: 22, 4: 21, 5: 21, 6: 21}, 'th_fill': 'DCE6F1', 'th_color': '0B2E59', 'rule': '0B5394'},
         'desc': '매뉴얼·가이드 — 표지(제목·부제·판·기관·날짜), 목차 쪽, 쪽 머리에 제목과 판, 파란 제목과 줄',
         'desc_en': 'A manual — a cover (title, subtitle, version, organisation, date), a contents page, the title and version in the header, blue headings with rules'}
    w = text_w(s)
    cover = (p(before=mm(55) * 1, after=0) + p(r(v('title'), b=True, size=60, color='0B5394'), after=200, line=270)
             + p(r('{{if:subtitle}}' + v('subtitle'), size=28, color='444444'), after=240)
             + p(r('{{if:version}}{{t:판|Version}} ' + v('version'), b=True, size=22, color='0B5394'), after=mm(80) * 1)
             + p(r(v('org'), b=True, size=24), after=40, border=rule('0B5394', 12, 8, 'top')) + p(r(v('date:long'), size=20, color='666666'), sect=sect_xml(s, [])))
    front = p(r('{{t:목   차|Contents}}', b=True, size=30, color='0B5394'), after=200, border=rule('0B5394', 8, 4)) + p(r(v('toc'))) + p(sect=sect_xml(s, [], kind='nextPage'))
    s['body'] = cover + front + p(r(v('body')))
    s['header'] = {}
    s['header']['default'] = p(r(v('title'), size=16, color='0B5394'), r('\t' + v("version|''"), size=16, color='777777'), style='Header', tabs=[('right', w)], border=rule('0B5394', 4, 4))
    s['footer'] = {'default': page_no()}
    s['last_sect'] = {'restart': True}
    return s


# ---- 꾸러미 ---------------------------------------------------------------------------------------------

def package(tid, s):
    """.dotx 꾸러미의 (이름, 바이트) — 날짜 없이, 같은 입력이면 같은 바이트"""
    rels, parts, refs = [], {}, []
    n = 0
    for kind in ('header', 'footer'):
        for typ, paras in (s.get(kind) or {}).items():
            n += 1
            name = f'{kind}{n}.xml'
            parts[f'word/{name}'] = hf_xml(kind, paras)
            rid = f'rIdHF{n}'
            rels.append((rid, kind, name))
            refs.append((kind, typ, rid))
    last = s.get('last_sect', {})
    final = sect_xml(s, refs, kind=last.get('kind'), cols=last.get('cols', 1), title_pg=last.get('title_pg', False), restart=last.get('restart', False))
    document = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:document {NS}><w:body>{s["body"]}{final}</w:body></w:document>'
    styles = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:styles {NS}>{"".join(B.default_styles("ko", s.get("theme")))}</w:styles>'
    settings = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:settings {NS}>{s.get("settings", "")}<w:defaultTabStop w:val="800"/>'
                '<w:characterSpacingControl w:val="doNotCompress"/><w:compat><w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="15"/></w:compat></w:settings>')
    rel_xml = ''.join(f'<Relationship Id="{rid}" Type="{B.REL[k]}" Target="{t}"/>' for rid, k, t in
                      [('rIdStyles', 'styles', 'styles.xml'), ('rIdSettings', 'settings', 'settings.xml')] + rels)
    overrides = ''.join(f'<Override PartName="/{name}" ContentType="{CT}.{"header" if "header" in name else "footer"}+xml"/>' for name in parts)
    types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
             '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
             f'<Override PartName="/word/document.xml" ContentType="{CT}.template.main+xml"/><Override PartName="/word/styles.xml" ContentType="{CT}.styles+xml"/>'
             f'<Override PartName="/word/settings.xml" ContentType="{CT}.settings+xml"/>{overrides}'
             '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/></Types>')
    core = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>' + esc(s['name']) + '</dc:title><dc:creator>Lectern</dc:creator><dc:description>' + esc(s['desc']) + '</dc:description></cp:coreProperties>')
    files = {
        '[Content_Types].xml': types,
        '_rels/.rels': f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="{B.RELS}"><Relationship Id="rId1" Type="{B.REL["doc"]}" Target="word/document.xml"/>'
                       f'<Relationship Id="rId2" Type="{B.REL["core"]}" Target="docProps/core.xml"/></Relationships>',
        'word/document.xml': document,
        'word/_rels/document.xml.rels': f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="{B.RELS}">{rel_xml}</Relationships>',
        'word/styles.xml': styles,
        'word/settings.xml': settings,
        'docProps/core.xml': core,
        **parts,
    }
    return files


def write_zip(path, files):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, files[name])


def fields_of(s):
    text = B.TF.plain_text(s['body'] + ''.join((s.get('header') or {}).values()) + ''.join((s.get('footer') or {}).values()))
    keys = []
    for m in re.finditer(r'\{\{\s*([^{}]+?)\s*\}\}', text):
        e = m[1]
        if e.startswith(('slot:', 'if:', 'date:', 'signoff:', 't:')) or e in ('body', 'toc'):
            if e.startswith('signoff:'):
                keys.append(e[8:])
            continue
        for alt in e.split('|'):
            alt = alt.strip()
            if alt.startswith('t:'):   # 이름표부터는 값이 아니다
                break
            if alt and alt[0] not in '\'"' and not alt.startswith('date:') and alt not in keys:
                keys.append(alt)
    return [k for k in dict.fromkeys(keys)]


def build_all(out=OUT):
    out.mkdir(parents=True, exist_ok=True)
    index = []
    for tid, fn in SPECS.items():
        head = layouts.parse_head((ROOT / 'web' / 'layouts' / f'{tid}.html').read_text(encoding='utf-8'))
        s = fn()
        s['name'] = head.get('name', tid)
        write_zip(out / f'{tid}.dotx', package(tid, s))
        slots = sorted(set(B.TF.slots_in([s['body']])))
        index.append({'id': tid, 'name': head.get('name', tid), 'name_en': head.get('name_en', tid), 'group': head.get('group', ''),
                      'group_en': head.get('group_en', ''), 'pages': PAGE_NAMES[s['page']], 'description': s['desc'], 'description_en': s['desc_en'],
                      'fields': fields_of(s), 'slots': slots})
    order = {g: k for k, g in enumerate(layouts.GROUP_ORDER)} if hasattr(layouts, 'GROUP_ORDER') else {}
    index.sort(key=lambda t: (order.get(t['group'], 99), list(SPECS).index(t['id'])))
    (out / 'index.json').write_text(json.dumps(index, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return index


if __name__ == '__main__':
    made = build_all()
    print(f'{len(made)}가지 → {OUT}')
