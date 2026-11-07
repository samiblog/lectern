// 새 문서 (D65·D105): 프로젝트 안의 이미 있는 폴더에 Markdown 문서를 새로 만든다 — '# 제목' 한 줄로 만들고
// (POST /api/save 의 create — 같은 이름이 있으면 만들지 않는다), 새 문서 탭의 md 문서 화면에서 바로 한 줄 편집으로 쓴다.
// 묻는 창은 newdialog.js 다. 보내기의 '새 문서…'(basket.js — 만든 뒤 조각을 넣는다)도 createDoc 을 쓴다.

import { S, emit } from './store.js';
import { getJSON, postJSON } from './api.js';
import { openInNewTab } from './doctabs.js';
import { dirname } from './util.js';
import { titleFromName } from './snippet.js';
import { templateLines } from './slideops.js';
import { applyScheme } from './headstyle.js';
import { slugify } from './markdown.js';
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
  path = path.replace(/(\.(?:md|markdown))\.md$/i, '$1');   // 입력란이 확장자 앞까지만 골라 두어 'x.md' 를 치면 'x.md.md' 가 된다
  if (path && !/\.(md|markdown)$/i.test(path)) path += '.md';
  return path;
}

/** 번호가 있는 스타일인지 — 번호 없음은 제목 한 줄로 시작한다 */
const numbered = (scheme) => !!scheme && scheme !== 'plain';

/** 새 md 문서의 글: 제목 한 줄. 번호가 있는 스타일이면 보기 머리글 두 줄 — 번호가 문서에 있어야 뒤에 더한 제목의 번호를 맞춘다 (D107) */
function firstText(title, scheme) {
  if (!numbered(scheme)) return `# ${title}\n`;
  const lines = [`# ${title}`, '', `## ${t('첫째 절')}`, '', `### ${t('세부 절')}`];
  return `${applyScheme(lines, scheme, slugify).lines.join('\n')}\n`;
}

/**
 * 새 문서를 만든다 — '# 제목'(title, 없으면 파일 이름에서) 한 줄과 스타일(scheme)의 보기 머리글, deck 이면 머리 설정과 고른 템플릿의 첫 장 (D96·D101). 먼저 만들 수 있는지 묻고(GET /api/new-doc — 답은 늘 200 이라 고쳐 쓸 이름이
 * 실패한 요청으로 남지 않는다) 만든다. 만든 경로 (폴더는 실제 이름). 안 되면 Error (까닭은 서버의 말 — 없는 폴더·같은 이름 등)
 */
export async function createDoc(path, { deck = false, template = null, title: name = '', scheme = '' } = {}) {
  const q = await getJSON(`/api/new-doc?p=${encodeURIComponent(S.tab.id)}&path=${encodeURIComponent(path)}`);
  if (q.error) throw new Error(q.error);
  const title = name || titleFromName(q.path);
  const first = template ? templateLines(template.text, title).join('\n') : `<!-- _class: lead -->\n<!-- _paginate: false -->\n\n# ${title}`;
  const group = template?.own ? `templates: ${template.group}\n` : '';   // 사용자의 묶음이면 기억한다 — 다음 장도, pptx 스타일도 그 묶음부터 (D101)
  const text = deck ? `---\nmarp: true\ntitle: ${title}\npaginate: true\n${group}---\n\n${first}\n` : firstText(title, scheme);
  const r = await postJSON('/api/save', { p: S.tab.id, path: q.path, text, create: true });
  return r.path || q.path;
}

/** 만든 새 문서를 새 문서 탭의 md 문서 화면에서 연다 — 제목 아래 새 줄에서, 번호 스타일이면 보기 머리글을 고른 채로 바로 쓴다 */
export async function openCreated(path, { deck = false, scheme = '' } = {}) {
  if (deck) {   // 슬라이드 창에서 (D96). 창이 없는 브라우저 개발 모드면 새 문서 탭에
    emit('open', { type: 'doc', path, deck: true, newTab: true, force: true });
    return;
  }
  const pane = await openInNewTab({ type: 'doc', path });
  if (pane) emit('line-open', numbered(scheme) ? { line: 3, select: true } : { line: 1, below: true });
}
