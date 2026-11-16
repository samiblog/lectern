"""시나리오 — 간트·달력의 가장자리 (D153): 업무 100건, 해를 넘기는 일정, 날짜가 하나도 없는 프로젝트, 읽지 못한 시작·마감보다 늦은 시작,
한 날에 일정 8건, 간트에서 마감을 시작 앞으로 옮기면, 시작을 비우면, 묶음 폴더의 개요와 상위 WORK.md 아래 칸에서 (날짜를 누르면 그 업무가 넣을 곳),
보기는 칸마다 기억, 영어 화면."""
import json
import tempfile
import time
import traceback
from datetime import date, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop

base = Path(tempfile.mkdtemp(prefix='lec-scengantt-'))
today = date.today()
d = lambda n: (today + timedelta(days=n)).isoformat()
proj = base / '리서치'
bare = base / '날짜없음'
home = base / 'home'


def card(status, title, due='', start='', events=()):
    lines = ['---', f'status: {status}', f'start: {start}', f'due: {due}', '---', '', f'# {title}', '', '## 일정', '']
    lines += [f'- {e}' for e in events]
    return '\n'.join(lines + ['', '## 기록', '']) + '\n'


def put(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


put(proj, 'WORK.md', card('', '총괄'))
put(proj, '많음/WORK.md', card('', '백 건 묶음'))
for i in range(1, 101):
    st = '완료' if i <= 60 else '진행' if i <= 90 else '막힘'
    put(proj, f'많음/{i:03d}/WORK.md', card(st, f'일 {i:03d}', d(i % 40 + 1), d(i % 40 - 6)))
put(proj, '해넘김/WORK.md', card('', '해를 넘기는 묶음'))
put(proj, '해넘김/가/WORK.md', card('진행', '연말 보고', f'{today.year + 1}-01-20', f'{today.year}-12-10'))
put(proj, '해넘김/나/WORK.md', card('예정', '신년 계획', f'{today.year + 1}-03-05', f'{today.year + 1}-02-01'))
put(proj, '이상/WORK.md', card('진행', '읽지 못한 시작', d(10), '2026-13-40'))
put(proj, '거꾸로/WORK.md', card('진행', '시작이 더 늦음', d(3), d(8)))
put(proj, '붐빔/WORK.md', card('진행', '일정이 많은 날', d(5), d(1), [f'{d(2)} {9 + k:02d}:00 회의 {k + 1}' for k in range(8)]))
put(proj, 'README.md', '# 리서치\n')
put(bare, 'WORK.md', card('진행', '날짜 없는 일'))
put(bare, 'README.md', '# 날짜 없음\n')
home.mkdir()
(home / 'WORK.md').write_text('# 공통 업무\n\n## 일정\n\n## 할 일\n', encoding='utf-8')
config = base / 'config'
config.mkdir()
cfg = {'work_home': str(home.resolve()), 'work_alerts': False}
(config / 'config.json').write_text(json.dumps(cfg), encoding='utf-8')
md = lambda rel: (proj / rel).read_text(encoding='utf-8')

server, url, port = serve(proj, config)
try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(viewport={'width': 1440, 'height': 950}).new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')
        settle = lambda ms=400: page.wait_for_timeout(ms)
        B = '.wk-board:not(.wk-under):not(.wk-folder-work):visible'   # 업무 현황의 칸만 — Alt+W 직후에는 앞 화면의 하위 업무 칸이 아직 보인다
        OPEN = "(o) => import('/static/js/store.js').then((m) => m.emit('open', o))"
        grow = lambda scope, title: f'{scope} .wk-g-row:has(button.wk-open:text-is("{title}"))'

        def board(mode=None):
            page.keyboard.press('Escape')
            # 방금 닫은 창의 입력 칸이 아직 초점을 쥐고 있으면(다음 화면을 그릴 때 풀린다) Alt+W 가 글 입력으로 여겨진다 — 사람 손으로는 못 누를 틈
            page.wait_for_function("() => !document.activeElement?.closest('[hidden]')")
            page.keyboard.press('Alt+w')
            page.wait_for_selector(f'{B} .wk-mode', timeout=15000)
            settle()
            if mode:
                page.locator(f'{B} button[data-wk-mode="{mode}"]').first.click()
                settle(300)

        def project_tab():
            page.keyboard.press('Escape')
            page.locator('.lec-tab', has_text='리서치').first.click()
            settle(300)

        print('[업무 100건]')
        board()
        began = time.time()
        page.locator(f'{B} button[data-wk-mode="gantt"]').first.click()
        page.wait_for_selector(f'{B} .wk-gantt')
        took = time.time() - began
        rows = page.locator(f'{B} .wk-g-row:not(.wk-g-head)').count()
        check(f'107건의 간트가 곧 그려짐 ({took:.1f}초, {rows}줄)', took < 4 and rows >= 40, (took, rows))
        check('끝난 60건은 한 줄로 접힘', page.locator(f'{B} .wk-g-row.wk-more', has_text='60건').count() == 1)
        check('열린 40건의 막대', page.locator(f'{B} .wk-g-bar:not(.group)').count() >= 40, page.locator(f'{B} .wk-g-bar:not(.group)').count())
        left = page.evaluate("""(sel) => [...document.querySelectorAll(sel)].every((e) => { const l = parseFloat(e.style.left); const w = parseFloat(e.style.width || '0'); return l >= 0 && l + w <= 100.01; })""",
                             '.wk-gantt .wk-g-bar, .wk-gantt .wk-g-mile')
        check('막대와 점이 모두 눈금 안에', left)
        began = time.time()
        page.locator(f'{B} button[data-wk-mode="calendar"]').first.click()
        page.wait_for_selector(f'{B} .wk-cal-week')
        check(f'달력도 곧 ({time.time() - began:.1f}초)', time.time() - began < 4)
        more = page.locator(f'{B} .wk-cal-items li.wk-faint').count()
        check("한 날에 다 못 보이는 항목은 '그 밖에 n개'", more >= 1, more)
        check('일정 8건인 날 — 다섯까지 보이고 나머지는 셈', page.locator(f'{B} .wk-cal-items', has_text='회의 1').locator('li').count() <= 6)

        print('[해를 넘기는 일정]')
        page.locator(f'{B} button[data-wk-mode="gantt"]').first.click()
        settle(300)
        ticks = page.locator(f'{B} .wk-g-scale span').all_inner_texts()
        check('기간이 길면 달 눈금 — 1월이 있다', '1월' in ticks and len(ticks) <= 12, ticks)
        page.locator(f'{B} button[data-wk-mode="calendar"]').first.click()
        settle(300)
        title = lambda: page.locator(f'{B} .wk-cal-nav b').inner_text()
        for _ in range(14):
            if title().startswith(f'{today.year + 1}년 1월'):
                break
            page.locator(f'{B} button[data-wk-cal="1"]').click()
            settle(120)
        check('› 로 12월에서 다음 해 1월로', title() == f'{today.year + 1}년 1월', title())
        check('— 해를 넘긴 막대가 1월에도 (앞 달에서 이어짐)', page.locator(f'{B} .wk-cal-bar.cont-l', has_text='연말 보고').count() >= 1)
        page.locator(f'{B} button[data-wk-cal="-1"]').click()
        settle(150)
        check('‹ 로 12월', title() == f'{today.year}년 12월', title())
        page.locator(f'{B} button[data-wk-cal="0"]').click()
        settle(150)
        check('이번 달로', title() == f'{today.year}년 {today.month}월', title())

        print('[이상한 날짜]')
        board('gantt')
        text = page.locator(B).inner_text()
        check('읽지 못한 시작은 확인할 줄, 간트의 칸에는 쓴 글 그대로', '시작 날짜를 읽지 못했습니다' in text and page.locator(grow(B, '읽지 못한 시작') + ' button[data-wk-act="start"]').inner_text() == '2026-13-40')
        check('— 그 업무는 마감 날의 점', page.locator(grow(B, '읽지 못한 시작') + ' .wk-g-mile').count() == 1)
        check('시작이 마감보다 늦으면 확인할 줄과 점', '시작이 마감보다 늦습니다' in text and page.locator(grow(B, '시작이 더 늦음') + ' .wk-g-mile').count() == 1)
        # 마감을 시작 뒤로 옮기면 막대가 된다
        page.locator(grow(B, '시작이 더 늦음') + ' button[data-wk-act="due"]').click()
        page.wait_for_selector('#lec-datepick:not([hidden])')
        for _ in range(2):
            page.keyboard.press('ArrowDown')   # 두 주 뒤
        page.keyboard.press('Enter')
        expect(page, '마감을 두 주 뒤로 — WORK.md 의 due', lambda: f'due: {d(17)}' in md('거꾸로/WORK.md'), lambda: md('거꾸로/WORK.md')[:80])
        expect(page, '— 막대가 되고 확인할 줄에서 빠짐', lambda: page.locator(grow(B, '시작이 더 늦음') + ' .wk-g-bar').count() == 1 and '시작이 마감보다 늦습니다' not in page.locator(B).inner_text())
        # 시작을 비우면 다시 점
        settle(600)
        page.locator(grow(B, '시작이 더 늦음') + ' button[data-wk-act="start"]').click()
        page.wait_for_selector('#lec-datepick:not([hidden])')
        page.locator('#lec-datepick button[data-quick="clear"]').click()
        expect(page, '시작을 비우면 start: 만 남고 점으로', lambda: '\nstart:\n' in md('거꾸로/WORK.md') and page.locator(grow(B, '시작이 더 늦음') + ' .wk-g-mile').count() == 1, lambda: md('거꾸로/WORK.md')[:80])

        print('[묶음 폴더의 개요 · 상위 WORK.md 아래]')
        project_tab()
        page.evaluate(OPEN, {'type': 'overview', 'path': '해넘김'})
        F = '.wk-folder-work'
        page.wait_for_selector(f'{F} .wk-mode', timeout=10000)
        check('폴더 개요는 목록에서 시작 (보기는 칸마다 따로)', page.locator(f'{F} button[data-wk-mode="list"]').get_attribute('aria-pressed') == 'true')
        page.locator(f'{F} button[data-wk-mode="gantt"]').click()
        settle(300)
        check("'이 폴더의 업무'의 간트 — 그 묶음과 하위 둘", page.locator(f'{F} .wk-g-row:not(.wk-g-head)').count() == 3 and page.locator(grow(F, '해를 넘기는 묶음') + ' .wk-g-bar.group').count() == 1)
        page.evaluate(OPEN, {'type': 'doc', 'path': '해넘김/WORK.md'})
        U = '.wk-under'
        page.wait_for_selector(f'{U} .wk-mode', timeout=10000)
        page.locator(f'{U} button[data-wk-mode="calendar"]').click()
        settle(300)
        page.locator(f'{U} .wk-cal-day:not(.out)').nth(9).click()
        page.wait_for_selector('#lec-workevent:not([hidden])')
        chosen = page.evaluate("() => { const s = document.querySelector('#lec-workevent-where'); return s.options[s.selectedIndex].textContent; }")
        check('하위 업무 칸의 달력에서 날짜를 누르면 — 넣을 곳은 그 묶음', '해를 넘기는 묶음' in chosen, chosen)
        check('— 날짜는 누른 날', page.locator('#lec-workevent-date').input_value().endswith('-10'), page.locator('#lec-workevent-date').input_value())
        page.keyboard.press('Escape')
        board()
        expect(page, '업무 현황은 간트 그대로 (칸마다 기억)', lambda: page.locator(f'{B} button[data-wk-mode="gantt"]').first.get_attribute('aria-pressed') == 'true',
               lambda: page.locator(f'{B} .wk-mode').first.inner_html()[:300])

        print('[날짜가 하나도 없는 프로젝트]')
        browser.close()
        server.terminate()
        server.wait(10)
        (config / 'config.json').write_text(json.dumps(cfg), encoding='utf-8')
        server, url, port = serve(bare, config)
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={'width': 1440, 'height': 950})
        ctx.grant_permissions(['clipboard-read', 'clipboard-write'], origin=url.rstrip('/'))
        page = ctx.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')
        board('gantt')
        only = page.locator(f'{B} .wk-g-row:has(button.wk-open:text-is("날짜 없는 일"))')
        if only.count():   # 앞 프로젝트의 업무가 목록에 남아 있다 — 이 업무만 본다
            check('날짜가 없는 업무는 막대도 점도 없다', only.locator('.wk-g-bar, .wk-g-mile').count() == 0)
        else:
            check('날짜가 없으면 까닭을 알린다', '시작·마감 날짜가 있는 업무가 없습니다' in page.locator(B).inner_text(), page.locator(B).inner_text()[:200])

        print('[영어 화면]')
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ language: 'en' }))")
        settle(500)
        page.reload()
        page.wait_for_selector('#lec-tree .row.file')
        board()
        names = page.locator(f'{B} .wk-mode').first.locator('button').all_inner_texts()
        check('List · Kanban · Gantt · Calendar', names == ['List', 'Kanban', 'Gantt', 'Calendar'], names)
        page.locator(f'{B} button[data-wk-mode="calendar"]').first.click()
        settle(300)
        en_title = page.locator(f'{B} .wk-cal-nav b').inner_text()
        dows = page.locator(f'{B} .wk-cal-dows span').all_inner_texts()
        check('달 이름과 요일이 영어', str(today.year) in en_title and not any('가' <= c <= '힣' for c in en_title) and dows[0] == 'Sun', (en_title, dows))
        page.locator(f'{B} button[data-wk-mode="gantt"]').first.click()
        settle(300)
        check('날짜가 없다는 안내도 영어', 'No work has start or due dates' in page.locator(B).inner_text(), page.locator(B).inner_text()[:200])
        korean = [x for x in page.locator(f'{B} .wk-tree-head').inner_text().split() if any('가' <= c <= '힣' for c in x)]
        check('보기 머리에 남은 한글 없음', not korean, korean)
        check('화면 스크립트 오류 없음', not errors, errors[:3])
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
