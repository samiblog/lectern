"""0.105.0 사람 시나리오 3 — 임의의 사용자가 PDF 를 오래 쓴다 (D201). 정해진 차례 대신 시드마다 동작을 마구 섞고, 걸음마다 지켜야 할 것을 본다:

- 화면에 보이는 쪽은 곧 그려진다 (빈 흰 쪽으로 남지 않는다 — 다른 탭에서 돌아와도, 확대·폭이 바뀌어도, 밖에서 고쳐 써도)
- 그려 둔 쪽은 보이는 근처뿐이다 (오래 써도 늘지 않는다)
- 지금 쪽 = 칸 맨 위에 걸친 쪽 = 막대의 쪽 칸 = 상태줄
- 화면 스크립트 오류가 없다, 끝에 JS 메모리가 크게 늘지 않는다

동작: 트리·Ctrl+P·담기함으로 열기, 문서 탭 고르기·Ctrl+Tab, 휠·PageDown·End·쪽 칸, 확대·축소·폭 맞춤, 사이드바 감추기, 창 크기, 모두 펼치기,
찾기, 고른 글 담기, md 문서로 갔다가 Alt+←, 다른 프로젝트로 갔다 오기, 밖에서 PDF 고쳐 쓰기, 다시 켜기.
시드를 주면 그것만 (python scen_105c.py 7). PDF 는 PyMuPDF 로 만든다 — 없으면 건너뛴다"""
import json
import random
import shutil
import sys
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop, until

try:
    import pymupdf
except ImportError:
    pymupdf = None

SEEDS = [int(x) for x in sys.argv[1:]] or [1, 2, 3]
STEPS = 60
FONT = 'C:/Windows/Fonts/malgun.ttf'
OPEN = "(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: p, newTab: true }))"
# 지켜야 할 것을 한 번에 잰다 — PDF 화면이 아니면 null
LOOK = """() => import('/static/js/store.js').then(({ S }) => {
  const pane = S.pane; const st = pane?.pdf; const view = document.querySelector('#lec-view');
  if (!st?.doc || !view?.classList.contains('pdf-view')) return null;
  const box = pane.scroller.getBoundingClientRect();
  const pages = [...view.querySelectorAll('.pdf-pg')];
  const seen = pages.filter((e) => { const r = e.getBoundingClientRect(); return r.bottom > box.top + 40 && r.top < box.bottom - 2 && r.height > 0; });
  const top = box.top + 50;
  const atTop = pages.find((e) => e.getBoundingClientRect().bottom >= top);
  return { path: st.path, pages: st.doc.numPages, cur: st.cur, atTop: atTop ? Number(atTop.dataset.n) : 0, input: view.querySelector('.pdf-page')?.value,
    seen: seen.map((e) => Number(e.dataset.n)), blank: seen.filter((e) => !e.classList.contains('drawn')).map((e) => Number(e.dataset.n)),
    drawn: st.drawn.size, status: document.querySelector('#lec-status')?.innerText || '', visible: box.height > 0 };
})"""
HEAP = "() => (performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1048576) : 0)"


def make(path, n, word):
    d = pymupdf.open()
    for i in range(1, n + 1):
        pg = d.new_page(width=842 if i % 9 == 0 else 595, height=595 if i % 9 == 0 else 842)
        pg.insert_font(fontname='mg', fontfile=FONT)
        pg.insert_text((40, 60), f'{word} {i}쪽 본문입니다 — 값 {i * 3}', fontname='mg', fontsize=12)
    d.set_toc([[1, f'{word} {i}쪽', i] for i in range(1, n + 1, 5)])
    d.subset_fonts()
    d.save(str(path), garbage=4, deflate=True)
    d.close()


