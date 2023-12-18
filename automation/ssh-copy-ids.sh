#!/usr/bin/bash

source ../.env

# generate ssh if it doesn't exist
if [ ! -f ~/.ssh/id_rsa.pub ]; then
    ssh-keygen -t rsa -N "" -f ~/.ssh/id_rsa
fi

# copy ssh to all workers
for worker in ${WORKER_MACHINES[@]}; do
    echo $worker
    ssh-copy-id -i ~/.ssh/id_rsa.pub $worker
done