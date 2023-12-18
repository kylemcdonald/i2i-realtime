import msgpack
import zmq
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
        job_timestamp = unpacked["job_timestamp"]
        index = unpacked["index"]
        jpg = unpacked["jpg"]
        packed = msgpack.packb([job_timestamp, index, jpg])
        self.sock.send(packed)

    def cleanup(self):
        self.sock.close()
        self.context.term()
