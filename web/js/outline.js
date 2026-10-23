// 코드 화면의 목차 (D43): 언어마다 정의(클래스·함수·메서드·형식)와 구분 주석, 설정 파일은 위 단계 키·섹션을 줄 단위 규칙으로 찾는다.
// 구문 분석기를 들이지 않는다 — 언어가 많고 빨라야 한다. 여러 줄 문자열·주석 안의 것을 잘못 잡을 수 있다 (목차일 뿐이다).
// 단계는 들여쓰기로 정한다 (더 들여 쓴 정의는 앞 정의의 아래). 결과: [{line(1부터), level(0~3), name, kind}]
// kind: section(구분 주석·영역) · class · type · function · method · key · selector · heading · label

// 확장자 → [highlight.js 언어, 보일 이름, 규칙 묶음]. highlight.js 에 없는 언어는 색 없이 글자로 (codeview.js)
const LANGS = {
  py: ['python', 'Python', 'python'], pyw: ['python', 'Python', 'python'],
  js: ['javascript', 'JavaScript', 'js'], mjs: ['javascript', 'JavaScript', 'js'], cjs: ['javascript', 'JavaScript', 'js'],
  jsx: ['javascript', 'JavaScript (JSX)', 'js'], ts: ['typescript', 'TypeScript', 'js'], tsx: ['typescript', 'TypeScript (TSX)', 'js'],
  json: ['json', 'JSON', 'json'], jsonc: ['json', 'JSON', 'json'], ipynb: ['json', 'Jupyter 노트북 (JSON)', 'json'],
  yaml: ['yaml', 'YAML', 'yaml'], yml: ['yaml', 'YAML', 'yaml'],
  toml: ['ini', 'TOML', 'ini'], ini: ['ini', 'INI', 'ini'], cfg: ['ini', '설정', 'ini'], conf: ['ini', '설정', 'ini'], env: ['bash', '환경 변수', 'env'],
  css: ['css', 'CSS', 'css'], scss: ['scss', 'SCSS', 'css'], less: ['less', 'Less', 'css'],
  htm: ['xml', 'HTML', 'html'], html: ['xml', 'HTML', 'html'], xml: ['xml', 'XML', 'none'], xsl: ['xml', 'XSL', 'none'],
  vue: ['xml', 'Vue', 'html'], svelte: ['xml', 'Svelte', 'html'],
  sh: ['bash', '셸 스크립트', 'shell'], bash: ['bash', 'Bash', 'shell'], zsh: ['bash', 'Zsh', 'shell'],
  bat: ['dos', '배치 파일', 'batch'], cmd: ['dos', '배치 파일', 'batch'],
  ps1: ['powershell', 'PowerShell', 'powershell'], psm1: ['powershell', 'PowerShell 모듈', 'powershell'],
  c: ['c', 'C', 'cfamily'], h: ['c', 'C 헤더', 'cfamily'], cc: ['cpp', 'C++', 'cfamily'], cpp: ['cpp', 'C++', 'cfamily'], hpp: ['cpp', 'C++ 헤더', 'cfamily'],
  cs: ['csharp', 'C#', 'java'], java: ['java', 'Java', 'java'], kt: ['kotlin', 'Kotlin', 'java'], swift: ['swift', 'Swift', 'java'],
  dart: ['dart', 'Dart', 'java'], go: ['go', 'Go', 'go'], rs: ['rust', 'Rust', 'rust'], rb: ['ruby', 'Ruby', 'ruby'],
  php: ['php', 'PHP', 'php'], sql: ['sql', 'SQL', 'sql'], r: ['r', 'R', 'r'], lua: ['lua', 'Lua', 'lua'], pl: ['perl', 'Perl', 'perl'],
  gradle: ['groovy', 'Gradle', 'java'], lock: ['plaintext', '잠금 파일', 'none'],
};

