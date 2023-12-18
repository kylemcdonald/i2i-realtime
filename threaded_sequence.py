import time
import os
import threading
import queue
from natsort import natsorted
from threaded_worker import ThreadedWorker

class ThreadedSequence(ThreadedWorker):
    def __init__(self, settings):
        super().__init__(has_input=False)
        self.settings = settings
        self.fns = natsorted(os.listdir(settings.directory))
        self.playing = threading.Event()
        self.scrub_queue = queue.Queue()
        
    def setup(self):
        self.start_time = time.time()
        self.frame_number = 0
        
    def read_scrub(self):
        while not self.scrub_queue.empty():
            self.frame_number = self.scrub_queue.get()
            timestamp = self.frame_number / self.settings.fps
            self.start_time = time.time() - timestamp
        
    def work(self):
        self.playing.wait()
        if self.should_exit:
            return
        
        self.read_scrub()
        
        timestamp = time.time()
        
        index = self.frame_number
        
        next_frame_time = self.start_time + (index + 1) / self.settings.fps
        sleep_time = next_frame_time - time.time()
        if sleep_time > 0:
            time.sleep(sleep_time)
            
        fn = os.path.join(self.settings.directory, self.fns[index])
        with open(fn, "rb") as f:
            encoded = f.read()
            
        self.frame_number += 1
        if self.frame_number == len(self.fns):
            self.frame_number = 0
            self.start_time = time.time()
            
        return timestamp, index, encoded
    
    def close(self):
        self.should_exit = True
        self.playing.set()
        super().close()
    
    def play(self):
        print("playing")
        if self.playing.is_set():
            return
        self.read_scrub()
        self.scrub(self.frame_number / len(self.fns))
        self.playing.set()
        
    def pause(self):
        print("pausing")
        self.playing.clear()
        
    def scrub(self, pct):
        frame = int(pct * len(self.fns))
        self.scrub_queue.put(frame)