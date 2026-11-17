"""글쓰기 스타일의 견본과 가린 비교 (D161 — 스타일을 고치면 다시 돌린다).

스타일마다 그 스타일에 맞는 과제 하나를 예제 프로젝트(samples)의 사본에서 실제 Claude Code(claude -p)에 두 번 시킨다 — 스타일 없이(Claude 기본)와
그 스타일로. 그 둘을 어느 쪽인지 가린 채 다른 Claude 에게 편집장 기준으로 순서를 바꿔 두 번 매기게 한다 (D132 의 방법).
--apply 면 두 글의 앞부분을 web/help/writing-styles.json 의 sample 에 넣는다 (고르기 창의 견본). 쓰기 도구는 막고, 이 PC 의 설정은 고치지 않는다
— 스타일은 사본 프로젝트의 .claude 안에만 둔다.
  python tools/make_style_samples.py --out <결과 폴더> [--apply] [스타일 id…]
"""
from __future__ import annotations

import json
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HELP = ROOT / 'web' / 'help'
META = HELP / 'writing-styles.json'
CLAUDE = shutil.which('claude') or 'claude'

TASKS = {   # i18n-ok (Claude 에게 시키는 한국어 과제)
    'research': '구매팀장에게 보낼 3분기 구리 구매 시점 검토 메모를 A4 한 쪽 분량으로 써 줘.',
    'brief': '팀장 결재를 받을 3분기 구리 구매 계획을 한 장 보고로 써 줘.',
    'academic': "이 폴더의 월별 가격 자료로 구리 값의 흐름을 분석한 연구 보고서의 '결과와 논의' 절을 A4 한 쪽으로 써 줘.",
    'plain': "구매팀에 새로 온 사원이 읽을 '구리 값은 어떻게 정해지고 우리는 언제 사나' 안내를 한두 화면으로 써 줘.",
}
SUFFIX = ' 개요 확인 없이 바로 쓰고, 파일로 만들지 말고 답에 글만 써 줘.'   # i18n-ok
GENRE = {   # i18n-ok (편집장 기준의 마지막 칸)
    'research': '보고서 메모다움 (결론 먼저, 근거, 읽는 사람이 내릴 결정)',
    'brief': '결재용 한 장 보고다움 (개조식, 맨 위의 결론과 할 일, 누가·언제까지, 한 쪽)',
    'academic': '학술 글다움 (주장의 세기가 근거에 맞음, 한계, 인용·숫자의 엄밀함)',
    'plain': '처음 읽는 사람이 따라 할 수 있음 (쉬운 말, 차례, 예)',
}
READ_ONLY = ['--permission-mode', 'default', '--disallowedTools', 'Edit', 'Write', 'NotebookEdit', 'Bash']


def run(cwd: Path, prompt: str) -> str:
    r = subprocess.run([CLAUDE, '-p', '--output-format', 'json', *READ_ONLY], input=prompt, cwd=cwd,
                       capture_output=True, text=True, encoding='utf-8', timeout=1200)
    try:
        return json.loads(r.stdout).get('result') or ''
    except ValueError:
        return r.stdout


def write_with_style(cwd: Path, style: dict | None) -> None:
    """사본 프로젝트에 스타일을 켠다 — 이 PC 에 설치된 같은 이름의 스타일과 섞이지 않게 이름 끝에 ' 시험'"""
    if style is None:
        return
    text = (HELP / f"{style['file']}.md").read_text(encoding='utf-8')
    name = re.search(r'^name: (.+)$', text, re.M).group(1).strip() + ' 시험'   # i18n-ok
    text = re.sub(r'^name: .+$', f'name: {name}', text, count=1, flags=re.M)
    (cwd / '.claude' / 'output-styles').mkdir(parents=True, exist_ok=True)
    (cwd / '.claude' / 'output-styles' / f"{style['file']}.md").write_text(text, encoding='utf-8')
    (cwd / '.claude' / 'settings.local.json').write_text(json.dumps({'outputStyle': name}, ensure_ascii=False), encoding='utf-8')


