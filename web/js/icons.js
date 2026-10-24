// 사이드바 목록(문서 트리·최근 변경·파일)의 파일 종류 아이콘. 그림은 index.html 의 i-* 기호, 모양은 app.css 의 .ficon.
// 문서(md·트리에 보이는 html)는 강조색으로 다른 파일과 구분한다. 여는 방법은 아이콘과 상관없이 서버가 정한다 (osutil.how_to_open).

import { t } from './i18n.js';

const KINDS = {
  image: 'png jpg jpeg gif webp bmp svg ico tif tiff heic avif',
  table: 'csv tsv xls xlsx xlsm xlsb ods',
  text: 'txt log pdf doc docx docm rtf odt hwp hwpx ppt pptx pptm odp key pages tex rst',
  code: 'py pyw js mjs cjs ts tsx jsx json jsonc yaml yml toml ini cfg conf env css scss less htm html xml xsl sh bash zsh bat cmd '
    + 'ps1 psm1 c h cc cpp hpp cs java kt go rs rb php sql r ipynb vue svelte lua swift dart pl gradle lock',
  archive: 'zip 7z rar tar gz tgz bz2 xz cab iso',
  media: 'mp3 wav flac m4a ogg mp4 mov avi mkv webm wmv',
  app: 'exe msi msix dll sys com scr lnk url jar apk',
};
const KIND_OF = new Map(Object.entries(KINDS).flatMap(([kind, exts]) => exts.split(' ').map((x) => [x, kind])));

const svg = (id, extra = '') => `<svg class="ficon${extra}" aria-hidden="true"><use href="#i-${id}"/></svg>`;

/** 파일 이름 앞의 아이콘. docKind 가 있으면 문서 (scanner 의 kind: markdown | html) */
export function fileIcon(name, docKind) {
  if (docKind === 'markdown') return svg('md', ' doc');
  if (docKind === 'html') return svg('html', ' doc');
  const i = name.lastIndexOf('.');
  return svg((i > 0 && KIND_OF.get(name.slice(i + 1).toLowerCase())) || 'file');
}

export const folderIcon = () => svg('folder');

/** 코드 파일인지 (사이드바 '코드' 목록 — others.js): 아이콘의 코드 종류와 같다 — 소스·스크립트·웹(css·소스 폴더의 html)·설정 */
export function isCode(name) {
  const i = name.lastIndexOf('.');
  return i > 0 && KIND_OF.get(name.slice(i + 1).toLowerCase()) === 'code';
}

// 코드 화면에서 보는 자료 (D60): csv·tsv 는 표, txt·log 는 글자 그대로. '자료' 목록에 남고, 누르면 코드처럼 Lectern 에서 본다
export const DATA_VIEW_EXT = new Set(['csv', 'tsv', 'txt', 'log']);

/** Lectern 의 코드 화면에서 보는 파일 — 코드 + csv·tsv·txt·log */
export function isViewable(name) {
  const i = name.lastIndexOf('.');
  return isCode(name) || (i > 0 && DATA_VIEW_EXT.has(name.slice(i + 1).toLowerCase()));
}

// 모아 보기의 '파일 종류' (D50): 확장자 → 형식 이름. 같은 프로그램이 여는 형식은 한 이름으로 (엑셀·파워포인트·워드·한글 등), 나머지는 확장자를 대문자로
const TYPE_NAMES = [
  [t('엑셀'), 'xls xlsx xlsm xlsb'], [t('파워포인트'), 'ppt pptx pptm'], [t('워드'), 'doc docx docm'], [t('한글'), 'hwp hwpx'],
  ['Markdown', 'md markdown'], ['HTML', 'html htm'], ['JPG', 'jpg jpeg'], ['TIFF', 'tif tiff'], ['YAML', 'yaml yml'],
];
const TYPE_OF = new Map(TYPE_NAMES.flatMap(([label, exts]) => {
  const key = exts.split(' ')[0];
  return exts.split(' ').map((x) => [x, { key, label }]);
}));
/** 브라우저가 그릴 수 있는 그림 — 파일 종류에서 작은 그림으로 */
export const PICTURE_EXT = new Set('png jpg jpeg gif webp bmp svg ico avif'.split(' '));

export const extOf = (name) => {
  const i = name.lastIndexOf('.');
  return i > 0 ? name.slice(i + 1).toLowerCase() : '';
};

/** 파일 이름 → 형식 {key, label} (확장자가 없으면 key '') */
export function fileType(name) {
  const ext = extOf(name);
  if (!ext) return { key: '', label: t('확장자 없음') };
  return TYPE_OF.get(ext) || { key: ext, label: ext.toUpperCase() };
}
