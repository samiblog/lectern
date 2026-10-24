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
    assert src['size'] == p.stat().st_size and src['mtime_ns'] == str(p.stat().st_mtime_ns)   # 글자 (JS 수의 정밀도)
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
    r = save_source(p, 'one\nTWO\nthree\n', src['mtime_ns'], src['size'])
    assert p.read_bytes() == b'\xef\xbb\xbfone\r\nTWO\r\nthree\r\n'
    assert r == {'mtime_ns': str(p.stat().st_mtime_ns), 'size': p.stat().st_size}
    assert [x.name for x in tmp_path.iterdir()] == ['a.md']   # 임시 파일은 남지 않는다
    # 받은 수정 시각·크기로 이어서 저장한다. LF 파일은 LF 그대로 (편집기가 CRLF 를 보내도)
    (tmp_path / 'b.py').write_bytes(b'x = 1\n')
    src = read_source(tmp_path / 'b.py')
    save_source(tmp_path / 'b.py', 'x = 2\r\ny = 3\r\n', src['mtime_ns'], src['size'])
    assert (tmp_path / 'b.py').read_bytes() == b'x = 2\ny = 3\n'


def test_save_refuses_when_file_changed_meanwhile_unless_forced(tmp_path):
    import os
    import time

    p = tmp_path / 'a.md'
    write(p, 'mine\n')
    src = read_source(p)
    write(p, 'theirs — Claude Code 가 고침\n')
    os.utime(p, ns=(time.time_ns(), time.time_ns() + 5_000_000_000))
    with pytest.raises(EditError) as err:
        save_source(p, 'mine edited\n', src['mtime_ns'], src['size'])
    assert err.value.status == 409 and p.read_text(encoding='utf-8').startswith('theirs')
    save_source(p, 'mine edited\n', src['mtime_ns'], src['size'], force=True)
    assert p.read_text(encoding='utf-8') == 'mine edited\n'


def test_save_refuses_non_utf8_target_and_wrong_kind(tmp_path):
    p = tmp_path / 'a.md'
    p.write_bytes(b'\xb0\xa1')
    st = p.stat()
    with pytest.raises(EditError):
        save_source(p, 'x', str(st.st_mtime_ns), st.st_size, force=True)
    assert p.read_bytes() == b'\xb0\xa1'
    write(tmp_path / 'a.txt', 'x')
    st = (tmp_path / 'a.txt').stat()
    with pytest.raises(EditError):
        save_source(tmp_path / 'a.txt', 'y', str(st.st_mtime_ns), st.st_size)
