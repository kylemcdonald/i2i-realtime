#!/usr/bin/bash

cd ..
source .env
pwd=$(pwd)
cp_command="rsync ${PRIMARY_HOSTNAME}:$pwd/.env ."
dir=$(pwd)
for worker in ${WORKER_MACHINES[@]}; do
    echo $worker
    ssh -t "$worker" "cd $dir && \
        WORKER_ID_LINE=\$(grep 'WORKER_ID' .env) && \
        $cp_command && \
        sed -i \"s/WORKER_ID=.*/\${WORKER_ID_LINE}/g\" .env"
done