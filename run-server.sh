#!/bin/bash
sleep 60
cd "$(dirname "$0")"
source .venv/bin/activate
python app.py