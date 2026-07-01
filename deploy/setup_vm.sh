#!/usr/bin/env bash
# One-time setup for a fresh Oracle Cloud "Always Free" Ubuntu VM.
# Run this after SSHing into the VM for the first time:
#   bash setup_vm.sh
set -euo pipefail

REPO_URL="https://github.com/Denisa26d/vesttest.git"
APP_DIR="$HOME/vesttest"

sudo apt-get update -y
sudo apt-get install -y python3 python3-venv python3-pip git

if [ -d "$APP_DIR" ]; then
    git -C "$APP_DIR" pull
else
    git clone "$REPO_URL" "$APP_DIR"
fi

cd "$APP_DIR"
python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt

if [ ! -f "$APP_DIR/.env" ]; then
    cp "$APP_DIR/deploy/.env.example" "$APP_DIR/.env"
    chmod 600 "$APP_DIR/.env"
    echo "Created $APP_DIR/.env — edit it now and fill in your real Telegram token/chat ID:"
    echo "  nano $APP_DIR/.env"
fi

CRON_LINE="*/10 * * * * $APP_DIR/deploy/run_monitor.sh >> $APP_DIR/monitor.log 2>&1"
( crontab -l 2>/dev/null | grep -v "run_monitor.sh" ; echo "$CRON_LINE" ) | crontab -

echo
echo "Done. Cron installed to run every 10 minutes."
echo "Next steps:"
echo "  1. nano $APP_DIR/.env   (fill in TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)"
echo "  2. bash $APP_DIR/deploy/run_monitor.sh   (test it manually once)"
echo "  3. tail -f $APP_DIR/monitor.log   (watch it work)"
