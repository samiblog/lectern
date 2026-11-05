"""가장자리 점검: ui_smoke 에 없는 동작 — 문서에 적은 조합·실패 길·경쟁 상태·줄 구조 편집을 실제 키로 본다.

tools/edges/ 의 점검마다 임시 프로젝트·설정으로 서버를 따로 띄워 돌린다. 준비는 ui_smoke 와 같다 (playwright).

    python tools/ui_edges.py              :: 모두
    python tools/ui_edges.py structure    :: 이름이 맞는 것만
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITES = ['reading', 'frames', 'lines', 'combos', 'structure', 'data', 'data_wide']


def main() -> int:
    want = sys.argv[1:] or SUITES
    failed = []
    for name in SUITES:
        if name not in want:
            continue
        print(f'\n=== {name} ===', flush=True)
        started = time.time()
        code = subprocess.run([sys.executable, str(ROOT / 'tools' / 'edges' / f'{name}.py')], cwd=ROOT).returncode
        print(f'--- {name}: {"통과" if code == 0 else "실패"} ({time.time() - started:.0f}초)', flush=True)
        if code:
            failed.append(name)
    print(f'\n실패한 점검: {failed}' if failed else '\n모두 통과')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
