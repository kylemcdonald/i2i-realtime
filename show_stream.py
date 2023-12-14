import numpy as np
import cv2
from turbojpeg import TurboJPEG, TJPF_RGB
import zmq
import msgpack
import time
from threaded_worker import ThreadedWorker
import subprocess

class ShowStream(ThreadedWorker):
    def __init__(self, port, fullscreen, mirror=False, debug=False):
        super().__init__(has_input=False, has_output=False)
        self.jpeg = TurboJPEG()
        self.context = zmq.Context()
        self.img_subscriber = self.context.socket(zmq.SUB)
        address = f"tcp://localhost:{port}"
        print(f"Connecting to {address}")
        self.img_subscriber.connect(address)
        self.img_subscriber.setsockopt(zmq.SUBSCRIBE, b"")
        self.fullscreen = fullscreen
        self.mirror = mirror
        self.debug = debug
        self.window_name = f"Port {port}"
        
    def setup(self):
        cv2.namedWindow(self.window_name, cv2.WINDOW_GUI_NORMAL)
        if self.fullscreen:
            cv2.setWindowProperty(self.window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    def work(self):
        msg = self.img_subscriber.recv()
        
        timestamp, index, jpg = msgpack.unpackb(msg)
        img = self.jpeg.decode(jpg, pixel_format=TJPF_RGB)
        input_h, input_w = img.shape[:2]

        # put the image on the left
        canvas = np.zeros((1024, 1280, 3), dtype=np.uint8)
        if self.mirror:
            img = img[:,::-1,:]
        canvas[:, :1024] = img
        img = canvas
        
        if self.debug:
            latency = time.time() - timestamp
            text = f"{input_w}x{input_h} @ {int(1000*latency)} ms"
            cv2.putText(
                img,
                text,
                (10, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 255),
                2,
                cv2.LINE_AA,
            )
        
        cv2.imshow(self.window_name, img[:, :, ::-1])

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
        elif key == ord("q") or key == ord("Q"):
            print("Shutting down", flush=True)
            subprocess.call(["./shutdown.sh"])
                
    def cleanup(self):
        self.img_subscriber.close()
        self.context.term()
        cv2.destroyAllWindows()