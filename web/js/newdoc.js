// 새 문서 (D65): 프로젝트 안의 이미 있는 폴더에 Markdown 문서를 새로 만든다 — 경로를 정하면 바로 '# 제목' 한 줄로 만들고
// (POST /api/save 의 create — 같은 이름이 있으면 만들지 않는다), 새 문서 탭에서 편집 모드로 연다.
// 여는 곳: 문서 탭 줄의 + (빠른 열기 맨 위 '새 문서 만들기…'), Ctrl+N, 트리·'코드'·'자료' 목록의 폴더 우클릭 '이 폴더에 새 문서…',
// 보내기의 '새 문서…'(basket.js — 만든 뒤 조각을 넣는다). 경로를 묻는 창은 basket.js 의 보낼 곳 고르기 창(#lec-insert)을 쓴다.

import { S } from './store.js';
import { getJSON, postJSON } from './api.js';
import { openInNewTab } from './doctabs.js';
import { openEditor } from './editor.js';
import { dirname } from './util.js';
import { titleFromName } from './snippet.js';
import { t } from './i18n.js';

/** 새 문서 경로의 처음 값: dir(없으면 지금 보는 문서·폴더 개요의 폴더)에 '새 문서.md' — 있으면 번호를 붙여 */
export function newDocGuess(dir = null) {
  let folder = dir;
  if (folder == null) {
    const view = S.view?.type === 'doc' || S.view?.type === 'code' || S.view?.type === 'overview' ? S.view : null;
    folder = view ? (view.type === 'overview' ? view.path : dirname(view.path)) : '';
  }
  const name = t('새 문서');
  for (let n = 1; ; n += 1) {
    const path = `${folder ? `${folder}/` : ''}${name}${n > 1 ? ` ${n}` : ''}.md`;
    if (!S.fileMap.has(path)) return path;
  }
}

/** 적은 경로를 다듬는다: 앞의 /·\ 를 떼고, .md 가 없으면 붙인다 */
export function cleanPath(raw) {
  let path = String(raw || '').trim().replace(/\\/g, '/').replace(/^\/+/, '');
  if (path && !/\.(md|markdown)$/i.test(path)) path += '.md';
  return path;
}

/**
 * 새 문서를 만든다 — '# 제목'(파일 이름에서) 한 줄. 먼저 만들 수 있는지 묻고(GET /api/new-doc — 답은 늘 200 이라 고쳐 쓸 이름이
 * 실패한 요청으로 남지 않는다) 만든다. 만든 경로 (폴더는 실제 이름). 안 되면 Error (까닭은 서버의 말 — 없는 폴더·같은 이름 등)
 */
export async function createDoc(path) {
  const q = await getJSON(`/api/new-doc?p=${encodeURIComponent(S.tab.id)}&path=${encodeURIComponent(path)}`);
  if (q.error) throw new Error(q.error);
  const r = await postJSON('/api/save', { p: S.tab.id, path: q.path, text: `# ${titleFromName(q.path)}\n\n`, create: true });
  return r.path || q.path;
}

/** 만든 새 문서를 새 문서 탭에서 편집 모드로 연다 — 커서는 제목 아래 */
export async function openCreated(path) {
  const pane = await openInNewTab({ type: 'doc', path });
  if (pane) await openEditor(pane, { line: 3 });
}