def project(style: dict | None) -> Path:
    cwd = Path(tempfile.mkdtemp(prefix='lec-style-')) / 'samples'
    # 예제의 CLAUDE.md 는 뺀다 — 그 '글' 절이 스타일의 요약이라, 두면 'Claude 기본'도 스타일의 일부를 받고 쓴다 (보통 폴더의 차이를 보이려고)
    shutil.copytree(ROOT / 'samples', cwd, ignore=shutil.ignore_patterns('slides', 'guide', '*.html', 'CLAUDE*.md'))
    write_with_style(cwd, style)
    return cwd


def judge(task: str, genre: str, a: str, b: str) -> dict:
    prompt = (f"아래는 같은 요청에 대한 두 글 A·B 다. 요청: «{task}»\n\n"   # i18n-ok
              f"이 글을 받는 쪽의 편집장이 되어 두 글을 견줘라. 기준마다 1~5점: 읽는 사람에 맞음, 결론·요점의 자리, 근거와 숫자의 쓰임, 흐름과 짜임, "
              f"정직(사실·추정 구분, 지어낸 것 없음), {genre}. 더 나은 글을 하나 골라라. "
              f'JSON 한 줄로만 답하라: {{"A": 합계, "B": 합계, "better": "A" 또는 "B", "why": "한 문장"}}\n\n'
              f"=== A ===\n{a}\n\n=== B ===\n{b}\n")
    out = run(Path(tempfile.mkdtemp(prefix='lec-judge-')), prompt)
    m = re.search(r'\{.*\}', out, re.S)
    try:
        return json.loads(m.group(0)) if m else {'raw': out[-400:]}
    except ValueError:
        return {'raw': out[-400:]}


def excerpt(text: str, limit: int = 700) -> str:
    """앞부분 — 줄 단위로 limit 자 안팎. 글 전체를 코드 울타리(```markdown)로 감싸 답했으면 울타리를 뗀다"""
    lines = text.strip().split('\n')
    if lines and lines[0].startswith('```'):
        lines = lines[1:]
        if '```' in lines:
            lines = lines[:lines.index('```')]
    out, size = [], 0
    for line in lines:
        if size + len(line) > limit and out:
            break
        out.append(line)
        size += len(line) + 1
    return '\n'.join(out).strip()


def apply_from(out_dir: Path) -> None:
    """먼저 돌린 결과(<out>/<id>.json)로 견본만 넣는다 — 다시 시키지 않고"""
    meta = json.loads(META.read_text(encoding='utf-8'))
    for style in meta['styles']:
        got = out_dir / f"{style['id']}.json"
        if got.is_file():
            r = json.loads(got.read_text(encoding='utf-8'))
            style['sample'] = {'request': r['task'], 'default': excerpt(r['default']), 'style': excerpt(r['style'])}
    META.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def main() -> None:
    args = sys.argv[1:]
    if '--apply-from' in args:
        apply_from(Path(args[args.index('--apply-from') + 1]))
        return
    out_dir = Path(args[args.index('--out') + 1])
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = json.loads(META.read_text(encoding='utf-8'))
    want = [a for a in args if a in TASKS] or list(TASKS)
    report = {}
    for style in meta['styles']:
        sid = style['id']
        if sid not in want:
            continue
        task = TASKS[sid]
        t0 = time.time()
        base = run(project(None), task + SUFFIX)
        mine = run(project(style), task + SUFFIX)
        votes = []
        for flip in (False, True):
            a, b = (mine, base) if flip else (base, mine)
            got = judge(task, GENRE[sid], a, b)
            better = got.get('better')
            votes.append({'style_wins': better == ('A' if flip else 'B'), 'style': got.get('A' if flip else 'B'), 'default': got.get('B' if flip else 'A'), 'why': got.get('why'), 'raw': got.get('raw')})
        report[sid] = {'task': task, 'default': base, 'style': mine, 'votes': votes, 'secs': round(time.time() - t0)}
        (out_dir / f'{sid}.json').write_text(json.dumps(report[sid], ensure_ascii=False, indent=1), encoding='utf-8')
        print(sid, [v['style_wins'] for v in votes], [(v['default'], v['style']) for v in votes], f"{report[sid]['secs']}s", flush=True)
        if '--apply' in args:
            style['sample'] = {'request': task, 'default': excerpt(base), 'style': excerpt(mine)}
    if '--apply' in args:
        META.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    random.seed(0)
    main()
