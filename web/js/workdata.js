// 업무 관리의 글 (D124, DOM 없음): WORK.md 읽기 — 머리 설정의 status·priority·due, 제목, 할 일과 끝의 기한, 일정 줄.
// 오늘을 받아 계산한다 (D-n·주의할 것·오늘 일정·알림 시각). 일정 더하기가 넣을 줄과 자리도 여기서 정한다.
// 절 이름과 차례에는 기대지 않는다 — 머리 설정과 줄 모양만 본다 (본문은 자유). 규칙 시험(tools/edges/work_cases.js)으로 본다.

/** 상태: 키, 한국어·영어로 쓰는 값. 차례가 업무 현황의 무리 차례와 같다 */
export const STATUSES = [
  { key: 'planned', names: ['예정', 'planned'] },   // i18n-ok — 파일에 쓰는 값
  { key: 'active', names: ['진행', 'active', 'in-progress'] },   // i18n-ok — 파일에 쓰는 값
  { key: 'at-risk', names: ['지연위험', 'at-risk'] },   // i18n-ok — 파일에 쓰는 값
  { key: 'blocked', names: ['막힘', 'blocked'] },   // i18n-ok — 파일에 쓰는 값
  { key: 'on-hold', names: ['보류', 'on-hold'] },   // i18n-ok — 파일에 쓰는 값
  { key: 'done', names: ['완료', 'done'] },   // i18n-ok — 파일에 쓰는 값
  { key: 'dropped', names: ['중단', 'dropped'] },   // i18n-ok — 파일에 쓰는 값
];
const STATUS_OF = new Map(STATUSES.flatMap((s) => s.names.map((n) => [n.toLowerCase(), s.key])));
export const CLOSED = new Set(['done', 'dropped']);
export const STALE_DAYS = 14;    // 진행인데 이만큼 WORK.md 가 안 바뀌면 주의할 것 (계획 — 써 본 뒤 설정으로)
export const SOON_DAYS = 3;      // 마감 D-3 부터 주의할 것
export const REMIND_MINUTES = 10;   // 일정 몇 분 전에 알림
export const LOG_TIME = '17:30';    // 기록 알림 시각
export const SCHEDULE_HEADS = ['일정', 'schedule'];   // 일정 더하기가 찾는 절 이름 (대소문자 무시)   // i18n-ok
/** 기획 메모 절 (D150) — 사람이 자유롭게 쓰는 곳이라 할 일·일정·확인할 줄을 읽지 않는다 */
export const MEMO_HEADS = ['기획 메모', '자유 서술', 'planning notes'];   // i18n-ok

const pad = (n) => String(n).padStart(2, '0');
/** Date → 그 날의 'YYYY-MM-DD' (화면의 시간대) */
export const isoDay = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

/** 연도가 있는 날짜 표기를 'YYYY-MM-DD' 로 — 2026-11-5·2026.11.05·2026/11/05 도 (오타에 너그럽게). 없는 날이면 null */
export function normDay(text) {
  const m = /^(\d{4})[-./](\d{1,2})[-./](\d{1,2})$/.exec(String(text || '').trim());
  if (!m) return null;
  const iso = `${m[1]}-${pad(Number(m[2]))}-${pad(Number(m[3]))}`;
  return dayOf(iso) ? iso : null;
}

/** 'YYYY-MM-DD' 가 있는 날짜면 그 Date(그날 0시), 아니면 null */
export function dayOf(text) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(text || '').trim());
  if (!m) return null;
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  return d.getMonth() === Number(m[2]) - 1 && d.getDate() === Number(m[3]) ? d : null;
}

/** 두 'YYYY-MM-DD' 사이의 날 수 (b - a). 서머타임에도 하루는 하루 */
export function daysBetween(a, b) {
  const x = dayOf(a);
  const y = dayOf(b);
  if (!x || !y) return null;
  return Math.round((Date.UTC(y.getFullYear(), y.getMonth(), y.getDate()) - Date.UTC(x.getFullYear(), x.getMonth(), x.getDate())) / 86400000);
}

