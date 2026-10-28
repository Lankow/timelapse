"""Refine the front view using calibrated central-face templates and camera roll."""
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import cv2
import numpy as np
from make_face_videos import load_tiles, stabilize

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'Output/Video/Body_Refined'

def camera_roll(image):
    small=cv2.resize(image,(300,400))
    lines=cv2.HoughLinesP(cv2.Canny(small,60,130),1,np.pi/1800,45,minLineLength=160,maxLineGap=25)
    angles=[]
    if lines is not None:
        for (x1,y1,x2,y2), in lines:
            if y1>y2:x1,x2,y1,y2=x2,x1,y2,y1
            if .18*300<(x1+x2)/2<.39*300 and abs(x2-x1)<.14*(y2-y1):
                angles.append(-np.degrees(np.arctan2(x2-x1,y2-y1)))
    return float(np.median(angles)) if angles else None

def subpixel(values,i):
    if i<1 or i>=len(values)-1:return 0.
    a,b,c=map(float,values[i-1:i+2]);den=a-2*b+c
    return float(np.clip(.5*(a-c)/den,-.5,.5)) if den< -1e-6 else 0.

def build_bank():
    refs=json.loads((ROOT/'Script/body_front_calibration.json').read_text())
    bank=[]
    for ref in refs:
        im=load_tiles(ROOT/'Output/Body/JPG'/ref['file'],900,{'front':{'quadrant':[0,0]}})['front']
        mx=ref['center_x'];my=ref['center_y'];span=ref['eye_span']
        angle=camera_roll(im) or 0.
        # Same camera-roll correction for reference and candidate; no body warp.
        mat=cv2.getRotationMatrix2D((mx,my),angle,32/span)
        mat[:,2]+=np.array([40-mx,32-my])
        canonical=cv2.warpAffine(cv2.cvtColor(im,cv2.COLOR_BGR2GRAY),mat,(80,64))
        refsizes=[]
        for sep in np.arange(22.,40.01,.5):
            t=cv2.resize(canonical,(round(80*sep/32),round(64*sep/32)))
            refsizes.append((float(sep),t))
        bank.append((ref['file'],refsizes))
    return bank

def refine(frame,bank):
    im=load_tiles(ROOT/'Output/Body/JPG'/frame['file'],600,{'front':{'quadrant':[0,0]}})['front']
    x,y,span,_=frame['views']['front']['anchor'];cx=x*600;cy=y*800;hh=span*600
    roll=camera_roll(im)
    angle=roll or 0.
    mat=cv2.getRotationMatrix2D((cx,cy),angle,1.)
    upright=cv2.warpAffine(im,mat,(600,800))
    gray=cv2.cvtColor(upright,cv2.COLOR_BGR2GRAY)
    x0=max(0,round(cx-.40*hh));x1=min(600,round(cx+.40*hh))
    y0=max(0,round(cy-.20*hh));y1=min(800,round(cy+.55*hh))
    roi=gray[y0:y1,x0:x1]
    best=(-1,None)
    for name,sizes in bank:
        candidates=[]
        for sep,t in sizes:
            th,tw=t.shape
            if th>=roi.shape[0] or tw>=roi.shape[1]:candidates.append(None);continue
            score=cv2.matchTemplate(roi,t,cv2.TM_CCOEFF_NORMED)
            _,value,_,(px,py)=cv2.minMaxLoc(score)
            dx=subpixel(score[py],px);dy=subpixel(score[:,px],py)
            candidates.append((value,px+dx+x0+tw/2,py+dy+y0+th/2,sep))
        valid=[(c[0],i,c) for i,c in enumerate(candidates) if c]
        if not valid:continue
        value,i,c=max(valid)
        scale_delta=0.
        if 0<i<len(candidates)-1 and candidates[i-1] and candidates[i+1]:
            scale_delta=subpixel([v[0] if v else -1 for v in candidates],i)*.5
        if value>best[0]:best=(value,(c[1],c[2],c[3]+scale_delta,name))
    if best[1] is None:raise RuntimeError(f'No front match: {frame["file"]}')
    ex,ey,sep,name=best[1]
    inverse=cv2.invertAffineTransform(mat)
    sx,sy=inverse@np.array([ex,ey,1.])
    return {'anchor':[float(sx/600),float(sy/800),float(sep/600),angle],
            'score':float(best[0]),'method':'central-face-subpixel','template':name,
            'camera_roll_detected':roll is not None}

def main():
    OUT.mkdir(exist_ok=True)
    source=json.loads((ROOT/'Output/Video/Body_Stabilized/alignment_report.json').read_text())
    bank=build_bank()
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i,result in enumerate(pool.map(lambda f:refine(f,bank),source['frames'])):
            source['frames'][i]['views']['front']=result
            if (i+1)%100==0:print(f'Refined {i+1}/559',flush=True)
    # Use neighboring roll only when no long background vertical was detected.
    good=[i for i,f in enumerate(source['frames']) if f['views']['front']['camera_roll_detected']]
    angles=[source['frames'][i]['views']['front']['anchor'][3] for i in good]
    for i,f in enumerate(source['frames']):
        if not f['views']['front']['camera_roll_detected']:
            f['views']['front']['anchor'][3]=float(np.interp(i,good,angles)) if good else 0.
    source['photos_per_second']=8
    source['alignment']='Front: subpixel central-face matching, uniform scale, translation and background camera-roll correction. Other views: original head alignment.'
    source.pop('outputs',None);source.pop('monthly_outputs',None)
    (OUT/'alignment_report.json').write_text(json.dumps(source,indent=2))
    config=json.loads((ROOT/'Script/body_video_config.json').read_text())
    config['views']['front']['target']=[.5,.26,.08]
    (OUT/'render_config.json').write_text(json.dumps(config,indent=2))
    from body_render import render
    import argparse
    args=argparse.Namespace(views=['front'],layout='separate',width=720,height=960,fps=24,speed=8,workers=4,overwrite=True)
    files=[ROOT/'Output/Body/JPG'/f['file'] for f in source['frames']]
    records=[f['views'] for f in source['frames']]
    source['outputs']={k:str(v) for k,v in render(files,records,config,args,OUT).items()}
    (OUT/'alignment_report.json').write_text(json.dumps(source,indent=2))

if __name__=='__main__':main()
