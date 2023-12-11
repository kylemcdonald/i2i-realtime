from threaded_producer import ThreadedProducer
import zmq


class BatchingSubscriber(ThreadedProducer):
    def __init__(self, hostname, port, batch_size=4):
        super().__init__()
        self.context = zmq.Context()
        self.sub = self.context.socket(zmq.PULL)
        self.sub.connect(f"tcp://{hostname}:{port}")
        self.batch_size = batch_size
        self.batch = []

    def produce(self):
        while len(self.batch) < self.batch_size:
            self.batch.append(self.receive())
        batch = self.batch
        self.batch = []
        return batch

    def receive(self):
        msg = self.sub.recv()
        ignored_count = 0
        while True:
            try:
                msg = self.sub.recv(flags=zmq.NOBLOCK)
                ignored_count += 1
            except zmq.Again:
                break
        if ignored_count > 0:
            print("Ignored messages:", ignored_count)
        return msg

    def cleanup(self):
        self.sub.close()
        self.context.term()
