#!/bin/bash
cd "$(dirname "$0")"
printenv > env.txt
systemctl stop i2i-worker