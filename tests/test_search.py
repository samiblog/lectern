from __future__ import annotations

from conftest import write

from lectern.scanner import iter_files, scan
from lectern.search import MAX_HITS_PER_FILE, SNIPPET, search_docs, snippet


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
