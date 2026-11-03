"""엑셀 보기 (D77): .xlsx 를 표준 라이브러리로 — 공유 문자열·표시 형식·수식 값·시트 목록·한도·깨진 파일."""
from __future__ import annotations

import zipfile

import pytest

from lectern import sheet
from lectern.sheet import SheetError, col_index, col_name, format_value, read

MAIN = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG = 'http://schemas.openxmlformats.org/package/2006/relationships'


def make_xlsx(path, sheets, shared=(), formats=(), xfs=(0,), date1904=False, extra=None):
    """시험용 xlsx. sheets: [(이름, 시트 XML 의 <sheetData> 안, state)], shared: 공유 문자열, formats: [(id, code)], xfs: 칸 형식마다 numFmtId"""
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('_rels/.rels', f'<Relationships xmlns="{PKG}"><Relationship Id="rId1" '
                    f'Type="{R}/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        rels = [f'<Relationship Id="rId{i + 1}" Type="{R}/worksheet" Target="worksheets/sheet{i + 1}.xml"/>' for i in range(len(sheets))]
        rels.append(f'<Relationship Id="rS" Type="{R}/sharedStrings" Target="sharedStrings.xml"/>')
        rels.append(f'<Relationship Id="rT" Type="{R}/styles" Target="/xl/styles.xml"/>')
        zf.writestr('xl/_rels/workbook.xml.rels', f'<Relationships xmlns="{PKG}">{"".join(rels)}</Relationships>')
        items = ''.join(f'<sheet name="{name}" sheetId="{i + 1}" r:id="rId{i + 1}"{f" state={chr(34)}{state}{chr(34)}" if state else ""}/>'
                        for i, (name, _, state) in enumerate(sheets))
        pr = '<workbookPr date1904="1"/>' if date1904 else ''
        zf.writestr('xl/workbook.xml', f'<workbook xmlns="{MAIN}" xmlns:r="{R}">{pr}<sheets>{items}</sheets></workbook>')
        for i, (_, data, _) in enumerate(sheets):
            zf.writestr(f'xl/worksheets/sheet{i + 1}.xml', f'<worksheet xmlns="{MAIN}"><sheetData>{data}</sheetData></worksheet>')
        si = ''.join(s if s.startswith('<') else f'<si><t xml:space="preserve">{s}</t></si>' for s in shared)
        zf.writestr('xl/sharedStrings.xml', f'<sst xmlns="{MAIN}">{si}</sst>')
        nf = ''.join(f'<numFmt numFmtId="{i}" formatCode="{c}"/>' for i, c in formats)
        xf = ''.join(f'<xf numFmtId="{n}"/>' for n in xfs)
        zf.writestr('xl/styles.xml', f'<styleSheet xmlns="{MAIN}"><numFmts>{nf}</numFmts><cellXfs>{xf}</cellXfs></styleSheet>')
        for name, data in (extra or {}).items():
            zf.writestr(name, data)
    return path


@pytest.fixture(autouse=True)
def fresh_cache():
    sheet._cache.clear()
    yield
    sheet._cache.clear()


def test_values_shared_strings_formulas_and_sheets(tmp_path):
    data = ('<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c><c r="C1" t="s"><v>2</v></c></row>'
            '<row r="2"><c r="A2" t="s"><v>3</v></c><c r="B2"><v>8950</v></c><c r="C2" t="b"><v>1</v></c></row>'
            '<row r="4"><c r="A4" t="inlineStr"><is><t>합계</t></is></c><c r="B4"><f>SUM(B2:B3)</f><v>8950</v></c>'
            '<c r="C4" t="e"><v>#DIV/0!</v></c></row>')
    rich = '<si><r><t>굵은 </t></r><r><t>글</t></r><rPh><t>윗주</t></rPh></si>'
    p = make_xlsx(tmp_path / 'a.xlsx', [('1분기', data, None), ('숨김', '', 'hidden'), ('빈 시트', '', None)],
                  shared=['품목', '값', '확인', rich])
    got = read(p)
    assert got['sheets'] == [{'name': '1분기', 'hidden': False}, {'name': '숨김', 'hidden': True}, {'name': '빈 시트', 'hidden': False}]
    s = got['sheet']
    assert s['name'] == '1분기' and s['first_col'] == 0 and s['cols'] == 3 and not s['truncated']
    assert s['rows'] == [[1, ['품목', '값', '확인']], [2, ['굵은 글', '8950', 'TRUE']], [4, ['합계', '8950', '#DIV/0!']]]
    assert s['formulas'] == {'B4': '=SUM(B2:B3)'}
    assert read(p, 2)['sheet']['rows'] == [] and read(p, 99)['index'] == 0   # 없는 시트는 첫 시트


def test_display_formats_follow_the_cell_style(tmp_path):
    formats = [(164, 'yyyy&quot;년&quot; m&quot;월&quot; d&quot;일&quot;'), (165, '#,##0&quot;원&quot;;[Red]\\(#,##0\\)'), (166, '[$₩-412]#,##0')]
    xfs = (0, 14, 10, 3, 164, 165, 166, 20, 22, 4)
    cells = [(1, 45000), (2, 0.0525), (3, 1234567.4), (4, 45000), (5, -1500), (6, 3000), (7, 0.75), (8, 45000.5), (9, 1234.5)]
    data = '<row r="1">' + ''.join(f'<c r="{col_name(i - 1)}1" s="{s}"><v>{v}</v></c>' for i, (s, v) in enumerate(cells, 1)) + '</row>'
    got = read(make_xlsx(tmp_path / 'f.xlsx', [('S', data, None)], formats=formats, xfs=xfs))['sheet']['rows'][0][1]
    assert got == ['2023-03-15', '5.25%', '1,234,567', '2023-03-15', '(1,500)', '₩3,000', '18:00', '2023-03-15 12:00', '1,234.50']


def test_general_numbers_like_excel():
    assert format_value(3.0, 'General') == '3' and format_value(0.1 + 0.2, 'General') == '0.3'
    assert format_value(1e20, 'General') == '1e+20' and format_value(-2.5, '') == '-2.5'
    assert format_value(1500, '0.00E+00') == '1.50E+03' and format_value(0, '0;-0;"없음"') == '없음'
    assert format_value(1.5, '[h]:mm') == '36:00' and format_value(45000, 'yyyy-mm-dd', date1904=True) == '2027-03-16'


def test_columns_start_at_the_first_used_column_and_rows_without_refs(tmp_path):
    data = '<row r="3"><c r="C3"><v>1</v></c><c r="E3"><v>2</v></c></row><row><c><v>3</v></c><c><v>4</v></c></row>'
    s = read(make_xlsx(tmp_path / 'c.xlsx', [('S', data, None)]))['sheet']
    assert s['first_col'] == 0 and s['rows'][0] == [3, ['', '', '1', '', '2']] and s['rows'][1] == [4, ['3', '4']]
    s = read(make_xlsx(tmp_path / 'd.xlsx', [('S', '<row r="2"><c r="B2"><v>1</v></c><c r="D2"><v>2</v></c></row>', None)]))['sheet']
    assert s['first_col'] == 1 and s['cols'] == 3 and s['rows'] == [[2, ['1', '', '2']]]
    assert col_index('A') == 0 and col_index('AA') == 26 and col_name(27) == 'AB'


def test_limits_cut_the_sheet(tmp_path, monkeypatch):
    monkeypatch.setattr(sheet, 'MAX_ROWS', 3)
    data = ''.join(f'<row r="{r}"><c r="A{r}"><v>{r}</v></c></row>' for r in range(1, 11))
    s = read(make_xlsx(tmp_path / 'l.xlsx', [('S', data, None)]))['sheet']
    assert [r[0] for r in s['rows']] == [1, 2, 3] and s['truncated']


def test_cache_follows_file_changes_and_does_not_hold_the_file(tmp_path):
    p = make_xlsx(tmp_path / 'k.xlsx', [('A', '<row r="1"><c r="A1"><v>1</v></c></row>', None)])
    assert read(p)['sheet']['rows'] == [[1, ['1']]]
    p.unlink()   # 읽은 뒤 파일을 열어 두지 않는다 (엑셀이 바꿔 끼우며 저장할 수 있게)
    make_xlsx(p, [('B', '<row r="1"><c r="A1"><v>2</v></c><c r="B1"><v>3</v></c></row>', None)])
    got = read(p)
    assert got['sheets'][0]['name'] == 'B' and got['sheet']['rows'] == [[1, ['2', '3']]]


@pytest.mark.parametrize('name, data, status', [
    ('a.xls', b'\xd0\xcf\x11\xe0', 415),     # 옛 형식
    ('a.xlsx', b'not a zip', 422),           # 깨진 파일
])
def test_unsupported_and_broken_files(tmp_path, name, data, status):
    p = tmp_path / name
    p.write_bytes(data)
    with pytest.raises(SheetError) as err:
        read(p)
    assert err.value.status == status


def test_huge_parts_are_refused(tmp_path, monkeypatch):
    p = make_xlsx(tmp_path / 'b.xlsx', [('S', '<row r="1"><c r="A1"><v>1</v></c></row>' * 50, None)])
    monkeypatch.setattr(sheet, 'MAX_PART', 100)   # 압축 푼 크기가 한도를 넘는 부분 (압축 폭탄)
    with pytest.raises(SheetError) as err:
        read(p)
    assert err.value.status == 413

