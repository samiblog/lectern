"""0.111 사람 시나리오 2 — 임의의 사용자 (D210·D211). 시드마다 동작을 마구 섞고 걸음마다 지켜야 할 것을 본다:

- 글머리 글자 묶음의 □(수준 0)는 그 묶음에 ○(수준 1)가 있을 때만 맨 위 굵기(--lec-list-top-weight — 스타일·내 스타일이 정한 값, GitHub 은 보통)이고
  아니면 본문 굵기. Markdown 목록의 맨 위 항목도 그 목록에 하위가 있을 때만.
- '내 스타일 만들기' 창이 닫혀 있으면 미리보기가 없다.
- 손으로 쓴 스타일 파일은 바뀌지 않는다. 스타일 폴더의 파일 수 = 손으로 쓴 것 + 창으로 저장한 새 스타일 수.
- 화면 스크립트 오류가 없다.

동작: □ 줄에서 Shift+Enter 로 ○ 줄 더하기, ○ 줄 Delete 두 번, Markdown 항목 레벨 안·밖, AI(밖에서)가 ○ 줄을 더하거나 지우기,
스타일 바꾸기(GitHub·어두운·내 스타일 포함), 창을 열어 칸을 바꾸고 Esc, 새 스타일로 저장, 이 창이 만든 스타일을 고쳐 쓰기.
시드를 주면 그것만 (python scen_111b.py 7)"""
import hashlib
import json
import random
import sys
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop, until

SEEDS = [int(x) for x in sys.argv[1:]] or [1, 2, 3]
STEPS = 28
DOC = """# 주간 점검

## 1. 핵심

□ 생산성 효과는 서비스업에서 먼저
○ 3분기 서비스업 생산성 1.8%
□ 고용 충격은 직무 단위로
□ 투자는 데이터센터로

## 2. 지표

- 데이터센터 투자
  - 미국 빅테크 4사
- 전력 수요
- 반도체 수출

## 3. 위험

□ 전력망 병목
□ 규제 불확실성
"""
HAND = '/* lectern-style\n   name: 손\n   base: paper\n*/\n.md-body h2 { border-bottom: 2px solid rgb(0, 128, 0); }\n'

STATE = """() => {
  const raw = getComputedStyle(document.documentElement).getPropertyValue('--lec-list-top-weight').trim();
  const top = raw === 'normal' ? 400 : raw === 'bold' ? 700 : Number(raw) || 400;   // 지금 스타일이 정한 맨 위 항목의 굵기 (내 스타일이 '보통' 일 수 있다)
  const body = (e) => Number(getComputedStyle(e.closest('#lec-view')).fontWeight);
  const weight = (e) => Number(getComputedStyle(e).fontWeight);
  const bad = [];
  for (const g of document.querySelectorAll('#lec-view .lec-marklist')) {
    const want = g.querySelector(':scope > .lec-lv1') ? top : body(g);
    for (const m of g.querySelectorAll(':scope > .lec-lv0')) if (Math.abs(weight(m) - want) > 60) bad.push('mark:' + m.textContent.slice(0, 12) + ':' + want + '/' + weight(m));
  }
  for (const ul of document.querySelectorAll('#lec-view > ul, #lec-view > ol')) {
    const want = ul.querySelector(':scope > li > ul, :scope > li > ol') ? top : body(ul);
    for (const li of ul.children) if (Math.abs(weight(li) - want) > 60) bad.push('li:' + li.textContent.slice(0, 12) + ':' + want + '/' + weight(li));
  }
  const preview = !!document.getElementById('lec-stylemaker-preview');
  const open = !document.querySelector('#lec-stylemaker').hidden;
  if (preview && !open) bad.push('preview-left');
  return bad;
}"""


