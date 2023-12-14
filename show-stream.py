import argparse
import time
from show_stream import ShowStream

parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=5557, help="Port number")
parser.add_argument("--fullscreen", action="store_true", help="Enable fullscreen")
parser.add_argument("--mirror", action="store_true", help="Mirror output")
parser.add_argument("--debug", action="store_true", help="Show debug info")
args = parser.parse_args()

show_stream = ShowStream(args.port, args.fullscreen, args.mirror, args.debug)
show_stream.start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass

show_stream.close()