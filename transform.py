import zmq
import json
import base64
import cv2
import numpy as np

from diffusers import AutoPipelineForImage2Image, AutoPipelineForText2Image
import torch

from PIL import Image

publish = True
show_window = False
show_both = False

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

context = zmq.Context()
img_subscriber = context.socket(zmq.SUB)
img_subscriber.connect("tcp://localhost:5555")
img_subscriber.setsockopt(zmq.SUBSCRIBE, b"")

prompt_subscriber = context.socket(zmq.SUB)
prompt_subscriber.connect("tcp://localhost:5556")
prompt_subscriber.setsockopt(zmq.SUBSCRIBE, b"")

context = zmq.Context()
img_publisher = context.socket(zmq.PUB)
img_publisher.bind('tcp://*:5557')

prompt = "A man playing piano."
num_inference_steps = 2
strength = 0.7
reseed = False
seed = 0
size = 512
guidance_scale = 0.0

if show_window:
    cv2.namedWindow("canvas", cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty("canvas", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

try:
    while True:
        try:
            msg = prompt_subscriber.recv_string(flags=zmq.NOBLOCK)
            if msg.startswith("/show"):
                show_both = not show_both
            elif msg.startswith("/reseed"):
                reseed = not reseed
            elif msg.startswith("/seed"):
                seed = int(msg.split(" ")[1])
            elif msg.startswith("/steps"):
                num_inference_steps = int(msg.split(" ")[1])
            elif msg.startswith("/guidance"):
                guidance_scale = float(msg.split(" ")[1])
            elif msg.startswith("/strength"):
                strength = float(msg.split(" ")[1])
            elif msg.startswith("/size"):
                size = int(msg.split(" ")[1])
            else:
                prompt = msg
                print("Received prompt:", prompt)
        except zmq.Again:
            pass
        except KeyboardInterrupt:
            raise
        except:
            print("Invalid message:", msg)

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
        input_image = cv2.resize(img, (size, int(size * h / w)), interpolation=cv2.INTER_CUBIC)
        # input_image = input_image[:, :, ::-1]  # RB swap

        if not reseed:
            generator = torch.manual_seed(seed)
            
        results = i2i_pipe(
            prompt=prompt,
            image=input_image / 255,
            generator=generator,
            num_inference_steps=num_inference_steps,
            guidance_scale=guidance_scale,
            strength=strength,
            output_type="np",
        )
        output_image = results.images[0] * 255
        
        if publish:
            img_u8 = output_image.astype(np.uint8)
            buffer = cv2.imencode('.jpg', img_u8[:, :, ::-1])[1].tobytes()
            jpg_b64 = base64.b64encode(buffer)
            msg = b'{"index":' + str(index).encode('ascii') + b',"data":"' + jpg_b64 + b'"}'
            img_publisher.send(msg)

        if show_window:
            if show_both:
                canvas = np.concatenate((input_image, output_image), axis=1)
                cv2.imshow("canvas", canvas[:, :, ::-1].astype(np.uint8))
            else:
                cv2.imshow("canvas", output_image[:, :, ::-1].astype(np.uint8))

            key = cv2.waitKey(1)
            if key == 27:
                break

except Exception as e:
    print(e)
    img_subscriber.close()
    prompt_subscriber.close()
    img_publisher.close()
    context.term()