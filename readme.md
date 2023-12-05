# Realtime i2i for Rhizomatiks

## stream-images.py

Reads a folder from disk and streams it over the specified port at the specified fps.

By default, loads from ../frames at 15 fps to port 5555.

Does not encode or decode image files, just sends the image file in the format:

```
{
    "index": <Integer>,
    "data": <String>
}
``````

Where "data" is a base64-encoded byte string.

## show-stream.py

Displays the streaming JPEG files streaming to the specified port.

## transform.py

Transforms the images received on port 5555 and returns them on port 5557.

Receives prompts and other commands as strings on port 5556.

## input-publisher.py

Streams keyboard input to the transform.py app on port 5556.