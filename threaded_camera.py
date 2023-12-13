import time
import cv2
from turbojpeg import TurboJPEG
from threaded_worker import ThreadedWorker

class ThreadedCamera(ThreadedWorker):
    def __init__(self):
        super().__init__(has_input=False)
        self.jpeg = TurboJPEG()
        self.cap = cv2.VideoCapture(-1, cv2.CAP_V4L2)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
        self.cap.set(cv2.CAP_PROP_FPS, 30)

    def setup(self):
        self.start_time = time.time()
        self.frame_number = 0
        
    def work(self):
        timestamp = time.time()
        self.frame_number += 1
        # if self.frame_number % 30 == 0:
        #     duration = time.time() - self.start_time
        #     fps = self.frame_number / duration
        #     print(f"fps {fps:.2f}")
        
        ret, frame = self.cap.read()
        
        # crop to the center 1024x1024
        frame = frame[28:1052, 448:1472]
        
        # print(frame.shape)
        encoded = self.jpeg.encode(frame)
        return timestamp, self.frame_number, encoded
        
    def cleanup(self):
        self.cap.release()