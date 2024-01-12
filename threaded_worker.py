import multiprocessing
import threading
import queue
import time


class ThreadedWorker:
    def __init__(self, has_input=True, has_output=True, mode="thread", debug=False):
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
        
        self.debug = debug
        self.last_print = time.time()
        self.print_interval = 1
        self.durations = []

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
                
                cur_time = time.time()
                if hasattr(self, "input_queue"):
                    try:
                        input = self.input_queue.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    if input is None:
                        break
                    start_time = time.time()
                    result = self.work(input)
                else:
                    start_time = time.time()
                    result = self.work()
                duration = time.time() - start_time
                
                if result is not None and hasattr(self, "output_queue"):
                    self.output_queue.put(result)
                    
                self.durations.append(duration)
                if len(self.durations) > 10:
                    self.durations.pop(0)
                    
                time_since_print = cur_time - self.last_print
                if self.debug and time_since_print > self.print_interval:
                    duration = sum(self.durations) / len(self.durations)
                    print(self.name, f"{duration*1000:.2f}ms", flush=True)
                    self.last_print = cur_time
                
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
