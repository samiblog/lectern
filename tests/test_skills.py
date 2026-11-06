"""스킬 시험: Lectern 문서 → pptx → Lectern 문서 → pptx. PowerPoint 없이 돈다 (실제로 여는 시험은 docs/TESTING.md)."""
import hashlib
import importlib
import io
import json
import re
import subprocess
import sys
import types
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FORWARD = ROOT / 'skills' / 'pptx-to-lectern' / 'scripts'
BACK = ROOT / 'skills' / 'lectern-to-pptx' / 'scripts'
DECK = """---
marp: true
title: 시험 발표
paginate: true
footer: 시험 꼬리말
---

<!-- _class: lead -->

# 시험 발표

부제목 글

---

<!-- layout: two -->

## 표와 차트

::: a card
### 소제목

- 첫째 **굵게** 항목
  - 아래 단계
- H<sub>2</sub>O [링크](https://example.com/a)
:::

::: b
| 분기 | 값 |
|---|---:|
| 1분기 | 10 |
| 2분기 | 20 |
:::

<!-- 발표자 노트입니다 -->

---

<!-- hidden: true -->
<!-- grid: t t / a b -->
<!-- links: a>b -->

## 차트와 선

::: a
```vega-lite
{"width": "container", "data": {"values": [{"분기": "1", "값": 3}, {"분기": "2", "값": 5}]}, "mark": "bar", "encoding": {"x": {"field": "분기", "type": "ordinal"}, "y": {"field": "값", "type": "quantitative"}}}
```
:::

::: b kpi
**96%**
정시 배송
:::
"""


def run(script, *args):
    r = subprocess.run([sys.executable, '-I', str(script), *map(str, args)], capture_output=True, text=True, encoding='utf-8', timeout=120)
    return r


def slide_parts(path):
    with zipfile.ZipFile(path) as z:
        pres = z.read('ppt/presentation.xml').decode('utf-8')
        rels = z.read('ppt/_rels/presentation.xml.rels').decode('utf-8')
        targets = {}
        for tag in re.findall(r'<Relationship\b[^>]*>', rels):
            a = dict(re.findall(r'(\w+)="([^"]*)"', tag))
            targets[a['Id']] = a['Target']
        return [z.read('ppt/' + targets[rid]) for rid in re.findall(r'<p:sldId\b[^>]*r:id="([^"]+)"', pres)]


@pytest.fixture()
def pptx(tmp_path):
    md = tmp_path / 'deck.md'
    md.write_text(DECK, encoding='utf-8')
    r = run(BACK / 'build_pptx.py', md, '--style', 'deck')
    assert r.returncode == 0, r.stderr
    return tmp_path / 'deck.pptx'


def test_export_keeps_structure(pptx):
    with zipfile.ZipFile(pptx) as z:
        names = z.namelist()
        assert sum(1 for n in names if re.fullmatch(r'ppt/slides/slide\d+\.xml', n)) == 3
        assert any(n.startswith('ppt/charts/chart') for n in names), '값을 고칠 수 있는 차트'
        assert any(n.startswith('ppt/embeddings/') for n in names), '차트의 데이터 편집'
        assert any(n.startswith('ppt/notesSlides/') for n in names)
    slides = slide_parts(pptx)
    text = b''.join(slides).decode('utf-8')
    assert '<a:tbl>' in text and '<p:cxnSp>' in text and 'type="slidenum"' in text
    assert 'baseline="-25000"' in text, '아래 첨자'
    assert b'show="0"' in slides[2], '숨긴 장'
    assert b'b="1"' in slides[1]


def test_export_uses_slide_style(pptx):
    first = slide_parts(pptx)[0].decode('utf-8')
    assert '17293D' in first, '표지의 어두운 바탕'


def test_check_reports_text(tmp_path, pptx):
    r = run(BACK / 'check_pptx.py', tmp_path / 'deck.md', pptx)
    report = json.loads(r.stdout)
    assert report['slides'] == [3, 3] and not report['broken_xml'] and not report['slides_missing_text']


