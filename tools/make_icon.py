"""앱 아이콘 만들기: assets/lectern.svg → assets/lectern.ico

16~256px PNG를 담은 ICO를 만든다 (Windows Vista 이후는 ICO 안의 PNG를 읽는다).
SVG를 그리는 데 playwright(Chromium)를 쓴다 — requirements-dev.txt. 결과 ico 는 저장소에 넣어 두므로
아이콘을 바꿀 때만 다시 실행하면 된다.

    python tools/make_icon.py
"""
from __future__ import annotations

import struct
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / 'assets'
SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]


def render(svg: str) -> list[bytes]:
    from playwright.sync_api import sync_playwright

    pngs = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for size in SIZES:
            page = browser.new_page(viewport={'width': size, 'height': size})
            page.set_content(f'<style>html, body {{ margin: 0; background: transparent; }} '
                             f'svg {{ display: block; width: {size}px; height: {size}px; }}</style>{svg}')
            pngs.append(page.screenshot(omit_background=True))
            page.close()
        browser.close()
    return pngs


def ico(pngs: list[bytes]) -> bytes:
    """ICONDIR + ICONDIRENTRY × n + PNG 데이터. 너비·높이 칸의 0은 256을 뜻한다."""
    head = struct.pack('<HHH', 0, 1, len(pngs))
    offset = len(head) + 16 * len(pngs)
    entries, data = b'', b''
    for size, png in zip(SIZES, pngs):
        entries += struct.pack('<BBBBHHII', size % 256, size % 256, 0, 0, 1, 32, len(png), offset + len(data))
        data += png
    return head + entries + data


def main() -> None:
    svg = (ASSETS / 'lectern.svg').read_text(encoding='utf-8')
    out = ASSETS / 'lectern.ico'
    out.write_bytes(ico(render(svg)))
    print(f'만들었습니다: {out} ({", ".join(map(str, SIZES))}px)')


if __name__ == '__main__':
    main()
