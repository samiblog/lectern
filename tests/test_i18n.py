"""화면 문구의 영어 (D46): 한국어 문구는 모두 t() 로 감싸고, 영어 사전에 빠진 것·안 쓰는 것이 없어야 한다.

- JS: 문자열·템플릿 속 한국어는 t('…') 의 첫 인자여야 한다 (템플릿 글자에 한국어를 적지 않는다 — ${t('…')} 로).
  번역하지 않는 것(문서 내용을 읽는 정규식 등)은 그 줄 끝에 // i18n-ok.
- index.html: 글자 마디와 title·placeholder·aria-label 의 한국어 (translate="no" 안은 빼고).
- Python: 문자열 속 한국어는 t()·N_() 의 첫 인자여야 한다 (docstring 과 # i18n-ok 줄은 빼고).
"""
from __future__ import annotations

import ast
import json
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from lectern import i18n
from lectern.config import Config
from lectern.state import AppState

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / 'web'
HANGUL = re.compile('[\uac00-\ud7a3]')
REGEX_BEFORE = set('(,=:[!&|?{};+-*%<>~^') | {'', 'return', 'typeof', 'case', 'of', 'in', 'delete', 'void', 'throw', 'new'}
ESC = {'n': '\n', 't': '\t', 'r': '\r', 'b': '\b', 'f': '\f', 'v': '\v', '0': '\0'}


def unescape(body: str) -> str:
    return re.sub(r'\\(u\{[0-9a-fA-F]+\}|u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|.)',
                  lambda m: chr(int(m[1][2:-1] if m[1].startswith('u{') else m[1][1:], 16)) if m[1][0] in 'ux' and len(m[1]) > 1
                  else ESC.get(m[1], m[1]), body, flags=re.S)


def js_strings(src: str) -> list[tuple[int, str, bool, bool]]:
    """JS 소스의 문자열 → [(줄, 값, t() 의 첫 인자인지, 템플릿 글자인지)]. 주석·정규식은 건너뛴다 (이 저장소의 코드에 맞춘 단순한 읽기)"""
    out: list[tuple[int, str, bool, bool]] = []
    toks: list[str] = []          # 지나온 의미 있는 토큰 (정규식·t( 판단)
    stack: list[int] = []         # 템플릿 ${ } 를 연 중괄호 깊이
    depth = 0
    i, n = 0, len(src)
    line = lambda at: src.count('\n', 0, at) + 1

    def template(at: int) -> int:
        """at: 여는 ` 다음. 글자 조각을 기록하고, ${ 에서 멈추거나 닫는 ` 다음 위치를 돌려준다"""
        nonlocal depth
        start = at
        while at < n:
            c = src[at]
            if c == '\\':
                at += 2
                continue
            if c == '`':
                out.append((line(start), unescape(src[start:at]), False, True))
                return at + 1
            if src.startswith('${', at):
                out.append((line(start), unescape(src[start:at]), False, True))
                depth += 1
                stack.append(depth)
                toks.append('${')
                return at + 2
            at += 1
        return at

    while i < n:
        c = src[i]
        if c in ' \t\r\n':
            i += 1
        elif src.startswith('//', i):
            i = src.find('\n', i) if '\n' in src[i:] else n
        elif src.startswith('/*', i):
            i = src.index('*/', i) + 2
        elif c in '\'"':
            j = i + 1
            while src[j] != c:
                j += 2 if src[j] == '\\' else 1
            wrapped = len(toks) >= 2 and toks[-1] == '(' and toks[-2] == 't' and (len(toks) < 3 or toks[-3] != '.')
            out.append((line(i), unescape(src[i + 1:j]), wrapped, False))
            toks.append('"str"')
            i = j + 1
        elif c == '`':
            i = template(i + 1)
            toks.append('`tpl`')
        elif c == '/' and (toks[-1] if toks else '') in REGEX_BEFORE:
            j, cls = i + 1, False
            while True:
                ch = src[j]
                if ch == '\\':
                    j += 2
                    continue
                if ch == '[':
                    cls = True
                elif ch == ']':
                    cls = False
                elif ch == '/' and not cls:
                    break
                j += 1
            j += 1
            while j < n and src[j].isalpha():
                j += 1
            toks.append('/re/')
            i = j
        elif c == '{':
            depth += 1
            toks.append('{')
            i += 1
        elif c == '}':
            if stack and stack[-1] == depth:   # 템플릿의 ${ } 끝 — 글자를 이어 읽는다
                stack.pop()
                depth -= 1
                i = template(i + 1)
                toks.append('`tpl`')
            else:
                depth -= 1
                toks.append('}')
                i += 1
        else:
            m = re.compile(r'[A-Za-z_$][\w$]*|\d[\w.]*|\S').match(src, i)
            toks.append(m[0])
            i = m.end()
    return out


