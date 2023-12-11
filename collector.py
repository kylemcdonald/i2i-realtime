import zmq
import msgpack
import time

context = zmq.Context()
receiver = context.socket(zmq.PULL)
receiver.bind("tcp://0.0.0.0:5558")

publisher = context.socket(zmq.PUB)
publisher.bind(f"tcp://0.0.0.0:5557")

while True:
    msg = receiver.recv()
    timestamp, index, jpg, ip = msgpack.unpackb(msg)
    latency = int(time.time() * 1000) - timestamp
    print(f"{ip} {index} {latency}ms")
    publisher.send(msg)