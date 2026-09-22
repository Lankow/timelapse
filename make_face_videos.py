"""Local, reusable four-view timelapse renderer. See VIDEO_README.md."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import itertools
import json
import math
from pathlib import Path
import re
import threading

import cv2
import numpy as np
from PIL import Image, ImageOps

VERSION = 4
MONTHS = {name: n for n, name in enumerate(
    'January February March April May June July August September October November December'.split(), 1)}
LOCAL = threading.local()
cv2.setNumThreads(1)


def ordered_files(root):
    """Use month IDs and integer image numbers, never lexical image ordering."""
    result = []
    for folder in root.iterdir():
        if not folder.is_dir():
            continue
        match = re.fullmatch(r'(\d+)_([A-Za-z]+)_(\d{4})', folder.name)
        if not match or match[2] not in MONTHS:
            continue
        for path in folder.iterdir():
            if path.suffix.lower() not in {'.jpg', '.jpeg', '.png'}:
                continue
            number = re.search(r'(\d+)$', path.stem)
            if not number:
                raise ValueError(f'Cannot determine image order: {path}')
            result.append((int(match[3]), MONTHS[match[2]], int(number[1]), path))
    result.sort(key=lambda item: item[:3])
    if not result:
        raise ValueError(f'No numbered images in monthly folders under {root}')
    keys = [item[:3] for item in result]
    if len(set(keys)) != len(keys):
        raise ValueError('Duplicate frame numbers in a month; resolve them before rendering.')
    return [item[3] for item in result]


def load_tiles(path, width, views):
    with Image.open(path) as image:
        image.draft('RGB', (width * 2, round(width * 8 / 3)))
        image = ImageOps.exif_transpose(image).convert('RGB')
        w, h = image.size
        if abs(w / h - 3072 / 4092) > .06:
            raise ValueError(f'Unexpected collage aspect ratio {w}x{h}: {path}')
        tiles = {}
        for view, settings in views.items():
            x, y = settings['quadrant']
            crop = image.crop((x*w//2, y*h//2, (x+1)*w//2, (y+1)*h//2))
            crop = crop.resize((width, round(width * 4 / 3)), Image.Resampling.LANCZOS)
            tiles[view] = cv2.cvtColor(np.asarray(crop), cv2.COLOR_RGB2BGR)
        return tiles


def detectors():
    if not hasattr(LOCAL, 'face'):
        LOCAL.face = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        LOCAL.eyes = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
    return LOCAL.face, LOCAL.eyes


def front_anchor(image):
    """Eye midpoint, inter-eye distance and roll; no deforming warp."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    face, eye = detectors()
    boxes = face.detectMultiScale(gray, 1.06, 4, minSize=(60, 60), maxSize=(240, 240))
    candidates = []
    for x, y, bw, bh in boxes:
        if not (.2*w < x+bw/2 < .8*w and .35*h < y+bh/2 < .86*h):
            continue
        eyes = eye.detectMultiScale(gray[y:y+int(bh*.65), x:x+bw], 1.05, 4,
                                    minSize=(12, 12), maxSize=(int(bw*.4), int(bh*.4)))
        centers = [(ex+ew/2, ey+eh/2) for ex, ey, ew, eh in eyes]
        for a, b in itertools.combinations(centers, 2):
            a, b = sorted([a, b])
            dx, dy = b[0]-a[0], b[1]-a[1]
            if not (.27*bw < dx < .55*bw and abs(dy) < .12*bw
                    and .12*bw < a[0] < .49*bw and .51*bw < b[0] < .9*bw
                    and .19*bh < (a[1]+b[1])/2 < .56*bh):
                continue
            quality = 1 - abs(dx/bw-.36) - abs(dy)/bw
            candidates.append((quality, [(x+(a[0]+b[0])/2)/w,
                (y+(a[1]+b[1])/2)/h, math.hypot(dx, dy)/w,
                math.degrees(math.atan2(dy, dx))]))
    if candidates:
        score, anchor = max(candidates, key=lambda item: item[0])
        return {'anchor': anchor, 'score': float(score), 'method': 'eyes'}
    return {'anchor': None, 'score': 0., 'method': 'missing-eyes'}


