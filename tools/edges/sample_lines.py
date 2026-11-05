"""예제 guide/09-한-줄-편집.md 를 적힌 대로 따라 한다: 복사한 예제 폴더에서 사례마다 실제로 고치고 파일을 본다. 문서의 설명이 틀리면 여기서 잡힌다"""
import shutil
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import ROOT, check, fails, report, serve, stop

base = Path(tempfile.mkdtemp(prefix='lec-sample-'))
proj = base / 'copy'
shutil.copytree(ROOT / 'samples', proj)
doc = proj / 'guide' / '09-한-줄-편집.md'
config = base / 'config'
config.mkdir()
server, url, port = serve(proj, config)


def read():
    for _ in range(100):
        try:
            return doc.read_text(encoding='utf-8')
        except OSError:
            time.sleep(0.02)
    return ''


def until(cond, ms=5000):
    end = time.time() + ms / 1000
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.03)
    return False


try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1280, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:160]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')
        page.evaluate("import('/static/js/store.js').then(({ emit }) => emit('open', { type: 'doc', path: 'guide/09-한-줄-편집.md' }))")
        page.wait_for_selector('#lec-view h1:has-text("한 줄 편집")')
        page.wait_for_timeout(800)
        settle = lambda ms=400: page.wait_for_timeout(ms)
        cell = '#lec-view .lec-line-edit'

        def opened(locator):
            locator.click()
            page.keyboard.press('F2')
            page.wait_for_selector(cell, timeout=3000)

        # 표의 링크가 모두 그 절로 간다
        links = page.locator('#lec-view table a')
        count = links.count()
        bad = []
        for i in range(count):
            text = links.nth(i).text_content()
            links.nth(i).click()
            settle(200)
            if '찾지 못했습니다' in (page.text_content('#lec-toast') or ''):
                bad.append(text)
        check(f'사례 표의 링크 {count}개가 모두 그 절로 간다', count == 13 and not bad, [count, bad])
        page.evaluate("document.querySelector('#lec-content').scrollTop = 0")

        # 1. 오타: 두 번 눌러 그 자리에서
        at = page.evaluate("""() => { const w = document.createTreeWalker(document.querySelector('#lec-view'), NodeFilter.SHOW_TEXT);
          for (let n = w.nextNode(); n; n = w.nextNode()) { const i = n.nodeValue.indexOf('1분기에 상승햇다'); if (i >= 0 && n.parentElement.tagName === 'P') {
            n.parentElement.scrollIntoView({ block: 'center' }); const r = document.createRange(); r.setStart(n, i + 7); r.setEnd(n, i + 8);
            const b = r.getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2]; } } }""")
        page.mouse.dblclick(*at)
        page.wait_for_selector(cell, timeout=3000)
        page.keyboard.press('Delete')
        page.keyboard.type('했')
        page.keyboard.press('Enter')
        check('사례 1: 두 번 누른 자리에서 오타를 고친다', until(lambda: '구리 가격은 1분기에 상승했다.' in read()), [x for x in read().split('\n') if '1분기에' in x][:1])

        # 2. 제목
        head = page.locator('#lec-view h3', has_text='임시 제목')
        head.scroll_into_view_if_needed()
        head.dblclick()
        page.wait_for_selector(cell, timeout=3000)
        page.keyboard.press('Control+a')
        page.keyboard.type('수요 전망')
        page.keyboard.press('Enter')
        check('사례 2: 제목을 바꾼다 (# 표시는 그대로)', until(lambda: '### 수요 전망' in read()))
        check('사례 2: 목차도 바뀐다', until(lambda: '수요 전망' in page.text_content('#lec-toc')))

        # 3. 표의 칸
        settle()
        opened(page.locator('#lec-view tr', has_text='2분기').locator('td').first)
        page.keyboard.press('Tab')
        settle(150)
        page.keyboard.press('Control+a')
        page.keyboard.type('19.2')
        page.keyboard.press('Enter')
        check('사례 3: Tab 으로 옆 칸을 고친다', until(lambda: '| 2분기 | 19.2 | -5.1% |' in read()), [x for x in read().split('\n') if '2분기 |' in x])

        # 4. ↓ 로 이어서
        settle()
        opened(page.locator('#lec-view li', has_text='수요 둘화'))
        page.keyboard.press('Control+a')
        page.keyboard.type('수요 둔화')
        page.keyboard.press('ArrowDown')
        ok = until(lambda: '- 수요 둔화' in read())
        page.wait_for_function("document.querySelector('.lec-line-edit')?.textContent.includes('공급 차질')", timeout=3000)
        page.keyboard.press('ArrowDown')
        page.wait_for_function("document.querySelector('.lec-line-edit')?.textContent.includes('환율')", timeout=3000)
        page.keyboard.press('Control+a')
        page.keyboard.type('환율 변동성')
        page.keyboard.press('Enter')
        check('사례 4: ↓ 는 저장하고 다음 줄을 연다', ok and until(lambda: '- 환율 변동성' in read()))

        # 5. 체크 칸
        settle()
        page.locator('#lec-view li', has_text='재고 자료 대조하기').locator('input').click()
        check('사례 5: 체크 칸이 [x] 로', until(lambda: '- [x] 재고 자료 대조하기' in read()))

        # 6. 새 줄과 번호
        settle()
        opened(page.locator('#lec-view li', has_text='자료 수집'))
        page.keyboard.press('Control+Enter')
        page.wait_for_selector('li.lec-new-line', timeout=3000)
        page.keyboard.type('자료 점검')
        page.keyboard.press('Enter')
        check('사례 6: 항목을 더하면 뒤 번호가 다시 매겨진다', until(lambda: '1. 자료 수집\n2. 자료 점검\n3. 분석\n4. 보고서 작성' in read().replace('\r\n', '\n')))

        # 7. 나누기·합치기
        settle()
        opened(page.locator('#lec-view p', has_text='공급 차질이 이어지며'))
        page.keyboard.press('Home')
        for _ in range('구리 가격은 수요 둔화로 하락했으나 '.__len__()):
            page.keyboard.press('ArrowRight')
        page.keyboard.press('Control+Enter')
        ok = until(lambda: '하락했으나' in read() and any(x.startswith('공급 차질이 이어지며') for x in read().split('\n')))
        settle(500)
        if page.locator(cell).count():
            page.keyboard.press('Escape')
        settle()
        check('사례 7: Ctrl+Enter 로 나눈다', ok, [x for x in read().split('\n') if '이어지며' in x])
        opened(page.locator('#lec-view p', has_text='공급 차질이 이어지며'))
        page.keyboard.press('Home')
        page.keyboard.press('Backspace')
        check('사례 7: 맨 앞에서 Backspace 로 합친다', until(lambda: any('하락했으나' in x and '이어지며' in x for x in read().split('\n'))), [x for x in read().split('\n') if '이어지며' in x])
        settle(500)
        if page.locator(cell).count():
            page.keyboard.press('Escape')

        # 8. 옮기기
        settle()
        opened(page.locator('#lec-view li', has_text='배경'))
        page.keyboard.press('Alt+ArrowUp')
        check('사례 8: Alt+↑ 로 옮기면 번호도', until(lambda: '1. 배경\n2. 결론\n3. 분석' in read().replace('\r\n', '\n')))
        settle(500)
        if page.locator(cell).count():
            page.keyboard.press('Escape')

        # 9. 단계
        settle()
        opened(page.locator('#lec-view li', has_text='광산 파업'))
        page.keyboard.press('Tab')
        check('사례 9: Tab 은 하위 항목으로', until(lambda: '- 공급\n  - 광산 파업' in read().replace('\r\n', '\n')), [x for x in read().split('\n') if '광산' in x])
        settle(500)
        if page.locator(cell).count():
            page.keyboard.press('Escape')

        # 10. 복제
        settle()
        opened(page.locator('#lec-view li', has_text='칠레 구리'))
        page.keyboard.press('Control+Shift+D')
        settle(600)
        page.keyboard.press('Control+a')
        page.keyboard.type('페루 구리 생산량')
        page.keyboard.press('Enter')
        check('사례 10: 복제한 줄을 이어서 고친다', until(lambda: '- 칠레 구리 생산량 — 전년 대비 2% 증가\n- 페루 구리 생산량' in read().replace('\r\n', '\n')))

        # 11. 지우기
        settle()
        page.locator('#lec-view li', has_text='지워도 되는 메모').click()
        page.keyboard.press('Shift+Enter')
        settle(200)
        page.keyboard.press('Delete')
        check('사례 11: 하이라이트하고 Delete', until(lambda: '지워도 되는 메모' not in read().split('## 사례 12')[0].split('## 사례 11')[1]))
        settle(500)

        # 12. 코드 블록
        opened(page.locator('#lec-view .code-block', has_text='START_YEAR').locator('code'))
        page.keyboard.press('Control+a')
        page.keyboard.type('START_YEAR = 2021')
        page.keyboard.press('Enter')
        check('사례 12: 코드 블록의 그 줄만', until(lambda: 'START_YEAR = 2021' in read()))

        # 13. 되돌리기
        settle(700)
        page.locator('#lec-view h1').click()
        page.keyboard.press('Control+z')
        back = until(lambda: 'START_YEAR = 2020' in read())
        settle(700)
        page.keyboard.press('Control+y')
        check('사례 13: Ctrl+Z 로 되돌리고 Ctrl+Y 로 다시', back and until(lambda: 'START_YEAR = 2021' in read()))
        check('스크립트 오류가 없다', not errors, errors[:3])
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('멈춤')
finally:
    stop(server, base)
report()
