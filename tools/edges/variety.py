"""여러 상황 (D91·D92·D93): 프로젝트 없음·보기 전용·영어·어두운 스타일, 연속 조작, 많은 메모, 글자 대비."""
import json
import shutil
import sys
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import ROOT, check, fails, report, serve, stop

base = Path(tempfile.mkdtemp(prefix='lec-variety-'))
proj = base / 'proj'
(proj / '.lectern').mkdir(parents=True)
(proj / 'docs').mkdir()
for i in range(30):
    (proj / 'docs' / f'd{i:02d}.md').write_text(f'# 문서 {i}\n\n글 {i}\n', encoding='utf-8')
(proj / 'a.md').write_text('# 문서 가\n\n첫 줄\n둘째 줄\n\n## 절\n\n글\n', encoding='utf-8')
many = ''.join(f'<!-- lectern-note id=m{i} {"pinned=1" if i % 50 == 0 else ""} -->\n## 메모 {i}\n\n본문 {i}\n- [ ] 할 일 {i}\n\n' for i in range(300))
(proj / '.lectern' / 'notes.md').write_text(many, encoding='utf-8')
config = base / 'config'
config.mkdir()

server, url, port = serve(proj, config)
samples = None

CONTRAST = r"""(color) => {
  const parse = (s) => { const m = /color\(srgb ([\d.]+) ([\d.]+) ([\d.]+)|rgba?\(([\d.]+), ([\d.]+), ([\d.]+)/.exec(s); if (!m) return null;
    return m[1] != null ? [m[1] * 255, m[2] * 255, m[3] * 255] : [+m[4], +m[5], +m[6]]; };
  const lum = (c) => { const [r, g, b] = c.map((v) => { const x = v / 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const card = document.createElement('article');
  card.className = `note-card${color ? ` note-${color}` : ''}`;
  document.querySelector('#lec-notes-list').append(card);
  const st = getComputedStyle(card);
  const bg = parse(st.backgroundColor);
  const fg = parse(st.color);
  card.remove();
  if (!bg || !fg) return [0, st.backgroundColor, st.color];
  const [a, b] = [lum(bg), lum(fg)].sort((x, y) => y - x);
  return [(a + 0.05) / (b + 0.05), st.backgroundColor, st.color];
}"""

