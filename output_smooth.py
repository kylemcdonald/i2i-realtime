import time
import msgpack
import zmq
from threaded_worker import ThreadedWorker

class OutputSmooth(ThreadedWorker):
    def __init__(self, port, min_size=1, max_size=5, max_delay=200):
        super().__init__(has_output=False)
        self.context = zmq.Context()
        self.sock = self.context.socket(zmq.PUB)
        self.sock.bind(f"tcp://0.0.0.0:{port}")
        self.sock.setsockopt(zmq.SNDHWM, 1)
        self.sock.setsockopt(zmq.LINGER, 0)
        self.max_delay = max_delay
        self.min_size = min_size
        self.max_size = max_size
        self.delay = 33
        self.jump = 0.1

    def work(self, unpacked):
        start_time = time.time()

        job_timestamp = unpacked["job_timestamp"]
        index = unpacked["index"]
        jpg = unpacked["jpg"]

        # worker_id = unpacked["worker_id"]
        # latency = time.time() - timestamp
        # print("\033[K", end="", flush=True)  # clear entire line
        # print(
        #     f"outgoing: {index} #{worker_id} {int(1000*latency)}ms, {self.queue.qsize()}q {self.delay:.01f}ms"
        # )

        packed = msgpack.packb([job_timestamp, index, jpg])

        self.sock.send(packed)
        
        # doing this with smaller amounts for smaller offsets
        # would help staibilize the framerate
        if self.input_queue.qsize() > self.max_size:
            # need to speed up
            self.delay -= self.jump
        if self.input_queue.qsize() < self.min_size:
            # need to slow down
            self.delay += self.jump
        self.delay = max(0, self.delay)
        self.delay = min(self.max_delay, self.delay)

        next_time = start_time + (self.delay / 1000)
        wait_time = next_time - time.time()
        if wait_time > 0:
            time.sleep(wait_time)

    def cleanup(self):
        self.sock.close()
        self.context.term()
