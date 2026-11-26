// 담기함의 상태와 저장 (D197): 프로젝트 탭마다 tab.clips — 담기함들과 '지금 담기함'(담는 곳). 글은 .lectern/clips/ 의 파일마다 하나
// (clipdata.js 가 읽고 쓰고, 서버는 lectern/clips.py). 화면은 basket.js(사이드바 '담기' 탭)와 clipview.js(펼쳐 보기) — 바뀌면 'clips' 이벤트로 함께 다시 그린다.
// 저장은 담고 빼고 옮긴 것은 바로, 글을 쓰는 동안은 조금 뒤에, 칸을 떠나면 바로. 그사이 파일이 바뀌었으면(다른 창·Claude Code) 다시 읽어 합친다 (mergeBox).
// 사용자가 담거나 고칠 때만 파일이 생긴다. 보기만 하는 프로젝트(D71)는 쓰지 않고 이 창에만 둔다 (memory).

import { S, emit } from './store.js';
import { getJSON, getText, postJSON } from './api.js';
import { toast, docUrl, isMd, isPdf } from './util.js';
import { t } from './i18n.js';
import { parseBox, writeBox, mergeBox, newClipId, findPiece } from './clipdata.js';

const SAVE_MS = 500;

const fresh = (file, data, hash, mtime) => ({
  file, title: data.title, note: data.note, items: data.items, hash, mtime, error: '', touched: new Set(), removed: new Set(), head: false, order: false, timer: 0, saving: null, again: false,
});

/** 탭의 담기함 상태. undo: 마지막에 뺀 조각들 {file, entries: [{clip, at}]}, clock: 이 창이 저장·만들기·지우기를 한 횟수 (읽는 사이에 바뀌었는지), making: 만드는 중인 첫 담기함,
 * open: 사이드바에서 펼친 담기함의 파일, states: 조각 id → 원래 문서와 대조한 것 {key, state('' | 'changed' | 'gone'), lines(지금 있는 줄)} */
export const clipsOf = (tab) => (tab.clips ??= { boxes: [], cur: '', saved: '', loaded: false, loading: null, next: null, error: '', memory: !!tab.readonly, undo: null, clock: 0, making: null, open: new Set(), states: new Map() });
export const boxOf = (tab, file) => clipsOf(tab).boxes.find((b) => b.file === file) || null;
/** 지금 담기함 (담는 곳) — 하나도 없으면 null */
export const curBox = (tab) => (tab ? boxOf(tab, clipsOf(tab).cur) : null);
export const boxName = (box) => box.title || box.file.replace(/\.md$/i, '');
const pending = (box) => box.touched.size > 0 || box.removed.size > 0 || box.head || box.order;
const changed = (tab) => emit('clips', tab);

/** 담기함들을 읽는다. 저장을 기다리는 것이 있는 담기함은 그대로 둔다 (저장할 때 합친다). 처음 읽으면 마지막에 고친 것이 지금 담기함 */
export async function loadClips(tab, { force = false } = {}) {
  const st = clipsOf(tab);
  if (st.memory) {
    st.loaded = true;
    return;
  }
  if (st.loading) {   // 읽는 중에 또 — 읽던 것은 그 뒤에 바뀐 것을 모른다, 이어서 한 번 더 읽는다
    if (!force) return st.loading;
    return (st.next ??= st.loading.then(() => {
      st.next = null;
      return loadClips(tab, { force: true });
    }));
  }
  if (st.loaded && !force) return;
  st.loading = (async () => {
    try {
      let boxes;
      let cur;
      for (let i = 0, from = -1; i < 4 && from !== st.clock; i += 1) {   // 읽는 사이에 이 창이 저장했으면 받은 것이 옛것이다 — 다시 읽는다
        from = st.clock;
        ({ boxes, cur } = await getJSON(`/api/clips?p=${encodeURIComponent(tab.id)}`));
      }
      const next = [];
      for (const b of boxes) {
        const had = boxOf(tab, b.file);
        if (had && (pending(had) || had.saving)) next.push(had);
        else if (b.error) next.push(Object.assign(had || fresh(b.file, { title: '', note: '', items: [] }, null, 0), { error: b.error }));
        else if (had && had.hash === b.hash) next.push(Object.assign(had, { mtime: b.mtime, error: '' }));
        else if (had) next.push(Object.assign(had, parseBox(b.text), { hash: b.hash, mtime: b.mtime, error: '' }));
        else next.push(fresh(b.file, parseBox(b.text), b.hash, b.mtime));
      }
      for (const had of st.boxes) if ((pending(had) || had.saving) && !next.includes(had)) next.push(had);
      st.boxes = next;
      st.error = '';
      st.loaded = true;
      pickCur(st, cur);
    } catch (e) {
      st.error = e.message;
    } finally {
      st.loading = null;
    }
    changed(tab);
  })();
  return st.loading;
}

