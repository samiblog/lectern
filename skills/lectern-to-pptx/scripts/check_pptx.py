#!/usr/bin/env python3
"""만든 pptx 를 문서와 맞춰 본다.

    python check_pptx.py 문서.md 결과.pptx [--render 폴더]

살피는 것: ZIP·XML 이 온전한지, 쪽 수, 쪽마다 문서의 글이 있는지, 노트.
PowerPoint 가 있으면 실제로 열어 보고 --render 폴더에 쪽 그림을 뽑는다. 파일을 고치지 않는다.
"""
import argparse
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lectern_md as lm  # noqa: E402


def words(text):
    return Counter(re.findall(r'[0-9a-z가-힣]+', text.lower()))


def source_words(slide):
    out = Counter()

    def blocks(items):
        for b in items:
            k = b['kind']
            if k in ('para', 'heading'):
                out.update(words(lm.plain(b['runs'])))
            elif k == 'list':
                for it in b['items']:
                    out.update(words(lm.plain(it['runs'])))
            elif k == 'table':
                for row in b['rows']:
                    for c in row:
                        out.update(words(lm.plain(c)))
            elif k == 'quote':
                blocks(b['blocks'])

    if slide['title']:
        out.update(words(lm.plain(slide['title'])))
    blocks(slide['body'])
    for c in slide['cells']:
        blocks(c['blocks'])
    return out


