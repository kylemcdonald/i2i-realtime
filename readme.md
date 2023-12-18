# Realtime i2i for Rhizomatiks

This system takes input from an image stream (`ThreadedSequence`) or from a live camera stream (`ThreadedCamera`).

The final output is a msgpack-encoded list served as ZMQ publisher on port 5557 in the format [timestamp, index, jpg].

* timestamp (int) is the time in milliseconds since Unix epoch. Useful for estimating overall latency.
* index (int) is the frame index.
* jpg (byte buffer) is a libturbo-jpeg encoded JPG of the image.

By default, the results are also displayed fullscreen.

## Machine Setup

This software runs on multiple computers that are networked together.

First, install Ubuntu 20.04 on a computer with an NVIDIA GPU. When rebooting, disable secure boot so that you can install the NVIDIA drivers.

Open a Terminal and enable ssh access:

```
sudo apt install -y openssh-server
mkdir -m700 ~/.ssh
wget -qO- https://github.com/<username>.keys | head -n1 > ~/.ssh/authorized_keys
```

Replace `<username>` with your GitHub username. Then ssh into the server and continue.

```
# install curl
sudo apt-get update
sudo apt install -y curl

# install git
sudo apt install -y git

# install NVIDIA drivers
wget https://developer.download.nvidia.com/compute/cuda/12.3.1/local_installers/cuda_12.3.1_545.23.08_linux.run
sudo apt remove -y --purge "*nvidia*"
sudo apt install -y build-essential
sudo sh cuda_12.3.1_545.23.08_linux.run # select the option to use the NVIDIA drivers with X
rm cuda_12.3.1_545.23.08_linux.run

# install CuDNN
# download from https://developer.nvidia.com/rdp/cudnn-download
sudo dpkg -i cudnn-local-repo-ubuntu2004-8.9.7.29_1.0-1_amd64.deb
sudo cp /var/cudnn-local-repo-ubuntu2004-8.9.7.29/cudnn-local-30472A84-keyring.gpg /usr/share/keyrings/
sudo apt-get update
sudo apt-get install libcudnn8

# grab source
git clone https://github.com/kylemcdonald/i2i-realtime.git
cd i2i-realtime
```

If you are running natively:

```
sudo apt install python3.10 python3.10-dev python3.10-venv libturbojpeg
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If you are using Docker:

```
# install docker
sudo apt-get update
sudo apt-get install ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# install NVIDIA container toolkit
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
  && curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list \
  && \
    sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
sudo nvidia-ctk runtime configure --runtime=containerd
sudo systemctl restart containerd

# disable updates and notifications
gsettings set org.gnome.desktop.notifications show-banners false
sudo systemctl disable --now apt-daily{{,-upgrade}.service,{,-upgrade}.timer}
sudo systemctl disable --now unattended-upgrades
sudo systemctl daemon-reload
sudo systemctl stop unattended-upgrades
sudo systemctl mask unattended-upgrades
```

## Useful commands

Remove the cursor after 1 second (applied on reboot):

```
sudo apt-get install unclutter
```

Generate frames of images from a video:

```
mkdir -p data/frames && ffmpeg -i video.mp4 -vf fps=30 data/frames/%06d.jpg
```

## Running manually

The code has two parts: the server and the worker.

To run the worker, enable the virtual env and run the worker:

```
source .venv/bin/activate
python transform.py
```

To run the server, do the same:

```
source .venv/bin/activate
python app.py
```

Both the worker and server have flags that can be configured at the command line. There are also some flags that can be controlled using the .env file, with examples shown in .env.example. For example, when running the worker on a different computer from the server, you should specify the `--primary_hostname` of the server, or set that hostname in the .env so that the worker can communicate with the server.

If you have enabled prompt translation or safety checking, you will need to provide an OpenAI API key and a Google Service Account JSON file.

## Running automatically

To run the app automatically on boot, and to recover automatically from crashes, install systemd services.

Before doing this, make sure that the user has access to controlling systemctl, and for controlling shutdown:

```
bash install-polkit.sh
sudo usermod -aG sudo <username>
```

### Setting Keyboard shortcuts

Add a keyboard shortcut pointing to "/home/rzm/Documents/i2i-realtime/./shutdown.sh"

Add another keyboard shortcut pointing to "/home/rzm/Documents/i2i-realtime/./reload.sh"

Copy ssh keys from your server to all the workers so that they can be shutdown automatically over ssh (use the script in `automation/ssh-copy-ids.sh`).

```
bash install-worker-service.sh # install on all workers
bash install-server-service.sh # install on server only
```

To make it easy to adminster the installation, add a [custom keyboard shortcut](https://help.ubuntu.com/stable/ubuntu-help/keyboard-shortcuts-set.html.en).

* Add a shortcut for `Alt+Q` pointing to the absolute path of `shutdown.sh`. This will stop the app and all worker services and shutdown the server and all workers.
* Add a shortcut for `Alt+R` pointing to the absolute path of `reload.sh`. This will reload the app and all worker services.

## Controlling the parameters in realtime

The server exposes some parameters over FastAPI on port 5556.

A text-based controller example is available by running `input-publisher.py`. This streams keyboard input to the server.

Use chat-style commands: plain text or `/prompt` to update the prompt, and `/seed 123` to set the seed, etc.

Other useful commands include `/passthrough True` or `/passthrough False`.
