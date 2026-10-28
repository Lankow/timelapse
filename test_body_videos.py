import unittest
from unittest.mock import patch
import cv2
import numpy as np
from make_body_videos import detect
from make_face_videos import stabilize
from refine_body_front import camera_roll, subpixel
from refine_body_torso import reference, track

class BodyTests(unittest.TestCase):
    def test_torso_tracker_recovers_camera_transform(self):
        rng=np.random.default_rng(19)
        image=np.full((1600,1200,3),180,np.uint8)
        texture=rng.integers(0,255,(136,192,3),dtype=np.uint8)
        image[440:576,420:612]=cv2.GaussianBlur(texture,(3,3),.7)
        frame={'file':'synthetic.jpg','views':{'front':{'anchor':[.5,.18,.22,0]}}}
        with patch('refine_body_torso.load_tiles',return_value={'front':image}):ref=reference(frame)
        mat=cv2.getRotationMatrix2D((520,505),4,1.04)
        mat[:,2]+=np.array([12,-8])
        moved=cv2.warpAffine(image,mat,(1200,1600))
        moved[800:1100,200:900]=50
        with patch('refine_body_torso.load_tiles',return_value={'front':moved}):result=track(frame,ref)
        self.assertIsNotNone(result)
        expected=mat@np.array([520,505,1])
        self.assertAlmostEqual(result['anchor'][0]*1200,expected[0],delta=1)
        self.assertAlmostEqual(result['anchor'][1]*1600,expected[1],delta=1)
        self.assertAlmostEqual(result['anchor'][2]*1200/192,1.04,delta=.01)
        self.assertAlmostEqual(result['anchor'][3],4,delta=.3)

    def test_subpixel_peak(self):
        x=np.arange(5,dtype=float)
        self.assertAlmostEqual(subpixel(-(x-2.3)**2,2),.3,places=5)

    def test_camera_roll_from_background_vertical(self):
        image=np.zeros((400,300,3),np.uint8)
        cv2.line(image,(80,5),(100,395),(255,255,255),3)
        self.assertAlmostEqual(camera_roll(image),-np.degrees(np.arctan2(20,390)),delta=.5)

    def test_head_detection_ignores_torso_width(self):
        rng=np.random.default_rng(7)
        head=rng.integers(0,255,(44,32),dtype=np.uint8)
        bank=[('test',44,head)]
        anchors=[]
        for width in (40,90):
            image=np.full((320,240),170,np.uint8)
            image[35:79,104:136]=head
            image[100:220,120-width//2:120+width//2]=70
            result=detect(cv2.cvtColor(image,cv2.COLOR_GRAY2BGR),bank,'front')
            self.assertGreater(result['score'],.99)
            anchors.append(result['anchor'])
        self.assertEqual(anchors[0],anchors[1])
        self.assertAlmostEqual(anchors[0][0],.5)
        self.assertAlmostEqual(anchors[0][2],44/240)

    def test_uniform_scaling_preserves_body_aspect(self):
        image=np.zeros((320,240,3),np.uint8)
        image[100:200,90:150]=255
        output=stabilize(image,[.5,.2,.2,0],[.5,.2,.3],480,640)
        ys,xs=np.where(output[:,:,0]>220)
        self.assertAlmostEqual((xs.max()-xs.min()+1)/(ys.max()-ys.min()+1),.6,delta=.02)

if __name__=='__main__':unittest.main()
