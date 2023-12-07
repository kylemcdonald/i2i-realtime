import zmq
import time
from itertools import cycle
import base64
import argparse
import os

parser = argparse.ArgumentParser()
parser.add_argument("--input_folder", default="data/frames", help="Path to the input folder")
parser.add_argument("--fps", type=int, default=15, help="Frames per second")
parser.add_argument("--port", type=int, default=5555, help="Port number")
args = parser.parse_args()

context = zmq.Context()
publisher = context.socket(zmq.PUB)
publisher.bind(f'tcp://*:{args.port}')

try:
    file_list = os.listdir(args.input_folder)
    n_frames = len(file_list)

    for i in cycle(range(1, 1+n_frames)):
        fn = f'{args.input_folder}/{i:04d}.jpg'
        with open(fn, 'rb') as f:
            frame = f.read()
        jpg_b64 = base64.b64encode(frame)
        timestamp = str(int(time.time() * 1000)).encode('ascii')
        index = str(i).encode('ascii')
        msg = b'{"timestamp":'+ timestamp +b',"index":' + index + b',"data":"' + jpg_b64 + b'"}'
        publisher.send(msg)
        print(fn, end='\r')
        time.sleep(1/args.fps)
        
except KeyboardInterrupt:
    pass
finally:
    publisher.close()
    context.term()
    print()
