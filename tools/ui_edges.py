"""가장자리 점검: ui_smoke 에 없는 동작 — 문서에 적은 조합·실패 길·경쟁 상태·줄 구조 편집·데이터 보기를 실제 키로 본다.

tools/edges/ 의 묶음마다 임시 프로젝트·설정으로 서버를 따로 띄워 돌린다. 준비는 ui_smoke 와 같다 (playwright).

    python tools/ui_edges.py              :: 모두
    python tools/ui_edges.py structure    :: 이름이 맞는 것만
    python tools/ui_edges.py --changed    :: 고친 파일에 닿는 것만 (master 와 다른 파일, 커밋 전 것도)
    python tools/ui_edges.py -j 4         :: 4개씩 동시에 (묶음마다 서버·임시 폴더가 따로라 부딪히지 않는다 — 40분 → 10분쯤)

동시에 돌리면 묶음의 출력은 그 묶음이 끝날 때 한 덩어리로 찍는다. 지난 실행의 묶음별 시간(ui-shots/edges/times.json)으로 긴 묶음부터 넣는다.
--changed 로 돌리면 무작위 시험(tab_fuzz)은 씨앗을 모두 쓴다 (LECTERN_TEST_FUZZ=all — 전체 실행에서는 씨앗 하나).
실패한 묶음은 한 번 다시 돌린다 (동시에 돌렸어도 다시 돌릴 때는 하나씩). 종료 코드: 0 모두 통과, 1 두 번 모두 실패한 묶음이 있음, 3 흔들린 묶음만 있음 (다시 돌리니 통과).
실패하면 그때의 화면이 ui-shots/edges/ 에 남는다 (harness.py). 느린 PC·CI 에서는 LECTERN_TEST_SLOW=2 로 대기 시간을 늘린다.
"""
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import close_windows

