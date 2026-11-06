#!/usr/bin/env python3
"""PowerPoint(win32com)로 발표를 읽어 read_pptx.py 와 같은 deck.json·outline.md 를 낸다.

    python read_com.py 원본.pptx 출력폴더 [--pages 3,5-9] [--no-pictures] [--render]

PowerPoint 가 파일을 대신 여니 ZIP 으로 못 여는 파일도 읽는다 (옛 .ppt, DRM 이 걸린 파일).
값은 상속이 끝난 실제 값이다. 그림은 Shape.Export 로 받아 자르기가 들어가고 EMF 도 PNG 가 된다.
원본은 읽기 전용으로 열고 창을 띄우지 않고 매크로는 끈다.
"""
import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import read_pptx as rp  # noqa: E402

import pythoncom  # noqa: E402
import win32com.client as wc  # noqa: E402

PH = {1: 'title', 2: 'body', 3: 'ctrTitle', 4: 'subTitle', 5: 'title', 6: 'body', 7: 'obj', 8: 'chart', 9: 'pic', 10: 'media',
      11: 'dgm', 12: 'tbl', 13: 'sldNum', 14: 'hdr', 15: 'ftr', 16: 'dt', 17: 'obj', 18: 'pic'}
LAYOUT = {1: 'title', 11: 'titleOnly', 12: 'blank', 33: 'secHead', 2: 'obj', 29: 'twoObj'}
CHART = {51: ('bar', 'col', 'clustered'), 52: ('bar', 'col', 'stacked'), 53: ('bar', 'col', 'percentStacked'),
         57: ('bar', 'bar', 'clustered'), 58: ('bar', 'bar', 'stacked'), 59: ('bar', 'bar', 'percentStacked'),
         4: ('line', '', ''), 65: ('line', '', ''), 63: ('line', '', 'stacked'), 5: ('pie', '', ''), -4120: ('doughnut', '', ''),
         1: ('area', '', ''), 76: ('area', '', 'stacked'), 77: ('area', '', 'percentStacked'), -4169: ('scatter', '', ''),
         74: ('scatter', '', ''), 72: ('scatter', '', ''), -4151: ('radar', '', ''), 81: ('radar', '', ''), 82: ('radar', '', ''), 15: ('bubble', '', '')}


def attach():
    """PowerPoint 에 붙는다. 이미 떠 있었으면 끝나고 닫지 않는다 — 사용자가 쓰던 창일 수 있다."""
    import pythoncom
    import win32com.client as wc
    try:
        app = wc.GetActiveObject('PowerPoint.Application')
        return app, True
    except pythoncom.com_error:
        return wc.Dispatch('PowerPoint.Application'), False


def release(app, was_running):
    if not was_running and app.Presentations.Count == 0:
        app.Quit()


def rgb(v):
    """COM 의 색은 BGR 정수다."""
    v = int(v) & 0xFFFFFF
    return f'#{v & 255:02X}{(v >> 8) & 255:02X}{(v >> 16) & 255:02X}'


def safe(fn, default=None):
    try:
        return fn()
    except Exception:  # noqa: BLE001 — COM 은 없는 속성을 예외로 알린다
        return default


