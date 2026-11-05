// 자동 이스케이프 (D89): html`<p>${값}</p>` 의 값은 글로 들어간다 — 태그가 되지 않는다.
// 화면에 HTML 을 넣는 길은 setHtml·addHtml 둘이다 (tests/test_rules.py 가 innerHTML 을 바로 쓰는 곳을 잡는다).
//
// 값은 이렇게 들어간다: html`` 의 결과는 그대로, 배열은 이어서 (.join('') 을 쓰면 글이 되어 이스케이프된다),
// 그 밖에는 esc 와 같다 — null·undefined 는 빈칸, false 는 'false' (aria-pressed="${on}" 이 되게).
// 조건은 ${on ? html`…` : ''} 로 쓴다. ${on && html`…`} 은 꺼졌을 때 false 가 글로 보인다.
//
// html`` 의 결과는 글이 아니다. a + b, += 로 이으면 글이 되어 통째로 이스케이프된다 — 배열에 모아 html`${조각들}` 로.
// raw(글) 은 이미 안전하다고 약속하는 것이다 (DOMPurify 를 거친 HTML 등). 쓰는 곳은 시험이 세어 둔다.

const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

/** 글을 HTML 글자로. 화면에는 html`` 을 쓰고, 이것은 html 밖의 글(내려받을 HTML 등)에 */
export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ESC[c]);

/** 이미 안전한 HTML 조각 */
export class Safe {
  /** @param {string} text */
  constructor(text) {
    this.text = text;
  }

  toString() {
    return this.text;
  }
}

/** @returns {string} */
const piece = (value) => {
  if (value instanceof Safe) return value.text;
  if (Array.isArray(value)) return value.map(piece).join('');
  return esc(value);
};

/**
 * @param {TemplateStringsArray} strings
 * @param {...any} values
 * @returns {Safe}
 */
export function html(strings, ...values) {
  let out = strings[0];
  values.forEach((value, i) => {
    out += piece(value) + strings[i + 1];
  });
  return new Safe(out);
}

/** @param {string} text 이미 안전한 HTML */
export const raw = (text) => new Safe(String(text ?? ''));

/**
 * el 의 내용을 바꾼다. Safe 가 아닌 글은 글자 그대로 보인다
 * @param {Element} el
 * @param {Markup} value
 */
export function setHtml(el, value) {
  el.innerHTML = piece(value);
}

/**
 * @param {Element} el
 * @param {InsertPosition} where
 * @param {Markup} value
 */
export function addHtml(el, where, value) {
  el.insertAdjacentHTML(where, piece(value));
}