ROOT = Path(__file__).resolve().parents[1]
SUITES = ['deckguard', 'slidecheck', 'templates', 'mdstyle', 'docedit', 'slideedit', 'sample_decks', 'reading', 'frames', 'lines', 'combos', 'structure', 'data', 'data_wide', 'hostile', 'input', 'notes', 'variety', 'refresh', 'solo', 'solo_cases', 'sample_lines', 'slides', 'sidebar', 'refs_vi', 'textbox', 'pickkeys', 'work', 'work_scenarios', 'work_more', 'impress', 'impress_scenarios', 'termfont', 'printpdf', 'closeall', 'chartdata', 'termstack', 'aitool', 'fastopen', 'inlinefmt', 'wordpick', 'sidekinds', 'exporthtml', 'layouts', 'exportdocx', 'export_scenarios', 'export_more', 'writingreq', 'work_tree', 'work_tree_more', 'keys_tidy', 'work_gantt', 'put_settings', 'scen_day', 'scen_levels', 'scen_gantt', 'scen_put', 'change_kinds', 'keys_tabs', 'scen_088', 'view_keys', 'aiscope', 'stylepick', 'focus_tabs', 'enter_chars', 'tab_trap', 'tab_fuzz', 'sidekeys', 'scen_093', 'dataedit', 'scen_094', 'scen_093_094', 'tablewidth', 'tablealign', 'scen_tables', 'linebreaks', 'toolbar_fit', 'newfiles', 'termreattach', 'labels', 'settings_term', 'scen_096', 'helpwindow', 'refwindows', 'exhibit', 'slidefit', 'scen_slidefit', 'wrapdrag']
# 고친 파일 → 돌릴 묶음. 맞는 것이 없는 web/·lectern/ 파일은 AREA_OTHER
AREAS = [
    (r'web/js/(aisetup|stylepick)\.js|lectern/aistatus\.py|web/help/(writing-styles\.json|new-style.*|business-report.*|academic-writing.*|plain-explainer.*)', ['aiscope', 'aitool', 'stylepick']),
    (r'web/js/(watch|search)\.js', ['refresh', 'reading', 'hostile', 'aiscope', 'focus_tabs']),
    (r'web/css/app\.css|web/index\.html|web/js/lang/en\.js|web/js/(textsize|docwidth|theme|spotlight)\.js', ['toolbar_fit']),
    (r'web/js/(newdialog|newdoc|others|tree|commands)\.js|lectern/editing\.py|lectern/server\.py', ['newfiles']),
    (r'web/js/(terminal|commands)\.js', ['termreattach']),
    (r'web/js/(tree|others|palette|search|recent|parts|doctabs)\.js', ['labels']),
    (r'web/js/(settings|terminal|ui)\.js', ['settings_term']),
    (r'web/js/(newdialog|terminal|settings|doctabs|lineedit)\.js|lectern/editing\.py', ['scen_096']),
    (r'web/js/(help|solo|doctabs|main|commands|tabs|util)\.js|lectern/windows\.py|lectern/server\.py|web/help/manual', ['helpwindow', 'refwindows']),
    (r'web/js/(charpick|datepick)\.js|web/data/chars\.json', ['enter_chars']),
    (r'web/js/(doc|toc|tablefit|slides|lineedit|charts|mermaid|mdhtml|layout|parts)\.js|web/themes/(base|print)\.css|web/layouts/.*', ['exhibit']),   # 전시물 — 캡션과 주·자료 (2026-11-20)
    (r'web/js/(slides|slidetools|charts)\.js|web/themes/base\.css', ['slidefit', 'scen_slidefit']),   # 슬라이드의 넘침 맞춤 (D188)
    (r'web/js/(line\w+|spotlight)\.js|lectern/editing\.py', ['linebreaks', 'tab_trap', 'tab_fuzz', 'enter_chars', 'docedit', 'slideedit', 'structure', 'lines', 'refresh', 'sample_lines', 'slides', 'textbox', 'pickkeys', 'termstack', 'inlinefmt', 'wordpick', 'tablealign', 'wrapdrag']),
    (r'web/js/(line\w+|spotlight|vikeys|editor|docops|docmenu|wordpick|main|others|tree)\.js', ['keys_tidy', 'scen_levels', 'change_kinds', 'scen_088', 'view_keys', 'tablealign']),
    (r'web/js/(inlinefmt|wordpick)\.js', ['inlinefmt', 'wordpick', 'docedit', 'pickkeys', 'reading', 'sidekinds', 'wrapdrag']),
    (r'web/js/(slide\w+|present|theme|csssafe)\.js|web/themes/.*', ['slides', 'slidecheck', 'deckguard', 'sample_decks', 'reading', 'textbox', 'impress', 'impress_scenarios', 'printpdf', 'tablewidth', 'tablealign', 'scen_tables']),
    (r'web/js/impress\w+\.js|lectern/htmlexport\.py|web/vendor/impress/.*', ['impress', 'impress_scenarios']),
    (r'samples/slides/.*|web/help/slides.*', ['sample_decks']),
    (r'web/js/project\.js|lectern/(scanner|docinfo|titlecache|state)\.py', ['fastopen', 'refresh', 'reading', 'sidebar', 'focus_tabs']),
    (r'web/js/(sideorder|tree|others)\.js|lectern/marks\.py', ['sidebar', 'sidekinds']),
    (r'web/js/(tree|others|palette|commands|diffmark|fold|main|help)\.js|lectern/config\.py|web/index\.html', ['sidekeys', 'scen_093', 'scen_093_094']),
    (r'web/js/(work|workdata|workalert|workview|datepick)\.js|lectern/work\.py|web/templates/work.*', ['work', 'work_scenarios', 'work_more', 'work_tree', 'work_tree_more', 'work_gantt', 'scen_gantt', 'scen_day']),
    (r'web/js/(refs|vikeys|editor|settings|help)\.js|web/vendor/codemirror/keymap/.*', ['refs_vi', 'textbox', 'docedit', 'reading', 'termfont', 'printpdf', 'aitool', 'aiscope', 'tablealign']),
    (r'web/js/(markdown|doc|fold)\.js', ['textbox', 'reading', 'docedit', 'hostile', 'tablewidth', 'tablealign', 'scen_tables']),
    # 2026-11-19 조사 — 표에 없어 기본 묶음만 돌던 모듈 (그 모듈을 실제로 쓰는 묶음으로)
    (r'web/js/(notes|notesdata)\.js', ['notes', 'variety', 'hostile']),
    (r'web/js/editsync\.js', ['docedit', 'refresh', 'combos']),
    (r'web/js/rawview\.js', ['aiscope']),
    (r'web/js/rename\.js', ['docedit', 'hostile', 'combos']),
    (r'web/js/(docwidth|textsize)\.js', ['tablewidth', 'scen_tables', 'combos', 'variety']),
    (r'web/js/(parts|snippet)\.js', ['reading', 'hostile', 'aitool', 'input']),
    (r'web/js/overview\.js', ['reading', 'hostile', 'work_tree_more']),
    (r'web/js/outline\.js', ['data', 'frames', 'reading', 'focus_tabs']),
    (r'web/js/(pathlink|position)\.js', ['reading', 'hostile', 'lines']),
    (r'web/js/recent\.js', ['sidebar', 'sidekinds', 'hostile', 'combos']),
    (r'web/js/(resize|status|bootguard|mermaid)\.js', ['reading', 'combos', 'variety', 'slides']),
    (r'web/js/(api|store|util|html|i18n)\.js', ['reading', 'combos', 'hostile', 'docedit', 'structure', 'refresh', 'variety', 'keys_tabs']),
    (r'web/js/(tablefit|tablefitplan|mdhtml|doc|tablecopy)\.js|web/themes/base\.css', ['tablewidth', 'tablealign', 'scen_tables', 'reading', 'chartdata', 'exporthtml', 'printpdf']),
    (r'web/js/(csvview|tabledata|quickchart|codeview|charts)\.js|lectern/sheet\.py', ['data', 'data_wide', 'hostile', 'chartdata', 'dataedit', 'scen_094']),
    (r'web/js/(editor|icons|lineedit|spotlight)\.js|lectern/editing\.py', ['dataedit', 'scen_094', 'docedit', 'data_wide']),
    (r'web/js/(chartdata|chartops|tablecopy)\.js', ['chartdata']),
    (r'web/js/(htmldoc|nav|find|toc)\.js', ['frames', 'reading', 'hostile', 'refresh', 'textbox', 'focus_tabs']),
    (r'web/js/solo\.js|lectern/(windows|native)\.py', ['solo', 'solo_cases']),
    (r'web/js/(headstyle|mdstyle)\.js', ['mdstyle', 'docedit']),
    (r'web/js/(deletedoc|newdialog|newdoc|docops|putmenu|lineblock|chartops)\.js|lectern/trash\.py', ['docedit', 'slideedit', 'textbox', 'pickkeys']),
    (r'web/js/(slidegallery|pptxdialog)\.js|web/templates/.*|lectern/(slidetemplates|pptxexport)\.py|skills/lectern-to-pptx/.*', ['templates']),
    (r'samples/.*', ['sample_lines']),
    (r'web/js/(tabs|doctabs|tabdrag|panes|tree|others|main|terminal|gather|spread)\.js', ['combos', 'structure', 'hostile', 'solo', 'solo_cases', 'termfont', 'closeall', 'termstack', 'aitool', 'fastopen', 'focus_tabs', 'reading', 'frames', 'tab_trap', 'tab_fuzz']),
    (r'web/js/ui\.js|lectern/terminal\.py', ['termstack', 'aitool', 'termreattach']),
    (r'web/js/help\.js|web/index\.html|web/help/manual', ['keys_tabs']),
    (r'web/js/(putmenu|settings|theme|vikeys|printdoc|work|main)\.js|web/index\.html|lectern/config\.py', ['put_settings', 'scen_put', 'change_kinds', 'aiscope']),
    (r'web/js/(aitool|basket)\.js|lectern/config\.py|web/index\.html', ['aitool', 'reading', 'combos', 'aiscope']),
    (r'web/js/(printdoc|docmenu)\.js|lectern/pdfexport\.py|web/help/(research-)?writing.*', ['printpdf', 'exporthtml', 'layouts', 'exportdocx', 'export_scenarios', 'export_more']),
    (r'lectern/docxexport\.py|skills/lectern-to-docx/.*', ['exportdocx', 'export_scenarios', 'export_more']),
    (r'web/js/(docmenu|aitool|settings)\.js|web/help/(review|voice|research-writing).*|web/index\.html|lectern/state\.py', ['writingreq', 'aiscope']),
    (r'web/js/(mdhtml|htmlpack|layout)\.js', ['exporthtml', 'layouts', 'impress', 'impress_scenarios']),
    (r'web/layouts/.*|lectern/layouts\.py|web/help/layouts.*', ['layouts']),
    (r'tools/edges/harness\.py', SUITES),
    (r'tools/edges/(\w+)\.py', None),
]
AREA_OTHER = ['reading', 'combos', 'hostile']


