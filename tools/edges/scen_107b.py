"""0.106·0.107 사람 시나리오 2 — 임의의 사용자 (D202·D203). 시드마다 동작을 마구 섞고 걸음마다 지켜야 할 것을 본다:

- '문서' 의 오피스 묶음 개수 = 디스크에서 그 확장자를 가진 파일 수 (숨긴 것·제외 폴더 안은 빼고), 보이는 묶음 = 설정에서 켠 것 가운데 파일이 있는 것
- '폴더' 묶음의 맨 위 행 = 디스크의 맨 위 항목 모두 (숨긴 것도)
- 있던 파일은 사라지거나 바뀌지 않는다 (붙여 넣기는 덮어쓰지 않는다 — 밖에서 지운 것만 빼고)
- Ctrl+C 한 뒤의 클립보드 = 고른 행의 전체 경로
- 화면 스크립트 오류가 없다

동작: 탐색기에서 복사한 것(파일·폴더·숨긴 것·오피스 섞어서)을 아무 폴더에 Ctrl+V 나 우클릭 붙여 넣기, 여럿 골라 Ctrl+C, 하위 묶음 켜고 끄기(우클릭·설정 창),
하위 묶음 펼치기, 오피스 행 누르기, '제목' 단추, 묶음 바꾸기, 폴더 펼치고 접기, 밖에서 파일 만들고 지우기, F5.
시드를 주면 그것만 (python scen_107b.py 7)"""
import hashlib
import json
import os
import random
import sys
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import ROOT, hold_clipboard, check, fails, report, serve, stop, until

sys.path[:0] = [str(ROOT)]
from lectern import fileclip  # noqa: E402
from lectern.scanner import DEFAULT_EXCLUDE_DIRS  # noqa: E402

if sys.platform != 'win32':
    print('Windows 에서만')
    report()
    raise SystemExit(0)
hold_clipboard()   # 클립보드를 쓰는 다른 묶음과 겹치지 않게

SEEDS = [int(x) for x in sys.argv[1:]] or [1, 2, 3]
STEPS = 45
OFFICE = {'word': {'docx', 'doc', 'docm', 'dotx', 'dot', 'rtf', 'odt'}, 'ppt': {'pptx', 'ppt', 'pptm', 'ppsx', 'pps', 'potx', 'odp'},
          'excel': {'xlsx', 'xls', 'xlsm', 'xlsb', 'xltx', 'csv', 'tsv', 'ods'}, 'hwp': {'hwp', 'hwpx'}}
OPTIONAL = ['word', 'ppt', 'excel', 'hwp', 'work', 'marks', 'tasks']
EXCLUDE = {x.lower() for x in DEFAULT_EXCLUDE_DIRS}
KINDS = "() => [...document.querySelectorAll('#lec-docs .kind-head')].map((b) => [b.dataset.kind, b.querySelector('.n').textContent])"
FOLDER = "() => [...document.querySelectorAll('#lec-folder-list .row')].map((r) => r.dataset.path)"
CONF = "() => import('/static/js/store.js').then(({ S }) => S.config.doc_kinds)"


def office_counts(root):
    n = {k: 0 for k in OFFICE}
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d.lower() not in EXCLUDE]
        for f in files:
            if f.startswith('.') or '.' not in f:
                continue
            ext = f.rsplit('.', 1)[1].lower()
            for k, exts in OFFICE.items():
                if ext in exts:
                    n[k] += 1
    return n


def office_files(root):
    out = {k: [] for k in OFFICE}
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d.lower() not in EXCLUDE]
        for f in files:
            if f.startswith('.') or '.' not in f:
                continue
            for k, exts in OFFICE.items():
                if f.rsplit('.', 1)[1].lower() in exts:
                    out[k].append(Path(dirpath, f).relative_to(root).as_posix())
    return {k: sorted(v) for k, v in out.items()}


def digest(root):
    out = {}
    for p in root.rglob('*'):
        if p.is_file():
            out[p.relative_to(root).as_posix()] = hashlib.md5(p.read_bytes()).hexdigest()
    return out


def make_pool(base):
    pool = base / '메일함'
    (pool / '묶음 폴더' / '.숨김').mkdir(parents=True)
    names = ['보고서.docx', '옛 보고서.doc', '발표.pptx', '공문.hwp', '공문2.hwpx', '가격.csv', '재고.xlsx', '목록.tsv', '메모.txt', '그림.png', '.DS_Store', '.env']
    for i, n in enumerate(names):
        (pool / n).write_bytes(f'{n}-{i}'.encode())
    (pool / '묶음 폴더' / '안의 표.csv').write_text('a\n1\n', encoding='utf-8')
    (pool / '묶음 폴더' / '안의 문서.docx').write_bytes(b'inner')
    (pool / '묶음 폴더' / '.숨김' / 'x.pptx').write_bytes(b'hidden ppt')
    return sorted(pool.iterdir())


