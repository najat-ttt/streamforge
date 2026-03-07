#!/usr/bin/env bash
set -euo pipefail

echo "== Install Deno and Chromium for streamforge =="

if [ "$(id -u)" -ne 0 ]; then
  echo "This script should be run as root or via sudo. Exiting." >&2
  exit 1
fi

STREAMFORGE_HOME=/home/streamforge

# Install Deno for the streamforge user
echo "Installing Deno for user 'streamforge'..."
sudo -u streamforge bash -lc 'curl -fsSL https://deno.land/install.sh | sh'

# Create systemd drop-in to expose Deno and the venv to the service
echo "Creating systemd drop-in to add Deno to PATH..."
mkdir -p /etc/systemd/system/streamforge.service.d
cat > /etc/systemd/system/streamforge.service.d/deno-path.conf <<'EOF'
[Service]
Environment=PATH=/home/streamforge/.deno/bin:/home/streamforge/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin
EOF

echo "Reloading systemd and restarting streamforge.service..."
systemctl daemon-reload
if systemctl list-units --full -all | grep -q streamforge.service; then
  systemctl restart streamforge.service || true
fi

echo "Installing Chromium (APT package)..."
apt-get update
apt-get install -y chromium || apt-get install -y chromium-browser || true

echo "Preparing Chromium profile directory..."
mkdir -p "$STREAMFORGE_HOME/chrome-profile"
chown -R streamforge:streamforge "$STREAMFORGE_HOME/chrome-profile"

cat > /tmp/install_deno_chromium_note.txt <<'NOTE'
Done.

Next steps (interactive sign-in):

1) Sign in to Chromium on the VM using the dedicated profile. Example:

   chromium --remote-debugging-port=9222 --user-data-dir=/home/streamforge/chrome-profile

   or if the command is 'chromium-browser' on your distro, use that instead.

2) From your desktop, you can forward or open the remote debugging port (9222) and sign in.

3) After signing in, run yt-dlp preferring browser cookies:

   /home/streamforge/venv/bin/yt-dlp --cookies-from-browser chromium --js-runtimes deno 'https://www.youtube.com/watch?v=VIDEO_ID'

Security note: keep the profile and any cookie files owned by 'streamforge' and mode 600.

If you want, I'll help with the remote-debugging sign-in step after you run this script.
NOTE

cat /tmp/install_deno_chromium_note.txt

echo "Install script finished."
