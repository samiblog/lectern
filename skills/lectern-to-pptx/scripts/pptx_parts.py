"""pptx 패키지와 조각을 만든다. 표준 라이브러리만 쓴다.

원본이 있으면 그 패키지에 쪽을 끼워 넣고, 없으면 작은 새 패키지를 만든다. 요소의 차례는 스키마가 정하므로
바꾸지 않는다. PowerPoint 는 차례가 틀린 파일을 '복구'하거나 열지 않는다.
"""
import hashlib
import io
import posixpath
import re
import zipfile
from xml.sax.saxutils import escape

NS_A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
NS_R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NS_P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
NS_C = 'http://schemas.openxmlformats.org/drawingml/2006/chart'
REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG_REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
XMLNS = f'xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}"'
CT_SLIDE = 'application/vnd.openxmlformats-officedocument.presentationml.slide+xml'
CT_NOTES = 'application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml'
CT_CHART = 'application/vnd.openxmlformats-officedocument.drawingml.chart+xml'
IMAGE_TYPES = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'gif': 'image/gif', 'bmp': 'image/bmp', 'svg': 'image/svg+xml',
               'emf': 'image/x-emf', 'wmf': 'image/x-wmf', 'tif': 'image/tiff', 'tiff': 'image/tiff'}


def esc(text):
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', str(text))
    return escape(text, {'"': '&quot;'})


class Package:
    """ZIP 안의 파트를 사전으로 다룬다. 관계와 내용 형식을 함께 고친다."""

    def __init__(self, files):
        self.files = dict(files)

    @classmethod
    def read(cls, path):
        with zipfile.ZipFile(path) as z:
            return cls({n: z.read(n) for n in z.namelist() if not n.endswith('/')})

    def text(self, name):
        return self.files[name].decode('utf-8')

    def put(self, name, data):
        self.files[name] = data.encode('utf-8') if isinstance(data, str) else data

    @staticmethod
    def rels_name(part):
        return f'{posixpath.dirname(part)}/_rels/{posixpath.basename(part)}.rels'

    def rels(self, part):
        """[(id, type, target, external)]"""
        name = self.rels_name(part)
        if name not in self.files:
            return []
        out = []
        for tag in re.findall(r'<Relationship\b[^>]*>', self.text(name)):
            attrs = dict(re.findall(r'([\w:]+)="([^"]*)"', tag))
            out.append((attrs.get('Id'), attrs.get('Type', ''), attrs.get('Target', ''), attrs.get('TargetMode') == 'External'))
        return out

    def write_rels(self, part, items):
        body = ''.join(f'<Relationship Id="{i}" Type="{t}" Target="{esc(g)}"{" TargetMode=\"External\"" if ext else ""}/>' for i, t, g, ext in items)
        self.put(self.rels_name(part), f'{HEAD}<Relationships xmlns="{PKG_REL}">{body}</Relationships>')

    def add_rel(self, part, kind, target, external=False):
        items = self.rels(part)
        for i, t, g, ext in items:
            if t.endswith('/' + kind) and g == target:
                return i
        used = {int(m[1]) for i, *_ in items if (m := re.match(r'rId(\d+)$', i or ''))}
        rid = f'rId{max(used, default=0) + 1}'
        items.append((rid, f'{REL}/{kind}', target, external))
        self.write_rels(part, items)
        return rid

    def target(self, part, target):
        return target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join(posixpath.dirname(part), target))

    def add_override(self, part, ctype):
        ct = self.text('[Content_Types].xml')
        tag = f'<Override PartName="/{part}" ContentType="{ctype}"/>'
        if f'PartName="/{part}"' not in ct:
            self.put('[Content_Types].xml', ct.replace('</Types>', tag + '</Types>'))

    def add_default(self, ext, ctype):
        ct = self.text('[Content_Types].xml')
        if not re.search(rf'<Default\s+Extension="{re.escape(ext)}"', ct, flags=re.I):
            self.put('[Content_Types].xml', ct.replace('<Override', f'<Default Extension="{ext}" ContentType="{ctype}"/><Override', 1))

    def add_media(self, data, ext):
        ext = ext.lower().lstrip('.')
        name = f'ppt/media/lectern-{hashlib.sha1(data).hexdigest()[:12]}.{ext}'
        self.put(name, data)
        self.add_default(ext, IMAGE_TYPES.get(ext, 'application/octet-stream'))
        return name

    def next_part(self, folder, stem, ext='xml'):
        n = 1 + max((int(m[1]) for f in self.files if (m := re.fullmatch(rf'{re.escape(folder)}/{stem}(\d+)\.{ext}', f))), default=0)
        return f'{folder}/{stem}{n}.{ext}'

    def prune(self):
        """어디서도 이어지지 않는 파트를 지운다. 지운 쪽의 차트·노트가 남지 않게."""
        seen, todo = set(), ['']
        roots = [t for _, _, t, ext in self.rels_root() if not ext]
        todo = [t.lstrip('/') for t in roots]
        while todo:
            part = todo.pop()
            if part in seen or part not in self.files:
                continue
            seen.add(part)
            for _, _, target, ext in self.rels(part):
                if not ext:
                    todo.append(self.target(part, target))
        ct = self.text('[Content_Types].xml')
        for name in list(self.files):
            if name == '[Content_Types].xml' or name.endswith('.rels') or name in seen:
                continue
            del self.files[name]
            ct = re.sub(rf'<Override\s+PartName="/{re.escape(name)}"[^>]*/>', '', ct)
        for name in list(self.files):
            if name.endswith('.rels') and name != '_rels/.rels':
                base = posixpath.join(posixpath.dirname(posixpath.dirname(name)), posixpath.basename(name)[:-5])
                if base not in self.files:
                    del self.files[name]
        self.put('[Content_Types].xml', ct)

    def rels_root(self):
        items = []
        for tag in re.findall(r'<Relationship\b[^>]*>', self.text('_rels/.rels')):
            attrs = dict(re.findall(r'([\w:]+)="([^"]*)"', tag))
            items.append((attrs.get('Id'), attrs.get('Type', ''), attrs.get('Target', ''), attrs.get('TargetMode') == 'External'))
        return items

    def save(self, path):
        order = ['[Content_Types].xml'] + sorted(n for n in self.files if n != '[Content_Types].xml')
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
            for name in order:
                z.writestr(name, self.files[name])
        with open(path, 'wb') as f:
            f.write(buf.getvalue())


