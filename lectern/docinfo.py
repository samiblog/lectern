"""문서 제목·요약 추출 (트리 제목 표시와 폴더 개요 화면용).

파일 앞부분(16KB)만 읽고, (수정 시각, 크기)가 같으면 캐시를 쓴다.
- 제목: frontmatter의 title/name → 첫 번째 H1 → 첫 번째 제목(H2~H6)
- 요약: frontmatter의 description/summary → 본문 첫 문단 (마크다운 기호 제거, 160자)
- html: 제목은 <title> → 첫 <h1> → 첫 제목, 요약은 <meta name="description"> → 첫 <p> (앞 64KB)
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

HEAD_BYTES = 16 * 1024
HTML_HEAD_BYTES = 64 * 1024   # html 은 앞에 큰 <style> 이 오기도 한다
SUMMARY_LEN = 160

_CACHE: dict[str, tuple[tuple[int, int], dict[str, Any]]] = {}

# 제목 줄. 끝의 닫는 # 는 _heading_text 가 뗀다 — 정규식으로 떼면(\s*#*\s*$) 공백이 많은 줄에서 시간이 제곱 이상으로 늘어
# 스캔 전체가 멈춘다 (점검에서 발견: 공백 1600개에 4초)
_RE_HEADING = re.compile(r'^\s{0,3}(#{1,6})(?:[ \t]+(.*))?$')
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


def _heading_text(rest: str) -> str:
    """제목 줄의 글자. 끝의 닫는 #(앞에 공백이 있을 때만 — 'C#' 은 그대로)과 공백을 뗀다."""
    text = rest.strip()
    bare = text.rstrip('#')
    if bare != text and (not bare or bare[-1] in ' \t'):
        text = bare.rstrip()
    return text


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
            text_ = strip_inline(_heading_text(heading.group(2) or ''))
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


class _HtmlInfo(HTMLParser):
    """<title>, 첫 h1·제목·p 의 글자와 meta description 을 모은다. 스크립트·스타일 안은 보지 않는다."""
    SKIP = frozenset({'script', 'style', 'template', 'noscript', 'svg'})
    GRAB = frozenset({'title', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p'})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found: dict[str, str] = {}
        self.description = ''
        self._skip = 0
        self._tag: str | None = None
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP:
            self._skip += 1
        elif tag == 'meta':
            a = {k: v or '' for k, v in attrs}
            if a.get('name', '').lower() == 'description' and not self.description:
                self.description = a.get('content', '').strip()
        elif tag in self.GRAB and self._tag is None and not self._skip:
            self._tag, self._buf = tag, []

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP:
            self._skip = max(0, self._skip - 1)
        elif tag == self._tag:
            text = re.sub(r'\s+', ' ', ''.join(self._buf)).strip()
            if text:
                self.found.setdefault('heading' if tag[0] == 'h' and tag != 'h1' else tag, text)
            self._tag = None

    def handle_data(self, data: str) -> None:
        if self._tag and not self._skip:
            self._buf.append(data)


def extract_html_info(text: str) -> dict[str, Any]:
    parser = _HtmlInfo()
    try:
        parser.feed(text)
    except Exception:   # 망가진 표기(<![x> 등)에서 html.parser 가 AssertionError 를 낸다 — 그때까지 찾은 것으로 (점검에서 발견)
        pass
    found = parser.found
    summary = parser.description or found.get('p') or ''
    return {
        'title': found.get('title') or found.get('h1') or found.get('heading'),
        'summary': _truncate(re.sub(r'\s+', ' ', summary)) if summary else '',
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
        if path.suffix.lower() in ('.html', '.htm'):
            info = extract_html_info(read_text(path, HTML_HEAD_BYTES))
        else:
            info = extract_info(read_text(path, HEAD_BYTES))
    except OSError:
        return empty
    _CACHE[key] = (sig, info)
    return info
