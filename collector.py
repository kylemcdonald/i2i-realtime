import zmq
import msgpack
import time

context = zmq.Context()
receiver = context.socket(zmq.PULL)
receiver.bind("tcp://0.0.0.0:5558")

publisher = context.socket(zmq.PUB)
publisher.bind(f"tcp://0.0.0.0:5557")

# msg_buffer = {}
# next_index = None

while True:
    msg = receiver.recv()
    timestamp, index, jpg, ip = msgpack.unpackb(msg)
    
    # if next_index is None:
    #     next_index = index
    # if index == 0:
    #     next_index = 0
    # if index < next_index:
    #     print("dropping", index)
    #     continue        
    
    latency = int(time.time() * 1000) - timestamp
    # msg_buffer[index] = msg
    print(f"{ip} {index} {latency}ms")
    
    publisher.send(msg)
    
    # while next_index in msg_buffer:
    #     print("sending", next_index)
    #     publisher.send(msg_buffer[next_index])
    #     del msg_buffer[next_index]
    #     next_index += 1