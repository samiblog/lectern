// 본문 속 경로 표기 자동 링크 (ROADMAP 3단계): `src/app.py:42`, src/app.py 처럼 프로젝트에 실제로 있는 파일 경로를 링크로.
// 누르면 md·html 문서는 뷰어에서, 코드는 읽기 화면의 그 줄로(codeview.js, D43), 그 밖의 파일은 기본 앱·편집기로 연다
// (실행하지 않는다 — osutil.open_path). 코드도 편집기로 열려면 우클릭 메뉴.
// 코드 블록·링크·수식·다이어그램 안은 건드리지 않는다. 문장 속 `코드` 는 내용 전체가 경로일 때만 링크로 감싼다.
// 있는지는 서버가 본다 (POST /api/exists — 숨김·프로젝트 밖은 없는 것으로).

import { S, emit } from './store.js';
import { postJSON, openExternal } from './api.js';
import { isCode } from './icons.js';
import { isMd, isHtml, dirname, basename } from './util.js';
import { t } from './i18n.js';

// 경로: (./ ../)* (폴더/)* 이름.확장자, 뒤에 :줄(:칸) 이나 #L줄. 한글 파일 이름을 받고, 뒤에 붙은 조사('에서')는 끝으로 본다
const PATH = /(?<![A-Za-z0-9_./\\-])((?:\.{1,2}[\\/])*(?:[\p{L}\p{N}_.-]+[\\/])*[\p{L}\p{N}_-][\p{L}\p{N}_.-]*\.[A-Za-z][A-Za-z0-9]{0,7})(?::(\d+)(?::\d+)?|#L(\d+))?(?![A-Za-z0-9_\\/-])/gu;
const WHOLE = new RegExp(`^${PATH.source}$`, 'u');
const SKIP = 'a, pre, .code-block, .katex, .math-inline, .math-display, .math-block, svg, .mermaid-error, .front-matter, script, style';
const MAX_CANDIDATES = 300;

function link(doc, text, path, line) {
  const a = doc.createElement('a');
  a.href = '#';
  a.className = 'path-link';
  a.dataset.path = path;
  if (line) a.dataset.line = line;
  a.dataset.lecHref = line ? `${path}:${line}` : path;   // 우클릭 '링크 주소 복사'
  a.title = line ? `${path} ${t('{a}행', { a: line })}` : path;
  a.append(text);
  return a;
}

function onClick(e) {
  const a = e.target.closest('a.path-link');
  if (!a) return;
  e.preventDefault();
  const { path, line } = a.dataset;
  if ((isMd(path) || isHtml(path)) && S.fileMap.has(path)) emit('open', { type: 'doc', path });   // 누를 수 있는 것은 선택된 탭의 문서뿐
  else if (isCode(basename(path))) emit('open', { type: 'code', path, line: line ? Number(line) : undefined });
  else openExternal(path, line ? Number(line) : undefined);
}

/** root(무대) 안의 경로 표기를 찾아 탭(tab)의 프로젝트에 있는 파일이면 링크로 바꾼다. 서버에 묻지 못하면 그대로 둔다. */
export async function linkPaths(root, docPath, tab) {
  const doc = root.ownerDocument;
  const codes = [];   // 내용 전체가 경로인 문장 속 `코드`
  const texts = [];   // [텍스트 노드, 찾은 것들]
  const wanted = new Set();
  for (const code of root.querySelectorAll('code')) {
    if (code.closest(SKIP)) continue;
    const m = WHOLE.exec(code.textContent.trim());
    if (m) {
      codes.push([code, m]);
      wanted.add(m[1]);
    }
  }
  const walker = doc.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode: (n) => (n.parentElement.closest(`${SKIP}, code`) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
  });
  for (let n = walker.nextNode(); n && wanted.size < MAX_CANDIDATES; n = walker.nextNode()) {
    const hits = [...n.nodeValue.matchAll(PATH)];
    if (!hits.length) continue;
    texts.push([n, hits]);
    for (const h of hits) wanted.add(h[1]);
  }
  if (!wanted.size) return;
  let found;
  try {
    ({ found } = await postJSON('/api/exists', { p: tab.id, paths: [...wanted].slice(0, MAX_CANDIDATES), base: dirname(docPath) }));
  } catch {
    return;
  }
  for (const [code, m] of codes) {
    if (found[m[1]]) code.replaceWith(link(doc, code.cloneNode(true), found[m[1]], m[2] || m[3]));
  }
  for (const [node, hits] of texts) {
    if (!hits.some((h) => found[h[1]])) continue;
    const frag = doc.createDocumentFragment();
    let at = 0;
    for (const h of hits) {
      if (!found[h[1]]) continue;
      frag.append(node.nodeValue.slice(at, h.index), link(doc, h[0], found[h[1]], h[2] || h[3]));
      at = h.index + h[0].length;
    }
    frag.append(node.nodeValue.slice(at));
    node.replaceWith(frag);
  }
}

export function initPathLinks() {
  document.querySelector('#lec-panes').addEventListener('click', onClick);
}
