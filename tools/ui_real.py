"""실제 창(WebView2) 시험을 차례로 돌린다 — tools/real/real*.py (판마다 하나씩 더해 온 것, 2026-11-20 저장소로).

    python tools/ui_real.py --exe dist\\Lectern\\Lectern.exe     빌드본으로 모두
    python tools/ui_real.py --exe "%LOCALAPPDATA%\\Programs\\Lectern\\Lectern.exe" real097   설치본으로 그 시험만
    python tools/ui_real.py                                       소스의 app.py 로 (창 pid 를 다루는 것은 빌드본으로)

창을 띄워 앞에 두는 시험이 있다 (실제 키 SendInput 은 맨 앞 창이 시험 창일 때만 보낸다) — 도는 동안 컴퓨터를 쓰면 흔들릴 수 있다.
실패한 시험은 한 번 다시 돌려 '흔들린 시험'으로 따로 알린다. 시험마다의 출력은 ui-shots/real/<이름>.log
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT / 'tools' / 'real'
LOGS = ROOT / 'ui-shots' / 'real'
LIMIT = 900   # 시험 하나의 한도 (초)


def run(name: str, exe: str | None) -> tuple[bool, str, float]:
    cmd = [sys.executable, str(REAL / f'{name}.py')] + (['--exe', exe] if exe else [])
    start = time.monotonic()
    try:
        out = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace',
                             timeout=LIMIT, env=os.environ | {'PYTHONIOENCODING': 'utf-8'}).stdout   # 예외의 자취(stderr)도 기록에
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or '') if isinstance(e.stdout, str) else ''
        out += f'\n{LIMIT}초 안에 끝나지 않았다'
    took = time.monotonic() - start
    LOGS.mkdir(parents=True, exist_ok=True)
    (LOGS / f'{name}.log').write_text(out, encoding='utf-8')
    m = re.search(r'(\d+)개 중 실패 (\d+)개(.*)$', out.strip().splitlines()[-1] if out.strip() else '')
    ok = bool(m) and m[2] == '0'
    return ok, (f'{m[1]}개 중 실패 {m[2]}개{m[3]}' if m else out.strip().splitlines()[-1][:200] if out.strip() else '출력 없음'), took


def main() -> int:
    args = sys.argv[1:]
    exe = None
    if '--exe' in args:
        i = args.index('--exe')
        exe = str(Path(args[i + 1]).resolve())
        del args[i:i + 2]
        if not Path(exe).is_file():
            print(f'실행 파일이 없습니다: {exe}')
            return 2
    names = args or sorted(p.stem for p in REAL.glob('real*.py') if re.fullmatch(r'real\d+\w*', p.stem))   # 도우미 realwin 은 빼고
    print(f"실제 창 시험 {len(names)}개 — {exe or '소스의 app.py'}", flush=True)
    failed, shaky = [], []
    for name in names:
        ok, line, took = run(name, exe)
        if not ok:
            again, line2, took2 = run(name, exe)
            if again:
                shaky.append(name)
                line, took = f'{line} → 다시 돌려 통과', took + took2
            else:
                failed.append(name)
                line = line2
        print(f"  {'ok  ' if ok or name in shaky else 'FAIL'} {name} — {line} ({took:.0f}초)", flush=True)
    if shaky:
        print(f'흔들린 시험 (다시 돌려 통과): {shaky}')
    print('모두 통과' if not failed else f'실패한 시험: {failed} — ui-shots/real/<이름>.log')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
