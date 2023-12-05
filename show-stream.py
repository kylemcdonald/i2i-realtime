import zmq
import json
import base64
import cv2
import numpy as np
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, help="Port number")
parser.add_argument("--fullscreen", action="store_true", help="Enable fullscreen")
args = parser.parse_args()

context = zmq.Context()
img_subscriber = context.socket(zmq.SUB)
img_subscriber.connect(f"tcp://localhost:{args.port}")
img_subscriber.setsockopt(zmq.SUBSCRIBE, b"")

if args.fullscreen:
    cv2.namedWindow("canvas", cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty("canvas", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

try:
    while True:
        msg = img_subscriber.recv()
        while img_subscriber.get(zmq.RCVMORE):
            msg = img_subscriber.recv()

        data = json.loads(msg)
        index = data['index']
        jpg_b64 = data['data']
        jpg = base64.b64decode(jpg_b64)
        img = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_UNCHANGED)

        # write index to image using putText
        cv2.putText(img, str(index), (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        cv2.imshow("canvas", img)

        key = cv2.waitKey(1)
        if key == 27:
            break

except Exception as e:
    print(e)
    img_subscriber.close()
    context.term()