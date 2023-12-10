sudo docker run -ti \
    -p 5555:5555 \
    -p 5556:5556 \
    -p 5557:5557 \
    -e HF_HOME=/data \
    -v ~/.cache/huggingface:/data \
    --gpus all \
    i2i-realtime \
    /usr/bin/python3 transform.py