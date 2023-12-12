import threading
import queue


class ThreadedWorker:
    def __init__(self):
        self.input_queue = queue.Queue()
        self.output_queue = queue.Queue()
        self.should_exit = False
        self.thread = threading.Thread(target=self.run)

    def feed(self, feeder):
        self.input_queue = feeder.output_queue
        return self

    def start(self):
        self.thread.start()
        return self

    def process(self, value):
        return value

    def run(self):
        try:
            while not self.should_exit:
                input = self.input_queue.get()
                if input is None:
                    break
                self.output_queue.put(self.process(input))
        except KeyboardInterrupt:
            print("ThreadedWorker interrupted")

    def close(self):
        self.should_exit = True
        self.input_queue.put(None)
        self.thread.join()
