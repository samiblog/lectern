"""시나리오 — 0.93 과 0.94 를 함께 쓰는 흐름 (D169·D170 × D171·D172):
1 '폴더' 묶음에서 키보드로 CSV 를 찾아 열고(Ctrl+Shift+E·글자·→·Enter) 그 행에서 Enter 로 편집 모드 → 저장 → F6 으로 사이드바에 갔다가 돌아오기
2 Claude 가 메모(txt)를 고침 → F7 로 바뀐 줄 → Enter 로 그 줄에서 편집 모드 → 고쳐 저장 → F7 은 다음 바뀐 곳으로
3 csv 표는 통째로 한 블록이라 바뀐 곳을 세지 않는다 — F7 은 알리기만 (편집 모드·표 그대로)
4 명령 찾기로 csv 의 편집 모드를 열고 닫기, log 에서는 까닭을 알림, 편집기 안에서 Ctrl+Shift+E·Ctrl+Shift+P
5 저장하지 않은 csv 편집이 있는 채 명령 찾기 '열린 문서 모두 닫기' — 한 번 묻고, 그만두면 그대로
6 '폴더' 묶음의 F2 는 이름 바꾸기(편집 모드가 아님), 정렬한 csv 표에서 Shift+← 위치 복사가 누른 행"""
import json
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-scen9394-'))
proj = base / 'proj'
(proj / 'data').mkdir(parents=True)
(proj / 'notes').mkdir()
(proj / '보고서.md').write_text('# 보고서\n\n본문.\n', encoding='utf-8')
PRICES = '월,품목,가격\r\n2026-01,구리,9010\r\n2026-02,구리,9400\r\n2026-03,구리,9120\r\n'
(proj / 'data' / '가격.csv').write_bytes(PRICES.encode('cp949'))
(proj / 'data' / 'run.log').write_bytes(b'start\n')
MEMO = '회의 메모\n첫째 줄\n둘째 줄\n셋째 줄\n넷째 줄\n다섯째 줄\n'
(proj / 'notes' / '메모.txt').write_bytes(MEMO.encode('utf-8'))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)

FOCUS = """() => { const a = document.activeElement;
  const sec = a?.closest('.side-sec');
  if (sec) return sec.id + ':' + (a.dataset.doc ?? a.dataset.dir ?? a.dataset.path ?? a.id ?? '');
  if (a?.closest('.CodeMirror')) return 'editor';
  if (a?.closest('#lec-panes')) return 'doc';
  return a?.id || a?.tagName || ''; }"""
HERE = "() => import('/static/js/store.js').then(({ S }) => S.pane?.here?.line || 0)"
CURSOR = "() => document.querySelector('.CodeMirror')?.CodeMirror.getCursor().line + 1"


def raw(rel):
    for _ in range(40):
        try:
            return (proj / rel).read_bytes()
        except OSError:
            time.sleep(0.05)
    return b''


