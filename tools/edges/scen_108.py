"""0.108 사람 시나리오 — '작업' 묶음으로 하루를 정리한다 (D204).
보고서 몇 편을 쓰는 연구원이: 사이드바를 Ctrl+Shift+E 로 돌아 '작업' 에 들어가 할 일을 훑고, 한 줄을 눌러 그 자리로 가 체크해 끝내고,
AI 도구가 밖에서 문서에 할 일을 더하면 목록이 따라오고, 읽다가 줄에 형광펜을 칠하고, '폴더' 묶음에서 하위 폴더에 업무 카드를 만들고,
거르기로 찾고, Shift+→ 로 할 일 줄을 터미널에 보내고, 다른 프로젝트에 다녀오고, 다시 켠다.
걸음마다: 화면 오류가 없고, 접혀 있는 동안은 형광펜·할 일을 읽지 않는다."""
import json
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-scen108-'))
proj = base / '구리 보고서'
(proj / '1장').mkdir(parents=True)
(proj / '2장').mkdir()
(proj / '1장' / '시장 동향.md').write_text('# 시장 동향\n\n- [ ] 2025 수치 확인\n- [x] 끝낸 일\n\n본문 첫 줄.\n\n재고는 3주 연속 줄었다.\n', encoding='utf-8', newline='\n')
(proj / '2장' / '공급.md').write_text('# 공급\n\n- [ ] 칠레 생산 출처 달기\n\n<mark>광산 파업</mark>이 길어졌다.\n', encoding='utf-8', newline='\n')
(proj / '요약.md').write_text('# 요약\n\n아직 할 일 없음.\n', encoding='utf-8', newline='\n')
(proj / 'WORK.md').write_text('# 구리 보고서\n\n상태: 진행\n', encoding='utf-8', newline='\n')
other = base / '다른 과제'
other.mkdir()
(other / '메모.md').write_text('# 메모\n\n- [ ] 다른 일\n', encoding='utf-8', newline='\n')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')

ITEMS = "() => [...document.querySelectorAll('#lec-work-list .row.item')].map((r) => r.dataset.itemDoc + '#' + r.dataset.line + ':' + r.querySelector('.label').textContent)"
WKINDS = "() => [...document.querySelectorAll('#lec-work .kind-head')].map((b) => b.dataset.kind + ':' + b.querySelector('.n').textContent)"
DKINDS = "() => [...document.querySelectorAll('#lec-docs .kind-head')].map((b) => b.dataset.kind)"
SECS = "() => ['#lec-docs', '#lec-code', '#lec-others', '#lec-work', '#lec-folder'].map((s) => document.querySelector(s).classList.contains('grow') ? 'open' : '-')"
VIEW = "() => import('/static/js/store.js').then(({ S }) => S.pane?.here ? S.pane.here.path + ':' + S.pane.here.line : (S.view && S.view.path))"
FOCUS = "() => document.activeElement?.closest?.('.side-sec')?.id || document.activeElement?.id || ''"


def text(path):
    return path.read_text(encoding='utf-8').replace('\r\n', '\n')


