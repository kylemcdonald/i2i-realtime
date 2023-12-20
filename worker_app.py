from settings import Settings

settings = Settings()

print(f"Starting worker #{settings.worker_id}")

import zmq
import msgpack
import numpy as np
import time
from turbojpeg import TurboJPEG, TJPF_RGB
from threaded_worker import ThreadedWorker
from diffusion_processor import DiffusionProcessor

class WorkerReceiver(ThreadedWorker):
    def __init__(self, hostname, port):
        super().__init__(has_input=False)
        self.context = zmq.Context()
        self.sock = self.context.socket(zmq.PULL)
        self.sock.setsockopt(zmq.RCVTIMEO, 100)
        self.sock.setsockopt(zmq.RCVHWM, 1)
        self.sock.setsockopt(zmq.LINGER, 0)
        address = f"tcp://{hostname}:{port}"
        print(f"WorkerReceiver connecting to {address}")
        self.sock.connect(address)
        self.jpeg = TurboJPEG()

    def work(self):
        while not self.should_exit:            
            try:
                msg = self.sock.recv(flags=zmq.NOBLOCK, copy=False).bytes
                receive_time = time.time()
                # print(int(time.time()*1000)%1000, "receiving")
            except zmq.Again:
                continue
            
            try:
                unpacked = msgpack.unpackb(msg)
                parameters = unpacked["parameters"]
                images = []
                for frame in unpacked["frames"]:
                    img = self.jpeg.decode(frame, pixel_format=TJPF_RGB)
                    images.append(img / 255)
                unpacked["frames"] = images
                return unpacked
            except OSError:
                continue

    def cleanup(self):
        self.sock.close()
        self.context.term()


class Processor(ThreadedWorker):
    def __init__(self, settings):
        super().__init__()
        self.generator = None
        self.batch_count = 0
        warmup = None
        if settings.warmup:
            warmup = f"{settings.batch_size}x{settings.warmup}"
        self.processor = DiffusionProcessor(warmup, settings.local_files_only)

    def work(self, unpacked):
        start_time = time.time()

        images = unpacked["frames"]
        parameters = unpacked["parameters"]

        if parameters["passthrough"]:
            results = images
        else:
            seed = None
            if parameters["fixed_seed"]:
                seed = parameters["seed"]
            try:
                results = self.processor.run(
                    images,
                    prompt=parameters["prompt"],
                    num_inference_steps=parameters["num_inference_steps"],
                    strength=parameters["strength"],
                    use_compel=parameters["use_compel"],
                    seed=seed
                )
            except:
                results = images

        unpacked["frames"] = results

        if self.batch_count % 10 == 0:
            latency = time.time() - unpacked["job_timestamp"]
            duration = time.time() - start_time
            print(
                f"diffusion {int(duration*1000)}ms latency {int(latency*1000)}ms",
                flush=True,
            )
        self.batch_count += 1
        
        return unpacked


class WorkerSender(ThreadedWorker):
    def __init__(self, hostname, port):
        super().__init__(has_output=False)
        self.context = zmq.Context()
        self.sock = self.context.socket(zmq.PUSH)
        self.sock.setsockopt(zmq.SNDHWM, 1)
        self.sock.setsockopt(zmq.LINGER, 0)
        address = f"tcp://{hostname}:{port}"
        print(f"WorkerSender connecting to {address}")
        self.sock.connect(address)
        self.jpeg = TurboJPEG()

    def work(self, unpacked):
        indices = unpacked["indices"]
        results = unpacked["frames"]
        job_timestamp = unpacked["job_timestamp"]
        frame_timestamps = unpacked["frame_timestamps"]

        msgs = []
        for index, frame_timestamp, result in zip(indices, frame_timestamps, results):
            img_u8 = (result * 255).astype(np.uint8)
            
            if unpacked["debug"]:
                x = index % img_u8.shape[1]
                img_u8[:, x, :] = 255
            
            jpg = self.jpeg.encode(img_u8, pixel_format=TJPF_RGB)
            msg = msgpack.packb(
                {
                    "job_timestamp": job_timestamp,
                    "frame_timestamp": frame_timestamp,
                    "index": index,
                    "jpg": jpg,
                    "worker_id": settings.worker_id,
                }
            )
            msgs.append(msg)
            
        for index, msg in zip(indices, msgs):
            self.sock.send(msg)
        
    def cleanup(self):
        print("WorkerSender push close")
        self.sock.close()
        print("WorkerSender context term")
        self.context.term()


# create from beginning to end
receiver = WorkerReceiver(settings.primary_hostname, settings.job_start_port)
processor = Processor(settings).feed(receiver)
sender = WorkerSender(settings.primary_hostname, settings.job_finish_port).feed(processor)

if settings.threaded:
    # start from end to beginning
    sender.start()
    processor.start()
    receiver.start()

try:
    while True:
        if not settings.threaded:
            sender.work(
                processor.work(
                    receiver.work()))
        else:
            time.sleep(1)
except KeyboardInterrupt:
    pass

# close end to beginning
if settings.threaded:
    sender.close()
    processor.close()
    receiver.close()
else:
    sender.cleanup()
    processor.cleanup()
    receiver.cleanup()