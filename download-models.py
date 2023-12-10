from diffusers import (
    ControlNetModel,
    AutoencoderTiny,
    AutoPipelineForImage2Image)
import torch

torch_dtype = torch.float16

ControlNetModel.from_pretrained("thibaud/controlnet-sd21-canny-diffusers", torch_dtype=torch_dtype)
ControlNetModel.from_pretrained("diffusers/controlnet-canny-sdxl-1.0", torch_dtype=torch_dtype, variant="fp16")
AutoencoderTiny.from_pretrained("madebyollin/taesd", torch_dtype=torch_dtype, use_safetensors=True)
AutoPipelineForImage2Image.from_pretrained("stabilityai/sdxl-turbo", torch_dtype=torch_dtype, variant="fp16")
AutoPipelineForImage2Image.from_pretrained("stabilityai/sd-turbo", torch_dtype=torch_dtype, variant="fp16")