class Reader:
    def __init__(self, pres, out, pages, pictures):
        self.pres = pres
        self.out = Path(out)
        self.pages = pages
        self.pictures = pictures
        self.flags = Counter()
        self.errors = []
        self.seen = {}
        self.charts = 0
        setup = pres.PageSetup
        self.w, self.h = setup.SlideWidth, setup.SlideHeight
        ratio = self.w / self.h
        self.ratio = ratio
        self.target = (960, 720) if abs(ratio - 4 / 3) < abs(ratio - 16 / 9) else (1280, 720)
        self.fit = 'exact' if min(abs(ratio - 4 / 3), abs(ratio - 16 / 9)) < .02 else 'other'
        self.k = min(self.target[0] / self.w, self.target[1] / self.h)

    def pos(self, sh, out):
        out['x'], out['y'] = round(sh.Left * self.k), round(sh.Top * self.k)
        out['w'], out['h'] = round(sh.Width * self.k), round(sh.Height * self.k)
        rot = safe(lambda: sh.Rotation, 0)
        if rot:
            out['rot'] = round(rot)

    def picture(self, sh, tag):
        """그림을 PNG 로 받는다. 같은 내용은 파일 하나로 모은다."""
        if not self.pictures:
            return None
        media = self.out / 'media'
        media.mkdir(parents=True, exist_ok=True)
        path = media / f'{tag}.png'
        try:
            sh.Export(str(path), 2)
        except Exception:  # noqa: BLE001
            self.flags['export-failed'] += 1
            return None
        data = path.read_bytes()
        digest = hashlib.sha1(data).hexdigest()
        if digest in self.seen:
            path.unlink()
            return self.seen[digest]
        rel = f'media/{path.name}'
        self.seen[digest] = rel
        return rel

    def paras(self, sh, title):
        tr = sh.TextFrame.TextRange
        out = []
        counts = Counter()
        for p in tr.Paragraphs():
            text = p.Text.replace('\r', '').replace('\x0b', '\n')
            if not text.strip():
                continue
            para = {}
            lvl = p.IndentLevel - 1
            if lvl:
                para['lvl'] = lvl
            fmt = p.ParagraphFormat
            if not title and fmt.Bullet.Visible:
                para['bullet'] = '1.' if fmt.Bullet.Type == 2 else (safe(lambda: chr(fmt.Bullet.Character), '•') or '•')
            algn = {2: 'ctr', 3: 'r', 4: 'just'}.get(fmt.Alignment)
            if algn:
                para['align'] = algn
            runs = []
            for r in p.Runs():
                value = r.Text.replace('\r', '').replace('\x0b', '\n')
                if not value:
                    continue
                f = r.Font
                run = {'t': value, 'sz': round(f.Size, 1), 'font': safe(lambda: f.Name, '')}
                if f.Bold:
                    run['b'] = True
                if f.Italic:
                    run['i'] = True
                if f.Underline:
                    run['u'] = True
                run['base_c'] = rgb(f.Color.RGB)
                counts[run['base_c']] += len(value)
                link = safe(lambda: r.ActionSettings(1).Hyperlink.Address)
                if link:
                    run['link'] = link
                runs.append(run)
            para['runs'] = runs
            para['text'] = text.strip()
            out.append(para)
        main = counts.most_common(1)[0][0] if counts else None
        for para in out:
            for run in para['runs']:
                if run['base_c'] != main:
                    run['c'] = run['base_c']
        return out

    def fill(self, sh):
        f = sh.Fill
        if not f.Visible:
            return None
        kind = f.Type
        if kind == 3:
            stops = [rgb(f.GradientStops(i + 1).Color.RGB) for i in range(f.GradientStops.Count)]
            return {'grad': stops, 'ang': safe(lambda: round(f.GradientAngle))}
        if kind == 6:
            return {'img': {}}
        return {'c': rgb(f.ForeColor.RGB)}

    def shape(self, sh, n, group=None):
        kind = sh.Type
        out = {'kind': 'shape', 'id': str(sh.Id), 'name': sh.Name}
        self.pos(sh, out)
        alt = safe(lambda: sh.AlternativeText, '')
        if alt:
            out['alt'] = alt.strip()
        if group:
            out['group'] = group
        if not sh.Visible:
            out['hidden'] = True
        link = safe(lambda: sh.ActionSettings(1).Hyperlink.Address)
        if link:
            out['link'] = link
        is_ph = kind == 14
        if is_ph:
            out['ph'] = PH.get(sh.PlaceholderFormat.Type, 'body')
            contained = safe(lambda: sh.PlaceholderFormat.ContainedType, 1)
        else:
            contained = kind
        if safe(lambda: sh.HasTable):
            out['kind'] = 'table'
            out.update(self.table(sh.Table))
        elif safe(lambda: sh.HasChart):
            out['kind'] = 'chart'
            out['chart'] = self.chart(sh.Chart, n, sh.Id)
        elif safe(lambda: sh.HasSmartArt):
            out['kind'] = 'smartart'
            sa = sh.SmartArt
            out['layout'] = safe(lambda: sa.Layout.Name, '')
            out['nodes'] = [{'lvl': x.Level - 1, 'text': x.TextFrame2.TextRange.Text.strip()} for x in sa.AllNodes if x.TextFrame2.TextRange.Text.strip()]
            out['shape_count'] = safe(lambda: sa.Nodes.Count, 0)
        elif contained in (13, 11, 28, 29):
            out['kind'] = 'picture'
            src = self.picture(sh, f's{n:03d}-{sh.Id}')
            if src:
                out['src'] = src
        elif contained in (7, 10, 12):
            out['kind'] = 'ole'
            out['prog'] = safe(lambda: sh.OLEFormat.ProgID, '')
            src = self.picture(sh, f's{n:03d}-{sh.Id}')
            if src:
                out['src'] = src
            self.flags['ole'] += 1
        elif contained in (16, 26):
            out['kind'] = 'media'
            src = self.picture(sh, f's{n:03d}-{sh.Id}')
            if src:
                out['src'] = src
            self.flags['media'] += 1
        elif safe(lambda: sh.Connector):
            out['kind'] = 'line'
            cf = sh.ConnectorFormat
            if cf.BeginConnected:
                out['from'] = str(cf.BeginConnectedShape.Id)
            if cf.EndConnected:
                out['to'] = str(cf.EndConnectedShape.Id)
            out['line'] = {'c': rgb(sh.Line.ForeColor.RGB)}
        elif kind == 9:
            out['kind'] = 'line'
            out['line'] = {'c': rgb(sh.Line.ForeColor.RGB)}
        else:
            if kind == 5:
                out['geom'] = 'custom'
            else:
                geom = safe(lambda: sh.AutoShapeType, 1)
                if geom not in (1, -2):
                    out['geom'] = f'mso{geom}'
            fill = safe(lambda: self.fill(sh))
            if fill:
                out['fill'] = fill
            if safe(lambda: sh.Line.Visible):
                out['line'] = {'c': rgb(sh.Line.ForeColor.RGB)}
            if sh.HasTextFrame and sh.TextFrame.HasText:
                out['paras'] = self.paras(sh, out.get('ph') in ('title', 'ctrTitle'))
                if out['paras']:
                    out['kind'] = 'text'
        return out

    def table(self, t):
        rows = []
        rc, cc = t.Rows.Count, t.Columns.Count
        for r in range(1, rc + 1):
            row = []
            for c in range(1, cc + 1):
                cell = t.Cell(r, c)
                text = cell.Shape.TextFrame.TextRange.Text.replace('\r', '\n').replace('\x0b', '\n').strip()
                item = {'text': text}
                if safe(lambda: cell.Merged):
                    item['mergedish'] = True
                row.append(item)
            rows.append(row)
        return {'rows': rows, 'cols': [round(t.Columns(c).Width * self.k) for c in range(1, cc + 1)], 'head': bool(t.FirstRow)}

    def chart(self, c, n, sid):
        kind, direction, grouping = CHART.get(c.ChartType, (f'type{c.ChartType}', '', ''))
        info = {'plots': []}
        if c.HasTitle:
            info['title'] = safe(lambda: c.ChartTitle.Text, '')
        series = []
        for i in range(1, c.SeriesCollection().Count + 1):
            s = c.SeriesCollection(i)
            xs = list(safe(lambda: s.XValues, ()) or ())
            ys = list(safe(lambda: s.Values, ()) or ())
            if kind in ('scatter', 'bubble'):
                series.append({'name': s.Name, 'x': xs, 'y': ys})
            else:
                series.append({'name': s.Name, 'cats': [str(x) for x in xs], 'vals': ys})
        p = {'type': kind, 'series': series}
        if direction:
            p['barDir'] = direction
        if grouping:
            p['grouping'] = grouping
        info['plots'].append(p)
        if c.HasLegend:
            info['legend'] = str(safe(lambda: c.Legend.Position, ''))
        rows = rp.chart_rows(info)
        if rows:
            self.charts += 1
            name = f'charts/chart-s{n:03d}-{sid}.csv'
            target = self.out / name
            target.parent.mkdir(parents=True, exist_ok=True)
            import csv
            with open(target, 'w', encoding='utf-8-sig', newline='') as f:
                csv.writer(f).writerows(rows)
            info['csv'] = name
        return info

    def walk(self, shapes, n):
        out = []
        for sh in shapes:
            try:
                if sh.Type == 6:
                    gid = f'g{sh.Id}'
                    for item in sh.GroupItems:
                        out.append(self.one(item, n, gid))
                else:
                    out.append(self.one(sh, n))
            except Exception as e:  # noqa: BLE001 — 도형 하나 때문에 발표 전체를 놓치지 않는다
                self.flags['group-failed'] += 1
                self.errors.append(f'{n}: {type(e).__name__} {str(e)[:90]}')
        return out

    def one(self, sh, n, gid=None):
        try:
            return self.shape(sh, n, gid)
        except Exception as e:  # noqa: BLE001
            self.flags['shape-failed'] += 1
            self.errors.append(f'{n}/{safe(lambda: sh.Name)}: {type(e).__name__} {str(e)[:90]}')
            return {'kind': 'unknown', 'id': str(safe(lambda: sh.Id, '')), 'name': safe(lambda: sh.Name, ''), 'failed': True}

    def background(self, holder):
        f = safe(lambda: holder.Background.Fill)
        if f is None:
            return None
        kind = safe(lambda: f.Type)
        if kind == 3:
            return {'grad': [rgb(f.GradientStops(i + 1).Color.RGB) for i in range(f.GradientStops.Count)], 'ang': None}
        if kind in (4, 6):
            return {'img': {}}
        return {'c': rgb(f.ForeColor.RGB)}

    def notes(self, s):
        if not s.HasNotesPage:
            return ''
        for sh in s.NotesPage.Shapes:
            if sh.Type == 14 and sh.PlaceholderFormat.Type == 2 and sh.HasTextFrame:
                return sh.TextFrame.TextRange.Text.replace('\r', '\n').replace('\x0b', '\n').strip()
        return ''

    def slide(self, s):
        n = s.SlideIndex
        seq = s.TimeLine.MainSequence
        order = safe(lambda: [str(seq.Item(i + 1).Shape.Id) for i in range(min(seq.Count, 60))], []) if seq.Count else []
        out = {
            'n': n, 'part': f'slide{s.SlideID}', 'hidden': bool(s.SlideShowTransition.Hidden), 'layout': s.CustomLayout.Name,
            'layout_type': LAYOUT.get(s.Layout, ''), 'bg': self.background(s), 'shapes': self.walk(s.Shapes, n),
            'notes': safe(lambda: self.notes(s), ''), 'animated': seq.Count > 0, 'anim_order': order,
            'transition': safe(lambda: s.SlideShowTransition.EntryEffect != 0, False), 'comments': safe(lambda: s.Comments.Count, 0),
            'show_master': bool(s.DisplayMasterShapes),
        }
        out['title'] = rp.title_of(out['shapes'])
        out['form'] = rp.form_of(out)
        return out

    def theme(self):
        m = self.pres.SlideMaster
        th = m.Theme
        names = ('dk1', 'lt1', 'dk2', 'lt2', 'accent1', 'accent2', 'accent3', 'accent4', 'accent5', 'accent6', 'hlink', 'folHlink')
        colors = {name: rgb(th.ThemeColorScheme.Colors(i + 1).RGB).lstrip('#') for i, name in enumerate(names)}
        fonts = {}
        for key, f in (('major', th.ThemeFontScheme.MajorFont), ('minor', th.ThemeFontScheme.MinorFont)):
            fonts[key] = {'latin': safe(lambda: f(1).Name, ''), 'ea': safe(lambda: f(3).Name, '')}
        return {'name': safe(lambda: m.Name, ''), 'colors': colors, 'fonts': fonts}

    def decor(self, shapes, tag):
        items = []
        for i, sh in enumerate(shapes):
            if sh.Type == 14:
                continue
            items.append(self.shape(sh, 0) if sh.Type != 6 else {'kind': 'group', 'id': str(sh.Id), 'x': round(sh.Left * self.k), 'y': round(sh.Top * self.k), 'w': round(sh.Width * self.k), 'h': round(sh.Height * self.k)})
        return items


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('deck')
    ap.add_argument('out')
    ap.add_argument('--pages')
    ap.add_argument('--no-pictures', action='store_true')
    ap.add_argument('--render', help='쪽 PNG 를 이 폴더에')
    args = ap.parse_args(argv)
    pages = None
    if args.pages:
        pages = set()
        for bit in args.pages.split(','):
            a, _, b = bit.partition('-')
            pages.update(range(int(a), int(b or a) + 1))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    pythoncom.CoInitialize()
    started = time.time()
    app, was_running = attach()
    saved = app.AutomationSecurity
    app.AutomationSecurity = 3
    pres = app.Presentations.Open(os.path.abspath(args.deck), True, False, False)
    if os.environ.get('PPTX_OPENED'):
        Path(os.environ['PPTX_OPENED']).touch()
    try:
        r, data = read_presentation(pres, out, pages, not args.no_pictures, args.render, str(args.deck))
    finally:
        pres.Close()
        app.AutomationSecurity = saved
        release(app, was_running)
    write(out, data)
    slides = data['slides']
    print(json.dumps({'slides': len(slides), 'seconds': round(time.time() - started, 1), 'forms': Counter(s['form'] for s in slides), 'flags': r.flags, 'media': len(r.seen), 'errors': r.errors[:6]}, ensure_ascii=False))
    return 0


