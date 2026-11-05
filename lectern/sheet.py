"""엑셀 보기 (D77): .xlsx·.xlsm 을 표준 라이브러리(zipfile·ElementTree)로 읽어 시트의 칸 값(보이는 글)을 준다 — GET /api/sheet.

- 값만 읽는다: 숫자·글·참거짓·오류, 수식은 파일에 저장된 계산 값 (수식 글은 따로 준다 — 마우스를 올리면 보인다).
  색·글꼴·숨긴 행 같은 서식은 읽지 않는다. 병합 칸은 범위만 준다 (화면이 여러 줄 머리행을 합치는 데 쓴다 — D86). 파일은 고치지 않는다 (보기 전용).
- 숫자는 칸의 표시 형식을 조금 따른다: 날짜·시각(형식에 y·m·d·h·s), 백분율(%), 자리 쉼표(#,##0), 소수 자리(0.00), 지수(E+),
  앞뒤 글(₩·$·"원" 등), 음수 구역(;). 그 밖은 엑셀의 '일반'처럼 (15자리까지, 정수는 정수로).
- 옛 형식 .xls(BIFF)·.xlsb·.ods 는 읽지 않는다 (엑셀로 연다).
- 큰 파일·압축 폭탄을 막는다: 파일 크기, 읽는 부분의 압축 푼 크기, 시트마다 행·칸 수 한도 (넘으면 앞부분만 — truncated).
  XML 은 ElementTree(expat) — 외부 엔터티를 읽지 않고, 엔터티 부풀리기는 expat 이 막는다. 압축 안의 경로는 압축 안에서만 찾는다.
- 같은 파일(경로·수정 시각·크기)의 시트 목록·공유 문자열·형식은 기억해 둔다 — 시트를 바꿀 때 다시 읽지 않게.
"""
from __future__ import annotations

import datetime
import math
import posixpath
import re
import threading
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Iterator

from .i18n import t

SHEET_EXT = frozenset({'.xlsx', '.xlsm'})
MAX_FILE = 100 * 1024 * 1024        # 엑셀 파일 크기
MAX_PART = 400 * 1024 * 1024        # 압축 안의 한 부분(공유 문자열·시트)의 압축 푼 크기
MAX_ROWS = 50_000                   # 시트마다 보이는 행 (값이 있는 행)
MAX_CELLS = 1_000_000               # 시트마다 칸
MAX_COLS = 1_000                    # 이보다 오른쪽 열은 버린다
MAX_FORMULAS = 5_000
MAX_MERGES = 5_000

REL_TYPE_SHEET = 'worksheet'


class SheetError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def can_view(name: str) -> bool:
    return Path(name).suffix.lower() in SHEET_EXT


def _local(tag: str) -> str:
    return tag.rsplit('}', 1)[-1]


def _attr(el: ET.Element, name: str) -> str | None:
    """이름 공간과 상관없이 속성 (r:id 등)"""
    if name in el.attrib:
        return el.attrib[name]
    for key, value in el.attrib.items():
        if _local(key) == name:
            return value
    return None


# ---- 압축 안의 부분 ---------------------------------------------------------------

def _open_part(zf: zipfile.ZipFile, name: str):
    try:
        info = zf.getinfo(name)
    except KeyError:
        return None
    if info.file_size > MAX_PART:
        raise SheetError(413, t('엑셀 파일 안의 내용이 너무 큽니다 — 엑셀로 여세요'))
    return zf.open(info)


def _parse(zf: zipfile.ZipFile, name: str) -> ET.Element | None:
    fh = _open_part(zf, name)
    if fh is None:
        return None
    with fh:
        return ET.parse(fh).getroot()


def _rels(zf: zipfile.ZipFile, part: str) -> dict[str, tuple[str, str]]:
    """부분(part)의 관계: Id → (형식의 끝 이름, 압축 안 경로)"""
    folder, base = posixpath.split(part)
    root = _parse(zf, posixpath.join(folder, '_rels', f'{base}.rels'))
    out: dict[str, tuple[str, str]] = {}
    if root is None:
        return out
    for rel in root:
        target = rel.get('Target', '')
        if rel.get('TargetMode') == 'External' or not target:
            continue
        path = target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join(folder, target))
        out[rel.get('Id', '')] = (rel.get('Type', '').rsplit('/', 1)[-1], path)
    return out


