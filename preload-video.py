import numpy as np
from utils.ffmpeg import vidread
from utils.imutil import imread, imresize, imwrite
import argparse
import os

parser = argparse.ArgumentParser(description='Preload video frames')
parser.add_argument('--input', type=str, required=True, help='input video file path')
parser.add_argument('--output', type=str, default='data/frames.npy', help='output file path for frames')
parser.add_argument('--input_fps', type=int, default=30, help='input frames per second')
parser.add_argument('--fps', type=int, default=15, help='output frames per second')
parser.add_argument('--width', type=int, default=1024, help='output frame width')
parser.add_argument('--jpg', action='store_true', help='save jpgs')
args = parser.parse_args()

images = []

if os.path.isfile(args.input):
    for frame in vidread(args.input, rate=args.fps):
        img = imresize(frame, output_wh=(args.width, None))
        images.append(img)
else:
    fns = os.listdir(args.input)
    fns.sort()
    skip = args.input_fps // args.fps
    index = 0
    for fn in fns[::skip]:
        img = imread(os.path.join(args.input, fn))
        if args.width != img.shape[1]:
            img = imresize(frame, output_wh=(args.width, None))
        if args.jpg:
            imwrite(os.path.join(args.output, f"{index:04d}.jpg"), img)
            index += 1
        else:
            images.append(img)
    
if not args.jpg:
    images = np.asarray(images)
    np.save(args.output, images)