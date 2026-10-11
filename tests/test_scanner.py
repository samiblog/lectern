from __future__ import annotations

import os
import sys

import pytest

from lectern.scanner import iter_files, natural_key, resolve_inside, scan


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
