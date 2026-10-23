"""로컬 HTTP 서버 (127.0.0.1 전용).

- /              index.html (모드 정보 주입)
- /static/...    web/ 정적 파일 (앱 UI, vendor 라이브러리, 테마)
- /api/...       JSON API — pywebview 모드에서는 X-Token 헤더 검사. 프로젝트(탭)를 다루는 요청은 p=<프로젝트 id>
- /doc/<id>/<경로> 그 프로젝트 안의 파일 (md 원문, 이미지 등). 숨김·프로젝트 밖·모르는 id 는 404

API 명세는 docs/ARCHITECTURE.md 에 있다. 바꾸면 문서도 함께 고친다.
"""
from __future__ import annotations

import mimetypes
import posixpath
import re
from pathlib import Path
from typing import Any

from flask import Flask, Response, abort, jsonify, request, send_file

from . import __version__, i18n, osutil, terminal
from .config import is_number
from .docinfo import doc_info, read_text
from .i18n import t
from .paths import web_dir
from .scanner import MAX_DIR_ENTRIES, MAX_OTHER_FILES, doc_kind, in_excluded, is_code, iter_files, list_dir, resolve_inside
from .search import MAX_QUERY, search
from .state import AppState, Project, TooManyTabs

RECENT_IN_OVERVIEW = 6
ALLOWED_HOSTS = frozenset({'127.0.0.1', 'localhost'})

# 형식이 틀리면 브라우저가 거부하는 파일들. Windows에서 mimetypes 는 레지스트리 값을 기본값보다 우선하는데,
# 레지스트리에 .js·.css 가 text/plain 으로 잡힌 PC가 있다. 그러면 모듈 스크립트·스타일이 거부되어 화면이 빈다.
FIXED_TYPES = {
    '.js': 'text/javascript',
    '.mjs': 'text/javascript',
    '.css': 'text/css',
    '.svg': 'image/svg+xml',   # <img> 의 SVG 는 이 형식이어야 그려진다 (/doc/* 의 그림)
    '.woff2': 'font/woff2',
}


def content_security_policy(external_images: bool) -> str:
    """앱 페이지(/)의 CSP. 문서 HTML은 앱과 같은 출처에서 그려지므로, 정화(doc.js)를 빠져나간 경로의 요청도 브라우저가 막게 한다.

    스타일 지시어는 두지 않는다 (KaTeX·Mermaid 는 인라인 스타일을 쓴다). 스크립트는 앱 자신의 파일만 (D14 → D38).
    """
    img = "'self' data: blob:" + (' http: https:' if external_images else '')
    return '; '.join((
        # 스크립트는 앱 자신의 파일만 (문서에 끼어든 인라인 스크립트·이벤트 속성을 브라우저가 막는다 — 터미널이 생겨 한 단계 올림, D38).
        # pywebview 가 결과를 돌려줄 때 eval 을 쓸 수 있어 'unsafe-eval' 은 둔다 (D14). pywebview 가 넣는 스크립트는 페이지 CSP 를 받지 않는다
        "script-src 'self' 'unsafe-eval'",
        f'img-src {img}',
        "media-src 'self'",
        "font-src 'self' data:",
        "connect-src 'self'",
        "object-src 'none'",
        "frame-src 'self'",          # html 문서를 iframe 으로 보인다 (D27)
        "base-uri 'none'",
        "form-action 'none'",
    ))


def html_doc_policy(external_images: bool) -> str:
    """문서로 보는 html(/doc/*.html)의 CSP. 스크립트·연결·폼·하위 프레임은 막고, 문서 안의 스타일과 프로젝트 안의 그림만 허용한다.

    allow-same-origin 이 있어야 앱이 iframe 안을 읽어 목차·찾기·링크를 다룰 수 있다. allow-scripts 가 없으므로
    문서 자신의 스크립트는 돌지 않는다 (D27). 인터넷 그림은 md 와 같은 설정 external_images 를 따른다.
    """
    img = "'self' data:" + (' http: https:' if external_images else '')
    return '; '.join((
        'sandbox allow-same-origin allow-modals',   # allow-modals: 앱이 문서를 인쇄하려고 (스크립트는 여전히 없음)
        "default-src 'none'",
        f'img-src {img}',
        "style-src 'self' 'unsafe-inline'",
        "font-src 'self' data:",
        "media-src 'self'",
        "base-uri 'self'",
        "form-action 'none'",
    ))


