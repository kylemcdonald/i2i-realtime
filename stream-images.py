import zmq
import time
import argparse
import os
import re
import msgpack
from threaded_worker import ThreadedWorker

from settings_subscriber import SettingsSubscriber
# from threaded_sequence import ThreadedSequence
from threaded_camera import ThreadedCamera
from batching_worker import BatchingWorker
from zmq_sender import ZmqSender
from osc_video_controller import OscVideoController

parser = argparse.ArgumentParser()
parser.add_argument("--fps", type=int, default=30)
parser.add_argument("--job_port", type=int, default=5555)
parser.add_argument("--settings_port", type=int, default=5556)
parser.add_argument("--osc_port", type=int, default=8000)
args = parser.parse_args()

settings = SettingsSubscriber(args.settings_port)
# video = ThreadedSequence(settings, args.fps)
video = ThreadedCamera()
batcher = BatchingWorker(settings).feed(video)
sender = ZmqSender(settings, args.job_port).feed(batcher)
# controller = OscVideoController(video, "0.0.0.0", args.osc_port)

from threaded_worker import ThreadedWorker
from osc_socket import OscSocket

class OscSettingsController(ThreadedWorker):
    def __init__(self, settings, host, port):
        super().__init__(has_input=False, has_output=False)
        self.osc = OscSocket(host, port)
        self.settings = settings
        
    def work(self):
        msg = self.osc.recv()
        if msg is None:
            return
        print("osc", msg.address, msg.params)
        if msg.address == "/prompt":
            prompt = ' '.join(msg.params)
            settings.settings["prompt"] = prompt
            
    def cleanup(self):
        self.osc.close()
        
controller = OscSettingsController(settings, "0.0.0.0", args.osc_port)

controller.start()
sender.start()
batcher.start()
video.start()

# video.play()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass

print()
controller.close()
settings.close()
sender.close()
batcher.close()
video.close()
