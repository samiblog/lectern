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
    # html 문서의 인터넷 CSS 는 막혀야 한다 (그림만 허용). 요청이 나가면 아래 '새지 않음' 점검이 잡는다
    report = work / 'docs' / '04-HTML-보고서.html'
    report.write_text(report.read_text(encoding='utf-8').replace(
        '</head>', f'<link rel="stylesheet" href="{remote}leak-html.css"></head>'), encoding='utf-8')
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
            menu(page.locator('#lec-view .math-inline').first)
            tex = choose('LaTeX 복사')
            check(tex == r'x_t = \beta x_{t-1} + \varepsilon_t', f'문장 속 수식 우클릭: LaTeX 복사 ({tex!r})')
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
            check(len(themes) == 12 and groups == ['밝은 스타일', '어두운 스타일'], f'스타일 {len(themes)}종, 밝은·어두운 묶음 ({groups})')
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
              const rgb = (s) => s.match(/[\\d.]+/g).slice(0, 3).map(Number);
              const lum = (c) => c.map((x) => { x /= 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; })
                .reduce((a, x, i) => a + x * [0.2126, 0.7152, 0.0722][i], 0);
              const ratio = (a, b) => { const [x, y] = [lum(rgb(a)), lum(rgb(b))].sort((m, n) => n - m); return (x + 0.05) / (y + 0.05); };
              const bg = getComputedStyle(document.querySelector('#lec-content')).backgroundColor;
              const p = css('p').color, h = css('h2').color, th = css('thead th'), td = css('tbody td');
              return { text: ratio(p, bg), heading: ratio(h, bg), muted: ratio(css('.footnotes').color, bg), link: ratio(css('p a').color, bg),
                       headingDiffers: h !== p, headerDiffers: th.backgroundColor !== td.backgroundColor || th.color !== td.color };
            }'''
            if folded('표'):
                sec('표').click()   # 캡처에 표가 보이도록
            problems = []
            for theme in themes:
                if not use_theme(theme):
                    problems.append(f'{theme}: 스타일 파일이 적용되지 않음')
                    continue
                m = page.evaluate(measure)
                low = [k for k, need in (('text', 4.5), ('muted', 4.5), ('link', 4.5), ('heading', 3)) if m[k] < need]
                if low or not m['headingDiffers'] or not m['headerDiffers']:
                    problems.append(f"{theme}: 대비 부족 {low}, 제목 색 구분 {m['headingDiffers']}, 표 머리행 구분 {m['headerDiffers']}")
                shot(f'04-theme-{theme}')
            check(not problems, '모든 스타일: 글자 대비(WCAG 4.5:1), 제목 색·표 머리행 구분' + (f': {problems}' if problems else ''))
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
            check(any('HTML 보고서 예시' in t and 'HTML' in t.replace('HTML 보고서', '') for t in labels)
                  and page.locator('#lec-tree .row.dir', has_text='src').count() == 0,
                  'html 문서는 트리에 HTML 표시와 함께, src 폴더의 html(앱 소스)은 보이지 않음')
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
            page.locator('#lec-tree .row.file', has_text='스타일 없는 HTML').click()
            wait_until(page, f"{frame_js}?.contentDocument?.title === '스타일 없는 HTML'")
            themed = page.evaluate(f"""(() => {{ const d = {frame_js}.contentDocument;
              return d.body.classList.contains('md-body') && !!d.querySelector('link[href*="/static/themes/base.css"]'); }})()""")
            check(themed, '스타일이 없는 html 은 Lectern 스타일로')
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

            print('[설정과 마지막 위치]')
            page.keyboard.press('Control+Comma')
            dialog = page.locator('#lec-settings')
            boxes = page.evaluate("[...document.querySelectorAll('#lec-settings input[data-key]')].map(i => i.dataset.key + '=' + i.checked)")
            check(dialog.is_visible() and boxes == ['restore_last=true', 'expand_first_level=true', 'math=true', 'external_images=false'],
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
                pos = page.evaluate("fetch('/api/state').then(r => r.json()).then(s => s.position)")
                if pos['doc'] == 'docs/01-기능-점검.md' and pos['scroll'].get('docs/01-기능-점검.md') == 500:
                    remembered = True
                    break
                page.wait_for_timeout(200)
            page.reload()
            page.wait_for_selector('#lec-view h1:has-text("렌더링 기능 점검")')
            top = page.locator('#lec-content').evaluate('el => el.scrollTop')
            check(remembered and top == 500, f'다시 열면 마지막에 보던 문서와 스크롤 위치로 (scrollTop {top})')

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
            check(page.evaluate("fetch('/doc/.hidden-note.md').then(r => r.status)") == 404, '숨김 문서 직접 요청 차단')
            check(page.evaluate("fetch('/doc/..%2F..%2Fetc%2Fpasswd').then(r => r.status)") == 404, '프로젝트 밖 경로 차단')
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
