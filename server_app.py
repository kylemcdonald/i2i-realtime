import os
import psutil
import json

from settings import Settings
from settings_api import SettingsAPI
from threaded_sequence import ThreadedSequence
from threaded_camera import ThreadedCamera
from batching_worker import BatchingWorker
from zmq_sender import ZmqSender
from osc_video_controller import OscVideoController
from osc_settings_controller import OscSettingsController
from remove_jitter import RemoveJitter
from reordering_receiver import ReorderingReceiver
from show_stream import ShowStream

# load up settings
settings = Settings()

# create endpoint
settings_api = SettingsAPI(settings)

# create sending end
if settings.mode == "video":
    video = ThreadedSequence(settings)
    controller = OscVideoController(video, settings)
elif settings.mode == "camera":
    video = ThreadedCamera()
    controller = OscSettingsController(settings)
batcher = BatchingWorker(settings).feed(video)
sender = ZmqSender(settings).feed(batcher)

# create receiving end
remove_jitter = RemoveJitter(settings.output_port)
reordering_receiver = ReorderingReceiver(remove_jitter, settings.job_finish_port)

# create display end
show_stream = ShowStream(settings.output_port, settings)

# start from the end of the chain to the beginning

# start display
show_stream.start()

# start receiving end
settings_api.start()
reordering_receiver.start()
remove_jitter.start()

# start sending end
controller.start()
sender.start()
batcher.start()
video.start()

if settings.mode == "video":
    video.play()

try:
    process = psutil.Process(os.getpid())
    while True:
        memory_usage_bytes = process.memory_info().rss
        memory_usage_gb = memory_usage_bytes / (1024**3)
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