# ---- 새 패키지

def theme_xml(name, colors, major='Malgun Gothic', minor='Malgun Gothic'):
    slots = ''.join(f'<a:{k}><a:srgbClr val="{colors[k]}"/></a:{k}>' for k in
                    ('dk1', 'lt1', 'dk2', 'lt2', 'accent1', 'accent2', 'accent3', 'accent4', 'accent5', 'accent6', 'hlink', 'folHlink'))
    fills = '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>' * 3
    lines = ''.join(f'<a:ln w="{w}" cap="flat" cmpd="sng" algn="ctr"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/></a:ln>' for w in (6350, 12700, 19050))
    effects = '<a:effectStyle><a:effectLst/></a:effectStyle>' * 3

    def font(tag, face):
        return f'<a:{tag}><a:latin typeface="{esc(face)}"/><a:ea typeface="{esc(face)}"/><a:cs typeface=""/></a:{tag}>'

    return (f'{HEAD}<a:theme xmlns:a="{NS_A}" name="{esc(name)}"><a:themeElements><a:clrScheme name="{esc(name)}">{slots}</a:clrScheme>'
            f'<a:fontScheme name="{esc(name)}">{font("majorFont", major)}{font("minorFont", minor)}</a:fontScheme>'
            f'<a:fmtScheme name="{esc(name)}"><a:fillStyleLst>{fills}</a:fillStyleLst><a:lnStyleLst>{lines}</a:lnStyleLst>'
            f'<a:effectStyleLst>{effects}</a:effectStyleLst><a:bgFillStyleLst>{fills}</a:bgFillStyleLst></a:fmtScheme></a:themeElements></a:theme>')


