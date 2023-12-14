import threading
from queue import Queue
import time
import msgpack
import zmq

class RemoveJitter:
    def __init__(self, port, min_size=1, max_size=5, max_delay=200):
        self.context = zmq.Context()
        self.publisher = self.context.socket(zmq.PUB)
        self.publisher.bind(f"tcp://0.0.0.0:{port}")
        self.max_delay = max_delay
        self.min_size = min_size
        self.max_size = max_size
        self.thread = threading.Thread(target=self.run)
        self.queue = Queue()
        self.should_exit = False
        self.delay = 33
        self.jump = 0.1

    def start(self):
        if self.thread.is_alive():
            return
        self.thread.start()

    def run(self):
        while not self.should_exit:
            start_time = time.time()
            unpacked = self.queue.get()
            if unpacked is None:
                break

            timestamp = unpacked["timestamp"]
            index = unpacked["index"]
            worker_id = unpacked["worker_id"]
            jpg = unpacked["jpg"]

            latency = time.time() - timestamp
            # print("\033[K", end="", flush=True)  # clear entire line
            # print(
            #     f"outgoing: {index} #{worker_id} {int(1000*latency)}ms, {self.queue.qsize()}q {self.delay:.01f}ms"
            # )

            packed = msgpack.packb([timestamp, index, jpg])

            self.publisher.send(packed)
            
            # doing this with smaller amounts for smaller offsets
            # would help staibilize the framerate
            if self.queue.qsize() > self.max_size:
                # need to speed up
                self.delay -= self.jump
            if self.queue.qsize() < self.min_size:
                # need to slow down
                self.delay += self.jump
            self.delay = max(0, self.delay)
            self.delay = min(self.max_delay, self.delay)

            next_time = start_time + (self.delay / 1000)
            wait_time = next_time - time.time()
            if wait_time > 0:
                time.sleep(wait_time)

    def stop(self):
        print("stopping RemoveJitter")
        self.should_exit = True
        self.queue.put(None)
        if self.thread.is_alive():
            self.thread.join()
        self.publisher.close()
        self.context.term()
