#!/usr/bin/env python3
"""변환 결과를 원본과 맞춰 본다. 앱 없이 도는 정적 점검이다.

    python verify.py 문서.md 읽은폴더

살피는 것: 쪽 수, 쪽마다 원본 글이 빠졌는지, 그림 파일, 칸·주석·코드 짝, 격자의 칸 이름, 넘칠 듯한 칸 (약값).
정확한 넘침과 대비는 화면을 그려야 하니 Lectern 의 '점검'이 본다.
--seal 은 다 고친 뒤 쓴다: 쪽마다 지문과 옮긴 방식을 변환기록에 적고 안 쓰는 쪽 그림을 지운다.
"""
import argparse
import hashlib
import json
import math
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

FOOT = ('dt', 'ftr', 'sldNum')
HEAD = re.compile(r'^:::\s*(\S+)(.*)$')
IMG = re.compile(r'!\[[^\]]*\]\((<[^>]+>|[^)\s]+)\)')
LAYOUTS = {'two': 'ab', 'two-left': 'ab', 'two-right': 'ab', 'three': 'abc', 'quad': 'abcd', 'left-stack': 'abc', 'right-stack': 'abc',
           'kpi': 'abcde', 'kpi-two': 'abcde', 'stack': 'ab'}


def words(text):
    return Counter(re.findall(r'[0-9a-z가-힣]+', text.lower()))


def source_words(slide):
    out = Counter()
    for s in slide['shapes']:
        if s.get('ph') in FOOT or s.get('hidden'):
            continue
        for p in s.get('paras', []):
            out.update(words(p['text']))
        for row in s.get('rows', []):
            for c in row:
                if not c.get('merged'):
                    out.update(words(c.get('text', '')))
        for n in s.get('nodes', []):
            out.update(words(n['text']))
    return out


def split_slides(md):
    body = md
    if md.startswith('---'):
        end = md.find('\n---', 3)
        body = md[end + 4:] if end > 0 else md
    parts, buf, fence = [], [], None
    for line in body.split('\n'):
        m = re.match(r'^(`{3,}|~{3,})', line)
        if m:
            mark = m.group(1)
            if fence is None:
                fence = mark
            elif line.strip() == fence or line.strip().startswith(fence):
                fence = None
        if fence is None and re.fullmatch(r'---\s*', line) and (not buf or not buf[-1].strip()):
            parts.append('\n'.join(buf))
            buf = []
            continue
        buf.append(line)
    parts.append('\n'.join(buf))
    return parts


def plain(text):
    text = re.sub(r'data:image/[^)\'"\s]+', '', text)
    text = re.sub(r'!\[[^\]]*\]\([^)]*\)', ' ', text)
    # 표시 글자만 뺀다. 경로의 \\ 는 낱말 사이이니 빈칸으로, 윗첨자 앞의 ** 는 낱말 안이니 없앤다
    text = re.sub(r'</?su[bp]>', '', text)
    return text.replace('\\\\', ' ').replace('\\', '').replace('*', '').replace('&lt;', '<').replace('<br>', ' ')


def tracks(spec, count, total, gap):
    """격자 줄·열의 px. auto 는 제목 줄이라 어림 값을 쓴다."""
    items = spec.split() if spec else ['1fr'] * count
    if len(items) != count:
        items = ['1fr'] * count
    fixed = sum(float(i[:-2]) for i in items if i.endswith('px')) + sum(62 for i in items if i == 'auto')
    room = total - fixed - gap * (count - 1)
    parts = sum(float(i[:-2]) for i in items if i.endswith('fr')) or 1
    out = []
    for i in items:
        out.append(float(i[:-2]) if i.endswith('px') else 62 if i == 'auto' else room * float(i[:-2]) / parts if i.endswith('fr') else room / count)
    return out


def need_height(lines, width, size):
    """칸의 글이 차지할 높이를 어림한다. 그림은 줄어드니 세지 않는다."""
    total, fence, chart = 0, False, False
    for line in lines:
        if line.startswith(('```', '~~~')):
            chart = not fence and bool(re.match(r'^`{3,}\s*(vega-lite|echarts|plotly|dot|mermaid)', line))
            fence = not fence
            continue
        if fence:
            total += 0 if chart else 1.6 * 14
            continue
        text = line.strip()
        if not text or text.startswith(('![', '[![')):
            continue
        if text.startswith('|'):
            total += 40 * (size or 14) / 14 if not re.match(r'^\|[-:| ]+\|$', text) else 0
            continue
        s = size or 18
        text = re.sub(r'^([-#>]+|\d+\.)\s*', '', text).replace('*', '')
        ko = len(re.findall(r'[가-힣]', text))
        total += max(1, math.ceil((ko * 1.28 + (len(text) - ko) * .72) * s / max(width - 30, 60))) * 1.95 * s
    return total


