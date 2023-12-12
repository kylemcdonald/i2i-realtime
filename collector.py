import zmq
import msgpack
import time
from queue import Queue
import threading

context = zmq.Context()
receiver = context.socket(zmq.PULL)
receiver.bind("tcp://0.0.0.0:5558")

publisher = context.socket(zmq.PUB)
publisher.bind(f"tcp://0.0.0.0:5557")

msg_buffer = {}
next_index = None


class RemoveJitter:
    def __init__(self, min_size=1, max_size=5, max_delay=200):
        self.max_delay = max_delay
        self.min_size = min_size
        self.max_size = max_size
        self.thread = threading.Thread(target=self.run)
        self.queue = Queue()
        self.running = False
        self.should_exit = False
        self.delay = 33
        self.jump = 1

    def start(self):
        if self.running:
            return
        self.thread.start()

    def feed(self, msg):
        self.queue.put(msg)

    def run(self):
        self.running = True
        while not self.should_exit:
            start_time = time.time()
            unpacked = self.queue.get()
            if unpacked is None:
                break

            timestamp = unpacked["timestamp"]
            index = unpacked["index"]
            worker_id = unpacked["worker_id"]
            jpg = unpacked["jpg"]

            latency = int(time.time() * 1000) - timestamp
            print("\033[K", end="", flush=True)  # clear entire line
            print(
                f"outgoing: {index} #{worker_id} {latency}ms, {self.queue.qsize()}q {self.delay}ms",
                end="\r",
            )

            packed = msgpack.packb([timestamp, index, jpg])

            publisher.send(packed)

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
        self.should_exit = True
        self.queue.put(None)
        self.thread.join()
        self.running = False


print("ready for messages")

remove_jitter = RemoveJitter()

try:
    while True:
        msg = receiver.recv()
        unpacked = msgpack.unpackb(msg)
        index = unpacked["index"]

        if next_index is None:
            next_index = index
        if index == 0:
            next_index = 0
        if index < next_index:
            print("dropping", index)
            continue

        timestamp = unpacked["timestamp"]
        index = unpacked["index"]
        worker_id = unpacked["worker_id"]
        jpg = unpacked["jpg"]

        latency = int(time.time() * 1000) - timestamp
        msg_buffer[index] = unpacked
        # print(f"incoming: {index} #{worker_id} {latency}ms")

        # packed = msgpack.packb([timestamp, index, jpg])
        # publisher.send(packed) # echo mode

        # ordered mode
        while next_index in msg_buffer:
            unpacked = msg_buffer[next_index]
            remove_jitter.feed(unpacked)
            remove_jitter.start()
            del msg_buffer[next_index]
            next_index += 1

except KeyboardInterrupt:
    pass
finally:
    print()
    print("stopping remove_jitter")
    remove_jitter.stop()
    print("closing receiver")
    receiver.close()
    print("closing publisher")
    publisher.close()
    print("term context")
    context.term()
