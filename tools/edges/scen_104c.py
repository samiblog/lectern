"""0.104.0 다른 방식의 시나리오 — 손으로 적은 차례가 아니라 임의의 사용자 둘과 밖의 프로그램 (D197~D199).

두 창(사용자)이 같은 프로젝트에서 담고·빼고·되돌리고·옮기고·복사하고·차례를 바꾸고·제목과 메모를 쓰고·담기함을 만들고·이름을 바꾸고·담는 곳을
바꾸고·다시 켜는 일을 마구 섞는다. 그 사이 밖의 프로그램(Claude Code 자리)이 파일에 조각을 더하고 메모를 고치고 원래 문서를 고친다.
무엇이 있어야 하는지를 따로 적어 두고(본보기), 한참 뒤 모두 가라앉으면 파일·두 창의 목록·펼친 화면이 본보기와 같은지 본다:
담은 글을 하나도 잃지 않고, 뺀 것이 되살아나지 않고, 두 벌이 되지 않고, 쓴 제목·메모가 남는다.
시드를 주면 그것만 (python scen_104c.py 7)"""
import json
import random
import re
import sys
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop, until

SEEDS = [int(x) for x in sys.argv[1:]] or [1, 2, 3]
STEPS = 70
base = Path(tempfile.mkdtemp(prefix='lec-scen104c-'))
OPEN = "(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: p, newTab: true }))"
MODEL = """() => import('/static/js/store.js').then(({ S }) => Object.fromEntries((S.tab.clips?.boxes || []).map((b) => [b.file, b.items.map((c) => [c.id, c.text.split('\\n')[0], c.title, c.memo])])))"""
CUR = "() => import('/static/js/store.js').then(({ S }) => S.tab.clips?.cur || '')"
QUIET = "() => import('/static/js/store.js').then(({ S }) => (S.tab.clips?.boxes || []).every((b) => !b.saving && !b.timer && !b.touched.size && !b.removed.size && !b.head && !b.order) && !S.tab.clips?.loading)"
CLIP = re.compile(r'<!-- lectern-clip id=(\S+)[^>]*-->\n(.*?)<!-- lectern-clip-text -->\n(.*?)\n(?:<!-- lectern-clip-notes -->\n.*?\n)?<!-- /lectern-clip -->', re.S)


