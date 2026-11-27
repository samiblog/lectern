"""사용자 설정 (%APPDATA%\\Lectern\\config.json).

뷰어가 디스크에 쓰는 파일은 이 설정 파일 하나뿐이다 (보기 전용 원칙).
사용자가 편집기로 고칠 수 있는 파일이므로(설정 창의 '설정 파일 열기'), 읽거나 저장하기 전에
파일이 밖에서 바뀌었는지 보고 다시 읽는다 — 손으로 고친 값을 앱이 들고 있던 옛 값으로 덮어쓰지 않도록 (D21).
"""
from __future__ import annotations

import copy
import json
import math
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .i18n import N_, resolve, t
from .paths import config_dir

MAX_RECENT = 10
MAX_PROJECTS = 20     # 마지막 위치를 기억하는 프로젝트 수
MAX_POSITIONS = 100   # 프로젝트마다 스크롤 위치를 기억하는 문서 수
MAX_DOC_TABS = 40     # 프로젝트 탭마다 여는 문서 탭 수 (D64·D67·D140 — 화면의 doctabs.js MAX_DOCS 와 같게)
MAX_TABS = 10         # 한 번에 여는 프로젝트 탭 수 (최근 폴더 수와 같게)
MAX_WORK_FOLDERS = 1000   # 업무 폴더 목록에 기억하는 폴더 수 (D124 — WORK.md 가 있는 폴더, D149 — 하위 폴더의 것도 들어 200 → 1000)

CONFIG_VERSION = 4   # 설정 형식 판. 올리면 _upgrade 에 옛 판을 바꾸는 코드를 둔다
TERM_FONT = (10, 24)   # 터미널 글자 크기(px)의 범위 (D130 — 화면 terminal.js 의 TERM_FONT 와 같게)

