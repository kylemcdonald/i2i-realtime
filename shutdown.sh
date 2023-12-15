#!/bin/bash
cd "$(dirname "$0")"
source .env
systemctl stop i2i-worker
ssh $OTHER_MACHINE "systemctl stop i2i-worker && shutdown now"
systemctl stop i2i-server
shutdown now