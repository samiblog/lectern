#!/usr/bin/env python3
"""쪽 그림에서 한 자리를 오린다. 좌표는 outline.md 와 같은 Lectern 쪽 좌표(px)다.

    python crop.py .pptx-work/문서이름/ref 쪽번호 x y 너비 높이 문서이름-그림/쪽013-도식.png

이름은 쪽NNN 으로 시작한다. 그래야 변환기록이 이 쪽을 그림 쪽으로 알아본다.
"""
import sys
from pathlib import Path

from PIL import Image


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 7:
        print(__doc__)
        return 2
    ref, n, out = Path(argv[0]), int(argv[1]), Path(argv[6])
    x, y, w, h = (float(v) for v in argv[2:6])
    img = Image.open(ref / f'{n:03d}.png')
    k = img.height / 720        # Lectern 쪽 높이는 늘 720 이다
    out.parent.mkdir(parents=True, exist_ok=True)
    img.crop((round(x * k), round(y * k), round((x + w) * k), round((y + h) * k))).save(out, optimize=True)
    print(out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
