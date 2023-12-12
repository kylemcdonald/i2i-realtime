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
        self.name = "ThreadedWorker"

    def feed(self, feeder):
        print(self.name, "feeding with", feeder.name)
        self.input_queue = feeder.output_queue
        return self

    def start(self):
        print(self.name, "starting")
        self.thread.start()
        return self

    def run(self):
        print(self.name, "running")
        try:
            while not self.should_exit:
                if hasattr(self, "input_queue"):
                    # print(self.name, "waiting for input")
                    input = self.input_queue.get()
                    # print(self.name, "got input")
                    if input is None:
                        break
                    result = self.work(input)
                else:
                    result = self.work()
                if hasattr(self, "output_queue"):
                    # print(self.name, "adding to output_queue")
                    self.output_queue.put(result)
                    
        except KeyboardInterrupt:
            print(self.name, "interrupted")

    def close(self):
        print(self.name, "closing")
        self.should_exit = True
        if hasattr(self, "input_queue"):
            self.input_queue.put(None)
        self.thread.join()
