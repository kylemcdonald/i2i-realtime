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


class Receiver(ThreadedWorker):
    def __init__(self, hostname, port):
        super().__init__(has_input=False)
        self.context = zmq.Context()
        self.pull = self.context.socket(zmq.PULL)
        self.pull.connect(f"tcp://{hostname}:{port}")
        self.jpeg = TurboJPEG()

    def load_image(self, path, max_side):
        with open(path, "rb") as f:
            frame = f.read()
        img = self.jpeg.decode(frame, pixel_format=TJPF_RGB)

        # slower but higher quality
        # img = imresize(img, max_side=max_side)

        # faster
        width = max_side
        h, w = img.shape[:2]
        height = int(width * h / w)
        img = cv2.resize(img, (width, height), interpolation=cv2.INTER_AREA)

        return img

    def work(self):
        while not self.should_exit:
            msg = self.pull.recv()
            unpacked = msgpack.unpackb(msg)
            latency = (time.time() * 1000) - unpacked["timestamp"]
            if latency > 0.1:
                # print(f"{int(latency)}ms dropping old frames")
                continue
            # print(f"{int(latency)}ms received {unpacked['indices']}")
            settings = unpacked["settings"]
            images = []
            for frame in unpacked["frames"]:
                if isinstance(frame, str):
                    img = self.load_image(frame, settings["resolution"])
                else:
                    img = self.jpeg.decode(frame, pixel_format=TJPF_RGB)
                    img = imresize(img, max_side=settings["resolution"])
                images.append(img / 255)
            unpacked["frames"] = images
            return unpacked

    def cleanup(self):
        self.pull.close()
        self.context.term()


class Processor(ThreadedWorker):
    def __init__(self):
        super().__init__()
        self.generator = None
        
    def work(self, unpacked):
        start_time = time.time()

        timestamp = unpacked["timestamp"]
        indices = unpacked["indices"]
        images = unpacked["frames"]
        settings = unpacked["settings"]

        if settings["passthrough"]:
            results = images
        else:
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
            ).images

        unpacked["frames"] = results
        unpacked["worker_id"] = worker_id

        duration = time.time() - start_time
        latency = time.time() - timestamp / 1000

        print(f"Diffusion {int(duration*1000)}ms Latency {int(latency*1000)}ms")

        return unpacked


class Sender(ThreadedWorker):
    def __init__(self, hostname, port):
        super().__init__(has_output=False)
        self.context = zmq.Context()
        self.push = self.context.socket(zmq.PUSH)
        self.push.connect(f"tcp://{hostname}:{port}")
        self.jpeg = TurboJPEG()

    def work(self, unpacked):
        indices = unpacked["indices"]
        results = unpacked["frames"]
        timestamp = unpacked["timestamp"]
        worker_id = unpacked["worker_id"]

        for index, result in zip(indices, results):
            img_u8 = (result * 255).astype(np.uint8)
            jpg = self.jpeg.encode(img_u8, pixel_format=TJPF_RGB)

            msg = msgpack.packb(
                {
                    "timestamp": timestamp,
                    "index": index,
                    "jpg": jpg,
                    "worker_id": worker_id,
                }
            )

            self.push.send(msg)

    def cleanup(self):
        self.push.close()
        self.context.close()


# create from beginning to end
receiver = Receiver(args.primary_hostname, args.input_port)
processor = Processor().feed(receiver)
sender = Sender(args.primary_hostname, args.output_port).feed(processor)

# start from end to beginning
sender.start()
processor.start()
receiver.start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass

# close end to beginning
print("closing sender")
sender.close()
print("closing processor")
processor.close()
print("closing receiver")
receiver.close()

# print("term context")
# context.term()
