import threading
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import time
import json

from safety_checker import SafetyChecker
from translate import Translate


class SettingsAPI:
    def __init__(self, settings):
        self.shutdown = False
        self.settings = settings
        port = settings.settings_port
        self.thread = threading.Thread(target=self.run, args=(port,))
        
    def start(self):
        if not self.thread.is_alive():
            self.thread.start()

    def run(self, port):
        if self.settings.translation:
            translate = Translate()
        if self.settings.safety:
            safety_checker = SafetyChecker()

        app = FastAPI()

        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @app.get("/prompt/{msg}")
        async def prompt(msg: str):
            if self.settings.translation:
                prompt = translate.translate_to_en(msg)
                if prompt != msg:
                    print("Translating from:", msg)
            else:
                prompt = msg
            
            override = "-f" in prompt
            if override:
                prompt = prompt.replace("-f", "").strip()
            if self.settings.safety and not override:
                safety = safety_checker(prompt)
                if safety != "safe":
                    print(f"Ignoring prompt ({safety}):", prompt)
                    return {"safety": "unsafe"}
            
            self.settings.prompt = prompt
            print("Updated prompt:", prompt)
            return {"safety": "safe"}

        @app.get("/directory/{status}")
        async def directory(status: str):
            self.settings.directory = "data/" + status
            print("Updated directory status:", self.settings.directory)
            return {"status": "updated"}
        
        @app.get("/debug/{status}")
        async def debug(status: bool):
            self.settings.debug = status
            print("Updated debug status:", status)
            return {"status": "updated"}
        
        @app.get("/passthrough/{status}")
        async def passthrough(status: bool):
            self.settings.passthrough = status
            print("Updated passthrough status:", self.settings.passthrough)
            return {"status": "updated"}

        @app.get("/fixed_seed/{status}")
        async def fixed_seed(status: bool):
            self.settings.fixed_seed = status
            print("Updated fixed_seed status:", self.settings.fixed_seed)
            return {"status": "updated"}

        @app.get("/batch_size/{value}")
        async def batch_size(value: int):
            self.settings.batch_size = value
            print("Updated batch_size:", self.settings.batch_size)
            return {"status": "updated"}

        @app.get("/seed/{value}")
        async def seed(value: int):
            self.settings.seed = value
            print("Updated seed:", self.settings.seed)
            return {"status": "updated"}

        @app.get("/steps/{value}")
        async def steps(value: int):
            self.settings.num_inference_steps = value
            print("Updated num_inference_steps:", self.settings.num_inference_steps)
            return {"status": "updated"}

        @app.get("/strength/{value}")
        async def strength(value: float):
            self.settings.strength = value
            print("Updated strength:", self.settings.strength)
            return {"status": "updated"}

        config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
        self.server = uvicorn.Server(config=config)
        try:
            self.server.run()
        except KeyboardInterrupt:
            pass

    def close(self):
        if hasattr(self, "server"):
            self.server.should_exit = True
        self.thread.join()