#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
DISPLAY=:0 python solo_app.py