from __future__ import annotations

import os
import re
import time
from pathlib import Path

from conftest import write

from lectern.scanner import CODE_EXT, is_code, iter_files, scan, scan_others
from lectern.search import MAX_CODE_BYTES, MAX_HITS_PER_FILE, SNIPPET, TextCache, search, search_docs, snippet


def run(root, q):
    return search_docs(root, list(iter_files(scan(root))), q)


def test_finds_case_insensitive_with_line_numbers(project):
    # 바이트로 쓴다 (write_text 는 Windows에서 \n 을 \r\n 으로 바꾼다). frontmatter 뒤의 줄 번호와 \r\n 을 함께 본다
    (project / 'docs' / 'note.md').write_bytes('---\ntitle: 메모\n---\n# 메모\r\n\r\n구리 가격은 Copper 와 같다.\r\n다음 줄\n'.encode())
    r = run(project, 'copper')
    assert r['total'] == 1 and [x['path'] for x in r['results']] == ['docs/note.md']
    assert r['results'][0]['hits'] == [{'line': 6, 'text': '구리 가격은 Copper 와 같다.'}]


def test_skips_hidden_and_excluded(project):
    r = run(project, '숨김')
    assert r['results'] == []          # .hidden.md, .claude/ 는 트리에 없으므로 찾지 않는다
    assert run(project, '제외')['results'] == []
    assert run(project, '   ')['results'] == []


def test_title_matches_come_first(project):
    write(project / 'a.md', '# 다른 제목\n\n열쇠 단어\n')
    write(project / 'b.md', '# 열쇠 문서\n\n본문\n')
    paths = [x['path'] for x in run(project, '열쇠')['results']]
    assert paths[0] == 'b.md'


def test_limits_and_snippet(project):
    write(project / 'many.md', '\n'.join(['찾을말'] * (MAX_HITS_PER_FILE + 5)))
    r = run(project, '찾을말')
    assert len(r['results'][0]['hits']) == MAX_HITS_PER_FILE and r['truncated']
    long = 'ㄱ' * 300 + '찾을말' + 'ㄴ' * 300
    s = snippet(long, 300)
    assert s.startswith('…') and s.endswith('…') and '찾을말' in s and len(s) <= SNIPPET + 2


def test_html_searches_visible_text_only(project):
    write(project / 'r.html', '<html><head><style>.구리 {}</style><script>var 구리 = 1</script></head>\n<body>\n<p>구리 <b>가격</b> &amp; 재고</p>\n</body></html>')
    r = run(project, '구리 가격')
    assert r['results'][0]['hits'] == [{'line': 3, 'text': '구리 가격 & 재고'}]
    assert run(project, 'var')['results'] == []      # 스크립트·스타일 안은 찾지 않는다


# ---- 코드 (D44) -------------------------------------------------------------------

def code_files(root):
    return [f for f in iter_files(scan_others(root)[0]) if is_code(f['name'])]


def test_code_ext_matches_icons_js():
    # 화면의 '코드' 목록(icons.js 의 code 종류)과 서버의 코드 검색이 같은 파일을 본다
    js = (Path(__file__).resolve().parent.parent / 'web' / 'js' / 'icons.js').read_text(encoding='utf-8')
    block = re.search(r"code: '([^']*)'\s*\+\s*'([^']*)'", js)
    assert set((block.group(1) + block.group(2)).split()) == CODE_EXT
    assert is_code('a.PY') and is_code('b.tsx') and not is_code('c.md') and not is_code('d.pdf') and not is_code('README')


def test_searches_code_after_docs(project):
    write(project / 'src' / 'app.py', 'import os\n\ndef find_copper():\n    return "copper"\n')
    write(project / 'docs' / 'cu.md', '# 구리\n\ncopper 가격\n')
    r = search(project, list(iter_files(scan(project))), code_files(project), 'copper')
    kinds = [(x['kind'], x['path']) for x in r['results']]
    assert kinds == [('doc', 'docs/cu.md'), ('code', 'src/app.py')] and r['docs'] == 1 and r['code'] == 1
    code = r['results'][1]
    assert code['title'] is None and [h['line'] for h in code['hits']] == [3, 4] and code['hits'][0]['text'] == 'def find_copper():'
    only_code = search(project, [], code_files(project), 'copper')
    assert [x['kind'] for x in only_code['results']] == ['code'] and only_code['docs'] == 0
    assert run(project, 'find_copper')['results'] == []   # 문서만 찾으면 코드는 없다


def test_skips_huge_code(project):
    big = project / 'src' / 'big.json'
    big.parent.mkdir(parents=True, exist_ok=True)
    big.write_text('"needle"\n' + 'x' * (MAX_CODE_BYTES + 10), encoding='utf-8')
    assert search(project, [], code_files(project), 'needle')['results'] == []


def test_text_cache_rereads_changed_files(tmp_path):
    f = tmp_path / 'a.py'
    f.write_bytes(b'first\n')   # write_text 는 Windows 에서 \n 을 \r\n 으로 바꾼다
    cache = TextCache()
    assert cache.read(f, 1000) == 'first\n'
    assert cache.read(f, 1000) == 'first\n'   # 그대로면 기억한 글
    f.write_bytes(b'second line\n')
    later = time.time() + 5
    os.utime(f, (later, later))               # 같은 초 안에 고쳐도 시각·크기가 바뀌게
    assert cache.read(f, 1000) == 'second line\n'
