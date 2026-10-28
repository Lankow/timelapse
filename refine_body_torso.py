"""Track the persistent chest tattoo with a uniform-scale rigid transform."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json, threading
import cv2
import numpy as np
from make_face_videos import load_tiles
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'Output/Video/Body_Refined'
LOCAL=threading.local()

def detector():
    if not hasattr(LOCAL,'sift'):LOCAL.sift=cv2.SIFT_create(contrastThreshold=.015)
    return LOCAL.sift

def reference(frame):
    im=load_tiles(ROOT/'Output/Body/JPG'/frame['file'],1200,{'front':{'quadrant':[0,0]}})['front']
    crop=im[440:576,420:612]
    mask=np.zeros(crop.shape[:2],np.uint8)
    cv2.fillPoly(mask,[np.array([(42,43),(135,20),(168,24),(160,71),(116,104),(61,108)])],255)
    kp,desc=detector().detectAndCompute(cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY),mask)
    return kp,desc

def alternate_reference(frame,result):
    im=load_tiles(ROOT/'Output/Body/JPG'/frame['file'],1200,{'front':{'quadrant':[0,0]}})['front']
    x,y,span,angle=result['anchor'];scale=span*1200/192
    mat=cv2.getRotationMatrix2D((100.,65.),angle,scale)
    mat[:,2]+=np.array([x*1200-100,y*1600-65])
    crop=cv2.warpAffine(im,cv2.invertAffineTransform(mat),(192,136))
    mask=np.zeros((136,192),np.uint8)
    cv2.fillPoly(mask,[np.array([(42,43),(135,20),(168,24),(160,71),(116,104),(61,108)])],255)
    return detector().detectAndCompute(cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY),mask)

def track(frame,ref):
    im=load_tiles(ROOT/'Output/Body/JPG'/frame['file'],1200,{'front':{'quadrant':[0,0]}})['front']
    x,y,span,_=frame['views']['front']['anchor'];cx=x*1200;cy=y*1600;hh=span*1200
    x0=max(0,round(cx-hh*.95));x1=min(1200,round(cx+hh*.25))
    y0=max(0,round(cy+hh*.30));y1=min(1600,round(cy+hh*1.65))
    crop=im[y0:y1,x0:x1]
    kp,desc=detector().detectAndCompute(cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY),None)
    refkp,refdesc=ref
    if desc is None:return None
    pairs=cv2.BFMatcher().knnMatch(refdesc,desc,k=2)
    matches=[a for a,b in pairs if a.distance<.73*b.distance]
    if len(matches)<5:return None
    a=np.float32([refkp[m.queryIdx].pt for m in matches]);b=np.float32([kp[m.trainIdx].pt for m in matches])
    mat,inliers=cv2.estimateAffinePartial2D(a,b,method=cv2.RANSAC,ransacReprojThreshold=2.,maxIters=3000,confidence=.995,refineIters=20)
    if mat is None:return None
    count=int(inliers.sum());scale=float(np.hypot(mat[0,0],mat[1,0]));angle=float(-np.degrees(np.arctan2(mat[1,0],mat[0,0])))
    if count<5 or not .65<scale<1.45 or abs(angle)>18:return None
    src=a[inliers.ravel().astype(bool)]
    if np.ptp(src[:,0])<35 or np.ptp(src[:,1])<20:return None
    center=mat@np.array([100.,65.,1.]);center+=np.array([x0,y0])
    error=float(np.sqrt(np.mean(np.sum((a@mat[:,:2].T+mat[:,2]-b)[inliers.ravel().astype(bool)]**2,axis=1))))
    return {'anchor':[float(center[0]/1200),float(center[1]/1600),192*scale/1200,angle],
            'method':'tattoo-sift-similarity','score':count/len(matches),'inliers':count,'matches':len(matches),'reprojection_error_px':error}

def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--retry-missing',action='store_true',help='Reuse the existing analysis for this unchanged archive')
    parser.add_argument('--source-report',type=Path,default=ROOT/'Output/Video/Body_Stabilized/alignment_report.json')
    args=parser.parse_args()
    source=json.loads(args.source_report.read_text())
    ref=reference(source['frames'][0])
    if args.retry_missing:
        results=json.loads((OUT/'torso_tracking.json').read_text())
        if len(results)!=len(source['frames']):raise ValueError('Archive changed; rerun without --retry-missing')
    else:
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=[]
            for i,r in enumerate(pool.map(lambda f:track(f,ref),source['frames'])):
                results.append(r)
                if (i+1)%100==0:print(f'Torso tracked {i+1}/{len(source["frames"])}',flush=True)
    alternatives=[alternate_reference(source['frames'][i],results[i]) for i in [80,239,399,500] if i<len(results) and results[i]]
    for i,r in enumerate(results):
        if r is None:
            candidates=[track(source['frames'][i],ref) for ref in alternatives]
            candidates=[c for c in candidates if c]
            if candidates:
                results[i]=max(candidates,key=lambda c:c['inliers'])
                results[i]['method']='tattoo-sift-alternate-reference'
    (OUT/'torso_tracking.json').write_text(json.dumps(results,indent=2))
    print('Missing:',[f['file'] for f,r in zip(source['frames'],results) if r is None],flush=True)
    if any(r is None for r in results):raise RuntimeError('Unresolved torso matches; review before rendering.')
    for f,r in zip(source['frames'],results):f['views']['front']=r
    source['photos_per_second']=8
    source['alignment']='Front: chest tattoo feature matching; translation, rotation and uniform scale only. Body contours are not tracking inputs.'
    source.pop('outputs',None);source.pop('monthly_outputs',None)
    (OUT/'alignment_report.json').write_text(json.dumps(source,indent=2))
    config=json.loads((ROOT/'Script/body_video_config.json').read_text())
    config['views']['front']['target']=[.39,.43,.26]
    config['views']['front']['label']='Front - torso stabilized'
    (OUT/'render_config.json').write_text(json.dumps(config,indent=2))

if __name__=='__main__':main()
