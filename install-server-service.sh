SERVICE_ID=i2i-server
SERVICE_NAME="i2i-server"
SCRIPT_NAME="run-server.sh"

# do not edit below this line

USER=$(whoami)
SERVICES_DIR=/etc/systemd/system
SERVICE_FN="$SERVICES_DIR/$SERVICE_ID.service"

echo "Installing $SERVICE_NAME to $SERVICE_FN"

sudo tee "$SERVICE_FN" > /dev/null <<EOL
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

sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_ID
sudo systemctl start $SERVICE_ID