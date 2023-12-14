import time
from remove_jitter import RemoveJitter
from reordering_receiver import ReorderingReceiver

print("ready for messages")

remove_jitter = RemoveJitter(5557)
reordering_receiver = ReorderingReceiver(remove_jitter, 5558)

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    print()
    remove_jitter.stop()
    reordering_receiver.close()