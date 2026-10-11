"""프로젝트 전체 본문 검색 (사이드바 '검색' 탭, GET /api/search).

트리에 보이는 문서만 찾는다 — 숨김·제외·링크는 scan 이 이미 뺐다. 대소문자를 가리지 않고 글자 그대로 찾는다.
결과는 문서별로 묶고, 긴 줄은 찾은 곳 둘레만 잘라 보낸다. 너무 많으면 자르고 truncated 를 켠다.
html 은 태그를 빼고 화면에 보이는 글자만 찾는다 (script·style 안은 찾지 않음).
줄 번호는 markdown-it 과 같게 센다 (\\r\\n·\\r·\\n 만 줄바꿈) — 화면에서 그 줄의 블록(data-lines)을 찾을 수 있도록.
"""
from __future__ import annotations

import html
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
_HTML_HIDDEN = re.compile(r'<(script|style|template|svg)\b.*?</\1\s*>|<!--.*?-->', re.IGNORECASE | re.DOTALL)
_HTML_TAG = re.compile(r'<[^>]*>')


def _keep_newlines(m: re.Match) -> str:
    return '\n' * m.group(0).count('\n') or ' '


def lines_of(text: str, kind: str | None = None) -> list[str]:
    """줄 목록. html 은 태그와 보이지 않는 부분(script·style·주석)을 지우되 그 안의 줄바꿈은 남겨 줄 번호를 지킨다."""
    text = _NEWLINE.sub('\n', text)
    if kind != 'html':
        return text.split('\n')
    text = _HTML_TAG.sub(_keep_newlines, _HTML_HIDDEN.sub(_keep_newlines, text))
    return [' '.join(html.unescape(line).split()) for line in text.split('\n')]


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
        lines = lines_of(text, f.get('kind'))
        if needle not in '\n'.join(lines).lower():   # html 은 태그를 뺀 글자로 본다 ('구리 <b>가격' → '구리 가격')
            continue
        hits = []
        more = False
        for no, line in enumerate(lines, 1):
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
