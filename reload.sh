#!/bin/bash
cd "$(dirname "$0")"
source .env
./run-on-workers.sh "systemctl stop i2i-worker"
systemctl stop i2i-server
sleep 5
./run-on-workers.sh "systemctl start i2i-worker"
systemctl start i2i-server