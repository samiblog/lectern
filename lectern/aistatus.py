"""AI 도구 설정의 지금 상태 (D159) — 설정 창 'AI 도구에 건네는 것'이 무엇이 어디에 있는지 보이려고 읽는다.

Lectern 이 AI 도구에 건네는 것(작성 안내 요약·스킬·글쓰기 스타일·내 문체)은 사용자가 시킬 때 AI 도구가 쓴다 (D57·D98·D132·D148).
Lectern 은 쓰지 않고, 아래 TOOLS 표의 정해진 파일만 읽는다 — 사용자의 개인 폴더(홈)와 열린 프로젝트의 것.
경로는 이 표에 고정되고 화면의 요청이 고르지 못한다 (CLAUDE.md 원칙 3 의 예외 — 업무 현황 D124 와 같은 꼴).
설정 파일(settings.json)은 outputStyle 값 하나만 꺼내고 나머지(권한·환경 변수 등)는 읽은 자리에서 버린다.
지시 파일은 'Lectern' 이 들어 있는지만 본다. 스킬은 Lectern 에 든 것과 같은지만 본다.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

# 도구마다의 자리 (홈 기준 — web/js/aitool.js 의 AI_TOOLS 와 같게. 각 도구의 공식 문서로 확인, 2026-11-17)
#   skills: 개인 스킬 폴더, project_skills: 프로젝트 스킬 폴더(프로젝트 기준), rules: Lectern 요약을 넣는 개인 파일,
#   file: 프로젝트 지시 파일, override: 있으면 개인 지시 파일 대신 읽히는 파일 (Codex)
TOOLS: dict[str, dict[str, tuple[str, ...]]] = {
    'claude': {'skills': ('.claude', 'skills'), 'project_skills': ('.claude', 'skills'),
               'rules': ('.claude', 'rules', 'lectern.md'), 'file': ('CLAUDE.md',)},
    'codex': {'skills': ('.agents', 'skills'), 'project_skills': ('.agents', 'skills'),
              'rules': ('.codex', 'AGENTS.md'), 'override': ('.codex', 'AGENTS.override.md'), 'file': ('AGENTS.md',)},
    'antigravity': {'skills': ('.gemini', 'config', 'skills'), 'project_skills': ('.agents', 'skills'),
                    'rules': ('.gemini', 'AGENTS.md'), 'file': ('AGENTS.md',)},
    'opencode': {'skills': ('.config', 'opencode', 'skills'), 'project_skills': ('.agents', 'skills'),
                 'rules': ('.config', 'opencode', 'AGENTS.md'), 'file': ('AGENTS.md',)},
}
LECTERN_SKILLS = ('pptx-to-lectern', 'lectern-to-pptx', 'lectern-to-docx')
# Claude Code: 내 문체 노트는 개인 규칙 폴더의 한 파일 (D159 — 글쓰기 스타일 파일 끝에서 꺼냈다). 화면 언어마다 이름이 다르다
VOICE_FILES = ('내-문체.md', 'my-voice.md')   # i18n-ok (파일 이름)
STYLES_DIR = ('.claude', 'output-styles')
USER_SETTINGS = ('.claude', 'settings.json')
PROJECT_SETTINGS = (('local', ('.claude', 'settings.local.json')), ('shared', ('.claude', 'settings.json')))
VOICE_HEADS = ('## 내 문체', '## My style')   # i18n-ok (파일 속 제목) — 예전 판: 글쓰기 스타일 파일 끝의 내 문체 절 (D148)
MAX_READ = 1_000_000   # 지시·설정 파일을 읽는 크기 (넘으면 읽지 않는다)
SKIP_DIRS = {'__pycache__'}


def _read(path: Path) -> str | None:
    """작은 글 파일. 없거나 크거나 읽지 못하면 None"""
    try:
        if not path.is_file() or path.stat().st_size > MAX_READ:
            return None
        return path.read_text(encoding='utf-8-sig', errors='replace')
    except OSError:
        return None


def output_style(path: Path) -> tuple[str | None, bool]:
    """설정 파일의 outputStyle 값 하나와 읽었는지. 다른 값은 버린다. 파일이 없으면 (None, True), 깨졌으면 (None, False)"""
    if not path.exists():
        return None, True
    text = _read(path)
    if text is None:
        return None, False
    try:
        data = json.loads(text)
    except ValueError:
        return None, False
    value = data.get('outputStyle') if isinstance(data, dict) else None
    return (value if isinstance(value, str) else None), True


def _head(text: str) -> dict[str, str]:
    """맨 위 --- 사이의 name·description (한 줄짜리 값만 — YAML 을 다 읽지 않는다)"""
    m = re.match(r'---\r?\n(.*?)\r?\n---', text, re.S)
    out: dict[str, str] = {}
    for line in (m.group(1).splitlines() if m else []):
        key, sep, value = line.partition(':')
        if sep and key.strip() in ('name', 'description'):
            out[key.strip()] = value.strip().strip('"\'')
    return out


def _norm(text: str) -> str:
    return text.replace('\r\n', '\n').strip()


def _without_voice(text: str) -> tuple[str, bool]:
    """예전 판처럼 끝에 붙인 내 문체 절을 뗀 본문과, 그 절이 있었는지"""
    t = text.replace('\r\n', '\n')
    for head in VOICE_HEADS:
        i = t.find('\n' + head + '\n')
        if i < 0 and t.endswith('\n' + head):
            i = len(t) - len(head) - 1
        if i >= 0:
            return t[:i], True
    return t, False


def style_state(bundled: Path, installed: Path) -> dict[str, Any]:
    """Lectern 의 글쓰기 스타일이 설치됐는지: state missing|same|differs, voice(예전 판의 내 문체 절이 끝에 있는지)"""
    text = _read(installed)
    if text is None:
        return {'state': 'missing', 'voice': False}
    body, voice = _without_voice(text)
    mine = _read(bundled) or ''
    return {'state': 'same' if _norm(body) == _norm(mine) else 'differs', 'voice': voice}


def _files(root: Path) -> list[Path]:
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        out += [Path(dirpath) / f for f in filenames if not f.endswith('.pyc')]
    return out


def skill_state(bundled: Path, installed: Path) -> str:
    """missing(폴더 없음) | same(Lectern 의 파일이 모두 같다 — 더 있는 파일은 보지 않는다) | differs"""
    if not installed.is_dir():
        return 'missing'
    try:
        for src in _files(bundled):
            dst = installed / src.relative_to(bundled)
            if not dst.is_file() or dst.stat().st_size != src.stat().st_size or dst.read_bytes() != src.read_bytes():
                return 'differs'
    except OSError:
        return 'differs'
    return 'same'


def _mentions(path: Path, word: str = 'Lectern') -> bool | None:
    """지시 파일에 그 낱말이 있는지. 파일이 없으면 None"""
    text = _read(path)
    return None if text is None else word in text


def home_dir() -> Path:
    """사용자의 개인 폴더(홈). 시험은 LECTERN_HOME 으로 바꾼다 — 화면 점검이 이 PC 의 실제 ~/.claude 를 읽지 않게"""
    override = os.environ.get('LECTERN_HOME')
    return Path(override) if override else Path.home()


def home_voice(home: Path, bundled_style: Path) -> Path:
    """Claude Code 의 내 문체 노트 — 있으면 그 파일, 없으면 화면 언어의 이름 (D159)"""
    rules = home / '.claude' / 'rules'
    found = next((rules / f for f in VOICE_FILES if (rules / f).is_file()), None)
    return found or rules / (VOICE_FILES[1] if bundled_style.name.endswith('.en.md') else VOICE_FILES[0])


def status(home: Path, tool: str, skills_dir: Path, bundled_style: Path, project: Path | None = None) -> dict[str, Any]:
    """설정 창에 보일 지금 상태. tool: config ai_tool (any 면 Claude Code 의 것을 보인다 — 도구마다의 파일은 요청 글이 적는다)"""
    key = tool if tool in TOOLS else 'claude'
    info = TOOLS[key]
    at = lambda *parts: home.joinpath(*parts)   # noqa: E731
    skills = at(*info['skills'])
    out: dict[str, Any] = {
        'home': str(home),
        'tool': key,
        'skills': {'dir': str(skills), 'items': {n: skill_state(skills_dir / n, skills / n) for n in LECTERN_SKILLS}},
        'rules': {'path': str(at(*info['rules'])), 'exists': at(*info['rules']).is_file(), 'lectern': bool(_mentions(at(*info['rules'])))},
        'project': None,
    }
    if 'override' in info:   # Codex: 이 파일이 있으면 개인 AGENTS.md 는 읽히지 않는다
        out['rules']['override'] = str(at(*info['override'])) if at(*info['override']).is_file() else None
    if key == 'claude':
        rules_dir = at('.claude', 'rules')
        voice = next((rules_dir / f for f in VOICE_FILES if (rules_dir / f).is_file()), None)
        styles_dir = at(*STYLES_DIR)
        installed = styles_dir / bundled_style.name
        if not installed.is_file():   # 다른 언어판을 설치했을 수도 있다
            other = bundled_style.with_name('research-writing.md' if bundled_style.name.endswith('.en.md') else 'research-writing.en.md')
            installed = styles_dir / other.name if (styles_dir / other.name).is_file() else installed
        others = []
        try:
            for f in sorted(styles_dir.glob('*.md')) if styles_dir.is_dir() else []:
                if f.name not in ('research-writing.md', 'research-writing.en.md'):
                    others.append(_head(_read(f) or '').get('name') or f.stem)
        except OSError:
            pass
        user_style, user_ok = output_style(at(*USER_SETTINGS))
        mine = _head(_read(bundled_style) or '')
        out['claude'] = {
            'voice': str(voice) if voice else None,
            'voice_path': str(rules_dir / (VOICE_FILES[1] if bundled_style.name.endswith('.en.md') else VOICE_FILES[0])),
            'styles_dir': str(styles_dir),
            'style': {'path': str(installed), 'name': mine.get('name', ''), **style_state(bundled_style, installed)},
            'other_styles': others,
            'settings': {'user': {'path': str(at(*USER_SETTINGS)), 'value': user_style, 'ok': user_ok}},
        }
    if project is not None:
        files = TOOLS['claude']['file'] + TOOLS['codex']['file'] if tool == 'any' else info['file']
        proj: dict[str, Any] = {
            'root': str(project),
            'name': project.name or str(project),
            'rules': [{'path': str(project / f), 'exists': (project / f).is_file(), 'lectern': bool(_mentions(project / f))} for f in files],
        }
        pskills = project.joinpath(*info['project_skills'])
        proj['skills'] = {'dir': str(pskills), 'items': {n: skill_state(skills_dir / n, pskills / n) for n in LECTERN_SKILLS}}
        if key == 'claude':
            proj['settings'] = {}
            for name, parts in PROJECT_SETTINGS:
                value, ok = output_style(project.joinpath(*parts))
                proj['settings'][name] = {'path': str(project.joinpath(*parts)), 'value': value, 'ok': ok}
        out['project'] = proj
    return out
