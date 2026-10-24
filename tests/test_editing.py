"""편집 모드 (D54): 원문 주기·저장 — 줄바꿈·BOM 되살리기, 그사이 바뀐 파일, UTF-8·크기·종류."""
from __future__ import annotations

import pytest

from conftest import write

from lectern import editing
from lectern.editing import EditError, read_source, save_source


def test_read_source_gives_lf_text_and_remembers_newline_and_bom(tmp_path):
    p = tmp_path / 'a.md'
    p.write_bytes(b'\xef\xbb\xbf# \xec\xa0\x9c\xeb\xaa\xa9\r\n\r\nbody\r\n')
    src = read_source(p)
    assert src['text'] == '# 제목\n\nbody\n' and src['newline'] == '\r\n' and src['bom'] is True
    assert src['size'] == p.stat().st_size and len(src['hash']) == 64   # 원문 바이트의 SHA-256 (그사이 바뀌었는지)
    (tmp_path / 'b.py').write_bytes(b'x = 1\n')   # conftest.write 는 Windows 에서 CRLF 로 쓴다
    assert read_source(tmp_path / 'b.py')['newline'] == '\n' and read_source(tmp_path / 'b.py')['bom'] is False


@pytest.mark.parametrize('name, data, status', [
    ('a.csv', b'a,b\n', 400),             # 문서·코드가 아님
    ('a.md', b'\xb0\xa1\xb3\xaa', 400),   # cp949 — UTF-8 이 아님
    ('a.py', b'x\x00y', 400),             # 글 파일이 아님
])
def test_read_source_refuses(tmp_path, name, data, status):
    (tmp_path / name).write_bytes(data)
    with pytest.raises(EditError) as err:
        read_source(tmp_path / name)
    assert err.value.status == status


def test_read_source_refuses_big_files(tmp_path, monkeypatch):
    monkeypatch.setattr(editing, 'MAX_EDIT_BYTES', 10)
    write(tmp_path / 'a.md', 'x' * 11)
    with pytest.raises(EditError) as err:
        read_source(tmp_path / 'a.md')
    assert err.value.status == 413


def test_save_keeps_crlf_and_bom(tmp_path):
    p = tmp_path / 'a.md'
    p.write_bytes(b'\xef\xbb\xbfone\r\ntwo\r\n')
    src = read_source(p)
    r = save_source(p, 'one\nTWO\nthree\n', src['hash'])
    assert p.read_bytes() == b'\xef\xbb\xbfone\r\nTWO\r\nthree\r\n'
    assert r == {'hash': read_source(p)['hash'], 'size': p.stat().st_size}
    assert [x.name for x in tmp_path.iterdir()] == ['a.md']   # 임시 파일은 남지 않는다
    # 받은 수정 시각·크기로 이어서 저장한다. LF 파일은 LF 그대로 (편집기가 CRLF 를 보내도)
    (tmp_path / 'b.py').write_bytes(b'x = 1\n')
    src = read_source(tmp_path / 'b.py')
    save_source(tmp_path / 'b.py', 'x = 2\r\ny = 3\r\n', src['hash'])
    assert (tmp_path / 'b.py').read_bytes() == b'x = 2\ny = 3\n'


def test_save_refuses_when_file_changed_meanwhile_unless_forced(tmp_path):
    import os

    p = tmp_path / 'a.md'
    p.write_bytes('본문\n'.encode())
    st = p.stat()
    src = read_source(p)
    # 같은 크기로, 수정 시각까지 그대로 바뀌어도 (같은 순간의 두 저장 — 수정 시각·크기로는 놓친다) 내용으로 알아챈다
    p.write_bytes('고침\n'.encode())
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns))
    with pytest.raises(EditError) as err:
        save_source(p, 'mine edited\n', src['hash'])
    assert err.value.status == 409 and p.read_bytes() == '고침\n'.encode()
    save_source(p, 'mine edited\n', src['hash'], force=True)
    assert p.read_bytes() == b'mine edited\n'


def test_save_refuses_non_utf8_target_and_wrong_kind(tmp_path):
    p = tmp_path / 'a.md'
    p.write_bytes(b'\xb0\xa1')
    with pytest.raises(EditError):
        save_source(p, 'x', None, force=True)
    assert p.read_bytes() == b'\xb0\xa1'
    write(tmp_path / 'a.txt', 'x')
    with pytest.raises(EditError):
        save_source(tmp_path / 'a.txt', 'y', None, force=True)


