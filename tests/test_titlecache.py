"""제목 기억 (D140): 다음 실행에 문서마다 파일을 열지 않고 트리를 그린다."""
import json
import os

from lectern import docinfo
from lectern.config import Config
from lectern.scanner import Titles, iter_files, scan
from lectern.state import Project
from lectern.titlecache import TitleCache, cache_path


def make(tmp_path, n=3):
    root = tmp_path / 'proj'
    (root / 'sub').mkdir(parents=True)
    for i in range(n):
        (root / ('sub' if i % 2 else '.') / f'd{i}.md').write_text(f'# 제목 {i}\n\n본문 {i}\n', encoding='utf-8')
    (root / 'deck.md').write_text('---\nmarp: true\n---\n\n# 발표\n', encoding='utf-8')
    return root


def titles_of(nodes):
    return {f['path']: (f.get('title'), bool(f.get('deck'))) for f in iter_files(nodes)}


def no_reading(monkeypatch):
    """파일을 열면 시험이 실패한다. 이번 실행의 기억(메모리)도 비운다 — 새로 띄운 것처럼"""
    docinfo._CACHE.clear()

    def boom(*a, **k):
        raise AssertionError('파일을 열었다')
    monkeypatch.setattr(docinfo, 'read_text', boom)


def test_cache_roundtrip(tmp_path):
    root = make(tmp_path)
    cfg = tmp_path / 'cfg'
    st = (root / 'd0.md').stat()
    c = TitleCache(root, cfg)
    assert c.get('d0.md', st) is None
    c.put('d0.md', st, ('제목 0', False))
    assert c.save() and not c.save()   # 바뀐 것이 없으면 다시 쓰지 않는다
    again = TitleCache(root, cfg)
    assert again.get('d0.md', st) == ('제목 0', False)
    (root / 'd0.md').write_text('# 바뀐 제목\n\n더 긴 본문\n', encoding='utf-8')
    assert again.get('d0.md', (root / 'd0.md').stat()) is None   # 크기·수정 시각이 다르면 쓰지 않는다
    again.keep({'d2.md'})
    assert again.save() and TitleCache(root, cfg).get('d0.md', st) is None


def test_cache_ignores_other_project_and_broken_file(tmp_path):
    root = make(tmp_path)
    cfg = tmp_path / 'cfg'
    st = (root / 'd0.md').stat()
    c = TitleCache(root, cfg)
    c.put('d0.md', st, ('제목 0', False))
    c.save()
    path = cache_path(cfg, root)
    data = json.loads(path.read_text(encoding='utf-8'))
    assert set(data) == {'version', 'root', 'docs'} and '본문' not in path.read_text(encoding='utf-8')   # 제목과 슬라이드 여부만
    path.write_text(json.dumps(data | {'root': 'C:/다른/곳'}), encoding='utf-8')
    assert TitleCache(root, cfg).get('d0.md', st) is None
    path.write_text('{깨진', encoding='utf-8')
    assert TitleCache(root, cfg).get('d0.md', st) is None
    assert TitleCache(root, None).save() is False   # 설정 폴더가 없으면 쓰지 않는다


def test_second_run_opens_no_file(tmp_path, monkeypatch):
    root = make(tmp_path)
    cfg = Config(tmp_path / 'cfg' / 'config.json')
    first = titles_of(Project('a', root, cfg).scan())
    assert first['d0.md'] == ('제목 0', False) and first['deck.md'] == ('발표', True) and first['sub/d1.md'] == ('제목 1', False)
    assert cache_path(tmp_path / 'cfg', root).is_file()
    assert sorted(p.name for p in root.rglob('*')) == ['d0.md', 'd1.md', 'd2.md', 'deck.md', 'sub']   # 프로젝트 폴더에는 쓰지 않는다
    no_reading(monkeypatch)
    assert titles_of(Project('b', root, cfg).scan()) == first


def test_quick_scan_reads_nothing_and_counts_unknown(tmp_path, monkeypatch):
    root = make(tmp_path)
    cfg = Config(tmp_path / 'cfg' / 'config.json')
    no_reading(monkeypatch)
    nodes, pending = Project('a', root, cfg).scan_quick()
    assert pending == 4 and all(t == (None, False) for t in titles_of(nodes).values())
    monkeypatch.undo()
    docinfo._CACHE.clear()
    p = Project('b', root, cfg)
    full = titles_of(p.scan())
    no_reading(monkeypatch)
    q = Project('c', root, cfg)
    nodes, pending = q.scan_quick()
    assert pending == 0 and titles_of(nodes) == full
    assert q.scan() is nodes   # 모르는 문서가 없으면 보통 스캔과 같은 결과다 — 다시 훑지 않는다


def test_changed_file_is_read_again_and_gone_file_forgotten(tmp_path):
    root = make(tmp_path)
    cfg = Config(tmp_path / 'cfg' / 'config.json')
    Project('a', root, cfg).scan()
    (root / 'd0.md').write_text('# 새 제목\n\n본문이 달라졌다\n', encoding='utf-8')
    (root / 'sub' / 'd1.md').unlink()
    docinfo._CACHE.clear()
    p = Project('b', root, cfg)
    nodes, pending = p.scan_quick()
    assert pending == 1 and titles_of(nodes)['d0.md'] == (None, False)
    assert titles_of(p.scan())['d0.md'] == ('새 제목', False)
    docs = json.loads(cache_path(tmp_path / 'cfg', root).read_text(encoding='utf-8'))['docs']
    assert 'sub/d1.md' not in docs and docs['d0.md'][2] == '새 제목'


def test_unreadable_file_is_not_remembered(tmp_path, monkeypatch):
    root = make(tmp_path, 1)
    cache = TitleCache(root, tmp_path / 'cfg')

    def locked(*a, **k):
        raise PermissionError('잠김')
    docinfo._CACHE.clear()
    monkeypatch.setattr(docinfo, 'read_text', locked)
    nodes = scan(root, titles=Titles(cache))
    assert titles_of(nodes)['d0.md'] == (None, False)
    assert cache.get('d0.md', os.stat(root / 'd0.md')) is None
