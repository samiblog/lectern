"""문서 속 형광펜과 할 일 (D143) — 사이드바 '문서'의 하위 묶음 '형광펜'·'할 일'이 쓴다 (GET /api/marks).

문서 본문을 읽어 줄마다 찾는다. 읽기만 한다 — 지우는 것은 화면(lineedit.js)이 사용자가 고를 때 저장 길로 한다.
- 형광펜: `<mark>글</mark>`·`<mark class="green|pink|blue">글</mark>` (D141 — 이름 있는 색만). 한 줄에 여럿.
- 할 일: 끝내지 않은 `- [ ] 글` (인용·들여쓰기 안도). 끝낸 것은 세지 않는다.
- 코드 블록(``` ~~~) 안과 문장 속 코드(`…`) 안은 보지 않는다.
"""
from __future__ import annotations

import re
from typing import Any

MAX_PER_DOC = 300   # 문서 하나에서 싣는 수 — 넘으면 거기서 멈추고 more 를 단다
MARKS_READ = 2_000_000   # 문서마다 읽는 글자 수 (아주 큰 문서의 뒤는 보지 않는다)
TEXT_LEN = 80       # 싣는 글의 길이

_FENCE = re.compile(r'^\s{0,3}(?:>\s?)*\s{0,3}(`{3,}|~{3,})')
_MARK = re.compile(r'<mark(?: class="(green|pink|blue)")?>(.*?)</mark>')
_TASK = re.compile(r'^\s*(?:>\s?)*\s*[-*+]\s+\[ \]\s+(.*)$')
_CODE = re.compile(r'`[^`\n]*`')
_TAGS = re.compile(r'<[^>]+>')
_EMPH = re.compile(r'(\*\*|__|~~|\*|`)')


def _plain(text: str) -> str:
    """보이는 글에 가깝게 — 태그와 서식 표시를 걷고 줄인다"""
    s = _EMPH.sub('', _TAGS.sub('', text)).strip()
    return s if len(s) <= TEXT_LEN else s[:TEXT_LEN - 1] + '…'


def marks_of(text: str) -> dict[str, Any]:
    """문서 글 → {marks: [{line, color, text}], tasks: [{line, text}], more: bool}. 줄 번호는 1부터, color 는 '' 가 노랑"""
    marks: list[dict[str, Any]] = []
    tasks: list[dict[str, Any]] = []
    fence = ''
    more = False
    for n, line in enumerate(text.replace('\r\n', '\n').split('\n'), 1):
        m = _FENCE.match(line)
        if m:
            mark = m.group(1)
            if not fence:
                fence = mark[0] * len(mark)
                continue
            if mark[0] == fence[0] and len(mark) >= len(fence):
                fence = ''
                continue
        if fence:
            continue
        if len(marks) + len(tasks) >= MAX_PER_DOC:
            more = True
            break
        bare = _CODE.sub(lambda c: ' ' * len(c.group(0)), line)   # 문장 속 코드는 같은 길이의 빈칸으로 — 자리는 그대로
        for mk in _MARK.finditer(bare):
            inner = line[mk.start(2):mk.end(2)]
            marks.append({'line': n, 'color': mk.group(1) or '', 'text': _plain(inner)})
        t = _TASK.match(line)
        if t:
            tasks.append({'line': n, 'text': _plain(t.group(1))})
    return {'marks': marks, 'tasks': tasks, 'more': more}
