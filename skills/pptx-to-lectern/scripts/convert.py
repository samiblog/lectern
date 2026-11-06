#!/usr/bin/env python3
"""pptx 하나를 Lectern 발표 문서 초안으로 바꾼다: 읽기 → 쪽 그림 → 초안 → 검증.

    python convert.py 원본.pptx 출력폴더 [--name 이름] [--level 3] [--no-powerpoint] [--force]
    python convert.py --active 출력폴더 [--pick 이름] [--name 이름]     PowerPoint 에 띄워 둔 발표

읽기는 ZIP 안 XML 로 먼저 한다. 빠르고 PowerPoint 가 없어도 된다.
ZIP 으로 못 여는 파일(.ppt, DRM)은 PowerPoint 로 pptx 사본을 받아 읽고, 사본이 막히면 PowerPoint 에서 직접 읽는다.
띄워 둔 발표는 저장 전의 수정까지 포함해 사본을 받는다. 그 발표를 닫거나 저장하지 않는다.
PowerPoint 가 있으면 쪽 그림을 뽑고 EMF 를 PNG 로 받는다.
작업 파일은 출력폴더의 .pptx-work/<이름>/ 에 둔다 (Lectern 트리에 나오지 않는다).
source.pptx 는 이때의 원본이다. 되돌릴 때 쪽 번호가 이 판을 가리키니 지우지 않는다.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import draft_md  # noqa: E402
import read_pptx  # noqa: E402
import verify  # noqa: E402

OLE_HEAD = bytes.fromhex('d0cf11e0a1b11ae1')
OPEN_LIMIT = 60        # 이 안에 못 열면 보이지 않는 창에서 멈춘 것으로 본다
TOTAL_LIMIT = 1800
PPTX_FORMAT = 24       # ppSaveAsOpenXMLPresentation


def has_com():
    try:
        import win32com.client  # noqa: F401
        return True
    except ImportError:
        return False


def encrypted(deck):
    """암호를 건 pptx 는 ZIP 이 아니라 EncryptedPackage 가 든 OLE 파일이다. 열어 보기 전에 알 수 있다."""
    with open(deck, 'rb') as f:
        if f.read(8) != OLE_HEAD:
            return False
        return 'EncryptedPackage'.encode('utf-16-le') in f.read(256 * 1024 * 1024)


def powerpoint_pids():
    try:
        out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq POWERPNT.EXE', '/FO', 'CSV', '/NH'], capture_output=True, timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        return set()
    return set(re.findall(rb'"POWERPNT\.EXE","(\d+)"', out))


def remove(path):
    """끊긴 PowerPoint 가 파일을 잠시 잡고 있을 수 있다. 못 지워도 작업 폴더의 파일일 뿐이다."""
    for _ in range(10):
        try:
            path.unlink(missing_ok=True)
            return
        except OSError:
            time.sleep(.5)


class Turn:
    """PowerPoint 는 한 프로세스를 나눠 쓰니 변환을 한 번에 하나씩 돌린다."""

    def __init__(self, wait=240):
        self.path = Path(tempfile.gettempdir()) / 'pptx-to-lectern.lock'
        self.wait = wait
        self.held = False

    def __enter__(self):
        end = time.time() + self.wait
        while time.time() < end:
            try:
                os.close(os.open(self.path, os.O_CREAT | os.O_EXCL))
                self.held = True
                return self
            except FileExistsError:
                if time.time() - self.path.stat().st_mtime > 2 * TOTAL_LIMIT:
                    remove(self.path)      # 끊긴 변환이 남긴 잠금
                time.sleep(1)
        return self                         # 오래 기다렸으면 그냥 간다

    def __exit__(self, *_):
        if self.held:
            remove(self.path)


def run_com(mode, work, deck='', pick=''):
    """PowerPoint 일은 자식 프로세스로 돌린다. 암호나 확인 창이 뜨면 COM 호출이 돌아오지 않기 때문이다.

    제한 시간에 걸리면 자식을 끊고, 그사이 새로 뜬 PowerPoint 만 닫는다. 사용자가 쓰던 창은 건드리지 않는다.
    문제가 없으면 None, 있으면 까닭을 준다.
    """
    marker = work / '.opened'
    marker.unlink(missing_ok=True)
    errors = work / '.com-error.txt'
    before = powerpoint_pids()
    env = {**os.environ, 'PPTX_OPENED': str(marker)}
    with Turn(), open(errors, 'wb') as log:
        child = subprocess.Popen([sys.executable, '-I', str(Path(__file__).resolve()), '--com-child', mode, str(work), str(deck), pick],
                                 stdout=subprocess.DEVNULL, stderr=log, env=env)
        start = time.time()
        while child.poll() is None:
            waited = time.time() - start
            if (not marker.exists() and waited > OPEN_LIMIT) or waited > TOTAL_LIMIT:
                child.kill()
                for pid in powerpoint_pids() - before:
                    subprocess.run(['taskkill', '/PID', pid.decode(), '/F'], capture_output=True)
                return '제한 시간 안에 PowerPoint 가 응답하지 않았습니다. 암호나 DRM 확인 창이 떠 있을 수 있습니다. PowerPoint 창을 봐 주세요'
            time.sleep(.4)
    if child.returncode == 0:
        return None
    tail = errors.read_text(encoding='utf-8', errors='replace').strip().split('\n')[-1][:200]
    return f'PowerPoint 로 처리하지 못했습니다: {tail}'


def opened():
    if os.environ.get('PPTX_OPENED'):
        Path(os.environ['PPTX_OPENED']).touch()


def open_copy(deck, fn):
    """파일을 읽기 전용, 창 없이, 매크로를 끄고 연다. 이미 떠 있던 PowerPoint 는 닫지 않는다."""
    from read_com import attach, release
    app, was_running = attach()
    saved = app.AutomationSecurity
    app.AutomationSecurity = 3
    pres = app.Presentations.Open(str(deck), True, False, False)
    opened()
    try:
        return fn(pres)
    finally:
        pres.Close()
        app.AutomationSecurity = saved
        release(app, was_running)


def render_slides(pres, ref, height=1440):
    ref.mkdir(parents=True, exist_ok=True)
    width = round(height * pres.PageSetup.SlideWidth / pres.PageSetup.SlideHeight)
    for s in pres.Slides:
        s.Export(str(ref / f'{s.SlideIndex:03d}.png'), 'PNG', width, height)


def export_pictures(pres, work):
    """EMF·WMF 는 도형을 PNG 로 받는다. 쪽 그림에서 오리면 겹친 글이 구워진다."""
    path = work / 'deck.json'
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding='utf-8'))
    changed = False
    for slide in data['slides']:
        wanted = {s['id']: s for s in slide['shapes'] if s.get('needs_convert') and s.get('ext') not in ('.tif', '.tiff')}
        if not wanted:
            continue
        found = []
        for sh in pres.Slides(slide['n']).Shapes:
            found.append(sh)
            if sh.Type == 6:
                found += list(sh.GroupItems)
        for sh in found:
            item = wanted.get(str(sh.Id))
            if item is None:
                continue
            rel = f"media/conv-{slide['n']:03d}-{sh.Id}.png"
            (work / 'media').mkdir(exist_ok=True)
            try:
                sh.Export(str(work / rel), 2)
                item['converted'] = rel
                changed = True
            except Exception:  # noqa: BLE001 — 안 되면 쪽 그림에서 오린다
                pass
    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')


def retry(fn, tries=3):
    """PowerPoint 가 막 뜨거나 닫히는 순간에는 붙지 못할 때가 있다."""
    last = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 + 2 * i)
    raise last


def com_child(mode, work, deck='', pick=''):
    work = Path(work)
    if mode == 'copy':
        open_copy(deck, lambda pres: pres.SaveCopyAs(str(work / 'source.pptx'), PPTX_FORMAT))
    elif mode == 'render':
        def job(pres):
            render_slides(pres, work / 'ref')
            export_pictures(pres, work)
        retry(lambda: open_copy(work / 'source.pptx', job))
    elif mode == 'read':
        import read_com
        return read_com.main([deck, str(work)])
    elif mode in ('active-copy', 'active-read'):
        import read_com
        pres, info = read_com.pick_open(pick)
        opened()
        if mode == 'active-copy':
            (work / '.active.json').write_text(json.dumps(info, ensure_ascii=False), encoding='utf-8')
            try:
                pres.SaveCopyAs(str(work / 'source.pptx'), PPTX_FORMAT)
            except Exception:  # noqa: BLE001 — DRM 이 저장을 막으면 직접 읽는다
                remove(work / 'source.pptx')
        else:
            read_com.read_open(pres, work, work / 'ref')
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ['--com-child']:
        return com_child(*argv[1:5])
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('paths', nargs='+', help='원본.pptx 출력폴더, 또는 --active 일 때 출력폴더')
    ap.add_argument('--active', action='store_true', help='PowerPoint 에 띄워 둔 발표를 옮긴다')
    ap.add_argument('--pick', default='', help='--active 에서 발표가 여럿이면 이름의 일부')
    ap.add_argument('--name')
    ap.add_argument('--level', type=int, default=3)
    ap.add_argument('--no-powerpoint', action='store_true')
    ap.add_argument('--force', action='store_true', help='이미 있는 문서를 덮어쓴다')
    ap.add_argument('--no-draft', action='store_true', help='읽고 쪽 그림만 뽑는다 (reference.py 가 쓴다)')
    args = ap.parse_args(argv)

    def stop(message):
        print(json.dumps({'error': message}, ensure_ascii=False))
        return 2

    com = has_com() and not args.no_powerpoint
    if args.active:
        if len(args.paths) != 1:
            return stop('--active 에는 출력폴더 하나만 줍니다')
        if not com:
            return stop('띄워 둔 발표를 읽으려면 PowerPoint 와 pywin32 가 필요합니다')
        deck, out = None, Path(args.paths[0]).resolve()
    else:
        if len(args.paths) != 2:
            return stop('원본.pptx 와 출력폴더를 주세요')
        deck, out = Path(args.paths[0]).resolve(), Path(args.paths[1]).resolve()
        if not deck.exists():
            return stop(f'파일이 없습니다: {deck}')
        if encrypted(deck):
            return stop('암호가 걸린 파일입니다. PowerPoint 에서 암호를 풀어 저장한 뒤 다시 주세요')

    # 띄워 둔 발표는 이름을 물어봐야 작업 폴더를 정한다
    info = {}
    staging = None
    if args.active:
        staging = out / '.pptx-work' / '.active'
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True)
        problem = run_com('active-copy', staging, pick=args.pick)
        if problem:
            return stop(problem)
        info = json.loads((staging / '.active.json').read_text(encoding='utf-8'))
    name = args.name or (Path(info['name']).stem if info else deck.stem)
    work = out / '.pptx-work' / name
    md = out / f'{name}.md'
    if md.exists() and not args.force:
        draft = work / 'draft.md'
        if not draft.exists() or draft.read_bytes() != md.read_bytes():
            return stop(f'{md.name} 이 이미 있고 초안과 다릅니다. 고친 내용을 잃지 않게 멈춥니다. 다른 --name 을 쓰거나, 덮어써도 되면 --force 를 주세요')
    shutil.rmtree(work, ignore_errors=True)
    if staging:
        staging.rename(work)
    work.mkdir(parents=True, exist_ok=True)
    pictures = out / f'{name}-그림'
    if pictures.exists():
        shutil.rmtree(pictures)      # 다시 돌릴 때 지난 그림이 쌓이지 않게. 스크립트가 만든 폴더다

    source = work / 'source.pptx'
    log = []
    live = False
    if deck is not None:
        if zipfile.is_zipfile(deck):
            shutil.copyfile(deck, source)
        elif com:
            temp = work / f'.input{deck.suffix}'     # 같은 파일이 열려 있어도 그 발표를 돌려받지 않게
            shutil.copyfile(deck, temp)
            problem = run_com('copy', work, temp)
            if problem or not zipfile.is_zipfile(source):
                remove(source)
                problem = run_com('read', work, temp)
                if problem:
                    remove(temp)
                    return stop(problem)
                live = True
                log.append('pptx 사본을 받지 못해 PowerPoint 에서 직접 읽었습니다. 되돌릴 때 원본 쪽을 다시 쓸 수 없습니다')
            remove(temp)
        else:
            return stop('ZIP 으로 열 수 없습니다. .ppt 나 DRM 이 걸린 파일이면 PowerPoint 와 pywin32 가 필요합니다')
    elif not source.exists() or not zipfile.is_zipfile(source):
        remove(source)
        problem = run_com('active-read', work, pick=args.pick)
        if problem:
            return stop(problem)
        live = True
        log.append('발표의 사본을 받지 못해 PowerPoint 에서 직접 읽었습니다. 되돌릴 때 원본 쪽을 다시 쓸 수 없습니다')

    via = 'powerpoint' if live else 'xml'
    if not live:
        read_pptx.main([str(source), str(work)])
    ref = work / 'ref'
    if not live and com:
        problem = run_com('render', work)     # 그림 없이도 초안은 만든다
        if problem:
            log.append(f'쪽 그림을 뽑지 못했습니다. 도식이 칸으로 옮겨졌으니 다시 돌려 보세요. {problem}')
    elif not com:
        log.append('PowerPoint 없이 진행합니다. 도식은 칸으로만 옮기고 EMF 는 빠집니다')

    path = work / 'deck.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    data['file'] = info.get('path') or info.get('name') or str(deck)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    if args.no_draft:
        if log:
            print(json.dumps({'log': log}, ensure_ascii=False))
        return 0
    builder = draft_md.Builder(data, work, md, args.level, str(ref) if ref.exists() else None)
    how = builder.build()
    shutil.copyfile(md, work / 'draft.md')
    record_path = md.with_name(md.stem + '-변환기록.json')
    rec = json.loads(record_path.read_text(encoding='utf-8'))
    if source.exists():
        rec['snapshot'] = f'.pptx-work/{name}/source.pptx'
        rec['snapshot_sha1'] = hashlib.sha1(source.read_bytes()).hexdigest()
    if info:
        rec['unsaved_changes'] = not info.get('saved', True)
    record_path.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding='utf-8')
    review = {'표지·장 구분': [r['n'] for r in rec['slides'] if r['how'] in ('cover', 'section')],
              '그림으로 둔 쪽': [r['n'] for r in rec['slides'] if r['how'] == 'picture'],
              '도형을 뺀 쪽': [r['n'] for r in rec['slides'] if r['how'] != 'picture' and r.get('dropped_shapes')],
              '움직임이 있던 쪽': [r['n'] for r in rec['slides'] if r.get('animated')],
              '숨긴 쪽': [r['n'] for r in rec['slides'] if r.get('hidden')]}
    comments = sum(s.get('comments', 0) for s in data['slides'])
    if comments:
        log.append(f'검토 메모 {comments}개는 옮기지 않았습니다. 사용자에게 알리세요')
    if info.get('others'):
        log.append(f"PowerPoint 에 다른 발표도 열려 있습니다: {', '.join(info['others'])}. 옮긴 것은 '{info['name']}' 입니다")
    if info and not info.get('saved', True):
        log.append('저장하지 않은 수정까지 옮겼습니다. 띄워 둔 발표는 저장하지 않았습니다')
    print(json.dumps({'md': str(md), 'source': data['file'], 'read_via': via, 'work': str(work), 'how': how, 'review': review, 'log': log}, ensure_ascii=False))
    return verify.main([str(md), str(work)])


if __name__ == '__main__':
    sys.exit(main())
