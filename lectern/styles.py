"""사용자 스타일 (D53): 설정 폴더의 styles\\*.css — 툴바 스타일 목록의 '내 스타일'.

Lectern 은 이 파일을 읽기만 한다 (쓰는 것은 사용자나 Claude Code 같은 AI — 만드는 법은 web/help/styles.md).
파일 맨 앞의 머리 주석에서 이름·밝기·바탕 스타일을 읽는다 (없으면 파일 이름, 밝음, 밝으면 default·어두우면 dark):

    /* lectern-style
       name: 우리 회사 보고서
       dark: no
       base: report
    */

화면에 내보낼 때는 인터넷에서 무엇을 불러오는 길(@import, data: 가 아닌 url(), image-set())을 지운다 — 로컬 전용 (원칙 2).
놓친 길은 앱 페이지의 CSP 가 막는다 (style-src·font-src 는 'self', 그림은 설정 external_images).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .paths import config_dir, web_dir
from .scanner import has_hidden_attr, natural_key

MAX_STYLE_BYTES = 1024 * 1024   # 이보다 큰 파일은 읽지 않는다
MAX_STYLES = 100                # 목록에 싣는 수
HEAD_BYTES = 8192               # 머리 주석을 찾는 앞부분

_HEAD = re.compile(r'\A\s*(?:@charset\s+"[^"]*";\s*)?/\*\s*lectern-style\b(.*?)\*/', re.DOTALL | re.IGNORECASE)
_FIELD = re.compile(r'^\s*\*?\s*([a-z-]+)\s*:\s*(.*?)\s*$', re.IGNORECASE)
_TRUE = {'yes', 'true', 'on', '1', '예', '네', 'dark', '어두운', '어두움'}   # i18n-ok (머리 주석의 값 — 한국어로 적어도 되게)
# CSS 이스케이프로 글자를 숨긴 것('\75 rl(' · 'u\rl(' = 'url(')을 먼저 푼다 — 영문자·괄호·붙임표만 (따옴표 등을 풀면 문자열이 깨진다)
_HEX_ESCAPE = re.compile(r'\\([0-9a-fA-F]{1,6})[ \t\n\r\f]?')
_CHAR_ESCAPE = re.compile(r'\\([g-zG-Z()-])')
_PLAIN = re.compile(r'[A-Za-z()-]')
_IMPORT = re.compile(r'@import\b[^;]*;?', re.IGNORECASE)
_URL = re.compile(r'url\(\s*([\'"]?)(.*?)\1\s*\)', re.IGNORECASE | re.DOTALL)
_IMAGE_SET = re.compile(r'(-webkit-)?image-set\(', re.IGNORECASE)
_SAFE_NAME = re.compile(r'^[^\\/:*?"<>|\x00-\x1f]+\.css$', re.IGNORECASE)


def styles_dir() -> Path:
    """사용자 스타일 폴더 (설정 폴더의 styles)"""
    return config_dir() / 'styles'


def builtin_styles() -> list[str]:
    """앱에 든 스타일 id (web/themes/<id>.css — base.css 는 공통 규칙이라 빼고)"""
    return sorted(p.stem for p in (web_dir() / 'themes').glob('*.css') if p.stem != 'base')


def parse_head(text: str, builtins: list[str]) -> dict[str, Any]:
    """머리 주석의 name·dark·base. 없거나 틀린 값은 기본값"""
    fields: dict[str, str] = {}
    m = _HEAD.match(text)
    if m:
        for line in m.group(1).splitlines():
            f = _FIELD.match(line)
            if f:
                fields[f.group(1).lower()] = f.group(2)
    dark = fields.get('dark', '').strip().lower() in _TRUE
    base = fields.get('base', '').strip().lower()
    if base not in builtins:
        base = 'dark' if dark else 'default'
    name = fields.get('name', '').strip()[:60]
    return {'name': name, 'dark': dark, 'base': base, 'head': bool(m)}


def _style_file(folder: Path, name: str) -> Path | None:
    """폴더 바로 안의 .css 파일 (숨김·링크·하위 폴더는 아님). 없으면 None"""
    if not _SAFE_NAME.match(name) or name.startswith('.'):
        return None
    path = folder / name
    try:
        st = path.lstat()
    except OSError:
        return None
    if not path.is_file() or path.is_symlink() or has_hidden_attr(st):
        return None
    return path


def list_styles(folder: Path | None = None) -> list[dict[str, Any]]:
    """폴더의 스타일: [{id: 'user:<파일 이름>', file, name, dark, base, head, mtime, size}] — 이름 순, MAX_STYLES 개까지"""
    folder = folder or styles_dir()
    try:
        names = sorted((e.name for e in folder.iterdir() if e.suffix.lower() == '.css'), key=natural_key)
    except OSError:
        return []
    builtins = builtin_styles()
    out = []
    for name in names:
        path = _style_file(folder, name)
        if path is None:
            continue
        st = path.stat()
        try:
            with path.open('rb') as fh:
                head = fh.read(HEAD_BYTES).decode('utf-8-sig', errors='replace')
        except OSError:
            continue
        info = parse_head(head, builtins)
        out.append({'id': f'user:{path.stem}', 'file': name, 'name': info['name'] or path.stem, 'dark': info['dark'],
                    'base': info['base'], 'head': info['head'], 'mtime': st.st_mtime, 'size': st.st_size})
        if len(out) >= MAX_STYLES:
            break
    return out


def _unescape(m: re.Match) -> str:
    code = int(m.group(1), 16)
    ch = chr(code) if code < 0x110000 else ''
    return ch if _PLAIN.fullmatch(ch) else m.group(0)


def sanitize_css(text: str) -> str:
    """인터넷에서 무엇을 불러오는 길을 지운다: @import, data: 가 아닌 url(), image-set()"""
    text = _HEX_ESCAPE.sub(_unescape, _CHAR_ESCAPE.sub(r'\1', text))
    text = _IMPORT.sub('/* @import 은 쓰지 않습니다 (Lectern) */', text)   # i18n-ok (CSS 주석)
    text = _URL.sub(lambda m: m.group(0) if m.group(2).strip().lower().startswith('data:') else 'none', text)
    return _IMAGE_SET.sub('lectern-blocked(', text)


def read_style(name: str, folder: Path | None = None) -> str | None:
    """화면에 내보낼 스타일 글 (sanitize_css 를 거친). 없거나 너무 크면 None"""
    path = _style_file(folder or styles_dir(), name)
    if path is None or path.stat().st_size > MAX_STYLE_BYTES:
        return None
    try:
        return sanitize_css(path.read_bytes().decode('utf-8-sig', errors='replace'))
    except OSError:
        return None
