"""업무 관리 (D124) — 사용자 시나리오 시험 둘째 묶음: 시간 흐름(알림), 보기만 하는 예제, 영어 화면, 큰 것, 알림 끄기,
키보드만으로, 열린 문서와 함께. 첫째 묶음(오타·부분 삭제·입력 실수·파일 형식)은 work_scenarios.py.

  E 시간 흐름     10분 전 알림, 같은 알림은 한 번, 절전에서 깬 듯 건너뛴 일정은 알리지 않음, 17:30 기록 알림, 자정 뒤 새 요약
  F 예제          보기만 하는 예제는 열어도 기억하지 않고 더할 수도 없음, 복사본은 기억
  G 영어 화면     표의 말·영어 기본 틀·Schedule 절·all-day, 한국어 값도 읽음
  H 큰 것         폴더 40개, 2MB 넘는 WORK.md, 아주 긴 제목, 할 일 500개
  I 알림 끄기     설정을 끄면 켤 때 요약도 없음
  J 키보드만으로  Alt+S → 쓰고 Enter, Esc 는 쓰지 않음, 입력칸 안의 Alt+S 는 창을 열지 않음
  K 열린 문서     WORK.md 를 보고 있는 탭이 넣은 일정을 따라 다시 그림
"""
import json
import os
import shutil
import tempfile
import time
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import ROOT, check, fails, report, serve, stop

base = Path(tempfile.mkdtemp(prefix='lec-workmore-'))
today = date.today()
iso = today.isoformat()
local = datetime.now().astimezone()
at = lambda h, m, day=today: local.replace(year=day.year, month=day.month, day=day.day, hour=h, minute=m, second=0, microsecond=0)


def make(root: Path, text=None, raw=None):
    root.mkdir(parents=True, exist_ok=True)
    (root / 'README.md').write_text(f'# {root.name}\n', encoding='utf-8')
    if raw is not None:
        (root / 'WORK.md').write_bytes(raw)
    elif text is not None:
        (root / 'WORK.md').write_text(text, encoding='utf-8')
    return root.resolve()


def config(path: Path, data: dict) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / 'config.json').write_text(json.dumps(data), encoding='utf-8')
    return path


def open_page(p, url, clock_at=None):
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('dialog', lambda d: d.accept(answers.pop(0)) if (d.type == 'prompt' and answers) else (d.accept() if d.type == 'beforeunload' else d.dismiss()))
    if clock_at:
        page.clock.install(time=clock_at)
    page.goto(url)
    page.wait_for_selector('#lec-tablist')
    return browser, page, errors


answers = []
notes = lambda page: page.locator('#lec-work-notes').inner_text() if page.locator('#lec-work-notes').count() else ''
count_notes = lambda page, text: page.locator('#lec-work-notes .wk-notice', has_text=text).count()