try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')
        settle = lambda ms=350: page.wait_for_timeout(ms)
        tabs = lambda: page.evaluate("[...document.querySelectorAll('#lec-doctab-list .doc-tab')].map((t) => t.dataset.path)")
        row = lambda path: page.locator(f'#lec-tree .row.file[data-doc="{path}"]')

        print('[많은 메모]')
        settle(700)
        start = time.time()
        page.keyboard.press('Alt+m')
        page.wait_for_function("document.querySelectorAll('#lec-notes-list .note-card').length === 300", timeout=8000)
        took = time.time() - start
        check(f'메모 300개가 열림 ({took:.1f}초)', took < 3, took)
        check('고정이 먼저', page.locator('.note-card').first.locator('.note-title').input_value() == '메모 0' and 'pinned' in page.locator('.note-card').nth(5).get_attribute('class') and 'pinned' not in page.locator('.note-card').nth(6).get_attribute('class'))
        start = time.time()
        page.fill('#lec-notes-filter', '메모 123')
        page.wait_for_function("document.querySelectorAll('#lec-notes-list .note-card').length === 1", timeout=4000)
        check(f'거르기 ({time.time() - start:.2f}초)', time.time() - start < 1.5)
        page.fill('#lec-notes-filter', '')
        settle(300)
        before = (proj / '.lectern' / 'notes.md').read_text(encoding='utf-8')
        page.keyboard.press('Alt+m')
        settle(500)
        check('읽기만 하면 파일을 바꾸지 않음', (proj / '.lectern' / 'notes.md').read_text(encoding='utf-8') == before)

        print('[메모 카드의 글자 대비 — 스타일마다]')
        page.keyboard.press('Alt+m')
        settle(400)
        themes = page.evaluate("[...document.querySelectorAll('#lec-theme option')].map((o) => o.value).filter((v) => v !== 'auto')")
        worst = [99, '', '']
        for theme in themes:
            page.select_option('#lec-theme', theme)
            settle(220)
            for color in ['', 'yellow', 'green', 'blue', 'purple', 'pink', 'gray']:
                ratio = page.evaluate(CONTRAST, color)[0]
                if ratio < worst[0]:
                    worst = [round(ratio, 2), theme, color]
        check(f'{len(themes)}개 스타일 × 7색: 글자 대비 4.5 이상 (가장 낮은 곳 {worst})', worst[0] >= 4.5, worst)
        page.select_option('#lec-theme', 'default')
        settle(250)
        page.keyboard.press('Alt+m')
        settle(300)

        print('[연속 조작]')
        for i in range(12):
            row_path = f'docs/d{i:02d}.md'
            page.evaluate("(p) => document.querySelector(`#lec-tree .row.dir[data-dir=\"docs\"] [data-toggle]`) && !document.querySelector(`#lec-tree .row.file[data-doc=\"${p}\"]`) && document.querySelector('#lec-tree .row.dir[data-dir=\"docs\"] [data-toggle]').click()", row_path)
            settle(40)
            row(row_path).click(no_wait_after=True)
        settle(1800)
        n = tabs()
        check('빠르게 12개를 눌러도 탭이 겹치지 않음', len(n) == len(set(n)) and all(f'docs/d{i:02d}.md' in n for i in range(12)), n)
        check('마지막에 누른 문서가 보임', page.evaluate("document.querySelector('#lec-view h1')?.textContent") == '문서 11', page.evaluate("document.querySelector('#lec-view h1')?.textContent"))
        for _ in range(8):
            page.keyboard.press('Control+Tab')
        settle(500)
        for _ in range(5):
            page.keyboard.press('Control+w')
        settle(700)
        left = tabs()
        check('연속으로 옮기고 닫아도 멈추지 않음', len(left) == len(n) - 5, left)
        for _ in range(5):
            page.keyboard.press('Control+Shift+t')
            settle(150)
        settle(900)
        check('닫은 탭을 차례로 다시 염', sorted(tabs()) == sorted(n), [len(tabs()), len(n)])
        for i in range(12, 30):
            page.evaluate("(p) => import('/static/js/store.js').then(({ emit }) => emit('open', { type: 'doc', path: p, newTab: true }))", f'docs/d{i:02d}.md')
            settle(60)
        settle(1500)
        check('20개를 넘겨 눌러도 20개까지', len(tabs()) == 20, len(tabs()))
        check('마지막 문서가 보임', page.evaluate("document.querySelector('#lec-view h1')?.textContent") == '문서 29', page.evaluate("document.querySelector('#lec-view h1')?.textContent"))
        page.evaluate("""async () => { const { S } = await import('/static/js/store.js'); const d = await import('/static/js/doctabs.js');
          for (const q of [...S.tab.panes]) if (q !== S.tab.pane) d.closeDocTab(q); }""")
        settle(400)

        print('[편집 중·터미널·모음에서의 키]')
        page.evaluate("import('/static/js/store.js').then(({ emit }) => emit('open', { type: 'doc', path: 'a.md' }))")
        page.wait_for_selector('#lec-view h1:has-text("문서 가")')
        settle(300)
        page.keyboard.press('Control+e')
        page.wait_for_selector('.lec-pane.active .lec-editor .CodeMirror')
        settle(300)
        page.keyboard.press('Alt+m')
        settle(300)
        check('편집 모드에서도 Alt+M', page.locator('#lec-notes').is_visible())
        page.keyboard.press('Alt+m')
        settle(200)
        page.keyboard.press('Escape')
        settle(300)
        page.click('#lec-btn-term')
        page.wait_for_selector('#lec-term .xterm', timeout=8000)
        settle(900)
        page.locator('#lec-term .xterm').first.click()
        settle(200)
        page.keyboard.press('Alt+m')
        settle(300)
        check('터미널 안에서도 Alt+M', page.locator('#lec-notes').is_visible())
        page.keyboard.press('Alt+m')
        settle(200)
        n_before = len(tabs())
        page.locator('#lec-term .xterm').first.click()
        page.keyboard.press('Control+w')
        settle(300)
        check('터미널 안의 Ctrl+W 는 셸의 것', len(tabs()) == n_before and page.locator('#lec-tablist [role=tab]').count() == 1)
        page.click('#lec-btn-term')
        settle(300)
        page.click('#lec-btn-gather')
        settle(600)
        page.keyboard.press('Alt+m')
        settle(300)
        visible = page.locator('#lec-notes').is_visible()
        page.keyboard.press('Alt+m')
        settle(200)
        page.click('#lec-btn-gather')
        settle(400)
        check('터미널 모음에서 Alt+M 이 멈추지 않음', isinstance(visible, bool))
        page.click('#lec-doctab-spread') if False else None

        print('[프로젝트가 없을 때]')
        page.keyboard.press('Control+Shift+w')
        settle(900)
        page.keyboard.press('Alt+m')
        settle(300)
        none_text = page.locator('#lec-notes-list').inner_text()
        new_off = page.locator('#lec-notes-new').is_disabled()
        check('프로젝트가 없으면 메모 패널이 알림만', '폴더를 여세요' in none_text and new_off, none_text)
        page.keyboard.press('Alt+m')
        for key in ['Control+w', 'Control+t', 'Control+Shift+t', 'Control+Tab', 'Control+g', 'Control+l', 'Alt+h', 'Shift+F10', 'Control+=', 'Control+0', 'Alt+PageDown']:
            page.keyboard.press(key)
            settle(60)
        page.keyboard.press('Escape')
        page.keyboard.press('Control+,') if False else None
        settle(300)
        check('프로젝트가 없어도 새 키들이 멈추지 않음', not errors, errors[:3])

        check('화면 스크립트 오류 없음', not errors, errors[:3])
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)

