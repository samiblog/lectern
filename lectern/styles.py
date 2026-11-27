"""사용자 스타일 (D53): 설정 폴더의 styles\\*.css — 툴바 스타일 목록의 '내 스타일'.

Lectern 은 이 파일을 읽기만 한다 (쓰는 것은 사용자나 Claude Code 같은 AI — 만드는 법은 web/help/styles.md).
예외는 '내 스타일 만들기' 창(D211 — save_made): 사용자가 저장을 누를 때 새 파일 하나를 만들고, 그 창이 만든 파일(머리 주석 maker: lectern)만
물은 뒤 고쳐 쓴다 — 그사이 바뀌었으면 쓰지 않는다. 손이나 AI 로 쓴 파일은 고치지 않는다 (바탕으로 삼아 새 이름으로만).
파일 맨 앞의 머리 주석에서 이름·밝기·바탕 스타일을 읽는다 (없으면 파일 이름, 밝음, 밝으면 default·어두우면 dark):

    /* lectern-style
       name: 우리 회사 보고서
       dark: no
       base: report
    */

화면에 내보낼 때는 인터넷에서 무엇을 불러오는 길(@import, data: 가 아닌 url(), image-set())을 지운다 — 로컬 전용 (원칙 2).
CSS 이스케이프로 숨긴 것('\\75 rl(' 등)은 먼저 풀고, 그래도 숨긴 주소가 남으면 그 스타일은 쓰지 않는다 (빈 css).
앱 페이지의 CSP 도 막는다 (style-src·font-src 는 'self' — @import·글꼴. 그림은 설정 external_images 를 따르므로 거르기가 지킨다).
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from .editing import BAD_NAME_CHARS, RESERVED_NAMES, EditError
from .i18n import t
from .paths import config_dir, web_dir
from .scanner import has_hidden_attr, natural_key

MAX_STYLE_BYTES = 1024 * 1024   # 이보다 큰 파일은 읽지 않는다
MAX_STYLES = 100                # 목록에 싣는 수
HEAD_BYTES = 8192               # 머리 주석을 찾는 앞부분

_HEAD = re.compile(r'\A\s*(?:@charset\s+"[^"]*";\s*)?/\*\s*lectern-style\b(.*?)\*/', re.DOTALL | re.IGNORECASE)
_FIELD = re.compile(r'^\s*\*?\s*([a-z-]+)\s*:\s*(.*?)\s*$', re.IGNORECASE)
_TRUE = {'yes', 'true', 'on', '1', '예', '네', 'dark', '어두운', '어두움'}   # i18n-ok (머리 주석의 값 — 한국어로 적어도 되게)
# CSS 이스케이프로 글자를 숨긴 것('\75 rl(' · 'u\rl(' = 'url(')을 먼저 푼다 — 영문자·괄호·붙임표만 (따옴표 등을 풀면 문자열이 깨진다).
# 왼쪽부터 한 번에: '\\' 는 그 자체로 한 묶음이라 뒤 글자를 이스케이프로 잘못 읽지 않는다
_ESCAPE = re.compile(r'\\(?:([0-9a-fA-F]{1,6})[ \t\n\r\f]?|(.))', re.DOTALL)
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
    return {'name': name, 'dark': dark, 'base': base, 'head': bool(m), 'maker': fields.get('maker', '').strip().lower() == 'lectern'}


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
                    'base': info['base'], 'head': info['head'], 'mtime': st.st_mtime, 'size': st.st_size, 'maker': info['maker']})
        if len(out) >= MAX_STYLES:
            break
    return out


def _unescape(m: re.Match) -> str:
    if m.group(1):
        code = int(m.group(1), 16)
        ch = chr(code) if code < 0x110000 else ''
    else:
        ch = m.group(2) if not re.fullmatch(r'[0-9a-fA-F]', m.group(2)) else ''
    return ch if _PLAIN.fullmatch(ch) else m.group(0)


def _cleaned(text: str) -> str:
    text = _IMPORT.sub('/* @import 은 쓰지 않습니다 (Lectern) */', text)   # i18n-ok (CSS 주석)
    text = _URL.sub(lambda m: m.group(0) if m.group(2).strip().lower().startswith('data:') else 'none', text)
    return _IMAGE_SET.sub('lectern-blocked(', text)


def sanitize_css(text: str) -> str:
    """인터넷에서 무엇을 불러오는 길을 지운다: @import, data: 가 아닌 url(), image-set(). 그래도 숨긴 것이 남으면 빈 css"""
    text = _cleaned(_ESCAPE.sub(_unescape, text))
    probe = text.replace('\\', '').lower()   # 이스케이프를 다 지우고 봐도 남은 길이 있으면 (숨기려 한 것)
    if _cleaned(probe) != probe:
        return '/* Lectern: 이 스타일은 인터넷 주소를 이스케이프로 숨겨 불러오려 해서 쓰지 않습니다 */\n'   # i18n-ok (CSS 주석)
    return text


def read_style(name: str, folder: Path | None = None) -> str | None:
    """화면에 내보낼 스타일 글 (sanitize_css 를 거친). 없거나 너무 크면 None"""
    path = _style_file(folder or styles_dir(), name)
    if path is None or path.stat().st_size > MAX_STYLE_BYTES:
        return None
    try:
        return sanitize_css(path.read_bytes().decode('utf-8-sig', errors='replace'))
    except OSError:
        return None


# ---- 내 스타일 만들기 (D211) — 창이 고른 값으로 CSS 파일 하나 ----------------------------------------------
# 값은 각 스타일이 이미 쓰는 :root 의 변수만, 종류마다 거른다 (글꼴 이름·#색·범위 안의 숫자). CSS 글은 서버가 짓는다 — 화면이 보낸 글을 쓰지 않는다.
MAKER_VARS: dict[str, tuple] = {
    '--md-font': ('font',), '--md-heading-font': ('font',),
    '--md-size': ('px', 12, 24), '--md-line': ('num', 1.2, 2.4), '--md-width': ('px', 560, 1400),
    '--md-fg': ('color',), '--md-heading': ('color',), '--md-link': ('color',), '--md-th-bg': ('color',),
    '--lec-list-top-weight': ('int', 400, 800), '--lec-list-top-scale': ('num', 1, 1.2),
}
MAKER_MARK = '/* lectern-maker */'
MAX_NAME = 40
_FONT = re.compile(r'^[^;{}()\\<>@/*:!\n\r]{1,300}$')
_COLOR = re.compile(r'^#[0-9a-fA-F]{6}$')
_DECL = re.compile(r'(--[a-z-]+)\s*:\s*([^;]*);')


def _stamp(path: Path) -> str:
    st = path.stat()
    return f'{st.st_mtime_ns}:{st.st_size}'


def _value(key: str, raw: Any) -> str:
    """거른 값의 CSS 글 — 틀리면 EditError"""
    spec = MAKER_VARS.get(key)
    bad = EditError(400, t('스타일 값이 올바르지 않습니다: {key}', key=str(key)[:40]))
    if spec is None:
        raise bad
    kind = spec[0]
    if kind == 'font':
        if not isinstance(raw, str) or not _FONT.match(raw.strip()) or 'url' in raw.lower():
            raise bad
        return raw.strip()
    if kind == 'color':
        if not isinstance(raw, str) or not _COLOR.match(raw):
            raise bad
        return raw.lower()
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not spec[1] <= raw <= spec[2]:
        raise bad
    if kind == 'int':
        return str(int(raw))
    return f'{round(float(raw), 3):g}' + ('px' if kind == 'px' else '')


def _clean_name(name: Any) -> str:
    clean = ' '.join(name.split()) if isinstance(name, str) else ''
    if (not clean or len(clean) > MAX_NAME or clean[0] == '.' or clean[-1] == '.' or any(c in BAD_NAME_CHARS for c in clean)
            or clean.lower() in RESERVED_NAMES):
        raise EditError(400, t('스타일 이름은 {n}자까지입니다 — 점으로 시작하거나 끝나면 안 되고 : * ? " < > | / \\ 를 쓸 수 없습니다', n=MAX_NAME))
    return clean


def _maker_block(values: dict[str, str]) -> str:
    lines = ''.join(f'  {k}: {v};\n' for k, v in values.items())
    return f'{MAKER_MARK}\n:root {{\n{lines}}}\n'


def made_values(name: str, folder: Path | None = None) -> dict[str, Any] | None:
    """'내 스타일 만들기' 가 만든 파일의 이름·바탕·값 — 다시 열 때 불러온다. 그 창이 만든 파일이 아니면 None"""
    path = _style_file(folder or styles_dir(), name)
    if path is None or path.stat().st_size > MAX_STYLE_BYTES:
        return None
    try:
        text = path.read_bytes().decode('utf-8-sig', errors='replace')
    except OSError:
        return None
    info = parse_head(text[:HEAD_BYTES], builtin_styles())
    at = text.rfind(MAKER_MARK)
    if not info['maker'] or at < 0:
        return None
    values: dict[str, Any] = {}
    for key, raw in _DECL.findall(text[at:]):
        spec = MAKER_VARS.get(key)
        if spec is None:
            continue
        raw = raw.strip()
        if spec[0] in ('font', 'color'):
            values[key] = raw
        else:
            try:
                values[key] = float(raw[:-2] if raw.endswith('px') else raw)
            except ValueError:
                continue
    return {'file': path.name, 'name': info['name'] or path.stem, 'base': info['base'], 'dark': info['dark'], 'values': values,
            'stamp': _stamp(path), 'copied': '/* lectern-base:' in text[:at]}


def save_made(name: Any, base: Any, dark: Any, values: Any, file: Any = None, stamp: Any = None, copy: Any = None,
              folder: Path | None = None) -> dict[str, Any]:
    """'내 스타일 만들기' 의 저장 (D211). file 이 없으면 새 파일 하나 (같은 이름이 있으면 만들지 않는다).
    file 이 있으면 그 창이 만든 그 파일을 고쳐 쓴다 — 머리 주석에 maker: lectern 이 있고, 불러온 뒤 바뀌지 않았을 때만 (stamp).
    copy 는 손이나 AI 로 쓴 내 스타일 — 그 규칙을 새 파일에 옮겨 담고 그 위에 값을 얹는다 (원래 파일은 그대로)"""
    folder = folder or styles_dir()
    builtins = builtin_styles()
    clean = _clean_name(name)
    if base not in builtins or not isinstance(values, dict) or len(values) > len(MAKER_VARS):
        raise EditError(400, t('스타일 값이 올바르지 않습니다: {key}', key='base'))
    decls = {k: _value(k, v) for k, v in values.items()}
    decls = {k: decls[k] for k in MAKER_VARS if k in decls}   # 늘 같은 차례
    head = (f'/* lectern-style\n   name: {clean}\n   dark: {"yes" if dark is True else "no"}\n   base: {base}\n   maker: lectern\n*/\n')
    if file:
        path = _style_file(folder, file) if isinstance(file, str) else None
        old = made_values(file, folder) if path else None
        if old is None:
            raise EditError(404, t("이 스타일은 '내 스타일 만들기' 가 만든 것이 아니라 고치지 않습니다 — 새 이름으로 저장하세요"))
        if stamp != old['stamp']:
            raise EditError(409, t('스타일 파일이 그사이 바뀌었습니다 — 창을 닫고 다시 열면 바뀐 값을 불러옵니다'))
        text = path.read_bytes().decode('utf-8-sig', errors='replace')
        m = _HEAD.match(text)
        middle = text[m.end():text.rfind(MAKER_MARK)] if m else ''
        tmp = path.with_name(f'.{path.stem}.lectern-tmp')
        try:
            tmp.write_text(head + middle.lstrip('\n') + _maker_block(decls), encoding='utf-8', newline='\n')
            os.replace(tmp, path)
        except OSError as exc:
            tmp.unlink(missing_ok=True)
            raise EditError(500, t('스타일을 저장하지 못했습니다: {why}', why=exc.strerror or exc)) from None
        return {'file': path.name, 'id': f'user:{path.stem}', 'stamp': _stamp(path)}
    middle = ''
    if copy:
        src = _style_file(folder, copy) if isinstance(copy, str) else None
        if src is None or src.stat().st_size > MAX_STYLE_BYTES:
            raise EditError(404, t('바탕으로 삼을 스타일 파일이 없습니다'))
        text = src.read_bytes().decode('utf-8-sig', errors='replace')
        m = _HEAD.match(text)
        body = text[m.end():] if m else text
        if MAKER_MARK in body:   # 이 창이 만든 파일을 바탕으로 — 그 값 칸은 빼고(새 값 칸이 대신한다), 그 파일이 옮겨 담은 규칙은 그대로
            body = re.sub(r'\A\s*/\* lectern-base: [^*]*\*/\n?', '', body[:body.rfind(MAKER_MARK)])
        middle = f'/* lectern-base: {src.name} */\n{body.strip()}\n\n' if body.strip() else ''
    path = folder / f'{clean}.css'
    try:
        folder.mkdir(parents=True, exist_ok=True)
        with open(path, 'x', encoding='utf-8', newline='\n') as fh:
            fh.write(head + middle + _maker_block(decls))
    except FileExistsError:
        raise EditError(409, t('같은 이름의 스타일이 있습니다 — 다른 이름으로 저장하세요')) from None
    except OSError as exc:
        raise EditError(500, t('스타일을 저장하지 못했습니다: {why}', why=exc.strerror or exc)) from None
    return {'file': path.name, 'id': f'user:{path.stem}', 'stamp': _stamp(path)}

