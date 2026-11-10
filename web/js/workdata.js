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
  for (let i = start; i < lines.length; i++) {
    const line = lines[i];
    if (FENCE.test(line)) {
      fenced = !fenced;
      continue;
    }
    if (fenced) continue;
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

/** 일정 한 줄: '- 2026-11-14 10:00-11:00 팀 회의' / '- 2026-11-14 종일 워크숍' / '- 2026-11-14 내용' */
export function eventLine({ date, time = '', end = '', allDay = false, text }, allDayWord = '종일') {   // i18n-ok — 파일에 쓰는 값
  const words = String(text || '').replace(/\s+/g, ' ').trim();
  const at = allDay ? ` ${allDayWord}` : clock(time) ? ` ${clock(time)}${clock(end) ? `-${clock(end)}` : ''}` : '';
  return `- ${date}${at} ${words}`;
}

/**
 * 일정 줄을 '## 일정' 절의 끝에 넣는다 (절 이름은 SCHEDULE_HEADS — 대소문자 무시). 절이 없으면 문서 끝에 절을 만든다.
 * 절의 끝 = 같은 수준(##) 이상의 다음 제목 앞. 그 앞의 빈 줄들 위에 넣는다. 코드 블록 안의 제목은 보지 않는다.
 * @returns {{text: string, line: number}} line: 넣은 줄의 번호 (1 부터)
 */
export function insertEvent(text, line, heading = '일정') {   // i18n-ok — 파일에 쓰는 값
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
    // ## 또는 ### 제목이 '일정' 그 자체거나 '일정 (11월)'·'일정:' 처럼 뒤에 괄호·콜론만 붙은 것 — '##일정'(빈칸 빠짐)도.
    // # 제목(과제 이름)이나 '일정 관리 개선' 같은 제목은 일정 절이 아니다
    const h = /^(#{2,3})\s*([^#\s].*?)\s*#*\s*$/.exec(lines[i]);
    const name = h ? h[2].trim().toLowerCase() : '';
    if (h && SCHEDULE_HEADS.some((head) => name === head || (name.startsWith(head) && /^\s*[(（:：\-—]/.test(name.slice(head.length))))) {
      head = i;
      level = h[1].length;
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