DEFAULTS: dict[str, Any] = {
    'version': CONFIG_VERSION,
    'recent': [],            # 최근 연 프로젝트 폴더 (최신순)
    'last_folder': None,     # 마지막으로 연 폴더 (tabs 가 없던 옛 설정이면 이 폴더를 연다)
    'tabs': [],              # 열어 둔 프로젝트 탭 (왼쪽부터). 다음 실행에 되살린다 (서버가 기록)
    'active_tab': 0,         # 선택돼 있던 탭의 순번
    'language': 'auto',      # 화면 언어: auto(Windows 표시 언어) | ko | en — 설정 창, 바꾸면 화면을 다시 불러온다 (D46)
    'theme': 'auto',         # auto 또는 스타일 id (web/js/theme.js 의 THEMES). 고른 스타일이 다음 실행의 기본
    'slide_theme': 'deck',   # 슬라이드 창의 스타일 (D96 — 메인 창과 따로)
    'pptx_style': '',        # 기본 pptx 스타일 (D102 — 설정 폴더 pptx-styles 의 파일 이름)
    'recent_md_styles': [],  # 최근 쓴 md 문서 스타일 (최신순 — D103)
    'recent_templates': [],  # 갤러리의 최근 쓴 템플릿 ('묶음\t이름', 최신순 — D101)
    'recent_puts': [],       # 넣기 창의 최근 넣은 것 (구성 요소의 이름, 최신순 다섯 — D154)
    'recent_chars': [],      # 특수 문자 창에서 최근 넣은 문자 (최신순 열둘 — D165)
    'settings_section': 'general',   # 설정 창에서 마지막에 고른 분류 (D154)
    'font_scale': 1.0,       # 문서 글자 크기 배율 (툴바의 − 100% + 버튼, 0.8~2)
    'doc_width': 1.0,        # md 문서 본문의 폭 배율 (툴바의 문서 폭 버튼, 0.8~2, 10 = 가득 — D68)
    'line_numbers': False,   # md 문서 왼쪽 여백의 원문 줄 번호 (툴바 버튼·Alt+L — D80)
    'theme_groups': 'use',   # 스타일 목록을 묶는 방식: use(용도별) | mood(분위기별) | tone(밝기별) — 설정 창
    'diagram_style': 1,      # 도해 스타일의 기본 번호 (D212 — 1~DIAGRAM_STYLES, 그림 블록의 '%% 스타일: 3' 줄이 먼저. 화면은 web/js/diagramstyles.js)
    'diagram_colors': 1,     # 색 조합의 기본 번호 (D213 — 1~DIAGRAM_COLORS, 차트·도해 블록의 '색: 2' 줄과 문서의 '<!-- 도해: 색 2 -->' 가 먼저)
    'ref_windows': 'auto',   # 사용설명서·예제 가이드를 따로 창에서 (D181): auto(앱 창에서는 따로 창, 브라우저 개발 모드는 덮는 보기)·on·off
    'show_titles': False,    # 트리에 파일 이름 대신 문서 제목 표시 (기본은 파일 이름, 마우스를 올리면 제목 — 트리의 '제목' 버튼)
    'sidebar_visible': True,
    'sidebar_width': None,   # 사이드바 폭(px, 200~480). None 이면 기본 폭
    'toc_width': None,       # 목차 폭(px, 160~560). None 이면 기본 폭 — 경계를 끌어 바꾸고 두 번 누르면 기본 (D47)
    'side_sort': 'name',     # 사이드바 목록의 차례: name | time | type (D97 — 폴더가 먼저)
    'clip_sort': 'name',     # 사이드바 '담기' 탭의 담기함 차례: name | time (마지막에 고친 것부터 — D198)
    'files_open': 'docs',    # 사이드바 '파일' 탭에서 펼친 묶음 — docs·code·others·folder (D143 — 한 번에 하나만 펼친다, folder 는 폴더 구조 그대로 — D169)
    'docs_kind': 'all',      # '문서' 묶음에서 펼친 하위 묶음 — all·md·deck·html·pdf·work·marks·tasks·word·ppt·excel·hwp (D143·D201·D202)
    'doc_kinds': [],         # '문서' 묶음으로 옮길 종류 — pdf·word·ppt·excel·hwp (D206 — 기본은 없음: '문서' 에는 md·html 만, 나머지는 '자료'. D202·D204)
    'work_kind': 'tasks',    # '작업' 묶음에서 펼친 하위 묶음 — work·marks·tasks (D204)
    'others_kind': 'all',    # '자료' 묶음에서 펼친 하위 묶음 — all·pdf·word·ppt·excel·hwp·image·etc (D207)
    'toc_visible': True,
    'search_docs': True,     # 전체 검색에서 문서를 찾음 (검색 탭의 '문서' 버튼)
    'search_code': True,     # 전체 검색에서 코드를 찾음 ('코드' 버튼, D44)
    'search_others': True,   # 전체 검색에서 자료를 이름으로 찾음 ('자료' 버튼, D50 — 문서·코드도 이름이 맞으면 먼저 보인다)
    'recent_docs': True,     # 최근 변경 탭에 문서를 보임 ('문서' 버튼, D50)
    'recent_code': True,     # 최근 변경 탭에 코드를 보임 ('코드' 버튼)
    'recent_others': True,   # 최근 변경 탭에 자료를 보임 ('자료' 버튼)
    'toc_hidden_parts': [],  # 목차에서 감춘 구성 요소 종류: table·figure·box·diagram·code·math (목차 머리의 종류 버튼)
    'math': True,            # $...$ 수식 렌더링
    'external_images': True, # 문서 속 http(s) 이미지 표시 (끄면 링크로만)
    'md_breaks': True,       # 문단 안의 줄바꿈을 화면에서도 줄바꿈으로 (D93 — 끄면 표준 Markdown)
    'vi_keys': False,        # vi 키: 읽는 화면의 글자 키(j·k·V·dd·i…) (D122 — 설정 창)
    'doc_check': True,       # md 문서 점검 — 상태줄의 '점검 N곳' (D190: 깨진 틀·보고서의 틀)
    'doc_check_style': False,  # 문서 점검의 글버릇 묶음 — 긴 문단·문장·칸, 줄 끝 공백, 탭 (D190 — 기본 끔)
    'editor_keys': 'default',  # 전체 편집 방식: default(Esc 로 닫기) | vim(CodeMirror vim 키맵 — D122, 설정 창)
    'restore_last': True,    # 폴더를 열면 마지막에 보던 문서와 위치로
    'expand_first_level': True,  # 폴더를 열면 트리의 첫 단계 폴더를 펼쳐 둠
    'window': {'width': 1280, 'height': 860},
    'exclude_dirs': [],      # 기본 제외 폴더에 추가할 폴더 이름 (직접 편집)
    'html_exclude_dirs': [], # 이 이름의 폴더 안 html 은 문서로 보지 않음 (기본 src·public 등에 더함, 직접 편집)
    'editor': None,          # 코드 파일을 열 편집기 실행 파일 경로 (None이면 PATH의 code)
    'terminal_shell': None,  # 오른쪽 터미널의 셸 실행 파일 전체 경로 (None 이면 Windows PowerShell 5.1, 직접 편집 — 예: pwsh.exe)
    'terminal_width': None,  # 오른쪽 터미널 폭(px). None 이면 기본 (경계를 끌어 바꾸고 두 번 누르면 기본)
    'terminal_height': None, # 아래 터미널 높이(px). None 이면 기본 (D52)
    'terminal_position': 'auto',  # 터미널 자리: auto(창이 세로로 길면 아래, 아니면 오른쪽) | side | bottom (설정 창·터미널 머리줄, D52)
    'terminal_follow_style': True,  # 터미널 색을 문서 스타일에 맞춤 (끄면 늘 어둡게 — 설정 창)
    'terminal_font_size': 14,  # 터미널 글자 크기(px) 10~24 (D130 — 설정 창. 0.72 까지는 13 고정)
    'csv_stats': True,       # CSV 표 위의 통계 줄 (표 막대의 '통계' 버튼, D60)
    'table_align': 'auto',   # md 문서 표의 칸 맞춤: auto(글 왼쪽·숫자 오른쪽·위) | report(보고서식 — 머리행·짧은 열 가운데, 세로 가운데) (D174 — 설정 창)
    'projects': {},          # 프로젝트별 마지막 문서와 문서별 스크롤 위치, 지금 담기함(clip — D199) (서버가 기록)
    'work_home': None,       # 업무 관리의 공통 폴더 (D124 — 공통 WORK.md 와 정리 문서. 설정 창·업무 현황에서 고른다, 서버가 기록)
    'work_folders': [],      # WORK.md 가 있는 폴더들 (D124 — 열거나 '폴더 더하기'로 더한다. 경로만, 서버가 기록)
    'work_alerts': True,     # Lectern 안의 업무 알림 (D124 — 시작 요약·일정 10분 전·17:30 기록. 설정 창)
    'print_font': 'serif',   # 인쇄·PDF 의 본문 글꼴: serif(명조) | sans(고딕) (D131 — 설정 창, 보고서 인쇄 양식 web/themes/print.css)
    'print_margin': 'normal',  # 인쇄·PDF 의 여백: normal(위 25·아래 22·좌우 22mm) | narrow(사방 15mm) | wide(위 30·아래 25·좌우 30mm) | custom(print_margin_mm) (D134·D200 — PDF·인쇄 창)
    'print_margin_mm': [25, 22, 22, 22],  # 여백 '직접' 의 숫자 — 위·오른쪽·아래·왼쪽 mm (0~80, D200)
    'print_header': True,    # 인쇄·PDF 의 쪽 머리 — 2쪽부터 문서 제목과 날짜 (D134)
    'print_page_numbers': True,  # 인쇄·PDF 의 바닥 쪽 번호 (D134)
    'ai_tool': 'claude',     # 터미널에서 쓰는 AI 도구: claude(Claude Code) | codex(Codex CLI) | antigravity(Antigravity CLI) | opencode(OpenCode) | any(여럿 — 이름을 정하지 않음)
                             # (D138 — 설정 창. 화면의 이름과 요청 글의 지시 파일·스킬 폴더가 이것을 따른다. 앱이 그 도구를 실행하지는 않는다)
    # AI 도구에 건네는 것을 넣을 곳 (D159 — 설정 창. 요청 글이 이것을 적는다. 쓰는 것은 사용자가 시킬 때 AI 도구가)
    'ai_scope_guide': 'all',   # Lectern 작성 안내 요약: all(개인 규칙 파일 — 모든 폴더) | folder(그 폴더의 지시 파일)
    'ai_scope_skills': 'all',  # PowerPoint·Word 스킬: all(개인 스킬 폴더) | folder(그 폴더의 스킬 폴더)
    'ai_style_where': 'folder',  # 글쓰기 스타일을 켤 곳: folder(그 폴더에서) | all(모든 폴더의 기본) | off(그 폴더에서 끄기). 파일은 늘 개인 폴더에
    'ai_style': 'research',   # 고른 글쓰기 스타일 (D161 — 고르기 창): research·brief·academic·plain(Lectern 에 든 것, web/help/writing-styles.json) | mine:<파일 이름>(개인 폴더의 내 스타일)
}

