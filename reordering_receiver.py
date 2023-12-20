from threaded_worker import ThreadedWorker
import msgpack
import time
import zmq

class ReorderingReceiver(ThreadedWorker):
    def __init__(self, port):
        super().__init__(has_input=False)
        self.context = zmq.Context()
        self.sock = self.context.socket(zmq.PULL)
        self.sock.setsockopt(zmq.RCVTIMEO, 100)
        self.sock.setsockopt(zmq.RCVHWM, 1)
        self.sock.setsockopt(zmq.LINGER, 0)
        self.sock.bind(f"tcp://0.0.0.0:{port}")
        self.reset_buffer()
        
    def reset_buffer(self):
        self.msg_buffer = {}
        self.next_index = None
        
    def work(self):
        try:
            msg = self.sock.recv(flags=zmq.NOBLOCK, copy=False).bytes
            # print(int(time.time()*1000)%1000, "receiving")
        except zmq.Again:
            return
        
        receive_time = time.time()
        unpacked = msgpack.unpackb(msg)
        
        index = unpacked["index"]
        if index == 0:
            self.reset_buffer()
        self.msg_buffer[index] = unpacked  # start by adding to buffer

        if unpacked["index"] % 31 == 0: # close to 30, but prime (for logs)
            round_trip = receive_time - unpacked["job_timestamp"]
            worker_id = unpacked["worker_id"]
            print(f"worker {worker_id} round trip: {int(1000*round_trip)}ms")
        
        # drop all old messages to avoid memory leak
        recent_time = max([e["job_timestamp"] for e in self.msg_buffer.values()])
        for key in list(self.msg_buffer.keys()):
            timestamp = unpacked["job_timestamp"]
            latency = recent_time - timestamp
            if latency > 1:
                print(f"dropping {key} latency {int(1000*latency)}ms")
                del self.msg_buffer[key]
                continue
            
        if len(self.msg_buffer) > 100:
            print(f"reordering buffer size: {len(self.msg_buffer)}")

        index = unpacked["index"]
        worker_id = unpacked["worker_id"]
        jpg = unpacked["jpg"]

        if self.next_index is None:
            # if next_index is None, let's start with this one
            self.next_index = index

        diff = abs(index - self.next_index)
        if diff > 12:
            # if we got a big jump, let's just jump to it
            # this also works for resetting to 0
            self.next_index = index

        # msg_buffer[index] = unpacked
        # print(f"incoming: {index} #{worker_id} {latency}ms")

        # packed = msgpack.packb([timestamp, index, jpg])
        # publisher.send(packed) # echo mode

        # ordered mode
        while self.next_index in self.msg_buffer:
            unpacked = self.msg_buffer[self.next_index]
            self.output_queue.put(unpacked)
            del self.msg_buffer[self.next_index]
            self.next_index += 1
        
    def cleanup(self):
        self.sock.close()
        self.context.term()