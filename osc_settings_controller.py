from threaded_worker import ThreadedWorker
from osc_socket import OscSocket
from pythonosc import osc_packet

class OscSettingsController(ThreadedWorker):
    def __init__(self, settings):
        super().__init__(has_input=False, has_output=False)
        address = f"0.0.0.0:{settings.osc_port}"
        print(self.name, f"connecting to OSC on {address}")
        self.osc = OscSocket("0.0.0.0", settings.osc_port)
        self.settings = settings
        
    def work(self):
        try:
            msg = self.osc.recv()
            if msg is None:
                return
            if msg.address == "/prompt":
                prompt = ' '.join(msg.params)
                # print("OSC prompt:", prompt)
                self.settings.prompt = prompt
            elif msg.address == "/seed":
                seed = msg.params[0]
                # print("OSC seed:", seed)
                self.settings.seed = seed
            elif msg.address == "/mode":
                mode = msg.params[0]
                if mode == "soft":
                    self.settings.num_inference_steps = 3
                    self.settings.strength = 0.5
                elif mode == "hard":
                    self.settings.num_inference_steps = 2
                    self.settings.strength = 0.7               
            # else:
                # print("unknown osc", msg.address, msg.params)
        except TypeError:
            print("osc TypeError")
        except osc_packet.ParseError:
            print("osc ParseError")
        except Exception as e:
            print("osc error", e)
            
    def cleanup(self):
        self.osc.close()