def test_refuses_to_overwrite(tmp_path, pptx):
    r = run(BACK / 'build_pptx.py', tmp_path / 'deck.md')
    assert 'error' in json.loads(r.stdout)


def test_round_trip_reuses_untouched_slides(tmp_path, pptx):
    out = tmp_path / 'back'
    r = run(FORWARD / 'convert.py', pptx, out, '--name', 'd', '--no-powerpoint')
    assert (out / 'd.md').exists(), r.stdout + r.stderr
    report = json.loads(r.stdout[r.stdout.index('{\n'):])
    assert report['text_kept_pct'] >= 99 and not report['errors']
    run(FORWARD / 'verify.py', out / 'd.md', out / '.pptx-work' / 'd', '--seal')
    record = json.loads((out / 'd-변환기록.json').read_text(encoding='utf-8'))
    assert all(s.get('sha1') for s in record['slides'])
    assert record['snapshot'].endswith('source.pptx')

    r = run(BACK / 'build_pptx.py', out / 'd.md', '--out', out / 'same.pptx')
    info = json.loads(r.stdout)
    assert info['reused'] == 3 and info['rebuilt'] == 0
    assert [hashlib.sha1(x).digest() for x in slide_parts(pptx)] == [hashlib.sha1(x).digest() for x in slide_parts(out / 'same.pptx')]

    text = (out / 'd.md').read_text(encoding='utf-8')
    (out / 'd.md').write_text(text.replace('소제목', '고친 소제목'), encoding='utf-8')
    r = run(BACK / 'build_pptx.py', out / 'd.md', '--out', out / 'edit.pptx')
    info = json.loads(r.stdout)
    assert info['reused'] == 2 and info['patched'] == 1 and info['rebuilt'] == 0, '글만 고친 쪽은 다시 만들지 않는다'
    edited, original = slide_parts(out / 'edit.pptx')[1], slide_parts(pptx)[1]
    assert '고친 소제목'.encode() in edited
    assert edited.replace('고친 소제목'.encode(), '소제목'.encode()) == original, '바뀐 글자 말고는 원본 쪽 그대로'

    # 칸을 더하면 구조가 바뀌었으니 다시 만든다
    (out / 'd.md').write_text(text.replace('## 표와 차트', '## 표와 차트\n\n::: zz note at 900 560 300 80\n더한 칸\n:::'), encoding='utf-8')
    r = run(BACK / 'build_pptx.py', out / 'd.md', '--out', out / 'struct.pptx')
    info = json.loads(r.stdout)
    assert info['reused'] == 2 and info['patched'] == 0 and info['rebuilt'] == 1
    assert '더한 칸'.encode() in slide_parts(out / 'struct.pptx')[1]


def test_convert_refuses_edited_document(tmp_path, pptx):
    out = tmp_path / 'o'
    assert run(FORWARD / 'convert.py', pptx, out, '--name', 'd', '--no-powerpoint').returncode == 0
    (out / 'd.md').write_text((out / 'd.md').read_text(encoding='utf-8') + '\n고친 글\n', encoding='utf-8')
    r = run(FORWARD / 'convert.py', pptx, out, '--name', 'd', '--no-powerpoint')
    assert r.returncode == 2 and '고친 내용을 잃지 않게' in r.stdout


def test_password_file_is_refused_before_powerpoint(tmp_path):
    bad = tmp_path / 'locked.pptx'
    bad.write_bytes(bytes.fromhex('d0cf11e0a1b11ae1') + b'\0' * 64 + 'EncryptedPackage'.encode('utf-16-le'))
    r = run(FORWARD / 'convert.py', bad, tmp_path / 'o')
    assert r.returncode == 2 and '암호' in r.stdout


