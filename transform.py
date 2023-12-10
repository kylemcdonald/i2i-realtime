import zmq
import json
import base64
import cv2
import numpy as np
import argparse
import time
import threading
from turbojpeg import TurboJPEG, TJPF_RGB

from sfast.compilers.stable_diffusion_pipeline_compiler import (
    compile, CompilationConfig)

from diffusers import AutoPipelineForImage2Image, AutoencoderTiny
import torch
import warnings
warnings.filterwarnings("ignore", category=torch.jit.TracerWarning)

from PIL import Image

from settings_subscriber import SettingsSubscriber

pipe = AutoPipelineForImage2Image.from_pretrained(
    "stabilityai/sdxl-turbo",
    torch_dtype=torch.float16,
    variant="fp16",
)

pipe.vae = AutoencoderTiny.from_pretrained(
    "madebyollin/taesdxl",
    torch_dtype=torch.float16)

pipe.set_progress_bar_config(disable=True)

config = CompilationConfig.Default()
config.enable_xformers = True
config.enable_triton = True
config.enable_cuda_graph = True
pipe = compile(pipe, config=config)

pipe.to(device="cuda", dtype=torch.float16).to("cuda")
pipe.set_progress_bar_config(disable=True)

parser = argparse.ArgumentParser()
parser.add_argument("--input_port", type=int, default=5555, help="Input port")
parser.add_argument("--output_port", type=int, default=5557, help="Output port")
parser.add_argument("--settings_port", type=int, default=5556, help="Settings port")
args = parser.parse_args()

context = zmq.Context()
img_subscriber = context.socket(zmq.SUB)
img_subscriber.connect(f"tcp://localhost:{args.input_port}")
img_subscriber.setsockopt(zmq.SUBSCRIBE, b"")

img_publisher = context.socket(zmq.PUB)
img_publisher.bind(f"tcp://*:{args.output_port}")

settings = SettingsSubscriber(args.settings_port)

jpeg = TurboJPEG()

class Transform:
    def __init__(self):
        self.should_exit = False
        self.thread = threading.Thread(target=self.run)
        self.thread.start()
            
    def step(self):
        start_time = time.time()
        
        msg = img_subscriber.recv()
        dropped_count = 0
        while True:
            try:
                msg = img_subscriber.recv(flags=zmq.NOBLOCK)
                dropped_count += 1
            except zmq.Again:
                break
        receiving_duration = time.time() - start_time
            
        if dropped_count > 0:
            print("Dropped messages:", dropped_count)
        
        using_json = True
        try:
            data = json.loads(msg)
            jpg_b64 = data['data']
            jpg_buffer = base64.b64decode(jpg_b64)
        except Exception as e:
            jpg_buffer = msg
            using_json = False
            
        img = jpeg.decode(jpg_buffer, pixel_format=TJPF_RGB)
        
        h, w, _ = img.shape
        size = settings["size"]
        input_image = cv2.resize(img, (size, int(size * h / w)), interpolation=cv2.INTER_CUBIC)

        diffusion_start_time = time.time()
        if settings["fixed_seed"]:
            self.generator = torch.manual_seed(settings["seed"])
            
        results = pipe(
            prompt=settings["prompt"],
            image=input_image / 255,
            generator=self.generator,
            num_inference_steps=settings["num_inference_steps"],
            guidance_scale=settings["guidance_scale"],
            strength=settings["strength"],
            output_type="np",
        )
        diffusion_duration = time.time() - diffusion_start_time
        
        output_image = results.images[0] * 255
    
        img_u8 = output_image.astype(np.uint8)
        jpg_buffer = jpeg.encode(img_u8, pixel_format=TJPF_RGB)
        if using_json:
            index = str(data["index"]).encode('ascii')
            timestamp = str(data["timestamp"]).encode('ascii')
            jpg_b64 = base64.b64encode(jpg_buffer)
            msg = b'{"timestamp":'+timestamp+b',"index":' + index + b',"data":"' + jpg_b64 + b'"}'
        else:
            msg = jpg_buffer
        img_publisher.send(msg)
        
        # time.sleep(0.5)
        
        duration = time.time() - start_time
        overhead = duration - diffusion_duration - receiving_duration
        print(f"Diffusion {int(diffusion_duration*1000)}ms + Overhead {int(overhead*1000)}ms + Receiving {int(receiving_duration*1000)}ms = {int(duration*1000)}ms")

    def run(self):
        try:
            self.generator = torch.manual_seed(settings["seed"])
            while not self.should_exit:
                self.step()
        except KeyboardInterrupt:
            pass
            
    def close(self):
        self.should_exit = True
        self.thread.join()
            
    
transform = Transform()
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    print("closing transform")
    transform.close()
    print("closing settings")
    settings.close()
    print("closing img_subscriber")
    img_subscriber.close()
    print("closing img_publisher")
    img_publisher.close()
    print("closing zmq_context")
    context.term()