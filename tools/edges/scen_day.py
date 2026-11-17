"""시나리오 — 하루 일과를 이어서 (D149~D154): 기획 메모에 적기 → 업무 현황에는 안 나옴 → 상위에서 할 일 더하기·체크 → 간트에서 시작 정하기 →
달력의 막대·날짜를 눌러 일정 더하기 → Mermaid 간트를 보고서에 붙여 그림으로 → 넣기 창으로 쪽 나눔 → 기획 메모 반영 요청.
앞 단계가 고친 파일을 다음 단계가 그대로 쓴다 (단계마다 되돌리지 않는다)."""
import json
import tempfile
import traceback
from datetime import date, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop

base = Path(tempfile.mkdtemp(prefix='lec-scenday-'))
today = date.today()
d = lambda n: (today + timedelta(days=n)).isoformat()
proj = base / '리서치'
home = base / 'home'


def put(rel, text):
    path = proj / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


CARD = '---\nstatus: {st}\npriority: 중\nstart:\ndue: {due}\n---\n\n# {title}\n\n(한 줄 요약)\n\n## 기획 메모\n\n## 할 일\n\n## 일정\n\n## 기록\n'
put('WORK.md', CARD.format(st='', due='', title='리서치 총괄'))
put('이슈/WORK.md', CARD.format(st='진행', due=d(9), title='이슈 보고서'))
put('주간/WORK.md', CARD.format(st='예정', due=d(4), title='주간 보고'))
put('보고서.md', '# 3분기 보고서\n\n첫 문단이다.\n\n## 일정\n\n일정표는 아래와 같다.\n')
home.mkdir()
(home / 'WORK.md').write_text('# 공통 업무\n\n## 일정\n\n## 할 일\n', encoding='utf-8')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_home': str(home.resolve()), 'work_alerts': False}), encoding='utf-8')
md = lambda rel: (proj / rel).read_text(encoding='utf-8')