def run(seed):
    rnd = random.Random(seed)
    base = Path(tempfile.mkdtemp(prefix=f'lec-scen107b-{seed}-'))
    proj = base / '과제'
    (proj / '보고').mkdir(parents=True)
    (proj / '자료' / '원자료').mkdir(parents=True)
    (proj / 'node_modules').mkdir()
    (proj / '보고' / '본문.md').write_text('# 본문 제목\n\n- [ ] 할 일 하나\n\n<mark>칠한 글</mark>\n', encoding='utf-8', newline='\n')
    (proj / 'WORK.md').write_text('# 업무\n', encoding='utf-8', newline='\n')
    (proj / '자료' / '처음.csv').write_text('x\n1\n', encoding='utf-8')
    (proj / 'node_modules' / '숨은.docx').write_bytes(b'x')
    pool = make_pool(base)
    config = base / 'config'
    config.mkdir()
    (config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
    server, url, port = serve(proj, config)
    print(f'[시드 {seed}]')
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page(viewport={'width': 1300, 'height': 860})
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)[:300]))
            page.goto(url)
            page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
            page.wait_for_timeout(500)
            known = digest(proj)
            removed = set()
            log = []

            def section(name):
                page.click(f'#lec-{name}-head')
                page.wait_for_timeout(100)

            def folder_dirs():
                return [x for x in page.evaluate(FOLDER) if (proj / x).is_dir() and not (proj / x).is_symlink()]

            def paste_into(target):
                before = sum(1 for _ in proj.rglob('*'))
                if rnd.random() < 0.5:
                    page.focus(f'#lec-folder-list .row[data-path="{target}"]')
                    page.keyboard.press('Control+v')
                else:
                    page.click(f'#lec-folder-list .row[data-path="{target}"]', button='right')
                    page.locator('#lec-menu').get_by_text('붙여 넣기', exact=False).first.click()
                until(page, lambda: sum(1 for _ in proj.rglob('*')) > before, ms=15000)

            def step(i):
                what = rnd.choice(['paste', 'paste', 'copy', 'kind_toggle', 'kind_open', 'office_click', 'titles', 'section', 'expand', 'outside', 'refresh', 'settings'])
                log.append(what)
                if what == 'paste':
                    section('folder')
                    dirs = folder_dirs() or ['']
                    target = rnd.choice([d for d in dirs if not d.startswith('node_modules')] or [''])
                    fileclip.put(rnd.sample(pool, rnd.randint(1, 4)))
                    if target:
                        paste_into(target)
                elif what == 'copy':
                    section('folder')
                    rows = [x for x in page.evaluate(FOLDER) if x and not (proj / x).is_symlink()]
                    if not rows:
                        return
                    pick = rnd.sample(rows, min(len(rows), rnd.randint(1, 3)))
                    page.click(f'#lec-folder-list .row[data-path="{pick[0]}"]')
                    for x in pick[1:]:
                        if page.locator(f'#lec-folder-list .row[data-path="{x}"]').count():
                            page.click(f'#lec-folder-list .row[data-path="{x}"]', modifiers=['Control'])
                    page.focus(f'#lec-folder-list .row[data-path="{pick[-1]}"]')
                    page.keyboard.press('Control+c')
                    want = sorted(str((proj / x).resolve()).lower() for x in pick)
                    ok = until(page, lambda: sorted(str(p.resolve()).lower() for p in fileclip.read()[0]) == want, ms=6000)
                    check(f'시드 {seed} 걸음 {i}: Ctrl+C 의 클립보드 = 고른 {len(pick)}개', ok, (pick, fileclip.read()))
                elif what == 'kind_toggle':
                    section('docs')
                    if not page.locator('#lec-docs .kind-head').count():
                        return
                    page.click('#lec-docs .kind-head >> nth=0', button='right')
                    name = rnd.choice(['Word', 'PowerPoint', 'Excel·CSV', '한글(HWP)', '업무', '형광펜', '할 일'])
                    page.locator('#lec-menu').get_by_text(name, exact=True).click()
                elif what == 'settings':
                    page.click('#lec-btn-settings')
                    page.wait_for_selector('#lec-set-kinds input', timeout=5000)
                    page.click(f'#lec-set-kinds input[data-kind="{rnd.choice(OPTIONAL)}"]')
                    page.wait_for_timeout(200)
                    page.keyboard.press('Escape')
                elif what == 'kind_open':
                    section('docs')
                    heads = page.locator('#lec-docs .kind-head')
                    if heads.count():
                        heads.nth(rnd.randrange(heads.count())).click()
                elif what == 'office_click':
                    section('docs')
                    rows = page.locator('#lec-tree .row[data-file]')
                    if rows.count():
                        rows.nth(rnd.randrange(rows.count())).click()
                elif what == 'titles':
                    page.click('#lec-btn-titles')
                elif what == 'section':
                    section(rnd.choice(['docs', 'code', 'others', 'folder']))
                elif what == 'expand':
                    section('folder')
                    dirs = page.locator('#lec-folder-list .row.dir [data-toggle]')
                    if dirs.count():
                        dirs.nth(rnd.randrange(dirs.count())).click()
                elif what == 'outside':
                    if rnd.random() < 0.6:
                        ext = rnd.choice(['docx', 'pptx', 'xlsx', 'csv', 'hwp', 'txt'])
                        (proj / '자료' / f'밖에서 {i}.{ext}').write_bytes(f'outside {i}'.encode())
                    else:
                        cands = [p for p in (proj / '자료').glob('밖에서 *')]
                        if cands:
                            victim = rnd.choice(cands)
                            removed.add(victim.relative_to(proj).as_posix())
                            victim.unlink()
                elif what == 'refresh':
                    page.keyboard.press('F5')
                    page.wait_for_timeout(600)

            def look(i):
                # 오피스 묶음의 개수 = 디스크 (보이는 것만), 보이는 묶음 = 켠 것
                on = page.evaluate(CONF)

                def ok():   # 디스크도 다시 센다 — 큰 붙여 넣기는 기다리는 동안에도 이어진다
                    want = office_counts(proj)
                    got = dict(page.evaluate(KINDS))
                    for k in OFFICE:
                        shown = k in got
                        should = k in on and want[k] > 0
                        if shown != should or (shown and got[k] != str(want[k])):
                            return False
                    return not any(k in got for k in ('work', 'marks', 'tasks') if k not in on)
                good = until(page, ok, ms=12000)
                detail = (dict(page.evaluate(KINDS)), office_counts(proj), on)
                if not good:   # 어느 파일이 다르게 세어지는지
                    app = page.evaluate("""() => import('/static/js/store.js').then(({ S }) => { const out = []; const walk = (ns) => { for (const n of ns) { if (n.type === 'file') out.push(n.path); else if (!n.excluded && n.children) walk(n.children); } }; walk(S.tab.others.data?.tree || []); return out; })""")
                    disk = sorted(p.relative_to(proj).as_posix() for p in proj.rglob('*') if p.is_file())
                    detail = detail + ([x for x in app if x not in disk], [x for x in disk if x not in app and not any(s.startswith('.') for s in x.split('/'))], {k: sorted(x for x in app if '.' in x.rsplit('/', 1)[-1] and x.rsplit('.', 1)[-1].lower() in OFFICE[k]) for k in OFFICE}, office_files(proj))
                check(f'시드 {seed} 걸음 {i} ({log[-1]}): 오피스 묶음 = 디스크, 보이는 묶음 = 켠 것', good, detail)
                # '폴더' 묶음이 펼쳐 있으면 맨 위 항목이 모두 보인다
                if page.locator('#lec-folder.grow, #lec-folder:not(.closed)').count() and page.evaluate(FOLDER):
                    top = sorted(x.name for x in proj.iterdir())
                    seen = until(page, lambda: all(n in page.evaluate(FOLDER) for n in top), ms=10000)
                    check(f'시드 {seed} 걸음 {i}: \'폴더\' 묶음에 맨 위 항목 모두 (숨긴 것도)', seen, (top, page.evaluate(FOLDER)[:20]))
                # 있던 파일은 그대로 (밖에서 지운 것만 빼고)
                now = digest(proj)
                lost = [k for k, v in known.items() if k not in removed and now.get(k) != v]
                check(f'시드 {seed} 걸음 {i}: 있던 파일은 사라지거나 바뀌지 않았다', not lost, lost[:5])
                known.update(now)
                check(f'시드 {seed} 걸음 {i}: 화면 오류 없음', not errors, errors[:3])

            for i in range(1, STEPS + 1):
                try:
                    step(i)
                except Exception as e:   # noqa: BLE001 — 동작 하나가 실패해도 다음 걸음
                    print(f'  (걸음 {i} {log[-1] if log else ""} 건너뜀: {str(e)[:120]})')
                    page.keyboard.press('Escape')
                look(i)
            print(f'  동작: {", ".join(log)}')
            b.close()
    except Exception:   # noqa: BLE001
        traceback.print_exc()
        fails.append(f'시드 {seed} 점검이 멈춤')
    finally:
        stop(server, base)


for s in SEEDS:
    run(s)
report()
