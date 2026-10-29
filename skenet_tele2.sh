#!/usr/bin/env bash
# Tele2 cenu skenēšana no tava datora (Tele2 bloķē GitHub serverus).
# Ieplānošana (macOS/Linux): crontab -e  →  20 8,18 * * * /ceļš/uz/cenu-skeneris/skenet_tele2.sh
set -e
cd "$(dirname "$0")"
# export TG_TOKEN=123456:ABC...   # Telegram (neobligāti)
# export TG_CHAT=123456789
export OPERATORI=tele2
git pull --rebase --quiet origin main
python3 -m pip install --quiet -r requirements.txt
python3 scan.py || true
git add data
git commit --quiet -m "Tele2 cenas (lokāli)" && git push --quiet origin main || true