server, url, port = serve(proj, config)
try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={'width': 1440, 'height': 950})
        ctx.grant_permissions(['clipboard-read', 'clipboard-write'], origin=url.rstrip('/'))
        page = ctx.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')
        settle = lambda ms=400: page.wait_for_timeout(ms)
        B = '.wk-board:not(.wk-under):not(.wk-folder-work):visible'   # 업무 현황의 칸만 — Alt+W 직후에는 앞 화면의 하위 업무 칸이 아직 보인다
        OPEN = "(path) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path }))"
        HOOK = "() => import('/static/js/store.js').then((m) => { window.__pasted = []; m.on('term-paste', (x) => window.__pasted.push(typeof x === 'string' ? x : x.text)); })"

        def board(mode=None):
            page.keyboard.press('Escape')
            # 방금 닫은 창의 입력 칸이 아직 초점을 쥐고 있으면(다음 화면을 그릴 때 풀린다) Alt+W 가 글 입력으로 여겨진다 — 사람 손으로는 못 누를 틈
            page.wait_for_function("() => !document.activeElement?.closest('[hidden]')")
            page.keyboard.press('Alt+w')
            page.wait_for_selector(f'{B} .wk-mode', timeout=10000)
            settle()
            if mode:
                page.locator(f'{B} button[data-wk-mode="{mode}"]').click()
                settle(300)

        def open_doc(path, sel='#lec-view h1'):
            page.keyboard.press('Escape')
            page.locator('.lec-tab', has_text='리서치').first.click()   # 업무 현황은 공통 폴더의 탭이다 — 프로젝트 탭으로
            settle(300)
            page.evaluate(OPEN, path)
            page.wait_for_selector(sel, timeout=15000)
            settle(500)

        print('[1 기획 메모에 적는다]')
        page.evaluate(HOOK)
        open_doc('이슈/WORK.md')
        page.locator('#lec-view h2', has_text='기획 메모').click()
        page.keyboard.press('Control+Enter')
        page.wait_for_selector('#lec-view .lec-line-edit')
        page.keyboard.type(f'- [ ] 메모 속 할 일 ({d(2)})')
        page.keyboard.press('Shift+Enter')   # 저장하고 아래에 새 줄 (D158)
        settle(600)
        page.keyboard.type(f'- {d(3)} 10:00 메모 속 회의?')
        page.keyboard.press('Enter')   # 저장하고 닫기 (D158)
        settle(600)
        expect(page, '메모 두 줄이 파일에', lambda: '메모 속 할 일' in md('이슈/WORK.md') and '메모 속 회의?' in md('이슈/WORK.md'), lambda: md('이슈/WORK.md'))
        memo = md('이슈/WORK.md')
        check('— 기획 메모 절 안에', memo.index('## 기획 메모') < memo.index('메모 속 할 일') < memo.index('## 할 일'), memo)

        print('[2 업무 현황 — 메모는 안 나오고, 상위에서 할 일을 더한다]')
        board('list')
        check('메모 속 할 일·일정은 업무 현황에 없다', '메모 속' not in page.locator(B).inner_text())
        row = f'{B} tr.wk-tr:has(button.wk-open:text-is("이슈 보고서"))'
        page.locator(row + ' button[data-wk-act="todos"]').click()
        page.locator(f'{B} input[data-wk-add]').first.fill('공급사 자료 받기')
        page.locator(f'{B} input[data-wk-add]').first.press('Enter')
        expect(page, '상위에서 더한 할 일이 그 WORK.md 의 할 일 절에', lambda: '## 할 일\n\n- [ ] 공급사 자료 받기\n' in md('이슈/WORK.md'), lambda: md('이슈/WORK.md'))
        check('— 기획 메모는 그대로', '메모 속 할 일' in md('이슈/WORK.md') and md('이슈/WORK.md').index('메모 속 할 일') < md('이슈/WORK.md').index('공급사 자료 받기'))
        expect(page, '할 일 칸이 0 / 1', lambda: '1 / 1' in page.locator(row).inner_text() or '0 / 1' in page.locator(row).inner_text(), lambda: page.locator(row).inner_text())
        settle(600)
        page.locator(f'{B} input[data-wk-todo]').first.check()
        expect(page, '체크하면 [x]', lambda: '- [x] 공급사 자료 받기' in md('이슈/WORK.md'), lambda: md('이슈/WORK.md'))
        check('— 메모 속 체크 칸은 그대로', '- [ ] 메모 속 할 일' in md('이슈/WORK.md'))

        print('[3 간트 — 시작을 정한다]')
        settle(700)
        page.locator(f'{B} button[data-wk-mode="gantt"]').click()
        settle(400)
        g = f'{B} .wk-g-row:has(button.wk-open:text-is("이슈 보고서"))'
        check('마감만 있으면 점', page.locator(g + ' .wk-g-mile').count() == 1)
        page.locator(g + ' button[data-wk-act="start"]').click()
        page.wait_for_selector('#lec-datepick:not([hidden])')
        page.keyboard.press('Enter')
        expect(page, '시작 = 오늘 — 머리 설정의 빈 start: 줄에', lambda: f'\nstart: {today.isoformat()}\n' in md('이슈/WORK.md') and md('이슈/WORK.md').count('start:') == 1, lambda: md('이슈/WORK.md')[:90])
        expect(page, '막대가 된다', lambda: page.locator(g + ' .wk-g-bar').count() == 1)
        check('총괄은 하위의 처음~끝 (가는 막대)', page.locator(f'{B} .wk-g-row:has(button.wk-open:text-is("리서치 총괄")) .wk-g-bar.group').count() == 1)

        print('[4 달력 — 막대, 날짜를 눌러 일정]')
        page.locator(f'{B} button[data-wk-mode="calendar"]').click()
        settle(400)
        check('여러 날 막대 (이슈 보고서)', page.locator(f'{B} .wk-cal-bar', has_text='이슈 보고서').count() >= 1)
        page.locator(f'{B} .wk-cal-day.today').click()
        page.wait_for_selector('#lec-workevent:not([hidden])')
        page.fill('#lec-workevent-time', '15:00')
        page.fill('#lec-workevent-text', '팀장 중간 보고')
        where = page.locator('#lec-workevent-where')
        where.select_option(label=[o for o in where.locator('option').all_inner_texts() if '이슈 보고서' in o][0])
        page.click('#lec-workevent-go')
        expect(page, '일정이 그 WORK.md 의 일정 절에', lambda: f'## 일정\n\n- {today.isoformat()} 15:00 팀장 중간 보고\n' in md('이슈/WORK.md'), lambda: md('이슈/WORK.md'))
        board('calendar')
        expect(page, '달력의 오늘 칸에 일정', lambda: page.locator(f'{B} .wk-cal-items .k-event', has_text='팀장 중간 보고').count() == 1)
        check('메모 속 회의는 달력에도 없다', page.locator(f'{B} .wk-cal-items', has_text='메모 속').count() == 0)

        print('[5 Mermaid 간트를 보고서에]')
        page.locator(f'{B} button[data-wk-mode="gantt"]').click()
        settle(300)
        page.locator(f'{B} button[data-wk-mermaid]').click()
        settle(500)
        clip = page.evaluate('navigator.clipboard.readText()').replace(chr(13), '')
        check('복사한 글 — 두 업무와 section', '이슈 보고서 :active, t' in clip and '주간 보고 :milestone, t' in clip and 'section 리서치 총괄' in clip, clip)
        (proj / '보고서.md').write_text(md('보고서.md') + '\n' + clip, encoding='utf-8')
        open_doc('보고서.md')
        expect(page, '보고서에서 그림으로 그려진다', lambda: page.locator('#lec-view pre.mermaid svg, #lec-view .mermaid svg').count() >= 1, lambda: page.locator('#lec-view').inner_text()[-200:], 20000)

        print('[6 넣기 창으로 쪽 나눔]')
        page.locator('#lec-view p', has_text='첫 문단이다').click()
        page.click('#lec-btn-put')
        page.wait_for_selector('#lec-put.board:not([hidden])')
        page.keyboard.type('ㅉㄴ')
        settle(300)
        page.keyboard.press('Enter')
        expect(page, '쪽 나눔이 첫 문단 아래에', lambda: '첫 문단이다.\n\n<div style="page-break-after: always;"></div>\n' in md('보고서.md'), lambda: md('보고서.md')[:160])
        page.keyboard.press('Escape')

        print('[7 기획 메모 반영 요청]')
        open_doc('이슈/WORK.md')
        box = page.evaluate("""() => { const v = document.querySelector('#lec-view'); const r = v.getBoundingClientRect();
          const left = Math.min(...[...v.children].map((c) => c.getBoundingClientRect().left));
          const c = document.querySelector('#lec-content').getBoundingClientRect(); return { x: Math.max(r.left + 4, left - 14), y: c.top + Math.min(200, c.height / 3) }; }""")
        page.mouse.click(box['x'], box['y'], button='right')
        page.wait_for_selector('#lec-menu:not([hidden])')
        page.click('#lec-menu button:has-text("기획 메모 반영 요청")')
        settle(300)
        got = page.evaluate('() => window.__pasted.slice(-1)[0] || ""')
        check('요청 글 — 그 WORK.md 와 작성 안내', '@이슈/WORK.md' in got and "'기획 메모'" in got and 'writing.md' in got and '\n' not in got, got)
        final = md('이슈/WORK.md')
        check('하루가 끝난 WORK.md — 머리 설정·메모·할 일·일정이 제자리', final.startswith('---\nstatus: 진행\npriority: 중\nstart: ') and final.index('## 기획 메모') < final.index('메모 속 회의?') < final.index('## 할 일')
              < final.index('- [x] 공급사 자료 받기') < final.index('## 일정') < final.index('팀장 중간 보고') < final.index('## 기록'), final)
        check('화면 스크립트 오류 없음', not errors, errors[:3])
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
