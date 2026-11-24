"""README 의 화면 그림을 다시 찍는다 — docs/images/*.png (1440×900, 예제 프로젝트 samples).

    python tools/readme_shots.py            여섯 장 모두
    python tools/readme_shots.py doc dark   고른 것만

화면이 바뀌어 README 그림이 옛 모습이 되면 돌린다. 브라우저로 앱을 띄워(서버만) 찍으므로 창 테두리는 없다.
설정은 임시 폴더의 새 것 — 사용자의 Lectern 설정을 읽지도 바꾸지도 않는다.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools' / 'edges'))
from harness import serve, stop  # noqa: E402

OUT = ROOT / 'docs' / 'images'
SIZE = {'width': 1440, 'height': 900}


def shoot(names: set[str]) -> list[str]:
    base = Path(tempfile.mkdtemp(prefix='lec-readme-'))
    proj = base / 'samples'
    shutil.copytree(ROOT / 'samples', proj, copy_function=shutil.copy)   # 예제를 복사해 연다 — 보기만 하는 탭이 되지 않게. 수정 시각은 오늘로
    config = base / 'config'
    config.mkdir()
    (config / 'config.json').write_text(json.dumps({'language': 'ko', 'work_alerts': False, 'toc_visible': True}), encoding='utf-8')
    server, url, _ = serve(proj, config)
    made = []
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page(viewport=SIZE, device_scale_factor=1)

            def start(lang='ko', theme='auto'):
                if page.url.startswith('http'):   # 언어·스타일은 앱의 설정 저장으로 바꾸고 다시 불러온다
                    page.evaluate("(c) => import('/static/js/api.js').then((m) => m.saveConfig(c))", {'language': lang, 'theme': theme})
                    page.wait_for_timeout(400)
                    page.reload()
                else:
                    page.goto(url)
                page.wait_for_selector('#lec-tree .row.file', timeout=30000)
                page.wait_for_timeout(800)

            def open_doc(path, wait='#lec-view h1'):
                page.evaluate("(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: p }))", path)
                page.wait_for_selector(wait, timeout=20000)
                page.wait_for_function("() => ![...document.querySelectorAll('#lec-view pre.mermaid, #lec-view pre.lec-chart')].some((x) => !x.querySelector('svg, canvas') && !x.classList.contains('diagram-error'))", timeout=20000)
                page.wait_for_timeout(900)

            def save(name):
                page.mouse.move(SIZE['width'] - 5, SIZE['height'] - 5)   # 툴팁이 남지 않게
                page.wait_for_timeout(300)
                page.screenshot(path=str(OUT / f'{name}.png'))
                made.append(name)

            if names & {'doc', 'parts', 'spotlight', 'code'}:
                start()
                if 'doc' in names:
                    open_doc('research/구리-시장-동향.md')
                    save('doc')
                if 'code' in names:
                    page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open', { type: 'code', path: 'src/report.py' }))")
                    page.wait_for_selector('#lec-view .cv-head, #lec-view table, #lec-view pre', timeout=20000)
                    page.wait_for_timeout(900)
                    save('code')
                if 'parts' in names:
                    open_doc('reports/3분기-구리-구매-전략.md')
                    page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('parts', { path: '', kind: 'table' }))")   # 문서 탭 하나에 (D196)
                    page.wait_for_selector('#lec-view.parts-view .pv-done', timeout=20000)
                    page.wait_for_timeout(800)
                    save('parts')
                if 'spotlight' in names:
                    page.click('.side-tabs button[data-tab="files"]')
                    open_doc('reports/3분기-구리-구매-전략.md')
                    page.click('#lec-btn-spot')
                    page.wait_for_timeout(400)
                    page.keyboard.press('ArrowDown')
                    page.wait_for_timeout(700)
                    save('spotlight')
            if 'dark' in names:
                start(theme='dark')
                open_doc('reports/3분기-구리-구매-전략.md')   # 표의 캡션·자료 줄이 보이는 곳 (D184)
                page.evaluate("() => { const c = document.querySelector('#lec-content'); const t = [...document.querySelectorAll('#lec-view h2')][0]; if (t) c.scrollTop = t.offsetTop - 20; }")
                page.wait_for_timeout(600)
                save('dark')
            if 'en' in names:
                start(lang='en')
                open_doc('research/구리-시장-동향.md')
                save('en')
            b.close()
    finally:
        stop(server, base)
    return made


if __name__ == '__main__':
    want = set(sys.argv[1:]) or {'doc', 'code', 'parts', 'spotlight', 'dark', 'en'}
    print('찍은 것:', shoot(want))
