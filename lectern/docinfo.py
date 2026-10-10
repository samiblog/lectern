"""문서 제목·요약 추출 (트리 제목 표시와 폴더 개요 화면용).

파일 앞부분(16KB)만 읽고, (수정 시각, 크기)가 같으면 캐시를 쓴다.
- 제목: frontmatter의 title/name → 첫 번째 H1 → 첫 번째 제목(H2~H6)
- 요약: frontmatter의 description/summary → 본문 첫 문단 (마크다운 기호 제거, 160자)
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

HEAD_BYTES = 16 * 1024
SUMMARY_LEN = 160

_CACHE: dict[str, tuple[tuple[int, int], dict[str, Any]]] = {}

_RE_HEADING = re.compile(r'^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$')
_RE_FENCE = re.compile(r'^\s{0,3}(```|~~~)')
_RE_FM_KEY = re.compile(r'^(title|name|description|summary)\s*:\s*(.+?)\s*$', re.IGNORECASE)
_RE_QUOTE = re.compile(r'^(?:>\s?)+')
_RE_LIST = re.compile(r'^(?:[-*+]\s+(?:\[[ xX]\]\s+)?|\d+[.)]\s+)')
_SKIP_PREFIXES = ('|', '<', '---', '***', '___', '===', '![', '[^', '$$')
_RE_META_LINE = re.compile(r'^[\w가-힣 ./()-]{1,16}\s*[:：]\s*\S.{0,60}$')

_RE_IMG = re.compile(r'!\[([^\]]*)\]\([^)]*\)')
_RE_LINK = re.compile(r'\[([^\]]+)\]\([^)]*\)')
_RE_REF = re.compile(r'\[([^\]]+)\]\[[^\]]*\]')
_RE_CODE = re.compile(r'`+([^`]*)`+')
_RE_TAG = re.compile(r'<[^>]+>')
_RE_EMPHS = (
    re.compile(r'\*\*(.+?)\*\*'),
    re.compile(r'__(.+?)__'),
    re.compile(r'~~(.+?)~~'),
    re.compile(r'(?<![\w*])\*(?=\S)(.+?)(?<=\S)\*(?![\w*])'),
    re.compile(r'(?<!\w)_(?=\S)(.+?)(?<=\S)_(?!\w)'),
)


def read_text(path: Path, limit: int | None = None) -> str:
    """UTF-8(BOM 허용)로 읽는다. Claude가 만드는 문서는 UTF-8이다."""
    with open(path, 'rb') as f:
        raw = f.read(limit) if limit else f.read()
    return raw.decode('utf-8-sig', errors='replace')


def strip_inline(text: str) -> str:
    text = _RE_IMG.sub(r'\1', text)
    text = _RE_LINK.sub(r'\1', text)
    text = _RE_REF.sub(r'\1', text)
    text = _RE_CODE.sub(r'\1', text)
    text = _RE_TAG.sub('', text)
    for pattern in _RE_EMPHS:
        text = pattern.sub(r'\1', text)
    return re.sub(r'\s+', ' ', text).strip()


def split_front_matter(text: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != '---':
        return {}, text
    for i in range(1, min(len(lines), 300)):
        if lines[i].strip() in ('---', '...'):
            meta: dict[str, str] = {}
            for line in lines[1:i]:
                m = _RE_FM_KEY.match(line)
                if m and m.group(1).lower() not in meta:
                    value = m.group(2).strip().strip('"\'')
                    if value not in ('|', '>', '|-', '>-'):
                        meta[m.group(1).lower()] = value
            return meta, '\n'.join(lines[i + 1:])
    return {}, text


def _truncate(text: str, limit: int = SUMMARY_LEN) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + '…'


def extract_info(text: str) -> dict[str, Any]:
    meta, body = split_front_matter(text)
    title = meta.get('title') or meta.get('name') or None
    summary = meta.get('description') or meta.get('summary') or ''
    first_heading = None
    para: list[str] = []
    in_fence = False

    meta_fallback = ''

    def flush() -> None:
        nonlocal summary, para, meta_fallback
        lines = [p for p in para if p]
        para = []
        if not lines or summary:
            return
        # '작성일: 2026-10-09' 같은 메타데이터 줄만 있는 문단은 다른 문단이 없을 때만 쓴다
        if all(_RE_META_LINE.match(p) for p in lines):
            meta_fallback = meta_fallback or ' '.join(lines)
        else:
            summary = ' '.join(lines)

    for line in body.splitlines():
        if _RE_FENCE.match(line):
            in_fence = not in_fence
            flush()
            continue
        if in_fence:
            continue
        heading = _RE_HEADING.match(line)
        if heading:
            text_ = strip_inline(heading.group(2))
            if title is None and heading.group(1) == '#' and text_:
                title = text_
            if first_heading is None and text_:
                first_heading = text_
            flush()
        else:
            stripped = line.strip()
            if not stripped or stripped.startswith(_SKIP_PREFIXES):
                flush()
            elif not summary:
                cleaned = _RE_LIST.sub('', _RE_QUOTE.sub('', stripped))
                para.append(strip_inline(cleaned))
        if title and summary:
            break
    flush()
    summary = summary or meta_fallback
    return {
        'title': title or first_heading,
        'summary': _truncate(summary) if summary else '',
    }


def doc_info(path: Path, st: Any = None) -> dict[str, Any]:
    """파일의 제목·요약. 읽을 수 없으면 빈 값."""
    empty = {'title': None, 'summary': ''}
    try:
        st = st or path.stat()
    except OSError:
        return empty
    key = str(path)
    sig = (st.st_mtime_ns, st.st_size)
    hit = _CACHE.get(key)
    if hit and hit[0] == sig:
        return hit[1]
    try:
        info = extract_info(read_text(path, HEAD_BYTES))
    except OSError:
        return empty
    _CACHE[key] = (sig, info)
    return info
