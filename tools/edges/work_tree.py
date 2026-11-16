"""업무 나무 (D149): 폴더마다 WORK.md, 상위는 하위를 모아 보이고 상위에서 고치면 하위 파일이 고쳐진다. 칸반, 달력 입력.

  A 나무        업무 현황의 나무 — 부모는 가장 가까운 위 업무, 비운 상태는 하위에서 셈(막힘*), 주의할 것에 깊은 하위도
  B 고치기      상태(메뉴)·할 일 체크·할 일 더하기·마감(달력)이 그 하위 WORK.md 한 줄만 바꿈, 그사이 줄이 바뀌었으면 쓰지 않음
  C 칸반        끝 업무가 상태 다섯 칸에, 끌어 놓으면 그 WORK.md 의 상태
  D 칸          총괄·묶음 폴더 개요의 '이 폴더의 업무', 상위 WORK.md 아래의 '하위 업무'(본문 밖), 하위 업무는 품은 프로젝트 탭에서 열림
  E 만들기      사이드바 폴더 우클릭 '이 폴더에 업무 카드 만들기' — 작은 업무 틀, 나무에 들어감
  F 날짜        일정 더하기의 달력 단추·잘못 쓴 날짜, 한 줄 편집 칸의 Ctrl+;"""
import json
import time
import tempfile
import traceback
from datetime import date, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop

base = Path(tempfile.mkdtemp(prefix='lec-worktree-'))
today = date.today()
iso = lambda d: d.isoformat()
proj = base / '원자재'
home = base / 'home'


def card(status, title, due='', todos=(), extra=''):
    lines = ['---', f'status: {status}', f'due: {due}', '---', '', f'# {title}', '', '## 할 일', '']
    lines += [f'- [ ] {x}' for x in todos]
    return '\n'.join(lines + ['', '## 기록', '', extra]).rstrip() + '\n'


def put(rel, text):
    path = proj / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return path


