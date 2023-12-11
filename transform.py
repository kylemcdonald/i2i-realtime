import os
import dotenv
dotenv.load_dotenv()
worker_id = os.environ["WORKER_ID"]
print(f"Starting worker #{worker_id}")

import socket
import zmq
import msgpack
import cv2
import numpy as np
import argparse
import time
import threading
from turbojpeg import TurboJPEG, TJPF_RGB

from sfast.compilers.stable_diffusion_pipeline_compiler import (
    compile,
    CompilationConfig,
)

from diffusers import AutoPipelineForImage2Image, AutoencoderTiny
import torch
import warnings

warnings.filterwarnings("ignore", category=torch.jit.TracerWarning)

from PIL import Image

from fixed_seed import fix_seed
from settings_subscriber import SettingsSubscriber
from batching_subscriber import BatchingSubscriber
from threaded_worker import ThreadedWorker

xl = True
if xl:
    base_model = "stabilityai/sdxl-turbo"
    vae_model = "madebyollin/taesdxl"
else:
    base_model = "stabilityai/sd-turbo"
    vae_model = "madebyollin/taesd"

pipe = AutoPipelineForImage2Image.from_pretrained(
    base_model,
    torch_dtype=torch.float16,
    variant="fp16",
)

pipe.vae = AutoencoderTiny.from_pretrained(vae_model, torch_dtype=torch.float16)

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
parser.add_argument("--primary_hostname", type=str, default="0.0.0.0", help="Hostname of primary server")
parser.add_argument("--batch_size", type=int, default=1, help="Batch size")
parser.add_argument("--input_port", type=int, default=5555, help="Input port")
parser.add_argument("--output_port", type=int, default=5558, help="Output port")
parser.add_argument("--settings_port", type=int, default=5556, help="Settings port")
args = parser.parse_args()

context = zmq.Context()
img_publisher = context.socket(zmq.PUSH)
img_publisher.connect(f"tcp://{args.primary_hostname}:{args.output_port}")

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

            images.append(img / 255)

        diffusion_start_time = time.time()
        if settings["fixed_seed"] or self.generator is None:
            self.generator = torch.manual_seed(settings["seed"])

        results = pipe(
            prompt=[settings["prompt"]] * len(images),
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

            msg = msgpack.packb([timestamp, index, jpg, worker_id])

            zmq_start = time.time()
            img_publisher.send(msg)
            zmq_duration += time.time() - zmq_start

        duration = time.time() - start_time
        overhead = duration - diffusion_duration - jpg_duration
        print(
            f"Diffusion {int(diffusion_duration*1000)}ms + ZMQ {int(zmq_duration*1000)}ms + JPG {int(jpg_duration*1000)}ms + Overhead {int(overhead*1000)}ms = {int(duration*1000)}ms",
            end="\r",
        )


image_generator = BatchingSubscriber(args.primary_hostname, args.input_port, batch_size=args.batch_size)
batch_transformer = BatchTransformer()

batch_transformer.feed(image_generator)

batch_transformer.start()
image_generator.start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    print("closing batch_transformer")
    batch_transformer.close()
    print("closing image_generator")
    image_generator.close()
    print("closing settings")
    settings.close()
    print("closing img_publisher")
    img_publisher.close()
    print("closing zmq_context")
    context.term()
