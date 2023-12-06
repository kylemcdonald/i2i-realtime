import readline
import argparse
import requests

parser = argparse.ArgumentParser()
parser.add_argument('--port', type=int, default=5556, help='Port number')
args = parser.parse_args()

previous_msg = ''
try:
    while True:
        msg = input()
        command = "prompt"
        if msg.startswith('/'):
            command = msg.split()[0][1:]
            msg = msg[len(command)+2:]
        url = f'http://localhost:{args.port}/{command}/{msg}'
        print(url)
        response = requests.get(url)
        print(response.json())
except KeyboardInterrupt:
    pass