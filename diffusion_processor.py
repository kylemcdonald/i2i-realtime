import numpy as np
import time
from fixed_seed import fix_seed

from sfast.compilers.stable_diffusion_pipeline_compiler import (
    compile,
    CompilationConfig,
)

from diffusers.utils.logging import disable_progress_bar
from diffusers import AutoPipelineForImage2Image, AutoencoderTiny
import torch
import warnings


class DiffusionProcessor:
    def __init__(self, warmup=None, local_files_only=True):
        base_model = "stabilityai/sdxl-turbo"
        vae_model = "madebyollin/taesdxl"

        warnings.filterwarnings("ignore", category=torch.jit.TracerWarning)

        disable_progress_bar()
        self.pipe = AutoPipelineForImage2Image.from_pretrained(
            base_model,
            torch_dtype=torch.float16,
            variant="fp16",
            local_files_only=local_files_only,
        )

        self.pipe.vae = AutoencoderTiny.from_pretrained(
            vae_model, torch_dtype=torch.float16, local_files_only=local_files_only
        )
        fix_seed(self.pipe)

        print("Model loaded")

        config = CompilationConfig.Default()
        config.enable_xformers = True
        config.enable_triton = True
        config.enable_cuda_graph = True
        self.pipe = compile(self.pipe, config=config)

        print("Model compiled")

        self.pipe.to(device="cuda", dtype=torch.float16)
        self.pipe.set_progress_bar_config(disable=True)

        print("Model moved to GPU", flush=True)

        self.generator = torch.manual_seed(0)
        
        if warmup:
            warmup_shape = [int(e) for e in warmup.split("x")]
            images = np.zeros(warmup_shape, dtype=np.float32)
            for i in range(2):
                print(f"Warmup {warmup} {i+1}/2")
                start_time = time.time()
                self.run(
                    images,
                    prompt="warmup",
                    num_inference_steps=2,
                    strength=1.0
                )
            print("Warmup finished", flush=True)

    def run(self, images, prompt, num_inference_steps, strength, seed=None):
        strength = min(max(1 / num_inference_steps, strength), 1)
        if seed is not None:
            self.generator = torch.manual_seed(seed)
        return self.pipe(
            prompt=[prompt] * len(images),
            image=images,
            generator=self.generator,
            num_inference_steps=num_inference_steps,
            guidance_scale=0,
            strength=strength,
            output_type="np",
        ).images