AI_TOOLS = ('claude', 'codex', 'antigravity', 'opencode', 'any')
AI_STYLES = ('research', 'brief', 'academic', 'plain')   # 설정 ai_style (D161 — web/help/writing-styles.json 의 id 와 같게, 시험이 견준다)
FILES_OPEN = ('docs', 'code', 'others', 'work', 'folder')   # 설정 files_open (D143·D169 — 화면은 others.js)
DOC_KINDS_OPTIONAL = ('pdf', 'word', 'ppt', 'excel', 'hwp', 'work', 'marks', 'tasks')   # 설정 doc_kinds — 고를 수 있는 하위 묶음 (D202)
DIAGRAM_STYLES = 10   # 도해 스타일의 수 (D212 — web/js/diagramstyles.js 의 STYLES 와 같게, 시험이 견준다)
DIAGRAM_COLORS = 8    # 색 조합의 수 (D213 — web/js/diagramstyles.js 의 PALETTES 와 같게, 시험이 견준다)
DIAGRAM_NUMBER_MAX = 99   # 내 도해 스타일·내 색 조합의 번호 끝 (D215 — mydiagrams.LAST_NUMBER)
DOCS_KINDS = ('all', 'md', 'deck', 'html', 'pdf', 'work', 'marks', 'tasks', 'word', 'ppt', 'excel', 'hwp')   # 설정 docs_kind (D143 — 화면은 tree.js 의 KINDS)   # 설정 ai_tool (D138 — 화면의 표는 web/js/aitool.js)

