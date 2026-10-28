"""Create locally aligned body timelapses without reshaping the body."""
import argparse
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import cv2
import numpy as np
from make_face_videos import ordered_files, load_tiles, fingerprint
from body_render import render

VERSION = 2

def templates(root, config):
    bank = {}
    for view, refs in config['templates'].items():
        bank[view] = []
        for ref in refs:
            im = load_tiles(root/ref['file'], 300, config['views'])[view]
            x,y,w,h = ref['box']
            crop = im[round(y*400):round((y+h)*400),round(x*300):round((x+w)*300)]
            gray = cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY)
            limits={'front':(44,70),'back':(32,62),'side_right':(40,76),'side_left':(44,76)}
            for height in range(*limits[view],2):
                width = round(height*crop.shape[1]/crop.shape[0])
                bank[view].append((ref['file'],height,cv2.resize(gray,(width,height))))
    return bank

def detect(im, bank, view):
    gray=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)
    # Broad view-specific regions allow mirror framing changes while excluding phones.
    regions={'front':(.28,.01,.75,.39),'back':(.28,.06,.85,.72),
             'side_right':(.035,.08,.53,.53),'side_left':(.43,.01,.96,.50)}
    x0,y0,x1,y1=regions[view]
    x0,x1=round(x0*240),round(x1*240)
    y0,y1=round(y0*320),round(y1*320)
    roi=gray[y0:y1,x0:x1]
    best=(-1,None,None)
    for name,height,t in bank:
        th,tw=t.shape
        if th>roi.shape[0] or tw>roi.shape[1]: continue
        score=cv2.matchTemplate(roi,t,cv2.TM_CCOEFF_NORMED)
        yy,xx=np.indices(score.shape)
        xx=(xx+x0+tw/2)/240;yy=(yy+y0+th/2)/320
        bounds={'front':(.38,.68,.07,.29),'back':(.37,.78,.12,.59),
                'side_right':(.12,.43,.14,.43),'side_left':(.57,.91,.10,.35)}
        left,right,top,bottom=bounds[view]
        score[(xx<left)|(xx>right)|(yy<top)|(yy>bottom)]=-1
        _,value,_,(x,y)=cv2.minMaxLoc(score)
        if value>best[0]:
            best=(value,[(x+x0+tw/2)/240,(y+y0+th/2)/320,th/240,0.],name)
    return {'score':best[0],'anchor':best[1],'template':best[2],'method':'head-template'}

