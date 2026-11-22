// 번호·글머리 글자로 시작하는 제목·문단·목록 항목의 내어쓰기 (D191) — 화면에서 둘째 줄로 꺾이면 그 글자 뒤에 맞춰 들여 쓴다.
//
// - '1. 요약'·'1.2 생산성'·'가.'·'(1)'·'①'·'□'·'○'·'ㅇ'·'※'·'[1]' 처럼 보고서에 흔한 머리 글자만 본다. Markdown 목록의 글머리표·번호는 브라우저가 이미 맞춘다.
// - 폭은 글자 종류마다의 평균 폭(em)으로 어림한다 — 재지 않는다. 스타일·글꼴마다 조금씩 다르지만(사용자 요청: 평균에 맞춤) 글자 크기·배율은 em 이 따라가고,
//   화면 밖에서 그려도·내보낸 html 에서도 같다. 어림값은 tools/edges/hang.py 가 모든 스타일에서 잰 실제 폭과 견준다.
// - CSS 는 base.css 의 `.lec-hang` — `text-indent: <폭> hanging each-line`. 첫 줄과 줄바꿈(<br>) 뒤의 줄은 그대로, 꺾인 줄만 들여 쓴다.
//   블록의 글이나 구조는 바꾸지 않는다 (class 와 CSS 변수 --lec-hang 만).
// - 가운데·오른쪽 맞춘 블록(캡션, 책·논문 스타일의 제목)과 표의 칸, 할 일 항목, Lectern 슬라이드는 건너뛴다.

/** 글머리 글자 — 뒤에 빈칸이 있어야 한다 ('○○ 기관'의 ○ 는 글머리가 아니다) */
const BULLETS = '□■▢▣◇◆◈○●◎◉◦•‣∙·ㆍ▪▫►▶▷▸▹→⇒➔➜➢➤★☆✓✔✗✘❖ㅁㅇ-–—+';
/** 빈칸 없이 붙여 써도 머리 글자인 것 — ※, 둥근·괄호 번호(①⑴⒈ⓐ❶➀㈀㉠ …) */
const TIGHT = /^(?:※|[①-⓿❶-➓㈀-㉟㉠-㉿])/u;
/** 번호 — 뒤에 빈칸이 있어야 한다 */
const NUMBERS = [
  /^\(?\d{1,3}\)/,                                   // (1)  1)
  /^\[\d{1,3}\]/,                                    // [1] — 참고 문헌
  /^[1-9]\d{0,2}(?:[.-][1-9]\d?){0,3}[.)]/,          // 1.  1.2.  1-1.  1-1)  100.   (첫 자리 1~999·다음 자리 1~99 — '0.50.0' 같은 판 번호·'2024.' 는 아니다)
  /^[1-9]\d{0,2}(?:\.[1-9]\d?){1,3}(?=\s)/,          // 1.2   ('3 가지'·'2024년'·'8-1 의'는 아니다 — 붙임표 꼴은 '1-1.' 처럼 점이 있어야)
  /^\(?[가나다라마바사아자차카타파하][.)]/,            // 가.  나)  (다)
  /^\(?[A-Za-z]\)/, /^[A-Za-z]\./,                   // a)  (a)  A.
  /^[Ⅰ-ⅿ]{1,3}[.)]?/u,                     // Ⅰ.  Ⅱ  ⅲ)
  /^(?:I{1,3}|IV|VI{0,3}|IX|X)[.)]/,                 // I.  IV.
  /^제\s?\d{1,3}\s?[장절조편관항부]/,                   // 제1장
];

/** 좁은 글자의 평균 폭 (em) — 25가지 스타일에서 잰 값의 가운데 (2026-11-22, tools/edges/hang.py 가 어림값과 잰 값의 차이를 본다) */
const NARROW = {
  ' ': 0.28, ' ': 0.28, '.': 0.22, ',': 0.22, '(': 0.32, ')': 0.32, '[': 0.31, ']': 0.31, '-': 0.33, '+': 0.68, '–': 0.5,
  '•': 0.4, '‣': 0.4, '∙': 0.3, '·': 0.22, '▪': 0.35, '□': 0.6, '●': 0.6, '■': 0.85, '○': 0.85, '✓': 0.68, '→': 0.86, '❶': 1.32,
  I: 0.3,
};

