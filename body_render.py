"""Video output shared with the face renderer; body grid mapping."""
from make_face_videos import *

def render(files, records, config, args, output):
    views = list(config['views']) if 'all' in args.views else list(dict.fromkeys(args.views))
    grid = args.layout in ['grid', 'both']
    if grid and len(views) != 4:
        raise ValueError('The grid needs all four views. Use --views all or --layout separate.')
    names = views if args.layout in ['separate', 'both'] else []
    names = names + (['all_views'] if grid else [])
    if getattr(args, 'output_names', None):
        names = [name for name in names if name in args.output_names]
    if not names:
        raise ValueError('No requested output matches the selected views and layout.')
    prefix = getattr(args, 'prefix', 'Body')
    paths = {name: output/f'{prefix}_{name}_stabilized.mp4' for name in names}
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
    repeats = getattr(args, 'hold_frames', args.fps // args.speed)
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
                        rendered['all_views'] = np.vstack([np.hstack([rendered['front'], rendered['side_right']]),
                            np.hstack([rendered['back'], rendered['side_left']])])
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
        print(f'Verified: {path} ({len(files)*repeats/args.fps:.1f} s)', flush=True)
    for view, sheet in sheets.items():
        cv2.imwrite(str(output/f'{prefix}_preview_{view}.jpg'), sheet)
    return paths
