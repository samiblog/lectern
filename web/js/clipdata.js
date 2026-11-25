// 담기함의 글 (D197, DOM 없음): .lectern/clips/<이름>.md ↔ 담기함 {title, note, items}. 화면은 basket.js(사이드바)·clipview.js(펼쳐 보기), 저장은 clipstore.js.
//
// 사람과 Claude Code 가 그대로 읽는 Markdown 이다:
//
//   # 담기함 제목
//
//   질문이나 설명
//
//   <!-- lectern-clip id=c1 path=docs%2Fa.md line=12 end=20 kind=table name=… label=… at=2026-11-25 -->
//   ## 조각 제목           ← 사용자가 달았을 때만
//   메모
//   <!-- lectern-clip-text -->
//   담은 원문 (상대경로는 원래 문서 path 기준)
//   <!-- lectern-clip-notes -->   ← 조각이 쓰는 각주의 정의 (있을 때만)
//   <!-- /lectern-clip -->
//
// 값은 encodeURIComponent 로 적는다. 담은 글에 같은 표시 줄이 들어 있으면 \ 를 하나 더해 적고 읽을 때 뗀다. 표시 밖에 사람이 직접 쓴 글도 잃지 않는다 —
// 맨 앞은 설명, 조각 사이는 출처 없는 조각이 된다. 모르는 값은 그대로 다시 적는다. 파일의 경로는 믿지 않는다 (safePath).

const HEADER = '<!-- lectern-clips: read and written by Lectern, safe to edit by hand. Relative paths in a piece are relative to its source document (path=) -->';
const META = /^<!-- lectern-clip(?: (.*?))? ?-->$/;
const TEXT = '<!-- lectern-clip-text -->';
const NOTES = '<!-- lectern-clip-notes -->';
const END = '<!-- /lectern-clip -->';
const MARK = /^(\s*<!-- )(\\*)(\/?lectern-clip)/;
const KNOWN = ['id', 'path', 'line', 'end', 'kind', 'name', 'label', 'at', 'plain'];

let seq = 0;

/** 새 조각의 id. 같은 순간에, 다른 창에서 만들어도 겹치지 않게 */
export function newClipId(now = Date.now()) {
  seq += 1;
  return `c${now.toString(36)}${seq.toString(36)}${Math.floor(Math.random() * 1296).toString(36).padStart(2, '0')}`;
}

/** 프로젝트 안의 상대경로만 — 파일은 밖에서 고칠 수 있다 (절대경로·\\서버·.. 로 앱이 다른 곳을 찾아가지 않게) */
export function safePath(path) {
  const p = String(path ?? '');
  return !p || /[\\:\u0000-\u001f]/.test(p) || p.split('/').some((s) => s === '' || s === '.' || s === '..') ? '' : p;
}

const escapeLines = (text) => text.split('\n').map((l) => l.replace(MARK, '$1\\$2$3')).join('\n');
const unescapeLines = (lines) => lines.map((l) => l.replace(MARK, (m, a, slashes, c) => a + slashes.slice(1) + c)).join('\n');
/** 짝이 없는 대리 글자(잘린 그림 글자)는 encodeURIComponent 가 받지 않는다 */
const encode = (v) => encodeURIComponent(String(v).replace(/[\ud800-\udbff](?![\udc00-\udfff])|(?<![\ud800-\udbff])[\udc00-\udfff]/g, '�'));

function readMeta(line) {
  const out = {};
  for (const part of (line || '').split(' ').filter(Boolean)) {
    const at = part.indexOf('=');
    if (at < 1) continue;
    try {
      out[part.slice(0, at)] = decodeURIComponent(part.slice(at + 1));
    } catch {
      out[part.slice(0, at)] = part.slice(at + 1);
    }
  }
  return out;
}

