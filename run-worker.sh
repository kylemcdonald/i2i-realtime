#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
python worker_app.py