def fit_checks(n, text, wide):
    grid = re.search(r'<!--\s*grid:\s*(.+?)\s*-->', text)
    cols = re.search(r'<!--\s*cols:\s*(.+?)\s*-->', text)
    rows = re.search(r'<!--\s*rows:\s*(.+?)\s*-->', text)
    out = []
    cells = re.findall(r'^:::\s*(\S+)(.*?)\n(.*?)^:::\s*$', text, flags=re.S | re.M)
    table = None
    if grid:
        table = [r.split() for r in grid[1].split('/')]
        if len({len(r) for r in table}) != 1:
            return out
        ws = tracks(cols[1] if cols else '', len(table[0]), wide, 18)
        spec = rows[1] if rows else ' '.join('auto' if 't' in r else '1fr' for r in table)
        hs = tracks(spec, len(table), 624, 14)
    for name, rest, body in cells:
        words = rest.split()
        size = next((float(w) for w in words if re.fullmatch(r'\d+(\.\d+)?', w) and 'at' not in words), None)
        if 'at' in words:
            i = words.index('at')
            try:
                w, h = float(words[i + 3]), float(words[i + 4])
            except (ValueError, IndexError):
                continue
            size = next((float(x) for x in words[i + 5:] if x.replace('.', '').isdigit()), None) or next((float(x) for x in words[:i] if x.replace('.', '').isdigit()), None)
        elif table:
            spots = [(r, c) for r, row in enumerate(table) for c, v in enumerate(row) if v == name]
            if not spots:
                continue
            w = sum(ws[c] for c in sorted({c for _, c in spots})) + 18 * (len({c for _, c in spots}) - 1)
            h = sum(hs[r] for r in sorted({r for r, _ in spots})) + 14 * (len({r for r, _ in spots}) - 1)
        else:
            continue
        if 'kpi' in words or len([l for l in body.split('\n') if l.strip()]) < 3:
            continue
        pad = 24 if any(x in words for x in ('card', 'accent', 'dark', 'note')) else 0
        need = need_height(body.split('\n'), w, size)
        if need > (h - pad) * 1.3:
            out.append(('주의', f'{n}쪽: 칸 {name} 이 약 {round(need - h + pad)}px 넘칠 듯합니다 (칸 높이 {round(h)}px)'))
    return out


def check_slide(n, text, base):
    out = []
    if '<!--' in re.sub(r'<!--.*?-->', '', text, flags=re.S):
        out.append(('오류', f'{n}쪽: 주석이 닫히지 않았습니다'))
    lines = text.split('\n')
    inside, fence, names = None, False, []
    for i, line in enumerate(lines):
        if line.startswith(('```', '~~~')):
            fence = not fence
            continue
        if fence:
            continue
        if line.strip() == ':::':
            if inside is None:
                out.append(('오류', f'{n}쪽: 짝이 없는 ::: 가 있습니다'))
            inside = None
            continue
        m = HEAD.match(line)
        if m:
            if inside is not None:
                out.append(('오류', f'{n}쪽: 칸 {inside} 이 닫히기 전에 칸 {m[1]} 이 열렸습니다'))
            inside = m[1]
            names.append((m[1], m[2]))
    if inside is not None:
        out.append(('오류', f'{n}쪽: 칸 {inside} 의 닫는 ::: 가 없습니다'))
    if fence:
        out.append(('오류', f'{n}쪽: 코드 블록이 닫히지 않았습니다'))
    seen = [a for a, _ in names]
    for name, c in Counter(seen).items():
        if c > 1:
            out.append(('오류', f'{n}쪽: 칸 {name} 이 두 번 나옵니다'))
    grid = re.search(r'<!--\s*grid:\s*(.+?)\s*-->', text)
    layout = re.search(r'<!--\s*layout:\s*(\S+)\s*-->', text)
    allowed = None
    if grid:
        rows = [r.split() for r in grid[1].split('/')]
        if len({len(r) for r in rows}) != 1:
            out.append(('오류', f'{n}쪽: 격자의 줄마다 칸 수가 다릅니다'))
        allowed = {c for r in rows for c in r} - {'.', 't'}
    elif layout:
        if layout[1] not in LAYOUTS:
            out.append(('오류', f"{n}쪽: 배치 '{layout[1]}' 이 없습니다"))
        else:
            allowed = set(LAYOUTS[layout[1]])
    if allowed is not None:
        for name, rest in names:
            if name not in allowed and ' at ' not in f' {rest} ':
                out.append(('오류', f'{n}쪽: 칸 {name} 이 배치에 없습니다'))
    for m in IMG.finditer(re.sub(r'<!--.*?-->', '', text, flags=re.S)):
        p = m[1].strip('<>')
        if not re.match(r'[a-z]+:', p) and not (base / p).exists():
            out.append(('오류', f'{n}쪽: 그림 {p} 이 없습니다'))
    if re.search(r'[^\s*]\*\*[\w가-힣]', re.sub(r'\*\*[^*\n]+\*\*(?=\s|$|[.,:;)!?])', '', text)) and re.search(r'[.,:;!?%)\]]\*\*[\w가-힣]', text):
        out.append(('주의', f'{n}쪽: 문장부호로 끝난 굵은 글 뒤에 글자가 붙어 별표가 보일 수 있습니다'))
    return out


