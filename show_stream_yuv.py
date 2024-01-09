import numpy as np
import cv2
import zmq
import msgpack
import time
from threaded_worker import ThreadedWorker
import torch
import torch.nn.functional as F

def uyvy_to_rgb_half(uyvy_image):
    uyvy_f32 = uyvy_image.to(torch.float32)
    y_channel = uyvy_f32[:, :, 1].unsqueeze(0).unsqueeze(0)
    y_channel = F.interpolate(y_channel, scale_factor=0.5, mode='area')
    y_channel = y_channel.squeeze()
    u_channel = uyvy_f32[:, 0::2, 0].unsqueeze(0).unsqueeze(0)
    u_channel = F.interpolate(u_channel, size=(540, 960), mode='area').squeeze()
    v_channel = uyvy_f32[:, 1::2, 0].unsqueeze(0).unsqueeze(0)
    v_channel = F.interpolate(v_channel, size=(540, 960), mode='area').squeeze()
    y_channel /= 255
    u_channel /= 255
    v_channel /= 255
    r = y_channel + 1.402 * (v_channel - 0.5)
    g = y_channel - 0.344136 * (u_channel - 0.5) - 0.714136 * (v_channel - 0.5)
    b = y_channel + 1.772 * (u_channel - 0.5)
    rgb_image = torch.stack((r, g, b), -1)
    rgb_image = torch.clamp(rgb_image * 255.0, 0.0, 255.0).to(torch.uint8)
    return rgb_image

def uyvy_to_rgb_full(uyvy_image):
    y_channel = uyvy_image[:, :, 1]
    u_channel = uyvy_image[:, 0::2, 0]
    v_channel = uyvy_image[:, 1::2, 0]
    u_channel = u_channel.repeat_interleave(2, dim=1)
    v_channel = v_channel.repeat_interleave(2, dim=1)
    y_channel = y_channel.to(torch.float32) / 255
    u_channel = u_channel.to(torch.float32) / 255
    v_channel = v_channel.to(torch.float32) / 255
    r = y_channel + 1.402 * (v_channel - 0.5)
    g = y_channel - 0.344136 * (u_channel - 0.5) - 0.714136 * (v_channel - 0.5)
    b = y_channel + 1.772 * (u_channel - 0.5)
    rgb_image = torch.stack((r, g, b), -1)
    rgb_image = torch.clamp(rgb_image * 255.0, 0.0, 255.0).to(torch.uint8)
    return rgb_image

class ShowStream(ThreadedWorker):
    def __init__(self):
        super().__init__(has_input=False, has_output=False)
        self.context = zmq.Context()
        self.img_subscriber = self.context.socket(zmq.SUB)
        address = f"ipc:///tmp/zmq"
        print(f"Connecting to {address}")
        self.img_subscriber.connect(address)
        self.img_subscriber.setsockopt(zmq.SUBSCRIBE, b"")
        self.fullscreen = False #True
        self.window_name = "Stream"
        
    def setup(self):
        cv2.namedWindow(self.window_name, cv2.WINDOW_GUI_NORMAL)
        if self.fullscreen:
            cv2.setWindowProperty(self.window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    def work(self):
        msg = self.img_subscriber.recv(copy=False)
        uyvy_image = torch.frombuffer(msg.buffer, dtype=torch.uint8).view(1080, 1920, 2).to("cuda")
        img = uyvy_to_rgb_half(uyvy_image).cpu().numpy()
        
        cv2.imshow(self.window_name, img[:,:,::-1])

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
        self.img_subscriber.close()
        self.context.term()
        cv2.destroyAllWindows()
        
if __name__ == "__main__":
    show_stream = ShowStream()
    show_stream.run()