def analyze(files,root,config,workers,rebuild):
    import hashlib
    cache_path=Path(__file__).with_name('body_alignment_cache.json')
    signature=hashlib.sha256(json.dumps([VERSION,{**config,'overrides':{}}],sort_keys=True).encode()).hexdigest()
    cache={} if rebuild or not cache_path.exists() else json.loads(cache_path.read_text())
    bank=templates(root,config)
    jobs=[(p,fingerprint(p,root,signature)) for p in files]
    pending=[j for j in jobs if j[1] not in cache]
    def job(item):
        p,key=item
        tiles=load_tiles(p,240,config['views'])
        result={v:detect(im,bank[v],v) for v,im in tiles.items()}
        for v,refs in config['templates'].items():
            for ref in refs:
                if ref['file']==p.relative_to(root).as_posix():
                    x,y,w,h=ref['box']
                    result[v]={'anchor':[x+w/2,y+h/2,h*4/3,0.], 'score':1.,'method':'manual-calibration'}
        for v,a in config.get('overrides',{}).get(p.relative_to(root).as_posix(),{}).items():
            result[v]={'anchor':a,'score':1.,'method':'manual-correction'}
        return key,result
    print(f'Analyzing {len(pending)} photographs; {len(jobs)-len(pending)} cached.',flush=True)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i,(key,result) in enumerate(pool.map(job,pending),1):
            cache[key]=result
            if i%50==0:
                print(f'Analyzed {i}/{len(pending)}',flush=True)
                cache_path.write_text(json.dumps(cache))
    cache_path.write_text(json.dumps(cache))
    records=[json.loads(json.dumps(cache[key])) for _,key in jobs]
    for p,record in zip(files,records):
        for view,anchor in config.get('overrides',{}).get(p.relative_to(root).as_posix(),{}).items():
            if len(anchor)!=4 or anchor[2]<=0 or not np.isfinite(anchor).all():
                raise ValueError(f'Invalid manual anchor: {p} / {view}')
            record[view]={'anchor':anchor,'score':1.,'method':'manual-correction'}
    return records

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=Path(__file__).with_name('body_video_config.json'))
    parser.add_argument('--output',type=Path)
    parser.add_argument('--speed',type=int,default=6)
    parser.add_argument('--fps',type=int,default=24)
    parser.add_argument('--width',type=int,default=720)
    parser.add_argument('--height',type=int,default=960)
    parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--sample-step',type=int,default=1)
    parser.add_argument('--layout',choices=['separate','grid','both'],default='both')
    parser.add_argument('--views',nargs='+',choices=['all','front','back','side_right','side_left'],default=['all'])
    parser.add_argument('--analyze-only',action='store_true')
    parser.add_argument('--rebuild-cache',action='store_true')
    parser.add_argument('--overwrite',action='store_true')
    parser.add_argument('--extras',action='store_true',help='Also make monthly grid and beginning/end comparisons')
    parser.add_argument('--output-names',nargs='+',choices=['front','back','side_right','side_left','all_views'],help='Regenerate only specified outputs')
    args=parser.parse_args()
    if args.speed<1 or args.fps<1 or args.fps%args.speed: parser.error('FPS must be a positive multiple of speed.')
    if args.workers<1 or args.sample_step<1: parser.error('Workers and sample-step must be positive.')
    if min(args.width,args.height)<480 or args.width%2 or args.height%2: parser.error('Dimensions must be even and at least 480.')
    config=json.loads(args.config.read_text())
    root=(args.config.parent/config['input']).resolve()
    output=(args.output or args.config.parent/config['output']).resolve()
    output.mkdir(parents=True,exist_ok=True)
    previous_report=json.loads((output/'alignment_report.json').read_text()) if (output/'alignment_report.json').exists() else {}
    files=ordered_files(root)[::args.sample_step]
    records=analyze(files,root,config,args.workers,args.rebuild_cache)
    report={'version':VERSION,'source_count':len(files),'photos_per_second':args.speed,'fps':args.fps,
            'alignment':'Head center and head height; translation and uniform scaling only. Camera roll and body pose retained.',
            'summary':{v:{'below_0.65':sum(r[v]['score']<.65 for r in records)} for v in config['views']},
            'frames':[{'file':p.relative_to(root).as_posix(),'views':r} for p,r in zip(files,records)]}
    (output/'alignment_report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report['summary']),flush=True)
    if not args.analyze_only:
        report['outputs']={k:str(v) for k,v in render(files,records,config,args,output).items()}
        if args.output_names:
            report['outputs']={**previous_report.get('outputs',{}),**report['outputs']}
            for key in ['monthly_selection','monthly_outputs']:
                if key in previous_report: report[key]=previous_report[key]
        if args.extras:
            import copy
            from make_face_videos import stabilize, add_header, MONTHS
            groups={}
            for i,p in enumerate(files): groups.setdefault(p.parent.name,[]).append(i)
            selected=[indices[len(indices)//2] for indices in groups.values()]
            monthly=copy.copy(args)
            monthly.views=['all'];monthly.layout='grid';monthly.hold_frames=args.fps*2
            monthly.output_names=None
            monthly.prefix='Body_monthly'
            report['monthly_selection']=[files[i].relative_to(root).as_posix() for i in selected]
            report['monthly_outputs']={k:str(v) for k,v in render([files[i] for i in selected],[records[i] for i in selected],config,monthly,output).items()}
            for view in config['views']:
                pair=[]
                for i in [0,len(files)-1]:
                    tile=load_tiles(files[i],720,config['views'])[view]
                    aligned=stabilize(tile,records[i][view]['anchor'],config['views'][view]['target'],args.width,args.height-64)
                    _,month,year=files[i].parent.name.split('_')
                    pair.append(add_header(aligned,f'{MONTHS[month]:02d}.{year}',config['views'][view]['label'],(i+1)/len(files)))
                cv2.imwrite(str(output/f'Body_beginning_end_{view}.jpg'),np.hstack(pair))
        (output/'alignment_report.json').write_text(json.dumps(report,indent=2))

if __name__=='__main__': main()
