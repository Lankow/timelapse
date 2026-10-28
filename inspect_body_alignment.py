"""Create contact sheets of weakest head matches for visual review."""
import json
from pathlib import Path
import cv2
import numpy as np
from make_face_videos import load_tiles, stabilize

def main():
    config=json.loads(Path(__file__).with_name('body_video_config.json').read_text())
    root=(Path(__file__).parent/config['input']).resolve()
    output=(Path(__file__).parent/config['output']).resolve()
    frames=json.loads((output/'alignment_report.json').read_text())['frames']
    for view in config['views']:
        ordered=sorted(frames,key=lambda f:f['views'][view]['score'])
        # Include worst matches and evenly spaced timeline samples.
        chosen=ordered[:16]+[frames[i] for i in np.linspace(0,len(frames)-1,16,dtype=int)]
        sheet=np.full((4*320,8*180,3),24,np.uint8)
        for i,frame in enumerate(chosen):
            record=frame['views'][view]
            im=load_tiles(root/frame['file'],240,config['views'])[view]
            im=stabilize(im,record['anchor'],config['views'][view]['target'],180,296)
            tile=np.full((320,180,3),24,np.uint8);tile[24:]=im
            text=f"{Path(frame['file']).stem} {record['score']:.2f}"
            cv2.putText(tile,text,(3,16),0,.38,(240,240,240),1,cv2.LINE_AA)
            y,x=divmod(i,8);sheet[y*320:(y+1)*320,x*180:(x+1)*180]=tile
        cv2.imwrite(str(output/f'review_{view}.jpg'),sheet)

if __name__=='__main__':main()
