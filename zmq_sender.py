import time
import msgpack
import zmq
from threaded_worker import ThreadedWorker


class ZmqSender(ThreadedWorker):
    def __init__(self, settings):
        super().__init__(has_output=False)
        self.context = zmq.Context()
        self.publisher = self.context.socket(zmq.PUSH)
        self.publisher.bind(f"tcp://0.0.0.0:{settings.job_start_port}")
        self.settings = settings

    def work(self, batch):
        timestamps, indices, frames = zip(*batch)
        settings = self.settings
        packed = msgpack.packb(
            {
                "timestamps": timestamps,
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
        self.publisher.send(packed)
        print("sending", indices)

    def cleanup(self):
        self.publisher.close()
        self.context.term()
