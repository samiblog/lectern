"""md 문서를 Word(docx)로 (D146) — 사용자가 내보내기 창에서 형식 'Word' 를 고를 때만.

만드는 것은 스킬의 build_docx.py 가 한다 (pptx 로 전환과 같은 길 — 정해진 프로그램을 인자로만 부르고 셸을 거치지 않는다).
결과는 임시 폴더에 만들어 바로 메모리로 옮기고 지운다. 디스크에 쓰는 것은 사용자가 저장 대화상자에서 고른 곳 하나뿐이다
(pdfexport.save_kept). Word 양식은 Lectern 전체가 함께 쓰는 설정 폴더 docx-styles 에 두고 읽기만 한다.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from .i18n import t
from .paths import config_dir, program_dir, skills_dir

TIMEOUT = 300
SUFFIXES = ('.dotx', '.docx')
_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)   # 콘솔 프로그램이라 창이 번쩍이지 않게


class ExportError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def styles_dir() -> Path:
    """Word 양식 보관소 (설정 폴더의 docx-styles)"""
    return config_dir() / 'docx-styles'


def list_styles() -> list[dict[str, str]]:
    """보관소의 양식 (.dotx·.docx). Word 가 열어 둔 잠금 파일(~$…)과 숨김 이름은 뺀다. 이름은 확장자를 뗀 파일 이름"""
    folder = styles_dir()
    try:
        files = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in SUFFIXES and not p.name.startswith(('~$', '.')))
    except OSError:
        return []
    return [{'name': p.stem, 'file': p.name} for p in files]


def style_path(name: Any) -> Path | None:
    """보관소의 양식 하나 — 파일 이름이나 확장자를 뗀 이름으로. 보관소 밖·다른 형식은 None"""
    if not isinstance(name, str) or not name or any(c in name for c in '\\/:') or name.startswith('.'):
        return None
    for s in list_styles():
        if name in (s['name'], s['file']):
            return styles_dir() / s['file']
    return None


def _command() -> list[str]:
    script = skills_dir() / 'lectern-to-docx' / 'scripts' / 'build_docx.py'
    folder = program_dir()
    return [str(folder / 'lectern-skill.exe') if folder else sys.executable, str(script)]


def build(md: Path, style: Any) -> tuple[bytes, dict[str, Any]]:
    """md 문서를 docx 바이트로. style 이 있으면 보관소의 그 양식으로, 없으면 Lectern 의 기본 보고서 양식.
    (바이트, build_docx 의 보고 {figures, notes})"""
    args: list[str] = []
    if style:
        path = style_path(style)
        if path is None:
            raise ExportError(404, t("Word 양식 '{name}' 이 보관소에 없습니다 — 다른 양식을 고르세요", name=style))
        args = ['--template', str(path)]
    with tempfile.TemporaryDirectory(prefix='lectern-docx-') as tmp:
        out = Path(tmp) / 'out.docx'
        try:
            r = subprocess.run([*_command(), str(md), '--out', str(out), *args], capture_output=True, text=True, encoding='utf-8', errors='replace',
                               timeout=TIMEOUT, creationflags=_NO_WINDOW, cwd=str(md.parent))
        except subprocess.TimeoutExpired:
            raise ExportError(504, t('제한 시간 안에 끝내지 못했습니다 — 차트가 많으면 Claude 에게 전환을 맡기세요')) from None
        except OSError as exc:
            raise ExportError(500, t('전환 프로그램을 띄우지 못했습니다: {why}', why=exc.strerror or exc)) from None
        report = next((json.loads(line) for line in reversed(r.stdout.split('\n')) if line.startswith('{"docx"')), None)
        if r.returncode or report is None or not out.is_file():
            why = (r.stderr or r.stdout).strip().split('\n')[-1][:300]
            raise ExportError(500, t('Word 파일을 만들지 못했습니다: {why}', why=why))
        data = out.read_bytes()
    return data, {'figures': report.get('figures', 0), 'notes': [str(n) for n in report.get('notes') or []]}
