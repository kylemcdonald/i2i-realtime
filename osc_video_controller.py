from threaded_worker import ThreadedWorker
from osc_socket import OscSocket

class OscVideoController(ThreadedWorker):
    def __init__(self, video, host, port):
        super().__init__(has_input=False, has_output=False)
        self.osc = OscSocket(host, port)
        self.video = video
        
    def work(self):
        msg = self.osc.recv()
        if msg is None:
            return
        if msg.address == "/scene":
            if msg.params[0] == 1:
                self.video.scrub(0)
                self.video.play()
            else:
                self.video.pause()
        # elif msg.address == "/progress":
        #     pct = msg.params[0]
        #     self.video.scrub(pct)
            
    def cleanup(self):
        self.osc.close()