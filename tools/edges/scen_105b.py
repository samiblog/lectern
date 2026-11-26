"""0.105.0 사람 시나리오 2 — 까다로운 PDF 와 엇갈리는 동작 (D201). 시나리오 1(scen_105)이 연구원의 하루라면 이것은 받은 자료가 고르지 않을 때:

1. 이름이 까다로운 PDF — 빈칸·#·%·&·+·한글·긴 이름, 대문자 .PDF
2. 쪽이 고르지 않은 PDF — 가로·세로가 섞이고, 돌린 쪽, 아주 큰 쪽과 작은 쪽 — 폭 맞춤·쪽 칸·찾기·담기
3. 문서 안 링크(목차 쪽으로 가는 링크)와 바깥 링크가 섞인 PDF
4. 받지 못하는 PDF — 0 바이트, 반쯤 잘린 것, 암호, PDF 가 아닌 것을 .pdf 로 — 까닭을 알리고 다른 것은 그대로
5. 읽는 도중에 — 큰 PDF 를 열자마자 탭을 닫거나 다른 프로젝트로, 열자마자 밖에서 고쳐 씀, 연달아 확대·축소
6. 두 창에서 같은 PDF — 한 창이 담고 다른 창이 다른 쪽을 본다
7. 확대의 끝 — 가장 크게·가장 작게에서 더 누르기, 크게 한 채 찾기·쪽 칸
(PDF 는 PyMuPDF 로 만든다 — 없으면 이 점검은 건너뛴다)"""
import json
import shutil
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

try:
    import pymupdf
except ImportError:   # 점검용 Python 에 없으면
    pymupdf = None

base = Path(tempfile.mkdtemp(prefix='lec-scen105b-'))
proj = base / '받은 자료'
other = base / '다른'
(proj / '들어온 것').mkdir(parents=True)
other.mkdir()
(other / '개요.md').write_text('# 다른\n\n글\n', encoding='utf-8')
CLIPS = proj / '.lectern' / 'clips'
FONT = 'C:/Windows/Fonts/malgun.ttf'


def doc_pdf(path, pages, label, rotate=None, link=False, password=None):
    """pages: [(w, h)] — 쪽마다 글 '{label} N쪽 본문' (한글 글꼴), 책갈피, 원하면 돌린 쪽·문서 안 링크·바깥 링크·암호"""
    d = pymupdf.open()
    for i, (w, h) in enumerate(pages, 1):
        pg = d.new_page(width=w, height=h)
        pg.insert_font(fontname='mg', fontfile=FONT)
        pg.insert_text((40, 60), f'{label} {i}쪽 본문입니다 — 재고 {500 + i}톤', fontname='mg', fontsize=12)
        if rotate and i in rotate:
            pg.set_rotation(rotate[i])
    if link and len(pages) >= 5:
        first = d[0]
        first.insert_text((40, 100), '5쪽으로 가기', fontname='mg', fontsize=12)
        first.insert_link({'kind': pymupdf.LINK_GOTO, 'from': pymupdf.Rect(36, 86, 160, 106), 'page': 4, 'to': pymupdf.Point(0, 0)})
        first.insert_text((40, 140), '누리집', fontname='mg', fontsize=12)
        first.insert_link({'kind': pymupdf.LINK_URI, 'from': pymupdf.Rect(36, 126, 120, 146), 'uri': 'https://example.org/src'})
    d.set_toc([[1, f'{label} {i}쪽', i] for i in range(1, len(pages) + 1)])
    d.subset_fonts()   # 쪽마다 넣은 글꼴을 쓰는 글자만 — 실제 PDF 처럼 (안 하면 쪽마다 맑은 고딕 통째로 수백 MB)
    if password:
        d.save(str(path), garbage=4, deflate=True, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw=password, owner_pw=password)
    else:
        d.save(str(path), garbage=4, deflate=True)
    d.close()


OPEN = "(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: p, newTab: true }))"
ST = "() => import('/static/js/store.js').then(({ S }) => S.pane.pdf?.doc ? { path: S.pane.pdf.path, cur: S.pane.pdf.cur, pages: S.pane.pdf.doc.numPages, scale: Math.round(S.pane.pdf.scale * 100), fit: S.pane.pdf.fit, drawn: S.pane.pdf.drawn.size } : null)"
LAYER = "(n) => [...document.querySelectorAll(`#lec-view .pdf-pg[data-n=\"${n}\"] .textLayer span`)].map((e) => e.textContent).join('')"
TOAST = "() => { const e = document.querySelector('#lec-toast'); return e && !e.hidden ? e.textContent : ''; }"
TABS = "() => [...document.querySelectorAll('#lec-doctab-list .doc-tab')].map((e) => e.querySelector('.name').textContent + (e.classList.contains('active') ? '*' : ''))"

