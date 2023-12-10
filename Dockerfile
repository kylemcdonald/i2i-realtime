FROM nvidia/cuda:12.1.1-cudnn8-devel-ubuntu22.04

ARG DEBIAN_FRONTEND=noninteractive

ENV PYTHONUNBUFFERED=1

# google-perftools installs libtcmalloc
# libturbojpeg is needed for pyturbojpeg
# git is needed for installing pyturbojpeg
RUN apt-get update && apt-get install --no-install-recommends -y \
    build-essential \
    python3.10 \
    python3.10-dev \
    python3-pip \
    libturbojpeg \
    ffmpeg \
    google-perftools \
    git \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
    
WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

# Set up a new user named "user" with user ID 1000
RUN useradd -m -u 1000 user
# Switch to the "user" user
USER user
# Set home to the user's home directory
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONPATH=$HOME/app \
    PYTHONUNBUFFERED=1 \
    SYSTEM=spaces

RUN pip3 install --no-cache-dir --upgrade -r /code/requirements.txt

# Set the working directory to the user's home directory
WORKDIR $HOME/app

# Copy the current directory contents into the container at $HOME/app setting the owner to the user
COPY --chown=user . $HOME/app

ENV LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libtcmalloc.so.4
# CMD ["/usr/bin/python3", "transform.py"] # use run-docker.sh instead