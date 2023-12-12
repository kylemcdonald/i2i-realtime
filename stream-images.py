import zmq
import time
from itertools import cycle
import argparse
import os
import msgpack
from settings_subscriber import SettingsSubscriber

parser = argparse.ArgumentParser()
parser.add_argument(
    "--input_folder", default="data/frames", help="Path to the input folder"
)
parser.add_argument("--input_fps", type=int, default=15, help="Input frames per second")
parser.add_argument(
    "--output_fps", type=int, default=15, help="Output frames per second"
)
parser.add_argument("--port", type=int, default=5555, help="Port number")
parser.add_argument("--settings_port", type=int, default=5556, help="Settings port")
args = parser.parse_args()

settings = SettingsSubscriber(args.settings_port)

context = zmq.Context()
publisher = context.socket(zmq.PUSH)
publisher.bind(f"tcp://0.0.0.0:{args.port}")

start_time = time.time()
input_frame_number = 0
output_frame_number = 0

try:
    file_list = os.listdir(args.input_folder)
    fns = list(sorted(file_list))
    n_frames = len(file_list)
    skip = args.input_fps // args.output_fps
    
    while True:
        frames = []
        indices = []
        for i in range(settings["batch_size"]):
            fn = os.path.join(args.input_folder, fns[input_frame_number])
            with open(fn, "rb") as f:
                frames.append(f.read())
            indices.append(input_frame_number)
            output_frame_number += 1
            input_frame_number += skip
            if input_frame_number >= n_frames:
                input_frame_number = 0
        
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

        next_send_time = start_time + output_frame_number / args.output_fps
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
