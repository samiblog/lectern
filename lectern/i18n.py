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
    '스타일 이름이나 머리글 모양이 올바르지 않습니다': 'The style name or heading shape is not valid',
    '스타일 이름은 {n}자까지입니다 — 점으로 시작하거나 끝나면 안 되고 : * ? " < > | / \\ 를 쓸 수 없습니다': 'A style name is at most {n} characters, cannot start or end with a dot, and cannot use : * ? " < > | / \\',
    '같은 이름의 스타일이 있습니다 — 다른 이름으로 저장하세요': 'A style with this name exists — save under another name',
    '스타일을 저장하지 못했습니다: {why}': 'Could not save the style: {why}',
    '{n}번 장': 'Slide {n}',
    '내 템플릿': 'My templates',
    '{name} 이 링크라서 쓰지 않습니다': '{name} is a link, so it is not written',
    '템플릿 이름은 {n}자까지입니다 — : * ? " < > | / \\ 를 쓸 수 없습니다': 'A template name is at most {n} characters and cannot use : * ? " < > | / \\',
    '템플릿 이름과 글이 올바르지 않습니다': 'The template name or text is not valid',
    '템플릿으로 저장할 글이 없거나 너무 깁니다': 'There is nothing to save as a template, or it is too long',
    '같은 이름의 템플릿이 있습니다 — 다른 이름으로 저장하세요': 'A template with this name exists — save under another name',
    '템플릿을 저장하지 못했습니다: {why}': 'Could not save the template: {why}',
    '같은 이름의 pptx 가 너무 많습니다 — 정리한 뒤 다시 하세요': 'Too many pptx files with this name — tidy them up and try again',
    "pptx 스타일 '{name}' 이 보관소에 없습니다 — 다른 스타일을 고르세요": "The pptx style '{name}' is not in the library — pick another style",
    '제한 시간 안에 끝내지 못했습니다 — 차트가 많으면 Claude 에게 전환을 맡기세요': 'It did not finish in time — with many charts, ask Claude to convert it',
    '전환 프로그램을 띄우지 못했습니다: {why}': 'Could not start the converter: {why}',
    'pptx 를 만들지 못했습니다: {why}': 'Could not make the pptx: {why}',
    '보기만 하는 프로젝트라 pptx 를 만들지 않습니다 — 폴더를 복사해서 여세요': 'This project is view-only, so no pptx is made — copy the folder and open the copy',
    'Lectern 프로그램 폴더 안에서는 메모를 쓰지 않습니다 — 고쳐 보려면 그 폴더를 복사해 여세요': 'Notes are not written inside the Lectern program folder — copy that folder and open the copy',
    '메모 폴더가 링크라 쓰지 않았습니다 — .lectern 을 보통 폴더로 바꾸세요': 'The notes folder is a link, so nothing was written — make .lectern a normal folder',
    '메모 폴더를 만들지 못했습니다: {error}': 'Could not create the notes folder: {error}',
    # sheet.py (엑셀 보기 — D77)
    '엑셀 파일 안의 내용이 너무 큽니다 — 엑셀로 여세요': 'The contents of this Excel file are too large — open it in Excel.',
    '엑셀 파일을 읽지 못했습니다 — 손상되었거나 다른 형식입니다 ({error})': 'Could not read the Excel file — it is damaged or in another format ({error}).',
    '이 형식은 Lectern 에서 보지 못합니다 — .xlsx·.xlsm 만 봅니다. 엑셀로 여세요': 'Lectern cannot show this format — only .xlsx and .xlsm. Open it in Excel.',
    '엑셀 파일이 너무 큽니다 ({n}MB 넘음) — 엑셀로 여세요': 'The Excel file is too large (over {n} MB) — open it in Excel.',
    # server.py
    '열려 있지 않은 프로젝트입니다. 탭이 닫혔을 수 있습니다': 'This project is not open. Its tab may have been closed.',
    'JSON 본문만 받습니다': 'Only JSON request bodies are accepted.',
    '검색어는 {n}자까지입니다': 'Search text can be up to {n} characters.',
    '터미널은 Windows 10(1809) 이상에서만 쓸 수 있습니다': 'The terminal needs Windows 10 (1809) or later.',
    '끝난 터미널입니다': 'This terminal has ended.',
    '셸을 시작하지 못했습니다 ({error}). 설정 파일의 terminal_shell 을 확인하세요':
        'Could not start the shell ({error}). Check terminal_shell in the settings file.',
    'Lectern 프로그램 폴더 안에서는 터미널을 열지 않습니다 — 그 폴더를 다른 곳에 복사해 여세요':
        'Lectern does not open a terminal inside its program folder — copy that folder elsewhere and open the copy.',
    'Lectern 프로그램 폴더 안의 파일은 고치지 않습니다 — 고쳐 보려면 그 폴더를 다른 곳에 복사해 여세요':
        'Lectern does not change files inside its program folder — to try editing, copy that folder elsewhere and open the copy.',
    '한 번에 보낼 수 있는 글은 65536자까지입니다': 'Up to 65536 characters can be sent at once.',
    '제외 폴더 안이 아닙니다': 'This is not inside an excluded folder.',
    '문서와 코드 파일만 편집할 수 있습니다': 'Only document and code files can be edited.',
    '파일이 없습니다 — 그사이 지워졌거나 이름이 바뀌었습니다': 'The file is not there — it was deleted or renamed in the meantime.',
    '읽기 전용 파일이라 저장하지 않았습니다 — 파일 속성에서 읽기 전용을 끄면 저장할 수 있습니다':
        'Not saved because the file is read-only — turn off Read-only in the file properties to save it.',
    '{n}MB 가 넘는 파일은 편집할 수 없습니다': 'Files over {n} MB cannot be edited.',
    '글 파일이 아니라서 편집할 수 없습니다': 'This is not a text file, so it cannot be edited.',
    'EViews 파일은 Windows 인코딩이라 한글을 넣어 저장하지 않았습니다 — 저장하면 UTF-8 로 바뀌어 EViews 에서 글자가 깨집니다':
        'EViews files use the Windows encoding, so this was not saved with Korean text — saving would turn the file into UTF-8 and EViews would show broken characters',
    'UTF-8 이 아닌 파일은 편집할 수 없습니다 (Lectern 은 UTF-8 글만 고칩니다)': 'Files that are not UTF-8 cannot be edited (Lectern only edits UTF-8 text).',
    '편집하는 동안 다른 곳에서 이 파일이 바뀌었습니다': 'This file was changed elsewhere while you were editing it.',
    '저장하지 못했습니다: {error}': 'Could not save: {error}',
    '저장하지 못했습니다: {error}. 고친 내용은 {tmp} 에 남겨 두었습니다': 'Could not save: {error}. Your edited text was kept in {tmp}',
    '저장하지 않은 편집이 있습니다:\n{files}\n\n닫으면 이 내용은 사라집니다. 닫을까요?':
        'There are unsaved edits:\n{files}\n\nClosing will discard them. Close anyway?',
    '독립창의 저장하지 않은 편집을 두기로 해서 닫지 않았습니다': 'Not closed, because you chose to keep the unsaved edits in the separate window',
    # editing.py — 새 문서 (D63)
    '새 문서의 경로가 올바르지 않습니다': 'The path of the new document is not valid.',
    '새 문서는 .md 로 끝나는 이름이어야 합니다 — 점으로 시작하거나 : * ? " < > | 같은 글자가 든 이름은 쓸 수 없습니다':
        'The new document needs a name ending in .md — names starting with a dot or containing characters such as : * ? " < > | cannot be used.',
    '제외 폴더({name}) 안에는 만들지 않습니다 — 트리에 보이지 않습니다': 'Not created inside an excluded folder ({name}) — it would not show in the tree.',
    '폴더가 없습니다 — 새 문서는 이미 있는 폴더에만 만듭니다': 'There is no such folder — a new document is only created in a folder that already exists.',
    '같은 이름의 파일이 있습니다 — 다른 이름으로 만드세요': 'A file with that name already exists — choose another name.',
    '새 문서를 만들지 못했습니다: {error}': 'Could not create the new document: {error}',
    # editing.py — 이름 바꾸기 (D66)
    '파일 경로가 올바르지 않습니다': 'The file path is not valid.',
    '제외 폴더({name}) 안의 파일은 이름을 바꾸지 않습니다': 'Files inside an excluded folder ({name}) are not renamed.',
    '쓸 수 없는 이름입니다 — 점으로 시작하거나 끝나는 이름, / \\ : * ? " < > | 같은 글자가 든 이름은 쓸 수 없습니다':
        'That name cannot be used — names starting or ending with a dot, or containing characters such as / \\ : * ? " < > |, are not allowed.',
    '같은 이름의 파일이 있습니다 — 다른 이름을 고르세요': 'A file with that name already exists — choose another name.',
    '다른 프로그램이 이 파일을 쓰고 있어 이름을 바꾸지 못했습니다 — 그 프로그램에서 닫은 뒤 다시 하세요':
        'Another program is using this file, so it could not be renamed — close it there and try again.',
    '이름을 바꾸지 못했습니다: {error}': 'Could not rename the file: {error}',
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
    '이 컴퓨터에서는 휴지통으로 보낼 수 없습니다 — 파일은 그대로입니다': 'This computer has no Recycle Bin to send it to — the file is unchanged.',
    '이 드라이브에는 휴지통이 없어 지우지 않았습니다 — 탐색기에서 지우세요': 'This drive has no Recycle Bin, so nothing was deleted — delete it in File Explorer.',
    '휴지통으로 보내지 못했습니다: {error}': 'Could not send it to the Recycle Bin: {error}',
    '지우기를 그만두었습니다 — 파일은 그대로입니다': 'Delete was cancelled — the file is unchanged.',
    '휴지통으로 보내지 못했습니다 — 다른 프로그램이 이 파일을 쓰고 있으면 그 프로그램에서 닫은 뒤 다시 하세요': 'Could not send it to the Recycle Bin — if another program is using this file, close it there and try again.',
    '문서만 지웁니다 — 코드와 자료는 지우지 않습니다': 'Only documents can be deleted — code and other files are not.',
    '제외 폴더 안의 문서는 지우지 않습니다': 'Documents inside an excluded folder are not deleted.',
    '그림 파일이 아닙니다 — PNG, JPEG, GIF, WebP 를 붙여 넣으세요': 'That is not an image — paste a PNG, JPEG, GIF or WebP.',
    '그림이 너무 큽니다 — 20MB 까지 넣습니다': 'The image is too large — the limit is 20MB.',
    '{name}-그림': '{name}-images',
    '{name} 폴더를 쓸 수 없습니다 — 이름이 같은 파일이 있습니다': 'Cannot use the {name} folder — a file has the same name.',
    '그림 {n}': 'image {n}',
    '그림을 저장하지 못했습니다: {error}': 'Could not save the image: {error}',
    '그림 폴더가 가득 찼습니다 — 다른 이름의 문서로 옮기세요': 'The image folder is full — move this to a document with another name.',
}
