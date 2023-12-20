from pydantic.v1 import BaseSettings, Field

class Settings(BaseSettings):
    # config, cannot be changed
    mode: str = Field(default="video")
    worker_id: int = Field(default=0)
    
    output_fast: bool = Field(default=True)
    zmq_video_port: int = Field(default=5554)
    job_start_port: int = Field(default=5555)
    settings_port: int = Field(default=5556)
    job_finish_port: int = Field(default=5557)
    output_port: int = Field(default=5558)
    osc_port: int = Field(default=8000)
    primary_hostname: str = Field(default='localhost')
    
    translation: bool = Field(default=False)
    safety: bool = Field(default=False)
    local_files_only: bool = Field(default=False)
    warmup: str = Field(default=None)
    
    # parameters for inference
    prompt: str = Field(default='A psychedelic landscape.')
    num_inference_steps: int = Field(default=2)
    fixed_seed: bool = Field(default=True)
    seed: int = Field(default=0)
    batch_size: int = Field(default=1)
    strength: float = Field(default=0.7)
    passthrough: bool = Field(default=False)
    
    # can be changed dynamically
    mirror: bool = Field(default=False)
    debug: bool = Field(default=False)
    pad: bool = Field(default=False)
    fps: int = Field(default=30)
    directory: str = Field(default='data/frames')
    
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'