def _workbook_part(zf: zipfile.ZipFile) -> str:
    for kind, path in _rels(zf, '').values():
        if kind == 'officeDocument':
            return path
    return 'xl/workbook.xml'


# ---- 공유 문자열·형식 ----------------------------------------------------------------

def _text_of(el: ET.Element) -> str:
    """<si>·<is> 의 글: <t> 와 <r><t> 를 잇는다 (윗주 <rPh> 는 빼고)"""
    parts: list[str] = []
    for child in el:
        name = _local(child.tag)
        if name == 't':
            parts.append(child.text or '')
        elif name == 'r':
            parts.extend(x.text or '' for x in child if _local(x.tag) == 't')
    return ''.join(parts)


def _shared_strings(zf: zipfile.ZipFile, path: str | None) -> list[str]:
    fh = _open_part(zf, path) if path else None
    if fh is None:
        return []
    out: list[str] = []
    with fh:
        for _, el in ET.iterparse(fh, events=('end',)):
            if _local(el.tag) == 'si':
                out.append(_text_of(el))
                el.clear()
    return out


# 기본 형식 번호 → 형식 (엑셀에 들어 있는 것 — 파일에 적히지 않는다). 27~36·50~58 은 한국어·일본어·중국어 엑셀의 날짜
BUILTIN = {
    0: 'General', 1: '0', 2: '0.00', 3: '#,##0', 4: '#,##0.00', 9: '0%', 10: '0.00%', 11: '0.00E+00', 12: '# ?/?', 13: '# ??/??',
    14: 'yyyy-mm-dd', 15: 'd-mmm-yy', 16: 'd-mmm', 17: 'mmm-yy', 18: 'h:mm AM/PM', 19: 'h:mm:ss AM/PM', 20: 'h:mm', 21: 'h:mm:ss',
    22: 'yyyy-mm-dd h:mm', 37: '#,##0 ;(#,##0)', 38: '#,##0 ;[Red](#,##0)', 39: '#,##0.00;(#,##0.00)', 40: '#,##0.00;[Red](#,##0.00)',
    45: 'mm:ss', 46: '[h]:mm:ss', 47: 'mm:ss.0', 48: '##0.0E+0', 49: '@',
}
BUILTIN.update({i: 'yyyy-mm-dd' for i in (*range(27, 37), *range(50, 59))})


def _formats(zf: zipfile.ZipFile, path: str | None) -> list[str]:
    """칸 형식 차례(<c s="…">) → 표시 형식 글"""
    root = _parse(zf, path) if path else None
    if root is None:
        return []
    custom: dict[int, str] = {}
    xfs: list[str] = []
    for el in root:
        name = _local(el.tag)
        if name == 'numFmts':
            for f in el:
                try:
                    custom[int(f.get('numFmtId', ''))] = f.get('formatCode', '')
                except ValueError:
                    pass
        elif name == 'cellXfs':
            for xf in el:
                try:
                    fid = int(xf.get('numFmtId', '0'))
                except ValueError:
                    fid = 0
                xfs.append(custom.get(fid, BUILTIN.get(fid, 'General')))
    return xfs


# ---- 값 → 보이는 글 ---------------------------------------------------------------

_QUOTED = re.compile(r'"[^"]*"|\\.|_.|\*.')
_BRACKET = re.compile(r'\[[^\]]*\]')


def _date_kind(code: str) -> str:
    """'' (날짜 아님) / 'date' / 'time' / 'datetime' / 'elapsed'"""
    first = code.split(';', 1)[0]
    bare = _QUOTED.sub('', first)
    elapsed = bool(re.search(r'\[(?:h+|m+|s+)\]', bare, re.I))
    bare = _BRACKET.sub('', bare).lower()
    if bare.strip() in ('', 'general', '@'):
        return 'elapsed' if elapsed else ''
    has_date = bool(re.search(r'[yd]', bare)) or (('m' in bare) and not re.search(r'[hs]', bare))
    has_time = bool(re.search(r'[hs]', bare))
    if elapsed:
        return 'elapsed'
    if has_date and has_time:
        return 'datetime'
    if has_time:
        return 'time'
    return 'date' if has_date else ''