def changed_files() -> list[str]:
    def git(*args):
        return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True, encoding='utf-8').stdout.split('\n')
    return sorted({f for f in git('diff', '--name-only', 'master') + git('ls-files', '--others', '--exclude-standard') if f})


def suites_for(files: list[str]) -> list[str]:
    """고친 파일에 닿는 묶음 — 파일이 걸리는 줄을 모두 합친다 (처음 맞는 줄에서 멈추면 doc.js 처럼 두 줄에 걸리는 파일의 뒤 줄이 빠졌다)"""
    want: set[str] = set()
    for f in files:
        hit = False
        for pattern, names in AREAS:
            m = re.fullmatch(pattern, f)
            if m:
                hit = True
                want |= {m.group(1)} if names is None and m.group(1) in SUITES else set(names or [])
        if not hit and f.startswith(('web/', 'lectern/')):
            want |= set(AREA_OTHER)
    return [s for s in SUITES if s in want]


def main() -> int:
    before = close_windows.snapshot()
    try:
        return run_suites(sys.argv[1:])
    finally:
        close_windows.close_new(before)


TIMES = ROOT / 'ui-shots' / 'edges' / 'times.json'   # 지난 실행의 묶음별 시간 (동시에 돌릴 때 긴 묶음부터)


def jobs_of(args: list[str]) -> tuple[int, list[str]]:
    """-j N (-jN) 을 떼어 낸다"""
    jobs, rest, i = 1, [], 0
    while i < len(args):
        a = args[i]
        if a == '-j' and i + 1 < len(args) and args[i + 1].isdigit():
            jobs, i = int(args[i + 1]), i + 2
            continue
        if re.fullmatch(r'-j\d+', a):
            jobs = int(a[2:])
        else:
            rest.append(a)
        i += 1
    return max(1, jobs), rest


