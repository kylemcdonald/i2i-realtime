import os
import psutil

from settings import Settings
from settings_api import SettingsAPI
from threaded_sequence import ThreadedSequence
from threaded_camera import ThreadedCamera
from threaded_zmq_video import ThreadedZmqVideo
from batching_worker import BatchingWorker
from zmq_sender import ZmqSender
from osc_video_controller import OscVideoController
from osc_settings_controller import OscSettingsController
from output_smooth import OutputSmooth
from output_fast import OutputFast
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
elif settings.mode == "zmq":
    video = ThreadedZmqVideo(settings)
    controller = OscSettingsController(settings)
batcher = BatchingWorker(settings).feed(video)
sender = ZmqSender(settings).feed(batcher)

# create receiving end
reordering_receiver = ReorderingReceiver(settings.job_finish_port)
if settings.output_fast:
    output = OutputFast(settings.output_port).feed(reordering_receiver)
else:
    output = OutputSmooth(settings.output_port).feed(reordering_receiver)

# create display end
show_stream = ShowStream(settings.output_port, settings)

# start from the end of the chain to the beginning

# start display
show_stream.start()

# start receiving end
settings_api.start()
reordering_receiver.start()
output.start()

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
output.close()
reordering_receiver.close()

# close sending end
controller.close()
settings_api.close()
sender.close()
batcher.close()
video.close()
