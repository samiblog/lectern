"""설정 원문 보기 (D160) — Lectern 설정과 AI 도구에 건네는 것(작성 안내 요약·내 문체·글쓰기 스타일·스킬·Claude Code 설정)을
고치지 않고 원문 그대로 읽는다. 줄마다의 뜻은 Lectern 이 설명 줄로 끼워 보인다 — 파일에는 쓰지 않는다 (config.json 은 JSON 이라
주석을 넣으면 읽지 못한다). 읽는 파일은 `catalog` 가 정한 자리뿐이고 요청은 그 id 로만 고른다 (CLAUDE.md 원칙 3 의 예외 — D159·D160).
스킬은 그 폴더 안의 파일만 (`resolve_inside`). 쓰지 않는다.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from . import aistatus
from .config import DEFAULTS, value_ok
from .i18n import N_, t
from .scanner import resolve_inside

MAX_TEXT = 1_000_000   # 이보다 큰 파일은 글을 보이지 않는다
SKIP = {'__pycache__'}

# ---- 바꾸는 곳 ----------------------------------------------------------------------------------------
W_GENERAL = N_("설정 창 '일반'")
W_VIEW = N_("설정 창 '보기'")
W_EDIT = N_("설정 창 '편집'")
W_PRINT = N_("설정 창 '인쇄·내보내기'")
W_TERM = N_("설정 창 '터미널'")
W_AI = N_("설정 창 'AI 도구'")
W_WORK = N_("설정 창 '업무'")
W_TOOLBAR = N_('툴바')
W_SIDEBAR = N_('사이드바')
W_TOC = N_('목차')
W_TERMINAL = N_('터미널 경계·머리줄')
W_EXPORT = N_('내보내기 창')
W_TABLE = N_('표 막대')
W_SLIDE = N_('슬라이드 창의 툴바')
W_PPTX = N_("'pptx 로 전환' 창")
W_RECORD = N_('Lectern 이 기록 — 고칠 일 없음')
W_FILE = N_("이 파일에서만 — 설정 창 '고급'의 '설정 파일 열기'")

# Lectern 설정의 열쇠마다 (뜻, 바꾸는 곳) — config.DEFAULTS 와 같은 열쇠 (시험이 견준다)
CONFIG_DOCS: dict[str, tuple[str, str]] = {
    'version': (N_('설정 형식의 판 — 옛 설정을 새 판으로 바꿀 때 본다'), W_RECORD),
    'recent': (N_('최근 연 프로젝트 폴더 (최신순, 열 개까지)'), W_RECORD),
    'last_folder': (N_('마지막으로 연 폴더 — 탭 기록이 없던 옛 설정이면 이 폴더를 연다'), W_RECORD),
    'tabs': (N_('열어 둔 프로젝트 탭 (왼쪽부터) — 다음 실행에 되살린다'), W_RECORD),
    'active_tab': (N_('선택돼 있던 프로젝트 탭의 순번 (0부터)'), W_RECORD),
    'language': (N_('화면 언어 — auto(Windows 표시 언어)·ko·en. 바꾸면 화면을 다시 불러온다'), W_GENERAL),
    'theme': (N_("문서 스타일 — auto(시스템의 밝음·어두움) 또는 스타일 이름. 'user:' 로 시작하면 내 스타일"), W_TOOLBAR),
    'slide_theme': (N_('슬라이드 창의 스타일 (메인 창과 따로)'), W_SLIDE),
    'pptx_style': (N_("'pptx 로 전환'의 기본 pptx 스타일 — 설정 폴더 pptx-styles 의 파일 이름"), W_PPTX),
    'recent_md_styles': (N_('최근 쓴 md 문서 스타일 (최신순)'), W_RECORD),
    'recent_templates': (N_('슬라이드 갤러리에서 최근 쓴 템플릿 (묶음과 이름)'), W_RECORD),
    'recent_puts': (N_('넣기 창에서 최근 넣은 것 (다섯까지)'), W_RECORD),
    'recent_chars': (N_('특수 문자 창에서 최근 넣은 문자 (열둘까지)'), W_RECORD),
    'settings_section': (N_('설정 창에서 마지막에 고른 분류 — 다음에 그 분류로 연다'), W_RECORD),
    'font_scale': (N_('문서 글자 크기 배율 (0.8~2, 1 이 100%)'), W_TOOLBAR),
    'doc_width': (N_('md 문서 본문의 폭 배율 (0.8~2, 10 이면 칸 가득)'), W_TOOLBAR),
    'line_numbers': (N_('md 문서 왼쪽 여백의 원문 줄 번호 (Alt+L)'), W_TOOLBAR),
    'theme_groups': (N_('스타일 목록을 묶는 방식 — use(용도별)·mood(분위기별)·tone(밝기별)'), W_VIEW),
    'show_titles': (N_('사이드바 목록에 파일 이름 대신 문서 제목'), W_SIDEBAR),
    'sidebar_visible': (N_('사이드바 보이기 (Ctrl+B)'), W_TOOLBAR),
    'sidebar_width': (N_('사이드바 폭 (px) — null 이면 기본 폭'), W_SIDEBAR),
    'toc_width': (N_('목차 폭 (px) — null 이면 기본 폭'), W_TOC),
    'side_sort': (N_('사이드바 목록의 차례 — name(이름)·time(시간)·type(형식). 폴더가 먼저'), W_SIDEBAR),
    'files_open': (N_("사이드바 '파일' 탭에서 펼친 묶음 — docs·code·others·folder(폴더 구조 그대로)"), W_SIDEBAR),
    'docs_kind': (N_("'문서' 묶음에서 펼친 하위 묶음 — all·md·deck·html·work·marks·tasks"), W_SIDEBAR),
    'toc_visible': (N_('오른쪽 목차 보이기'), W_TOC),
    'search_docs': (N_('검색에서 문서를 찾음'), W_SIDEBAR),
    'search_code': (N_('검색에서 코드를 찾음'), W_SIDEBAR),
    'search_others': (N_('검색에서 자료를 이름으로 찾음'), W_SIDEBAR),
    'recent_docs': (N_('최근 변경에 문서를 보임'), W_SIDEBAR),
    'recent_code': (N_('최근 변경에 코드를 보임'), W_SIDEBAR),
    'recent_others': (N_('최근 변경에 자료를 보임'), W_SIDEBAR),
    'toc_hidden_parts': (N_('목차에서 감춘 구성 요소 종류 — table·figure·box·diagram·code·math'), W_TOC),
    'math': (N_('$…$ 수식을 그림'), W_VIEW),
    'external_images': (N_('문서 속 인터넷(https) 그림을 불러옴 — 끄면 링크로만, 인터넷에 요청하지 않음'), W_VIEW),
    'md_breaks': (N_('문단 안의 줄바꿈을 화면에서도 줄바꿈으로 — 끄면 표준 Markdown'), W_VIEW),
    'vi_keys': (N_('읽는 화면의 vi 키 (j·k·dd·i …)'), W_EDIT),
    'editor_keys': (N_('전체 편집기의 키 — default(Esc 로 닫기)·vim'), W_EDIT),
    'restore_last': (N_('폴더를 열면 마지막에 보던 문서와 위치로'), W_GENERAL),
    'expand_first_level': (N_('폴더를 열 때 트리의 첫 단계 폴더를 펼쳐 둠'), W_GENERAL),
    'window': (N_('창 크기 (px) — 다음 실행에 이 크기로'), W_RECORD),
    'exclude_dirs': (N_("트리에서 뺄 폴더 이름 — 기본 제외 폴더에 더한다 ('자료' 목록에는 접혀 나온다)"), W_FILE),
    'html_exclude_dirs': (N_('이 이름의 폴더 안 html 은 문서로 보지 않음 — src·public 등에 더한다'), W_FILE),
    'editor': (N_('코드 파일을 열 편집기의 전체 경로 — null 이면 VS Code(code)'), W_FILE),
    'terminal_shell': (N_('오른쪽 터미널의 셸 전체 경로 — null 이면 Windows PowerShell'), W_FILE),
    'terminal_width': (N_('오른쪽 터미널 폭 (px) — null 이면 기본'), W_TERMINAL),
    'terminal_height': (N_('아래 터미널 높이 (px) — null 이면 기본'), W_TERMINAL),
    'terminal_position': (N_('터미널 자리 — auto(창이 세로로 길면 아래)·side·bottom'), W_TERM),
    'terminal_follow_style': (N_('터미널 색을 문서 스타일에 맞춤 — 끄면 늘 어둡게'), W_TERM),
    'terminal_font_size': (N_('터미널 글자 크기 (px, 10~24)'), W_TERM),
    'csv_stats': (N_('CSV 표 위의 통계 줄'), W_TABLE),
    'table_align': (N_('md 문서 표의 칸 맞춤 — auto(글 왼쪽·숫자 오른쪽)·report(보고서식 — 머리행·짧은 열 가운데)'), W_VIEW),
    'projects': (N_('프로젝트마다 마지막 문서·열어 둔 문서 탭·문서별 스크롤 위치 (스무 프로젝트까지)'), W_RECORD),
    'work_home': (N_('업무 관리의 공통 폴더'), W_WORK),
    'work_folders': (N_('WORK.md 가 있는 폴더들 — 업무 현황이 모아 보인다 (경로만)'), W_RECORD),
    'work_alerts': (N_('Lectern 안의 업무 알림'), W_WORK),
    'print_font': (N_('인쇄·PDF 본문 글꼴 — serif(명조)·sans(고딕)'), W_PRINT),
    'print_margin': (N_('인쇄·PDF 여백 — normal·narrow·wide'), W_EXPORT),
    'print_header': (N_('인쇄·PDF 쪽 머리 — 2쪽부터 문서 제목과 날짜'), W_EXPORT),
    'print_page_numbers': (N_('인쇄·PDF 바닥 쪽 번호'), W_EXPORT),
    'ai_tool': (N_('터미널에서 쓰는 AI 도구 — claude·codex·antigravity·opencode·any(여럿). 화면의 이름과 요청 글이 따른다'), W_AI),
    'ai_scope_guide': (N_('작성 안내 요약을 넣을 곳 — all(개인 폴더, 모든 폴더에 듣는다)·folder(그 폴더)'), W_AI),
    'ai_scope_skills': (N_('PowerPoint·Word 스킬을 넣을 곳 — all(개인 스킬 폴더)·folder(그 폴더)'), W_AI),
    'ai_style_where': (N_('글쓰기 스타일을 켤 곳 — folder(그 폴더)·all(모든 폴더의 기본)·off(그 폴더에서 끄기)'), W_AI),
    'ai_style': (N_('고른 글쓰기 스타일 — research(리서치 글쓰기)·brief(업무 보고)·academic(학술 글)·plain(쉬운 설명), mine:파일 이름(내 스타일)'), W_AI),
}

# Claude Code 설정 파일(settings.json)의 열쇠 — 자주 쓰는 것만. 그 밖은 GENERIC (뜻을 지어내지 않는다)
CLAUDE_DOCS: dict[str, str] = {
    'outputStyle': N_('출력 스타일 — 이 파일이 듣는 곳의 글쓰기 방식. Lectern 의 글쓰기 스타일을 켜면 이 값이 된다. 폴더의 값이 개인 값보다 앞선다'),
    'permissions': N_('Claude Code 가 묻지 않고 해도 되는 일·물어야 하는 일·하면 안 되는 일'),
    'env': N_('Claude Code 를 띄울 때 넣는 환경 변수 — 비밀 값이 있을 수 있다'),
    'model': N_('기본 모델'),
    'hooks': N_('정한 때(도구를 쓰기 전·뒤 등)에 저절로 돌리는 명령'),
    'statusLine': N_('아래 상태줄을 그리는 명령'),
    'enabledPlugins': N_('켜 둔 플러그인'),
    'extraKnownMarketplaces': N_('더한 플러그인 마켓플레이스'),
    'apiKeyHelper': N_('API 키를 내주는 명령'),
    'cleanupPeriodDays': N_('대화 기록을 남겨 두는 날 수'),
    'includeCoAuthoredBy': N_('커밋에 Claude 공동 저자 줄을 넣을지'),
    'alwaysThinkingEnabled': N_('늘 깊이 생각하기'),
    'enableAllProjectMcpServers': N_('프로젝트의 MCP 서버를 묻지 않고 모두 켜기'),
    'enabledMcpjsonServers': N_('켜 둔 프로젝트 MCP 서버'),
}
PERMISSION_DOCS: dict[str, str] = {
    'allow': N_('묻지 않고 해도 되는 일'),
    'ask': N_('할 때마다 묻는 일'),
    'deny': N_('하면 안 되는 일'),
    'defaultMode': N_('처음 권한 방식'),
    'additionalDirectories': N_('작업 폴더 밖에서 더 읽고 쓸 수 있는 폴더'),
}
GENERIC_CLAUDE = N_('Claude Code 의 설정 — 뜻은 Claude Code 설명서의 settings 장')

# 맨 위 설정(--- 사이)의 열쇠 — 출력 스타일·스킬
STYLE_HEAD_DOCS: dict[str, str] = {
    'name': N_('스타일 이름 — /output-style 목록과 설정 값 outputStyle 에 쓰인다'),
    'description': N_('스타일 목록에 보이는 설명'),
    'keep-coding-instructions': N_('true 면 Claude Code 의 개발 지침을 남긴다 — 없거나 false 면 뺀다'),
}
SKILL_HEAD_DOCS: dict[str, str] = {
    'name': N_('스킬 이름'),
    'description': N_('Claude 가 이 스킬을 쓸지 정할 때 읽는 설명 — 이런 요청이면 이 스킬을 쓴다'),
    'allowed-tools': N_('이 스킬이 묻지 않고 쓸 수 있는 도구'),
    'license': N_('스킬의 라이선스'),
}

HEADS = {
    'config': N_("Lectern 의 설정 — 모든 폴더와 창에 듣는다. 설정 창·툴바에서 바꾸면 Lectern 이 이 파일에 쓰고, 손으로 고치려면 설정 창 '고급'의 '설정 파일 열기'"),
    'rules': N_("{cli} 가 모든 프로젝트에서 읽는 Lectern 작성 안내 요약 — 설정 창 'Lectern 알려 주기'의 요청 글로 넣는다"),
    'rules_shared': N_("{cli} 가 모든 프로젝트에서 읽는 개인 지시 파일 — Lectern 작성 안내 요약은 그 안의 한 절"),
    'voice': N_('내 문체 노트 — 글을 쓰거나 다듬을 때 Claude Code 가 참고한다 (모든 프로젝트)'),
    'csettings': N_('Claude Code 의 개인 설정 — 모든 프로젝트에 듣는다. 프로젝트의 .claude/settings.json·settings.local.json 이 앞선다. 비밀 값이 있을 수 있으니 화면을 나눌 때 조심한다'),
    'csettings-local': N_('이 폴더에서 나만 쓰는 Claude Code 설정 — /output-style 로 고른 값이 여기에 들어간다. 가장 앞선다'),
    'csettings-shared': N_('이 폴더를 함께 쓰는 사람과 나누는 Claude Code 설정 (git 에 올린다)'),
    'style': N_('Claude Code 의 출력 스타일 — 켜면 아래 본문이 Claude Code 의 시스템 지시를 대신한다. --- 사이는 설정, 그 밑은 Claude 에게 주는 글'),
    'lstyle': N_('Lectern 에 든 글쓰기 스타일 — 설치하면 이 파일이 ~/.claude/output-styles 로 복사된다'),
    'skill': N_('스킬 — 요청이 맞으면 Claude 가 SKILL.md 를 읽고 그대로 한다. 같은 폴더의 scripts 는 그 안내가 돌리는 프로그램'),
    'lskill': N_('Lectern 에 든 스킬 — 설치하면 이 폴더가 개인 스킬 폴더로 복사된다'),
}


def _note(text: str) -> dict[str, str]:
    return {'note': text}


def _rows(lines: list[str], notes: dict[int, list[str]]) -> list[dict[str, Any]]:
    """파일 줄과 설명 줄을 합친다 — 설명은 그 줄 앞에. 파일 줄에만 번호 (1부터)"""
    out: list[dict[str, Any]] = []
    for i, line in enumerate(lines):
        out += [_note(x) for x in notes.get(i, [])]
        out.append({'n': i + 1, 'text': line})
    out += [_note(x) for x in notes.get(len(lines), [])]
    return out


def json_keys(text: str) -> list[tuple[int, int, str, str | None]]:
    """(줄 순번, 깊이, 열쇠, 부모 열쇠) — 문자열 밖에서 '"열쇠":' 로 시작하는 줄. 깊이 1 이 맨 바깥 객체의 열쇠"""
    out = []
    depth = 0
    in_str = esc = False
    last: dict[int, str] = {}
    for i, line in enumerate(text.split('\n')):
        m = None if in_str else re.match(r'\s*"((?:[^"\\]|\\.)*)"\s*:', line)
        if m:
            try:
                key = json.loads(f'"{m.group(1)}"')
            except ValueError:
                key = m.group(1)
            last[depth] = key
            out.append((i, depth, key, last.get(depth - 1)))
        for ch in line:
            if in_str:
                if esc:
                    esc = False
                elif ch == '\\':
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch in '{[':
                depth += 1
            elif ch in '}]':
                depth -= 1
    return out


def _short(value: Any) -> str | None:
    """설명에 붙일 기본값 — 짧은 값만"""
    if isinstance(value, (list, dict)):
        return None if value else json.dumps(value)
    return json.dumps(value, ensure_ascii=False)


def config_notes(text: str) -> dict[int, list[str]]:
    lines = text.split('\n')
    notes: dict[int, list[str]] = {0: [t(HEADS['config'])]}
    try:
        data = json.loads(text)
    except ValueError:
        notes[0].append(t('JSON 으로 읽지 못하는 파일입니다 — Lectern 은 기본값으로 돌고, 파일을 고칠 때까지 설정을 저장하지 않습니다'))
        data = None
    seen = set()
    for i, depth, key, _ in json_keys(text):
        if depth != 1:
            continue
        seen.add(key)
        doc = CONFIG_DOCS.get(key)
        if doc is None:
            notes.setdefault(i, []).append(t('Lectern 이 쓰지 않는 열쇠입니다'))
            continue
        default = _short(DEFAULTS.get(key))
        notes.setdefault(i, []).append(t('{doc} · 기본 {default} · 바꾸는 곳: {where}', doc=t(doc[0]), default=default, where=t(doc[1]))
                                       if default is not None else t('{doc} · 바꾸는 곳: {where}', doc=t(doc[0]), where=t(doc[1])))
        if isinstance(data, dict) and key in data and not value_ok(key, data[key]):
            notes[i].append(t('형식이 틀려 기본값으로 돌고 있습니다'))
    missing = [k for k in DEFAULTS if k not in seen]
    if data is not None and missing:
        notes.setdefault(len(lines), []).append(t('파일에 없는 설정은 기본값으로 돈다: {keys}', keys=', '.join(missing)))
    return notes


def claude_notes(text: str, head: str) -> dict[int, list[str]]:
    notes: dict[int, list[str]] = {0: [t(head)]}
    for i, depth, key, parent in json_keys(text):
        if depth == 1:
            notes.setdefault(i, []).append(t(CLAUDE_DOCS.get(key, GENERIC_CLAUDE)))
        elif depth == 2 and parent == 'permissions' and key in PERMISSION_DOCS:
            notes.setdefault(i, []).append(t(PERMISSION_DOCS[key]))
    return notes


def md_notes(text: str, head: str, head_docs: dict[str, str] | None = None) -> dict[int, list[str]]:
    """맨 위의 설명과, 맨 앞 설정(--- 사이)의 열쇠마다"""
    lines = text.split('\n')
    notes: dict[int, list[str]] = {0: [head]}
    if head_docs and lines and lines[0].strip() == '---':
        for i in range(1, len(lines)):
            if lines[i].strip() == '---':
                break
            key = lines[i].split(':', 1)[0].strip() if ':' in lines[i] and not lines[i].startswith((' ', '\t')) else ''
            if key in head_docs:
                notes.setdefault(i, []).append(t(head_docs[key]))
    return notes


# ---- 자리 ------------------------------------------------------------------------------------------------

def _style_files(folder: Path) -> list[Path]:
    try:
        return sorted(f for f in folder.glob('*.md') if f.is_file()) if folder.is_dir() else []
    except OSError:
        return []


def catalog(home: Path, tool: str, config_path: Path, skills_dir: Path, styles: list[dict[str, Any]], project: Path | None,
            project_name: str = '', en: bool = False) -> list[dict[str, Any]]:
    """보일 수 있는 것: 묶음마다 [{id, label, path, exists, kind}]. id 는 read() 가 받는 것 — 경로는 여기서만 정한다"""
    key = tool if tool in aistatus.TOOLS else 'claude'
    info = aistatus.TOOLS[key]
    cli = {'claude': 'Claude Code', 'codex': 'Codex', 'antigravity': 'Antigravity', 'opencode': 'OpenCode'}[key]

    def item(id_: str, label: str, path: Path, kind: str) -> dict[str, Any]:
        return {'id': id_, 'label': label, 'path': str(path), 'exists': path.exists(), 'kind': kind}

    groups = [{'group': 'Lectern', 'items': [item('config', t('Lectern 설정'), config_path, 'config')]}]
    mine = [item('rules', t('작성 안내 요약'), home.joinpath(*info['rules']), 'rules')]
    if key == 'claude':
        mine.append(item('voice', t('내 문체 노트'), aistatus.home_voice(home, en), 'voice'))
        mine.append(item('csettings', t('Claude Code 개인 설정'), home.joinpath(*aistatus.USER_SETTINGS), 'csettings'))
        mine += [item(f'style:{f.name}', t('글쓰기 스타일: {name}', name=f.stem), f, 'style') for f in _style_files(home.joinpath(*aistatus.STYLES_DIR))]
    sk = home.joinpath(*info['skills'])
    mine += [item(f'skill:{n}', t('스킬: {name}', name=n), sk / n, 'skill') for n in aistatus.LECTERN_SKILLS]
    groups.append({'group': t('{cli} — 개인 폴더', cli=cli), 'items': mine})
    if project is not None:
        here = []
        if key == 'claude':
            here.append(item('csettings-local', t('Claude Code 설정 (나만)'), project.joinpath(*aistatus.PROJECT_SETTINGS[0][1]), 'csettings-local'))
            here.append(item('csettings-shared', t('Claude Code 설정 (함께)'), project.joinpath(*aistatus.PROJECT_SETTINGS[1][1]), 'csettings-shared'))
            here += [item(f'pstyle:{f.name}', t('글쓰기 스타일: {name}', name=f.stem), f, 'style') for f in _style_files(project / '.claude' / 'output-styles')]
        psk = project.joinpath(*info['project_skills'])
        here += [item(f'pskill:{n}', t('스킬: {name}', name=n), psk / n, 'skill') for n in aistatus.LECTERN_SKILLS if (psk / n).is_dir()]
        groups.append({'group': t('이 폴더 — {name}', name=project_name or project.name), 'items': here})
    groups.append({'group': t('Lectern 에 든 것'), 'items': [item(f"lstyle:{s['id']}", t('글쓰기 스타일: {name}', name=s['name']), Path(s['path']), 'lstyle') for s in styles]
                   + [item(f'lskill:{n}', t('스킬: {name}', name=n), skills_dir / n, 'lskill') for n in aistatus.LECTERN_SKILLS]})
    return groups


def _skill_files(root: Path) -> list[dict[str, Any]]:
    out = []
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP and not d.startswith('.'))
            for f in sorted(filenames):
                if f.endswith('.pyc') or f.startswith('.'):
                    continue
                p = Path(dirpath) / f
                out.append({'rel': p.relative_to(root).as_posix(), 'size': p.stat().st_size})
    except OSError:
        pass
    return out


def _text(path: Path) -> tuple[str | None, str]:
    """(글, 까닭) — 글이 아니거나 크면 (None, 'binary'·'big'·'missing')"""
    try:
        if not path.is_file():
            return None, 'missing'
        if path.stat().st_size > MAX_TEXT:
            return None, 'big'
        data = path.read_bytes()
    except OSError:
        return None, 'missing'
    if b'\x00' in data[:8192]:
        return None, 'binary'
    return data.decode('utf-8-sig', errors='replace').replace('\r\n', '\n'), ''


def read(groups: list[dict[str, Any]], id_: str, sub: str = '', cli: str = 'Claude Code') -> dict[str, Any] | None:
    """catalog 의 id 하나를 읽는다. 스킬이면 sub(그 폴더 안의 상대경로, 없으면 SKILL.md)와 폴더의 파일 목록. 없는 id 면 None"""
    found = next((it for g in groups for it in g['items'] if it['id'] == id_), None)
    if found is None:
        return None
    kind = found['kind']
    path = Path(found['path'])
    out: dict[str, Any] = {'id': id_, 'label': found['label'], 'kind': kind}
    if kind in ('skill', 'lskill'):
        root = path
        out['files'] = _skill_files(root) if root.is_dir() else []
        rel = sub or 'SKILL.md'
        target = resolve_inside(root.resolve(), rel) if root.is_dir() else None
        if target is None:
            return None if sub else {**out, 'path': str(root / rel), 'rows': [], 'reason': 'missing', 'sub': rel}
        path = target
        out['sub'] = rel
    out['path'] = str(path)
    text, reason = _text(path)
    if text is None:
        return {**out, 'rows': [], 'reason': reason, 'size': path.stat().st_size if path.is_file() else 0}
    out['size'] = path.stat().st_size
    if kind == 'config':
        notes = config_notes(text)
    elif kind.startswith('csettings'):
        notes = claude_notes(text, HEADS[kind])
    elif kind in ('style', 'lstyle'):
        notes = md_notes(text, t(HEADS[kind]) if kind == 'lstyle' else t(HEADS['style']), STYLE_HEAD_DOCS)
        if kind == 'lstyle':
            notes[0].append(t(HEADS['style']))
    elif kind in ('skill', 'lskill'):
        head = t(HEADS[kind]) if out['sub'] == 'SKILL.md' else ''
        notes = md_notes(text, head, SKILL_HEAD_DOCS) if out['sub'] == 'SKILL.md' else {}
        if kind == 'lskill' and out['sub'] == 'SKILL.md':
            notes[0].append(t(HEADS['skill']))
        notes = {k: [x for x in v if x] for k, v in notes.items()}
    elif kind == 'rules':
        notes = {0: [t(HEADS['rules'] if cli == 'Claude Code' else HEADS['rules_shared'], cli=cli)]}
    elif kind == 'voice':
        notes = {0: [t(HEADS['voice'])]}
    else:
        notes = {}
    out['rows'] = _rows(text.split('\n'), notes)
    return out
