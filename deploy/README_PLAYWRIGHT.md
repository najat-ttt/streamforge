# Playwright cookie-refresh for streamforge

## What this does

- Provides a small Playwright script that opens Firefox with the existing
  profile directory so session cookies are refreshed automatically.
- Includes a helper install script and systemd unit/timer templates you can
  copy to `/etc/systemd/system` and enable.

## Files added

- `refresh_cookies.py` — Python Playwright script (run as `streamforge`).
- `install_playwright.sh` — Installs system deps and Playwright into the venv.
- `ytcookies-refresh.service` — systemd unit template (copy to `/etc/systemd/system`).
- `ytcookies-refresh.timer` — systemd timer template (copy to `/etc/systemd/system`).

## Install and enable (run as root)

1. Install system deps and Playwright in the existing venv:

```bash
sudo bash /home/streamforge/deploy/install_playwright.sh
```

2. Copy systemd unit/timer to `/etc/systemd/system` and enable

```bash
sudo cp /home/streamforge/deploy/ytcookies-refresh.service /etc/systemd/system/
sudo cp /home/streamforge/deploy/ytcookies-refresh.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ytcookies-refresh.timer
```

3. Ensure the `streamforge` user can run headful browsers when no one is logged in.
   Enable linger so user services can run without an active login session:

```bash
sudo loginctl enable-linger streamforge
```

4. Manual test run (as root):

```bash
sudo -u streamforge /home/streamforge/venv/bin/python /home/streamforge/deploy/refresh_cookies.py
tail -n 200 /home/streamforge/playwright-refresh.log
```

## Notes

- The script uses the existing Firefox profile at `/home/streamforge/.mozilla/firefox/streamforge-profile`.
- If you changed profile location, update `PROFILE_DIR` at the top of `refresh_cookies.py`.
- If YouTube forces interactive login (password change / 2FA), manual intervention is required.
