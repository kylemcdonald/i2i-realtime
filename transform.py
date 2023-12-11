import zmq
import msgpack
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

from fixed_seed import fix_seed
from settings_subscriber import SettingsSubscriber
from batching_subscriber import BatchingSubscriber
from threaded_worker import ThreadedWorker

pipe = AutoPipelineForImage2Image.from_pretrained(
    "stabilityai/sdxl-turbo",
    torch_dtype=torch.float16,
    variant="fp16",
)

pipe.vae = AutoencoderTiny.from_pretrained(
    "madebyollin/taesdxl",
    torch_dtype=torch.float16)

pipe.set_progress_bar_config(disable=True)

fix_seed(pipe)

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
img_publisher = context.socket(zmq.PUB)
img_publisher.bind(f"tcp://*:{args.output_port}")

settings = SettingsSubscriber(args.settings_port)

jpeg = TurboJPEG()

class BatchTransformer(ThreadedWorker):
    def __init__(self):
        super().__init__()
        self.generator = None
            
    def process(self, batch):
        start_time = time.time()
        
        images = []
        jpg_duration = 0
        zmq_duration = 0
        timestamps = []
        indices = []
        for msg in batch:
            timestamp, index, jpg = msgpack.unpackb(msg)
            timestamps.append(timestamp)
            indices.append(index)
            
            jpg_start = time.time()
            img = jpeg.decode(jpg, pixel_format=TJPF_RGB)
            jpg_duration += time.time() - jpg_start
            
            # we should not take responsibility for resizing
            # h, w, _ = img.shape
            # size = settings["size"]
            # img = cv2.resize(img, (size, int(size * h / w)), interpolation=cv2.INTER_CUBIC)
            
            images.append(img / 255)

        diffusion_start_time = time.time()
        if settings["fixed_seed"] or self.generator is None:
            self.generator = torch.manual_seed(settings["seed"])
            
        results = pipe(
            prompt=[settings["prompt"]]*len(images),
            image=images,
            generator=self.generator,
            num_inference_steps=settings["num_inference_steps"],
            guidance_scale=settings["guidance_scale"],
            strength=settings["strength"],
            output_type="np",
        )
        diffusion_duration = time.time() - diffusion_start_time
        
        for timestamp, index, result in zip(timestamps, indices, results.images):
            img_u8 = (result * 255).astype(np.uint8)
            jpg_start = time.time()
            jpg = jpeg.encode(img_u8, pixel_format=TJPF_RGB)
            jpg_duration += time.time() - jpg_start
            
            msg = msgpack.packb([timestamp, index, jpg]) 
                
            zmq_start = time.time()
            img_publisher.send(msg)
            zmq_duration += time.time() - zmq_start
        
        # time.sleep(0.5)
        
        duration = time.time() - start_time
        overhead = duration - diffusion_duration - jpg_duration
        print(f"Diffusion {int(diffusion_duration*1000)}ms + ZMQ {int(zmq_duration*1000)}ms + JPG {int(jpg_duration*1000)}ms + Overhead {int(overhead*1000)}ms = {int(duration*1000)}ms")
        
batching_subscriber = BatchingSubscriber(args.input_port, batch_size=4)
batch_transformer = BatchTransformer()

batch_transformer.feed(batching_subscriber)

batch_transformer.start()
batching_subscriber.start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    print("closing batch_transformer")
    batch_transformer.close()
    print("closing batching_subscriber")
    batching_subscriber.close()
    print("closing settings")
    settings.close()
    print("closing img_publisher")
    img_publisher.close()
    print("closing zmq_context")
    context.term()