/** 지금 담기함이 없어졌으면 마지막에 고친 것으로 */
function pickCur(st, saved = '') {
  if (saved && saved !== st.saved && st.boxes.some((b) => b.file === saved && !b.error)) st.cur = saved;   // 다른 창에서 정한 담는 곳
  st.saved = saved || st.saved;
  if (st.boxes.some((b) => b.file === st.cur)) return;
  st.cur = st.boxes.some((b) => b.file === saved && !b.error) ? saved : [...st.boxes].filter((b) => !b.error).sort((a, b) => b.mtime - a.mtime)[0]?.file || '';
}

/** 담는 곳을 정한다 — 다시 켜도 그대로 (D199 — 마지막에 고친 담기함으로 정하면, 다른 담기함에 메모를 쓴 뒤 다시 켰을 때 담는 곳이 바뀐다) */
export function setCur(tab, file) {
  const st = clipsOf(tab);
  st.cur = file;
  if (!st.memory) {
    st.saved = file;
    st.clock += 1;   // 적는 사이에 읽은 것은 옛것이다
    postJSON('/api/clips/current', { p: tab.id, file }).catch(() => {}).finally(() => { st.clock += 1; });
  }
  changed(tab);
}

/** 새 담기함을 만들고 지금 담기함으로. 만들지 못하면 null (까닭을 알린다) */
export async function newBox(tab, title) {
  const st = clipsOf(tab);
  const data = { title: title.replace(/\s+/g, ' ').trim() || t('담기함'), note: '', items: [] };
  let box;
  if (st.memory) {
    let file = 'clips.md';
    for (let n = 2; boxOf(tab, file); n += 1) file = `clips-${n}.md`;
    box = fresh(file, data, null, Date.now() / 1000);
  } else {
    try {
      const r = await postJSON('/api/clips', { p: tab.id, title: data.title, text: writeBox(data) });
      st.clock += 1;
      box = fresh(r.file, data, r.hash, r.mtime);
    } catch (e) {
      toast(t('담기함을 만들지 못했습니다: {error}', { error: e.message }), 'error', 6000);
      return null;
    }
  }
  st.boxes = [...st.boxes.filter((b) => b.file !== box.file), box].sort((a, b) => a.file.localeCompare(b.file));
  setCur(tab, box.file);
  return box;
}

/** 담을 곳: 지금 담기함, 하나도 없으면 '담기함' 하나를 만든다 (처음 담을 때) */
export async function ensureBox(tab) {
  await loadClips(tab);
  const st = clipsOf(tab);
  if (st.error) {
    toast(t('담기함을 읽지 못했습니다: {error}', { error: st.error }), 'error', 6000);
    return null;
  }
  const box = curBox(tab);
  if (box && !box.error) return box;
  st.making ??= newBox(tab, t('담기함')).finally(() => { st.making = null; });   // 잇따라 담아도 하나만 만든다
  return st.making;
}

// ---- 저장 ------------------------------------------------------------------------

/** 파일이 그사이 바뀌었다 — 다시 읽어 내가 고친 것을 얹는다. 지워졌으면 그 자리에 다시 만든다 (담은 것을 잃지 않게) */
async function merge(tab, box, marks) {
  const { boxes } = await getJSON(`/api/clips?p=${encodeURIComponent(tab.id)}`);
  const theirs = boxes.find((b) => b.file === box.file);
  if (!theirs) {
    box.hash = null;
    return;
  }
  if (theirs.error) throw new Error(theirs.error);
  Object.assign(box, mergeBox(box, parseBox(theirs.text), marks), { hash: theirs.hash });
  toast(t('담기함이 밖에서 바뀌어 다시 읽고 합쳤습니다'));
}

