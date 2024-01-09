import time
import zmq
import cv2
import numpy as np
import torch
import torch.nn.functional as F
from threaded_worker import ThreadedWorker
from diffusion_processor import DiffusionProcessor
from settings import Settings
from settings_api import SettingsAPI
from osc_settings_controller import OscSettingsController

def uyvy_to_rgb_batch(uyvy_images):
    # Convert the batch of images to float32
    uyvy_f32 = uyvy_images.to(torch.float32)
    
    # Handle the Y channel
    y_channel = uyvy_f32[:, :, :, 1].unsqueeze(1)  # Keep the Y channel in its own dimension
    y_channel = F.interpolate(y_channel, scale_factor=0.5, mode='area')
    
    # Handle the U channel
    u_channel = uyvy_f32[:, :, 0::2, 0].unsqueeze(1)
    h, w = y_channel.shape[-2], y_channel.shape[-1] # Extract the new dimensions after Y interpolation
    u_channel = F.interpolate(u_channel, size=(h,w), mode='area')
    
    # Handle the V channel
    v_channel = uyvy_f32[:, :, 1::2, 0].unsqueeze(1)
    v_channel = F.interpolate(v_channel, size=(h,w), mode='area')

    # Normalize channels to [0,1] range
    y_channel /= 255.0
    u_channel /= 255.0
    v_channel /= 255.0
    
    # Recalculate R, G, B based on Y, U, V
    r = y_channel + 1.402 * (v_channel - 0.5)
    g = y_channel - 0.344136 * (u_channel - 0.5) - 0.714136 * (v_channel - 0.5)
    b = y_channel + 1.772 * (u_channel - 0.5)

    # Stack the channels and clamp the values
    rgb_images = torch.cat((r, g, b), dim=1)  # Concatenate along the color channel dimension
    rgb_images = torch.clamp(rgb_images, 0.0, 1.0)
    
    return rgb_images

class Receiver(ThreadedWorker):
    def __init__(self, batch_size):
        super().__init__(has_input=False, has_output=True)
        self.batch_size = batch_size
        
    def setup(self):
        self.context = zmq.Context()
        self.sock = self.context.socket(zmq.SUB)
        address = f"ipc:///tmp/zmq"
        print(f"Connecting to {address}")
        self.sock.connect(address)
        self.sock.setsockopt(zmq.SUBSCRIBE, b"")
        self.sock.setsockopt(zmq.RCVTIMEO, 100)
        self.sock.setsockopt(zmq.RCVHWM, 1)
        self.sock.setsockopt(zmq.LINGER, 0)
        self.batch = []
        
    def work(self):
        try:
            msg = self.sock.recv(flags=zmq.NOBLOCK, copy=False).bytes
        except zmq.Again:
            return
        
        uyvy_image = torch.frombuffer(msg, dtype=torch.uint8).view(1080, 1920, 2).to("cuda")        
        self.batch.append(uyvy_image)
        
        n = self.batch_size
        if len(self.batch) >= n:
            batch = torch.stack(self.batch[:n]) # save the first n elements
            batch = uyvy_to_rgb_batch(batch)
            self.batch = self.batch[n:] # drop the first n elements
            return batch
        
    def cleanup(self):
        self.sock.close()
        self.context.term()

class Processor(ThreadedWorker):
    def __init__(self, settings):
        super().__init__(has_input=True, has_output=True)
        self.batch_size = settings.batch_size
        self.durations = []
        self.frame_count = 0
        self.print_interval = 30
        self.settings = settings
        
    def setup(self):
        warmup = f"{self.batch_size}x540x960x3"
        self.diffusion_processor = DiffusionProcessor(warmup=warmup)
        self.clear_input() # drop old frames
        
    def work(self, images):        
        # cuda_images = torch.FloatTensor(np.array(images)).to("cuda")
        start_time = time.time()
        results = self.diffusion_processor.run(
            images=images,
            prompt=self.settings.prompt,
            use_compel=True,
            num_inference_steps=2,
            strength=0.7,
            seed=self.settings.seed)
        duration = time.time() - start_time
        self.durations.append(duration)
        if len(self.durations) > 10:
            self.durations.pop(0)
        duration = np.mean(self.durations)
        
        if self.frame_count > self.print_interval:
            print(
                f"diffusion {duration*1000:.2f}ms/batch, {duration*1000/self.batch_size:.2f}ms/frame",
                flush=True,
            )
            self.frame_count -= self.print_interval
        self.frame_count += len(results)
        
        for result in results:
            self.output_queue.put(result)

class Display(ThreadedWorker):
    def __init__(self, batch_size):
        super().__init__(has_input=True, has_output=False)
        self.fullscreen = True
        self.window_name = "i2i"
        self.batch_size = batch_size
        self.target_frame_duration = 1/30
        self.last_frame_time = None
    
    def setup(self):
        cv2.namedWindow(self.window_name, cv2.WINDOW_GUI_NORMAL)
        if self.fullscreen:
            cv2.setWindowProperty(self.window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    
    def work(self, frame):
        # this isn't the most elegant solution, but it works
        if self.input_queue.qsize() > self.batch_size:
            print("delayed:", self.input_queue.qsize(), flush=True)
            self.clear_input()
            
        cv2.imshow(self.window_name, frame[:,:,::-1])
        
        # toggle fullscreen when user presses 'f' key
        key = cv2.waitKey(1)
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
    
        if self.last_frame_time is not None:
            elapsed = time.time() - self.last_frame_time
            if elapsed < self.target_frame_duration:
                time.sleep(self.target_frame_duration - elapsed)
                
    def cleanup(self):
        cv2.destroyAllWindows()

try:    
    settings = Settings()
    settings_api = SettingsAPI(settings)
    settings_controller = OscSettingsController(settings)
    
    receiver = Receiver(settings.batch_size)
    processor = Processor(settings).feed(receiver)
    display = Display(settings.batch_size).feed(processor)

    settings_api.start()
    settings_controller.start()
    display.start()
    processor.start()
    receiver.start()
    
    while True:
        time.sleep(1)
        
except KeyboardInterrupt:
    pass
finally:
    settings_api.close()
    settings_controller.close()
    display.close()
    processor.close()
    receiver.close()