def build_templates(root, config):
    bank = {}
    for view, refs in config['templates'].items():
        bank[view] = []
        for reference in refs:
            path = root / reference['file']
            if not path.is_file():
                raise FileNotFoundError(f'Calibration image missing: {path}')
            image = load_tiles(path, 400, {view: config['views'][view]})[view]
            h, w = image.shape[:2]
            x, y, bw, bh = reference['box']
            crop = image[round(y*h):round((y+bh)*h), round(x*w):round((x+bw)*w)]
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            # Precompute scales once, shared read-only by analysis workers.
            scales = []
            for size in range(72, 181, 6):
                height = round(size * gray.shape[0] / gray.shape[1])
                if height < 230:
                    scales.append(cv2.resize(gray, (size, height)))
            bank[view].append((reference['file'], scales))
    return bank


def plausible(anchor, front, view):
    if anchor is None:
        return False
    if front is None:
        return .25 <= anchor[0] <= .75 and .32 <= anchor[2] <= .75
    x, y, span, _ = anchor
    fx, fy, eyes, _ = front
    y_low, y_high = (fy, min(.94, fy+.38)) if view == 'top' else (fy-.13, fy+.13)
    return abs(x-fx) <= .22 and y_low <= y <= y_high and eyes*2.4 <= span <= eyes*5.2


def template_anchor(image, templates, front=None, view=None):
    gray = cv2.resize(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), (240, 320))
    roi = gray[80:320, 20:225]
    def edge(a):
        a = cv2.GaussianBlur(a, (5, 5), 1.2)
        return cv2.magnitude(cv2.Sobel(a, cv2.CV_32F, 1, 0), cv2.Sobel(a, cv2.CV_32F, 0, 1))
    edge_roi = edge(roi)
    best = (-1., None, None)

    def match(candidate):
        th, tw = candidate.shape
        if view is not None:
            minimum, maximum = (front[2]*2.4, front[2]*5.2) if front else (.32,.75)
            if not minimum <= tw/240 <= maximum:
                return None
        scores = .35*cv2.matchTemplate(roi, candidate, cv2.TM_CCOEFF_NORMED) + .65*cv2.matchTemplate(edge_roi, edge(candidate), cv2.TM_CCOEFF_NORMED)
        if view is not None:
            yy, xx = np.indices(scores.shape)
            xx = (xx+20+tw/2)/240
            yy = (yy+80+th/2)/320
            if front:
                fx, fy = front[:2]
                low, high = (fy,min(.94,fy+.38)) if view=='top' else (fy-.13,fy+.13)
                allowed = (np.abs(xx-fx)<=.22) & (yy>=low) & (yy<=high)
            else:
                allowed = (xx>=.25) & (xx<=.75)
            scores[~allowed] = -1
        _, score, _, location = cv2.minMaxLoc(scores)
        return score, location

    for name, scales in templates:
        for template in scales:
            matched = match(template)
            if matched is None:
                continue
            score, (x,y) = matched
            if score > best[0]:
                th, tw = template.shape
                best = (score, (template, x, y), name)
    if best[1] is None:
        return {'anchor':None,'score':0.,'method':'missing-template'}
    score, (template, x, y), name = best
    # Refine scale in one-pixel increments to avoid visible six-pixel zoom steps.
    base_h, base_w = template.shape
    refined = (score, x, y, base_w, base_h)
    for tw in range(max(60, base_w-5), base_w+6):
        th = round(tw * base_h / base_w)
        if th >= roi.shape[0]:
            continue
        candidate = cv2.resize(template, (tw, th))
        matched = match(candidate)
        if matched is None:
            continue
        candidate_score, (cx,cy) = matched
        if candidate_score > refined[0]:
            refined = (candidate_score, cx, cy, tw, th)
    score, x, y, tw, th = refined
    anchor = [(x+20+tw/2)/240, (y+80+th/2)/320, tw/240, 0.]
    return {'anchor': anchor if score >= .40 else None,
            'score': float(score), 'method': 'template', 'reference': name}


def fingerprint(path, root, config_hash):
    stat = path.stat()
    return hashlib.sha256(f'{path.relative_to(root)}|{stat.st_size}|{stat.st_mtime_ns}|{config_hash}'.encode()).hexdigest()


