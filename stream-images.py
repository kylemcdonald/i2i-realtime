import zmq
import time
import argparse
import os
import re
import msgpack
from threaded_worker import ThreadedWorker

from settings_subscriber import SettingsSubscriber
from threaded_sequence import ThreadedSequence
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
video = ThreadedSequence(settings, args.fps)
batcher = BatchingWorker(settings).feed(video)
sender = ZmqSender(settings, args.job_port).feed(batcher)
controller = OscVideoController(video, "0.0.0.0", args.osc_port)

controller.start()
sender.start()
batcher.start()
video.start()

video.play()

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