/** 앞뒤의 빈 줄을 뗀 줄들 */
function trimmed(lines) {
  let a = 0;
  let b = lines.length;
  while (a < b && !lines[a].trim()) a += 1;
  while (b > a && !lines[b - 1].trim()) b -= 1;
  return lines.slice(a, b);
}

function makeClip(meta, head, text, notes) {
  const rest = trimmed(head);
  let title = '';
  const m = /^##(?: (.*))?$/.exec((rest[0] ?? '').replace(/\s+$/, ''));
  if (m) {
    title = (m[1] || '').trim();
    rest.shift();
  }
  const line = Number(meta.line) || 0;
  const end = Number(meta.end) || line;
  const extra = Object.fromEntries(Object.entries(meta).filter(([k]) => !KNOWN.includes(k)));
  return {
    id: meta.id || '', path: safePath(meta.path), lines: line > 0 ? [line, Math.max(line, end)] : null, kind: meta.kind || 'block', name: meta.name || '', label: meta.label || '',
    text: unescapeLines(text), notes: unescapeLines(notes), plain: meta.plain === '1', at: /^\d{4}-\d{2}-\d{2}$/.test(meta.at || '') ? meta.at : '', title, memo: unescapeLines(trimmed(rest)), extra,
  };
}

/** 파일의 글 → {title, note, items} (파일 차례) */
export function parseBox(source) {
  const lines = String(source || '').replace(/^﻿/, '').replace(/\r\n?/g, '\n').split('\n');
  const top = [];
  const items = [];
  let cur = null;         // 읽는 조각 {meta, head, text, notes}
  let part = 'top';       // 지금 줄이 들어갈 곳: top(조각 앞) | head | text | notes | loose(조각 사이)
  let loose = [];
  const flush = () => {
    if (cur) items.push(makeClip(cur.meta, cur.head, cur.text, cur.notes));
    cur = null;
    const free = trimmed(loose);
    if (free.length) items.push(makeClip({}, [], free, []));   // 사람이 조각 사이에 직접 쓴 글 — 출처 없는 조각
    loose = [];
  };
  for (const line of lines) {
    const bare = line.trim();
    const m = META.exec(bare);
    if (m) {
      flush();
      cur = { meta: readMeta(m[1]), head: [], text: [], notes: [] };
      part = 'head';
    } else if (bare.startsWith('<!-- lectern-clips')) continue;
    else if (cur && bare === TEXT && part === 'head') part = 'text';
    else if (cur && bare === NOTES && part === 'text') part = 'notes';
    else if (cur && bare === END) {
      flush();
      part = 'loose';
    } else if (part === 'top') top.push(line);
    else if (part === 'loose') loose.push(line);
    else cur[part].push(line);
  }
  flush();
  const rest = trimmed(top);
  let title = '';
  const h = /^#(?: (.*))?$/.exec((rest[0] ?? '').replace(/\s+$/, ''));
  if (h) {
    title = (h[1] || '').trim();
    rest.shift();
  }
  const seen = new Set();
  items.forEach((it, i) => {   // id 는 화면의 열쇠다 — 없거나 겹치면(파일을 손으로 복사한 것) 자리로 만든다
    if (!it.id || seen.has(it.id)) it.id = `x${i}`;
    while (seen.has(it.id)) it.id += 'x';
    seen.add(it.id);
  });
  return { title, note: unescapeLines(trimmed(rest)), items };
}

