"""업무의 간트·달력 보기 (D153): 보기 넷, 간트의 막대·점·묶음 막대·오늘 선, 시작 칸을 달력으로 고치기(start: 를 머리 설정에), 막대를 누르면 열기,
Mermaid 간트로 복사, 달력의 여러 날 막대·날 항목·달 옮기기·날짜를 누르면 그날로 일정 더하기, 읽지 못한 start 는 확인할 줄"""
import json
import tempfile
import traceback
from datetime import date, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop

base = Path(tempfile.mkdtemp(prefix='lec-workgantt-'))
today = date.today()
iso = lambda d: d.isoformat()
proj = base / '리서치'
home = base / 'home'


def card(status, title, due='', start='', events=()):
    lines = ['---', f'status: {status}', f'start: {start}', f'due: {due}', '---', '', f'# {title}', '', '## 일정', '']
    lines += [f'- {e}' for e in events]
    return '\n'.join(lines + ['', '## 기록', '']) + '\n'


def put(rel, text):
    path = proj / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


d = lambda n: iso(today + timedelta(days=n))
put('WORK.md', card('', '총괄'))
put('가/WORK.md', card('진행', '가 업무', d(6), d(-2), [f'{d(3)} 10:00 가 회의']))
put('나/WORK.md', card('막힘', '나 업무', d(9)))
put('다/WORK.md', card('완료', '다 업무', d(-3), d(-10)))
put('라/WORK.md', card('예정', '라 업무', '', '다음주'))   # 읽지 못한 시작
put('README.md', '# 리서치\n')
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
        B = '.wk-board:visible'
        toast = lambda: page.text_content('#lec-toast') or ''

        def open_board():
            page.keyboard.press('Escape')
            page.keyboard.press('Alt+w')
            page.wait_for_selector(f'{B} .wk-mode', timeout=10000)   # 보기는 칸마다 기억된다 (목록·칸반·간트·달력)
            settle()

        def mode(name):
            page.locator(f'{B} button[data-wk-mode="{name}"]').click()
            settle(300)

        grow = lambda title: f'{B} .wk-g-row:has(button.wk-open:text-is("{title}"))'

        print('[보기 넷]')
        open_board()
        names = page.locator(f'{B} .wk-mode button').all_inner_texts()
        check('목록 · 칸반 · 간트 · 달력', names == ['목록', '칸반', '간트', '달력'], names)
        check('읽지 못한 start 는 확인할 줄', '시작 날짜를 읽지 못했습니다' in page.locator(f'{B}').inner_text())

        print('[간트]')
        mode('gantt')
        check('간트가 그려짐', page.locator(f'{B} .wk-gantt').count() == 1)
        check('시작~마감 막대 (가)', page.locator(grow('가 업무') + ' .wk-g-bar').count() == 1)
        check('마감만이면 점 (나)', page.locator(grow('나 업무') + ' .wk-g-mile').count() == 1)
        check('묶음은 가는 막대 (총괄)', page.locator(grow('총괄') + ' .wk-g-bar.group').count() == 1)
        check('오늘 선', page.locator(f'{B} .wk-g-today').count() >= 1)
        check('끝난 하위는 접힘', page.locator(f'{B} .wk-g-row.wk-more').count() == 1 and page.locator(grow('다 업무')).count() == 0)
        # 시작 칸 → 달력 → 하루 뒤
        page.locator(grow('나 업무') + ' button[data-wk-act="start"]').click()
        page.wait_for_selector('#lec-datepick:not([hidden])')
        page.keyboard.press('Enter')   # 달력은 비어 있으면 오늘에서 시작
        expect(page, '시작 칸 → 달력 → start: 를 머리 설정에', lambda: f'start: {iso(today)}' in md('나/WORK.md'), lambda: md('나/WORK.md')[:80])
        expect(page, '— 다시 그리면 나 의 막대가 생김', lambda: page.locator(grow('나 업무') + ' .wk-g-bar').count() == 1)
        # Mermaid
        page.locator(f'{B} button[data-wk-mermaid]').click()
        settle(500)
        clip = page.evaluate('navigator.clipboard.readText()').replace(chr(13), '')   # Windows 클립보드는 줄 끝이 CRLF
        check('Mermaid 간트로 복사 — gantt·section·태그', clip.startswith('```mermaid\ngantt\n') and '  section 총괄' in clip and ':active, t' in clip and ':crit, t' in clip and clip.rstrip().endswith('```'), clip[:300])
        check('— 날짜가 없는 업무는 뺐다고 알림', '날짜가 없는 1개는 뺐습니다' in toast(), toast())
        # 막대를 누르면 연다
        page.locator(grow('가 업무') + ' .wk-g-bar').click()
        expect(page, '막대를 누르면 그 WORK.md 가 열림', lambda: page.locator('#lec-view h1', has_text='가 업무').count() == 1)

        print('[달력]')
        open_board()
        mode('calendar')
        check('달 격자', page.locator(f'{B} .wk-cal-week').count() >= 4)
        title = page.locator(f'{B} .wk-cal-nav b').inner_text()
        bar = page.locator(f'{B} .wk-cal-bar', has_text='가 업무')
        check('여러 날 막대 (가)', bar.count() >= 1, bar.count())
        check('날 항목 — 마감(■)과 일정(•)', page.locator(f'{B} .wk-cal-items .k-due', has_text='나 업무').count() >= 1 or d(9)[:7] != iso(today)[:7], '')
        page.locator(f'{B} button[data-wk-cal="1"]').click()
        settle(300)
        nxt = page.locator(f'{B} .wk-cal-nav b').inner_text()
        page.locator(f'{B} button[data-wk-cal="0"]').click()
        settle(300)
        check('› 다음 달, 이번 달로 돌아옴', nxt != title and page.locator(f'{B} .wk-cal-nav b').inner_text() == title, (title, nxt))
        page.locator(f'{B} .wk-cal-day.today').click()
        page.wait_for_selector('#lec-workevent:not([hidden])')
        check('날짜를 누르면 그날로 일정 더하기', page.locator('#lec-workevent-date').input_value() == iso(today), page.locator('#lec-workevent-date').input_value())
        page.keyboard.press('Escape')
        check('화면 스크립트 오류 없음', not errors, errors[:3])
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
