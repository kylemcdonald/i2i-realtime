from threaded_worker import ThreadedWorker

class BatchingWorker(ThreadedWorker):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        
    def setup(self):
        self.batch = []
        
    def work(self, input):
        self.batch.append(input)
        n = self.settings.batch_size
        if len(self.batch) >= n:
            batch = self.batch[:n]
            self.batch = self.batch[n:]
            return batch