def test_from_md_finds_invented_numbers(tmp_path):
    src = tmp_path / 's.md'
    deck = tmp_path / 'd.md'
    src.write_text('# 보고\n\n## 시장\n\n가격은 9,120 달러다.\n', encoding='utf-8')
    deck.write_text('---\nmarp: true\n---\n\n## 보고\n\n## 시장\n\n가격은 9,120 달러, 재고는 77 이다.\n', encoding='utf-8')
    r = run(FORWARD / 'from_md.py', src, deck)
    report = json.loads(r.stdout)
    assert report['numbers_added'] == ['77'] and r.returncode == 1


def bright_template(tmp_path, pptx):
    """강조색이 노랑인 양식. 이런 양식에서 큰 숫자와 표 머리가 사라졌었다"""
    out = tmp_path / 'bright.pptx'
    with zipfile.ZipFile(pptx) as src, zipfile.ZipFile(out, 'w') as dst:
        for name in src.namelist():
            data = src.read(name)
            if name.startswith('ppt/theme/'):
                data = re.sub(rb'(<a:accent1><a:srgbClr val=")[0-9A-F]{6}', rb'\g<1>FFD24E', data)
            dst.writestr(name, data)
    return out


def test_template_with_bright_accent_stays_readable(tmp_path, pptx):
    md = tmp_path / 'deck.md'
    r = run(BACK / 'build_pptx.py', md, '--template', bright_template(tmp_path, pptx), '--out', tmp_path / 't.pptx')
    assert r.returncode == 0, r.stderr
    report = json.loads(run(BACK / 'check_pptx.py', md, tmp_path / 't.pptx').stdout)
    assert not report['low_contrast'], report['low_contrast']
    text = b''.join(slide_parts(tmp_path / 't.pptx')).decode('utf-8')
    assert 'schemeClr val="accent1"' not in text, '밝은 강조색을 글자나 표 머리에 쓰지 않는다'


def test_check_reports_invisible_text(tmp_path):
    md = tmp_path / 'c.md'
    md.write_text('---\nmarp: true\nstyle: |\n  .bad { background: #FFD24E; color: #FFE680; }\n---\n\n<!-- grid: t / a -->\n\n## 제목\n\n::: a bad\n안 보이는 글\n:::\n', encoding='utf-8')
    assert run(BACK / 'build_pptx.py', md, '--style', 'deck').returncode == 0
    r = run(BACK / 'check_pptx.py', md, tmp_path / 'c.pptx')
    assert json.loads(r.stdout)['low_contrast'] and r.returncode == 1


def test_baseline_stays_a_native_chart(tmp_path):
    md = tmp_path / 'r.md'
    spec = {'width': 'container', 'data': {'values': [{'달': '1월', '값': 3}, {'달': '2월', '값': 5}]},
            'encoding': {'x': {'field': '달', 'type': 'ordinal'}},
            'layer': [{'mark': 'bar', 'encoding': {'y': {'field': '값', 'type': 'quantitative'}, 'color': {'condition': {'test': "datum['값'] > 4", 'value': '#b4533c'}, 'value': '#5f7d95'}}},
                      {'mark': 'text', 'encoding': {'y': {'field': '값', 'type': 'quantitative'}, 'text': {'field': '값'}}},
                      {'mark': {'type': 'rule', 'color': '#123456'}, 'encoding': {'y': {'datum': 4}}}]}
    md.write_text(f'---\nmarp: true\n---\n\n<!-- grid: t / a -->\n\n## 차트\n\n::: a\n```vega-lite\n{json.dumps(spec, ensure_ascii=False)}\n```\n:::\n', encoding='utf-8')
    r = run(BACK / 'build_pptx.py', md, '--style', 'deck')
    assert '그림으로' not in r.stdout, r.stdout
    with zipfile.ZipFile(tmp_path / 'r.pptx') as z:
        chart = z.read('ppt/charts/chart1.xml').decode('utf-8')
    assert '<c:lineChart>' in chart and 'prstDash' in chart and '123456' in chart, '기준선'
    assert 'B4533C' in chart and '<c:dLbls>' in chart, '조건 색과 값 라벨'


