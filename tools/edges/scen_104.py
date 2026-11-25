"""0.104.0 사람 시나리오 — 연구원이 질문마다 담기함을 두고 며칠 쌓는다 (D197).

1. 두 창에서 같은 담기함에 번갈아 담는다 — 하나도 잃지 않는다
2. 메모를 쓰는 동안(한글 조합) 다른 창이 조각을 더한다 — 쓰던 글과 초점이 그대로
3. 쓰다가 곧바로 다른 프로젝트·다른 탭으로, 쓰다가 바로 다시 켜기 — 마지막 글자까지 저장
4. 저장이 실패한다(연결 끊김) — 알리고, 다음에 고칠 때 함께 저장
5. 조각 300개 — 펼치고 끝까지 내리고 차례를 바꾼다
6. 같은 문서를 크게 고쳐 쓴 뒤 — 어느 조각이 옛것인지
7. 담기함 파일을 밖에서 지운다 — 담은 것을 잃지 않는다
8. 편집 모드로 보고서를 쓰며 커서 자리에 하나씩
9. 펼친 화면에서 담고(다른 탭에서 Alt+C) 되돌리고 옮기기를 섞는다"""
import json
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-scen104-'))
proj = base / '리서치'
other = base / '다른'
for d in (proj, other):
    d.mkdir(parents=True)
CLIPS = proj / '.lectern' / 'clips'
(proj / '조사.md').write_text('# 조사\n\n' + '\n\n'.join(f'문단 {i} 입니다. 구리 이야기 {i}.' for i in range(1, 31)) + '\n', encoding='utf-8', newline='\n')
(proj / '보고.md').write_text('# 보고\n\n## 결론\n\n끝 문단.\n', encoding='utf-8', newline='\n')
(other / '개요.md').write_text('# 다른 개요\n\n글.\n', encoding='utf-8', newline='\n')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)

OPEN = "(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: p }))"
TOAST = "() => { const e = document.querySelector('#lec-toast'); return e && !e.hidden ? e.textContent : ''; }"
IDS = "() => [...document.querySelectorAll('#lec-view .cb-card')].map((e) => e.dataset.id)"


def src(name='담기함.md'):
    for _ in range(30):
        try:
            return (CLIPS / name).read_text(encoding='utf-8')
        except OSError:
            time.sleep(0.03)
    return ''


def count(name='담기함.md'):
    return src(name).count('<!-- /lectern-clip -->')


