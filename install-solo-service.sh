SERVICE_ID=i2i-solo
SERVICE_NAME="i2i-solo"
SCRIPT_NAME="run-solo.sh"

# do not edit below this line

USER=$(whoami)
SERVICES_DIR=/etc/systemd/system
SERVICE_FN="$SERVICES_DIR/$SERVICE_ID.service"

echo "Installing $SERVICE_NAME to $SERVICE_FN"

sudo tee "$SERVICE_FN" > /dev/null <<EOL
[Unit]
Description=$SERVICE_NAME
After=network-online.target
Wants=network-online.target
[Service]
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/$SCRIPT_NAME
TimeoutStopSec=5s
User=$USER
Restart=always
[Install]
WantedBy=multi-user.target
EOL

sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_ID
sudo systemctl start $SERVICE_ID