/** 글자 하나의 평균 폭 (em) */
function charEm(c) {
  if (c in NARROW) return NARROW[c];
  if (/\d/.test(c)) return 0.5;
  if (/[A-Z]/.test(c)) return 0.63;
  if (/[a-z]/.test(c)) return 0.48;
  if (/[가-힣ㄱ-ㆎ]/u.test(c)) return 0.93;
  return 1;   // 한자·둥근 번호·로마 숫자 글자·◇▶※ 같은 기호 — 전각
}

/** 머리 글자와 그 뒤의 빈칸 — 없으면 '' */
export function hangPrefix(text) {
  const s = text.replace(/^[ \t\n\r]+/, '');
  const gapAfter = (mark) => /^[ \t ]*/.exec(s.slice(mark.length))[0];
  /** 머리 글자 다음에 꺾일 글이 있어야 한다 (머리 글자뿐인 줄은 아니다) */
  const done = (mark, gap) => (s.slice(mark.length + gap.length).trim() ? mark + gap : '');
  const tight = TIGHT.exec(s)?.[0];
  if (tight) return done(tight, gapAfter(tight));
  const marks = [BULLETS.includes(s[0] ?? '\0') ? s[0] : '', ...NUMBERS.map((re) => re.exec(s)?.[0] ?? '')];
  for (const mark of marks) {
    const gap = mark && gapAfter(mark);
    if (gap) return done(mark, gap);   // 빈칸이 없으면 다음 꼴을 본다 ('1.2 생산성'은 '1.' 이 아니라 '1.2')
  }
  return '';
}

/** 내어쓸 폭 (em) — 이어진 빈칸은 화면에서 하나로 보이므로 하나로 센다 (줄 바꿈 없는 빈칸 nbsp 는 그대로) */
export function hangEm(prefix) {
  let em = 0;
  let space = false;
  for (const c of prefix) {
    if (c === ' ' || c === '\t' || c === '\n') {
      if (!space) em += charEm(' ');
      space = true;
      continue;
    }
    space = false;
    em += charEm(c);
  }
  return Math.round(em * 100) / 100;
}

/**
 * 블록 글의 머리 글자 — 줄바꿈(<br>)으로 나뉜 줄마다 보고, 머리 글자가 있는 줄 가운데 가장 긴 줄의 것 (꺾이는 것은 긴 줄이다. 폭은 블록에 하나뿐이라
 * '□ 제목 / ○ 내용 / - 세부' 처럼 줄마다 다르면 긴 줄에 맞춘다). 첫 줄에 머리 글자가 없으면 줄의 반 넘게 머리 글자가 있을 때만 ('다음과 같다' 뒤의 ①·② 줄들)
 * @param {string} text
 * @returns {{ prefix: string, at: number } | null} at: 글에서 그 머리 글자가 시작하는 자리
 */
export function blockHang(text) {
  const lines = [];
  let at = 0;
  for (const line of text.split('\n')) {
    const lead = line.length - line.replace(/^[ \t\r]+/, '').length;
    if (line.trim()) lines.push({ prefix: hangPrefix(line), at: at + lead, len: line.trim().length });
    at += line.length + 1;
  }
  const marked = lines.filter((x) => x.prefix);
  if (!marked.length || (!lines[0].prefix && marked.length * 2 <= lines.length)) return null;
  const best = marked.reduce((x, y) => (y.len > x.len ? y : x));
  return { prefix: best.prefix, at: best.at };
}

/** 볼 블록: 제목·문단·목록 항목 (문단으로 시작하는 항목은 그 문단이 본다) */
const SKIP = '.front-matter, .lec-doctoc, table, pre, .lec-slide-wrap, .diagram-error, .lec-caption, .task-list-item';
const INLINE = /^(A|B|STRONG|EM|I|CODE|SPAN|MARK|KBD|SUP|SUB|S|DEL|U|SMALL|IMG|BR|WBR|INPUT|LABEL|ABBR|Q|CITE|DFN|TIME|VAR|SAMP|INS)$/;

