"""업무 관리 (D124)와 폴더 모두 펼치기·접기 (D125): 공통 폴더 정하기, 업무 현황, 업무 카드 만들기, 일정 더하기·되돌리기, 폴더 더하기,
설정 창의 목록 빼기, 알림 칸, 사이드바 '펼침'. 날짜는 오늘 기준으로 만든다."""
import json
import tempfile
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop

base = Path(tempfile.mkdtemp(prefix='lec-work-'))
today = date.today()
iso = lambda d: d.isoformat()
now = datetime.now()
soon = now + timedelta(minutes=5)
can_remind = soon.date() == today   # 자정 가까이면 10분 전 알림은 보지 않는다


def make(name, text=None, extra=None):
    root = base / name
    root.mkdir(parents=True)
    (root / 'README.md').write_text(f'# {name}\n', encoding='utf-8')
    if text is not None:
        (root / 'WORK.md').write_text(text, encoding='utf-8')
    for rel, body in (extra or {}).items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body, encoding='utf-8')
    return root


a = make('alpha', f"""---
status: 진행
priority: 상
due: {iso(today + timedelta(days=2))}
---

# 알파 과제

## 할 일

- [ ] 지난 일 ({iso(today - timedelta(days=1))})
- [ ] 다음 주 일 ({iso(today + timedelta(days=20))})

## 일정

- {iso(today)} {soon:%H:%M} 곧 할 회의

## 기록
""", {'docs/sub/deep.md': '# 깊은 문서\n', 'docs/top.md': '# 위 문서\n', 'node_modules/lib/README.md': '# 제외\n', 'data/raw.csv': 'a,b\n1,2\n'})
closed = make('closed', '---\nstatus: 완료\n---\n\n# 끝난 과제\n')
bare = make('bare')
home = make('home')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_folders': [str(closed.resolve())]}), encoding='utf-8')

server, url, port = serve(a, config)

