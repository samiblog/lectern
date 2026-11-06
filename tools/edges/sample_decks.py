"""슬라이드 예제 (samples/slides): 열 개 모두 점검 없이 그려지고, 글을 한 줄 편집으로 고칠 수 있고, 과정 문서와 목록이 이어지는지"""
import re
import shutil
import tempfile
import traceback
from pathlib import Path
from urllib.parse import unquote

from playwright.sync_api import sync_playwright

from harness import ROOT, check, fails, report, serve, stop

base = Path(tempfile.mkdtemp(prefix='lec-sampledecks-'))
proj = base / 'proj'
shutil.copytree(ROOT / 'samples', proj)
slides = proj / 'slides'
decks = sorted(slides.glob('[0-9][0-9]-*.md'))
config = base / 'config'
config.mkdir()
server, url, port = serve(proj, config)
extra = []
OPEN = "(path) => import('/static/js/store.js').then(({ emit }) => emit('open', { type: 'doc', path, force: true }))"
LOOK = """async () => { const sp = await import('/static/js/spotlight.js'); const ln = await import('/static/js/lineunits.js'); const v = document.querySelector('#lec-view'); const src = sp.sourceLines();
  const wraps = [...v.querySelectorAll(':scope > .lec-slide-wrap')];
  let text = 0, ok = 0;
  for (const u of sp.currentUnits()) {
    if (u.el.matches('pre.mermaid, pre.lec-chart, .math-block, .diagram-error') || (u.el.querySelector('img') && !u.el.textContent.trim())) continue;
    text += 1;
    if (ln.editableLines(u, src).some((n) => ln.lineSlot(v, n, src))) ok += 1;
  }
  return { slides: wraps.length, text, ok, issues: wraps.flatMap((w, i) => JSON.parse(w.dataset.issues || '[]').map((x) => `${i + 1}장 ${x.text}`)),
    errors: [...v.querySelectorAll('.diagram-error')].map((e) => e.textContent.slice(0, 80)), broken: [...v.querySelectorAll('img')].filter((i) => !i.naturalWidth).map((i) => i.getAttribute('src')),
    plain: wraps.slice(1).filter((w) => !w.querySelector(':scope > .lec-slide-notes')).length, html: [...v.querySelectorAll('.lec-slide > :not(.lec-cell, h1, h2, h3, p, ul, ol, table, .table-wrap, pre, blockquote, header, footer, .lec-slide-bg, .lec-eyebrow, .lec-links, style, script, .lec-tag, .lec-slide-tags)')].length }; }"""


def links_of(path):
    """문서의 상대 링크가 가리키는 파일들"""
    text = path.read_text(encoding='utf-8')
    text = re.sub(r'^(`{3,}).*?^\1\s*$', '', text, flags=re.M | re.S)   # 코드 조각의 경로는 완성본 기준이다
    text = re.sub(r'`[^`\n]*`', '', text)
    for quoted, plain in re.findall(r'\]\(<([^>]+)>|\]\(([^)#\s]+)', text):
        target = quoted or plain
        if re.match(r'[a-z]+:', target):
            continue
        yield target, (path.parent / unquote(target)).resolve()


def run():
    check('예제 열 개', len(decks) == 10, [d.name for d in decks])
    check('번호가 이어진다', [d.name[:2] for d in decks] == [f'{i:02d}' for i in range(1, 11)], [d.name[:2] for d in decks])
    for doc in (slides / 'README.md', slides / 'README.en.md'):
        text = doc.read_text(encoding='utf-8')
        for deck in decks:
            check(f'{doc.name} 가 {deck.stem} 을 잇는다', f'{deck.stem}.md' in text and f'{deck.stem}-과정.md' in text)
    for name in ('README.md', 'README.en.md'):
        check(f'예제 프로젝트의 {name} 가 목록을 잇는다', 'slides/README' in (proj / name).read_text(encoding='utf-8'))
    for doc in ('web/help/manual.md', 'web/help/manual.en.md', 'web/help/slides.md', 'web/help/slides.en.md'):
        check(f'{doc} 가 예제를 말한다', 'slides/README.md' in (ROOT / doc).read_text(encoding='utf-8'))
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1400, 'height': 900})
        page.on('pageerror', lambda e: extra.append(str(e)[:200]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row')
        for deck in decks:
            print(f'[{deck.stem}]')
            rel = f'slides/{deck.name}'
            page.evaluate(OPEN, rel)
            page.wait_for_function("(n) => document.querySelector('#lec-st-path')?.textContent.includes(n) && document.querySelector('#lec-view .lec-slide')", arg=deck.name, timeout=10000)
            page.wait_for_timeout(1800)
            r = page.evaluate(LOOK)
            check('장 수', 6 <= r['slides'] <= 9, r['slides'])
            check('점검 0건', not r['issues'], r['issues'][:3])
            check('차트 오류 없음', not r['errors'], r['errors'][:2])
            check('그림을 모두 불렀다', not r['broken'], r['broken'][:2])
            check('글을 모두 한 줄 편집으로 연다', r['ok'] == r['text'] and r['text'] > 0, [r['ok'], r['text']])
            check('내용 장마다 노트', r['plain'] == 0, r['plain'])
            process = slides / '과정' / f'{deck.stem}-과정.md'
            check('과정 문서가 있다', process.is_file())
            if process.is_file():
                text = process.read_text(encoding='utf-8')
                heads = re.findall(r'^## (\d)\. ', text, re.M)
                check('과정의 일곱 단계', heads == list('1234567'), heads)
                check('완성본으로 가는 링크', f'../{deck.name}' in text)
                check('요청문이 있다', '```text' in text)
                for target, path in links_of(process):
                    check(f'링크 {target}', path.exists())
            for target, path in links_of(deck):
                check(f'링크 {target}', path.exists())
        print('[복잡한 배치]')
        folder = slides / '복잡한-배치'
        complex_decks = sorted(folder.glob('[0-9][0-9]-*.md'))
        check('복잡한 배치 스무 개', len(complex_decks) == 20, len(complex_decks))
        for deck in complex_decks:
            rel = f'slides/복잡한-배치/{deck.name}'
            page.evaluate(OPEN, rel)
            page.wait_for_function("(n) => document.querySelector('#lec-st-path')?.textContent.includes(n) && document.querySelector('#lec-view .lec-slide')", arg=deck.name, timeout=10000)
            page.wait_for_timeout(1300)
            r = page.evaluate(LOOK)
            check(f'{deck.stem}: 점검 0건', not r['issues'], r['issues'][:3])
            check(f'{deck.stem}: 차트·그림 오류 없음', not r['errors'] and not r['broken'], [r['errors'][:2], r['broken'][:2]])
            check(f'{deck.stem}: 글을 모두 한 줄 편집으로 연다', r['ok'] == r['text'], [r['ok'], r['text']])
        for doc in (slides / 'README.md', slides / 'README.en.md', folder / 'README.md', folder / 'README.en.md'):
            for target, path in links_of(doc):
                check(f'{doc.name} 의 링크 {target}', path.exists())
        check('화면 오류 없음', not extra, extra[:3])
        b.close()


try:
    run()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