/** {title, note, items} → 파일의 글 */
export function writeBox({ title, note, items }) {
  const out = [HEADER, `# ${String(title || '').replace(/\s+/g, ' ').trim()}`.trim()];
  if (note?.trim()) out.push(escapeLines(note.trim()));
  for (const c of items) {
    const meta = { id: c.id, path: c.path, line: c.lines?.[0] || '', end: c.lines?.[1] || '', kind: c.kind, name: c.name, label: c.label, at: c.at, plain: c.plain ? '1' : '', ...c.extra };
    const fields = Object.entries(meta).filter(([, v]) => v !== '' && v != null).map(([k, v]) => `${k}=${encode(v)}`);
    const rows = [`<!-- lectern-clip ${fields.join(' ')} -->`];
    const name = String(c.title || '').replace(/\s+/g, ' ').trim();
    const memo = String(c.memo || '').trim();
    if (name || /^##(?: |$)/m.test(memo.split('\n')[0])) rows.push(`## ${name}`.trim());   // 메모가 '## ' 로 시작하면 빈 제목 줄을 두어 제목으로 읽지 않게
    if (memo) rows.push(escapeLines(memo));
    rows.push(TEXT, escapeLines(String(c.text ?? '')));
    if (c.notes) rows.push(NOTES, escapeLines(c.notes));
    rows.push(END);
    out.push(rows.join('\n'));
  }
  return `${out.join('\n\n')}\n`;
}

/**
 * 저장하려는데 파일이 그사이 바뀌었을 때(다른 창·Claude Code) 합친다: 파일의 것을 바탕으로 — 내가 뺀 조각은 빼고, 고친 조각은 내 것으로, 더한 조각은
 * 내 차례의 앞 조각 뒤에, 차례를 바꿨으면 내 차례로, 제목·설명을 고쳤으면 내 것으로.
 * marks: {touched(고치거나 더한 조각의 id), removed(뺀 조각의 id), head(제목·설명을 고침), order(차례를 바꿈)}
 */
export function mergeBox(mine, theirs, { touched, removed, head = false, order = false }) {
  const items = theirs.items.filter((c) => !removed.has(c.id));
  mine.items.forEach((c, i) => {
    if (!touched.has(c.id)) return;
    const at = items.findIndex((x) => x.id === c.id);
    if (at >= 0) {
      items[at] = c;
      return;
    }
    let after = -1;
    for (let j = i - 1; j >= 0 && after < 0; j -= 1) after = items.findIndex((x) => x.id === mine.items[j].id);
    items.splice(after < 0 ? (i ? items.length : 0) : after + 1, 0, c);
  });
  if (order) {
    const rank = new Map(mine.items.map((c, i) => [c.id, i]));
    let last = -1;
    const keys = new Map();
    items.forEach((c, i) => {   // 내가 모르는 조각은 파일에서 앞에 있던 조각 바로 뒤에
      if (rank.has(c.id)) last = rank.get(c.id);
      keys.set(c.id, [last, rank.has(c.id) ? -1 : i]);
    });
    items.sort((x, y) => keys.get(x.id)[0] - keys.get(y.id)[0] || keys.get(x.id)[1] - keys.get(y.id)[1]);
  }
  return { title: head ? mine.title : theirs.title, note: head ? mine.note : theirs.note, items };
}

/**
 * 담은 조각이 지금 원문(lines — 그 문서의 줄들)에 그대로 있는지: {state: 'same'|'moved'|'changed', lines?: [a, b]}.
 * 줄 앞뒤의 빈칸은 보지 않는다 (들여 쓴 목록은 들여쓰기를 걷고 담았다). 옮겨졌으면 가장 가까운 곳
 */
export function findPiece(lines, clip) {
  const want = clip.text.split('\n').map((l) => l.trim());
  while (want.length && !want.at(-1)) want.pop();
  if (!want.length || !clip.lines) return { state: 'changed' };
  const hit = (i) => i >= 0 && want.every((w, k) => i + k < lines.length && lines[i + k].trim() === w);
  const from = clip.lines[0] - 1;
  if (hit(from)) return { state: 'same', lines: [from + 1, from + want.length] };
  let best = -1;
  for (let i = 0; i + want.length <= lines.length; i += 1) if (hit(i) && (best < 0 || Math.abs(i - from) < Math.abs(best - from))) best = i;
  return best < 0 ? { state: 'changed' } : { state: 'moved', lines: [best + 1, best + want.length] };
}
