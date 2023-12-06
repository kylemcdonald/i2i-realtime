import threading
import zmq
from safety_checker import SafetyChecker
from translate import Translate

class SettingsSubscriber:
    def __init__(self, port):
        self.shutdown = False
        self.settings = {
            "reseed": False,
            "seed": 0,
            "num_inference_steps": 2,
            "guidance_scale": 0.0,
            "strength": 0.7,
            "size": 512,
            "prompt": "A man playing piano."
        }
        self.thread = threading.Thread(target=self.run, args=(port,))
        self.thread.start()
        
    def __getitem__(self, key):
        return self.settings[key]
        
    def receive(self, msg):
        print(msg)
        try:
            if msg.startswith("/reseed"):
                self.settings["reseed"] = not self.settings["reseed"]
                print("Updated reseed status:", self.settings["reseed"])
            elif msg.startswith("/seed"):
                self.settings["seed"] = int(msg.split(" ")[1])
                print("Updated seed:", self.settings["seed"])
            elif msg.startswith("/steps"):
                self.settings["num_inference_steps"] = int(msg.split(" ")[1])
                print("Updated num_inference_steps:", self.settings["num_inference_steps"])
            elif msg.startswith("/guidance"):
                self.settings["guidance_scale"] = float(msg.split(" ")[1])
                print("Updated guidance_scale:", self.settings["guidance_scale"])
            elif msg.startswith("/strength"):
                self.settings["strength"] = float(msg.split(" ")[1])
                print("Updated strength:", self.settings["strength"])
            elif msg.startswith("/size"):
                self.settings["size"] = int(msg.split(" ")[1])
                print("Updated size:", self.settings["size"])
            else:
                prompt = self.translate.translate_to_en(msg)
                if prompt != msg:
                    print("Translating from:", msg)
                if self.safety_checker(prompt) == "unsafe":
                    print("Ignoring unsafe prompt:", prompt)
                else:
                    self.settings["prompt"] = prompt
                    print("Updated prompt:", prompt)
        except Exception as e:
            print("Invalid message")
            print(e)


    def run(self, port):
        self.safety_checker = SafetyChecker()
        self.translate = Translate()
        
        context = zmq.Context()
        sub = context.socket(zmq.SUB)
        sub.connect(f"tcp://localhost:{port}")
        sub.setsockopt(zmq.SUBSCRIBE, b"")
        sub.setsockopt(zmq.RCVTIMEO, 100)

        while not self.shutdown:
            try:
                self.receive(sub.recv_string())
            except zmq.Again:
                pass
            
        sub.close()
        context.term()
            
    def close(self):
        self.shutdown = True
        self.thread.join()
        
if __name__ == "__main__":
    sub = SettingsSubscriber(5556)
    try:
        input("Press Enter to stop...\n")
    except KeyboardInterrupt:
        pass
    sub.close()