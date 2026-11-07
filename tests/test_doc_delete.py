"""문서 삭제 (D104): 트리의 문서만 휴지통으로. 코드·자료·밖의 경로는 받지 않고, 휴지통이 안 되면 파일은 그대로다."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from lectern import editing, trash
from lectern.scanner import DEFAULT_EXCLUDE_DIRS, DEFAULT_HTML_EXCLUDE_DIRS


@pytest.fixture
def sent(monkeypatch):
    """휴지통 대신 지운 파일 이름을 적는다"""
    names: list[str] = []

    def fake(path: Path) -> None:
        names.append(path.name)
        path.unlink()

    monkeypatch.setattr(trash, 'send', fake)
    return names


def delete(root: Path, rel: str) -> None:
    editing.delete_doc(root, rel, DEFAULT_EXCLUDE_DIRS, DEFAULT_HTML_EXCLUDE_DIRS)


def test_sends_a_document(tmp_path: Path, sent: list[str]) -> None:
    (tmp_path / '글.md').write_text('# 글\n', encoding='utf-8')
    (tmp_path / '쪽.html').write_text('<p>쪽</p>', encoding='utf-8')
    delete(tmp_path, '글.md')
    delete(tmp_path, '쪽.html')
    assert sent == ['글.md', '쪽.html']


@pytest.mark.parametrize('name', ['a.py', 'a.csv', 'a.xlsx', 'a.pdf', 'a.png', 'a.txt'])
def test_refuses_code_and_data(tmp_path: Path, sent: list[str], name: str) -> None:
    (tmp_path / name).write_text('x', encoding='utf-8')
    with pytest.raises(editing.EditError) as e:
        delete(tmp_path, name)
    assert e.value.status == 400
    assert (tmp_path / name).exists() and not sent


def test_refuses_html_in_app_source_folder(tmp_path: Path, sent: list[str]) -> None:
    (tmp_path / 'src').mkdir()
    (tmp_path / 'src' / 'index.html').write_text('<p>앱</p>', encoding='utf-8')
    with pytest.raises(editing.EditError):
        delete(tmp_path, 'src/index.html')
    assert not sent


def test_refuses_excluded_folder(tmp_path: Path, sent: list[str]) -> None:
    (tmp_path / 'node_modules').mkdir()
    (tmp_path / 'node_modules' / 'a.md').write_text('# a\n', encoding='utf-8')
    with pytest.raises(editing.EditError):
        delete(tmp_path, 'node_modules/a.md')
    assert not sent


@pytest.mark.parametrize('rel', ['../밖.md', 'a/../../밖.md', '', '.', '없는.md'])
def test_refuses_bad_paths(tmp_path: Path, sent: list[str], rel: str) -> None:
    root = tmp_path / 'proj'
    root.mkdir()
    (tmp_path / '밖.md').write_text('# 밖\n', encoding='utf-8')
    with pytest.raises(editing.EditError):
        delete(root, rel)
    assert (tmp_path / '밖.md').exists() and not sent


def test_refuses_hidden(tmp_path: Path, sent: list[str]) -> None:
    (tmp_path / '.lectern').mkdir()
    (tmp_path / '.lectern' / 'notes.md').write_text('메모\n', encoding='utf-8')
    with pytest.raises(editing.EditError):
        delete(tmp_path, '.lectern/notes.md')
    assert not sent


def test_refuses_program_folder(tmp_path: Path, sent: list[str], monkeypatch) -> None:
    (tmp_path / '예제.md').write_text('# 예제\n', encoding='utf-8')
    monkeypatch.setattr(editing.paths, 'is_protected', lambda p: True)
    with pytest.raises(editing.EditError) as e:
        delete(tmp_path, '예제.md')
    assert e.value.status == 403 and not sent


def test_trash_failure_keeps_the_file(tmp_path: Path, monkeypatch) -> None:
    doc = tmp_path / '글.md'
    doc.write_text('# 글\n', encoding='utf-8')

    def refuse(path: Path) -> None:
        raise trash.TrashError('휴지통 없음')

    monkeypatch.setattr(trash, 'send', refuse)
    with pytest.raises(editing.EditError) as e:
        delete(tmp_path, '글.md')
    assert e.value.status == 409 and e.value.message == '휴지통 없음' and doc.exists()


@pytest.mark.skipif(sys.platform == 'win32', reason='Windows 가 아닐 때만')
def test_no_recycle_bin_elsewhere(tmp_path: Path) -> None:
    doc = tmp_path / '글.md'
    doc.write_text('# 글\n', encoding='utf-8')
    with pytest.raises(trash.TrashError):
        trash.send(doc)
    assert doc.exists()


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows 만')
def test_never_unlinks_on_a_drive_without_bin(tmp_path: Path, monkeypatch) -> None:
    """드라이브가 고정 디스크가 아니면 부르기 전에 멈춘다 (네트워크·이동식은 휴지통 없이 바로 지워진다)"""
    doc = tmp_path / '글.md'
    doc.write_text('# 글\n', encoding='utf-8')
    called: list[Path] = []
    monkeypatch.setattr(trash, '_recycle', lambda p: called.append(p) or (0, False))
    monkeypatch.setattr(trash, 'DRIVE_FIXED', -1)
    with pytest.raises(trash.TrashError):
        trash.send(doc)
    assert doc.exists() and not called
