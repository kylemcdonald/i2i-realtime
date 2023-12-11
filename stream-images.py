import zmq
import time
from itertools import cycle
import argparse
import os
import msgpack

parser = argparse.ArgumentParser()
parser.add_argument(
    "--input_folder", default="data/frames", help="Path to the input folder"
)
parser.add_argument("--input_fps", type=int, default=15, help="Input frames per second")
parser.add_argument(
    "--output_fps", type=int, default=15, help="Output frames per second"
)
parser.add_argument("--port", type=int, default=5555, help="Port number")
args = parser.parse_args()

context = zmq.Context()
publisher = context.socket(zmq.PUSH)
publisher.bind(f"tcp://0.0.0.0:{args.port}")

start_time = time.time()
frame_number = 0

try:
    file_list = os.listdir(args.input_folder)
    fns = list(sorted(file_list))
    n_frames = len(file_list)
    skip = args.input_fps // args.output_fps
    for i, fn in cycle(enumerate(fns[::skip])):
        fn = os.path.join(args.input_folder, fn)
        with open(fn, "rb") as f:
            frame = f.read()
        timestamp = int(time.time() * 1000)
        msg = [timestamp, i, frame]
        packed = msgpack.packb(msg)
        publisher.send(packed)
        print(fn, end="\r")

        next_send_time = start_time + (frame_number + 1) / args.output_fps
        sleep_time = next_send_time - time.time()
        if sleep_time > 0:
            time.sleep(sleep_time)
        frame_number += 1

except KeyboardInterrupt:
    pass
finally:
    publisher.close()
    context.term()
    print()