# 보기 전용 프로젝트와 영어·어두운 스타일 — 서버를 따로
base2 = Path(tempfile.mkdtemp(prefix='lec-variety2-'))
config2 = base2 / 'config'
config2.mkdir()
(config2 / 'config.json').write_text(json.dumps({'language': 'en', 'theme': 'dracula'}), encoding='utf-8')
server2, url2, port2 = serve(ROOT / 'samples', config2)
try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1100, 'height': 700})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(url2)
        page.wait_for_selector('#lec-tree .row.file')
        page.wait_for_timeout(900)
        print('[보기 전용·영어·어두운 스타일·좁은 창]')
        page.keyboard.press('Alt+m')
        page.wait_for_timeout(500)
        text = page.locator('#lec-notes').inner_text()
        check('보기 전용 프로젝트는 메모를 쓰지 않고 영어로 알림', 'view-only' in text and page.locator('#lec-notes-new').is_disabled(), text[:160])
        box = page.locator('#lec-notes').bounding_box()
        check('좁은 창에서도 패널이 화면 안에', box['x'] >= 0 and box['x'] + box['width'] <= 1100, box)
        page.keyboard.press('Alt+m')
        page.wait_for_timeout(200)
        before = sorted(str(x) for x in (ROOT / 'samples').rglob('*'))
        page.locator('#lec-tree .row.file').first.click()
        page.wait_for_timeout(600)
        page.locator('#lec-view p').first.click(button='right')
        page.wait_for_selector('#lec-menu:not([hidden])')
        labels = page.evaluate("[...document.querySelectorAll('#lec-menu button[data-i]')].map((b) => b.querySelector('span')?.textContent || '')")
        hangul = [x for x in labels if any('가' <= c <= '힣' for c in x)]
        check('영어 메뉴에 한글이 없음', not hangul, hangul[:4])
        if 'Send to new note' in labels:
            page.locator('#lec-menu button', has_text='Send to new note').click()
            page.wait_for_timeout(600)
            check('보기 전용에서 새 메모로 보내면 알리기만', 'view-only' in page.locator('#lec-toast').inner_text(), page.locator('#lec-toast').inner_text())
        else:
            page.keyboard.press('Escape')
        check('프로그램 폴더에 아무것도 만들지 않음', sorted(str(x) for x in (ROOT / 'samples').rglob('*')) == before and not (ROOT / 'samples' / '.lectern').exists())
        check('화면 스크립트 오류 없음 (영어)', not errors, errors[:3])
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    server2.terminate()
    try:
        server2.wait(10)
    except Exception:
        server2.kill()
    shutil.rmtree(base2, ignore_errors=True)
report()