if pymupdf is None:
    print('PyMuPDF 가 없어 건너뜁니다')
    report()
    raise SystemExit(0)

NAMES = ['보고서 #1 (최종).pdf', '50% 할인 & 특가+안내.pdf', 'UPPER CASE.PDF', '아주 긴 이름의 기관 보고서 — 2026년 하반기 구리 수급 전망과 정책 과제 최종본.pdf']
for i, n in enumerate(NAMES):
    doc_pdf(proj / '들어온 것' / n, [(595, 842)] * 3, f'이름{i}')
A4, LAND, BIG, SMALL = (595, 842), (842, 595), (2384, 3370), (200, 300)
doc_pdf(proj / '들어온 것' / '섞인 쪽.pdf', [A4, LAND, A4, BIG, SMALL, A4, LAND], '섞인', rotate={3: 90, 6: 180}, link=True)
doc_pdf(proj / '들어온 것' / '암호.pdf', [A4], '암호', password='secret')
(proj / '들어온 것' / '빈 파일.pdf').write_bytes(b'')
good = (proj / '들어온 것' / 'UPPER CASE.PDF').read_bytes()
(proj / '들어온 것' / '잘린 파일.pdf').write_bytes(good[:len(good) // 2])
(proj / '들어온 것' / '사실은 글.pdf').write_text('이건 PDF 가 아닙니다', encoding='utf-8')
doc_pdf(proj / '큰 문서.pdf', [A4] * 600, '큰')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 1360, 'height': 900})
        page = ctx.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.on('dialog', lambda d: d.accept())

        def start(pg):
            pg.goto(url)
            pg.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
            pg.wait_for_timeout(400)
            pg.evaluate("() => { window.__opened = []; window.open = (u) => { window.__opened.push(u); return null; }; }")

        def st(pg=None):
            return (pg or page).evaluate(ST)

        def open_pdf(path, pg=None):
            pg = pg or page
            pg.evaluate(OPEN, path)
            pg.wait_for_selector('#lec-view.pdf-view .pdf-pg[data-n="1"].drawn, #lec-view.pdf-failed', timeout=30000)
            pg.wait_for_timeout(250)

        start(page)
        print('[1. 이름이 까다로운 PDF]')
        for i, n in enumerate(NAMES):
            open_pdf(f'들어온 것/{n}')
            ok = (st() or {}).get('pages') == 3 and f'이름{i} 1쪽 본문입니다' in page.evaluate(LAYER, 1)
            check(f'{n[:24]} — 열고 글 층이 읽힌다', ok, (st(), page.evaluate(LAYER, 1)[:60]))
        tabs = page.evaluate(TABS)
        check('탭 이름이 그대로 (# % & + 대문자)', all(any(n[:12] in x for x in tabs) for n in NAMES), tabs)
        page.locator('#lec-content').focus()
        page.keyboard.press('Shift+ArrowLeft')
        page.wait_for_timeout(200)
        check('긴 이름도 상태줄에 지금 쪽', 'PDF · 1/3쪽' in page.inner_text('#lec-status'), page.inner_text('#lec-status')[:120])

        print('[2. 쪽이 고르지 않은 PDF]')
        open_pdf('들어온 것/섞인 쪽.pdf')
        sizes = page.evaluate("() => [...document.querySelectorAll('#lec-view .pdf-pg')].map((e) => [Math.round(e.offsetWidth), Math.round(e.offsetHeight)])")
        widest = max(w for w, _ in sizes)
        view_w = page.evaluate("() => document.querySelector('#lec-view').clientWidth")
        check('폭 맞춤은 보통 쪽에 — 아주 큰 쪽이 섞여도 다른 쪽이 작아지지 않는다 (큰 쪽은 옆으로 넘겨 본다)', sizes[0][0] <= view_w and sizes[0][0] > view_w * 0.6 and widest > view_w and sizes[1][0] > sizes[1][1] and sizes[4][0] < sizes[0][0], (sizes, view_w))
        check('돌린 쪽은 돌린 모양 (3쪽 90도 — 가로가 길다)', sizes[2][0] > sizes[2][1], sizes[2])
        page.fill('#lec-view .pdf-page', '5')
        page.keyboard.press('Enter')
        expect(page, '아주 작은 5쪽으로', lambda: st()['cur'] == 5 and '섞인 5쪽 본문입니다' in page.evaluate(LAYER, 5), st)
        page.keyboard.press('Control+f')
        page.keyboard.type('재고 503톤')
        expect(page, '돌린 쪽에서도 찾는다', lambda: page.inner_text('#lec-find-count') == '1/1' and st()['cur'] == 3, lambda: (page.inner_text('#lec-find-count'), st()), ms=10000)
        page.keyboard.press('Escape')
        span = page.locator('#lec-view .pdf-pg[data-n="3"] .textLayer span', has_text='섞인 3쪽').first
        span.click(click_count=3)   # 세 번 눌러 그 줄을 고른다 (돌린 쪽은 글이 세로로 흐른다)
        sel = page.evaluate('() => getSelection().toString()')
        check('돌린 쪽의 글도 고를 수 있다', '섞인 3쪽' in sel, sel)
        page.keyboard.press('Alt+c')
        expect(page, '돌린 쪽의 글을 골라 담는다 — 담은 곳 3쪽', lambda: CLIPS.exists() and 'page=3' in ''.join(f.read_text(encoding='utf-8') for f in CLIPS.glob('*.md')), lambda: (sel, page.evaluate(TOAST)))

        print('[3. 문서 안 링크와 바깥 링크]')
        page.fill('#lec-view .pdf-page', '1')
        page.keyboard.press('Enter')
        expect(page, '1쪽', lambda: st()['cur'] == 1)
        page.wait_for_selector('#lec-view .pdf-pg[data-n="1"] a.pdf-link', timeout=10000)
        page.locator('#lec-view .pdf-pg[data-n="1"] a.pdf-link').first.click()
        expect(page, '문서 안 링크는 그 쪽으로 (5쪽)', lambda: st()['cur'] == 5, st)
        page.fill('#lec-view .pdf-page', '1')
        page.keyboard.press('Enter')
        page.wait_for_timeout(300)
        page.locator('#lec-view .pdf-pg[data-n="1"] a.pdf-link').nth(1).click()
        expect(page, '바깥 링크는 기본 브라우저로 — 화면은 그대로', lambda: page.evaluate('() => window.__opened') == ['https://example.org/src'] and st()['path'] == '들어온 것/섞인 쪽.pdf', lambda: page.evaluate('() => window.__opened'))

        print('[4. 받지 못하는 PDF]')
        for name, want in (('암호.pdf', '암호가 걸린 PDF'), ('빈 파일.pdf', 'PDF 가 아니거나 깨진 파일입니다'), ('잘린 파일.pdf', None), ('사실은 글.pdf', 'PDF 가 아니거나 깨진 파일입니다')):
            open_pdf(f'들어온 것/{name}')
            text = page.inner_text('#lec-view')
            if want:
                check(f'{name} — 까닭과 기본 앱으로 열기', want in text and page.locator('#lec-view [data-act="external"]').count() == 1, text[:160])
            else:
                check(f'{name} — 읽을 수 있는 만큼 보이거나 까닭을 알린다 (멈추지 않는다)', (st() or {}).get('pages', 0) >= 1 or '읽지 못했습니다' in text, text[:160])
        page.locator('#lec-doctab-list .doc-tab', has_text='섞인 쪽').click()
        expect(page, '다른 탭의 PDF 는 그대로', lambda: (st() or {}).get('path') == '들어온 것/섞인 쪽.pdf' and st()['cur'] == 1, st)

        print('[5. 읽는 도중에]')
        t0 = time.monotonic()
        open_pdf('큰 문서.pdf')
        took = time.monotonic() - t0
        check(f'600쪽 열기 {took:.1f}초 — 새 탭이 곧 뜬다', took < 3 and (st() or {}).get('pages') == 600, (took, st()))
        page.keyboard.press('Control+w')
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: '큰 문서.pdf', newTab: true }))")
        page.wait_for_timeout(20)
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: '들어온 것/암호.pdf' }))")
        page.wait_for_timeout(2500)
        tabs = ' '.join(page.evaluate(TABS))
        check('여는 도중에 지금 탭에서 다른 것을 열어도 오류 없이 둘 다 열린다', not errors and '큰 문서.pdf' in tabs and '암호.pdf' in tabs, (errors[:2], page.evaluate(TABS)))
        page.locator('#lec-doctab-list .doc-tab', has_text='큰 문서').locator('.tab-close').click(force=True)
        page.evaluate(OPEN, '큰 문서.pdf')
        page.wait_for_timeout(30)
        page.evaluate("(dir) => import('/static/js/tabs.js').then((m) => m.openFolder(dir))", str(other))
        until(page, lambda: page.evaluate("() => import('/static/js/store.js').then((m) => m.S.tab?.name)") == '다른', 15000)
        page.wait_for_timeout(1500)
        check('열자마자 다른 프로젝트로 가도 오류가 없다', not errors, errors[:2])
        page.evaluate("() => import('/static/js/tabs.js').then((m) => m.selectTabAt(1))")
        page.wait_for_timeout(500)
        check('돌아오면 고르던 탭 그대로 — 연 PDF 는 뒤의 탭에', '큰 문서.pdf' in ' '.join(page.evaluate(TABS)) and '큰 문서.pdf*' not in page.evaluate(TABS), page.evaluate(TABS))
        page.locator('#lec-doctab-list .doc-tab', has_text='큰 문서').click()
        page.wait_for_selector('#lec-view.pdf-view .pdf-pg[data-n="1"].drawn', timeout=30000)
        expect(page, '— 그 탭을 고르면 그려져 있다', lambda: (st() or {}).get('pages') == 600, st, ms=15000)
        open_pdf('들어온 것/UPPER CASE.PDF')
        shutil.copy(proj / '들어온 것' / '섞인 쪽.pdf', proj / '들어온 것' / 'UPPER CASE.PDF')
        expect(page, '열자마자 밖에서 고쳐 쓰면 새 것으로 (7쪽)', lambda: (st() or {}).get('pages') == 7, st, ms=15000)
        for _ in range(6):
            page.keyboard.press('Control+=')
        for _ in range(3):
            page.keyboard.press('Control+-')
        page.wait_for_timeout(800)
        check('연달아 확대·축소 — 그린 쪽이 남지 않고 오류 없다', st()['drawn'] <= 8 and not errors, (st(), errors[:2]))

        print('[6. 두 창에서 같은 PDF]')
        second = ctx.new_page()
        second.on('pageerror', lambda e: errors.append(str(e)[:300]))
        start(second)
        open_pdf('들어온 것/섞인 쪽.pdf', second)
        second.fill('#lec-view .pdf-page', '7')
        second.keyboard.press('Enter')
        expect(second, '둘째 창은 7쪽', lambda: st(second)['cur'] == 7, lambda: st(second))
        page.locator('#lec-doctab-list .doc-tab', has_text='섞인 쪽').click()
        page.fill('#lec-view .pdf-page', '2')
        page.keyboard.press('Enter')
        expect(page, '첫 창은 2쪽', lambda: st()['cur'] == 2)
        span = page.locator('#lec-view .pdf-pg[data-n="2"] .textLayer span', has_text='섞인 2쪽').first
        bx = span.bounding_box()
        page.mouse.move(bx['x'] + 2, bx['y'] + bx['height'] / 2)
        page.mouse.down()
        page.mouse.move(bx['x'] + bx['width'] - 2, bx['y'] + bx['height'] / 2, steps=6)
        page.mouse.up()
        page.keyboard.press('Alt+c')
        expect(page, '첫 창에서 담는다', lambda: 'page=2' in ''.join(f.read_text(encoding='utf-8') for f in CLIPS.glob('*.md')))
        second.evaluate("() => window.dispatchEvent(new Event('focus'))")
        second.wait_for_timeout(800)
        check('둘째 창은 보던 쪽 그대로', st(second)['cur'] == 7, st(second))
        second.close()

        page.click('#lec-doctab-spread')
        expect(page, '모두 펼치기 — PDF 여럿이 함께 그려진다', "() => document.querySelectorAll('.sp-cell .pdf-view .pdf-pg[data-n=\"1\"].drawn').length >= 3", lambda: page.evaluate("() => document.querySelectorAll('.sp-cell .pdf-view').length"), ms=20000)
        page.click('#lec-doctab-spread')
        page.wait_for_timeout(400)
        print('[7. 확대의 끝]')
        for _ in range(15):
            page.keyboard.press('Control+=')
        page.wait_for_timeout(500)
        top = st()['scale']
        page.keyboard.press('Control+=')
        page.wait_for_timeout(300)
        check('가장 크게(300%)에서 더 눌러도 그대로', top == 300 and st()['scale'] == 300, st())
        wide = page.evaluate("() => { const v = document.querySelector('#lec-content'); return v.scrollWidth > v.clientWidth; }")
        check('크게 하면 옆으로 넘겨 볼 수 있다', wide)
        page.keyboard.press('Control+f')
        page.keyboard.type('재고 506톤')
        expect(page, '크게 한 채 찾기 — 6쪽으로', lambda: st()['cur'] == 6 and page.inner_text('#lec-find-count') == '1/1', lambda: (page.inner_text('#lec-find-count'), st()), ms=10000)
        page.keyboard.press('Escape')
        for _ in range(15):
            page.keyboard.press('Control+-')
        page.wait_for_timeout(500)
        check('가장 작게(50%)', st()['scale'] == 50 and not st()['fit'], st())
        page.keyboard.press('Control+0')
        expect(page, 'Ctrl+0 으로 폭 맞춤', lambda: st()['fit'], st)
        check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
