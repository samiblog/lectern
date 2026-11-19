"""툴바·탭 막대가 창 폭마다 한 줄에 (2026-11-19 사용자 보고): 창 폭 900~1100px 에서 사이드바·뒤로·앞으로 단추가 '문서 열기'·글자 크기 단추
밑으로 깔렸다 — 묶음이 내용보다 좁아졌다. 한국어·영어로 720~1440px 를 20px 마다 재어 단추끼리 겹치지 않고 막대가 넘치지 않는다"""
import json
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop

base = Path(tempfile.mkdtemp(prefix='lec-toolbar-'))
proj = base / 'proj'
proj.mkdir(parents=True)
(proj / '문서.md').write_text('# 문서\n\n## 절\n\n본문입니다.\n', encoding='utf-8')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)

# 보이는 단추·묶음끼리 겹친 쌍과 막대의 넘침 (한쪽이 다른 쪽을 품은 것은 빼고)
MEASURE = """() => { const out = {};
  for (const sel of ['#lec-toolbar', '#lec-tabbar']) {
    const bar = document.querySelector(sel); if (!bar || !bar.offsetParent) continue;
    const items = [...bar.querySelectorAll(':scope > *, :scope > * > button, :scope > * > select, :scope > * > div')]
      .filter((e) => e.offsetParent && e.getBoundingClientRect().width > 0);
    const hits = [];
    for (let i = 0; i < items.length; i++) for (let j = i + 1; j < items.length; j++) {
      if (items[i].contains(items[j]) || items[j].contains(items[i])) continue;
      const a = items[i].getBoundingClientRect(), b = items[j].getBoundingClientRect();
      if (a.right - 1 > b.left && b.right - 1 > a.left && a.bottom - 1 > b.top && b.bottom - 1 > a.top)
        hits.push((items[i].id || items[i].className) + ' × ' + (items[j].id || items[j].className));
    }
    out[sel] = { over: bar.scrollWidth - bar.clientWidth, hits: hits.slice(0, 3) };
  }
  return out; }"""


def sweep(page, lang):
    bad = {}
    for w in range(1440, 700, -20):
        page.set_viewport_size({'width': w, 'height': 760})
        page.wait_for_timeout(60)
        got = page.evaluate(MEASURE)
        worse = {k: v for k, v in got.items() if v['over'] > 0 or v['hits']}
        if worse:
            bad[w] = worse
    check(f'{lang}: 720~1440px 의 어느 폭에서도 툴바·탭 막대의 단추가 겹치지 않고 넘치지 않는다', not bad, dict(list(bad.items())[:4]))


try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1440, 'height': 760})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        page.locator('#lec-tree .row.file[data-doc="문서.md"]').click()
        page.wait_for_selector('#lec-view h1')
        sweep(page, '한국어')
        page.set_viewport_size({'width': 1440, 'height': 760})
        lb = page.evaluate("() => getComputedStyle(document.querySelector('#lec-btn-work .lb')).display")
        check('넓은 창에서는 \'업무\' 같은 단추 이름이 보인다', lb != 'none', lb)

        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ language: 'en' }))")
        page.reload()
        page.wait_for_function("document.documentElement.lang === 'en'", timeout=15000)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        page.locator('#lec-tree .row.file[data-doc="문서.md"]').click()
        page.wait_for_selector('#lec-view h1')
        sweep(page, '영어')
        check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
