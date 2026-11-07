"""Lectern 슬라이드 템플릿 (D101) — 장 하나의 뼈대.

Lectern 슬라이드 파일 하나가 묶음이고 그 안의 장 하나가 템플릿이다. 평소처럼 한 줄 편집·구조 보기·점검으로 고치고, 장 차례가 번호다.
기본 묶음은 web/templates/<언어>/ 에, 사용자의 묶음은 설정 폴더의 templates 에 있다. 프로젝트가 아니라 Lectern 전체가 함께 쓴다.
장의 이름은 <!-- template: 이름 --> 이고 없으면 제목이다. 같은 이름의 pptx 스타일이 묶음의 짝이다 (D102).
앱이 쓰는 것은 사용자가 '이 장을 템플릿으로 저장'을 고를 때 '내 템플릿' 묶음에 장 하나를 더하는 것뿐이다. 다른 묶음은 읽기만 한다.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import i18n
from .editing import BAD_NAME_CHARS, RESERVED_NAMES, EditError
from .i18n import t
from .paths import config_dir, web_dir

MAX_SLIDE = 200_000
MAX_GROUP = 4_000_000
MAX_NAME = 60
_RULE = re.compile(r'^ {0,3}---+\s*$')
_FENCE = re.compile(r'^\s*(`{3,}|~{3,})')
_NAME = re.compile(r'^\s*<!--\s*template:\s*(.+?)\s*-->\s*$')
_HEAD = re.compile(r'^#{1,6}\s+(.+?)\s*$')


def templates_dir() -> Path:
    """사용자 템플릿 폴더 (설정 폴더의 templates)"""
    return config_dir() / 'templates'


def builtin_dir() -> Path:
    return web_dir() / 'templates' / ('en' if i18n.language() == 'en' else 'ko')


def split_slides(text: str) -> list[str]:
    """맨 앞 설정을 빼고 --- 로 장을 나눈다. 코드 블록 안의 --- 는 글이다."""
    lines = text.lstrip('﻿').replace('\r\n', '\n').split('\n')
    if lines and lines[0].strip() == '---':
        end = next((i for i, s in enumerate(lines[1:], 1) if s.strip() == '---'), None)
        if end is not None:
            lines = lines[end + 1:]
    slides: list[list[str]] = [[]]
    fence = ''
    for s in lines:
        m = _FENCE.match(s)
        if fence:
            if m and m[1][0] == fence[0] and len(m[1]) >= len(fence) and not s.strip(' \t`~'):
                fence = ''
        elif m:
            fence = m[1]
        if not fence and _RULE.match(s):
            slides.append([])
        else:
            slides[-1].append(s)
    return ['\n'.join(x).strip('\n') for x in slides if '\n'.join(x).strip()]


def parse_group(text: str) -> list[dict[str, Any]]:
    """묶음 글의 템플릿들: {number, name, text}. 이름 줄은 글에서 뺀다."""
    out = []
    for i, slide in enumerate(split_slides(text), 1):
        lines = slide.split('\n')
        named = next((m[1] for s in lines if (m := _NAME.match(s))), '')
        head = next((m[1] for s in lines if (m := _HEAD.match(s))), '')
        body = '\n'.join(s for s in lines if not _NAME.match(s)).strip('\n')
        out.append({'number': i, 'name': named or head or t('{n}번 장', n=i), 'text': body + '\n'})
    return out


def _read(folder: Path, own: bool) -> list[dict[str, Any]]:
    """폴더의 묶음들. 링크·너무 큰 파일·UTF-8 이 아닌 파일은 넘어간다."""
    if not folder.is_dir():
        return []
    out = []
    for path in sorted(folder.glob('*.md'), key=lambda p: p.name.lower()):
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_GROUP:
                continue
            templates = parse_group(path.read_text(encoding='utf-8'))
        except (OSError, UnicodeDecodeError):
            continue
        if templates:
            out.append({'name': path.stem, 'own': own, 'templates': templates})
    return out


def list_groups() -> list[dict[str, Any]]:
    """고를 차례대로: 기본 묶음 다음에 사용자의 것."""
    return _read(builtin_dir(), False) + _read(templates_dir(), True)


def save_template(name: Any, text: Any) -> dict[str, Any]:
    """'내 템플릿' 묶음에 장 하나를 더한다. 없으면 만든다. 같은 이름의 장이 있으면 더하지 않는다."""
    if not isinstance(name, str) or not isinstance(text, str):
        raise EditError(400, t('템플릿 이름과 글이 올바르지 않습니다'))
    clean = ' '.join(name.split())
    body = text.replace('\r\n', '\n').strip('\n')
    if not clean or len(clean) > MAX_NAME or '-->' in clean or any(c in BAD_NAME_CHARS for c in clean) or clean.lower() in RESERVED_NAMES:
        raise EditError(400, t('템플릿 이름은 {n}자까지입니다 — : * ? " < > | / \\ 를 쓸 수 없습니다', n=MAX_NAME))
    if not body.strip() or len(body.encode('utf-8')) > MAX_SLIDE:
        raise EditError(400, t('템플릿으로 저장할 글이 없거나 너무 깁니다'))
    group = t('내 템플릿')
    path = templates_dir() / f'{group}.md'
    if path.is_symlink():
        raise EditError(400, t('{name} 이 링크라서 쓰지 않습니다', name=path.name))
    try:
        old = path.read_text(encoding='utf-8') if path.exists() else ''
        if any(x['name'].lower() == clean.lower() for x in parse_group(old)):
            raise EditError(409, t('같은 이름의 템플릿이 있습니다 — 다른 이름으로 저장하세요'))
        path.parent.mkdir(parents=True, exist_ok=True)
        slide = f'<!-- template: {clean} -->\n\n{body}\n'
        with open(path, 'a', encoding='utf-8', newline='\n') as f:
            f.write(f'\n---\n\n{slide}' if old.strip() else f'---\nmarp: true\ntitle: {group}\npaginate: true\n---\n\n{slide}')
    except (OSError, UnicodeDecodeError) as exc:
        raise EditError(500, t('템플릿을 저장하지 못했습니다: {why}', why=getattr(exc, 'strerror', None) or exc)) from None
    saved = parse_group(path.read_text(encoding='utf-8'))
    return {'group': group, 'number': len(saved), 'name': clean}