def run_suites(args: list[str]) -> int:
    jobs, args = jobs_of(args)
    changed = args == ['--changed']
    want = suites_for(changed_files()) if changed else args or SUITES
    unknown = [a for a in want if a not in SUITES]
    if unknown:   # 목록에 없는 이름은 돌지 않는다 — 말없이 '모두 통과'로 끝나지 않게
        print(f'모르는 묶음: {unknown} — tools/ui_edges.py 의 SUITES 에 더하세요', flush=True)
        return 1
    if changed:
        print('고친 파일에 닿는 묶음:', want or '없음', flush=True)
        os.environ.setdefault('LECTERN_TEST_FUZZ', 'all')   # 고친 곳을 볼 때는 무작위 시험을 넓게
    names = [n for n in SUITES if n in want]
    try:
        times = json.loads(TIMES.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        times = {}
    if jobs > 1:
        names.sort(key=lambda n: -times.get(n, 60))   # 긴 묶음부터 — 끝이 고르게
        print(f'{len(names)}묶음을 {jobs}개씩 동시에', flush=True)
        with ThreadPoolExecutor(jobs) as ex:
            first = list(ex.map(lambda n: (n, run_suite(n, quiet=True, times=times)), names))
    else:
        first = [(n, run_suite(n, times=times)) for n in names]
    try:
        TIMES.parent.mkdir(parents=True, exist_ok=True)
        TIMES.write_text(json.dumps(times, ensure_ascii=False, indent=1), encoding='utf-8')
    except OSError:
        pass
    failed, flaky = [], []
    for name, ok in first:
        if ok:
            continue
        # 실패하면 한 번 다시 돌려 '가끔 실패'를 가른다 — 통과로 치지는 않고 따로 알린다 (흔들린 점검은 고칠 것이다). 다시 돌릴 때는 하나씩
        print(f'--- {name}: 다시 돌립니다', flush=True)
        (flaky if run_suite(name) else failed).append(name)
    if flaky:
        print(f'\n흔들린 점검 (실패했다가 다시 돌리니 통과): {flaky}')
        if os.environ.get('GITHUB_ACTIONS'):
            print(f'::warning title=흔들린 화면 점검::{", ".join(flaky)}')
    print(f'\n실패한 점검: {failed}' if failed else '\n모두 통과' if not flaky else '\n두 번 모두 실패한 점검은 없음')
    return 1 if failed else FLAKY if flaky else 0


FLAKY = 3   # 종료 코드: 흔들린 점검만 있다 (실패는 1)


def run_suite(name: str, quiet: bool = False, times: dict | None = None) -> bool:
    """묶음 하나. quiet 이면 출력을 모았다가 끝날 때 한 덩어리로 (동시에 돌릴 때 섞이지 않게)"""
    if not quiet:
        print(f'\n=== {name} ===', flush=True)
    started = time.time()
    cmd = [sys.executable, str(ROOT / 'tools' / 'edges' / f'{name}.py')]
    if quiet:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace')
        code = r.returncode
        sys.stdout.write(f'\n=== {name} ===\n{r.stdout}{r.stderr}')
    else:
        code = subprocess.run(cmd, cwd=ROOT).returncode
    took = time.time() - started
    if times is not None and code == 0:
        times[name] = round(took)
    print(f'--- {name}: {"통과" if code == 0 else "실패"} ({took:.0f}초)', flush=True)
    return code == 0


if __name__ == '__main__':
    sys.exit(main())
