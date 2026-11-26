"""0.105.0 사람 시나리오 — 연구원이 기관 보고서 PDF 를 읽으며 근거를 모으고 보고서에 옮긴다 (D201).

1. 키보드로 PDF 를 찾아 열고(Ctrl+P) 넘기고 찾고, 책갈피로 장을 오간다
2. 근거를 골라 담기함에 (Alt+Shift+C) — 여러 PDF 에서, 담은 곳은 쪽
3. 보고서 초안(md)의 링크로 PDF 의 그 쪽에 가고, 뒤로(Alt+←) 돌아온다
4. 편집 모드로 초안을 쓰며 담은 근거를 커서 자리에 — 주석에 쪽
5. PDF 와 문서 탭 여럿을 오가고, 모두 펼치기·사이드바 감추기·좁은 창·어두운 스타일
6. Claude Code 가 PDF 를 새로 넣고, 열린 PDF 를 고쳐 쓰고, 지운다 — 이름도 바꾼다
7. 1000쪽 PDF, 빠르게 여러 PDF 를 연달아 누르기
8. PDF 를 보는 중에 다른 기능의 키·단추 (편집·넣기·내보내기·스타일) — 오류 없이 까닭을 알린다"""
import json
import shutil
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

HERE = Path(__file__).parent
base = Path(tempfile.mkdtemp(prefix='lec-scen105-'))
proj = base / '구리 연구'
(proj / '자료').mkdir(parents=True)
(proj / '보고서').mkdir()
CLIPS = proj / '.lectern' / 'clips'
shutil.copy(HERE / 'pdfs' / 'cid.pdf', proj / '자료' / '정부 보고서.pdf')


def make(path, n, word, extra='', browser=None):
    if browser is None:
        with sync_playwright() as p:
            b = p.chromium.launch()
            make(path, n, word, extra, b)
            b.close()
        return
    pg = browser.new_page()
    if True:
        pg.set_content('<!doctype html><meta charset="utf-8"><style>body{font:11pt "Malgun Gothic"}</style>' + ''.join(
            f'<h1>{i}. {word} {i}장</h1><p>{word} {i}장 본문입니다. 재고는 {1000 + i}톤이었다.{extra}</p><p>{"이어지는 문단. " * 30}</p><div style="page-break-after:always"></div>' for i in range(1, n + 1)))
        pg.pdf(path=str(path), format='A4', outline=True, tagged=True)
        pg.close()


make(proj / '자료' / 'LME 연보.pdf', 120, 'LME')
make(proj / '자료' / '광산 동향.pdf', 30, '광산')
(proj / '보고서' / '초안.md').write_text('# 구리 보고서 초안\n\n## 근거\n\n재고는 [LME 연보 12쪽](../자료/LME%20연보.pdf#page=12)에 있다.\n\n## 결론\n\n끝 문단.\n', encoding='utf-8', newline='\n')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)

OPEN = "(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: p, newTab: true }))"
ST = "() => import('/static/js/store.js').then(({ S }) => S.pane.pdf?.doc ? { path: S.pane.pdf.path, cur: S.pane.pdf.cur, pages: S.pane.pdf.doc.numPages, scale: Math.round(S.pane.pdf.scale * 100), fit: S.pane.pdf.fit, drawn: S.pane.pdf.drawn.size } : null)"
TOAST = "() => { const e = document.querySelector('#lec-toast'); return e && !e.hidden ? e.textContent : ''; }"
TABS = "() => [...document.querySelectorAll('#lec-doctab-list .doc-tab')].map((e) => e.querySelector('.name').textContent + (e.classList.contains('active') ? '*' : ''))"
LAYER = "(n) => [...document.querySelectorAll(`#lec-view .pdf-pg[data-n=\"${n}\"] .textLayer span`)].map((e) => e.textContent).join('')"
EDITOR = "() => import('/static/js/store.js').then((m) => m.S.pane.editor ? m.S.pane.editor.cm.getValue() : '')"


def clips():
    return '\n'.join(f.read_text(encoding='utf-8') for f in sorted(CLIPS.glob('*.md'))) if CLIPS.exists() else ''


