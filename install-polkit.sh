FN="/etc/polkit-1/localauthority/50-local.d/allow-systemctl-and-shutdown.pkla"

sudo tee "$FN" > /dev/null <<EOL
[Allow all users to start, stop services and power off the system]
Identity=unix-user:*
Action=org.freedesktop.systemd1.manage-units;org.freedesktop.login1.power-off
ResultActive=yes
ResultInactive=yes
ResultAny=yes
EOL

sudo systemctl restart polkit