import time
import msgpack
import zmq
from threaded_worker import ThreadedWorker


class ZmqSender(ThreadedWorker):
    def __init__(self, settings):
        super().__init__(has_output=False)
        self.context = zmq.Context()
        self.sock = self.context.socket(zmq.PUSH)
        self.sock.setsockopt(zmq.SNDHWM, 1)
        self.sock.setsockopt(zmq.LINGER, 0)
        self.sock.bind(f"tcp://0.0.0.0:{settings.job_start_port}")
        self.settings = settings

    def work(self, batch):
        frame_timestamps, indices, frames = zip(*batch)
        settings = self.settings
        job_timestamp = time.time()
        packed = msgpack.packb(
            {
                "job_timestamp": job_timestamp,
                "indices": indices,
                "frames": frames,
                "parameters": {
                    "prompt": settings.prompt,
                    "num_inference_steps": settings.num_inference_steps,
                    "strength": settings.strength,
                    "seed": settings.seed,
                    "passthrough": settings.passthrough,
                    "fixed_seed": settings.fixed_seed,
                },
            }
        )
        frame = zmq.Frame(packed)
        self.sock.send(frame, copy=False)
        print(int(time.time()*1000)%1000, "sending")
        # print("outgoing length", len(packed))
        # print("sending", indices)

    def cleanup(self):
        self.sock.close()
        self.context.term()
