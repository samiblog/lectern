"""내 도해 스타일·내 색 조합 (D215): 설정 폴더의 diagram-styles\\*.json — 고르기 창·설정 창에 기본 번호 뒤로 (모양 11번부터, 색 9번부터).

Lectern 은 이 파일을 읽기만 한다 (쓰는 것은 사용자나 Claude — 만드는 법은 web/help/diagram-styles.md, 그림 우클릭
'이 모양으로 내 도해 스타일 만들기…' 가 요청 글을 터미널에 넣는다). 폴더는 '폴더 열기'가 비어 있을 때 만들기만 한다.

파일 하나가 스타일 하나다. 값은 정해진 열쇠와 범위만 받는다 — CSS·Mermaid 설정을 그대로 받지 않는다 (문서·파일이 할 수 있는 것을
늘리지 않는다 — D56, '내 스타일 만들기'의 정해진 변수 — D211). 틀린 값은 빼고 그 까닭을 problems 에 남긴다 (설정 창이 보인다).

    {"kind": "style", "number": 11, "name": "우리 회사", "tip": "…", "base": 8,
     "corner": 4, "border": 1.5, "line": "step", "line_width": 1.4, "dash": false, "shadow": false,
     "fill": "light", "spacing": "normal", "bold": true, "title": "band", "zones": false, "sketch": false}
    {"kind": "colors", "number": 9, "name": "회사 색", "tip": "…",
     "series": ["#17304f", "#c2410c", …], "strong": "#17304f", "accent": "#c2410c", "zones": ["#17304f", …]}
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .i18n import t
from .paths import config_dir
from .scanner import has_hidden_attr, natural_key

FIRST_STYLE = 11      # 기본 모양은 1~10 (web/js/diagramstyles.js 의 STYLES, config.DIAGRAM_STYLES)
FIRST_COLORS = 9      # 기본 색 조합은 1~8 (PALETTES, config.DIAGRAM_COLORS)
LAST_NUMBER = 99
BUILTIN_STYLES = 10
MAX_FILES = 60
MAX_BYTES = 32 * 1024
NAME_MAX = 24
TIP_MAX = 80

# 모양의 값 — 열쇠마다 (종류, 범위·고를 것)
STYLE_VALUES: dict[str, tuple[str, Any]] = {
    'base': ('int', (1, BUILTIN_STYLES)),
    'corner': ('num', (0, 24)),           # 상자 모서리 둥글기 (px)
    'border': ('num', (0, 4)),            # 상자 테두리 굵기 (px)
    'line': ('choice', ('curve', 'step', 'straight')),
    'line_width': ('num', (0.5, 4)),      # 선 굵기 (px)
    'dash': ('bool', None),               # 선을 점선으로
    'shadow': ('bool', None),             # 상자 그림자
    'fill': ('choice', ('none', 'light', 'solid')),   # 상자 채움 — 없음(바탕색)·옅게·진하게
    'spacing': ('choice', ('tight', 'normal', 'wide')),
    'bold': ('bool', None),               # 상자 글자 굵게
    'title': ('choice', ('none', 'band', 'tint', 'rule')),   # 제목 상자 — 줄을 바꾼 상자의 첫 줄이 제목
    'zones': ('bool', None),              # 묶음마다 색을 돌려 쓰기
    'sketch': ('bool', None),             # 손그림 선 (Mermaid 만)
}
_HEX = re.compile(r'^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')
_BAD_NAME = re.compile(r'[·,;:<>{}\[\]"\\`\x00-\x1f]')   # 표시 줄을 나누는 글자(·,;)와 그 밖의 쓰지 않을 글자
_SAFE_FILE = re.compile(r'^[^\\/:*?"<>|\x00-\x1f]+\.json$', re.IGNORECASE)


def styles_dir() -> Path:
    """내 도해 스타일 폴더 (설정 폴더의 diagram-styles)"""
    return config_dir() / 'diagram-styles'


def _file(folder: Path, name: str) -> Path | None:
    """폴더 바로 안의 .json 파일 (숨김·링크·하위 폴더는 아님)"""
    if not _SAFE_FILE.match(name) or name.startswith('.'):
        return None
    path = folder / name
    try:
        st = path.lstat()
    except OSError:
        return None
    if not path.is_file() or path.is_symlink() or has_hidden_attr(st):
        return None
    return path


def _hex(value: Any) -> str | None:
    """'#abc'·'#aabbcc' → '#aabbcc' (소문자). 아니면 None"""
    if not isinstance(value, str) or not _HEX.match(value.strip()):
        return None
    v = value.strip().lower()
    return '#' + ''.join(c * 2 for c in v[1:]) if len(v) == 4 else v


def _name(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    v = ' '.join(value.split())
    if not v or len(v) > NAME_MAX or _BAD_NAME.search(v) or v[0].isdigit():
        return None
    return v


def _value(kind: str, rule: Any, value: Any) -> Any:
    """정해진 값이면 그 값 (숫자는 범위 안), 아니면 None"""
    if kind == 'bool':
        return value if isinstance(value, bool) else None
    if kind in ('int', 'num'):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        if kind == 'int' and value != int(value):
            return None
        lo, hi = rule
        if not lo <= value <= hi:
            return None
        return int(value) if kind == 'int' else round(float(value), 2)
    if kind == 'choice':
        return value if isinstance(value, str) and value in rule else None
    return None


def _read(path: Path) -> tuple[dict | None, str]:
    try:
        if path.stat().st_size > MAX_BYTES:
            return None, t('파일이 너무 큽니다 ({kb}KB 까지)', kb=MAX_BYTES // 1024)
        data = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, UnicodeDecodeError):
        return None, t('파일을 읽지 못했습니다')
    except ValueError as exc:
        return None, t('JSON 이 아닙니다: {error}', error=str(exc)[:80])
    if not isinstance(data, dict):
        return None, t('JSON 객체 하나여야 합니다')
    return data, ''


def _style(data: dict, notes: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in data.items():
        if key in ('kind', 'number', 'name', 'tip'):
            continue
        rule = STYLE_VALUES.get(key)
        if rule is None:
            notes.append(t("모르는 열쇠 '{key}' — 뺐습니다", key=key))
            continue
        v = _value(rule[0], rule[1], value)
        if v is None:
            notes.append(t("'{key}' 의 값이 틀려 뺐습니다: {value}", key=key, value=json.dumps(value, ensure_ascii=False)[:40]))
            continue
        out[key] = v
    return out


def _colors(data: dict, notes: list[str]) -> dict[str, Any] | None:
    for key in data:
        if key not in ('kind', 'number', 'name', 'tip', 'series', 'strong', 'accent', 'zones'):
            notes.append(t("모르는 열쇠 '{key}' — 뺐습니다", key=key))
    series = data.get('series')
    if not isinstance(series, list) or not 2 <= len(series) <= 12 or any(_hex(c) is None for c in series):
        notes.append(t("'series' 는 '#rrggbb' 색 2~12개여야 합니다"))
        return None
    out: dict[str, Any] = {'series': [_hex(c) for c in series]}
    for key in ('strong', 'accent'):
        c = _hex(data.get(key))
        if data.get(key) is not None and c is None:
            notes.append(t("'{key}' 의 값이 틀려 뺐습니다: {value}", key=key, value=json.dumps(data.get(key), ensure_ascii=False)[:40]))
        out[key] = c or out['series'][0 if key == 'strong' else min(1, len(out['series']) - 1)]
    zones = data.get('zones')
    if zones is not None:
        if isinstance(zones, list) and 1 <= len(zones) <= 12 and all(_hex(c) for c in zones):
            out['zones'] = [_hex(c) for c in zones]
        else:
            notes.append(t("'zones' 는 '#rrggbb' 색 1~12개여야 합니다 — 뺐습니다"))
    return out


def load(folder: Path | None = None) -> dict[str, Any]:
    """폴더의 내 도해 스타일·내 색 조합: {styles: [{n, name, tip, file, …값}], colors: [{n, name, tip, file, series, strong, accent, zones?}],
    problems: [{file, why}], next: {style, colors} (다음에 쓸 빈 번호)}. 번호가 겹치면 먼저 있던 파일(고친 때가 이른 것 — 쓰던 번호를 새 파일이
    빼앗지 않게), 같으면 이름 순으로 앞의 것"""
    folder = folder or styles_dir()
    styles: list[dict[str, Any]] = []
    colors: list[dict[str, Any]] = []
    problems: list[dict[str, str]] = []
    try:
        names = sorted((e.name for e in folder.iterdir() if e.name.lower().endswith('.json')), key=natural_key)
    except OSError:
        names = []
    if len(names) > MAX_FILES:
        problems.append({'file': '', 'why': t('파일이 {n}개를 넘어 앞의 {n}개만 읽었습니다', n=MAX_FILES)})
        names = names[:MAX_FILES]

    def age(name: str) -> float:
        try:
            return (folder / name).stat().st_mtime
        except OSError:
            return 0.0

    names.sort(key=lambda n: (age(n), natural_key(n)))   # 번호가 겹치면 먼저 있던 파일이 그 번호를 쓴다
    taken: dict[str, set[int]] = {'style': set(), 'colors': set()}
    for name in names:
        path = _file(folder, name)
        if path is None:
            continue
        data, why = _read(path)
        if data is None:
            problems.append({'file': name, 'why': why})
            continue
        kind = data.get('kind')
        if kind not in ('style', 'colors'):
            problems.append({'file': name, 'why': t("'kind' 는 \"style\" 이나 \"colors\" 여야 합니다")})
            continue
        first = FIRST_STYLE if kind == 'style' else FIRST_COLORS
        n = data.get('number')
        if isinstance(n, bool) or not isinstance(n, int) or not first <= n <= LAST_NUMBER:
            problems.append({'file': name, 'why': t("'number' 는 {lo}~{hi} 의 정수여야 합니다", lo=first, hi=LAST_NUMBER)})
            continue
        if n in taken[kind]:
            problems.append({'file': name, 'why': t('번호 {n} 은 먼저 있던 파일이 씁니다 — 다른 번호로', n=n)})
            continue
        label = _name(data.get('name'))
        if label is None:
            problems.append({'file': name, 'why': t("'name' 은 {max}자까지, 숫자로 시작하지 않고 · , ; : 같은 글자가 없어야 합니다", max=NAME_MAX)})
            continue
        tip = data.get('tip')
        tip = ' '.join(tip.split())[:TIP_MAX] if isinstance(tip, str) else ''
        notes: list[str] = []
        if kind == 'style':
            values = _style(data, notes)
            styles.append({'n': n, 'name': label, 'tip': tip, 'file': name, **values})
        else:
            values = _colors(data, notes)
            if values is None:
                problems.append({'file': name, 'why': '; '.join(notes)})
                continue
            colors.append({'n': n, 'name': label, 'tip': tip, 'file': name, **values})
        taken[kind].add(n)
        problems.extend({'file': name, 'why': x} for x in notes)

    def free(kind: str, first: int) -> int:
        return next((k for k in range(first, LAST_NUMBER + 1) if k not in taken[kind]), 0)

    styles.sort(key=lambda s: s['n'])
    colors.sort(key=lambda s: s['n'])
    return {'styles': styles, 'colors': colors, 'problems': problems, 'next': {'style': free('style', FIRST_STYLE), 'colors': free('colors', FIRST_COLORS)}}