def run(p, seed):
    rnd = random.Random(seed)
    home = base / f's{seed}'
    proj = home / '리서치'
    proj.mkdir(parents=True)
    clips = proj / '.lectern' / 'clips'
    names = ['가격', '수급', '위험']
    for n in names:
        (proj / f'{n}.md').write_text(f'# {n}\n\n' + '\n\n'.join(f'{n} 문단 {i} 입니다.' for i in range(1, 41)) + '\n', encoding='utf-8', newline='\n')
    config = home / 'config'
    config.mkdir()
    (config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
    server, url, port = serve(proj, config)
    errors, log = [], []
    try:
        b = p.chromium.launch()

        def window():
            page = b.new_page(viewport={'width': 1280, 'height': 820})
            page.on('pageerror', lambda e: errors.append(str(e)[:300]))
            page.on('dialog', lambda d: d.accept())
            return page

        def load(page):
            page.goto(url)
            page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
            page.wait_for_timeout(350)
            page.click('.side-tabs button[data-tab="basket"]')

        def src(file):
            for _ in range(40):
                try:
                    return (clips / file).read_text(encoding='utf-8')
                except OSError:
                    time.sleep(0.03)
            return ''

        def disk():
            """파일 → {담은 글의 첫 줄: 몇 번} — 담긴 것"""
            out = {}
            for f in sorted(clips.glob('*.md')) if clips.exists() else []:
                out[f.name] = [(i, text.split('\n')[0], head) for i, head, text in CLIP.findall(src(f.name))]
            return out

        wins = [window(), window()]
        for w in wins:
            load(w)
        used = set()
        # 본보기: 글 → 있는 담기함 파일들(여러 번 담지 않는다). 제목·메모는 글 → (제목, 메모)
        have = {}
        words = {}
        boxes = 0
        outside = 0
        deleted = []

        def quiet(page=None):
            for w in ([page] if page else wins):
                until(w, lambda w=w: w.evaluate(QUIET), 8000)

        def sync():
            quiet()
            for w in wins:
                w.evaluate("() => window.dispatchEvent(new Event('focus'))")
            time.sleep(0.25)
            quiet()

        def card_of(page, text):
            """사이드바를 펼쳐 그 글의 조각 줄을 찾는다 — 이름이 바뀌었을 수 있어 id 로"""
            m = page.evaluate(MODEL)
            for file, items in m.items():
                for cid, t, *_ in items:
                    if t == text:
                        row = page.locator(f'#lec-basket-list .bk-box[data-file="{file}"]')
                        if row.get_attribute('aria-expanded') != 'true':
                            row.locator('.caret').click()
                        page.wait_for_timeout(60)
                        return file, cid, page.locator(f'#lec-basket-list .bk-item[data-id="{cid}"]')
            return None, None, None

        for step in range(STEPS):
            page = rnd.choice(wins)
            op = rnd.choices(['clip', 'pick', 'remove', 'undo', 'move', 'copy', 'order', 'memo', 'title', 'rename', 'here', 'outside', 'editdoc', 'reload', 'other'],
                             [16, 9, 8, 4, 6, 3, 5, 9, 5, 2, 4, 6, 3, 2, 3])[0]
            if op in ('remove', 'move', 'copy', 'order', 'memo', 'title') and not have:
                op = 'clip'
            log.append(op)
            page.keyboard.press('Escape')
            if op in ('clip', 'pick'):
                n = rnd.choice(names)
                left = [i for i in range(1, 41) if (n, i) not in used]
                if not left:
                    continue
                i = rnd.choice(left)
                used.add((n, i))
                text = f'{n} 문단 {i} 입니다.'
                if not page.evaluate("(p) => import('/static/js/store.js').then(({ S }) => S.view?.type === 'doc' && S.view.path === p)", f'{n}.md'):
                    page.evaluate(OPEN, f'{n}.md')
                    page.wait_for_selector(f'#lec-view h1:has-text("{n}")', timeout=15000)
                    page.wait_for_timeout(120)
                page.locator('#lec-view p', has_text=re.compile(f'^{re.escape(text)}')).first.click()
                if op == 'clip':
                    page.keyboard.press('Alt+c')
                else:
                    page.keyboard.press('Alt+Shift+c')
                    page.wait_for_selector('#lec-boxpick:not([hidden])')
                    if rnd.random() < 0.35 and boxes < 6:
                        boxes += 1
                        page.keyboard.insert_text(f'질문 {seed}-{boxes}')
                        page.wait_for_timeout(40)
                    else:
                        for _ in range(rnd.randint(0, 2)):
                            page.keyboard.press('ArrowDown')
                        sel = page.locator('#lec-boxpick button.sel')
                        if 'new' in (sel.get_attribute('class') or ''):
                            page.keyboard.press('ArrowUp')
                        if 'new' in (page.locator('#lec-boxpick button.sel').get_attribute('class') or ''):
                            boxes += 1
                            page.keyboard.insert_text(f'질문 {seed}-{boxes}')
                            page.wait_for_timeout(40)
                    page.keyboard.press('Enter')
                ok = until(page, lambda: sum(x[1] == text for items in disk().values() for x in items) == 1, 8000)
                where = [f for f, items in disk().items() if any(x[1] == text for x in items)]
                if not ok:
                    check(f'[{seed}] {step} {op}: 담은 것이 파일에', False, (text, disk(), page.evaluate("() => document.querySelector('#lec-toast')?.textContent")))
                    return
                have[text] = where
            elif op == 'other':   # 저장을 기다리지 않고 곧바로 다른 일
                page.evaluate("() => window.dispatchEvent(new Event('focus'))")
            elif op == 'remove':
                sync()
                text = rnd.choice(sorted(have))
                file, cid, row = card_of(page, text)
                if row is None:
                    continue
                row.focus()
                page.keyboard.press('Delete')
                have[text] = [f for f in have[text] if f != file]
                if not have[text]:
                    del have[text]
                deleted.append((page, file, text))
                quiet(page)
            elif op == 'undo':
                if not deleted or deleted[-1][0] is not page or not page.locator('#lec-basket-undo').is_visible():
                    continue
                _, file, text = deleted.pop()
                page.click('#lec-basket-undo button')
                have.setdefault(text, []).append(file)
                quiet(page)
            elif op in ('move', 'copy'):
                sync()
                if len(disk()) < 2:
                    continue
                text = rnd.choice(sorted(have))
                file, cid, row = card_of(page, text)
                if row is None:
                    continue
                row.click(button='right')
                page.locator('#lec-menu button[data-i]', has_text='다른 담기함으로 옮기기' if op == 'move' else '다른 담기함에 복사').click()
                page.wait_for_selector('#lec-boxpick:not([hidden])')
                cands = [f for f in disk() if f != file and f not in have[text]]
                opts = page.locator('#lec-boxpick button:not(.new)')
                m = page.evaluate("() => import('/static/js/store.js').then(({ S }) => Object.fromEntries(S.tab.clips.boxes.map((x) => [x.title, x.file])))")
                idx = [k for k in range(opts.count()) if m.get(opts.nth(k).locator('.bp-name').inner_text()) in cands]
                if not idx:
                    page.keyboard.press('Escape')
                    continue
                k = rnd.choice(idx)
                to = m[opts.nth(k).locator('.bp-name').inner_text()]
                opts.nth(k).click()
                have[text] = [f for f in have[text] if op == 'copy' or f != file] + [to]
                deleted.clear()   # 옮기면 되돌리기가 없어진다
                until(page, lambda: any(x[1] == text for x in disk()[to]), 6000)
                quiet(page)
            elif op == 'order':
                sync()
                file, cid, row = card_of(page, rnd.choice(sorted(have)))
                if row is not None:
                    row.focus()
                    page.keyboard.press(rnd.choice(['Alt+ArrowUp', 'Alt+ArrowDown']))
                    quiet(page)
            elif op in ('memo', 'title'):
                sync()
                text = rnd.choice(sorted(have))
                if len(have[text]) != 1:
                    continue
                file, cid, row = card_of(page, text)
                if row is None:
                    continue
                row.click()
                card = page.locator(f'#lec-view .cb-card[data-id="{cid}"]')
                card.wait_for(timeout=10000)
                value = f'{op}-{seed}-{step}'
                card.locator('.cb-memo' if op == 'memo' else '.cb-name').fill(value)
                old = words.get(text, ('', ''))
                words[text] = (old[0], value) if op == 'memo' else (value, old[1])
                if rnd.random() < 0.5:
                    page.keyboard.press('Control+Tab')   # 쓰다가 곧바로 떠난다
                else:
                    quiet(page)
            elif op == 'rename':
                sync()
                f = rnd.choice(sorted(disk()))
                row = page.locator(f'#lec-basket-list .bk-box[data-file="{f}"]')
                if not row.count():
                    continue
                row.click()
                page.wait_for_selector('#lec-view.clips-view .cb-title', timeout=10000)
                page.fill('#lec-view .cb-title', f'이름 {seed}-{step}')
                page.keyboard.press('Tab')
            elif op == 'here':
                rows = page.locator('#lec-basket-list .bk-box:not(.cur)')
                if rows.count():
                    r = rows.nth(rnd.randrange(rows.count()))
                    r.hover()
                    r.locator('.bk-here').click()
            elif op == 'outside' and disk():   # Claude Code 자리 — 파일 끝에 조각을 더하거나 남의 메모를 고친다
                f = rnd.choice(sorted(disk()))
                quiet()
                body = src(f)
                outside += 1
                text = f'밖에서 더함 {seed}-{outside}'
                (clips / f).write_text(body.rstrip('\n') + f'\n\n<!-- lectern-clip id=out{seed}x{outside} path=%EA%B0%80%EA%B2%A9.md line=3 -->\n<!-- lectern-clip-text -->\n{text}\n<!-- /lectern-clip -->\n', encoding='utf-8', newline='\n')
                have[text] = [f]
            elif op == 'editdoc':
                d = proj / f'{rnd.choice(names)}.md'
                d.write_text(d.read_text(encoding='utf-8').rstrip('\n') + f'\n\n덧붙인 줄 {step}.\n', encoding='utf-8', newline='\n')
                time.sleep(0.05)
            elif op == 'reload':
                page.evaluate("() => document.activeElement?.blur?.()")
                page.wait_for_timeout(80)
                cur = page.evaluate(CUR)
                quiet(page)
                load(page)
                until(page, lambda: page.evaluate("() => import('/static/js/store.js').then(({ S }) => !!S.tab?.clips?.loaded)"), 8000)
                saved = json.loads((config / 'config.json').read_text(encoding='utf-8')).get('projects', {})
                deleted = [d for d in deleted if d[0] is not page]
                if cur and not any(v.get('clip') for v in saved.values()):
                    check(f'[{seed}] {step} 담는 곳이 설정에', False, saved)
        sync()
        sync()
        got = disk()
        want = {}
        for text, files in have.items():
            for f in files:
                want.setdefault(f, []).append(text)
        real = {f: sorted(x[1] for x in items) for f, items in got.items() if items}
        want = {f: sorted(v) for f, v in want.items()}
        check(f'[{seed}] {STEPS}걸음 뒤 파일에 있는 조각이 본보기와 같다 (조각 {sum(map(len, want.values()))}개, 담기함 {len(got)}개)', real == want,
              {f: (sorted(set(want.get(f, [])) - set(real.get(f, []))), sorted(set(real.get(f, [])) - set(want.get(f, [])))) for f in {*real, *want} if real.get(f) != want.get(f)})
        dup = [i for items in got.values() for i in [x[0] for x in items] if [x[0] for x in items].count(i) > 1]
        check(f'[{seed}] 한 담기함 안에 두 벌이 없다', not dup, dup)
        lost = [(text, w) for text, w in words.items() if text in have and len(have[text]) == 1 and not all(x in ''.join(h for items in got.values() for _, t, h in items if t == text) for x in w if x)]
        check(f'[{seed}] 쓴 제목과 메모가 남는다 ({len(words)}곳)', not lost, lost)
        for k, w in enumerate(wins):
            m = {f: sorted(t for _, t, *_ in items) for f, items in w.evaluate(MODEL).items() if items}
            check(f'[{seed}] 창 {k + 1} 의 목록도 파일과 같다', m == real, {f: (m.get(f), real.get(f)) for f in {*m, *real} if m.get(f) != real.get(f)})
        f = max(real, key=lambda x: len(real[x]))
        wins[0].locator(f'#lec-basket-list .bk-box[data-file="{f}"]').click()
        wins[0].wait_for_selector('#lec-view.clips-view .cb-card', timeout=15000)
        wins[0].wait_for_timeout(400)
        order = [x[0] for x in got[f]]
        check(f'[{seed}] 펼친 화면의 차례가 파일과 같다', wins[0].evaluate("() => [...document.querySelectorAll('#lec-view .cb-card')].map((e) => e.dataset.id)") == order)
        check(f'[{seed}] 화면 스크립트 오류 없음', not errors, errors[:3])
        if fails:
            print('      걸음:', ' '.join(log))
        b.close()
    finally:
        stop(server, home)


try:
    with sync_playwright() as p:
        for s in SEEDS:
            print(f'[임의의 사용자 — 시드 {s}]')
            run(p, s)
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
report()
