import numpy as np
import cv2
from turbojpeg import TurboJPEG, TJPF_RGB
import zmq
import msgpack
import time
from threaded_worker import ThreadedWorker

class ShowStream(ThreadedWorker):
    def __init__(self, port, settings):
        super().__init__(has_input=False, has_output=False)
        self.jpeg = TurboJPEG()
        self.context = zmq.Context()
        self.sock = self.context.socket(zmq.SUB)
        self.sock.setsockopt(zmq.RCVTIMEO, 100)
        self.sock.setsockopt(zmq.RCVHWM, 1)
        self.sock.setsockopt(zmq.LINGER, 0)
        address = f"tcp://localhost:{port}"
        print(f"Connecting to {address}")
        self.sock.connect(address)
        self.sock.setsockopt(zmq.SUBSCRIBE, b"")
        self.fullscreen = True
        self.settings = settings
        self.window_name = f"Port {port}"
        
    def setup(self):
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
            canvas = np.zeros((1024, 1280, 3), dtype=np.uint8)
            canvas[:, :1024] = img
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
                
    def cleanup(self):
        self.sock.close()
        self.context.term()
        cv2.destroyAllWindows()