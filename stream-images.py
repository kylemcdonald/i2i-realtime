import zmq
import time
from itertools import cycle
import argparse
import os
import re
import msgpack
from settings_subscriber import SettingsSubscriber

parser = argparse.ArgumentParser()
parser.add_argument(
    "--input_folder",
    default="data/m8_Perspective_BG_20231130",
    help="Path to the input folder",
)
parser.add_argument("--input_fps", type=int, default=30, help="Input frames per second")
parser.add_argument("--port", type=int, default=5555, help="PUSH port number")
parser.add_argument("--settings_port", type=int, default=5556, help="Settings port")
args = parser.parse_args()

settings = SettingsSubscriber(args.settings_port)

from threaded_worker import ThreadedWorker

class AutomaticPlayback(ThreadedWorker):
    def __init__(self, total_frames):
        super().__init__(has_input=False)
        self.total_frames = total_frames
        self.current_frame = 0
        self.playing = False
        
    def setup(self):
        self.start_time = time.time()
    
    def work(self):
        indices = []
        for i in range(settings["batch_size"]):
            indices.append(self.current_frame)
            self.current_frame += 1
            if self.current_frame >= self.total_frames:
                self.current_frame = 0
        
        time_in_seconds = self.current_frame / settings["fps"]
        next_frame_time = self.start_time + time_in_seconds
        time_to_sleep = next_frame_time - time.time()
        if time_to_sleep > 0:
            time.sleep(time_to_sleep)
                
        return indices
        
class Sender(ThreadedWorker):
    def __init__(self, fns, port):
        super().__init__(has_output=False)
        self.context = zmq.Context()
        self.publisher = self.context.socket(zmq.PUSH)
        self.publisher.bind(f"tcp://0.0.0.0:{port}")
        self.fns = fns
        
    def work(self, indices):
        frames = []
        for index in indices:
            fn = os.path.join(self.fns[index])
            if settings["local_mode"]:
                frames.append(fn)
            else:
                with open(fn, "rb") as f:
                    frames.append(f.read())

        timestamp = int(time.time() * 1000)
        packed = msgpack.packb(
            {
                "timestamp": timestamp,
                "indices": indices,
                "frames": frames,
                "settings": settings.settings,
            }
        )
        
        self.publisher.send(packed)
        print(fn, end="\r")
        
        
def extract_number(filename):
    match = re.search(r'\d+', filename)
    if match:
        return int(match.group())
    return None

def numeric_sort(file_list):
    return sorted(file_list, key=extract_number)


file_list = os.listdir(args.input_folder)
fns = numeric_sort(file_list)
fns = [os.path.join(args.input_folder, fn) for fn in fns]

playback = AutomaticPlayback(len(fns)).set_name("playback")
sender = Sender(fns, args.port).set_name("sender").feed(playback)

playback.start()
sender.start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    print()
    settings.close()
    sender.close()
    playback.close()
