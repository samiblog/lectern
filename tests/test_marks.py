"""문서 속 형광펜과 할 일 (D143)"""
from lectern.config import Config
from lectern.marks import MAX_PER_DOC, marks_of
from lectern.server import create_app
from lectern.state import AppState


def test_marks_and_tasks():
    text = ('# 글\n\n가 <mark>노랑</mark> 와 <mark class="green">**초록** 말</mark>\n\n'
            '- [ ] 열린 일\n- [x] 끝낸 일\n> - [ ] 인용 안의 일\n  - [ ] 들여쓴 일\n')
    got = marks_of(text)
    assert got['marks'] == [{'line': 3, 'color': '', 'text': '노랑'}, {'line': 3, 'color': 'green', 'text': '초록 말'}]
    assert [t['line'] for t in got['tasks']] == [5, 7, 8] and got['tasks'][0]['text'] == '열린 일'
    assert got['more'] is False


def test_code_is_not_read():
    text = ('```\n<mark>코드 안</mark>\n- [ ] 코드 안의 일\n```\n\n'
            '`<mark>문장 속 코드</mark>` 와 <mark class="pink">밖</mark>\n\n'
            '~~~~\n```\n<mark>네 물결 안</mark>\n~~~~\n<mark class="blue">끝</mark>\n')
    got = marks_of(text)
    assert got['marks'] == [{'line': 6, 'color': 'pink', 'text': '밖'}, {'line': 12, 'color': 'blue', 'text': '끝'}]
    assert got['tasks'] == []


def test_unknown_colors_and_crlf():
    got = marks_of('<mark class="red">정하지 않은 색</mark>\r\n<mark>가</mark>\r\n')
    assert got['marks'] == [{'line': 2, 'color': '', 'text': '가'}]


def test_long_text_and_limit():
    got = marks_of('<mark>' + '가' * 200 + '</mark>\n')
    assert len(got['marks'][0]['text']) == 80 and got['marks'][0]['text'].endswith('…')
    many = '\n'.join(f'- [ ] 일 {i}' for i in range(MAX_PER_DOC + 20))
    got = marks_of(many)
    assert len(got['tasks']) == MAX_PER_DOC and got['more'] is True


def test_api_marks(tmp_path):
    root = tmp_path / 'proj'
    (root / 'sub').mkdir(parents=True)
    (root / 'a.md').write_text('# 가\n\n<mark>칠한 말</mark>\n\n- [ ] 할 일\n', encoding='utf-8')
    (root / 'sub' / 'b.md').write_text('# 나\n\n칠하지 않음\n', encoding='utf-8')
    (root / 'c.html').write_text('<p><mark>html 은 보지 않는다</mark></p>', encoding='utf-8')
    st = AppState(Config(), mode='browser')
    st.open(root.resolve())
    try:
        c = create_app(st).test_client()
        docs = c.get(f'/api/marks?p={st.active}').get_json()['docs']
        assert docs == [{'path': 'a.md', 'marks': [{'line': 3, 'color': '', 'text': '칠한 말'}], 'tasks': [{'line': 5, 'text': '할 일'}], 'more': False}]
        assert c.get('/api/marks?p=nope').status_code == 404
    finally:
        st.close()

