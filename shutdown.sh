#!/bin/bash
cd "$(dirname "$0")"
printenv > env.txt
systemctl stop i2i-worker
source .env
ssh $OTHER_MACHINE "systemctl stop i2i-worker && shutdown -r now"
systemctl stop i2i-server
shutdown -r now