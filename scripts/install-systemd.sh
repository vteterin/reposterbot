#!/usr/bin/env bash
# Install reposterbot as a systemd service.
# Assumes repo checked out at /home/ubuntu/Workspaces/reposterbot with .env populated.

set -euo pipefail

REPO_DIR="/home/ubuntu/Workspaces/reposterbot"
UNIT="/etc/systemd/system/reposterbot.service"

if [ ! -f "$REPO_DIR/.env" ]; then
    echo "Missing $REPO_DIR/.env — copy .env.example and fill it in first." >&2
    exit 1
fi

sudo tee "$UNIT" > /dev/null <<EOF
[Unit]
Description=Reposterbot (wholesale → retail crossposter)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$REPO_DIR
EnvironmentFile=$REPO_DIR/.env
ExecStart=/usr/bin/python3 -m src.bot
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable reposterbot
sudo systemctl restart reposterbot
sudo systemctl status reposterbot --no-pager
