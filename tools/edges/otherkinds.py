"""'자료' 묶음의 종류별 하위 묶음 (D207) — '문서' 묶음과 같은 짜임.
- 전체 · PDF · Word · PowerPoint · Excel·CSV · 한글(HWP) · 그림 · 기타 — 그 파일이 없는 종류와 '전체' 와 같은 종류는 감춘다. 개수.
- 하위 묶음을 누르면 그 종류만, 폴더는 늘 펼쳐 둔다. 제외 폴더는 '전체' 에만. 누르기·두 번 누르기·우클릭·Enter·Shift+→ 는 '자료' 그대로.
- '문서' 로 옮긴 종류(D206)는 '자료' 의 하위 묶음에서도 사라진다. 거르기 칸. 설정(others_kind)에 남고 다시 켜도 그대로.
- 파일이 생기고 지워지면 개수·묶음이 따른다. 영어."""
import json
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

HERE = Path(__file__).parent
base = Path(tempfile.mkdtemp(prefix='lec-otherkinds-'))
proj = base / '과제'
(proj / '받은 자료' / '그림').mkdir(parents=True)
(proj / '데이터').mkdir()
(proj / 'node_modules' / 'x').mkdir(parents=True)
(proj / '보고서.md').write_text('# 보고서\n', encoding='utf-8', newline='\n')
(proj / '받은 자료' / '기관 보고서.pdf').write_bytes((HERE / 'pdfs' / 'cid.pdf').read_bytes())
(proj / '받은 자료' / '계약서.docx').write_bytes(b'PK\x03\x04 docx')
(proj / '받은 자료' / '발표.pptx').write_bytes(b'PK\x03\x04 pptx')
(proj / '받은 자료' / '공문.hwp').write_bytes(b'\xd0\xcf\x11\xe0 hwp')
(proj / '데이터' / '가격.csv').write_text('월,가격\n1월,9100\n', encoding='utf-8')
(proj / '데이터' / '목록.tsv').write_text('a\tb\n1\t2\n', encoding='utf-8')
(proj / '받은 자료' / '그림' / '도표.png').write_bytes(b'\x89PNG\r\n\x1a\n')
(proj / '받은 자료' / '그림' / '사진.jpg').write_bytes(b'\xff\xd8\xff')
(proj / '데이터' / '메모.txt').write_text('메모\n', encoding='utf-8')
(proj / '받은 자료' / '묶음.zip').write_bytes(b'PK\x05\x06' + b'\x00' * 18)
(proj / 'node_modules' / 'x' / '숨은.pdf').write_bytes(b'%PDF-1.4')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')

