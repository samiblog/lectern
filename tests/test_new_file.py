"""새 코드·자료 파일 (D177): 사용자가 '만들기'에서 이름을 정한 빈 파일 하나 — 프로젝트 안의 이미 있는 폴더에, 받는 확장자만, 덮어쓰지 않고.
CSV 는 UTF-8 BOM 과 머리행(있으면), TSV 는 머리행만, 코드·텍스트는 빈 파일."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from conftest import write
from lectern import editing, paths
from lectern.config import Config
from lectern.scanner import DEFAULT_EXCLUDE_DIRS
from lectern.server import create_app
from lectern.state import AppState

BOM = b'\xef\xbb\xbf'


def place(root: Path, rel: str) -> Path:
    return editing.new_file_path(root, rel, DEFAULT_EXCLUDE_DIRS)


@pytest.mark.parametrize('name, kind', [('정리.py', 'code'), ('a.JS', 'code'), ('설정.json', 'code'), ('q.sql', 'code'), ('run.ps1', 'code'),
                                        ('표.csv', 'data'), ('표.TSV', 'data'), ('메모.txt', 'data')])
def test_kinds_it_makes(name: str, kind: str) -> None:
    assert editing.new_file_kind(name) == kind


@pytest.mark.parametrize('name', ['a.md', 'a.html', 'a.htm', 'a.ipynb', 'package.lock', 'a.exe', 'a.dll', 'a.zip', 'a.xlsx', 'a.log', 'a.pdf', '확장자없음'])
def test_kinds_it_does_not_make(name: str) -> None:
    assert editing.new_file_kind(name) is None


def test_first_bytes() -> None:
    assert editing.new_file_bytes('a.py') == b'' and editing.new_file_bytes('a.txt', ['x']) == b''
    assert editing.new_file_bytes('a.csv') == BOM   # 머리행이 없어도 BOM — 그 뒤 편집 모드가 그대로 둔다 (D171)
    assert editing.new_file_bytes('a.csv', ['날짜', ' 품목 ', 'a,b', 'q"x']) == BOM + '날짜,품목,"a,b","q""x"\r\n'.encode('utf-8')
    assert editing.new_file_bytes('a.csv', ['', '  ']) == BOM   # 빈 열 이름뿐이면 머리행 없이
    assert editing.new_file_bytes('a.tsv', ['가', '나\t다']) == '가\t나 다\r\n'.encode('utf-8')   # 열 이름 안의 탭·줄바꿈은 빈칸으로
    assert editing.new_file_bytes('a.tsv') == b''


def test_places_in_existing_folders(tmp_path: Path) -> None:
    (tmp_path / '분석').mkdir()
    assert place(tmp_path, '정리.py') == tmp_path / '정리.py'
    assert place(tmp_path, '분석\\표.csv') == tmp_path / '분석' / '표.csv'
    with pytest.raises(editing.EditError) as e:
        place(tmp_path, '없는 폴더/a.py')
    assert e.value.status == 404


@pytest.mark.parametrize('rel', ['', '.env.py', '끝점.py.', 'a:b.py', 'con.py', 'NUL.txt', '../밖.py', 'a/../b.py', 'node_modules/a.js', '.숨김/a.py', 'a.md', 'a.exe'])
def test_refuses_bad_paths(tmp_path: Path, rel: str) -> None:
    root = tmp_path / 'proj'
    (root / 'node_modules').mkdir(parents=True)
    (root / '.숨김').mkdir()
    with pytest.raises(editing.EditError):
        place(root, rel)


def test_does_not_overwrite(tmp_path: Path) -> None:
    write(tmp_path / '표.csv', '원래,내용\n')
    with pytest.raises(editing.EditError) as e:
        editing.create_file(place(tmp_path, '표.csv'), BOM)
    assert e.value.status == 409
    assert (tmp_path / '표.csv').read_text(encoding='utf-8') == '원래,내용\n'
    if sys.platform == 'win32':   # 대소문자만 다른 이름도 같은 파일 (Windows) — 다른 체계에서는 다른 파일이라 만들어진다
        with pytest.raises(editing.EditError):
            editing.create_file(place(tmp_path, '표.CSV'), b'')
        assert (tmp_path / '표.csv').read_text(encoding='utf-8') == '원래,내용\n'


def test_refuses_the_program_folder(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(editing.paths, 'is_protected', lambda p: True)
    with pytest.raises(editing.EditError) as e:
        editing.create_file(tmp_path / 'a.py', b'')
    assert e.value.status == 403 and not (tmp_path / 'a.py').exists()


def test_api(tmp_path: Path) -> None:
    root = tmp_path / 'proj'
    write(root / 'README.md', '# 프로젝트\n')
    write(root / '분석' / 'a.md', '# a\n')
    (root / '빈 폴더').mkdir()
    st = AppState(Config(), mode='browser')
    try:
        pid = st.open(root.resolve()).id
        c = create_app(st).test_client()
        r = c.post('/api/new-file', json={'p': pid, 'path': '분석/정리.py'})
        assert r.status_code == 200 and r.get_json() == {'path': '분석/정리.py', 'kind': 'code'}
        assert (root / '분석' / '정리.py').read_bytes() == b''
        r = c.post('/api/new-file', json={'p': pid, 'path': '빈 폴더/표.csv', 'header': ['날짜', '금액']})
        assert r.get_json() == {'path': '빈 폴더/표.csv', 'kind': 'data'}
        assert (root / '빈 폴더' / '표.csv').read_bytes() == BOM + b'\xeb\x82\xa0\xec\xa7\x9c,\xea\xb8\x88\xec\x95\xa1\r\n'
        # 만든 CSV 는 편집 모드가 BOM 과 CRLF 를 그대로 두고 고친다 (D171)
        src = c.get(f'/api/source?p={pid}&path=빈 폴더/표.csv').get_json()
        assert src['text'] == '날짜,금액\n'
        saved = c.post('/api/save', json={'p': pid, 'path': '빈 폴더/표.csv', 'text': '날짜,금액\n2026-11-19,100\n', 'hash': src['hash']})
        assert saved.status_code == 200
        assert (root / '빈 폴더' / '표.csv').read_bytes() == BOM + '날짜,금액\r\n2026-11-19,100\r\n'.encode('utf-8')
        # 머리행이 없는 CSV — BOM 만. 편집 모드로 열고 저장해도 BOM 이 남는다
        assert c.post('/api/new-file', json={'p': pid, 'path': '빈.csv'}).status_code == 200
        src = c.get(f'/api/source?p={pid}&path=빈.csv').get_json()
        assert src['text'] == ''
        assert c.post('/api/save', json={'p': pid, 'path': '빈.csv', 'text': '가,나\n', 'hash': src['hash']}).status_code == 200
        assert (root / '빈.csv').read_bytes().startswith(BOM + '가,나'.encode('utf-8'))
        # 덮어쓰지 않음·받지 않는 것
        before = (root / 'README.md').read_bytes()
        assert c.post('/api/new-file', json={'p': pid, 'path': '분석/정리.py'}).status_code == 409
        assert c.post('/api/new-file', json={'p': pid, 'path': 'README.md'}).status_code == 400
        assert (root / 'README.md').read_bytes() == before
        assert c.post('/api/new-file', json={'p': pid, 'path': 'a.exe'}).status_code == 400
        assert c.post('/api/new-file', json={'p': pid, 'path': '../밖.py'}).status_code == 400
        assert not (tmp_path / '밖.py').exists()
        assert c.post('/api/new-file', json={'p': pid, 'path': 'a.csv', 'header': 'x'}).status_code == 400
        assert c.post('/api/new-file', json={'p': pid, 'path': 'a.csv', 'header': [1]}).status_code == 400
        assert c.post('/api/new-file', json={'p': pid, 'path': 3}).status_code == 400
        assert c.post('/api/new-file', json={'p': 'nope', 'path': 'x.py'}).status_code in (400, 404)
        assert not (root / 'a.csv').exists() and not (root / 'x.py').exists()
    finally:
        st.close()


def test_api_in_the_program_folder(tmp_path: Path, monkeypatch) -> None:
    prog = tmp_path / 'prog'
    write(prog / 'samples' / 'README.md', '# 예제\n')
    monkeypatch.setattr(paths, 'protected_dirs', lambda: [prog.resolve()])
    st = AppState(Config(), mode='browser')
    try:
        pid = st.open((prog / 'samples').resolve()).id
        c = create_app(st).test_client()
        assert c.post('/api/new-file', json={'p': pid, 'path': 'a.py'}).status_code == 403
        assert sorted(x.name for x in (prog / 'samples').iterdir()) == ['README.md']
    finally:
        st.close()
