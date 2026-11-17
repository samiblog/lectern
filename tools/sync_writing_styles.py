"""글쓰기 스타일의 공통 절을 '리서치 글쓰기'에서 다른 스타일로 옮긴다 (D161).

스타일 넷(web/help/*.md — writing_styles.json 의 목록)은 '남의 글을 옮기거나 다듬을 때'·'개발자 글버릇'·'AI 글버릇'·'답할 때' 네 절이 같다.
공통 절을 고칠 때는 research-writing.md(영어판 .en.md)만 고치고 이것을 돌린다 — 다른 스타일의 그 절을 그대로 바꿔 넣는다.
  python tools/sync_writing_styles.py          바꿔 넣는다
  python tools/sync_writing_styles.py --check  같은지만 본다 (다르면 종료 코드 1 — tests/test_writing_styles.py 도 본다)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HELP = ROOT / 'web' / 'help'
SOURCE = 'research-writing'
SHARED = {
    '': ['## 남의 글을 옮기거나 다듬을 때', '## 개발자 글버릇을 쓰지 않는다', '## AI 글버릇을 쓰지 않는다', '## 답할 때'],
    '.en': ["## When you carry over or edit someone else's writing", '## Do not write like a developer', '## Do not write like an AI', '## When answering'],
}


def styles() -> list[str]:
    return [s['file'] for s in json.loads((HELP / 'writing-styles.json').read_text(encoding='utf-8'))['styles']]


def sections(text: str) -> dict[str, str]:
    """'## 제목' 줄마다 그 절(제목 줄부터 다음 '## ' 앞까지, 끝의 빈 줄 빼고)"""
    out: dict[str, str] = {}
    lines = text.split('\n')
    starts = [i for i, line in enumerate(lines) if line.startswith('## ')]
    for n, i in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        out[lines[i]] = '\n'.join(lines[i:end]).rstrip('\n')
    return out


def synced(text: str, source: str, heads: list[str]) -> str:
    """text 의 공통 절을 source 의 것으로 바꾼다. text 에 그 제목이 없으면 ValueError"""
    src = sections(source)
    mine = sections(text)
    for head in heads:
        if head not in mine:
            raise ValueError(f'공통 절이 없습니다: {head}')
        text = text.replace(mine[head], src[head], 1)
    return text


def main(check: bool) -> int:
    bad = []
    for lang, heads in SHARED.items():
        source = (HELP / f'{SOURCE}{lang}.md').read_text(encoding='utf-8')
        for name in styles():
            if name == SOURCE:
                continue
            path = HELP / f'{name}{lang}.md'
            text = path.read_text(encoding='utf-8')
            new = synced(text, source, heads)
            if new != text:
                bad.append(path.name)
                if not check:
                    path.write_text(new, encoding='utf-8', newline='\n')
    if bad:
        print(('공통 절이 리서치 글쓰기와 다릅니다: ' if check else '바꿔 넣었습니다: ') + ', '.join(bad))   # i18n-ok (개발 도구)
    return 1 if bad and check else 0


if __name__ == '__main__':
    sys.exit(main('--check' in sys.argv))
