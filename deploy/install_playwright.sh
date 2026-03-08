#!/usr/bin/env bash
set -euo pipefail

# Install system dependencies and Playwright into the existing venv.
# Run this as root on the VM.

apt update
apt install -y --no-install-recommends \
  ca-certificates curl gnupg libgtk-3-0 libx11-xcb1 libdbus-1-3 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libasound2 \
  libpangocairo-1.0-0 libnss3 libatk-bridge2.0-0 libdrm2 libxtst6 libxss1

if [ ! -x /home/streamforge/venv/bin/pip ]; then
  echo "Virtualenv pip not found at /home/streamforge/venv/bin/pip" >&2
  exit 2
fi

sudo -u streamforge /home/streamforge/venv/bin/pip install "playwright>=1.40.0"
sudo -u streamforge /home/streamforge/venv/bin/python -m playwright install firefox

echo "Playwright and Firefox installed into /home/streamforge/venv." 
echo "If running without a user session you may need: sudo loginctl enable-linger streamforge"
