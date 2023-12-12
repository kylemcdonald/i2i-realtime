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

print("ready for messages")

try:
    while True:
        msg = receiver.recv()
        unpacked = msgpack.unpackb(msg)
        index = unpacked["index"]

        if next_index is None:
            next_index = index
        if index == 0:
            next_index = 0
        if index < next_index:
            print("dropping", index)
            continue

        timestamp = unpacked["timestamp"]
        index = unpacked["index"]
        worker_id = unpacked["worker_id"]
        jpg = unpacked["jpg"]

        latency = int(time.time() * 1000) - timestamp
        msg_buffer[index] = unpacked
        print(f"incoming: {index} #{worker_id} {latency}ms")

        # publisher.send(packed) # echo mode

        # ordered mode
        while next_index in msg_buffer:
            unpacked = msg_buffer[next_index]
            timestamp = unpacked["timestamp"]
            index = unpacked["index"]
            worker_id = unpacked["worker_id"]
            jpg = unpacked["jpg"]

            latency = int(time.time() * 1000) - timestamp
            print(f"outgoing: {index} #{worker_id} {latency}ms")

            packed = msgpack.packb([timestamp, index, jpg])
            publisher.send(packed)
            del msg_buffer[next_index]
            next_index += 1

except KeyboardInterrupt:
    pass
finally:
    print()
    print("closing receiver")
    receiver.close()
    print("closing publisher")
    publisher.close()
    print("term context")
    context.term()
