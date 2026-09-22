import tempfile
import unittest
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
from make_face_videos import ordered_files, load_tiles, stabilize, template_anchor

class VideoTests(unittest.TestCase):
    def test_numeric_chronology_and_mixed_formats(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for month, names in [('39_October_2025',['face_1000.jpg','face_999.png']),('38_September_2025',['face_998.jpg'])]:
                folder=root/month;folder.mkdir()
                for name in names:(folder/name).touch()
            self.assertEqual([p.stem for p in ordered_files(root)],['face_998','face_999','face_1000'])
            (root/'39_October_2025'/'face_999.jpg').touch()
            with self.assertRaises(ValueError):ordered_files(root)

    def test_quadrants_not_swapped(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'collage.png'
            image=Image.new('RGB',(800,1066))
            colors={'front':(255,0,0),'top':(0,255,0),'left':(0,0,255),'right':(255,255,0)}
            settings={}
            for (name,color),(x,y) in zip(colors.items(),[(0,0),(1,0),(0,1),(1,1)]):
                image.paste(color,(x*400,y*533,(x+1)*400,(y+1)*533));settings[name]={'quadrant':[x,y]}
            image.save(path)
            tiles=load_tiles(path,120,settings)
            for name,color in colors.items():self.assertEqual(tuple(int(v) for v in tiles[name][50,50]),color[::-1])

    def test_eye_transform_levels_and_centers_landmarks(self):
        image=np.zeros((320,240,3),np.uint8)
        angle=12.;span=60.;center=np.array([110.,170.])
        direction=np.array([np.cos(np.deg2rad(angle)),np.sin(np.deg2rad(angle))])
        for p in [center-direction*span/2,center+direction*span/2]:cv2.circle(image,tuple(np.rint(p).astype(int)),3,(255,255,255),-1)
        aligned=stabilize(image,[center[0]/240,center[1]/320,span/240,angle],[.5,.45,.3],480,640)
        count,_,stats,centers=cv2.connectedComponentsWithStats((aligned[:,:,0]>220).astype(np.uint8))
        eyes=sorted(centers[1:].tolist())
        self.assertEqual(len(eyes),2)
        self.assertAlmostEqual((eyes[0][0]+eyes[1][0])/2,240,delta=2)
        self.assertAlmostEqual((eyes[0][1]+eyes[1][1])/2,288,delta=2)
        self.assertAlmostEqual(eyes[1][0]-eyes[0][0],144,delta=3)
        self.assertAlmostEqual(eyes[1][1]-eyes[0][1],0,delta=3)

    def test_template_follows_translation(self):
        rng=np.random.default_rng(42)
        template=rng.integers(0,255,(114,90),dtype=np.uint8)
        image=np.full((320,240),160,np.uint8)
        image[150:264,73:163]=template
        bank=[('synthetic',[template])]
        first=template_anchor(cv2.cvtColor(image,cv2.COLOR_GRAY2BGR),bank)['anchor']
        shifted=cv2.warpAffine(image,np.float32([[1,0,9],[0,1,12]]),(240,320),borderValue=160)
        second=template_anchor(cv2.cvtColor(shifted,cv2.COLOR_GRAY2BGR),bank)['anchor']
        self.assertAlmostEqual((second[0]-first[0])*240,9,delta=1)
        self.assertAlmostEqual((second[1]-first[1])*320,12,delta=1)
        self.assertAlmostEqual(second[2],first[2],delta=.01)

if __name__=='__main__':unittest.main()