def pptx_slides(path):
    z = zipfile.ZipFile(path)
    bad = []
    for n in z.namelist():
        if n.endswith(('.xml', '.rels')):
            try:
                ET.fromstring(z.read(n))
            except ET.ParseError as e:
                bad.append(f'{n}: {e}')
    pres = z.read('ppt/presentation.xml').decode('utf-8')
    rels = z.read('ppt/_rels/presentation.xml.rels').decode('utf-8')
    targets = {}
    for tag in re.findall(r'<Relationship\b[^>]*>', rels):
        a = dict(re.findall(r'(\w+)="([^"]*)"', tag))
        targets[a['Id']] = a['Target']
    slides = []
    for rid in re.findall(r'<p:sldId\b[^>]*r:id="([^"]+)"', pres):
        target = targets[rid].lstrip('/')
        part = target if target.startswith('ppt/') else 'ppt/' + target
        text = z.read(part).decode('utf-8')
        notes = ''
        rel = part.replace('slides/', 'slides/_rels/') + '.rels'
        if rel in z.namelist():
            m = re.search(r'Target="\.\./notesSlides/([^"]+)"', z.read(rel).decode('utf-8'))
            if m:
                notes = ' '.join(re.findall(r'<a:t>([^<]*)</a:t>', z.read('ppt/notesSlides/' + m[1]).decode('utf-8')))
        paras = [''.join(re.findall(r'<a:t>([^<]*)</a:t>', p.replace('<a:br/>', '<a:t> </a:t>'))) for p in re.findall(r'<a:p>.*?</a:p>', text, flags=re.S)]
        behind = ''
        if rel in z.namelist():      # 레이아웃과 마스터의 글도 쪽에 보이는 글이다
            m = re.search(r'Target="\.\./slideLayouts/([^"]+)"', z.read(rel).decode('utf-8'))
            if m:
                behind = ' '.join(re.findall(r'<a:t>([^<]*)</a:t>', z.read('ppt/slideLayouts/' + m[1]).decode('utf-8')))
        slides.append({'text': (' '.join(paras) + ' ' + behind).replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>'), 'notes': notes})
    return slides, bad


THEME_NAMES = {'tx1': 'dk1', 'tx2': 'dk2', 'bg1': 'lt1', 'bg2': 'lt2'}


def luminance(c):
    r, g, b = (int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda v: v / 12.92 if v <= .03928 else ((v + .055) / 1.055) ** 2.4
    return .2126 * f(r) + .7152 * f(g) + .0722 * f(b)


def contrast_issues(path):
    """상자 바탕과 글자색이 비슷한 곳. 글 수를 세는 것만으로는 안 보이는 글을 못 찾는다."""
    z = zipfile.ZipFile(path)
    theme = {}
    for name in sorted(n for n in z.namelist() if re.fullmatch(r'ppt/theme/theme\d+\.xml', n))[:1]:
        for k, v in re.findall(r'<a:(dk1|lt1|dk2|lt2|accent[1-6])>\s*<a:\w+Clr\b[^>]*?(?:val|lastClr)="([0-9A-Fa-f]{6})"', z.read(name).decode('utf-8')):
            theme[k] = v

    def color(block):
        m = re.search(r'<a:srgbClr val="([0-9A-Fa-f]{6})"', block)
        if m:
            return m[1]
        m = re.search(r'<a:schemeClr val="(\w+)"\s*/>', block)
        return theme.get(THEME_NAMES.get(m[1], m[1])) if m else None

    out = []
    pres = z.read('ppt/presentation.xml').decode('utf-8')
    rels = dict(re.findall(r'Id="([^"]+)"[^>]*?Target="([^"]+)"', z.read('ppt/_rels/presentation.xml.rels').decode('utf-8')))
    rels.update({b: a for a, b in re.findall(r'Target="([^"]+)"[^>]*?Id="([^"]+)"', z.read('ppt/_rels/presentation.xml.rels').decode('utf-8'))})
    for n, rid in enumerate(re.findall(r'<p:sldId\b[^>]*r:id="([^"]+)"', pres), 1):
        t = rels[rid].lstrip('/')
        text = z.read(t if t.startswith('ppt/') else 'ppt/' + t).decode('utf-8')
        for piece in re.findall(r'<p:sp>.*?</p:sp>|<a:tc>.*?</a:tc>', text, flags=re.S):
            fill = re.search(r'</a:prstGeom>\s*<a:solidFill>(.*?)</a:solidFill>|<a:tcPr\b.*?(?:</a:ln[A-Z]>)\s*<a:solidFill>(.*?)</a:solidFill>\s*</a:tcPr>', piece, flags=re.S)
            back = color(fill[1] or fill[2]) if fill else None
            if not back:
                continue
            for run in re.findall(r'<a:r>\s*<a:rPr[^>]*>(.*?)</a:rPr>\s*<a:t>([^<]*)</a:t>', piece, flags=re.S):
                paint = re.search(r'<a:solidFill>(.*?)</a:solidFill>', run[0], flags=re.S)
                front = color(paint[1]) if paint else None
                if front:
                    x, y = sorted((luminance(front), luminance(back)), reverse=True)
                    if (x + .05) / (y + .05) < 2.5:
                        out.append(f'{n}쪽: 글자가 바탕과 비슷합니다: {run[1][:24]}')
    return out[:20]


def open_in_powerpoint(path, render):
    code = f'''
import os, sys
import pythoncom
import win32com.client as wc
path, out = sys.argv[1], sys.argv[2]
try:
    app = wc.GetActiveObject("PowerPoint.Application"); running = True
except pythoncom.com_error:
    app = wc.Dispatch("PowerPoint.Application"); running = False
saved = app.AutomationSecurity
app.AutomationSecurity = 3
pres = app.Presentations.Open(path, True, False, False)
n = pres.Slides.Count
if out:
    os.makedirs(out, exist_ok=True)
    w = round(720 * pres.PageSetup.SlideWidth / pres.PageSetup.SlideHeight)
    for s in pres.Slides:
        s.Export(os.path.join(out, f"{{s.SlideIndex:03d}}.png"), "PNG", w, 720)
pres.Close()
app.AutomationSecurity = saved
if not running and app.Presentations.Count == 0:
    app.Quit()
print(n)
'''
    try:
        import win32com.client  # noqa: F401
    except ImportError:
        return None
    # 같은 파일이 열려 있으면 그 발표를 돌려받아 닫게 되니 복사본을 연다
    import shutil
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / 'check-copy.pptx'
        shutil.copyfile(path, copy)
        try:
            r = subprocess.run([sys.executable, '-I', '-c', code, str(copy), str(Path(render).resolve()) if render else ''], capture_output=True, text=True, encoding='utf-8', timeout=180)
        except subprocess.TimeoutExpired:
            return {'opened': False, 'error': 'PowerPoint 가 제한 시간 안에 끝내지 못했습니다. 복구 창이 떠 있을 수 있습니다'}
    if r.returncode == 0:
        return {'opened': True, 'slides': int(r.stdout.strip().split('\n')[-1])}
    return {'opened': False, 'error': r.stderr.strip().split('\n')[-1][:200]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('md')
    ap.add_argument('pptx')
    ap.add_argument('--render')
    args = ap.parse_args(argv)
    deck = lm.read_deck(args.md)
    slides, bad = pptx_slides(args.pptx)
    report = {'slides': [len(deck['slides']), len(slides)], 'broken_xml': bad[:5], 'slides_missing_text': [], 'notes_missing': []}
    total = lost = 0
    # 원본 쪽을 그대로 쓴 쪽은 맞춰 볼 것이 없다. 글이 레이아웃에 있을 수도 있다
    record = Path(args.md).with_name(Path(args.md).stem + '-변환기록.json')
    same = set()
    if record.exists():
        same = {r.get('sha1') for r in json.loads(record.read_text(encoding='utf-8')).get('slides', [])}
    if len(slides) == len(deck['slides']):
        for i, (s, p) in enumerate(zip(deck['slides'], slides), 1):
            if lm.fingerprint(deck['parts'][i - 1]) in same:
                continue
            src = source_words(s)
            miss = src - words(p['text'] + ' ' + p['notes'])
            total += sum(src.values())
            lost += sum(miss.values())
            if sum(miss.values()) >= 3:
                report['slides_missing_text'].append({'slide': i, 'words': sum(miss.values()), 'sample': [w for w, _ in miss.most_common(6)]})
            if s['notes'] and not p['notes'].strip():
                report['notes_missing'].append(i)
    report['text_kept_pct'] = round(100 * (total - lost) / max(1, total), 1)
    report['low_contrast'] = contrast_issues(args.pptx)
    report['powerpoint'] = open_in_powerpoint(args.pptx, args.render)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    ok = not bad and report['slides'][0] == report['slides'][1] and not report['slides_missing_text'] and not report['low_contrast']
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
