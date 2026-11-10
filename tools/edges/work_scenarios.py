"""업무 관리 (D124) — 사용자 시나리오 시험: 손으로 쓰다 낸 오타, 일부를 지웠을 때, 입력 창의 실수, 파일 형식.
글을 읽는 규칙의 세부는 규칙 시험(tools/edges/work_cases.js)이 보고, 여기서는 사용자가 화면에서 겪는 것을 따라 한다.

  A 오타        상태·키 이름·마감·할 일 기한·체크 칸·일정 시각·없는 날 — 과제는 표에 남고 '확인할 줄'에 모이며, 누르면 그 줄로
  B 부분 삭제   닫는 ---·WORK.md·과제 폴더·## 일정 제목·공통 폴더를 지우거나 옮김, 창을 연 채 지움, 넣은 뒤 고치고 되돌리기
  C 입력 실수   빈 내용·거꾸로 된 시각·특수 글자와 태그·같은 일정 두 번·빈 제목·틀린 경로
  D 파일 형식   CRLF·BOM·끝 줄바꿈 없음은 그대로, CP949 는 읽지 못한 폴더로, 편집 중인 파일은 덮어쓰지 않음
"""
import json
import tempfile
import traceback
from datetime import date, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop

base = Path(tempfile.mkdtemp(prefix='lec-worksc-'))
today = date.today().isoformat()
later = (date.today() + timedelta(days=30)).isoformat()


def make(name, text=None, raw=None):
    root = base / name
    root.mkdir(parents=True)
    (root / 'README.md').write_text(f'# {name}\n', encoding='utf-8')
    if raw is not None:
        (root / 'WORK.md').write_bytes(raw)
    elif text is not None:
        (root / 'WORK.md').write_text(text, encoding='utf-8', newline='')
    return root


home = make('home', raw=('﻿# 공통 업무\r\n\r\n## 일정\r\n\r\n## 할 일\r\n').encode('utf-8'))   # BOM·CRLF
typo = make('typo', f"""---
status: 진핸
prority: 상
due: 2026-12-32
---

# 오타 과제 <img src=x onerror="window.__xss=1">

## 할 일

- [ ] 기한 오타 (11/31)
- [] 체크 칸 오타

## 일정

- {today} 25:00 시각 오타
- 2026-11-31 날짜 오타
- {today} 09:00 제대로 된 회의
""")
broken = make('broken', '---\nstatus: 진행\ndue: 2026-12-15\n\n# 닫는 줄 없음\n')
gone = make('gone', '---\nstatus: 진행\n---\n\n# 지울 카드\n')
gone2 = make('gone2', '---\nstatus: 진행\n---\n\n# 창을 연 채 지울 카드\n')
moved = make('moved', '---\nstatus: 진행\n---\n\n# 옮길 과제\n')
cp949 = make('cp949', raw='---\nstatus: 진행\n---\n\n# 한글 CP949\n'.encode('cp949'))
empty = make('empty', '')
nosched = make('nosched', '---\nstatus: 진행\n---\n\n# 일정 절 없음\n\n- 2026-11-01 지난 일정')   # 끝 줄바꿈 없음, ## 일정 없음
fresh = base / 'fresh'
fresh.mkdir()
(fresh / 'README.md').write_text('# fresh\n', encoding='utf-8')
listed = [typo, broken, gone, gone2, moved, cp949, empty, nosched]
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_home': str(home.resolve()), 'work_folders': [str(p.resolve()) for p in listed]}), encoding='utf-8')

server, url, port = serve(home, config)

