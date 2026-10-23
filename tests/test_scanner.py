from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from conftest import write

from lectern.scanner import iter_files, list_dir, natural_key, resolve_inside, scan, scan_others


def paths(nodes):
    return [n['path'] for n in iter_files(nodes)]


def test_scan_excludes_hidden_excluded_and_empty(project):
    tree = scan(project)
    found = paths(tree)
    assert 'README.md' in found and 'CLAUDE.md' in found
    assert '.hidden.md' not in found
    assert not any(p.startswith(('.claude', 'node_modules', 'Build', 'empty', 'src')) for p in found)
    top_dirs = [n['name'] for n in tree if n['type'] == 'dir']
    assert top_dirs == ['docs']


def test_scan_order_dirs_first_then_natural(project):
    docs = next(n for n in scan(project) if n['name'] == 'docs')
    assert [n['name'] for n in docs['children']] == ['sub', '2-b.md', '10-a.md']


def test_scan_includes_titles_and_mtime(project):
    files = {n['path']: n for n in iter_files(scan(project))}
    assert files['README.md']['title'] == '프로젝트'
    assert files['docs/sub/deep.md']['title'] == '깊은 문서'
    assert files['README.md']['mtime'] > 0


def test_scan_subfolder_keeps_root_relative_paths(project):
    nodes = scan(project, rel='docs')
    assert 'docs/sub/deep.md' in paths(nodes)


def test_scan_extra_exclude(project):
    found = paths(scan(project, exclude={'docs'}))
    assert not any(p.startswith('docs/') for p in found)


@pytest.mark.skipif(not hasattr(os, 'symlink'), reason='symlink 미지원')
def test_scan_skips_symlinks(project, tmp_path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'x.md').write_text('# 밖', encoding='utf-8')
    try:
        os.symlink(outside, project / 'link', target_is_directory=True)
    except OSError:
        pytest.skip('symlink 권한 없음')
    assert not any(p.startswith('link/') for p in paths(scan(project)))


@pytest.mark.skipif(sys.platform != 'win32', reason='정션은 Windows 전용')
def test_scan_skips_junctions(project, tmp_path):
    import _winapi   # 정션은 관리자 권한 없이 만들 수 있어 Windows에서 늘 돈다 (심볼릭 링크 테스트와 달리)

    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'x.md').write_text('# 밖', encoding='utf-8')
    junctions = [project / 'to-outside', project / 'docs' / 'loop']
    _winapi.CreateJunction(str(outside), str(junctions[0]))
    _winapi.CreateJunction(str(project), str(junctions[1]))   # 상위 폴더를 가리키는 순환
    try:
        found = paths(scan(project))
        assert not any(p.startswith(('to-outside/', 'docs/loop/')) for p in found)
        assert 'docs/2-b.md' in found
        assert resolve_inside(project, 'to-outside/x.md') is None
    finally:
        for j in junctions:
            os.rmdir(j)   # 정션만 지운다 (대상 폴더는 그대로)


def test_natural_key():
    assert sorted(['10장', '2장', '1장'], key=natural_key) == ['1장', '2장', '10장']


def test_resolve_inside(project):
    assert resolve_inside(project, '') == project
    assert resolve_inside(project, 'docs/2-b.md') == project / 'docs' / '2-b.md'
    assert resolve_inside(project, '../x.md') is None
    assert resolve_inside(project, 'docs/../../x.md') is None
    assert resolve_inside(project, '.hidden.md') is None
    assert resolve_inside(project, '.claude/notes.md') is None
    assert resolve_inside(project, str(project.parent / 'other.md')) is None
    assert resolve_inside(project, 'a\x00b') is None
    # 제외 폴더는 트리에는 안 나오지만 링크로는 열 수 있다 (숨김이 아니므로)
    assert resolve_inside(project, 'node_modules/lib/README.md') is not None


def test_resolve_inside_does_not_touch_paths_outside(project, monkeypatch):
    # \\host\share 를 resolve() 하면 Windows 가 그 서버에 접속한다 (NTLM 인증이 새 나감). 글자만 보고 먼저 거른다
    touched = []
    real = Path.resolve
    monkeypatch.setattr(Path, 'resolve', lambda self, *a, **k: touched.append(str(self)) or real(self, *a, **k))
    for rel in ('\\\\evil.example\\share\\x.png', '//evil.example/share/x.png', '\\\\?\\UNC\\evil.example\\s\\x',
                'C:\\Windows\\win.ini', '/etc/passwd', '../../x.md', 'docs/../../x.md'):
        assert resolve_inside(project, rel) is None, rel
    assert touched == []
    assert resolve_inside(project, 'docs/./2-b.md') == project / 'docs' / '2-b.md'


