"""프로젝트 폴더 스캔과 경로 안전 검사.

트리에서 빠지는 것
- 이름이 '.'으로 시작하는 파일·폴더 (.git, .claude, .venv …)
- Windows 숨김(HIDDEN)·시스템(SYSTEM) 속성 파일·폴더
- 심볼릭 링크와 정션 (순환·프로젝트 밖 참조 방지)
- 제외 폴더 (node_modules, __pycache__ … + 설정의 exclude_dirs)
- 문서(.md, .html)가 하나도 없는 폴더
- html 은 앱 소스·빌드 결과인 경우가 많아, src·public·static·templates·web·www·frontend·out 폴더 안에서는
  문서로 보지 않는다 (md 는 그대로 보인다). 설정 html_exclude_dirs 로 이름을 더한다 (D27)
"""
from __future__ import annotations

import os
import re
import stat
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from .docinfo import doc_info

DOC_TYPES = {'.md': 'markdown', '.markdown': 'markdown', '.html': 'html', '.htm': 'html'}
DEFAULT_HTML_EXCLUDE_DIRS = frozenset({'src', 'public', 'static', 'templates', 'web', 'www', 'frontend', 'out'})
DEFAULT_EXCLUDE_DIRS = frozenset({
    'node_modules', '__pycache__', 'venv', 'env', 'dist', 'build', 'target',
    'site-packages', 'htmlcov',
})
_HIDDEN_ATTRS = getattr(stat, 'FILE_ATTRIBUTE_HIDDEN', 0x2) | getattr(stat, 'FILE_ATTRIBUTE_SYSTEM', 0x4)
_JUNCTION_TAG = getattr(stat, 'IO_REPARSE_TAG_MOUNT_POINT', 0xA0000003)

Node = dict[str, Any]


def natural_key(name: str) -> list:
    """'2장' < '10장' 순서가 되도록 숫자 부분을 정수로 비교한다."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', name)]


def doc_kind(name: str) -> str | None:
    """'markdown' | 'html' | None (문서가 아님)"""
    return DOC_TYPES.get(os.path.splitext(name)[1].lower())


def has_hidden_attr(st: os.stat_result) -> bool:
    # st_file_attributes 는 Windows에만 있다. 다른 OS에서는 점(.) 규칙만 적용된다.
    return bool(getattr(st, 'st_file_attributes', 0) & _HIDDEN_ATTRS)


def _is_link(entry: os.DirEntry) -> bool:
    """심볼릭 링크 또는 정션. 정션은 reparse tag 로 본다 (DirEntry.is_junction 은 3.12부터라 3.10·3.11에는 없다)."""
    try:
        if entry.is_symlink():
            return True
        # st_reparse_tag 는 Windows에만 있다. 다른 OS에는 정션이 없다
        return getattr(entry.stat(follow_symlinks=False), 'st_reparse_tag', 0) == _JUNCTION_TAG
    except OSError:
        return True


def scan(root: Path, exclude: Iterable[str] = DEFAULT_EXCLUDE_DIRS, rel: str = '',
         with_info: bool = True, html_exclude: Iterable[str] = DEFAULT_HTML_EXCLUDE_DIRS) -> list[Node]:
    """root/rel 아래의 트리. 각 노드의 path는 root 기준 '/' 구분 상대경로. 파일 노드의 kind 는 markdown | html."""
    excl = frozenset(x.lower() for x in exclude)
    html_excl = frozenset(x.lower() for x in html_exclude)
    html_ok = not any(part.lower() in html_excl for part in rel.split('/') if part)
    return _scan_dir(root, rel, excl, with_info, html_excl, html_ok)


def _scan_dir(root: Path, rel: str, exclude: frozenset[str], with_info: bool,
              html_excl: frozenset[str], html_ok: bool) -> list[Node]:
    base = root / rel if rel else root
    try:
        with os.scandir(base) as it:
            entries = list(it)
    except OSError:
        return []
    dirs: list[Node] = []
    files: list[Node] = []
    for entry in entries:
        name = entry.name
        if name.startswith('.') or _is_link(entry):
            continue
        try:
            st = entry.stat(follow_symlinks=False)
            is_dir = entry.is_dir(follow_symlinks=False)
        except OSError:
            continue
        if has_hidden_attr(st):
            continue
        path = f'{rel}/{name}' if rel else name
        if is_dir:
            if name.lower() in exclude:
                continue
            children = _scan_dir(root, path, exclude, with_info, html_excl, html_ok and name.lower() not in html_excl)
            if children:
                dirs.append({'type': 'dir', 'name': name, 'path': path, 'children': children})
        else:
            kind = doc_kind(name)
            if kind is None or (kind == 'html' and not html_ok):
                continue
            node: Node = {'type': 'file', 'name': name, 'path': path, 'kind': kind,
                          'mtime': st.st_mtime, 'size': st.st_size}
            if with_info:
                node['title'] = doc_info(Path(entry.path), st)['title']
            files.append(node)
    dirs.sort(key=lambda n: natural_key(n['name']))
    files.sort(key=lambda n: natural_key(n['name']))
    return dirs + files


def iter_files(nodes: list[Node]) -> Iterator[Node]:
    for node in nodes:
        if node['type'] == 'file':
            yield node
        else:
            yield from iter_files(node['children'])


def is_hidden_path(root: Path, target: Path) -> bool:
    """root 에서 target 까지 경로 중 숨김 요소가 하나라도 있으면 True."""
    cur = root
    for part in target.relative_to(root).parts:
        if part.startswith('.'):
            return True
        cur = cur / part
        try:
            st = os.stat(cur, follow_symlinks=False)
        except OSError:
            return True
        if has_hidden_attr(st):
            return True
    return False


def resolve_inside(root: Path, rel: str) -> Path | None:
    """root 기준 상대경로 rel 을 실제 경로로. root 밖이거나 숨김 경로면 None.

    root 는 resolve() 된 절대경로여야 한다. 링크를 따라가 root 밖으로 나가는 경우도 막는다.
    """
    if '\x00' in rel:
        return None
    # resolve() 하기 전에 글자만으로 root 안인지 본다. \\서버\공유 같은 값을 resolve() 하면 Windows 가 그 서버에 접속해
    # 로그인 정보(NTLM)를 건넬 수 있다 — /doc/%5C%5C서버… 주소 하나로 (점검에서 발견). 드라이브·루트로 시작하는 값도 여기서 걸린다
    base = os.path.normcase(os.path.join(root, ''))
    joined = os.path.normcase(os.path.normpath(os.path.join(root, rel)))
    if joined != os.path.normcase(str(root)) and not joined.startswith(base):
        return None
    try:
        target = (root / rel).resolve()
    except (OSError, RuntimeError, ValueError):
        return None
    if target == root:
        return target
    if not target.is_relative_to(root):
        return None
    if is_hidden_path(root, target):
        return None
    return target
