import cv2
import numpy as np
from turbojpeg import TurboJPEG, TJPF_RGB
import zmq
import msgpack
import time
from threaded_worker import ThreadedWorker

class ShowStream(ThreadedWorker):
    def __init__(self, port, settings):
        super().__init__(has_input=False, has_output=False)
        self.port = port
        self.fullscreen = True
        self.settings = settings
        
    def setup(self):
        self.jpeg = TurboJPEG()
        
        self.context = zmq.Context()
        self.sock = self.context.socket(zmq.SUB)
        self.sock.setsockopt(zmq.RCVTIMEO, 100)
        self.sock.setsockopt(zmq.RCVHWM, 1)
        self.sock.setsockopt(zmq.LINGER, 0)
        address = f"tcp://localhost:{self.port}"
        print(f"Connecting to {address}")
        self.sock.connect(address)
        self.sock.setsockopt(zmq.SUBSCRIBE, b"")
        
        self.window_name = f"Port {self.port}"
        cv2.namedWindow(self.window_name, cv2.WINDOW_GUI_NORMAL)
        
        if self.fullscreen:
            cv2.setWindowProperty(self.window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    def show_msg(self, msg):
        timestamp, index, jpg = msgpack.unpackb(msg)
        img = self.jpeg.decode(jpg, pixel_format=TJPF_RGB)
        input_h, input_w = img.shape[:2]

        if self.settings.mirror:
            img = img[:,::-1,:]
            
        if self.settings.pad:
            screen_h, screen_w = (1080, 1920)
            canvas = np.zeros((screen_h, screen_w, 3), dtype=np.uint8)
            start_x = (screen_w - input_w) // 2
            start_y = (screen_h - input_h) // 2
            canvas[start_y:start_y+input_h, start_x:start_x+input_w] = img
            img = canvas
        
        if self.settings.debug:
            latency = time.time() - timestamp
            text = f"{input_w}x{input_h} @ {int(1000*latency)} ms"
            cv2.putText(
                img,
                text,
                (10, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (255, 255, 0),
                2,
                cv2.LINE_AA,
            )
        
        cv2.imshow(self.window_name, img[:, :, ::-1])

    def work(self):
        try:
            msg = self.sock.recv(flags=zmq.NOBLOCK, copy=False).bytes
            self.show_msg(msg)
        except zmq.Again:
            pass

        key = cv2.waitKey(1)
        # toggle fullscreen when user presses 'f' key
        if key == ord("f") or key == ord("F"):
            self.fullscreen = not self.fullscreen
            if self.fullscreen:
                cv2.setWindowProperty(
                    self.window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN
                )
            else:
                cv2.setWindowProperty(
                    self.window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_KEEPRATIO
                )
                
        if key == ord("d") or key == ord("D"):
            self.settings.debug = not self.settings.debug
                
    def cleanup(self):
        self.sock.close()
        self.context.term()
        cv2.destroyAllWindows()