def read_presentation(pres, out, pages, pictures, render, label, height=720):
    """열린 발표에서 읽기만 한다. 여는 일과 닫는 일은 부른 쪽이 맡는다."""
    r = Reader(pres, out, pages, pictures)
    slides = []
    for s in pres.Slides:
        if pages and s.SlideIndex not in pages:
            continue
        slides.append(r.slide(s))
        if render:
            Path(render).mkdir(parents=True, exist_ok=True)
            s.Export(os.path.join(os.path.abspath(render), f'{s.SlideIndex:03d}.png'), 'PNG', round(height * r.ratio), height)
    used = Counter(s['layout'] for s in slides)
    layouts = []
    for design in pres.Designs:
        master = design.SlideMaster
        base = safe(lambda: r.decor(master.Shapes, 'm'), [])
        for lay in master.CustomLayouts:
            if used[lay.Name]:
                layouts.append({'name': lay.Name, 'type': '', 'used': used[lay.Name], 'bg': r.background(lay),
                                'decor': safe(lambda: r.decor(lay.Shapes, 'l'), []), 'master_decor': base if lay.DisplayMasterShapes else []})
    feet = Counter(p['text'] for s in slides for sh in s['shapes'] if sh.get('ph') == 'ftr' for p in sh.get('paras', []))
    sections = safe(lambda: [{'name': pres.SectionProperties.Name(i + 1), 'slides': pres.SectionProperties.SlidesCount(i + 1)} for i in range(pres.SectionProperties.Count)], [])
    data = {
        'file': label, 'via': 'com', 'slides_total': pres.Slides.Count,
        'comments': sum(s['comments'] for s in slides),
        'size': {'px': f'{round(r.w / .75)}×{round(r.h / .75)}', 'target': f'{r.target[0]}×{r.target[1]}', 'ratio': round(r.ratio, 3), 'fit': r.fit, 'scale': round(r.k * .75, 4)},
        'theme': safe(r.theme, {'name': '', 'colors': {}, 'fonts': {}}), 'masters': pres.Designs.Count, 'footer': rp.common_footer(feet, len(slides)),
        'page_numbers': sum(1 for s in slides for sh in s['shapes'] if sh.get('ph') == 'sldNum'), 'sections': sections,
        'layouts': layouts, 'flags': dict(r.flags), 'media': sorted(set(r.seen.values())), 'slides': slides,
    }
    return r, data