try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 1360, 'height': 900}, permissions=['clipboard-read', 'clipboard-write'])
        page = ctx.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.on('dialog', lambda d: d.accept())
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        page.wait_for_timeout(500)
        page.evaluate("() => { window.__opened = []; window.open = (u) => { window.__opened.push(u); return null; }; }")

        def st():
            return page.evaluate(ST)

        def select_in(n, text):
            span = page.locator(f'#lec-view .pdf-pg[data-n="{n}"] .textLayer span', has_text=text).first
            box = span.bounding_box()
            page.mouse.move(box['x'] + 2, box['y'] + box['height'] / 2)
            page.mouse.down()
            page.mouse.move(box['x'] + box['width'] - 2, box['y'] + box['height'] / 2, steps=8)
            page.mouse.up()

        print('[1. 키보드로 찾아 열고 넘긴다]')
        page.keyboard.press('Control+p')
        page.keyboard.type('LME 연보')
        page.wait_for_timeout(300)
        page.keyboard.press('Enter')
        page.wait_for_selector('#lec-view.pdf-view .pdf-pg[data-n="1"].drawn', timeout=20000)
        expect(page, 'Ctrl+P 로 이름을 쳐서 연다', lambda: (st() or {}).get('pages') == 120)
        page.locator('#lec-content').focus()
        for _ in range(3):
            page.keyboard.press('PageDown')
        expect(page, 'PageDown 으로 넘긴다', lambda: st()['cur'] >= 2, st)
        page.keyboard.press('Control+f')
        page.keyboard.type('1077톤')
        expect(page, '수치로 찾는다 — 77쪽', lambda: page.inner_text('#lec-find-count') == '1/1' and st()['cur'] == 77, lambda: (page.inner_text('#lec-find-count'), st()), ms=15000)
        page.keyboard.press('Escape')
        page.locator('#lec-toc a[data-i]').nth(11).click()
        expect(page, '책갈피로 12장', lambda: st()['cur'] == 12)
        page.keyboard.press('End')
        expect(page, 'End', lambda: st()['cur'] == 120)
        page.keyboard.press('Home')
        expect(page, 'Home', lambda: st()['cur'] == 1)

        print('[2. 여러 PDF 에서 근거를 담는다]')
        page.locator('#lec-toc a[data-i]').nth(11).click()
        expect(page, '12쪽', lambda: st()['cur'] == 12 and 'LME 12장 본문입니다' in page.evaluate(LAYER, 12))
        select_in(12, 'LME 12장 본문입니다')
        page.keyboard.press('Alt+Shift+c')
        page.wait_for_selector('#lec-boxpick:not([hidden])')
        page.keyboard.insert_text('재고 근거')
        page.keyboard.press('Enter')
        expect(page, '고른 글을 새 담기함에 — 담은 곳은 12쪽', lambda: 'page=12' in clips() and 'LME 12장 본문입니다' in clips(), clips)
        page.evaluate(OPEN, '자료/광산 동향.pdf')
        page.wait_for_selector('#lec-view.pdf-view .pdf-pg[data-n="1"].drawn', timeout=20000)
        page.locator('#lec-toc a[data-i]').nth(4).click()
        expect(page, '광산 5쪽', lambda: st()['cur'] == 5 and '광산 5장 본문입니다' in page.evaluate(LAYER, 5))
        select_in(5, '광산 5장 본문입니다')
        page.keyboard.press('Alt+c')
        expect(page, 'Alt+C 로 같은 담기함에', lambda: clips().count('/lectern-clip -->') == 2 and 'page=5' in clips(), clips)
        page.evaluate(OPEN, '자료/정부 보고서.pdf')
        page.wait_for_selector('#lec-view.pdf-view .pdf-pg[data-n="1"].drawn', timeout=20000)
        expect(page, '글꼴을 넣지 않은 한글 PDF', lambda: '핵심 광물 공급망' in page.evaluate(LAYER, 1), lambda: page.evaluate(LAYER, 1))
        select_in(1, '핵심 광물')
        page.locator('#lec-view .pdf-pg[data-n="1"] .textLayer span', has_text='핵심 광물').first.click(button='right')
        page.wait_for_selector('#lec-menu:not([hidden])')
        check("우클릭에 '고른 글 담기 — 재고 근거'", "고른 글 담기 — '재고 근거'" in page.inner_text('#lec-menu') or '고른 글 담기' in page.inner_text('#lec-menu'), page.inner_text('#lec-menu'))
        page.keyboard.press('Escape')

        print('[3. 초안의 링크로 그 쪽에 갔다가 돌아온다]')
        page.evaluate(OPEN, '보고서/초안.md')
        page.wait_for_selector('#lec-view h1:has-text("구리 보고서 초안")')
        page.locator('#lec-view a', has_text='LME 연보 12쪽').click()
        page.wait_for_selector('#lec-view.pdf-view .pdf-pg.drawn', timeout=20000)
        expect(page, '#page=12 링크는 PDF 의 12쪽으로', lambda: st() and st()['path'] == '자료/LME 연보.pdf' and st()['cur'] == 12, st)
        page.keyboard.press('Alt+ArrowLeft')
        page.wait_for_timeout(800)
        check('Alt+← 로 초안이나 앞 화면으로 돌아온다', page.evaluate("() => import('/static/js/store.js').then(({ S }) => S.view?.type)") == 'doc', page.evaluate(TABS))

        print('[4. 초안을 쓰며 근거를 커서 자리에]')
        page.evaluate(OPEN, '보고서/초안.md')
        page.wait_for_selector('#lec-view h1:has-text("구리 보고서 초안")')
        page.locator('#lec-content').focus()
        page.keyboard.press('Control+e')
        page.wait_for_selector('.lec-pane.active .lec-editor .CodeMirror', timeout=20000)
        page.keyboard.press('Control+End')
        page.click('.side-tabs button[data-tab="basket"]')
        row = page.locator('#lec-basket-list .bk-box', has_text='재고 근거').first
        if row.get_attribute('aria-expanded') != 'true':
            row.locator('.caret').click()
        page.locator('#lec-basket-list .bk-item').first.locator('.bk-put').click()
        expect(page, '커서 자리에 — 담은 곳 주석에 쪽', lambda: '<!-- 담은 곳: 자료/LME 연보.pdf 12쪽 -->' in page.evaluate(EDITOR) and 'LME 12장 본문입니다' in page.evaluate(EDITOR), lambda: page.evaluate(EDITOR)[-300:])
        page.keyboard.press('Control+s')
        expect(page, '저장', lambda: '12쪽 -->' in (proj / '보고서' / '초안.md').read_text(encoding='utf-8'))
        page.keyboard.press('Control+e')
        page.click('.side-tabs button[data-tab="files"]')

        print('[5. 탭·모두 펼치기·사이드바·창·스타일]')
        page.locator('#lec-doctab-list .doc-tab', has_text='LME 연보').click()
        expect(page, '탭을 돌아오면 그 쪽 그대로', lambda: st() and st()['path'] == '자료/LME 연보.pdf' and st()['cur'] == 12, st)
        page.locator('#lec-doctab-list .doc-tab', has_text='광산 동향').click()
        expect(page, '— 광산도 5쪽 그대로', lambda: st() and st()['path'] == '자료/광산 동향.pdf' and st()['cur'] == 5, st)
        s0 = st()['scale']
        page.keyboard.press('Control+b')
        expect(page, '사이드바를 감추면 폭 맞춤이 커진다', lambda: st()['scale'] > s0, st)
        page.keyboard.press('Control+b')
        expect(page, '— 되돌리면 그대로', lambda: st()['scale'] == s0 and st()['cur'] == 5, st)
        page.click('#lec-doctab-spread')
        expect(page, '모두 펼치기에서도 PDF 가 그려진다', "() => document.documentElement.classList.contains('spread-on') && !!document.querySelector('.sp-cell .pdf-view .pdf-pg.drawn')")
        page.click('#lec-doctab-spread')
        page.set_viewport_size({'width': 760, 'height': 700})
        page.wait_for_timeout(500)
        wide = page.evaluate("() => { const v = document.querySelector('#lec-content'); return v.scrollWidth - v.clientWidth; }")
        check('좁은 창에서 옆으로 넘치지 않는다 (폭 맞춤)', wide <= 1 and st()['fit'], (wide, st()))
        page.set_viewport_size({'width': 1360, 'height': 900})
        page.evaluate("() => { document.documentElement.dataset.theme = 'dark'; }")
        page.wait_for_timeout(300)
        bg = page.evaluate("() => getComputedStyle(document.querySelector('#lec-view .pdf-pg')).backgroundColor")
        check('어두운 화면에서도 쪽은 흰 종이', bg == 'rgb(255, 255, 255)', bg)

        print('[6. 밖에서 넣고·고치고·지우고·이름을 바꾼다]')
        make(proj / '자료' / '새 자료.pdf', 3, '새', browser=b)
        page.evaluate("() => window.dispatchEvent(new Event('focus'))")
        expect(page, 'Claude Code 가 넣은 PDF 가 트리에', lambda: page.locator('#lec-tree .row[data-doc="자료/새 자료.pdf"]').count() == 1, ms=15000)
        page.locator('#lec-doctab-list .doc-tab', has_text='LME 연보').click()
        expect(page, 'LME 12쪽', lambda: st() and st()['cur'] == 12)
        time.sleep(0.3)
        make(proj / '자료' / 'LME 연보.pdf', 130, 'LME', browser=b)
        expect(page, '열린 PDF 를 고쳐 쓰면 다시 읽는다 — 보던 쪽 근처', lambda: st() and st()['pages'] == 130 and abs(st()['cur'] - 12) <= 1, st, ms=15000)
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('rename', { path: '자료/광산 동향.pdf' }))")
        page.wait_for_selector('#lec-rename:not([hidden])')
        page.fill('#lec-rename-input', '광산 보고.pdf')
        page.keyboard.press('Enter')
        expect(page, '이름을 바꾸면 탭과 담은 곳이 따라간다', lambda: '광산 보고.pdf' in ' '.join(page.evaluate(TABS)) and 'path=%EC%9E%90%EB%A3%8C%2F%EA%B4%91%EC%82%B0%20%EB%B3%B4%EA%B3%A0.pdf' in clips(), lambda: (page.evaluate(TABS), clips()[-400:]), ms=10000)
        (proj / '자료' / '광산 보고.pdf').unlink()
        page.evaluate("() => window.dispatchEvent(new Event('focus'))")
        page.locator('#lec-doctab-list .doc-tab', has_text='광산 보고').click()
        expect(page, '지운 PDF 의 탭은 없다고 알린다', lambda: '없거나' in page.inner_text('#lec-view') or '읽지 못했습니다' in page.inner_text('#lec-view'), lambda: page.inner_text('#lec-view')[:200], ms=15000)
        page.click('.side-tabs button[data-tab="basket"]')
        page.locator('#lec-basket-list .bk-box', has_text='재고 근거').first.click()
        page.wait_for_selector('#lec-view.clips-view .cb-card')
        expect(page, '담은 조각에도 원래 문서가 없다고', lambda: '원래 문서가 없습니다' in page.inner_text('#lec-view'), lambda: page.inner_text('#lec-view')[:300], ms=10000)
        page.click('.side-tabs button[data-tab="files"]')

        print('[7. 1000쪽, 빠르게 연달아]')
        make(proj / '자료' / '천 쪽.pdf', 1000, '천', browser=b)
        page.evaluate("() => window.dispatchEvent(new Event('focus'))")
        page.wait_for_selector('#lec-tree .row[data-doc="자료/천 쪽.pdf"]', timeout=15000)
        t0 = time.monotonic()
        page.locator('#lec-tree .row[data-doc="자료/천 쪽.pdf"]').click()
        page.wait_for_selector('#lec-view.pdf-view .pdf-pg[data-n="1"].drawn', timeout=30000)
        took = time.monotonic() - t0
        check(f'1000쪽 열기 {took:.1f}초', took < 8 and st()['pages'] == 1000, (took, st()))
        page.fill('#lec-view .pdf-page', '777')
        page.keyboard.press('Enter')
        expect(page, '777쪽으로', lambda: st()['cur'] == 777 and '천 777장 본문입니다' in page.evaluate(LAYER, 777), st, ms=10000)
        check('그려 둔 쪽은 몇 개뿐', st()['drawn'] <= 6, st())
        for name in ('자료/정부 보고서.pdf', '자료/새 자료.pdf', '자료/LME 연보.pdf', '자료/정부 보고서.pdf', '자료/새 자료.pdf'):
            page.locator(f'#lec-tree .row[data-doc="{name}"]').click()
            page.wait_for_timeout(60)
        expect(page, '연달아 눌러도 마지막 것이 보인다', lambda: st() and st()['path'] == '자료/새 자료.pdf' and page.locator('#lec-view .pdf-pg').count() == 3, st, ms=15000)

        print('[8. PDF 를 보며 다른 기능]')
        page.locator('#lec-content').focus()
        for key, want in (('Control+e', 'PDF 는 보기만'), ('/', '')):
            page.keyboard.press(key)
            page.wait_for_timeout(300)
        check('편집 키는 까닭을 알린다', 'PDF 는 보기만' in page.evaluate(TOAST) or page.locator('#lec-put:not([hidden])').count() == 0, page.evaluate(TOAST))
        page.keyboard.press('Escape')
        for btn in ('#lec-btn-put', '#lec-btn-export', '#lec-btn-style', '#lec-btn-edit', '#lec-btn-ai'):
            if page.locator(btn).count() and page.locator(btn).is_enabled():
                page.click(btn)
                page.wait_for_timeout(250)
                page.keyboard.press('Escape')
                page.keyboard.press('Escape')
        check('탭 막대의 단추를 눌러도 화면 오류가 없다', not errors, errors[:3])
        check('PDF 는 그대로', st() and st()['path'] == '자료/새 자료.pdf', st())
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