/** 목록 항목이 문단·블록으로 시작하는지 (그러면 그 문단이 따로 본다) */
function firstChildIsBlock(li) {
  for (const n of li.childNodes) {
    if (n.nodeType === Node.TEXT_NODE && !n.data.trim()) continue;
    return n.nodeType === Node.ELEMENT_NODE && !INLINE.test(/** @type {Element} */ (n).tagName);
  }
  return true;
}

/** 블록 자신의 글 — 목록 항목이면 하위 목록·코드 같은 안의 블록 앞까지 (textContent 의 앞부분이라 글자 자리가 같다) */
function ownText(el) {
  if (el.tagName !== 'LI') return el.textContent ?? '';
  let s = '';
  for (const n of el.childNodes) {
    if (n.nodeType === Node.ELEMENT_NODE && !INLINE.test(/** @type {Element} */ (n).tagName)) break;
    s += n.textContent ?? '';
  }
  return s;
}

/**
 * 그린 문서(root)의 블록에 내어쓰기를 단다 — `lec-hang` 과 `--lec-hang`. 무대(화면 밖)에서 불러도 된다 (가운데 맞춤만 스타일에서 읽는다)
 * @param {ParentNode} root
 */
export function markHangs(root) {
  const found = [];
  for (const el of /** @type {NodeListOf<HTMLElement>} */ (root.querySelectorAll('h1, h2, h3, h4, h5, h6, p, li'))) {
    if (el.closest(SKIP)) continue;
    if (el.tagName === 'LI' && firstChildIsBlock(el)) continue;
    const hang = blockHang(ownText(el));
    if (hang) found.push([el, hangEm(hang.prefix)]);
  }
  // 스타일을 읽는 것은 머리 글자가 있는 블록만, 쓰기 전에 모두 읽는다 (읽고 쓰기를 번갈아 하면 블록마다 스타일을 다시 계산한다)
  const aligned = found.filter(([el]) => !/^(center|right|end)$/.test(getComputedStyle(el).textAlign));
  for (const [el, em] of aligned) {
    el.classList.add('lec-hang');
    el.style.setProperty('--lec-hang', `${em}em`);
  }
}

/** 블록 글(textContent)의 i 번째 글자의 상자 — 글자가 없거나 보이지 않으면 null */
function charBox(el, i) {
  const walk = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  let at = 0;
  for (let n = walk.nextNode(); n; n = walk.nextNode()) {
    const len = /** @type {Text} */ (n).length;
    if (i < at + len) {
      const r = document.createRange();
      r.setStart(n, i - at);
      r.setEnd(n, i - at + 1);
      return [...r.getClientRects()].find((b) => b.width > 0) ?? null;
    }
    at += len;
  }
  return null;
}

/**
 * 그린 칸에서 머리 글자의 실제 폭을 재어 `--lec-hang-fit` 에 — 화면은 그 값을, 종이·내보낸 html·지면 틀은 어림값(--lec-hang)을 쓴다 (글꼴이 다르다).
 * 칸에 붙은 뒤에 부른다: 그리려면 어차피 배치하므로 재는 값이 따로 들지 않는다. 숨은 블록·첫 줄에서 머리 글자와 글이 갈린 블록은 어림값 그대로
 * @param {ParentNode} root
 */
export function fitHangs(root) {
  const fits = [];
  for (const el of /** @type {NodeListOf<HTMLElement>} */ (root.querySelectorAll('.lec-hang'))) {
    const hang = blockHang(ownText(el));
    const a = hang ? charBox(el, hang.at) : null;
    const b = a && hang ? charBox(el, hang.at + hang.prefix.length) : null;
    const size = b ? parseFloat(getComputedStyle(el).fontSize) : 0;
    if (!a || !b || !size || Math.abs(b.top - a.top) > size / 2 || b.left <= a.left) continue;
    fits.push([el, Math.round(((b.left - a.left) / size) * 100) / 100]);
  }
  for (const [el, em] of fits) el.style.setProperty('--lec-hang-fit', `${em}em`);   // 다 잰 뒤에 쓴다
}
