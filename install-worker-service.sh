SERVICE_ID=i2i-worker
SERVICE_NAME="i2i-worker"
SCRIPT_NAME="run-worker.sh"

# do not edit below this line

USER=$(whoami)
SERVICES_DIR=/etc/systemd/system/

cat >$SERVICES_DIR/$SERVICE_ID.service <<EOL
[Unit]
Description=$SERVICE_NAME
Wants=network-online.target
After=network-online.target
[Service]
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/$SCRIPT_NAME
User=$USER
Restart=always
[Install]
WantedBy=multi-user.target
EOL

systemctl daemon-reload

systemctl enable $SERVICE_ID
systemctl start $SERVICE_ID