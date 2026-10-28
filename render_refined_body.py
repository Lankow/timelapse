"""Render the reviewed torso alignment at eight source photos per second."""
import argparse, copy, json
from pathlib import Path
import numpy as np
import cv2
from body_render import render
from make_face_videos import load_tiles, stabilize, add_header, MONTHS

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'Output/Video/Body_Refined'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--speed',type=int,default=8)
    parser.add_argument('--views',nargs='+',default=['all'])
    parser.add_argument('--layout',choices=['separate','grid','both'],default='both')
    parser.add_argument('--extras',action='store_true')
    args=parser.parse_args()
    if args.speed<1 or 24%args.speed:parser.error('Speed must divide 24.')
    args.width=720;args.height=960;args.fps=24;args.workers=4;args.overwrite=True
    report=json.loads((OUT/'alignment_report.json').read_text())
    config=json.loads((OUT/'render_config.json').read_text())
    files=[ROOT/'Output/Body/JPG'/f['file'] for f in report['frames']]
    records=[f['views'] for f in report['frames']]
    report['photos_per_second']=args.speed
    report['outputs']={k:str(v) for k,v in render(files,records,config,args,OUT).items()}
    if args.extras:
        months={}
        for i,p in enumerate(files):months.setdefault(p.parent.name,[]).append(i)
        selected=[indices[len(indices)//2] for indices in months.values()]
        monthly=copy.copy(args);monthly.views=['all'];monthly.layout='grid';monthly.hold_frames=36;monthly.prefix='Body_monthly'
        report['monthly_selection']=[report['frames'][i]['file'] for i in selected]
        report['monthly_outputs']={k:str(v) for k,v in render([files[i] for i in selected],[records[i] for i in selected],config,monthly,OUT).items()}
        report['monthly_seconds_per_photo']=1.5
        for view in config['views']:
            pair=[]
            for i in [0,len(files)-1]:
                tile=load_tiles(files[i],720,config['views'])[view]
                im=stabilize(tile,records[i][view]['anchor'],config['views'][view]['target'],720,896)
                _,month,year=files[i].parent.name.split('_')
                pair.append(add_header(im,f'{MONTHS[month]:02d}.{year}',config['views'][view]['label'],(i+1)/len(files)))
            cv2.imwrite(str(OUT/f'Body_beginning_end_{view}.jpg'),np.hstack(pair))
    (OUT/'alignment_report.json').write_text(json.dumps(report,indent=2))

if __name__=='__main__':main()
