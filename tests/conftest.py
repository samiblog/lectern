from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def write(path: Path, text: str = '# 제목\n\n본문\n') -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return path


@pytest.fixture(autouse=True)
def isolated_config(tmp_path_factory, monkeypatch):
    """테스트가 실제 %APPDATA% 설정을 건드리지 않도록 한다."""
    monkeypatch.setenv('LECTERN_CONFIG_DIR', str(tmp_path_factory.mktemp('config')))


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """숨김·제외·빈 폴더가 섞인 예시 프로젝트."""
    root = tmp_path / 'proj'
    write(root / 'README.md', '# 프로젝트\n\n설명 문단입니다.\n')
    write(root / 'CLAUDE.md', '# Claude 지침\n')
    write(root / 'docs' / '2-b.md', '# 둘\n')
    write(root / 'docs' / '10-a.md', '# 열\n')
    write(root / 'docs' / 'sub' / 'deep.md', '---\ntitle: 깊은 문서\ndescription: frontmatter 설명\n---\n본문\n')
    write(root / 'docs' / 'img.svg', '<svg xmlns="http://www.w3.org/2000/svg"/>')
    write(root / '.hidden.md', '# 숨김\n')
    write(root / '.claude' / 'notes.md', '# 숨김 폴더\n')
    write(root / 'node_modules' / 'lib' / 'README.md', '# 제외\n')
    write(root / 'Build' / 'out.md', '# 제외 (대소문자 무시)\n')
    write(root / 'empty' / 'note.txt', 'md 없음')
    write(root / 'src' / 'app.py', 'print(1)\n')
    return root.resolve()