/** 파일 경로의 언어: {hljs, name, family} */
export function languageOf(path) {
  const ext = path.slice(path.lastIndexOf('.') + 1).toLowerCase();
  const [hljs, name, family] = LANGS[ext] || ['plaintext', ext.toUpperCase(), 'none'];
  return { hljs, name, family };
}

const ID = '[A-Za-z_$][\\w$]*';
const KEYWORDS = new Set(['if', 'for', 'while', 'switch', 'catch', 'function', 'return', 'else', 'do', 'try', 'with', 'typeof', 'sizeof', 'foreach', 'using', 'lock']);
// 구분 주석: '# ---- 그리기 ----', '// ==== 읽기 ====', '/* ---- 묶음 ---- */', '-- ---- 표 ----', '; ---- 섹션 ----'
const SECTION = /^\s*(?:\/\/+|\/\*+|#+|--|;+|')\s*[-=─━]{3,}\s*(.+?)\s*[-=─━]{3,}[-=─━\s]*(?:\*+\/)?\s*$/;

// 규칙: [정규식, kind, 이름이 든 묶음 번호]. 첫 묶음은 들여쓰기 (없으면 0)
const R = (src, kind, nameGroup = 2, flags = '') => [new RegExp(src, flags), kind, nameGroup];
const RULES = {
  python: [
    R('^(\\s*)class\\s+([A-Za-z_]\\w*)', 'class'),
    R('^(\\s*)(?:async\\s+)?def\\s+([A-Za-z_]\\w*)', 'function'),
  ],
  js: [
    R(`^(\\s*)(?:export\\s+(?:default\\s+)?)?(?:abstract\\s+)?class\\s+(${ID})`, 'class'),
    R(`^(\\s*)(?:export\\s+)?(?:declare\\s+)?(?:interface|type|enum)\\s+(${ID})`, 'type'),
    R(`^(\\s*)(?:export\\s+(?:default\\s+)?)?(?:async\\s+)?function\\s*\\*?\\s*(${ID})`, 'function'),
    R(`^(\\s*)(?:export\\s+)?(?:const|let|var)\\s+(${ID})\\s*=\\s*(?:async\\s+)?(?:function\\b|\\([^)]*\\)\\s*=>|${ID}\\s*=>)`, 'function'),
    R(`^(\\s+)(?:(?:static|async|get|set|public|private|protected|readonly|override)\\s+)*#?(${ID})\\s*\\([^)]*\\)\\s*(?::\\s*[^{]+)?\\{\\s*$`, 'method'),
  ],
  java: [
    R('^(\\s*)(?:[@\\w]+\\s+)*(?:class|interface|enum|record|struct|object|trait|protocol|extension)\\s+([A-Za-z_]\\w*)', 'class'),
    R('^(\\s*)(?:[@\\w]+\\s+)*(?:fun|func|def)\\s+(?:<[^>]*>\\s*)?([A-Za-z_]\\w*)', 'function'),
    R('^(\\s*)(?:(?:public|private|protected|internal|static|final|abstract|override|virtual|async|sealed|synchronized|extern|unsafe|partial|open)\\s+)+'
      + '[\\w<>\\[\\],.?\\s]*?\\b([A-Za-z_]\\w*)\\s*\\([^;]*$', 'method'),
  ],
  go: [
    R('^()type\\s+([A-Za-z_]\\w*)\\s+(?:struct|interface)', 'type'),
    R('^()func\\s+(?:\\([^)]*\\)\\s*)?([A-Za-z_]\\w*)', 'function'),
  ],
  rust: [
    R('^(\\s*)(?:pub(?:\\([^)]*\\))?\\s+)?(?:struct|enum|trait|union|type)\\s+([A-Za-z_]\\w*)', 'type'),
    R('^(\\s*)impl(?:<[^>]*>)?\\s+([\\w:<>, ]+?)\\s*(?:\\{|where|$)', 'class'),
    R('^(\\s*)(?:pub(?:\\([^)]*\\))?\\s+)?(?:const\\s+)?(?:async\\s+)?(?:unsafe\\s+)?(?:extern\\s+"[^"]*"\\s+)?fn\\s+([A-Za-z_]\\w*)', 'function'),
    R('^(\\s*)(?:pub(?:\\([^)]*\\))?\\s+)?mod\\s+([A-Za-z_]\\w*)', 'section'),
  ],
  cfamily: [
    R('^(\\s*)(?:template\\s*<[^>]*>\\s*)?(?:class|struct|namespace|union|enum(?:\\s+class)?)\\s+([A-Za-z_]\\w*)\\s*(?::[^;{]*)?\\{?\\s*$', 'class'),
    R('^()(?!(?:if|for|while|switch|return|else|do|typedef)\\b)[A-Za-z_][\\w:*&<>,\\s]*?[\\s*&]([A-Za-z_~][\\w:~]*)\\s*\\([^;]*\\)\\s*(?:const\\s*)?(?:noexcept\\s*)?\\{?\\s*$', 'function'),
  ],
  ruby: [
    R('^(\\s*)(?:class|module)\\s+([A-Z][\\w:]*)', 'class'),
    R('^(\\s*)def\\s+((?:self\\.)?[\\w?!=]+)', 'function'),
  ],
  php: [
    R('^(\\s*)(?:abstract\\s+|final\\s+)?(?:class|interface|trait|enum)\\s+([A-Za-z_]\\w*)', 'class'),
    R('^(\\s*)(?:(?:public|private|protected|static|abstract|final)\\s+)*function\\s+&?([A-Za-z_]\\w*)', 'function'),
  ],
  lua: [R('^(\\s*)(?:local\\s+)?function\\s+([\\w.:]+)', 'function')],
  perl: [R('^(\\s*)sub\\s+(\\w+)', 'function'), R('^()package\\s+([\\w:]+)', 'class')],
  r: [R('^(\\s*)([\\w.]+)\\s*(?:<-|=)\\s*function\\b', 'function')],
  shell: [
    R('^(\\s*)function\\s+([A-Za-z_][\\w-]*)', 'function'),
    R('^(\\s*)([A-Za-z_][\\w-]*)\\s*\\(\\)\\s*\\{?', 'function'),
  ],
  powershell: [
    R('^(\\s*)#region\\s+(.+)$', 'section', 2, 'i'),
    R('^(\\s*)class\\s+([A-Za-z_]\\w*)', 'class', 2, 'i'),
    R('^(\\s*)(?:function|filter)\\s+([\\w-]+)', 'function', 2, 'i'),
  ],
  batch: [R('^():([A-Za-z_][\\w-]*)\\s*$', 'label')],
  sql: [R('^(\\s*)create\\s+(?:or\\s+replace\\s+)?(?:temporary\\s+|temp\\s+|unique\\s+)?((?:table|view|function|procedure|index|trigger|schema|type)\\s+(?:if\\s+not\\s+exists\\s+)?[\\w."`\\[\\]]+)', 'type', 2, 'i')],
  css: [
    R('^()(@(?:media|supports|layer|container|keyframes|font-face)\\b[^{]*?)\\s*\\{', 'section'),
    R('^()([^\\s@}/][^{]*?)\\s*\\{', 'selector'),
  ],
  ini: [R('^(\\s*)\\[\\[?([^\\]]+)\\]\\]?', 'section')],
  env: [R('^()(?:export\\s+)?([A-Za-z_][A-Za-z0-9_]*)\\s*=', 'key')],
};

/** 들여쓰기 칸 수 (탭은 4칸) */
const width = (s) => s.replace(/\t/g, '    ').length;

/** 들여쓰기로 단계를 매긴다: 더 들여 쓴 항목은 앞 항목의 아래. 구분 주석은 늘 맨 위 단계 */
function leveled(items) {
  const stack = [];
  for (const it of items) {
    if (it.kind === 'section') {
      stack.length = 0;
      it.level = 0;
      continue;
    }
    while (stack.length && stack[stack.length - 1] >= it.indent) stack.pop();
    it.level = Math.min(stack.length, 3);
    stack.push(it.indent);
  }
  return items.map(({ line, level, name, kind }) => ({ line, level, name, kind }));
}

/** 줄 단위 규칙으로 찾는다 */
function byRules(lines, rules) {
  const items = [];
  lines.forEach((text, i) => {
    const sec = SECTION.exec(text);
    if (sec) {
      items.push({ line: i + 1, indent: 0, name: sec[1].replace(/[-=─━\s]+$/, ''), kind: 'section' });
      return;
    }
    for (const [re, kind, g] of rules) {
      const m = re.exec(text);
      if (!m || !m[g]) continue;
      const name = m[g].trim().replace(/\s+if\s+not\s+exists\b/i, '').replace(/^(table|view|function|procedure|index|trigger|schema|type)\b/i, (w) => w.toUpperCase());   // SQL: 'TABLE users'
      if (KEYWORDS.has(name)) continue;
      const indent = width(m[1] || '');
      items.push({ line: i + 1, indent, name, kind: kind === 'function' && indent > 0 ? 'method' : kind });
      break;
    }
  });
  return leveled(items);
}

/** json: 위 두 단계의 키 (들여쓰기 단위는 처음 들여 쓴 줄로 정한다) */
function jsonKeys(lines) {
  let unit = 0;
  const items = [];
  lines.forEach((text, i) => {
    const m = /^(\s*)"((?:[^"\\]|\\.)+)"\s*:/.exec(text);
    if (!m) return;
    const w = width(m[1]);
    if (!w) return;   // 한 줄로 쓴 JSON
    unit ||= w;
    const depth = w / unit;
    if (depth === 1 || depth === 2) items.push({ line: i + 1, level: depth - 1, name: m[2], kind: 'key' });
  });
  return items;
}

