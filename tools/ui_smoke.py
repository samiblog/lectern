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
import re
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
    shutil.copytree(ROOT / 'tests' / 'fixture', work)   # 점검용 프로젝트 (사용자 예제 samples 와 따로 — D57)
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
    # 문서 외 파일: 목록에 나올 것(csv·실행 파일·루트의 pdf, 접힌 제외 폴더)과 나오지 않을 것(숨김)
    (work / 'data').mkdir()
    (work / 'data' / '표.csv').write_text('품목,값\n구리,1\n', encoding='utf-8')
    (work / 'data' / 'setup.exe').write_bytes(b'MZ')
    (work / 'data' / '.secret.txt').write_text('숨김', encoding='utf-8')
    (work / 'node_modules' / 'some-lib' / 'index.js').write_text('x', encoding='utf-8')
    (work / '첨부.pdf').write_bytes(b'%PDF-1.4')
    # 차트 예제의 CSV(docs/data)는 [차트] 점검 동안만 둔다 — '자료' 목록·거르기 점검은 위의 파일만 센다
    shutil.rmtree(work / 'docs' / 'data')
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
            row_tip = lambda box: page.locator(f'#lec-{box} .row[data-{"doc" if box == "tree" else "file"}="docs/01-기능-점검.md"]').get_attribute('title')
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
            check(page.locator('#lec-toc a[data-i]').count() == 7, '목차 7개')
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
            page.locator('#lec-toc a[data-i]', has_text='파일과 바깥 주소').click()
            check(sec('파일과-바깥-주소').is_visible() and not folded('링크'), '목차로 접힌 절 안의 제목에 가면 펴짐')
            sec('파일과-바깥-주소').click()
            sec('코드').dblclick(position={'x': 12, 'y': 16})   # 제목 글자 위
            selected = page.evaluate('getSelection().toString().trim()')
            check(not folded('코드') and selected == '코드', f'두 번 눌러 낱말을 고를 때는 접지 않음: {selected!r}')
            page.locator('#lec-view p', has_text='상대경로 그림은').click(position={'x': 5, 'y': 10})
            sec('그림').click(position={'x': 30, 'y': 16}, modifiers=['Shift'])   # 끌어서 고르면 click 이 오지 않는다 (Chromium)
            check(not folded('그림'), 'Shift+클릭으로 글자를 고를 때는 접지 않음')

            print('[목차의 구성 요소]')
            toc_rows = lambda: page.evaluate('''() => [...document.querySelectorAll('#lec-toc li')].map(li => li.classList.contains('part')
              ? [[...li.classList].find(c => c.startsWith('part-')).slice(5), li.querySelector('.tp-name').textContent, li.querySelector('.tp-label')?.textContent || '']
              : ['head', li.textContent.trim()])''')
            toc_buttons = lambda: page.evaluate('''[...document.querySelectorAll('#lec-toc .toc-parts button')]
              .map(b => b.textContent.trim() + (b.getAttribute('aria-pressed') === 'true' ? '' : ' 꺼짐'))''')
            rows = toc_rows()
            under = {}
            head = ''
            for r in rows:
                if r[0] == 'head':
                    head = r[1]
                else:
                    under.setdefault(head, []).append(f'{r[1]} · {r[2]}' if r[2] else r[1])
            check(under.get('표') == ['표 1 · 품목·1분기·2분기 · 6행 5열']
                  and [x.split(' · ')[1] for x in under.get('코드', [])] == ['python', 'powershell', 'json']
                  and [x.split(' · ')[0] for x in under.get('콜아웃', [])] == ['참고', '팁', '중요', '경고', '인용']
                  and under.get('그림') == ['그림 1 · 분기별 가격 범위']
                  and toc_buttons() == ['표 1', '그림 1', '박스글 5', '코드 3'],
                  f'목차의 제목 아래에 그 절의 표·코드·박스글·그림이 문서 순서로, 머리에 종류 버튼 ({under}, {toc_buttons()})')
            shot('02-toc-parts')
            sec('콜아웃').click()   # 접힌 절 안의 박스글로 가면 편다
            page.locator('#lec-toc li.part-box a', has_text='경고').click()
            warn = page.locator('#lec-view blockquote.alert-warning')
            went = wait_until(page, '''(() => { const el = document.querySelector('#lec-view blockquote.alert-warning');
              const r = el.getBoundingClientRect(), c = document.querySelector('#lec-content').getBoundingClientRect();
              return el.classList.contains('lec-target') && r.top >= c.top && r.bottom <= c.bottom; })()''')
            check(went and warn.is_visible() and not folded('콜아웃'), '목차의 구성 요소를 누르면 그 자리로 (접힌 절은 펴고), 잠깐 테두리로 표시')
            page.locator('#lec-toc li.part-table a').click()
            table_went = wait_until(page, "document.querySelector('#lec-view .table-wrap').classList.contains('lec-target')")
            check(table_went, '표를 누르면 표로 (표 상자에 표시)')
            page.locator('#lec-toc .toc-parts button', has_text='코드').click()
            no_code = page.locator('#lec-toc li.part-code').count() == 0 and toc_buttons()[3] == '코드 3 꺼짐'
            saved_hidden = wait_until(page, "fetch('/api/config').then(r => r.json()).then(c => JSON.stringify(c.toc_hidden_parts) === '[\"code\"]')")
            page.locator('#lec-tree .row.file', has_text='수식과 달러').click()
            page.wait_for_selector('#lec-view h1:has-text("수식과 달러")')
            math = [r for r in toc_rows() if r[0] == 'math']
            maths_btn = toc_buttons()
            page.locator('#lec-tree .row.file', has_text='렌더링 기능 점검').click()
            page.wait_for_selector('#lec-view h1:has-text("렌더링 기능 점검")')
            still_off = page.locator('#lec-toc li.part-code').count() == 0
            page.locator('#lec-toc .toc-parts button', has_text='코드').click()
            back_on = page.locator('#lec-toc li.part-code').count() == 3 and wait_until(page, "fetch('/api/config').then(r => r.json()).then(c => c.toc_hidden_parts.length === 0)")
            check(no_code and saved_hidden and still_off and back_on,
                  '종류 버튼으로 그 종류를 목차에서 감추고 보이기 — 다른 문서·다시 그려도 그대로 (설정 toc_hidden_parts)')
            check(len(math) >= 3 and math[0][1] == '수식 1' and '\\frac' in ''.join(m[2] for m in math) and any(b.startswith('수식') for b in maths_btn),
                  f'수식 블록도 목차에 (TeX 원문으로): {math[:3]}')

            print('[모아 보기]')
            pv = lambda: page.evaluate('''() => ({ kinds: Object.fromEntries([...document.querySelectorAll('#lec-parts-kinds button')]
                .map(b => [b.dataset.kind, +b.querySelector('.n').textContent])),
              active: document.querySelector('#lec-parts-kinds button.active')?.dataset.kind,
              scope: document.querySelector('#lec-parts-scope').textContent, info: document.querySelector('#lec-parts-info').textContent,
              groups: [...document.querySelectorAll('#lec-parts-list .pt-doc')].map(d => d.querySelector('.label').textContent),
              items: [...document.querySelectorAll('#lec-parts-list .pt-item')].map(r => [r.closest('#lec-parts-list') && r.dataset.doc,
                r.querySelector('.pt-name').textContent, r.querySelector('.pt-label')?.textContent || '', r.querySelector('.pt-sec')?.textContent || '']),
              thumbs: document.querySelectorAll('#lec-parts-list .pt-thumb').length,
              more: [...document.querySelectorAll('#lec-parts-list .pt-more')].map(m => m.textContent) })''')
            read_done = lambda: wait_until(page, "!document.querySelector('#lec-parts-info').textContent.includes('읽는 중') && document.querySelector('#lec-parts-info').textContent !== ''", 15000)
            page.click('.side-tabs button[data-tab="parts"]')
            read_done()
            p1 = pv()
            mine = [i for i in p1['items'] if i[0] == 'docs/01-기능-점검.md']
            check(not page.locator('#lec-parts').is_hidden() and p1['active'] == 'table' and p1['scope'] == 'samples 전체'
                  and ['docs/01-기능-점검.md', '표 1', '품목·1분기·2분기 · 6행 5열', '표'] in mine
                  and p1['kinds']['table'] == len(p1['items']) and all(p1['kinds'][k] > 0 for k in ('figure', 'box', 'diagram', 'code', 'math')),
                  f"사이드바 '모아 보기' 탭: 프로젝트의 표를 문서별로 (이름·크기·절), 종류마다 개수 ({p1['kinds']}, {mine})")
            page.click('#lec-parts-kinds button[data-kind="box"]')
            boxes = [i[1] for i in pv()['items'] if i[0] == 'docs/01-기능-점검.md']
            page.fill('#lec-parts-filter', '경고 프로젝트')
            wait_until(page, "document.querySelectorAll('#lec-parts-list .pt-item').length === 1")
            filtered = pv()['items']
            page.press('#lec-parts-filter', 'Enter')
            went = wait_until(page, "document.querySelector('#lec-view blockquote.alert-warning')?.classList.contains('lec-target')", 5000)
            check(boxes == ['참고', '팁', '중요', '경고', '인용'] and len(filtered) == 1 and filtered[0][1] == '경고' and went,
                  f'박스글 모아 보기, 거르기, Enter 로 그 문서의 그 자리로 (목차와 같은 번호로 찾아감) ({boxes}, {filtered})')
            page.fill('#lec-parts-filter', '')
            page.click('#lec-parts-kinds button[data-kind="figure"]')
            loaded = wait_until(page, "[...document.querySelectorAll('#lec-parts-list .pt-pic img')].some(i => i.complete && i.naturalWidth > 0)", 8000)
            p2 = pv()
            shot('12-parts-figures')
            check(p2['thumbs'] > 0 and loaded and any(m.startswith('+') for m in p2['more']) and p2['kinds']['figure'] > p2['thumbs'],
                  f"그림은 작은 그림 격자, 같은 그림은 한 번만 ('+N곳') ({p2['thumbs']}개 / {p2['kinds']['figure']}곳, {p2['more']})")
            page.click('.side-tabs button[data-tab="files"]')
            page.locator('#lec-tree .row.dir', has_text='docs').first.click()
            page.wait_for_selector('#lec-view .ov-parts button[data-parts="diagram"]')
            page.click('#lec-view .ov-parts button[data-parts="diagram"]')
            read_done()
            p3 = pv()
            check(p3['scope'] == 'docs 폴더' and p3['active'] == 'diagram'
                  and [i[1] for i in p3['items'] if i[0] == 'docs/03-다이어그램.md'] == ['다이어그램 1', '다이어그램 2', '다이어그램 3']
                  and any(i[0] == 'docs/06-차트.md' for i in p3['items']) and all(i[0].startswith('docs/') for i in p3['items']),
                  f"폴더 개요의 '모아 보기' 버튼: 그 폴더(하위 포함)의 그 종류 ({p3['scope']}, {p3['items']})")
            page.click('.side-tabs button[data-tab="files"]')
            page.locator('#lec-tree .row.dir', has_text='plans').first.click(button='right')
            page.locator('#lec-menu button', has_text='이 폴더의 표·그림 등 모아 보기').click()
            read_done()
            p4 = pv()
            check(p4['scope'] == 'plans 폴더' and p4['kinds'][p4['active']] > 0 and p4['kinds']['diagram'] == 0 and all(i[0].startswith('plans/') for i in p4['items']),
                  f"트리 폴더 우클릭 '이 폴더의 표·그림 등 모아 보기' — 그 폴더에 있는 종류로 ({p4['scope']}, {p4['active']}, {p4['kinds']})")
            page.click('#lec-parts-all')
            read_done()
            before_n = pv()['kinds']['table']
            (work / 'docs' / '96-새-표.md').write_text('# 새 표\n\n| 가 | 나 |\n|---|---|\n| 1 | 2 |\n', encoding='utf-8')
            grew = wait_until(page, f"+document.querySelector('#lec-parts-kinds button[data-kind=\"table\"] .n')?.textContent === {before_n + 1}", 10000)
            (work / 'docs' / '96-새-표.md').unlink()
            gone_back = wait_until(page, f"+document.querySelector('#lec-parts-kinds button[data-kind=\"table\"] .n')?.textContent === {before_n}", 10000)
            check(pv()['scope'] == 'samples 전체' and grew and gone_back, f"'전체'로 프로젝트 전체, 문서가 생기거나 지워지면 바로 반영 (표 {before_n} → +1 → {before_n})")
            page.click('.side-tabs button[data-tab="files"]')
            page.locator('#lec-tree .row.file', has_text='렌더링 기능 점검').click()
            page.wait_for_selector('#lec-view h1:has-text("렌더링 기능 점검")')

            print('[글자 크기와 장 하이라이트]')
            size = lambda: page.evaluate("parseFloat(getComputedStyle(document.querySelector('#lec-view p')).fontSize)")
            base_size = size()
            # 100% 의 글자는 스타일의 --md-size 보다 한 단계(×1.1) 크다 (D47)
            md_size = page.evaluate("parseFloat(getComputedStyle(document.querySelector('#lec-view')).getPropertyValue('--md-size'))")
            check(abs(base_size - md_size * 1.1) < 0.1, f'100% 글자는 스타일 기본 크기의 한 단계 위 ({md_size}px × 1.1 = {base_size}px)')
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
            page.locator('#lec-toc a[data-i]', has_text='링크').first.click()
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
            check(page.locator('#lec-view .diagram-error').count() == 1, '문법 오류 블록은 원문 표시')
            head = menu(page.locator('pre.mermaid svg p').first).split('\n')[0]   # 그림 속 글자(<p>)를 눌러도 다이어그램
            fence = choose('원문 복사')
            check(head == '다이어그램' and fence.startswith('```mermaid') and fence.endswith('```'),
                  f'다이어그램 우클릭: 원문 복사 ({head!r}, {fence[:12]!r})')
            menu(page.locator('pre.mermaid svg').first)
            choose('그림 복사')
            check(clip_types() == ['image/png'], f'다이어그램 우클릭: 그림 복사(PNG) ({clip_types()})')
            shot('03-mermaid')

            print('[차트]')   # D56 — ```vega-lite·```echarts·```dot 를 SVG 로 (charts.js)
            shutil.copytree(ROOT / 'tests' / 'fixture' / 'docs' / 'data', work / 'docs' / 'data')   # 예제가 읽는 CSV (점검 뒤 지운다)
            page.locator('#lec-tree .row.file[data-doc="docs/06-차트.md"]').click()
            page.wait_for_selector('#lec-view h1:has-text("차트와 그래프")')
            drawn = wait_until(page, "document.querySelectorAll('#lec-view pre.lec-chart.chart-ok').length === 11", 30000)
            # 문서 폭을 따르는 것(ECharts·Plotly·width "container")은 목차가 나온 뒤의 폭으로 다시 그린다 — 줄여 보이지 않게
            fit = wait_until(page, """[...document.querySelectorAll('#lec-view pre.lec-chart.chart-ok[data-chart="echarts"], #lec-view pre.lec-chart.chart-ok[data-chart="plotly"]')]
              .every(p => Math.abs(parseFloat(p.querySelector('svg').getAttribute('width')) - p.clientWidth) <= 16)""", 5000)
            charts = page.evaluate("""() => ({
              kinds: [...document.querySelectorAll('#lec-view pre.lec-chart.chart-ok')].map(p => p.dataset.chart).join(','),
              err: [...document.querySelectorAll('#lec-view .diagram-error > p')].map(p => p.textContent),
              csv: Math.max(0, ...[...document.querySelectorAll('#lec-view pre.lec-chart')[2]?.querySelectorAll('svg path[d]') || []].map(p => p.getAttribute('d').length)),
              font: getComputedStyle(document.querySelector('#lec-view pre.lec-chart[data-chart="echarts"] svg text')).fontFamily,
              toc: [...document.querySelectorAll('#lec-toc a[data-c]')].map(a => a.textContent).join(' | ') })""")
            check(drawn and fit and charts['kinds'] == 'vega-lite,vega-lite,vega-lite,echarts,echarts,echarts,plotly,plotly,plotly,dot,dot'
                  and len(charts['err']) == 1 and '함수는 쓸 수 없습니다' in charts['err'][0] and charts['csv'] > 200
                  and 'Segoe UI' in charts['font'] and 'Vega-Lite · 분기별 구리 가격과 거래소 재고' in charts['toc']
                  and 'Graphviz · Lectern' in charts['toc'] and 'ECharts · 용도별 소비 비중' in charts['toc'] and 'Plotly · 월별 생산과 가동률' in charts['toc'],
                  f"차트: Vega-Lite 3(프로젝트의 CSV 포함)·ECharts 3(따옴표 없는 키도)·Plotly 3·Graphviz 2, 문서 폭으로 다시 그림, 함수는 원문과 까닭, 목차에 종류·제목 ({charts['kinds']}, {charts['err']}, {charts['font'][:20]})")
            head = menu(page.locator('#lec-view pre.lec-chart[data-chart="dot"] svg').first).split('\n')[0]
            fence = choose('원문 복사')
            menu(page.locator('#lec-view pre.lec-chart[data-chart="vega-lite"] svg').first)
            choose('그림 복사')
            png = clip_types()
            page.locator('#lec-view pre.lec-chart[data-chart="echarts"]').first.click()
            big = wait_until(page, "!document.querySelector('#lec-lightbox').hidden && !!document.querySelector('#lec-lightbox svg')", 3000)
            page.keyboard.press('Escape')
            check(head == '다이어그램' and fence.startswith('```dot') and png == ['image/png'] and big,
                  f"차트 우클릭: 원문 복사·그림 복사(PNG), 누르면 크게 ({head!r}, {fence[:8]!r}, {png})")
            shot('03-charts')
            # 차트가 인터넷에 닿거나 앱 창을 떠나게 하는 길: 인터넷 데이터, 링크(Vega href·Graphviz URL), 인터넷 그림(ECharts graphic)
            bad = work / 'docs' / '97-차트-막기.md'
            bad.write_text('# 차트 막기\n\n```vega-lite\n{"data": {"url": "https://example.com/x.csv"}, "mark": "bar",'
                           ' "encoding": {"x": {"field": "a", "type": "nominal"}}}\n```\n\n'
                           '```vega-lite\n{"data": {"url": "data/없는-파일.csv"}, "mark": "bar", "encoding": {"x": {"field": "a", "type": "nominal"}}}\n```\n\n'
                           '```vega-lite\n{"data": {"values": [{"a": "링크", "b": 1, "u": "https://example.com/"}]}, "mark": "bar",'
                           ' "encoding": {"x": {"field": "a", "type": "nominal"}, "y": {"field": "b", "type": "quantitative"}, "href": {"field": "u"}}}\n```\n\n'
                           '```echarts\n{"graphic": [{"type": "image", "style": {"image": "https://example.com/x.png", "width": 40, "height": 40}}],'
                           ' "xAxis": {"type": "category", "data": ["a"]}, "yAxis": {}, "series": [{"type": "bar", "data": [1]}]}\n```\n\n'
                           '```dot\ndigraph { a [URL="https://example.com/", label="링크"]; a -> b; }\n```\n\n'
                           '```plotly\n{"data": [{"type": "bar", "x": ["a"], "y": [1]}], "layout": {"images": [{"source": "https://example.com/plotly.png",'
                           ' "x": 0, "y": 1, "sizex": 0.3, "sizey": 0.3, "xref": "paper", "yref": "paper"}],'
                           ' "annotations": [{"text": "<a href=\\"https://example.com/\\">링크</a>", "x": 0, "y": 1, "xref": "paper", "yref": "paper", "showarrow": false}]}}\n```\n\n'
                           '```plotly\n{"data": [{"type": "scattergeo", "lon": [127], "lat": [37]}]}\n```\n', encoding='utf-8')
            page.wait_for_selector('#lec-tree .row.file[data-doc="docs/97-차트-막기.md"]', timeout=8000)
            page.locator('#lec-tree .row.file[data-doc="docs/97-차트-막기.md"]').click()
            page.wait_for_selector('#lec-view h1:has-text("차트 막기")')
            wait_until(page, "document.querySelectorAll('#lec-view pre.lec-chart.chart-ok, #lec-view .diagram-error').length === 7", 30000)
            guard = page.evaluate("""() => ({
              err: [...document.querySelectorAll('#lec-view .diagram-error > p')].map(p => p.textContent),
              ok: document.querySelectorAll('#lec-view pre.lec-chart.chart-ok').length,
              links: document.querySelectorAll('#lec-view pre.lec-chart a').length,
              remote: [...document.querySelectorAll('#lec-view pre.lec-chart image')].map(i => i.getAttribute('href') || i.getAttribute('xlink:href') || '')
                .filter(h => /^(https?:)?\\/\\//.test(h)).length })""")
            bad.unlink()
            shutil.rmtree(work / 'docs' / 'data')
            asked = [u for u, _ in outside if 'example.com' in u]   # 그리는 동안에도 인터넷에 닿지 않아야 한다 (Plotly 는 배경 그림을 불러온다)
            check(len(guard['err']) == 3 and '프로젝트 안의 파일만' in guard['err'][0] and '데이터 파일을 읽지 못했습니다' in guard['err'][1]
                  and '지도 차트' in guard['err'][2] and guard['ok'] == 4 and not guard['links'] and not guard['remote'] and not asked,
                  f"차트는 인터넷 데이터를 읽지 않고(없는 파일도 빈 그림 대신 까닭, Plotly 지도는 그리지 않음), 그림 속 링크는 풀고, 인터넷 그림은 부르지도 넣지도 않음 ({guard}, {asked})")
            page.locator('#lec-tree .row.file', has_text='다이어그램').click()   # 아래 스타일 점검은 Mermaid 문서에서
            page.wait_for_selector('pre.mermaid svg', timeout=20000)

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
            # 내 스타일 (D53): 설정 폴더의 styles\*.css — 저장하면 목록 맨 아래 '내 스타일'에, 고르면 바탕 스타일 위에, 고치면 바로 다시
            page.locator('#lec-tree .row.file', has_text='렌더링 기능 점검').click()   # 다시 불러온 뒤 폴더 개요일 수 있다 — 문서에서 본다
            page.wait_for_selector('#lec-view.md-body h1:has-text("렌더링 기능 점검")')
            mine = tmp / 'config' / 'styles'
            mine.mkdir(parents=True, exist_ok=True)
            css = mine / '점검.css'
            css.write_text('/* lectern-style\n   name: 점검 스타일\n   base: report\n*/\n'
                           ':root { --md-heading: rgb(170, 20, 20); }\n.md-body h1 { letter-spacing: 3px; }\n'
                           'body { background-image: url(https://example.invalid/leak.png); }\n', encoding='utf-8')
            listed = wait_until(page, "!!document.querySelector('#lec-theme optgroup:last-of-type option[value=\"user:점검\"]')", 8000)
            group = page.evaluate("document.querySelector('#lec-theme optgroup:last-of-type').label")
            page.select_option('#lec-theme', 'user:점검')
            applied = wait_until(page, "getComputedStyle(document.querySelector('#lec-view h1')).color === 'rgb(170, 20, 20)'", 5000)
            base_css = page.evaluate("document.querySelector('#lec-theme-css').getAttribute('href')")
            spacing = page.evaluate("getComputedStyle(document.querySelector('#lec-view h1')).letterSpacing")
            css.write_text(css.read_text(encoding='utf-8').replace('170, 20, 20', '20, 120, 20'), encoding='utf-8')
            live = wait_until(page, "getComputedStyle(document.querySelector('#lec-view h1')).color === 'rgb(20, 120, 20)'", 8000)
            page.click('#lec-btn-settings')
            info = page.inner_text('#lec-mystyles-info')
            page.evaluate("document.querySelector('#lec-toast').textContent = ''")
            page.click('#lec-mystyles-prompt')
            wait_until(page, "document.querySelector('#lec-toast').textContent.includes('복사')")
            prompt = page.evaluate('navigator.clipboard.readText()')
            page.click('#lec-settings-close')
            check(listed and group == '내 스타일' and applied and base_css.endswith('/report.css') and spacing == '3px' and live
                  and '내 스타일 1개' in info and str(mine) in prompt and 'styles.md' in prompt,
                  f"내 스타일: 설정 폴더 styles 에 저장하면 목록 맨 아래 '내 스타일'에, 고르면 바탕 스타일(report) 위에, 고치면 바로 다시 입힘, 설정 창의 요청 글 ({group}, {base_css}, {info[:12]})")
            css.unlink()
            gone = wait_until(page, "!document.querySelector('#lec-theme option[value=\"user:점검\"]')", 8000)
            check(gone and page.evaluate("document.documentElement.dataset.theme") == 'default' and not page.evaluate("document.querySelector('#lec-user-css').getAttribute('href')"),
                  '내 스타일 파일을 지우면 목록에서 빠지고 기본 스타일로')
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
            page.keyboard.press('Control+p')
            page.fill('#lec-palette-input', 'example')
            code_item = wait_until(page, "!!document.querySelector('#lec-palette-list li.code')", 5000)
            pal = page.evaluate("[...document.querySelectorAll('#lec-palette-list li')].map(li => (li.classList.contains('code') ? 'code:' : 'doc:') + li.querySelector('.p').textContent)")
            page.locator('#lec-palette-list li.code', has_text='code/example.py').click()
            pal_code = wait_until(page, "document.querySelector('#lec-view.code-view .cv-title')?.textContent === 'example.py'", 5000)
            check(code_item and 'code:code/example.py' in pal and pal_code,
                  f'Ctrl+P 에 코드도 — 맞는 문서 먼저, 그다음 코드(아이콘), 고르면 코드 화면 ({pal[:5]})')
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
            def cfg_is(key, want):
                for _ in range(20):
                    if page.evaluate(f"fetch('/api/config').then(r => r.json()).then(c => c.{key})") == want:
                        return True
                    page.wait_for_timeout(100)
                return False

            sr = lambda: page.evaluate('''() => ({ info: document.querySelector('#lec-search-info').textContent,
              group: !!document.querySelector('#lec-search-results .sr-group'),
              docs: [...document.querySelectorAll('#lec-search-results .sr-doc')].map(d => (d.dataset.kind || 'doc') + ':' + d.dataset.doc) })''')
            page.fill('#lec-search-input', 'moving_average')
            wait_until(page, "!!document.querySelector('#lec-search-results .sr-doc[data-kind=\"code\"]')", 5000)
            s1 = sr()
            check(s1['group'] and s1['docs'][0].startswith('doc:') and 'code:code/example.py' in s1['docs'] and '코드' in s1['info'] and '문서' in s1['info'],
                  f"전체 검색에 코드도 — 문서 결과 먼저, 그 아래 '코드' 묶음 ({s1})")
            page.locator('#lec-search-results .sr-hit[data-kind="code"]').first.click()
            to_code = wait_until(page, "document.querySelector('#lec-view.code-view .lec-target')?.dataset.line === '8'", 5000)
            code_find = page.evaluate("document.querySelector('#lec-findbar').hidden ? null : document.querySelector('#lec-find-count').textContent")
            page.keyboard.press('Escape')
            check(to_code and code_find and code_find.startswith('1/'), f'코드 결과를 누르면 코드 화면의 그 줄로, 검색어 표시 ({code_find})')
            page.click('#lec-search-docs')
            only_code = wait_until(page, "[...document.querySelectorAll('#lec-search-results .sr-doc')].every(d => d.dataset.kind === 'code')"
                                   " && !document.querySelector('#lec-search-results .sr-group')", 5000)
            saved_docs = cfg_is('search_docs', False)
            page.click('#lec-search-code')
            page.click('#lec-search-others')
            none = wait_until(page, "document.querySelector('#lec-search-info').textContent.includes('고르세요')", 3000)
            page.click('#lec-search-docs')
            page.click('#lec-search-code')
            page.click('#lec-search-others')
            back_both = wait_until(page, "!!document.querySelector('#lec-search-results .sr-group')", 5000)
            check(only_code and saved_docs and none and back_both and cfg_is('search_code', True) and cfg_is('search_docs', True) and cfg_is('search_others', True),
                  "'문서'·'코드'·'자료' 버튼으로 찾을 곳을 고름 (설정에 저장), 모두 끄면 고르라고 알림")
            page.fill('#lec-search-input', '')
            page.locator('.side-tabs button[data-tab="files"]').click()
            page.locator('#lec-tree .row.file[data-doc="docs/01-기능-점검.md"]').click()
            page.wait_for_selector('#lec-view h1:has-text("렌더링 기능 점검")')
            opened_code = page.locator('#lec-code-list .row[data-path="code"][aria-expanded="true"] [data-toggle]')
            if opened_code.count():   # 코드 화면이 '코드' 목록에서 펼친 폴더를 접어 둔다 (아래 파일 목록 점검은 접힌 채로 시작)
                opened_code.click()

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
            wait_until(page, "document.querySelectorAll('#lec-code-list .row').length > 0")
            boxes = [page.locator(sel).bounding_box() for sel in ('#lec-docs', '#lec-code-split', '#lec-code', '#lec-others-split', '#lec-others')]
            count = page.inner_text('#lec-others-count')
            clabels = lambda: page.locator('#lec-code-list .row .label').all_inner_texts()
            ccount = page.inner_text('#lec-code-count')
            heads = [page.inner_text(f'#lec-{h}-head').split()[0] for h in ('docs', 'code', 'others')]
            docs_n = page.inner_text('#lec-docs-count')
            check(olabels() == ['data', 'empty-folder', 'node_modules', 'research', '첨부.pdf'] and clabels() == ['code', 'src']
                  and int(count) + int(ccount) == 7 and heads == ['문서', '코드', '자료'] and int(docs_n) == page.evaluate('document.querySelectorAll("#lec-tree .row.file").length')
                  and all(boxes[i]['y'] + boxes[i]['height'] <= boxes[i + 1]['y'] + 1 for i in range(4)),
                  f"위에서부터 '문서'·'코드'·'자료' 세 묶음 — 자료는 문서·코드가 아닌 것과 제외 폴더, 코드는 소스·웹·설정, 폴더 먼저·접힌 채로, 숨김은 없음 "
                  f"({olabels()}, {clabels()}, 자료 {count}·코드 {ccount}·문서 {docs_n})")
            orow('data').locator('[data-toggle]').click()
            page.wait_for_selector(f'{olist} .row[data-path="data/표.csv"]')
            in_data = olabels()[1:3]
            # 이름 앞의 종류 아이콘: 문서(md·html)와 폴더, 최근 변경, 파일 목록
            icon_of = lambda sel: page.evaluate(f"document.querySelector('{sel} .ficon use')?.getAttribute('href') || null")
            icons = [icon_of(sel) for sel in ('#lec-tree .row[data-doc="docs/01-기능-점검.md"]', '#lec-tree .row[data-doc="docs/04-HTML-보고서.html"]',
                                              '#lec-tree .row.dir[data-dir="docs"]', '#lec-recent .row[data-file="docs/01-기능-점검.md"]',
                                              f'{olist} .row[data-path="data/표.csv"]', f'{olist} .row[data-path="data/setup.exe"]',
                                              f'{olist} .row[data-path="첨부.pdf"]', f'{olist} .row[data-path="data"]')]
            head = page.inner_text('#lec-others-head')
            check(icons == ['#i-md', '#i-html', '#i-folder', '#i-md', '#i-table', '#i-app', '#i-text', '#i-folder'] and head.startswith('자료'),
                  f"파일 이름 앞에 종류 아이콘 — 문서(md·html)·폴더·최근 변경·자료 목록, 머리줄은 '자료' ({icons}, {head!r})")
            # 제외 폴더 (D49): 흐린 접힌 폴더 — 펼칠 때 안을 한 단계씩 읽고, 안의 것은 종류를 나누지 않고 모두 여기 (개수에는 넣지 않는다)
            nm = orow('node_modules')
            faded = float(page.evaluate(f"getComputedStyle(document.querySelector('{olist} .row[data-path=\"node_modules\"] .label')).opacity"))
            nm_tip = nm.get_attribute('title') or ''
            with page.expect_request('**/api/others/dir*'):
                nm.locator('[data-toggle]').click()
            page.wait_for_selector(f'{olist} .row[data-path="node_modules/some-lib"]')
            orow('node_modules/some-lib').locator('[data-toggle]').click()
            page.wait_for_selector(f'{olist} .row[data-path="node_modules/some-lib/index.js"]')
            lib_js = orow('node_modules/some-lib/index.js')
            inner = 'excluded' in (lib_js.get_attribute('class') or '')
            in_code = page.locator('#lec-code-list .row[data-path^="node_modules"]').count()
            same_count = page.inner_text('#lec-others-count') == count
            nm_menu = menu(nm)
            page.keyboard.press('Escape')
            lib_js.click()   # 코드는 한 번 누르면 읽기 화면 (제외 폴더 안이어도)
            code_view = wait_until(page, "document.querySelector('#lec-st-path').textContent === 'node_modules/some-lib/index.js'"
                                   " && !!document.querySelector('#lec-view .cv-line')")
            nm.locator('[data-toggle]').click()   # 접으면 읽어 둔 것을 버리고, 다시 펼치면 새로 읽는다 (안에서 펼쳐 둔 폴더도)
            (work / 'node_modules' / 'new-lib').mkdir()
            with page.expect_request('**/api/others/dir*'):
                nm.locator('[data-toggle]').click()
            reread = wait_until(page, f"!!document.querySelector('{olist} .row[data-path=\"node_modules/new-lib\"]')"
                                f" && !!document.querySelector('{olist} .row[data-path=\"node_modules/some-lib/index.js\"]')")
            nm.locator('[data-toggle]').click()
            (work / 'node_modules' / 'new-lib').rmdir()
            check(faded < 1 and '제외 폴더' in nm_tip and inner and in_code == 0 and same_count and '제외 폴더' in nm_menu and code_view and reread,
                  f"제외 폴더(node_modules)는 '자료'에 흐린 접힌 폴더 — 펼칠 때 읽고, 안의 코드도 여기서 읽기 화면으로, 개수에는 넣지 않음, "
                  f"접었다 펼치면 새로 읽음 (흐림 {faded}, 자료 {page.inner_text('#lec-others-count')})")
            (work / 'dist').mkdir()
            dist_came = wait_until(page, f"!!document.querySelector('{olist} .row.excluded[data-path=\"dist\"]')", 8000)
            if dist_came:
                orow('dist').locator('[data-toggle]').click()
            empty_note = wait_until(page, f"document.querySelector('{olist} .side-note')?.textContent === '빈 폴더'")
            (work / 'dist').rmdir()
            dist_gone = wait_until(page, f"!document.querySelector('{olist} .row[data-path=\"dist\"]')", 8000)
            check(dist_came and empty_note and dist_gone, "제외 폴더가 생기면(비어 있어도) '자료'에 바로 나오고, 지우면 사라짐")
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
            page.keyboard.press('r')           # 그 글자로 시작하는 다음 행 (같은 글자를 거듭 치면 그다음 것)
            page.keyboard.press('r')
            typed = picked()
            check(up == 'data/setup.exe' and body['path'] == 'data/setup.exe' and parent == 'data' and folded_data
                  and down == 'empty-folder' and opened_dir and typed == 'research',
                  f'키보드: ↑↓ 로 고르고 Enter 로 열기, ← 부모·접기, → 펼치기, 글자로 찾아가기 ({up}, {parent}, {down}, {typed})')
            page.fill('#lec-filter', 'csv')
            flat = page.evaluate(f"""[...document.querySelectorAll('{olist} .row')]
                .map(r => r.querySelector('.label').textContent + '|' + (r.querySelector('.sub')?.textContent || ''))""")
            no_docs = '일치하는 문서가 없습니다' in page.inner_text('#lec-tree')
            page.locator('#lec-filter').press('Escape')
            check(flat == ['표.csv|data'] and no_docs and olabels()[0] == 'data',
                  f'사이드바 거르기는 파일 목록에도 — 거른 파일을 폴더와 함께 평평하게, Esc 로 되돌림 ({flat})')
            later_file = work / '나중-파일.txt'
            later_code = work / '나중-코드.py'
            later_file.write_text('x', encoding='utf-8')
            later_code.write_text('x = 1', encoding='utf-8')
            appeared = wait_until(page, "!!document.querySelector('#lec-others-list .row[data-path=\"나중-파일.txt\"]')"
                                  " && !!document.querySelector('#lec-code-list .row[data-path=\"나중-코드.py\"]')", 8000)
            counts_after = (page.inner_text('#lec-others-count'), page.inner_text('#lec-code-count'))
            later_file.unlink()
            later_code.unlink()
            gone = wait_until(page, "!document.querySelector('#lec-others-list .row[data-path=\"나중-파일.txt\"]')"
                              " && !document.querySelector('#lec-code-list .row[data-path=\"나중-코드.py\"]')", 8000)
            check(appeared and counts_after == (str(int(count) + 1), str(int(ccount) + 1)) and gone,
                  f'파일·코드가 생기거나 지워지면 그 목록에 바로 반영 ({counts_after})')
            code_body = opens(lambda: page.locator('#lec-code-list .row[data-path="code"]').locator('[data-toggle]').click()
                              or page.locator('#lec-code-list .row[data-path="code/example.py"]').dblclick())
            code_items = menu(page.locator('#lec-code-list .row[data-path="code/example.py"]'))
            page.keyboard.press('Escape')
            check(code_body['path'] == 'code/example.py' and '읽기 화면에서 보기' in code_items and '편집기로' in code_items,
                  f"'코드' 목록도 탐색기처럼 — 두 번 누르면 편집기, 우클릭 메뉴 ({code_body}, {code_items[:80]!r})")
            page.locator('#lec-tree .row.file[data-doc="docs/01-기능-점검.md"]').click()   # 한 번 누를 때 연 코드 화면에서 문서로
            page.wait_for_selector('#lec-view h1:has-text("렌더링 기능 점검")')
            tree_h = page.locator('#lec-tree').bounding_box()['height']
            page.click('#lec-others-head')
            wait_until(page, "document.querySelector('#lec-others').classList.contains('closed')")
            hidden_list = page.evaluate("getComputedStyle(document.querySelector('#lec-others-list')).display") == 'none'
            taller = page.locator('#lec-tree').bounding_box()['height'] > tree_h + 100
            saved_off = config_is('others_visible', False)
            page.click('#lec-others-head')
            check(hidden_list and taller and saved_off and wait_until(page, "!document.querySelector('#lec-others').classList.contains('closed')"),
                  '머리줄을 누르면 접히고 문서 트리가 그만큼 길어짐 (설정에 저장), 다시 누르면 펼침')
            page.click('#lec-docs-head')
            docs_closed = wait_until(page, "document.querySelector('#lec-docs').classList.contains('closed') && document.querySelector('#lec-code').classList.contains('grow')")
            tree_hidden = page.evaluate("getComputedStyle(document.querySelector('#lec-tree')).display") == 'none'
            saved_docs = config_is('docs_visible', False)
            page.click('#lec-docs-head')
            docs_back = wait_until(page, "document.querySelector('#lec-docs').classList.contains('grow') && getComputedStyle(document.querySelector('#lec-tree')).display !== 'none'")
            check(docs_closed and tree_hidden and saved_docs and docs_back,
                  "'문서' 머리줄로 문서 트리도 접음 — 접으면 바로 아래 '코드'가 남은 높이를 가짐, 다시 누르면 펼침")
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
            split = page.locator('#lec-code-split').bounding_box()
            c0 = page.locator('#lec-code').bounding_box()['height']
            page.mouse.move(split['x'] + 40, split['y'] + 4)
            page.mouse.down()
            page.mouse.move(split['x'] + 40, split['y'] - 56, steps=5)
            page.mouse.up()
            c1 = page.locator('#lec-code').bounding_box()['height']
            saved_c = config_is('code_height', round(c1))
            page.locator('#lec-code-split').dblclick()
            check(abs(h1 - h0 - 100) <= 4 and saved_h and abs(h2 - h0) <= 2 and config_is('others_height', None)
                  and abs(c1 - c0 - 60) <= 4 and saved_c and config_is('code_height', None),
                  f'분리선을 끌어 코드·자료 높이 조절·저장, 두 번 누르면 기본 높이 (자료 {h0:.0f} → {h1:.0f} → {h2:.0f}, 코드 {c0:.0f} → {c1:.0f})')
            shot('05-others')
            print('[폴더 보기]')
            page.click('#lec-btn-view')
            wait_until(page, "document.querySelector('#lec-files').classList.contains('folder-view')")
            wait_until(page, f"!!document.querySelector('{olist} .row.root')")
            hidden = page.evaluate("['#lec-docs', '#lec-others-split', '#lec-others-head', '#lec-code'].map(s => getComputedStyle(document.querySelector(s)).display)")
            active_row = lambda: page.evaluate(f"document.querySelector('{olist} .row.active')?.dataset.path ?? null")
            revealed = active_row()
            research = orow('research')
            if research.get_attribute('aria-expanded') != 'true':
                research.locator('[data-toggle]').click()
            mixed = [orow('research/images').count(), orow('research/구리-시장-동향.md').count(),
                     icon_of(f'{olist} .row[data-path="research/구리-시장-동향.md"]')]
            check(hidden == ['none'] * 4 and revealed == 'docs/01-기능-점검.md' and mixed == [1, 1, '#i-md']
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
            check(back_kind and page.is_visible('#lec-tree') and page.is_visible('#lec-others-head') and olabels()[0] == 'data' and page.is_visible('#lec-code-head')
                  and config_is('files_view', 'kind'),
                  "다시 누르면 종류별 보기 ('문서'·'코드'·'자료' 묶음)")

            print('[코드·자료의 최근 변경·검색·파일 종류]')
            page.locator('.side-tabs button[data-tab="recent"]').click()
            rrow = lambda path: page.locator(f'#lec-recent .row[data-file="{path}"]')
            got_files = wait_until(page, "!!document.querySelector('#lec-recent .row[data-file=\"첨부.pdf\"]')"
                                   " && !!document.querySelector('#lec-recent .row[data-file=\"code/example.py\"]')", 8000)
            pressed = page.evaluate("['docs', 'code', 'others'].map(k => document.querySelector('#lec-recent-' + k).getAttribute('aria-pressed'))")
            example = work / 'code' / 'example.py'
            example.write_bytes(example.read_bytes())   # 내용은 그대로 고침 — 감시가 touch 로 남긴다
            touched = wait_until(page, "document.querySelector('#lec-recent .row')?.dataset.file === 'code/example.py'", 8000)
            page.click('#lec-recent-code')
            no_code = wait_until(page, "!document.querySelector('#lec-recent .row[data-file$=\".py\"]')"
                                 " && !!document.querySelector('#lec-recent .row[data-file=\"첨부.pdf\"]')", 5000)
            saved_off = config_is('recent_code', False)
            page.click('#lec-recent-code')
            back = wait_until(page, "document.querySelector('#lec-recent .row')?.dataset.file === 'code/example.py'", 5000)
            body = opens(rrow('첨부.pdf').dblclick)
            rrow('code/example.py').click()
            to_code = wait_until(page, "document.querySelector('#lec-st-path').textContent === 'code/example.py' && !!document.querySelector('#lec-view .cv-line')", 5000)
            r_menu = menu(rrow('첨부.pdf'))
            page.keyboard.press('Escape')
            check(got_files and pressed == ['true'] * 3 and touched and no_code and saved_off and back and body['path'] == '첨부.pdf' and to_code
                  and '탐색기에서 보기' in r_menu and '@첨부.pdf 복사' in r_menu,
                  "최근 변경에 코드·자료도 — '문서'·'코드'·'자료' 버튼(설정 저장), 코드를 고치면 맨 위로, 자료는 두 번 눌러 열기, 코드는 한 번 눌러 읽기 화면, 우클릭은 자료 목록과 같은 메뉴")
            page.locator('.side-tabs button[data-tab="search"]').click()
            page.fill('#lec-search-input', 'setup')
            names_ok = wait_until(page, "!!document.querySelector('#lec-search-results .sr-name[data-file=\"data/setup.exe\"]')", 5000)
            sinfo = page.inner_text('#lec-search-info')
            body = opens(page.locator('#lec-search-results .sr-name[data-file="data/setup.exe"]').dblclick)
            page.click('#lec-search-others')
            no_name = wait_until(page, "!document.querySelector('#lec-search-results .sr-name[data-file=\"data/setup.exe\"]')"
                                 " && !document.querySelector('#lec-search-info').textContent.includes('…')", 5000)
            saved_off = cfg_is('search_others', False)
            page.click('#lec-search-others')
            page.fill('#lec-search-input', 'example')
            code_name = wait_until(page, "!!document.querySelector('#lec-search-results .sr-name[data-file=\"code/example.py\"]')", 5000)
            page.fill('#lec-search-input', '')
            check(names_ok and '이름 1개' in sinfo and body['path'] == 'data/setup.exe' and no_name and saved_off and code_name,
                  f"검색에 '자료' 버튼 — 맨 위에 이름이 맞는 파일(자료는 이름으로만, 코드도), 자료는 두 번 눌러 열기, 끄면 빠짐 ({sinfo})")
            page.locator('.side-tabs button[data-tab="parts"]').click()
            page.locator('#lec-parts-mode button[data-mode="files"]').click()
            page.wait_for_selector('#lec-parts-kinds button[data-ftype="others:csv"]', timeout=8000)
            chips = page.evaluate('''() => Object.fromEntries([...document.querySelectorAll('#lec-parts-kinds .ft-group')].map(g =>
              [g.querySelector('.ft-label').textContent, [...g.querySelectorAll('button')].map(b => b.dataset.ftype.split(':')[1])]))''')
            page.locator('#lec-parts-kinds button[data-ftype="others:svg"]').click()
            thumb = wait_until(page, "document.querySelector('#lec-parts-list .ft-thumb img')?.naturalWidth > 0", 5000)
            page.locator('#lec-parts-kinds button[data-ftype="others:csv"]').click()
            wait_until(page, "!!document.querySelector('#lec-parts-list .ft-row[data-file=\"data/표.csv\"]')", 3000)
            csv_rows = page.evaluate("[...document.querySelectorAll('#lec-parts-list [data-file]')].map(r => r.dataset.file)")
            pinfo = page.inner_text('#lec-parts-info')
            body = opens(page.locator('#lec-parts-list .ft-row[data-file="data/표.csv"]').dblclick)
            page.locator('.side-tabs button[data-tab="files"]').click()
            menu(orow('data'))
            page.locator('#lec-menu button', has_text='이 폴더의 파일을 종류별로 모아 보기').click()
            scoped = wait_until(page, "!document.querySelector('#lec-parts').hidden && document.querySelector('#lec-parts-scope').textContent === 'data 폴더'", 5000)
            data_chips = page.evaluate("[...document.querySelectorAll('#lec-parts-kinds button[data-ftype]')].map(b => b.dataset.ftype).sort()")
            shot('12-parts-files')
            page.click('#lec-parts-all')
            page.locator('#lec-parts-mode button[data-mode="parts"]').click()   # 아래 점검은 문서 속 요소로
            back_parts = wait_until(page, "!!document.querySelector('#lec-parts-kinds button[data-kind]')", 5000)
            check(chips.get('문서', [])[:1] == ['md'] and 'py' in chips.get('코드', []) and {'csv', 'exe', 'pdf', 'svg'} <= set(chips.get('자료', []))
                  and thumb and csv_rows == ['data/표.csv'] and pinfo == '파일 1개' and body['path'] == 'data/표.csv'
                  and scoped and data_chips == ['others:csv', 'others:exe'] and back_parts,
                  f"모아 보기 '파일 종류' — 문서·코드·자료마다 형식 버튼, 그림 파일은 작은 그림, 자료는 두 번 눌러 열기, '자료' 목록의 폴더 우클릭으로 그 폴더만 ({chips}, {data_chips})")
            page.locator('.side-tabs button[data-tab="files"]').click()
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

            print('[코드 보기]')
            cv = lambda: page.evaluate('''() => ({ code: document.querySelector('#lec-view').classList.contains('code-view'),
              title: document.querySelector('#lec-view .cv-title')?.textContent || '', lines: document.querySelectorAll('#lec-view .cv-line').length,
              status: document.querySelector('#lec-st-info').textContent, toc: [...document.querySelectorAll('#lec-toc .code-outline a')].map(a => a.textContent),
              active: document.querySelector('#lec-code-list .row.active')?.dataset.path || '', target: document.querySelector('#lec-view .lec-target')?.dataset.line || '',
              treeActive: document.querySelector('#lec-tree .row.active')?.dataset.doc || '', title2: document.title })''')
            page.locator('#lec-tree .row.file[data-doc="docs/95-경로.md"]').click()
            wait_until(page, "document.querySelectorAll('#lec-view a.path-link').length >= 3")
            page.locator('#lec-view a.path-link', has_text='code/example.py:13').click()
            page.wait_for_selector('#lec-view.code-view .cv-line')
            by_path = wait_until(page, "document.querySelector('#lec-view .lec-target')?.dataset.line === '13'", 3000)
            c1 = cv()
            shot('13-code-view')
            check(by_path and c1['title'] == 'example.py' and c1['lines'] >= 15 and c1['status'].startswith('Python')
                  and 'ƒmoving_average' in c1['toc'] and c1['active'] == 'code/example.py' and not c1['treeActive'] and c1['title2'].startswith('example.py'),
                  f"문서 속 코드 경로(`code/example.py:13`)를 누르면 읽기 화면의 그 줄로 — 줄 번호·언어 색, 오른쪽 목차(함수), '코드' 목록에서 강조 ({c1})")
            fonts = page.evaluate("""() => {
              const fam = (el) => el && getComputedStyle(el).fontFamily;
              const probe = document.createElement('h1');   // 이 스타일의 문서 제목 글꼴
              probe.style.position = 'absolute';
              document.querySelector('#lec-view').append(probe);
              const out = { title: fam(document.querySelector('#lec-view .cv-title')), heading: fam(probe),
                edit: fam(document.querySelector('#lec-view .cv-edit')), status: fam(document.querySelector('#lec-st-edit')),
                icon: !!document.querySelector('#lec-view .cv-edit use[href="#i-edit"]') };
              probe.remove();
              return out; }""")
            check(fonts['title'] == fonts['heading'] and fonts['edit'] == fonts['status'] and fonts['icon'],
                  f"코드 화면의 파일 이름은 문서 제목과 같은 글꼴, '편집' 버튼은 상태줄의 '편집'과 같은 글꼴·연필 ({fonts})")
            page.keyboard.press('Alt+ArrowLeft')
            back_doc = wait_until(page, "document.querySelector('#lec-view h1')?.textContent === '경로 표기 확인'")
            doc_title = page.evaluate('document.title')   # 창 제목: 파일 이름 [문서 제목]
            check(doc_title == '95-경로.md [경로 표기 확인] - samples - Lectern' and c1['title2'] == 'example.py - samples - Lectern',
                  f'창 제목은 파일 이름 [문서 제목] - 프로젝트, 코드는 파일 이름 ({doc_title!r})')
            page.locator('#lec-tree .row.file[data-doc="docs/01-기능-점검.md"]').click()
            page.wait_for_selector('#lec-view h1:has-text("렌더링 기능 점검")')
            page.locator('#lec-view a.file-link', has_text='example.py').first.click()
            by_link = wait_until(page, "document.querySelector('#lec-view.code-view .lec-target')?.dataset.line === '13'", 5000)
            check(back_doc and by_link, '뒤로 가기로 문서에 돌아오고, 문서 속 코드 파일 링크(#L13)도 읽기 화면의 그 줄로')
            crow = page.locator('#lec-code-list .row[data-path="code/example.py"]')
            if not crow.count():
                page.locator('#lec-code-list .row[data-path="code"] [data-toggle]').click()
            page.locator('#lec-tree .row.file[data-doc="docs/01-기능-점검.md"]').click()
            page.wait_for_selector('#lec-view h1:has-text("렌더링 기능 점검")')
            crow.click()
            by_click = wait_until(page, "document.querySelector('#lec-view.code-view .cv-title')?.textContent === 'example.py'", 5000)
            page.locator('#lec-toc .code-outline a', has_text='moving_average').click()
            toc_go = wait_until(page, "document.querySelector('#lec-view .lec-target')?.dataset.line === '8'", 3000)
            body = opens(crow.dblclick)
            check(by_click and toc_go and body['path'] == 'code/example.py',
                  f"'코드' 목록에서 한 번 누르면 읽기 화면, 목차를 누르면 그 줄로, 두 번 누르면 편집기 ({body})")
            src = work / 'code' / 'example.py'
            original = src.read_text(encoding='utf-8')
            src.write_text(original + '\n\ndef added_later():\n    return 1\n', encoding='utf-8')
            refreshed = wait_until(page, "[...document.querySelectorAll('#lec-toc .code-outline a')].some(a => a.textContent.includes('added_later'))", 8000)
            flashed = page.evaluate("document.querySelectorAll('#lec-view .cv-line.lec-changed').length")
            src.write_text(original, encoding='utf-8')
            restored = wait_until(page, "![...document.querySelectorAll('#lec-toc .code-outline a')].some(a => a.textContent.includes('added_later'))", 8000)
            check(refreshed and flashed >= 2 and restored, f'보고 있는 코드가 바뀌면 다시 그리고 바뀐 줄 강조 ({flashed}줄)')
            page.keyboard.press('Control+f')
            page.fill('#lec-find-input', 'window')
            found_code = wait_until(page, "/^1\\/\\d+$/.test(document.querySelector('#lec-find-count').textContent)", 3000)
            page.keyboard.press('Escape')
            items = menu(page.locator('#lec-view .cv-line[data-line="3"]'))
            copied = choose('Claude용 위치 복사')
            check(found_code and '편집기에서 이 줄 열기' in items and '코드 전체 복사' in items and copied == '@code/example.py 3행',
                  f"코드 화면에서도 Ctrl+F 찾기, 줄 우클릭 메뉴 — Claude용 위치 ({copied!r})")
            page.locator('#lec-tree .row.file[data-doc="docs/01-기능-점검.md"]').click()
            page.wait_for_selector('#lec-view h1:has-text("렌더링 기능 점검")')

            print('[편집 모드]')   # D54 — CodeMirror 5, 저장은 POST /api/save
            plan = work / 'plans' / '10-후속-과제.md'
            original = plan.read_bytes()
            ed_state = lambda: page.evaluate("document.querySelector('.lec-editor .ed-state')?.textContent || ''")
            page.locator('#lec-tree .row.file', has_text='후속 과제').click()
            page.wait_for_selector('#lec-view h1:has-text("후속 과제")')
            page.click('#lec-btn-edit')   # 탭 막대의 [편집] — 켜기 (목차·터미널 왼쪽)
            page.wait_for_selector('.lec-editor .CodeMirror')
            pressed_on = page.get_attribute('#lec-btn-edit', 'aria-pressed') == 'true'
            page.click('#lec-btn-edit')   # 끄기
            off = wait_until(page, "!document.querySelector('.lec-editor') && document.querySelector('#lec-btn-edit').getAttribute('aria-pressed') === 'false'", 3000)
            order = page.evaluate("[...document.querySelectorAll('#lec-tabbar .tabbar-btn')].map(b => b.id)")
            page.click('#lec-tree .row.root')   # 폴더 개요에서는 누를 수 없다
            no_edit = wait_until(page, "document.querySelector('#lec-btn-edit').disabled", 3000)
            page.locator('#lec-tree .row.file', has_text='후속 과제').click()
            page.wait_for_selector('#lec-view h1:has-text("후속 과제")')
            check(pressed_on and off and no_edit and order == ['lec-btn-edit', 'lec-btn-toc', 'lec-btn-term'],
                  f"탭 막대의 [편집] [목차] [터미널] — [편집]을 누르면 편집 모드가 켜지고(눌린 모양) 다시 누르면 꺼짐, 폴더 개요에서는 누를 수 없음 ({order})")
            page.click('#lec-st-edit')
            page.wait_for_selector('.lec-editor .CodeMirror')
            in_editor = page.evaluate("!!document.activeElement?.closest('.lec-editor') && document.querySelector('#lec-st-edit').hidden")
            page.keyboard.press('Control+End')
            page.keyboard.press('Enter')
            page.keyboard.type('- [ ] edit ')
            page.keyboard.insert_text('편집 모드로 더함')   # 한글 입력기(IME)가 글자를 넣는 것처럼
            dirty = page.evaluate("document.querySelector('.lec-editor').classList.contains('dirty')")
            page.keyboard.press('Control+f')   # 편집 상자 안의 Ctrl+F 는 편집기의 찾기 (앱의 찾기 막대가 아니라)
            cm_find = wait_until(page, "!!document.querySelector('.lec-editor .CodeMirror-dialog')", 2000) and page.is_hidden('#lec-findbar')
            page.keyboard.press('Escape')
            page.keyboard.press('Control+s')
            saved = wait_until(page, "document.querySelector('.lec-editor .ed-state').textContent.startsWith('저장했습니다')", 5000)
            on_disk = plan.read_bytes()
            page.keyboard.press('Escape')
            closed = wait_until(page, "!document.querySelector('.lec-editor')", 3000)
            shown = wait_until(page, "document.querySelector('#lec-view').textContent.includes('편집 모드로 더함')", 8000)
            check(in_editor and dirty and cm_find and saved and on_disk.endswith('- [ ] edit 편집 모드로 더함'.encode()) and b'\r\n' not in on_disk
                  and closed and shown,
                  f"편집 모드: 상태줄 '편집'으로 문서 원문을 고치고(한글 입력), Ctrl+F 는 편집기의 찾기, Ctrl+S 저장(LF 그대로), Esc 로 닫으면 고친 문서가 보임 "
                  f"({ed_state()}, {dict(in_editor=in_editor, dirty=dirty, cm_find=cm_find, saved=saved, tail=on_disk[-30:].decode('utf-8', 'replace'), closed=closed, shown=shown)})")
            # 그사이 다른 곳(Claude Code 등)에서 바뀌면 덮어쓰지 않고 묻는다. 저장하지 않은 채 닫으면 묻는다
            page.locator('#lec-view li').last.click(button='right')
            page.locator('#lec-menu button', has_text='여기를 편집').click()
            page.wait_for_selector('.lec-editor .CodeMirror')
            at_line = page.evaluate("document.querySelector('.CodeMirror').CodeMirror.getCursor().line + 1")
            want_line = int(page.evaluate("[...document.querySelectorAll('#lec-view li')].pop().closest('[data-lines]').dataset.lines.split('-')[0]"))
            plan.write_bytes(plan.read_bytes() + '\n외부에서 더함\n'.encode())
            page.keyboard.type('x')
            asked = []
            page.once('dialog', lambda dlg: (asked.append(dlg.message), dlg.dismiss()))
            page.keyboard.press('Control+s')
            wait_until(page, "!document.querySelector('.lec-editor .ed-state').textContent.includes('…')", 3000)
            page.wait_for_timeout(300)
            kept = '외부에서 더함' in plan.read_text(encoding='utf-8') and page.evaluate("document.querySelector('.lec-editor').classList.contains('dirty')")
            asked2 = []
            page.once('dialog', lambda dlg: (asked2.append(dlg.message), dlg.accept()))
            page.keyboard.press('Escape')
            closed2 = wait_until(page, "!document.querySelector('.lec-editor')", 3000)
            plan.write_bytes(original)
            check(at_line == want_line and asked and '바뀌었습니다' in asked[0] and kept and asked2 and '저장하지 않은' in asked2[0] and closed2,
                  f"우클릭 '여기를 편집'은 그 줄에서, 그사이 다른 곳에서 바뀌면 덮어쓰지 않고 물음, 저장하지 않고 닫으면 물음 ({at_line}/{want_line}, {asked[:1]})")
            code_dir = page.locator('#lec-code-list .row[data-path="code"]')
            if code_dir.get_attribute('aria-expanded') != 'true':   # 앞에서 코드 화면을 보며 펼쳐 두었을 수 있다
                code_dir.locator('[data-toggle]').click()
            page.locator('#lec-code-list .row[data-path="code/example.py"]').click()
            page.wait_for_selector('#lec-view .cv-edit')
            page.click('#lec-content')
            page.keyboard.press('Control+e')   # Ctrl+E 로 열고 닫기
            page.wait_for_selector('.lec-editor .CodeMirror')
            mode = page.evaluate("document.querySelector('.CodeMirror').CodeMirror.getMode().name")
            page.keyboard.press('Control+e')
            code_closed = wait_until(page, "!document.querySelector('.lec-editor')", 3000)
            check(mode == 'python' and code_closed, f'코드 화면도 Ctrl+E 로 편집 모드 — 언어 색 ({mode})')
            page.locator('#lec-tree .row.file[data-doc="docs/01-기능-점검.md"]').click()
            page.wait_for_selector('#lec-view h1:has-text("렌더링 기능 점검")')

            print('[편집 위치 잇기]')   # D55 — 읽는 화면·편집기·목차가 원문의 같은 곳을
            mapping = page.evaluate("""() => import('/static/js/editsync.js').then((m) => {
              let bad = 0;   // 무작위 편집 뒤 남은 줄이 제자리로 옮겨지는지
              for (let trial = 0; trial < 200; trial++) {
                const orig = Array.from({ length: 30 }, (_, i) => 'L' + i);
                const lines = orig.slice();
                const log = [];
                for (let k = 0; k < 6; k++) {
                  const from = Math.floor(Math.random() * lines.length);
                  const to = Math.min(lines.length - 1, from + Math.floor(Math.random() * 4));
                  const text = Array.from({ length: 1 + Math.floor(Math.random() * 5) }, (_, i) => `n${trial}-${k}-${i}`);
                  lines.splice(from, to - from + 1, ...text);
                  m.logChange(log, { from: { line: from }, to: { line: to }, text });
                }
                orig.forEach((name, i) => { const j = lines.indexOf(name); if (j >= 0 && m.toEditor(log, i) !== j) bad++; });
                lines.forEach((name, j) => { const i = orig.indexOf(name); if (i >= 0 && m.toView(log, j) !== i) bad++; });
              }
              const heads = m.headLines('<p>\\n<!-- <h2> -->\\n<h1>a</h1><style>x{content:"<h2 "}</style>\\n<H2\\n id=b>b</H2><hr><header>\\n<h3>c</h3>');
              return { bad, heads };
            })""")
            check(mapping['bad'] == 0 and mapping['heads'] == [2, 3, 5],
                  f"편집기에서 줄이 늘거나 줄어도 읽는 화면의 줄과 이어짐, html 은 원문의 제목 태그 줄 ({mapping})")
            doc1 = work / 'docs' / '01-기능-점검.md'
            doc1_orig = doc1.read_bytes()
            cm = "document.querySelector('.lec-editor .CodeMirror').CodeMirror"
            head_line = lambda name: int(page.evaluate(
                f"[...document.querySelectorAll('#lec-view h2, #lec-view h3')].find(h => h.textContent.trim() === '{name}').dataset.lines.split('-')[0]"))
            cursor_line = lambda: page.evaluate(f"{cm}.getCursor().line + 1")
            active_toc = lambda: page.evaluate("document.querySelector('#lec-toc a.active')?.textContent.trim() || ''")
            # 읽던 곳에서 연다
            page.locator('#lec-toc a[data-i]', has_text='콜아웃').click()
            page.wait_for_timeout(300)
            page.click('#lec-btn-edit')
            page.wait_for_selector('.lec-editor .CodeMirror')
            page.wait_for_timeout(200)
            callout = head_line('콜아웃')
            opened_at = page.evaluate(f"""(() => {{ const cm = {cm}; const r = cm.getScrollerElement().getBoundingClientRect();
              return [cm.lineAtHeight(r.top + 40, 'window') + 1, cm.getCursor().line + 1]; }})()""")
            # 커서를 다른 절로 옮기면 목차의 '지금 읽는 위치'가 따라온다
            link = head_line('링크')
            page.evaluate(f"(() => {{ const cm = {cm}; cm.setCursor({{ line: {link + 1}, ch: 0 }}); cm.scrollIntoView(null, 120); }})()")
            follows = wait_until(page, "document.querySelector('#lec-toc a.active')?.textContent.trim() === '링크'", 2000)
            # 편집 중에 목차를 누르면 편집기가 그 제목의 줄로
            page.locator('#lec-toc a[data-i]', has_text='표').first.click()
            page.wait_for_timeout(200)
            to_table = (cursor_line(), head_line('표'), page.is_visible('.lec-editor'), active_toc())
            check(callout <= opened_at[0] <= callout + 4 and abs(opened_at[1] - opened_at[0]) <= 1 and follows
                  and to_table[0] == to_table[1] and to_table[2] and to_table[3] == '표',
                  f"편집 모드를 읽던 곳(콜아웃 {callout}행)에서 열고, 커서를 옮기면 목차가 따라오고, 목차를 누르면 편집기가 그 줄로 ({opened_at}, {to_table})")
            # 위에 세 줄을 더한 뒤(저장 전) 목차 — 늘어난 줄만큼 옮겨서. 저장해서 다시 그린 뒤에는 그 화면의 줄 그대로
            page.evaluate(f"{cm}.replaceRange('하나\\n둘\\n셋\\n', {{ line: 0, ch: 0 }})")
            figure = head_line('그림')
            page.locator('#lec-toc a[data-i]', has_text='그림').click()
            page.wait_for_timeout(200)
            shifted = cursor_line()
            page.keyboard.press('Control+s')
            saved = wait_until(page, "document.querySelector('.lec-editor .ed-state').textContent.startsWith('저장했습니다')", 5000)
            redrawn = wait_until(page, f"[...document.querySelectorAll('#lec-view h2')].find(h => h.textContent.trim() === '그림')?.dataset.lines.startsWith('{figure + 3}-')", 8000)
            page.locator('#lec-toc a[data-i]', has_text='코드').click()
            page.wait_for_timeout(200)
            after_save = (cursor_line(), head_line('코드'))
            check(shifted == figure + 3 and saved and redrawn and after_save[0] == after_save[1],
                  f"편집기에서 줄이 늘면 목차는 늘어난 만큼 옮긴 줄로, 저장해서 다시 그린 뒤에는 새 화면의 줄로 ({shifted}/{figure + 3}, {after_save})")
            # 검색 결과(편집 중인 파일)를 누르면 편집기가 그 줄로
            page.click('.side-tabs button[data-tab="search"]')
            page.fill('#lec-search-input', '인도네시아')
            wait_until(page, "document.querySelector('#lec-search-results .sr-hit[data-doc=\"docs/01-기능-점검.md\"]')", 5000)
            hit = page.locator('#lec-search-results .sr-hit[data-doc="docs/01-기능-점검.md"]').first
            hit_line = int(hit.get_attribute('data-line') or 0)
            hit.click()
            page.wait_for_timeout(200)
            searched = (cursor_line(), hit_line, page.is_visible('.lec-editor'))
            page.click('.side-tabs button[data-tab="files"]')
            # 닫으면 읽는 화면이 편집하던 곳(커서의 줄이 같은 높이)에
            page.locator('#lec-toc a[data-i]', has_text='체크리스트와 각주').click()
            page.wait_for_timeout(200)
            cursor_y = page.evaluate(f"{cm}.cursorCoords(true, 'window').top")
            page.evaluate(f"{cm}.focus()")
            page.keyboard.press('Escape')
            closed = wait_until(page, "!document.querySelector('.lec-editor')", 3000)
            page.wait_for_timeout(200)
            head_y = page.evaluate("[...document.querySelectorAll('#lec-view h2')].find(h => h.textContent.trim() === '체크리스트와 각주').getBoundingClientRect().top")
            check(searched[0] == searched[1] and searched[2] and closed and abs(head_y - cursor_y) <= 6 and active_toc() == '체크리스트와 각주',
                  f"검색 결과를 누르면 편집기가 그 줄로, 닫으면 읽는 화면이 편집하던 곳에 (검색 {searched}, 높이 {head_y:.0f}/{cursor_y:.0f})")
            doc1.write_bytes(doc1_orig)
            wait_until(page, "!document.querySelector('#lec-view p')?.textContent.startsWith('하나')", 8000)
            # 코드 화면: 목차(클래스·함수)를 누르면 편집기가 그 줄로. html 문서: 원문의 그 제목 태그로
            page.locator('#lec-code-list .row[data-path="code/example.py"]').click()
            page.wait_for_selector('#lec-view .cv-edit')
            page.click('#lec-btn-edit')
            page.wait_for_selector('.lec-editor .CodeMirror')
            page.evaluate(f"(() => {{ const cm = {cm}; cm.setCursor({{ line: cm.lineCount() - 1, ch: 0 }}); }})()")   # 끝에서
            item = page.locator('#lec-toc a[data-i]').first
            want_code = int(item.get_attribute('title').rsplit('— ', 1)[1].rstrip('행'))
            item.click()
            page.wait_for_timeout(200)
            code_at = cursor_line()
            page.click('#lec-btn-edit')
            page.locator('#lec-tree .row.file[data-doc="docs/04-HTML-보고서.html"]').click()
            wait_until(page, "document.querySelector('#lec-view iframe.lec-html:not(.lec-loading)')?.contentDocument?.querySelector('h2')")
            page.click('#lec-btn-edit')
            page.wait_for_selector('.lec-editor .CodeMirror')
            page.locator('#lec-toc a[data-i]').nth(1).click()
            page.wait_for_timeout(200)
            html_at = page.evaluate(f"(() => {{ const cm = {cm}; return cm.getLine(cm.getCursor().line); }})()")
            want_html = page.evaluate("document.querySelectorAll('#lec-toc a[data-i]')[1].textContent.trim()")
            page.click('#lec-btn-edit')
            html_closed = wait_until(page, "!document.querySelector('.lec-editor')", 3000)
            check(code_at == want_code and want_html in html_at and '<h' in html_at.lower() and html_closed,
                  f"코드 화면의 목차는 그 줄로 ({code_at}/{want_code}), html 문서의 목차는 원문의 그 제목 태그로 ({html_at.strip()[:60]!r})")
            page.locator('#lec-tree .row.file[data-doc="docs/01-기능-점검.md"]').click()
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
                       toc: document.querySelectorAll('#lec-toc a[data-i]').length }}; }}""")
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
            check(page.locator('#lec-view .image-off').inner_text().startswith('인터넷 그림을 불러오지 못했습니다'),
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
            # 목차 폭 (D47): 문서와 목차 사이 경계를 왼쪽으로 끌면 목차가 넓어지고 저장, 두 번 누르면 기본 폭, 목차를 감추면 경계도 감춤
            toc_w = lambda: page.locator('#lec-toc').bounding_box()['width']
            toc_before, doc_before = toc_w(), page.locator('#lec-panes').bounding_box()['width']
            tbox = page.locator('#lec-toc-resizer').bounding_box()
            page.mouse.move(tbox['x'] + 3, tbox['y'] + 200)
            page.mouse.down()
            page.mouse.move(tbox['x'] + 3 - 100, tbox['y'] + 220, steps=6)
            page.mouse.up()
            toc_dragged, doc_after = toc_w(), page.locator('#lec-panes').bounding_box()['width']
            saved_toc = page.evaluate("fetch('/api/config').then(r => r.json()).then(c => c.toc_width)")
            page.locator('#lec-toc-resizer').dblclick()
            page.wait_for_timeout(100)
            toc_reset = toc_w()
            handle_shown = "getComputedStyle(document.querySelector('#lec-toc-resizer')).display !== 'none'"
            page.click('#lec-btn-toc')   # 목차 버튼은 설정을 저장한 뒤 화면을 바꾼다 — 바뀔 때까지 기다린다
            handle_hidden = wait_until(page, f'!({handle_shown})', 3000)
            page.click('#lec-btn-toc')
            handle_back = wait_until(page, handle_shown, 3000)
            check(abs(toc_dragged - toc_before - 100) <= 3 and abs((doc_before - doc_after) - 100) <= 3 and saved_toc
                  and abs(saved_toc - toc_dragged) <= 1 and abs(toc_reset - toc_before) <= 1 and handle_hidden and handle_back,
                  f'목차 경계를 끌어 목차 폭 조절·저장(문서 칸은 그만큼 좁아짐), 두 번 누르면 기본 폭, 목차를 감추면 경계도 ({toc_before:.0f} → {toc_dragged:.0f}, 저장 {saved_toc}, 기본 {toc_reset:.0f})')
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
            ui_now = lambda: page.evaluate('''() => ({ toc: document.querySelector('#lec-toc .toc-list a[data-i]')?.textContent || '',
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
            check(cross['off'] and cross['img'].startswith('표시할 수 없는 그림'), f'다른 탭 프로젝트로 넘어가는 상대경로는 막힘 ({cross})')
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
            page.click('#lec-view.welcome button[data-act="help"]')   # 폴더를 열기 전에도 사용설명서
            welcome_help = wait_until(page, "!document.querySelector('#lec-help').hidden && document.querySelectorAll('#lec-help-toc a').length > 10")
            page.keyboard.press('F1')
            welcome_help = welcome_help and wait_until(page, "document.querySelector('#lec-help').hidden")
            page.locator('#lec-view.welcome button[data-path]', has_text=str(work)).click()   # 최근 연 폴더에서 다시 열기
            reopened = n_tabs(1) and h1_has('렌더링 기능 점검') and tree_root() == 'samples'
            check(middle and welcome and title == 'Lectern' and welcome_help and reopened,
                  f"탭을 가운데 버튼으로도 닫고, 모두 닫으면 시작 화면(트리 비움, '사용설명서' 버튼), 최근 연 폴더로 다시 열기"
                  f' ({middle}, {welcome}, {title!r}, {welcome_help}, {reopened})')

            print('[예제]')   # D57 — 사용자·AI 용 예제 프로젝트(설치 폴더의 samples)와 'Claude Code 에 Lectern 알려 주기'
            page.click('#lec-btn-recent')
            page.locator('#lec-menu button', has_text='예제 열기').click()
            readme = n_tabs(2) and h1_has('Lectern 예제')   # 처음 열면 폴더 개요 대신 README
            page.locator('#lec-tree .row.file[data-doc="guide/07-차트.md"]').click()
            charts_ok = wait_until(page, "document.querySelectorAll('#lec-view pre.lec-chart.chart-ok').length === 11", 30000)
            chart_errs = page.evaluate("[...document.querySelectorAll('#lec-view .diagram-error > p')].map(p => p.textContent)")
            page.locator('#lec-tree .row.file[data-doc="guide/06-다이어그램.md"]').click()
            mermaid_ok = wait_until(page, "document.querySelectorAll('#lec-view pre.mermaid.mermaid-ok').length === 8", 30000) \
                and page.locator('#lec-view .diagram-error').count() == 0
            page.locator('#lec-tree .row.file[data-doc="guide/04-문서-쓰는-법.md"]').click()
            page.wait_for_selector('#lec-view h1:has-text("문서 쓰는 법")')
            page.locator('#lec-view img').first.scroll_into_view_if_needed()
            img_ok = wait_until(page, "[...document.querySelectorAll('#lec-view img')].every(i => i.complete && i.naturalWidth > 0)", 5000)
            code_links = page.locator('#lec-view a.path-link[data-line]').count()
            page.keyboard.press('Control+,')
            page.click('#lec-aiguide-prompt')
            guide_prompt = page.evaluate('navigator.clipboard.readText()')
            page.click('#lec-settings-close')

            print('[슬라이드]')   # D59 — marp: true 인 발표 문서 (예제의 guide/08-발표.md)
            page.locator('#lec-tree .row.file[data-doc="guide/08-발표.md"]').click()
            deck_ok = wait_until(page, '''(() => { const v = document.querySelector('#lec-view');
              return v.classList.contains('lec-deck') && v.querySelector('pre.mermaid.mermaid-ok') && v.querySelector('pre.lec-chart.chart-ok'); })()''', 30000)
            page.wait_for_timeout(500)
            deck = page.evaluate('''() => { const v = document.querySelector('#lec-view'); const q = (s) => v.querySelectorAll(s);
              const frame = v.querySelector('.lec-slide-frame'), first = v.querySelector('.lec-slide');
              const btn = (id) => { const b = document.querySelector(id); return b.hidden ? null : b.textContent.trim(); };
              return { slides: q(':scope > .lec-slide-wrap').length, over: q('.lec-over').length, bg: q('.lec-slide-bg img').length,
                notes: q('.lec-slide-notes').length, page: q('.lec-paginate')[0]?.dataset.page, fm: q('.front-matter').length,
                scale: Math.abs(+v.style.getPropertyValue('--slide-scale') - frame.clientWidth / 1280) < 0.01,
                fit: Math.abs(first.getBoundingClientRect().width - frame.clientWidth) < 2,
                lead: first.classList.contains('lead'), styled: getComputedStyle(first.querySelector('p')).color,
                chartText: Math.max(...[...v.querySelectorAll('.lec-chart svg text')].map((e) => e.getBoundingClientRect().height)),
                toggle: btn('#lec-st-slides'), present: btn('#lec-st-present') }; }''')
            check(deck_ok and deck['slides'] == 8 and not deck['over'] and deck['bg'] == 1 and deck['notes'] == 2 and deck['page'] == '2'
                  and not deck['fm'] and deck['scale'] and deck['fit'] and deck['lead'] and deck['styled'] == 'rgb(107, 114, 128)'
                  and deck['chartText'] >= 7 and deck['toggle'] == '문서로 보기' and deck['present'] == '발표',
                  f"발표 문서(marp: true)는 16:9 슬라이드 8장 — 다이어그램·차트(키워 그림)·배경 그림·노트·쪽 번호·lead·style: CSS, 상태줄 '문서로 보기'·'발표' ({deck})")
            shot('20-slides')
            pr = lambda: page.evaluate('''() => { const b = document.querySelector('#lec-present'); const h = b.querySelector('.pr-deck');
              return { shown: !b.hidden, count: b.querySelector('.pr-count').textContent, notes: !b.querySelector('.pr-notes').hidden,
                       fill: h ? Math.max(h.offsetWidth / innerWidth, h.offsetHeight / b.querySelector('.pr-stage').clientHeight) : 0 }; }''')
            page.locator('#lec-view .lec-slide-frame').nth(1).hover()
            page.locator('#lec-view .lec-slide-frame').nth(1).locator('.lec-slide-play').click()   # 이 장부터 발표
            p1 = pr()
            page.keyboard.press('ArrowRight')
            page.keyboard.press('Space')
            page.keyboard.press('n')
            p2 = pr()
            shot('20-slides-present')
            page.keyboard.press('ArrowLeft')
            page.keyboard.press('End')
            p3 = pr()
            page.keyboard.press('Escape')
            p4 = pr()
            page.keyboard.press('Shift+F5')
            p5 = pr()
            page.keyboard.press('Escape')
            check(p1['shown'] and p1['count'] == '2 / 8' and p1['fill'] > 0.98 and p2['count'] == '4 / 8' and p2['notes']
                  and p3['count'] == '8 / 8' and not p4['shown'] and p5['shown'] and p5['count'] == '8 / 8',
                  f"발표 모드: ▶ 로 그 장부터 창 가득, → Space ← End 로 넘기기, N 노트, Esc 끝내면 그 장으로, Shift+F5 는 보던 장부터 ({p1}, {p2}, {p3}, {p5})")
            pdf = page.pdf(prefer_css_page_size=True, print_background=True)
            pages = len(re.findall(rb'/Type\s*/Page[^s]', pdf))
            boxes = set(re.findall(rb'/MediaBox\s*\[([^\]]+)\]', pdf))
            page.click('#lec-st-slides')   # 문서로 보기
            as_doc = wait_until(page, "!document.querySelector('#lec-view').classList.contains('lec-deck')", 10000)
            doc_state = page.evaluate('''() => ({ fm: !!document.querySelector('#lec-view .front-matter'), hr: document.querySelectorAll('#lec-view > hr').length,
              changes: !document.querySelector('#lec-st-changes').hidden, toggle: document.querySelector('#lec-st-slides').textContent.trim(),
              present: !document.querySelector('#lec-st-present').hidden })''')
            page.click('#lec-st-slides')
            back_deck = wait_until(page, "document.querySelector('#lec-view').classList.contains('lec-deck')", 10000)
            check(pages == 8 and boxes == {b'0 0 960 540'} and as_doc and doc_state['fm'] and doc_state['hr'] == 7 and not doc_state['changes']
                  and doc_state['toggle'] == '슬라이드로 보기' and not doc_state['present'] and back_deck,
                  f"인쇄·PDF 는 한 장에 한 쪽(1280×720), '문서로 보기'는 보통 문서(바뀐 곳으로 잡지 않음)·다시 슬라이드 ({pages}, {boxes}, {doc_state})")

            print('[모아 보기 더]')   # D62 — 차트(작은 그림)·할 일·링크·출처, 문서 정보(frontmatter)
            page.click('.side-tabs button[data-tab="parts"]')
            wait_until(page, "!document.querySelector('#lec-parts-info').textContent.includes('읽는 중') && document.querySelector('#lec-parts-info').textContent !== ''", 30000)
            mk = lambda: page.evaluate('''() => Object.fromEntries([...document.querySelectorAll('#lec-parts-kinds button')]
              .map(b => [b.dataset.kind || b.dataset.mkey, +b.querySelector('.n').textContent]))''')
            more_kinds = mk()
            page.click('#lec-parts-kinds button[data-kind="chart"]')
            chart_thumbs = wait_until(page, "document.querySelectorAll('#lec-parts-list .pt-chart .pt-pic svg').length >= 3", 40000)
            shot('23-parts-charts')
            page.click('#lec-parts-kinds button[data-kind="task"]')
            task_sub = page.evaluate("[...document.querySelectorAll('#lec-parts-sub button')].map(b => b.dataset.sub + (b.classList.contains('active') ? '*' : ''))")
            open_tasks = page.locator('#lec-parts-list .pt-item.pt-done').count() == 0 and page.locator('#lec-parts-list .pt-item').count() > 0
            page.click('#lec-parts-sub button[data-sub="done"]')
            done_tasks = page.locator('#lec-parts-list .pt-item').count() == page.locator('#lec-parts-list .pt-item.pt-done').count() > 0
            page.click('#lec-parts-sub button[data-sub="open"]')
            page.click('#lec-parts-kinds button[data-kind="link"]')
            links = page.evaluate('''() => ({ n: document.querySelectorAll('#lec-parts-list .pt-item').length,
              bad: document.querySelectorAll('#lec-parts-list .pt-bad').length,
              code: [...document.querySelectorAll('#lec-parts-list .pt-label')].some(l => l.textContent.startsWith('코드 · src/report.py')) })''')
            page.click('#lec-parts-kinds button[data-kind="source"]')
            notes = page.evaluate("[...document.querySelectorAll('#lec-parts-list .pt-label')].map(l => l.textContent)")
            page.click('#lec-parts-mode button[data-mode="meta"]')
            wait_until(page, "!!document.querySelector('#lec-parts-kinds button[data-mkey]')", 5000)
            meta_keys = list(mk())
            page.click('#lec-parts-kinds button[data-mkey="status"]')
            meta_rows = page.evaluate("[...document.querySelectorAll('#lec-parts-list .pt-val .label, #lec-parts-list .pt-mdoc .label')].map(e => e.textContent)")
            shot('23-parts-meta')
            page.click('#lec-parts-mode button[data-mode="parts"]')
            page.click('#lec-parts-kinds button[data-kind="table"]')
            page.click('.side-tabs button[data-tab="files"]')
            check(all(more_kinds.get(k, 0) > 0 for k in ('chart', 'task', 'link', 'source')) and more_kinds['diagram'] > 0 and chart_thumbs
                  and task_sub == ['open*', 'done', 'all'] and open_tasks and done_tasks and links['n'] > 10 and links['bad'] == 0 and links['code']
                  and any(n.startswith('각주') for n in notes) and 'status' in meta_keys and 'tags' in meta_keys
                  and meta_rows[:2] == ['진행 중', '리서치 자동화 구현 계획'] and '구리 시장 2분기 리뷰' not in meta_rows,
                  f"모아 보기의 차트(작은 그림)·할 일(안 한 것/한 것)·링크(코드 위치·깨짐 없음)·출처(각주), 문서 정보(frontmatter 키·값) "
                  f"({more_kinds}, {chart_thumbs}, {task_sub}, {links}, {notes[:2]}, {meta_keys}, {meta_rows[:4]})")

            tab_el(1).locator('.tab-close').click()   # 예제 탭을 닫고 점검 프로젝트로
            back = n_tabs(1) and tree_root() == 'samples'
            check(readme and charts_ok and len(chart_errs) == 1 and '함수는 쓸 수 없습니다' in chart_errs[0] and mermaid_ok and img_ok
                  and code_links >= 2 and 'writing.md' in guide_prompt and 'CLAUDE.md' in guide_prompt and back,
                  f"예제 열기: README 부터, 차트 11개(오류 예시 하나)·다이어그램 8개·그림·코드 위치 링크, 설정 창의 작성 안내 요청 글 "
                  f"({readme}, {chart_errs}, {mermaid_ok}, {img_ok}, {code_links}, {guide_prompt[:40]!r}, {back})")

            print('[CSV]')   # D60 — 자료 목록의 csv·tsv 는 표(거르기·정렬·통계), txt 는 글자로. UTF-8 이 아니면 CP949·UTF-16
            tables = tmp / 'tables'
            (tables / 'data').mkdir(parents=True)
            (tables / 'README.md').write_text('# 표 시험\n\n[월별 가격](data/prices.csv)\n\n`data/prices.csv:5` 를 보세요.\n', encoding='utf-8')
            price_rows = ['월,품목,가격,비고'] + [f'2025-{m:02d},{"구리" if m % 3 else "니켈"},"{p:,}",{"" if (m - 1) % 4 else "점검"}'
                                                 for m, p in zip(range(1, 13), [8920, 9180, 9650, 9310, 9540, 9870, 9720, 9460, 9890, 10240, 10010, 10380])]
            (tables / 'data' / 'prices.csv').write_text('\n'.join(price_rows) + '\n', encoding='utf-8')
            (tables / 'data' / 'excel.csv').write_bytes('지역,물동량(천톤),증감률\n부산,1234,3.5%\n인천,987,-1.2%\n'.encode('cp949'))
            (tables / 'data' / 'memo.txt').write_bytes('한글 메모 (CP949)\n두 번째 줄\n'.encode('cp949'))
            (tables / 'data' / 'uni.txt').write_bytes('\ufeff유니코드 텍스트\n'.encode('utf-16-le'))
            # 캡션 (D61): 굵은 〈표 Ⅱ-15〉, '표 1.', 캡션 없는 표, 아래 캡션이 있는 그림과 없는 그림
            (tables / 'img').mkdir()
            for n in ('a', 'b'):
                shutil.copy(ROOT / 'samples' / 'research' / 'images' / 'price-band.svg', tables / 'img' / f'{n}.svg')
            (tables / 'caps.md').write_text('# 캡션\n\n**〈표 Ⅱ-15〉 철재의 HS코드**\n\n| HS코드 | 품명 |\n|---|---|\n| 7208 | 열연강판 |\n\n'
                                            '표 1. 항만별 물동량\n\n| 항만 | 물동량 |\n|---|---|\n| 부산 | 1,234 |\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n'
                                            '![가](img/a.svg)\n\n[그림 1] 분기별 가격 범위\n\n![나만](img/b.svg)\n', encoding='utf-8')
            # 문서 정보의 들여 쓴 키(author.name)와 name 은 키로 안 보임, 문서가 없는 폴더를 / 없이 가리킨 링크는 깨짐이 아님 (D62)
            (tables / 'meta.md').write_text('---\nname: meta-doc\nauthor:\n  name: 김\n  team: 리서치\nstatus: 진행 중\n---\n\n'
                                            '# 문서 정보\n\n[자료 폴더](data) · [없는 폴더](nope)\n', encoding='utf-8')
            page.once('dialog', lambda d: d.accept(str(tables)))
            page.click('#lec-btn-open')
            n_tabs(2)
            page.wait_for_selector('#lec-others-list .row[data-path="data"]')
            page.locator('#lec-others-list .row[data-path="data"] [data-toggle]').click()
            page.locator('#lec-others-list .row[data-path="data/prices.csv"]').click()   # 한 번 누르면 Lectern 에서
            page.wait_for_selector('#lec-view.csv-view tbody.csv-rows tr.cv-line')
            csv_state = lambda: page.evaluate("""() => { const v = document.querySelector('#lec-view');
              return { head: [...v.querySelectorAll('.csv-head th[data-col]')].map(th => th.textContent + (th.classList.contains('num') ? '#' : '')),
                rows: v.querySelectorAll('tbody.csv-rows tr.cv-line').length, first: [...(v.querySelector('tbody.csv-rows tr.cv-line')?.cells || [])].map(c => c.textContent),
                count: v.querySelector('.csv-count')?.textContent, info: document.querySelector('#lec-st-info').textContent,
                stats: [...v.querySelectorAll('.csv-stats td')].map(td => td.innerText.replace(/\\n/g, ' ')), statsShown: !v.querySelector('.csv-stats')?.hidden,
                text: [...v.querySelectorAll('.cv-line .cv-text')].map(e => e.textContent).join('|') }; }""")
            c1 = csv_state()
            shot('21-csv')
            page.fill('.csv-filter input[data-col="2"]', '>9800')
            page.fill('.csv-filter input[data-col="1"]', '구리')
            wait_until(page, "document.querySelector('.csv-count').textContent.includes('중')", 3000)
            page.click('.csv-head th[data-col="2"]')
            page.click('.csv-head th[data-col="2"]')   # 두 번 — 내림차순
            page.wait_for_timeout(200)
            c2 = csv_state()
            shot('21-csv-filtered')
            check(c1['head'] == ['월', '품목', '가격#', '비고'] and c1['rows'] == 12 and c1['count'] == '12행' and 'CSV · 12행 · 4열 · 쉼표' in c1['info']
                  and '합계116,170' in c1['stats'][2].replace(' ', '') and '중앙값9,685' in c1['stats'][2].replace(' ', '') and '최빈' not in c1['stats'][0]
                  and c2['count'] == '12행 중 2행' and c2['rows'] == 2 and c2['first'][1:4] == ['2025-10', '구리', '10,240']
                  and '합계20,250' in c2['stats'][2].replace(' ', ''),
                  f"csv 는 표 — 머리행 어림·숫자 열·통계 줄(합계·중앙값), 열마다 거르기(>9800·구리)·머리행으로 내림차순, 통계는 거른 행으로 ({c1['head']}, {c1['count']}, {c2['count']}, {c2['first']})")
            page.locator('#lec-view tbody.csv-rows tr.cv-line').first.click(button='right')
            page.wait_for_selector('#lec-menu:not([hidden])')
            row_hint = page.locator('#lec-menu .menu-row', has_text='이 줄 복사').locator('small').inner_text()
            page.keyboard.press('Escape')
            page.click('.csv-stats-btn')
            stats_off = not csv_state()['statsShown'] and page.evaluate("fetch('/api/config').then(r => r.json()).then(c => c.csv_stats)") is False
            page.click('.csv-stats-btn')
            page.click('.csv-headrow input')   # 첫 줄은 머리행 끄기 → A·B·C·D, 13행
            c3 = csv_state()
            page.click('.csv-headrow input')
            check(row_hint == '2025-10,구리,"10,240",' and stats_off and csv_state()['statsShown'] and c3['head'][:2] == ['A', 'B'] and c3['count'] == '13행',
                  f"표 행의 우클릭 '이 줄 복사'는 원문 줄, '통계' 버튼(설정에 저장), '첫 줄은 머리행' 끄면 A·B… ({row_hint!r}, {stats_off}, {c3['head']}, {c3['count']})")
            enc = {}
            for path in ('data/excel.csv', 'data/memo.txt', 'data/uni.txt'):
                page.locator(f'#lec-others-list .row[data-path="{path}"]').click()
                wait_until(page, f"document.querySelector('#lec-view').dataset.codePath === '{path}' && !!document.querySelector('#lec-view .cv-line')", 8000)
                enc[path] = csv_state()
            page.locator('#lec-tree .row.file[data-doc="README.md"]').click()
            page.wait_for_selector('#lec-view h1:has-text("표 시험")')
            page.locator('#lec-view a', has_text='월별 가격').click()
            by_link = wait_until(page, "document.querySelector('#lec-view').dataset.codePath === 'data/prices.csv' && !!document.querySelector('#lec-view .csv-table')", 8000)
            page.go_back() if False else page.click('#lec-btn-back')
            page.wait_for_selector('#lec-view h1:has-text("표 시험")')
            page.locator('#lec-view a.path-link', has_text='data/prices.csv:5').click()
            to_line = wait_until(page, "!!document.querySelector('#lec-view.csv-view tr.cv-line[data-line=\"5\"].lec-target')", 8000)
            check(enc['data/excel.csv']['head'] == ['지역', '물동량(천톤)#', '증감률#'] and 'CP949' in enc['data/excel.csv']['info']
                  and enc['data/memo.txt']['text'] == '한글 메모 (CP949)|두 번째 줄' and '텍스트 · 2줄' in enc['data/memo.txt']['info'] and 'CP949' in enc['data/memo.txt']['info']
                  and enc['data/uni.txt']['text'] == '유니코드 텍스트' and 'UTF-16' in enc['data/uni.txt']['info'] and by_link and to_line,
                  f"엑셀 CSV(CP949)·CP949·UTF-16 txt 도 읽고, 문서 속 csv 링크·`경로:줄`은 표의 그 행으로 ({enc['data/excel.csv']['head']}, {enc['data/memo.txt']['info']}, {by_link}, {to_line})")
            print('[캡션]')   # D61 — 모아 보기는 캡션을 이름으로, 우클릭은 Claude용 위치·원문 복사와 터미널 버튼
            page.click('.side-tabs button[data-tab="parts"]')
            wait_until(page, "!document.querySelector('#lec-parts-info').textContent.includes('읽는 중') && !!document.querySelector('#lec-parts-list .pt-item')", 15000)
            page.click('#lec-parts-kinds button[data-kind="table"]')
            cap_rows = lambda: page.evaluate('''() => [...document.querySelectorAll('#lec-parts-list :is(.pt-item, .pt-thumb)[data-doc="caps.md"]')]
              .map(e => [e.querySelector('.pt-name, .pt-cap')?.textContent || '', e.querySelector('.pt-label')?.textContent || ''])''')
            cap_tables = cap_rows()
            page.click('#lec-parts-kinds button[data-kind="figure"]')
            wait_until(page, "!!document.querySelector('#lec-parts-list .pt-thumb')", 5000)
            cap_figs = [r[0] for r in cap_rows()]
            page.click('#lec-parts-kinds button[data-kind="table"]')
            page.locator('#lec-parts-list .pt-item[data-doc="caps.md"]').first.click(button='right')
            page.wait_for_selector('#lec-menu:not([hidden]) .menu-row')
            cap_menu = page.evaluate('''() => ({ rows: [...document.querySelectorAll('#lec-menu .menu-row')].map(r => r.querySelector('button[data-i] span').textContent),
              ref: [...document.querySelectorAll('#lec-menu .menu-row')].find(r => r.textContent.includes('Claude용 위치'))?.querySelector('small').textContent,
              terms: document.querySelectorAll('#lec-menu .menu-term').length })''')
            shot('22-parts-caption')
            page.keyboard.press('Escape')
            page.click('#lec-parts-kinds button[data-kind="link"]')
            meta_links = page.evaluate('''() => [...document.querySelectorAll('#lec-parts-list .pt-item[data-doc="meta.md"]')]
              .map(e => [e.querySelector('.pt-name').textContent, e.querySelector('.pt-label')?.textContent || ''])''')
            page.click('#lec-parts-mode button[data-mode="meta"]')
            wait_until(page, "!!document.querySelector('#lec-parts-kinds button[data-mkey]')", 5000)
            nested_keys = page.evaluate("[...document.querySelectorAll('#lec-parts-kinds button[data-mkey]')].map(b => b.dataset.mkey)")
            page.click('#lec-parts-mode button[data-mode="parts"]')
            page.click('.side-tabs button[data-tab="files"]')
            check(cap_tables == [['〈표 Ⅱ-15〉 철재의 HS코드', '표 1 · 1행 2열'], ['표 1. 항만별 물동량', '표 2 · 1행 2열'], ['표 3', 'a·b · 1행 2열']]
                  and cap_figs == ['[그림 1] 분기별 가격 범위', '나만']
                  and cap_menu['rows'][:2] == ['Claude용 위치 복사', '원문 복사'] and cap_menu['ref'] == "@caps.md 3~7행 ('〈표 Ⅱ-15〉 철재의 HS코드')"
                  and cap_menu['terms'] >= 2,
                  f"모아 보기: 캡션(굵은 〈표 Ⅱ-15〉·'표 1.'·그림 아래 [그림 1])이 이름, 없으면 머리행·대체 글. 우클릭은 Claude용 위치(줄·캡션)·원문 복사와 터미널 버튼 "
                  f"({cap_tables}, {cap_figs}, {cap_menu})")
            check(meta_links == [['자료 폴더', '폴더 · data/'], ['없는 폴더', '깨짐자료 · nope']]
                  and {'author.name', 'author.team', 'status'} <= set(nested_keys) and 'name' not in nested_keys,
                  f"모아 보기: 문서가 없는 폴더로 가는 링크는 '폴더'(깨짐 아님), 문서 정보의 들여 쓴 키는 author.name 처럼, name 은 키로 안 보임 ({meta_links}, {nested_keys})")

            print('[담기]')   # D63·D65 — 우클릭 담기, 담기 탭, 보낼 곳은 열린 문서 탭·새 문서, 새 문서(다른 폴더 — 그림 경로를 맞춤)로 보내고 저장, 탭으로 연 문서 끝으로 보내고 버리기
            page.evaluate("async () => (await import('/static/js/nav.js')).navigate({ type: 'doc', path: 'caps.md' })")
            page.wait_for_selector('#lec-view img[alt="가"]')

            def take(selector: str) -> None:
                page.locator(selector).first.click(button='right')
                page.wait_for_selector('#lec-menu:not([hidden])')
                page.locator('#lec-menu button[data-i]', has_text='담기').first.click()

            take('#lec-view table')
            take('#lec-view img[alt="가"]')
            page.click('.side-tabs button[data-tab="basket"]')
            bk = page.evaluate('''() => ({ rows: [...document.querySelectorAll('#lec-basket-list .bk-item .pt-name')].map(e => e.textContent),
              count: document.querySelector('#lec-basket-count').textContent })''')
            page.click('#lec-basket-insert')
            page.wait_for_selector('#lec-insert:not([hidden]) #lec-insert-list li.ins-new')
            targets = page.evaluate('''() => ({ docs: [...document.querySelectorAll('#lec-insert-list li.ins-doc .p')].map(e => e.textContent),
              note: !!document.querySelector('#lec-insert-list li.note') })''')   # 받는 곳은 열린 문서 탭과 새 문서뿐 (D65)
            page.click('#lec-insert-list li.ins-new')
            page.fill('#lec-insert-input', 'data/모음')
            page.keyboard.press('Enter')
            new_doc = tables / 'data' / '모음.md'
            cm_text = lambda: page.evaluate("document.querySelector('.lec-pane.active .lec-editor .CodeMirror').CodeMirror.getValue()")
            wait_until(page, "!!document.querySelector('.lec-pane.active .lec-editor .CodeMirror')?.CodeMirror.getValue().includes('담은 곳')", 10000)
            made_first = new_doc.exists() and new_doc.read_text(encoding='utf-8') == '# 모음\n\n'   # 경로를 정할 때 만들고, 보낸 것은 편집기에만
            new_text = cm_text()
            new_tab = page.evaluate("document.querySelector('#lec-doctab-list .doc-tab.active')?.dataset.path")
            shot('24-basket-new-doc')
            page.keyboard.press('Control+s')
            wait_until(page, "!document.querySelector('.lec-pane.active .lec-editor.dirty')", 5000)
            page.keyboard.press('Escape')
            drawn = wait_until(page, '''(() => { const v = document.querySelector('#lec-view'); const img = v.querySelector('img');
              return !document.querySelector('.lec-pane.active .lec-editor') && v.querySelector('h1')?.textContent === '모음' && !!v.querySelector('table')
                && !!img && img.complete && img.naturalWidth > 0 && !v.innerHTML.includes('담은 곳'); })()''', 10000)
            check(bk['rows'] == ['〈표 Ⅱ-15〉 철재의 HS코드', '[그림 1] 분기별 가격 범위'] and bk['count'] == '2' and targets == {'docs': ['caps.md'], 'note': True}
                  and new_text.startswith('# 모음\n\n<!-- 담은 곳: caps.md 3~7행 -->\n**〈표 Ⅱ-15〉 철재의 HS코드**\n')
                  and '![가](../img/a.svg)' in new_text and '[그림 1] 분기별 가격 범위' in new_text
                  and made_first and new_tab == 'data/모음.md' and new_doc.read_text(encoding='utf-8') == new_text and drawn,
                  f"담기: 우클릭 담기(캡션까지) → 담기 탭 → 보낼 곳은 열린 문서 탭과 새 문서뿐 → 새 문서(data/모음.md)는 경로를 정할 때 만들어 새 문서 탭에서 편집, 그림 경로를 맞춰 저장하면 깨지지 않게 그림 ({bk}, {targets}, {made_first}, {new_tab}, {new_text[:60]!r})")
            page.click('.side-tabs button[data-tab="basket"]')
            page.click('#lec-basket-insert')
            page.fill('#lec-insert-input', 'README')
            page.wait_for_selector('#lec-insert-list li.empty')
            not_open = page.locator('#lec-insert-list li.ins-doc').count() == 0 and page.locator('#lec-insert-list li.note').count() == 1
            page.keyboard.press('Escape')
            page.click('.side-tabs button[data-tab="files"]')
            page.locator('#lec-tree .row[data-doc="README.md"]').click(modifiers=['Control'])   # 문서 탭으로 열어야 받는 곳이 된다
            wait_until(page, "document.querySelector('#lec-doctab-list .doc-tab.active')?.dataset.path === 'README.md'", 10000)
            page.click('.side-tabs button[data-tab="basket"]')
            page.click('#lec-basket-insert')
            page.fill('#lec-insert-input', 'README')
            page.wait_for_selector('#lec-insert-list li.ins-doc')
            page.locator('#lec-insert-list li.ins-doc').first.click()
            page.wait_for_selector('#lec-insert-list li.ins-place')
            page.locator('#lec-insert-list li.ins-place', has_text='맨 끝').click()
            wait_until(page, "document.querySelector('.lec-pane.active .lec-editor')?.dataset.path === 'README.md' || !!document.querySelector('.lec-pane.active .lec-editor .ed-inserted')", 10000)
            readme_before = (tables / 'README.md').read_text(encoding='utf-8')
            readme_text = cm_text()
            inserted = page.locator('.lec-pane.active .lec-editor .ed-inserted').count()
            asked = []
            page.once('dialog', lambda d: (asked.append(d.message), d.accept()))   # 저장하지 않은 것 — 버리고 닫기
            page.keyboard.press('Escape')
            wait_until(page, "!document.querySelector('.lec-pane.active .lec-editor')", 3000)
            check(not_open and readme_text.startswith(readme_before.rstrip('\n') + '\n\n<!-- 담은 곳: caps.md 3~7행 -->') and '![가](img/a.svg)' in readme_text
                  and inserted > 0 and asked and (tables / 'README.md').read_text(encoding='utf-8') == readme_before,
                  f'담기: 문서 탭에 없는 문서는 받는 곳에 없고(안내 줄), 탭으로 열면 맨 끝으로 보내 편집 모드로 (넣은 곳 표시), 저장하지 않고 닫으면 파일은 그대로 ({not_open}, {inserted}, {len(asked)})')

            print('[새로 만들기]')   # D65 — 폴더 우클릭·Ctrl+N·문서 탭 줄의 + : 경로를 정하면 바로 '# 제목'으로 만들어 새 문서 탭에서 편집
            page.click('.side-tabs button[data-tab="files"]')
            page.wait_for_selector('#lec-tree .row[data-dir="data"]')   # data/모음.md 를 만들어 트리에 나온 폴더
            page.locator('#lec-tree .row[data-dir="data"]').click(button='right')
            page.wait_for_selector('#lec-menu:not([hidden])')
            page.locator('#lec-menu button[data-i]', has_text='이 폴더에 새 문서').click()
            page.wait_for_selector('#lec-insert:not([hidden])')
            guess = page.input_value('#lec-insert-input')
            page.keyboard.type('메모')   # 이름 부분을 골라 두었다 — 바로 고쳐 쓴다
            page.keyboard.press('Enter')
            memo = tables / 'data' / '메모.md'
            on_memo = wait_until(page, '''document.querySelector('#lec-doctab-list .doc-tab.active')?.dataset.path === 'data/메모.md'
              && !!document.querySelector('.lec-pane.active .lec-editor .CodeMirror')''', 10000)
            memo_text = memo.read_text(encoding='utf-8') if memo.exists() else None
            cursor = page.evaluate("document.querySelector('.lec-pane.active .lec-editor .CodeMirror')?.CodeMirror.getCursor().line")
            focused = page.evaluate("!!document.activeElement?.closest('.lec-pane.active .lec-editor')")
            in_tree = wait_until(page, "!!document.querySelector('#lec-tree .row[data-doc=\"data/메모.md\"]')", 10000)
            page.keyboard.press('Escape')   # 고치지 않았으니 묻지 않고 닫힌다
            wait_until(page, "!document.querySelector('.lec-pane.active .lec-editor')", 3000)
            page.keyboard.press('Control+n')
            page.wait_for_selector('#lec-insert:not([hidden])')
            ctrl_n = [page.text_content('#lec-insert-title'), page.input_value('#lec-insert-input')]
            page.keyboard.type('메모')
            page.keyboard.press('Enter')   # 같은 이름 — 만들지 않고 까닭을 보인다
            dup = wait_until(page, "!document.querySelector('#lec-insert-msg').hidden && document.querySelector('#lec-insert-msg').classList.contains('bad')", 5000)
            page.keyboard.press('Escape')
            closed_pick = wait_until(page, "document.querySelector('#lec-insert').hidden", 2000)
            page.click('#lec-doctab-new')
            page.wait_for_selector('#lec-palette:not([hidden]) #lec-palette-list li.new-doc')
            first_new = page.evaluate("document.querySelector('#lec-palette-list li[data-i]')?.classList.contains('new-doc')")
            page.click('#lec-palette-list li.new-doc')
            plus_pick = wait_until(page, "!document.querySelector('#lec-insert').hidden && document.querySelector('#lec-insert-title').textContent === '새 문서 만들기'", 3000)
            page.keyboard.press('Escape')
            page.keyboard.press('Control+p')
            page.wait_for_selector('#lec-palette:not([hidden]) #lec-palette-list li[data-i]')
            plain_palette = page.locator('#lec-palette-list li.new-doc').count() == 0
            page.keyboard.press('Escape')
            check(guess == 'data/새 문서.md' and on_memo and memo_text == '# 메모\n\n' and cursor == 2 and focused and in_tree
                  and ctrl_n == ['새 문서 만들기', 'data/새 문서.md'] and dup and closed_pick and first_new and plus_pick and plain_palette,
                  f"새로 만들기: 폴더 우클릭 '이 폴더에 새 문서…'(이름 부분을 골라 둠) → 바로 '# 메모'로 만들어 새 문서 탭에서 편집(커서는 제목 아래), 트리에 나옴. Ctrl+N, 같은 이름은 만들지 않음, 문서 탭 줄의 + 맨 위 '새 문서 만들기…' ({guess}, {memo_text!r}, {cursor}, {focused}, {in_tree}, {ctrl_n}, {dup}, {first_new}, {plus_pick}, {plain_palette})")
            page.click('.side-tabs button[data-tab="files"]')

            print('[이름 바꾸기]')   # D66 — 파일 우클릭 '이름 바꾸기…'·F2: 같은 폴더 안에서 이름만, 보던 문서 탭·담은 조각이 새 이름으로
            page.locator('#lec-tree .row[data-doc="data/메모.md"]').click()
            on_doc = lambda path: wait_until(page, f"document.querySelector('#lec-doctab-list .doc-tab.active')?.dataset.path === '{path}'", 10000)
            on_doc('data/메모.md')
            page.locator('#lec-tree .row[data-doc="data/메모.md"]').focus()
            page.keyboard.press('F2')
            page.wait_for_selector('#lec-rename:not([hidden])')
            sel = page.evaluate("(() => { const i = document.querySelector('#lec-rename-input'); return [i.value, i.selectionStart, i.selectionEnd]; })()")
            shot('26-rename')
            page.keyboard.type('메모-고침')
            page.keyboard.press('Enter')
            doc_moved = on_doc('data/메모-고침.md') and wait_until(page, "!!document.querySelector('#lec-tree .row[data-doc=\"data/메모-고침.md\"]')", 10000)
            disk = (tables / 'data' / '메모-고침.md').exists() and not (tables / 'data' / '메모.md').exists()
            if not page.locator('#lec-others-list .row[data-path="data/memo.txt"]').count():
                page.locator('#lec-others-list .row[data-path="data"] [data-toggle]').click()
            page.locator('#lec-others-list .row[data-path="data/memo.txt"]').click(button='right')
            page.locator('#lec-menu button[data-i]', has_text='이름 바꾸기').click()
            page.fill('#lec-rename-input', 'uni.txt')   # 같은 이름 — 바꾸지 않고 까닭
            page.keyboard.press('Enter')
            dup = wait_until(page, "document.querySelector('#lec-rename-msg').classList.contains('bad') && !document.querySelector('#lec-rename-msg').hidden", 5000)
            page.fill('#lec-rename-input', 'memo-2.txt')
            page.keyboard.press('Enter')
            other_moved = wait_until(page, "document.querySelector('#lec-rename').hidden && !!document.querySelector('#lec-others-list .row[data-path=\"data/memo-2.txt\"]')", 10000)
            check(sel == ['메모.md', 0, 2] and doc_moved and disk and dup and other_moved and (tables / 'data' / 'memo-2.txt').exists() and (tables / 'data' / 'uni.txt').exists(),
                  f"이름 바꾸기: 트리에서 F2(확장자 앞까지 골라 둠) → 보던 문서 탭·트리가 새 이름으로, '자료' 목록 우클릭, 같은 이름은 바꾸지 않음 ({sel}, {doc_moved}, {disk}, {dup}, {other_moved})")

            print('[문서 폭·표 첫 열]')   # D68 — 툴바의 문서 폭(100% 가 스타일 폭, 끝은 '가득'), 첫 열이 여러 줄로 감긴 표는 첫 열을 넓힘
            # 둘째 열은 한 칸만 아주 길어 폭을 다 가져가고, 첫 열은 고르게 중간 길이 — 짧은 둘째 칸 옆의 첫 칸이 행을 높인다
            long_cell = ('공급 충격은 가격에 바로 반영되므로 소식이 나오면 그날 안에 추정치를 고친다. 추정 근거는 출처와 함께 남기고, '
                         '같은 소식이 여러 곳에서 다르게 나오면 가장 이른 원문을 기준으로 삼는다. 숫자를 바꾸면 리서치 문서의 표와 보고서의 숫자를 함께 맞춘다.')
            rows = [('정련 구리 재고 집계, 월말 대조, 기준일 맞추기', '기준일이 거래소마다 다르다', '② 수급팀, 자료 정리'),
                    ('광산 차질 소식 모으기, 영향 추정, 보고서 반영', long_cell, '② 리서치, ③ 최종본 수정'),
                    ('전력망 투자 계획 검토, 각국 발표 다시 보기', '수요 전망의 바탕이다', '①, 리서치(자료함)'),
                    ('가격 전망 모형 계수 갱신, 오차 점검, 결과 기록', '모형은 사람이 고친다', '①, ③ 최종본 구성'),
                    ('보고서 문체·표기 통일, 단위 확인, 출처 줄 정리', '지침은 팀이 정한다', '② 문체 지침(공통)·형식·길이')]
            (tables / 'wide.md').write_text(
                '# 폭 시험\n\n## 할 일 표\n\n| 할 일 | 까닭 | 하는 곳 |\n|---|---|---|\n' + ''.join(f'| {a} | {b} | {c} |\n' for a, b, c in rows)
                + '\n## 보통 표\n\n| 이름 | 설명 |\n|---|---|\n| a | 짧은 설명 |\n'
                '| b | 아주 긴 설명이 들어가는 칸입니다. 이 칸은 내용이 길어서 여러 줄로 감기는 것이 자연스럽습니다. 첫 열은 짧습니다. |\n', encoding='utf-8')
            page.wait_for_selector('#lec-tree .row[data-doc="wide.md"]', timeout=10000)
            page.locator('#lec-tree .row[data-doc="wide.md"]').click()
            page.wait_for_selector('#lec-view h1:has-text("폭 시험")')
            tables_state = lambda: page.evaluate('''() => [...document.querySelectorAll('#lec-view .table-wrap > table')].map(t => {
              const lh = parseFloat(getComputedStyle(t.querySelector('td')).lineHeight);
              const lines = (c) => { const r = document.createRange(); r.selectNodeContents(c); return Math.round(r.getBoundingClientRect().height / lh); };
              // 첫 열 때문에 높은 행 (첫 칸이 3줄 이상이고 다른 칸들보다 많음), 머리행 첫 칸의 줄 수
              const tall = [...t.rows].slice(1).filter(r => lines(r.cells[0]) >= 3 && lines(r.cells[0]) > Math.max(...[...r.cells].slice(1).map(lines))).length;
              return [t.classList.contains('lec-wide1'), tall, lines(t.rows[0].cells[0])]; })''')
            fit = tables_state()
            width = lambda: page.evaluate("[parseFloat(getComputedStyle(document.querySelector('#lec-view')).maxWidth), document.querySelector('#lec-width-reset').textContent]")
            w0 = width()
            page.click('#lec-width-wider')
            w1 = width()
            stored = page.evaluate("import('/static/js/store.js').then(m => m.S.config.doc_width)")
            while not page.evaluate("document.querySelector('#lec-width-wider').disabled"):
                page.click('#lec-width-wider')
            full = width() + [page.evaluate("Math.round(document.querySelector('#lec-view').getBoundingClientRect().width) === document.querySelector('#lec-content').clientWidth")]
            shot('27-doc-width-full')
            page.click('#lec-width-reset')
            page.click('#lec-width-narrower')
            w2 = width()
            page.click('#lec-width-reset')
            w3 = width()
            check(fit[0][:2] == [True, 0] and fit[1] == [False, 0, 1]
                  and w0[1] == '폭 100%' and abs(w1[0] - w0[0] * 1.15) < 1 and w1[1] == '폭 115%' and stored == 1.15
                  and full[1] == '폭 가득' and full[2] and abs(w2[0] - w0[0] * 0.9) < 1 and w2[1] == '폭 90%' and w3 == w0,
                  f"문서 폭: 넓게(115%·설정에 저장)·'가득'은 칸 폭 전체·좁게·누르면 100%, 첫 열 때문에 높은 행이 있는 표만 첫 열을 넓혀 없앰, 머리행 '이름'은 끊지 않음 ({fit}, {w0} → {w1} → {full[1:]} → {w2})")

            tab_el(1).locator('.tab-close').click()   # 시험 표 탭을 닫고 점검 프로젝트로
            n_tabs(1)
            page.wait_for_selector('#lec-view h1')

            print('[문서 탭]')   # D64 — Ctrl+누르기·가운데 버튼으로 새 탭, 열린 문서는 그 탭으로, Alt+n·Ctrl+F4, 편집 상자는 탭마다
            dt = lambda: page.evaluate('''() => [...document.querySelectorAll('#lec-doctab-list .doc-tab')]
              .map(t => (t.classList.contains('active') ? '*' : '') + t.dataset.path)''')   # 이름은 '제목' 버튼에 따라 — 경로로 본다
            on_tab = lambda path: wait_until(page, f"document.querySelector('#lec-doctab-list .doc-tab.active')?.dataset.path === '{path}'", 10000)
            plan_doc = work / 'plans' / '구현-계획.md'
            plan_before = plan_doc.read_bytes()
            d0 = dt()
            page.locator('#lec-tree .row[data-doc="docs/02-수식과-달러.md"]').click(modifiers=['Control'])
            on_tab('docs/02-수식과-달러.md')
            page.locator('#lec-tree .row[data-doc="plans/구현-계획.md"]').click(button='middle')
            on_tab('plans/구현-계획.md')
            d1 = dt()
            shot('25-doctabs')
            page.locator('#lec-tree .row[data-doc="docs/02-수식과-달러.md"]').click()   # 이미 열린 문서 — 그 탭으로
            on_tab('docs/02-수식과-달러.md')
            d2 = dt()
            page.keyboard.press('Alt+1')
            alt1 = on_tab(d0[0].lstrip('*')) if d0 else False
            page.keyboard.press('Alt+3')
            on_tab('plans/구현-계획.md')
            page.click('#lec-btn-edit')
            page.wait_for_selector('.lec-pane.active .lec-editor .CodeMirror')
            page.keyboard.press('Control+End')
            page.keyboard.insert_text('문서 탭')
            dirty_mark = wait_until(page, "!!document.querySelector('#lec-doctab-list .doc-tab.active .dirty')", 3000)
            page.keyboard.press('Alt+1')
            other_clean = wait_until(page, "!document.querySelector('.lec-pane.active .lec-editor')", 3000)
            page.keyboard.press('Alt+3')
            back_in_editor = wait_until(page, "!!document.activeElement?.closest('.lec-pane.active .lec-editor.dirty')", 3000)
            page.once('dialog', lambda d: d.accept())   # 저장하지 않은 편집 — 버리고 닫기
            page.keyboard.press('Escape')
            wait_until(page, "!document.querySelector('.lec-pane.active .lec-editor')", 3000)
            page.keyboard.press('Control+F4')
            page.keyboard.press('Control+F4')
            closed = wait_until(page, "document.querySelectorAll('#lec-doctab-list .doc-tab').length === 1", 5000)
            d3 = dt()
            check(len(d0) == 1 and d1 == [d0[0].lstrip('*'), 'docs/02-수식과-달러.md', '*plans/구현-계획.md'] and d2[1] == '*docs/02-수식과-달러.md' and len(d2) == 3
                  and alt1 and dirty_mark and other_clean and back_in_editor and closed and d3 == d0 and plan_doc.read_bytes() == plan_before,
                  f"문서 탭: Ctrl+누르기·가운데 버튼으로 새 탭(지금 탭 오른쪽), 열린 문서는 그 탭으로, Alt+n, 편집 상자는 탭마다(● — 돌아오면 편집기에 초점), Ctrl+F4 로 닫기 ({d0} → {d1} → {d2} → {d3})")
            # 문서 탭 우클릭은 탭 메뉴 (본문 메뉴가 덮지 않게 — 문서 탭 줄은 #lec-panes 안), 다른 탭에서 편집 중인 파일의 줄로 가면
            # 그 탭의 편집기가 그 줄로 (다시 그리며 편집을 닫거나 버릴지 묻지 않게)
            page.locator('#lec-tree .row[data-doc="plans/구현-계획.md"]').click(modifiers=['Control'])
            on_tab('plans/구현-계획.md')
            page.locator('#lec-doctab-list .doc-tab').first.click(button='right')
            page.wait_for_selector('#lec-menu:not([hidden])')
            tab_menu = page.evaluate("[...document.querySelectorAll('#lec-menu button[data-i]')].map(b => b.textContent)")
            page.keyboard.press('Escape')
            page.click('#lec-btn-edit')
            page.wait_for_selector('.lec-pane.active .lec-editor .CodeMirror')
            page.keyboard.press('Control+Home')
            page.keyboard.insert_text('고침 ')
            page.keyboard.press('Alt+1')
            on_tab(d0[0].lstrip('*'))
            asked = []
            on_dialog = lambda d: (asked.append(d.message), d.dismiss())
            page.once('dialog', on_dialog)
            page.evaluate("import('/static/js/store.js').then(m => m.emit('open', { type: 'doc', path: 'plans/구현-계획.md', line: 5 }))")
            on_tab('plans/구현-계획.md')
            page.remove_listener('dialog', on_dialog)   # 묻지 않았으면 남은 것을 거둔다 — 뒤의 점검에서 같은 창을 두 번 닫으려 하지 않게
            page.wait_for_timeout(300)
            kept = page.evaluate('''(() => { const ed = document.querySelector('.lec-pane.active .lec-editor.dirty .CodeMirror')?.CodeMirror;
              return ed ? [ed.getValue().startsWith('고침 '), ed.getCursor().line + 1] : null; })()''')
            page.evaluate("document.querySelector('.lec-pane.active .lec-editor .CodeMirror').CodeMirror.undo()")
            wait_until(page, "!document.querySelector('.lec-pane.active .lec-editor.dirty')", 3000)
            page.keyboard.press('Escape')
            wait_until(page, "!document.querySelector('.lec-pane.active .lec-editor')", 3000)
            page.keyboard.press('Control+F4')
            wait_until(page, "document.querySelectorAll('#lec-doctab-list .doc-tab').length === 1", 5000)
            check(any('다른 문서 탭 모두 닫기' in m for m in tab_menu) and not any('인쇄' in m for m in tab_menu) and kept == [True, 5] and not asked
                  and plan_doc.read_bytes() == plan_before,
                  f"문서 탭 우클릭은 탭 메뉴, 다른 탭에서 편집 중인 파일의 줄로 가면 묻지 않고 그 편집기가 그 줄로 ({tab_menu[:2]}, {kept}, {asked})")
            # D67 — 사이드바 목록에서 두 번 누르면 새 탭 (지금 탭은 보던 문서로 돌아옴, 새 탭은 뒤로 기록 없음), 오른쪽 끝 ∨ 의 열린 문서 탭 목록, Alt+9
            base = d0[0].lstrip('*')
            panes_of = lambda: page.evaluate('''import('/static/js/store.js').then(({ S }) =>
              S.tab.panes.map(p => [p.current?.path ?? null, p.history.length, p === S.pane]))''')
            page.locator('#lec-tree .row[data-doc="docs/02-수식과-달러.md"]').dblclick()
            on_tab('docs/02-수식과-달러.md')
            wait_until(page, "document.querySelectorAll('#lec-doctab-list .doc-tab').length === 2", 5000)
            for _ in range(100):   # 왼쪽 탭(앞 화면)은 숨은 채 다시 그린다
                twice_panes = panes_of()
                if twice_panes[0][0] == base:
                    break
                page.wait_for_timeout(100)
            twice = dt()
            page.locator('#lec-tree .row[data-doc="docs/02-수식과-달러.md"]').dblclick()   # 이미 열린 문서 — 그 탭 그대로
            page.wait_for_timeout(400)
            again = dt()
            page.click('#lec-doctab-all')
            page.wait_for_selector('#lec-menu:not([hidden])')
            badge = page.text_content('#lec-doctab-all .n')
            listed = page.evaluate('''[...document.querySelectorAll('#lec-menu button[data-i]')]
              .map(b => (b.getAttribute('aria-current') ? '*' : '') + (b.querySelector('small')?.textContent || b.textContent))''')
            shot('25b-doctab-list')
            page.locator('#lec-menu button[data-i]').first.click()
            picked = on_tab(base)
            page.keyboard.press('Alt+9')
            alt9 = on_tab('docs/02-수식과-달러.md')
            page.keyboard.press('Control+F4')
            wait_until(page, "document.querySelectorAll('#lec-doctab-list .doc-tab').length === 1", 5000)
            on_tab(base)
            check(twice == [base, '*docs/02-수식과-달러.md'] and twice_panes[0][0] == base and twice_panes[1][1:] == [1, True] and again == twice
                  and badge == '2' and len(listed) == 3 and listed[0].startswith(base) and listed[1].startswith('*docs/02-수식과-달러.md')
                  and listed[2] == '다른 문서 탭 모두 닫기' and picked and alt9,
                  f"문서 탭: 트리에서 두 번 누르면 새 탭(지금 탭은 보던 문서로, 새 탭은 뒤로 기록 없음 — 열린 문서는 그 탭 그대로), 오른쪽 끝 [2 ∨] 의 열린 문서 탭 목록에서 고르기, Alt+9 마지막 탭 ({twice}, {twice_panes}, {again}, {badge}, {listed})")

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
            # 터미널 자리 (D52): 머리줄 버튼으로 아래 ↔ 오른쪽, 아래면 문서·목차 아래 전체 폭에 높이 조절, 자동이면 창 모양을 따른다
            place = lambda: page.evaluate('''() => { const r = (s) => document.querySelector(s).getBoundingClientRect();
              const term = r('#lec-term'), panes = r('#lec-panes');
              return { below: document.documentElement.classList.contains('term-bottom'), under: term.top >= panes.bottom - 1,
                       wide: term.width > panes.width, h: Math.round(term.height), toc: !document.documentElement.classList.contains('toc-off') }; }''')
            page.click('#lec-term-place')
            wait_until(page, "document.documentElement.classList.contains('term-bottom')")
            p1 = place()
            saved_pos = page.evaluate("fetch('/api/config').then(r => r.json()).then(c => c.terminal_position)")
            handle = page.locator('#lec-term-resizer').bounding_box()
            page.mouse.move(handle['x'] + 200, handle['y'] + 3)
            page.mouse.down()
            page.mouse.move(handle['x'] + 200, handle['y'] - 77, steps=4)
            page.mouse.up()
            p2 = place()
            saved_h = page.evaluate("fetch('/api/config').then(r => r.json()).then(c => c.terminal_height)")
            page.dblclick('#lec-term-resizer')
            page.click('#lec-term-place')
            wait_until(page, "!document.documentElement.classList.contains('term-bottom')")
            p3 = place()
            page.click('#lec-btn-settings')   # 설정 창에서 '자동'으로 되돌린다
            page.check('#lec-settings input[name="terminal_position"][value="auto"]')
            auto_saved = wait_until(page, "fetch('/api/config').then(r => r.json()).then(c => c.terminal_position === 'auto')", 3000)
            page.click('#lec-settings-close')
            size0 = page.viewport_size
            page.set_viewport_size({'width': 900, 'height': 1200})   # 세로로 긴 창 — 자동이면 아래
            auto_below = wait_until(page, "document.documentElement.classList.contains('term-bottom')", 5000)
            page.set_viewport_size(size0)
            auto_side = wait_until(page, "!document.documentElement.classList.contains('term-bottom')", 5000) and auto_saved
            check(p1['below'] and p1['under'] and p1['wide'] and p1['toc'] and saved_pos == 'bottom' and abs(p2['h'] - p1['h'] - 80) <= 3
                  and saved_h and abs(saved_h - p2['h']) <= 3 and not p3['below'] and not p3['under'] and auto_below and auto_side,
                  f"터미널 자리: 머리줄 버튼으로 아래(문서·목차 아래 전체 폭, 목차는 그대로)·높이 조절, 다시 오른쪽, 자동이면 세로로 긴 창에서 아래 ({p1}, {p2}, {saved_h})")
            page.click('#lec-term-restart')
            restarted = wait_until(page, '''![...document.querySelectorAll('#lec-term .term-box:not([hidden]) .xterm-rows > div')]
              .map(r => r.textContent).join('').includes('lecterm')''') and term_has('PS ', 30000)
            check(restarted, '다시 시작 버튼: 셸을 새로 띄움 (화면도 비움)')
            # 시작하다 멈춘 프로그램 (D58): 보안 프로그램(DRM)이 막은 것과 같은 모양 — 셸에서 띄운 프로그램이 일시 정지로 만든 자식.
            # 서버가 STUCK_AFTER(10초) 뒤에 알아채면 머리줄 아래 띠·다시 시작 강조, 모음 칸에 '멈춤', 띠의 다시 시작으로 풀린다
            stuck_py = tmp / 'stuck.py'
            stuck_py.write_text('import os, subprocess, time\n'
                                'cmd = os.path.join(os.environ["SystemRoot"], "System32", "cmd.exe")\n'
                                'subprocess.Popen([cmd, "/c", "exit"], creationflags=4)\n'   # CREATE_SUSPENDED
                                'print("stuck-child", flush=True)\ntime.sleep(120)\n', encoding='utf-8')
            page.keyboard.type(f"& '{sys.executable}' '{stuck_py}'")
            page.keyboard.press('Enter')
            stuck_shown = term_has('stuck-child') and wait_until(page, "!document.querySelector('#lec-term-stuck').hidden", 30000)
            stuck_ui = page.evaluate('''() => ({ text: document.querySelector('#lec-term-stuck-text').textContent,
              attention: document.querySelector('#lec-term-restart').classList.contains('attention') })''')
            shot('10-terminal-stuck')
            page.click('#lec-btn-gather')
            g_stuck = wait_until(page, "!!document.querySelector('#lec-gather .g-tile .g-state.stuck')", 5000)
            page.click('#lec-btn-gather')
            page.click('#lec-term-stuck-restart')
            unstuck = (term_has('PS ', 30000) and wait_until(page, "document.querySelector('#lec-term-stuck').hidden", 5000)
                       and not page.evaluate("document.querySelector('#lec-term-restart').classList.contains('attention')"))
            check(stuck_shown and 'cmd.exe' in stuck_ui['text'] and 'claude --continue' in stuck_ui['text'] and stuck_ui['attention']
                  and g_stuck and unstuck,
                  f"셸에서 띄운 프로그램이 시작하다 멈추면 머리줄 아래 띠와 다시 시작 강조·모음 칸에 '멈춤', 띠의 다시 시작으로 풀림 "
                  f"({stuck_shown}, {stuck_ui}, {g_stuck}, {unstuck})")
            # 우클릭 메뉴의 '터미널에 붙여 넣기' (D51): 복사 항목 옆 버튼 — Enter 없이, 여러 줄이면 묻는다 (PowerShell 프롬프트)
            doc_path = page.inner_text('#lec-st-path')
            page.locator('#lec-view h1').first.click(button='right')
            page.wait_for_selector('#lec-menu:not([hidden])')
            term_btns = page.locator('#lec-menu .menu-term').count()
            page.locator('#lec-menu .menu-row', has_text='Claude용 위치 복사').locator('.menu-term').click()
            pasted = term_has(f'@{doc_path} ')
            in_term = page.evaluate("!!document.activeElement?.closest('#lec-term')")
            told = wait_until(page, "document.querySelector('#lec-toast').textContent.includes('탭의 터미널에 넣었습니다')", 3000)   # 넣었다는 알림
            term_label = page.evaluate("document.querySelector('#lec-menu .menu-term')?.textContent.trim() ?? '(메뉴 닫힘)'")
            page.keyboard.press('Escape')   # 셸의 입력 줄 지우기 (PSReadLine)
            asked = []
            page.once('dialog', lambda dlg: (asked.append(dlg.message), dlg.dismiss()))
            page.locator('#lec-view h1').first.click(button='right')
            page.locator('#lec-menu .menu-row', has_text='이 절 원문 복사').locator('.menu-term').click()
            page.wait_for_timeout(300)
            check(term_btns >= 2 and pasted and in_term and told and asked and '줄을 터미널에 붙여 넣습니다' in asked[0],
                  f"우클릭 메뉴의 복사 항목 옆 터미널 버튼: Claude용 위치를 Enter 없이 터미널에('넣었습니다' 알림), 여러 줄이면 먼저 물음 ({term_btns}, {told}, {asked[:1]})")
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
                       light: document.documentElement.classList.contains('term-light'), worst: Math.round(worst * 100) / 100 }; }''')
            page.click('#lec-term-body')
            page.keyboard.type('Write-Host 흰글자 -ForegroundColor White; Write-Host 회색 -ForegroundColor DarkGray; $n = 42')
            page.keyboard.press('Enter')
            term_has('회색')

            def settled_colors() -> dict:
                """스타일을 바꾸면 터미널은 바탕을 먼저 바꾸고 글자는 한 그림 뒤에 다시 그린다 — 그 사이(바탕만 새 색)를 읽지 않게 3초까지 기다린다"""
                for _ in range(30):
                    c = term_colors()
                    if c['worst'] >= 4.45:
                        return c
                    page.wait_for_timeout(100)
                return c

            use_theme('default')
            c_light = settled_colors()
            use_theme('solarized-dark')
            c_dark = settled_colors()
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

            print('[터미널 모음]')
            def tile_has(name: str, text: str, ms: int = 20000) -> bool:
                try:
                    page.wait_for_function('''([name, t]) => { const tile = [...document.querySelectorAll('.g-tile')]
                        .find(el => el.querySelector('.g-name').textContent === name);
                      return !!tile && [...tile.querySelectorAll('.xterm-rows > div')].map(r => r.textContent).join('').includes(t); }''',
                                           arg=[name, text], timeout=ms)
                    return True
                except Exception:
                    return False
            g_ui = lambda: page.evaluate('''() => ({ on: document.documentElement.classList.contains('gather-on'), hidden: document.querySelector('#lec-gather').hidden,
              pressed: document.querySelector('#lec-btn-gather').getAttribute('aria-pressed'), count: document.querySelector('#lec-gather-count').textContent,
              tiles: [...document.querySelectorAll('.g-tile')].map(t => [t.querySelector('.g-name').textContent, t.querySelector('.g-state').textContent,
                t.querySelector('.xterm') ? 'xterm' : t.querySelector('.g-start') ? 'start' : '']),
              cols: getComputedStyle(document.querySelector('#lec-gather')).gridTemplateColumns.split(' ').length,
              focus: document.activeElement?.closest('.g-tile')?.querySelector('.g-name').textContent || '' })''')
            page.once('dialog', lambda d: d.accept(str(second)))
            page.click('#lec-btn-open')
            n_tabs(2)
            page.locator('#lec-content').focus()
            before = g_ui()
            page.keyboard.press('Control+Shift+Backquote')
            # 칸의 초점은 한 그림 뒤에 간다 (gather.js 의 requestAnimationFrame) — 그것까지 기다린다
            wait_until(page, "document.documentElement.classList.contains('gather-on') && document.querySelectorAll('.g-tile').length === 2"
                             " && !!document.activeElement?.closest('.g-tile')")
            g1 = g_ui()
            shot('11-gather')
            check(before['count'] == '1' and g1['on'] and not g1['hidden'] and g1['pressed'] == 'true' and g1['cols'] == 2
                  and g1['tiles'] == [['samples', '대기', 'xterm'], ['second', '시작 전', 'start']] and g1['focus'] == 'second',
                  f"Ctrl+Shift+` 로 터미널 모음 — 탭마다 칸, 셸이 있으면 그 터미널, 없으면 '터미널 시작' ({before['count']}, {g1})")
            page.locator('.g-tile', has_text='second').locator('.g-start').click()
            started2 = tile_has('second', f'PS {second}>')
            g2 = g_ui()
            check(started2 and g2['count'] == '2' and g2['focus'] == 'second' and g2['tiles'][1][2] == 'xterm',
                  f"칸의 '터미널 시작'으로 그 프로젝트 폴더에서 셸을 띄움, 버튼의 셸 수 ({g2})")
            page.keyboard.press('Control+Tab')
            to_first = g_ui()['focus']
            page.keyboard.press('Control+p')
            no_palette = page.evaluate("document.querySelector('#lec-palette').hidden")
            page.keyboard.press('Backspace')   # 셸 줄에 들어간 ^P 를 지운다
            page.keyboard.type('ping -n 20 127.0.0.1')
            page.keyboard.press('Enter')
            busy = wait_until(page, "[...document.querySelectorAll('.g-tile .g-state')][0].textContent === '실행 중'", 8000)
            page.keyboard.press('Control+c')   # 고른 글이 없으면 셸로 — ping 을 멈춘다
            idle = wait_until(page, "[...document.querySelectorAll('.g-tile .g-state')][0].textContent === '대기'", 8000)
            check(to_first == 'samples' and no_palette and busy and idle,
                  f"칸 안에서 Ctrl+Tab 은 다음 칸, 다른 키는 셸로 (Ctrl+P 도), 프로그램이 돌면 칸 머리에 '실행 중' ({to_first}, {busy}, {idle})")
            page.locator('.g-tile', has_text='second').locator('.g-head').dblclick(position={'x': 150, 'y': 12})
            solo = page.evaluate("[...document.querySelectorAll('.g-tile')].filter(t => t.offsetWidth).map(t => t.querySelector('.g-name').textContent)")
            page.locator('.g-tile.solo .g-solo').click()
            back_grid = page.evaluate("[...document.querySelectorAll('.g-tile')].filter(t => t.offsetWidth).length")
            check(solo == ['second'] and back_grid == 2, f'칸 머리를 두 번 누르면 그 칸만 크게, 버튼으로 다시 모두 ({solo}, {back_grid})')
            page.locator('.g-tile', has_text='second').locator('.g-go').click()
            went = wait_until(page, "!document.documentElement.classList.contains('gather-on') && document.querySelector('.lec-tab.active .name').textContent === 'second'")
            g3 = page.evaluate('''() => ({ panel: !document.querySelector('#lec-term').hidden, title: document.querySelector('#lec-term-title').textContent,
              boxes: document.querySelectorAll('#lec-term-body .term-box').length, gather: document.querySelector('#lec-gather').hidden,
              focus: !!document.activeElement?.closest('#lec-term') })''')
            kept_out = term_has(f'PS {second}>', 3000)
            check(went and g3['panel'] and g3['title'] == 'PowerShell — second' and g3['boxes'] == 2 and g3['gather'] and g3['focus'] and kept_out,
                  f"칸의 '이 프로젝트로' — 모음을 닫고 그 프로젝트의 오른쪽 터미널로 (화면은 패널로 돌아옴, 셸은 그대로) ({g3})")
            page.keyboard.press('Control+Shift+Backquote')
            again = wait_until(page, "document.documentElement.classList.contains('gather-on')")
            page.locator('#lec-tablist .lec-tab', has_text='samples').click()
            left = wait_until(page, "!document.documentElement.classList.contains('gather-on') && document.querySelector('.lec-tab.active .name').textContent === 'samples'")
            check(again and left and h1_has('렌더링 기능 점검'), '프로젝트 탭을 누르면 모음을 닫고 그 프로젝트의 문서 화면으로')
            place = page.evaluate('''() => ({ term: !!document.querySelector('#lec-tabbar #lec-btn-term'), gather: !!document.querySelector('#lec-toolbar #lec-btn-gather') })''')
            page.keyboard.press('Control+Shift+Backquote')
            wait_until(page, "document.documentElement.classList.contains('gather-on')")
            page.click('#lec-btn-term')
            by_term_btn = wait_until(page, '''!document.documentElement.classList.contains('gather-on') && !document.querySelector('#lec-term').hidden
              && document.querySelector('#lec-btn-term').getAttribute('aria-pressed') === 'true'
              && document.querySelector('#lec-term-title').textContent === 'PowerShell — samples' ''')
            check(place['term'] and place['gather'] and by_term_btn,
                  f"터미널 버튼은 탭 막대 끝, 터미널 모음 버튼은 툴바 — 모음에서 터미널 버튼을 누르면 모음을 닫고 이 프로젝트의 터미널 ({place}, {by_term_btn})")
            page.keyboard.press('Control+Shift+Backquote')
            wait_until(page, "document.documentElement.classList.contains('gather-on')")
            page.click('#lec-btn-toc')
            toc_shown = wait_until(page, '''!document.documentElement.classList.contains('gather-on') && !document.documentElement.classList.contains('toc-off')
              && document.querySelector('#lec-btn-toc').getAttribute('aria-pressed') === 'true' && !!document.querySelector('#lec-tabbar #lec-btn-toc')''')
            page.click('#lec-btn-toc')   # 되돌린다 (터미널을 연 동안 목차를 함께 보던 것)
            check(toc_shown and wait_until(page, "document.documentElement.classList.contains('toc-off')"),
                  '목차 버튼도 탭 막대 끝 — 모음에서 누르면 모음을 닫고 목차를 보임, 다시 누르면 감춤')
            tab_el(1).hover()   # 고르지 않은 탭의 × 는 마우스를 올려야 보인다
            tab_el(1).locator('.tab-close').click()
            n_tabs(1)
            page.click('#lec-term-close')

            print('[사용설명서와 단축키]')
            keys = page.locator('#lec-keys')
            manual = page.locator('#lec-help')
            page.click('#lec-btn-help')
            groups = page.evaluate("[...document.querySelectorAll('#lec-keys .keys-group h3')].map(h => h.textContent)")
            caps = page.evaluate("[...document.querySelectorAll('#lec-keys th')].map(th => th.textContent.replace(/\\s/g, ''))")
            by_button = keys.is_visible()
            shot('07b-keys')
            page.keyboard.press('Escape')
            esc_closed = not keys.is_visible()
            page.keyboard.press('Control+/')
            by_key = keys.is_visible()
            page.keyboard.press('Control+/')
            check(by_button and esc_closed and by_key and not keys.is_visible() and len(groups) >= 8
                  and {'Ctrl+P', 'Ctrl+Shift+F', 'F1', 'Ctrl+/', 'Ctrl+`'} <= set(caps),
                  f"툴바 '?' 버튼·Ctrl+/ 로 단축키 표, Esc·Ctrl+/ 로 닫힘 ({len(groups)}묶음, {len(caps)}줄)")
            page.click('#lec-btn-help')
            page.click('#lec-keys-manual')
            page.wait_for_selector('#lec-help-toc a')
            info = page.evaluate('''() => ({ toc: [...document.querySelectorAll('#lec-help-toc a')].map(a => a.textContent),
              keys: !document.querySelector('#lec-keys').hidden, kbd: document.querySelectorAll('#lec-help-view table kbd').length,
              alert: !!document.querySelector('#lec-help-view .alert'), ver: document.querySelector('#lec-help-ver').textContent,
              focus: document.activeElement.id, covers: (() => { const h = document.querySelector('#lec-help').getBoundingClientRect(),
                s = document.querySelector('#lec-sidebar').getBoundingClientRect(); return h.left <= s.left && h.width > s.width * 2; })() })''')
            shot('07c-manual')
            check(manual.is_visible() and not info['keys'] and len(info['toc']) >= 20 and {'단축키', '터미널', '코드 읽기'} <= set(info['toc'])
                  and info['kbd'] >= 40 and info['alert'] and info['ver'] and info['focus'] == 'lec-help-scroll' and info['covers'],
                  f"단축키 표의 '사용설명서 열기' → 사이드바·문서 위를 덮는 설명서, 차례·박스글·단축키 장 ({len(info['toc'])}개, kbd {info['kbd']})")
            page.locator('#lec-help-toc a', has_text='터미널 모음').click()
            jumped = wait_until(page, '''(() => { const h = [...document.querySelectorAll('#lec-help-view h3')].find(h => h.textContent === '터미널 모음');
              const t = h.getBoundingClientRect().top - document.querySelector('#lec-help-scroll').getBoundingClientRect().top; return t >= 0 && t < 40; })()''')
            active = wait_until(page, "document.querySelector('#lec-help-toc a.active')?.textContent === '터미널 모음'")
            check(jumped and active, '설명서 차례를 누르면 그 장으로, 읽는 곳이 차례에 표시됨')
            page.keyboard.press('Control+f')
            page.keyboard.type('Claude용 위치')
            found = wait_until(page, "/^1\\/\\d+$/.test(document.querySelector('#lec-find-count').textContent)")
            where = page.evaluate("document.querySelector('#lec-findbar').parentElement.id")
            page.keyboard.press('Escape')   # 찾기를 닫고
            still = manual.is_visible()
            page.keyboard.press('Escape')   # 설명서를 닫는다
            back_bar = page.evaluate("document.querySelector('#lec-findbar').parentElement.id")
            check(found and where == 'lec-help-scroll' and still and not manual.is_visible() and back_bar == 'lec-content',
                  f'설명서 안에서 Ctrl+F (찾기 막대가 설명서로 갔다가 문서로 돌아옴), Esc 는 찾기 → 설명서 차례로 닫음 ({where} → {back_bar})')
            page.keyboard.press('F1')
            f1 = wait_until(page, "!document.querySelector('#lec-help').hidden")
            page.keyboard.press('Control+p')
            page.fill('#lec-palette-input', '우선순위')
            page.keyboard.press('Enter')
            to_doc = wait_until(page, "document.querySelector('#lec-view h1')?.textContent.includes('우선순위') && document.querySelector('#lec-help').hidden")
            page.keyboard.press('F1')
            again = wait_until(page, "!document.querySelector('#lec-help').hidden")
            page.locator('.lec-tab.active').click()
            by_tab = wait_until(page, "document.querySelector('#lec-help').hidden")
            check(f1 and to_doc and again and by_tab, 'F1 로 설명서, 문서를 열거나(Ctrl+P) 프로젝트 탭을 누르면 닫힘')

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


# 영어 화면 점검 (D46): 영어로만 된 프로젝트를 English 설정으로 열고, 화면 곳곳을 연 뒤 앱 글자에 한글이 남았는지 찾는다.
# 문서·파일 이름이 모두 영어라서, 남은 한글은 번역하지 않은 앱 문구다 (언어 이름 '한국어' 처럼 translate="no" 안은 빼고).
EN_SCAN = r"""() => {
  const HANGUL = /[가-힣]/;
  const skip = (el) => !el || el.closest('[translate="no"], #lec-term-body, .xterm, script, style');
  const bad = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    if (HANGUL.test(n.nodeValue.replaceAll('한국어', '')) && !skip(n.parentElement)) bad.push(n.nodeValue.trim().slice(0, 70));   // 언어 이름은 그대로
  }
  for (const el of document.querySelectorAll('[title], [placeholder], [aria-label], [label]')) {
    if (skip(el)) continue;
    for (const a of ['title', 'placeholder', 'aria-label', 'label']) {
      const v = el.getAttribute(a);
      if (v && HANGUL.test(v)) bad.push(`${a}=${v.slice(0, 70)}`);
    }
  }
  return bad;
}"""


def run_english(headed: bool) -> None:
    from playwright.sync_api import sync_playwright

    tmp = Path(tempfile.mkdtemp(prefix='lectern-smoke-en-'))
    work = tmp / 'demo'
    (work / 'docs').mkdir(parents=True)
    (work / 'code').mkdir()
    (work / 'data').mkdir()
    (work / 'README.md').write_text(
        '# Demo project\n\nA short overview paragraph about copper prices.\n\n## Prices\n\n| Item | Q1 | Q2 |\n|---|---:|---:|\n'
        '| Copper | 10 | 12 |\n| Zinc | 7 | 8 |\n\n## Notes\n\n> [!NOTE]\n> Prices are estimates.\n\n```python\nprint("copper")\n```\n\n'
        'See `code/app.py:2` for the code.\n\n## Summary\n\nCopper goes up.\n', encoding='utf-8')
    (work / 'docs' / 'guide.md').write_text('# Guide\n\n## Part one\n\nFirst part.\n\n## Part two\n\nSecond part about copper.\n', encoding='utf-8')
    (work / 'docs' / 'report.html').write_text('<!doctype html><html><head><meta charset="utf-8"><title>Report</title></head>'
                                               '<body><h1>Report</h1><p>Copper report.</p></body></html>', encoding='utf-8')
    (work / 'code' / 'app.py').write_text('def main():\n    return "copper"\n\n\nclass Shop:\n    pass\n', encoding='utf-8')
    (work / 'data' / 'sample.csv').write_text('item,value\ncopper,1\n', encoding='utf-8')
    cfg = tmp / 'config'
    cfg.mkdir()
    (cfg / 'config.json').write_text('{"language": "en"}', encoding='utf-8')
    port = free_port()
    env = os.environ | {'LECTERN_CONFIG_DIR': str(cfg)}
    server = subprocess.Popen([sys.executable, str(ROOT / 'app.py'), '--browser', '--port', str(port), str(work)],
                              cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f'http://127.0.0.1:{port}/'
    errors: list[str] = []
    found: dict[str, list[str]] = {}
    try:
        wait_http(url + 'api/state')
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not headed)
            context = browser.new_context(viewport={'width': 1440, 'height': 900}, locale='en-US',
                                          permissions=['clipboard-read', 'clipboard-write'])
            page = context.new_page()
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.route('**/api/open-external', lambda r: r.fulfill(status=200, content_type='application/json', body='{"action":"editor"}'))
            shot = lambda name: page.screenshot(path=str(SHOTS / f'{name}.png'))
            scan = lambda where: found.update({where: page.evaluate(EN_SCAN)})

            print('[영어 화면]')
            page.goto(url)
            page.wait_for_selector('#lec-tree .row.file')
            page.wait_for_selector('#lec-view.overview h1')
            ui = page.evaluate('''() => ({ lang: document.documentElement.lang, open: document.querySelector('#lec-btn-palette span').textContent,
              tabs: [...document.querySelectorAll('.side-tabs button')].map(b => b.firstChild.textContent.trim()),
              sub: document.querySelector('.ov-sub').textContent, when: document.querySelector('.ov-files .when')?.textContent })''')
            shot('en-01-overview')
            scan('개요')
            check(ui['lang'] == 'en' and ui['open'] == 'Quick open' and ui['tabs'] == ['Files', 'Recent', 'Search', 'Elements', 'Clip']
                  and ui['sub'] == '3 documents, 1 folder' and ui['when'] == 'just now',
                  f'설정 language: en 이면 화면이 영어 — 툴바·사이드바 탭·개수(복수형)·날짜 ({ui})')
            page.locator('#lec-tree .row.file', has_text='README').click()
            page.wait_for_selector('#lec-view h1:has-text("Demo project")')
            doc = page.evaluate('''() => ({ alert: document.querySelector('#lec-view .alert-title')?.textContent,
              copy: document.querySelector('#lec-view .code-copy')?.textContent, toc: document.querySelector('#lec-toc .toc-head')?.textContent,
              chips: [...document.querySelectorAll('#lec-toc .toc-parts button')].map(b => b.textContent.trim()),
              status: document.querySelector('#lec-st-info').textContent })''')
            scan('문서')
            page.locator('#lec-view p', has_text='overview paragraph').click(button='right')
            page.wait_for_selector('#lec-menu:not([hidden])')
            menu = page.locator('#lec-menu').inner_text()
            scan('본문 우클릭')
            page.keyboard.press('Escape')
            check(doc['alert'] == 'Note' and doc['copy'] == 'Copy' and doc['toc'] == 'Contents' and 'Table 1' in doc['chips']
                  and doc['status'].startswith('Modified') and 'Copy location for Claude' in menu and '@README.md line ' in menu,
                  f'문서: 박스글 이름·코드 복사·목차·구성 요소·상태줄·우클릭 메뉴가 영어 ({doc})')
            page.click('#lec-btn-spot')
            spot = page.evaluate("document.querySelector('#lec-btn-spot').title")
            page.keyboard.press('Escape')
            page.locator('#lec-tree .row.file', has_text='README').click(button='right')
            scan('트리 우클릭')
            page.keyboard.press('Escape')
            page.locator('.lec-tab').first.click(button='right')
            scan('탭 우클릭')
            page.keyboard.press('Escape')
            page.keyboard.press('Control+f')
            page.keyboard.type('copper')
            wait_until(page, "/\\d/.test(document.querySelector('#lec-find-count').textContent)")
            scan('찾기')
            page.keyboard.press('Escape')
            page.keyboard.press('Control+p')
            page.fill('#lec-palette-input', 'app')
            page.wait_for_selector('#lec-palette-list li.code')
            scan('빠른 열기')
            page.keyboard.press('Escape')
            page.keyboard.press('Control+Shift+F')
            page.fill('#lec-search-input', 'copper')
            wait_until(page, "!!document.querySelector('#lec-search-results .sr-group')", 5000)
            search = page.evaluate("document.querySelector('#lec-search-info').textContent")
            scan('검색')
            page.locator('.side-tabs button[data-tab="parts"]').click()
            wait_until(page, "document.querySelectorAll('#lec-parts-list .pt-item').length > 0", 8000)
            parts = page.evaluate("[document.querySelector('#lec-parts-kinds .active')?.textContent, document.querySelector('#lec-parts-info').textContent]")
            scan('모아 보기')
            page.locator('#lec-parts-mode button[data-mode="files"]').click()
            wait_until(page, "!!document.querySelector('#lec-parts-kinds button[data-ftype]')", 8000)
            scan('모아 보기 — 파일 종류')
            page.locator('#lec-parts-mode button[data-mode="parts"]').click()
            page.locator('.side-tabs button[data-tab="recent"]').click()
            wait_until(page, "!!document.querySelector('#lec-recent .row[data-file$=\".py\"]')", 8000)
            scan('최근 변경')
            page.locator('.side-tabs button[data-tab="files"]').click()
            page.locator('#lec-code-list .row[data-path="code"] [data-toggle]').click()
            page.locator('#lec-code-list .row[data-path="code/app.py"]').click()
            page.wait_for_selector('#lec-view.code-view .cv-line')
            code = page.evaluate("[document.querySelector('.cv-editor').textContent, document.querySelector('#lec-st-info').textContent]")
            scan('코드 화면')
            page.locator('#lec-code-list .row[data-path="code/app.py"]').click(button='right')
            scan('코드 우클릭')
            page.keyboard.press('Escape')
            check(spot.startswith('Turn off section focus') and search.startswith('3 documents·1 code file, ')
                  and parts[0].startswith('Tables') and parts[1] == '1 document, 1 table' and code[0] == 'Open in editor',
                  f'영어 글의 복수형·이름 — 장 하이라이트 설명, 검색 개수, 모아 보기 종류·개수, 코드 화면 ({spot[:40]}, {search}, {parts}, {code})')
            page.keyboard.press('Control+Comma')
            lang_radio = page.evaluate("document.querySelector('#lec-settings input[name=\"language\"]:checked')?.value")
            shot('en-02-settings')
            scan('설정 창')
            page.keyboard.press('Escape')
            page.keyboard.press('Control+/')
            shot('en-03-keys')
            scan('단축키 표')
            page.keyboard.press('Escape')
            page.keyboard.press('F1')
            page.wait_for_selector('#lec-help-toc a')
            guide = page.evaluate("[document.querySelector('#lec-help-view h1').textContent, document.querySelectorAll('#lec-help-view table kbd').length]")
            shot('en-04-guide')
            scan('사용설명서')
            page.keyboard.press('Escape')
            page.click('#lec-btn-gather')
            page.wait_for_selector('#lec-gather .g-tile')
            scan('터미널 모음')
            page.click('#lec-btn-gather')
            widths = {}
            for w in (720, 1060):
                page.set_viewport_size({'width': w, 'height': 800})
                page.wait_for_timeout(150)
                widths[w] = page.evaluate('''() => [...document.querySelectorAll('#lec-toolbar, #lec-tabbar, .side-tabs')]
                  .map(el => el.scrollWidth - el.clientWidth)''')
            page.set_viewport_size({'width': 1440, 'height': 900})
            shot('en-05-code')
            leftover = {k: v for k, v in found.items() if v}
            check(not leftover, '영어 화면에 남은 한글 없음 — 개요·문서·우클릭·찾기·빠른 열기·검색·모아 보기·코드·설정·단축키·설명서·터미널 모음'
                  + (f': {leftover}' if leftover else ''))
            check(lang_radio == 'en' and guide[0] == 'Lectern User Guide' and guide[1] >= 40
                  and code[0] == 'Open in editor' and code[1].startswith('Python · 6 lines'),
                  f'설정 창에 English 가 골라져 있고, 영어 사용설명서(단축키 표 포함)·코드 화면 ({lang_radio}, {guide}, {code})')
            check(all(x <= 0 for v in widths.values() for x in v), f'영어 글자로도 툴바·탭 막대·사이드바 탭이 넘치지 않음 (720·1060px: {widths})')
            page.keyboard.press('Control+Comma')
            page.locator('#lec-settings input[name="language"][value="ko"]').check()
            page.wait_for_function("document.documentElement.lang === 'ko'", timeout=10000)
            page.wait_for_selector('#lec-tree .row.file')
            ko = page.evaluate("[document.querySelector('#lec-btn-palette span').textContent, document.querySelector('.side-tabs button').textContent]")
            saved = page.evaluate("fetch('/api/config').then(r => r.json()).then(c => c.language)")
            check(ko == ['문서 열기', '파일'] and saved == 'ko', f'설정 창에서 한국어를 고르면 저장하고 화면을 다시 불러와 한국어로 ({ko}, {saved})')
            browser.close()
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
        shutil.rmtree(tmp, ignore_errors=True)
    check(not errors, '영어 화면 스크립트 오류 없음' + (f': {errors}' if errors else ''))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--headed', action='store_true', help='브라우저 창을 띄워서 실행')
    args = parser.parse_args()
    run(args.headed)
    run_english(args.headed)
    print()
    if failures:
        print(f'실패 {len(failures)}건. 캡처: {SHOTS}')
        sys.exit(1)
    print(f'모두 통과. 캡처: {SHOTS}')


if __name__ == '__main__':
    main()
