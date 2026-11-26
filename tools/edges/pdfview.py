"""PDF 보기 (D201): 사이드바 '문서'의 PDF 묶음, 문서 탭에 pdf.js 로 — 보이는 쪽만 그림, 지금 쪽, 쪽 칸·Home·End, 확대·폭 맞춤, 책갈피 목차,
찾기(Ctrl+F — 모든 쪽), 고른 글 담기(담은 곳은 그 쪽)와 그 쪽으로 돌아가기, Shift+→ 로 '@경로 N쪽', 우클릭, 보기만(편집·삭제 없음),
글꼴을 넣지 않은 한글(CMap), 스캔 PDF, 스크립트·바깥 링크가 든 PDF, 깨진 PDF·암호, 밖에서 바뀜, 다시 켜기, 영어 화면.
작은 시험용 PDF 셋은 tools/edges/pdfs 에 있고 300쪽 보고서는 Chromium 으로 그때 만든다 (Lectern 의 'PDF로 저장' 과 같은 길)."""
import json
import shutil
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

HERE = Path(__file__).parent
base = Path(tempfile.mkdtemp(prefix='lec-pdfview-'))
proj = base / '자료함'
(proj / '보고서').mkdir(parents=True)
for n in ('cid', 'scan', 'script'):
    shutil.copy(HERE / 'pdfs' / f'{n}.pdf', proj / '보고서' / f'{n}.pdf')
(proj / '보고서' / '깨짐.pdf').write_bytes(b'%PDF-1.7\nnot really a pdf\n')
(proj / '메모.md').write_text('# 메모\n\n글\n', encoding='utf-8', newline='\n')
(proj / '자료.csv').write_text('a,b\n1,2\n', encoding='utf-8')
CLIPS = proj / '.lectern' / 'clips'
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'version': 4, 'doc_kinds': ['pdf'], 'work_alerts': False}), encoding='utf-8')

OPEN = "(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: p }))"
ST = "() => import('/static/js/store.js').then(({ S }) => S.pane.pdf ? { cur: S.pane.pdf.cur, pages: S.pane.pdf.doc?.numPages || 0, scale: Math.round(S.pane.pdf.scale * 100), fit: S.pane.pdf.fit, drawn: [...S.pane.pdf.drawn.keys()] } : null)"
TOAST = "() => { const e = document.querySelector('#lec-toast'); return e && !e.hidden ? e.textContent : ''; }"
LAYER = "(n) => [...document.querySelectorAll(`#lec-view .pdf-pg[data-n=\"${n}\"] .textLayer span`)].map((e) => e.textContent).join('')"


def make_report():
    """300쪽 한글 보고서 — 절마다 책갈피, 쪽마다 표 (Chromium 의 PDF)"""
    secs = []
    for i in range(1, 301):
        rows = ''.join(f'<tr><td>{q}Q</td><td>{9000 + i * 7 + q}</td></tr>' for q in range(1, 5))
        secs.append(f'<h1>{i}. 구리 시장 {i}절</h1><p>{i}절 본문입니다. 2분기 구리 가격은 LME 재고 감소와 함께 올랐다.</p>'
                    f'<table border="1"><caption>표 {i}. 분기별 가격</caption>{rows}</table><p>자료: LME</p><p>{"긴 문단을 이어 쓴다. " * 30}</p>'
                    f'{"<p><a href=\"https://example.com/source\">출처 누리집</a></p>" if i == 2 else ""}<div style="page-break-after:always"></div>')
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.set_content('<!doctype html><meta charset="utf-8"><style>body{font:11pt "Malgun Gothic"}</style>' + ''.join(secs))
        pg.pdf(path=str(proj / '보고서' / '구리 보고서.pdf'), format='A4', outline=True, tagged=True)
        b.close()


