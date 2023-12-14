#!/bin/bash
echo "Waiting to start..."
sleep 300
echo "Done waiting, starting..."
cd "$(dirname "$0")"
source .venv/bin/activate
DISPLAY=:0 python app.py --mode camera --mirror --fullscreen