try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(viewport={'width': 1400, 'height': 900}).new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        answer = {'accept': True}
        dialogs = []

        def on_dialog(d):
            dialogs.append(d.message)
            d.accept() if answer['accept'] else d.dismiss()
        page.on('dialog', on_dialog)
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        focus = lambda: page.evaluate(FOCUS)  # noqa: E731
        here = lambda: page.evaluate(HERE)  # noqa: E731
        toast = lambda: page.text_content('#lec-toast') or ''  # noqa: E731

        def command(name):
            page.keyboard.press('Control+Shift+P')
            page.keyboard.type(name)
            page.keyboard.press('Enter')
            page.wait_for_timeout(300)

        print("[1 '폴더' 묶음에서 키보드로 CSV 를 찾아 고치기]")
        page.click('#lec-folder-head')
        page.locator('#lec-view').click()
        page.keyboard.press('Control+Shift+E')
        expect(page, 'Ctrl+Shift+E — 폴더 묶음으로', lambda: focus().startswith('lec-folder:'), focus)
        page.keyboard.press('Home')
        page.keyboard.press('d')
        expect(page, '글자 d — data', lambda: focus() == 'lec-folder:data', focus)
        for _ in range(2):
            if focus() == 'lec-folder:data':
                page.keyboard.press('ArrowRight')
                page.wait_for_timeout(150)
        expect(page, '→ — 펼치고 첫 항목 (이름순 — run.log)', lambda: focus() == 'lec-folder:data/run.log', focus)
        page.keyboard.press('ArrowDown')
        expect(page, '↓ — 가격.csv', lambda: focus() == 'lec-folder:data/가격.csv', focus)
        page.keyboard.press('Enter')
        page.wait_for_selector('#lec-view.csv-view', timeout=10000)
        page.wait_for_timeout(400)
        page.keyboard.press('F6')
        expect(page, 'F6 — 표로', lambda: focus() == 'doc', focus)
        page.keyboard.press('ArrowDown')
        page.keyboard.press('ArrowDown')
        line = here()
        page.keyboard.press('Enter')
        page.wait_for_selector('.CodeMirror', timeout=15000)
        check('↓↓ 뒤 Enter — 그 줄에서 편집 모드 (CP949)', page.evaluate(CURSOR) == line and page.inner_text('.lec-editor .ed-enc') == 'CP949', (page.evaluate(CURSOR), line))
        page.keyboard.press('End')
        page.keyboard.type('0')
        page.keyboard.press('Control+s')
        lines = PRICES.split('\r\n')
        lines[line - 1] += '0'
        expect(page, '저장 — CP949 그대로, 그 줄만', lambda: raw('data/가격.csv') == '\r\n'.join(lines).encode('cp949'), lambda: raw('data/가격.csv'))
        page.keyboard.press('F6')
        page.wait_for_timeout(200)
        if focus() != 'doc' and not focus().startswith('lec-'):
            page.keyboard.press('F6')
        page.keyboard.press('Control+Shift+E')
        expect(page, '편집기에서 Ctrl+Shift+E — 사이드바 (편집기는 열린 채)', lambda: focus().startswith('lec-') and page.locator('.CodeMirror').count() == 1, focus)
        page.keyboard.press('F6')
        expect(page, 'F6 — 편집기로 돌아온다', lambda: focus() == 'editor', focus)
        page.keyboard.press('Escape')
        page.wait_for_selector('.CodeMirror', state='detached', timeout=8000)

        print('[2 Claude 가 고친 메모(txt) — F7 → Enter → 편집 모드]')
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open', { type: 'code', path: 'notes/메모.txt' }))")
        page.wait_for_selector('#lec-view.code-view .cv-line', timeout=10000)
        page.wait_for_timeout(500)
        page.locator('#lec-view .cv-line').first.click()
        time.sleep(1.1)
        (proj / 'notes' / '메모.txt').write_bytes(MEMO.replace('둘째 줄', '둘째 줄 — 고침').replace('다섯째 줄', '다섯째 줄 — 고침').encode('utf-8'))
        expect(page, '자동으로 다시 그림', lambda: page.locator('#lec-view .cv-line', has_text='다섯째 줄 — 고침').count() == 1, ms=12000)
        page.wait_for_timeout(400)
        page.locator('#lec-view .cv-line').first.click()
        page.keyboard.press('F7')
        expect(page, 'F7 — 첫 바뀐 줄 (3행)', lambda: here() == 3, here)
        page.keyboard.press('Enter')
        page.wait_for_selector('.CodeMirror', timeout=15000)
        check('Enter — 그 줄에서 편집 모드 (txt)', page.evaluate(CURSOR) == 3, page.evaluate(CURSOR))
        page.keyboard.press('End')
        page.keyboard.type(' (확인)')
        page.keyboard.press('Control+s')
        expect(page, '저장', lambda: '둘째 줄 — 고침 (확인)' in raw('notes/메모.txt').decode('utf-8'))
        page.keyboard.press('Escape')
        page.wait_for_selector('.CodeMirror', state='detached', timeout=8000)
        page.wait_for_timeout(700)
        page.keyboard.press('F7')
        expect(page, 'F7 — 다음 바뀐 곳 (6행 — 내가 고친 3행 다음)', lambda: here() == 6, here)

        print('[3 csv 표의 F7]')
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open', { type: 'code', path: 'data/가격.csv' }))")
        page.wait_for_selector('#lec-view.csv-view', timeout=10000)
        page.wait_for_timeout(400)
        page.locator('#lec-view tbody.csv-rows tr.cv-line').first.click()
        time.sleep(1.1)
        (proj / 'data' / '가격.csv').write_bytes(raw('data/가격.csv') + '\r\n2026-04,구리,9300'.encode('cp949'))
        expect(page, 'Claude 가 더한 행이 표에', lambda: page.locator('#lec-view tr.cv-line', has_text='9300').count() == 1, ms=12000)
        page.keyboard.press('F7')
        expect(page, 'F7 — 표는 통째로 한 블록이라 알리기만', lambda: '바뀐 곳이 없습니다' in toast(), toast)
        check('— 표·통계 체크 칸은 그대로', page.locator('.csv-stats-toggle input').count() == 1 and page.locator('#lec-view .csv-table').count() == 1)

        print('[4 명령 찾기로 편집 모드]')
        page.locator('#lec-view tbody.csv-rows tr.cv-line').first.click()
        command('편집 모드')
        expect(page, "명령 '편집 모드 열기·닫기' — csv 의 편집 모드", lambda: page.locator('.CodeMirror').count() == 1)
        page.keyboard.press('Control+Shift+P')
        expect(page, '편집기 안에서도 Ctrl+Shift+P', lambda: not page.is_hidden('#lec-palette') and page.input_value('#lec-palette-input') == '>')
        page.keyboard.type('편집 모드')
        page.keyboard.press('Enter')
        expect(page, '— 다시 고르면 닫힌다', lambda: page.locator('.CodeMirror').count() == 0)
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open', { type: 'code', path: 'data/run.log' }))")
        page.wait_for_selector('#lec-view.code-view .cv-line', timeout=10000)
        page.locator('#lec-view .cv-line').first.click()
        command('편집 모드')
        expect(page, 'log 에서는 까닭을 알린다', lambda: '로그 파일은 보기만' in toast() and page.locator('.CodeMirror').count() == 0, toast)

        print("[5 저장하지 않은 csv 편집이 있는 채 '열린 문서 모두 닫기']")
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open', { type: 'code', path: 'data/가격.csv', newTab: true }))")
        page.wait_for_selector('#lec-view.csv-view', timeout=10000)
        page.locator('#lec-view tbody.csv-rows tr.cv-line').first.click()
        page.keyboard.press('Control+e')
        page.wait_for_selector('.CodeMirror', timeout=15000)
        page.keyboard.press('Control+End')
        page.keyboard.type('X')
        before = raw('data/가격.csv')
        n = len(dialogs)
        answer['accept'] = False
        page.keyboard.press('Control+Shift+P')
        page.keyboard.type('열린 문서 모두')
        page.keyboard.press('Enter')
        page.wait_for_timeout(600)
        check('한 번 묻는다', len(dialogs) == n + 1, dialogs[n:])
        check('— 그만두면 편집기와 문서 탭 그대로, 파일도 그대로', page.locator('.CodeMirror').count() == 1 and page.locator('#lec-doctab-list .doc-tab').count() >= 2 and raw('data/가격.csv') == before)
        expect(page, '— 초점은 편집기로 돌아온다 (이어 치면 편집기에)', lambda: focus() == 'editor', focus)
        page.keyboard.type('Y')
        check('— 이어 친 글자가 편집기에', 'XY' in (page.evaluate("() => document.querySelector('.CodeMirror').CodeMirror.getValue()") or ''))
        answer['accept'] = True
        page.keyboard.press('Escape')
        page.wait_for_selector('.CodeMirror', state='detached', timeout=8000)

        print("[6 '폴더' 묶음의 F2 · 정렬한 표의 위치 복사]")
        page.click('#lec-folder-head')
        row = page.locator('#lec-folder-list .row[data-path="data/가격.csv"]')
        if not row.count():
            page.locator('#lec-folder-list .row[data-path="data"] [data-toggle]').click()
        row.click()
        page.keyboard.press('F2')
        expect(page, "'폴더' 묶음의 F2 — 이름 바꾸기 창 (편집 모드가 아님)", lambda: not page.is_hidden('#lec-rename') and page.locator('.CodeMirror').count() == 0)
        page.keyboard.press('Escape')
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open', { type: 'code', path: 'data/가격.csv' }))")
        page.wait_for_selector('#lec-view.csv-view', timeout=10000)
        page.wait_for_timeout(300)
        page.locator('.csv-head th[data-col="2"]').click()
        page.locator('.csv-head th[data-col="2"]').click()
        top = page.locator('#lec-view tbody.csv-rows tr.cv-line').first
        want = int(top.get_attribute('data-line'))
        top.click()
        page.wait_for_timeout(200)
        check('정렬한 표에서 누른 행이 현재 줄', here() == want, (here(), want))
        page.context.grant_permissions(['clipboard-read', 'clipboard-write'])
        page.keyboard.press('Shift+ArrowLeft')
        page.wait_for_timeout(300)
        clip = page.evaluate('navigator.clipboard.readText()')
        check('Shift+← — 누른 행의 위치를 복사', f'@data/가격.csv {want}' in clip.replace('행', '') or f'{want}행' in clip, clip)

        real = [e for e in errors if 'addressunreachable' not in e]
        check('화면 스크립트 오류 없음', not real, real[:3])
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
