#!/usr/bin/env python3
"""pptx 를 Lectern 전체의 pptx 스타일로 등록한다 (D102). 같은 이름의 템플릿 묶음은 Claude 가 안내를 보고 쓴다.

    python register_style.py 양식.pptx 출력폴더 --name 회사 보고
    python register_style.py --active 출력폴더 --name 회사 보고

보관소(설정 폴더의 pptx-styles)에 이름.pptx 와 미리보기 그림 이름-1.png(표지)·이름-2.png(본문)을 둔다.
출력폴더에는 양식 안내(reference.py)가 생긴다. 출력의 group 이 템플릿 묶음을 쓸 자리다.
"""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import reference  # noqa: E402


def config_folder():
    if os.environ.get('LECTERN_CONFIG_DIR'):
        return Path(os.environ['LECTERN_CONFIG_DIR'])
    if os.environ.get('APPDATA'):
        return Path(os.environ['APPDATA']) / 'Lectern'
    raise SystemExit('Lectern 설정 폴더를 찾지 못했습니다')


def stop(message):
    print(json.dumps({'error': message}, ensure_ascii=False))
    return 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('paths', nargs='+', help='원본.pptx 출력폴더, 또는 --active 일 때 출력폴더')
    ap.add_argument('--active', action='store_true')
    ap.add_argument('--pick', default='')
    ap.add_argument('--name', required=True, help='스타일 이름. 템플릿 묶음도 같은 이름으로 쓴다')
    ap.add_argument('--force', action='store_true', help='같은 이름의 스타일을 바꾼다. 사용자에게 물은 뒤에만')
    ap.add_argument('--no-powerpoint', action='store_true', help='미리보기 그림 없이')
    args = ap.parse_args(argv)
    if any(c in args.name for c in '<>:"/\\|?*') or not args.name.strip():
        return stop('스타일 이름에 쓸 수 없는 글자가 있습니다')
    library = config_folder() / 'pptx-styles'
    target = library / f'{args.name}.pptx'
    if target.exists() and not args.force:
        return stop(f"'{args.name}' 스타일이 이미 있습니다. 바꿔도 되는지 사용자에게 물은 뒤 --force 를 주세요")
    forward = [*(['--active'] if args.active else []), *args.paths, '--name', args.name, *(['--pick', args.pick] if args.pick else []),
               *(['--no-powerpoint'] if args.no_powerpoint else []), *(['--force'] if args.force else [])]
    code = reference.main(forward)
    if code:
        return code
    out = Path(args.paths[-1]).resolve()
    work = out / '.pptx-work' / f'{args.name}-양식'
    source = work / 'source.pptx'
    if not source.exists():
        return stop('pptx 사본을 받지 못해 스타일로 등록할 수 없습니다. DRM 이 저장을 막았을 수 있습니다')
    library.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    pictures = sorted((work / 'ref').glob('*.png')) if (work / 'ref').is_dir() else []
    previews = []
    for n, picture in enumerate(pictures[:1] + pictures[1:2], 1):
        path = library / f'{args.name}-{n}.png'
        shutil.copyfile(picture, path)
        previews.append(path.name)
    print(json.dumps({'style': str(target), 'previews': previews, 'guide': str(out / f'{args.name}-양식.md'),
                      'group': str(config_folder() / 'templates' / f'{args.name}.md')}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
