import time
import zmq
import msgpack

from threaded_worker import ThreadedWorker
from threaded_camera import ThreadedCamera
        
class ZmqSender(ThreadedWorker):
    def __init__(self, host, port):
        super().__init__(has_output=False)
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.bind(f"tcp://{host}:{port}")
        
    def work(self, value):
        self.socket.send(msgpack.packb(value))
        
    def cleanup(self):
        self.socket.close()
        self.context.term()
        
video = ThreadedCamera()
sender = ZmqSender("0.0.0.0", "8000").feed(video)

sender.start()
video.start()


try:
    while True:
        time.sleep(1)
                
except KeyboardInterrupt:
    pass

sender.close()
video.close()