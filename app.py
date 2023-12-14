import zmq
import time
import argparse
import os
import re
import msgpack
from threaded_worker import ThreadedWorker

from settings_subscriber import SettingsSubscriber
from threaded_sequence import ThreadedSequence
from threaded_camera import ThreadedCamera
from batching_worker import BatchingWorker
from zmq_sender import ZmqSender
from osc_video_controller import OscVideoController
from osc_settings_controller import OscSettingsController
from remove_jitter import RemoveJitter
from reordering_receiver import ReorderingReceiver
from show_stream import ShowStream

parser = argparse.ArgumentParser()
parser.add_argument("--fps", type=int, default=30)
parser.add_argument("--job_port", type=int, default=5555)
parser.add_argument("--settings_port", type=int, default=5556)
parser.add_argument("--display_port", type=int, default=5557)
parser.add_argument("--fullscreen", action="store_true")
parser.add_argument("--mirror", action="store_true", help="Mirror output")
parser.add_argument("--debug", action="store_true", help="Show debug info")
parser.add_argument("--translation", action="store_true", help="Use translation")
parser.add_argument("--safety", action="store_true", help="Use safety")
parser.add_argument("--osc_port", type=int, default=8000)
parser.add_argument("--mode", required=True, choices=["video", "camera"])
args = parser.parse_args()

settings = SettingsSubscriber(args.settings_port, args.translation, args.safety)

# create sending end
if args.mode == "video":
    video = ThreadedSequence(settings, args.fps)
    controller = OscVideoController(video, "0.0.0.0", args.osc_port)        
elif args.mode == "camera":
    video = ThreadedCamera()
    controller = OscSettingsController(settings, "0.0.0.0", args.osc_port)
batcher = BatchingWorker(settings).feed(video)
sender = ZmqSender(settings, args.job_port).feed(batcher)

# create receiving end
remove_jitter = RemoveJitter(5557)
reordering_receiver = ReorderingReceiver(remove_jitter, 5558)

# create display end
show_stream = ShowStream(args.display_port, args.fullscreen, args.mirror, args.debug)

# start from the end of the chain to the beginning

# start display
show_stream.start()

# start receiving end
reordering_receiver.start()
remove_jitter.start()

# start sending end
controller.start()
sender.start()
batcher.start()
video.start()

if args.mode == "video":
    video.play()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass

print()

# stop from the end of the chain to the beginning

# close display end
show_stream.close()

# close receiving end
remove_jitter.stop()
reordering_receiver.close()
    
# close sending end
controller.close()
settings.close()
sender.close()
batcher.close()
video.close()
