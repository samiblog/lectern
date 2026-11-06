#!/usr/bin/env python3
"""SVG 를 PNG 로. pptx 의 그림에는 PNG 가 있어야 한다. PowerPoint 가 있을 때만 된다.

    python svg_png.py 목록.json      목록은 svg 경로의 배열이다. 출력은 {svg: png} JSON 한 줄

새 빈 발표를 창 없이 만들어 쓰고 닫는다. 사용자의 발표에는 손대지 않는다. 이미 떠 있던 PowerPoint 는 닫지 않는다.
"""
import json
import sys
from pathlib import Path

import pythoncom
import win32com.client as wc


def main():
    paths = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    try:
        app = wc.GetActiveObject('PowerPoint.Application')
        running = True
    except pythoncom.com_error:
        app = wc.Dispatch('PowerPoint.Application')
        running = False
    pres = app.Presentations.Add(False)
    out = {}
    try:
        slide = pres.Slides.Add(1, 12)
        for p in paths:
            src = Path(p)
            target = src.with_suffix('.svg.png')
            sh = slide.Shapes.AddPicture(str(src), False, True, 0, 0)
            sh.Export(str(target), 2, round(sh.Width * 3), round(sh.Height * 3), 4)
            sh.Delete()
            if target.exists():
                out[str(src)] = str(target)
    finally:
        pres.Saved = True
        pres.Close()
        if not running and app.Presentations.Count == 0:
            app.Quit()
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
