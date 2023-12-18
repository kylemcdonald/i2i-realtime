from threaded_worker import ThreadedWorker
import msgpack
import time
import zmq

class ReorderingReceiver(ThreadedWorker):
    def __init__(self, sender, port):
        super().__init__(has_input=False, has_output=False)
        self.context = zmq.Context()
        self.sock = self.context.socket(zmq.PULL)
        self.sock.setsockopt(zmq.RCVHWM, 1)
        self.sock.setsockopt(zmq.LINGER, 0)
        self.sock.bind(f"tcp://0.0.0.0:{port}")
        self.sender = sender
        self.reset_buffer()
        
    def reset_buffer(self):
        self.msg_buffer = {}
        self.next_index = None
        
    def work(self):
        try:
            msg = self.sock.recv(flags=zmq.NOBLOCK, copy=False).bytes
            receive_time = time.time()
        except zmq.ZMQError:
            time.sleep(0.1)
            return
        unpacked = msgpack.unpackb(msg)
        
        full_round_trip = receive_time - unpacked["job_timestamp"]
        print(f"full_round_trip: {int(1000*full_round_trip)}ms")
        
        index = unpacked["index"]
        if index == 0:
            self.reset_buffer()
        self.msg_buffer[index] = unpacked  # start by adding to buffer

        # drop all old messages to avoid memory leak
        cur_time = time.time()
        for key in list(self.msg_buffer.keys()):
            timestamp = unpacked["job_timestamp"]
            latency = cur_time - timestamp
            if latency > 1:
                print(f"dropping {key} latency: {int(1000*latency)}ms")
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
            self.sender.queue.put(unpacked)
            self.sender.start()
            del self.msg_buffer[self.next_index]
            self.next_index += 1
        
    def cleanup(self):
        self.sock.close()
        self.context.term()