make_report()
server, url, port = serve(proj, config)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 1360, 'height': 900}, permissions=['clipboard-read', 'clipboard-write'])
        page = ctx.new_page()
        errors, outside, dialogs = [], [], []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.on('request', lambda r: outside.append(r.url) if not r.url.startswith(url) and not r.url.startswith(('data:', 'blob:')) else None)
        page.on('dialog', lambda d: (dialogs.append(d.message), d.dismiss()))

        def start():
            page.goto(url)
            page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
            page.wait_for_timeout(500)
            page.evaluate("""() => import('/static/js/store.js').then((m) => { window.__pasted = []; window.__opened = [];
              m.on('term-paste', (d) => window.__pasted.push(typeof d === 'string' ? d : d.text)); window.open = (u) => { window.__opened.push(u); return null; }; })""")

        def st():
            return page.evaluate(ST)

        def open_pdf(path):
            page.evaluate(OPEN, path)
            page.wait_for_selector('#lec-view.pdf-view .pdf-pg.drawn, #lec-view.pdf-failed', timeout=30000)
            page.wait_for_timeout(300)

        start()
        print('[사이드바]')
        rows = page.evaluate("() => [...document.querySelectorAll('#lec-tree .row.file')].map((e) => [e.dataset.doc, !!e.querySelector('.ficon.pdf')])")
        check("PDF 는 '문서' 트리에 — PDF 아이콘", sorted(r[0] for r in rows if r[1]) == sorted(f'보고서/{n}' for n in ('cid.pdf', '구리 보고서.pdf', '깨짐.pdf', 'scan.pdf', 'script.pdf')), rows)
        kinds = page.evaluate("() => [...document.querySelectorAll('#lec-files .kind-head, #lec-tree .kind-row, .docs-kind')].map((e) => e.textContent.replace(/\\s+/g, ''))")
        check("'문서' 묶음의 하위 묶음 PDF 5", 'PDF5' in kinds, kinds)
        others = page.evaluate("() => import('/static/js/api.js').then((m) => m.getJSON('/api/others?p=' + encodeURIComponent(document.querySelector('.lec-tab.active')?.dataset.id || '')).catch(() => null))")
        check("'자료' 목록에는 없다 (서버)", others is None or not any(str(f).endswith(".pdf'") for f in json.dumps(others, ensure_ascii=False).split(',') if '.pdf' in f), str(others)[:200])

        print('[300쪽 보고서]')
        t0 = time.monotonic()
        page.locator('#lec-tree .row[data-doc="보고서/구리 보고서.pdf"]').click()
        page.wait_for_selector('#lec-view.pdf-view .pdf-pg[data-n="1"].drawn', timeout=30000)
        took = time.monotonic() - t0
        s = st()
        check(f'열기 {took:.1f}초 — 300쪽, 폭 맞춤', s['pages'] == 300 and s['fit'] and s['cur'] == 1 and took < 6, (s, took))
        check('그린 쪽은 보이는 근처만', len(s['drawn']) <= 6, s['drawn'])
        check('상태줄에 지금 쪽', 'PDF · 1/300쪽' in page.inner_text('#lec-status'), page.inner_text('#lec-status')[:120])
        check('글 층에 한글', '2분기 구리 가격은 LME 재고 감소와 함께 올랐다' in page.evaluate(LAYER, 1), page.evaluate(LAYER, 1)[:80])
        expect(page, '책갈피 300개가 목차에', lambda: page.locator('#lec-toc a[data-i]').count() == 300 and page.inner_text('#lec-toc .toc-head') == '책갈피', lambda: page.inner_text('#lec-toc')[:100])
        check('상태줄의 편집 단추는 없다', page.locator('#lec-st-edit').is_hidden())
        page.locator('#lec-toc a[data-i]').nth(156).click()
        expect(page, '책갈피를 누르면 그 쪽으로', lambda: st()['cur'] == 157 and '157절 본문입니다' in page.evaluate(LAYER, 157), st)
        page.fill('#lec-view .pdf-page', '250')
        page.keyboard.press('Enter')
        expect(page, '쪽 칸에 적고 Enter', lambda: st()['cur'] == 250 and page.evaluate("() => document.querySelector('#lec-view .pdf-page').value") == '250', st)
        page.keyboard.press('End')
        expect(page, 'End 는 마지막 쪽', lambda: st()['cur'] == 300, st)
        page.keyboard.press('Home')
        expect(page, 'Home 은 첫 쪽', lambda: st()['cur'] == 1, st)
        page.keyboard.press('PageDown')
        page.keyboard.press('PageDown')
        expect(page, 'PageDown 으로 넘긴다', lambda: st()['cur'] >= 2, st)
        s0 = st()['scale']
        page.click('#lec-view [data-act="in"]')
        expect(page, '크게 — 폭 맞춤이 풀린다', lambda: st()['scale'] > s0 and not st()['fit'], st)
        cur = st()['cur']
        page.keyboard.press('Control+0')
        expect(page, 'Ctrl+0 은 폭 맞춤 — 보던 쪽 그대로', lambda: st()['fit'] and st()['scale'] == s0 and abs(st()['cur'] - cur) <= 1, st)
        page.keyboard.press('Control+-')
        expect(page, 'Ctrl+- 작게', lambda: st()['scale'] < s0, st)
        page.keyboard.press('Control+0')
        page.set_viewport_size({'width': 1000, 'height': 800})
        expect(page, '폭 맞춤이면 창 폭을 따른다', lambda: st()['fit'] and st()['scale'] < s0, st)
        page.set_viewport_size({'width': 1360, 'height': 900})
        page.wait_for_timeout(500)

        print('[찾기]')
        page.keyboard.press('Control+f')
        page.keyboard.type('157절 본문')
        expect(page, 'Ctrl+F 는 모든 쪽에서 — 그 쪽으로 가서 표시', lambda: page.inner_text('#lec-find-count') == '1/1' and st()['cur'] == 157
               and page.evaluate("() => CSS.highlights.has('lec-find-current')"), lambda: (page.inner_text('#lec-find-count'), st()), ms=15000)
        page.fill('#lec-find-input', '구리 시장 29')
        expect(page, '여럿 (29·290~299절)', lambda: page.inner_text('#lec-find-count') == '1/11', lambda: page.inner_text('#lec-find-count'))
        page.keyboard.press('Enter')
        expect(page, 'Enter 는 다음 것으로', lambda: page.inner_text('#lec-find-count') == '2/11' and st()['cur'] == 290, lambda: (page.inner_text('#lec-find-count'), st()))
        page.fill('#lec-find-input', '없는말없는말')
        expect(page, '없으면 없음', lambda: page.inner_text('#lec-find-count') == '없음')
        page.keyboard.press('Escape')

        print('[담기·위치]')
        page.evaluate("() => import('/static/js/store.js').then(({ S }) => { const st = S.pane.pdf; })")
        page.locator('#lec-toc a[data-i]').nth(1).click()
        expect(page, '2쪽', lambda: st()['cur'] == 2 and '2절 본문입니다' in page.evaluate(LAYER, 2))
        span = page.locator('#lec-view .pdf-pg[data-n="2"] .textLayer span', has_text='2절 본문입니다').first
        box = span.bounding_box()
        page.mouse.move(box['x'] + 2, box['y'] + box['height'] / 2)
        page.mouse.down()
        page.mouse.move(box['x'] + box['width'] - 2, box['y'] + box['height'] / 2, steps=10)
        page.mouse.up()
        page.keyboard.press('Alt+c')
        expect(page, '고른 글을 Alt+C 로 담는다 — 담은 곳은 그 쪽', lambda: CLIPS.exists() and any('page=2' in f.read_text(encoding='utf-8') and '2절 본문입니다' in f.read_text(encoding='utf-8') for f in CLIPS.glob('*.md')),
               lambda: [f.read_text(encoding='utf-8')[-300:] for f in CLIPS.glob('*.md')] if CLIPS.exists() else page.evaluate(TOAST))
        check('알림', '담았습니다' in page.evaluate(TOAST), page.evaluate(TOAST))
        page.click('.side-tabs button[data-tab="basket"]')
        page.locator('#lec-basket-list .bk-box .caret').first.click()
        tip = page.locator('#lec-basket-list .bk-item').first.get_attribute('title')
        check('사이드바의 조각 — 담은 곳에 쪽', '보고서/구리 보고서.pdf · 2쪽' in tip, tip)
        page.locator('#lec-basket-list .bk-box').first.click()
        page.wait_for_selector('#lec-view.clips-view .cb-card')
        check('펼친 화면의 출처 줄', page.inner_text('#lec-view .cb-go').startswith('보고서/구리 보고서.pdf 2쪽'), page.inner_text('#lec-view .cb-go'))
        page.locator('#lec-view .cb-go').first.click()
        page.wait_for_selector('#lec-view.pdf-view .pdf-pg.drawn', timeout=20000)
        expect(page, '출처 줄을 누르면 그 PDF 의 그 쪽으로 (열려 있던 탭)', lambda: st() and st()['cur'] == 2 and page.evaluate("() => document.querySelector('#lec-doctab-list .doc-tab.active .name').textContent") == '구리 보고서.pdf', st)
        page.locator('#lec-doctab-list .doc-tab', has_text='담기함').click()
        page.wait_for_selector('#lec-view.clips-view .cb-card', timeout=15000)
        page.locator('#lec-view .cb-card').first.locator('.cb-src').click(button='right', position={'x': 400, 'y': 6})
        page.locator('#lec-menu button[data-i]', has_text='문서로 보내기').click()
        page.wait_for_selector('#lec-insert:not([hidden]) li.ins-new')
        page.click('#lec-insert-list li.ins-new')
        page.fill('#lec-insert-input', '모음')
        page.keyboard.press('Enter')
        until(page, lambda: (proj / '모음.md').exists() and '담은 곳' in (proj / '모음.md').read_text(encoding='utf-8'), 10000)
        made = (proj / '모음.md').read_text(encoding='utf-8') if (proj / '모음.md').exists() else ''
        check('보내면 담은 곳이 그 쪽으로 적힌다', '<!-- 담은 곳: 보고서/구리 보고서.pdf 2쪽 -->' in made and '2절 본문입니다' in made, made[:300])
        page.click('.side-tabs button[data-tab="files"]')
        open_pdf('보고서/구리 보고서.pdf')
        page.locator('#lec-toc a[data-i]').nth(11).click()
        expect(page, '12쪽', lambda: st()['cur'] == 12)
        page.locator('#lec-content').focus()
        page.keyboard.press('Shift+ArrowRight')
        expect(page, "Shift+→ 는 '@경로 N쪽' 을 터미널로 (Enter 없이)", lambda: page.evaluate('() => window.__pasted') == ['@보고서/구리 보고서.pdf 12쪽 '], lambda: page.evaluate('() => window.__pasted'))
        until(page, lambda: page.locator('#lec-term').is_visible(), 5000)
        page.click('#lec-btn-term')
        page.locator('#lec-content').focus()
        page.keyboard.press('Shift+ArrowLeft')
        expect(page, 'Shift+← 는 복사', lambda: page.evaluate('() => navigator.clipboard.readText()') == '@보고서/구리 보고서.pdf 12쪽', lambda: page.evaluate('() => navigator.clipboard.readText()'))

        print('[우클릭·보기만]')
        page.locator('#lec-view .pdf-pg[data-n="12"]').click(button='right', position={'x': 50, 'y': 50})
        page.wait_for_selector('#lec-menu:not([hidden])')
        menu = page.inner_text('#lec-menu')
        check('우클릭: 그 쪽의 위치·기본 앱·경로·이름 바꾸기', all(x in menu for x in ('구리 보고서.pdf · 12쪽', '위치 복사', '기본 앱으로 열기', '탐색기에서 보기', '이름 바꾸기')) and '고른 글 담기' not in menu, menu)
        page.keyboard.press('Escape')
        page.keyboard.press('Control+e')
        expect(page, 'Ctrl+E — 보기만 한다고 알린다', lambda: 'PDF 는 보기만 합니다' in page.evaluate(TOAST), lambda: page.evaluate(TOAST))
        check('편집기가 열리지 않는다', page.locator('.lec-pane.active .lec-editor').count() == 0)
        page.locator('#lec-tree .row[data-doc="보고서/구리 보고서.pdf"]').click(button='right')
        page.wait_for_selector('#lec-menu:not([hidden])')
        menu = page.inner_text('#lec-menu')
        check("트리 우클릭: '기본 앱으로 열기', 문서 삭제는 없다", '기본 앱으로 열기' in menu and '문서 삭제' not in menu and '외부 편집기로 열기' not in menu, menu)
        page.keyboard.press('Escape')
        r = page.evaluate("""() => import('/static/js/store.js').then(({ S }) => fetch('/api/delete-doc', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ p: S.tab.id, path: '보고서/scan.pdf' }) }).then((x) => x.status))""")
        check('서버도 PDF 를 지우지 않는다', (proj / '보고서' / 'scan.pdf').exists(), r)
        page.keyboard.press('Control+Shift+f')
        page.keyboard.type('구리')
        page.wait_for_timeout(1200)
        found = page.evaluate("() => import('/static/js/api.js').then((a) => import('/static/js/store.js').then(({ S }) => a.getJSON(`/api/search?p=${S.tab.id}&q=${encodeURIComponent('2분기 구리')}`)))")
        check('사이드바 검색은 PDF 의 글을 읽지 않는다 (이름이 맞으면 이름으로)', not any(r['path'].endswith('.pdf') for r in found.get('results', found.get('docs', [])) if isinstance(r, dict)) and '구리 보고서.pdf' in page.inner_text('#lec-sidebar'), str(found)[:300])
        page.keyboard.press('Escape')
        page.click('.side-tabs button[data-tab="files"]')
        page.keyboard.press('Control+p')
        page.keyboard.type('구리 보고서')
        page.wait_for_timeout(400)
        check('문서 열기(Ctrl+P)에는 이름으로', '구리 보고서.pdf' in page.inner_text('#lec-palette'), page.inner_text('#lec-palette')[:200])
        page.keyboard.press('Escape')

        print('[글꼴을 넣지 않은 한글 · 스캔 · 스크립트 · 깨짐]')
        open_pdf('보고서/cid.pdf')
        expect(page, 'CMap 으로 한글을 읽는다 — 글 층과 책갈피 셋', lambda: '핵심 광물 공급망' in page.evaluate(LAYER, 1) and page.locator('#lec-toc a[data-i]').count() == 3, lambda: page.evaluate(LAYER, 1))
        open_pdf('보고서/scan.pdf')
        expect(page, '스캔한 PDF 는 글이 없다고 알린다', lambda: '글자가 없는 PDF' in page.inner_text('#lec-view .pdf-note'), lambda: page.inner_text('#lec-view .pdf-bar'))
        page.locator('#lec-content').focus()
        page.keyboard.press('Alt+c')
        expect(page, '— Alt+C 도 까닭을 알린다', lambda: '글자가 없는 PDF' in page.evaluate(TOAST), lambda: page.evaluate(TOAST))
        check('목차는 비어 있다 (책갈피 없음)', page.locator('#lec-toc a[data-i]').count() == 0)
        outside.clear()
        open_pdf('보고서/script.pdf')
        page.wait_for_timeout(1200)
        page.locator('#lec-view a.pdf-link').first.click()
        page.wait_for_timeout(500)
        check('PDF 의 스크립트는 돌지 않는다', not dialogs, dialogs)
        check('링크는 앱이 받는다 — 인터넷 주소는 기본 브라우저로 (이 칸은 그대로)', page.evaluate('() => window.__opened') == ['http://127.0.0.1:9/leak-link'] and 'pdf-view' in page.evaluate("() => document.querySelector('#lec-view').className"), page.evaluate('() => window.__opened'))
        check('— 바깥 요청이 없다', not outside, outside)
        open_pdf('보고서/구리 보고서.pdf')
        page.locator('#lec-toc a[data-i]').nth(1).click()
        page.wait_for_selector('#lec-view .pdf-pg[data-n="2"] a.pdf-link', timeout=15000)
        page.locator('#lec-view .pdf-pg[data-n="2"] a.pdf-link').first.click()
        expect(page, 'https 링크는 기본 브라우저로', lambda: page.evaluate('() => window.__opened')[-1:] == ['https://example.com/source'], lambda: page.evaluate('() => window.__opened'))
        open_pdf('보고서/깨짐.pdf')
        check('깨진 PDF 는 까닭과 기본 앱으로 열기', 'PDF 를 읽지 못했습니다' in page.inner_text('#lec-view') and page.locator('#lec-view [data-act="external"]').count() == 1, page.inner_text('#lec-view')[:200])

        print('[밖에서 바뀜 · 다시 켜기]')
        open_pdf('보고서/cid.pdf')
        time.sleep(0.4)
        shutil.copy(proj / '보고서' / '구리 보고서.pdf', proj / '보고서' / 'cid.pdf')
        expect(page, '밖에서 바뀌면 다시 읽는다', lambda: (st() or {}).get('pages') == 300, st, ms=15000)
        page.locator('#lec-toc a[data-i]').nth(41).click()
        expect(page, '42쪽', lambda: st()['cur'] == 42)
        page.wait_for_timeout(1500)
        start()
        page.wait_for_selector('#lec-view.pdf-view .pdf-pg.drawn', timeout=30000)
        expect(page, '다시 켜면 그 PDF 의 그 근처로', lambda: st() and st()['pages'] == 300 and abs(st()['cur'] - 42) <= 1, st, ms=10000)
        page.evaluate(OPEN, '메모.md')
        page.wait_for_selector('#lec-view h1:has-text("메모")')
        check('다른 문서로 가면 PDF 를 놓는다', page.evaluate("() => import('/static/js/store.js').then(({ S }) => S.pane.pdf == null && S.pane.findProvider == null)"))

        print('[영어]')
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ language: 'en' }))")
        start()
        open_pdf('보고서/구리 보고서.pdf')
        bar = page.evaluate("() => { const b = document.querySelector('#lec-view .pdf-bar'); return b.innerText + [...b.querySelectorAll('[title], [aria-label]')].map((e) => (e.title || '') + (e.getAttribute('aria-label') || '')).join(' '); }")
        import re
        check('막대에 남은 한글 없음', not re.findall(r'[가-힣]+', bar.replace('구리 보고서', '')), re.findall(r'[가-힣]+', bar))
        check('상태줄: p. 1/300', 'PDF · p. 1/300' in page.inner_text('#lec-status'), page.inner_text('#lec-status')[:120])
        check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
