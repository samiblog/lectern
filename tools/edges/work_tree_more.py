"""업무 나무 (D149) — 사용자 시나리오 시험: 쌓이는 것과 바뀌는 것. 기본 동작은 work_tree.py.

  G 40건       묶음 아래 이슈리포트 40개 — 곧 그림, 끝난 하위는 접힘, 칸반의 완료 칸
  H 오타       하위의 상태 값 오타 — 그 줄은 '확인할 줄', 묶음의 셈은 오타를 빼고
  I 이름·옮김   프로젝트가 열린 채 하위 폴더 이름을 바꾸거나 밖으로 옮김 — 다시 읽으면 새 자리, 옛 자리는 빠짐
  J 닫힌 탭    프로젝트 탭을 닫아도 업무 현황에서 하위를 고칠 수 있음
  K 영어 값    영어 값(status: active)을 쓰는 파일은 영어로 고침
  L 어긋남     상위가 완료인데 하위가 열림, 상위 상태 비우기 → 하위에서 셈"""
import json
import shutil
import tempfile
import time
import traceback
from datetime import date, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop

base = Path(tempfile.mkdtemp(prefix='lec-worktree2-'))
today = date.today()
iso = lambda d: d.isoformat()
proj = base / '리서치'
outside = base / '밖'
home = base / 'home'


def card(status, title, due=''):
    return f'---\nstatus: {status}\ndue: {due}\n---\n\n# {title}\n\n## 할 일\n\n- [ ] 첫 할 일\n\n## 기록\n'


def put(rel, text):
    path = proj / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


put('WORK.md', card('', '2026 리서치'))
put('이슈리포트/WORK.md', card('', '이슈리포트 묶음', iso(today + timedelta(days=60))))
statuses = ['완료'] * 25 + ['진행'] * 10 + ['예정'] * 3 + ['막힘'] * 2
for i, st in enumerate(statuses, 1):
    put(f'이슈리포트/{i:02d}/WORK.md', card(st, f'이슈 {i:02d}', iso(today + timedelta(days=i))))