server, url, port = serve(proj, config)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1300, 'height': 900})
        errors, marks_calls = [], []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.on('request', lambda r: marks_calls.append(r.url) if '/api/marks' in r.url else None)
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        page.wait_for_timeout(1500)
        page.evaluate("() => import('/static/js/store.js').then((m) => { window.__pasted = []; m.on('term-paste', (d) => window.__pasted.push(typeof d === 'string' ? d : d.text)); })")

        def items():
            return page.evaluate(ITEMS)

        def no_errors(step):
            check(f'{step} — 화면 오류 없음', not errors, errors[:3])

        print('[아침 — 작업 묶음은 접혀 있다]')
        check('처음은 문서 묶음, 작업은 접혀 있다', page.evaluate(SECS) == ['open', '-', '-', '-', '-'], page.evaluate(SECS))
        check('접혀 있는 동안 형광펜·할 일을 읽지 않는다 (/api/marks 없음)', not marks_calls, marks_calls)
        check("'문서' 의 하위 묶음에 업무·형광펜·할 일이 없다", not set(page.evaluate(DKINDS)) & {'work', 'marks', 'tasks'}, page.evaluate(DKINDS))

        print('[Ctrl+Shift+E 로 돌아 작업에 들어간다]')
        page.locator('#lec-tree .row.file').first.focus()
        for _ in range(3):   # 문서 → 자료 → 코드 → 작업
            page.keyboard.press('Control+Shift+e')
            page.wait_for_timeout(250)
        check('세 번 더 누르면 작업 묶음에 초점', until(page, lambda: page.evaluate(SECS)[3] == 'open' and page.evaluate(FOCUS) == 'lec-work'), (page.evaluate(SECS), page.evaluate(FOCUS)))
        check('펼치자 할 일을 읽는다', until(page, lambda: bool(marks_calls)))
        check('할 일: 두 문서의 열린 할 일 (끝낸 일은 없다)', until(page, lambda: sorted(items()) == ['1장/시장 동향.md#3:2025 수치 확인', '2장/공급.md#3:칠레 생산 출처 달기']), items())
        check('머리줄 개수 — 업무 카드 1 · 형광펜 1 · 할 일 2', until(page, lambda: page.evaluate(WKINDS) == ['work:1', 'marks:1', 'tasks:2']), page.evaluate(WKINDS))
        page.keyboard.press('ArrowDown')
        page.keyboard.press('ArrowDown')
        check('↓ 로 할 일 줄까지 옮긴다', until(page, lambda: page.evaluate("() => document.activeElement?.classList.contains('item')")))
        no_errors('들어가기')

        print('[할 일을 눌러 그 자리로 가 끝낸다]')
        page.locator('#lec-work-list .row.item', has_text='2025 수치 확인').click()
        check('누르면 그 문서의 그 줄', until(page, lambda: page.evaluate(VIEW) == '1장/시장 동향.md:3'), page.evaluate(VIEW))
        page.locator('#lec-view .task-list-item-checkbox').first.click()
        check('체크하면 파일에 [x]', until(page, lambda: '- [x] 2025 수치 확인' in text(proj / '1장' / '시장 동향.md')), text(proj / '1장' / '시장 동향.md'))
        check('할 일 목록에서 빠지고 개수도 1', until(page, lambda: items() == ['2장/공급.md#3:칠레 생산 출처 달기'] and 'tasks:1' in page.evaluate(WKINDS), ms=10000), (items(), page.evaluate(WKINDS)))

        print('[AI 도구가 밖에서 할 일을 더한다]')
        (proj / '요약.md').write_text('# 요약\n\n- [ ] 결론 문단 쓰기\n- [ ] 그림 2 바꾸기\n', encoding='utf-8', newline='\n')
        check('목록이 따라온다 — 요약.md 의 둘', until(page, lambda: '요약.md#3:결론 문단 쓰기' in items() and '요약.md#4:그림 2 바꾸기' in items(), ms=12000), items())
        check('개수 3', until(page, lambda: 'tasks:3' in page.evaluate(WKINDS)), page.evaluate(WKINDS))
        no_errors('밖에서 고침')

        print('[읽다가 형광펜]')
        page.click('#lec-work .kind-head[data-kind="marks"]')
        check('형광펜: 광산 파업', until(page, lambda: items() == ['2장/공급.md#5:광산 파업']), items())
        page.locator('#lec-work-list .row.file[data-doc="2장/공급.md"]').click()
        page.wait_for_selector('#lec-view h1')
        page.locator('#lec-view p', has_text='이 길어졌다').click()
        page.evaluate("() => { const p = [...document.querySelectorAll('#lec-view p')].find((e) => e.textContent.includes('이 길어졌다')); const r = document.createRange(); const t = [...p.childNodes].find((n) => n.nodeType === 3 && n.textContent.includes('길어졌다')); r.setStart(t, t.textContent.indexOf('길어졌다')); r.setEnd(t, t.textContent.indexOf('길어졌다') + 4); getSelection().removeAllRanges(); getSelection().addRange(r); }")
        page.keyboard.press('m')
        check('고른 글에 M — 파일에 <mark>', until(page, lambda: '<mark>길어졌다</mark>' in text(proj / '2장' / '공급.md')), text(proj / '2장' / '공급.md'))
        check('형광펜 목록에 더해진다 (2)', until(page, lambda: len(items()) == 2 and 'marks:2' in page.evaluate(WKINDS), ms=10000), (items(), page.evaluate(WKINDS)))

        print("['폴더' 묶음에서 하위 폴더에 업무 카드]")
        page.click('#lec-folder-head')
        page.locator('#lec-folder-list .row[data-path="2장"]').click(button='right')
        page.locator('#lec-menu').get_by_text('이 폴더에 업무 카드 만들기').click()
        page.wait_for_selector('#lec-workcard:not([hidden])', timeout=8000)
        page.locator('#lec-workcard-title').fill('2장 공급 정리')
        page.locator('#lec-workcard-go').click()
        check('2장/WORK.md 가 생긴다', until(page, lambda: (proj / '2장' / 'WORK.md').exists(), ms=8000))
        page.click('#lec-work-head')
        page.click('#lec-work .kind-head[data-kind="work"]')
        check('업무 카드: 맨 위와 2장의 WORK.md', until(page, lambda: sorted(page.evaluate("() => [...document.querySelectorAll('#lec-work-list .row.file')].map((r) => r.dataset.doc)")) == ['2장/WORK.md', 'WORK.md'], ms=10000),
              page.evaluate("() => [...document.querySelectorAll('#lec-work-list .row.file')].map((r) => r.dataset.doc)"))
        no_errors('업무 카드')

        print('[거르기 · Shift+→]')
        page.click('#lec-work .kind-head[data-kind="tasks"]')
        page.fill('#lec-filter', '그림')
        check('거르기 — 그림 2 바꾸기만', until(page, lambda: items() == ['요약.md#4:그림 2 바꾸기']), items())
        page.fill('#lec-filter', '')
        check('지우면 셋', until(page, lambda: len(items()) == 3), items())
        page.locator('#lec-work-list .row.item', has_text='결론 문단 쓰기').focus()
        page.keyboard.press('Shift+ArrowRight')
        check("Shift+→ — '@요약.md 3행' 을 터미널로", until(page, lambda: any('@요약.md' in x and '3' in x for x in page.evaluate('() => window.__pasted'))), page.evaluate('() => window.__pasted'))

        print('[다른 프로젝트에 다녀온다]')
        page.evaluate("(dir) => import('/static/js/tabs.js').then((m) => m.openFolder(dir))", str(other))
        until(page, lambda: page.evaluate("() => import('/static/js/store.js').then((m) => m.S.tab?.name)") == '다른 과제', 15000)
        page.wait_for_timeout(800)
        check('새 프로젝트는 처음 묶음대로 — 작업이 아니라도 오류 없다', not errors, errors[:2])
        page.click('#lec-work-head')
        check('다른 프로젝트의 할 일 — 다른 일', until(page, lambda: items() == ['메모.md#3:다른 일']), items())
        page.evaluate("() => import('/static/js/tabs.js').then((m) => m.selectTabAt(1))")
        check('돌아오면 작업 묶음의 할 일 셋', until(page, lambda: page.evaluate(SECS)[3] == 'open' and len(items()) == 3), (page.evaluate(SECS), items()))

        print('[다시 켜기]')
        page.reload()
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        check('다시 켜도 작업 묶음 · 할 일', until(page, lambda: page.evaluate(SECS)[3] == 'open' and len(items()) == 3, ms=10000), (page.evaluate(SECS), items()))
        cfg = json.loads((config / 'config.json').read_text(encoding='utf-8'))
        check('설정 files_open = work, work_kind = tasks', cfg.get('files_open') == 'work' and cfg.get('work_kind') == 'tasks', (cfg.get('files_open'), cfg.get('work_kind')))

        print('[영어]')
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ language: 'en' }))")
        page.reload()
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        names = until(page, lambda: (x := page.evaluate("() => [document.querySelector('#lec-work-head span:nth-child(2)').textContent, ...[...document.querySelectorAll('#lec-work .kind-head span:nth-child(2)')].map((s) => s.textContent)]")) and len(x) == 4 and x)
        check('영어: Tasks — Work cards · Highlights · To-dos', names == ['Tasks', 'Work cards', 'Highlights', 'To-dos'], names)
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ language: 'ko' }))")
        no_errors('하루')
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
