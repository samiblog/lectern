"""지면 틀 (D145) — md 문서에 입히는 출력 양식. 앱에 든 틀(web/layouts/*.html)과 설정 폴더 layouts 의 '내 틀'.

틀 파일 하나가 틀 하나다: 맨 앞의 머리 주석(<!--lectern-layout … -->)에 이름·묶음·쪽·쓰는 맨 앞 설정 키·박스글 자리·설명,
그 뒤에 <style> 과 뼈대 html. 뼈대의 {{title}}·{{body}}·{{slot:요약}} 같은 자리는 화면(layout.js)이 채운다.

- 앱은 틀을 읽기만 한다. 사용자의 틀 폴더는 '틀 폴더 열기'를 누를 때 비어 있으면 만들기만 한다 (내 스타일과 같다 — D53).
- 받은 사람의 브라우저에서 열리는 파일이 되므로 틀에서 스크립트·이벤트 속성·javascript: 주소·바깥 문서(iframe·object)·
  인터넷에서 무엇을 불러오는 CSS(@import·data: 가 아닌 url()·image-set)를 지운다 (styles.sanitize_css).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .paths import config_dir, web_dir
from .styles import sanitize_css

MAX_BYTES = 512 * 1024   # 이보다 큰 틀은 읽지 않는다
MAX_USER = 100           # 목록에 싣는 내 틀 수
HEAD = re.compile(r'\A\s*<!--\s*lectern-layout\b(.*?)-->', re.DOTALL | re.IGNORECASE)
FIELD = re.compile(r'^\s*([a-z_]+)\s*:\s*(.*?)\s*$', re.IGNORECASE)
SAFE_NAME = re.compile(r'^[^\\/:*?"<>|\x00-\x1f.][^\\/:*?"<>|\x00-\x1f]*\.html$', re.IGNORECASE)
STYLE = re.compile(r'<style\b[^>]*>(.*?)</style\s*>', re.DOTALL | re.IGNORECASE)
PAIRED = re.compile(r'<(script|iframe|object|frameset|applet|form|template|noscript|style)\b[^>]*>.*?</\1\s*>', re.DOTALL | re.IGNORECASE)
LONE = re.compile(r'</?(script|iframe|object|embed|frame|frameset|applet|form|base|meta|link|template|noscript)\b[^>]*>', re.IGNORECASE)
EVENT_ATTR = re.compile(r'\s(on[a-z]+)\s*=\s*("[^"]*"|\'[^\']*\'|[^\s>]+)', re.IGNORECASE)
JS_URL = re.compile(r'(\s(?:href|src|action|formaction|xlink:href)\s*=\s*)(["\']?)\s*javascript:[^"\'>\s]*\2', re.IGNORECASE)
EXT_SRC = re.compile(r'(\s(?:src|srcset|poster|background)\s*=\s*)(["\']?)\s*(?:https?:)?//[^"\'>\s]*\2', re.IGNORECASE)
STYLE_ATTR = re.compile(r'(\sstyle\s*=\s*)(["\'])(.*?)\2', re.DOTALL | re.IGNORECASE)
GROUP_ORDER = ['업무·공공', '연구', '금융·컨설팅', '매체·출판', '안내']   # i18n-ok (틀 머리의 묶음 이름 — 차례만 정한다)


def builtin_dir() -> Path:
    return web_dir() / 'layouts'


def user_dir() -> Path:
    """사용자의 틀 폴더 (설정 폴더의 layouts)"""
    return config_dir() / 'layouts'


def parse_head(text: str) -> dict[str, str]:
    """머리 주석의 키: 값 — 없으면 빈 표"""
    m = HEAD.match(text)
    if not m:
        return {}
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        f = FIELD.match(line)
        if f:
            out[f.group(1).lower()] = f.group(2)
    return out


def _split(value: str) -> list[str]:
    return [x.strip() for x in value.split(',') if x.strip()]


def _info(lid: str, path: Path, user: bool) -> dict[str, Any] | None:
    try:
        if path.stat().st_size > MAX_BYTES:
            return None
        head = parse_head(path.read_bytes()[:8192].decode('utf-8-sig', errors='replace'))
    except OSError:
        return None
    pages = head.get('pages', 'A4')
    return {
        'id': lid, 'user': user,
        'name': head.get('name') or path.stem, 'name_en': head.get('name_en') or head.get('name') or path.stem,
        'group': head.get('group', ''), 'group_en': head.get('group_en') or head.get('group', ''),
        'pages': pages, 'flow': pages.strip().lower() in ('continuous', '연속'),   # i18n-ok (머리의 값)
        'fields': _split(head.get('fields', '')), 'slots': _split(head.get('slots', '')),
        'description': head.get('description', ''), 'description_en': head.get('description_en') or head.get('description', ''),
    }


def list_layouts(folder: Path | None = None) -> list[dict[str, Any]]:
    """고를 수 있는 틀 — 앱에 든 것(묶음 차례, 그 안은 파일 이름 차례) 다음에 내 틀. 내 틀의 id 는 'user/파일 이름'"""
    out = []
    for p in sorted(builtin_dir().glob('*.html')):
        info = _info(p.stem, p, False)
        if info:
            out.append(info)
    rank = {g: i for i, g in enumerate(GROUP_ORDER)}
    out.sort(key=lambda x: (rank.get(x['group'], len(GROUP_ORDER)), x['id']))
    mine = folder or user_dir()
    if mine.is_dir():
        files = [p for p in sorted(mine.iterdir(), key=lambda p: p.name.lower()) if p.is_file() and SAFE_NAME.match(p.name)][:MAX_USER]
        for p in files:
            info = _info(f'user/{p.stem}', p, True)
            if info:
                out.append(info)
    return out


def _file(lid: str, folder: Path | None = None) -> Path | None:
    """id → 파일. 앱의 틀은 이름만, 내 틀은 'user/이름' — 폴더 밖으로 나가는 이름은 받지 않는다"""
    if not isinstance(lid, str) or not lid:
        return None
    if lid.startswith('user/'):
        name = lid[5:] + '.html'
        base = folder or user_dir()
    else:
        name = lid + '.html'
        base = builtin_dir()
    if not SAFE_NAME.match(name) or name.startswith('_'):
        return None
    path = base / name
    return path if path.is_file() else None


def sanitize(markup: str) -> str:
    """틀의 뼈대 html 에서 스크립트·이벤트 속성·javascript: 주소·바깥 문서·인터넷 그림을 지운다. style 속성의 CSS 도 거른다"""
    prev = None
    while prev != markup:   # 겹쳐 숨긴 것(<scr<script>ipt>)까지
        prev = markup
        markup = LONE.sub('', PAIRED.sub('', markup))
    markup = EVENT_ATTR.sub('', markup)
    markup = JS_URL.sub(r'\1""', markup)
    markup = EXT_SRC.sub(r'\1""', markup)
    return STYLE_ATTR.sub(lambda m: f'{m.group(1)}{m.group(2)}{sanitize_css(m.group(3)).replace(m.group(2), "")}{m.group(2)}', markup)


def read_layout(lid: str, folder: Path | None = None) -> dict[str, Any] | None:
    """화면에 줄 틀: {id, css(<style> 들을 거른 것), markup(뼈대 — 거른 것), base(모든 틀 앞의 _base.css)}. 없거나 너무 크면 None"""
    path = _file(lid, folder)
    if path is None:
        return None
    try:
        if path.stat().st_size > MAX_BYTES:
            return None
        text = path.read_bytes().decode('utf-8-sig', errors='replace')
        base = (builtin_dir() / '_base.css').read_text(encoding='utf-8')
    except OSError:
        return None
    m = HEAD.match(text)
    body = text[m.end():] if m else text
    css = '\n'.join(sanitize_css(s) for s in STYLE.findall(body))
    markup = sanitize(STYLE.sub('', body)).strip()
    return {'id': lid, 'css': css, 'markup': markup, 'base': base}