try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        errors = []

        def window():
            page = b.new_page(viewport={'width': 1300, 'height': 850})
            page.on('pageerror', lambda e: errors.append(str(e)[:300]))
            page.on('dialog', lambda d: d.accept())
            page.goto(url)
            page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
            page.wait_for_timeout(500)
            return page

        def doc(page, path='조사.md', head='조사'):
            page.evaluate(OPEN, path)
            page.wait_for_selector(f'#lec-view h1:has-text("{head}")', timeout=20000)
            page.wait_for_timeout(150)

        def clip(page, text):
            page.locator('#lec-view p', has_text=text).first.click()
            page.keyboard.press('Alt+c')

        def basket(page):
            page.click('.side-tabs button[data-tab="basket"]')

        def expand(page, name='담기함'):
            row = page.locator('.bk-box', has_text=name).first
            if row.get_attribute('aria-expanded') != 'true':
                row.locator('.caret').click()

        a, c = window(), window()
        print('[1. 두 창에서 번갈아]')
        doc(a)
        doc(c)
        a.locator('#lec-view p', has_text='문단 1 입니다').first.click()
        a.evaluate("() => import('/static/js/docmenu.js').then((m) => { m.clipHere(); m.clipHere(); m.clipHere(); })")
        expect(a, '처음부터 잇따라 세 번 담아도 담기함은 하나', lambda: count() == 3 and len(list(CLIPS.glob('*.md'))) == 1, lambda: [x.name for x in CLIPS.glob('*.md')])
        basket(a)
        expand(a)
        for _ in range(2):
            a.locator('.bk-item').last.focus()
            a.keyboard.press('Delete')
            a.wait_for_timeout(150)
        expect(a, '둘을 뺀다', lambda: count() == 1, src)
        a.route('**/api/clips?*', lambda r: (time.sleep(0.6), r.continue_()))   # 읽기가 느린 동안 담는다
        a.evaluate("() => window.dispatchEvent(new Event('focus'))")
        clip(a, '문단 20 입니다')
        a.wait_for_timeout(2200)
        a.unroute('**/api/clips?*')
        expect(a, '느린 읽기가 방금 담은 것을 지우지 않는다', lambda: a.locator('.bk-item').count() == 2 and count() == 2, lambda: (a.locator('.bk-item').count(), count()))
        a.locator('.bk-item').last.focus()
        a.keyboard.press('Delete')
        expect(a, '처음 담기', lambda: count() == 1, src)
        c.evaluate("() => window.dispatchEvent(new Event('focus'))")
        basket(c)
        c.wait_for_selector('.bk-box')
        expand(c)
        expect(c, '다른 창의 담기 탭에도 보인다', lambda: c.locator('.bk-item').count() == 1, lambda: c.inner_text('#lec-basket-list'))
        for i in range(2, 10):
            clip(a if i % 2 else c, f'문단 {i} 입니다')
            a.wait_for_timeout(60)
        expect(a, '여덟을 번갈아 담아도 아홉 모두 남는다', lambda: count() == 9 and all(f'문단 {i} 입니다' in src() for i in range(1, 10)), lambda: (count(), src()[-500:]), ms=15000)
        check('담기함은 하나다 (두 창이 따로 만들지 않았다)', [p_.name for p_ in CLIPS.glob('*.md')] == ['담기함.md'], [p_.name for p_ in CLIPS.glob('*.md')])

        print('[2. 쓰는 동안 다른 창이 더한다]')
        basket(a)
        a.evaluate("() => window.dispatchEvent(new Event('focus'))")
        a.locator('.bk-box', has_text='담기함').first.click()
        a.wait_for_selector('#lec-view.clips-view .cb-card')
        expect(a, '아홉이 펼쳐진다', lambda: len(a.evaluate(IDS)) == 9, lambda: a.evaluate(IDS))
        memo = a.locator('#lec-view .cb-memo').nth(2)
        memo.click()
        cdp = a.context.new_cdp_session(a)
        cdp.send('Input.imeSetComposition', {'text': '구', 'selectionStart': 1, 'selectionEnd': 1})
        clip(c, '문단 10 입니다')
        until(a, lambda: count() == 10, 8000)
        cdp.send('Input.imeSetComposition', {'text': '구리', 'selectionStart': 2, 'selectionEnd': 2})
        a.wait_for_timeout(900)
        cdp.send('Input.insertText', {'text': '구리 재고'})
        expect(a, '조합하던 글이 끊기지 않고 그대로', lambda: memo.input_value() == '구리 재고' and a.evaluate("() => document.activeElement.className") == 'cb-memo', lambda: memo.input_value())
        expect(a, '다른 창의 조각과 함께 저장된다', lambda: count() == 10 and '구리 재고\n<!-- lectern-clip-text -->' in src() and len(a.evaluate(IDS)) == 10, lambda: (count(), a.evaluate(IDS)), ms=10000)

        print('[3. 쓰다가 곧바로 떠난다]')
        memo.click()
        a.keyboard.press('End')
        a.keyboard.type(' 끝까지')
        a.keyboard.press('Control+Tab')
        expect(a, '문서 탭을 바꿔도 마지막 글자까지', lambda: '구리 재고 끝까지\n' in src(), lambda: src()[:700])
        a.locator('#lec-doctab-list .doc-tab', has_text='담기함').click()
        a.wait_for_selector('#lec-view.clips-view .cb-card')
        a.locator('#lec-view .cb-name').nth(0).fill('첫 근거')
        a.evaluate("(dir) => import('/static/js/tabs.js').then((m) => m.openFolder(dir))", str(other))
        expect(a, '다른 프로젝트로 가도', lambda: '## 첫 근거\n' in src(), lambda: src()[:500])
        until(a, lambda: a.evaluate("() => import('/static/js/store.js').then((m) => m.S.tab?.name)") == '다른', 15000)
        basket(a)
        expect(a, '다른 프로젝트의 담기는 비어 있다', lambda: a.locator('.bk-box').count() == 0, lambda: a.inner_text('#lec-basket-list'))
        a.evaluate("() => import('/static/js/tabs.js').then((m) => m.selectTabAt(1))")
        a.wait_for_selector('#lec-view.clips-view .cb-card')
        a.locator('#lec-view .cb-memo').nth(1).fill('다시 켜기 직전')
        a.keyboard.press('Tab')
        a.wait_for_timeout(120)
        a.reload()
        a.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        expect(a, '칸을 떠나자마자 다시 켜도', lambda: '다시 켜기 직전\n' in src(), lambda: src()[:900])

        print('[4. 저장 실패]')
        a.wait_for_timeout(600)
        a.evaluate("() => import('/static/js/tabs.js').then((m) => m.selectTabAt(1))")
        basket(a)
        a.wait_for_selector('.bk-box')
        a.locator('.bk-box', has_text='담기함').first.click()
        a.wait_for_selector('#lec-view.clips-view .cb-card')
        a.route('**/api/clips', lambda r: r.abort() if r.request.method == 'POST' else r.continue_())
        a.locator('#lec-view .cb-memo').nth(3).fill('끊긴 동안')
        expect(a, '저장하지 못했다고 알린다', lambda: '저장하지 못했습니다' in a.evaluate(TOAST), lambda: a.evaluate(TOAST), ms=8000)
        check('— 쓴 글은 화면에 남는다', a.locator('#lec-view .cb-memo').nth(3).input_value() == '끊긴 동안')
        a.unroute('**/api/clips')
        a.locator('#lec-view .cb-memo').nth(4).fill('이어진 뒤')
        expect(a, '다음에 고칠 때 함께 저장된다', lambda: '끊긴 동안\n' in src() and '이어진 뒤\n' in src(), lambda: src()[-900:], ms=8000)

        print('[5. 조각 300개]')
        body = src()
        more = ''.join(f'\n<!-- lectern-clip id=m{i} path=%EC%A1%B0%EC%82%AC.md line={2 * (i % 30) + 3} kind=block label=m{i} -->\n<!-- lectern-clip-text -->\n| 열{i} | 값 |\n|---|---|\n| {i} | {i * i} |\n<!-- /lectern-clip -->\n' for i in range(290))
        (CLIPS / '많음.md').write_text('# 많음\n' + more, encoding='utf-8', newline='\n')
        a.evaluate("() => window.dispatchEvent(new Event('focus'))")
        a.wait_for_selector('.bk-box:has-text("많음")')
        t0 = time.monotonic()
        a.locator('.bk-box', has_text='많음').click()
        a.wait_for_function("() => document.querySelectorAll('#lec-view .cb-card').length === 290", timeout=20000)
        check('290개를 3초 안에 펼친다 (보이는 것만 그린다)', time.monotonic() - t0 < 3 and a.locator('#lec-view .cb-filled').count() < 100, (round(time.monotonic() - t0, 1), a.locator('#lec-view .cb-filled').count()))
        for _ in range(90):
            a.mouse.move(650, 500)
            a.mouse.wheel(0, 900)
            a.wait_for_timeout(60)
            if a.evaluate("() => { const v = document.querySelector('#lec-content'); return v.scrollTop + v.clientHeight >= v.scrollHeight - 4; }"):
                break
        expect(a, '끝까지 내려도 맨 끝 표가 그려진다', "() => { const l = document.querySelector('#lec-view .cb-card:last-child'); return !!l.querySelector('.pv-body.md-body table'); }", ms=8000)
        a.locator('#lec-view .cb-memo').last.click()
        t0 = time.monotonic()
        a.keyboard.type('삼백 개여도 글자가 밀리지 않는다')
        took = time.monotonic() - t0
        check('글자를 쳐도 밀리지 않는다 (3초 안)', took < 3, round(took, 2))
        expect(a, '— 저장된다', lambda: '삼백 개여도 글자가 밀리지 않는다' in src('많음.md'), ms=8000)
        a.keyboard.press('Escape')
        a.keyboard.press('Alt+ArrowUp')
        expect(a, '차례 바꾸기', lambda: a.evaluate(IDS)[-2:] == ['m289', 'm288'], lambda: a.evaluate(IDS)[-3:])
        check('다른 담기함은 건드리지 않았다', src() == body)

        print('[6. 원래 문서를 크게 고친 뒤]')
        a.locator('#lec-doctab-list .doc-tab', has_text='담기함').first.click()
        a.wait_for_selector('#lec-view.clips-view .cb-card')
        text = (proj / '조사.md').read_text(encoding='utf-8')
        time.sleep(0.3)
        (proj / '조사.md').write_text('# 조사\n\n새 머리.\n\n' + text.split('\n', 2)[2].replace('구리 이야기 3.', '니켈 이야기 3.').replace('문단 5 입니다', '다섯째 문단입니다'), encoding='utf-8', newline='\n')
        expect(a, '고친 두 문단을 담은 조각만 알린다', lambda: a.evaluate("() => [...document.querySelectorAll('#lec-view .cb-card')].filter((e) => !e.querySelector('.cb-state').hidden).map((e) => e.querySelector('.pv-hold, .pv-body').textContent.trim().slice(0, 5))") == ['문단 3 ', '문단 5 '], lambda: a.evaluate("() => [...document.querySelectorAll('#lec-view .cb-card')].filter((e) => !e.querySelector('.cb-state').hidden).map((e) => e.innerText.slice(0, 60))"), ms=15000)

        print('[7. 파일을 밖에서 지운다]')
        n = len(a.evaluate(IDS))
        a.locator('#lec-view .cb-memo').nth(0).fill('지워진 뒤에 씀')
        (CLIPS / '담기함.md').unlink(missing_ok=True)
        a.locator('#lec-view .cb-memo').nth(0).fill('지워진 뒤에 또 씀')
        expect(a, '쓰고 있던 담기함은 다시 만든다 — 담은 것이 그대로', lambda: count() == n and '지워진 뒤에 또 씀\n' in src(), lambda: (count(), n), ms=10000)
        (CLIPS / '많음.md').unlink()
        a.evaluate("() => window.dispatchEvent(new Event('focus'))")
        expect(a, '쓰지 않던 담기함은 목록에서 사라진다', lambda: a.locator('.bk-box', has_text='많음').count() == 0, ms=8000)

        print('[8. 편집 모드로 쓰며 하나씩]')
        doc(a, '보고.md', '보고')
        a.locator('#lec-content').focus()
        a.keyboard.press('Control+e')
        a.wait_for_selector('.lec-pane.active .lec-editor .CodeMirror', timeout=20000)
        a.keyboard.press('Control+End')
        expand(a)
        a.locator('#lec-basket-list .bk-item .bk-put').first.click()
        expect(a, '커서 자리에 조각이 — 단 제목·메모째', lambda: '## 첫 근거' in a.evaluate("() => import('/static/js/store.js').then((m) => m.S.pane.editor.cm.getValue())").replace('### ', '## ') and '> 메모: 지워진 뒤에 또 씀' in a.evaluate("() => import('/static/js/store.js').then((m) => m.S.pane.editor.cm.getValue())"), lambda: a.evaluate("() => import('/static/js/store.js').then((m) => m.S.pane.editor.cm.getValue())"))
        a.evaluate("() => import('/static/js/store.js').then((m) => import('/static/js/editor.js').then((e) => e.closeEditor(m.S.pane, { ask: false, sync: false })))")

        print('[9. 담고 되돌리고 옮기기를 섞는다]')
        c.evaluate("() => window.dispatchEvent(new Event('focus'))")
        basket(c)
        c.wait_for_timeout(600)
        c.click('#lec-basket-new')
        c.keyboard.type('둘째 질문')
        c.keyboard.press('Enter')
        expect(c, '새 담기함', lambda: c.locator('.bk-box.cur', has_text='둘째 질문').count() == 1)
        doc(c)
        for i in (11, 12, 13):
            clip(c, f'문단 {i} 입니다')
        expect(c, '셋', lambda: count('둘째-질문.md') == 3, lambda: src('둘째-질문.md'))
        c.locator('.bk-box', has_text='둘째 질문').first.click()
        c.wait_for_selector('#lec-view.clips-view .cb-card')
        c.locator('#lec-view .cb-card').nth(1).focus()
        c.keyboard.press('Delete')
        c.wait_for_timeout(150)
        c.locator('#lec-doctab-list .doc-tab', has_text='조사.md').click()
        c.wait_for_selector('#lec-view h1:has-text("조사")')
        clip(c, '문단 14 입니다')
        c.locator('#lec-doctab-list .doc-tab', has_text='둘째 질문').click()
        c.wait_for_selector('#lec-view.clips-view .cb-card')
        c.click('#lec-view [data-act="undo"]')
        expect(c, '빼고 하나 더 담은 뒤 되돌려도 제자리로 (11·12·13·14)', lambda: c.evaluate("() => [...document.querySelectorAll('#lec-view .cb-name')].map((e) => e.placeholder.match(/문단 (\\d+)/)?.[1]).join()") == '11,12,13,14', lambda: c.evaluate("() => [...document.querySelectorAll('#lec-view .cb-name')].map((e) => e.placeholder)"))
        c.locator('#lec-view .cb-card').last.locator('.cb-src').click(button='right', position={'x': 420, 'y': 6})
        c.locator('#lec-menu button[data-i]', has_text='다른 담기함으로 옮기기').click()
        c.wait_for_selector('#lec-boxpick:not([hidden])')
        c.locator('#lec-boxpick button', has_text='담기함').first.click()
        expect(c, '옮기면 한 곳에만', lambda: '문단 14 입니다' in src() and '문단 14 입니다' not in src('둘째-질문.md') and count('둘째-질문.md') == 3, lambda: (count(), count('둘째-질문.md')), ms=8000)
        check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
