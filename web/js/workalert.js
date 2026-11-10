// 업무 알림 (D124): Lectern 이 켜져 있는 동안 메인 창 안에서만 — 시스템 알림·알림 영역·백그라운드는 쓰지 않는다.
// 1분마다 기억한 WORK.md 들을 읽어(GET /api/work — 바뀌지 않은 파일은 서버가 다시 읽지 않는다) 오늘 기준으로 계산한다:
//   시작 요약 — 켤 때·날짜가 바뀔 때 한 번 (마감 지남·오늘·D-3, 기한 지난·오늘 할 일, 오늘 일정)
//   일정 — 시각이 있는 일정의 10분 전 (이미 시작한 것은 건너뛴다 — 절전에서 깨도 몰려 나오지 않게)
//   기록 — 17:30 이 지나면 그날 한 번, 오늘 WORK.md 가 바뀌지 않은 진행 중 과제
// 띄운 알림은 메모리에만 기억한다 (디스크에 쓰지 않는다). 다시 켜면 시작 요약이 또 나온다. 설정 '업무 알림'(work_alerts)으로 끈다.

import { S, on } from './store.js';
import { solo } from './solo.js';
import { t } from './i18n.js';
import { loadBoard, notice, openBoard, openCard, redrawBoard } from './work.js';
import { daysBetween, dueTodos, dayEvents, eventsToRemind, pastLogTime, quietToday, isoDay, CLOSED } from './workdata.js';

const TICK_MS = 60 * 1000;
const FIRST_MS = 4000;   // 켠 뒤 처음 볼 때 — 탭을 되살리는 동안은 기다린다

let summaryDay = '';
let logDay = '';
const reminded = new Set();   // 알린 일정 (날짜 시각 내용)
let lastSign = '';            // 보이는 업무 현황을 다시 그릴지 — 읽은 글이 바뀌었을 때만

const wanted = () => S.config.work_alerts !== false && (!!S.config.work_home || (S.config.work_folders || []).length > 0);

function summary(b) {
  const lines = [];
  const open = b.rows.filter((r) => !CLOSED.has(r.card.status));
  const late = open.filter((r) => r.card.due && daysBetween(b.today, r.card.due) < 0);
  const todayDue = open.filter((r) => r.card.due === b.today);
  const soon = open.filter((r) => r.card.due && daysBetween(b.today, r.card.due) > 0 && daysBetween(b.today, r.card.due) <= 3);
  const cards = [...b.rows, ...(b.home ? [b.home] : [])].map((r) => r.card);
  const todos = dueTodos(cards, b.today).filter((x) => x.left <= 0);
  const events = dayEvents(cards, b.today);
  if (late.length) lines.push(t('마감 지남: {names}', { names: late.map((r) => r.title).join(', ') }));
  if (todayDue.length) lines.push(t('오늘 마감: {names}', { names: todayDue.map((r) => r.title).join(', ') }));
  if (soon.length) lines.push(t('마감 임박 (3일 안): {names}', { names: soon.map((r) => r.title).join(', ') }));
  if (todos.length) lines.push(t('기한이 지났거나 오늘인 할 일 {n}개', { n: todos.length }));
  if (events.length) lines.push(t('오늘 일정 {n}개 — 처음: {first}', { n: events.length, first: `${events[0].event.time || t('종일')} ${events[0].event.text}` }));
  const checks = [...open, ...(b.home ? [b.home] : [])].reduce((sum, r) => sum + r.card.problems.length, 0);
  if (checks) lines.push(t('확인할 줄 {n}개 — 업무 현황에서 고칠 곳을 봅니다', { n: checks }));
  return lines;
}

async function tick() {
  if (!wanted()) return;
  let b;
  try {
    b = await loadBoard();
  } catch {
    return;   // 서버가 잠깐 바쁨 — 다음 번에
  }
  const now = new Date();
  const today = isoDay(now);
  if (b.today !== today) return;   // 읽는 사이 자정이 지났다 — 다음 번에
  const sign = JSON.stringify([b.rows.map((r) => [r.path, r.mtime]), b.home?.mtime, b.bad.map((f) => f.path)]);
  if (lastSign && sign !== lastSign) redrawBoard();   // 다른 곳(Claude·편집기)에서 WORK.md 가 바뀌었다
  lastSign = sign;
  if (summaryDay !== today) {
    summaryDay = today;
    reminded.clear();
    const lines = summary(b);
    if (lines.length) notice({ title: t('오늘의 업무 — {day}', { day: today }), lines, actions: [{ label: t('업무 현황'), action: openBoard }] });
  }
  const rows = [...b.rows, ...(b.home ? [b.home] : [])];
  for (const { card, event, key } of eventsToRemind(rows.map((r) => r.card), now)) {
    if (reminded.has(key)) continue;
    reminded.add(key);
    const row = rows.find((r) => r.card === card);
    notice({
      title: t('{time} 일정 — 곧 시작합니다', { time: event.time }), lines: [`${event.text} (${row.home ? t('공통') : row.title})`], kind: 'soon',
      actions: [{ label: t('열기'), action: () => openCard(row.home ? 'home' : row.path, event.line) }],
    });
  }
  if (logDay !== today && pastLogTime(now)) {
    logDay = today;
    const quiet = quietToday(b.rows, today);
    if (quiet.length) {
      notice({
        title: t('오늘 기록이 없는 진행 중 과제 {n}개', { n: quiet.length }), lines: quiet.map((r) => r.title),
        actions: [{ label: t('업무 현황'), action: openBoard }],
      });
    }
  }
}

export function initWorkAlert() {
  if (solo) return;   // 메인 창에서만
  setTimeout(() => {
    tick();
    setInterval(tick, TICK_MS);
  }, FIRST_MS);
  on('work-changed', () => { lastSign = ''; });   // 일정을 넣었다 — 다음 번에 새로 견준다
}