def _date_text(value: float, kind: str, code: str, date1904: bool) -> str:
    if kind == 'elapsed':
        total = round(value * 86400)
        h, rest = divmod(total, 3600)
        return f'{h}:{rest // 60:02d}:{rest % 60:02d}' if re.search(r's', code, re.I) else f'{h}:{rest // 60:02d}'
    base = datetime.datetime(1904, 1, 1) if date1904 else datetime.datetime(1899, 12, 30)
    try:
        when = base + datetime.timedelta(days=value)
    except (OverflowError, ValueError):
        return _general(value)
    when = when.replace(microsecond=0) + datetime.timedelta(seconds=round(when.microsecond / 1e6))
    seconds = bool(re.search(r's', _BRACKET.sub('', _QUOTED.sub('', code)), re.I))
    clock = when.strftime('%H:%M:%S' if seconds else '%H:%M')
    if kind == 'time':
        return clock
    day = when.strftime('%Y-%m-%d')
    return f'{day} {clock}' if kind == 'datetime' else day


def _general(value: float) -> str:
    if math.isfinite(value) and value == int(value) and abs(value) < 1e15:
        return str(int(value))
    return f'{value:.15g}'


def _literal(part: str) -> str:
    """형식 조각의 글자 부분: "글"·\\x 는 그대로, _x(자리 띄우기)·*x(채우기)·[색]은 빼고, [$₩-412] 는 기호만"""
    out = []
    i = 0
    while i < len(part):
        c = part[i]
        if c == '"':
            j = part.find('"', i + 1)
            j = len(part) if j < 0 else j
            out.append(part[i + 1:j])
            i = j + 1
        elif c == '\\' and i + 1 < len(part):
            out.append(part[i + 1])
            i += 2
        elif c in '_*' and i + 1 < len(part):
            out.append(' ' if c == '_' else '')
            i += 2
        elif c == '[':
            j = part.find(']', i)
            j = len(part) if j < 0 else j
            inner = part[i + 1:j]
            if inner.startswith('$'):
                out.append(inner[1:].split('-', 1)[0])
            i = j + 1
        else:
            out.append(c)
            i += 1
    return ''.join(out)


_NUMBER_PART = re.compile(r'[0#?][0#?,.]*(?:[Ee][+-][0#?]+)?%?|%')


def _number_text(value: float, code: str) -> str:
    sections = code.split(';')
    section = sections[0]
    if value < 0 and len(sections) >= 2 and sections[1].strip():
        section, value = sections[1], -value   # 음수 구역은 부호 없이 그 구역의 모양으로 ((1,234) 등)
        if section.strip().lower() == 'general':
            return f'-{_general(value)}'
    elif value == 0 and len(sections) >= 3 and sections[2].strip():
        section = sections[2]
    if section.strip().lower() == 'general':
        return _general(value)
    plain = _QUOTED.sub(lambda m: ' ' * len(m.group(0)), section)
    plain = _BRACKET.sub(lambda m: ' ' * len(m.group(0)), plain)
    match = _NUMBER_PART.search(plain)
    if not match:   # 숫자 자리가 없는 구역 ("-" 나 "없음" 같은 글만)
        return _literal(section).strip() or _general(value)
    spec = match.group(0)
    prefix = _literal(section[:match.start()])
    suffix = _literal(section[match.end():])
    percent = '%' in spec
    number = value * 100 if percent else value
    digits = spec.replace('%', '')
    if re.search(r'[Ee][+-]', digits):
        mant = digits.split('E')[0].split('e')[0]
        decimals = len(mant.split('.', 1)[1]) if '.' in mant else 0
        body = f'{number:.{decimals}E}'
    else:
        whole, _, frac = digits.partition('.')
        decimals = len(frac.replace(',', '').strip())
        grouped = ',' in whole.strip(',')   # 끝의 쉼표(천 단위 나누기)는 무시
        body = f'{number:,.{decimals}f}' if grouped else f'{number:.{decimals}f}'
        if body.startswith('-') and float(body.replace(',', '')) == 0:
            body = body[1:]
    return f'{prefix}{body}{"%" if percent else ""}{suffix}'.strip()


def format_value(value: float, code: str, date1904: bool = False) -> str:
    """숫자를 칸의 표시 형식(code)으로"""
    if not math.isfinite(value):
        return _general(value)
    if not code or code.lower() == 'general' or code == '@':
        return _general(value)
    kind = _date_kind(code)
    if kind:
        return _date_text(value, kind, code, date1904)
    try:
        return _number_text(value, code)
    except (ValueError, OverflowError):
        return _general(value)


# ---- 시트 ----------------------------------------------------------------------