def test_save_keeps_file_attributes_and_refuses_read_only_and_missing(tmp_path):
    import os
    import stat
    import sys

    p = tmp_path / 'a.md'
    p.write_bytes(b'# a\n')
    if sys.platform == 'win32':   # 숨김 속성은 그대로 (ReplaceFileW)
        import ctypes

        ctypes.windll.kernel32.SetFileAttributesW(str(p), 0x2)
        save_source(p, '# b\n', read_source(p)['hash'])
        assert p.read_bytes() == b'# b\n' and ctypes.windll.kernel32.GetFileAttributesW(str(p)) & 0x2
        ctypes.windll.kernel32.SetFileAttributesW(str(p), 0x80)
    os.chmod(p, stat.S_IREAD)   # 읽기 전용은 고치지 않는다
    with pytest.raises(EditError) as err:
        save_source(p, '# c\n', read_source(p)['hash'])
    os.chmod(p, stat.S_IREAD | stat.S_IWRITE)
    assert err.value.status == 403 and p.read_bytes() != b'# c\n'
    src = read_source(p)
    p.unlink()   # 편집하는 사이 지워짐 — 다시 만들지 않는다
    with pytest.raises(EditError) as err:
        save_source(p, '# d\n', src['hash'])
    assert err.value.status == 404 and not p.exists()
    assert [x.name for x in tmp_path.iterdir()] == []   # 임시 파일이 남지 않는다


def test_save_follows_the_majority_line_ending(tmp_path):
    # PowerShell 이 CRLF 줄을 더한 LF 파일 — 많은 쪽(LF)으로. 하나 섞였다고 모두 CRLF 로 바꾸지 않는다
    p = tmp_path / 'run.sh'
    p.write_bytes(b'echo a\necho b\r\necho c\n')
    src = read_source(p)
    assert src['newline'] == '\n'
    save_source(p, src['text'] + 'echo d\n', src['hash'])
    assert p.read_bytes() == b'echo a\necho b\necho c\necho d\n'


def test_save_survives_odd_text_and_long_paths(tmp_path):
    p = tmp_path / 'a.md'
    p.write_bytes(b'x\n')
    save_source(p, 'broken \ud800 paste\n', read_source(p)['hash'])   # 짝 없는 대리 문자
    assert p.read_bytes() == b'broken ? paste\n'
    deep = tmp_path / ('d' * 60) / ('e' * 60)
    deep.mkdir(parents=True)
    q = deep / (('f' * (250 - len(str(deep)) - 4)) + '.md')   # 경로가 Windows 의 길이 한도 가까이
    q.write_bytes(b'# long\n')
    save_source(q, '# long 2\n', read_source(q)['hash'])
    assert q.read_bytes() == b'# long 2\n'


def test_failed_save_keeps_the_edited_text_in_the_temp_file(tmp_path, monkeypatch):
    from lectern import editing

    p = tmp_path / 'a.md'
    p.write_bytes(b'original\n')
    src = read_source(p)

    def broken_swap(tmp, path):   # ReplaceFileW 가 원래 파일을 치운 뒤 새 파일을 옮기지 못함 (ERROR_UNABLE_TO_MOVE_REPLACEMENT)
        path.unlink()
        raise PermissionError(1176, 'ReplaceFileW', str(path))

    real_write = type(p).write_bytes

    def refuse_write(self, data):
        if self == p:
            raise PermissionError(13, 'Permission denied')
        return real_write(self, data)

    monkeypatch.setattr(editing, '_swap', broken_swap)
    monkeypatch.setattr(type(p), 'write_bytes', refuse_write)
    monkeypatch.setattr(editing.time, 'sleep', lambda s: None)
    with pytest.raises(EditError) as err:
        save_source(p, 'edited\n', src['hash'])
    kept = [x for x in tmp_path.iterdir() if x.name.startswith('.lectern-')]
    assert err.value.status == 500 and len(kept) == 1 and str(kept[0]) in err.value.message
    assert kept[0].read_bytes() == b'edited\n'   # 고친 내용은 남아 있다


