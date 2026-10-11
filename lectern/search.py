"""프로젝트 전체 본문 검색 (사이드바 '검색' 탭, GET /api/search).

트리에 보이는 문서만 찾는다 — 숨김·제외·링크는 scan 이 이미 뺐다. 대소문자를 가리지 않고 글자 그대로 찾는다.
결과는 문서별로 묶고, 긴 줄은 찾은 곳 둘레만 잘라 보낸다. 너무 많으면 자르고 truncated 를 켠다.
줄 번호는 markdown-it 과 같게 센다 (\\r\\n·\\r·\\n 만 줄바꿈) — 화면에서 그 줄의 블록(data-lines)을 찾을 수 있도록.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .docinfo import read_text
from .scanner import Node

MAX_QUERY = 200
MAX_FILES = 200
MAX_HITS_PER_FILE = 20
MAX_TOTAL = 1000
MAX_BYTES = 4 * 1024 * 1024   # 아주 큰 파일은 앞부분만
SNIPPET = 160                 # 결과 한 줄의 최대 글자 수
LEAD = 40                     # 잘라 낼 때 찾은 곳 앞에 남기는 글자 수

_NEWLINE = re.compile(r'\r\n?')


def lines_of(text: str) -> list[str]:
    return _NEWLINE.sub('\n', text).split('\n')


def snippet(line: str, at: int) -> str:
    """긴 줄은 찾은 곳(at) 둘레만 남기고 잘린 쪽에 '…'를 붙인다."""
    line = line.rstrip()
    if len(line) <= SNIPPET:
        return line.strip()
    start = max(0, at - LEAD)
    end = start + SNIPPET
    return ('…' if start else '') + line[start:end].strip() + ('…' if end < len(line) else '')


def search_docs(root: Path, files: list[Node], query: str) -> dict[str, Any]:
    needle = query.strip().lower()
    out: dict[str, Any] = {'query': query.strip(), 'results': [], 'total': 0, 'truncated': False}
    if not needle:
        return out
    results = []
    for f in files:
        try:
            text = read_text(root / f['path'], MAX_BYTES)
        except OSError:
            continue
        if needle not in text.lower():
            continue
        hits = []
        more = False
        for no, line in enumerate(lines_of(text), 1):
            at = line.lower().find(needle)
            if at < 0:
                continue
            if len(hits) >= MAX_HITS_PER_FILE:
                more = True
                break
            hits.append({'line': no, 'text': snippet(line, at)})
        named = needle in f'{f.get("title") or ""} {f["path"]}'.lower()
        results.append({'path': f['path'], 'title': f.get('title'), 'mtime': f.get('mtime', 0),
                        'hits': hits, 'more': more, 'named': named})
    # 제목·경로에 검색어가 든 문서를 먼저, 그다음 최근에 고친 문서부터
    results.sort(key=lambda r: (not r['named'], -r['mtime']))
    kept, count = [], 0
    for r in results:
        if len(kept) >= MAX_FILES or count >= MAX_TOTAL:
            out['truncated'] = True
            break
        kept.append(r)
        count += len(r['hits'])
    out['truncated'] = out['truncated'] or any(r['more'] for r in kept)
    out['results'] = kept
    out['total'] = count
    return out
