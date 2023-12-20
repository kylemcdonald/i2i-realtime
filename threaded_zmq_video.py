import zmq
import msgpack
from threaded_worker import ThreadedWorker

class ThreadedZmqVideo(ThreadedWorker):
    def __init__(self, settings):
        super().__init__(has_input=False)
        self.context = zmq.Context()
        self.sock = self.context.socket(zmq.SUB)
        self.sock.setsockopt(zmq.RCVTIMEO, 100)
        self.sock.setsockopt(zmq.RCVHWM, 1)
        self.sock.setsockopt(zmq.LINGER, 0)
        address = f"tcp://10.0.0.24:{settings.zmq_video_port}"
        print(self.name, "binding to", address)
        self.sock.connect(address)
        self.sock.setsockopt(zmq.SUBSCRIBE, b"")
        
    def work(self):
        while not self.should_exit:
            try:
                msg = self.sock.recv(flags=zmq.NOBLOCK, copy=False).bytes
            except zmq.Again:
                continue
            timestamp, index, encoded = msgpack.unpackb(msg)
            # print(self.name, "zmq received", index)
            return timestamp, index, encoded
        
    def cleanup(self):
        self.sock.close()
        self.context.term()