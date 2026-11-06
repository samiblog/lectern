// 문서가 준 CSS 를 앱에 들이기 전에 거른다 (D96 — 맨 앞 설정 style:, <style>, <style scoped>).
// 글자를 치환해서는 막지 못한다: CSS 는 이스케이프(u\72l)·문자열·주석을 해석기가 풀기 때문에 눈으로 찾는 글과 해석기가 읽는 글이 다르다.
// 그래서 브라우저의 해석기로 읽고, 정규화된 규칙만 다시 쓴다 — 여는 괄호를 벗어나는 글이 남지 않고, 이스케이프도 풀린 값을 본다.
// 규칙은 슬라이드의 틀 안에 중첩해서 넣으므로 그 안만 고른다. & 는 부모를 건너뛰는 길(:has(&) #앱요소)이라 그런 선택자는 버린다.

const LOADS = /\b(?:url|src|image-set|image|cross-fade|element|paint)\s*\(/i;
const INNER_REF = /url\(\s*(['"]?)(?:data:image\/|#)[^)]*\)/gi;   // 문서 안의 그림·SVG 참조는 요청을 내지 않는다

/** 값이 무엇을 불러올 수 있으면 true. 이스케이프가 남은 값(사용자 변수는 풀리지 않는다)도 믿지 않는다 */
const unsafe = (value) => value.includes('\\') || LOADS.test(value.replace(INNER_REF, ''));

const POSITIONS = new Set(['static', 'relative', 'absolute', 'sticky']);   // fixed 는 슬라이드를 벗어나 앱을 덮는다 (var() 로 숨길 수 있어 허용 목록으로)

function cleanStyle(style) {
  for (const name of [...style]) {
    const value = style.getPropertyValue(name);
    if (unsafe(value) || (name === 'position' && !POSITIONS.has(value))) style.removeProperty(name);
  }
}

/** 규칙 하나를 안전한 글로. 버리면 빈 글. 글꼴·@import·키프레임은 들이지 않는다 */
function ruleText(rule) {
  if (rule instanceof CSSStyleRule) {
    if (rule.selectorText.includes('&')) return '';
    while (rule.cssRules?.length) rule.deleteRule(0);
    cleanStyle(rule.style);
    // 변수를 쓴 줄임 속성(background: var(--a) url(…))은 세부 값이 비어 위에서 보이지 않는다 — 다시 쓴 글 전체로 한 번 더 본다
    return rule.style.length && !unsafe(rule.style.cssText) ? rule.cssText : '';
  }
  if (rule instanceof CSSMediaRule) {
    const inner = [...rule.cssRules].map(ruleText).filter(Boolean).join('\n');
    return inner ? `@media ${rule.media.mediaText} {\n${inner}\n}` : '';
  }
  return '';
}

/** 문서의 CSS 를 parent 선택자 안에 가둔 글로 */
export function confinedCss(css, parent) {
  const sheet = new CSSStyleSheet();
  sheet.replaceSync(String(css));
  const rules = [...sheet.cssRules].map(ruleText).filter(Boolean);
  return rules.length ? `${parent} {\n${rules.join('\n')}\n}` : '';
}
