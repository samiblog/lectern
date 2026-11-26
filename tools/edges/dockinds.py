"""'문서' 에는 md·html 만, PDF·오피스는 '자료' 에 — 설정에서 켠 종류만 '문서' 로 옮긴다 (D206).
- 기본: '문서' 트리·개수에 PDF 가 없고 하위 묶음 줄도 없다 (md·html 만). '자료' 에 PDF·docx·xlsx·csv·hwp 가 있다.
- '자료' 의 PDF: 한 번 누르면 PDF 보기, 두 번 누르면 기본 앱, 우클릭은 문서 메뉴. 개수에 든다.
- 설정 창에서 PDF 를 켜면 '문서' 의 PDF 하위 묶음으로 옮겨 가고 '자료' 에서 빠진다. Word 를 켜면 docx 가 옮겨 간다. 끄면 돌아온다.
- 머리줄 우클릭으로도. 다시 켜도 그대로. '폴더' 묶음에는 늘 한 번씩. 옛 기본값(오피스 넷)이 적힌 설정은 새 기본값으로 (config.py — tests 에도)."""
import json
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

HERE = Path(__file__).parent
base = Path(tempfile.mkdtemp(prefix='lec-dockinds-'))
proj = base / '과제'
(proj / '보고').mkdir(parents=True)
(proj / '받은 자료').mkdir()
(proj / '보고서.md').write_text('# 보고서\n\n글\n', encoding='utf-8', newline='\n')
(proj / '보고' / '발표.html').write_text('<!doctype html><title>발표</title><h1>발표</h1>', encoding='utf-8')
(proj / '받은 자료' / '기관 보고서.pdf').write_bytes((HERE / 'pdfs' / 'cid.pdf').read_bytes())
(proj / '받은 자료' / '계약서.docx').write_bytes(b'PK\x03\x04 docx')
(proj / '받은 자료' / '가격.csv').write_text('a,b\n1,2\n', encoding='utf-8')
(proj / '받은 자료' / '공문.hwp').write_bytes(b'\xd0\xcf\x11\xe0 hwp')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'version': 3, 'work_alerts': False, 'doc_kinds': ['word', 'ppt', 'excel', 'hwp']}), encoding='utf-8')   # 0.108 을 쓰던 사람 (옛 기본값)

DOCS = "() => [...document.querySelectorAll('#lec-tree .row[data-doc], #lec-tree .row[data-file]')].map((r) => r.dataset.doc || r.dataset.file)"
KINDS = "() => [...document.querySelectorAll('#lec-docs .kind-head')].map((b) => b.dataset.kind)"
OTHERS = "() => import('/static/js/store.js').then(({ S }) => [...S.tab.others.index.files.values()].filter((n) => n.type === 'file').map((n) => n.path).sort())"
FOLDER = "() => import('/static/js/store.js').then(({ S }) => { const out = []; const walk = (ns) => { for (const n of ns) { if (n.type === 'file') out.push(n.path); else if (n.children) walk(n.children); } }; walk(S.tab.others.all || []); return out.sort(); })"
VIEW = "() => import('/static/js/store.js').then(({ S }) => S.view && S.view.type + ':' + S.view.path)"