def analyze(files, root, config, cache_path, workers, rebuild):
    config_hash = hashlib.sha256(json.dumps([VERSION, {**config, "overrides": {}}], sort_keys=True).encode()).hexdigest()
    cache = {} if rebuild or not cache_path.exists() else json.loads(cache_path.read_text())
    templates = build_templates(root, config)
    jobs = [(path, fingerprint(path, root, config_hash)) for path in files]
    pending = [(p, key) for p, key in jobs if key not in cache]

    def detect(job):
        path, key = job
        tiles = load_tiles(path, 400, config['views'])
        results = {'front': front_anchor(tiles['front'])}
        for view in ['left', 'right', 'top']:
            results[view] = template_anchor(tiles[view], templates[view], results['front']['anchor'], view)
        return key, results

    print(f'Alignment: {len(jobs)-len(pending)} cached, {len(pending)} to analyze.', flush=True)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, (key, result) in enumerate(pool.map(detect, pending), 1):
            cache[key] = result
            if i % 100 == 0:
                cache_path.write_text(json.dumps(cache))
                print(f'Analyzed {i}/{len(pending)}', flush=True)
    cache_path.write_text(json.dumps(cache))
    records = [json.loads(json.dumps(cache[key])) for _, key in jobs]
    for path, record in zip(files, records):
        overrides = config.get('overrides', {}).get(path.relative_to(root).as_posix(), {})
        for view, anchor in overrides.items():
            if view not in config['views'] or len(anchor) != 4 or not all(math.isfinite(x) for x in anchor) or anchor[2] <= 0:
                raise ValueError(f'Invalid override for {path}: {view}')
            record[view] = {'anchor': anchor, 'score': 1., 'method': 'manual'}
    # Interpolate only missed detections. Smoothing valid positions would reintroduce camera shake.
    for view in config['views']:
        good = [i for i, record in enumerate(records) if record[view]['anchor'] is not None]
        if not good:
            raise ValueError(f'No usable alignment for {view}; add calibration/overrides.')
        anchors = np.array([records[i][view]['anchor'] for i in good])
        for i, record in enumerate(records):
            if record[view]['anchor'] is None:
                record[view]['anchor'] = [float(np.interp(i, good, anchors[:, j])) for j in range(4)]
                record[view]['method'] = 'interpolated'
    return records


def stabilize(image, anchor, target, width, height):
    h, w = image.shape[:2]
    x, y, span, angle = anchor
    scale = target[2] * width / (span * w)
    matrix = cv2.getRotationMatrix2D((x*w, y*h), angle, scale)
    matrix[0, 2] += target[0]*width - x*w
    matrix[1, 2] += target[1]*height - y*h
    return cv2.warpAffine(image, matrix, (width, height), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=(24, 20, 18))


def add_header(image, date, label, progress):
    h, w = image.shape[:2]
    canvas = np.full((h+64, w, 3), (24, 20, 18), np.uint8)
    canvas[64:] = image
    cv2.putText(canvas, date, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, .85, (245,245,245), 2, cv2.LINE_AA)
    cv2.putText(canvas, label, (210, 39), cv2.FONT_HERSHEY_SIMPLEX, .48, (205,195,190), 1, cv2.LINE_AA)
    cv2.rectangle(canvas, (0,h+60), (round((w-1)*progress),h+63), (220,200,115), -1)
    return canvas


