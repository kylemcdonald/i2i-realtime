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
parser.add_argument("--start_time", type=int, default=0, help="Start time in seconds")
parser.add_argument("--duration", type=int, default=None, help="Duration in seconds")
parser.add_argument("--port", type=int, default=5555, help="PUSH port number")
parser.add_argument("--settings_port", type=int, default=5556, help="Settings port")
args = parser.parse_args()

settings = SettingsSubscriber(args.settings_port)

context = zmq.Context()
publisher = context.socket(zmq.PUSH)
publisher.bind(f"tcp://0.0.0.0:{args.port}")

start_time = time.time()
start_fps = settings["fps"]

start_frame_number = args.start_time * args.input_fps
input_frame_number = start_frame_number
output_frame_number = 0

def extract_number(filename):
    match = re.search(r'\d+', filename)
    if match:
        return int(match.group())
    return None

def numeric_sort(file_list):
    return sorted(file_list, key=extract_number)

try:
    file_list = os.listdir(args.input_folder)
    fns = numeric_sort(file_list)
    end_frame_number = len(file_list)
    if args.duration:
        end_frame_number = start_frame_number + args.duration * args.input_fps

    while True:
        skip = args.input_fps // settings["fps"]
        true_fps = args.input_fps // skip
        
        if settings["fps"] != start_fps:
            start_time = time.time()
            output_frame_number = 0
    
        frames = []
        indices = []
        for i in range(settings["batch_size"]):
            fn = os.path.join(args.input_folder, fns[input_frame_number])
            if settings["local_mode"]:
                frames.append(fn)
            else:
                with open(fn, "rb") as f:
                    frames.append(f.read())
            indices.append(input_frame_number)
            output_frame_number += 1
            input_frame_number += skip
            if input_frame_number >= end_frame_number:
                input_frame_number = start_frame_number

        timestamp = int(time.time() * 1000)
        packed = msgpack.packb(
            {
                "timestamp": timestamp,
                "indices": indices,
                "frames": frames,
                "settings": settings.settings,
            }
        )
        publisher.send(packed)
        print(fn, end="\r")

        next_send_time = start_time + output_frame_number / true_fps
        sleep_time = next_send_time - time.time()
        if sleep_time > 0:
            time.sleep(sleep_time)

except KeyboardInterrupt:
    pass
finally:
    print()
    print("closing settings")
    settings.close()
    print("closing publisher")
    publisher.close()
    print("term context")
    context.term()