# 프런트엔드(POST /api/config)에서 바꿀 수 있는 키. 나머지는 config.json 직접 편집.
# recent·last_folder·tabs·active_tab·projects 는 서버가 기록한다 (add_recent, set_tabs, remember_position).
CLIENT_KEYS = frozenset({'language', 'theme', 'slide_theme', 'pptx_style', 'recent_templates', 'recent_puts', 'recent_chars', 'settings_section', 'recent_md_styles', 'theme_groups', 'diagram_style', 'diagram_colors', 'font_scale', 'doc_width', 'line_numbers', 'show_titles', 'sidebar_visible', 'sidebar_width', 'toc_width', 'toc_visible', 'math',
                         'external_images', 'restore_last', 'expand_first_level', 'side_sort', 'clip_sort', 'files_open', 'docs_kind', 'doc_kinds', 'work_kind', 'others_kind',
                         'terminal_width', 'terminal_height', 'terminal_position',
                         'terminal_follow_style', 'terminal_font_size', 'toc_hidden_parts', 'search_docs', 'search_code', 'search_others',
                         'recent_docs', 'recent_code', 'recent_others', 'csv_stats', 'table_align', 'md_breaks', 'vi_keys', 'doc_check', 'doc_check_style', 'editor_keys', 'work_alerts', 'print_font', 'print_margin', 'print_margin_mm', 'print_header', 'print_page_numbers', 'ai_tool',
                         'ai_scope_guide', 'ai_scope_skills', 'ai_style_where', 'ai_style'})

# null 도 되는 키 (나머지는 기본값과 같은 형식이어야 한다)
NULLABLE = frozenset({'last_folder', 'editor', 'sidebar_width', 'toc_width', 'terminal_shell', 'terminal_width',
                      'terminal_height', 'work_home'})
_EXAMPLE = {bool: N_('true 또는 false'), int: N_('숫자'), float: N_('숫자'), str: N_('"글자"'), list: N_('["이름", ...] 목록'),
            dict: N_('{ } 객체')}


