import time
import cv2
import zmq
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
        
    def work(self):
        ret, frame = self.cap.read()
        encoded = self.jpeg.encode(frame)
        return encoded
        
    def cleanup(self):
        self.cap.release()
        
class ZmqSender(ThreadedWorker):
    def __init__(self):
        super().__init__(has_input=True)
        self.context = zmq.Context()
        self.sock = self.context.socket(zmq.PUB)
        self.sock.bind(f"ipc:///tmp/zmq")
        self.sock.setsockopt(zmq.SNDHWM, 1)
        self.sock.setsockopt(zmq.LINGER, 0)
      
    def work(self, encoded):
        self.sock.send(encoded)
        
    def cleanup(self):
        self.sock.close()
        self.context.term()
        
if __name__ == "__main__":
    camera = ThreadedCamera()
    sender = ZmqSender()
    
    sender.feed(camera)
    
    sender.start()
    camera.start()
    try:
        while True:
            time.sleep(1)
    except:
        pass
    sender.close()
    camera.close()