try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        answers = []   # 브라우저 모드의 폴더 고르기는 prompt — 차례대로 답한다
        page.on('dialog', lambda d: d.accept(answers.pop(0)) if answers else d.dismiss())
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')
        settle = lambda ms=400: page.wait_for_timeout(ms)
        cfg = lambda: page.evaluate("async () => (await (await fetch('/api/config')).json())")
        work_md = lambda root: (root / 'WORK.md').read_text(encoding='utf-8') if (root / 'WORK.md').exists() else ''

        def until(fn, ms=5000):
            for _ in range(ms // 100):
                if fn():
                    return True
                page.wait_for_timeout(100)
            return fn()

        print('[기억하기]')
        folders = cfg()['work_folders']
        check('WORK.md 가 있는 폴더를 열면 목록에 들어감', str(a.resolve()) in folders and str(closed.resolve()) in folders, folders)

        print('[알림]')
        check('켤 때 오늘의 요약 (마감 임박·기한 지난 할 일)', until(lambda: '오늘의 업무' in (page.locator('#lec-work-notes').inner_text() if page.locator('#lec-work-notes').count() else ''), 9000))
        notes_text = page.locator('#lec-work-notes').inner_text()
        check('요약에 마감 임박 과제', '알파 과제' in notes_text, notes_text)
        if can_remind:
            check('10분 안의 일정 알림', '곧 시작합니다' in notes_text and '곧 할 회의' in notes_text, notes_text)
        page.locator('#lec-work-notes .wk-n-close').first.click()
        settle(200)

        print('[공통 폴더]')
        page.keyboard.press('Alt+w')
        page.wait_for_selector('#lec-workask:not([hidden])')
        check('공통 폴더가 없으면 먼저 묻는다', '공통 폴더' in page.locator('#lec-workask').inner_text())
        answers.append(str(home))
        page.locator('#lec-workask button.primary').click()
        page.wait_for_selector('.wk-board .wk-table', timeout=8000)
        settle()
        check('공통 폴더가 탭으로 열리고 업무 현황이 보임', page.locator('.lec-tab.active .name').inner_text() == 'home')
        board = page.locator('.wk-board').inner_text()
        check('과제 줄과 주의할 것', '알파 과제' in board and '마감 임박' in board, board[:300])
        check('완료는 접혀 있음', page.locator('.wk-closed').count() == 1 and not page.locator('.wk-closed').evaluate('d => d.open'))
        check('기한 지난 할 일', '지난 일' in board and '다음 주 일' not in board, board)
        check('공통 WORK.md 가 없다고 알림', '공통 WORK.md 만들기' in board)
        check('공통 폴더는 과제 목록에 없음', str(home.resolve()) not in cfg()['work_folders'])
        page.locator('.wk-board button[data-wk="make-home"]').click()
        check('공통 WORK.md 를 공통용 틀로 만듦', until(lambda: work_md(home).startswith('# ')))
        settle(600)

        print('[일정 더하기]')
        page.keyboard.press('Escape')
        page.keyboard.press('Alt+s')
        page.wait_for_selector('#lec-workevent:not([hidden])')
        check('넣을 곳에 공통과 끝나지 않은 과제 (완료는 없음)', page.locator('#lec-workevent-where option').all_inner_texts()[0].startswith('공통')
              and not any('끝난 과제' in x for x in page.locator('#lec-workevent-where option').all_inner_texts()))
        page.locator('#lec-workevent-time').fill('10:00')
        page.locator('#lec-workevent-text').fill('팀 회의')
        settle(100)
        line = f'- {iso(today)} 10:00 팀 회의'
        check('넣을 줄 미리보기', page.locator('#lec-workevent-line').inner_text() == line, page.locator('#lec-workevent-line').inner_text())
        page.locator('#lec-workevent-text').press('Enter')
        check('공통 WORK.md 의 일정 절에 한 줄', until(lambda: line in work_md(home)), work_md(home))
        lines = work_md(home).split('\n')
        check('일정 절 안에 들어감', lines.index(line) > lines.index('## 일정' if '## 일정' in lines else '## Schedule'), lines)
        page.locator('#lec-work-notes .wk-notice', has_text='일정을 넣었습니다').locator('button', has_text='되돌리기').click()
        check('되돌리기', until(lambda: line not in work_md(home)), work_md(home))
        page.keyboard.press('Alt+s')
        page.wait_for_selector('#lec-workevent:not([hidden])')
        page.locator('#lec-workevent-where').select_option(label=[x for x in page.locator('#lec-workevent-where option').all_inner_texts() if '알파' in x][0])
        page.locator('#lec-workevent button[data-dow="5"]').click()
        page.locator('#lec-workevent-allday').check()
        page.locator('#lec-workevent-text').fill('워크숍')
        page.locator('#lec-workevent-go').click()
        check('과제 WORK.md 에 종일 일정 (요일 단추는 다가오는 날)', until(lambda: ' 종일 워크숍' in work_md(a)), work_md(a))
        added = [x for x in work_md(a).split('\n') if '워크숍' in x][0]
        friday = date.fromisoformat(added.split()[1])
        check('금요일', friday.weekday() == 4 and today < friday <= today + timedelta(days=7), added)

        print('[폴더 더하기]')
        page.locator('#lec-work-notes .wk-n-close').first.click() if page.locator('#lec-work-notes .wk-n-close').count() else None
        page.keyboard.press('Alt+w')
        page.wait_for_selector('.wk-board:visible button[data-wk="add"]')
        answers.append(str(bare))
        page.locator('.wk-board:visible button[data-wk="add"]').click()
        page.wait_for_selector('#lec-workask:not([hidden])')
        check('WORK.md 가 없으면 만들지 묻는다', 'WORK.md 가 없습니다' in page.locator('#lec-workask').inner_text())
        page.locator('#lec-workask button.primary').click()
        page.wait_for_selector('#lec-workcard:not([hidden])')
        check('제목은 폴더 이름', page.locator('#lec-workcard-title').input_value() == 'bare')
        page.locator('#lec-workcard-title').fill('새 과제 이름')
        page.locator('#lec-workcard-due').fill(iso(today + timedelta(days=30)))
        page.locator('#lec-workcard-go').click()
        check('업무 카드를 기본 틀로 만듦', until(lambda: '# 새 과제 이름' in work_md(bare)), work_md(bare))
        card = work_md(bare)
        check('머리 설정 값', 'status: 예정' in card and 'priority: 중' in card and f'due: {iso(today + timedelta(days=30))}' in card, card[:120])
        check('만든 폴더가 목록에 들어감', until(lambda: str(bare.resolve()) in cfg()['work_folders']))
        page.wait_for_selector('#lec-tree .row.file[data-doc="WORK.md"]')   # 트리가 새 파일을 안 뒤
        page.locator('.lec-tab', has_text='bare').click(button='right')
        settle(200)
        check('탭 메뉴는 이제 업무 카드 열기', page.locator('.menu, #lec-menu').filter(has_text='업무 카드 열기').count() >= 1)
        page.keyboard.press('Escape')

        print('[설정 창]')
        page.keyboard.press('Control+,')
        page.wait_for_selector('#lec-settings:not([hidden])')
        check('공통 폴더 경로', str(home.resolve()) in page.locator('#lec-work-home').inner_text())
        drop = page.locator(f'#lec-work-folders li', has_text='closed').locator('button')
        drop.click()
        check('목록에서 빼기 (파일은 그대로)', until(lambda: str(closed.resolve()) not in cfg()['work_folders']) and (closed / 'WORK.md').exists())
        page.keyboard.press('Escape')
        settle(200)

        print('[펼침]')
        page.locator('.lec-tab', has_text='alpha').click()
        page.wait_for_selector('#lec-tree .row.dir[data-dir="docs"]')
        page.locator('#lec-btn-expand').click()
        page.locator('#lec-menu, .menu').get_by_text('폴더 모두 펼치기', exact=True).click()
        settle()
        check('문서 트리의 모든 폴더가 펼쳐짐', page.locator('#lec-tree .row.dir[data-dir="docs/sub"]').count() == 1)
        check('제외 폴더는 펼치지 않음', page.locator('#lec-others-list .row.dir.excluded[aria-expanded="true"]').count() == 0)
        page.locator('#lec-btn-expand').click()
        page.locator('#lec-menu, .menu').get_by_text('폴더 모두 접기', exact=True).click()
        settle()
        check('모두 접기', page.locator('#lec-tree .row.dir[data-dir="docs/sub"]').count() == 0 and page.locator('#lec-tree .caret.open').count() == 0)

        check('페이지 오류 없음', not errors, errors)
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)

report()
