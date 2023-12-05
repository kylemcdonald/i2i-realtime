import zmq
import time
from itertools import cycle
import base64
import readline

fps = 15
n_frames = 5632

context = zmq.Context()
publisher = context.socket(zmq.PUB)
publisher.bind('tcp://*:5556')

previous_msg = ''
try:
    while True:
        msg = input()
        publisher.send_string(msg)
except:
    publisher.close()
    context.term()