def test_document_css_reaches_cells_and_tables(tmp_path):
    md = tmp_path / 'k.md'
    md.write_text('''---
marp: true
style: |
  .box { background: #112233; color: #FFFFFF; border: 3px solid #445566; border-radius: 0; }
  .box strong { color: #FFCC00; }
---

<!-- grid: t t / a b -->

<style scoped>
tbody tr:last-child td { font-weight: 700; background: #FFF1E6; }
td:nth-child(2) { color: #AA0000; }
</style>

## 제목

::: a kpi box
**96%** 달성
정시 배송
:::

::: b
| 이름 | 값 |
|---|---:|
| 가 | 1 |
| 합계 | 2 |
:::
''', encoding='utf-8')
    assert run(BACK / 'build_pptx.py', md, '--style', 'deck').returncode == 0
    slide = slide_parts(tmp_path / 'k.pptx')[0].decode('utf-8')
    assert '112233' in slide and 'FFCC00' in slide and 'w="28575"' in slide and '445566' in slide
    assert 'FFF1E6' in slide and 'AA0000' in slide
    sizes = {text.strip(): int(size) for size, text in re.findall(r'<a:r><a:rPr[^>]*\bsz="(\d+)".*?<a:t>([^<]*)</a:t></a:r>', slide, flags=re.S)}
    assert sizes['96%'] > sizes['달성'], '앱처럼 굵은 글만 크게'


def test_old_ppt_with_a_zip_tail_is_not_taken_for_pptx(tmp_path):
    """PowerPoint 가 저장한 .ppt 는 끝에 ZIP 조각이 있어 zipfile.is_zipfile 이 참이다."""
    fake = tmp_path / '옛형식.ppt'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('theme/theme1.xml', '<a/>')
    fake.write_bytes(bytes.fromhex('d0cf11e0a1b11ae1') + b'\0' * 600 + buf.getvalue())
    assert zipfile.is_zipfile(fake)
    r = run(FORWARD / 'convert.py', fake, tmp_path / 'o', '--no-powerpoint')
    assert r.returncode != 0
    assert 'Traceback' not in r.stderr
    assert 'PowerPoint' in r.stdout


def test_pywin32_without_powerpoint_is_not_taken_for_powerpoint(monkeypatch):
    """실행기에는 pywin32 가 늘 있다. Office 가 없는 PC 에서 PowerPoint 를 부르다 실패하지 않는다."""
    win32com = types.ModuleType('win32com')
    win32com.client = types.ModuleType('win32com.client')
    winreg = types.ModuleType('winreg')
    winreg.HKEY_CLASSES_ROOT = 0

    def missing(*_):
        raise OSError('없는 키')

    winreg.OpenKey = missing
    monkeypatch.setitem(sys.modules, 'win32com', win32com)
    monkeypatch.setitem(sys.modules, 'win32com.client', win32com.client)
    monkeypatch.setitem(sys.modules, 'winreg', winreg)
    monkeypatch.syspath_prepend(str(FORWARD))
    monkeypatch.syspath_prepend(str(BACK))
    convert = importlib.import_module('convert')
    check_pptx = importlib.import_module('check_pptx')
    assert convert.has_com() is False
    assert check_pptx.open_in_powerpoint('x.pptx', None) is None


def test_skill_files_are_complete():
    for name in ('pptx-to-lectern', 'lectern-to-pptx'):
        text = (ROOT / 'skills' / name / 'SKILL.md').read_text(encoding='utf-8')
        assert text.startswith(f'---\nname: {name}\n')
        for script in re.findall(r'scripts/(\w+\.py)', text):
            assert (ROOT / 'skills' / name / 'scripts' / script).exists(), script
    assert "('skills', 'skills')" in (ROOT / 'lectern.spec').read_text(encoding='utf-8')
