#!/bin/bash
sleep 60
cd "$(dirname "$0")"
source .venv/bin/activate
DISPLAY=:0 python app.py --mode camera --mirror --fullscreen