def is_number(value: Any) -> bool:
    """유한한 숫자. JSON 의 1e400 은 inf 로 읽히는데, 그대로 내보내면 화면이 받는 JSON 이 깨진다 (Infinity)"""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def value_ok(key: str, value: Any) -> bool:
    """설정 값의 형식이 맞는지. 손으로 고치는 파일이라 JSON 은 맞아도 형식이 틀릴 수 있다 (예: "exclude_dirs": "data")."""
    if value is None:
        return key in NULLABLE
    default = DEFAULTS[key]
    if key in ('sidebar_width', 'toc_width', 'terminal_width', 'terminal_height'):
        return is_number(value)
    if key == 'clip_sort':
        return value in ('name', 'time')
    if key == 'files_open':
        return value in FILES_OPEN
    if key == 'docs_kind':
        return value in DOCS_KINDS
    if key == 'work_kind':
        return value in ('work', 'marks', 'tasks')
    if key == 'others_kind':
        return value in ('all', 'pdf', 'word', 'ppt', 'excel', 'hwp', 'image', 'etc')
    if key == 'doc_kinds':
        return isinstance(value, list) and all(x in DOC_KINDS_OPTIONAL for x in value)
    if key == 'terminal_position':
        return value in ('auto', 'side', 'bottom')
    if key == 'editor_keys':
        return value in ('default', 'vim')
    if key == 'print_font':
        return value in ('serif', 'sans')
    if key == 'print_margin':
        return value in ('normal', 'narrow', 'wide', 'custom')
    if key == 'print_margin_mm':
        return isinstance(value, list) and len(value) == 4 and all(is_number(x) and 0 <= x <= 80 for x in value)
    if key == 'ai_tool':
        return value in AI_TOOLS
    if key in ('ai_scope_guide', 'ai_scope_skills'):
        return value in ('all', 'folder')
    if key == 'ai_style_where':
        return value in ('folder', 'all', 'off')
    if key == 'ai_style':
        return isinstance(value, str) and (value in AI_STYLES or (value.startswith('mine:') and value.endswith('.md') and '/' not in value and '\\' not in value))
    if key == 'ref_windows':
        return value in ('auto', 'on', 'off')
    if key == 'settings_section':
        return value in ('general', 'view', 'edit', 'print', 'term', 'ai', 'work', 'more')
    if key in ('diagram_style', 'diagram_colors'):   # 기본 번호, 내 도해 스타일·내 색 조합(D215 — 모양 11~·색 9~)까지. 그 파일이 없으면 화면이 1 로 그린다
        return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= DIAGRAM_NUMBER_MAX
    if key == 'terminal_font_size':
        return isinstance(value, int) and not isinstance(value, bool) and TERM_FONT[0] <= value <= TERM_FONT[1]
    if key in ('last_folder', 'editor', 'terminal_shell', 'work_home'):
        return isinstance(value, str)
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, float):   # 1 처럼 정수로 적어도 된다
        return is_number(value)
    if isinstance(default, int):
        return isinstance(value, int) and not isinstance(value, bool)
    if isinstance(default, list):
        return isinstance(value, list) and all(isinstance(x, str) for x in value)
    return isinstance(value, type(default))


def _upgrade(data: dict[str, Any], loaded: dict[str, Any] | None = None) -> None:
    """옛 판(version)의 설정을 지금 판으로 바꾼다. 파일에는 다음에 설정을 저장할 때 쓰인다 (그 전까지는 읽을 때마다 같은 값으로 바꾼다).
    loaded: 파일에서 읽은 그대로 (없어진 키를 옮길 때)"""
    if data['version'] < 2:
        # v0.7.1: 트리는 파일 이름이 기본이 됐다 (사용자 요청 — 마우스를 올리면 제목). 앱은 저장할 때 기본값도 함께 적으므로
        # 옛 파일의 show_titles: true 는 사용자가 고른 것인지 알 수 없다. 한 번 파일 이름으로 돌린다
        data['show_titles'] = False
    if data['version'] < 3 and (loaded or {}).get('files_view') == 'folder':
        # v0.93.0 (D169): '폴더' 버튼(files_view)은 사이드바의 넷째 묶음 '폴더'가 됐다 — 폴더 보기로 쓰던 사람은 그 묶음을 펼친 채로
        data['files_open'] = 'folder'
    if data['version'] < 4 and (loaded or {}).get('doc_kinds') == ['word', 'ppt', 'excel', 'hwp']:
        # v0.109.0 (D206): 오피스 넷은 기본으로 '자료' 에 — 앱은 저장할 때 기본값도 적으므로 옛 기본값 그대로면 새 기본값으로 (고쳐 둔 것은 그대로)
        data['doc_kinds'] = []
    data['version'] = max(data['version'], CONFIG_VERSION)


def _expected(key: str, lang: str) -> str:
    default = DEFAULTS[key]
    kind = (str if key in ('last_folder', 'editor', 'terminal_shell', 'work_home')
            else int if key in ('sidebar_width', 'toc_width', 'terminal_width') else type(default))
    return t(_EXAMPLE.get(kind, N_('맞는 형식')), lang)


