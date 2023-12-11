import zmq
import msgpack
import time

context = zmq.Context()
receiver = context.socket(zmq.PULL)
receiver.bind("tcp://0.0.0.0:5558")

publisher = context.socket(zmq.PUB)
publisher.bind(f"tcp://0.0.0.0:5557")

msg_buffer = {}
next_index = None

while True:
    msg = receiver.recv()
    timestamp, index, jpg, ip = msgpack.unpackb(msg)
    latency = int(time.time() * 1000) - timestamp
    msg_buffer[index] = msg
    print(f"{ip} {index} {latency}ms")
    
    while next_index in msg_buffer:
        print("sending", next_index)
        publisher.send(msg_buffer[next_index])
        del msg_buffer[next_index]
        next_index += 1