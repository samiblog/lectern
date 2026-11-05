"""v0.48.0 의 아직 안 본 조합: 프로젝트 탭, 글자 크기·폭, 모든 스타일, CRLF·BOM, 지운 파일, 편집 모드와 교차, 시작 복구의 경계"""
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import ROOT, check, fails, report, serve, stop



PARA = '긴 문단입니다. ' * 40
base = Path(tempfile.mkdtemp(prefix='lec-49-'))
proj, proj2 = base / 'proj', base / 'second'
proj.mkdir()
proj2.mkdir()
doc = proj / 'a.md'
A_TEXT = '# 첫 문서\n\n첫 문단\n\n- [ ] 할 일\n\n둘째 문단\n\n' + ''.join(f'## 절 {i}\n\n' + (PARA + '\n\n') * 4 for i in range(1, 4))
doc.write_text(A_TEXT, encoding='utf-8')
(proj / 'dia.md').write_text('# 그림\n\n```mermaid\ngraph TD; A-->B\n```\n', encoding='utf-8')
(proj / 'tall.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="300" height="900"><rect width="300" height="900" fill="#88a"/></svg>', encoding='utf-8')
(proj / 'img.md').write_text('# 그림 문서\n\n위 문단\n\n![긴 그림](tall.svg)\n\n아래 문단\n', encoding='utf-8')
crlf = proj / 'crlf.md'
CRLF_BYTES = b'\xef\xbb\xbf# \xec\xa0\x9c\xeb\xaa\xa9\r\n\r\nline a\r\nline b\r\n\r\nline c\r\n'
crlf.write_bytes(CRLF_BYTES)
nonl = proj / 'nonl.md'
NONL_BYTES = '# 끝\n\n마지막 줄'.encode('utf-8')
nonl.write_bytes(NONL_BYTES)
gone = proj / 'gone.md'
gone.write_text('# 지울 문서\n\n지울 글\n', encoding='utf-8')
ren = proj / 'ren.md'
ren.write_text('# 이름 문서\n\n이름 글\n', encoding='utf-8')
many = proj / 'many.md'
many.write_text('# 많이\n\n값 0\n', encoding='utf-8')
(proj2 / 'b.md').write_text('# 둘째 프로젝트\n\n글\n\n더 많은 글\n', encoding='utf-8')
server, url, port = serve(proj, base / 'config')

GUTTER = '#lec-content > .lec-gutter span'
REPLACE = """([path, at, before, after]) => Promise.all([import('/static/js/lineedit.js'), import('/static/js/store.js')])
  .then(([e, { S }]) => e.replaceLines(S.pane, path, at, before, after)).then((r) => r && r.at)"""
CONTRAST = """(() => { const nums = (c) => { const m = c.match(/[\\d.]+/g).map(Number); return c.startsWith('color(') ? m.slice(0, 3).map((v) => v * 255) : m.slice(0, 3); };
  const s = document.querySelector('#lec-content > .lec-gutter span'); const cs = getComputedStyle(s); const fg = nums(cs.color); const bg = nums(getComputedStyle(document.querySelector('#lec-content')).backgroundColor);
  const a = Number(cs.opacity); const mix = fg.map((v, i) => v * a + bg[i] * (1 - a));
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
  const [x, y] = [lum(mix), lum(bg)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); })()"""


def until_bytes(path, want, ms=5000):
    end = time.time() + ms / 1000
    while time.time() < end:
        try:
            if path.read_bytes() == want:
                return True
        except OSError:
            pass
        time.sleep(0.05)
    return False


def until_text(path, n, want, ms=5000):
    end = time.time() + ms / 1000
    while time.time() < end:
        try:
            if path.read_text(encoding='utf-8').split('\n')[n - 1] == want:
                return True
        except OSError:   # 앱이 파일을 바꿔 끼우는 순간 (ReplaceFileW)
            pass
        time.sleep(0.05)
    return False


