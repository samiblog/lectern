"""화면 회귀 점검: 브라우저 모드 서버를 띄우고 headless Chromium으로 주요 동작을 확인한다.

UI(web/)를 고친 뒤 실행해서 깨진 곳이 없는지 본다. 화면 캡처는 ui-shots/ 에 저장된다.

준비 (한 번만, 인터넷 필요):
    pip install playwright
    python -m playwright install chromium

사용:
    python tools/ui_smoke.py             # 점검 + 캡처
    python tools/ui_smoke.py --headed    # 브라우저 창을 띄워서 보기

samples/ 를 임시 폴더에 복사해서 쓰므로 원본은 바뀌지 않는다. 실패하면 종료 코드 1.
"""
from __future__ import annotations

import argparse
import functools
import http.server
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / 'ui-shots'

failures: list[str] = []


def check(cond: bool, message: str) -> None:
    print(('  ok   ' if cond else '  FAIL ') + message)
    if not cond:
        failures.append(message)


def wait_until(page, js: str, timeout: int = 5000) -> bool:
    """페이지 안의 조건(js)이 참이 될 때까지 기다린다. 시간 안에 안 되면 False.
    고정 시간 대기 대신 써서, 느린 PC나 부하가 있을 때도 점검이 흔들리지 않게 한다."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    try:
        page.wait_for_function(js, timeout=timeout)
        return True
    except PlaywrightTimeout:
        return False


def free_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def wait_http(url: str, timeout: float = 15) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError(f'서버가 응답하지 않습니다: {url}')


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass


def start_image_server(folder: Path) -> tuple[http.server.ThreadingHTTPServer, int]:
    """'외부' 이미지 역할을 하는 두 번째 로컬 서버 (인터넷 없이 외부 이미지 동작을 확인하려고)."""
    (folder / 'dot.svg').write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="40"><rect width="120" height="40" fill="#2b5c8a"/></svg>',
        encoding='utf-8')
    handler = functools.partial(_QuietHandler, directory=str(folder))
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


# <img> 가 아닌 길로 그림을 부르는 HTML. 정화 훅(doc.js)과 CSP(server.py)가 막아야 한다
LEAKS = (
    '<table background="{r}leak-table.svg"><tr><td background="{r}leak-td.svg">표 배경</td></tr></table>',
    '<svg width="40" height="40"><image href="{r}leak-image.svg" width="40" height="40"/>'
    '<rect width="40" height="40" fill="url({r}leak-fill.svg#g)"/></svg>',
    '<div style="background-image:image-set(\'{r}leak-imageset.svg\' 1x)">image-set</div>',
)

# 앱 화면을 망가뜨리던 원시 HTML: SVG 링크(target 읽기 전용, xlink:href), 이미지 맵, document 를 가리는 img name
RAW_HTML = (
    '# 원시 HTML 확인\n\n'
    '<svg width="200" height="30"><a href="{r}page.html"><text x="4" y="20">SVG 외부 링크</text></a></svg>\n\n'
    '<svg width="200" height="30"><a xlink:href="02-수식과-달러.md"><text x="4" y="20">SVG 문서 링크</text></a></svg>\n\n'
    '<img src="../research/images/price-band.svg" usemap="#m" width="320" height="120" alt="이미지 맵">'
    '<map name="m"><area shape="rect" coords="0,0,320,120" href="02-수식과-달러.md" alt="수식 문서"></map>\n\n'
    '<img name="querySelector" src="../research/images/price-band.svg" width="160" height="60" alt="name 속성">\n'
)


def run(headed: bool) -> None:
    from playwright.sync_api import sync_playwright

    tmp = Path(tempfile.mkdtemp(prefix='lectern-smoke-'))
    work = tmp / 'samples'
    shutil.copytree(ROOT / 'samples', work)
    img_dir = tmp / 'remote'
    img_dir.mkdir()
    img_server, img_port = start_image_server(img_dir)
    remote = f'http://127.0.0.1:{img_port}/'
    (work / 'docs' / '99-외부-이미지.md').write_text(
        f'# 외부 이미지 확인\n\n![있는 그림]({remote}dot.svg)\n\n![없는 그림]({remote}missing.png)\n\n'
        + '\n\n'.join(x.format(r=remote) for x in LEAKS) + '\n', encoding='utf-8')
    (work / 'docs' / '98-원시-HTML.md').write_text(RAW_HTML.format(r=remote), encoding='utf-8')
    port = free_port()
    env = os.environ | {'LECTERN_CONFIG_DIR': str(tmp / 'config')}
    server = subprocess.Popen([sys.executable, str(ROOT / 'app.py'), '--browser', '--port', str(port), str(work)],
                              cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f'http://127.0.0.1:{port}/'
    SHOTS.mkdir(exist_ok=True)
    errors: list[str] = []
    try:
        wait_http(url + 'api/state')
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not headed)
            page = browser.new_page(viewport={'width': 1440, 'height': 900}, locale='ko-KR')
            page.on('pageerror', lambda e: errors.append(str(e)))
            # 앱 서버 밖으로 나가는 요청 기록. 허용되는 것은 문서 속 외부 이미지뿐이다 (설정 external_images)
            outside: list[tuple[str, str]] = []
            page.on('request', lambda r: outside.append((r.url, r.resource_type))
                    if not r.url.startswith((url, 'data:', 'blob:')) else None)
            shot = lambda name: page.screenshot(path=str(SHOTS / f'{name}.png'))

            print('[트리와 개요]')
            page.goto(url)
            page.wait_for_selector('.overview .ov-head h1')
            labels = page.locator('#lec-tree .row .label').all_inner_texts()
            check('렌더링 기능 점검' in labels, '트리에 문서 제목 표시')
            check(not any('숨김' in t or 'some-lib' in t for t in labels), '숨김·제외 문서는 트리에 없음')
            check('empty-folder' not in labels, 'md 없는 폴더는 트리에 없음')
            check(labels.index('우선순위') < labels.index('후속 과제'), '자연 정렬 (2 → 10)')
            shot('01-overview')

            print('[문서 렌더링]')
            page.locator('#lec-tree .row.file', has_text='렌더링 기능 점검').click()
            page.wait_for_selector('#lec-view.md-body h1')
            check(page.locator('td.num').count() >= 15, '숫자 열 오른쪽 정렬')
            check(page.locator('blockquote.alert').count() == 4, '콜아웃 4개')
            check(page.locator('.code-block .code-copy').count() == 3, '코드 블록 복사 버튼')
            check(page.locator('#lec-toc a').count() == 7, '목차 7개')
            check(page.locator('.footnotes li').count() == 2, '각주 2개')
            shot('02-doc')

            print('[수식과 달러]')
            page.locator('#lec-view a', has_text='수식과 달러 표기').click()
            page.wait_for_selector('#lec-view h1:has-text("수식과 달러 표기")')
            check(page.locator('#lec-view .katex').count() >= 5, 'KaTeX 수식 렌더링')
            dollars = ' '.join(page.locator('#lec-view h2:has-text("달러 표기") + ul li').all_inner_texts())
            check('$105에서 $110' in dollars and 'US$1.2bn' in dollars, '달러 표기는 수식으로 바뀌지 않음')
            page.keyboard.press('Alt+ArrowLeft')
            page.wait_for_selector('#lec-view h1:has-text("렌더링 기능 점검")')
            check(True, '뒤로 가기')

            print('[다이어그램]')
            page.locator('#lec-tree .row.file', has_text='다이어그램').click()
            page.wait_for_selector('pre.mermaid svg', timeout=20000)
            widths = page.evaluate("[...document.querySelectorAll('pre.mermaid svg')].map(s => s.getBoundingClientRect().width)")
            check(len(widths) == 2 and min(widths) > 200, 'Mermaid 그림 2개가 제 크기로 보임')
            check(page.locator('#lec-view h2#mermaid').count() == 1, "'## Mermaid' 제목(id=mermaid)이 있는 문서도 처음 열 때 그림을 그림")
            check(page.locator('.mermaid-error').count() == 1, '문법 오류 블록은 원문 표시')
            shot('03-mermaid')

            print('[테마]')
            for theme in ('report', 'dark', 'default'):
                page.select_option('#lec-theme', theme)
                check(wait_until(page, f"document.documentElement.dataset.theme === '{theme}'"), f'테마 전환: {theme}')
                page.wait_for_timeout(500)   # 캡처용: 다시 그린 다이어그램이 자리 잡을 시간
                shot(f'04-theme-{theme}')

            print('[빠른 열기와 찾기]')
            page.keyboard.press('Control+p')
            page.fill('#lec-palette-input', '우선')
            page.keyboard.press('Enter')
            page.wait_for_selector('#lec-view h1:has-text("우선순위")')
            check(True, 'Ctrl+P 로 문서 열기')
            page.locator('#lec-tree .row.file', has_text='렌더링 기능 점검').click()
            page.wait_for_selector('#lec-view h1:has-text("렌더링 기능 점검")')
            page.keyboard.press('Control+f')
            page.fill('#lec-find-input', '예시')   # 한 번에 넣어 검색이 한 번만 돌게 (글자마다 치면 '예'로 먼저 찾을 수 있음)
            wait_until(page, "document.querySelector('#lec-find-count').textContent !== ''")
            found = page.locator('#lec-find-count').inner_text()
            check(found.endswith('/6'), '문서 안 찾기 (6건)' + ('' if found.endswith('/6') else f': {found!r}'))
            page.keyboard.press('Escape')

            print('[자동 새로고침]')
            page.locator('#lec-content').evaluate('el => el.scrollTop = 600')
            doc = work / 'docs' / '01-기능-점검.md'
            doc.write_text(doc.read_text(encoding='utf-8').replace('# 렌더링 기능 점검', '# 렌더링 기능 점검 (수정됨)'), encoding='utf-8')
            (work / 'research' / '새-메모.md').write_text('# 새 메모\n\n방금 만든 문서\n', encoding='utf-8')
            page.wait_for_selector('#lec-view h1:has-text("(수정됨)")', timeout=8000)
            page.wait_for_selector('#lec-tree .row.file:has-text("새 메모")', timeout=8000)
            check(page.locator('#lec-content').evaluate('el => el.scrollTop') == 600, '보던 문서는 스크롤 위치를 유지하며 다시 그림')
            check(page.locator('#lec-tree .row.file:has-text("새 메모") .dot').count() == 1, '새 문서에 변경 표시')
            shot('05-live-reload')

            print('[문서 속 원시 HTML]')
            page.locator('#lec-tree .row.file', has_text='원시 HTML 확인').click()
            page.wait_for_selector('#lec-view h1:has-text("원시 HTML 확인")')
            check(page.locator('#lec-view svg a[target="_blank"]').count() == 1, 'SVG 속 외부 링크가 있어도 문서를 그리고, 링크는 새 창으로')
            check(page.evaluate('typeof document.querySelector') == 'function', '<img name="querySelector"> 가 document 를 가리지 않음')
            page.locator('#lec-view img[usemap]').click()
            page.wait_for_selector('#lec-view h1:has-text("수식과 달러 표기")')
            check(page.url == url, '이미지 맵 링크는 앱 안에서 문서를 엶 (앱 창이 떠나지 않음)')
            page.keyboard.press('Alt+ArrowLeft')
            page.wait_for_selector('#lec-view h1:has-text("원시 HTML 확인")')
            page.locator('#lec-view svg a[href$=".md"]').click()
            page.wait_for_selector('#lec-view h1:has-text("수식과 달러 표기")')
            check(page.url == url, 'SVG xlink:href 링크도 앱 안에서 문서를 엶')

            print('[외부 이미지]')
            page.locator('#lec-tree .row.file', has_text='외부 이미지 확인').click()
            page.wait_for_selector('#lec-view h1:has-text("외부 이미지 확인")')
            page.wait_for_selector('#lec-view .image-off', timeout=8000)
            # 없는 그림의 대체 표시가 먼저 나타날 수 있으므로, 있는 그림을 다 받을 때까지 기다린 뒤 크기를 읽는다
            wait_until(page, "[...document.querySelectorAll('#lec-view img.external')].every(i => i.complete)")
            loaded = page.evaluate("[...document.querySelectorAll('#lec-view img.external')].map(i => i.naturalWidth)")
            check(loaded == [120], '외부 이미지 표시' + ('' if loaded == [120] else f': naturalWidth={loaded}'))
            check(page.locator('#lec-view .image-off').inner_text().startswith('외부 이미지를 불러오지 못했습니다'),
                  '불러오지 못한 외부 이미지는 링크로 대체')
            leaked = [u for u, _ in outside if 'leak-' in u]
            check(not leaked, '표 배경·SVG·image-set 으로는 외부 요청이 나가지 않음' + (f': {leaked}' if leaked else ''))
            shot('06-external-images')
            page.evaluate("fetch('/api/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({external_images:false})})")
            page.reload()
            page.wait_for_selector('.overview .ov-head h1')
            before = len(outside)
            page.locator('#lec-tree .row.file', has_text='외부 이미지 확인').click()
            page.wait_for_selector('#lec-view h1:has-text("외부 이미지 확인")')
            page.wait_for_timeout(500)
            check(page.locator('#lec-view .image-off').count() == 2 and len(outside) == before,
                  '설정을 끄면 외부 이미지를 불러오지 않음')

            print('[보안]')
            check(page.evaluate("fetch('/doc/.hidden-note.md').then(r => r.status)") == 404, '숨김 문서 직접 요청 차단')
            check(page.evaluate("fetch('/doc/..%2F..%2Fetc%2Fpasswd').then(r => r.status)") == 404, '프로젝트 밖 경로 차단')
            not_images = [u for u, kind in outside if kind != 'image']
            check(not not_images, '외부 요청은 문서 속 이미지뿐 (스크립트·글꼴·CDN 없음)' + (f': {not_images[:3]}' if not_images else ''))

            browser.close()
    finally:
        img_server.shutdown()
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
        shutil.rmtree(tmp, ignore_errors=True)

    check(not errors, '페이지 스크립트 오류 없음' + (f': {errors}' if errors else ''))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--headed', action='store_true', help='브라우저 창을 띄워서 실행')
    args = parser.parse_args()
    run(args.headed)
    print()
    if failures:
        print(f'실패 {len(failures)}건. 캡처: {SHOTS}')
        sys.exit(1)
    print(f'모두 통과. 캡처: {SHOTS}')


if __name__ == '__main__':
    main()
