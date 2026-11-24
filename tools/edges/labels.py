"""이름과 제목 (D179): 문서 열기(Ctrl+P)·검색 결과·모아 보기도 사이드바의 '제목' 설정을 따른다 (끄면 파일 이름, 켜면 제목).
한 목록에서 같은 글이 둘 이상이면 가르는 말을 흐리게 — 같은 제목이면 파일 이름, 폴더가 보이지 않는 문서 탭에서 같은 이름이면 폴더"""
import json
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop

base = Path(tempfile.mkdtemp(prefix='lec-labels-'))
proj = base / 'proj'
for folder in ('a', 'b', 'c'):
    (proj / folder).mkdir(parents=True)
(proj / 'a' / 'README.md').write_text('# 소개\n\n본문 가나다\n', encoding='utf-8')
(proj / 'b' / 'README.md').write_text('# 소개\n\n본문 가나다\n', encoding='utf-8')
(proj / 'c' / '노트.md').write_text('# 같은 제목\n\n본문 가나다\n', encoding='utf-8')
(proj / 'c' / '메모.md').write_text('# 같은 제목\n\n본문 가나다\n', encoding='utf-8')
(proj / '보고.md').write_text('# 보고서\n\n본문 가나다\n', encoding='utf-8')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)

# 목록의 [글, 가르는 말] — .label(또는 탭의 .name) 안의 .tell 을 떼어
ROWS = """(sel) => [...document.querySelectorAll(sel)].map((el) => { const tell = el.querySelector('.tell');
  const own = [...el.childNodes].filter((n) => n !== tell && !(n.classList && n.classList.contains('ficon'))).map((n) => n.textContent).join('').trim();
  return [own, tell ? tell.textContent : '']; })"""

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1400, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        rows = lambda sel: page.evaluate(ROWS, sel)  # noqa: E731
        tree = lambda folder: rows(f'#lec-tree .row.file[data-doc^="{folder}"] .label')  # noqa: E731

        def palette():
            page.locator('#lec-content').focus()
            page.keyboard.press('Control+p')
            page.wait_for_selector('#lec-palette:not([hidden]) #lec-palette-list li')
            got = page.evaluate("() => [...document.querySelectorAll('#lec-palette-list li .t')].map((el) => [el.textContent.trim(), !!el.querySelector('.tell')])")
            page.keyboard.press('Escape')
            return got

        def search():
            page.click('.side-tabs button[data-tab="search"]')
            page.fill('#lec-search-input', '가나다')
            page.wait_for_selector('#lec-search .sr-doc', timeout=10000)
            page.wait_for_timeout(400)
            return sorted(rows('#lec-search .sr-doc .label'))

        print("[제목 끄기 — 처음 값]")
        for folder in ('a', 'b', 'c'):
            page.locator(f'#lec-tree .row.dir[data-dir="{folder}"]').click()
        expect(page, '트리 — 파일 이름, 같은 폴더의 다른 이름이라 가르는 말 없음', lambda: tree('c/') == [['노트.md', ''], ['메모.md', '']], lambda: tree('c/'))
        got = palette()
        check('문서 열기 — 큰 글이 파일 이름 (경로는 아래 줄), 가르는 말 없음', sorted(x for x, _ in got) == ['README.md', 'README.md', '노트.md', '메모.md', '보고.md']
              and not any(t for _, t in got), got)
        check('검색 결과 — 문서 머리가 파일 이름, 같은 이름은 옆의 폴더가 가른다', search() == [['README.md', ''], ['README.md', ''], ['노트.md', ''], ['메모.md', ''], ['보고.md', '']], search())
        page.click('.side-tabs button[data-tab="files"]')
        page.locator('#lec-tree .row.file[data-doc="a/README.md"]').click()
        page.wait_for_selector('#lec-view h1')
        page.locator('#lec-tree .row.file[data-doc="b/README.md"]').click(modifiers=['Control'])
        expect(page, '문서 탭 — 같은 이름이면 폴더를 흐리게', lambda: sorted(rows('#lec-doctab-list .doc-tab .name')) == [['README.md', 'a'], ['README.md', 'b']],
               lambda: rows('#lec-doctab-list .doc-tab .name'))

        print("[제목 켜기]")
        page.click('#lec-btn-titles')
        expect(page, '트리 — 같은 폴더의 같은 제목에 파일 이름', lambda: sorted(tree('c/')) == [['같은 제목', '노트.md'], ['같은 제목', '메모.md']], lambda: tree('c/'))
        check('— 다른 폴더의 같은 제목은 폴더가 가른다 (가르는 말 없음)', tree('a/') == [['소개', '']] and tree('b/') == [['소개', '']], (tree('a/'), tree('b/')))
        got = palette()
        check('문서 열기 — 큰 글이 제목', sorted(x for x, _ in got) == ['같은 제목', '같은 제목', '보고서', '소개', '소개'], got)
        check('검색 결과 — 제목, 같은 제목은 파일 이름 (이름까지 같으면 옆의 폴더가 가른다)',
              search() == [['같은 제목', '노트.md'], ['같은 제목', '메모.md'], ['보고서', ''], ['소개', ''], ['소개', '']], search())
        expect(page, '문서 탭 — 제목도 이름도 같으면 경로', lambda: sorted(rows('#lec-doctab-list .doc-tab .name')) == [['소개', 'a/README.md'], ['소개', 'b/README.md']],
               lambda: rows('#lec-doctab-list .doc-tab .name'))

        print('[모아 보기 — 파일 종류]')
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('parts', { path: '', mode: 'files' }))")
        page.wait_for_selector('#lec-view.parts-view .parts-list')
        expect(page, '모아 보기의 문서 — 제목, 같은 제목은 파일 이름', lambda: sorted(rows('#lec-view .parts-list .ft-row .label'))[:2] == [['같은 제목', '노트.md'], ['같은 제목', '메모.md']],
               lambda: rows('#lec-view .parts-list .ft-row .label'))
        # '제목' 버튼은 '파일' 탭에만 보인다 — 다른 창에서 바꾼 것처럼 (config-follow 가 하는 일: 설정을 바꾸고 'titles')
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ show_titles: false })).then(() => import('/static/js/store.js')).then((m) => m.emit('titles'))")
        expect(page, "— '제목'을 끄면 바로 파일 이름으로", lambda: ['노트.md', ''] in rows('#lec-view .parts-list .ft-row .label'), lambda: rows('#lec-view .parts-list .ft-row .label'))

        check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