def verify(path, frames, fps):
    cap = cv2.VideoCapture(str(path))
    try:
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if count != frames or abs(cap.get(cv2.CAP_PROP_FPS)-fps) > .01:
            raise RuntimeError(f'Video verification failed: {path}, frames={count}/{frames}')
        for index in [0, frames//2, frames-1]:
            cap.set(cv2.CAP_PROP_POS_FRAMES, index)
            if not cap.read()[0]:
                raise RuntimeError(f'Cannot decode frame {index} of {path}')
    finally:
        cap.release()


def render(files, records, config, args, output):
    views = list(config['views']) if 'all' in args.views else list(dict.fromkeys(args.views))
    grid = args.layout in ['grid', 'both']
    if grid and len(views) != 4:
        raise ValueError('The grid needs all four views. Use --views all or --layout separate.')
    names = views if args.layout in ['separate', 'both'] else []
    names = names + (['all_views'] if grid else [])
    paths = {name: output/f'Face_{name}_stabilized.mp4' for name in names}
    if not args.overwrite:
        exists = [str(path) for path in paths.values() if path.exists()]
        if exists:
            raise FileExistsError('Output exists; use --overwrite to replace: ' + ', '.join(exists))
    writers, partials = {}, {}
    for name, path in paths.items():
        partials[name] = path.with_name(path.stem+'.partial.mp4')
        size = (args.width*2, args.height*2) if name == 'all_views' else (args.width, args.height)
        writers[name] = cv2.VideoWriter(str(partials[name]), cv2.VideoWriter_fourcc(*'mp4v'), args.fps, size)
        if not writers[name].isOpened():
            raise RuntimeError(f'MPEG-4 encoder unavailable for {path}')
    repeats = args.fps // args.speed
    samples = set(np.linspace(0, len(files)-1, min(16,len(files)), dtype=int).tolist())
    sheets = {view: np.full((4*256, 4*192, 3), 24, np.uint8) for view in views}
    sample_count = 0
    try:
        def prepare(item):
            i, path = item
            tiles = load_tiles(path, 720, {v:config['views'][v] for v in views})
            _, month, year = path.parent.name.split('_')
            date = f'{MONTHS[month]:02d}.{year}'
            result = {}
            for view in views:
                aligned = stabilize(tiles[view], records[i][view]['anchor'], config['views'][view]['target'], args.width, args.height-64)
                result[view] = add_header(aligned, date, config['views'][view]['label'], (i+1)/len(files))
            return i, result

        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            # Bounded prefetch: do not keep thousands of decoded images in memory.
            for start in range(0, len(files), args.workers*2):
                jobs = [(i,files[i]) for i in range(start,min(start+args.workers*2,len(files)))]
                for i, rendered in pool.map(prepare, jobs):
                    if grid:
                        rendered['all_views'] = np.vstack([np.hstack([rendered['front'], rendered['top']]),
                            np.hstack([rendered['left'], rendered['right']])])
                    for name, writer in writers.items():
                        for _ in range(repeats):
                            writer.write(rendered[name])
                    if i in samples:
                        row, col = divmod(sample_count, 4)
                        for view in views:
                            sheets[view][row*256:(row+1)*256,col*192:(col+1)*192] = cv2.resize(rendered[view],(192,256))
                        sample_count += 1
                    if (i+1) % 100 == 0:
                        print(f'Rendered {i+1}/{len(files)}', flush=True)
    finally:
        for writer in writers.values():
            writer.release()
    for name, path in paths.items():
        verify(partials[name], len(files)*repeats, args.fps)
        partials[name].replace(path)
        print(f'Verified: {path} ({len(files)/args.speed:.1f} s)', flush=True)
    for view, sheet in sheets.items():
        cv2.imwrite(str(output/f'preview_{view}.jpg'), sheet)
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path(__file__).with_name('video_config.json'))
    parser.add_argument('--input', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--views', nargs='+', choices=['all','front','left','right','top'], default=['all'])
    parser.add_argument('--layout', choices=['separate','grid','both'], default='separate')
    parser.add_argument('--speed', type=int, default=12, help='Source photos per second')
    parser.add_argument('--fps', type=int, default=24)
    parser.add_argument('--width', type=int, default=720)
    parser.add_argument('--height', type=int, default=960, help='Includes 64-pixel date header')
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--sample-step', type=int, default=1, help='Use every Nth photo for a quick preview')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--analyze-only', action='store_true')
    parser.add_argument('--rebuild-cache', action='store_true')
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    if args.speed <= 0 or args.fps <= 0 or args.fps % args.speed:
        parser.error('--fps must be a positive multiple of --speed (e.g. 24 and 12).')
    if args.width < 480 or args.height < 480 or args.width % 2 or args.height % 2:
        parser.error('Video dimensions must be even and at least 480.')
    if args.workers < 1 or args.sample_step < 1 or (args.limit is not None and args.limit < 1):
        parser.error('Workers, sample-step and limit must be positive.')
    config = json.loads(args.config.read_text(encoding='utf-8-sig'))
    root = (args.input or args.config.parent/config['input']).resolve()
    output = (args.output or args.config.parent/config['output']).resolve()
    output.mkdir(parents=True, exist_ok=True)
    files = ordered_files(root)[::args.sample_step]
    if args.limit:
        files = files[:args.limit]
    # Share alignment cache across output variants and playback speeds.
    cache_path = args.config.parent/'video_alignment_cache.json'
    records = analyze(files, root, config, cache_path, args.workers, args.rebuild_cache)
    summary = {view: {'interpolated':sum(r[view]['method']=='interpolated' for r in records),
                    'low_confidence':sum(r[view]['score']<.52 for r in records)} for view in config['views']}
    report = {'version':VERSION,'source_count':len(files),'photos_per_second':args.speed,
              'fps':args.fps,'summary':summary,'frames':[
                  {'file':p.relative_to(root).as_posix(),'views':r} for p,r in zip(files,records)]}
    (output/'alignment_report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(summary), flush=True)
    if not args.analyze_only:
        paths = render(files, records, config, args, output)
        report['outputs'] = {name:str(path) for name,path in paths.items()}
        (output/'alignment_report.json').write_text(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
