from settings import Settings

settings = Settings()

print(f"Starting worker #{settings.worker_id}")

import os
import psutil
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

disable_progress_bar()
pipe = AutoPipelineForImage2Image.from_pretrained(
    base_model,
    torch_dtype=torch.float16,
    variant="fp16",
    local_files_only=settings.local_files_only,
)

pipe.vae = AutoencoderTiny.from_pretrained(
    vae_model, torch_dtype=torch.float16, local_files_only=settings.local_files_only
)
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


class WorkerReceiver(ThreadedWorker):
    def __init__(self, hostname, port):
        super().__init__(has_input=False)
        self.context = zmq.Context()
        self.pull = self.context.socket(zmq.PULL)
        address = f"tcp://{hostname}:{port}"
        print(f"WorkerReceiver connecting to {address}")
        self.pull.connect(address)
        self.jpeg = TurboJPEG()

    def work(self):
        while not self.should_exit:
            try:
                msg = self.pull.recv(flags=zmq.NOBLOCK)
                receive_time = time.time()
            except zmq.ZMQError:
                time.sleep(0.1)
                continue
            unpacked = msgpack.unpackb(msg)
            print("incoming length", len(msg))
            unpacked["timings"] = []
            unpacked["timings"].append(("receive_start_time", receive_time))
            # print("receiving", unpacked["indices"])
            
            # oldest_timestamp = min(unpacked["timestamps"])
            # latency = time.time() - oldest_timestamp
            # if latency > 0.5:
                # print(f"{int(latency)}ms dropping old frames")
                # continue
            # print(f"{int(latency)}ms received {unpacked['indices']}")
            
            parameters = unpacked["parameters"]
            images = []
            for frame in unpacked["frames"]:
                img = self.jpeg.decode(frame, pixel_format=TJPF_RGB)
                images.append(img / 255)
            unpacked["timings"].append(("receiver_unpack_decode", time.time()))
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

    def diffusion(self, images, parameters):
        return pipe(
            prompt=[parameters["prompt"]] * len(images),
            image=images,
            generator=self.generator,
            num_inference_steps=parameters["num_inference_steps"],
            guidance_scale=0,
            strength=parameters["strength"],
            output_type="np",
        ).images

    def work(self, unpacked):
        start_time = time.time()
        unpacked["timings"].append(("processor_start_time", start_time))

        images = unpacked["frames"]
        parameters = unpacked["parameters"]

        if parameters["passthrough"]:
            results = images
        else:
            if parameters["fixed_seed"] or self.generator is None:
                self.generator = torch.manual_seed(parameters["seed"])
            results = self.diffusion(images, parameters)
            unpacked["timings"].append(("processor_diffusion", time.time()))

        unpacked["frames"] = results
        unpacked["worker_id"] = settings.worker_id

        if self.batch_count % 10 == 0:
            latency = time.time() - unpacked["job_timestamp"]
            duration = time.time() - start_time
            print(
                f"Diffusion {int(duration*1000)}ms Latency {int(latency*1000)}ms",
                flush=True,
            )
        self.batch_count += 1
        
        return unpacked


class WorkerSender(ThreadedWorker):
    def __init__(self, hostname, port):
        super().__init__(has_output=False)
        self.context = zmq.Context()
        self.push = self.context.socket(zmq.PUSH)
        address = f"tcp://{hostname}:{port}"
        print(f"WorkerSender connecting to {address}")
        self.push.connect(address)
        self.jpeg = TurboJPEG()

    def work(self, unpacked):
        unpacked["timings"].append(("sender_start_time", time.time()))

        indices = unpacked["indices"]
        results = unpacked["frames"]
        job_timestamp = unpacked["job_timestamp"]
        worker_id = unpacked["worker_id"]

        msgs = []
        for index, result in zip(indices, results):
            img_u8 = (result * 255).astype(np.uint8)
            jpg = self.jpeg.encode(img_u8, pixel_format=TJPF_RGB)
            msg = msgpack.packb(
                {
                    "job_timestamp": job_timestamp,
                    "index": index,
                    "jpg": jpg,
                    "worker_id": worker_id,
                }
            )
            msgs.append(msg)
        unpacked["timings"].append(("sender_msgpack_encode", time.time()))
            
        for index, msg in zip(indices, msgs):
            self.push.send(msg)
            print("sending", index)
            
        previous = unpacked["job_timestamp"]
        for k,v in unpacked["timings"]:
            duration = v - previous
            print(f"{k}: {int(duration*1000)}ms")
            previous = v

    def cleanup(self):
        print("WorkerSender push close")
        self.push.close()
        print("WorkerSender context term")
        self.context.term()


# create from beginning to end
receiver = WorkerReceiver(settings.primary_hostname, settings.job_start_port)
processor = Processor().feed(receiver)
sender = WorkerSender(settings.primary_hostname, settings.job_finish_port).feed(processor)

# warmup
if settings.warmup:
    warmup_shape = [settings.batch_size, *map(int, settings.warmup.split("x"))]
    shape_str = "x".join(map(str, warmup_shape))
    images = np.zeros(warmup_shape, dtype=np.float32)
    for i in range(2):
        print(f"Warmup {shape_str} {i+1}/2")
        start_time = time.time()
        processor.diffusion(
            images, {"prompt": "warmup", "num_inference_steps": 2, "strength": 1.0}
        )
    print("Warmup finished", flush=True)

# start from end to beginning
sender.start()
processor.start()
receiver.start()

try:
    process = psutil.Process(os.getpid())
    while True:
        memory_usage_bytes = process.memory_info().rss
        memory_usage_gb = memory_usage_bytes / (1024**3)
        if memory_usage_gb > 10:
            print(f"memory usage: {memory_usage_gb:.2f}GB")
        time.sleep(1)
except KeyboardInterrupt:
    pass

# close end to beginning
sender.close()
processor.close()
receiver.close()
