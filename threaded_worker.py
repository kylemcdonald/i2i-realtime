import threading
import queue


class ThreadedWorker:
    def __init__(self, has_input=True, has_output=True):
        if has_input:
            self.input_queue = queue.Queue()
        if has_output:
            self.output_queue = queue.Queue()
        self.should_exit = False
        self.thread = threading.Thread(target=self.run)

    def feed(self, feeder):
        self.input_queue = feeder.output_queue
        return self

    def start(self):
        self.thread.start()
        return self

    def run(self):
        try:
            while not self.should_exit:
                if hasattr(self, "input_queue"):
                    input = self.input_queue.get()
                    if input is None:
                        break
                    result = self.work(input)
                else:
                    result = self.work()
                if hasattr(self, "output_queue"):
                    self.output_queue.put(result)
                    
        except KeyboardInterrupt:
            print("ThreadedWorker interrupted")

    def close(self):
        self.should_exit = True
        if hasattr(self, "input_queue"):
            self.input_queue.put(None)
        self.thread.join()
