import argparse

parser = argparse.ArgumentParser()
parser.add_argument(
    "--primary_hostname", type=str, default="0.0.0.0", help="Hostname of primary server"
)
parser.add_argument("--input_port", type=int, default=5555, help="Input port")
parser.add_argument("--output_port", type=int, default=5558, help="Output port")
args = parser.parse_args()

import os
import dotenv

dotenv.load_dotenv()
worker_id = os.environ["WORKER_ID"]
print(f"Starting worker #{worker_id}")

import zmq
import msgpack
import numpy as np
import time
from turbojpeg import TurboJPEG, TJPF_RGB
from utils.imutil import imresize
import cv2

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

context = zmq.Context()
batch_subscriber = context.socket(zmq.PULL)
batch_subscriber.connect(f"tcp://{args.primary_hostname}:{args.input_port}")

img_publisher = context.socket(zmq.PUSH)
img_publisher.connect(f"tcp://{args.primary_hostname}:{args.output_port}")


def load_image(path, max_side):
    with open(path, "rb") as f:
        frame = f.read()
    img = jpeg.decode(frame, pixel_format=TJPF_RGB)
    
    # slower but higher quality
    # img = imresize(img, max_side=max_side)
    
    # faster
    width = max_side
    h,w = img.shape[:2]
    height = int(width * h / w)
    img = cv2.resize(img, (width, height), interpolation=cv2.INTER_AREA)
    
    return img


jpeg = TurboJPEG()

generator = None

try:
    while True:
        start_time = time.time()

        zmq_duration = 0
        zmq_start = time.time()
        msg = batch_subscriber.recv()
        zmq_duration += time.time() - zmq_start

        # ignored_count = 0
        # while True:
        #     try:
        #         msg = batch_subscriber.recv(flags=zmq.NOBLOCK)
        #         ignored_count += 1
        #     except zmq.Again:
        #         break
        # if ignored_count > 0:
        #     print("Ignored messages:", ignored_count)

        unpacked = msgpack.unpackb(msg)
        timestamp = unpacked["timestamp"]
        indices = unpacked["indices"]
        frames = unpacked["frames"]
        settings = unpacked["settings"]

        images = []
        for frame in frames:
            if isinstance(frame, str):
                img = load_image(frame, settings["resolution"])
            else:
                img = jpeg.decode(frame, pixel_format=TJPF_RGB)
                img = imresize(img, max_side=settings["resolution"])
            images.append(img / 255)

        diffusion_start_time = time.time()

        if settings["passthrough"]:
            results = images
        else:
            if settings["fixed_seed"] or generator is None:
                generator = torch.manual_seed(settings["seed"])
            results = pipe(
                prompt=[settings["prompt"]] * len(images),
                image=images,
                generator=generator,
                num_inference_steps=settings["num_inference_steps"],
                guidance_scale=settings["guidance_scale"],
                strength=settings["strength"],
                output_type="np",
            ).images
        diffusion_duration = time.time() - diffusion_start_time

        for index, result in zip(indices, results):
            img_u8 = (result * 255).astype(np.uint8)
            jpg = jpeg.encode(img_u8, pixel_format=TJPF_RGB)

            msg = msgpack.packb(
                {
                    "timestamp": timestamp,
                    "index": index,
                    "jpg": jpg,
                    "worker_id": worker_id,
                }
            )

            zmq_start = time.time()
            img_publisher.send(msg)
            zmq_duration += time.time() - zmq_start

        duration = time.time() - start_time
        overhead = duration - diffusion_duration - zmq_duration
        # print("\033[K", end="", flush=True)  # clear entire line
        print(
            f"Diffusion {int(diffusion_duration*1000)}ms + ZMQ {int(zmq_duration*1000)}ms Overhead {int(overhead*1000)}ms = {int(duration*1000)}ms",
            # end="\r",
        )
except KeyboardInterrupt:
    pass
finally:
    print("closing batch_subscriber")
    batch_subscriber.close()
    print("closing img_publisher")
    img_publisher.close()
    print("term context")
    context.term()
