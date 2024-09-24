#!/bin/bash
echo "Waiting to start..."
sleep 30
echo "Done waiting, starting..."
cd "$(dirname "$0")"
# source .venv/bin/activate
DISPLAY=:0 $HOME/anaconda3/envs/i2i/bin/python server_app.py