put('오타/WORK.md', card('진헹', '오타 난 업무'))
put('영어/WORK.md', card('active', 'English task'))
put('끝난묶음/WORK.md', card('완료', '끝났다고 적은 묶음'))
put('끝난묶음/남은일/WORK.md', card('진행', '아직 하는 일'))
put('README.md', '# 리서치\n')
outside.mkdir()
home.mkdir()
(home / 'WORK.md').write_text('# 공통\n', encoding='utf-8')
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
        rowsel = lambda title: f'.wk-board:visible tr.wk-tr:has(button.wk-open:text-is("{title}"))'
        st = lambda title: page.locator(rowsel(title) + ' .wk-st').first.inner_text()

        def open_board():
            page.keyboard.press('Escape')
            started = time.time()
            page.keyboard.press('Alt+w')
            page.wait_for_selector('.wk-board:visible .wk-tree', timeout=15000)
            settle()
            return time.time() - started

        def refresh():
            page.locator('.wk-board:visible button[data-wk="refresh"]').click()
            settle(900)

        def set_status(title, label):
            page.locator(rowsel(title) + ' button[data-wk-act="status"]').click()
            page.wait_for_selector('#lec-menu:not([hidden])')
            page.locator('#lec-menu button', has_text=label).first.click()

        print('[G 40건]')
        took = open_board()
        check(f'G 46개 업무도 곧 그림 ({took:.1f}초)', took < 6)
        group = page.locator(rowsel('이슈리포트 묶음')).inner_text()
        check('G 묶음에 하위 40', '하위 40' in group and '완료 25' in group and '막힘 2' in group, group)
        check('G 묶음은 막힘* (하위에서 셈)', st('이슈리포트 묶음') == '막힘*')
        more = page.locator('.wk-board:visible tr.wk-more').first.inner_text()
        check('G 끝난 25건은 접힘', '25건' in more, more)
        shown = page.locator('.wk-board:visible .wk-tree button.wk-open').all_inner_texts()
        check('G 열린 15건은 보임, 끝난 것은 안 보임', sum(1 for x in shown if x.startswith('이슈 ')) == 15, len(shown))
        page.locator('.wk-board:visible button[data-wk-mode="kanban"]').click()
        page.wait_for_selector('.wk-board:visible .wk-kanban')
        lane = page.locator('.wk-board:visible .wk-lane[data-wk-lane="closed"] h4').inner_text()
        check('G 칸반 완료 칸 25', lane.endswith('25'), lane)
        page.locator('.wk-board:visible button[data-wk-mode="list"]').click()

        print('[H 오타]')
        check('H 오타 값이 그대로 보임', st('오타 난 업무') == '진헹', st('오타 난 업무'))
        checks = page.locator('.wk-board:visible .wk-check').inner_text() if page.locator('.wk-board:visible .wk-check').count() else ''
        check('H 확인할 줄에', '정해진 상태 값이 아닙니다' in checks and '진헹' in checks, checks[:200])
        check('H 맨 위 총괄의 셈은 오타를 빼고 (막힘)', st('2026 리서치') == '막힘*', st('2026 리서치'))

        print('[I 이름 바꾸기·옮기기]')
        (proj / '이슈리포트' / '39').rename(proj / '이슈리포트' / '39-이름바꿈')
        shutil.move(str(proj / '이슈리포트' / '40'), str(outside / '40'))
        time.sleep(2.5)   # 감시가 알리고 트리가 바뀌기를
        refresh()
        expect(page, 'I 다시 읽으면 바뀐 자리에서', lambda: page.locator(rowsel('이슈 39')).count() == 1 and page.locator(rowsel('이슈 40')).count() == 0)
        cfg = json.loads((config / 'config.json').read_text(encoding='utf-8'))['work_folders']
        check('I 목록도 바뀜 — 옛 자리·옮긴 것은 빠짐', any(x.endswith('39-이름바꿈') for x in cfg) and not any(x.endswith('이슈리포트\\39') or x.endswith('이슈리포트/39') or x.endswith('\\40') for x in cfg), [x[-20:] for x in cfg if '이슈리포트' in x][-3:])
        set_status('이슈 39', '보류')
        expect(page, 'I 바뀐 자리의 파일을 고침', lambda: 'status: 보류' in md('이슈리포트/39-이름바꿈/WORK.md'))
        check('I 옮겨 간 파일은 그대로', 'status: 막힘' in (outside / '40' / 'WORK.md').read_text(encoding='utf-8'))

        print('[J 닫힌 탭]')
        page.locator('.lec-tab', has_text='리서치').first.click(button='right')
        page.wait_for_selector('#lec-menu:not([hidden])')
        page.locator('#lec-menu button', has_text='탭 닫기').first.click()
        settle(800)
        open_board()
        check('J 탭을 닫아도 하위가 보임', page.locator(rowsel('이슈 38')).count() == 1)
        set_status('이슈 38', '완료')
        expect(page, 'J 닫힌 프로젝트의 하위 파일도 고침', lambda: 'status: 완료' in md('이슈리포트/38/WORK.md'))

        print('[K 영어 값]')
        set_status('English task', '막힘')
        expect(page, 'K 영어 값을 쓰는 파일은 영어로', lambda: 'status: blocked' in md('영어/WORK.md'), lambda: md('영어/WORK.md')[:40])

        print('[L 어긋남]')
        hot = page.locator('.wk-board:visible .wk-hotlist').inner_text()
        check('L 완료라 적었는데 하위가 열림', '끝났다고 적은 묶음' in hot and '하위가 아직 열림' in hot, hot[:300])
        set_status('2026 리서치', '진행')
        expect(page, 'L 맨 위에 상태를 적으면 그 값', lambda: 'status: 진행' in md('WORK.md'))
        settle(700)
        page.locator(rowsel('2026 리서치') + ' button[data-wk-act="status"]').click()
        page.wait_for_selector('#lec-menu:not([hidden])')
        page.locator('#lec-menu button', has_text='비우기 — 하위에서 셈').click()
        expect(page, 'L 비우면 status: 만 남음', lambda: '\nstatus:\n' in md('WORK.md'))
        expect(page, 'L 다시 하위에서 셈 (*)', lambda: st('2026 리서치').endswith('*'))
        check('화면 스크립트 오류 없음', not errors, errors[:3])
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
