#!/bin/bash
echo "Waiting to start..."
sleep 30
echo "Done waiting, starting..."
cd "$(dirname "$0")"
source .venv/bin/activate
DISPLAY=:0 python app.py