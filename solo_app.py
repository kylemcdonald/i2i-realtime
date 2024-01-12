import time
import zmq
import sdl2
import sdl2.ext
import numpy as np
import ctypes
import numpy as np
import torch
import torch.nn.functional as F
from threaded_worker import ThreadedWorker
from diffusion_processor import DiffusionProcessor
from settings import Settings
from settings_api import SettingsAPI
from osc_settings_controller import OscSettingsController

def unpack_rgb444_image(buffer, image_shape):
    mask = (2<<10) - 1
    img = np.frombuffer(buffer, dtype=np.uint32).reshape(*image_shape).byteswap()
    red = (img >> 20) & mask
    green = (img >> 10) & mask
    blue = (img) & mask
    unpacked_image = np.stack((red, green, blue)).astype(np.float32) / 1024.
    return unpacked_image

def half_size_batch(batch):
    return F.interpolate(batch, scale_factor=0.5, mode='area')

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
        self.settings_batch = []
        
    def work(self):
    
        try:
            msg = self.sock.recv(copy=False).bytes
        except zmq.Again:
            return
        
        if len(msg) == 8294400:
            img = torch.from_numpy(unpack_rgb444_image(msg, (1080, 1920)))
        elif len(msg) == 4147200:
            img = torch.frombuffer(msg, dtype=torch.uint8).view(1080, 1920, 2)
        else:
            print(f"Unknown image size {len(msg)}")
            return
        # self.batch.append(img) # on CPU from here
        self.batch.append(img.to("cuda")) # on GPU from here
        self.settings_batch.append(settings.copy())
        
        n = self.batch_size
        if len(self.batch) >= n:
            batch = torch.stack(self.batch[:n]) # save the first n elements
            if batch.shape[1] == 3:
                batch = half_size_batch(batch)
            elif batch.shape[-1] == 2:
                batch = uyvy_to_rgb_batch(batch)
            else:
                print("unknown channels")
            settings_batch = self.settings_batch[:n]
            self.batch = self.batch[n:] # drop the first n elements
            self.settings_batch = self.settings_batch[n:]
            return batch, settings_batch
        
    def cleanup(self):
        self.sock.close()
        self.context.term()

class Processor(ThreadedWorker):
    def __init__(self, settings):
        super().__init__(has_input=True, has_output=True, debug=True)
        self.batch_size = settings.batch_size
        self.settings = settings
        
    def setup(self):
        warmup = f"{self.batch_size}x540x960x3"
        self.diffusion_processor = DiffusionProcessor(warmup=warmup)
        self.clear_input() # drop old frames
        
    def work(self, args):
        images, settings_batch = args
        # cuda_images = torch.FloatTensor(np.array(images)).to("cuda")
        
        results = self.diffusion_processor.run(
            images=images,
            prompt=self.settings.prompt,
            use_compel=True,
            num_inference_steps=2,
            strength=0.7,
            seed=self.settings.seed)
        
        for frame_settings, image, result in zip(settings_batch, images, results):
            if frame_settings.opacity == 1:
                self.output_queue.put(result)
            else:
                opacity = float(frame_settings.opacity)
                input_image = np.transpose(image.cpu().numpy(), (1, 2, 0))[:result.shape[0]]
                blended = result * opacity + input_image * (1 - opacity) 
                self.output_queue.put(blended)
        
class Display(ThreadedWorker):
    def __init__(self, batch_size):
        super().__init__(has_input=True, has_output=False)
        self.fullscreen = True
        self.batch_size = batch_size
        self.width = 960
        self.height = 536
        self.channels = 3
        self.frame_repeat = 2
    
    def setup(self):
        sdl2.ext.init()
        
        self.window = sdl2.ext.Window("i2i", size=(self.width, self.height))
        self.renderer = sdl2.ext.Renderer(self.window, flags=sdl2.SDL_RENDERER_ACCELERATED | sdl2.SDL_RENDERER_PRESENTVSYNC)
        self.window.show()
        self.event = sdl2.SDL_Event()
        self.texture = sdl2.SDL_CreateTexture(self.renderer.sdlrenderer,
                                              sdl2.SDL_PIXELFORMAT_RGB24,
                                              sdl2.SDL_TEXTUREACCESS_STREAMING,
                                              self.width, self.height)
        
        if self.fullscreen:
            sdl2.SDL_SetWindowFullscreen(self.window.window, sdl2.SDL_WINDOW_FULLSCREEN_DESKTOP)
        
        self.clear_input() # drop old frames
    
    def work(self, frame):
        while self.input_queue.qsize() > self.batch_size:
            # print("dropping frame")
            frame = self.input_queue.get()
        
        # Event handling
        while sdl2.SDL_PollEvent(ctypes.byref(self.event)):
            if self.event.type == sdl2.SDL_QUIT:
                self.should_exit = True
            elif self.event.type == sdl2.SDL_KEYDOWN:
                keysym = self.event.key.keysym.sym
                if keysym == sdl2.SDLK_f:
                    self.fullscreen = not self.fullscreen
                    mode = sdl2.SDL_WINDOW_FULLSCREEN_DESKTOP if self.fullscreen else 0
                    sdl2.SDL_SetWindowFullscreen(self.window.window, mode)

        # Update texture
        image_data = (frame * 255).astype(np.uint8)
        sdl2.SDL_UpdateTexture(self.texture, None, image_data.ctypes.data, self.width * self.channels)

        # Render noise on screen
        sdl2.SDL_RenderClear(self.renderer.sdlrenderer)
        for i in range(self.frame_repeat):
            sdl2.SDL_RenderCopy(self.renderer.sdlrenderer, self.texture, None, None)
            sdl2.SDL_RenderPresent(self.renderer.sdlrenderer)
            # Renderer will now wait for vsync
                
    def cleanup(self):
        sdl2.SDL_DestroyTexture(self.texture)
        sdl2.ext.quit()

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

try:
    while True:
        time.sleep(1)
except:
    pass

settings_api.close()
settings_controller.close()
display.close()
processor.close()
receiver.close()