_REF = re.compile(r'([A-Za-z]{1,3})(\d+)')


def col_index(letters: str) -> int:
    n = 0
    for ch in letters.upper():
        n = n * 26 + ord(ch) - 64
    return n - 1


def col_name(i: int) -> str:
    name = ''
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        name = chr(65 + r) + name
    return name


def _cells(fh, shared: list[str], formats: list[str], date1904: bool, merges: list[str] | None = None) -> Iterator[tuple[int, int, str, str | None]]:
    """시트 XML 의 칸마다 (행 차례, 열 차례, 보이는 글, 수식) — 0부터. 값이 없는 칸은 건너뛴다. merges: 병합 칸의 범위 글('A1:C1')을 모은다"""
    row = -1
    col = -1
    for event, el in ET.iterparse(fh, events=('start', 'end')):
        name = _local(el.tag)
        if event == 'start':
            if name == 'row':
                r = el.get('r')
                row = int(r) - 1 if r and r.isdigit() else row + 1
                col = -1
            continue
        if name != 'c':
            if name == 'row':
                el.clear()
            elif name == 'mergeCell' and merges is not None and len(merges) < MAX_MERGES:
                merges.append(el.get('ref') or '')
            continue
        ref = _REF.fullmatch(el.get('r') or '')
        col = col_index(ref.group(1)) if ref else col + 1
        if ref:
            row = int(ref.group(2)) - 1
        kind = el.get('t', 'n')
        style_attr = el.get('s', '0')
        value = formula = None
        for child in el:
            cname = _local(child.tag)
            if cname == 'v':
                value = child.text
            elif cname == 'f' and child.text:
                formula = '=' + child.text
            elif cname == 'is':
                value = _text_of(child)
        el.clear()
        if value is None or value == '':
            if formula:
                yield row, col, '', formula
            continue
        if kind == 's':
            try:
                text = shared[int(value)]
            except (ValueError, IndexError):
                text = ''
        elif kind == 'b':
            text = 'TRUE' if value.strip() in ('1', 'true') else 'FALSE'
        elif kind in ('str', 'inlineStr', 'e'):
            text = value
        elif kind == 'd':
            text = value.replace('T00:00:00', '').replace('T', ' ')
        else:
            try:
                number = float(value)
            except ValueError:
                text = value
            else:
                try:
                    style = int(style_attr)
                except ValueError:
                    style = 0
                text = format_value(number, formats[style] if 0 <= style < len(formats) else 'General', date1904)
        yield row, col, text, formula


def _merge_spans(refs: list[str], first: int) -> list[list[int]]:
    """병합 칸의 범위 'B2:D3' → [첫 행, 첫 열, 끝 행, 끝 열] (행은 1부터, 열은 rows 의 칸 차례 — first 를 뺀다)"""
    out = []
    for ref in refs:
        a, _, b = ref.partition(':')
        m, n = _REF.fullmatch(a), _REF.fullmatch(b or a)
        if m and n:
            out.append([int(m.group(2)), col_index(m.group(1)) - first, int(n.group(2)), col_index(n.group(1)) - first])
    return out


def _broken(error: str) -> SheetError:
    return SheetError(422, t('엑셀 파일을 읽지 못했습니다 — 손상되었거나 다른 형식입니다 ({error})', error=error))


def _zip(path: Path) -> zipfile.ZipFile:
    try:
        return zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise _broken(str(exc)) from exc