KINDS = "() => [...document.querySelectorAll('#lec-others .kind-head')].map((b) => b.dataset.kind + ':' + b.querySelector('.n').textContent)"
ROWS = "() => [...document.querySelectorAll('#lec-others-list .row')].map((r) => (r.classList.contains('dir') ? 'D:' : 'F:') + r.dataset.path)"
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
        page.click('#lec-others-head')

        def kinds():
            return page.evaluate(KINDS)

        def rows():
            return page.evaluate(ROWS)

        def pick(k):
            page.click(f'#lec-others .kind-head[data-kind="{k}"]')
            page.wait_for_timeout(150)

        print("['자료' 의 하위 묶음]")
        got = until(page, lambda: (k := kinds()) and len(k) > 2 and k)
        check('전체 10 · PDF 1 · Word 1 · PowerPoint 1 · Excel·CSV 2 · 한글 1 · 그림 2 · 기타 2 (제외 폴더 안은 세지 않는다)',
              got == ['all:10', 'pdf:1', 'word:1', 'ppt:1', 'excel:2', 'hwp:1', 'image:2', 'etc:2'], got)
        check('처음은 전체 — 제외 폴더도 보인다', 'D:node_modules' in rows(), rows())
        pick('pdf')
        check('PDF: 받은 자료 폴더를 펼친 채 기관 보고서.pdf 만 (제외 폴더 안의 PDF 는 없다)', until(page, lambda: rows() == ['D:받은 자료', 'F:받은 자료/기관 보고서.pdf']), rows())
        order = page.evaluate("() => [...document.querySelector('#lec-others').children].map((e) => e.id || e.className)")
        check('펼친 하위 묶음 바로 아래에 목록, 나머지는 그 아래', order.index('lec-others-kinds-top') < order.index('lec-others-list') < order.index('lec-others-kinds-bottom')
              and page.evaluate("document.querySelector('#lec-others-kinds-top').lastElementChild.dataset.kind") == 'pdf', order)
        page.click('#lec-others-list .row[data-path="받은 자료/기관 보고서.pdf"]')
        check('PDF 를 누르면 PDF 보기', until(page, lambda: page.evaluate(VIEW) == 'doc:받은 자료/기관 보고서.pdf'), page.evaluate(VIEW))
        pick('excel')
        check('Excel·CSV: 가격.csv · 목록.tsv', until(page, lambda: sorted(x for x in rows() if x.startswith('F:')) == ['F:데이터/가격.csv', 'F:데이터/목록.tsv']), rows())
        page.click('#lec-others-list .row[data-path="데이터/가격.csv"]')
        check('csv 를 누르면 표', until(page, lambda: page.evaluate(VIEW) == 'code:데이터/가격.csv'), page.evaluate(VIEW))
        page.focus('#lec-others-list .row[data-path="데이터/목록.tsv"]')
        page.keyboard.press('ArrowUp')
        check('↑ 로 옮겨 다닌다', until(page, "() => document.activeElement?.dataset?.path === '데이터/가격.csv'"), page.evaluate("() => document.activeElement?.dataset?.path"))
        pick('image')
        check('그림: 하위 폴더 그림 안의 둘, 폴더는 펼친 채', until(page, lambda: rows() == ['D:받은 자료', 'D:받은 자료/그림', 'F:받은 자료/그림/도표.png', 'F:받은 자료/그림/사진.jpg']), rows())
        page.click('#lec-others-list .row[data-path="받은 자료/그림"] [data-toggle]')
        page.wait_for_timeout(200)
        check('폴더를 눌러도 접히지 않는다 (늘 펼침)', 'F:받은 자료/그림/도표.png' in rows(), rows())
        pick('etc')
        check('기타: 메모.txt · 묶음.zip', until(page, lambda: sorted(x for x in rows() if x.startswith('F:')) == ['F:데이터/메모.txt', 'F:받은 자료/묶음.zip']), rows())
        page.dblclick('#lec-others-list .row[data-path="받은 자료/묶음.zip"]')
        check('두 번 누르기는 그대로 (압축은 탐색기에서 선택만 — /api/open-external)', until(page, lambda: '받은 자료/묶음.zip' in opened), opened)
        page.click('#lec-others-list .row[data-path="데이터/메모.txt"]', button='right')
        menu = until(page, lambda: page.evaluate("() => [...document.querySelectorAll('#lec-menu button')].map((b) => b.textContent.trim())"))
        check('우클릭은 그대로', any('탐색기에서 보기' in m for m in menu), menu)
        page.keyboard.press('Escape')
        check('설정에 남는다 — others_kind', until(page, lambda: json.loads((config / 'config.json').read_text(encoding='utf-8')).get('others_kind') == 'etc'))

        print('[거르기]')
        pick('word')
        page.fill('#lec-filter', '계약')
        check('거르기 — 그 종류 안에서', until(page, lambda: [x for x in rows() if x.startswith('F:')] == ['F:받은 자료/계약서.docx']), rows())
        page.fill('#lec-filter', '가격')
        check('다른 종류의 것은 걸리지 않는다', until(page, lambda: not [x for x in rows() if x.startswith('F:')]), rows())
        page.fill('#lec-filter', '')

        print("['문서' 로 옮긴 종류는 '자료' 의 하위 묶음에서도 빠진다]")
        page.keyboard.press('Control+Comma')
        page.wait_for_selector('#lec-set-kinds input', timeout=5000)
        page.click('#lec-set-kinds input[data-kind="pdf"]')
        page.click('#lec-set-kinds input[data-kind="word"]')
        page.keyboard.press('Escape')
        check("PDF·Word 하위 묶음이 '자료' 에서 사라지고 전체는 8", until(page, lambda: kinds() == ['all:8', 'ppt:1', 'excel:2', 'hwp:1', 'image:2', 'etc:2']), kinds())
        check('펼쳐 둔 Word 가 사라지면 전체로', until(page, lambda: page.evaluate("() => document.querySelector('#lec-others .kind-head.open')?.dataset.kind") == 'all'))

        print('[파일이 생기고 지워지면]')
        (proj / '받은 자료' / '새 그림.gif').write_bytes(b'GIF89a')
        check('그림 3', until(page, lambda: 'image:3' in kinds(), ms=10000), kinds())
        (proj / '받은 자료' / '발표.pptx').unlink()
        check('PowerPoint 가 없어지면 그 묶음도', until(page, lambda: not any(k.startswith('ppt:') for k in kinds()), ms=10000), kinds())

        print('[다시 켜기]')
        pick('image')
        page.reload()
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        page.click('#lec-others-head')
        check('다시 켜도 그림 묶음', until(page, lambda: page.evaluate("() => document.querySelector('#lec-others .kind-head.open')?.dataset.kind") == 'image' and len([x for x in rows() if x.startswith('F:')]) == 3), (kinds(), rows()))

        print('[영어]')
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ language: 'en' }))")
        page.reload()
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        names = until(page, "() => [...document.querySelectorAll('#lec-others .kind-head span:nth-child(2)')].map((s) => s.textContent)")
        check('영어: All · … · Figures · Other', names and names[0] == 'All' and 'Other' in names and not any('그림' in n or '기타' in n for n in names), names)
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ language: 'ko' }))")
        check('화면 스크립트 오류 없음', not errors, errors[:5])
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
