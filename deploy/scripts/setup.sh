#!/bin/bash
set -euo pipefail

APP_DIR=/opt/ulrtrack
USER_NAME=ulrtrack

sudo useradd --system --create-home --shell /bin/bash "$USER_NAME" || true
sudo mkdir -p "$APP_DIR"
sudo chown -R "$USER_NAME":"$USER_NAME" "$APP_DIR"

python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --upgrade pip
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/server/requirements.txt"

sudo cp deploy/nginx/ulrtrack.conf /etc/nginx/sites-available/ulrtrack.conf
sudo ln -sf /etc/nginx/sites-available/ulrtrack.conf /etc/nginx/sites-enabled/ulrtrack.conf

sudo cp deploy/fail2ban/filter.d/ulrtrack-auth.conf /etc/fail2ban/filter.d/ulrtrack-auth.conf
sudo cp deploy/fail2ban/filter.d/ulrtrack-scan.conf /etc/fail2ban/filter.d/ulrtrack-scan.conf
sudo cp deploy/fail2ban/ulrtrack.conf /etc/fail2ban/jail.d/ulrtrack.conf

sudo cp deploy/systemd/ulrtrack.service /etc/systemd/system/ulrtrack.service
sudo systemctl daemon-reload
sudo systemctl enable ulrtrack

echo "Setup files installed. Review /opt/ulrtrack/.env, then run:"
echo "  sudo systemctl restart ulrtrack"
echo "  sudo systemctl reload nginx"
echo "  sudo systemctl restart fail2ban"
