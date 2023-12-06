import zmq
import json
import base64
import cv2
import numpy as np
import argparse

from diffusers import AutoPipelineForImage2Image, AutoPipelineForText2Image
import torch

from PIL import Image

from settings_subscriber import SettingsSubscriber

device = torch.device("cuda")
torch_device = device
torch_dtype = torch.float16

i2i_pipe = AutoPipelineForImage2Image.from_pretrained(
    "stabilityai/sdxl-turbo",
    torch_dtype=torch_dtype,
    variant="fp16" if torch_dtype == torch.float16 else "fp32",
)

i2i_pipe.to(device=torch_device, dtype=torch_dtype).to(device)
i2i_pipe.set_progress_bar_config(disable=True)

parser = argparse.ArgumentParser()
parser.add_argument("--input_port", type=int, default=5555, help="Input port")
parser.add_argument("--output_port", type=int, default=5557, help="Output port")
parser.add_argument("--prompt_port", type=int, default=5556, help="Prompt port")
args = parser.parse_args()

context = zmq.Context()
img_subscriber = context.socket(zmq.SUB)
img_subscriber.connect(f"tcp://localhost:{args.input_port}")
img_subscriber.setsockopt(zmq.SUBSCRIBE, b"")

img_publisher = context.socket(zmq.PUB)
img_publisher.bind(f"tcp://*:{args.output_port}")

settings = SettingsSubscriber(args.prompt_port)

try:
    while True:
        msg = img_subscriber.recv()
        while img_subscriber.get(zmq.RCVMORE):
            msg = img_subscriber.recv()

        # print('received msg', msg[:40])
        data = json.loads(msg)
        index = data['index']
        jpg_b64 = data['data']
        jpg = base64.b64decode(jpg_b64)
        img = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_UNCHANGED)

        h, w, _ = img.shape
        size = settings["size"]
        input_image = cv2.resize(img, (size, int(size * h / w)), interpolation=cv2.INTER_CUBIC)
        # input_image = input_image[:, :, ::-1]  # RB swap

        if not settings["reseed"]:
            generator = torch.manual_seed(settings["seed"])
            
        results = i2i_pipe(
            prompt=settings["prompt"],
            image=input_image / 255,
            generator=generator,
            num_inference_steps=settings["num_inference_steps"],
            guidance_scale=settings["guidance_scale"],
            strength=settings["strength"],
            output_type="np",
        )
        output_image = results.images[0] * 255
    
        img_u8 = output_image.astype(np.uint8)
        buffer = cv2.imencode('.jpg', img_u8[:, :, ::-1])[1].tobytes()
        jpg_b64 = base64.b64encode(buffer)
        msg = b'{"index":' + str(index).encode('ascii') + b',"data":"' + jpg_b64 + b'"}'
        img_publisher.send(msg)

except Exception as e:
    print(e)
    settings.close()
    img_subscriber.close()
    img_publisher.close()
    context.term()