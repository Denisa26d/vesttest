#!/usr/bin/env bash
# Wrapper cron calls every 10 minutes: loads secrets from .env, pulls the
# latest config/keyword tuning from git, runs the monitor. seen.json lives
# only on this VM's disk (gitignored) since the process is long-running,
# not ephemeral like a GitHub Actions runner — no git push needed for it.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"

set -a
source "$APP_DIR/.env"
set +a

git pull --quiet
.venv/bin/python monitor.py