def js_files() -> list[Path]:
    return sorted(p for p in (WEB / 'js').rglob('*.js') if p.parent.name != 'lang')


def ok_lines(path: Path, mark: str) -> set[int]:
    return {k for k, text in enumerate(path.read_text(encoding='utf-8').splitlines(), 1) if mark in text}


class Page(HTMLParser):
    """index.html 의 번역할 글자: 글자 마디와 title·placeholder·aria-label (translate="no"·script·style 안은 빼고)"""

    VOID = {'meta', 'link', 'input', 'br', 'img', 'hr', 'use', 'path', 'circle', 'rect'}

    def __init__(self):
        super().__init__()
        self.stack: list[bool] = []   # 열린 요소마다 '번역하지 않음'
        self.found: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        off = (self.stack[-1] if self.stack else False) or a.get('translate') == 'no' or tag in ('script', 'style')
        if not off:
            self.found += [v for k, v in attrs if k in ('title', 'placeholder', 'aria-label') and v and HANGUL.search(v)]
        if tag not in self.VOID:
            self.stack.append(off)

    def handle_startendtag(self, tag, attrs):
        if not (self.stack and self.stack[-1]):
            self.found += [v for k, v in attrs if k in ('title', 'placeholder', 'aria-label') and v and HANGUL.search(v)]

    def handle_endtag(self, tag):
        if tag not in self.VOID and self.stack:
            self.stack.pop()

    def handle_data(self, data):
        if HANGUL.search(data) and not (self.stack and self.stack[-1]):
            self.found.append(data.strip())


def page_strings() -> list[str]:
    p = Page()
    p.feed((WEB / 'index.html').read_text(encoding='utf-8'))
    return p.found


def english() -> dict:
    text = (WEB / 'js' / 'lang' / 'en.js').read_text(encoding='utf-8')
    body = '\n'.join(x for x in text.splitlines() if not x.startswith('//')).replace('export default', '', 1).strip().rstrip(';')
    return json.loads(body)


def python_strings() -> tuple[list[str], list[str]]:
    """(t()·N_() 로 감싼 열쇠, 감싸지 않은 한국어 [파일:줄])"""
    keys, bare = [], []
    for path in sorted(set((ROOT / 'lectern').glob('*.py')) - {ROOT / 'lectern' / 'i18n.py'}) + [ROOT / 'app.py']:   # i18n.py 는 사전
        src = path.read_text(encoding='utf-8')
        tree = ast.parse(src)
        skip = ok_lines(path, '# i18n-ok')
        docs, wrapped = set(), set()
        for node in ast.walk(tree):
            body = getattr(node, 'body', None)
            if isinstance(body, list) and body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                docs.add(id(body[0].value))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('t', 'N_') and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    keys.append(first.value)
                    wrapped.add(id(first))
        for node in ast.walk(tree):
            text = node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None
            if isinstance(node, ast.JoinedStr):
                text = ast.get_source_segment(src, node) or ''
            if text and HANGUL.search(text) and id(node) not in docs | wrapped and node.lineno not in skip:
                if isinstance(node, ast.Constant) and any(id(node) in {id(v) for v in ast.walk(j)} for j in ast.walk(tree) if isinstance(j, ast.JoinedStr)):
                    continue   # f-문자열의 조각은 f-문자열로 한 번만 센다
                bare.append(f'{path.name}:{node.lineno}')
    return keys, bare


