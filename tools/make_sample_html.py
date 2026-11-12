"""예제의 html 발표(samples/slides/기초/07-html-발표.html)를 다시 만든다 — html 로 전환(D129)을 고친 뒤나 그 예제 발표를 고친 뒤.

예제 폴더는 앱에서 보기만 하는 곳이라(D71) 임시 폴더에 예제를 복사해 점검용 앱으로 열고, 슬라이드 창에서 사람이 하듯
'html 로 전환' → 만들기를 누른 결과를 예제 폴더로 가져온다. 가져오기 전에 브라우저에서 발표로 켜지는지,
바깥 요청이 없는지 본다. tests/test_htmlexport.py 가 이 파일이 지금의 impress.js·발표와 맞는지 확인한다.

    python tools/make_sample_html.py
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent / 'edges'))
from harness import ROOT, serve, stop, until  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

DECK = 'slides/기초/07-html-발표.md'
OUT = ROOT / 'samples' / Path(DECK).with_suffix('.html')
READY = """() => {
  const v = document.querySelector('#lec-view');
  if (!v || !v.classList.contains('lec-deck') || !v.querySelector('.lec-slide-wrap')) return false;
  return ![...v.querySelectorAll('pre.mermaid, pre.lec-chart')].some((p) => !p.querySelector('svg') && !p.classList.contains('diagram-error'));
}"""


def main() -> int:
    base = Path(tempfile.mkdtemp(prefix='lec-sample-html-'))
    proj = base / 'proj'
    shutil.copytree(ROOT / 'samples', proj)
    made = proj / Path(DECK).with_suffix('.html')
    made.unlink(missing_ok=True)   # 지난 결과가 있으면 '07-html-발표 2.html' 이 된다
    server, url, _ = serve(proj, base / 'config')
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page(viewport={'width': 1400, 'height': 900})
            page.goto(url)
            page.wait_for_selector('#lec-tree .row.file', timeout=20000)
            pid = page.evaluate("import('/static/js/store.js').then((m) => m.S.tab.id)")
            win = b.new_page(viewport={'width': 1300, 'height': 850})   # 슬라이드 창 — 그 창의 기본 스타일로
            win.goto(f"{url}?solo={quote(pid)}&w=abcdef0199&type=doc&path={quote(DECK)}&deck=1")
            win.wait_for_selector('#lec-view.lec-deck', timeout=20000)
            if not until(win, READY, 30000):
                print('발표를 다 그리지 못했습니다')
                return 1
            win.wait_for_timeout(800)
            issues = win.evaluate("[...document.querySelectorAll('#lec-view > .lec-slide-wrap')].flatMap((w, i) => JSON.parse(w.dataset.issues || '[]').map((x) => `${i + 1}장 ${x.text}`))")
            if issues:
                print('점검에 나온 것이 있습니다 — 발표를 먼저 고칩니다:', *issues, sep='\n  ')
                return 1
            win.click('#lec-st-html')
            win.wait_for_selector('#lec-html:not([hidden])', timeout=8000)
            win.keyboard.press('Enter')
            until(win, "!document.querySelector('#lec-html-done').hidden || document.querySelector('#lec-html-msg').classList.contains('bad')", 60000)
            if not made.is_file():
                print('html 을 만들지 못했습니다:', win.text_content('#lec-html-msg'))
                return 1
            ctx = b.new_context(viewport={'width': 1600, 'height': 900})
            outside = []
            ctx.route('**/*', lambda route: (outside.append(route.request.url), route.abort()) if not route.request.url.startswith('file:') else route.continue_())
            show = ctx.new_page()
            errors = []
            show.on('pageerror', lambda e: errors.append(str(e)[:200]))
            show.goto(made.as_uri())
            on = until(show, "document.body.classList.contains('impress-enabled')", 10000)
            steps = show.evaluate("document.querySelectorAll('#impress .step').length")
            ctx.close()
            b.close()
        if not on or outside or errors:
            print('만든 html 이 발표로 켜지지 않았습니다:', json.dumps({'켜짐': bool(on), '바깥 요청': outside[:3], '오류': errors[:3]}, ensure_ascii=False))
            return 1
        shutil.copyfile(made, OUT)
        print(f'{OUT.relative_to(ROOT)} — 장 {steps}개(전체 보기 포함), {OUT.stat().st_size // 1024}KB')
        return 0
    finally:
        stop(server, base)


if __name__ == '__main__':
    sys.exit(main())
