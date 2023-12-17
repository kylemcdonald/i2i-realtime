import time
import argparse
import os
import dotenv
import re
import msgpack
import psutil
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

dotenv.load_dotenv()

parser = argparse.ArgumentParser()
need_mode = "MODE" not in os.environ
parser.add_argument("--mode", required=need_mode, choices=["video", "camera"])
parser.add_argument("--fps", type=int, default=30)
parser.add_argument("--job_port", type=int, default=5555)
parser.add_argument("--settings_port", type=int, default=5556)
parser.add_argument("--display_port", type=int, default=5557)
parser.add_argument("--num_inference_steps", type=int, default=2)
parser.add_argument("--windowed", action="store_true")
parser.add_argument("--mirror", action="store_true", help="Mirror output")
parser.add_argument("--debug", action="store_true", help="Show debug info")
parser.add_argument("--pad", action="store_true", help="Right pad the output")
parser.add_argument("--translation", action="store_true", help="Use translation")
parser.add_argument("--safety", action="store_true", help="Use safety")
parser.add_argument("--osc_port", type=int, default=8000)
args = parser.parse_args()

if "MODE" in os.environ:
    args.mode = os.environ["MODE"]
if "MIRROR" in os.environ:
    args.mirror = os.environ["MIRROR"] == "TRUE"
if "TRANSLATION" in os.environ:
    args.translation = os.environ["TRANSLATION"] == "TRUE"
if "SAFETY" in os.environ:
    args.safety = os.environ["SAFETY"] == "TRUE"
if "DEBUG" in os.environ:
    args.debug = os.environ["DEBUG"] == "TRUE"
if "NUM_INFERENCE_STEPS" in os.environ:
    args.num_inference_steps = int(os.environ["NUM_INFERENCE_STEPS"])

settings = SettingsSubscriber(args.settings_port, args.translation, args.safety, args.num_inference_steps)

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
show_stream = ShowStream(args.display_port, args.windowed, args.mirror, args.debug, args.pad)

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
    process = psutil.Process(os.getpid())
    while True:
        memory_usage_bytes = process.memory_info().rss
        memory_usage_gb = memory_usage_bytes / (1024 ** 3)
        if memory_usage_gb > 10:
            print(f"memory usage: {memory_usage_gb:.2f}GB")
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