try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        answers = []   # prompt(폴더 고르기)에는 차례대로 답하고, confirm(덮어쓸까요)은 거절한다
        asked = []

        def on_dialog(d):
            asked.append(d.message)
            if d.type == 'prompt' and answers:
                d.accept(answers.pop(0))
            elif d.type == 'beforeunload':   # 시험이 다시 불러올 때 — 저장하지 않은 편집을 버린다
                d.accept()
            else:
                d.dismiss()

        page.on('dialog', on_dialog)
        page.goto(url)
        page.wait_for_selector('.wk-board .wk-table', timeout=15000)
        settle = lambda ms=400: page.wait_for_timeout(ms)
        board = lambda: page.locator('.wk-board:visible')
        btext = lambda: board().inner_text()
        cfg = lambda: page.evaluate("async () => (await (await fetch('/api/config')).json())")
        def read(root):
            for _ in range(20):   # 서버가 바꿔 끼우는 순간이면 잠깐 잠기거나 없다 — 다시 읽는다
                try:
                    return (root / 'WORK.md').read_bytes()
                except FileNotFoundError:
                    if not (root / 'WORK.md').parent.exists():
                        return b''
                    page.wait_for_timeout(50)
                except OSError:
                    page.wait_for_timeout(50)
            return b''

        def write(root, data):
            for _ in range(20):
                try:
                    (root / 'WORK.md').write_bytes(data)
                    return
                except OSError:
                    page.wait_for_timeout(50)

        def until(fn, ms=5000):
            for _ in range(ms // 100):
                if fn():
                    return True
                page.wait_for_timeout(100)
            return fn()

        def refresh():
            board().locator('button[data-wk="refresh"]').click()
            settle(900)

        def close_notes():
            while page.locator('#lec-work-notes .wk-n-close').count():
                page.locator('#lec-work-notes .wk-n-close').first.click()
                settle(80)

        def event_dialog(where, text, time='', end='', allday=False):
            close_notes()
            page.keyboard.press('Escape')
            page.keyboard.press('Alt+s')
            page.wait_for_selector('#lec-workevent:not([hidden])')
            labels = page.locator('#lec-workevent-where option').all_inner_texts()
            pick = [x for x in labels if where in x]
            assert pick, (where, labels)
            page.locator('#lec-workevent-where').select_option(label=pick[0])
            if time:
                page.locator('#lec-workevent-time').fill(time)
            if end:
                page.locator('#lec-workevent-end').fill(end)
            if allday:
                page.locator('#lec-workevent-allday').check()
            page.locator('#lec-workevent-text').fill(text)
            settle(100)

        def dialog_msg():
            return page.locator('#lec-workevent-msg').inner_text() if page.locator('#lec-workevent-msg').is_visible() else ''

        close_notes()
        print('[A 오타 — 손으로 쓴 WORK.md]')
        text = btext()
        row = board().locator('tr', has_text='오타 과제')
        check('A 오타가 있어도 과제는 표에 남음', row.count() == 1, text[:300])
        check('A1 상태 오타는 글 그대로 (정해진 값이 아님 표시)', row.locator('.wk-st.st-unknown').inner_text() == '진핸')
        check('A 표의 과제에 확인할 줄 수', '확인할 줄 7' in row.inner_text(), row.inner_text())
        checks = board().locator('.wk-check li')
        kinds = checks.all_inner_texts()
        want = ['정해진 상태 값', '키 이름이 틀린', '마감 날짜를 읽지', '할 일의 기한을 읽지', '체크 칸 모양이 아닙니다', '시각을 읽지 못해', '날짜가 없는 날']
        check('A 확인할 줄에 일곱 가지 오타가 모두', all(any(w in k for k in kinds) for w in want), kinds)
        check('A5 키 이름 오타는 맞는 키를 알려 줌', any('(priority)' in k for k in kinds), kinds)
        check('A9 시각 오타 일정은 시각 없이 오늘 일정에 남음', '25:00 시각 오타' in text)
        check('A 제대로 쓴 일정은 그대로', '제대로 된 회의' in text)
        check('A 제목의 태그는 글자로 (태그가 되지 않음)', board().locator('img').count() == 0 and '<img' in text and page.evaluate('window.__xss') is None)
        check('B1 닫는 --- 를 지운 카드도 표에 남고 확인할 줄', board().locator('tr', has_text='닫는 줄 없음').count() == 1 and any('머리 설정이 닫히지' in k for k in kinds))
        check('B4 내용을 모두 지운 WORK.md 는 폴더 이름으로', board().locator('tr', has_text='empty').count() == 1)
        check('D2 CP949 로 저장한 WORK.md 는 읽지 못한 폴더 (까닭: UTF-8)', 'UTF-8' in board().locator('.wk-bad').inner_text(), board().locator('.wk-bad').inner_text() if board().locator('.wk-bad').count() else '')
        checks.filter(has_text='체크 칸 모양').locator('button').click()
        check('A 확인할 줄을 누르면 그 카드의 WORK.md 가 열림', until(lambda: page.locator('.lec-tab.active .name').inner_text() == 'typo' and 'WORK.md' in page.locator('#lec-doctab-list .active, #lec-doctab-list [aria-selected="true"]').first.inner_text()), page.locator('#lec-doctab-list').inner_text())
        check('A 그 줄로 감 (그 줄이 반짝)', until(lambda: page.locator('#lec-view .lec-changed').count() > 0, 2500) and '찾지 못했습니다' not in page.locator('#lec-toast').inner_text())

        print('[B 부분 삭제]')
        page.keyboard.press('Alt+w')
        page.wait_for_selector('.wk-board:visible .wk-table')
        (gone / 'WORK.md').unlink()
        refresh()
        bad = board().locator('.wk-bad').inner_text()
        check('B5 WORK.md 를 지우면 읽지 못한 폴더 (WORK.md 가 없습니다)', 'gone' in bad and 'WORK.md 가 없습니다' in bad, bad)
        moved.rename(base / 'moved2')
        refresh()
        bad = board().locator('.wk-bad').inner_text()
        check('B6 과제 폴더 이름을 바꾸면 폴더가 없다고', 'moved' in bad and '폴더가 없습니다' in bad, bad)
        board().locator('.wk-bad li', has_text='moved').locator('button').click()
        check('B6 목록에서 빼기', until(lambda: not any(x.endswith('moved') for x in cfg()['work_folders'])))
        page.evaluate("async (p) => fetch('/api/open', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({path: p})})", str((base / 'moved2').resolve()))
        check('B6 새 이름으로 열면 다시 기억', until(lambda: str((base / 'moved2').resolve()) in cfg()['work_folders']))
        page.keyboard.press('Alt+w')
        page.wait_for_selector('.wk-board:visible .wk-table')

        event_dialog('일정 절 없음', '절 없는 곳에 넣기', time='13:00')
        page.locator('#lec-workevent-go').click()
        new = f'- {today} 13:00 절 없는 곳에 넣기'
        check('B3 ## 일정 절이 없으면 끝에 만들어 넣음', until(lambda: read(nosched).decode().endswith(f'\n\n## 일정\n\n{new}')), read(nosched)[-120:])
        check('B3 원래 줄은 그대로 (끝 줄바꿈 없던 파일은 그대로 없음)', read(nosched).decode().startswith('---\nstatus: 진행\n---\n\n# 일정 절 없음\n\n- 2026-11-01 지난 일정\n'))

        event_dialog('창을 연 채 지울', '사라진 파일에 넣기')
        (gone2 / 'WORK.md').unlink()
        page.locator('#lec-workevent-go').click()
        check('B8 창을 연 채 WORK.md 를 지우면 넣지 않고 까닭을 알림', until(lambda: 'WORK.md' in dialog_msg()), dialog_msg())
        check('B8 파일을 새로 만들지 않음', not (gone2 / 'WORK.md').exists())
        page.keyboard.press('Escape')

        before = read(home)
        event_dialog('공통', '되돌릴 일정', time='15:00')
        page.locator('#lec-workevent-go').click()
        line = f'- {today} 15:00 되돌릴 일정'
        check('D1 BOM·CRLF 파일에 넣어도 BOM·CRLF 그대로', until(lambda: line.encode() in read(home)) and read(home).startswith(b'\xef\xbb\xbf') and b'\n' not in read(home).replace(b'\r\n', b''), read(home)[:80])
        write(home, read(home).replace(line.encode(), (line + ' (직접 고침)').encode()))
        page.locator('#lec-work-notes .wk-notice', has_text='일정을 넣었습니다').locator('button', has_text='되돌리기').click()
        settle(600)
        check('B9 넣은 뒤 직접 고친 파일은 되돌리지 않고 알림', '(직접 고침)' in read(home).decode('utf-8-sig') and '되돌리지 않았습니다' in page.locator('#lec-toast').inner_text(), page.locator('#lec-toast').inner_text())
        write(home, before)

        print('[C 입력 창의 실수]')
        event_dialog('공통', '   ', time='10:00')
        page.locator('#lec-workevent-go').click()
        settle(200)
        check('C1 내용을 비우면 넣지 않음', '내용을 쓰세요' in dialog_msg() and read(home) == before, dialog_msg())
        page.locator('#lec-workevent-text').fill('거꾸로 된 시각')
        page.locator('#lec-workevent-time').fill('11:00')
        page.locator('#lec-workevent-end').fill('10:00')
        page.locator('#lec-workevent-go').click()
        settle(200)
        check('C2 끝나는 시각이 시작보다 앞이면 넣지 않음', '끝나는 시각이 시작보다 앞' in dialog_msg() and read(home) == before, dialog_msg())
        special = '<b>굵게</b> & | # [ ] 50% `코드` *별*'
        page.locator('#lec-workevent-end').fill('')
        page.locator('#lec-workevent-text').fill(special)
        page.locator('#lec-workevent-go').click()
        check('C3 특수 글자·태그는 파일에 글자 그대로', until(lambda: f'{today} 11:00 {special}'.encode() in read(home)), read(home).decode('utf-8-sig')[-120:])
        page.keyboard.press('Alt+w')
        settle(900)
        check('C3 업무 현황에 글자로 보이고 태그가 되지 않음', special in btext() and board().locator('.wk-list b').count() == 0)
        event_dialog('공통', '두 번 넣은 일정', time='16:00')
        page.locator('#lec-workevent-go').click()
        settle(500)
        event_dialog('공통', '두 번 넣은 일정', time='16:00')
        page.locator('#lec-workevent-go').click()
        check('C7 같은 일정을 두 번 넣으면 두 줄 (막지 않음 — 되돌리기로 뺀다)', until(lambda: read(home).decode('utf-8-sig').count('16:00 두 번 넣은 일정') == 2))
        close_notes()
        answers.append(str(base / 'no-such-folder'))
        board().locator('button[data-wk="add"]').click()
        settle(500)
        check('C6 없는 경로를 더하면 까닭을 알리고 목록 그대로', '폴더가 아닙니다' in page.locator('#lec-toast').inner_text(), page.locator('#lec-toast').inner_text())
        answers.append('relative\\folder')
        board().locator('button[data-wk="add"]').click()
        settle(500)
        check('C6 상대 경로도 까닭을 알림', '전체 경로' in page.locator('#lec-toast').inner_text(), page.locator('#lec-toast').inner_text())
        page.evaluate("async (p) => fetch('/api/open', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({path: p})})", str(fresh.resolve()))
        page.goto(url)   # 서버가 연 탭을 화면이 받는다
        page.wait_for_selector('#lec-tablist')
        page.locator('.lec-tab', has_text='fresh').click()
        settle(600)
        page.locator('.lec-tab', has_text='fresh').click(button='right')
        page.locator('#lec-menu').get_by_text('업무 카드 만들기…').click()
        page.wait_for_selector('#lec-workcard:not([hidden])')
        page.locator('#lec-workcard-title').fill('   ')
        page.locator('#lec-workcard-go').click()
        check('C5 제목을 비우면 폴더 이름', until(lambda: '# fresh' in read(fresh).decode()), read(fresh)[:120])

        print('[D 편집 중인 WORK.md]')
        page.locator('.lec-tab', has_text='home').click()
        settle(500)
        page.locator('#lec-tree .row.file[data-doc="WORK.md"]').click()
        page.wait_for_selector('#lec-view h1')
        page.locator('#lec-view h1').click()
        page.keyboard.press('Control+e')
        page.wait_for_selector('.lec-pane.active .lec-editor .CodeMirror', timeout=8000)
        settle(400)
        cm = "document.querySelector('.lec-pane.active .lec-editor .CodeMirror').CodeMirror"
        page.evaluate(f"{cm}.replaceRange('편집기에서 쓴 글\\n', {{ line: {cm}.lineCount() - 1, ch: 0 }})")
        page.evaluate(f"{cm}.focus()")
        snap = page.evaluate("async (f) => (await (await fetch('/api/work/card?folder=' + encodeURIComponent(f))).json())", str(home.resolve()))
        added = snap['text'] + f'- {today} 17:00 다른 창에서 넣은 일정\n'
        page.evaluate("async ([f, t, h]) => fetch('/api/work/card', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({folder: f, text: t, hash: h})})",
                      [str(home.resolve()), added, snap['hash']])
        page.keyboard.press('Control+s')
        settle(800)
        check('D 편집 중에 일정이 들어온 파일은 편집기 저장이 덮어쓰지 않음 (묻고, 거절하면 그대로)',
              '다른 창에서 넣은 일정' in read(home).decode('utf-8-sig') and '편집기에서 쓴 글' not in read(home).decode('utf-8-sig') and len(asked) >= 1, asked[-1:])

        print('[B 공통 폴더가 없어짐]')
        page.keyboard.press('Escape')
        settle(300)
        page.evaluate("async () => { const s = await (await fetch('/api/state')).json(); for (const t of s.projects) if (t.name === 'home') await fetch('/api/close', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({p: t.id})}); }")
        page.goto(url)
        page.wait_for_selector('#lec-tablist')
        home.rename(base / 'home-moved')
        settle(300)
        close_notes()
        page.keyboard.press('Alt+w')
        page.wait_for_selector('#lec-workask:not([hidden])', timeout=8000)
        check('B7 공통 폴더를 옮기면 다시 고르라고 묻고 과제 목록은 그대로', '공통 폴더를 열지 못했습니다' in page.locator('#lec-workask').inner_text() and len(cfg()['work_folders']) >= 5)

        check('페이지 오류 없음', not errors, errors)
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)

report()