def test_new_doc_only_in_existing_visible_folders_with_md_names(tmp_path):
    """새 문서 (D63): 이미 있는 폴더에 .md 하나 — 숨김·제외 폴더, 밖, 이상한 이름은 안 된다"""
    root = tmp_path.resolve()
    (root / 'reports').mkdir()
    (root / '.claude').mkdir()
    (root / 'node_modules').mkdir()
    exclude = frozenset({'node_modules'})
    assert editing.new_doc_path(root, 'reports/요약.md', exclude) == root / 'reports' / '요약.md'
    assert editing.new_doc_path(root, '새 문서.md', exclude) == root / '새 문서.md'
    for rel, status in [('nope/a.md', 404), ('.claude/a.md', 404), ('node_modules/a.md', 400), ('../a.md', 400),
                        ('reports/a.txt', 400), ('reports/a.html', 400), ('reports/.a.md', 400), ('reports/a?.md', 400),
                        ('reports/con.md', 400), ('reports/ .md', 400), ('reports//a.md', 400), ('reports/a.md.', 400)]:
        with pytest.raises(EditError) as err:
            editing.new_doc_path(root, rel, exclude)
        assert err.value.status == status, rel


def test_rename_file_in_same_folder_only_visible_files_never_overwrites(tmp_path):
    """이름 바꾸기 (D66): 같은 폴더 안에서 이름만, 보이는 파일만, 같은 이름이 있으면 바꾸지 않는다 (대소문자만은 된다)"""
    root = tmp_path.resolve()
    (root / 'docs').mkdir()
    (root / 'docs' / 'a.md').write_bytes(b'# a\n')
    (root / 'docs' / 'b.md').write_bytes(b'# b\n')
    (root / 'data.csv').write_bytes(b'x\n')
    (root / '.claude').mkdir()
    (root / '.claude' / 'n.md').write_bytes(b'x')
    (root / 'node_modules').mkdir()
    (root / 'node_modules' / 'p.js').write_bytes(b'x')
    exclude = frozenset({'node_modules'})
    assert editing.rename_file(root, 'docs/a.md', '요약.md', exclude) == root / 'docs' / '요약.md'
    assert (root / 'docs' / '요약.md').read_bytes() == b'# a\n' and not (root / 'docs' / 'a.md').exists()
    assert editing.rename_file(root, 'data.csv', ' 자료.txt ', exclude) == root / '자료.txt'   # 앞뒤 빈칸은 뗀다, 확장자도 바꿀 수 있다
    assert editing.rename_file(root, 'docs/b.md', 'B.md', exclude).name == 'B.md'   # 대소문자만
    assert sorted(p.name for p in (root / 'docs').iterdir()) == ['B.md', '요약.md']
    assert editing.rename_file(root, 'docs/B.md', 'B.md', exclude) == root / 'docs' / 'B.md'   # 그대로면 아무것도 하지 않는다
    for rel, name, status in [('docs/요약.md', 'B.md', 409), ('docs/요약.md', 'b.MD', 409),   # 이미 있음 (대소문자만 다른 것도)
                              ('docs/nope.md', 'x.md', 404), ('.claude/n.md', 'x.md', 404), ('node_modules/p.js', 'q.js', 400),
                              ('../x.md', 'y.md', 400), ('docs', 'd2', 404),   # 폴더는 바꾸지 않는다
                              ('docs/요약.md', '../x.md', 400), ('docs/요약.md', 'sub/x.md', 400), ('docs/요약.md', '.숨김.md', 400),
                              ('docs/요약.md', 'a?.md', 400), ('docs/요약.md', 'con.md', 400), ('docs/요약.md', 'a.md.', 400),
                              ('docs/요약.md', '', 400), ('docs/요약.md', '.md', 400)]:
        with pytest.raises(EditError) as err:
            editing.rename_file(root, rel, name, exclude)
        assert err.value.status == status, (rel, name)
    assert (root / 'docs' / '요약.md').read_bytes() == b'# a\n' and (root / 'docs' / 'B.md').read_bytes() == b'# b\n'   # 덮어쓰지 않았다


def test_create_source_writes_lf_utf8_and_never_overwrites(tmp_path):
    p = tmp_path / '새.md'
    r = editing.create_source(p, '# 새 문서\r\n\r\n본문\n')
    assert p.read_bytes() == '# 새 문서\n\n본문\n'.encode() and r['size'] == len(p.read_bytes())
    assert save_source(p, '# 고침\n', r['hash'])   # 만든 뒤에는 보통 저장 — 만들 때의 hash 로
    with pytest.raises(EditError) as err:
        editing.create_source(p, 'x')
    assert err.value.status == 409 and p.read_bytes() == b'# \xea\xb3\xa0\xec\xb9\xa8\n'   # 덮어쓰지 않는다