def create_app(state: AppState) -> Flask:
    for ext, mime in FIXED_TYPES.items():
        mimetypes.add_type(mime, ext)   # 레지스트리를 읽은 뒤에 덮어쓴다 (add_type 이 먼저 init 한다)
    web = web_dir()
    app = Flask(__name__, static_folder=str(web), static_url_path='/static')
    app.json.ensure_ascii = False
    app.json.sort_keys = False

    def project_of(pid: Any) -> Project:
        project = state.get(pid)
        if project is None:
            abort(404, description=t('열려 있지 않은 프로젝트입니다. 탭이 닫혔을 수 있습니다'))
        return project

    def arg_project() -> Project:
        """GET 요청의 ?p=<프로젝트 id>"""
        return project_of(request.args.get('p'))

    def body() -> dict[str, Any]:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            abort(400)
        return data

    def path_from_body() -> Path:
        data = body()
        root = project_of(data.get('p')).root
        rel = data.get('path')
        if not isinstance(rel, str):
            abort(400)
        target = resolve_inside(root, rel)
        if target is None or not target.exists():
            abort(404)
        return target

    @app.before_request
    def check_request() -> None:
        # DNS 리바인딩 방지: 다른 도메인 이름으로 들어온 요청은 거부
        if request.host.rsplit(':', 1)[0] not in ALLOWED_HOSTS:
            abort(403)
        if state.token and request.path.startswith('/api/'):
            if request.headers.get('X-Token') != state.token:
                abort(403)
        # POST 는 JSON 본문만: 다른 사이트의 폼·단순 요청은 사전 확인(preflight) 없이 올 수 있다 (토큰이 없는 브라우저 모드)
        if request.method == 'POST' and request.path.startswith('/api/') and not request.is_json:
            abort(415, description=t('JSON 본문만 받습니다'))

    @app.after_request
    def common_headers(resp: Response) -> Response:
        if request.path.startswith(('/api/', '/doc/')) or request.path == '/':
            resp.headers['Cache-Control'] = 'no-cache'
        if request.path.startswith('/doc/'):
            # 프로젝트 안의 html·svg 를 주소로 직접 열어도 앱과 같은 출처에서 스크립트가 돌지 않게 한다 (D20).
            # 문서로 보는 html 은 doc() 가 따로 정한다 (html_doc_policy)
            resp.headers.setdefault('Content-Security-Policy', 'sandbox')
            resp.headers['X-Content-Type-Options'] = 'nosniff'
            # html 문서 속 인터넷 그림이 앱 주소(Referer)를 보내지 않게 (md 그림은 img 마다 no-referrer, D19)
            resp.headers['Referrer-Policy'] = 'no-referrer'
        return resp

    @app.get('/')
    def index() -> Response:
        html = (web / 'index.html').read_text(encoding='utf-8')
        html = html.replace('{{MODE}}', state.mode).replace('{{VERSION}}', __version__).replace('{{TERM}}', state.term_secret)
        html = html.replace('{{LANG}}', i18n.language())   # 화면 언어 (설정 language, D46) — web/js/i18n.js 가 읽는다
        resp = Response(html, content_type='text/html; charset=utf-8')
        resp.headers['Content-Security-Policy'] = content_security_policy(state.config.get('external_images') is not False)
        resp.headers['Referrer-Policy'] = 'no-referrer'
        return resp

    @app.get('/api/state')
    def api_state() -> Any:
        return jsonify(state.info())

    @app.post('/api/open')
    def api_open() -> Any:
        """폴더를 탭으로 연다 (이미 열려 있으면 그 탭). 연 탭이 선택된다. 돌려주는 것은 /api/state 와 같고 opened 가 그 탭의 id."""
        folder = body().get('path')
        if not isinstance(folder, str) or not folder.strip():
            abort(400)
        try:
            project = state.open(folder.strip().strip('"'))
        except (OSError, NotADirectoryError, TooManyTabs) as exc:
            return jsonify(error=str(exc)), 400
        return jsonify(state.info() | {'opened': project.id})

    @app.post('/api/close')
    def api_close() -> Any:
        """탭을 닫는다 (그 폴더의 감시를 멈춘다). 이미 닫혔으면 그대로. /api/state 와 같은 것을 돌려준다."""
        pid = body().get('p')
        if not isinstance(pid, str):
            abort(400)
        state.close_tab(pid)
        return jsonify(state.info())

    @app.post('/api/activate')
    def api_activate() -> Any:
        """선택된 탭을 알린다 (다음 실행에 되살리고, 폴더 대화상자가 그 폴더에서 시작)."""
        project = project_of(body().get('p'))
        state.activate(project.id)
        return jsonify(ok=True)

    @app.get('/api/tree')
    def api_tree() -> Any:
        project = arg_project()
        return jsonify(root=str(project.root), tree=project.scan(fresh=request.args.get('fresh') == '1'))

    @app.get('/api/others')
    def api_others() -> Any:
        """문서 외 파일의 트리 (사이드바 아래 목록). 문서 트리와 따로 — 화면이 그 목록을 보일 때만 부른다."""
        project = arg_project()
        nodes, count, truncated = project.scan_others(fresh=request.args.get('fresh') == '1')
        return jsonify(tree=nodes, count=count, truncated=truncated, limit=MAX_OTHER_FILES)

    @app.get('/api/others/dir')
    def api_others_dir() -> Any:
        """제외 폴더(dist·build·node_modules 등) 안의 한 단계 — 자료 목록에서 그 폴더를 펼칠 때 (D49).
        숨김·밖·없는 경로는 404, 제외 폴더 안이 아니면 400 (그 밖의 폴더는 /api/others 가 이미 싣는다)."""
        project = arg_project()
        rel = request.args.get('path', '').strip('/')
        target = resolve_inside(project.root, rel) if rel else None
        if target is None or target == project.root or not target.is_dir():
            abort(404)
        rel = target.relative_to(project.root).as_posix()
        if not in_excluded(rel, project.exclude):
            abort(400, description=t('제외 폴더 안이 아닙니다'))
        nodes, truncated = list_dir(project.root, rel)
        return jsonify(path=rel, nodes=nodes, truncated=truncated, limit=MAX_DIR_ENTRIES)

    @app.get('/api/overview')
    def api_overview() -> Any:
        project = arg_project()
        root = project.root
        rel = request.args.get('path', '').strip('/')
        if rel:
            target = resolve_inside(root, rel)
            if target is None or not target.is_dir():
                abort(404)
            # 'docs/../docs' 나 대소문자가 다른 'DOCS' 도 트리와 같은 경로로 맞춘다
            rel = '' if target == root else target.relative_to(root).as_posix()
        nodes = project.scan(rel=rel)
        dirs, files = [], []
        for node in nodes:
            if node['type'] == 'dir':
                inner = list(iter_files(node['children']))
                dirs.append({
                    'name': node['name'], 'path': node['path'], 'count': len(inner),
                    'mtime': max((f['mtime'] for f in inner), default=0),
                })
            else:
                info = doc_info(root / node['path'])
                files.append(node | {'summary': info['summary']})
        recent = sorted(iter_files(nodes), key=lambda f: f['mtime'], reverse=True)[:RECENT_IN_OVERVIEW]
        return jsonify(path=rel, name=(rel.rsplit('/', 1)[-1] if rel else (root.name or str(root))),
                       dirs=dirs, files=files, recent=recent,
                       total=sum(1 for _ in iter_files(nodes)))

    @app.get('/api/search')
    def api_search() -> Any:
        project = arg_project()
        query = request.args.get('q', '')
        if len(query) > MAX_QUERY:
            abort(400, description=t('검색어는 {n}자까지입니다', n=MAX_QUERY))
        # docs·code: 찾을 묶음 (없으면 문서만 — 예전 화면과 같게). 코드는 사이드바 '코드' 목록의 파일 (D44)
        want_docs = request.args.get('docs', '1') != '0'
        want_code = request.args.get('code', '0') == '1'
        docs = list(iter_files(project.scan())) if want_docs else []
        code = [f for f in iter_files(project.scan_others()[0]) if is_code(f['name'])] if want_code else []
        return jsonify(search(project.root, docs, code, query, project.texts))

    @app.get('/api/changes')
    def api_changes() -> Any:
        """?since=<id>:<seq>,<id>:<seq>… — 화면이 아는 탭마다 그 순번 뒤의 변경. 한 번의 요청으로 모든 탭을 본다.
        닫힌 탭은 빠진다. tabs_seq 가 화면이 아는 값과 다르면 탭 목록이 바뀐 것이다 (다른 실행이 넘긴 폴더)."""
        projects = {}
        for item in request.args.get('since', '').split(','):
            pid, _, seq = item.partition(':')
            project = state.get(pid)
            if project is not None and seq.isdigit():
                projects[pid] = project.log.since(int(seq))
        return jsonify(tabs_seq=state.tabs_seq, projects=projects)

    @app.get('/api/config')
    def api_config_get() -> Any:
        return jsonify(state.config.public())

    @app.post('/api/config')
    def api_config_set() -> Any:
        patch = request.get_json(silent=True)
        if not isinstance(patch, dict):
            abort(400)
        state.config.update_client(patch)
        return jsonify(state.config.public())

    @app.post('/api/position')
    def api_position() -> Any:
        """탭(p)에서 보는 문서와 스크롤 위치 {p, path, scroll} (다음에 열 때 되살림). 설정 restore_last 가 꺼져 있으면 기록하지 않는다."""
        data = body()
        root = project_of(data.get('p')).root
        rel, scroll = data.get('path'), data.get('scroll', 0)
        if not isinstance(rel, str):
            abort(400)
        target = resolve_inside(root, rel)
        if target is None or not target.exists():
            abort(404)
        if not target.is_file() or not is_number(scroll) or not 0 <= scroll < 10**8:
            abort(400)
        if state.config.get('restore_last') is not False:
            state.config.remember_position(str(root), target.relative_to(root).as_posix(), int(scroll))
        return jsonify(ok=True)

    # ---- 오른쪽 터미널 (D38) ----------------------------------------------------------
    # 셸로 가는 길은 사용자의 키 입력(/api/term/input)뿐이다. 토큰(창 모드)에 더해 페이지에 실은 비밀값(X-Term)과
    # 요청을 보낸 페이지(Origin)를 확인한다 — 다른 사이트나 다른 프로그램이 셸에 명령을 넣지 못하게.

    def term_guard() -> None:
        if not state.terminals.available:
            abort(501, description=t('터미널은 Windows 10(1809) 이상에서만 쓸 수 있습니다'))
        if request.headers.get('X-Term') != state.term_secret:
            abort(403)
        origin = request.headers.get('Origin')
        if origin and origin != f'{request.scheme}://{request.host}':
            abort(403)

    def session_of(sid: Any) -> terminal.Session:
        session = state.terminals.get(sid)
        if session is None:
            abort(404, description=t('끝난 터미널입니다'))
        return session

    def term_size(data: dict[str, Any]) -> tuple[int, int]:
        cols, rows = data.get('cols', 80), data.get('rows', 24)
        if not all(isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 1000 for v in (cols, rows)):
            abort(400)
        return cols, rows

    @app.post('/api/term/open')
    def api_term_open() -> Any:
        """탭(p)의 셸을 그 프로젝트 폴더에서 띄운다 (이미 돌고 있으면 그것). {id, shell, cwd}"""
        term_guard()
        data = body()
        project = project_of(data.get('p'))
        cols, rows = term_size(data)
        try:
            session = state.terminals.open(project.id, str(project.root), state.config.get('terminal_shell'), cols, rows)
        except OSError as exc:
            return jsonify(error=t('셸을 시작하지 못했습니다 ({error}). 설정 파일의 terminal_shell 을 확인하세요', error=exc)), 500
        return jsonify(id=session.id, shell=terminal.shell_label(session.exe), cwd=str(project.root))

    @app.get('/api/term/read')
    def api_term_read() -> Any:
        """from(받은 곳) 다음의 출력. 없으면 새 출력이 생기거나 셸이 끝날 때까지 기다린다 (긴 폴링). {data, next, reset, alive, exit}"""
        term_guard()
        session = session_of(request.args.get('t'))
        since = request.args.get('from', default=0, type=int)
        return jsonify(session.read(max(0, since), terminal.READ_WAIT))

    @app.post('/api/term/input')
    def api_term_input() -> Any:
        """사용자가 친 키·붙여 넣은 글 {t, data}"""
        term_guard()
        data = body()
        text = data.get('data')
        if not isinstance(text, str):
            abort(400)
        if len(text) > 65536:
            abort(413, description=t('한 번에 보낼 수 있는 글은 65536자까지입니다'))
        session_of(data.get('t')).write(text)
        return jsonify(ok=True)

    @app.post('/api/term/resize')
    def api_term_resize() -> Any:
        term_guard()
        data = body()
        session_of(data.get('t')).resize(*term_size(data))
        return jsonify(ok=True)

    @app.get('/api/term/info')
    def api_term_info() -> Any:
        """{alive, busy} — busy: 셸에서 띄운 프로그램이 돌고 있음 (탭을 닫기 전에 묻는다)"""
        term_guard()
        session = session_of(request.args.get('t'))
        return jsonify(alive=session.alive, busy=session.busy())

    @app.post('/api/term/close')
    def api_term_close() -> Any:
        """셸과 셸에서 띄운 프로그램을 끝낸다 (다시 시작할 때)"""
        term_guard()
        sid = body().get('t')
        if not isinstance(sid, str):
            abort(400)
        state.terminals.close(sid)
        return jsonify(ok=True)

    @app.post('/api/open-config')
    def api_open_config() -> Any:
        """설정 파일을 편집기로 연다 (API로 못 바꾸는 editor·exclude_dirs 를 고치도록). 파일이 없으면 기본값으로 만든다."""
        if not state.config.path.exists():
            state.config.save()
        try:
            how = osutil.open_path(state.config.path, None, state.config.get('editor'))
        except OSError as exc:
            return jsonify(error=str(exc)), 500
        return jsonify(action=how, path=str(state.config.path))

    @app.post('/api/open-external')
    def api_open_external() -> Any:
        target = path_from_body()
        line = body().get('line')
        line = int(line) if isinstance(line, int) or (isinstance(line, str) and line.isdigit()) else None
        prefer_editor = body().get('how') == 'editor'   # '편집기로 열기' — 기본 앱 형식(csv 등)도 편집기로
        try:
            how = osutil.open_path(target, line, state.config.get('editor'), prefer_editor)
        except OSError as exc:
            return jsonify(error=str(exc)), 500
        return jsonify(action=how)

    @app.post('/api/exists')
    def api_exists() -> Any:
        """문서 속 경로 표기(src/app.py:42) 중 프로젝트 안에 실제로 있는 파일 (본문 경로 자동 링크, pathlink.js).

        {p, paths:[...], base:'문서가 있는 폴더'} → {found:{입력: 프로젝트 기준 경로}}. 프로젝트 기준으로 먼저,
        없으면 문서 폴더 기준으로 본다. 숨김·밖·폴더는 없는 것으로 한다 (resolve_inside).
        """
        data = body()
        root = project_of(data.get('p')).root
        paths, base = data.get('paths'), data.get('base') or ''
        if not isinstance(paths, list) or len(paths) > 500 or not isinstance(base, str):
            abort(400)
        found: dict[str, str] = {}
        for raw in paths:
            if not isinstance(raw, str) or not raw or len(raw) > 300:
                continue
            rel = raw.replace('\\', '/')
            for cand in (rel.lstrip('/'), posixpath.join(base, rel) if base and not rel.startswith('/') else None):
                target = resolve_inside(root, cand) if cand else None
                if target is not None and target.is_file():
                    found[raw] = target.relative_to(root).as_posix()
                    break
        return jsonify(found=found)

    @app.post('/api/reveal')
    def api_reveal() -> Any:
        target = path_from_body()
        try:
            osutil.reveal(target)
        except OSError as exc:
            return jsonify(error=str(exc)), 500
        return jsonify(action='reveal')

    @app.get('/doc/<pid>/<path:rel>')
    def doc(pid: str, rel: str) -> Response:
        root = project_of(pid).root
        target = resolve_inside(root, rel)
        if target is None or not target.is_file():
            abort(404)
        kind = doc_kind(target.name)
        if kind == 'markdown':
            return Response(read_text(target), content_type='text/markdown; charset=utf-8')
        if kind == 'html':
            # Claude 가 만드는 문서는 UTF-8 이다 (D1). meta charset 이 없어도 한글이 깨지지 않게 헤더로 정한다
            resp = send_file(target, mimetype='text/html', conditional=True, max_age=0)
            resp.headers['Content-Type'] = 'text/html; charset=utf-8'
            resp.headers['Content-Security-Policy'] = html_doc_policy(state.config.get('external_images') is not False)
            return resp
        return send_file(target, conditional=True, max_age=0)

    @app.errorhandler(404)
    @app.errorhandler(403)
    @app.errorhandler(400)
    @app.errorhandler(405)
    @app.errorhandler(413)
    @app.errorhandler(415)
    @app.errorhandler(501)
    @app.errorhandler(500)
    def json_error(err: Any) -> Any:
        if request.path.startswith('/api/'):
            return jsonify(error=getattr(err, 'description', str(err))), getattr(err, 'code', 500)
        return Response(re.sub(r'<[^>]+>', '', str(err)), status=getattr(err, 'code', 500),
                        content_type='text/plain; charset=utf-8')

    return app