/** yaml: 위 두 단계의 키 */
function yamlKeys(lines) {
  let unit = 0;
  const items = [];
  lines.forEach((text, i) => {
    const m = /^(\s*)(?:-\s+)?([^\s#:'"{}[\],&*!|>%@`-][^:#]*?|"[^"]+"|'[^']+')\s*:(?:\s|$)/.exec(text);
    if (!m) return;
    const w = width(m[1]);
    if (w && !unit) unit = w;
    const depth = w ? w / unit : 0;
    if (depth <= 1) items.push({ line: i + 1, level: depth, name: m[2].replace(/^["']|["']$/g, ''), kind: 'key' });
  });
  return items;
}

/** html·vue·svelte: 제목(h1~h6)과 맨 위 template·script·style */
function htmlOutline(lines) {
  const items = [];
  lines.forEach((text, i) => {
    const top = /^<(template|script|style)\b/i.exec(text);
    if (top) items.push({ line: i + 1, level: 0, name: `<${top[1].toLowerCase()}>`, kind: 'section' });
    for (const m of text.matchAll(/<h([1-6])\b[^>]*>(.*?)<\/h\1>/gi)) {
      const name = m[2].replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').trim();
      if (name) items.push({ line: i + 1, level: Math.min(Number(m[1]) - 1, 3), name, kind: 'heading' });
    }
  });
  return items;
}

const MAX_ITEMS = 2000;

/** 코드 파일(path)의 목차 */
export function outlineOf(path, text) {
  const lines = text.split('\n');
  const { family } = languageOf(path);
  let items;
  if (family === 'json') items = jsonKeys(lines);
  else if (family === 'yaml') items = yamlKeys(lines);
  else if (family === 'html') items = htmlOutline(lines);
  else items = byRules(lines, RULES[family] || []);
  return items.slice(0, MAX_ITEMS);
}
