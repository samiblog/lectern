"""새 폴더와 위치 목록 (D114): 사용자가 이름을 정할 때만, 프로젝트 안에, 덮어쓰지 않고."""
from __future__ import annotations

from pathlib import Path

import pytest

from lectern import editing
from lectern.scanner import DEFAULT_EXCLUDE_DIRS, list_folders


def make(root: Path, parent: str, name: str) -> str:
    return editing.make_folder(root, parent, name, DEFAULT_EXCLUDE_DIRS)


def test_makes_a_folder_at_the_top_and_inside(tmp_path: Path) -> None:
    assert make(tmp_path, '', '자료') == '자료'
    assert make(tmp_path, '자료', '2026') == '자료/2026'
    assert (tmp_path / '자료' / '2026').is_dir()


def test_keeps_what_is_there(tmp_path: Path) -> None:
    (tmp_path / '자료').mkdir()
    (tmp_path / '자료' / 'a.md').write_text('# a\n', encoding='utf-8')
    with pytest.raises(editing.EditError) as e:
        make(tmp_path, '', '자료')
    assert e.value.status == 409
    assert (tmp_path / '자료' / 'a.md').exists()


def test_a_file_of_the_same_name_blocks_it(tmp_path: Path) -> None:
    (tmp_path / '이름').write_text('x', encoding='utf-8')
    with pytest.raises(editing.EditError):
        make(tmp_path, '', '이름')
    assert (tmp_path / '이름').is_file()


@pytest.mark.parametrize('name', ['', '  ', '.숨김', '끝점.', 'a/b', 'a\\b', 'a:b', 'con', 'NUL', 'node_modules', '..'])
def test_refuses_bad_names(tmp_path: Path, name: str) -> None:
    with pytest.raises(editing.EditError):
        make(tmp_path, '', name)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('parent', ['..', '../밖', '없는 폴더', 'node_modules'])
def test_refuses_bad_parents(tmp_path: Path, parent: str) -> None:
    root = tmp_path / 'proj'
    (root / 'node_modules').mkdir(parents=True)
    with pytest.raises(editing.EditError):
        make(root, parent, '새 폴더')
    assert not (tmp_path / '새 폴더').exists()


def test_refuses_the_program_folder(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(editing.paths, 'is_protected', lambda p: True)
    with pytest.raises(editing.EditError) as e:
        make(tmp_path, '', '새 폴더')
    assert e.value.status == 403 and not (tmp_path / '새 폴더').exists()


def test_lists_empty_folders_but_not_hidden_or_excluded(tmp_path: Path) -> None:
    (tmp_path / '빈 폴더').mkdir()
    (tmp_path / '가' / '나').mkdir(parents=True)
    (tmp_path / '.숨김').mkdir()
    (tmp_path / 'node_modules' / '안').mkdir(parents=True)
    (tmp_path / 'a.md').write_text('# a\n', encoding='utf-8')
    assert list_folders(tmp_path) == ['가', '가/나', '빈 폴더']
