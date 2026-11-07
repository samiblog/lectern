"""Lectern 슬라이드 템플릿 (D101) — 장 하나의 뼈대.

기본 템플릿은 web/templates/<언어>/ 에, 사용자의 것은 설정 폴더의 templates 에 있다. 프로젝트가 아니라 Lectern 전체가
함께 쓴다. 파일 하나가 템플릿 하나이고 이름은 '번호-이름.md' 다. 앱이 쓰는 것은 사용자가 '이 장을 템플릿으로 저장'을
고를 때의 새 파일 하나뿐이다. 있는 파일을 고치거나 지우지 않는다.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import i18n
from .editing import BAD_NAME_CHARS, RESERVED_NAMES, EditError
from .i18n import t
from .paths import config_dir, web_dir

MAX_BYTES = 200_000
MAX_NAME = 60
_NUMBERED = re.compile(r'^(\d+)[-_ ]+(.+)$')


def templates_dir() -> Path:
    """사용자 템플릿 폴더 (설정 폴더의 templates)"""
    return config_dir() / 'templates'


def builtin_dir() -> Path:
    return web_dir() / 'templates' / ('en' if i18n.language() == 'en' else 'ko')


def _name_of(stem: str) -> str:
    m = _NUMBERED.match(stem)
    return (m[2] if m else stem).replace('-', ' ').strip()


def _read(folder: Path) -> list[tuple[str, str, str]]:
    """폴더의 템플릿: (파일 이름, 이름, 글). 링크·너무 큰 파일·UTF-8 이 아닌 파일은 넘어간다."""
    if not folder.is_dir():
        return []
    out = []
    for path in sorted(folder.glob('*.md'), key=lambda p: p.name.lower()):
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
                continue
            out.append((path.name, _name_of(path.stem), path.read_text(encoding='utf-8').lstrip('﻿').replace('\r\n', '\n')))
        except (OSError, UnicodeDecodeError):
            continue
    return out


def list_templates() -> list[dict[str, Any]]:
    """고를 차례대로: 기본 템플릿 다음에 사용자의 것. number 는 화면의 번호다."""
    items = [(False, x) for x in _read(builtin_dir())] + [(True, x) for x in _read(templates_dir())]
    return [{'number': i, 'id': f"{'own' if own else 'base'}:{file}", 'name': name, 'text': text, 'own': own}
            for i, (own, (file, name, text)) in enumerate(items, 1)]


def save_template(name: Any, text: Any) -> dict[str, Any]:
    """사용자 폴더에 새 템플릿 파일 하나를 만든다. 같은 이름이 있으면 만들지 않는다."""
    if not isinstance(name, str) or not isinstance(text, str):
        raise EditError(400, t('템플릿 이름과 글이 올바르지 않습니다'))
    clean = ' '.join(name.split())
    body = text.replace('\r\n', '\n').strip('\n') + '\n'
    if (not clean or len(clean) > MAX_NAME or clean[-1] == '.' or clean.startswith('.') or any(c in BAD_NAME_CHARS for c in clean)
            or clean.lower() in RESERVED_NAMES):
        raise EditError(400, t('템플릿 이름은 {n}자까지입니다 — 점으로 시작하거나 : * ? " < > | / \\ 를 쓸 수 없습니다', n=MAX_NAME))
    if not body.strip() or len(body.encode('utf-8')) > MAX_BYTES:
        raise EditError(400, t('템플릿으로 저장할 글이 없거나 너무 깁니다'))
    folder = templates_dir()
    own = _read(folder)
    if any(existing.lower() == clean.lower() for _, existing, _ in own):
        raise EditError(409, t('같은 이름의 템플릿이 있습니다 — 다른 이름으로 저장하세요'))
    numbers = [int(m[1]) for file, _, _ in own if (m := _NUMBERED.match(Path(file).stem))]
    file = f'{max(numbers, default=0) + 1:02d}-{clean}.md'
    try:
        folder.mkdir(parents=True, exist_ok=True)
        with open(folder / file, 'x', encoding='utf-8', newline='\n') as f:
            f.write(body)
    except FileExistsError:
        raise EditError(409, t('같은 이름의 템플릿이 있습니다 — 다른 이름으로 저장하세요')) from None
    except OSError as exc:
        raise EditError(500, t('템플릿을 저장하지 못했습니다: {why}', why=exc.strerror or exc)) from None
    return next(x for x in list_templates() if x['id'] == f'own:{file}')
