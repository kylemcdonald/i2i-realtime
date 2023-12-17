import os
import dotenv

dotenv.load_dotenv()

worker_id = os.environ["WORKER_ID"]
print(f"Starting worker #{worker_id}")

import argparse

parser = argparse.ArgumentParser()
parser.add_argument(
    "--primary_hostname", type=str, default="0.0.0.0", help="Hostname of primary server"
)
parser.add_argument("--input_port", type=int, default=5555, help="Input port")
parser.add_argument("--warmup", type=str, help="Warmup batch size and resolution e.g. 4x576x1024x3")
parser.add_argument("--output_port", type=int, default=5558, help="Output port")
args = parser.parse_args()

try:
    args.primary_hostname = os.environ["PRIMARY_HOSTNAME"]
except KeyError:
    pass

try:
    args.warmup = os.environ["WARMUP"]
except KeyError:
    pass


import zmq
import msgpack
import numpy as np
import time
from turbojpeg import TurboJPEG, TJPF_RGB
from utils.imutil import imresize

from sfast.compilers.stable_diffusion_pipeline_compiler import (
    compile,
    CompilationConfig,
)

from diffusers.utils.logging import disable_progress_bar
from diffusers import AutoPipelineForImage2Image, AutoencoderTiny
import torch
import warnings

warnings.filterwarnings("ignore", category=torch.jit.TracerWarning)

from PIL import Image

from fixed_seed import fix_seed
from threaded_worker import ThreadedWorker

base_model = "stabilityai/sdxl-turbo"
vae_model = "madebyollin/taesdxl"

local_files_only = os.environ["LOCAL_FILES_ONLY"] == "TRUE"

disable_progress_bar()
pipe = AutoPipelineForImage2Image.from_pretrained(
    base_model,
    torch_dtype=torch.float16,
    variant="fp16",
    local_files_only=local_files_only
)

pipe.vae = AutoencoderTiny.from_pretrained(
    vae_model,
    torch_dtype=torch.float16,
    local_files_only=local_files_only)
fix_seed(pipe)

print("Model loaded")

config = CompilationConfig.Default()
config.enable_xformers = True
config.enable_triton = True
config.enable_cuda_graph = True
pipe = compile(pipe, config=config)

print("Model compiled")

pipe.to(device="cuda", dtype=torch.float16).to("cuda")
pipe.set_progress_bar_config(disable=True)

print("Model moved to GPU", flush=True)

class Receiver(ThreadedWorker):
    def __init__(self, hostname, port):
        super().__init__(has_input=False)
        self.context = zmq.Context()
        self.pull = self.context.socket(zmq.PULL)
        address = f"tcp://{hostname}:{port}"
        print(f"Receiver connecting to {address}")
        self.pull.connect(address) 
        self.jpeg = TurboJPEG()

    def work(self):
        while not self.should_exit:
            try:
                msg = self.pull.recv(flags=zmq.NOBLOCK)
            except zmq.ZMQError:
                time.sleep(0.1)
                continue
            unpacked = msgpack.unpackb(msg)
            oldest_timestamp = min(unpacked["timestamps"])
            latency = time.time() - oldest_timestamp
            if latency > 0.5:
                # print(f"{int(latency)}ms dropping old frames")
                continue
            # print(f"{int(latency)}ms received {unpacked['indices']}")
            settings = unpacked["settings"]
            images = []
            for frame in unpacked["frames"]:
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
        self.batch_count = 0
        
    def diffusion(self, images, settings):
        return pipe(
                prompt=[settings["prompt"]] * len(images),
                image=images,
                generator=self.generator,
                num_inference_steps=settings["num_inference_steps"],
                guidance_scale=settings["guidance_scale"],
                strength=settings["strength"],
                output_type="np",
            ).images
        
    def work(self, unpacked):
        start_time = time.time()

        images = unpacked["frames"]
        settings = unpacked["settings"]

        if settings["passthrough"]:
            results = images
        else:
            if settings["fixed_seed"] or self.generator is None:
                self.generator = torch.manual_seed(settings["seed"])
            results = self.diffusion(images, settings)

        unpacked["frames"] = results
        unpacked["worker_id"] = worker_id

        if self.batch_count % 10 == 0:
            latency = time.time() - min(unpacked["timestamps"])
            duration = time.time() - start_time
            print(f"Diffusion {int(duration*1000)}ms Latency {int(latency*1000)}ms", flush=True)
        self.batch_count += 1

        return unpacked


class Sender(ThreadedWorker):
    def __init__(self, hostname, port):
        super().__init__(has_output=False)
        self.context = zmq.Context()
        self.push = self.context.socket(zmq.PUSH)
        address = f"tcp://{hostname}:{port}"
        print(f"Sender connecting to {address}")
        self.push.connect(address)
        self.jpeg = TurboJPEG()

    def work(self, unpacked):
        indices = unpacked["indices"]
        results = unpacked["frames"]
        timestamps = unpacked["timestamps"]
        worker_id = unpacked["worker_id"]

        for index, timestamp, result in zip(indices, timestamps, results):
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
        self.context.term()


# create from beginning to end
receiver = Receiver(args.primary_hostname, args.input_port)
processor = Processor().feed(receiver)
sender = Sender(args.primary_hostname, args.output_port).feed(processor)

# warmup
if args.warmup:
    warmup_shape = tuple(map(int, args.warmup.split("x")))
    images = np.zeros(warmup_shape, dtype=np.float32)
    for i in range(2):
        print(f"Warmup {args.warmup} {i+1}/2")
        start_time = time.time()
        processor.diffusion(images, {"prompt": "warmup", "num_inference_steps": 2, "strength": 1.0, "guidance_scale": 0.0})
    print("Warmup finished", flush=True)

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
sender.close()
processor.close()
receiver.close()