put('WORK.md', card('', '2026 원자재 리서치', iso(today + timedelta(days=40))))
put('이슈리포트/WORK.md', card('', '하반기 이슈리포트', iso(today + timedelta(days=20))))
put('이슈리포트/01-구리/WORK.md', card('완료', '01 구리 관세'))
put('이슈리포트/02-리튬/WORK.md', card('막힘', '02 리튬 공급', iso(today + timedelta(days=5)), ['재고 자료 받기', '초안 쓰기']))
put('이슈리포트/03-니켈/WORK.md', card('진행', '03 니켈 재고', iso(today + timedelta(days=30)), ['표 정리']))   # 묶음 마감보다 늦다
put('정기보고/주간/WORK.md', card('진행', '주간 보고', iso(today + timedelta(days=2))))
put('정기보고/주간/메모.md', '# 주간 메모\n\n첫 줄입니다.\n')
put('README.md', '# 원자재\n')
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
        page = browser.new_page(viewport={'width': 1440, 'height': 950})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')
        settle = lambda ms=400: page.wait_for_timeout(ms)
        board = lambda: page.locator('.wk-board:visible').first
        rowsel = lambda title: f'.wk-board:visible tr.wk-tr:has(button.wk-open:text-is("{title}"))'

        def open_board():
            page.keyboard.press('Escape')
            page.keyboard.press('Alt+w')
            page.wait_for_selector('.wk-board:visible .wk-tree', timeout=10000)
            settle()

        print('[A 나무]')
        open_board()
        titles = page.locator('.wk-board:visible .wk-tree button.wk-open').all_inner_texts()
        check('A 나무 차례 — 총괄 아래 묶음·주간, 묶음 아래 02·03 (완료 01 은 접힘)', titles[:5] == ['2026 원자재 리서치', '주간 보고', '하반기 이슈리포트', '02 리튬 공급', '03 니켈 재고'] or titles[:5] == ['2026 원자재 리서치', '하반기 이슈리포트', '02 리튬 공급', '03 니켈 재고', '주간 보고'], titles)
        depth = lambda title: page.locator(rowsel(title) + ' td.wk-title').first.evaluate("e => getComputedStyle(e).getPropertyValue('--wk-depth').trim()")
        check('A 들여쓰기 — WORK.md 없는 정기보고 폴더는 건너뜀', [depth('2026 원자재 리서치'), depth('하반기 이슈리포트'), depth('02 리튬 공급'), depth('주간 보고')] == ['0', '1', '2', '1'],
              [depth(x) for x in ('2026 원자재 리서치', '하반기 이슈리포트', '02 리튬 공급', '주간 보고')])
        st = lambda title: page.locator(rowsel(title) + ' .wk-st').first.inner_text()
        check('A 비운 상태는 하위에서 셈 — 막힘*', st('하반기 이슈리포트') == '막힘*' and st('2026 원자재 리서치') == '막힘*', [st('하반기 이슈리포트'), st('2026 원자재 리서치')])
        check('A 하위 요약', '하위 3' in page.locator(rowsel('하반기 이슈리포트')).inner_text(), page.locator(rowsel('하반기 이슈리포트')).inner_text())
        hot = page.locator('.wk-board:visible .wk-hotlist').inner_text()
        check('A 주의할 것 — 깊은 하위가 경로와 함께, 하위 마감이 늦은 묶음도', '하반기 이슈리포트 › 02 리튬 공급' in hot and '하위 마감이 더 늦음' in hot, hot)
        check('A 완료 하위는 접힘 단추로', page.locator('.wk-board:visible tr.wk-more').count() == 1)
        page.locator('.wk-board:visible tr.wk-more button').click()
        settle()
        check('A 펼치면 01 이 보임', page.locator(rowsel('01 구리 관세')).count() == 1)

        print('[B 상위에서 고치기]')
        page.locator(rowsel('03 니켈 재고') + ' button[data-wk-act="status"]').click()
        page.wait_for_selector('#lec-menu:not([hidden])')
        page.locator('#lec-menu button', has_text='보류').first.click()
        check('B 상태 → 하위 WORK.md 의 그 줄만', expect(page, '03 의 status: 보류', lambda: 'status: 보류' in md('이슈리포트/03-니켈/WORK.md')) is not False
              and md('이슈리포트/03-니켈/WORK.md') == card('보류', '03 니켈 재고', iso(today + timedelta(days=30)), ['표 정리']))
        expect(page, 'B 다시 그림', lambda: st('03 니켈 재고') == '보류')
        page.locator(rowsel('02 리튬 공급') + ' button[data-wk-act="todos"]').click()
        page.wait_for_selector('.wk-board:visible .wk-todos-row input[data-wk-todo]')
        page.locator('.wk-board:visible .wk-todos-row li', has_text='재고 자료 받기').locator('input[type="checkbox"]').check()
        expect(page, 'B 할 일 체크 → [x]', lambda: '- [x] 재고 자료 받기' in md('이슈리포트/02-리튬/WORK.md'))
        settle(500)
        add = page.locator('.wk-board:visible .wk-todos-row input[data-wk-add]')
        if not add.count():
            page.locator(rowsel('02 리튬 공급') + ' button[data-wk-act="todos"]').click()
        page.locator('.wk-board:visible .wk-todos-row input[data-wk-add]').fill('공급사 통화')
        page.locator('.wk-board:visible .wk-todos-row input[data-wk-add]').press('Enter')
        expect(page, 'B 할 일 더하기 → 할 일 절 끝에', lambda: '- [ ] 초안 쓰기\n- [ ] 공급사 통화\n' in md('이슈리포트/02-리튬/WORK.md'))
        settle(500)
        page.locator(rowsel('02 리튬 공급') + ' button[data-wk-act="due"]').click()
        page.wait_for_selector('#lec-datepick:not([hidden])')
        check('B 마감 단추 → 달력', page.locator('#lec-datepick .dp-grid button').count() == 42)
        page.keyboard.press('ArrowRight')
        page.keyboard.press('Enter')
        want = iso(today + timedelta(days=6))
        expect(page, 'B 달력에서 하루 뒤 → due', lambda: f'due: {want}' in md('이슈리포트/02-리튬/WORK.md'), lambda: md('이슈리포트/02-리튬/WORK.md')[:80])
        settle(500)
        # 그사이 파일의 그 줄을 다른 데서 바꿈 — 화면은 옛 글을 들고 있다
        page.locator(rowsel('03 니켈 재고') + ' button[data-wk-act="todos"]').click()
        page.wait_for_selector('.wk-board:visible .wk-todos-row li:has-text("표 정리")')
        put('이슈리포트/03-니켈/WORK.md', md('이슈리포트/03-니켈/WORK.md').replace('표 정리', '표 다시 정리'))
        before = md('이슈리포트/03-니켈/WORK.md')
        page.locator('.wk-board:visible .wk-todos-row li', has_text='표 정리').locator('input[type="checkbox"]').check()
        settle(900)
        check('B 그사이 줄이 바뀌었으면 쓰지 않음', md('이슈리포트/03-니켈/WORK.md') == before)
        check('B 그 까닭을 알림', '그사이' in page.locator('#lec-toast').inner_text(), page.locator('#lec-toast').inner_text())

        print('[C 칸반]')
        open_board()
        page.locator('.wk-board:visible button[data-wk-mode="kanban"]').click()
        page.wait_for_selector('.wk-board:visible .wk-kanban')
        lanes = page.locator('.wk-board:visible .wk-lane h4').all_inner_texts()
        check('C 상태 다섯 칸', [x.split(' ')[0] for x in lanes][:5] == ['예정', '진행', '주의', '보류', '완료·중단'], lanes)
        check('C 끝 업무만 카드 (묶음은 아님)', page.locator('.wk-board:visible .wk-kcard').count() == 4, page.locator('.wk-board:visible .wk-kcard .wk-k-title').all_inner_texts())
        trail_ = page.locator('.wk-board:visible .wk-kcard:has(.wk-k-title:text-is("02 리튬 공급")) .wk-k-trail').inner_text()
        check('C 카드 위에 경로', trail_ == '2026 원자재 리서치 › 하반기 이슈리포트', trail_)
        page.locator('.wk-board:visible .wk-kcard:has(.wk-k-title:text-is("03 니켈 재고"))').drag_to(page.locator('.wk-board:visible .wk-lane[data-wk-lane="active"]'))
        expect(page, 'C 진행 칸에 놓으면 status: 진행', lambda: 'status: 진행' in md('이슈리포트/03-니켈/WORK.md'))
        settle(500)
        page.locator('.wk-board:visible .wk-kcard:has(.wk-k-title:text-is("주간 보고"))').drag_to(page.locator('.wk-board:visible .wk-lane[data-wk-lane="watch"]'))
        page.wait_for_selector('#lec-menu:not([hidden])')
        check('C 주의 칸은 막힘·지연위험 가운데 고름', page.locator('#lec-menu button').all_inner_texts()[:2] == ['막힘', '지연위험'], page.locator('#lec-menu button').all_inner_texts())
        page.locator('#lec-menu button', has_text='지연위험').click()
        expect(page, 'C 고른 값이 들어감', lambda: 'status: 지연위험' in md('정기보고/주간/WORK.md'))
        page.locator('.wk-board:visible button[data-wk-mode="list"]').click()

        print('[D 칸]')
        page.locator('.wk-board:visible ' + 'button.wk-open:text-is("02 리튬 공급")').click()
        page.wait_for_selector('#lec-view h1:has-text("02 리튬 공급")', timeout=10000)
        tab = page.locator('.lec-tab.active .name').inner_text()
        check('D 하위 업무는 품은 프로젝트 탭에서 열림', tab == '원자재', tab)
        here = page.evaluate("() => import('/static/js/store.js').then((m) => m.S.view.path)")
        check('D 그 하위 WORK.md', here == '이슈리포트/02-리튬/WORK.md', here)
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: '이슈리포트/WORK.md' }))")
        page.wait_for_selector('#lec-view h1:has-text("하반기 이슈리포트")')
        page.wait_for_selector('.lec-scroll > .wk-under .wk-tree', timeout=8000)
        under = page.locator('.lec-scroll > .wk-under').first.inner_text()
        check('D 상위 WORK.md 아래에 하위 업무 (본문 밖)', '02 리튬 공급' in under and page.locator('#lec-view .wk-under').count() == 0, under[:200])
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: 'README.md' }))")
        page.wait_for_selector('#lec-view h1:has-text("원자재")')
        settle(600)
        check('D 다른 문서로 가면 하위 업무 칸이 없어짐', page.locator('.lec-scroll:visible > .wk-under').count() == 0)
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open', { type: 'overview', path: '이슈리포트' }))")
        page.wait_for_selector('.wk-folder-work .wk-tree', timeout=8000)
        fw = page.locator('.wk-folder-work').inner_text()
        check('D 묶음 폴더 개요에 이 폴더의 업무', '이 폴더의 업무' in fw and '하반기 이슈리포트' in fw and '03 니켈 재고' in fw, fw[:200])

        print('[E 하위 폴더에 업무 카드]')
        page.locator('#lec-tree .row.dir', has_text='정기보고').first.click(button='right')
        page.wait_for_selector('#lec-menu:not([hidden])')
        page.locator('#lec-menu button', has_text='이 폴더에 업무 카드 만들기').click()
        page.wait_for_selector('#lec-workcard:not([hidden])')
        check('E 작은 업무가 기본 (하위 폴더)', page.locator('#lec-workcard-kind').input_value() == 'item')
        page.locator('#lec-workcard-kind').select_option('group')
        page.locator('#lec-workcard-title').fill('정기 보고 묶음')
        page.locator('#lec-workcard-go').click()
        expect(page, 'E 묶음 틀로 만듦 — status 비움', lambda: (proj / '정기보고' / 'WORK.md').exists() and md('정기보고/WORK.md').startswith('---\nstatus:\n') and '# 정기 보고 묶음' in md('정기보고/WORK.md'))
        check('E 틀에 기획 메모 절 (D150)', '\n## 기획 메모\n' in md('정기보고/WORK.md'))
        memo = md('정기보고/WORK.md').replace('## 기획 메모\n', '## 기획 메모\n\n- [ ] 메모 속 할 일 (2026-11-20)\n- 2026-11-21 10:00 메모 속 일정\n', 1)
        (proj / '정기보고' / 'WORK.md').write_text(memo, encoding='utf-8')
        time.sleep(1.5)
        open_board()
        check('E 기획 메모 속 할 일·일정은 업무 현황에 없다', '메모 속' not in page.locator('.wk-board:visible').inner_text())
        check('E 이제 주간 보고는 정기 보고 묶음 아래', page.locator(rowsel('주간 보고') + ' td.wk-title').evaluate("e => getComputedStyle(e).getPropertyValue('--wk-depth').trim()") == '2')

        print('[F 날짜]')
        page.keyboard.press('Escape')
        page.keyboard.press('Alt+s')
        page.wait_for_selector('#lec-workevent:not([hidden])')
        page.locator('#lec-workevent button[data-cal]').click()
        page.wait_for_selector('#lec-datepick:not([hidden])')
        page.keyboard.press('ArrowDown')
        page.keyboard.press('Enter')
        check('F 달력에서 한 주 뒤', page.locator('#lec-workevent-date').input_value() == iso(today + timedelta(days=7)), page.locator('#lec-workevent-date').input_value())
        check('F 달력을 닫아도 창은 남음', page.locator('#lec-workevent:not([hidden])').count() == 1)
        page.locator('#lec-workevent-date').fill('2026-13-40')
        page.locator('#lec-workevent-text').fill('회의')
        page.locator('#lec-workevent-go').click()
        check('F 읽지 못한 날짜는 까닭', '읽지 못했습니다' in page.locator('#lec-workevent-msg').inner_text())
        page.locator('#lec-workevent-date').fill('')
        page.locator('#lec-workevent-date').press('Control+;')
        page.wait_for_selector('#lec-datepick:not([hidden])')
        page.keyboard.press('Escape')
        check('F 달력의 Esc 는 달력만 닫음', page.locator('#lec-datepick').is_hidden() and page.locator('#lec-workevent:not([hidden])').count() == 1)
        page.locator('#lec-workevent-no').click()
        page.locator('.lec-tab', has_text='원자재').first.click()   # 업무 현황은 공통 탭 — 프로젝트 탭으로
        settle()
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: '정기보고/주간/메모.md' }))")
        page.wait_for_selector('#lec-view p:has-text("첫 줄입니다")')
        page.locator('#lec-view p', has_text='첫 줄입니다').click()
        page.keyboard.press('F2')
        page.wait_for_selector('.lec-line-edit', timeout=5000)
        page.keyboard.press('End')
        page.keyboard.press('Control+;')
        page.wait_for_selector('#lec-datepick:not([hidden])')
        page.keyboard.press('Enter')
        page.keyboard.press('Enter')
        expect(page, 'F 한 줄 편집 칸의 Ctrl+; → 오늘 날짜를 그 자리에', lambda: f'첫 줄입니다.{iso(today)}' in md('정기보고/주간/메모.md'), lambda: md('정기보고/주간/메모.md'))
        check('화면 스크립트 오류 없음', not errors, errors[:3])
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
