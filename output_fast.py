import msgpack
import zmq
import time
from threaded_worker import ThreadedWorker

class OutputFast(ThreadedWorker):
    def __init__(self, port):
        super().__init__(has_output=False)
        self.context = zmq.Context()
        self.sock = self.context.socket(zmq.PUB)
        self.sock.bind(f"tcp://0.0.0.0:{port}")
        self.sock.setsockopt(zmq.SNDHWM, 1)
        self.sock.setsockopt(zmq.LINGER, 0)

    def work(self, unpacked):
        timestamp = unpacked["frame_timestamp"]
        index = unpacked["index"]
        jpg = unpacked["jpg"]
        packed = msgpack.packb([timestamp, index, jpg])
        self.sock.send(packed)
        # duration = time.time() - unpacked["frame_timestamp"]
        # if index % 31 == 0:
        #     print(f"full loop {int(duration*1000)}ms", flush=True)

    def cleanup(self):
        self.sock.close()
        self.context.term()
