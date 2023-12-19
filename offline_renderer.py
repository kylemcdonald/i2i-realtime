import os
import numpy as np
from tqdm import tqdm
from natsort import natsorted
from turbojpeg import TurboJPEG, TJPF_RGB
from utils.itertools import chunks
from diffusion_processor import DiffusionProcessor

input_directory = "data/frames-1080"
output_directory = input_directory + "-i2i"
batch_size = 4
prompt = "Three ballety dancers in a psychedelic landscape."
steps = 2
strength = 0.7
seed = 0

jpeg = TurboJPEG()

def imread(fn):
    with open(fn, 'rb') as f:
        return jpeg.decode(f.read(), pixel_format=TJPF_RGB)

def imwrite(fn, img):
    with open(fn, 'wb') as f:
        f.write(jpeg.encode(img, pixel_format=TJPF_RGB))

def main():
    diffusion = DiffusionProcessor()
    fns = natsorted(os.listdir(input_directory))
    batches = list(chunks(fns, batch_size))
    os.makedirs(output_directory, exist_ok=True)
    for batch in tqdm(batches):
        input_fns = [os.path.join(input_directory, fn) for fn in batch]
        output_fns = [os.path.join(output_directory, fn) for fn in batch]
        images = [imread(fn) for fn in input_fns]
        images = np.asarray(images, np.float32) / 255
        output = diffusion.run(images, prompt, steps, strength, seed)
        output = (output * 255).astype(np.uint8)
        for output_fn, image in zip(output_fns, output):
            imwrite(output_fn, image)
        
try:
    main()
except KeyboardInterrupt:
    pass