server, url, port = serve(proj, config)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1300, 'height': 900})
        errors, opened = [], []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.on('request', lambda r: opened.append(json.loads(r.post_data or '{}').get('path')) if r.url.endswith('/api/open-external') else None)
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)

        def others():
            return page.evaluate(OTHERS)

        print('[기본 — 문서에는 md·html 만]')
        check('옛 기본값(오피스 넷)이 적힌 설정은 새 기본값으로', until(page, lambda: page.evaluate("() => import('/static/js/store.js').then(({ S }) => S.config.doc_kinds)") == []))
        page.click('#lec-tree .row[data-dir="받은 자료"]') if page.locator('#lec-tree .row[data-dir="받은 자료"]').count() else None
        check("'문서' 트리: 보고서.md · 보고/발표.html 뿐 (PDF 없음, PDF 만 든 폴더도 없음)", until(page, lambda: sorted(page.evaluate(DOCS)) == ['보고/발표.html', '보고서.md']), page.evaluate(DOCS))
        check('하위 묶음: 전체·문서·HTML 뿐 (PDF·오피스 없음)', page.evaluate(KINDS) == ['all', 'md', 'html'], page.evaluate(KINDS))
        check("'문서' 머리줄의 개수는 2", until(page, lambda: page.inner_text('#lec-docs-count') == '2'), page.inner_text('#lec-docs-count'))
        check("'자료': PDF·docx·csv·hwp 모두", until(page, lambda: others() == ['받은 자료/가격.csv', '받은 자료/계약서.docx', '받은 자료/공문.hwp', '받은 자료/기관 보고서.pdf']), others())
        check("'자료' 개수 4", until(page, lambda: page.inner_text('#lec-others-count') == '4'), page.inner_text('#lec-others-count'))

        print("['자료' 의 PDF]")
        page.click('#lec-others-head')
        page.click('#lec-others-list .row[data-path="받은 자료"] [data-toggle]')
        page.click('#lec-others-list .row[data-path="받은 자료/기관 보고서.pdf"]')
        check('한 번 누르면 PDF 보기', until(page, lambda: page.evaluate(VIEW) == 'doc:받은 자료/기관 보고서.pdf') and page.locator('#lec-view.pdf-view').count() == 1, page.evaluate(VIEW))
        expect(page, '— 그려진다', "() => !!document.querySelector('#lec-view .pdf-pg.drawn')", ms=15000)
        check('보고 있는 PDF 의 행이 강조된다', until(page, "() => document.querySelector('#lec-others-list .row.active')?.dataset.path === '받은 자료/기관 보고서.pdf'"))
        page.dblclick('#lec-others-list .row[data-path="받은 자료/기관 보고서.pdf"]')
        check('두 번 누르면 기본 앱으로', until(page, lambda: '받은 자료/기관 보고서.pdf' in opened), opened)
        page.click('#lec-others-list .row[data-path="받은 자료/기관 보고서.pdf"]', button='right')
        menu = until(page, lambda: page.evaluate("() => [...document.querySelectorAll('#lec-menu button')].map((b) => b.textContent.trim())"))
        check('우클릭은 PDF 문서 메뉴 (새 창에서 열기·기본 앱으로 열기)', any('새 창에서 열기' in m for m in menu) and any('기본 앱으로 열기' in m for m in menu), menu)
        page.keyboard.press('Escape')

        print("[설정에서 PDF·Word 를 '문서' 로]")
        page.keyboard.press('Control+Comma')
        page.wait_for_selector('#lec-set-kinds input', timeout=5000)
        boxes = page.evaluate("() => [...document.querySelectorAll('#lec-set-kinds input')].map((i) => i.dataset.kind + (i.checked ? '+' : '-'))")
        check('설정 창의 칸: PDF·Word·PowerPoint·Excel·CSV·한글 — 모두 꺼짐', boxes == ['pdf-', 'word-', 'ppt-', 'excel-', 'hwp-'], boxes)
        page.click('#lec-set-kinds input[data-kind="pdf"]')
        page.click('#lec-set-kinds input[data-kind="word"]')
        check('config.json 에 pdf·word', until(page, lambda: json.loads((config / 'config.json').read_text(encoding='utf-8')).get('doc_kinds') == ['pdf', 'word']))
        page.keyboard.press('Escape')
        check("'문서' 의 하위 묶음: 전체·문서·HTML·PDF·Word", until(page, lambda: page.evaluate(KINDS) == ['all', 'md', 'html', 'pdf', 'word']), page.evaluate(KINDS))
        check("'자료' 에서 PDF·docx 가 빠진다", until(page, lambda: others() == ['받은 자료/가격.csv', '받은 자료/공문.hwp']), others())
        check("'자료' 개수 2, '문서' 개수 3 (PDF 를 센다)", until(page, lambda: page.inner_text('#lec-others-count') == '2' and page.inner_text('#lec-docs-count') == '3'),
              (page.inner_text('#lec-others-count'), page.inner_text('#lec-docs-count')))
        page.click('#lec-docs-head')
        page.click('#lec-docs .kind-head[data-kind="pdf"]')
        check('PDF 하위 묶음에 기관 보고서.pdf', until(page, lambda: page.evaluate(DOCS) == ['받은 자료/기관 보고서.pdf']), page.evaluate(DOCS))
        page.click('#lec-docs .kind-head[data-kind="word"]')
        check('Word 하위 묶음에 계약서.docx', until(page, lambda: page.evaluate(DOCS) == ['받은 자료/계약서.docx']), page.evaluate(DOCS))
        page.click('#lec-tree .row[data-file="받은 자료/계약서.docx"]', button='right')
        menu = until(page, lambda: page.evaluate("() => [...document.querySelectorAll('#lec-menu button')].map((b) => b.textContent.trim())"))
        check("'문서' 로 옮긴 docx 의 우클릭도 그대로 (탐색기에서 보기)", any('탐색기에서 보기' in m for m in menu), menu)
        page.keyboard.press('Escape')
        check("'폴더' 묶음에는 늘 한 번씩", sorted(page.evaluate(FOLDER)) == ['받은 자료/가격.csv', '받은 자료/계약서.docx', '받은 자료/공문.hwp', '받은 자료/기관 보고서.pdf', '보고/발표.html', '보고서.md'] if page.evaluate("() => import('/static/js/store.js').then(({ S }) => !!S.tab.others.all)") else True,
              page.evaluate(FOLDER))

        print('[머리줄 우클릭으로 되돌리기]')
        page.click('#lec-docs .kind-head[data-kind="all"]', button='right')
        page.locator('#lec-menu').get_by_text('PDF', exact=True).click()
        check('PDF 를 끄면 문서에서 빠지고 자료로 돌아온다', until(page, lambda: 'pdf' not in page.evaluate(KINDS) and '받은 자료/기관 보고서.pdf' in others()), (page.evaluate(KINDS), others()))

        print('[밖에서 PDF 가 생기면]')
        (proj / '보고' / '새 자료.pdf').write_bytes((HERE / 'pdfs' / 'scan.pdf').read_bytes())
        check("꺼져 있으면 '자료' 에 (문서 트리가 바뀌어도 따라온다)", until(page, lambda: '보고/새 자료.pdf' in others(), ms=10000), others())
        check("'문서' 트리에는 없다", '보고/새 자료.pdf' not in page.evaluate(DOCS))

        print('[다시 켜기]')
        page.reload()
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        check('다시 켜도 Word 만 문서에', until(page, lambda: page.evaluate(KINDS) == ['all', 'md', 'html', 'word']), page.evaluate(KINDS))
        check('설정 파일의 판은 4', json.loads((config / 'config.json').read_text(encoding='utf-8')).get('version') == 4)
        check('화면 스크립트 오류 없음', not errors, errors[:5])
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