def until(page, fn, ms=6000):
    for _ in range(ms // 100):
        if fn():
            return True
        page.wait_for_timeout(100)
    return fn()


def read(root):
    for _ in range(20):
        try:
            return (root / 'WORK.md').read_text(encoding='utf-8')
        except OSError:
            time.sleep(0.05)
    return ''


try:
    with sync_playwright() as p:
        # ---- E 시간 흐름 ---------------------------------------------------------------------------
        print('[E 시간 흐름 — 페이지의 시계를 옮겨 가며]')
        tomorrow = (today + timedelta(days=1)).isoformat()
        e_home = make(base / 'e' / 'home', f'# 공통 업무\n\n## 일정\n\n- {iso} 09:10 아침 회의\n- {iso} 09:20 건너뛸 회의\n- {tomorrow} 10:00 내일 회의\n')
        e_task = make(base / 'e' / 'task', '---\nstatus: 진행\n---\n\n# 기록 안 한 과제\n')
        yesterday = time.time() - 86400
        os.utime(e_task / 'WORK.md', (yesterday, yesterday))
        cfg = config(base / 'e' / 'config', {'work_home': str(e_home), 'work_folders': [str(e_task)]})
        server, url, port = serve(e_home, cfg)
        try:
            browser, page, errors = open_page(p, url, clock_at=at(8, 58))
            check('E 켤 때 오늘의 요약', until(page, lambda: count_notes(page, '오늘의 업무') == 1, 9000), notes(page))
            check('E 아직 10분 밖이면 일정 알림 없음', count_notes(page, '곧 시작') == 0)
            page.clock.fast_forward('02:30')   # 09:00:30 — 09:10 회의의 10분 안
            check('E 10분 전 알림', until(page, lambda: count_notes(page, '09:10 일정') == 1), notes(page))
            page.clock.fast_forward('01:00')
            page.wait_for_timeout(1500)
            check('E 같은 일정은 한 번만 알림', count_notes(page, '09:10 일정') == 1, notes(page))
            page.clock.fast_forward('23:30')   # 09:25 — 09:20 회의가 지났다 (절전에서 깬 듯)
            page.wait_for_timeout(1500)
            check('E 건너뛴 시각의 일정은 알리지 않음', count_notes(page, '건너뛸 회의') == 0, notes(page))
            check('E 17:30 전에는 기록 알림 없음', count_notes(page, '오늘 기록이 없는') == 0)
            page.clock.fast_forward('08:06:00')   # 17:31
            check('E 17:30 이 지나면 오늘 기록이 없는 진행 과제 알림', until(page, lambda: count_notes(page, '오늘 기록이 없는') == 1), notes(page))
            page.clock.fast_forward('01:00:00')
            page.wait_for_timeout(1500)
            check('E 기록 알림은 그날 한 번', count_notes(page, '오늘 기록이 없는') == 1, notes(page))
            page.clock.fast_forward('05:40:00')   # 다음 날 00:11
            check('E 자정이 지나면 새 날의 요약 (그날 일정)', until(page, lambda: count_notes(page, tomorrow) == 1 and '내일 회의' in notes(page)), notes(page))
            check('E 페이지 오류 없음', not errors, errors)
            browser.close()
        finally:
            stop(server, base / 'e-unused')

        # ---- F 보기만 하는 예제 ----------------------------------------------------------------------
        print('[F 보기만 하는 예제]')
        f_home = make(base / 'f' / 'home', '# 공통 업무\n\n## 일정\n')
        copy = base / 'f' / 'samples-copy'
        shutil.copytree(ROOT / 'samples', copy)
        cfg = config(base / 'f' / 'config', {'work_home': str(f_home), 'work_folders': []})
        server, url, port = serve(f_home, cfg)
        try:
            browser, page, errors = open_page(p, url)
            api = lambda path, body: page.evaluate("async ([u, b]) => { const r = await fetch(u, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(b)}); return [r.status, await r.json()]; }", [path, body])
            cfgnow = lambda: page.evaluate("async () => (await (await fetch('/api/config')).json())")
            api('/api/open', {'path': str(ROOT / 'samples')})
            check('F 예제를 열어도 업무 폴더 목록에 들어가지 않음', cfgnow()['work_folders'] == [])
            status, body = api('/api/work/folders', {'add': str(ROOT / 'samples')})
            check('F 예제는 폴더 더하기도 되지 않음 (까닭: 복사해 쓰기)', status == 403 and '복사' in body.get('error', ''), body)
            api('/api/open', {'path': str(copy)})
            check('F 예제의 복사본은 기억', str(copy.resolve()) in cfgnow()['work_folders'])
            page.goto(url)
            page.wait_for_selector('#lec-tablist')
            page.keyboard.press('Alt+w')
            page.wait_for_selector('.wk-board:visible .wk-table', timeout=10000)
            board = page.locator('.wk-board:visible').inner_text()
            check('F 복사본의 견본 WORK.md 가 업무 현황에', '구리 시장 리서치 자동화' in board, board[:300])
            check('F 견본에는 확인할 줄이 없음', '확인할 줄' not in board)
            check('F 페이지 오류 없음', not errors, errors)
            browser.close()
        finally:
            stop(server, base / 'f-unused')

        # ---- G 영어 화면 ----------------------------------------------------------------------------
        print('[G 영어 화면]')
        g_home = make(base / 'g' / 'home', '# Common work\n\n## Schedule\n\n## To do\n')
        g_task = make(base / 'g' / 'task', f'---\nstatus: 진행\npriority: high\ndue: {(today + timedelta(days=2)).isoformat()}\n---\n\n# Korean status task\n')
        g_new = base / 'g' / 'newtask'
        g_new.mkdir(parents=True)
        (g_new / 'README.md').write_text('# newtask\n', encoding='utf-8')
        cfg = config(base / 'g' / 'config', {'language': 'en', 'work_home': str(g_home), 'work_folders': [str(g_task)]})
        server, url, port = serve(g_home, cfg)
        try:
            browser, page, errors = open_page(p, url)
            page.keyboard.press('Alt+w')
            page.wait_for_selector('.wk-board:visible .wk-table', timeout=10000)
            board = page.locator('.wk-board:visible').inner_text()
            check('G 영어 표의 말', 'Work board' in board and 'Due soon' in board, board[:200])
            check('G 한국어 상태 값도 읽어 영어로', page.locator('.wk-board:visible .wk-st').first.inner_text() == 'Active')
            check('G 화면에 한글이 남지 않음 (파일의 글 빼고)', not any('가' <= ch <= '힣' for ch in board), board)
            page.keyboard.press('Alt+s')
            page.wait_for_selector('#lec-workevent:not([hidden])')
            page.locator('#lec-workevent-where').select_option(index=0)
            page.locator('#lec-workevent-allday').check()
            page.locator('#lec-workevent-text').fill('Offsite')
            page.locator('#lec-workevent-go').click()
            check('G 공통 WORK.md 의 Schedule 절에 all-day 로', until(page, lambda: f'## Schedule\n\n- {iso} all-day Offsite\n' in read(g_home)), read(g_home))
            page.evaluate("async (p) => fetch('/api/open', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({path: p})})", str(g_new))
            page.goto(url)
            page.wait_for_selector('#lec-tablist')
            page.locator('.lec-tab', has_text='newtask').click()
            page.wait_for_timeout(500)
            page.locator('.lec-tab', has_text='newtask').click(button='right')
            page.locator('#lec-menu').get_by_text('Make work card…').click()
            page.wait_for_selector('#lec-workcard:not([hidden])')
            check('G 우선 값은 영어 (high·medium·low)', page.locator('#lec-workcard-pri option').all_inner_texts() == ['high', 'medium', 'low'])
            page.locator('#lec-workcard-go').click()
            check('G 영어 기본 틀 (planned·Schedule)', until(page, lambda: 'status: planned' in read(g_new) and '## Schedule' in read(g_new) and 'priority: medium' in read(g_new)), read(g_new))
            check('G 페이지 오류 없음', not errors, errors)
            browser.close()
        finally:
            stop(server, base / 'g-unused')

        # ---- H 큰 것 / I 알림 끄기 / J 키보드 / K 열린 문서 ----------------------------------------------
        print('[H 큰 것]')
        h_home = make(base / 'h' / 'home', '# 공통 업무\n\n## 일정\n')
        many = [make(base / 'h' / f'p{i:02d}', f'---\nstatus: 진행\ndue: {(today + timedelta(days=i)).isoformat()}\n---\n\n# 과제 {i:02d}\n') for i in range(40)]
        big = make(base / 'h' / 'big', raw=('---\nstatus: 진행\n---\n\n# 큰 파일\n\n' + '기록 줄입니다.\n' * 200000).encode('utf-8'))
        long_title = '아주 긴 제목 ' * 40
        longt = make(base / 'h' / 'long', f'---\nstatus: 진행\n---\n\n# {long_title}\n')
        todos = make(base / 'h' / 'todos', '---\nstatus: 진행\n---\n\n# 할 일 많은 과제\n\n' + ''.join(f'- [ ] 할 일 {i} ({iso})\n' for i in range(500)))
        cfg = config(base / 'h' / 'config', {'work_home': str(h_home), 'work_folders': [str(x) for x in [*many, big, longt, todos]]})
        server, url, port = serve(h_home, cfg)
        try:
            browser, page, errors = open_page(p, url)
            started = time.time()
            page.keyboard.press('Alt+w')
            page.wait_for_selector('.wk-board:visible .wk-table', timeout=15000)
            took = time.time() - started
            board = page.locator('.wk-board:visible')
            check(f'H 폴더 43개도 곧 그림 ({took:.1f}초)', took < 6 and board.locator('tbody tr').count() >= 42, board.locator('tbody tr').count())
            check('H 2MB 넘는 WORK.md 는 읽지 않고 까닭', '2MB' in board.locator('.wk-bad').inner_text(), board.locator('.wk-bad').inner_text() if board.locator('.wk-bad').count() else '')
            width = page.evaluate("() => { const b = document.querySelector('.wk-board'); return [b.scrollWidth, b.clientWidth]; }")
            check('H 아주 긴 제목도 표가 옆으로 넘치지 않음', width[0] <= width[1] + 2, width)
            todo_items = board.locator('.wk-list').nth(0).locator('li')
            check('H 할 일 500개는 50개만 보이고 나머지는 개수로', todo_items.count() == 51 and '그 밖에 450개' in todo_items.last.inner_text(), todo_items.count())

            print('[J 키보드만으로]')
            page.locator('#lec-work-notes .wk-n-close').first.click() if page.locator('#lec-work-notes .wk-n-close').count() else None
            page.keyboard.press('Alt+s')
            page.wait_for_selector('#lec-workevent:not([hidden])')
            check('J Alt+S 로 열면 내용 칸에 초점', page.evaluate("document.activeElement.id") == 'lec-workevent-text')
            page.keyboard.type('키보드로 넣은 일정')
            page.keyboard.press('Enter')
            check('J Enter 로 넣음', until(page, lambda: f'- {iso} 키보드로 넣은 일정' in read(h_home)), read(h_home))
            before = read(h_home)
            page.keyboard.press('Alt+s')
            page.wait_for_selector('#lec-workevent:not([hidden])')
            page.keyboard.type('넣지 않을 일정')
            page.keyboard.press('Escape')
            page.wait_for_timeout(300)
            check('J Esc 는 닫기만 하고 쓰지 않음', page.locator('#lec-workevent').is_hidden() and read(h_home) == before)
            page.locator('#lec-filter').click()
            page.keyboard.press('Alt+s')
            page.wait_for_timeout(300)
            check('J 입력칸 안의 Alt+S 는 창을 열지 않음', page.locator('#lec-workevent').is_hidden())
            page.keyboard.press('Escape')
            page.evaluate("async (p) => fetch('/api/open', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({path: p})})", str(many[3]))
            page.goto(url)
            page.wait_for_selector('#lec-tablist')
            page.locator('.lec-tab', has_text='p03').click()
            page.wait_for_timeout(500)
            page.keyboard.press('Alt+s')
            page.wait_for_selector('#lec-workevent:not([hidden])')
            chosen = page.evaluate("(() => { const s = document.querySelector('#lec-workevent-where'); return s.options[s.selectedIndex].text; })()")
            check('J 넣을 곳의 처음 값은 지금 보는 프로젝트의 WORK.md', '과제 03' in chosen, chosen)
            page.keyboard.press('Escape')
            page.locator('.lec-tab', has_text='home').click()
            page.wait_for_timeout(500)

            print('[K 열린 문서와 함께]')
            page.locator('#lec-tree .row.file[data-doc="WORK.md"]').click()
            page.wait_for_selector('#lec-view h1')
            page.wait_for_timeout(500)
            page.keyboard.press('Alt+s')
            page.wait_for_selector('#lec-workevent:not([hidden])')
            page.locator('#lec-workevent-time').fill('14:00')
            page.locator('#lec-workevent-text').fill('열린 문서에 보일 일정')
            page.keyboard.press('Enter')
            check('K 보고 있는 WORK.md 가 넣은 일정을 따라 다시 그림', until(page, lambda: '열린 문서에 보일 일정' in page.locator('#lec-view').inner_text(), 8000))

            print('[I 알림 끄기]')
            page.keyboard.press('Control+,')
            page.wait_for_selector('#lec-settings:not([hidden])')
            box = page.locator('#lec-settings input[data-key="work_alerts"]')
            check('I 설정 창에 업무 알림 (처음엔 켜짐)', box.is_checked())
            box.uncheck()
            page.wait_for_timeout(500)
            page.goto(url)
            page.wait_for_selector('#lec-tablist')
            page.wait_for_timeout(6000)
            check('I 끄면 켤 때 요약도 없음', page.locator('#lec-work-notes .wk-notice').count() == 0, notes(page))
            check('H·I·J·K 페이지 오류 없음', not errors, errors)
            browser.close()
        finally:
            stop(server, base / 'h-unused')
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    shutil.rmtree(base, ignore_errors=True)

report()
