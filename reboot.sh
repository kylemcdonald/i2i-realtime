#!/bin/bash
cd "$(dirname "$0")"
source .env
systemctl stop i2i-worker
ssh $OTHER_MACHINE "systemctl stop i2i-worker"
systemctl stop i2i-server
sleep 5
systemctl start i2i-worker
ssh $OTHER_MACHINE "systemctl start i2i-worker"
systemctl start i2i-server