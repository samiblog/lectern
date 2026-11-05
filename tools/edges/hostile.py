"""위험한 글자 (D89): 파일 이름과 내용에 HTML 글자가 든 프로젝트로 화면 곳곳을 연다.

html`` 이 지키는 것을 양쪽에서 본다. 값이 태그가 되면 안 되고(구멍), 두 번 이스케이프되어 &amp; 가 보이거나
조각이 글자로 나와도 안 된다(교체 실수). 화면마다 그 글자가 정말 보이는지도 확인한다 — 안 보이면 시험한 것이 아니다.
"""
import sys
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import ROOT, check, fails, report, serve, stop

sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from test_sheet import make_xlsx  # noqa: E402

MARK = '<i data-xss="1">'             # 태그가 되면 [data-xss] 로 잡힌다
SAFE_MARK = '&lt;i data-xss="1"&gt;'  # xml·html 안에 적을 때
NAME = "a&b 'c' #1"                   # Windows 파일 이름에 쓸 수 있는 위험한 글자

base = Path(tempfile.mkdtemp(prefix='lec-hostile-'))
proj = base / "proj & 'x'"
(proj / 'sub & dir').mkdir(parents=True)
BODY = f"""---
title: 앞머리 \\<i data-xss="1"\\> & 'x'
status: {MARK}
tags: [{MARK}, b&c]
---

# 제목 \\<i data-xss="1"\\> & 'x'

첫 문단 \\<i data-xss="1"\\> & "따옴표" 끝.

## 둘째 절 \\<i data-xss="1"\\> &

| 품목 \\<i data-xss="1"\\> | 값 |
|---|---|
| a&b | 1 |

표 1. 캡션 \\<i data-xss="1"\\> & 'x'

![그림 설명 \\<i data-xss="1"\\>](없는-그림&x.png)

- [ ] 할 일 \\<i data-xss="1"\\> &
- [링크 \\<i data-xss="1"\\>](없는-문서&x.md)

> [!NOTE] 박스글 \\<i data-xss="1"\\>
> 내용 &

```python
print("{MARK}")  # a&b
```

```mermaid
{MARK} 틀린 다이어그램 &
```

```vega-lite
{MARK} 틀린 차트 &
```
"""
(proj / f'{NAME}.md').write_text(BODY, encoding='utf-8')
(proj / 'sub & dir' / f'{NAME} 둘.md').write_text(f"# 둘째 문서 \\<i data-xss=\"1\"\\> & 'x'\n\n{NAME} 로 가는 글 \\<i data-xss=\"1\"\\>\n", encoding='utf-8')
(proj / f'{NAME}.py').write_text(f'# 주석 {MARK} a&b\ndef run():\n    return "{MARK}"\n\n\nclass Thing:\n    pass\n', encoding='utf-8')
quoted = lambda v: '"' + v.replace('"', '""') + '"'
table = [['연도', f'품목 {MARK}', "b&c 'x'"], ['2021', MARK, '1'], ['2022', 'a&b', '2'], ['2023', '가, 나', '3']]
(proj / f'{NAME}.csv').write_text(''.join(','.join(map(quoted, row)) + '\n' for row in table), encoding='utf-8')
(proj / f'{NAME}.txt').write_text(f'글 {MARK} a&b\n', encoding='utf-8')
(proj / f'{NAME}.html').write_text(f'<!doctype html><html><head><meta charset="utf-8"><title>쪽 {SAFE_MARK} &amp; x</title></head><body><h1>쪽 {SAFE_MARK}</h1></body></html>', encoding='utf-8')
cell = lambda ref, s: f'<c r="{ref}" t="inlineStr"><is><t>{s}</t></is></c>'
rows = (f'<row r="1">{cell("A1", f"연도 {SAFE_MARK}")}{cell("B1", "a&amp;b")}</row>'
        f'<row r="2"><c r="A2"><v>2021</v></c><c r="B2"><v>1</v></c></row>'
        f'<row r="3"><c r="A3"><v>2022</v></c><c r="B3"><v>2</v></c></row>')
sheet_name = '시트 &amp; ' + SAFE_MARK.replace('"', '&quot;')
make_xlsx(proj / f'{NAME}.xlsx', [(sheet_name, rows, None)])
styles = base / 'config' / 'styles'
styles.mkdir(parents=True)
(styles / 'mine.css').write_text(f'/* lectern-style\n   name: 내 스타일 {MARK} & x\n   dark: no\n*/\n', encoding='utf-8')

server, url, port = serve(proj, base / 'config')

