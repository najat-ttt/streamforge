# StreamForge Backend - Deployment Guide

This file contains step-by-step instructions to deploy the `streamforge-backend` FastAPI app on an Ubuntu 24.04 VM. It covers creating a dedicated user, virtualenv, systemd unit, nginx reverse proxy, firewall rules, and obtaining TLS via Let's Encrypt.

Files added in `deploy/`:

- [streamforge.service](deploy/streamforge.service) — systemd unit template
- [nginx_streamforge.conf](deploy/nginx_streamforge.conf) — nginx site config template

Before you begin: ensure you have SSH access to the VM and sudo privileges.

1. Create a dedicated system user and clone the repo

```bash
sudo adduser --system --group --no-create-home streamforge
sudo mkdir -p /home/streamforge
sudo chown $USER:streamforge /home/streamforge
cd /home/streamforge
git clone https://github.com/<your-org>/streamforge-backend.git streamforge-backend
cd streamforge-backend
```

2. Create a Python virtual environment and install dependencies

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip build-essential ffmpeg
python3 -m venv /home/streamforge/venv
source /home/streamforge/venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate
```

3. Configure the systemd service

- Copy the template to systemd and edit paths/user as needed:

```bash
sudo cp deploy/streamforge.service /etc/systemd/system/streamforge.service
sudo nano /etc/systemd/system/streamforge.service
# Update WorkingDirectory, Environment PATH, User to match your VM
```

Start and enable the service:

````bash
sudo systemctl daemon-reload
sudo systemctl enable --now streamforge.service
sudo systemctl status streamforge.service

3.1 Use an environment drop-in for secrets and environment variables

It's recommended to keep sensitive values (cookie files, proxy lists) out of the main unit file. Use a systemd drop-in or an EnvironmentFile.

Example drop-in placement and commands:

```bash
# Copy the example env template to /etc/default and edit values
sudo cp deploy/streamforge.env /etc/default/streamforge
sudo nano /etc/default/streamforge

# Create systemd unit drop-in directory and reference the EnvironmentFile
sudo mkdir -p /etc/systemd/system/streamforge.service.d
sudo tee /etc/systemd/system/streamforge.service.d/env.conf > /dev/null <<'EOF'
[Service]
EnvironmentFile=/etc/default/streamforge
EOF

# Reload systemd and restart
sudo systemctl daemon-reload
sudo systemctl restart streamforge.service
sudo systemctl status streamforge.service
````

Notes on `COOKIEFILE` and `PROXY_LIST`:

- Place `cookies.txt` in a secure path (owned by the `streamforge` user) and set `COOKIEFILE=/home/streamforge/cookies.txt` in `/etc/default/streamforge`.
- Set `PROXY_LIST` to a comma-separated list of trusted proxies only. Keep this file readable only by the service user.
- Ensure file permissions: `sudo chown streamforge:streamforge /home/streamforge/cookies.txt && sudo chmod 600 /home/streamforge/cookies.txt`.

If you prefer not to use `/etc/default`, you can set `Environment="VAR=value"` lines directly in the `env.conf` drop-in.

````

4. Install and configure nginx

```bash
sudo apt install -y nginx
sudo cp deploy/nginx_streamforge.conf /etc/nginx/sites-available/streamforge
sudo ln -s /etc/nginx/sites-available/streamforge /etc/nginx/sites-enabled/streamforge
sudo nginx -t
sudo systemctl restart nginx
````

Edit `/etc/nginx/sites-available/streamforge` and set `server_name` to your domain or VM public IP.

5. Open firewall ports (ufw)

```bash
sudo apt install -y ufw
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

6. Obtain TLS certificate with Certbot (Let's Encrypt)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your.domain.com
# Follow prompts; certbot will update the nginx config and reload nginx
```

7. Verify health check and API

```bash
curl -I https://your.domain.com/health
curl -s https://your.domain.com/analyze -X POST -H "Content-Type: application/json" -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```

8. Optional hardening and notes

- Consider running `uvicorn` under a process manager like `gunicorn` with `uvicorn.workers.UvicornWorker` for more robust worker management on higher traffic.
- Add rate limiting (nginx or upstream) if public usage is expected.
- Use environment variables for configuration (API keys, optional cookiefile path). Add them to the systemd unit using `Environment=` or a drop-in env file.
- If yt-dlp triggers bot detection often, add cookie support: upload `cookies.txt` to the server and set `cookiefile` in `downloader.py` optionally behind a configuration flag.

If you want, I can apply a small change to `downloader.py` to make `cookiefile` path and proxy-list configurable via environment variables, and add sample systemd drop-in demonstrating `EnvironmentFile` usage.
