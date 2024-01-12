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
        self.prompt_0 = ""
        self.prompt_1 = ""
        self.blend = 0.5
        
    def update_blend(self):
        if self.blend == 0:
            self.settings.prompt = self.prompt_0
        elif self.blend == 1:
            self.settings.prompt = self.prompt_1
        else:
            a = self.prompt_0
            b = self.prompt_1
            t = self.blend
            self.settings.prompt = f'("{a}", "{b}").blend({1-t:.2f}, {t:.2f})'
        
    def work(self):
        try:
            msg = self.osc.recv()
            if msg is None:
                return
            if msg.address == "/prompt":
                prompt = ' '.join(msg.params)
                # print("OSC prompt:", prompt)
                self.settings.prompt = prompt
                
            elif msg.address == "/blend":
                a, b, t = msg.params
                self.prompt_0 = a
                self.prompt_1 = b
                self.blend = t
                self.update_blend()
            elif msg.address == "/prompt/0":
                self.prompt_0 = ' '.join(msg.params)
                self.update_blend()
            elif msg.address == "/prompt/1":
                self.prompt_1 = ' '.join(msg.params)
                self.update_blend()
            elif msg.address == "/blend_t":
                self.blend = float(msg.params[0])
                self.update_blend()
                
            elif msg.address == "/seed":
                seed = msg.params[0]
                # print("OSC seed:", seed)
                self.settings.seed = seed
            elif msg.address == "/opacity":
                opacity = float(msg.params[0])
                opacity = min(max(opacity, 0), 1)
                self.settings.opacity = opacity
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