def run(seed):
    rnd = random.Random(seed)
    base = Path(tempfile.mkdtemp(prefix=f'lec-scen111b-{seed}-'))
    proj = base / '과제'
    proj.mkdir()
    doc = proj / '주간.md'
    doc.write_text(DOC, encoding='utf-8', newline='\n')
    config = base / 'config'
    (config / 'styles').mkdir(parents=True)
    (config / 'styles' / '손.css').write_bytes(HAND.encode('utf-8'))
    hand_hash = hashlib.sha256(HAND.encode('utf-8')).hexdigest()
    (config / 'config.json').write_text(json.dumps({'work_alerts': False, 'theme': 'report'}), encoding='utf-8')
    src = lambda: doc.read_text(encoding='utf-8').replace('\r\n', '\n')  # noqa: E731
    saved = 0
    server, url, port = serve(proj, config)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={'width': 1300, 'height': 900})
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)[:300]))
            page.goto(url)
            page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
            page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: '주간.md' }))")
            page.wait_for_selector('#lec-view .lec-marklist', timeout=10000)

            def theme():
                return page.evaluate('() => document.documentElement.dataset.theme')

            def ext_write(text):
                time.sleep(1.05)
                doc.write_text(text, encoding='utf-8', newline='\n')
                until(page, lambda: page.locator('#lec-view .lec-marklist').count() > 0 and page.evaluate(
                    "(n) => document.querySelectorAll('#lec-view .lec-mark').length === n", sum(1 for ln in text.split('\n') if ln[:1] in '□○')), ms=10000)

            def lines(mark):
                return [ln for ln in src().split('\n') if ln.startswith(mark)]

            def pick(text):
                page.locator('#lec-view .lec-mark, #lec-view li', has_text=text).first.click()
                page.wait_for_timeout(200)

            def maker_open():
                page.select_option('#lec-theme', '__make')
                page.wait_for_selector('#lec-stylemaker:not([hidden])', timeout=8000)

            def maker_tweak():
                key, val = rnd.choice([('--md-size', rnd.choice([15, 16, 17, 18])), ('--md-line', rnd.choice([1.6, 1.8, 2])),
                                       ('--lec-list-top-scale', rnd.choice([100, 104, 110]))])
                f = page.locator(f'#lec-stylemaker [data-key="{key}"]')
                f.fill(str(val))
                f.dispatch_event('input')
                if rnd.random() < 0.5:
                    page.select_option('#lec-stylemaker select[data-key="--lec-list-top-weight"]', rnd.choice(['400', '650', '700']))
                return key

            ops = ['add_sub', 'del_sub', 'indent', 'ext_add', 'ext_del', 'theme', 'maker_cancel', 'maker_new', 'maker_resave']
            for step in range(STEPS):
                op = rnd.choice(ops)
                did = op
                try:
                    if op == 'add_sub':
                        tops = lines('□')
                        if tops:
                            line = rnd.choice(tops)
                            pick(line[2:14])
                            page.keyboard.press('Shift+Enter')
                            page.wait_for_selector('#lec-view .lec-line-edit', timeout=5000)
                            page.keyboard.press('Control+a')
                            page.keyboard.type(f'○ 사람이 더한 근거 {step}')
                            page.keyboard.press('Enter')
                            until(page, lambda: f'○ 사람이 더한 근거 {step}' in src())
                    elif op == 'del_sub':
                        subs = lines('○')
                        if subs:
                            line = rnd.choice(subs)
                            pick(line[2:14])
                            page.keyboard.press('Delete')
                            page.keyboard.press('Delete')
                            until(page, lambda: line not in src())
                    elif op == 'indent':
                        body = src()
                        if '  - 전력 수요' in body and rnd.random() < 0.6:
                            pick('전력 수요')
                            page.keyboard.press('Alt+Shift+ArrowLeft')
                            page.keyboard.press('Alt+Shift+ArrowLeft')
                            until(page, lambda: '\n- 전력 수요' in src())
                        elif '\n- 전력 수요' in body:
                            pick('전력 수요')
                            page.keyboard.press('Alt+Shift+ArrowRight')
                            page.keyboard.press('Alt+Shift+ArrowRight')
                            until(page, lambda: '  - 전력 수요' in src())
                    elif op == 'ext_add':
                        body = src().split('\n')
                        tops = [i for i, ln in enumerate(body) if ln.startswith('□')]
                        at = rnd.choice(tops)
                        body.insert(at + 1, f'○ AI 가 더한 근거 {step}')
                        ext_write('\n'.join(body))
                    elif op == 'ext_del':
                        ext_write('\n'.join(ln for ln in src().split('\n') if not ln.startswith('○')))
                    elif op == 'theme':
                        opts = [v for v in page.eval_on_selector_all('#lec-theme option', 'os => os.map(o => o.value)') if not v.startswith('__')]
                        want = rnd.choice([v for v in opts if v in ('report', 'default', 'github', 'github-dark', 'dark', 'paper') or v.startswith('user:')])
                        page.select_option('#lec-theme', want)
                        until(page, lambda: theme() == want or (want == 'auto'))
                        did = f'theme {want}'
                    elif op == 'maker_cancel':
                        maker_open()
                        maker_tweak()
                        page.keyboard.press('Escape')
                        until(page, lambda: page.locator('#lec-stylemaker').is_hidden())
                    elif op == 'maker_new':
                        maker_open()
                        maker_tweak()
                        name = f'스타일 {seed}-{step}'
                        page.fill('#lec-stylemaker-name', name)
                        page.click('#lec-stylemaker-save')
                        if page.locator('#lec-stylemaker-ask').is_visible():   # 이 창이 만든 스타일을 고른 채였으면 — 새 스타일로
                            page.click('#lec-stylemaker-new')
                            page.fill('#lec-stylemaker-name', name)
                            page.click('#lec-stylemaker-save')
                        if until(page, lambda: theme() == f'user:{name}', ms=8000):
                            saved += 1
                        did = f'maker_new {name}'
                    elif op == 'maker_resave':
                        cur = theme() or ''
                        made = cur.startswith('user:') and cur != 'user:손'
                        maker_open()
                        key = maker_tweak()
                        page.click('#lec-stylemaker-save')
                        if made:
                            page.locator('#lec-stylemaker-replace').click()
                            until(page, lambda: page.locator('#lec-stylemaker').is_hidden(), ms=8000)
                        elif page.locator('#lec-stylemaker-msg').is_visible():   # 이름이 없으면 저장하지 않는다
                            page.keyboard.press('Escape')
                        did = f'maker_resave {cur} {key}'
                        if page.locator('#lec-stylemaker').is_visible():
                            page.keyboard.press('Escape')
                except Exception as exc:   # noqa: BLE001 — 한 걸음이 멈춰도 다음 걸음으로 (그 걸음은 실패로 적는다)
                    check(f'[{seed}] {step} {did} — 멈추지 않는다', False, str(exc)[:200])
                    page.keyboard.press('Escape')
                page.wait_for_timeout(350)
                bad = until(page, lambda: not page.evaluate(STATE)) or page.evaluate(STATE)
                if bad is not True and bad:
                    check(f'[{seed}] {step} {did} — 목록 굵기·미리보기', False, bad[:4])
                files = sorted(x.name for x in (config / 'styles').glob('*.css'))
                hand_now = hashlib.sha256((config / 'styles' / '손.css').read_bytes()).hexdigest()
                if hand_now != hand_hash or len(files) != 1 + saved:
                    check(f'[{seed}] {step} {did} — 손으로 쓴 스타일은 그대로, 파일 수 = 1 + 새로 저장한 {saved}', False, files)
            check(f'[{seed}] {STEPS}걸음 — 지킬 것을 모두 지켰다 (스타일 {saved}개 저장)', not [f for f in fails if f.startswith(f'[{seed}]')])
            check(f'[{seed}] 화면 스크립트 오류 없음', not errors, errors[:5])
            browser.close()
    except Exception:   # noqa: BLE001
        traceback.print_exc()
        fails.append(f'[{seed}] 점검이 멈춤')
    finally:
        stop(server, base)


for s in SEEDS:
    print(f'[시드 {s}]')
    run(s)
report()