def test_html_docs_and_source_folders(project):
    write(project / 'reports' / 'r.html', '<title>보고서</title><p>요약</p>')
    write(project / 'src' / 'index.html', '<html></html>')        # 앱 소스 — 문서로 보지 않음
    write(project / 'web' / 'notes.md', '# md 는 그대로')
    write(project / 'web' / 'app.html', '<p>앱</p>')
    kinds = {n['path']: n['kind'] for n in iter_files(scan(project))}
    assert kinds['reports/r.html'] == 'html' and kinds['README.md'] == 'markdown'
    assert 'src/index.html' not in kinds and 'web/app.html' not in kinds and kinds['web/notes.md'] == 'markdown'
    assert [n['path'] for n in iter_files(scan(project, rel='web'))] == ['web/notes.md']   # 하위 폴더 개요도 같게
    assert 'web/app.html' in {n['path'] for n in iter_files(scan(project, html_exclude=()))}


def test_scan_others_lists_non_documents(project):
    write(project / 'src' / 'index.html', '<title>앱</title>')                 # 소스 폴더의 html 은 문서가 아니다
    write(project / 'docs' / 'r.html', '<title>보고서</title>')                 # 트리에 보이는 html 은 문서
    write(project / 'data' / '표.csv', 'a,b\n1,2\n')
    write(project / 'data' / '.secret.txt', 'x')
    write(project / 'node_modules' / 'lib' / 'index.js', 'x')
    (project / 'data' / 'run.exe').write_bytes(b'MZ')
    nodes, count, truncated = scan_others(project)
    found = paths(nodes)
    assert found == ['data/run.exe', 'data/표.csv', 'docs/img.svg', 'empty/note.txt', 'src/app.py', 'src/index.html']
    assert count == 6 and truncated is False
    # 폴더 먼저, 자연 정렬. 제외 폴더(Build·node_modules)는 접힌 채로 실린다 (D49 — 안은 펼칠 때 list_dir)
    assert [n['name'] for n in nodes if n['type'] == 'dir'] == ['Build', 'data', 'docs', 'empty', 'node_modules', 'src']
    files = {n['path']: n for n in iter_files(nodes)}
    assert files['data/표.csv']['size'] == len('a,b\n1,2\n'.encode()) or files['data/표.csv']['size'] > 0
    # 두 번 누르면 어떻게 열리는지: 기본 앱 / 편집기 / 탐색기에서 선택만 (실행하지 않음)
    assert (files['data/표.csv']['open'], files['src/app.py']['open'], files['data/run.exe']['open']) == ('default', 'editor', 'reveal')


def test_scan_others_folds_excluded_folders(project):
    # 제외 폴더는 안을 훑지 않고(비었는지도 보지 않고) 접힌 노드로만 — 파일 수에 넣지 않는다. 숨김 폴더는 싣지 않는다
    write(project / 'node_modules' / 'lib' / 'index.js', 'x')
    (project / 'dist').mkdir()                          # 빈 제외 폴더
    write(project / 'build2' / 'x.txt', 'x')            # 이름이 비슷한 보통 폴더
    write(project / '.cache' / 'dist' / 'x.txt', 'x')   # 숨김 폴더 안
    nodes, count, _ = scan_others(project)
    excluded = {n['path']: n for n in nodes if n.get('excluded')}
    assert set(excluded) == {'Build', 'dist', 'node_modules'}
    assert all(n['children'] is None and n['type'] == 'dir' for n in excluded.values())
    assert count == len(paths(nodes)) and 'build2/x.txt' in paths(nodes)
    assert not any(p.startswith(('node_modules/', 'Build/', '.claude')) for p in paths(nodes))


def test_list_dir_reads_one_level(project):
    write(project / 'node_modules' / 'lib' / 'sub' / 'a.js', 'x')
    write(project / 'node_modules' / 'lib' / '.cache', 'x')
    nodes, truncated = list_dir(project, 'node_modules')
    assert [(n['path'], n['type'], n['children']) for n in nodes] == [('node_modules/lib', 'dir', None)] and not truncated
    nodes, _ = list_dir(project, 'node_modules/lib')
    # 하위 폴더는 다시 접힌 채로, 문서·코드도 종류를 나누지 않고 모두. 숨김은 뺀다
    assert [(n['path'], n['type']) for n in nodes] == [('node_modules/lib/sub', 'dir'), ('node_modules/lib/README.md', 'file')]
    assert all(n['excluded'] for n in nodes) and nodes[1]['open'] and nodes[1]['size'] > 0
    for i in range(4):
        write(project / 'dist' / f'{i}.txt', 'x')
    nodes, truncated = list_dir(project, 'dist', limit=2)
    assert len(nodes) == 2 and truncated


def test_scan_others_stops_at_limit(project):
    for i in range(5):
        write(project / 'many' / f'{i}.txt', 'x')
    nodes, count, truncated = scan_others(project, limit=3)
    assert count == 3 and truncated is True and len(paths(nodes)) == 3