/** 'YYYY-MM-DD' 에 날을 더한 날 */
export function addDays(day, n) {
  const d = dayOf(day);
  if (!d) return null;
  return isoDay(new Date(d.getFullYear(), d.getMonth(), d.getDate() + n));
}

/**
 * 기한 글을 날짜로: 'YYYY-MM-DD' 그대로, 'M/D' 는 오늘에서 가장 가까운 해 (앞뒤 6달 안 — 지난 기한이 내년으로 가지 않게)
 * @returns {string|null}
 */
export function dueDay(text, today) {
  const s = String(text || '').trim();
  const full = normDay(s);
  if (full) return full;
  const m = /^(\d{1,2})\/(\d{1,2})$/.exec(s);
  const now = dayOf(today);
  if (!m || !now) return null;
  const month = Number(m[1]);
  const date = Number(m[2]);
  let best = null;
  for (const year of [now.getFullYear() - 1, now.getFullYear(), now.getFullYear() + 1]) {
    const iso = `${year}-${pad(month)}-${pad(date)}`;
    if (!dayOf(iso)) continue;
    const gap = Math.abs(daysBetween(today, iso));
    if (best === null || gap < best.gap) best = { iso, gap };
  }
  return best ? best.iso : null;
}

/**
 * 머리 설정(맨 앞 --- 사이)의 '키: 값' — 맨 위 키만, 키는 작은 글자로.
 * {meta, at(키 → 줄 번호, 1 부터), start(본문이 시작하는 줄의 0 기준 번호), broken(--- 로 열었는데 닫지 않음)}
 */
