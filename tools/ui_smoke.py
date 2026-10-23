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
import urllib.parse
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
    received: list[str] = []   # '외부' 서버가 실제로 받은 경로 — 새는 요청을 가리는 최종 근거

    def log_message(self, *args) -> None:
        pass

    def do_GET(self) -> None:
        self.received.append(self.path)
        super().do_GET()


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
    '<img name="querySelector" src="../research/images/price-band.svg" width="160" height="60" alt="name 속성">\n\n'
    # 문서가 앱이 쓰는 data-lec-* 값을 적어 두거나 깨진 값을 적어도 우클릭 메뉴가 떠야 한다
    '<p><a href="https://example.com/" data-lec-open=\'{{"type":"doc","path":"README.md"}}\'>심은 값 링크</a> '
    '<a data-lec-href="x" data-lec-open="{{">깨진 값</a></p>\n'
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
    # html 문서의 인터넷 CSS 는 막혀야 한다 (그림만 허용). 요청이 나가면 아래 '새지 않음' 점검이 잡는다
    # 바탕을 칠하지 않고 밝은 글자만 정한 html (어두운 바탕을 가정하고 만든 보고서) — 흰 바탕에 묻히면 안 된다
    (work / 'docs' / '94-밝은-글자.html').write_text(
        '<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>밝은 글자 문서</title>'
        '<style>body{color:#f1f5f9;font-family:sans-serif} .card{background:#1e293b;padding:12px}</style></head>'
        '<body><h1>밝은 글자 문서</h1><p>바탕을 칠하지 않은 밝은 글자</p><div class="card"><p>카드 안 글자</p></div></body></html>',
        encoding='utf-8')
    # 접었다 펴는 내용(틀 높이가 줄어드는지)과 SVG 의 옛 링크(xlink:href — 누르면 iframe 이 떠나면 안 됨)
    (work / 'docs' / '93-접는-html.html').write_text(
        '<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>접는 html</title>'
        '<style>body{font-family:sans-serif}</style></head><body><h1>접는 html</h1>'
        '<details><summary>자세히</summary><div style="height:2000px">긴 내용</div></details>'
        '<svg width="240" height="40"><a xlink:href="01-기능-점검.md"><text x="5" y="25">SVG 링크</text></a></svg>'
        '</body></html>', encoding='utf-8')
    report = work / 'docs' / '04-HTML-보고서.html'
    report.write_text(report.read_text(encoding='utf-8').replace(
        '</head>', f'<link rel="stylesheet" href="{remote}leak-html.css"></head>'), encoding='utf-8')
    # 문서 외 파일: 목록에 나올 것(csv·실행 파일·루트의 pdf)과 나오지 않을 것(숨김·제외 폴더)
    (work / 'data').mkdir()
    (work / 'data' / '표.csv').write_text('품목,값\n구리,1\n', encoding='utf-8')
    (work / 'data' / 'setup.exe').write_bytes(b'MZ')
    (work / 'data' / '.secret.txt').write_text('숨김', encoding='utf-8')
    (work / 'node_modules' / 'some-lib' / 'index.js').write_text('x', encoding='utf-8')
    (work / '첨부.pdf').write_bytes(b'%PDF-1.4')
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
            # 클립보드 권한: 본문 우클릭 메뉴의 복사 결과를 읽어 본다 (headless 클립보드는 Windows 클립보드와 따로다)
            context = browser.new_context(viewport={'width': 1440, 'height': 900}, locale='ko-KR',
                                          permissions=['clipboard-read', 'clipboard-write'])
            page = context.new_page()
            page.on('pageerror', lambda e: errors.append(str(e)))
            # 앱 서버 밖으로 나가는 요청 기록. 허용되는 것은 문서 속 외부 이미지뿐이다 (설정 external_images)
            outside: list[tuple[str, str]] = []
            page.on('request', lambda r: outside.append((r.url, r.resource_type))
                    if not r.url.startswith((url, 'data:', 'blob:')) else None)
            # CSP 가 막은 요청은 브라우저가 '요청 → 실패(csp)'로 알리지만 밖으로 나가지 않는다 ('외부' 서버의 received 로도 확인)
            blocked: set[str] = set()
            page.on('requestfailed', lambda r: blocked.add(r.url) if 'csp' in (r.failure or '').lower() else None)
            shot = lambda name: page.screenshot(path=str(SHOTS / f'{name}.png'))

            print('[트리와 개요]')
            held = []   # 문서가 수천 개면 트리를 처음 훑는 데 몇 초 걸린다 — 응답을 붙잡아 그동안의 화면을 본다
            is_tree = lambda u: '/api/tree' in u
            page.route(is_tree, lambda route: held.append(route))
            page.goto(url)
            loading = wait_until(page, "document.querySelector('#lec-view').textContent.includes('폴더를 읽고 있습니다')")
            for r in held:
                r.continue_()
            page.unroute(is_tree)
            page.wait_for_selector('.overview .ov-head h1')
            check(loading, '폴더를 훑는 동안 빈 화면 대신 읽는 중이라고 알림')
            row_tip = lambda box: page.locator(f'#lec-{box} .row[data-doc="docs/01-기능-점검.md"]').get_attribute('title')
            names = page.locator('#lec-tree .row.file .label').all_inner_texts()
            tip = row_tip('tree')
            check('01-기능-점검.md' in names and '렌더링 기능 점검' not in names
                  and tip == '렌더링 기능 점검\ndocs/01-기능-점검.md' and row_tip('recent') == tip,
                  f'트리·최근 변경은 파일 이름, 마우스를 올리면 문서 제목과 경로 ({tip!r})')
            page.click('#lec-btn-titles')   # 아래 점검은 문서 제목으로 행을 찾는다
            wait_until(page, "document.querySelector('#lec-btn-titles').classList.contains('on')")   # 설정을 저장한 뒤에 켜진다
            titles_on = page.evaluate("fetch('/api/config').then(r => r.json()).then(c => c.show_titles)")
            labels = page.locator('#lec-tree .row .label').all_inner_texts()
            check('렌더링 기능 점검' in labels and titles_on is True and row_tip('tree') == 'docs/01-기능-점검.md\n렌더링 기능 점검',
                  "'제목' 버튼을 켜면 문서 제목 (마우스를 올리면 경로와 제목, 설정에 저장)")
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

            print('[제목 색·표 머리행·제목 접기]')
            colors = page.evaluate('''() => {
              const css = (sel, prop) => getComputedStyle(document.querySelector('#lec-view ' + sel))[prop];
              return [css('h2', 'color'), css('p', 'color'), css('thead th', 'backgroundColor'), css('tbody td', 'backgroundColor'),
                      css('thead th', 'color'), css('tbody td', 'color')];
            }''')
            check(colors[0] != colors[1], f'제목 색은 본문 색과 다름: {colors[:2]}')
            check(colors[2] != colors[3] and colors[4] != colors[5], f'표 머리행은 본문 행과 배경·글자색이 다름: {colors[2:]}')
            sec = lambda name: page.locator(f'#lec-view [id="{name}"]')
            text = lambda t: page.locator('#lec-view li, #lec-view p', has_text=t).first
            folded = lambda name: 'lec-folded' in (sec(name).get_attribute('class') or '')
            check(page.locator('#lec-view h1.lec-fold').count() == 0 and page.locator('#lec-view .lec-fold').count() == 7,
                  '절 제목 7개는 접을 수 있고, 문서 제목(H1 하나)은 접지 않음')
            sec('표').click()
            check(not page.locator('#lec-view .table-wrap').is_visible() and sec('체크리스트와-각주').is_visible(),
                  '제목을 누르면 다음 같은 수준 제목 전까지 접힘')
            sec('표').click()
            check(page.locator('#lec-view .table-wrap').is_visible(), '다시 누르면 펼쳐짐')
            sec('파일과-바깥-주소').click()
            sec('링크').click()
            hidden = [not sec('파일과-바깥-주소').is_visible(), not text('구현 계획').is_visible(), page.locator('#lec-view .footnotes').is_visible()]
            sec('링크').click()
            hidden += [sec('파일과-바깥-주소').is_visible(), not text('CommonMark 명세').is_visible()]
            check(all(hidden), f'하위 절도 함께 접히고, 펴면 따로 접어 둔 하위 절은 접힌 채 (각주는 접히지 않음): {hidden}')
            sec('링크').click()
            page.locator('#lec-toc a', has_text='파일과 바깥 주소').click()
            check(sec('파일과-바깥-주소').is_visible() and not folded('링크'), '목차로 접힌 절 안의 제목에 가면 펴짐')
            sec('파일과-바깥-주소').click()
            sec('코드').dblclick(position={'x': 12, 'y': 16})   # 제목 글자 위
            selected = page.evaluate('getSelection().toString().trim()')
            check(not folded('코드') and selected == '코드', f'두 번 눌러 낱말을 고를 때는 접지 않음: {selected!r}')
            page.locator('#lec-view p', has_text='상대경로 그림은').click(position={'x': 5, 'y': 10})
            sec('그림').click(position={'x': 30, 'y': 16}, modifiers=['Shift'])   # 끌어서 고르면 click 이 오지 않는다 (Chromium)
            check(not folded('그림'), 'Shift+클릭으로 글자를 고를 때는 접지 않음')

            print('[글자 크기와 장 하이라이트]')
            size = lambda: page.evaluate("parseFloat(getComputedStyle(document.querySelector('#lec-view p')).fontSize)")
            base_size = size()
            page.click('#lec-text-bigger')
            page.click('#lec-text-bigger')
            bigger, size_label = size(), page.inner_text('#lec-text-reset')
            saved_scale = wait_until(page, "fetch('/api/config').then(r => r.json()).then(c => c.font_scale === 1.2)")
            page.click('#lec-text-reset')
            page.click('#lec-text-smaller')
            smaller = size()
            page.click('#lec-text-reset')
            check(abs(bigger - base_size * 1.2) < 0.2 and size_label == '120%' and saved_scale and smaller < base_size and size() == base_size,
                  f'글자 크기 +·− (본문 {base_size}px → 두 번 + {bigger}px {size_label}, − {smaller}px), 가운데를 누르면 100%, 설정에 저장')
            lit = lambda: page.evaluate("[...document.querySelectorAll('#lec-view > .lec-lit')].filter(e => /^H[1-6]$/.test(e.tagName)).map(e => e.id)")
            # 접어 둔 절을 모두 편다 (앞 점검이 고른 글자가 남아 있으면 제목을 눌러도 접기·펴기를 하지 않으므로 선택부터 푼다)
            page.evaluate("getSelection().removeAllRanges(); document.querySelectorAll('#lec-view > .lec-folded').forEach(h => h.click())")
            page.locator('#lec-content').evaluate('el => el.scrollTop = 0')
            arrows_off = page.is_disabled('#lec-spot-prev') and page.is_disabled('#lec-spot-next')   # 하이라이트 전에는 꺼져 있다
            page.click('#lec-btn-spot')
            first = lit()
            faded_js = """(() => { const b = [...document.querySelectorAll('#lec-view > :not(.lec-lit)')].find(e => e.querySelector('img'));
              return b ? getComputedStyle(b).opacity : null; })()"""
            wait_until(page, f"{faded_js} === '0.16'")   # 흐려지는 데 0.2초 (transition)
            faded_img = page.evaluate(faded_js)
            page.keyboard.press('ArrowDown')
            down1 = lit()
            page.keyboard.press('PageDown')
            down2 = lit()
            page.keyboard.press('PageUp')
            up1 = lit()
            page.wait_for_timeout(300)   # 흐려지고 밝아지는 데 0.2초 — 캡처용
            shot('03-spotlight')
            check(first == ['렌더링-기능-점검'] and down1 == ['표'] and down2 == ['체크리스트와-각주'] and up1 == ['표'] and faded_img == '0.16',
                  f'장 하이라이트: 첫 장(제목·머리말)부터, ↓·PageDown·PageUp 으로 앞뒤 장, 다른 장의 그림도 흐림 ({first} → {down1} → {down2} → {up1}, 흐린 그림 {faded_img})')
            page.click('#lec-spot-next')
            btn_next = lit()
            page.click('#lec-spot-prev')
            btn_prev = lit()
            page.keyboard.press('PageUp')
            at_first = page.is_disabled('#lec-spot-prev') and not page.is_disabled('#lec-spot-next')
            # 장마다: 하이라이트 범위 = 그 장 제목을 눌러 접을 때 숨는 범위 + 제목 (첫 장의 문서 제목은 접지 않는다)
            spans = page.evaluate("""() => {
              const kids = [...document.querySelector('#lec-view').children];
              const idx = (pred) => kids.map((e, i) => (pred(e) ? i : -1)).filter((i) => i >= 0);
              const out = [];
              for (let n = 0; n < 40; n++) {
                const lit = idx((e) => e.classList.contains('lec-lit'));
                const head = kids[lit[0]];
                if (head.classList.contains('lec-fold')) {
                  const before = new Set(idx((e) => e.classList.contains('lec-fold-hidden')));
                  head.click();
                  const fold = [lit[0], ...idx((e) => e.classList.contains('lec-fold-hidden')).filter((i) => !before.has(i))];
                  head.click();
                  out.push(JSON.stringify(fold) === JSON.stringify(lit) ? 'same' : `${head.id}: ${lit} / ${fold}`);
                } else out.push('title');
                if (document.querySelector('#lec-spot-next').disabled) break;
                document.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
              }
              return out;
            }""")
            at_last = page.is_disabled('#lec-spot-next') and not page.is_disabled('#lec-spot-prev')
            check(arrows_off and btn_next == ['체크리스트와-각주'] and btn_prev == ['표'] and at_first and at_last,
                  f'하이라이트 버튼 옆 ∧·∨ 로 앞뒤 장, 하이라이트 전·첫 장·마지막 장에서는 그쪽 버튼이 꺼짐 ({btn_next} → {btn_prev})')
            check(spans == ['title'] + ['same'] * 6, f'하이라이트하는 장의 범위는 그 장 제목을 눌러 접히는 범위와 같음 ({spans})')
            page.locator('#lec-view p', has_text='표시가 없는 인용문').click()
            by_click = lit()
            page.locator('#lec-toc a', has_text='링크').first.click()
            by_toc = lit()
            page.keyboard.press('Escape')
            off = page.evaluate("!document.querySelector('#lec-view').classList.contains('lec-spotlight') && !document.querySelector('#lec-view .lec-lit')"
                                " && document.querySelector('#lec-spot-prev').disabled && document.querySelector('#lec-spot-next').disabled")
            check(by_click == ['콜아웃'] and by_toc[:1] == ['링크'] and off,
                  f'흐린 장을 누르거나 목차로 가면 그 장, Esc 로 끔 ({by_click}, {by_toc})')

            print('[본문 우클릭 메뉴]')
            src = (work / 'docs' / '01-기능-점검.md').read_text(encoding='utf-8').split('\n')
            first_line = lambda sel: int(page.locator(f'#lec-view {sel}').first.get_attribute('data-lines').split('-')[0])
            starts = [src[first_line(s) - 1][:9] for s in ('[id="코드"]', 'table', '.code-block code')]
            check(starts == ['## 코드', '| 품목 | 1분', '```python'], f'블록마다 원문 줄 범위를 앎: {starts}')

            def menu(target, **kw) -> str:
                target.click(button='right', **kw)
                page.wait_for_selector('#lec-menu:not([hidden])')
                return page.locator('#lec-menu').inner_text()

            def choose(label: str) -> str:
                """메뉴 항목을 누르고, 복사가 끝나면(알림이 뜨면) 클립보드 글을 돌려준다."""
                page.evaluate("document.querySelector('#lec-toast').textContent = ''")
                page.locator('#lec-menu button', has_text=label).first.click()
                wait_until(page, "document.querySelector('#lec-toast').textContent.startsWith('복사')")
                return page.evaluate('navigator.clipboard.readText()').replace('\r\n', '\n')

            clip_types = lambda: page.evaluate('navigator.clipboard.read().then(items => items.flatMap(i => i.types))')

            # 우클릭으로 장 하이라이트 / 하이라이트 해제
            quote = page.locator('#lec-view p', has_text='표시가 없는 인용문')
            items_off = menu(quote)
            page.locator('#lec-menu button', has_text='이 장 하이라이트').click()
            by_menu = lit()
            items_on = menu(quote)
            page.locator('#lec-menu button', has_text='하이라이트 해제').click()
            off_by_menu = page.evaluate("!document.querySelector('#lec-view').classList.contains('lec-spotlight')")
            check('이 장 하이라이트' in items_off and by_menu == ['콜아웃'] and '하이라이트 해제' in items_on
                  and '이 장 하이라이트' not in items_on and off_by_menu,
                  f'본문 우클릭 메뉴로 그 장 하이라이트 / 하이라이트 해제 ({by_menu})')
            para = page.locator('#lec-view p', has_text='숫자가 대부분인 열은')
            head = menu(para).split('\n')[0]
            picked = page.locator('#lec-view .lec-picked').count()
            copied = choose('원문 복사')
            check(head == '단락' and picked == 1 and copied == src[6] and page.locator('#lec-view .lec-picked').count() == 0,
                  f'단락 우클릭: 테두리 표시, 원문 복사 ({head!r}, 표시 {picked}개, {copied[:20]!r})')
            a, b = src.index('## 코드') + 1, src.index('## 콜아웃')
            while not src[b - 1].strip():
                b -= 1
            menu(sec('코드'))
            section = choose('이 절 원문 복사')
            menu(sec('코드'))
            ref = choose('Claude용 위치 복사')
            want = f"@docs/01-기능-점검.md {a}~{b}행 ('코드' 절)"
            check(section == '\n'.join(src[a - 1:b]) and ref == want, f'제목 우클릭: 절 원문 복사, Claude용 위치 복사 ({ref!r})')
            items = menu(sec('코드'))
            page.locator('#lec-menu button', has_text='같은 수준(H2) 모두 접기').click()
            h2_folded = page.evaluate("[...document.querySelectorAll('#lec-view > h2.lec-fold')].every(h => h.classList.contains('lec-folded'))")
            menu(sec('코드'))
            page.locator('#lec-menu button', has_text='같은 수준(H2) 모두 펴기').click()
            check(f'편집기에서 이 줄 열기\ndocs/01-기능-점검.md:{a}' in items and h2_folded and not folded('코드'),
                  '제목 우클릭: 편집기에서 이 줄 열기(줄 번호), 같은 수준 제목 모두 접기·펴기')
            menu(page.locator('#lec-view a', has_text='수식과 달러 표기'))
            link_addr = choose('링크 주소 복사')
            check(link_addr == 'docs/02-수식과-달러.md', f'링크 우클릭: 링크 주소 복사 ({link_addr!r})')
            menu(page.locator('#lec-view td').nth(3))
            shot('02-doc-menu')
            tsv = choose('표 복사')
            types = clip_types()
            check(tsv.startswith('품목\t1분기\t2분기') and 'text/html' in types, f'표 복사: 탭으로 나눈 글 + HTML 표 ({types})')
            menu(page.locator('#lec-view img').first)
            choose('그림 복사')
            check(clip_types() == ['image/png'], f'그림 복사: PNG ({clip_types()})')
            items = menu(page.locator('#lec-content'), position={'x': 30, 'y': 420})
            choose_fold = lambda label: page.locator('#lec-menu button', has_text=label).click()
            choose_fold('모두 접기')
            folded_all = page.locator('#lec-view .lec-folded').count() == page.locator('#lec-view .lec-fold').count()
            menu(page.locator('#lec-content'), position={'x': 30, 'y': 420})
            choose_fold('모두 펴기')
            check('@docs/01-기능-점검.md 복사' in items and folded_all and page.locator('#lec-view .lec-folded').count() == 0,
                  '빈 곳 우클릭: 문서 메뉴 (경로 복사, 모두 접기·펴기)')
            para.click(click_count=3)
            selected = page.evaluate('getSelection().toString().trim()')
            items = menu(para)   # 고른 곳 밖을 우클릭하면 브라우저가 선택을 푼다
            copied = choose('선택한 글 복사') if items.startswith('선택한 글 복사') else ''
            check(selected and copied == selected, f'글을 고른 채 우클릭하면 맨 위에 선택한 글 복사 ({items[:10]!r}, {copied[:20]!r})')
            page.evaluate('getSelection().removeAllRanges()')
            sec('표').click()   # 접은 채 다른 문서로 갔다가 돌아와도 유지되는지는 아래 찾기에서 본다
            shot('02-doc-folded')

            print('[수식과 달러]')
            page.locator('#lec-view a', has_text='수식과 달러 표기').click()
            page.wait_for_selector('#lec-view h1:has-text("수식과 달러 표기")')
            check(page.locator('#lec-view .katex').count() >= 5, 'KaTeX 수식 렌더링')
            dollars = ' '.join(page.locator('#lec-view h2:has-text("달러 표기") + ul li').all_inner_texts())
            check('$105에서 $110' in dollars and 'US$1.2bn' in dollars, '달러 표기는 수식으로 바뀌지 않음')
            bracket = page.locator('#lec-view p', has_text='[판독 불확실]')
            check(bracket.count() == 1 and bracket.locator('.katex').count() == 0, r'문장 속 \[판독 불확실\] 은 대괄호 글자 (수식 아님)')
            menu(page.locator('#lec-view .math-inline').first)
            tex = choose('LaTeX 복사')
            check(tex == r'x_t = \beta x_{t-1} + \varepsilon_t', f'문장 속 수식 우클릭: LaTeX 복사 ({tex!r})')
            fenced = page.locator(r'#lec-view .math-block[data-tex="\\ln Z_t = r_0 + r_1 \\ln X_t"] .katex-display')   # CSS 문자열은 \\ 가 \
            source = page.locator('#lec-view .code-block code', has_text=r'\documentclass')
            check(fenced.count() == 1 and source.count() == 1, '```latex 블록: 식은 수식, LaTeX 문서 원문은 코드 그대로')
            items = menu(fenced)
            tex = choose('LaTeX 복사')
            check(items.startswith('수식') and tex == r'\ln Z_t = r_0 + r_1 \ln X_t', f'```latex 수식 우클릭: LaTeX 복사 ({tex!r})')
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
            head = menu(page.locator('pre.mermaid svg p').first).split('\n')[0]   # 그림 속 글자(<p>)를 눌러도 다이어그램
            fence = choose('원문 복사')
            check(head == '다이어그램' and fence.startswith('```mermaid') and fence.endswith('```'),
                  f'다이어그램 우클릭: 원문 복사 ({head!r}, {fence[:12]!r})')
            menu(page.locator('pre.mermaid svg').first)
            choose('그림 복사')
            check(clip_types() == ['image/png'], f'다이어그램 우클릭: 그림 복사(PNG) ({clip_types()})')
            shot('03-mermaid')

            print('[스타일]')

            def use_theme(theme: str) -> bool:
                """스타일을 고르고, 그 스타일 파일이 실제로 적용될 때까지 기다린다."""
                page.select_option('#lec-theme', theme)
                return wait_until(page, f"""(() => {{ const s = document.querySelector('#lec-theme-css').sheet;
                    return document.documentElement.dataset.theme === '{theme}' && s && s.href.endsWith('/{theme}.css') && s.cssRules.length > 0; }})()""")

            themes = [t for t in page.eval_on_selector_all('#lec-theme option', 'os => os.map(o => o.value)') if t != 'auto']
            groups = page.eval_on_selector_all('#lec-theme optgroup', 'gs => gs.map(g => g.label)')
            check(len(themes) == 24 and len(set(themes)) == 24 and groups == ['업무·보고', '읽기·출판', '개발·기술', '어두운'],
                  f'스타일 {len(themes)}종, 처음에는 용도별 묶음 ({groups})')
            names = (page.inner_text('.theme-pick .pick-label'), page.inner_text('#lec-btn-spot'))
            check(names == ('스타일', '하이라이트'), f'툴바에 무엇을 고르는지 이름이 보임 ({names})')
            # 설정 창에서 묶는 방식을 바꾸면 목록이 다시 묶인다 (같은 24종, 고른 스타일은 그대로)
            picked = page.input_value('#lec-theme')
            grouped = {}
            for kind in ('mood', 'tone', 'use'):
                page.keyboard.press('Control+Comma')
                page.locator(f'#lec-settings input[name="theme_groups"][value="{kind}"]').check()
                page.keyboard.press('Escape')
                wait_until(page, f"fetch('/api/config').then(r => r.json()).then(c => c.theme_groups === '{kind}')")
                grouped[kind] = page.evaluate("""[...document.querySelectorAll('#lec-theme optgroup')]
                    .map(g => [g.label, [...g.querySelectorAll('option')].map(o => o.value)])""")
            ok_sets = all(sorted(v for _, opts in g for v in opts) == sorted(themes) for g in grouped.values())
            labels = {k: [label for label, _ in g] for k, g in grouped.items()}
            check(ok_sets and labels['mood'] == ['깔끔한', '따뜻한·종이', '색이 있는', '어두운'] and labels['tone'] == ['밝은', '종이·책', '어두운']
                  and page.input_value('#lec-theme') == picked,
                  f'설정 창에서 스타일 목록 묶는 방식(용도별·분위기별·밝기별)을 바꾸면 같은 스타일이 다시 묶임 ({labels})')
            # 목록 옆 위·아래 버튼: 목록에서 바로 위·아래 스타일로, 맨 처음·맨 끝이면 누를 수 없음
            order = page.eval_on_selector_all('#lec-theme option', 'os => os.map(o => o.value)')
            use_theme('default')
            below = order[order.index('default') + 1]
            page.click('#lec-theme-next')
            down = wait_until(page, f"document.documentElement.dataset.theme === '{below}'")
            saved_below = wait_until(page, f"fetch('/api/config').then(r => r.json()).then(c => c.theme === '{below}')")
            page.click('#lec-theme-prev')
            up = wait_until(page, "document.documentElement.dataset.theme === 'default'")
            page.select_option('#lec-theme', order[-1])
            last_off = page.is_disabled('#lec-theme-next') and not page.is_disabled('#lec-theme-prev')
            page.select_option('#lec-theme', 'auto')
            first_off = page.is_disabled('#lec-theme-prev')
            check(down and saved_below and up and last_off and first_off,
                  f'스타일 목록 옆 위·아래 버튼으로 바로 위·아래 스타일 (default → {below} → default), 처음·끝에서는 꺼짐')
            unstyled = []
            # 스타일마다 다이어그램 상자 색(theme.js 의 mermaid primaryColor)이 그 스타일 것이어야 한다
            for theme, fill in (('default', '#e8eff7'), ('dark', '#2a313a'), ('academic', '#fffff8'), ('nord', '#3b4252')):
                ok = use_theme(theme) and wait_until(page, f"""[...document.querySelectorAll('pre.mermaid.mermaid-ok svg style')]
                    .filter(s => s.textContent.includes('{fill}')).length === 2""", 20000)
                if not ok:
                    unstyled.append(theme)
                shot(f'04-theme-{theme}-mermaid')
            check(not unstyled, 'Mermaid 다이어그램을 스타일 색으로 다시 그림 (기본·다크·논문·Nord)' + (f': {unstyled}' if unstyled else ''))
            page.locator('#lec-tree .row.file', has_text='렌더링 기능 점검').click()
            page.wait_for_selector('#lec-view h1:has-text("렌더링 기능 점검")')
            measure = '''() => {
              const v = document.querySelector('#lec-view');
              const css = (sel) => getComputedStyle(v.querySelector(sel));
              // color-mix() 로 만든 색은 'color(srgb 0.9 0.9 0.9)' 처럼 0~1 로 나온다
              const rgb = (s) => s.match(/[\\d.]+/g).slice(0, 3).map(Number).map((x) => (s.startsWith('color(') ? x * 255 : x));
              const lum = (c) => c.map((x) => { x /= 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; })
                .reduce((a, x, i) => a + x * [0.2126, 0.7152, 0.0722][i], 0);
              const ratio = (a, b) => { const [x, y] = [lum(rgb(a)), lum(rgb(b))].sort((m, n) => n - m); return (x + 0.05) / (y + 0.05); };
              const bg = getComputedStyle(document.querySelector('#lec-content')).backgroundColor;
              const p = css('p').color, h = css('h2').color, th = css('thead th'), td = css('tbody td');
              const ui = (sel) => getComputedStyle(document.querySelector(sel));
              const side = ui('#lec-sidebar').backgroundColor, active = ui('#lec-tree .row.active');
              return { text: ratio(p, bg), heading: ratio(h, bg), muted: ratio(css('.footnotes').color, bg), link: ratio(css('p a').color, bg),
                       headingDiffers: h !== p, headerDiffers: th.backgroundColor !== td.backgroundColor || th.color !== td.color,
                       // 앱 UI 도 스타일 색을 따른다 (D28): 사이드바 글자, 상태줄의 흐린 글자, 고른 행
                       uiText: ratio(ui('#lec-tree .row .label').color, side), uiMuted: ratio(ui('#lec-status').color, ui('body').backgroundColor),
                       uiActive: ratio(active.color, active.backgroundColor), side };
            }'''
            if folded('표'):
                sec('표').click()   # 캡처에 표가 보이도록
            problems = []
            sides: set[str] = set()
            for theme in themes:
                if not use_theme(theme):
                    problems.append(f'{theme}: 스타일 파일이 적용되지 않음')
                    continue
                m = page.evaluate(measure)
                low = [k for k, need in (('text', 4.5), ('muted', 4.5), ('link', 4.5), ('heading', 3),
                                         ('uiText', 4.5), ('uiMuted', 4.5), ('uiActive', 4.5)) if m[k] < need]
                sides.add(m['side'])
                if low or not m['headingDiffers'] or not m['headerDiffers']:
                    problems.append(f"{theme}: 대비 부족 {low}, 제목 색 구분 {m['headingDiffers']}, 표 머리행 구분 {m['headerDiffers']}")
                shot(f'04-theme-{theme}')
            check(not problems and len(sides) == len(themes),
                  '모든 스타일: 글자 대비(WCAG 4.5:1), 제목 색·표 머리행 구분, 앱 UI(사이드바·상태줄)도 스타일 색으로'
                  + (f': {problems}' if problems else '') + ('' if len(sides) == len(themes) else f' (사이드바 색 {len(sides)}가지)'))
            use_theme('paper')
            saved = page.evaluate("fetch('/api/config').then(r => r.json()).then(c => c.theme)")
            page.reload()
            page.wait_for_selector('#lec-view h1')   # 마지막에 보던 문서나 폴더 개요 (마지막 위치 복원)
            check(saved == 'paper' and page.evaluate("document.documentElement.dataset.theme") == 'paper'
                  and page.input_value('#lec-theme') == 'paper', f'고른 스타일은 다음 실행에도 그대로 ({saved})')
            use_theme('default')
            page.locator('#lec-tree .row.file', has_text='렌더링 기능 점검').click()
            page.wait_for_selector('#lec-view h1:has-text("렌더링 기능 점검")')
            sec('표').click()   # 다시 불러오면 접은 상태를 잊는다(메모리에만 둠). 아래 찾기 점검을 위해 다시 접는다

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
            was_folded = folded('표')
            page.keyboard.press('Enter')   # 둘째 결과 '아래 값은 모두 예시입니다' 는 접어 둔 '표' 절 안에 있다
            check(was_folded and not folded('표') and text('아래 값은 모두').is_visible(),
                  '접은 절은 다른 문서에 다녀와도 접혀 있고, 찾기 결과로 가면 펴짐' + ('' if was_folded else ' (돌아왔을 때 펴져 있음)'))
            page.fill('#lec-find-input', '굵게, 코드')   # 원문은 **굵게**, `코드` — 글자 조각(텍스트 노드) 셋에 걸친다
            wait_until(page, "document.querySelector('#lec-find-count').textContent === '1/1'")
            crossed = page.locator('#lec-find-count').inner_text()
            page.fill('#lec-find-input', '표시가 없는 인용문은 콜아웃이 아니라 평범한')
            wait_until(page, "document.querySelector('#lec-find-count').textContent === '1/1'")
            crossed2 = page.locator('#lec-find-count').inner_text()
            page.fill('#lec-find-input', '체크리스트와 각주 숨김')   # 제목과 다음 목록 항목 사이는 넘어가지 않는다
            wait_until(page, "document.querySelector('#lec-find-count').textContent === '없음'")
            check(crossed == '1/1' and crossed2 == '1/1' and page.locator('#lec-find-count').inner_text() == '없음',
                  f'찾기가 굵게·코드 같은 서식 경계를 넘어 찾고, 블록(문단·제목) 경계는 넘지 않음 ({crossed!r}, {crossed2!r})')
            page.keyboard.press('Escape')

            print('[자동 새로고침]')
            sec('코드').click()
            page.locator('#lec-content').evaluate('el => el.scrollTop = 600')
            doc = work / 'docs' / '01-기능-점검.md'
            doc.write_text(doc.read_text(encoding='utf-8').replace('# 렌더링 기능 점검', '# 렌더링 기능 점검 (수정됨)'), encoding='utf-8')
            (work / 'research' / '새-메모.md').write_text('# 새 메모\n\n방금 만든 문서\n', encoding='utf-8')
            page.wait_for_selector('#lec-view h1:has-text("(수정됨)")', timeout=8000)
            page.wait_for_selector('#lec-tree .row.file:has-text("새 메모")', timeout=8000)
            check(page.locator('#lec-content').evaluate('el => el.scrollTop') == 600 and folded('코드'),
                  '보던 문서는 스크롤 위치와 접은 절을 유지하며 다시 그림')
            changed = page.evaluate("[...document.querySelectorAll('#lec-view .lec-changed')].map(e => e.tagName)")
            changes_btn = page.locator('#lec-st-changes')
            check(changed == ['H1'] and changes_btn.is_visible() and '1곳' in changes_btn.inner_text(),
                  f'바뀐 블록만 강조하고, 화면 밖이면 상태줄에 바뀐 곳 버튼 ({changed}, {changes_btn.inner_text()!r})')
            shot('05-live-reload')
            changes_btn.click()
            check(wait_until(page, "document.querySelector('#lec-content').scrollTop < 200"), '바뀐 곳 버튼을 누르면 그곳으로 이동')
            # 다시 그리는 동안(문서를 받는 중) 사용자가 스크롤하면, 다 그린 뒤 옛 위치로 되돌리지 않는다
            page.locator('#lec-content').evaluate('el => el.scrollTop = 300')
            held = []
            is_md_doc = lambda u: '/doc/' in u and urllib.parse.urlparse(u).path.endswith('.md')
            page.route(is_md_doc, lambda route: held.append(route))
            doc.write_text(doc.read_text(encoding='utf-8') + '\n다시 그리는 중에 더한 문단\n', encoding='utf-8')
            for _ in range(80):
                if held:
                    break
                page.wait_for_timeout(100)
            page.locator('#lec-content').evaluate('el => el.scrollTop = 900')
            for r in held:
                r.continue_()
            page.unroute(is_md_doc)
            page.wait_for_selector('#lec-view p:has-text("다시 그리는 중에 더한 문단")', timeout=8000)
            top = page.locator('#lec-content').evaluate('el => el.scrollTop')
            check(bool(held) and top == 900, f'다시 그리는 동안 스크롤하면 그 위치를 지킴 (scrollTop {top}, 붙잡은 요청 {len(held)})')
            check(page.locator('#lec-tree .row.file:has-text("새 메모") .dot').count() == 1, '새 문서에 변경 표시')

            print('[전체 검색]')
            page.locator('#lec-tree .row.file', has_text='우선순위').click()
            page.wait_for_selector('#lec-view h1:has-text("우선순위")')
            page.keyboard.press('Control+Shift+F')
            focused = page.evaluate("document.activeElement?.id")
            page.fill('#lec-search-input', '인도네시아')
            wait_until(page, "document.querySelector('#lec-search-results .sr-hit')")
            hit = page.locator('#lec-search-results .sr-hit[data-doc="docs/01-기능-점검.md"]').first
            line = int(hit.get_attribute('data-line') or 0)
            want = next(i for i, l in enumerate(doc.read_text(encoding='utf-8').split('\n'), 1) if '인도네시아' in l)
            check(focused == 'lec-search-input' and line == want and '<mark>' in hit.inner_html(),
                  f'Ctrl+Shift+F 전체 검색: 문서·줄 번호·검색어 표시 (줄 {line}, 원문 {want})')
            hit.click()
            wait_until(page, "document.querySelector('#lec-view .lec-changed')")
            state = page.evaluate("""() => ({
              title: document.querySelector('#lec-view h1')?.textContent,
              flashed: document.querySelector('#lec-view .lec-changed')?.tagName,
              find: document.querySelector('#lec-findbar').hidden ? null : document.querySelector('#lec-find-count').textContent })""")
            check(state['title'].startswith('렌더링 기능 점검') and state['flashed'] == 'TR' and state['find'] == '1/1',
                  f'검색 결과를 누르면 그 문서의 그 줄(표의 행)로 가고 검색어를 표시 ({state})')
            shot('05-search')
            page.keyboard.press('Escape')
            page.locator('.side-tabs button[data-tab="files"]').click()

            print('[파일 목록]')
            olist = '#lec-others-list'
            orow = lambda path: page.locator(f'{olist} .row[data-path="{path}"]')
            olabels = lambda: page.locator(f'{olist} .row .label').all_inner_texts()
            picked = lambda: page.evaluate(f"document.querySelector('{olist} .row.selected')?.dataset.path || null")

            def config_is(key, want, tries=20):
                """설정 저장은 뒤에서 하므로 서버 값이 바뀔 때까지 되묻는다"""
                for _ in range(tries):
                    got = page.evaluate(f"fetch('/api/config').then(r => r.json()).then(c => c.{key})")
                    if got == want:
                        return True
                    page.wait_for_timeout(100)
                return False

            def fake_open(route):   # 점검하는 PC 에서 엑셀·탐색기가 실제로 뜨지 않게 서버로 보내지 않는다
                route.fulfill(status=200, content_type='application/json', body='{"action": "default"}')

            page.route('**/api/open-external', fake_open)

            def opens(action):
                """action 을 하는 동안 보낸 '열기' 요청의 본문"""
                with page.expect_request('**/api/open-external') as req:
                    action()
                return req.value.post_data_json

            wait_until(page, f"document.querySelectorAll('{olist} .row').length > 0")
            boxes = [page.locator(sel).bounding_box() for sel in ('#lec-tree', '#lec-others-split', '#lec-others')]
            count = page.inner_text('#lec-others-count')
            check(olabels() == ['code', 'data', 'empty-folder', 'research', 'src', '첨부.pdf'] and count == '7'
                  and boxes[0]['y'] + boxes[0]['height'] <= boxes[1]['y'] + 1 <= boxes[2]['y'] + 1,
                  f"문서 트리 아래 분리선과 '파일' 목록 — 폴더 먼저·접힌 채로, 문서·숨김·제외 폴더의 파일은 없음 ({olabels()}, {count}개)")
            orow('data').locator('[data-toggle]').click()
            page.wait_for_selector(f'{olist} .row[data-path="data/표.csv"]')
            in_data = olabels()[2:4]
            # 이름 앞의 종류 아이콘: 문서(md·html)와 폴더, 최근 변경, 파일 목록
            icon_of = lambda sel: page.evaluate(f"document.querySelector('{sel} .ficon use')?.getAttribute('href') || null")
            icons = [icon_of(sel) for sel in ('#lec-tree .row[data-doc="docs/01-기능-점검.md"]', '#lec-tree .row[data-doc="docs/04-HTML-보고서.html"]',
                                              '#lec-tree .row.dir[data-dir="docs"]', '#lec-recent .row[data-doc="docs/01-기능-점검.md"]',
                                              f'{olist} .row[data-path="data/표.csv"]', f'{olist} .row[data-path="data/setup.exe"]',
                                              f'{olist} .row[data-path="첨부.pdf"]', f'{olist} .row[data-path="data"]')]
            head = page.inner_text('#lec-others-head')
            check(icons == ['#i-md', '#i-html', '#i-folder', '#i-md', '#i-table', '#i-app', '#i-text', '#i-folder'] and head.startswith('파일'),
                  f"파일 이름 앞에 종류 아이콘 — 문서(md·html)·폴더·최근 변경·파일 목록, 머리줄은 '파일' ({icons}, {head!r})")
            csv = orow('data/표.csv')
            csv.click()
            one_click = picked() == 'data/표.csv'
            body = opens(csv.dblclick)
            wait_until(page, "document.querySelector('#lec-toast').textContent.includes('열었습니다')")
            toast_text = page.locator('#lec-toast').text_content()
            check(in_data == ['setup.exe', '표.csv'] and orow('data/.secret.txt').count() == 0 and one_click
                  and body['path'] == 'data/표.csv' and 'how' not in body and '기본 앱' in toast_text,
                  f'탐색기처럼 한 번 누르면 고르고, 두 번 누르면 연다 ({body}, {toast_text!r})')
            items = menu(csv)
            copied = choose('@data/표.csv 복사')
            menu(csv)
            body = opens(lambda: page.locator('#lec-menu button', has_text='편집기로 열기').click())
            exe_items = menu(orow('data/setup.exe'))
            page.keyboard.press('Escape')
            check(all(x in items for x in ('열기', '편집기로 열기', '탐색기에서 보기', '전체 경로 복사', '파일 이름 복사', 'B ·'))
                  and copied == '@data/표.csv' and body.get('how') == 'editor'
                  and '실행하지 않음' in exe_items and '편집기로 열기' not in exe_items,
                  "우클릭: 열기·편집기로 열기·탐색기에서 보기·경로 복사, 실행 파일은 열지 않고 탐색기에서 선택만 ('편집기로 열기' 없음)")
            csv.click()
            page.keyboard.press('ArrowUp')
            up = picked()
            body = opens(lambda: page.keyboard.press('Enter'))
            page.keyboard.press('ArrowLeft')   # 파일 → 부모 폴더
            parent = picked()
            page.keyboard.press('ArrowLeft')   # 폴더 → 접기
            folded_data = orow('data/표.csv').count() == 0
            page.keyboard.press('ArrowDown')
            down = picked()
            page.keyboard.press('ArrowRight')  # 폴더 → 펼치기
            opened_dir = orow('empty-folder/readme.txt').count() == 1
            page.keyboard.press('s')           # 그 글자로 시작하는 다음 행
            typed = picked()
            check(up == 'data/setup.exe' and body['path'] == 'data/setup.exe' and parent == 'data' and folded_data
                  and down == 'empty-folder' and opened_dir and typed == 'src',
                  f'키보드: ↑↓ 로 고르고 Enter 로 열기, ← 부모·접기, → 펼치기, 글자로 찾아가기 ({up}, {parent}, {down}, {typed})')
            page.fill('#lec-filter', 'csv')
            flat = page.evaluate(f"""[...document.querySelectorAll('{olist} .row')]
                .map(r => r.querySelector('.label').textContent + '|' + (r.querySelector('.sub')?.textContent || ''))""")
            no_docs = '일치하는 문서가 없습니다' in page.inner_text('#lec-tree')
            page.locator('#lec-filter').press('Escape')
            check(flat == ['표.csv|data'] and no_docs and olabels()[0] == 'code',
                  f'사이드바 거르기는 파일 목록에도 — 거른 파일을 폴더와 함께 평평하게, Esc 로 되돌림 ({flat})')
            later_file = work / '나중-파일.txt'
            later_file.write_text('x', encoding='utf-8')
            appeared = wait_until(page, "!!document.querySelector('#lec-others-list .row[data-path=\"나중-파일.txt\"]')", 8000)
            count_after = page.inner_text('#lec-others-count')
            later_file.unlink()
            gone = wait_until(page, "!document.querySelector('#lec-others-list .row[data-path=\"나중-파일.txt\"]')", 8000)
            check(appeared and count_after == '8' and gone, f'파일이 생기거나 지워지면 목록에 바로 반영 ({count_after})')
            tree_h = page.locator('#lec-tree').bounding_box()['height']
            page.click('#lec-others-head')
            wait_until(page, "document.querySelector('#lec-files').classList.contains('others-off')")
            hidden_list = page.evaluate("getComputedStyle(document.querySelector('#lec-others-list')).display") == 'none'
            taller = page.locator('#lec-tree').bounding_box()['height'] > tree_h + 100
            saved_off = config_is('others_visible', False)
            page.click('#lec-others-head')
            check(hidden_list and taller and saved_off and wait_until(page, "!document.querySelector('#lec-files').classList.contains('others-off')"),
                  '머리줄을 누르면 접히고 문서 트리가 그만큼 길어짐 (설정에 저장), 다시 누르면 펼침')
            split = page.locator('#lec-others-split').bounding_box()
            h0 = page.locator('#lec-others').bounding_box()['height']
            page.mouse.move(split['x'] + 40, split['y'] + 4)
            page.mouse.down()
            page.mouse.move(split['x'] + 40, split['y'] - 96, steps=5)
            page.mouse.up()
            h1 = page.locator('#lec-others').bounding_box()['height']
            saved_h = config_is('others_height', round(h1))
            page.locator('#lec-others-split').dblclick()
            h2 = page.locator('#lec-others').bounding_box()['height']
            check(abs(h1 - h0 - 100) <= 4 and saved_h and abs(h2 - h0) <= 2 and config_is('others_height', None),
                  f'분리선을 끌어 높이 조절·저장, 두 번 누르면 기본 높이 ({h0:.0f} → {h1:.0f} → {h2:.0f})')
            shot('05-others')
            print('[폴더 보기]')
            page.click('#lec-btn-view')
            wait_until(page, "document.querySelector('#lec-files').classList.contains('folder-view')")
            wait_until(page, f"!!document.querySelector('{olist} .row.root')")
            hidden = page.evaluate("['#lec-tree', '#lec-others-split', '#lec-others-head'].map(s => getComputedStyle(document.querySelector(s)).display)")
            active_row = lambda: page.evaluate(f"document.querySelector('{olist} .row.active')?.dataset.path ?? null")
            revealed = active_row()
            research = orow('research')
            if research.get_attribute('aria-expanded') != 'true':
                research.locator('[data-toggle]').click()
            mixed = [orow('research/images').count(), orow('research/구리-시장-동향.md').count(),
                     icon_of(f'{olist} .row[data-path="research/구리-시장-동향.md"]')]
            check(hidden == ['none'] * 3 and revealed == 'docs/01-기능-점검.md' and mixed == [1, 1, '#i-md']
                  and page.is_visible('#lec-btn-view.on') and config_is('files_view', 'folder'),
                  f"'폴더' 버튼: 문서 트리를 감추고 한 트리에 문서와 파일을 폴더 구조 그대로, 지금 보는 문서까지 펼침, 설정에 저장 ({hidden}, {revealed}, {mixed})")
            orow('research/구리-시장-동향.md').click()
            doc_open = wait_until(page, "document.querySelector('#lec-st-path').textContent === 'research/구리-시장-동향.md'")
            now_active = active_row()
            orow('data').locator('[data-toggle]').click()
            page.wait_for_selector(f'{olist} .row[data-path="data/표.csv"]')
            body = opens(orow('data/표.csv').dblclick)
            doc_menu = menu(orow('research/구리-시장-동향.md'))
            page.keyboard.press('Escape')
            dir_menu = menu(orow('docs'))
            page.locator('#lec-menu button', has_text='폴더 개요 보기').click()
            overview = wait_until(page, "document.querySelector('#lec-view .ov-head h1')?.textContent === 'docs'")
            check(doc_open and now_active == 'research/구리-시장-동향.md' and body['path'] == 'data/표.csv'
                  and '@research/구리-시장-동향.md 복사' in doc_menu and '편집기로 열기' in doc_menu and '폴더 개요 보기' in dir_menu and overview,
                  '폴더 보기: 문서는 한 번 눌러 뷰어에서(강조), 파일은 두 번 눌러 열기, 문서·폴더 우클릭 메뉴(폴더 개요 보기)')
            shot('05-folder-view')
            page.click('#lec-btn-view')
            back_kind = wait_until(page, "!document.querySelector('#lec-files').classList.contains('folder-view')")
            check(back_kind and page.is_visible('#lec-tree') and page.is_visible('#lec-others-head') and olabels()[0] == 'code'
                  and config_is('files_view', 'kind'),
                  '다시 누르면 종류별 보기 (문서 트리 위, 분리선 아래 파일)')
            page.unroute('**/api/open-external', fake_open)

            print('[문서 속 원시 HTML]')
            page.locator('#lec-tree .row.file', has_text='원시 HTML 확인').click()
            page.wait_for_selector('#lec-view h1:has-text("원시 HTML 확인")')
            check(page.locator('#lec-view svg a[target="_blank"]').count() == 1, 'SVG 속 외부 링크가 있어도 문서를 그리고, 링크는 새 창으로')
            check(page.evaluate('typeof document.querySelector') == 'function', '<img name="querySelector"> 가 document 를 가리지 않음')
            planted = menu(page.locator('#lec-view a', has_text='심은 값 링크'))
            page.keyboard.press('Escape')
            broken = menu(page.locator('#lec-view a', has_text='깨진 값'))
            page.keyboard.press('Escape')
            check('링크 주소 복사' in planted and '링크 주소 복사' in broken,
                  '문서가 적어 둔 data-lec-* 값이 있거나 깨져 있어도 우클릭 메뉴가 뜸')
            page.locator('#lec-view img[usemap]').click()
            page.wait_for_selector('#lec-view h1:has-text("수식과 달러 표기")')
            check(page.url == url, '이미지 맵 링크는 앱 안에서 문서를 엶 (앱 창이 떠나지 않음)')
            page.keyboard.press('Alt+ArrowLeft')
            page.wait_for_selector('#lec-view h1:has-text("원시 HTML 확인")')
            page.locator('#lec-view svg a[href$=".md"]').click()
            page.wait_for_selector('#lec-view h1:has-text("수식과 달러 표기")')
            check(page.url == url, 'SVG xlink:href 링크도 앱 안에서 문서를 엶')

            print('[절대경로]')
            w = str(work)
            absdoc = work / 'docs' / '96-절대경로.md'
            absdoc.write_text(
                '# 절대경로 확인\n\n'
                f'![절대경로 그림](<{w}\\research\\images\\price-band.svg>)\n\n'
                f'- [역슬래시 절대경로 링크](<{w}\\docs\\02-수식과-달러.md>)\n'
                f'- [file 링크](file:///{w.replace(chr(92), "/")}/docs/01-기능-점검.md)\n'
                '- [프로젝트 밖](<C:\\Windows\\win.ini>)\n', encoding='utf-8')
            page.wait_for_selector('#lec-tree .row.file:has-text("절대경로 확인")', timeout=8000)
            page.locator('#lec-tree .row.file', has_text='절대경로 확인').click()
            page.wait_for_selector('#lec-view h1:has-text("절대경로 확인")')
            wait_until(page, "document.querySelector('#lec-view img')?.complete")
            got = page.evaluate("""() => ({
              img: document.querySelector('#lec-view img')?.naturalWidth || 0,
              links: [...document.querySelectorAll('#lec-view li a')].map(a => [a.title, a.classList.contains('link-off')]) })""")
            want = [['docs/02-수식과-달러.md', False], ['docs/01-기능-점검.md', False]]
            check(got['img'] > 0 and got['links'][:2] == want and got['links'][2][1],
                  f'프로젝트 안의 절대경로·file: 그림과 링크는 열리고, 밖은 막힘 ({got})')
            page.locator('#lec-view a', has_text='역슬래시 절대경로 링크').click()
            page.wait_for_selector('#lec-view h1:has-text("수식과 달러 표기")')

            page.locator('#lec-tree .row.file', has_text='구현 계획').click()
            page.wait_for_selector('#lec-view .front-matter')
            menu(page.locator('#lec-view .front-matter summary'))
            fm = choose('원문 복사')
            check(fm.startswith('---\nname: 구현 계획') and fm.endswith('---'), f'메타데이터 우클릭: 원문 복사 ({fm[:20]!r} … {fm[-6:]!r})')

            print('[경로 자동 링크]')
            (work / 'docs' / '95-경로.md').write_text(
                '# 경로 표기 확인\n\n'
                '설정은 `code/example.py:13` 에 있고, 글 속의 code/example.py 도 링크가 됩니다. docs/01-기능-점검.md에서 이어집니다.\n\n'
                '없는 파일 src/none.py 와 e.g. 같은 글자는 링크가 아닙니다.\n\n'
                '```\ncode/example.py\n```\n', encoding='utf-8')
            page.wait_for_selector('#lec-tree .row.file:has-text("경로 표기 확인")', timeout=8000)
            page.locator('#lec-tree .row.file', has_text='경로 표기 확인').click()
            wait_until(page, "document.querySelectorAll('#lec-view a.path-link').length >= 3")
            links = page.evaluate("[...document.querySelectorAll('#lec-view a.path-link')].map(a => [a.textContent, a.dataset.path, a.dataset.line || ''])")
            in_pre = page.locator('#lec-view pre a').count()
            want = [['code/example.py:13', 'code/example.py', '13'], ['code/example.py', 'code/example.py', ''],
                    ['docs/01-기능-점검.md', 'docs/01-기능-점검.md', '']]
            check(links == want and in_pre == 0, f'본문 속 경로 표기는 있는 파일만 링크로 (코드 블록 제외) ({links})')
            page.locator('#lec-view a.path-link', has_text='docs/01-기능-점검.md').click()
            page.wait_for_selector('#lec-view h1:has-text("렌더링 기능 점검")')

            print('[HTML 문서]')
            frame_js = "document.querySelector('#lec-view iframe.lec-html:not(.lec-loading)')"
            labels = page.locator('#lec-tree .row.file').all_inner_texts()
            check(page.locator('#lec-tree .row.file', has_text='HTML 보고서 예시').locator('use[href="#i-html"]').count() == 1
                  and page.locator('#lec-tree .row.dir', has_text='src').count() == 0,
                  'html 문서는 트리에 html 아이콘과 함께, src 폴더의 html(앱 소스)은 보이지 않음')
            page.locator('#lec-tree .row.file', has_text='HTML 보고서 예시').click()
            wait_until(page, f"{frame_js}?.contentDocument?.querySelector('h1')")
            frame = page.frame_locator('#lec-view iframe.lec-html:not(.lec-loading)')
            frame.locator('button').click()
            info = page.evaluate(f"""() => {{ const f = {frame_js}; const d = f.contentDocument;
              return {{ title: d.title, red: getComputedStyle(d.body).backgroundColor === 'rgb(255, 0, 0)', own: f.classList.contains('own-style'),
                       fit: Math.abs(f.getBoundingClientRect().height - d.documentElement.scrollHeight) < 4,
                       toc: document.querySelectorAll('#lec-toc a').length }}; }}""")
            check(info['title'] == 'HTML 보고서 예시' and not info['red'] and info['own'] and info['fit'] and info['toc'] == 4,
                  f'html 문서: 자기 스타일 그대로, 스크립트·인라인 이벤트는 돌지 않음, 문서 높이에 맞춘 틀, 목차 ({info})')
            spot_off = page.is_disabled('#lec-btn-spot')
            h_before = page.evaluate(f"{frame_js}.getBoundingClientRect().height")
            page.click('#lec-text-bigger')
            grown = wait_until(page, f"{frame_js}.getBoundingClientRect().height > {h_before} * 1.05")
            zoom = page.evaluate(f"{frame_js}.contentDocument.documentElement.style.zoom")
            page.click('#lec-text-reset')
            shrunk = wait_until(page, f"Math.abs({frame_js}.getBoundingClientRect().height - {h_before}) < 4")
            check(spot_off and grown and zoom == '1.1' and shrunk,
                  f'html 문서: 글자 크기는 문서 전체 확대로(틀 높이도 따라감), 장 하이라이트는 쓸 수 없음 (zoom {zoom!r}, 장 하이라이트 꺼짐 {spot_off})')
            frame.locator('td', has_text='코발트').click()
            page.keyboard.press('Control+f')   # iframe 안에 초점이 있어도 단축키가 앱으로 간다
            page.fill('#lec-find-input', '코발트')   # 찾기 막대는 앞의 검색어로 먼저 한 번 찾으므로 이 검색어의 결과를 기다린다
            wait_until(page, "document.querySelector('#lec-find-count').textContent === '1/1'")
            found = page.locator('#lec-find-count').inner_text()
            page.keyboard.press('Escape')
            frame.locator('td', has_text='코발트').click(button='right')
            page.wait_for_selector('#lec-menu:not([hidden])')
            head = page.locator('#lec-menu .menu-head').inner_text()
            frame.locator('h1').click()   # iframe 안을 누르면 메뉴가 닫힌다
            check(found == '1/1' and head == '표 · 3행 4열' and page.locator('#lec-menu').is_hidden(),
                  f'html 문서 안 찾기(Ctrl+F)와 우클릭 메뉴 ({found!r}, {head!r})')
            frame.locator('a', has_text='Markdown 문서의 표 절').click()
            page.wait_for_selector('#lec-view h1:has-text("렌더링 기능 점검")')
            page.keyboard.press('Alt+ArrowLeft')
            wait_until(page, f"{frame_js}?.contentDocument?.title === 'HTML 보고서 예시'")
            check(True, 'html 문서의 링크로 md 문서를 열고 뒤로 돌아옴')
            report.write_text(report.read_text(encoding='utf-8').replace('공급 과잉', '공급 과잉 해소'), encoding='utf-8')
            changed_ok = wait_until(page, f"{frame_js}?.contentDocument?.body.textContent.includes('공급 과잉 해소')", 8000)
            changed = page.evaluate(f"[...{frame_js}.contentDocument.querySelectorAll('.lec-changed')].map(e => e.tagName)")
            frames = page.locator('#lec-view iframe').count()
            check(changed_ok and changed == ['TR'] and frames == 1, f'html 문서도 자동 새로고침, 바뀐 행만 강조 ({changed}, 틀 {frames}개)')
            page.locator('#lec-tree .row.file', has_text='접는 html').click()
            wait_until(page, f"{frame_js}?.contentDocument?.title === '접는 html'")
            height = lambda: page.evaluate(f"{frame_js}.getBoundingClientRect().height")
            h0 = height()
            fold_frame = page.frame_locator('#lec-view iframe.lec-html:not(.lec-loading)')
            fold_frame.locator('summary').click()
            opened = wait_until(page, f"{frame_js}.getBoundingClientRect().height > {h0 + 1500}")
            fold_frame.locator('summary').click()
            closed = wait_until(page, f"{frame_js}.getBoundingClientRect().height < {h0 + 40}")
            check(opened and closed and h0 < 300, f'html 틀 높이가 내용을 따라 늘고 다시 줄어듦 (처음 {h0:.0f}px, 접은 뒤 {height():.0f}px)')
            fold_frame.locator('text=SVG 링크').click()
            svg_ok = wait_until(page, "document.querySelector('#lec-view h1')?.textContent.includes('렌더링 기능 점검')")
            check(svg_ok, 'html 문서 속 SVG 링크(xlink:href)도 뷰어 안에서 열림 (iframe 이 떠나지 않음)')
            # HEAD 뒤에 문서가 사라지면(404) 안내 화면, 앞 문서의 목차가 남지 않음
            fold_url = lambda u: '/doc/' in u and '/docs/93-' in urllib.parse.unquote(u)
            page.route(fold_url, lambda route: route.fulfill(status=404, body='없음', headers={'Content-Security-Policy': 'sandbox'})
                       if route.request.method == 'GET' else route.continue_())
            page.locator('#lec-tree .row.file', has_text='접는 html').click()
            gone = wait_until(page, "document.querySelector('#lec-view .doc-missing')?.textContent.includes('문서가 없거나')")
            toc_left = page.locator('#lec-toc a').count()
            page.unroute(fold_url)
            check(gone and toc_left == 0, f'html 을 불러오다 없어지면 \'문서 없음\' 안내, 앞 문서의 목차는 지움 (목차 {toc_left}개)')
            page.locator('#lec-tree .row.file', has_text='스타일 없는 HTML').click()
            wait_until(page, f"{frame_js}?.contentDocument?.title === '스타일 없는 HTML'")
            themed = page.evaluate(f"""(() => {{ const d = {frame_js}.contentDocument;
              return d.body.classList.contains('md-body') && !!d.querySelector('link[href*="/static/themes/base.css"]'); }})()""")
            check(themed, '스타일이 없는 html 은 Lectern 스타일로')
            readable_js = rf'''(() => {{ const d = {frame_js}.contentDocument, w = d.defaultView;
              const rgb = (s) => s.match(/[\d.]+/g).slice(0, 3).map(Number).map((x) => (s.startsWith('color(') ? x * 255 : x));
              const lum = (c) => c.map((x) => {{ x /= 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; }})
                .reduce((a, x, i) => a + x * [0.2126, 0.7152, 0.0722][i], 0);
              // 바탕을 칠하지 않으면(투명) Chromium 이 흰색을 칠하므로 흰색으로 본다
              const bg = w.getComputedStyle(d.documentElement).backgroundColor;
              const back = /,\s*0\)$/.test(bg) ? [255, 255, 255] : rgb(bg);
              const [a, b] = [lum(rgb(w.getComputedStyle(d.querySelector('p')).color)), lum(back)].sort((m, n) => n - m);
              return Math.round((a + 0.05) / (b + 0.05) * 10) / 10; }})()'''
            use_theme('dark')
            page.locator('#lec-tree .row.file', has_text='스타일 없는 HTML').click()
            wait_until(page, f"{frame_js}?.contentDocument?.documentElement.dataset.lecBackdrop === 'dark'")
            plain_dark = page.evaluate(readable_js)
            use_theme('default')
            page.locator('#lec-tree .row.file', has_text='밝은 글자 문서').click()
            wait_until(page, f"{frame_js}?.contentDocument?.title === '밝은 글자 문서'")
            light_text = page.evaluate(readable_js)
            shot('08-html-light-text')
            check(plain_dark >= 4.5 and light_text >= 4.5,
                  f'html 글자가 바탕에 묻히지 않음: 다크 스타일의 스타일 없는 문서 {plain_dark}:1, 바탕 없이 밝은 글자만 정한 문서 {light_text}:1')
            shot('08-html-plain')
            page.keyboard.press('Control+Shift+F')
            page.fill('#lec-search-input', '배터리 수요')
            stale = page.locator('#lec-search-results .sr-hit').count()   # 입력하면 앞 검색어의 결과는 바로 지운다
            page.keyboard.press('Enter')   # 결과를 기다리지 않고 Enter — 이 검색어로 찾은 첫 결과가 열려야 한다
            opened = wait_until(page, f"{frame_js}?.contentDocument?.title === 'HTML 보고서 예시' && document.querySelector('#lec-find-count').textContent === '1/1'")
            check(stale == 0 and opened, f'전체 검색이 html 본문도 찾고, 누르면 그 문서에서 표시 (남은 옛 결과 {stale}개)')
            shot('08-html')
            page.keyboard.press('Escape')
            page.locator('.side-tabs button[data-tab="files"]').click()

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
            ext_doc = work / 'docs' / '99-외부-이미지.md'
            ext_doc.write_text(ext_doc.read_text(encoding='utf-8') + '\n새로 더한 문단\n', encoding='utf-8')
            page.wait_for_selector('#lec-view p:has-text("새로 더한 문단")', timeout=8000)
            flashed = page.evaluate("[...document.querySelectorAll('#lec-view .lec-changed')].map(e => e.textContent.trim())")
            check(flashed == ['새로 더한 문단'], f'자동 새로고침 때 불러오지 못한 외부 이미지는 다시 기다리지 않고 바뀐 곳으로 잡지 않음 ({flashed})')
            leaked = [u for u, _ in outside if 'leak-' in u and u not in blocked] + [p for p in _QuietHandler.received if 'leak-' in p]
            check(not leaked, '표 배경·SVG·image-set 으로는 외부 요청이 나가지 않음' + (f': {leaked}' if leaked else ''))
            items = menu(page.locator('#lec-view img.external'))
            page.keyboard.press('Escape')
            check('그림 주소 복사' in items and '그림 복사' not in items, '인터넷 그림은 그림 대신 주소를 복사 (브라우저가 픽셀을 막음)')
            shot('06-external-images')
            page.evaluate("fetch('/api/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({external_images:false})})")
            page.reload()
            page.wait_for_selector('#lec-view h1')   # 마지막에 보던 문서나 폴더 개요 (마지막 위치 복원)
            before = len(outside)
            page.locator('#lec-tree .row.file', has_text='외부 이미지 확인').click()
            page.wait_for_selector('#lec-view h1:has-text("외부 이미지 확인")')
            page.wait_for_timeout(500)
            check(page.locator('#lec-view .image-off').count() == 2 and len(outside) == before,
                  '설정을 끄면 외부 이미지를 불러오지 않음')

            print('[뒤로 빠르게, 키보드 초점]')
            for title in ('우선순위', '후속 과제', '렌더링 기능 점검'):
                page.locator('#lec-tree .row.file', has_text=title).click()
                page.wait_for_selector(f'#lec-view h1:has-text("{title}")')
            page.keyboard.press('Alt+ArrowLeft')
            page.keyboard.press('Alt+ArrowLeft')   # 앞의 '뒤로'가 그리기를 마치기 전에
            two_back = wait_until(page, "document.querySelector('#lec-view h1')?.textContent.includes('우선순위')")
            check(two_back, '뒤로를 빠르게 두 번 누르면 두 칸 뒤로')
            row = page.locator('#lec-tree .row.file', has_text='우선순위')
            row.focus()
            memo = work / 'research' / '새-메모.md'
            memo.write_text('# 새 메모 (고침)\n\n방금 고친 문서\n', encoding='utf-8')
            page.wait_for_selector('#lec-tree .row.file:has-text("새 메모 (고침)")', timeout=8000)
            focused = page.evaluate("document.activeElement?.dataset?.doc")
            check(focused == row.get_attribute('data-doc'), f'파일이 바뀌어 트리를 다시 그려도 키보드 초점이 그 행에 남음 ({focused})')

            print('[설정과 마지막 위치]')
            page.keyboard.press('Control+Comma')
            dialog = page.locator('#lec-settings')
            boxes = page.evaluate("[...document.querySelectorAll('#lec-settings input[data-key]')].map(i => i.dataset.key + '=' + i.checked)")
            check(dialog.is_visible() and boxes == ['restore_last=true', 'expand_first_level=true', 'math=true', 'external_images=false',
                                                   'terminal_follow_style=true'],
                  f'Ctrl+, 로 설정 창, 지금 설정이 표시됨 ({boxes})')
            shot('07-settings')
            page.locator('#lec-settings input[data-key="expand_first_level"]').click()
            cfg = page.evaluate("fetch('/api/config').then(r => r.json())")
            page.locator('#lec-settings input[data-key="expand_first_level"]').click()
            page.keyboard.press('Escape')
            check(cfg['expand_first_level'] is False and not dialog.is_visible(), '설정 창에서 바꾼 값을 저장하고 Esc 로 닫힘')
            box = page.locator('#lec-resizer').bounding_box()
            page.mouse.move(box['x'] + 3, box['y'] + 200)
            page.mouse.down()
            page.mouse.move(400, box['y'] + 220, steps=6)
            page.mouse.up()
            dragged = page.locator('#lec-sidebar').bounding_box()['width']
            saved_w = page.evaluate("fetch('/api/config').then(r => r.json()).then(c => c.sidebar_width)")
            page.mouse.dblclick(400, box['y'] + 200)
            page.wait_for_timeout(100)
            reset = page.locator('#lec-sidebar').bounding_box()['width']
            check(abs(dragged - 400) <= 2 and saved_w and abs(saved_w - 400) <= 2 and abs(reset - 288) <= 1,
                  f'사이드바 경계를 끌어 폭 조절·저장, 두 번 누르면 기본 폭 ({dragged:.0f} → 저장 {saved_w}, 기본 {reset:.0f})')
            page.locator('#lec-tree .row.file', has_text='렌더링 기능 점검').click()
            page.wait_for_selector('#lec-view h1:has-text("렌더링 기능 점검")')
            page.locator('#lec-content').evaluate('el => el.scrollTop = 500')
            remembered = False   # wait_until 은 Promise 를 참으로 보므로 서버 상태는 여기서 되묻는다 (스크롤이 멈추고 1.5초 뒤 저장)
            for _ in range(40):
                pos = page.evaluate("fetch('/api/state').then(r => r.json()).then(s => s.projects.find(p => p.id === s.active).position)")
                if pos['doc'] == 'docs/01-기능-점검.md' and pos['scroll'].get('docs/01-기능-점검.md') == 500:
                    remembered = True
                    break
                page.wait_for_timeout(200)
            page.reload()
            # 한 번 시간 초과가 난 적이 있어(원인 못 찾음), 기다리지 못해도 무엇이 열렸는지 남긴다
            reopened = wait_until(page, "document.querySelector('#lec-view h1')?.textContent.includes('렌더링 기능 점검')", 15000)
            top = page.locator('#lec-content').evaluate('el => el.scrollTop')
            opened = page.evaluate("document.querySelector('#lec-view h1')?.textContent || document.querySelector('#lec-view')?.className")
            check(remembered and reopened and top == 500,
                  f'다시 열면 마지막에 보던 문서와 스크롤 위치로 (scrollTop {top}, 열린 것 {opened!r}, 기억 {pos})')

            print('[프로젝트 탭]')
            second = tmp / 'second'
            (second / 'notes').mkdir(parents=True)
            (second / 'README.md').write_text('# 둘째 프로젝트\n\n## 첫 절\n\n본문\n\n## 둘째 절\n\n' + '긴 문단입니다.\n\n' * 80, encoding='utf-8')
            (second / 'notes' / '메모.md').write_text('# 둘째의 메모\n\n내용\n', encoding='utf-8')
            (second / 'assets').mkdir()
            (second / 'assets' / 'logo.png').write_bytes(b'png')
            dup = tmp / 'other' / 'samples'   # 첫 프로젝트와 이름이 같은 폴더
            dup.mkdir(parents=True)
            (dup / 'a.md').write_text('# 같은 이름 폴더의 문서\n', encoding='utf-8')
            tabs = lambda: page.evaluate('''() => [...document.querySelectorAll('#lec-tablist .lec-tab')].map(t => ({
              name: t.querySelector('.name').textContent, sub: t.querySelector('.sub')?.textContent || '',
              active: t.classList.contains('active'), dot: !!t.querySelector('.dot') }))''')
            n_tabs = lambda n: wait_until(page, f"document.querySelectorAll('#lec-tablist .lec-tab').length === {n}")
            tab_el = lambda i: page.locator('#lec-tablist .lec-tab').nth(i)
            h1_has = lambda text: wait_until(page, f"document.querySelector('#lec-view h1')?.textContent.includes('{text}')", 10000)
            tree_root = lambda: page.evaluate("document.querySelector('#lec-tree .row.root .label')?.textContent")
            ui_now = lambda: page.evaluate('''() => ({ toc: document.querySelector('#lec-toc .toc-list a')?.textContent || '',
              status: document.querySelector('#lec-st-path').textContent, tree: document.querySelector('#lec-tree .row.active')?.dataset.doc,
              top: Math.round(document.querySelector('#lec-content').scrollTop) })''')
            api_state = lambda: page.evaluate('fetch("/api/state").then(r => r.json())')
            one = tabs()
            page.evaluate("window.__firstH1 = document.querySelector('#lec-view h1')")   # 탭을 오가도 다시 그리지 않는지 볼 표시
            first = ui_now()
            check(len(one) == 1 and one[0]['name'] == 'samples' and one[0]['active'] and first['status'] == 'docs/01-기능-점검.md',
                  f'연 폴더 하나가 탭 하나 ({one})')
            page.once('dialog', lambda d: d.accept(str(second)))   # 브라우저 모드의 폴더 열기는 경로를 묻는다
            page.click('#lec-btn-open')
            opened = n_tabs(2) and wait_until(page, "document.querySelector('#lec-view .ov-head h1')?.textContent === 'second'")
            t, labels = tabs(), page.locator('#lec-tree .row .label').all_inner_texts()
            check(opened and [x['active'] for x in t] == [False, True] and tree_root() == 'second'
                  and '둘째의 메모' in labels and '렌더링 기능 점검' not in labels
                  and wait_until(page, "document.querySelector('#lec-others-list .row .label')?.textContent === 'assets'")
                  and olabels() == ['assets'],
                  f'폴더 열기(+)는 새 탭으로 열고, 왼쪽 트리·문서 외 파일과 화면이 그 폴더의 것으로 ({t})')
            look = page.evaluate('''() => {
              const css = (sel) => getComputedStyle(document.querySelector(sel));
              const tab = css('#lec-tablist .lec-tab.active'), other = css('#lec-tablist .lec-tab:not(.active)');
              return { size: parseFloat(tab.fontSize), side: parseFloat(css('#lec-tree .row .label').fontSize),
                       weight: Number(tab.fontWeight), otherWeight: Number(other.fontWeight),
                       filled: tab.backgroundColor !== css('#lec-tabbar').backgroundColor && tab.backgroundColor !== other.backgroundColor,
                       icons: document.querySelectorAll('#lec-tablist .lec-tab .ficon use[href="#i-folder"]').length }; }''')
            check(look['size'] > look['side'] and look['weight'] >= 700 and look['otherWeight'] >= 600 and look['filled'] and look['icons'] == 2,
                  f'프로젝트 탭은 사이드바 글자보다 크고 굵게, 선택된 탭은 바탕색으로, 이름 앞에 폴더 아이콘 ({look})')
            page.locator('#lec-tree .row.file', has_text='둘째 프로젝트').click()
            h1_has('둘째 프로젝트')
            page.locator('#lec-content').evaluate('el => el.scrollTop = 900')
            tab_el(0).click()
            back_first = h1_has('렌더링 기능 점검')
            same = page.evaluate("document.querySelector('#lec-view h1') === window.__firstH1")
            st = ui_now()
            shot('09-tabs')
            check(back_first and same and st == first and tree_root() == 'samples',
                  f'탭을 누르면 트리·목차·상태줄과 문서가 그 탭의 것으로 — 문서는 다시 그리지 않고 읽던 위치 그대로 ({st})')
            tab_el(1).click()
            h1_has('둘째 프로젝트')
            second_top = ui_now()['top']
            page.keyboard.press('Alt+ArrowLeft')
            went_back = wait_until(page, "document.querySelector('#lec-view .ov-head h1')?.textContent === 'second'")
            tab_el(0).click()
            first_kept = h1_has('렌더링 기능 점검')
            tab_el(1).click()
            page.keyboard.press('Alt+ArrowRight')
            forward_ok = h1_has('둘째 프로젝트')
            check(second_top == 900 and went_back and first_kept and forward_ok, '뒤로/앞으로와 스크롤 위치는 탭마다')
            # 사이드바(파일 거르기·전체 검색)도 탭마다
            tab_el(0).click()
            page.fill('#lec-filter', '우선')
            tab_el(1).click()
            other_filter = page.input_value('#lec-filter')
            page.keyboard.press('Control+Shift+F')
            page.fill('#lec-search-input', '긴 문단')
            wait_until(page, "document.querySelector('#lec-search-results .sr-hit')")
            tab_el(0).click()
            first_side = page.evaluate('''() => ({ filter: document.querySelector('#lec-filter').value,
              files: !document.querySelector('#lec-files').hidden, rows: document.querySelectorAll('#lec-tree .row.file').length })''')
            tab_el(1).click()
            second_side = page.evaluate('''() => ({ search: !document.querySelector('#lec-search').hidden,
              q: document.querySelector('#lec-search-input').value, hits: document.querySelectorAll('#lec-search-results .sr-hit').length })''')
            check(other_filter == '' and first_side == {'filter': '우선', 'files': True, 'rows': 1}
                  and second_side['search'] and second_side['q'] == '긴 문단' and second_side['hits'] > 0,
                  f'사이드바의 거르기·검색어·검색 결과는 탭마다 ({first_side}, {second_side})')
            page.locator('.side-tabs button[data-tab="files"]').click()
            tab_el(0).click()
            page.fill('#lec-filter', '')
            page.locator('#lec-filter').dispatch_event('input')
            # 다른 탭 프로젝트의 파일은 링크·그림으로도 열지 않는다 (id 를 알아도)
            second_id = next(p['id'] for p in api_state()['projects'] if p['name'] == 'second')
            (work / 'docs' / '92-다른-탭.md').write_text(
                f'# 다른 탭 경로\n\n[다른 탭 문서](../../{second_id}/README.md)\n\n![다른 탭 그림](../../{second_id}/notes/x.png)\n', encoding='utf-8')
            page.wait_for_selector('#lec-tree .row.file:has-text("다른 탭 경로")', timeout=8000)
            page.locator('#lec-tree .row.file', has_text='다른 탭 경로').click()
            h1_has('다른 탭 경로')
            cross = page.evaluate('''() => ({ off: document.querySelector('#lec-view a')?.classList.contains('link-off'),
              img: document.querySelector('#lec-view .image-off')?.textContent || '' })''')
            check(cross['off'] and cross['img'].startswith('표시할 수 없는 이미지'), f'다른 탭 프로젝트로 넘어가는 상대경로는 막힘 ({cross})')
            # 숨은 탭에서 바뀐 문서: 탭에 점, 그 탭을 고르면 바뀐 곳을 강조하며 다시 그림
            page.keyboard.press('Alt+ArrowLeft')
            h1_has('렌더링 기능 점검')
            readme2 = second / 'README.md'
            readme2.write_text(readme2.read_text(encoding='utf-8').replace('본문\n', '본문\n\n숨은 탭에서 고친 문단\n'), encoding='utf-8')
            dotted = wait_until(page, "!!document.querySelectorAll('#lec-tablist .lec-tab')[1]?.querySelector('.dot')", 8000)
            not_yet = 'second' not in (page.evaluate("document.querySelector('#lec-view h1')?.textContent") or '')
            tab_el(1).click()
            redrawn = wait_until(page, "document.querySelector('#lec-view').textContent.includes('숨은 탭에서 고친 문단')", 8000)
            flashed = page.evaluate("[...document.querySelectorAll('#lec-view .lec-changed')].map(e => e.textContent.trim())")
            check(dotted and not_yet and redrawn and flashed == ['숨은 탭에서 고친 문단'] and not tabs()[1]['dot'],
                  f'숨은 탭의 문서가 바뀌면 탭에 점, 고르면 다시 그리고 바뀐 곳 강조 ({flashed})')
            # 다른 실행(탐색기 우클릭 등)이 서버에 폴더를 넘기면 그 탭이 생기고 고른다. 같은 이름의 폴더는 상위 폴더 이름으로 구분
            page.evaluate("p => fetch('/api/open', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({path: p})})"
                          ".then(r => r.status)", str(dup))
            ext = n_tabs(3) and wait_until(page, "document.querySelectorAll('#lec-tablist .lec-tab')[2]?.classList.contains('active')", 8000)
            t = tabs()
            check(ext and h1_has('samples') and t[2]['sub'] == 'other' and t[0]['sub'] == tmp.name,
                  f'서버에 새로 연 폴더는 탭으로 생기고 고름, 같은 이름의 탭은 상위 폴더 이름을 붙임 ({t})')
            page.click('#lec-btn-recent')
            page.locator('#lec-menu button', has_text='second').first.click()
            again = wait_until(page, "document.querySelectorAll('#lec-tablist .lec-tab')[1]?.classList.contains('active')")
            check(again and len(tabs()) == 3 and h1_has('둘째 프로젝트'), '이미 열린 폴더를 다시 열면 새 탭 대신 그 탭으로')
            page.keyboard.press('Control+1')
            k1 = tabs()[0]['active']
            before = ui_now()['top']
            page.keyboard.press('PageDown')
            scrolled = wait_until(page, f"document.querySelector('#lec-content').scrollTop > {before}")
            page.keyboard.press('Control+9')
            k9 = tabs()[2]['active']
            page.keyboard.press('Control+PageDown')
            wrap = tabs()[0]['active']
            page.keyboard.press('Control+Shift+Tab')
            prev = tabs()[2]['active']
            check(k1 and scrolled and k9 and wrap and prev, 'Ctrl+1~8·Ctrl+9(마지막), Ctrl+PageDown·Ctrl+Shift+Tab 으로 탭, 고른 뒤 PageDown 은 그 탭 문서를 스크롤')
            items = menu(tab_el(2))
            page.keyboard.press('Escape')
            tab_el(2).locator('.tab-close').click()
            closed = n_tabs(2) and tabs()[1]['active'] and h1_has('둘째 프로젝트')
            cfg = page.evaluate("fetch('/api/config').then(r => r.json())")
            check('탭 닫기' in items and '다른 탭 모두 닫기' in items and closed and cfg['tabs'] == [str(work), str(second)],
                  f'× 로 탭을 닫으면 옆 탭으로, 설정의 열린 탭 목록도 ({cfg["tabs"]})')
            page.locator('#lec-content').evaluate('el => el.scrollTop = 700')
            saved = False   # 스크롤이 멈추고 1.5초 뒤 저장
            for _ in range(40):
                pos = next(p['position'] for p in api_state()['projects'] if p['id'] == second_id)
                if pos['doc'] == 'README.md' and pos['scroll'].get('README.md') == 700:
                    saved = True
                    break
                page.wait_for_timeout(200)
            page.reload()
            restored = n_tabs(2) and h1_has('둘째 프로젝트')
            top2 = ui_now()['top']
            tab_el(0).click()   # 처음 고를 때 트리를 읽고 마지막 문서로
            lazy = h1_has('렌더링 기능 점검') and tree_root() == 'samples'
            check(saved and restored and tabs()[0]['active'] and top2 == 700 and lazy,
                  f'다시 열면 탭들과 선택된 탭, 탭마다 마지막 문서·스크롤 위치를 되살림 (scrollTop {top2})')
            tab_el(1).click(button='middle')   # 가운데 버튼으로 닫기
            middle = n_tabs(1) and tabs()[0]['active'] and h1_has('렌더링 기능 점검')
            tab_el(0).locator('.tab-close').click()
            welcome = wait_until(page, "!!document.querySelector('#lec-view.welcome h1') && !document.querySelector('#lec-tree .row')")
            title = page.title()
            page.locator('#lec-view.welcome button[data-path]', has_text=str(work)).click()   # 최근 연 폴더에서 다시 열기
            reopened = n_tabs(1) and h1_has('렌더링 기능 점검') and tree_root() == 'samples'
            check(middle and welcome and title == 'Lectern' and reopened,
                  f'탭을 가운데 버튼으로도 닫고, 모두 닫으면 시작 화면(트리 비움), 최근 연 폴더로 다시 열기 ({middle}, {welcome}, {title!r}, {reopened})')

            print('[터미널]')
            page.wait_for_selector('#lec-toc .toc-list a')   # 목차가 있는 문서 (터미널을 열면 감춘다)

            def term_has(text: str, ms: int = 15000) -> bool:
                """보이는 터미널 화면에 text 가 나올 때까지 (줄바꿈으로 나뉜 긴 경로도 이어서 본다)"""
                try:
                    page.wait_for_function('''t => [...document.querySelectorAll('#lec-term .term-box:not([hidden]) .xterm-rows > div')]
                      .map(r => r.textContent).join('').includes(t)''', arg=text, timeout=ms)
                    return True
                except Exception:
                    return False

            term_ui = lambda: page.evaluate('''() => { const h = document.documentElement; return {
              on: h.classList.contains('term-on'), toc: !h.classList.contains('toc-off'), hidden: document.querySelector('#lec-term').hidden,
              btn: document.querySelector('#lec-btn-term').classList.contains('on'), title: document.querySelector('#lec-term-title').textContent,
              focus: !!document.activeElement?.closest('#lec-term'), boxes: document.querySelectorAll('#lec-term .term-box').length }; }''')
            page.click('#lec-btn-term')
            started = term_has('PS ', 30000)
            t1 = term_ui()
            check(started and t1['on'] and not t1['hidden'] and t1['btn'] and not t1['toc'] and t1['focus'] and t1['title'] == 'PowerShell — samples',
                  f'터미널 버튼: 오른쪽에 PowerShell 이 프로젝트 폴더에서 뜨고, 목차는 감추고, 입력이 터미널로 ({t1})')
            page.keyboard.type('Write-Output ("lec" + "term" + "한글"); (Get-Location).Path')
            page.keyboard.press('Enter')
            ran = term_has('lecterm한글') and term_has(str(work))
            shot('10-terminal')
            check(ran, '터미널에 친 명령이 돌고, 한글 출력과 현재 폴더(프로젝트)가 보임')
            page.keyboard.press('Control+p')   # 터미널 안의 키는 셸 것 — 앱 단축키가 가로채지 않는다
            page.keyboard.press('Control+f')
            page.keyboard.press('Escape')
            no_app_keys = page.evaluate("document.querySelector('#lec-palette').hidden && document.querySelector('#lec-findbar').hidden")
            page.click('#lec-btn-toc')   # 터미널을 연 동안 목차 버튼은 목차를 함께 볼지만 바꾼다 (설정은 그대로)
            toc_with = term_ui()['toc']
            page.click('#lec-btn-toc')
            toc_cfg = page.evaluate("fetch('/api/config').then(r => r.json()).then(c => c.toc_visible)")
            check(no_app_keys and toc_with and not term_ui()['toc'] and toc_cfg is not False,
                  f'터미널 안에서는 Ctrl+P·Ctrl+F 가 셸로, 목차 버튼으로 목차를 함께 볼 수 있음 ({no_app_keys}, {toc_with}, {toc_cfg})')
            page.click('#lec-term-body')
            page.keyboard.press('Control+Backquote')
            closed = term_ui()
            page.keyboard.press('Control+Backquote')
            reopened = term_ui()
            kept = term_has('lecterm한글', 3000)
            check(closed['hidden'] and not closed['on'] and closed['toc'] and not reopened['hidden'] and reopened['focus'] and kept,
                  f'Ctrl+` 로 터미널을 닫고 열기 — 닫아도 셸은 그대로, 다시 열면 이어서 ({closed}, {reopened})')
            handle = page.locator('#lec-term-resizer').bounding_box()
            width0 = page.locator('#lec-term').bounding_box()['width']
            page.mouse.move(handle['x'] + 3, handle['y'] + 200)
            page.mouse.down()
            page.mouse.move(handle['x'] - 117, handle['y'] + 200, steps=4)
            page.mouse.up()
            width1 = page.locator('#lec-term').bounding_box()['width']
            saved_w = page.evaluate("fetch('/api/config').then(r => r.json()).then(c => c.terminal_width)")
            page.dblclick('#lec-term-resizer')
            width2 = page.locator('#lec-term').bounding_box()['width']
            reset_w = page.evaluate("fetch('/api/config').then(r => r.json()).then(c => c.terminal_width)")
            check(abs(width1 - width0 - 120) <= 3 and saved_w and abs(saved_w - width1) <= 2 and reset_w is None and abs(width2 - width0) <= 2,
                  f'경계를 끌어 터미널 폭 조절·저장, 두 번 누르면 기본 폭 ({width0:.0f} → {width1:.0f} 저장 {saved_w}, → {width2:.0f})')
            page.click('#lec-term-restart')
            restarted = wait_until(page, '''![...document.querySelectorAll('#lec-term .term-box:not([hidden]) .xterm-rows > div')]
              .map(r => r.textContent).join('').includes('lecterm')''') and term_has('PS ', 30000)
            check(restarted, '다시 시작 버튼: 셸을 새로 띄움 (화면도 비움)')
            # 터미널 색은 문서 스타일을 따른다 (바탕 = 코드 블록 바탕). 프로그램이 쓴 흰 글자·회색도 바탕과 4.5:1 이상 (minimumContrastRatio)
            term_colors = lambda: page.evaluate('''() => {
              const lum = (c) => { const m = c.match(/[\d.]+/g).map(Number);
                const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
                return 0.2126 * f(m[0]) + 0.7152 * f(m[1]) + 0.0722 * f(m[2]); };
              const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
              const box = document.querySelector('#lec-term .term-box:not([hidden])');
              const bg = getComputedStyle(box.querySelector('.xterm-viewport')).backgroundColor;
              const probe = document.createElement('div');
              probe.style.background = getComputedStyle(document.documentElement).getPropertyValue('--md-code-bg');
              document.body.append(probe);
              const code = getComputedStyle(probe).backgroundColor;
              probe.remove();
              let worst = 99;
              for (const span of box.querySelectorAll('.xterm-rows span')) {
                if (!span.textContent.trim()) continue;
                const st = getComputedStyle(span);
                worst = Math.min(worst, ratio(st.color, st.backgroundColor === 'rgba(0, 0, 0, 0)' ? bg : st.backgroundColor));
              }
              return { bg, code, panel: getComputedStyle(document.querySelector('#lec-term')).backgroundColor,
                       light: document.querySelector('#lec-term').classList.contains('term-light'), worst: Math.round(worst * 100) / 100 }; }''')
            page.click('#lec-term-body')
            page.keyboard.type('Write-Host 흰글자 -ForegroundColor White; Write-Host 회색 -ForegroundColor DarkGray; $n = 42')
            page.keyboard.press('Enter')
            term_has('회색')
            use_theme('default')
            c_light = term_colors()
            use_theme('solarized-dark')
            c_dark = term_colors()
            shot('10-terminal-solarized-dark')
            check(c_light['bg'] == c_light['code'] == c_light['panel'] and c_light['light'] and c_light['worst'] >= 4.45
                  and c_dark['bg'] == c_dark['code'] == 'rgb(7, 54, 66)' and not c_dark['light'] and c_dark['worst'] >= 4.45,
                  f'터미널 색이 스타일을 따름 — 바탕은 코드 블록 바탕, 글자 대비 4.5:1 이상 (기본 {c_light}, Solarized 다크 {c_dark})')
            follow = page.locator('#lec-settings input[data-key="terminal_follow_style"]')
            page.click('#lec-btn-settings')
            on_first = follow.is_checked()
            follow.uncheck()
            page.click('#lec-settings-close')
            wait_until(page, "getComputedStyle(document.querySelector('#lec-term .term-box:not([hidden]) .xterm-viewport')).backgroundColor === 'rgb(30, 31, 34)'")
            c_fixed = term_colors()
            saved_off = page.evaluate("fetch('/api/config').then(r => r.json()).then(c => c.terminal_follow_style)")
            page.click('#lec-btn-settings')
            follow.check()
            page.click('#lec-settings-close')
            wait_until(page, "getComputedStyle(document.querySelector('#lec-term .term-box:not([hidden]) .xterm-viewport')).backgroundColor === 'rgb(7, 54, 66)'")
            back_style = term_colors()
            use_theme('default')
            check(on_first and c_fixed['bg'] == c_fixed['panel'] == 'rgb(30, 31, 34)' and not c_fixed['light'] and saved_off is False
                  and back_style['bg'] == 'rgb(7, 54, 66)',
                  f"설정 창 '터미널 색을 스타일에 맞춤'을 끄면 늘 어둡게, 켜면 다시 스타일 색 ({c_fixed['bg']}, 저장 {saved_off}, {back_style['bg']})")
            term_status = page.evaluate('''async () => {
              const secret = document.querySelector('meta[name="lec-term"]').content;
              const get = (h) => fetch('/api/term/read?t=nope&from=0', { headers: h }).then(r => r.status);
              return [await get({}), await get({ 'X-Term': 'wrong' }), await get({ 'X-Term': secret })]; }''')
            check(term_status == [403, 403, 404], f'터미널 API 는 페이지의 비밀값(X-Term) 없이는 403 ({term_status})')
            page.once('dialog', lambda d: d.accept(str(second)))
            page.click('#lec-btn-open')
            per_tab = n_tabs(2) and term_has(f'PS {second}>', 30000)
            t2 = term_ui()
            check(per_tab and t2['title'] == 'PowerShell — second' and t2['boxes'] == 2,
                  f'탭마다 셸이 따로 — 새 탭을 고르면 그 폴더의 셸 ({t2})')
            page.click('#lec-term-body')
            page.keyboard.type('ping -n 30 127.0.0.1')
            page.keyboard.press('Enter')
            pinging = term_has('TTL=')
            asked: list[str] = []
            page.once('dialog', lambda d: (asked.append(d.message), d.dismiss()))
            tab_el(1).locator('.tab-close').click()
            for _ in range(50):   # 서버에 물어본 뒤 묻는다
                if asked:
                    break
                page.wait_for_timeout(100)
            kept_tab = len(asked) == 1 and n_tabs(2)
            page.once('dialog', lambda d: (asked.append(d.message), d.accept()))
            tab_el(1).locator('.tab-close').click()
            closed_tab = n_tabs(1) and wait_until(page, "document.querySelector('#lec-term-title').textContent === 'PowerShell — samples'")
            check(pinging and kept_tab and closed_tab and len(asked) == 2 and '실행 중' in asked[0]
                  and page.evaluate("document.querySelectorAll('#lec-term .term-box').length") == 1 and term_has('PS ', 3000),
                  f'터미널에서 프로그램이 돌면 탭을 닫기 전에 묻고, 닫으면 그 셸도 끝 — 남은 탭의 셸로 ({asked[:1]})')
            page.click('#lec-term-close')
            gone = term_ui()
            check(gone['hidden'] and not gone['on'] and gone['toc'] and not gone['btn'], f'✕ 로 터미널 닫기 ({gone})')

            print('[인쇄]')
            page.locator('#lec-tree .row.file', has_text='렌더링 기능 점검').click()
            page.wait_for_selector('#lec-view h1:has-text("렌더링 기능 점검")')
            items = menu(page.locator('#lec-content'), position={'x': 30, 'y': 420})
            page.keyboard.press('Escape')
            if not folded('코드'):
                sec('코드').click()   # 접어 둔 절도 인쇄되는지
            use_theme('dark')
            page.emulate_media(media='print')
            pr = page.evaluate('''() => ({
              toolbar: getComputedStyle(document.querySelector('#lec-toolbar')).display,
              folded: getComputedStyle(document.querySelector('#lec-view .lec-fold-hidden')).display,
              fg: getComputedStyle(document.querySelector('#lec-view p')).color,
              url: getComputedStyle(document.querySelector('#lec-view a.ext'), '::after').content })''')
            pdf = b'' if headed else page.pdf()   # PDF 만들기는 headless 에서만 된다
            page.emulate_media(media='screen')
            use_theme('default')
            sec('코드').click()
            check('인쇄 / PDF로 저장' in items and pr['toolbar'] == 'none' and pr['folded'] != 'none'
                  and pr['fg'] == 'rgb(17, 17, 17)' and 'https://' in pr['url'] and (headed or pdf.startswith(b'%PDF')),
                  f'인쇄: 문서 메뉴에 인쇄, 화면 UI 빼고 접은 절 펴서, 어두운 스타일도 검은 글자, 링크 주소 표시 ({pr}, PDF {len(pdf)}바이트)')

            print('[보안]')
            pid = page.evaluate("fetch('/api/state').then(r => r.json()).then(s => s.active)")
            status = lambda u: page.evaluate(f"fetch('{u}').then(r => r.status)")
            check(status(f'/doc/{pid}/README.md') == 200 and status(f'/doc/{pid}/.hidden-note.md') == 404, '숨김 문서 직접 요청 차단')
            check(status(f'/doc/{pid}/..%2F..%2Fetc%2Fpasswd') == 404, '프로젝트 밖 경로 차단')
            check(status('/doc/README.md') == 404 and status('/doc/0badc0de/README.md') == 404, '열려 있지 않은 프로젝트(탭) 주소는 404')
            not_images = [u for u, kind in outside if kind != 'image' and u not in blocked]
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
