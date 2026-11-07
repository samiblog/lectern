"""md 문서 스타일의 내 스타일 (D103) — 설정 폴더 md-styles 의 파일 하나가 스타일 하나다.

Lectern 전체가 함께 쓴다. 파일은 {"kind": "prose"|"outline", "marks": ["제{1}장", ...]} 이고 파일 이름이 스타일 이름이다.
앱이 쓰는 것은 사용자가 '이 문서를 스타일로 만들기'를 고를 때의 새 파일 하나뿐이다. 있는 파일을 고치거나 지우지 않는다.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .editing import BAD_NAME_CHARS, RESERVED_NAMES, EditError
from .i18n import t
from .paths import config_dir

MAX_NAME = 40
MAX_MARK = 16
KINDS = ('prose', 'outline')


def styles_dir() -> Path:
    """내 스타일 폴더 (설정 폴더의 md-styles)"""
    return config_dir() / 'md-styles'


def _good(data: Any) -> bool:
    return (isinstance(data, dict) and data.get('kind') in KINDS and isinstance(data.get('marks'), list)
            and 0 < len(data['marks']) <= 6 and all(isinstance(m, str) and len(m) <= MAX_MARK for m in data['marks'])
            and any(data['marks']))


def list_styles() -> list[dict[str, Any]]:
    """이름 차례로. 읽지 못하거나 모양이 틀린 파일은 넘어간다."""
    folder = styles_dir()
    if not folder.is_dir():
        return []
    out = []
    for path in sorted(folder.glob('*.json'), key=lambda p: p.name.lower()):
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 4000:
                continue
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if _good(data):
            out.append({'name': path.stem, 'kind': data['kind'], 'marks': data['marks']})
    return out


def save_style(name: Any, kind: Any, marks: Any) -> dict[str, Any]:
    """새 파일 하나를 만든다. 같은 이름이 있으면 만들지 않는다."""
    data = {'kind': kind, 'marks': marks}
    if not isinstance(name, str) or not _good(data):
        raise EditError(400, t('스타일 이름이나 머리글 모양이 올바르지 않습니다'))
    clean = ' '.join(name.split())
    if (not clean or len(clean) > MAX_NAME or clean[0] == '.' or clean[-1] == '.' or any(c in BAD_NAME_CHARS for c in clean)
            or clean.lower() in RESERVED_NAMES):
        raise EditError(400, t('스타일 이름은 {n}자까지입니다 — 점으로 시작하거나 끝나면 안 되고 : * ? " < > | / \\ 를 쓸 수 없습니다', n=MAX_NAME))
    folder = styles_dir()
    try:
        folder.mkdir(parents=True, exist_ok=True)
        with open(folder / f'{clean}.json', 'x', encoding='utf-8', newline='\n') as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
    except FileExistsError:
        raise EditError(409, t('같은 이름의 스타일이 있습니다 — 다른 이름으로 저장하세요')) from None
    except OSError as exc:
        raise EditError(500, t('스타일을 저장하지 못했습니다: {why}', why=exc.strerror or exc)) from None
    return {'name': clean, **data}
