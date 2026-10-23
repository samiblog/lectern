"""프로젝트 전체 본문 검색 (사이드바 '검색' 탭, GET /api/search).

트리에 보이는 문서와, 고르면 코드 파일(사이드바 '코드' 목록의 것 — scanner.is_code, D44)을 찾는다 — 숨김·제외·링크는 scan 이
이미 뺐다. 대소문자를 가리지 않고 글자 그대로 찾는다. 결과는 문서 먼저, 그다음 코드 (묶음마다 파일 수·찾은 곳 수 한도).
결과는 문서별로 묶고, 긴 줄은 찾은 곳 둘레만 잘라 보낸다. 너무 많으면 자르고 truncated 를 켠다.
html 은 태그를 빼고 화면에 보이는 글자만 찾는다 (script·style 안은 찾지 않음).
줄 번호는 markdown-it 과 같게 센다 (\\r\\n·\\r·\\n 만 줄바꿈) — 화면에서 그 줄의 블록(data-lines)을 찾을 수 있도록.
"""
from __future__ import annotations

import html
import re
import threading
from pathlib import Path
from typing import Any

from .docinfo import read_text
from .scanner import Node

MAX_QUERY = 200
MAX_FILES = 200
MAX_HITS_PER_FILE = 20
MAX_TOTAL = 1000
MAX_BYTES = 4 * 1024 * 1024   # 아주 큰 파일은 앞부분만
MAX_CODE_BYTES = 2 * 1024 * 1024   # 이보다 큰 코드 파일(잠금 파일·노트북 등)은 찾지 않는다
CACHE_CHARS = 64 * 1024 * 1024     # 읽은 글을 기억해 두는 한도 (글자 수)
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


class TextCache:
    """읽은 파일의 글을 (수정 시각, 크기)와 함께 기억한다 — 코드가 수천 개여도 검색어마다 디스크를 다 읽지 않게.
    바뀐 파일은 다시 읽는다. CACHE_CHARS 를 넘으면 더 기억하지 않는다 (읽기만 한다)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._texts: dict[Path, tuple[int, int, str]] = {}
        self._chars = 0

    def read(self, path: Path, limit: int) -> str:
        st = path.stat()
        key = (st.st_mtime_ns, st.st_size)
        with self._lock:
            hit = self._texts.get(path)
        if hit and hit[:2] == key:
            return hit[2]
        text = read_text(path, limit)
        with self._lock:
            old = self._texts.pop(path, None)
            if old:
                self._chars -= len(old[2])
            if self._chars + len(text) <= CACHE_CHARS:
                self._texts[path] = (*key, text)
                self._chars += len(text)
        return text


def _read(path: Path, limit: int, cache: TextCache | None) -> str:
    return cache.read(path, limit) if cache else read_text(path, limit)


def _matches(root: Path, files: list[Node], needle: str, kind: str, cache: TextCache | None) -> list[dict[str, Any]]:
    """files 중 needle 이 든 것. kind: doc(문서 — html 은 보이는 글자만) | code (글자 그대로)"""
    results = []
    for f in files:
        try:
            if kind == 'code' and (root / f['path']).stat().st_size > MAX_CODE_BYTES:
                continue
            text = _read(root / f['path'], MAX_BYTES, cache)
        except OSError:
            continue
        lines = lines_of(text, f.get('kind') if kind == 'doc' else None)
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
        results.append({'path': f['path'], 'title': f.get('title') if kind == 'doc' else None, 'mtime': f.get('mtime', 0),
                        'hits': hits, 'more': more, 'named': named, 'kind': kind})
    # 제목·경로에 검색어가 든 파일을 먼저, 그다음 최근에 고친 파일부터
    results.sort(key=lambda r: (not r['named'], -r['mtime']))
    return results


def search(root: Path, docs: list[Node], code: list[Node], query: str, cache: TextCache | None = None) -> dict[str, Any]:
    """문서(docs)와 코드(code)에서 찾는다. 결과는 문서 먼저. 묶음마다 MAX_FILES 파일·MAX_TOTAL 곳까지 (넘으면 truncated).
    docs·code: 찾을 파일 노드 (scanner 의 트리에서). 고르지 않은 묶음은 빈 목록으로 준다."""
    needle = query.strip().lower()
    out: dict[str, Any] = {'query': query.strip(), 'results': [], 'total': 0, 'truncated': False, 'docs': 0, 'code': 0}
    if not needle:
        return out
    for kind, files in (('doc', docs), ('code', code)):
        kept, count = [], 0
        for r in _matches(root, files, needle, kind, cache):
            if len(kept) >= MAX_FILES or count >= MAX_TOTAL:
                out['truncated'] = True
                break
            kept.append(r)
            count += len(r['hits'])
        out['truncated'] = out['truncated'] or any(r['more'] for r in kept)
        out['results'] += kept
        out['total'] += count
        out['docs' if kind == 'doc' else 'code'] = len(kept)
    return out


def search_docs(root: Path, files: list[Node], query: str, cache: TextCache | None = None) -> dict[str, Any]:
    """문서만 찾는다"""
    return search(root, files, [], query, cache)