try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(viewport={'width': 1440, 'height': 900}, locale='ko-KR', permissions=['clipboard-read', 'clipboard-write']).new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')
        settle = lambda ms=300: page.wait_for_timeout(ms)
        nums = lambda: page.evaluate(f"[...document.querySelectorAll('{GUTTER}')].map((s) => s.textContent)")
        toast_has = lambda s: page.wait_for_function(f"document.querySelector('#lec-toast').textContent.includes('{s}')", timeout=3000) and True
        clear_toast = lambda: page.evaluate("document.querySelector('#lec-toast').textContent = ''")
        replace = lambda path, at, before, after: page.evaluate(REPLACE, [path, at, before, after])

        def opened(path, title):
            page.click('.side-tabs button[data-tab="files"]')
            page.locator(f'#lec-tree .row.file[data-doc="{path}"]').click()
            page.wait_for_selector(f'#lec-view h1:has-text("{title}")')
            settle()

        def aligned():
            """제목 번호가 제목의 첫 줄 높이에 있는지, 번호가 칸 안에 있는지"""
            return page.evaluate(f"""(() => {{ const g = document.querySelector('{GUTTER}').getBoundingClientRect(); const h = document.querySelector('#lec-view h1').getBoundingClientRect();
              const sc = document.querySelector('#lec-content').getBoundingClientRect(); const all = [...document.querySelectorAll('{GUTTER}')].map((s) => s.getBoundingClientRect().left);
              return Math.abs((g.top + g.bottom) / 2 - (h.top + h.bottom) / 2) < h.height / 2 + 2 && Math.min(...all) >= sc.left; }})()""")

        print('[프로젝트 탭]')
        opened('a.md', '첫 문서')
        page.once('dialog', lambda d: d.accept(str(proj2)))
        page.click('#lec-btn-open')
        page.wait_for_function("document.querySelectorAll('#lec-tablist .lec-tab').length === 2")
        settle(600)
        page.locator('#lec-tree .row.file[data-doc="b.md"]').click()
        page.wait_for_selector('#lec-view h1:has-text("둘째 프로젝트")')
        settle()
        page.keyboard.press('Alt+l')
        page.wait_for_selector(GUTTER)
        settle()
        second_on = nums()
        page.keyboard.press('Control+1')
        page.wait_for_selector('#lec-view h1:has-text("첫 문서")')
        settle(500)
        first_on = nums()[:3]
        ok_tops = page.evaluate(f"(() => {{ const t = [...document.querySelectorAll('{GUTTER}')].map((s) => s.style.top); return new Set(t).size === t.length; }})()")
        check('다른 프로젝트 탭의 칸에도 번호가 맞게', second_on == ['1', '3', '5'] and first_on == ['1', '3', '5'] and ok_tops and aligned(), (second_on, first_on, ok_tops))
        page.keyboard.press('Alt+l')
        settle()
        page.keyboard.press('Control+2')
        page.wait_for_selector('#lec-view h1:has-text("둘째 프로젝트")')
        settle(500)
        check('한 탭에서 끄면 다른 탭도 꺼짐', nums() == [] and page.evaluate("!document.documentElement.classList.contains('line-numbers')"), nums())
        page.keyboard.press('Control+1')
        page.wait_for_selector('#lec-view h1:has-text("첫 문서")')
        settle()

        print('[글자 크기·문서 폭]')
        page.keyboard.press('Alt+l')
        page.wait_for_selector(GUTTER)
        for _ in range(4):
            page.click('#lec-text-bigger')
        settle(500)
        big = aligned()
        page.click('#lec-text-reset')
        settle(300)
        for _ in range(8):
            if page.evaluate("document.querySelector('#lec-width-wider').disabled"):
                break
            page.click('#lec-width-wider')
        settle(500)
        wide = aligned()
        page.click('#lec-width-reset')
        settle(300)
        check('글자를 키우거나 폭을 가득으로 해도 번호가 줄에 맞고 칸 안에', big and wide, (big, wide))
        before = page.evaluate(f"(() => {{ const g = document.querySelector('{GUTTER}').getBoundingClientRect(); return g.top - document.querySelector('#lec-view h1').getBoundingClientRect().top; }})()")
        page.evaluate("document.querySelector('#lec-content').scrollTop = 120")
        settle()
        after = page.evaluate(f"(() => {{ const g = document.querySelector('{GUTTER}').getBoundingClientRect(); return g.top - document.querySelector('#lec-view h1').getBoundingClientRect().top; }})()")
        page.evaluate("document.querySelector('#lec-content').scrollTop = 0")
        check('스크롤해도 번호가 글과 함께 움직임', abs(before - after) < 1, (before, after))

        print('[모든 스타일]')
        themes = page.evaluate("[...document.querySelectorAll('#lec-theme option')].map((o) => o.value).filter(Boolean)")
        low = []
        for th in themes:
            page.select_option('#lec-theme', th)
            page.wait_for_timeout(180)
            c = page.evaluate(CONTRAST)
            if c < 3:
                low.append((th, round(c, 2)))
        page.select_option('#lec-theme', themes[0])
        settle(300)
        check(f'{len(themes)}개 스타일에서 번호가 바탕과 구별됨 (3:1 이상)', len(themes) >= 20 and not low, low)

        print('[본문과 섞이지 않음]')
        text_on = page.evaluate("(() => { const s = getSelection(); s.selectAllChildren(document.querySelector('#lec-view')); const t = s.toString(); s.removeAllRanges(); return t; })()")
        page.keyboard.press('Control+f')
        page.keyboard.type('할 일')
        settle(350)
        find_on = page.inner_text('#lec-find-count')
        page.keyboard.press('Escape')
        page.locator('#lec-content').focus()
        page.keyboard.press('F1')
        page.wait_for_selector('#lec-help:not([hidden])')
        settle(500)
        help_on = page.evaluate("getComputedStyle(document.querySelector('#lec-help .md-body')).paddingLeft")
        page.keyboard.press('F1')
        settle()
        page.locator('#lec-content').focus()
        page.keyboard.press('Alt+l')
        settle()
        text_off = page.evaluate("(() => { const s = getSelection(); s.selectAllChildren(document.querySelector('#lec-view')); const t = s.toString(); s.removeAllRanges(); return t; })()")
        page.keyboard.press('Control+f')
        page.keyboard.type('할 일')
        settle(350)
        find_off = page.inner_text('#lec-find-count')
        page.keyboard.press('Escape')
        page.locator('#lec-content').focus()
        page.keyboard.press('F1')
        page.wait_for_selector('#lec-help:not([hidden])')
        settle(500)
        help_off = page.evaluate("getComputedStyle(document.querySelector('#lec-help .md-body')).paddingLeft")
        page.keyboard.press('F1')
        settle()
        check('글 고르기·찾기 결과가 켜고 끈 때 같고, 사용설명서의 여백은 그대로', text_on == text_off and find_on == find_off and find_on and help_on == help_off, (len(text_on), len(text_off), find_on, find_off, help_on, help_off))

        print('[그림이 늦게 불러와질 때·지운 문서]')
        page.locator('#lec-content').focus()
        page.keyboard.press('Alt+l')
        settle()
        opened('img.md', '그림 문서')
        page.wait_for_function("[...document.querySelectorAll('#lec-view img')].every((i) => i.complete && i.naturalHeight > 0)", timeout=8000)
        settle(500)
        offs = page.evaluate(f"""(() => {{ const p = [...document.querySelectorAll('#lec-view p')].find((e) => e.textContent.includes('아래 문단')).getBoundingClientRect();
          const n = [...document.querySelectorAll('{GUTTER}')].find((s) => s.textContent === '7').getBoundingClientRect(); return Math.abs((n.top + n.bottom) / 2 - (p.top + p.bottom) / 2); }})()""")
        check('그림을 불러온 뒤에도 아래 문단의 번호가 맞음', offs < 14, offs)
        opened('gone.md', '지울 문서')
        page.wait_for_selector(GUTTER)
        replace('gone.md', 3, ['지울 글'], ['고친 글'])
        settle(400)
        gone.unlink()
        page.wait_for_selector('#lec-view .doc-missing', timeout=8000)
        settle(300)
        missing = [page.locator('#lec-content > .lec-gutter').count(), page.evaluate("document.querySelector('#lec-btn-lines').disabled")]
        page.locator('#lec-content').focus()
        clear_toast()
        page.keyboard.press('Control+z')
        settle(600)
        check('지운 문서: 번호가 사라지고 Ctrl+Z 도 탈이 없음', missing == [0, True] and not gone.exists(), (missing, gone.exists(), page.inner_text('#lec-toast')))
        opened('a.md', '첫 문서')
        page.click('#lec-btn-lines')
        settle()

        print('[CRLF·BOM·끝 줄바꿈 없음]')
        opened('crlf.md', '제목')
        at = replace('crlf.md', 3, ['line a', 'line b'], ['line x', 'line y', 'line z'])
        want = CRLF_BYTES.replace(b'line a\r\nline b', b'line x\r\nline y\r\nline z')
        same = until_bytes(crlf, want)
        settle(400)
        page.locator('#lec-view h1').click()
        page.keyboard.press('Control+z')
        back = until_bytes(crlf, CRLF_BYTES)
        settle(500)
        page.keyboard.press('Control+y')
        fwd = until_bytes(crlf, want)
        settle(500)
        page.keyboard.press('Control+z')
        again = until_bytes(crlf, CRLF_BYTES)
        check('CRLF·BOM 파일의 여러 줄 저장·되돌리기가 바이트까지 그대로', at == 3 and same and back and fwd and again, (at, same, back, fwd, again, crlf.read_bytes()[:40]))
        settle(400)
        opened('nonl.md', '끝')
        replace('nonl.md', 3, ['마지막 줄'], ['고친 줄', '더한 줄'])
        w2 = '# 끝\n\n고친 줄\n더한 줄'.encode('utf-8')
        s2 = until_bytes(nonl, w2)
        settle(400)
        page.locator('#lec-view h1').click()
        page.keyboard.press('Control+z')
        b2 = until_bytes(nonl, NONL_BYTES)
        check('끝 줄바꿈이 없는 파일도 그대로', s2 and b2, nonl.read_bytes())

        print('[체크 칸과 밀린 줄]')
        opened('a.md', '첫 문서')
        text = doc.read_text(encoding='utf-8')
        doc.write_text('앞에 더한 줄\n\n' + text, encoding='utf-8')   # 화면이 따라오기 전에 누른다
        page.locator('#lec-view .task-list-item-checkbox').click()
        moved = until_text(doc, 7, '- [x] 할 일')
        check('화면이 원문보다 늦어도 체크 칸은 밀린 줄을 찾아 저장', moved and doc.read_text(encoding='utf-8').count('[x]') == 1 and doc.read_text(encoding='utf-8').startswith('앞에 더한 줄'), doc.read_text(encoding='utf-8')[:60])
        settle(1500)
        doc.write_text(A_TEXT, encoding='utf-8')
        page.wait_for_function("!document.querySelector('#lec-view').textContent.includes('앞에 더한 줄')", timeout=6000)
        settle(500)

        print('[편집 모드와 교차]')
        replace('a.md', 3, ['첫 문단'], ['첫 문단 고침'])
        settle(500)
        page.keyboard.press('Control+e')
        page.wait_for_selector('.lec-editor .CodeMirror')
        settle(400)
        cm = "document.querySelector('.lec-pane.active .lec-editor .CodeMirror').CodeMirror"
        page.evaluate(f"{cm}.replaceRange('편집기에서 고침\\n\\n', {{ line: 2, ch: 0 }})")
        page.evaluate(f"{cm}.focus()")
        page.keyboard.press('Control+z')
        cm_undo = '편집기에서' not in page.evaluate(f"{cm}.getValue()")
        page.keyboard.press('Control+y')
        cm_redo = '편집기에서' in page.evaluate(f"{cm}.getValue()")
        file_kept = '편집기에서' not in doc.read_text(encoding='utf-8')
        page.keyboard.press('Control+s')
        saved = until_text(doc, 3, '편집기에서 고침')
        settle(500)
        page.keyboard.press('Control+e')
        page.wait_for_function("!document.querySelector('.lec-editor')")
        settle(500)
        page.locator('#lec-view h1').click()
        clear_toast()
        page.keyboard.press('Control+z')
        told = toast_has('그사이 파일이 바뀌어 되돌리지')
        settle(400)
        kept = doc.read_text(encoding='utf-8')
        check('편집기의 Ctrl+Z·Y 는 편집기 것, 편집기로 저장한 뒤 문서의 Ctrl+Z 는 덮어쓰지 않음', cm_undo and cm_redo and file_kept and saved and told and '편집기에서 고침' in kept and '첫 문단 고침' in kept, (cm_undo, cm_redo, file_kept, saved, told))
        doc.write_text(A_TEXT, encoding='utf-8')
        page.wait_for_function("!document.querySelector('#lec-view').textContent.includes('편집기에서')", timeout=6000)
        settle(500)
        page.keyboard.press('Control+f')
        page.keyboard.type('문단')
        settle(300)
        typed = page.input_value('#lec-find-input')
        page.keyboard.press('Control+y')
        settle(300)
        check('찾기 칸의 Ctrl+Y 는 앱이 받지 않음', typed == '문단' and doc.read_text(encoding='utf-8') == A_TEXT)
        page.keyboard.press('Escape')

        print('[이름 바꾸기·기록 한도]')
        opened('ren.md', '이름 문서')
        replace('ren.md', 3, ['이름 글'], ['고친 글'])
        settle(400)
        row = page.locator('#lec-tree .row.file[data-doc="ren.md"]')
        row.focus()
        page.keyboard.press('F2')
        page.wait_for_selector('#lec-rename:not([hidden])')
        page.fill('#lec-rename-input', 'ren2.md')
        page.keyboard.press('Enter')
        page.wait_for_selector('#lec-tree .row.file[data-doc="ren2.md"]', timeout=8000)
        settle(500)
        page.locator('#lec-view h1').click()
        page.keyboard.press('Control+z')
        settle(500)
        check('이름을 바꾼 뒤 Ctrl+Z 는 조용히 지나감 (글은 그대로)', (proj / 'ren2.md').read_text(encoding='utf-8').split('\n')[2] == '고친 글')
        opened('many.md', '많이')
        for i in range(1, 53):
            replace('many.md', 3, [f'값 {i - 1}'], [f'값 {i}'])
        settle(400)
        page.locator('#lec-view h1').click()
        for _ in range(53):
            page.keyboard.press('Control+z')
        page.wait_for_timeout(4500)
        last = many.read_text(encoding='utf-8').split('\n')[2]
        check('기록은 50개까지 — 그 앞은 되돌리지 않고 탈 없음', last == '값 2', last)

        print('[시작 복구의 경계]')
        left = {'n': 0, 'hit': 0}

        def flaky(route):
            if left['n'] > 0:
                left['n'] -= 1
                left['hit'] += 1
                route.abort('addressunreachable')
            else:
                route.continue_()

        page.route('**/static/js/toc.js*', flaky)
        rows = "document.querySelectorAll('#lec-tree .row.file').length > 0"
        left['n'] = 1
        page.reload()
        page.wait_for_function(rows, timeout=8000)
        settle(400)
        left['n'] = 1
        page.reload()
        page.wait_for_function(rows, timeout=8000)
        check('한 번씩 두 번 실패해도 횟수가 쌓이지 않음', page.evaluate("sessionStorage.getItem('lec-boot-tries')") is None and left['hit'] == 2, (page.evaluate("sessionStorage.getItem('lec-boot-tries')"), left))
        left.update(n=3, hit=0)
        page.reload()
        page.wait_for_function(rows, timeout=9000)
        settle(300)
        check('세 번 연달아 실패해도 네 번째에 되살아남', left['hit'] == 3 and page.evaluate("document.querySelector('#lec-boot-fail').hidden"), left)
        page.unroute('**/static/js/toc.js*')
        hit = {'n': 0}

        def fail_once(route):
            if hit['n'] == 0:
                hit['n'] = 1
                route.abort('addressunreachable')
            else:
                route.continue_()

        page.route('**/static/vendor/dompurify/purify.min.js*', fail_once)
        page.reload()
        page.wait_for_function(rows, timeout=9000)
        check('일반 스크립트(라이브러리)를 못 받아도 되살아남', hit['n'] == 1)
        page.unroute('**/static/vendor/dompurify/purify.min.js*')
        settle(300)
        page.route('**/vendor/mermaid/**', lambda r: r.abort('addressunreachable'))
        page.evaluate("window.__stay = 1")
        page.click('.side-tabs button[data-tab="files"]')
        page.locator('#lec-tree .row.file[data-doc="dia.md"]').click()
        page.wait_for_selector('#lec-view h1:has-text("그림")')
        page.wait_for_timeout(2000)
        check('문서를 그릴 때 불러오는 라이브러리를 못 받아도 앱을 다시 불러오지 않음', page.evaluate("window.__stay === 1") and page.evaluate("document.querySelector('#lec-boot-fail').hidden"), page.evaluate("window.__stay"))
        page.unroute('**/vendor/mermaid/**')

        print('[보기만 하는 프로젝트]')
        page.click('#lec-btn-recent')
        page.locator('#lec-menu button', has_text='예제 열기').click()
        page.wait_for_selector('#lec-view h1:has-text("Lectern 예제")', timeout=8000)
        settle(400)
        page.keyboard.press('Alt+l')
        settle(400)
        ro_nums = len(nums()) > 0
        page.locator('#lec-view h1').click()
        page.keyboard.press('Control+y')
        settle(300)
        check('예제에서도 줄 번호는 쓸 수 있고 Ctrl+Y 는 탈이 없음', ro_nums)
        page.keyboard.press('Alt+l')
        settle(200)
        real = [e for e in errors if 'addressunreachable' not in e]
        check('화면 스크립트 오류 없음', not real, real[:3])
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('점검이 중간에 멈춤')
finally:
    stop(server, base)
report()
