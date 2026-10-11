"""로컬 HTTP 서버 (127.0.0.1 전용).

- /              index.html (모드 정보 주입)
- /static/...    web/ 정적 파일 (앱 UI, vendor 라이브러리, 테마)
- /api/...       JSON API — pywebview 모드에서는 X-Token 헤더 검사
- /doc/<경로>     프로젝트 안의 파일 (md 원문, 이미지 등). 숨김·프로젝트 밖은 404

API 명세는 docs/ARCHITECTURE.md 에 있다. 바꾸면 문서도 함께 고친다.
"""
from __future__ import annotations

import mimetypes
import re
from pathlib import Path
from typing import Any

from flask import Flask, Response, abort, jsonify, request, send_file

from . import __version__, osutil
from .docinfo import doc_info, read_text
from .paths import web_dir
from .scanner import is_md, iter_files, resolve_inside, scan
from .search import MAX_QUERY, search_docs
from .state import AppState

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

    스크립트·스타일 지시어는 두지 않는다 (D14: pywebview 가 eval 을 쓸 수 있고, KaTeX·Mermaid 는 인라인 스타일을 쓴다).
    """
    img = "'self' data: blob:" + (' http: https:' if external_images else '')
    return '; '.join((
        f'img-src {img}',
        "media-src 'self'",
        "font-src 'self' data:",
        "connect-src 'self'",
        "object-src 'none'",
        "frame-src 'none'",
        "base-uri 'none'",
        "form-action 'none'",
    ))


def create_app(state: AppState) -> Flask:
    for ext, mime in FIXED_TYPES.items():
        mimetypes.add_type(mime, ext)   # 레지스트리를 읽은 뒤에 덮어쓴다 (add_type 이 먼저 init 한다)
    web = web_dir()
    app = Flask(__name__, static_folder=str(web), static_url_path='/static')
    app.json.ensure_ascii = False
    app.json.sort_keys = False

    def require_root() -> Path:
        if state.root is None:
            abort(409, description='열린 폴더가 없습니다')
        return state.root

    def path_from_body() -> Path:
        data = request.get_json(silent=True) or {}
        rel = data.get('path')
        if not isinstance(rel, str):
            abort(400)
        target = resolve_inside(require_root(), rel)
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

    @app.after_request
    def common_headers(resp: Response) -> Response:
        if request.path.startswith(('/api/', '/doc/')) or request.path == '/':
            resp.headers['Cache-Control'] = 'no-cache'
        if request.path.startswith('/doc/'):
            # 프로젝트 안의 html·svg 를 주소로 직접 열어도 앱과 같은 출처에서 스크립트가 돌지 않게 한다 (D20)
            resp.headers['Content-Security-Policy'] = 'sandbox'
            resp.headers['X-Content-Type-Options'] = 'nosniff'
        return resp

    @app.get('/')
    def index() -> Response:
        html = (web / 'index.html').read_text(encoding='utf-8')
        html = html.replace('{{MODE}}', state.mode).replace('{{VERSION}}', __version__)
        resp = Response(html, content_type='text/html; charset=utf-8')
        resp.headers['Content-Security-Policy'] = content_security_policy(state.config.get('external_images') is not False)
        resp.headers['Referrer-Policy'] = 'no-referrer'
        return resp

    @app.get('/api/state')
    def api_state() -> Any:
        return jsonify(state.info())

    @app.post('/api/open')
    def api_open() -> Any:
        data = request.get_json(silent=True) or {}
        folder = data.get('path')
        if not isinstance(folder, str) or not folder.strip():
            abort(400)
        try:
            state.open(folder.strip().strip('"'))
        except (OSError, NotADirectoryError) as exc:
            return jsonify(error=str(exc)), 400
        return jsonify(state.info())

    @app.get('/api/tree')
    def api_tree() -> Any:
        root = require_root()
        return jsonify(root=str(root), tree=scan(root, state.exclude))

    @app.get('/api/overview')
    def api_overview() -> Any:
        root = require_root()
        rel = request.args.get('path', '').strip('/')
        if rel:
            target = resolve_inside(root, rel)
            if target is None or not target.is_dir():
                abort(404)
            # 'docs/../docs' 나 대소문자가 다른 'DOCS' 도 트리와 같은 경로로 맞춘다
            rel = '' if target == root else target.relative_to(root).as_posix()
        nodes = scan(root, state.exclude, rel=rel)
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
        root = require_root()
        query = request.args.get('q', '')
        if len(query) > MAX_QUERY:
            abort(400, description=f'검색어는 {MAX_QUERY}자까지입니다')
        return jsonify(search_docs(root, list(iter_files(scan(root, state.exclude))), query))

    @app.get('/api/changes')
    def api_changes() -> Any:
        since = request.args.get('since', default=0, type=int)
        result = state.log.since(since)
        result['root'] = str(state.root) if state.root else None
        return jsonify(result)

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

    @app.post('/api/open-external')
    def api_open_external() -> Any:
        target = path_from_body()
        line = (request.get_json(silent=True) or {}).get('line')
        line = int(line) if isinstance(line, int) or (isinstance(line, str) and line.isdigit()) else None
        try:
            how = osutil.open_path(target, line, state.config.get('editor'))
        except OSError as exc:
            return jsonify(error=str(exc)), 500
        return jsonify(action=how)

    @app.post('/api/reveal')
    def api_reveal() -> Any:
        target = path_from_body()
        try:
            osutil.reveal(target)
        except OSError as exc:
            return jsonify(error=str(exc)), 500
        return jsonify(action='reveal')

    @app.get('/doc/<path:rel>')
    def doc(rel: str) -> Response:
        root = require_root()
        target = resolve_inside(root, rel)
        if target is None or not target.is_file():
            abort(404)
        if is_md(target.name):
            return Response(read_text(target), content_type='text/markdown; charset=utf-8')
        return send_file(target, conditional=True, max_age=0)

    @app.errorhandler(404)
    @app.errorhandler(403)
    @app.errorhandler(409)
    @app.errorhandler(400)
    @app.errorhandler(405)
    @app.errorhandler(500)
    def json_error(err: Any) -> Any:
        if request.path.startswith('/api/'):
            return jsonify(error=getattr(err, 'description', str(err))), getattr(err, 'code', 500)
        return Response(re.sub(r'<[^>]+>', '', str(err)), status=getattr(err, 'code', 500),
                        content_type='text/plain; charset=utf-8')

    return app