EMPTY_TREE = '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
CLR_MAP = 'bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"'


def placeholder(sid, name, kind, idx, box, text=''):
    ph = f'<p:ph type="{kind}"' + (f' idx="{idx}"' if idx else '') + '/>'
    x, y, w, h = box
    sp = f'<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm></p:spPr>' if w else '<p:spPr/>'
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="{esc(name)}"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr>{ph}</p:nvPr></p:nvSpPr>{sp}'
            f'<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="ko-KR"/><a:t>{esc(text)}</a:t></a:r></a:p></p:txBody></p:sp>')


def level_style(tag, sizes, color, bullet=True):
    out = []
    for i, sz in enumerate(sizes):
        mar = 285750 + i * 342900
        bu = f'<a:buFont typeface="Arial"/><a:buChar char="•"/>' if bullet else '<a:buNone/>'
        out.append(f'<a:lvl{i + 1}pPr marL="{mar if bullet else 0}" indent="{-285750 if bullet else 0}" algn="l" defTabSz="914400" rtl="0" eaLnBrk="1" latinLnBrk="0" hangingPunct="1">'
                   f'<a:spcBef><a:spcPts val="{600 if i == 0 else 300}"/></a:spcBef>{bu}'
                   f'<a:defRPr sz="{sz}" kern="1200"><a:solidFill><a:schemeClr val="{color}"/></a:solidFill><a:latin typeface="+mn-lt"/><a:ea typeface="+mn-ea"/><a:cs typeface="+mn-cs"/></a:defRPr></a:lvl{i + 1}pPr>')
    return f'<p:{tag}>{"".join(out)}</p:{tag}>'