export async function saveBox(tab, box) {
  clearTimeout(box.timer);
  box.timer = 0;
  if (clipsOf(tab).memory) {
    box.touched.clear();
    box.removed.clear();
    return true;
  }
  if (box.saving) {
    box.again = true;
    return box.saving;
  }
  if (!pending(box) || box.error) return true;
  let failed = false;
  box.saving = (async () => {
    for (let attempt = 0; attempt < 3; attempt += 1) {
      // 보내는 동안 고친 것은 다음 저장에 남긴다 — 보낸 글에 들어 있는 것만 지운다
      const sent = { touched: new Set(box.touched), removed: new Set(box.removed), head: box.head, order: box.order };
      box.touched.clear();
      box.removed.clear();
      box.head = false;
      box.order = false;
      const restore = () => {
        for (const id of sent.touched) if (!box.removed.has(id)) box.touched.add(id);
        for (const id of sent.removed) box.removed.add(id);
        box.head ||= sent.head;
        box.order ||= sent.order;
      };
      try {
        const r = await postJSON('/api/clips', { p: tab.id, file: box.file, text: writeBox(box), hash: box.hash });
        box.hash = r.hash;
        box.mtime = r.mtime;
        clipsOf(tab).clock += 1;
        return true;
      } catch (e) {
        restore();
        let why = e;
        if (e.status === 409 && attempt < 2) {
          try {
            await merge(tab, box, box);
            changed(tab);
            continue;
          } catch (err) {
            why = err;
          }
        }
        toast(t('담기함을 저장하지 못했습니다: {error}', { error: why.message }), 'error', 6000);
        failed = true;   // 다시 시도하지 않는다 — 다음에 고칠 때 함께 저장한다
        return false;
      }
    }
    return false;
  })();
  const ok = await box.saving;
  box.saving = null;
  const more = box.again || pending(box);
  box.again = false;
  return !failed && more ? saveBox(tab, box) : ok;
}

/** 저장을 기다리는 것을 모두 바로 (칸을 떠날 때·다른 프로젝트로 갈 때·창을 닫을 때) */
export const flushClips = (tab = S.tab) => Promise.all((tab?.clips?.boxes || []).filter(pending).map((box) => saveBox(tab, box)));

/** 고친 것을 화면에 — 최근 순의 차례가 저장을 기다리지 않게 시각도 (저장하면 파일의 시각) */
function edited(tab, box) {
  box.mtime = Date.now() / 1000;
  changed(tab);
}

function later(tab, box) {
  clearTimeout(box.timer);
  box.timer = setTimeout(() => saveBox(tab, box), SAVE_MS);
}

// ---- 고치기 ----------------------------------------------------------------------

const today = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

/** 조각들(basket.js 의 snippetOf)을 담기함에 더한다 */
export function addClips(tab, box, snips) {
  const made = snips.map((sn) => ({
    id: newClipId(), path: sn.path || '', lines: sn.lines || null, kind: sn.kind, name: sn.name || '', label: sn.label || '', text: sn.text, notes: sn.notes || '', plain: !!sn.plain,
    at: sn.at || today(), title: sn.title || '', memo: sn.memo || '', extra: { ...(sn.extra || {}) },
  }));
  box.items.push(...made);
  for (const c of made) box.touched.add(c.id);
  edited(tab, box);
  saveBox(tab, box);
  return made;
}

/** 조각을 뺀다 — 마지막에 뺀 것은 되돌릴 수 있다 (undoRemove) */
export function removeClips(tab, box, ids) {
  const entries = [];
  box.items.forEach((clip, at) => { if (ids.has(clip.id)) entries.push({ clip, at }); });
  if (!entries.length) return;
  box.items = box.items.filter((c) => !ids.has(c.id));
  for (const { clip } of entries) {
    box.touched.delete(clip.id);
    box.removed.add(clip.id);
  }
  clipsOf(tab).undo = { file: box.file, entries };
  edited(tab, box);
  saveBox(tab, box);
}

/** 마지막에 뺀 조각들을 그 자리로 */
export function undoRemove(tab) {
  const st = clipsOf(tab);
  const box = st.undo && boxOf(tab, st.undo.file);
  if (!box) return false;
  for (const { clip, at } of st.undo.entries) {
    if (box.items.some((c) => c.id === clip.id)) continue;
    box.items.splice(Math.min(at, box.items.length), 0, clip);
    box.removed.delete(clip.id);
    box.touched.add(clip.id);
  }
  box.order = true;
  st.undo = null;
  edited(tab, box);
  saveBox(tab, box);
  return true;
}

export function moveClip(tab, box, clip, step) {
  const i = box.items.indexOf(clip);
  const j = i + step;
  if (i < 0 || j < 0 || j >= box.items.length) return false;
  [box.items[i], box.items[j]] = [box.items[j], box.items[i]];
  box.order = true;
  edited(tab, box);
  saveBox(tab, box);
  return true;
}