def write(out, data):
    (Path(out) / 'deck.json').write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    (Path(out) / 'outline.md').write_text(rp.outline(None, data['slides'], data), encoding='utf-8')


def pick_open(want=''):
    """사용자가 PowerPoint 에 띄워 둔 발표를 찾는다. 앞쪽 창의 발표가 기본이고 want 는 이름의 일부다.

    사용자의 PowerPoint 라서 설정을 바꾸지 않고 닫지도 않는다.
    """
    pythoncom.CoInitialize()
    try:
        app = wc.GetActiveObject('PowerPoint.Application')
    except pythoncom.com_error:
        raise RuntimeError('PowerPoint 가 떠 있지 않습니다. 발표를 연 뒤 다시 하거나 파일 경로를 주세요') from None
    try:
        names = [p.Name for p in app.Presentations]
    except (AttributeError, pythoncom.com_error):     # 대화상자가 떠 있으면 호출을 받지 않는다
        raise RuntimeError('PowerPoint 가 응답하지 않습니다. PowerPoint 에 떠 있는 안내 창을 닫은 뒤 다시 하세요') from None
    if not names:
        if safe(lambda: app.ProtectedViewWindows.Count, 0):
            raise RuntimeError("제한된 보기로 열린 발표입니다. PowerPoint 에서 '편집 사용'을 누른 뒤 다시 하세요")
        raise RuntimeError('PowerPoint 에 열린 발표가 없습니다')
    pres = None
    if want:
        matches = [p for p in app.Presentations if want.lower() in p.Name.lower()]
        if not matches:
            raise RuntimeError(f"'{want}' 이 이름에 든 발표가 없습니다. 열린 발표: {', '.join(names)}")
        pres = matches[0]
    else:
        pres = safe(lambda: app.ActivePresentation)
        if pres is None:
            pres = app.Presentations(1)
    return pres, {'name': pres.Name, 'path': pres.FullName if pres.Path else '', 'saved': bool(pres.Saved),
                  'others': [n for n in names if n != pres.Name], 'slides': pres.Slides.Count}


def read_open(pres, out, render):
    """띄워 둔 발표를 그대로 읽는다. DRM 이 사본을 막을 때의 길이다. 여기서 닫지 않는다."""
    Path(out).mkdir(parents=True, exist_ok=True)
    _, data = read_presentation(pres, Path(out), None, True, render, pres.Name, height=1440)
    write(out, data)


if __name__ == '__main__':
    sys.exit(main())
