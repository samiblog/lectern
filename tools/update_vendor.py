"""web/vendor 의 JS 라이브러리를 npm에서 받아 갱신한다.

인터넷이 되는 PC에서 실행한다 (Node.js / npm 필요).
만들어진 web/vendor 폴더를 그대로 사내 PC 프로젝트에 복사하면 된다.

사용법
    python tools/update_vendor.py            # PACKAGES에 고정된 버전으로 받기
    python tools/update_vendor.py --latest   # 최신 버전으로 받기 (화면 확인 후 PACKAGES 갱신)

받은 버전은 web/vendor/VERSIONS.json 에 기록된다.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / 'web' / 'vendor'

# 검증된 버전 (2026-10 기준). 올릴 때는 docs/TESTING.md 의 화면 점검을 다시 한다.
PACKAGES: dict[str, str] = {
    'markdown-it': '15.0.2',
    'markdown-it-anchor': '10.0.0',
    'markdown-it-footnote': '4.0.0',
    'markdown-it-task-lists': '2.1.1',
    'katex': '0.19.0',
    '@highlightjs/cdn-assets': '11.12.0',
    'mermaid': '12.1.0',
    'dompurify': '3.4.16',
    '@xterm/xterm': '5.5.0',            # 오른쪽 터미널 (D38) — 처음 열 때 terminal.js 가 불러온다
    '@xterm/addon-fit': '0.10.0',
    '@xterm/addon-unicode11': '0.8.0',  # 한글처럼 두 칸을 차지하는 글자의 폭
    'codemirror': '5.65.21',            # 편집 모드 (D54) — 처음 편집할 때 editor.js 가 불러온다. 6 은 묶는 도구가 있어야 해서 5
}

# 편집 모드의 언어 (codemirror/mode/<이름>.js). 편집기가 확장자에 맞는 것과 그것이 쓰는 것만 불러온다 (editor.js 의 MODES)
CODEMIRROR_MODES = ['markdown', 'xml', 'htmlmixed', 'javascript', 'css', 'python', 'yaml', 'toml', 'properties', 'shell',
                    'powershell', 'clike', 'go', 'rust', 'ruby', 'php', 'sql', 'r', 'lua', 'swift', 'perl', 'dart', 'groovy']

# (패키지, 패키지 안 원본 경로, vendor 안 대상 경로). 원본이 폴더면 woff2 글꼴만 복사한다.
FILES: list[tuple[str, str, str]] = [
    ('markdown-it', 'dist/browser/markdown-it.umd.min.js', 'markdown-it/markdown-it.min.js'),
    ('markdown-it-anchor', 'dist/markdownItAnchor.umd.js', 'markdown-it/markdown-it-anchor.min.js'),
    ('markdown-it-footnote', 'dist/markdown-it-footnote.min.js', 'markdown-it/markdown-it-footnote.min.js'),
    ('markdown-it-task-lists', 'dist/markdown-it-task-lists.min.js', 'markdown-it/markdown-it-task-lists.min.js'),
    ('katex', 'dist/katex.min.js', 'katex/katex.min.js'),
    ('katex', 'dist/katex.min.css', 'katex/katex.min.css'),
    ('katex', 'dist/fonts', 'katex/fonts'),
    ('@highlightjs/cdn-assets', 'highlight.min.js', 'highlight/highlight.min.js'),
    ('@highlightjs/cdn-assets', 'languages/powershell.min.js', 'highlight/languages/powershell.min.js'),
    ('@highlightjs/cdn-assets', 'languages/dos.min.js', 'highlight/languages/dos.min.js'),
    ('@highlightjs/cdn-assets', 'languages/dockerfile.min.js', 'highlight/languages/dockerfile.min.js'),
    ('@highlightjs/cdn-assets', 'styles/github.min.css', 'highlight/github.min.css'),
    ('@highlightjs/cdn-assets', 'styles/github-dark.min.css', 'highlight/github-dark.min.css'),
    ('mermaid', 'dist/mermaid.min.js', 'mermaid/mermaid.min.js'),
    ('dompurify', 'dist/purify.min.js', 'dompurify/purify.min.js'),
    ('@xterm/xterm', 'lib/xterm.js', 'xterm/xterm.js'),
    ('@xterm/xterm', 'css/xterm.css', 'xterm/xterm.css'),
    ('@xterm/addon-fit', 'lib/addon-fit.js', 'xterm/addon-fit.js'),
    ('@xterm/addon-unicode11', 'lib/addon-unicode11.js', 'xterm/addon-unicode11.js'),
    ('codemirror', 'lib/codemirror.js', 'codemirror/codemirror.js'),
    ('codemirror', 'lib/codemirror.css', 'codemirror/codemirror.css'),
    ('codemirror', 'addon/dialog/dialog.js', 'codemirror/addon/dialog.js'),
    ('codemirror', 'addon/dialog/dialog.css', 'codemirror/addon/dialog.css'),
    ('codemirror', 'addon/search/searchcursor.js', 'codemirror/addon/searchcursor.js'),
    ('codemirror', 'addon/search/search.js', 'codemirror/addon/search.js'),
    ('codemirror', 'addon/search/jump-to-line.js', 'codemirror/addon/jump-to-line.js'),
    ('codemirror', 'addon/edit/matchbrackets.js', 'codemirror/addon/matchbrackets.js'),
    ('codemirror', 'addon/selection/active-line.js', 'codemirror/addon/active-line.js'),
    ('codemirror', 'addon/mode/simple.js', 'codemirror/addon/simple.js'),   # rust 모드가 쓴다
    *(('codemirror', f'mode/{m}/{m}.js', f'codemirror/mode/{m}.js') for m in CODEMIRROR_MODES),
]

LICENSE_NAMES = ('LICENSE', 'LICENSE.md', 'LICENSE.txt', 'license', 'UNLICENSE')


def npm_install(workdir: Path, specs: list[str]) -> None:
    npm = shutil.which('npm')
    if not npm:
        sys.exit('npm을 찾을 수 없습니다. Node.js를 설치한 PC에서 실행하세요.')
    cmd = [npm, 'install', '--no-audit', '--no-fund', '--ignore-scripts', *specs]
    # Windows의 npm은 npm.cmd 이므로 셸을 거쳐 실행한다
    subprocess.run(cmd, cwd=workdir, check=True, shell=(os.name == 'nt'))


def copy_item(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        dest.mkdir(parents=True, exist_ok=True)
        for font in src.glob('*.woff2'):
            shutil.copy2(font, dest / font.name)
    else:
        shutil.copy2(src, dest)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--latest', action='store_true', help='고정 버전 대신 최신 버전 설치')
    args = parser.parse_args()

    specs = [name if args.latest else f'{name}@{ver}' for name, ver in PACKAGES.items()]
    with tempfile.TemporaryDirectory(prefix='lectern-vendor-') as tmp:
        work = Path(tmp)
        (work / 'package.json').write_text('{"name":"vendor-fetch","private":true}', encoding='utf-8')
        npm_install(work, specs)
        modules = work / 'node_modules'

        if VENDOR.exists():
            shutil.rmtree(VENDOR)
        VENDOR.mkdir(parents=True)

        for pkg, src_rel, dest_rel in FILES:
            src = modules / pkg / src_rel
            if not src.exists():
                sys.exit(f'원본 파일이 없습니다: {pkg}/{src_rel} (라이브러리 구조가 바뀌었을 수 있음)')
            copy_item(src, VENDOR / dest_rel)

        versions = {}
        for pkg in PACKAGES:
            meta = json.loads((modules / pkg / 'package.json').read_text(encoding='utf-8'))
            versions[pkg] = meta['version']
            for name in LICENSE_NAMES:
                lic = modules / pkg / name
                if lic.is_file():
                    lic_dir = VENDOR / 'licenses'
                    lic_dir.mkdir(exist_ok=True)
                    shutil.copy2(lic, lic_dir / f"{pkg.replace('/', '__')}.txt")
                    break

    (VENDOR / 'VERSIONS.json').write_text(json.dumps(versions, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print('web/vendor 갱신 완료:')
    for pkg, ver in versions.items():
        print(f'  {pkg} {ver}')


if __name__ == '__main__':
    main()
