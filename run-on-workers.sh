#!/usr/bin/bash

command=$1
dir=$(pwd)
source .env
for worker in ${WORKER_MACHINES[@]}; do
    echo $worker
    # run command after cd to dir
    ssh -t $worker "cd $dir && $command"
done