class Workbook:
    """한 엑셀 파일의 시트 목록·공유 문자열·형식 (시트 내용은 read_sheet 때 읽는다).
    파일은 읽을 때만 열고 닫는다 — 열어 둔 채면 Windows 에서 엑셀이 그 파일을 저장(바꿔 끼우기)하지 못할 수 있다"""

    def __init__(self, path: Path):
        self.path = path
        with _zip(path) as zf:
            try:
                self._load(zf)
            except (ET.ParseError, zipfile.BadZipFile, EOFError) as exc:
                raise _broken(str(exc)) from exc

    def _load(self, zf: zipfile.ZipFile) -> None:
        part = _workbook_part(zf)
        root = _parse(zf, part)
        if root is None:
            raise _broken('workbook.xml')
        rels = _rels(zf, part)
        self.date1904 = False
        self.sheets: list[dict[str, Any]] = []
        for el in root.iter():
            name = _local(el.tag)
            if name == 'workbookPr':
                self.date1904 = (el.get('date1904') or '').lower() in ('1', 'true')
            elif name == 'sheet':
                kind, target = rels.get(_attr(el, 'id') or '', ('', ''))
                if kind == REL_TYPE_SHEET:   # 차트 시트·대화 시트는 칸이 없다
                    self.sheets.append({'name': el.get('name', ''), 'hidden': el.get('state', 'visible') != 'visible', 'part': target})
        shared = styles = None
        for kind, target in rels.values():
            if kind == 'sharedStrings':
                shared = target
            elif kind == 'styles':
                styles = target
        self.shared = _shared_strings(zf, shared)
        self.formats = _formats(zf, styles)

    def read_sheet(self, index: int) -> dict[str, Any]:
        """시트 하나: {name, rows:[[행 번호(1부터), [칸 글…]]](값이 있는 행만), first_col, cols, formulas:{'B3': '=…'}, truncated}"""
        sheet = self.sheets[index]
        with _zip(self.path) as zf:
            try:
                return self._read(zf, sheet)
            except (zipfile.BadZipFile, EOFError) as exc:
                raise _broken(str(exc)) from exc

    def _read(self, zf: zipfile.ZipFile, sheet: dict[str, Any]) -> dict[str, Any]:
        fh = _open_part(zf, sheet['part'])
        if fh is None:
            raise _broken(sheet['part'])
        rows: dict[int, dict[int, str]] = {}
        formulas: dict[str, str] = {}
        merged: list[str] = []
        cells = 0
        truncated = False
        with fh:
            try:
                for r, c, text, formula in _cells(fh, self.shared, self.formats, self.date1904, merged):
                    if c >= MAX_COLS or c < 0 or r < 0:
                        truncated = truncated or c >= MAX_COLS
                        continue
                    if formula and len(formulas) < MAX_FORMULAS:
                        formulas[f'{col_name(c)}{r + 1}'] = formula
                    if text == '':
                        continue
                    if r not in rows:
                        if len(rows) >= MAX_ROWS:
                            truncated = True
                            break
                        rows[r] = {}
                    rows[r][c] = text
                    cells += 1
                    if cells >= MAX_CELLS:
                        truncated = True
                        break
            except ET.ParseError as exc:
                raise _broken(str(exc)) from exc
        used =[c for row in rows.values() for c in row]
        first = min(used, default=0)
        last = max(used, default=-1)
        out_rows = [[r + 1, [rows[r].get(c, '') for c in range(first, max(rows[r]) + 1)]] for r in sorted(rows)]
        return {'name': sheet['name'], 'rows': out_rows, 'first_col': first, 'cols': max(0, last - first + 1),
                'formulas': formulas, 'merges': _merge_spans(merged, first), 'truncated': truncated}


# ---- 열어 둔 파일 (경로·수정 시각·크기가 같으면 다시 읽지 않는다) ------------------------------

_cache: dict[str, tuple[tuple[int, int], Workbook]] = {}   # 경로 → ((수정 시각, 크기), 시트 목록·문자열·형식)
_lock = threading.Lock()
_KEEP = 3


def read(path: Path, index: int = 0) -> dict[str, Any]:
    """GET /api/sheet: {sheets:[{name, hidden}], index, sheet:{…read_sheet}}"""
    if not can_view(path.name):
        raise SheetError(415, t('이 형식은 Lectern 에서 보지 못합니다 — .xlsx·.xlsm 만 봅니다. 엑셀로 여세요'))
    stat = path.stat()
    if stat.st_size > MAX_FILE:
        raise SheetError(413, t('엑셀 파일이 너무 큽니다 ({n}MB 넘음) — 엑셀로 여세요', n=MAX_FILE // (1024 * 1024)))
    key = str(path)
    stamp = (stat.st_mtime_ns, stat.st_size)
    with _lock:
        held = _cache.get(key)
        if held and held[0] == stamp:
            book = held[1]
        else:
            book = Workbook(path)
            _cache.pop(key, None)
            _cache[key] = (stamp, book)
            while len(_cache) > _KEEP:
                _cache.pop(next(iter(_cache)))
        if not book.sheets:
            return {'sheets': [], 'index': 0, 'sheet': None}
        index = index if 0 <= index < len(book.sheets) else 0
        sheet = book.read_sheet(index)
        return {'sheets': [{'name': s['name'], 'hidden': s['hidden']} for s in book.sheets], 'index': index, 'sheet': sheet}
