import threading
import queue
import time

class ThreadedProducer:
    def __init__(self):
        self.output_queue = queue.Queue()
        self.should_exit = False
        self.thread = threading.Thread(target=self.run)
    
    def start(self):
        self.thread.start()
        return self
    
    def produce():
        pass
        
    def run(self):
        while not self.should_exit:
            self.output_queue.put(self.produce())
            
    def cleanup(self):
        pass
            
    def close(self):
        self.should_exit = True
        # this will not exit if the producer is blocked
        self.thread.join()
        self.cleanup()