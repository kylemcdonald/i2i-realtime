import time
import msgpack
import zmq
from threaded_worker import ThreadedWorker

class ZmqSender(ThreadedWorker):
    def __init__(self, settings, port):
        super().__init__(has_output=False)
        self.context = zmq.Context()
        self.publisher = self.context.socket(zmq.PUSH)
        self.publisher.bind(f"tcp://0.0.0.0:{port}")
        self.settings = settings

    def work(self, batch):
        timestamps, indices, frames = zip(*batch)
        packed = msgpack.packb(
            {
                "timestamps": timestamps,
                "indices": indices,
                "frames": frames,
                "settings": self.settings.settings,
            }
        )
        self.publisher.send(packed)
        print(indices, end="\r")

    def cleanup(self):
        self.publisher.close()
        self.context.term()