class Config:
    def __init__(self, path: Path | None = None):
        self.path = path or (config_dir() / 'config.json')
        self._lock = threading.RLock()
        self._disk: tuple[int, int] | None = None   # 마지막으로 읽거나 쓴 파일의 (수정 시각, 크기)
        # 파일이 있는데 읽지 못하면 그 이유. 이때는 기본값으로 돌고, 파일이 고쳐질 때까지 저장하지 않는다
        self.load_error: str | None = None
        # 설정의 판 번호 (D159): 화면에서 바꾼 값이나 밖에서 고친 파일을 읽을 때마다 하나 올린다. 창들은 변경 확인(/api/changes)으로
        # 이 번호를 보고, 바뀌었으면 설정을 다시 읽어 그 창에도 입힌다 — 열린 독립창·슬라이드 창도 바로 따르게. 위치·탭 기록은 올리지 않는다
        self.rev = 0
        data, self.load_error = self._read()
        self.data = data or copy.deepcopy(DEFAULTS)

    def _signature(self) -> tuple[int, int] | None:
        try:
            st = self.path.stat()
        except OSError:
            return None
        return st.st_mtime_ns, st.st_size

    def _read(self) -> tuple[dict[str, Any] | None, str | None]:
        """(설정, 오류). 파일이 없으면 기본값. 읽지 못하면 (None, 이유)."""
        self._disk = self._signature()
        data = copy.deepcopy(DEFAULTS)
        # 알릴 말의 언어: 읽은 파일의 language. 파일을 읽지 못하면 들고 있던 설정의 것 (처음이면 Windows 표시 언어)
        lang = resolve(getattr(self, 'data', {}).get('language'))
        try:
            text = self.path.read_text(encoding='utf-8-sig')  # 메모장·PowerShell 5.1 이 붙이는 BOM 허용
        except FileNotFoundError:
            return data, None
        except (OSError, ValueError) as exc:
            return None, self._error_message(t('파일을 읽을 수 없음 ({error})', lang, error=exc), '', lang)
        try:
            loaded = json.loads(text)
        except json.JSONDecodeError as exc:
            hint = t(' 경로 안의 \\ 는 \\\\ 로 씁니다.', lang) if 'escape' in exc.msg else ''
            return None, self._error_message(t('{line}행 {col}열: {error}', lang, line=exc.lineno, col=exc.colno, error=exc.msg), hint, lang)
        if not isinstance(loaded, dict):
            return None, self._error_message(t('맨 바깥이 { } 객체가 아님', lang), '', lang)
        lang = resolve(loaded.get('language'))
        wrong = []
        for key, value in loaded.items():
            if key not in DEFAULTS:
                continue
            if value_ok(key, value):
                data[key] = value
            else:
                wrong.append(t('{key} 는 {expected}', lang, key=key, expected=_expected(key, lang)))
        _upgrade(data, loaded)
        if wrong:
            # 맞는 값은 쓰고 틀린 값만 기본값으로. 파일을 고칠 때까지 저장하지 않는다 (손으로 쓴 값을 덮어쓰지 않게, D21)
            return data, t('설정 파일의 값 형식이 틀려 그 값은 기본값으로 실행합니다 ({wrong}). 파일을 고칠 때까지 설정은 저장하지 않습니다: {path}',
                           lang, wrong='; '.join(wrong), path=self.path)
        return data, None

    def _error_message(self, detail: str, hint: str, lang: str) -> str:
        return t('설정 파일을 읽지 못해 기본 설정으로 실행합니다 ({detail}).{hint} 파일을 고칠 때까지 설정은 저장하지 않습니다: {path}',
                 lang, detail=detail, hint=hint, path=self.path)

    def _refresh(self) -> None:
        """파일이 밖에서 바뀌었으면 다시 읽는다. 고친 파일이 깨졌으면 들고 있던 값으로 돌고 저장을 멈춘다."""
        if self._signature() == self._disk:
            return
        data, error = self._read()
        self.load_error = error
        if data is not None:
            if data != self.data:
                self.rev += 1
            self.data = data

    def save(self) -> None:
        with self._lock:
            if self.load_error:
                return
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.path.with_suffix('.tmp')
                tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding='utf-8')
                # Windows 는 누가 그 파일을 열고 있으면(백신 검사·편집기·다른 프로그램이 읽는 순간) 바꿔 끼우지 못한다 — 잠깐씩 다시.
                # 그냥 넘기면 메모리에만 남고 파일에는 다음 저장까지 빠진다 (0.112 시나리오 시험이 찾음)
                for wait in (0.02, 0.05, 0.1, 0.2, 0.4, 0):
                    try:
                        os.replace(tmp, self.path)
                        break
                    except PermissionError:
                        if not wait:
                            raise
                        time.sleep(wait)
                self._disk = self._signature()
            except OSError:
                pass  # 설정 저장 실패는 보기 기능에 영향을 주지 않는다

    def _update(self, change: Callable[[dict[str, Any]], bool | None]) -> None:
        """밖에서 고친 값을 먼저 읽어 들이고, 바꾼 뒤 저장한다. change 가 False 를 돌려주면 저장하지 않는다."""
        with self._lock:
            self._refresh()
            if change(self.data) is not False:
                self.save()

    def get(self, key: str) -> Any:
        with self._lock:
            self._refresh()
            return self.data.get(key, DEFAULTS.get(key))

    def update_client(self, patch: dict[str, Any]) -> None:
        def change(data: dict[str, Any]) -> bool:
            keys = [k for k in patch if k in CLIENT_KEYS and value_ok(k, patch[k]) and data.get(k) != patch[k]]
            for key in keys:
                data[key] = patch[key]
            if keys:
                self.rev += 1
            return bool(keys)
        self._update(change)

    def revision(self) -> int:
        """설정의 판 번호 (D159). 밖에서 고친 파일도 여기서 읽어 들인다 (변경 확인이 1초마다 부른다)"""
        with self._lock:
            self._refresh()
            return self.rev

    def set_window(self, width: int, height: int) -> None:
        self._update(lambda data: data.update(window={'width': int(width), 'height': int(height)}))

    def add_recent(self, folder: str) -> None:
        def change(data: dict[str, Any]) -> None:
            norm = os.path.normcase(folder)
            recent = [p for p in data.get('recent') or [] if os.path.normcase(p) != norm]
            data['recent'] = ([folder] + recent)[:MAX_RECENT]
            data['last_folder'] = folder
        self._update(change)

    def set_tabs(self, roots: list[str], active: int = 0) -> None:
        """열어 둔 탭(왼쪽부터 폴더 경로)과 선택된 탭의 순번. 다음 실행에 이대로 되살린다."""
        roots = roots[:MAX_TABS]
        active = active if 0 <= active < len(roots) else 0

        def change(data: dict[str, Any]) -> bool:
            if data.get('tabs') == roots and data.get('active_tab') == active:
                return False
            data['tabs'] = roots
            data['active_tab'] = active
            return True
        self._update(change)

    def set_work_home(self, folder: str | None) -> None:
        """업무 관리의 공통 폴더 (D124). None 이면 비운다. 목록에 같은 폴더가 있으면 뺀다 — 공통 WORK.md 는 과제가 아니다"""
        def change(data: dict[str, Any]) -> None:
            data['work_home'] = folder
            if folder:
                norm = os.path.normcase(folder)
                data['work_folders'] = [p for p in data.get('work_folders') or [] if os.path.normcase(p) != norm]
        self._update(change)

    def add_work_folder(self, folder: str) -> bool:
        """업무 폴더 목록에 더한다 (D124). 이미 있거나 공통 폴더면 그대로. 더했으면 True"""
        norm = os.path.normcase(folder)
        added = False

        def change(data: dict[str, Any]) -> bool:
            nonlocal added
            folders = [p for p in data.get('work_folders') or [] if isinstance(p, str)]
            home = data.get('work_home')
            if any(os.path.normcase(p) == norm for p in folders) or (isinstance(home, str) and os.path.normcase(home) == norm):
                return False
            if len(folders) >= MAX_WORK_FOLDERS:
                return False
            data['work_folders'] = folders + [folder]
            added = True
            return True
        self._update(change)
        return added

    def remove_work_folder(self, folder: str) -> bool:
        """업무 폴더 목록에서 뺀다 (D124 — 파일은 그대로). 뺐으면 True"""
        norm = os.path.normcase(folder)
        removed = False

        def change(data: dict[str, Any]) -> bool:
            nonlocal removed
            folders = [p for p in data.get('work_folders') or [] if isinstance(p, str)]
            kept = [p for p in folders if os.path.normcase(p) != norm]
            if len(kept) == len(folders):
                return False
            data['work_folders'] = kept
            removed = True
            return True
        self._update(change)
        return removed

    def remember_position(self, root: str, doc: str, scroll: int, docs: list[str] | None = None) -> None:
        """프로젝트의 마지막 문서와 스크롤 위치. 문서별 스크롤 위치도 남긴다 (뒤로 가기·다시 열 때).
        docs: 열어 둔 문서 탭들의 문서 (탭 차례, D64 — 없으면 doc 하나). 최근 것이 뒤에 오도록 다시 넣고 오래된 것부터 버린다."""
        def change(data: dict[str, Any]) -> None:
            projects = data.get('projects') if isinstance(data.get('projects'), dict) else {}
            key = os.path.normcase(root)
            entry = projects.pop(key, None)
            scrolls = entry.get('scroll') if isinstance(entry, dict) and isinstance(entry.get('scroll'), dict) else {}
            scrolls.pop(doc, None)
            scrolls[doc] = max(0, int(scroll))
            kept = {'clip': entry['clip']} if isinstance(entry, dict) and isinstance(entry.get('clip'), str) else {}
            projects[key] = {'doc': doc, 'scroll': dict(list(scrolls.items())[-MAX_POSITIONS:]), 'docs': list(docs or [doc])[:MAX_DOC_TABS], **kept}
            data['projects'] = dict(list(projects.items())[-MAX_PROJECTS:])
        self._update(change)

    def forget_docs(self, root: str) -> None:
        """프로젝트의 마지막 문서와 열어 둔 문서 탭 목록을 비운다 — 사용자가 문서 탭을 모두 닫아 폴더 개요만 남았다 (D133).
        다음에 열면 폴더 개요부터. 문서별 스크롤 위치는 둔다 (다시 열 때 읽던 자리)"""
        def change(data: dict[str, Any]) -> None:
            projects = data.get('projects')
            entry = projects.get(os.path.normcase(root)) if isinstance(projects, dict) else None
            if isinstance(entry, dict):
                entry['doc'] = None
                entry['docs'] = []
        self._update(change)

    def remember_clip(self, root: str, file: str) -> None:
        """프로젝트의 지금 담기함(담는 곳)의 파일 이름 — 다시 켜도 정해 둔 곳에 담기게 (D199)"""
        def change(data: dict[str, Any]) -> None:
            projects = data.get('projects') if isinstance(data.get('projects'), dict) else {}
            key = os.path.normcase(root)
            entry = projects.pop(key, None)
            projects[key] = {**(entry if isinstance(entry, dict) else {'doc': None, 'scroll': {}, 'docs': []}), 'clip': file}
            data['projects'] = dict(list(projects.items())[-MAX_PROJECTS:])
        self._update(change)

    def clip_box(self, root: str) -> str:
        """remember_clip 이 적은 것 — 없거나 형식이 틀리면 빈 글"""
        projects = self.get('projects')
        entry = projects.get(os.path.normcase(root)) if isinstance(projects, dict) else None
        file = entry.get('clip') if isinstance(entry, dict) else None
        return file if isinstance(file, str) else ''

    def position(self, root: str) -> dict[str, Any]:
        """{doc, scroll:{문서: 위치}, docs:[열어 둔 문서 탭들의 문서]}. 사용자가 고친 값도 있으므로 형식이 틀린 것은 버린다.
        창을 나누던 때(v0.6)의 기록에 남은 panes·active 는 읽지 않는다 — doc 이 그때 선택된 창의 문서다.
        docs 가 없는 옛 기록은 doc 하나 (문서 탭 — D64)."""
        projects = self.get('projects')
        entry = projects.get(os.path.normcase(root)) if isinstance(projects, dict) else None
        if not isinstance(entry, dict):
            return {'doc': None, 'scroll': {}, 'docs': []}
        doc = entry.get('doc') if isinstance(entry.get('doc'), str) else None
        scrolls = entry.get('scroll') if isinstance(entry.get('scroll'), dict) else {}
        docs = entry.get('docs') if isinstance(entry.get('docs'), list) else []
        docs = list(dict.fromkeys(d for d in docs if isinstance(d, str)))[:MAX_DOC_TABS]
        if doc and doc not in docs:
            docs = (docs + [doc])[-MAX_DOC_TABS:]
        return {'doc': doc, 'scroll': {k: v for k, v in scrolls.items() if is_number(v)}, 'docs': docs}

    def public(self) -> dict[str, Any]:
        with self._lock:
            self._refresh()
            return copy.deepcopy(self.data)
