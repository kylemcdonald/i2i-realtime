import multiprocessing
import threading
import queue


class ThreadedWorker:
    def __init__(self, has_input=True, has_output=True, mode="thread"):
        if mode == "thread":
            self.ParallelClass = threading.Thread
            self.QueueClass = queue.Queue
        elif mode == "process":
            self.ParallelClass = multiprocessing.Process
            self.QueueClass = multiprocessing.Queue
        if has_input:
            self.input_queue = self.QueueClass()
        if has_output:
            self.output_queue = self.QueueClass()
        self.should_exit = False
        self.parallel = self.ParallelClass(target=self.run)
        self.name = self.__class__.__name__

    def set_name(self, name):
        self.name = name
        return self

    def feed(self, feeder):
        print(self.name, "feeding with", feeder.name)
        self.input_queue = feeder.output_queue
        return self

    def start(self):
        if self.parallel.is_alive():
            return self
        print(self.name, "starting")
        self.parallel.start()
        return self

    # called after the parallel is started
    def setup(self):
        pass
    
    def clear_input(self):
        with self.input_queue.mutex:
            self.input_queue.queue.clear()

    # called before the parallel is joined
    def cleanup(self):
        pass

    def run(self):
        print(self.name, "running")
        self.setup()
        try:
            while not self.should_exit:
                if hasattr(self, "input_queue"):
                    try:
                        input = self.input_queue.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    if input is None:
                        break
                    result = self.work(input)
                else:
                    result = self.work()
                if result is not None and hasattr(self, "output_queue"):
                    self.output_queue.put(result)
        except KeyboardInterrupt:
            print(self.name, "interrupted")
        self.cleanup()

    def close(self):
        print(self.name, "closing")
        self.should_exit = True
        if hasattr(self, "input_queue"):
            self.input_queue.put(None)
        if self.parallel.is_alive():
            self.parallel.join()
