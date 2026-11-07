#!/usr/bin/env python3
"""pptx 를 '참고 양식'으로 읽는다. 글은 쓰지 않고 모양만 뽑는다.

    python reference.py 양식.pptx 출력폴더 [--name 이름]
    python reference.py --active 출력폴더 [--pick 이름] [--name 이름]     PowerPoint 에 띄워 둔 발표

출력: <이름>-양식.md   맨 앞 설정에 넣을 style, 쪽 종류별 배치와 쓰는 법, 쓰인 빈도
      .pptx-work/<이름>-양식/   source.pptx, deck.json, ref/ 쪽 그림, media/ 그림

md 문서의 내용을 이 양식으로 슬라이드로 만들 때 쓴다. 내보낼 때는 build_pptx.py --template source.pptx 로 같은 양식을 쓴다.
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import convert  # noqa: E402
import draft_md  # noqa: E402

FORMS = {'cover': '표지', 'section': '장 구분', 'bullets': '글 목록', 'text+picture': '글과 그림', 'picture': '그림', 'cards': '카드', 'table': '표', 'chart': '차트',
         'smartart': 'SmartArt', 'diagram': '도식', 'title-only': '제목만', 'blank': '빈 쪽'}


def recipes(data):
    """쪽 종류마다 대표 쪽과 그 쪽의 칸 자리를 뽑는다."""
    groups = {}
    for s in data['slides']:
        groups.setdefault(s['form'], []).append(s)
    out = []
    for form, slides in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        first = slides[0]
        boxes = [f"{sh['kind']} ({sh['x']},{sh['y']} {sh['w']}×{sh['h']})" for sh in first['shapes'] if 'x' in sh and sh.get('ph') not in ('dt', 'ftr', 'sldNum')][:8]
        layouts = Counter(s['layout'] for s in slides).most_common(3)
        out.append({'form': FORMS.get(form, form), 'count': len(slides), 'sample': first['n'], 'slides': [s['n'] for s in slides[:6]], 'layouts': layouts, 'boxes': boxes})
    return out


def sizes(data):
    title, body = Counter(), Counter()
    for s in data['slides']:
        for sh in s['shapes']:
            for p in sh.get('paras', []):
                for r in p['runs']:
                    if r.get('sz'):
                        (title if sh.get('ph') in ('title', 'ctrTitle') else body)[round(r['sz'])] += len(r['t'])
    return (title.most_common(1)[0][0] if title else None), (body.most_common(1)[0][0] if body else None)


def card_words(data):
    """쪽에 자주 나오는 상자 색을 칸 낱말 규칙으로."""
    seen = Counter()
    for s in data['slides']:
        for sh in s['shapes']:
            c = (sh.get('fill') or {}).get('c')
            if c and sh.get('kind') == 'text' and c.upper() not in ('#FFFFFF', '#000000'):
                seen[c.upper()] += 1
    out = []
    for c, _ in seen.most_common(4):
        fg = '#000000' if draft_md.lum(c) > .4 else '#FFFFFF'
        name = 'c' + c[1:].lower()
        out.append(f'.{name} {{ background: {c}; color: {fg}; --md-fg: {fg}; --md-strong: {fg}; --md-heading: {fg}; border-radius: 6px; padding: 12px 16px; }}')
    return out


def decorations(data, cover):
    lay = next((l for l in data['layouts'] if l['name'] == cover['layout']), None)
    out = []
    for d in (lay['decor'] if lay else []):
        if d.get('src'):
            out.append(f"그림 {d['src']} ({d.get('x')},{d.get('y')} {d.get('w')}×{d.get('h')}). `.pptx-work` 의 그림을 `![w:{d.get('w')}]` 로 쓴다")
        for p in d.get('paras', []):
            out.append(f"글 '{p['text'][:40]}'")
    return out


def write_guide(work, out, name, data):
    builder = draft_md.Builder(data, work, out / f'{name}-양식-초안.md', 3, str(work / 'ref') if (work / 'ref').exists() else None)
    slides = data['slides']
    bgs = Counter((s.get('bg') or {}).get('c', '#FFFFFF').upper() for s in slides)
    builder.base_bg = bgs.most_common(1)[0][0] if bgs else '#FFFFFF'
    css = builder.theme_css()
    title_pt, body_pt = sizes(data)
    lines = [f'# {name} 양식', '', f"원본 쪽 {len(slides)} · 크기 {data['size']['px']} → Lectern {data['size']['target']} · 테마 {data['theme']['name']}", '']
    lines += ['## 맨 앞 설정', '', '새 문서의 맨 앞 설정에 넣는다.', '', '```yaml', 'marp: true', 'paginate: true' if data.get('page_numbers') else 'paginate: false']
    if data['size']['target'].startswith('960'):
        lines.append('size: 4:3')
    if data.get('footer'):
        lines.append(f"footer: {json.dumps(data['footer'], ensure_ascii=False)}")
    lines += ['style: |', *['  ' + re.sub(r'url\(data:[^)]*\)', 'url(data:…)', l) for l in css], '```', '']
    has_logo = any('data:image' in l for l in css)
    if has_logo:
        lines += ['로고는 `.pptx-work` 의 `style.txt` 에 전체 글이 있다. 그 파일의 내용을 쓴다.', '']
    (work / 'style.txt').write_text('\n'.join(css), encoding='utf-8')
    lines += ['## 글자', '', f'원본의 제목은 {title_pt}pt, 본문은 {body_pt}pt 다. 슬라이드 크기가 같으면 칸 크기로 따를 수 있다.', '']
    words = card_words(data)
    if words:
        lines += ['## 칸 색', '', '양식의 상자 색이다. `style` 에 넣고 칸 머리에 낱말을 쓴다 (`::: a c123abc`).', '', '```css', *words, '```', '']
    lines += ['## 표지', '']
    cover = next((s for s in slides if s['form'] == 'cover'), slides[0] if slides else None)
    if cover:
        bg = (cover.get('bg') or {}).get('c')
        lines += [f"표지는 {cover['n']}쪽을 본다. 바탕 {bg or '없음'}. 이 양식의 표지는 다음 지시어로 만든다.", '', '```markdown', '<!-- _class: lead -->', '<!-- _paginate: false -->']
        if bg:
            dark = draft_md.lum(bg) < .4
            lines += [f'<!-- _backgroundColor: {bg} -->', f"<!-- _color: {'#FFFFFF' if dark else '#17293D'} -->"]
        lines += ['```', '']
        left = [sh for sh in cover['shapes'] if sh.get('ph') in ('ctrTitle', 'title') and 'x' in sh]
        if left and all((p.get('align') in (None, 'l')) for sh in left for p in sh.get('paras', [])):
            lines += ['양식의 표지는 왼쪽 정렬이다. 그 장에 이것을 더한다.', '', '```markdown', '<style scoped>', 'section { text-align: left; align-items: flex-start; }', '</style>', '```', '']
        marks = decorations(data, cover)
        if marks:
            lines += ['표지의 장식 (레이아웃에 있다). 로고에 다른 기관 이름이 있거나 글이 사실을 말하면 md 내용과 맞는지 보고 넣는다.', '', *[f'- {m}' for m in marks], '']
    lines += ['## 쪽 종류', '', '| 종류 | 쪽 수 | 대표 쪽 | 레이아웃 |', '|---|---:|---:|---|']
    plans = recipes(data)
    for r in plans:
        lines.append(f"| {r['form']} | {r['count']} | {r['sample']} | {', '.join(n for n, _ in r['layouts'])} |")
    lines += ['', '쪽 그림은 `.pptx-work` 의 `ref/` 에 있다. 비슷한 내용이면 그 쪽의 칸 짜임을 따른다.', '']
    for r in plans[:6]:
        lines += [f"### {r['form']} ({r['sample']}쪽)", '', *[f'- {b}' for b in r['boxes']], '']
    guide = out / f'{name}-양식.md'
    guide.write_text('\n'.join(lines), encoding='utf-8', newline='\n')
    return guide


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('paths', nargs='+')
    ap.add_argument('--active', action='store_true')
    ap.add_argument('--pick', default='')
    ap.add_argument('--name')
    ap.add_argument('--no-powerpoint', action='store_true')
    ap.add_argument('--force', action='store_true')
    args = ap.parse_args(argv)
    name = args.name
    forward = ['--no-draft', *(['--no-powerpoint'] if args.no_powerpoint else []), *(['--force'] if args.force else [])]
    if args.active:
        out = Path(args.paths[0]).resolve()
        forward += ['--active', str(out)]
        if args.pick:
            forward += ['--pick', args.pick]
    else:
        out = Path(args.paths[1]).resolve()
        forward += [args.paths[0], str(out)]
        name = name or Path(args.paths[0]).stem
    if name:
        forward += ['--name', f'{name}-양식']
    code = convert.main(forward)
    if code:
        return code
    work = max((p for p in (out / '.pptx-work').iterdir() if p.is_dir() and p.name.endswith('-양식') or p.is_dir()), key=lambda p: p.stat().st_mtime)
    data = json.loads((work / 'deck.json').read_text(encoding='utf-8'))
    stem = work.name[:-3] if work.name.endswith('-양식') else work.name
    guide = write_guide(work, out, stem, data)
    print(json.dumps({'guide': str(guide), 'work': str(work), 'template': str(work / 'source.pptx') if (work / 'source.pptx').exists() else None}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
