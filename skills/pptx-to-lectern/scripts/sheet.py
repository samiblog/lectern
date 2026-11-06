#!/usr/bin/env python3
"""쪽 그림을 한 장에 모은다. 쪽이 많은 발표를 몇 번의 읽기로 훑으려고 쓴다.

    python sheet.py .pptx-work/문서이름/ref 출력폴더 [--pages 3,5-9] [--per 12]
"""
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('ref')
    ap.add_argument('out')
    ap.add_argument('--pages')
    ap.add_argument('--per', type=int, default=12)
    args = ap.parse_args(argv)
    files = sorted(Path(args.ref).glob('[0-9][0-9][0-9].png'))
    if args.pages:
        want = set()
        for bit in args.pages.split(','):
            a, _, b = bit.partition('-')
            want.update(range(int(a), int(b or a) + 1))
        files = [f for f in files if int(f.stem) in want]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cols, tw = 3, 500
    for k in range(0, len(files), args.per):
        part = files[k:k + args.per]
        first = Image.open(part[0])
        th = round(tw * first.height / first.width)
        rows = -(-len(part) // cols)
        sheet = Image.new('RGB', (cols * (tw + 8) + 8, rows * (th + 26) + 8), (90, 90, 90))
        draw = ImageDraw.Draw(sheet)
        for i, f in enumerate(part):
            x, y = 8 + (i % cols) * (tw + 8), 8 + (i // cols) * (th + 26)
            draw.text((x, y), f.stem, fill=(255, 255, 255))
            with Image.open(f) as img:
                sheet.paste(img.convert('RGB').resize((tw, th)), (x, y + 16))
        name = out / f'sheet-{k // args.per + 1}.png'
        sheet.save(name)
        print(name)
    return 0


if __name__ == '__main__':
    sys.exit(main())
