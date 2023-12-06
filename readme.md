# Realtime i2i for Rhizomatiks

Images are sent and received in the following format:

```json
{
    "index": <Integer>,
    "data": <String>
}
``````

Where `index` is the frame index and `data` is a base 64-encoded byte string.

Example setup:

```
$ mkdir -p data/frames && ffmpeg -i video.mp4 -vf fps=15 data/frames/%04d.jpg
$ sudo apt install python3.10-venv
$ python3 -m venv venv
$ source venv/bin/activate
$ pip3 install -r requirements.txt
$ python stream-images.py --input_folder data/frames --fps 15 --port 5555 &
$ python show-stream.py --port 5555 &
$ python transform.py --input_port 5555 --prompt_port 5556 --output_port 5557 &
$ python show-stream.py --port 5557 &
$ python input-publisher.py --port 5556
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

Streams keyboard input to the transform.py app on port 5556.