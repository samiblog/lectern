from __future__ import annotations

from lectern.docinfo import doc_info, extract_info, split_front_matter, strip_inline


def test_title_from_h1_and_summary_from_first_paragraph():
    info = extract_info('# 제목\n\n첫 문단 **굵게** 와 [링크](a.md).\n\n둘째 문단\n')
    assert info == {'title': '제목', 'summary': '첫 문단 굵게 와 링크.'}


def test_front_matter_wins():
    info = extract_info('---\nname: plan\ndescription: "계획 설명"\n---\n# 다른 제목\n본문\n')
    assert info['title'] == 'plan'
    assert info['summary'] == '계획 설명'


def test_metadata_line_skipped_for_summary():
    info = extract_info('# 보고서\n\n> 작성: 2026-10-09 | 상태: 초안\n\n진짜 요약 문단입니다.\n')
    assert info['summary'] == '진짜 요약 문단입니다.'


def test_metadata_used_when_nothing_else():
    assert extract_info('# 메모\n\n상태: 초안\n')['summary'] == '상태: 초안'


def test_code_fence_and_tables_ignored():
    text = '```\n# 코드 속 제목\n```\n| a | b |\n|---|---|\n\n## 소제목\n본문\n'
    info = extract_info(text)
    assert info['title'] == '소제목'      # H1이 없으면 첫 제목
    assert info['summary'] == '본문'


def test_list_and_quote_markers_removed():
    assert extract_info('# t\n\n- [ ] 할 일 항목\n')['summary'] == '할 일 항목'
    assert extract_info('# t\n\n> 인용 문장\n')['summary'] == '인용 문장'


def test_summary_truncated():
    info = extract_info('# t\n\n' + '가' * 400)
    assert len(info['summary']) == 160 and info['summary'].endswith('…')


def test_strip_inline_keeps_snake_case():
    assert strip_inline('`code` and snake_case_name and *em*') == 'code and snake_case_name and em'


def test_split_front_matter_without_closing():
    meta, body = split_front_matter('---\ntitle: x\n본문')
    assert meta == {} and body.startswith('---')


def test_doc_info_cache_follows_mtime(tmp_path):
    p = tmp_path / 'a.md'
    p.write_text('# 하나\n', encoding='utf-8')
    assert doc_info(p)['title'] == '하나'
    # 크기가 달라져 캐시가 무효화됨. Windows는 수정 시각 단위가 거칠어(약 15ms) 시각만으로는 바뀐 줄 모를 수 있다
    p.write_text('# 둘째 제목\n', encoding='utf-8')
    assert doc_info(p)['title'] == '둘째 제목'
    assert doc_info(tmp_path / 'none.md') == {'title': None, 'summary': ''}


def test_html_info():
    from lectern.docinfo import extract_html_info

    head = '<html><head><title> 구리 보고서 </title><meta name="description" content="요약 문장"><style>p{}</style></head>'
    assert extract_html_info(head + '<body><h1>제목</h1><p>첫 문단</p></body></html>') == {'title': '구리 보고서', 'summary': '요약 문장'}
    body = '<body><script>var x = "<h1>아님</h1>"</script><h2>둘째</h2><p>첫 <b>문단</b>입니다</p></body>'
    assert extract_html_info(body) == {'title': '둘째', 'summary': '첫 문단입니다'}
