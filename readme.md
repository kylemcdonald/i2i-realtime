# Realtime i2i for Rhizomatiks

Images are sent and received as a msgpack-encoded list: [timestamp, index, jpg].

* timestamp (int) is the time in milliseconds since Unix epoch. Useful for estimating overall latency.
* index (int) is the frame index.
* jpg (byte buffer) is a libturbo-jpeg encoded JPG of the image.

## Setup

Example setup:

```
mkdir -p data/frames && ffmpeg -i video.mp4 -vf fps=15 data/frames/%04d.jpg
sudo apt install python3.10 python3.10-dev python3.10-venv libturbojpeg
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python stream-images.py --input_folder data/frames --fps 15 --port 5555 &
python show-stream.py --port 5555 &
python transform.py --input_port 5555 --settings_port 5556 --output_port 5557 &
python show-stream.py --port 5557 &
python input-publisher.py --port 8000
```

## `stream-images.py`

Reads a folder from disk and streams it over the specified port at the specified fps.

By default, loads from ../frames at 15 fps to port 5555.

Does not encode or decode image files, just sends the image file buffer.

## `show-stream.py`

Displays the JPEG files streaming to the specified port.

## `transform.py`

Transforms the images received on port 5555 and returns them on port 5557.

Receives prompts and other commands as strings on port 5556.

## `input-publisher.py`

Streams keyboard input to the transform.py Settings subscriber app on port 5556.

Chat-style commands: plain text or `/prompt` to update the prompt, and `/seed 123` to set the seed, etc.