def seal(md_path, parts):
    """쪽마다 지문을 남긴다. 되돌릴 때 지문이 같은 쪽은 원본 pptx 의 쪽을 그대로 쓸 수 있다."""
    record = md_path.with_name(md_path.stem + '-변환기록.json')
    if not record.exists():
        return
    data = json.loads(record.read_text(encoding='utf-8'))
    whole = '\n'.join(parts)
    for rec, part in zip(data['slides'], parts):
        rec['sha1'] = hashlib.sha1(part.strip().encode('utf-8')).hexdigest()
        shown = re.sub(r'<!--.*?-->', '', part, flags=re.S)
        if re.search(r'쪽\d{3}[^/)>]*\.png', shown):
            # 쪽 그림을 오려 쓴 쪽. 칸이 둘 이상이면 글은 칸으로 뺀 것이다
            rec['how'] = 'mixed' if len(re.findall(r'^:::\s*\S', shown, flags=re.M)) > 1 else 'picture'
        elif rec.get('how') == 'picture':
            rec['how'] = 'rebuilt'
            rec.pop('picture_text', None)
    record.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    work = md_path.parent / '.pptx-work' / md_path.stem
    if work.exists():      # 되돌릴 때 바뀐 글을 찾는 기준이다
        shutil.copyfile(md_path, work / 'sealed.md')
    box = md_path.with_name(md_path.stem + '-그림')
    for f in box.glob('쪽*.png') if box.exists() else []:
        if f.name not in whole:
            f.unlink()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('md')
    ap.add_argument('read')
    ap.add_argument('--seal', action='store_true', help='다 고친 뒤 쪽마다 지문을 변환기록에 적는다')
    args = ap.parse_args(argv)
    md_path = Path(args.md)
    md = md_path.read_text(encoding='utf-8')
    data = json.loads((Path(args.read) / 'deck.json').read_text(encoding='utf-8'))
    parts = split_slides(md)
    slides = data['slides']
    issues = []
    if not md.startswith('---') or 'marp: true' not in md[:400]:
        issues.append(('오류', '맨 앞 설정에 marp: true 가 없습니다'))
    if len(parts) != len(slides):
        issues.append(('주의', f'쪽 수가 다릅니다: 원본 {len(slides)}, 문서 {len(parts)}'))
    wide = 848 if re.search(r'^size:\s*4:3', md[:600], flags=re.M) else 1168
    for i, part in enumerate(parts, 1):
        issues += check_slide(i, part, md_path.parent)
        issues += fit_checks(i, part, wide)
    total = kept = editable = 0
    whole = words(plain(md))
    lost = Counter()
    for s in slides:
        src = source_words(s)
        total += sum(src.values())
        lost.update(src)
    lost_all = lost - whole
    kept = total - sum(lost_all.values())
    visible = words(plain(re.sub(r'<!--.*?-->', '', md, flags=re.S)))
    editable = sum((Counter(lost) & visible).values())
    per_slide = []
    if len(parts) == len(slides):
        for s, part in zip(slides, parts):
            miss = source_words(s) - words(plain(part))
            if sum(miss.values()) >= 3:
                per_slide.append((s['n'], sum(miss.values()), [w for w, _ in miss.most_common(6)]))
    notes_src = sum(1 for s in slides if s.get('notes'))
    notes_lost = 0
    if len(parts) == len(slides):
        for s, part in zip(slides, parts):
            if s.get('notes'):
                miss = words(s['notes']) - words(plain(part))
                if sum(miss.values()) > .1 * max(1, sum(words(s['notes']).values())):
                    notes_lost += 1
    report = {
        'slides': [len(slides), len(parts)],
        'text_kept_pct': round(100 * kept / max(1, total), 1),
        'text_editable_pct': round(100 * editable / max(1, total), 1),
        'notes_lost': [notes_lost, notes_src],
        'errors': [t for k, t in issues if k == '오류'],
        'warnings': [t for k, t in issues if k == '주의'],
        'slides_missing_text': [{'slide': a, 'words': b, 'sample': c} for a, b, c in per_slide[:30]],
    }
    print(json.dumps(report, ensure_ascii=False, indent=1))
    if args.seal and len(parts) == len(slides):
        seal(md_path, parts)
    return 1 if report['errors'] or per_slide else 0


if __name__ == '__main__':
    sys.exit(main())
