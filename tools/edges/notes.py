"""프로젝트 메모 (D92): 패널 열고 닫기, 카드, 할 일, 저장, 파일이 밖에서 바뀔 때, 보내기, 위험한 글자."""
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import ROOT, check, fails, report, serve, stop

base = Path(tempfile.mkdtemp(prefix='lec-notes-'))
proj = base / 'proj'
proj.mkdir()
other = base / 'other'
other.mkdir()
(other / 'o.md').write_text('# 다른 프로젝트\n\n글\n', encoding='utf-8')
(proj / 'a.md').write_text('# 문서 가\n\n첫 문단입니다.\n\n둘째 문단입니다.\n\n## 절\n\n셋째 문단입니다.\n', encoding='utf-8')
(proj / 'code.py').write_text('value = 1\nother = 2\n', encoding='utf-8')
store = proj / '.lectern' / 'notes.md'
MARK = '<i data-xss="1"> & \'x\''

server, url, port = serve(proj, base / 'config')

try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')
        settle = lambda ms=400: page.wait_for_timeout(ms)

        def saved():
            try:
                return store.read_text(encoding='utf-8')
            except OSError:   # 없거나 바꿔 끼우는 순간
                return ''

        def until(fn, ms=4000):
            for _ in range(ms // 100):
                if fn():
                    return True
                page.wait_for_timeout(100)
            return fn()

        cards = lambda: page.locator('#lec-notes-list .note-card')
        card = lambda i=0: cards().nth(i)
        print('[열고 닫기]')
        page.locator('#lec-tree .row.file[data-doc="a.md"]').click()
        page.wait_for_selector('#lec-view h1')
        settle()
        page.keyboard.press('Alt+m')
        page.wait_for_selector('#lec-notes:not([hidden])')
        settle()
        check('Alt+M 으로 열림, 메모가 없다고 알림', '메모가 없습니다' in page.locator('#lec-notes-list').inner_text() and page.get_attribute('#lec-btn-notes', 'aria-pressed') == 'true')
        check('열어 보기만 해서는 파일을 만들지 않음', not (proj / '.lectern').exists())
        page.keyboard.press('Alt+m')
        settle(200)
        check('Alt+M 으로 닫힘', page.locator('#lec-notes').is_hidden())
        page.click('#lec-btn-notes')
        settle(200)
        check('탭 막대 버튼으로 열림', page.locator('#lec-notes').is_visible())
        page.keyboard.press('Escape')
        settle(200)
        check('Esc 로 닫힘', page.locator('#lec-notes').is_hidden())
        page.click('#lec-btn-notes')
        settle(300)
        box = page.locator('#lec-notes').bounding_box()
        view = page.locator('#lec-view').bounding_box()
        check('문서 칸 폭은 그대로 — 위를 덮는다', box['x'] + box['width'] >= 1430 and view['width'] > 700, [box, view])

        print('[쓰기]')
        page.click('#lec-notes-new')
        settle(200)
        check('새 메모는 비어 있으면 파일을 만들지 않음', not store.exists() and cards().count() == 1)
        page.keyboard.type('첫 메모의 본문')
        check('쓰면 조금 뒤에 파일이 생김', until(lambda: '첫 메모의 본문' in saved()), saved()[:200])
        card().locator('.note-title').fill('구리 가격 메모')
        check('제목도 저장', until(lambda: '## 구리 가격 메모' in saved()), saved()[:200])
        check('사람이 읽는 Markdown', saved().count('<!-- lectern-note ') == 1 and '첫 메모의 본문' in saved())
        check('트리에는 나오지 않음', page.locator('#lec-tree').inner_text().find('notes') < 0)
        page.click('#lec-notes-new')
        settle(200)
        page.keyboard.type('둘째 메모')
        until(lambda: '둘째 메모' in saved())
        check('새 메모는 맨 위', '둘째 메모' == card(0).locator('.note-body').input_value() and cards().count() == 2)

        print('[고정·색·거르기]')
        card(1).locator('[data-act="pin"]').click()
        settle(200)
        check('고정하면 맨 위', card(0).locator('.note-title').input_value() == '구리 가격 메모' and 'pinned' in (card(0).get_attribute('class') or ''))
        card(0).locator('.note-dot.note-green').click()
        settle(200)
        check('색', 'note-green' in (card(0).get_attribute('class') or '') and until(lambda: 'color=green' in saved() and 'pinned=1' in saved()), saved()[:200])
        page.fill('#lec-notes-filter', '둘째')
        settle(200)
        check('글자로 거르기', cards().count() == 1)
        page.fill('#lec-notes-filter', '없는말')
        settle(200)
        check('맞는 것이 없으면 알림', '맞는 메모가 없습니다' in page.locator('#lec-notes-list').inner_text())
        page.fill('#lec-notes-filter', '')
        settle(200)

        print('[할 일]')
        page.click('#lec-notes-new')
        settle(200)
        page.keyboard.type('우유\n계란\n빵')
        tasks_card = page.locator('.note-card').nth(1)
        tasks_card.locator('[data-act="list"]').click()
        settle(300)
        rows = lambda: tasks_card.locator('.note-tasks li')
        check('글을 할 일 목록으로', rows().count() == 3, rows().count())
        rows().nth(0).locator('input[type="checkbox"]').click()
        settle(300)
        check('끝낸 항목은 아래로', rows().nth(2).locator('.note-task').input_value() == '우유' and 'done' in (rows().nth(2).get_attribute('class') or ''))
        tasks_card.locator('.note-add').fill('치즈')
        page.keyboard.press('Enter')
        settle(300)
        check('항목 더하기는 끝낸 것 앞에', rows().nth(2).locator('.note-task').input_value() == '치즈' and rows().count() == 4)
        rows().nth(0).locator('.note-task').fill('계란 두 판')
        page.keyboard.press('Tab')
        check('항목 고치기가 파일에', until(lambda: '- [ ] 계란 두 판' in saved() and '- [x] 우유' in saved()), saved()[-200:])

        print('[복사·보내기·지우기]')
        page.evaluate("() => { window.__text = null; navigator.clipboard.writeText = async (v) => { window.__text = v; }; }")
        card(0).locator('[data-act="copy"]').click()
        settle(200)
        check('복사는 Markdown 글', (page.evaluate('window.__text') or '').startswith('## 구리 가격 메모'), page.evaluate('window.__text'))
        page.evaluate("window.__term = null; import('/static/js/store.js').then(({ on }) => on('term-paste', (v) => { window.__term = v; }))")
        settle(100)
        card(0).locator('[data-act="term"]').click()
        settle(200)
        check('터미널로 보내기', '구리 가격 메모' in (page.evaluate('window.__term') or ''), page.evaluate('window.__term'))
        card(0).locator('[data-act="send"]').click()
        page.wait_for_selector('#lec-insert:not([hidden]), .insert-box:not([hidden]), #lec-pick:not([hidden])', timeout=3000)
        check('문서로 보내기는 보낼 곳을 고름', True)
        page.keyboard.press('Escape')
        settle(300)
        n = cards().count()
        keep = page.evaluate("[...document.querySelectorAll('.note-card .note-body')].map((a) => a.value)")
        page.locator('.note-card', has=page.locator('.note-body')).last.locator('[data-act="delete"]').click()
        settle(200)
        check('지우면 되돌리기가 보임', cards().count() == n - 1 and page.locator('#lec-notes-undo').is_visible())
        page.click('#lec-notes-undo-btn')
        settle(300)
        check('되돌리기', cards().count() == n and page.locator('#lec-notes-undo').is_hidden())
        check('되돌린 메모도 파일에', until(lambda: all(k in saved() for k in keep if k)), keep)

        print('[새 메모로 보내기]')
        page.locator('#lec-view p', has_text='둘째 문단').click(modifiers=['Shift'])
        settle(200)
        page.locator('#lec-view p', has_text='둘째 문단').click(button='right')
        page.wait_for_selector('#lec-menu:not([hidden])')
        page.locator('#lec-menu button', has_text='새 메모로 보내기').click()
        settle(600)
        top = card(0) if card(0).locator('.note-from').count() else page.locator('.note-card', has=page.locator('.note-from')).first
        check('하이라이트에서 새 메모로, 출처와 함께', top.locator('.note-from').inner_text().startswith('@a.md 5') and '둘째 문단입니다.' in top.locator('.note-body').input_value(), top.inner_text()[:120])
        check('파일에도 출처', until(lambda: 'path=a.md' in saved() and 'line=5' in saved()), saved()[:200])
        page.evaluate("import('/static/js/store.js').then(({ emit }) => emit('open', { type: 'code', path: 'code.py' }))")
        page.wait_for_selector('#lec-view .cv-line')
        settle(300)
        top.locator('.note-from').click()
        page.wait_for_function("document.querySelector('#lec-view h1')?.textContent === '문서 가'", timeout=4000)
        check('출처를 누르면 그 문서로', True)

        print('[밖에서 바뀜]')
        text = saved()
        store.write_text(text + '\n<!-- lectern-note id=ext -->\n밖에서 더한 메모\n', encoding='utf-8')
        page.keyboard.press('Alt+m')
        settle(200)
        page.keyboard.press('Alt+m')
        settle(600)
        check('다시 열면 밖에서 고친 것을 읽음', '밖에서 더한 메모' in page.evaluate("[...document.querySelectorAll('.note-card .note-body')].map((a) => a.value).join(' ')"))
        store.write_text(saved().replace('밖에서 더한 메모', '밖에서 또 고침'), encoding='utf-8')
        card(0).locator('.note-title').fill('고치던 메모')
        check('고치는 사이 밖에서 바뀌면 합침', until(lambda: '고치던 메모' in saved() and '밖에서 또 고침' in saved()), saved()[-300:])

        print('[위험한 글자]')
        page.click('#lec-notes-new')
        settle(200)
        page.keyboard.type(MARK)
        card(0).locator('.note-title').fill(MARK)
        settle(900)
        check('값이 태그가 되지 않음', page.locator('#lec-notes [data-xss]').count() == 0 and card(0).locator('.note-title').input_value() == MARK)
        page.keyboard.press('Alt+m')
        settle(300)
        page.reload()
        page.wait_for_selector('#lec-tree .row.file')
        settle(900)
        page.keyboard.press('Alt+m')
        settle(700)
        titles = page.evaluate("[...document.querySelectorAll('.note-title')].map((t) => t.value)")
        check('다시 읽어도 글자 그대로', page.locator('#lec-notes [data-xss]').count() == 0 and MARK in titles, [titles, saved()[:400]])

        print('[저장이 안 될 때]')
        posts = []
        page.route('**/api/notes', lambda r: (posts.append(1), r.fulfill(status=500, content_type='application/json', body='{"error": "디스크 오류"}')) if r.request.method == 'POST' else r.continue_())
        card(0).locator('.note-title').fill('저장이 안 되는 메모')
        settle(1800)
        told = '저장하지 못했습니다' in page.locator('#lec-toast').inner_text()
        check('저장이 안 되면 알리고 끝없이 다시 보내지 않음', told and 1 <= len(posts) <= 2, [told, len(posts)])
        page.unroute_all()
        card(0).locator('.note-title').fill('다시 되는 메모')
        check('서버가 돌아오면 고친 것이 저장됨', until(lambda: '## 다시 되는 메모' in saved()), saved()[:300])

        print('[프로젝트마다]')
        n_here = cards().count()
        page.evaluate("(p) => fetch('/api/open', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: p }) })", str(other))
        settle(1800)
        if page.locator('#lec-tablist [role=tab]').count() < 2:
            page.reload()
            page.wait_for_selector('#lec-tree .row.file')
            settle(900)
            page.keyboard.press('Alt+m')
        page.locator('#lec-tablist [role=tab]').nth(1).click()
        settle(900)
        check('다른 프로젝트의 메모는 따로', cards().count() == 0 and not (other / '.lectern').exists(), cards().count())
        page.locator('#lec-tablist [role=tab]').nth(0).click()
        settle(900)
        check('돌아오면 그 프로젝트의 메모', cards().count() == n_here, [cards().count(), n_here])

        check('화면 스크립트 오류 없음', not errors, errors[:3])
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
