#!/usr/bin/env python3
"""md 문서로 만든 슬라이드가 그 문서를 벗어나지 않았는지 본다.

    python from_md.py 원본문서.md 슬라이드.md

살피는 것: 칸·주석·그림 경로의 잘못, 원본의 제목이 슬라이드에 다 있는지, 원본의 숫자가 빠지지 않았는지,
슬라이드에 원본에 없는 숫자가 생기지 않았는지. 슬라이드는 글을 줄이므로 글 전체를 맞추지는 않는다.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify  # noqa: E402

NUMBER = re.compile(r'\d[\d,]*(?:\.\d+)?')


def body_of(text):
    if text.startswith('---'):
        end = text.find('\n---', 3)
        if end > 0:
            text = text[end + 4:]
    text = re.sub(r'<style[^>]*>.*?</style>', ' ', text, flags=re.S)
    return text


def visible(text):
    text = re.sub(r'<!--.*?-->', ' ', text, flags=re.S)
    return re.sub(r'!\[[^\]]*\]\([^)]*\)', ' ', text)


def numbers(text):
    text = re.sub(r'\]\([^)]*\)', '] ', text)                     # 링크 주소
    text = re.sub(r'#[0-9a-fA-F]{3,8}\b', ' ', text)               # 색 코드
    text = re.sub(r'^:::.*$', ' ', text, flags=re.M)              # 칸 머리 (at, 크기)
    text = re.sub(r'^```.*?^```', chart_values, text, flags=re.S | re.M)
    return {n.replace(',', '').rstrip('.') for n in NUMBER.findall(text)}


def chart_values(m):
    """차트 설정에서 data 의 값만 숫자로 친다. 폭이나 글자 크기는 내용이 아니다."""
    body = re.sub(r'^```.*$', '', m[0], flags=re.M)
    try:
        values = json.loads(body).get('data', {}).get('values')
    except (ValueError, AttributeError):
        return ' '
    return json.dumps(values, ensure_ascii=False) if values else ' '


def headings(text):
    out = []
    fence = False
    for line in text.split('\n'):
        if line.startswith('```'):
            fence = not fence
        m = None if fence else re.match(r'^#{1,4}\s+(.*)$', line)
        if m:
            out.append(re.sub(r'[*`]', '', m[1]).strip())
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('source')
    ap.add_argument('deck')
    args = ap.parse_args(argv)
    src = body_of(Path(args.source).read_text(encoding='utf-8'))
    deck_all = body_of(Path(args.deck).read_text(encoding='utf-8'))
    deck = visible(deck_all)
    words = re.sub(r'[*`\\]', '', deck_all)
    src_nums, deck_nums = numbers(src), numbers(deck)
    missing_heads = [h for h in headings(src) if h and h not in words]
    errors = []
    parts = verify.split_slides(Path(args.deck).read_text(encoding='utf-8'))
    for i, part in enumerate(parts, 1):
        errors += [text for kind, text in verify.check_slide(i, part, Path(args.deck).parent) if kind == '오류']
    report = {
        'errors': errors[:20],
        'headings': [len(headings(src)) - len(missing_heads), len(headings(src))],
        'headings_missing': missing_heads[:20],
        'numbers_missing': sorted(src_nums - numbers(deck_all))[:40],
        'numbers_added': sorted(deck_nums - src_nums)[:40],
    }
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 1 if report['numbers_added'] or errors else 0


if __name__ == '__main__':
    sys.exit(main())
