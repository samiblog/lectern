"""화면에 나가는 서버 문구의 언어 (D46).

설정 language: auto(Windows 표시 언어) | ko | en. 문구는 한국어 문장을 그대로 열쇠로 쓴다 — t('끝난 터미널입니다') 는
영어면 EN 의 문장, 한국어면 그대로. 값을 끼울 자리는 {이름}: t('폴더가 아닙니다: {path}', path=p).
화면(web/js/i18n.js)도 같은 방식이고, 서버가 정한 언어를 index.html 의 <html lang> 으로 넘긴다.
새 문구는 t() 로 감싸고 EN 에 영어를 넣는다 (tests/test_i18n.py 가 빠진 것과 안 쓰는 것을 잡는다).
"""
from __future__ import annotations

import ctypes
import locale
import os
import re
import sys
from collections.abc import Callable
from functools import lru_cache
from typing import Any

LANGS = ('ko', 'en')
_setting: Callable[[], Any] = lambda: 'auto'   # 설정의 language 를 읽는 함수 (AppState 가 정한다)
_SLOT = re.compile(r'\{(\w+)\}')


@lru_cache(maxsize=1)
def system_language() -> str:
    """Windows 표시 언어가 한국어면 ko, 아니면 en (Windows 가 아니면 LANG·로캘로)"""
    if sys.platform == 'win32':
        try:
            return 'ko' if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x12 else 'en'   # 0x12: LANG_KOREAN
        except (AttributeError, OSError):
            pass
    name = os.environ.get('LANG') or locale.getlocale()[0] or ''
    return 'ko' if name.lower().startswith(('ko', 'korean')) else 'en'


def resolve(setting: Any) -> str:
    """설정 값 → 쓸 언어 (auto·모르는 값이면 Windows 표시 언어)"""
    return setting if setting in LANGS else system_language()


def use_setting(getter: Callable[[], Any]) -> None:
    global _setting
    _setting = getter


def language() -> str:
    return resolve(_setting())


def t(ko: str, lang: str | None = None, **values: Any) -> str:
    """ko 문구를 지금 언어로. lang: 이 언어로 (설정을 읽기 전의 문구 — config.py)"""
    text = EN.get(ko, ko) if (lang or language()) == 'en' else ko
    return _SLOT.sub(lambda m: str(values[m[1]]) if m[1] in values else m[0], text) if values else text


def N_(ko: str) -> str:
    """번역할 문구라고 표시만 한다 (모듈을 읽을 때 정하는 상수 — 쓰는 곳에서 t() 로 바꾼다)"""
    return ko


EN: dict[str, str] = {
    # server.py
    '열려 있지 않은 프로젝트입니다. 탭이 닫혔을 수 있습니다': 'This project is not open. Its tab may have been closed.',
    'JSON 본문만 받습니다': 'Only JSON request bodies are accepted.',
    '검색어는 {n}자까지입니다': 'Search text can be up to {n} characters.',
    '터미널은 Windows 10(1809) 이상에서만 쓸 수 있습니다': 'The terminal needs Windows 10 (1809) or later.',
    '끝난 터미널입니다': 'This terminal has ended.',
    '셸을 시작하지 못했습니다 ({error}). 설정 파일의 terminal_shell 을 확인하세요':
        'Could not start the shell ({error}). Check terminal_shell in the settings file.',
    '한 번에 보낼 수 있는 글은 65536자까지입니다': 'Up to 65536 characters can be sent at once.',
    '제외 폴더 안이 아닙니다': 'This is not inside an excluded folder.',
    '문서와 코드 파일만 편집할 수 있습니다': 'Only document and code files can be edited.',
    '{n}MB 가 넘는 파일은 편집할 수 없습니다': 'Files over {n} MB cannot be edited.',
    '글 파일이 아니라서 편집할 수 없습니다': 'This is not a text file, so it cannot be edited.',
    'UTF-8 이 아닌 파일은 편집할 수 없습니다 (Lectern 은 UTF-8 글만 고칩니다)': 'Files that are not UTF-8 cannot be edited (Lectern only edits UTF-8 text).',
    '편집하는 동안 다른 곳에서 이 파일이 바뀌었습니다': 'This file was changed elsewhere while you were editing it.',
    '저장하지 못했습니다: {error}': 'Could not save: {error}',
    '저장하지 않은 편집이 있습니다:\n{files}\n\n닫으면 이 내용은 사라집니다. 닫을까요?':
        'There are unsaved edits:\n{files}\n\nClosing will discard them. Close anyway?',
    # state.py
    '폴더가 아닙니다: {path}': 'Not a folder: {path}',
    '탭은 {n}개까지 열 수 있습니다. 안 쓰는 탭을 닫고 다시 여세요': 'You can open up to {n} tabs. Close a tab you are not using and try again.',
    # terminal.py, conpty.py
    '명령 프롬프트': 'Command Prompt',
    '{what} 실패: {error}': '{what} failed: {error}',
    '이 Windows 에는 의사 콘솔(ConPTY)이 없습니다 (Windows 10 1809 이상 필요)':
        'This Windows has no pseudo console (ConPTY). Windows 10 1809 or later is needed.',
    'CreatePseudoConsole 실패 (0x{code})': 'CreatePseudoConsole failed (0x{code})',
    # config.py
    'true 또는 false': 'true or false',
    '숫자': 'a number',
    '"글자"': '"text"',
    '["이름", ...] 목록': 'a list like ["name", ...]',
    '{ } 객체': 'a { } object',
    '맞는 형식': 'the right type',
    '파일을 읽을 수 없음 ({error})': 'cannot read the file ({error})',
    ' 경로 안의 \\ 는 \\\\ 로 씁니다.': ' Write \\ in paths as \\\\.',
    '{line}행 {col}열: {error}': 'line {line}, column {col}: {error}',
    '맨 바깥이 { } 객체가 아님': 'the outermost value is not a { } object',
    '{key} 는 {expected}': '{key} must be {expected}',
    '설정 파일의 값 형식이 틀려 그 값은 기본값으로 실행합니다 ({wrong}). 파일을 고칠 때까지 설정은 저장하지 않습니다: {path}':
        'Some values in the settings file have the wrong type, so their defaults are used ({wrong}). '
        'Settings will not be saved until the file is fixed: {path}',
    '설정 파일을 읽지 못해 기본 설정으로 실행합니다 ({detail}).{hint} 파일을 고칠 때까지 설정은 저장하지 않습니다: {path}':
        'Could not read the settings file, so default settings are used ({detail}).{hint} '
        'Settings will not be saved until the file is fixed: {path}',
    # app.py
    '폴더를 열 수 없습니다: {error}': 'Cannot open the folder: {error}',
}