/** 조각의 제목·메모를 고친다 (쓰는 동안 — 조금 뒤에 저장). 화면은 쓰는 칸이 이미 보이고, 다른 화면은 'clips' 로 */
export function editClip(tab, box, clip, fields) {
  Object.assign(clip, fields);
  box.touched.add(clip.id);
  edited(tab, box);
  later(tab, box);
}

/** 담기함의 제목·설명을 고친다 */
export function editBox(tab, box, fields) {
  Object.assign(box, fields);
  box.head = true;
  edited(tab, box);
  later(tab, box);
}

/** 조각들을 다른 담기함으로 복사하거나(copy) 옮긴다 — 받는 쪽을 저장한 뒤에 뺀다 */
export async function toBox(tab, from, clips, to, { copy = false } = {}) {
  addClips(tab, to, clips);
  if (copy) return true;
  if (!(await saveBox(tab, to))) return false;
  removeClips(tab, from, new Set(clips.map((c) => c.id)));
  clipsOf(tab).undo = null;   // 옮긴 것은 되돌리기가 두 벌로 만든다
  changed(tab);
  return true;
}

/** 담기함을 휴지통으로. 안 되면 까닭을 알리고 false */
export async function deleteBox(tab, box) {
  const st = clipsOf(tab);
  await saveBox(tab, box);   // 고치던 것까지 휴지통으로 — 되살렸을 때 잃지 않게
  if (!st.memory) {
    try {
      await postJSON('/api/clips/delete', { p: tab.id, file: box.file });
    } catch (e) {
      toast(t('담기함을 지우지 못했습니다: {error}', { error: e.message }), 'error', 6000);
      return false;
    }
  }
  st.clock += 1;
  st.boxes = st.boxes.filter((b) => b !== box);
  if (st.undo?.file === box.file) st.undo = null;
  pickCur(st);
  changed(tab);
  return true;
}

/** Lectern 에서 파일 이름을 바꿈 (rename.js): 담은 곳의 경로도 — 읽어 둔 담기함만 (아직 읽지 않았으면 다음에 '원래 문서 없음') */
export async function renameSources(tab, from, to) {
  await loadClips(tab);
  for (const box of clipsOf(tab).boxes) {
    const mine = box.items.filter((c) => c.path === from);
    if (!mine.length || box.error) continue;
    for (const c of mine) {
      c.path = to;
      box.touched.add(c.id);
    }
    saveBox(tab, box);
  }
  changed(tab);
}

// ---- 원래 문서와의 대조 -------------------------------------------------------------

/** 조각의 대조한 것 — 아직이면 빈 것 */
export const stateOf = (tab, clip) => clipsOf(tab).states.get(clip.id) || { state: '', lines: null };

/**
 * 담은 글이 지금 원래 문서에 그대로 있는지 본다 (md 문서 — 바뀐 문서만 다시 받는다). 바뀐 것이 있으면 'clips-state' 이벤트.
 * 고른 글(보이는 글)과 문서가 아닌 것은 있는지만. 화면에 보이는 담기함만 부른다 (사이드바에서 펼친 것, 펼친 화면)
 */
export async function checkBox(tab, box) {
  const st = clipsOf(tab);
  const texts = new Map();
  let news = false;
  for (const c of [...(box?.items || [])]) {
    const f = c.path && (isMd(c.path) || isPdf(c.path)) ? tab.fileMap.get(c.path) : null;   // PDF 는 있는지만 (D201)
    const key = `${c.path}|${c.lines || ''}|${f ? f.mtime : ''}`;
    if (st.states.get(c.id)?.key === key) continue;
    let state = c.path && (isMd(c.path) || isPdf(c.path)) && !tab.fileMap.has(c.path) ? 'gone' : '';
    let lines = null;
    if (f && !c.plain && c.lines) {
      if (!texts.has(c.path)) {
        try {
          texts.set(c.path, (await getText(docUrl(tab, c.path))).replace(/^\ufeff/, '').split(/\r\n?|\n/));
        } catch {
          texts.set(c.path, null);   // 바뀌는 순간 — 다음에 다시 본다
        }
      }
      const found = texts.get(c.path) && findPiece(texts.get(c.path), c);
      if (!found) continue;
      lines = found.lines || null;
      state = found.state === 'changed' ? 'changed' : '';
    }
    const was = st.states.get(c.id);
    st.states.set(c.id, { key, state, lines });
    news ||= (was?.state || '') !== state;
  }
  if (news) emit('clips-state', tab);
}
