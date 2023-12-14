#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
HF_HOME=/home/rzm/.cache python transform.py