def run(p, seed):
    rnd = random.Random(seed)
    home = Path(tempfile.mkdtemp(prefix=f'lec-scen105c-{seed}-'))
    proj = home / '자료'
    other = home / '다른'
    (proj / 'pdf').mkdir(parents=True)
    other.mkdir()
    (other / '개요.md').write_text('# 다른\n\n글\n', encoding='utf-8')
    names = {'pdf/가.pdf': (40, '가'), 'pdf/나.pdf': (160, '나'), 'pdf/다 문서.pdf': (8, '다')}
    for rel, (n, w) in names.items():
        make(proj / rel, n, w)
    (proj / '메모.md').write_text('# 메모\n\n[가 7쪽](pdf/가.pdf#page=7)\n', encoding='utf-8')
    config = home / 'config'
    config.mkdir()
    (config / 'config.json').write_text(json.dumps({'version': 4, 'doc_kinds': ['pdf'], 'work_alerts': False}), encoding='utf-8')
    server, url, port = serve(proj, config)
    errors, log = [], []
    try:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1300, 'height': 860})
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.on('dialog', lambda d: d.accept())

        def boot():
            page.goto(url)
            page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
            page.wait_for_timeout(400)
            page.evaluate("() => { window.open = () => null; }")

        def look():
            return page.evaluate(LOOK)

        def settle():
            """그릴 틈을 주고 지켜야 할 것을 본다 — 보이는 쪽이 3초 안에 그려지는지"""
            page.wait_for_timeout(400)   # 누른 것이 화면을 바꾸기 시작할 틈 — 바로 보면 아직 앞 화면이라 '안정' 으로 본다
            got = until(page, lambda: (lambda s: s is None or (not s['blank'] and s['cur'] == s['atTop']))(look()), 3000)
            s = look()
            if s is None:
                return True
            bad = []
            if s['blank']:
                bad.append(f"보이는데 안 그려진 쪽 {s['blank']}")
            if s['cur'] != s['atTop']:
                bad.append(f"지금 쪽 {s['cur']} ≠ 맨 위 쪽 {s['atTop']}")
            if s['input'] != str(s['cur']) and page.evaluate("() => document.activeElement?.className") != 'pdf-page':
                bad.append(f"쪽 칸 {s['input']} ≠ {s['cur']}")
            if f"{s['cur']}/{s['pages']}" not in s['status']:
                bad.append(f"상태줄 {s['status'][:60]!r}")
            if s['drawn'] > 12:
                bad.append(f"그려 둔 쪽 {s['drawn']}개")
            if bad or not got:
                check(f'[{seed}] 걸음 {len(log)} {log[-1] if log else ""}: 지켜야 할 것', False, (bad, s))
                return False
            return True

        boot()
        heap0 = None
        for step in range(STEPS):
            pdfs = list(names)
            op = rnd.choices(['tree', 'palette', 'tab', 'ctrltab', 'wheel', 'pagedown', 'end', 'pageno', 'zoom', 'fit', 'sidebar', 'resize', 'spread',
                              'find', 'clip', 'clipgo', 'md', 'project', 'rewrite', 'reload'],
                             [10, 4, 8, 4, 10, 5, 3, 5, 6, 3, 3, 3, 2, 4, 3, 2, 3, 2, 2, 1])[0]
            log.append(op)
            page.keyboard.press('Escape')
            s = look()
            if op in ('tree', 'clipgo') and not page.locator('.side-tabs').is_visible():
                page.keyboard.press('Control+b')   # 감춘 사이드바를 꺼낸다 (사람도 그렇게 한다)
                page.wait_for_timeout(200)
            try:
                if op == 'tree':
                    page.click('.side-tabs button[data-tab="files"]')
                    page.locator(f'#lec-tree .row[data-doc="{rnd.choice(pdfs)}"]').click()
                elif op == 'palette':
                    rel = rnd.choice(pdfs)
                    page.keyboard.press('Control+p')
                    page.keyboard.type(Path(rel).stem)
                    page.wait_for_timeout(250)
                    page.keyboard.press('Enter')
                elif op == 'tab':
                    tabs = page.locator('#lec-doctab-list .doc-tab')
                    if tabs.count():
                        tabs.nth(rnd.randrange(tabs.count())).click()
                elif op == 'ctrltab':
                    page.locator('#lec-content').focus()
                    page.keyboard.press(rnd.choice(['Control+Tab', 'Control+Shift+Tab']))
                elif op == 'wheel' and s:
                    page.mouse.move(700, 450)
                    for _ in range(rnd.randint(1, 8)):
                        page.mouse.wheel(0, rnd.choice([-1, 1]) * rnd.randint(200, 1600))
                        page.wait_for_timeout(rnd.choice([0, 20, 80]))
                elif op == 'pagedown' and s:
                    page.locator('#lec-content').focus()
                    for _ in range(rnd.randint(1, 5)):
                        page.keyboard.press(rnd.choice(['PageDown', 'PageUp', 'Space']))
                elif op == 'end' and s:
                    page.locator('#lec-content').focus()
                    page.keyboard.press(rnd.choice(['End', 'Home']))
                elif op == 'pageno' and s:
                    page.fill('#lec-view .pdf-page', str(rnd.randint(1, s['pages'])))
                    page.keyboard.press('Enter')
                elif op == 'zoom' and s:
                    page.locator('#lec-content').focus()
                    for _ in range(rnd.randint(1, 4)):
                        page.keyboard.press(rnd.choice(['Control+=', 'Control+-']))
                elif op == 'fit' and s:
                    page.locator('#lec-content').focus()
                    page.keyboard.press('Control+0')
                elif op == 'sidebar':
                    page.keyboard.press('Control+b')
                elif op == 'resize':
                    page.set_viewport_size({'width': rnd.choice([760, 1000, 1300, 1600]), 'height': rnd.choice([600, 860, 1000])})
                elif op == 'spread':
                    page.click('#lec-doctab-spread')
                    page.wait_for_timeout(rnd.choice([100, 600]))
                    page.click('#lec-doctab-spread')
                elif op == 'find' and s:
                    page.keyboard.press('Control+f')
                    page.keyboard.type(f'{s["path"].split("/")[-1][0]} {rnd.randint(1, s["pages"])}쪽 본문')
                    page.wait_for_timeout(600)
                    page.keyboard.press('Enter')
                    page.wait_for_timeout(300)
                    page.keyboard.press('Escape')
                elif op == 'clip' and s and s['seen']:
                    n = s['seen'][0]
                    span = page.locator(f'#lec-view .pdf-pg[data-n="{n}"].drawn .textLayer span').first
                    if span.count():
                        span.click(click_count=3)
                        page.keyboard.press('Alt+c')
                elif op == 'clipgo':
                    page.click('.side-tabs button[data-tab="basket"]')
                    boxes = page.locator('#lec-basket-list .bk-box')
                    if boxes.count():
                        boxes.first.click()
                        page.wait_for_timeout(500)
                        go = page.locator('#lec-view .cb-go')
                        if go.count():
                            go.nth(rnd.randrange(go.count())).click()
                    page.click('.side-tabs button[data-tab="files"]')
                elif op == 'md':
                    page.evaluate(OPEN, '메모.md')
                    page.wait_for_selector('#lec-view h1', timeout=10000)
                    page.locator('#lec-view a', has_text='가 7쪽').click()
                    page.wait_for_timeout(rnd.choice([100, 800]))
                    if rnd.random() < 0.5:
                        page.keyboard.press('Alt+ArrowLeft')
                elif op == 'project':
                    page.evaluate("(dir) => import('/static/js/tabs.js').then((m) => m.openFolder(dir))", str(other))
                    until(page, lambda: page.evaluate("() => import('/static/js/store.js').then((m) => m.S.tab?.name)") == '다른', 10000)
                    page.wait_for_timeout(rnd.choice([50, 500]))
                    page.evaluate("() => import('/static/js/tabs.js').then((m) => m.selectTabAt(1))")
                elif op == 'rewrite':
                    rel = rnd.choice(pdfs)
                    n, w = names[rel]
                    n = max(3, n + rnd.choice([-5, 5]))
                    names[rel] = (n, w)
                    make(proj / rel, n, w)
                elif op == 'reload':
                    page.wait_for_timeout(600)
                    boot()
                else:
                    log[-1] += '(건너뜀)'
            except Exception as e:   # noqa: BLE001 — 한 동작이 맞지 않으면(그 자리에 없는 단추 등) 다음 동작으로
                log[-1] += f'(못함: {str(e)[:60]})'
            if not settle():
                break
            if step == 10:
                heap0 = page.evaluate(HEAP)
        page.wait_for_timeout(500)
        heap1 = page.evaluate(HEAP)
        check(f'[{seed}] {len(log)}걸음 — 화면 스크립트 오류 없음', not errors, errors[:3])
        if heap0:
            check(f'[{seed}] JS 메모리 {heap0}MB → {heap1}MB (오래 써도 크게 늘지 않는다)', heap1 < heap0 + 120, (heap0, heap1))
        if fails:
            print('      걸음:', ' '.join(log))
        b.close()
    finally:
        stop(server, home)


if pymupdf is None:
    print('PyMuPDF 가 없어 건너뜁니다')
else:
    try:
        with sync_playwright() as p:
            for s in SEEDS:
                print(f'[임의의 사용자 — 시드 {s}]')
                run(p, s)
    except Exception:   # noqa: BLE001
        traceback.print_exc()
        fails.append('점검이 멈춤')
report()
