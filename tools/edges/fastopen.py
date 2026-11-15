"""프로젝트를 빨리 연다 (D140): 첫 트리는 파일 이름으로 바로 그리고 제목은 뒤에서 채운다, 제목 기억은 설정 폴더에만
(본문 없이), 다음 실행은 제목을 기다리지 않는다, 바뀐 문서의 제목은 따라온다, 문서 탭은 40개까지."""
import json
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-fastopen-'))
proj = base / 'proj'
config = base / 'config'
N = 45
for i in range(N):
    d = proj if i < 5 else proj / f'폴더{i % 4}'
    d.mkdir(parents=True, exist_ok=True)
    (d / f'doc-{i:02d}.md').write_text(f'# 문서 {i:02d} 제목\n\n비밀 본문 {i:02d} 입니다.\n', encoding='utf-8')
(proj / 'deck.md').write_text('---\nmarp: true\n---\n\n# 발표 자료\n', encoding='utf-8')
TOTAL = N + 1
BEFORE = sorted(p.relative_to(proj).as_posix() for p in proj.rglob('*'))

# 제목 있는 트리(quick 이 아닌 /api/tree)의 응답을 늦춘다 — 이름으로 먼저 그린 화면을 볼 수 있게
SLOW_FULL = """() => { const real = window.fetch; window.__trees = [];
  window.fetch = async (u, o) => { const s = String(u); const r = await real(u, o);
    if (s.includes('/api/tree')) { window.__trees.push(s.includes('quick=1') ? 'quick' : 'full');
      if (!s.includes('quick=1')) await new Promise((ok) => setTimeout(ok, 1500)); }
    return r; }; }"""
FILES = "import('/static/js/store.js').then(({ S }) => [S.files.length, S.files.filter((f) => f.title).length, S.files.filter((f) => f.deck).length])"
TABS = "() => document.querySelectorAll('#lec-doctab-list .doc-tab').length"
OPEN = "(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: p, newTab: true, force: true }))"


def cache_files():
    return sorted((config / 'cache').glob('titles-*.json')) if (config / 'cache').is_dir() else []


server = None
try:
    with sync_playwright() as p:
        b = p.chromium.launch()

        print('[처음 여는 프로젝트]')
        server, url, port = serve(proj, config)
        page = b.new_page(viewport={'width': 1400, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.add_init_script(f'({SLOW_FULL})()')
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        first = page.evaluate(FILES)
        check('트리는 파일 이름으로 바로 그린다 — 제목은 아직 없다', first[0] == TOTAL and first[1] == 0, first)
        names = page.evaluate("[...document.querySelectorAll('#lec-tree .row.file .label')].map((e) => e.textContent)")
        check('행에는 파일 이름이 보인다', any('doc-00' in x for x in names), names[:6])
        check('제목이 뒤에서 채워진다', until(page, lambda: page.evaluate(FILES)[1] == TOTAL, 15000), page.evaluate(FILES))
        check('슬라이드 표시도 따라온다', page.evaluate(FILES)[2] == 1, page.evaluate(FILES))
        check('첫 트리는 quick, 이어서 제목 있는 트리 한 번', page.evaluate('window.__trees') == ['quick', 'full'], page.evaluate('window.__trees'))
        files = cache_files()
        got = until(page, lambda: len(cache_files()) == 1, 5000)
        files = cache_files()
        text = files[0].read_text(encoding='utf-8') if files else ''
        data = json.loads(text) if text else {}
        check('제목 기억은 설정 폴더의 cache 에 파일 하나', got and len(data.get('docs', {})) == TOTAL, [f.name for f in files])
        check('기억에는 제목과 슬라이드 여부만 — 본문은 없다', '문서 07 제목' in text and '비밀 본문' not in text and data['docs']['deck.md'][3] is True, text[:200])
        check('프로젝트 폴더에는 아무것도 쓰지 않는다', sorted(x.relative_to(proj).as_posix() for x in proj.rglob('*')) == BEFORE)
        page.close()
        server.terminate()
        server.wait(timeout=10)

        print('[다음 실행]')
        server, url, port = serve(proj, config)
        page = b.new_page(viewport={'width': 1400, 'height': 900})
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.add_init_script(f'({SLOW_FULL})()')
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        again = page.evaluate(FILES)
        check('첫 트리에 제목이 다 있다 — 파일을 다시 읽지 않는다', again == [TOTAL, TOTAL, 1], again)
        page.wait_for_timeout(700)
        check('제목 있는 트리를 따로 청하지 않는다', page.evaluate('window.__trees') == ['quick'], page.evaluate('window.__trees'))

        print('[바뀐 문서]')
        (proj / 'doc-00.md').write_text('# 새로 붙인 제목\n\n본문이 달라졌습니다.\n', encoding='utf-8')
        title = "import('/static/js/store.js').then(({ S }) => S.files.find((f) => f.path === 'doc-00.md')?.title)"
        check('바뀐 문서의 제목이 따라온다', until(page, lambda: page.evaluate(title) == '새로 붙인 제목', 10000), page.evaluate(title))
        check('기억도 고친다', until(page, lambda: '새로 붙인 제목' in cache_files()[0].read_text(encoding='utf-8'), 5000))
        (proj / 'doc-01.md').unlink()
        gone = "import('/static/js/store.js').then(({ S }) => S.files.some((f) => f.path === 'doc-01.md'))"
        check('지운 문서는 트리에서 빠진다', until(page, lambda: page.evaluate(gone) is False, 10000))
        check('지운 문서는 기억에서도 빠진다', until(page, lambda: 'doc-01.md' not in json.loads(cache_files()[0].read_text(encoding='utf-8'))['docs'], 5000))

        print('[문서 탭 40개]')
        paths = [f'doc-{i:02d}.md' if i < 5 else f'폴더{i % 4}/doc-{i:02d}.md' for i in range(2, N)]
        page.locator('#lec-tree .row.file').first.click()
        page.wait_for_selector('#lec-view h1')
        opened = page.evaluate(TABS)
        for path in paths[:41]:
            page.evaluate(OPEN, path)
            if opened < 40:
                opened += 1
                until(page, lambda: page.evaluate(TABS) == opened, 5000)
            else:
                page.wait_for_timeout(300)
        check('문서 탭은 40개까지 열린다', page.evaluate(TABS) == 40, page.evaluate(TABS))
        check('차면 가장 오래 안 본 탭에서 열고 알린다', '40개까지' in (page.text_content('#lec-toast') or ''), page.text_content('#lec-toast'))
        check('페이지 오류 없음', not errors, errors[:3])
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    if server:
        stop(server, base)
report()
