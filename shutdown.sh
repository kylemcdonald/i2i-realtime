#!/bin/bash
shutdown -r +1
systemctl stop i2i-worker
cd "$(dirname "$0")"
source .env
ssh $OTHER_MACHINE "systemctl stop i2i-worker && shutdown -r now"
systemctl stop i2i-server