def fresh(cx, cy, colors, name='Lectern', title='', major='Malgun Gothic', minor='Malgun Gothic', bg=None):
    """쪽이 없는 작은 pptx. 레이아웃 넷(표지, 제목과 내용, 제목만, 빈 쪽)과 노트 마스터가 있다."""
    pad_x = round(cx * 56 / 1280 if cx / cy > 1.5 else cx * 56 / 960)
    title_box = (pad_x, round(cy * .05), cx - 2 * pad_x, round(cy * .12))
    body_box = (pad_x, round(cy * .19), cx - 2 * pad_x, round(cy * .72))
    foot_y, foot_h = round(cy * .935), round(cy * .05)
    files = {}
    layouts = [
        ('표지', 'title', [placeholder(2, '제목', 'ctrTitle', '', (pad_x, round(cy * .3), cx - 2 * pad_x, round(cy * .22))),
                         placeholder(3, '부제목', 'subTitle', '1', (pad_x, round(cy * .54), cx - 2 * pad_x, round(cy * .2)))]),
        ('제목과 내용', 'obj', [placeholder(2, '제목', 'title', '', (0, 0, 0, 0)), placeholder(3, '내용', 'body', '1', (0, 0, 0, 0))]),
        ('제목만', 'titleOnly', [placeholder(2, '제목', 'title', '', (0, 0, 0, 0))]),
        ('빈 쪽', 'blank', []),
    ]
    master_rels = []
    ids = []
    for i, (lname, ltype, shapes) in enumerate(layouts, 1):
        part = f'ppt/slideLayouts/slideLayout{i}.xml'
        files[part] = (f'{HEAD}<p:sldLayout {XMLNS} type="{ltype}" preserve="1"><p:cSld name="{esc(lname)}"><p:spTree>{EMPTY_TREE}{"".join(shapes)}</p:spTree></p:cSld>'
                       '<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>')
        files[f'ppt/slideLayouts/_rels/slideLayout{i}.xml.rels'] = (f'{HEAD}<Relationships xmlns="{PKG_REL}"><Relationship Id="rId1" Type="{REL}/slideMaster" Target="../slideMasters/slideMaster1.xml"/></Relationships>')
        master_rels.append(f'<Relationship Id="rId{i}" Type="{REL}/slideLayout" Target="../slideLayouts/slideLayout{i}.xml"/>')
        ids.append(f'<p:sldLayoutId id="{2147483649 + i}" r:id="rId{i}"/>')
    master_rels.append(f'<Relationship Id="rId{len(layouts) + 1}" Type="{REL}/theme" Target="../theme/theme1.xml"/>')
    files['ppt/slideMasters/_rels/slideMaster1.xml.rels'] = f'{HEAD}<Relationships xmlns="{PKG_REL}">{"".join(master_rels)}</Relationships>'
    title_style = ('<p:titleStyle><a:lvl1pPr algn="l" defTabSz="914400" rtl="0" eaLnBrk="1" latinLnBrk="0" hangingPunct="1"><a:spcBef><a:spcPct val="0"/></a:spcBef><a:buNone/>'
                   '<a:defRPr sz="3000" b="1" kern="1200"><a:solidFill><a:schemeClr val="tx2"/></a:solidFill><a:latin typeface="+mj-lt"/><a:ea typeface="+mj-ea"/><a:cs typeface="+mj-cs"/></a:defRPr></a:lvl1pPr></p:titleStyle>')
    background = f'<p:bg><p:bgPr><a:solidFill><a:srgbClr val="{bg}"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>' if bg else '<p:bg><p:bgRef idx="1001"><a:schemeClr val="bg1"/></p:bgRef></p:bg>'
    files['ppt/slideMasters/slideMaster1.xml'] = (
        f'{HEAD}<p:sldMaster {XMLNS}><p:cSld>{background}<p:spTree>{EMPTY_TREE}'
        f'{placeholder(2, "제목", "title", "", title_box, "제목")}{placeholder(3, "내용", "body", "1", body_box, "내용")}'
        f'{placeholder(4, "꼬리말", "ftr", "3", (pad_x, foot_y, round(cx * .6), foot_h))}{placeholder(5, "쪽 번호", "sldNum", "4", (cx - pad_x - round(cx * .1), foot_y, round(cx * .1), foot_h))}'
        f'</p:spTree></p:cSld><p:clrMap {CLR_MAP}/><p:sldLayoutIdLst>{"".join(ids)}</p:sldLayoutIdLst>'
        f'<p:txStyles>{title_style}{level_style("bodyStyle", (1800, 1600, 1400, 1400, 1400), "tx1")}{level_style("otherStyle", (1800, 1800, 1800, 1800, 1800), "tx1", False)}</p:txStyles></p:sldMaster>')
    files['ppt/theme/theme1.xml'] = theme_xml(name, colors, major, minor)
    files['ppt/theme/theme2.xml'] = theme_xml(name + ' 노트', colors, major, minor)
    files['ppt/notesMasters/notesMaster1.xml'] = notes_master()
    files['ppt/notesMasters/_rels/notesMaster1.xml.rels'] = f'{HEAD}<Relationships xmlns="{PKG_REL}"><Relationship Id="rId1" Type="{REL}/theme" Target="../theme/theme2.xml"/></Relationships>'
    files['ppt/presProps.xml'] = f'{HEAD}<p:presentationPr {XMLNS}/>'
    files['ppt/viewProps.xml'] = f'{HEAD}<p:viewPr {XMLNS}/>'
    files['ppt/tableStyles.xml'] = f'{HEAD}<a:tblStyleLst xmlns:a="{NS_A}" def="{{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}}"/>'
    files['ppt/presentation.xml'] = (
        f'{HEAD}<p:presentation {XMLNS} saveSubsetFonts="1"><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>'
        f'<p:notesMasterIdLst><p:notesMasterId r:id="rId2"/></p:notesMasterIdLst><p:sldIdLst/><p:sldSz cx="{cx}" cy="{cy}"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>')
    files['ppt/_rels/presentation.xml.rels'] = (
        f'{HEAD}<Relationships xmlns="{PKG_REL}"><Relationship Id="rId1" Type="{REL}/slideMaster" Target="slideMasters/slideMaster1.xml"/>'
        f'<Relationship Id="rId2" Type="{REL}/notesMaster" Target="notesMasters/notesMaster1.xml"/><Relationship Id="rId3" Type="{REL}/presProps" Target="presProps.xml"/>'
        f'<Relationship Id="rId4" Type="{REL}/viewProps" Target="viewProps.xml"/><Relationship Id="rId5" Type="{REL}/theme" Target="theme/theme1.xml"/>'
        f'<Relationship Id="rId6" Type="{REL}/tableStyles" Target="tableStyles.xml"/></Relationships>')
    files['_rels/.rels'] = (
        f'{HEAD}<Relationships xmlns="{PKG_REL}"><Relationship Id="rId1" Type="{REL}/officeDocument" Target="ppt/presentation.xml"/>'
        f'<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        f'<Relationship Id="rId3" Type="{REL}/extended-properties" Target="docProps/app.xml"/></Relationships>')
    files['docProps/core.xml'] = (
        f'{HEAD}<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f'<dc:title>{esc(title)}</dc:title></cp:coreProperties>')
    files['docProps/app.xml'] = f'{HEAD}<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>Lectern</Application></Properties>'
    overrides = {
        'ppt/presentation.xml': 'application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml',
        'ppt/slideMasters/slideMaster1.xml': 'application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml',
        'ppt/notesMasters/notesMaster1.xml': 'application/vnd.openxmlformats-officedocument.presentationml.notesMaster+xml',
        'ppt/theme/theme1.xml': 'application/vnd.openxmlformats-officedocument.theme+xml',
        'ppt/theme/theme2.xml': 'application/vnd.openxmlformats-officedocument.theme+xml',
        'ppt/presProps.xml': 'application/vnd.openxmlformats-officedocument.presentationml.presProps+xml',
        'ppt/viewProps.xml': 'application/vnd.openxmlformats-officedocument.presentationml.viewProps+xml',
        'ppt/tableStyles.xml': 'application/vnd.openxmlformats-officedocument.presentationml.tableStyles+xml',
        'docProps/core.xml': 'application/vnd.openxmlformats-package.core-properties+xml',
        'docProps/app.xml': 'application/vnd.openxmlformats-officedocument.extended-properties+xml',
    }
    for i in range(1, len(layouts) + 1):
        overrides[f'ppt/slideLayouts/slideLayout{i}.xml'] = 'application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml'
    body = ''.join(f'<Override PartName="/{k}" ContentType="{v}"/>' for k, v in overrides.items())
    files['[Content_Types].xml'] = (
        f'{HEAD}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        f'<Default Extension="xml" ContentType="application/xml"/>{body}</Types>')
    return Package({k: v.encode('utf-8') if isinstance(v, str) else v for k, v in files.items()})


def notes_master():
    return (f'{HEAD}<p:notesMaster {XMLNS}><p:cSld><p:bg><p:bgRef idx="1001"><a:schemeClr val="bg1"/></p:bgRef></p:bg><p:spTree>{EMPTY_TREE}'
            f'{placeholder(2, "쪽 그림", "sldImg", "2", (685800, 1143000, 5486400, 3086100))}{placeholder(3, "노트", "body", "3", (685800, 4400550, 5486400, 3600450))}'
            f'</p:spTree></p:cSld><p:clrMap {CLR_MAP}/></p:notesMaster>')


def notes_slide(text):
    paras = ''.join(f'<a:p><a:r><a:rPr lang="ko-KR"/><a:t>{esc(line)}</a:t></a:r></a:p>' for line in text.split('\n')) or '<a:p/>'
    return (f'{HEAD}<p:notes {XMLNS}><p:cSld><p:spTree>{EMPTY_TREE}'
            '<p:sp><p:nvSpPr><p:cNvPr id="2" name="쪽 그림"/><p:cNvSpPr><a:spLocks noGrp="1" noRot="1" noChangeAspect="1"/></p:cNvSpPr><p:nvPr><p:ph type="sldImg"/></p:nvPr></p:nvSpPr><p:spPr/></p:sp>'
            '<p:sp><p:nvSpPr><p:cNvPr id="3" name="노트"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph type="body" idx="1"/></p:nvPr></p:nvSpPr><p:spPr/>'
            f'<p:txBody><a:bodyPr/><a:lstStyle/>{paras}</p:txBody></p:sp></p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:notes>')


# ---- 차트

def col_name(i):
    return chr(65 + i) if i < 26 else chr(64 + i // 26) + chr(65 + i % 26)


def workbook(header, rows):
    """차트의 '데이터 편집'이 열 수 있는 작은 xlsx."""
    def cell(ref, v):
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return f'<c r="{ref}"><v>{v}</v></c>'
        return f'<c r="{ref}" t="inlineStr"><is><t>{esc("" if v is None else v)}</t></is></c>'

    lines = []
    for r, row in enumerate([header] + rows, 1):
        lines.append(f'<row r="{r}">' + ''.join(cell(f'{col_name(c)}{r}', v) for c, v in enumerate(row)) + '</row>')
    buf = io.BytesIO()
    main = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', f'{HEAD}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        z.writestr('_rels/.rels', f'{HEAD}<Relationships xmlns="{PKG_REL}"><Relationship Id="rId1" Type="{REL}/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/workbook.xml', f'{HEAD}<workbook xmlns="{main}" xmlns:r="{NS_R}"><sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels', f'{HEAD}<Relationships xmlns="{PKG_REL}"><Relationship Id="rId1" Type="{REL}/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr('xl/worksheets/sheet1.xml', f'{HEAD}<worksheet xmlns="{main}"><sheetData>{"".join(lines)}</sheetData></worksheet>')
    return buf.getvalue()


def str_ref(ref, values):
    pts = ''.join(f'<c:pt idx="{i}"><c:v>{esc(v)}</c:v></c:pt>' for i, v in enumerate(values))
    return f'<c:strRef><c:f>{ref}</c:f><c:strCache><c:ptCount val="{len(values)}"/>{pts}</c:strCache></c:strRef>'


def num_ref(ref, values):
    pts = ''.join(f'<c:pt idx="{i}"><c:v>{v}</c:v></c:pt>' for i, v in enumerate(values) if isinstance(v, (int, float)))
    return f'<c:numRef><c:f>{ref}</c:f><c:numCache><c:formatCode>General</c:formatCode><c:ptCount val="{len(values)}"/>{pts}</c:numCache></c:numRef>'


def fill_of(color):
    return f'<c:spPr><a:solidFill><a:srgbClr val="{color}"/></a:solidFill></c:spPr>' if color else ''


DATA_LABELS = '<c:dLbls><c:showLegendKey val="0"/><c:showVal val="1"/><c:showCatName val="0"/><c:showSerName val="0"/><c:showPercent val="0"/><c:showBubbleSize val="0"/></c:dLbls>'


def chart_xml(model, rel_id, palette):
    """model: {type, dir, grouping, cats, series:[{name, vals, x?, colors?}], labels}"""
    kind = model['type']
    labels = DATA_LABELS if model.get('labels') else ''
    cats, series = model.get('cats', []), model['series']
    n = max(1, len(cats))
    sers = []
    for i, s in enumerate(series):
        col = col_name(i + 1)
        tx = f'<c:tx>{str_ref(f"Sheet1!${col}$1", [s["name"]])}</c:tx>'
        color = palette[i % len(palette)]
        head = f'<c:ser><c:idx val="{i}"/><c:order val="{i}"/>{tx}'
        if kind == 'scatter':
            xs = s['x']
            m = len(xs)
            sers.append(f'{head}<c:spPr><a:ln w="19050"><a:noFill/></a:ln></c:spPr><c:marker><c:symbol val="circle"/><c:size val="8"/>{fill_of(color)}</c:marker>'
                        f'<c:xVal>{num_ref(f"Sheet1!$A$2:$A${m + 1}", xs)}</c:xVal><c:yVal>{num_ref(f"Sheet1!${col}$2:${col}${m + 1}", s["vals"])}</c:yVal><c:smooth val="0"/></c:ser>')
            continue
        cat = f'<c:cat>{str_ref(f"Sheet1!$A$2:$A${n + 1}", cats)}</c:cat>'
        val = f'<c:val>{num_ref(f"Sheet1!${col}$2:${col}${n + 1}", s["vals"])}</c:val>'
        if kind == 'bar':
            points = ''.join(f'<c:dPt><c:idx val="{k}"/><c:invertIfNegative val="0"/><c:bubble3D val="0"/>{fill_of(c)}</c:dPt>' for k, c in enumerate(s.get('colors') or []) if c)
            sers.append(f'{head}{fill_of(color)}<c:invertIfNegative val="0"/>{points}{labels}{cat}{val}</c:ser>')
        elif kind == 'line':
            sers.append(f'{head}<c:spPr><a:ln w="28575"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill></a:ln></c:spPr><c:marker><c:symbol val="none"/></c:marker>{labels}{cat}{val}<c:smooth val="0"/></c:ser>')
        elif kind == 'radar':
            sers.append(f'{head}<c:spPr><a:ln w="28575"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill></a:ln></c:spPr>{cat}{val}</c:ser>')
        elif kind == 'area':
            sers.append(f'{head}{fill_of(color)}{cat}{val}</c:ser>')
        else:
            points = ''.join(f'<c:dPt><c:idx val="{k}"/><c:bubble3D val="0"/>{fill_of(palette[k % len(palette)])}</c:dPt>' for k in range(n))
            sers.append(f'{head}{points}{labels}{cat}{val}</c:ser>')
    body = ''.join(sers)
    axes_ids = '<c:axId val="111111111"/><c:axId val="222222222"/>'
    extra = ''
    if model.get('lines'):      # 기준선: 같은 축의 선 계열
        rows = []
        for k, line in enumerate(model['lines'], len(series)):
            col = col_name(k + 1)
            rows.append(f'<c:ser><c:idx val="{k}"/><c:order val="{k}"/><c:tx>{str_ref(f"Sheet1!${col}$1", [line["name"]])}</c:tx>'
                        f'<c:spPr><a:ln w="19050"><a:solidFill><a:srgbClr val="{line["color"]}"/></a:solidFill><a:prstDash val="dash"/></a:ln></c:spPr><c:marker><c:symbol val="none"/></c:marker>'
                        f'<c:cat>{str_ref(f"Sheet1!$A$2:$A${n + 1}", cats)}</c:cat><c:val>{num_ref(f"Sheet1!${col}$2:${col}${n + 1}", line["vals"])}</c:val><c:smooth val="0"/></c:ser>')
        extra = f'<c:lineChart><c:grouping val="standard"/><c:varyColors val="0"/>{"".join(rows)}<c:marker val="1"/>{axes_ids}</c:lineChart>'
    grouping = model.get('grouping', 'clustered')
    if kind == 'bar':
        overlap = '<c:overlap val="100"/>' if grouping in ('stacked', 'percentStacked') else ''
        plot = f'<c:barChart><c:barDir val="{model.get("dir", "col")}"/><c:grouping val="{grouping}"/><c:varyColors val="0"/>{body}<c:gapWidth val="60"/>{overlap}{axes_ids}</c:barChart>'
    elif kind == 'line':
        plot = f'<c:lineChart><c:grouping val="standard"/><c:varyColors val="0"/>{body}<c:marker val="1"/>{axes_ids}</c:lineChart>'
    elif kind == 'area':
        g = grouping if grouping in ('stacked', 'percentStacked') else 'standard'
        plot = f'<c:areaChart><c:grouping val="{g}"/><c:varyColors val="0"/>{body}{axes_ids}</c:areaChart>'
    elif kind == 'radar':
        plot = f'<c:radarChart><c:radarStyle val="marker"/><c:varyColors val="0"/>{body}{axes_ids}</c:radarChart>'
    elif kind == 'scatter':
        plot = f'<c:scatterChart><c:scatterStyle val="lineMarker"/><c:varyColors val="0"/>{body}{axes_ids}</c:scatterChart>'
    elif kind == 'doughnut':
        plot = f'<c:doughnutChart><c:varyColors val="1"/>{body}<c:firstSliceAng val="0"/><c:holeSize val="55"/></c:doughnutChart>'
    else:
        plot = f'<c:pieChart><c:varyColors val="1"/>{body}<c:firstSliceAng val="0"/></c:pieChart>'
    grid = '<c:majorGridlines><c:spPr><a:ln w="6350"><a:solidFill><a:srgbClr val="D9D9D9"/></a:solidFill></a:ln></c:spPr></c:majorGridlines>'
    cat_pos, val_pos = ('l', 'b') if model.get('dir') == 'bar' else ('b', 'l')
    if kind in ('pie', 'doughnut'):
        axes = ''
    elif kind == 'scatter':
        axes = (f'<c:valAx><c:axId val="111111111"/><c:scaling><c:orientation val="minMax"/></c:scaling><c:delete val="0"/><c:axPos val="b"/><c:numFmt formatCode="General" sourceLinked="0"/><c:majorTickMark val="out"/><c:minorTickMark val="none"/><c:tickLblPos val="nextTo"/><c:crossAx val="222222222"/><c:crosses val="autoZero"/><c:crossBetween val="midCat"/></c:valAx>'
                f'<c:valAx><c:axId val="222222222"/><c:scaling><c:orientation val="minMax"/></c:scaling><c:delete val="0"/><c:axPos val="l"/>{grid}<c:numFmt formatCode="General" sourceLinked="0"/><c:majorTickMark val="out"/><c:minorTickMark val="none"/><c:tickLblPos val="nextTo"/><c:crossAx val="111111111"/><c:crosses val="autoZero"/><c:crossBetween val="midCat"/></c:valAx>')
    else:
        orient = 'maxMin' if model.get('dir') == 'bar' else 'minMax'
        axes = (f'<c:catAx><c:axId val="111111111"/><c:scaling><c:orientation val="{orient}"/></c:scaling><c:delete val="0"/><c:axPos val="{cat_pos}"/><c:numFmt formatCode="General" sourceLinked="0"/><c:majorTickMark val="none"/><c:minorTickMark val="none"/><c:tickLblPos val="nextTo"/><c:crossAx val="222222222"/><c:crosses val="autoZero"/><c:auto val="1"/><c:lblAlgn val="ctr"/><c:lblOffset val="100"/><c:noMultiLvlLbl val="0"/></c:catAx>'
                f'<c:valAx><c:axId val="222222222"/><c:scaling><c:orientation val="minMax"/></c:scaling><c:delete val="0"/><c:axPos val="{val_pos}"/>{grid}<c:numFmt formatCode="General" sourceLinked="0"/><c:majorTickMark val="none"/><c:minorTickMark val="none"/><c:tickLblPos val="nextTo"/><c:crossAx val="111111111"/><c:crosses val="autoZero"/><c:crossBetween val="between"/></c:valAx>')
    legend = '<c:legend><c:legendPos val="b"/><c:overlay val="0"/></c:legend>' if len(series) > 1 or kind in ('pie', 'doughnut') else ''
    return (f'{HEAD}<c:chartSpace xmlns:c="{NS_C}" xmlns:a="{NS_A}" xmlns:r="{NS_R}"><c:roundedCorners val="0"/><c:chart><c:autoTitleDeleted val="1"/>'
            f'<c:plotArea><c:layout/>{plot}{extra}{axes}</c:plotArea>{legend}<c:plotVisOnly val="1"/><c:dispBlanksAs val="gap"/></c:chart>'
            f'<c:txPr><a:bodyPr/><a:lstStyle/><a:p><a:pPr><a:defRPr sz="1200"/></a:pPr><a:endParaRPr lang="ko-KR"/></a:p></c:txPr>'
            f'<c:externalData r:id="{rel_id}"><c:autoUpdate val="0"/></c:externalData></c:chartSpace>')