SCAN = r"""() => {
  const near = (text, i) => text.slice(Math.max(0, i - 30), i + 40).replace(/\n/g, ' ');
  const holes = [...document.querySelectorAll('[data-xss]')].map((el) => `${el.parentElement?.id || el.parentElement?.className || el.parentElement?.tagName}`);
  const text = document.body.innerText;
  const entities = [...text.matchAll(/&(amp|lt|gt|quot|#39);/g)].map((m) => near(text, m.index));
  const markup = [...text.matchAll(/<\/?(svg|span|button|div|use|small|li|ul|p|td|tr|th|b|code|a|label|input|section|option)\b/g)].map((m) => near(text, m.index));
  for (const el of document.querySelectorAll('[title], [aria-label], [placeholder]')) {
    for (const v of [el.getAttribute('title'), el.getAttribute('aria-label'), el.getAttribute('placeholder')]) {
      if (v && /&(amp|lt|gt|quot|#39);/.test(v)) entities.push(`속성: ${v.slice(0, 60)}`);
    }
  }
  return { holes, entities, markup };
}"""

try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')

        def settle(ms=350):
            page.wait_for_timeout(ms)

        def scan(name, box=None, shown=None):
            """화면을 살핀다. box 안에 shown 글자가 보여야 시험한 것이다"""
            got = page.evaluate(SCAN)
            seen = True if shown is None else shown in page.locator(box).first.inner_text()
            check(f'{name}: 값이 태그가 되지 않고 이스케이프도 맞음' + ('' if shown is None else ', 글자가 보임'),
                  not got['holes'] and not got['entities'] and not got['markup'] and seen,
                  f"태그 {got['holes'][:3]}, 두 번 {got['entities'][:3]}, 조각 {got['markup'][:3]}, 보임 {seen}")

        def wait(js, ms=6000):
            try:
                page.wait_for_function(js, timeout=ms)
                return True
            except Exception:
                return False

        def show(kind, path):
            page.evaluate(f"import('/static/js/store.js').then(({{ emit }}) => emit('open', {{ type: {kind!r}, path: {path!r} }}))")
            settle(700)

        def side(name):
            page.locator(f'[role=tab][data-tab="{name}"]').click()
            settle()

        def menu(target, name, shown=None):
            target.click(button='right')
            page.wait_for_selector('#lec-menu:not([hidden])', timeout=3000)
            scan(name, '#lec-menu', shown)
            page.keyboard.press('Escape')
            settle(120)

        print('[사이드바]')
        scan('트리와 프로젝트 탭', '#lec-tree', 'a&b')
        check('프로젝트 탭의 이름', "proj & 'x'" in page.locator('#lec-tablist').inner_text(), page.locator('#lec-tablist').inner_text())
        page.locator('#lec-btn-titles').click()
        settle()
        scan('트리의 문서 제목', '#lec-tree', 'data-xss')
        page.locator('#lec-btn-titles').click()
        settle()
        menu(page.locator('#lec-tree .row.file').first, '트리 우클릭 메뉴', 'a&b')
        menu(page.locator('#lec-tablist [role=tab]').first, '프로젝트 탭 우클릭 메뉴', "proj & 'x'")

        print('[문서]')
        page.locator(f'#lec-tree .row.file[data-doc="{NAME}.md"]').click()
        page.wait_for_selector('#lec-view h1')
        settle(1200)
        scan('문서·목차·문서 탭', '#lec-view', 'data-xss')
        check('목차의 제목', 'data-xss' in page.locator('#lec-toc').inner_text(), page.locator('#lec-toc').inner_text()[:200])
        check('문서 탭의 이름', 'a&b' in page.locator('#lec-doctab-list').inner_text(), page.locator('#lec-doctab-list').inner_text())
        check('앞머리 값', 'data-xss' in page.locator('#lec-view .lec-frontmatter, #lec-view .front-matter, #lec-view dl, #lec-view table').first.inner_text(), '')
        check('틀린 다이어그램·차트의 알림', page.locator('#lec-view pre code', has_text='틀린 다이어그램').count() + page.locator('#lec-view pre', has_text='틀린 차트').count() >= 2,
              page.locator('#lec-view').inner_text()[-300:])
        menu(page.locator('#lec-view h2').first, '문서 우클릭 메뉴')
        menu(page.locator('#lec-doctab-list [role=tab]').first, '문서 탭 우클릭 메뉴')

        print('[찾기]')
        page.keyboard.press('Control+p')
        page.wait_for_selector('#lec-palette:not([hidden])')
        page.keyboard.type('a&b')
        settle(400)
        scan('문서 열기', '#lec-palette-list', 'a&b')
        page.keyboard.press('Escape')
        settle(150)
        side('search')
        page.locator('#lec-search-input').fill('data-xss')
        wait("document.querySelectorAll('#lec-search-results li, #lec-search-results .row, #lec-search-results a').length > 0")
        settle(600)
        scan('본문 검색 결과', '#lec-search-results', 'data-xss')
        page.locator('#lec-search-input').fill('a&b')
        settle(800)
        scan('이름으로 찾은 검색 결과', '#lec-search-results', 'a&b')

        print('[최근 변경·모아 보기·담기]')
        side('recent')
        scan('최근 변경', '#lec-recent', 'a&b')
        side('parts')
        wait("document.querySelectorAll('#lec-parts-kinds button').length > 0")
        settle(800)
        for i in range(page.locator('#lec-parts-kinds button').count()):
            button = page.locator('#lec-parts-kinds button').nth(i)
            label = button.inner_text().replace('\n', ' ')
            if button.is_disabled():
                continue
            button.click()
            settle(500)
            scan(f'모아 보기 {label}')
            if not label.endswith(' 0'):   # 이 프로젝트에 없는 종류는 비어 있다
                check(f'모아 보기 {label}: 목록이 그려짐', page.locator('#lec-parts-list').inner_text().strip() != '', label)
        page.locator('[data-mode="meta"]').click()
        settle(700)
        for i in range(page.locator('#lec-parts-kinds button').count()):
            page.locator('#lec-parts-kinds button').nth(i).click()
            settle(350)
            scan('앞머리 ' + page.locator('#lec-parts-kinds button').nth(i).inner_text().replace('\n', ' '))
        page.locator('[data-mode="files"]').click()
        settle(700)
        scan('파일 종류', '#lec-parts-list', 'a&b')
        page.evaluate("""async (name) => {
          const b = await import('/static/js/basket.js');
          b.addSnippets([b.snippetOf({ path: name, lines: ['<i data-xss="1"> & x'] }, [1, 1], { kind: 'block', name: '<i data-xss="1">', label: '<i data-xss="1"> & x' })]);
        }""", f'{NAME}.md')
        side('basket')
        scan('담기', '#lec-basket-list', 'data-xss')
        menu(page.locator('#lec-basket-list li, #lec-basket-list .row, #lec-basket-list > *').first, '담은 것의 우클릭 메뉴')

        print('[폴더 개요]')
        show('overview', '')
        scan('폴더 개요', '#lec-view', 'a&b')
        show('overview', 'sub & dir')
        scan('하위 폴더 개요', '#lec-view', 'a&b')

        print('[코드·자료]')
        show('code', f'{NAME}.py')
        wait("!!document.querySelector('#lec-view .cv-title')")
        settle(500)
        scan('코드 화면', '#lec-view', 'data-xss')
        check('코드의 목차', 'run' in page.locator('#lec-toc').inner_text(), page.locator('#lec-toc').inner_text()[:100])
        show('code', f'{NAME}.txt')
        scan('글 파일', '#lec-view', 'data-xss')
        show('code', f'{NAME}.csv')
        wait("!!document.querySelector('#lec-view .csv-table')")
        settle(500)
        scan('CSV 표', '#lec-view', 'data-xss')
        menu(page.locator('#lec-view .csv-head th[data-col]').nth(1), '열 머리 메뉴')
        page.locator('#lec-view .csv-chart').click()
        wait("!document.querySelector('#lec-chart').hidden")
        settle(700)
        scan('차트 창', '#lec-chart', 'a&b')
        page.keyboard.press('Escape')
        settle(200)
        show('code', f'{NAME}.xlsx')
        wait("!!document.querySelector('#lec-view .csv-table')")
        settle(700)
        scan('엑셀 표와 시트 탭', '#lec-view', 'data-xss')

        print('[없는 파일]')
        show('doc', 'x&y <i data-xss="1">.md')
        scan('없는 문서', '#lec-view', 'x&y')
        show('code', 'x&y <i data-xss="1">.py')
        scan('없는 코드 파일', '#lec-view', 'x&y')

        print('[html 문서]')
        side('files')
        page.locator(f'#lec-tree .row.file[data-doc="{NAME}.html"]').click()
        wait("!!document.querySelector('iframe.lec-html')", 8000)
        settle(900)
        scan('html 문서의 머리줄·탭')

        print('[설정·보기]')
        page.keyboard.press('Control+,')
        settle(500)
        scan('설정 창')
        options = page.locator('#lec-theme option').all_inner_texts()
        check('내 스타일 이름', any('data-xss' in o for o in options), options[-3:])
        page.keyboard.press('Escape')
        settle(200)
        page.locator('#lec-doctab-spread').click()
        settle(800)
        scan('모두 펼치기')
        page.locator('#lec-doctab-spread').click()
        settle(400)
        page.locator('#lec-btn-gather').click()
        settle(800)
        scan('터미널 모음', '#lec-gather', "proj & 'x'")
        page.locator('#lec-btn-gather').click()
        settle(300)

        check('화면 스크립트 오류 없음', not errors, errors[:3])
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
