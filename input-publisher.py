import zmq
import readline
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--port', type=int, default=5556, help='Port number')
args = parser.parse_args()

context = zmq.Context()
publisher = context.socket(zmq.PUB)
publisher.bind(f'tcp://*:{args.port}')

previous_msg = ''
try:
    while True:
        msg = input()
        publisher.send_string(msg)
except:
    publisher.close()
    context.term()