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
