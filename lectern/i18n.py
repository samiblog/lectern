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
    '같은 이름의 html 이 너무 많습니다 — 정리한 뒤 다시 하세요': 'Too many html files with this name — tidy them up and try again',
    '전환한 html 이 아닙니다 — 슬라이드 창에서 다시 전환하세요': 'This is not a converted html — convert again from the slide window',
    'Lectern 슬라이드가 아닙니다 — 맨 앞 설정에 marp: true 가 있어야 합니다': 'This is not a Lectern slides document — the front matter needs marp: true',
    'Lectern 프로그램 폴더 안에는 만들지 않습니다 — 그 폴더를 다른 곳에 복사해 여세요': 'Nothing is made inside the Lectern program folder — copy that folder elsewhere and open the copy',
    'html 이 300MB 를 넘습니다 — 큰 그림을 줄인 뒤 다시 하세요': 'The html is over 300MB — make large images smaller and try again',
    'html 을 저장하지 못했습니다: {error}': 'Could not save the html: {error}',
    'Lectern 이 이번에 만든 html 만 브라우저로 엽니다 — 탐색기에서 여세요': 'Only html files Lectern made in this session open in the browser — open it from File Explorer',
    '보기만 하는 프로젝트라 html 을 만들지 않습니다 — 폴더를 복사해서 여세요': 'This project is view-only, so no html is made — copy the folder and open the copy',
    'Lectern 프로그램 폴더 안에서는 메모를 쓰지 않습니다 — 고쳐 보려면 그 폴더를 복사해 여세요': 'Notes are not written inside the Lectern program folder — copy that folder and open the copy',
    '메모 폴더가 링크라 쓰지 않았습니다 — .lectern 을 보통 폴더로 바꾸세요': 'The notes folder is a link, so nothing was written — make .lectern a normal folder',
    '메모 폴더를 만들지 못했습니다: {error}': 'Could not create the notes folder: {error}',
    '담기함': 'Clip box',
    '담기함의 차례 — name(이름)·time(마지막에 고친 것부터)': 'Order of the clip boxes — name or time (last edited first)',
    '담기함 폴더를 만들지 못했습니다: {error}': 'Could not create the clip box folder: {error}',
    '담기함 폴더가 링크라 쓰지 않았습니다 — .lectern 과 clips 를 보통 폴더로 바꾸세요': 'The clip box folder is a link, so nothing was written — make .lectern and clips ordinary folders',
    'Lectern 프로그램 폴더 안에서는 담기함을 쓰지 않습니다 — 고쳐 보려면 그 폴더를 복사해 여세요': 'Clip boxes are not written inside the Lectern program folder — copy that folder and open the copy to try it',
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
    '문서·코드와 csv·tsv·txt 파일만 편집할 수 있습니다': 'Only documents, code and csv, tsv or txt files can be edited.',
    '글자가 깨진 UTF-16 파일이라 편집할 수 없습니다': 'This UTF-16 file has broken characters, so it cannot be edited.',
    'UTF-8·UTF-16·CP949 어느 것으로도 읽히지 않는 파일이라 편집할 수 없습니다': 'This file cannot be read as UTF-8, UTF-16 or CP949, so it cannot be edited.',
    '이 파일은 CP949(엑셀이 저장한 한국어 CSV 등)라 {chars} 를 저장할 수 없습니다 — 그 글자를 빼고 저장하세요': 'This file is CP949 (such as a Korean CSV saved by Excel), so {chars} cannot be saved — remove those characters and save again.',
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
    '만들 수 있는 것은 코드 파일(.py·.js·.json 등)과 자료 파일(.csv·.tsv·.txt)입니다 — 이름 끝에 확장자를 쓰세요':
        'You can create code files (.py, .js, .json and so on) and data files (.csv, .tsv, .txt) — end the name with an extension',
    '파일을 만들지 못했습니다: {error}': 'Could not create the file: {error}',
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
    'PDF 는 보기만 합니다 — 지우려면 탐색기에서 지우세요': 'PDFs are view-only — delete it in File Explorer',
    '문서만 지웁니다 — 코드와 자료는 지우지 않습니다': 'Only documents can be deleted — code and other files are not.',
    '제외 폴더 안의 문서는 지우지 않습니다': 'Documents inside an excluded folder are not deleted.',
    '그림 파일이 아닙니다 — PNG, JPEG, GIF, WebP 를 붙여 넣으세요': 'That is not an image — paste a PNG, JPEG, GIF or WebP.',
    '그림이 너무 큽니다 — 20MB 까지 넣습니다': 'The image is too large — the limit is 20MB.',
    '{name}-그림': '{name}-images',
    '{name} 폴더를 쓸 수 없습니다 — 이름이 같은 파일이 있습니다': 'Cannot use the {name} folder — a file has the same name.',
    '그림 {n}': 'image {n}',
    '그림을 저장하지 못했습니다: {error}': 'Could not save the image: {error}',
    '그림 폴더가 가득 찼습니다 — 다른 이름의 문서로 옮기세요': 'The image folder is full — move this to a document with another name.',
    '제외 폴더 안에는 폴더를 만들지 않습니다': 'Folders are not created inside an excluded folder.',
    '폴더가 없습니다 — 그사이 지워졌거나 이름이 바뀌었습니다': 'The folder is not there — it was deleted or renamed in the meantime.',
    '{name} 은 제외 폴더 이름이라 목록에 나오지 않습니다 — 다른 이름을 쓰세요': '{name} is an excluded folder name and would not be listed — use another name.',
    '같은 이름이 있습니다 — 다른 이름을 쓰세요': 'That name is taken — use another one.',
    '폴더를 만들지 못했습니다: {error}': 'Could not create the folder: {error}',
    '업무 폴더 목록에 없는 폴더입니다 — 업무 현황을 다시 열어 고르세요': 'That folder is not in the work folder list — open the work board again and pick it there.',
    'WORK.md 가 없습니다 — 그사이 지워졌거나 폴더가 옮겨졌습니다': 'There is no WORK.md — it was deleted or the folder moved in the meantime.',
    '폴더를 고르세요': 'Pick a folder.',
    '폴더의 전체 경로가 필요합니다': 'The full path of the folder is needed.',
    'Lectern 프로그램 폴더 안은 업무 관리에 쓰지 않습니다 — 예제는 다른 곳에 복사해 쓰세요': 'Folders inside the Lectern program folder are not used for work management — copy the samples elsewhere to try them.',
    '그 폴더에 WORK.md 가 없습니다': 'That folder has no WORK.md.',
    'PDF 파일 (*.pdf)': 'PDF files (*.pdf)',
    'html 파일 (*.html;*.htm)': 'html files (*.html;*.htm)',
    'Word 문서 (*.docx)': 'Word documents (*.docx)',
    '만든 Word 파일이 없습니다 — 창을 닫고 다시 여세요': 'There is no Word file made — close the window and open it again',
    "Word 양식 '{name}' 이 보관소에 없습니다 — 다른 양식을 고르세요": "The Word template '{name}' is not in the templates folder — pick another template",
    'Word 파일을 만들지 못했습니다: {why}': 'Could not make the Word file: {why}',
    '내보낸 html 이 아닙니다 — 창을 닫고 다시 여세요': 'This is not an exported html — close the window and open it again',
    '미리 본 html 이 없습니다 — 창을 닫고 다시 여세요': 'There is no previewed html — close the window and open it again',
    '{name} 을 쓰지 못했습니다 — 다른 프로그램이 그 파일을 열고 있으면 닫고 다시 저장하세요': 'Could not write {name} — if another program has the file open, close it and save again',
    'Lectern 프로그램 폴더 안에는 저장하지 않습니다 — 다른 폴더를 고르세요': 'Lectern does not save inside its program folder — pick another folder.',
    '같은 이름의 폴더가 있습니다 — 다른 이름을 고르세요': 'A folder with that name exists — pick another name.',
    '저장할 폴더가 없습니다: {path}': 'The folder to save in does not exist: {path}',
    '{name} 을 쓰지 못했습니다 — PDF 보기 프로그램이 그 파일을 열고 있으면 닫고 다시 저장하세요': 'Could not write {name} — if a PDF viewer has the file open, close it and save again.',
    '{name} 을 쓰지 못했습니다: {error}': 'Could not write {name}: {error}',
    'PDF 를 만드는 데 {n}초가 넘게 걸려 멈췄습니다': 'Stopped making the PDF after more than {n} seconds.',
    'PDF 를 만들지 못했습니다: {error}': 'Could not make the PDF: {error}',
    '창이 없습니다': 'There is no window.',
    # 설정 원문 보기의 설명 줄 (D160 — rawfiles.py)
    '$…$ 수식을 그림': 'Render $…$ math',
    "'pptx 로 전환' 창": "the 'Convert to pptx' window",
    "'pptx 로 전환'의 기본 pptx 스타일 — 설정 폴더 pptx-styles 의 파일 이름": "Default pptx style for 'Convert to pptx' — a file name in the pptx-styles settings folder",
    "'문서' 묶음에서 펼친 하위 묶음 — all·md·deck·html·pdf·work·marks·tasks": "Sub-group open under 'Documents' — all, md, deck, html, pdf, work, marks, tasks",
    'API 키를 내주는 명령': 'Command that hands out the API key',
    'CSV 표 위의 통계 줄': 'Statistics line above CSV tables',
    'md 문서 표의 칸 맞춤 — auto(글 왼쪽·숫자 오른쪽)·report(보고서식 — 머리행·짧은 열 가운데)': 'Cell alignment in md document tables — auto (text left, numbers right) or report (Report style — header row and short columns centered)',
    'Claude Code 가 묻지 않고 해도 되는 일·물어야 하는 일·하면 안 되는 일': 'What Claude Code may do without asking, must ask about, and must not do',
    'Claude Code 개인 설정': 'Claude Code personal settings',
    'Claude Code 를 띄울 때 넣는 환경 변수 — 비밀 값이 있을 수 있다': 'Environment variables set when Claude Code starts — may hold secret values',
    'Claude Code 설정 (나만)': 'Claude Code settings (just me)',
    'Claude Code 설정 (함께)': 'Claude Code settings (shared)',
    'Claude Code 의 개인 설정 — 모든 프로젝트에 듣는다. 프로젝트의 .claude/settings.json·settings.local.json 이 앞선다. 비밀 값이 있을 수 있으니 화면을 나눌 때 조심한다': "Claude Code's personal settings — apply to every project. A project's .claude/settings.json and settings.local.json come first. May hold secret values; take care when sharing your screen",
    'Claude Code 의 설정 — 뜻은 Claude Code 설명서의 settings 장': "A Claude Code setting — see the settings chapter of Claude Code's documentation",
    'Claude Code 의 출력 스타일 — 켜면 아래 본문이 Claude Code 의 시스템 지시를 대신한다. --- 사이는 설정, 그 밑은 Claude 에게 주는 글': "A Claude Code output style — when on, the body below replaces Claude Code's system instructions. Between --- are settings; below is the text given to Claude",
    'Claude 가 이 스킬을 쓸지 정할 때 읽는 설명 — 이런 요청이면 이 스킬을 쓴다': 'The description Claude reads to decide whether to use this skill — requests like these use it',
    'JSON 으로 읽지 못하는 파일입니다 — Lectern 은 기본값으로 돌고, 파일을 고칠 때까지 설정을 저장하지 않습니다': 'This file cannot be read as JSON — Lectern runs on defaults and does not save settings until the file is fixed',
    'Lectern 설정': 'Lectern settings',
    'Lectern 안의 업무 알림': 'Work alerts inside Lectern',
    'Lectern 에 든 것': 'Included in Lectern',
    'Lectern 에 든 글쓰기 스타일 — 설치하면 이 파일이 ~/.claude/output-styles 로 복사된다': 'Writing style included in Lectern — installing copies this file to ~/.claude/output-styles',
    'Lectern 에 든 스킬 — 설치하면 이 폴더가 개인 스킬 폴더로 복사된다': 'Skill included in Lectern — installing copies this folder to the personal skills folder',
    "Lectern 의 설정 — 모든 폴더와 창에 듣는다. 설정 창·툴바에서 바꾸면 Lectern 이 이 파일에 쓰고, 손으로 고치려면 설정 창 '고급'의 '설정 파일 열기'": "Lectern's settings — apply to every folder and window. Lectern writes this file when you change things in Settings or the toolbar; to edit it by hand, use 'Open settings file' under 'Advanced' in Settings",
    'Lectern 이 기록 — 고칠 일 없음': 'Recorded by Lectern — nothing to edit',
    'Lectern 이 쓰지 않는 열쇠입니다': 'A key Lectern does not use',
    'PowerPoint·Word 스킬을 넣을 곳 — all(개인 스킬 폴더)·folder(그 폴더)': 'Where the PowerPoint and Word skills go — all (personal skills folder) or folder (that folder)',
    'WORK.md 가 있는 폴더들 — 업무 현황이 모아 보인다 (경로만)': 'Folders with a WORK.md — the work board gathers them (paths only)',
    'md 문서 본문의 폭 배율 (0.8~2, 10 이면 칸 가득)': 'Body width of md documents (0.8–2; 10 fills the pane)',
    'md 문서 왼쪽 여백의 원문 줄 번호 (Alt+L)': 'Source line numbers in the left margin of md documents (Alt+L)',
    'true 면 Claude Code 의 개발 지침을 남긴다 — 없거나 false 면 뺀다': "true keeps Claude Code's development guidance — missing or false drops it",
    '{cli} — 개인 폴더': '{cli} — personal folder',
    "{cli} 가 모든 프로젝트에서 읽는 Lectern 작성 안내 요약 — 설정 창 'Lectern 알려 주기'의 요청 글로 넣는다": "The Lectern writing guide summary {cli} reads in every project — added with the request from 'Teach … about Lectern' in Settings",
    '{cli} 가 모든 프로젝트에서 읽는 개인 지시 파일 — Lectern 작성 안내 요약은 그 안의 한 절': 'The personal instruction file {cli} reads in every project — the Lectern writing guide summary is one section of it',
    '{doc} · 기본 {default} · 바꾸는 곳: {where}': '{doc} · default {default} · changed in: {where}',
    '{doc} · 바꾸는 곳: {where}': '{doc} · changed in: {where}',
    '검색에서 문서를 찾음': 'Search finds documents',
    '검색에서 자료를 이름으로 찾음': 'Search finds other files by name',
    '검색에서 코드를 찾음': 'Search finds code',
    '글쓰기 스타일: {name}': 'Writing style: {name}',
    '글쓰기 스타일을 켤 곳 — folder(그 폴더)·all(모든 폴더의 기본)·off(그 폴더에서 끄기)': 'Where the writing style is on — folder (that folder), all (default in every folder) or off (off in that folder)',
    '기본 모델': 'Default model',
    '내 문체 노트': 'Voice note',
    '내 문체 노트 — 글을 쓰거나 다듬을 때 Claude Code 가 참고한다 (모든 프로젝트)': 'Voice note — Claude Code refers to it when writing or polishing (every project)',
    '내보내기 창': 'the export window',
    '넣기 창에서 최근 넣은 것 (다섯까지)': 'Recently inserted in the insert window (up to five)',
    '특수 문자 창에서 최근 넣은 문자 (열둘까지)': 'Characters recently inserted from the special characters window (up to twelve)',
    '늘 깊이 생각하기': 'Always think deeply',
    '대화 기록을 남겨 두는 날 수': 'Days to keep conversation history',
    '더한 플러그인 마켓플레이스': 'Added plugin marketplaces',
    '마지막으로 연 폴더 — 탭 기록이 없던 옛 설정이면 이 폴더를 연다': 'The last folder opened — opened if an older settings file has no tab record',
    '목차': 'contents',
    '목차 폭 (px) — null 이면 기본 폭': 'Contents width (px) — null for the default width',
    '목차에서 감춘 구성 요소 종류 — table·figure·box·diagram·code·math': 'Element kinds hidden from the contents — table, figure, box, diagram, code, math',
    '문단 안의 줄바꿈을 화면에서도 줄바꿈으로 — 끄면 표준 Markdown': 'Show line breaks inside paragraphs on screen too — off for standard Markdown',
    "md 문서 점검 — 깨진 틀·보고서의 틀을 상태줄의 '점검 N곳'으로": "md document check — broken and report structure as 'Check N' in the status bar",
    '문서 점검에 글버릇(긴 문단·문장·칸, 줄 끝 공백, 탭)도': 'Writing habits (long paragraphs, sentences and cells, trailing spaces, tabs) in the document check too',
    '문서 글자 크기 배율 (0.8~2, 1 이 100%)': 'Document text size (0.8–2; 1 is 100%)',
    '문서 속 인터넷(https) 그림을 불러옴 — 끄면 링크로만, 인터넷에 요청하지 않음': 'Load web (https) images in documents — when off they are links only and nothing is requested from the internet',
    "문서 스타일 — auto(시스템의 밝음·어두움) 또는 스타일 이름. 'user:' 로 시작하면 내 스타일": "Document style — auto (the system's light or dark) or a style name. Names starting with 'user:' are your own styles",
    '묻지 않고 해도 되는 일': 'Done without asking',
    '사이드바': 'sidebar',
    "사이드바 '파일' 탭에서 펼친 묶음 — docs·code·others·folder(폴더 구조 그대로)": "Group open in the sidebar's 'Files' tab — docs, code, others or folder (the folder tree as it is)",
    '사이드바 목록에 파일 이름 대신 문서 제목': 'Document titles instead of file names in sidebar lists',
    '사용설명서·예제 가이드를 따로 창에서 — auto(앱 창은 따로 창, 브라우저 개발 모드는 덮어서)·on·off (D181)':
        'User guide and example guide in their own windows — auto (own windows in the app, covering the window in browser dev mode), on or off (D181)',
    '사이드바 목록의 차례 — name(이름)·time(시간)·type(형식). 폴더가 먼저': 'Order of sidebar lists — name, time or type. Folders first',
    '사이드바 보이기 (Ctrl+B)': 'Show the sidebar (Ctrl+B)',
    '사이드바 폭 (px) — null 이면 기본 폭': 'Sidebar width (px) — null for the default width',
    '선택돼 있던 프로젝트 탭의 순번 (0부터)': 'Index of the selected project tab (from 0)',
    "설정 창 'AI 도구'": "Settings 'AI tool'",
    "설정 창 '보기'": "Settings 'View'",
    "설정 창 '업무'": "Settings 'Work'",
    "설정 창 '인쇄·내보내기'": "Settings 'Print and export'",
    "설정 창 '일반'": "Settings 'General'",
    "설정 창 '터미널'": "Settings 'Terminal'",
    "설정 창 '편집'": "Settings 'Editing'",
    '설정 창에서 마지막에 고른 분류 — 다음에 그 분류로 연다': 'Section last chosen in Settings — Settings opens there next time',
    '설정 형식의 판 — 옛 설정을 새 판으로 바꿀 때 본다': 'Settings format version — used to upgrade old settings',
    '스킬 — 요청이 맞으면 Claude 가 SKILL.md 를 읽고 그대로 한다. 같은 폴더의 scripts 는 그 안내가 돌리는 프로그램': 'Skill — when a request fits, Claude reads SKILL.md and follows it. The scripts in the same folder are the programs those instructions run',
    '스킬 이름': 'Skill name',
    '스킬: {name}': 'Skill: {name}',
    '스킬의 라이선스': "The skill's licence",
    '스타일 목록에 보이는 설명': 'Description shown in the style list',
    '스타일 목록을 묶는 방식 — use(용도별)·mood(분위기별)·tone(밝기별)': 'How the style list is grouped — use, mood or tone',
    '스타일 이름 — /output-style 목록과 설정 값 outputStyle 에 쓰인다': 'Style name — used in the /output-style list and as the outputStyle value',
    '슬라이드 갤러리에서 최근 쓴 템플릿 (묶음과 이름)': 'Templates used recently in the slide gallery (set and name)',
    '슬라이드 창의 스타일 (메인 창과 따로)': 'Style of slide windows (separate from the main window)',
    '슬라이드 창의 툴바': "the slide window's toolbar",
    '아래 상태줄을 그리는 명령': 'Command that draws the status line at the bottom',
    '아래 터미널 높이 (px) — null 이면 기본': 'Height of the terminal below (px) — null for the default',
    '업무 관리의 공통 폴더': 'Common folder for work management',
    '열어 둔 프로젝트 탭 (왼쪽부터) — 다음 실행에 되살린다': 'Open project tabs (from the left) — restored next time',
    '오른쪽 목차 보이기': 'Show the contents on the right',
    '오른쪽 터미널 폭 (px) — null 이면 기본': 'Width of the terminal on the right (px) — null for the default',
    '오른쪽 터미널의 셸 전체 경로 — null 이면 Windows PowerShell': 'Full path of the shell in the right-hand terminal — null for Windows PowerShell',
    '이 스킬이 묻지 않고 쓸 수 있는 도구': 'Tools this skill may use without asking',
    '이 이름의 폴더 안 html 은 문서로 보지 않음 — src·public 등에 더한다': 'html inside folders with these names is not treated as documents — added to src, public and the rest',
    "이 파일에서만 — 설정 창 '고급'의 '설정 파일 열기'": "this file only — 'Open settings file' under 'Advanced' in Settings",
    '이 폴더 — {name}': 'This folder — {name}',
    '이 폴더를 함께 쓰는 사람과 나누는 Claude Code 설정 (git 에 올린다)': 'Claude Code settings shared with people who use this folder (committed to git)',
    '이 폴더에서 나만 쓰는 Claude Code 설정 — /output-style 로 고른 값이 여기에 들어간다. 가장 앞선다': 'Claude Code settings for this folder, just for you — values chosen with /output-style go here. These come first',
    '인쇄·PDF 바닥 쪽 번호': 'Page numbers at the foot of printed pages and PDFs',
    '인쇄·PDF 본문 글꼴 — serif(명조)·sans(고딕)': 'Body font for printing and PDF — serif or sans',
    '인쇄·PDF 여백 — normal·narrow·wide·custom(아래 print_margin_mm)': 'Print · PDF margins — normal, narrow, wide or custom (print_margin_mm below)',
    "여백 '직접' 의 숫자 — 위·오른쪽·아래·왼쪽 mm (0~80)": 'Numbers for custom margins — top, right, bottom, left in mm (0–80)',
    '인쇄·PDF 쪽 머리 — 2쪽부터 문서 제목과 날짜': 'Running head for printing and PDF — the document title and date from page 2',
    '읽는 화면의 vi 키 (j·k·dd·i …)': 'vi keys in the reading view (j, k, dd, i …)',
    '작성 안내 요약': 'Writing guide summary',
    '작성 안내 요약을 넣을 곳 — all(개인 폴더, 모든 폴더에 듣는다)·folder(그 폴더)': 'Where the writing guide summary goes — all (personal folder, applies in every folder) or folder (that folder)',
    '작업 폴더 밖에서 더 읽고 쓸 수 있는 폴더': 'Folders outside the working folder that may also be read and written',
    '전체 편집기의 키 — default(Esc 로 닫기)·vim': 'Keys of the full editor — default (Esc closes) or vim',
    '정한 때(도구를 쓰기 전·뒤 등)에 저절로 돌리는 명령': 'Commands run automatically at set moments (before or after a tool is used, and so on)',
    '창 크기 (px) — 다음 실행에 이 크기로': 'Window size (px) — used next time',
    '처음 권한 방식': 'Initial permission mode',
    '최근 변경에 문서를 보임': 'Recent changes shows documents',
    '최근 변경에 자료를 보임': 'Recent changes shows other files',
    '최근 변경에 코드를 보임': 'Recent changes shows code',
    '최근 쓴 md 문서 스타일 (최신순)': 'md document styles used recently (newest first)',
    '최근 연 프로젝트 폴더 (최신순, 열 개까지)': 'Project folders opened recently (newest first, up to ten)',
    '출력 스타일 — 이 파일이 듣는 곳의 글쓰기 방식. Lectern 의 글쓰기 스타일을 켜면 이 값이 된다. 폴더의 값이 개인 값보다 앞선다': "Output style — the way of writing where this file applies. Turning on Lectern's writing style sets this value. A folder's value comes before the personal one",
    '커밋에 Claude 공동 저자 줄을 넣을지': 'Whether commits get a Claude co-author line',
    '켜 둔 프로젝트 MCP 서버': 'Project MCP servers turned on',
    '켜 둔 플러그인': 'Plugins turned on',
    '코드 파일을 열 편집기의 전체 경로 — null 이면 VS Code(code)': 'Full path of the editor that opens code files — null for VS Code (code)',
    '터미널 경계·머리줄': 'terminal border and header',
    '터미널 글자 크기 (px, 10~24)': 'Terminal text size (px, 10–24)',
    '터미널 색을 문서 스타일에 맞춤 — 끄면 늘 어둡게': 'Match terminal colours to the document style — when off, always dark',
    '터미널 자리 — auto(창이 세로로 길면 아래)·side·bottom': 'Where the terminal sits — auto (below when the window is tall), side or bottom',
    '터미널에서 쓰는 AI 도구 — claude·codex·antigravity·opencode·any(여럿). 화면의 이름과 요청 글이 따른다': 'AI tool used in the terminal — claude, codex, antigravity, opencode or any (several). Names on screen and requests follow it',
    '툴바': 'toolbar',
    "트리에서 뺄 폴더 이름 — 기본 제외 폴더에 더한다 ('자료' 목록에는 접혀 나온다)": "Folder names to leave out of the tree — added to the default excluded folders (they show folded in the 'Other files' list)",
    '파일에 없는 설정은 기본값으로 돈다: {keys}': 'Settings missing from the file run on defaults: {keys}',
    '폴더를 열 때 트리의 첫 단계 폴더를 펼쳐 둠': 'Expand the first level of folders in the tree when a folder opens',
    '폴더를 열면 마지막에 보던 문서와 위치로': 'Opening a folder returns to the last document and position',
    '표 막대': 'the table bar',
    '프로젝트마다 마지막 문서·열어 둔 문서 탭·문서별 스크롤 위치·지금 담기함 (스무 프로젝트까지)': 'For each project: the last document, open document tabs and the scroll position of each document (up to twenty projects)',
    '프로젝트의 MCP 서버를 묻지 않고 모두 켜기': 'Turn on all project MCP servers without asking',
    '하면 안 되는 일': 'Must not do',
    '할 때마다 묻는 일': 'Asked about each time',
    '형식이 틀려 기본값으로 돌고 있습니다': 'The value has the wrong form, so the default is used',
    '화면 언어 — auto(Windows 표시 언어)·ko·en. 바꾸면 화면을 다시 불러온다': 'Display language — auto (Windows display language), ko or en. Changing it reloads the screen',
    '고른 글쓰기 스타일 — research(리서치 글쓰기)·brief(업무 보고)·academic(학술 글)·plain(쉬운 설명), mine:파일 이름(내 스타일)': 'The chosen writing style — research (Research writing), brief (Business report), academic (Academic writing), plain (Plain explanation), or mine:file name (your own style)',
}