export function frontMatter(lines) {
  if (lines[0]?.trim() !== '---') return { meta: {}, at: {}, start: 0, broken: false };
  const meta = {};
  const at = {};
  for (let i = 1; i < Math.min(lines.length, 300); i++) {
    const line = lines[i];
    if (line.trim() === '---' || line.trim() === '...') return { meta, at, start: i + 1, broken: false };
    const m = /^([A-Za-z_][\w-]*)\s*[:：]\s*(.*)$/.exec(line);
    const key = m?.[1].toLowerCase();
    if (m && !(key in meta)) {
      meta[key] = m[2].trim().replace(/^(['"])(.*)\1$/, '$2');
      at[key] = i + 1;
    }
  }
  return { meta: {}, at: {}, start: 0, broken: true };   // 닫히지 않은 머리 설정은 머리 설정이 아니다
}

/** 두 글의 편집 거리 (짧은 키 이름의 오타를 알아보는 데만 — 2 를 넘으면 더 세지 않는다) */
function editDistance(a, b) {
  if (Math.abs(a.length - b.length) > 2) return 3;
  let prev = Array.from({ length: b.length + 1 }, (_, j) => j);
  for (let i = 1; i <= a.length; i++) {
    const row = [i];
    for (let j = 1; j <= b.length; j++) row.push(Math.min(prev[j] + 1, row[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1)));
    prev = row;
  }
  return prev[b.length];
}
const KEYS = ['status', 'priority', 'due'];
/** 키 이름 오타로 보이면 맞는 키 (stauts → status). 아니면 null */
const keyTypo = (key) => (KEYS.includes(key) ? null : KEYS.find((k) => editDistance(key, k) <= (k.length > 3 ? 2 : 1)) || null);

const TASK = /^\s*[-*+]\s+\[([ xX])\]\s+(.*)$/;
const DUE_END = /\s*\((\d{4}[-./]\d{1,2}[-./]\d{1,2}|\d{1,2}\/\d{1,2})\)\s*$/;   // 짧은 기한은 M/D 만 — (1.2) 같은 글을 날짜로 읽지 않게
const DUE_LOOSE = /\(\s*(?:\d{4}[-./]\d{1,2}[-./]\d{1,2}|\d{1,2}\/\d{1,2})\s*\)?\s*$/;   // 기한처럼 보이는 끝 (괄호가 빠졌거나 없는 날)
const EVENT = /^\s*[-*+]\s+(\d{4}[-./]\d{1,2}[-./]\d{1,2})(?:\s+(종일|all-day|\d{1,2}:\d{2})(?:\s*[-~–]\s*(\d{1,2}:\d{2}))?)?\s+(\S.*)$/i;   // i18n-ok
const EVENT_LOOSE = /^\s*[-*+]\s+(\d{4}[-./]\d{1,2}[-./]\d{1,2})(?=\s|$)\s*(.*)$/;   // 날짜로 시작하는 목록 줄 (읽지 못한 것을 알리려고)
const BOX_TYPO = /^\s*[-*+]\s*\[\s{0,3}\S?\s{0,3}\]|^\s*\[[ xX]?\]\s/;   // 체크 칸 오타: '- []', '-[ ]', '- [v]', '- [ ]글', '[ ] 할 일' (- [링크] 는 아님)
const ONLY_TIME = /^\d{1,2}:\d{2}(?:\s*[-~–]\s*\d{1,2}:\d{2})?$/;
const FENCE = /^\s*(```|~~~)/;

/**
 * 줄이 이름이 heads 가운데 하나인 절의 제목(##·###)이면 그 수준, 아니면 0. 대소문자는 보지 않는다.
 * 이름 그 자체거나 '일정 (11월)'·'일정:' 처럼 뒤에 괄호·콜론만 붙은 것 — '##일정'(빈칸 빠짐)도.
 * # 제목(과제 이름)이나 '일정 관리 개선' 같은 제목은 그 절이 아니다
 */
function sectionHead(line, heads) {
  const h = /^(#{2,3})\s*([^#\s].*?)\s*#*\s*$/.exec(line);
  const name = h ? h[2].trim().toLowerCase() : '';
  return h && heads.some((head) => name === head || (name.startsWith(head) && /^\s*[(（:：\-—]/.test(name.slice(head.length)))) ? h[1].length : 0;
}
const clock = (s) => (s && /^\d{1,2}:\d{2}$/.test(s) ? s.padStart(5, '0') : null);
const goodClock = (s) => !s || (Number(s.slice(0, 2)) < 24 && Number(s.slice(3)) < 60);

/**
 * 확인할 줄의 종류 — 업무 현황이 '확인할 줄'로 보인다 (줄은 버리지 않는다):
 * front 머리 설정이 닫히지 않음 · key 키 이름 오타 · status 정해지지 않은 상태 값 · due 마감을 읽지 못함 · todo-due 할 일의 기한을 읽지 못함 ·
 * todo-box 체크 칸 모양이 아님 · event-date 일정의 날짜가 없는 날 · event-time 일정의 시각을 읽지 못함 (시각 없는 일정으로 둠) · event-text 일정에 내용이 없음
 */
export const PROBLEM_KINDS = ['front', 'key', 'status', 'due', 'todo-due', 'todo-box', 'event-date', 'event-time', 'event-text'];

/**
 * WORK.md 하나를 읽는다
 * @returns {{status: string|null, statusText: string, priority: string, due: string|null, dueText: string, title: string,
 *   todos: {text: string, done: boolean, due: string|null, line: number}[], events: {date: string, time: string|null, end: string|null, allDay: boolean, text: string, line: number}[],
 *   problems: {kind: string, line: number, text: string, hint?: string}[]}}
 */
export function readWork(text, today) {
  const lines = String(text ?? '').replace(/^\uFEFF/, '').replace(/\r\n?/g, '\n').split('\n');
  const { meta, at, start, broken } = frontMatter(lines);
  const statusText = meta.status || '';
  const dueText = meta.due || '';
  let title = meta.title || '';
  const todos = [];
  const events = [];
  const problems = [];
  const note = (kind, i, hint) => problems.push({ kind, line: i + 1, text: lines[i].trim(), ...(hint ? { hint } : {}) });
  if (broken) note('front', 0);
  for (const key of Object.keys(meta)) {
    const want = keyTypo(key);
    if (want && !(want in meta)) note('key', at[key] - 1, want);
  }
  const status = STATUS_OF.get(statusText.toLowerCase()) || null;
  if (statusText && !status) note('status', at.status - 1);
  const due = dueDay(dueText, today);
  if (dueText && !due) note('due', at.due - 1);
  let fenced = false;
  let memo = 0;   // 기획 메모 절의 수준 (D150 — 0 이면 그 밖). 같거나 높은 수준의 다음 제목에서 끝난다
  for (let i = start; i < lines.length; i++) {
    const line = lines[i];
    if (FENCE.test(line)) {
      fenced = !fenced;
      continue;
    }
    if (fenced) continue;
    const head = /^(#{1,6})(?:\s|$)/.exec(line);
    if (memo && head && head[1].length <= memo) memo = 0;
    if (!memo) memo = sectionHead(line, MEMO_HEADS);
    if (memo) continue;
    if (!title) {
      const h = /^#\s+(.+?)\s*#*\s*$/.exec(line);
      if (h) title = h[1];
    }
    const task = TASK.exec(line);
    if (task) {
      const end = DUE_END.exec(task[2]);
      const day = end ? dueDay(end[1], today) : null;
      if (!day && DUE_LOOSE.test(task[2])) note('todo-due', i);
      todos.push({ text: (end && day ? task[2].slice(0, end.index) : task[2]).trim(), done: task[1] !== ' ', due: day, line: i + 1 });
      continue;
    }
    if (BOX_TYPO.test(line)) {
      note('todo-box', i);
      continue;
    }
    const ev = EVENT.exec(line);
    const date = ev ? normDay(ev[1]) : null;
    if (date) {
      const allDay = !!ev[2] && !/\d/.test(ev[2]);
      const time = allDay ? null : clock(ev[2]);
      const end = time ? clock(ev[3]) : null;
      if (goodClock(time) && goodClock(end)) {
        events.push({ date, time, end, allDay, text: ev[4].trim(), line: i + 1 });
        if (!time && !allDay && ONLY_TIME.test(ev[4].trim())) note('event-text', i);
        else if (!time && !allDay && /^\d{1,2}:\d{2}/.test(ev[4])) note('event-time', i);   // 14:00-1500 처럼 시각이 글로 넘어갔다
      } else {   // 없는 시각 (25:00) — 줄은 버리지 않고 시각 없는 일정으로
        events.push({ date, time: null, end: null, allDay: false, text: line.trim().replace(/^[-*+]\s+\S+\s+/, ''), line: i + 1 });
        note('event-time', i);
      }
      continue;
    }
    const loose = EVENT_LOOSE.exec(line);
    if (loose) note(normDay(loose[1]) ? 'event-text' : 'event-date', i);
  }
  return { status, statusText, priority: meta.priority || '', due, dueText, title, todos, events, problems };
}

/**
 * 주의할 것의 까닭들 — 끝난(완료·중단) 과제는 없다
 * @param {ReturnType<typeof readWork>} card
 * @param {number} mtime WORK.md 가 바뀐 때 (초)
 * @returns {string[]} blocked | at-risk | overdue | due-soon | stale
 */
export function attention(card, mtime, today) {
  if (CLOSED.has(card.status)) return [];
  const why = [];
  if (card.status === 'blocked') why.push('blocked');
  if (card.status === 'at-risk') why.push('at-risk');
  const left = card.due ? daysBetween(today, card.due) : null;
  if (left !== null && left < 0) why.push('overdue');
  else if (left !== null && left <= SOON_DAYS) why.push('due-soon');
  if (card.status === 'active' && mtime) {
    const changed = isoDay(new Date(mtime * 1000));
    if (daysBetween(changed, today) > STALE_DAYS) why.push('stale');
  }
  return why;
}

/** 업무 현황의 무리: attention(주의할 것) → open(진행·예정·모르는 값) → hold(보류) → closed(완료·중단) */
export function groupOf(card, why) {
  if (CLOSED.has(card.status)) return 'closed';
  if (why.length) return 'attention';
  return card.status === 'on-hold' ? 'hold' : 'open';
}

/** 마감이 빠른 차례 (없으면 뒤), 같으면 제목 */
export function byDue(a, b) {
  const x = a.due || '9999-99-99';
  const y = b.due || '9999-99-99';
  return x < y ? -1 : x > y ? 1 : String(a.title).localeCompare(String(b.title));
}

/** 기한 있는 할 일 중 지난 것·오늘·이번 주(7일 안) — 안 한 것만, 기한이 빠른 차례. items: [{card, todo}] 를 돌려준다 */
export function dueTodos(cards, today, days = 7) {
  const out = [];
  for (const card of cards) {
    if (CLOSED.has(card.status)) continue;
    for (const todo of card.todos) {
      if (todo.done || !todo.due) continue;
      const left = daysBetween(today, todo.due);
      if (left !== null && left < days) out.push({ card, todo, left });
    }
  }
  return out.sort((a, b) => a.left - b.left || a.todo.line - b.todo.line);
}

/** 그날의 일정 — 종일·시각 없는 것 먼저, 그다음 시각 차례. items: [{card, event}] */
export function dayEvents(cards, day) {
  const out = [];
  for (const card of cards) for (const event of card.events) if (event.date === day) out.push({ card, event });
  return out.sort((a, b) => (a.event.time || '').localeCompare(b.event.time || '') || a.event.line - b.event.line);
}

/** 지금 알릴 일정: 시작이 now 뒤 minutes 분 안. 이미 시작한 것은 알리지 않는다 (절전에서 깨도 지난 알림이 몰리지 않게) */
export function eventsToRemind(cards, now, minutes = REMIND_MINUTES) {
  const day = isoDay(now);
  const out = [];
  for (const { card, event } of dayEvents(cards, day)) {
    if (!event.time) continue;
    const [h, m] = event.time.split(':').map(Number);
    const at = new Date(now.getFullYear(), now.getMonth(), now.getDate(), h, m);
    const gap = (at.getTime() - now.getTime()) / 60000;
    if (gap > 0 && gap <= minutes) out.push({ card, event, key: `${day} ${event.time} ${event.text}` });
  }
  return out;
}

/** 기록 알림을 띄울 때인지 (그날 LOG_TIME 이 지났는지) */
export const pastLogTime = (now, at = LOG_TIME) => `${pad(now.getHours())}:${pad(now.getMinutes())}` >= at;

/** 오늘 WORK.md 가 바뀌지 않은 진행 중 과제 (기록 알림) — mtime 은 초 */
export function quietToday(rows, today) {
  return rows.filter(({ card, mtime }) => card.status === 'active' && (!mtime || isoDay(new Date(mtime * 1000)) !== today));
}

/** 오늘에서 다가오는 그 요일 (1~7일 뒤 — 오늘이 그 요일이면 다음 주). dow: 0 일요일 … 6 토요일 */
export function nextWeekday(today, dow) {
  const d = dayOf(today);
  if (!d) return null;
  const ahead = ((dow - d.getDay() + 7) % 7) || 7;
  return addDays(today, ahead);
}

// ---- 업무 나무 (D149) ------------------------------------------------------------------
// 폴더마다 WORK.md, 부모는 가장 가까운 위 폴더의 WORK.md. 상위는 하위를 화면에서 모아 보인다 — 파일에 옮겨 적지 않는다.

const pathKey = (p) => String(p || '').replace(/\\/g, '/').replace(/\/+$/, '').toLowerCase();
/** 하위에서 셈할 때 앞서는 차례 — 하나라도 막혔으면 묶음도 막힘 */
const OPEN_RANK = ['blocked', 'at-risk', 'active', 'planned', 'on-hold'];

/**
 * 행들을 나무로 잇는다: 행마다 parent(행 또는 null)·kids(행 배열)·depth 를 단다. 부모 = 가장 가까운 위 폴더의 행 (중간에 WORK.md 가 없는 폴더는 건너뛴다).
 * 그다음 아래부터 올라오며 eff(보이는 상태 — 적은 값, 비었으면 하위에서 셈)·derived(셈한 값인지)·leaves(하위의 끝 업무들)·next(열린 하위 가운데 가장 이른 마감) 를 단다.
 * @param {any[]} rows 업무 행들 ({path, card: readWork 의 결과, …})
 * @returns {any[]} 맨 위 행들
 */
export function linkTree(rows) {
  const keys = rows.map((r) => pathKey(r.path));
  for (const r of rows) {
    r.parent = null;
    r.kids = [];
  }
  rows.forEach((r, i) => {
    let best = -1;
    keys.forEach((k, j) => {
      if (j !== i && keys[i].startsWith(`${k}/`) && (best < 0 || k.length > keys[best].length)) best = j;
    });
    if (best >= 0) {
      r.parent = rows[best];
      rows[best].kids.push(r);
    }
  });
  const roots = rows.filter((r) => !r.parent);
  const visit = (r, depth) => {
    r.depth = depth;
    r.kids.forEach((k) => visit(k, depth + 1));
    rollup(r);
  };
  roots.forEach((r) => visit(r, 0));
  return roots;
}

/** 한 행의 셈 (하위는 이미 셈했다) */
function rollup(r) {
  const own = r.card.status;
  const blank = !String(r.card.statusText || '').trim();
  const kidStatus = r.kids.map((k) => k.eff).filter(Boolean);
  let derived = null;
  if (kidStatus.length) {
    const open = kidStatus.filter((s) => !CLOSED.has(s));
    if (open.length) derived = OPEN_RANK.find((s) => open.includes(s)) || 'planned';
    else derived = kidStatus.every((s) => s === 'dropped') ? 'dropped' : 'done';
  }
  r.eff = own || (blank ? derived : null);
  r.derived = !own && blank && !!derived;
  r.leaves = r.kids.length ? r.kids.flatMap((k) => (k.kids.length ? k.leaves : [k])) : [];
  const dues = r.kids.flatMap((k) => (CLOSED.has(k.eff) ? [] : [k.card.due, k.next])).filter(Boolean).sort();
  r.next = dues[0] || null;
}

/** 나무의 어긋남 — 주의할 것의 까닭에 더한다: kids-open(완료·중단인데 하위가 열림) · kid-late(하위의 마감이 이 업무의 마감보다 늦음) */
export function treeWhy(r) {
  const why = [];
  if (!r.kids?.length) return why;
  const openLeaves = r.leaves.filter((x) => !CLOSED.has(x.eff));
  if (CLOSED.has(r.card.status) && openLeaves.length) why.push('kids-open');
  const late = (x) => !CLOSED.has(x.eff) && !!x.card.due && x.card.due > r.card.due;
  const deep = (x) => late(x) || x.kids.some(deep);
  if (r.card.due && !CLOSED.has(r.eff) && r.kids.some(deep)) why.push('kid-late');
  return why;
}

/** 행의 하위 끝 업무들을 상태별로 센다: {total, open, byStatus: {key: n}} */
export function leafCounts(r) {
  const byStatus = {};
  for (const x of r.leaves || []) {
    const k = x.eff || 'unknown';
    byStatus[k] = (byStatus[k] || 0) + 1;
  }
  return { total: (r.leaves || []).length, open: (r.leaves || []).filter((x) => !CLOSED.has(x.eff)).length, byStatus };
}

/** 위로 올라가며 이름: ['총괄', '이슈리포트'] (그 행은 빼고). upTo 행에서 멈춘다 (그 행도 빼고) */
export function trail(r, upTo = null) {
  const out = [];
  for (let p = r.parent; p && p !== upTo; p = p.parent) out.unshift(p.title);
  return out;
}

/** 칸반의 칸: 상태 다섯 묶음 (D149 — 막힘·지연위험은 '주의', 중단은 '완료' 칸에). 상태를 모르는 업무는 'none' */
export const LANES = [
  { key: 'planned', statuses: ['planned'] },
  { key: 'active', statuses: ['active'] },
  { key: 'watch', statuses: ['blocked', 'at-risk'] },
  { key: 'hold', statuses: ['on-hold'] },
  { key: 'closed', statuses: ['done', 'dropped'] },
];
export const laneOf = (status) => LANES.find((l) => l.statuses.includes(status))?.key || 'none';

/** 파일에 쓸 상태 값 — 그 파일이 영어 값을 쓰고 있으면 영어로, 한국어 값이면 한국어로, 비었으면 화면 언어로 (lang: 'ko' | 'en') */
export function statusWord(key, sample = '', lang = 'ko') {
  const s = STATUSES.find((x) => x.key === key);
  if (!s) return '';
  const have = String(sample || '').trim();
  const english = have ? /^[a-z-]+$/i.test(have) : lang === 'en';
  return english ? s.names[1] : s.names[0];
}

// ---- 상위에서 고치기 (D149): 그 WORK.md 의 줄 하나만 바꾼다 — 고친 글을 돌려주고, 고칠 수 없으면 null ----------------

const META_LINE = /^(\s*[A-Za-z_][\w-]*\s*[:：])(.*)$/;

/**
 * 머리 설정의 키 하나를 바꾼다 (status·due·priority). 있으면 그 줄의 값만, 없으면 닫는 --- 앞에 한 줄 더한다.
 * 머리 설정이 없으면 맨 앞에 만든다 (값이 비었으면 그대로). 닫히지 않은 머리 설정이면 null — 어디가 머리인지 모른다.
 * value '' 은 값을 비운다 (status 를 비우면 하위에서 셈)
 */
export function setMeta(text, key, value) {
  const src = String(text ?? '');
  const lines = src.split('\n');
  const fm = frontMatter(lines);
  if (fm.broken) return null;
  const val = String(value ?? '').trim();
  if (lines[0]?.trim() !== '---') {
    if (!val) return src;
    return ['---', `${key}: ${val}`, '---', ...(src ? lines : [''])].join('\n');
  }
  const at = fm.at[key.toLowerCase()];
  if (at) {
    const m = META_LINE.exec(lines[at - 1]);
    lines[at - 1] = val ? `${m[1]} ${val}` : m[1];
  } else if (val) lines.splice(fm.start - 1, 0, `${key}: ${val}`);
  else return src;
  return lines.join('\n');
}

/**
 * 할 일 줄 하나를 고친다 — done(체크), due(끝의 기한: 'YYYY-MM-DD', '' 이면 뺀다). 안 준 것은 그대로.
 * expect 는 화면이 본 그 줄의 할 일 글(기한을 뺀 것) — 줄이 할 일이 아니거나 글이 다르면 null (그사이 줄이 옮겨졌다)
 * @param {string} text
 * @param {number} line
 * @param {string} expect
 * @param {{done?: boolean, due?: string}} [change]
 */
export function setTodo(text, line, expect, { done, due } = {}) {
  const lines = String(text ?? '').split('\n');
  const i = line - 1;
  const m = /^(\s*[-*+]\s+)\[([ xX])\](\s+)(.*)$/.exec(lines[i] ?? '');
  if (!m) return null;
  const end = DUE_END.exec(m[4]);
  const body = end ? m[4].slice(0, end.index) : m[4];
  if (body.trim() !== String(expect ?? '').trim()) return null;
  const box = done === undefined ? m[2] : done ? 'x' : ' ';
  const tail = due === undefined ? (end ? end[0] : '') : due ? ` (${due})` : '';
  lines[i] = `${m[1]}[${box}]${m[3]}${body.replace(/\s+$/, '')}${tail}`;
  return lines.join('\n');
}

/** 할 일 줄: '- [ ] 글 (YYYY-MM-DD)' */
export const todoLine = (words, due = '') => `- [ ] ${String(words || '').replace(/\s+/g, ' ').trim()}${due ? ` (${due})` : ''}`;
export const TODO_HEADS = ['할 일', 'todo', 'todos', 'to do', 'tasks'];   // 할 일 더하기가 찾는 절 이름   // i18n-ok

/** 일정 한 줄: '- 2026-11-14 10:00-11:00 팀 회의' / '- 2026-11-14 종일 워크숍' / '- 2026-11-14 내용' */
export function eventLine({ date, time = '', end = '', allDay = false, text }, allDayWord = '종일') {   // i18n-ok — 파일에 쓰는 값
  const words = String(text || '').replace(/\s+/g, ' ').trim();
  const at = allDay ? ` ${allDayWord}` : clock(time) ? ` ${clock(time)}${clock(end) ? `-${clock(end)}` : ''}` : '';
  return `- ${date}${at} ${words}`;
}

/**
 * 일정 줄을 '## 일정' 절의 끝에 넣는다 (절 이름은 SCHEDULE_HEADS — 대소문자 무시). 절이 없으면 문서 끝에 절을 만든다 (insertInSection).
 * 절의 끝 = 같은 수준(##) 이상의 다음 제목 앞. 그 앞의 빈 줄들 위에 넣는다. 코드 블록 안의 제목은 보지 않는다.
 * @returns {{text: string, line: number}} line: 넣은 줄의 번호 (1 부터)
 */
export const insertEvent = (text, line, heading = '일정') => insertInSection(text, line, SCHEDULE_HEADS, heading);   // i18n-ok — 파일에 쓰는 값

/** 할 일 줄을 '## 할 일' 절의 끝에 넣는다 (D149 — 상위에서 할 일 더하기). 절이 없으면 문서 끝에 만든다 */
export const insertTodo = (text, line, heading = '할 일') => insertInSection(text, line, TODO_HEADS, heading);   // i18n-ok — 파일에 쓰는 값

/** 이름이 heads 가운데 하나인 절(##·###)의 끝에 줄 하나 — insertEvent·insertTodo 가 쓴다 */
export function insertInSection(text, line, heads, heading) {
  const src = String(text ?? '').replace(/\r\n?/g, '\n');
  const lines = src.split('\n');
  const trailing = src.endsWith('\n');
  if (trailing) lines.pop();
  const { start } = frontMatter(lines);
  let head = -1;
  let level = 2;
  let fenced = false;
  for (let i = start; i < lines.length; i++) {
    if (FENCE.test(lines[i])) fenced = !fenced;
    if (fenced) continue;
    const found = sectionHead(lines[i], heads);
    if (found) {
      head = i;
      level = found;
      break;
    }
  }
  if (head < 0) {
    while (lines.length && !lines[lines.length - 1].trim()) lines.pop();
    const add = [...(lines.length ? [''] : []), `## ${heading}`, '', line];
    const at = lines.length + add.length;
    const whole = [...lines, ...add].join('\n');
    return { text: trailing || !src ? `${whole}\n` : whole, line: at };   // 끝 줄바꿈은 원래 파일대로
  }
  let end = lines.length;
  fenced = false;
  for (let i = head + 1; i < lines.length; i++) {
    if (FENCE.test(lines[i])) fenced = !fenced;
    const h = !fenced && /^(#{1,6})\s/.exec(lines[i]);
    if (h && h[1].length <= level) {
      end = i;
      break;
    }
  }
  let last = end - 1;
  while (last > head && !lines[last].trim()) last--;
  const add = last === head || !/^\s*[-*+]\s/.test(lines[last]) ? ['', line] : [line];
  lines.splice(last + 1, 0, ...add);
  const at = last + 1 + add.length;
  const out = lines.join('\n');
  return { text: trailing || !src ? `${out}\n` : out, line: at };
}

/** 기본 틀에 값을 채운다: {{title}}·{{due}}·{{priority}} (글은 한 줄로) */
export function fillTemplate(template, { title = '', due = '', priority = '' }) {
  const one = (s) => String(s || '').replace(/\s+/g, ' ').trim();
  return String(template).replace(/\{\{(title|due|priority)\}\}/g, (_, k) => one({ title, due, priority }[k]));
}