def js_keys() -> tuple[list[str], list[str]]:
    keys, bare = [], []
    for path in js_files():
        skip = ok_lines(path, '// i18n-ok')
        for line, value, wrapped, tpl in js_strings(path.read_text(encoding='utf-8')):
            if wrapped:
                keys.append(value)
            elif HANGUL.search(value) and line not in skip:
                bare.append(f'{path.name}:{line}: {value[:60]!r}' + (' (템플릿)' if tpl else ''))
    return keys, bare


@pytest.fixture
def state():
    st = AppState(Config(), mode='browser')
    yield st
    st.close()


def test_js_reader_handles_templates_regex_and_comments():
    src = r"""const a = t('하나'); // 주석 '둘'
    const r = /[가-힣'"]+\//g; /* '셋' */
    const b = `글자 ${t('넷', { n: `${x}` })} 끝`;
    obj.t('다섯'); f(t("여섯"));"""
    got = [(v, w, tpl) for _, v, w, tpl in js_strings(src) if v.strip()]
    assert got == [('하나', True, False), ('글자 ', False, True), ('넷', True, False), (' 끝', False, True),
                   ('다섯', False, False), ('여섯', True, False)]


def test_js_korean_is_wrapped():
    _, bare = js_keys()
    assert not bare, 'JS 의 한국어는 t() 로 감싼다 (번역하지 않을 것은 // i18n-ok):\n' + '\n'.join(bare)


def test_python_korean_is_wrapped():
    _, bare = python_strings()
    assert not bare, 'Python 의 화면 문구는 t()·N_() 로 감싼다 (번역하지 않을 것은 # i18n-ok): ' + ', '.join(bare)


def test_english_covers_every_phrase():
    en = english()
    used = set(js_keys()[0]) | set(page_strings())
    missing = sorted(k for k in used if HANGUL.search(k) and k not in en)
    unused = sorted(k for k in en if k not in used)
    assert not missing, '영어 사전(web/js/lang/en.js)에 없는 문구:\n' + '\n'.join(missing)
    assert not unused, '쓰지 않는 영어 사전 항목:\n' + '\n'.join(unused)
    assert all(not HANGUL.search(json.dumps(v, ensure_ascii=False)) for v in en.values()), '영어 값에 한국어가 남음'


def test_python_english_covers_every_phrase():
    keys = set(python_strings()[0])
    assert sorted(k for k in keys if k not in i18n.EN) == []
    assert sorted(k for k in i18n.EN if k not in keys) == []


@pytest.mark.parametrize('lang', ['ko', 'en'])
def test_index_html_gets_language(state, lang):
    from lectern.server import create_app

    state.config.update_client({'language': lang})
    html = create_app(state).test_client().get('/').get_data(as_text=True)
    assert f'<html lang="{lang}"' in html


def test_server_messages_follow_language(state):
    state.config.update_client({'language': 'en'})
    assert i18n.t('끝난 터미널입니다') == 'This terminal has ended.'
    assert i18n.t('검색어는 {n}자까지입니다', n=200) == 'Search text can be up to 200 characters.'
    state.config.update_client({'language': 'ko'})
    assert i18n.t('검색어는 {n}자까지입니다', n=200) == '검색어는 200자까지입니다'
    assert i18n.t('{ } 객체') == '{ } 객체'   # 값이 없으면 중괄호를 그대로 둔다


def test_auto_follows_windows_language(state, monkeypatch):
    monkeypatch.setattr(i18n, 'system_language', lambda: 'en')
    state.config.update_client({'language': 'auto'})
    assert i18n.language() == 'en'
    state.config.update_client({'language': 'ko'})
    assert i18n.language() == 'ko'
    state.config.update_client({'language': 'fr'})   # 모르는 값은 auto 처럼
    assert i18n.language() == 'en'
