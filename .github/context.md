# StreamForge — Full Project Context

## Project Overview

**StreamForge** is a web application that analyzes YouTube videos or playlists and provides direct downloadable streams in different quality formats.

The system consists of:

- React frontend (Vite)
- FastAPI backend
- yt-dlp extraction engine
- Azure VPS backend hosting
- Vercel frontend hosting

The architecture separates **UI and extraction logic** so that the browser only interacts with a lightweight API while heavy video processing happens on the server.

---

# System Architecture

```
User Browser
│
│
▼
Frontend (React + Vite)
Hosted on Vercel
https://streamforge.vercel.app

│
│ HTTP API
▼
Backend (FastAPI)
Azure Ubuntu VPS
http://4.193.226.56:8000

│
│
▼
yt-dlp + ffmpeg
YouTube extraction
```

---

# Core Idea

Instead of downloading videos server-side, the backend:

1. extracts **video stream URLs**
2. sends them to the frontend
3. the browser downloads directly from YouTube CDN

Advantages:

- no server bandwidth cost
- faster downloads
- minimal server load

---

# Technology Stack

## Frontend

```
React
Vite
Fetch API
Vanilla CSS (JS style objects)
```

## Backend

```
Python 3.12
FastAPI
Uvicorn
yt-dlp
ffmpeg
```

## Infrastructure

```
Frontend Hosting → Vercel
Backend Hosting → Azure VPS
OS → Ubuntu 24.04 LTS
```

---

# Repository Structure

```
streamforge/
│
├── frontend/
│ ├── src/
│ │ └── App.jsx
│ ├── index.html
│ └── package.json
│
├── backend/
│ ├── main.py
│ ├── downloader.py
│ └── requirements.txt
│
└── context.md
```

---

# Backend Architecture

## FastAPI Application

Main server file:

```
backend/main.py
```

Responsibilities:

- expose API endpoints
- handle request validation
- configure CORS
- call downloader logic

---

## API Routes

### Root

```
GET /
```

Response

```json
{
  "message": "StreamForge API running"
}
```

---

### Analyze Video

```
POST /analyze
```

Request

```json
{
  "url": "youtube link"
}
```

Response Types:

#### Video

```json
{
  "type": "video",
  "title": "",
  "thumbnail": "",
  "formats": []
}
```

#### Playlist

```json
{
  "type": "playlist",
  "title": "",
  "videos": []
}
```

---

# downloader.py

File:

```
backend/downloader.py
```

Responsible for:

- extracting metadata
- detecting playlists
- filtering formats
- returning usable stream URLs

Uses:

```
yt_dlp.YoutubeDL()
```

Important options:

```
skip_download=True
quiet=True
http_headers=user-agent
ignoreerrors=True
nocheckcertificate=True
```

---

# Video Format Filtering

Raw yt-dlp output contains many duplicate streams.

Filtering logic:

```
skip audio-only formats
skip duplicates
sort by resolution
```

Example returned format:

```json
{
  "quality": "1080p",
  "ext": "mp4",
  "url": "direct stream url",
  "filesize": 10000000
}
```

---

# Playlist Handling

If the video is a playlist:

```
info["_type"] == "playlist"
```

The backend returns a list of video entries:

```json
{
  "type": "playlist",
  "title": "",
  "videos": [
    {
      "title": "",
      "url": "youtube link"
    }
  ]
}
```

Frontend then analyzes each video separately when downloading.

---

# Frontend Architecture

Main UI file:

```
frontend/src/App.jsx
```

Core responsibilities:

```
URL input
API request
video player
format selector
download logic
playlist grid
```

---

# Frontend Environment Variables

```
VITE_API_URL
```

Example:

```
VITE_API_URL=http://4.193.226.56:8000
```

Used like:

```js
const API = import.meta.env.VITE_API_URL;
```

---

# Frontend UI Flow

### 1 User pastes YouTube link

Input field:

```
Paste YouTube URL
```

User clicks **Analyze**.

---

### 2 API request

Frontend sends:

```
POST /analyze
```

---

### 3 Backend returns formats

Frontend renders:

```
video player
quality selector
download button
```

---

# Video Player

HTML5 player:

```jsx
<video src={selectedFormat.url} controls />
```

This streams directly from YouTube.

# Smart Download System

Frontend creates a temporary link:

```js
const a = document.createElement("a");
a.href = streamUrl;
a.target = "_blank";
a.download = filename;
```

Advantages:

- no memory crash
- no buffering
- browser handles download

# Playlist UI

Playlist videos render in a grid:

- thumbnail
- title
- download button

Thumbnail source:

```
https://img.youtube.com/vi/VIDEO_ID/hqdefault.jpg
```

# Azure VPS Infrastructure

Backend is deployed on:

Microsoft Azure Virtual Machine

Specs:

```
OS: Ubuntu 24.04 LTS
CPU: 1 vCPU
RAM: 1GB
Public IP: 4.193.226.56
```

---

# Recent Changes (backend)

This repository has received a set of production-focused improvements and operational fixes. The list below summarizes the new features, stability work, and the root causes and fixes for issues encountered during testing on the Azure VM.

## Feature & operational highlights

- Health & monitoring:
  - `GET /health` returns `{"status":"ok"}` for quick probes.
  - Prometheus metrics are exposed at `GET /metrics` (using `prometheus-client`).

- Rate limiting & abuse protection:
  - `slowapi` integrated for per-IP rate limiting; environment-configurable via `RATE_LIMIT` and `DOWNLOAD_RATE`/`DOWNLOAD_DAILY`.
  - Example nginx config contains `limit_req` zone to protect the public endpoint.

- Extraction & downloader:
  - `downloader.py` supports `COOKIEFILE` for authenticated extraction and `PROXY_LIST` for proxy rotation.
  - Extraction attempts include retry/backoff to mitigate transient YouTube blocks.
  - `yt-dlp` configured with Deno JS runtime to support JS-challenged pages.

- Streaming & proxying:
  - New `/proxy` endpoint proxies manifests/segments for a small set of allowed hosts (`googlevideo.com`, `youtube.com`, `ytimg.com`) to avoid browser CORS issues.
  - Progressive formats (mp4/webm/mkv) are proxied with `Content-Disposition` set so browsers save files.
  - HLS/DASH manifests are streamed via `ffmpeg` into MP4 and piped to the client when required.

- Logging & diagnostics:
  - Structured JSON logs via `python-json-logger` and background capture of `ffmpeg` stderr (visible in `journalctl`) to debug mux/segment errors.

## Files added / updated

- `main.py` — FastAPI app with `/analyze`, `/download` (POST & GET wrapper), `/proxy`, `/health`, `/metrics`, CORS, `slowapi` and ffmpeg streaming logic.
- `downloader.py` — cookie support, proxy list, retries/backoff, improved logging.
- `requirements.txt` — added `slowapi`, `python-json-logger`, `prometheus-client`.
- `deploy/streamforge.service` — systemd unit template and drop-ins.
- `deploy/nginx_streamforge.conf` — nginx site with TLS and rate-limiting guidance.
- `deploy/refresh_cookies.py` — Playwright cookie refresh utility to generate `/home/streamforge/firefox-cookies.txt`.
- `DEPLOY.md` — deployment instructions.

These changes keep the server lightweight (no persistent large-media storage) while improving the production-readiness of extraction and streaming.

---

# Server Setup Steps (quick)

Install dependencies:

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv git ffmpeg
```

Create virtualenv and install requirements:

```bash
python3 -m venv /home/streamforge/venv
source /home/streamforge/venv/bin/activate
/home/streamforge/venv/bin/pip install -r /home/streamforge/streamforge-backend/requirements.txt
```

Deploy and run under systemd (drop-ins provided in `deploy/`):

```bash
sudo systemctl daemon-reload
sudo systemctl restart streamforge.service
sudo journalctl -u streamforge.service -f
```

Health checks:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/metrics
```

---

# Recent Bugs & How They Were Solved

This section documents notable issues encountered during integration tests and their fixes.

- Malformed AAC / tiny MP4 files:
  - Symptom: downloads produced very small MP4 files; `journalctl` showed ffmpeg messages like "Malformed AAC bitstream detected" and "Error muxing a packet".
  - Root cause: upstream HLS audio streams used ADTS framing that must be converted to MP4-friendly format.
  - Fix applied: add `-bsf:a aac_adtstoasc` to the ffmpeg command line. `ffmpeg` stderr is captured in logs to verify the fix.

- ffmpeg "Cannot reuse HTTP connection for different host":
  - Symptom: ffmpeg failed when playlist referenced segments on multiple googlevideo hosts.
  - Root cause: ffmpeg tried to reuse a single HTTP connection for chunks served from different hostnames.
  - Fix applied: set `-http_persistent 0` and a `-user_agent` value in the ffmpeg invocation so ffmpeg opens new connections per request and upstream behaves like a browser.

- Browser CORS blocking manifests/segments:
  - Symptom: browser could not load GoogleVideo manifests/segments directly (CORS preflight failures).
  - Fix applied: added `GET /proxy` to forward manifest/segment requests for a short allowlist of hosts; frontend rewrites manifest/segment URLs to use `/proxy` when necessary.

- Transient nginx 502 on backend restart:
  - Symptom: nginx returned 502 while uvicorn was restarting.
  - Root cause: backend unavailable during restart; nginx proxied while upstream was down.
  - Mitigation: restart carefully and watch `journalctl`; consider later adding healthcheck-aware reload/smarter socket activation.

---

# ffmpeg Hardening — applied & planned

Applied:

- `-bsf:a aac_adtstoasc` to convert ADTS AAC for MP4 muxing.
- `-http_persistent 0` to avoid cross-host HTTP connection reuse.
- `-user_agent "<browser UA>"` so upstream treats requests like a browser.
- Background logging of `ffmpeg` stderr for diagnostics.

Planned (follow-up):

- Add `-headers 'Connection: close\\r\\n'` to ffmpeg to force connection-close semantics when needed.
- Add a simple 1–2 attempt retry wrapper around the `ffmpeg` subprocess to recover from transient upstream network errors.

These hardening steps trade a small amount of TCP overhead for much higher reliability when streaming HLS/DASH manifests that reference multiple hosts.

---

# Current State (2026-03-09)

- The FastAPI app runs under systemd (`streamforge.service`) and responds to `/health`, `/analyze`, `/download` and `/proxy`.
- `downloader.py` uses `COOKIEFILE` when available and `yt-dlp` with Deno runtime where necessary.
- Frontend updated to open backend `/download` URLs in a new tab and to proxy manifest/segment requests through `/proxy` for allowed hosts.
- Rate limiting is in place via `slowapi` and the nginx template includes `limit_req` directives.

# Next steps & recommendations

1. Lock CORS to the production frontend origin (currently permissive for testing).
2. Consider adding the `Connection: close` header + ffmpeg retry wrapper if intermittent host-switch errors reappear.
3. Add persistent quota/store if daily download quotas are required (currently per-process limits via `slowapi`).
4. Configure nginx with TLS (see `deploy/nginx_streamforge.conf`) and point your domain to the VM; obtain certs with certbot.

If you want, I can implement (2) and deploy it, or help with nginx/TLS and setting `VITE_API_URL` in Vercel.

# StreamForge — Full Project Context

## Project Overview

**StreamForge** is a web application that analyzes YouTube videos or playlists and provides direct downloadable streams in different quality formats.

The system consists of:

- React frontend (Vite)
- FastAPI backend
- yt-dlp extraction engine
- Azure VPS backend hosting
- Vercel frontend hosting

The architecture separates **UI and extraction logic** so that the browser only interacts with a lightweight API while heavy video processing happens on the server.

---

# System Architecture

```
User Browser
│
│
▼
Frontend (React + Vite)
Hosted on Vercel
https://streamforge.vercel.app

│
│ HTTP API
▼
Backend (FastAPI)
Azure Ubuntu VPS
http://4.193.226.56:8000

│
│
▼
yt-dlp + ffmpeg
YouTube extraction
```

---

# Core Idea

Instead of downloading videos server-side, the backend:

1. extracts **video stream URLs**
2. sends them to the frontend
3. the browser downloads directly from YouTube CDN

Advantages:

- no server bandwidth cost
- faster downloads
- minimal server load

---

# Technology Stack

## Frontend

```
React
Vite
Fetch API
Vanilla CSS (JS style objects)
```

## Backend

```
Python 3.12
FastAPI
Uvicorn
yt-dlp
ffmpeg
```

## Infrastructure

```
Frontend Hosting → Vercel
Backend Hosting → Azure VPS
OS → Ubuntu 24.04 LTS
```

---

# Repository Structure

```
streamforge/
│
├── frontend/
│ ├── src/
│ │ └── App.jsx
│ ├── index.html
│ └── package.json
│
├── backend/
│ ├── main.py
│ ├── downloader.py
│ └── requirements.txt
│
└── context.md
```

---

# Backend Architecture

## FastAPI Application

Main server file:

```
backend/main.py
```

Responsibilities:

- expose API endpoints
- handle request validation
- configure CORS
- call downloader logic

---

## API Routes

### Root

```
GET /
```

Response

```json
{
  "message": "StreamForge API running"
}
```

---

### Analyze Video

```
POST /analyze
```

Request

```json
{
  "url": "youtube link"
}
```

Response Types:

#### Video

```json
{
  "type": "video",
  "title": "",
  "thumbnail": "",
  "formats": []
}
```

#### Playlist

```json
{
  "type": "playlist",
  "title": "",
  "videos": []
}
```

---

# downloader.py

File:

```
backend/downloader.py
```

Responsible for:

- extracting metadata
- detecting playlists
- filtering formats
- returning usable stream URLs

Uses:

```
yt_dlp.YoutubeDL()
```

Important options:

```
skip_download=True
quiet=True
http_headers=user-agent
ignoreerrors=True
nocheckcertificate=True
```

---

# Video Format Filtering

Raw yt-dlp output contains many duplicate streams.

Filtering logic:

```
skip audio-only formats
skip duplicates
sort by resolution
```

Example returned format:

```json
{
  "quality": "1080p",
  "ext": "mp4",
  "url": "direct stream url",
  "filesize": 10000000
}
```

---

# Playlist Handling

If the video is a playlist:

```
info["_type"] == "playlist"
```

The backend returns a list of video entries:

```json
{
  "type": "playlist",
  "title": "",
  "videos": [
    {
      "title": "",
      "url": "youtube link"
    }
  ]
}
```

Frontend then analyzes each video separately when downloading.

---

# Frontend Architecture

Main UI file:

```
frontend/src/App.jsx
```

Core responsibilities:

```
URL input
API request
video player
format selector
download logic
playlist grid
```

---

# Frontend Environment Variables

```
VITE_API_URL
```

Example:

```
VITE_API_URL=http://4.193.226.56:8000
```

Used like:

```js
const API = import.meta.env.VITE_API_URL;
```

---

# Frontend UI Flow

### 1 User pastes YouTube link

Input field:

```
Paste YouTube URL
```

User clicks **Analyze**.

---

### 2 API request

Frontend sends:

```
POST /analyze
```

---

### 3 Backend returns formats

Frontend renders:

```
video player
quality selector
download button
```

---

# Video Player

HTML5 player:

```jsx
<video src={selectedFormat.url} controls />
```

This streams directly from YouTube.

# Smart Download System

Frontend creates a temporary link:

```js
const a = document.createElement("a");
a.href = streamUrl;
a.target = "_blank";
a.download = filename;
```

Advantages:

- no memory crash
- no buffering
- browser handles download

# Playlist UI

Playlist videos render in a grid:

- thumbnail
- title
- download button

Thumbnail source:

```
https://img.youtube.com/vi/VIDEO_ID/hqdefault.jpg
```

# Azure VPS Infrastructure

Backend is deployed on:

Microsoft Azure Virtual Machine

Specs:

---

# Recent Changes (backend)

This project recently received several incremental, production-focused improvements to make the backend more robust and monitorable while keeping it lightweight.

- Health and metrics:
  - Added a lightweight health endpoint: `GET /health` (returns {"status":"ok"}).
  - Mounted Prometheus metrics at `GET /metrics` using `prometheus-client`.

- Rate limiting and abuse protection:
  - Integrated `slowapi` for in-process rate limiting. Default limits are configurable via the `RATE_LIMIT` environment variable and the `@limiter.limit` decorator protects `/analyze`.
  - Added nginx `limit_req` directives in the provided nginx template for an additional layer of protection.

- Logging and diagnostics:
  - Structured JSON logging via `python-json-logger` for easier ingestion into log systems and debugging.
  - `downloader.py` now emits informative logs about cookie/proxy usage and retry attempts.

- Resiliency and extraction improvements:
  - `downloader.py` now supports optional environment-driven configuration:
    - `COOKIEFILE` — path to `cookies.txt` to use authenticated extraction with yt-dlp.
    - `PROXY_LIST` — comma-separated list of proxies to rotate when extracting.
  - Extraction uses a retry/backoff loop (3 attempts) to mitigate transient YouTube blocking.

- Deployment and operations:
  - Added a systemd unit template (`deploy/streamforge.service`) and an example env drop-in (`deploy/streamforge.env`).
  - Added an nginx site template with rate-limiting and a recommendation to proxy `/metrics` only from localhost.
  - New `DEPLOY.md` contains step-by-step deploy instructions for Ubuntu 24.04 (systemd, nginx, certbot, ufw).

Files added/modified (backend):

- `main.py` — added `/health`, mounted `/metrics` (Prometheus ASGI), JSON logging, and `slowapi` rate limiting.
- `downloader.py` — supports `COOKIEFILE` and `PROXY_LIST`, adds retries/backoff and logging.
- `requirements.txt` — added `slowapi`, `python-json-logger`, and `prometheus-client`.
- `deploy/streamforge.service` — systemd unit template.
- `deploy/nginx_streamforge.conf` — nginx proxy + rate-limiting template.
- `deploy/streamforge.env` — example EnvironmentFile drop-in.
- `DEPLOY.md` — deployment guide with systemd env drop-in instructions.

These changes follow the project rules: keep the backend lightweight, avoid server-side downloads, and prefer incremental operational improvements.

```
OS: Ubuntu 24.04 LTS
CPU: 1 vCPU
RAM: 1GB
Public IP: 4.193.226.56
```

## Server Setup Steps

Install dependencies

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv git ffmpeg
```

Create virtual environment

```bash
python3 -m venv streamforge-env
```

Activate

```bash
source streamforge-env/bin/activate
```

Install backend dependencies

```bash
pip install fastapi uvicorn yt-dlp
```

Clone project

```bash
git clone https://github.com/najat-ttt/streamforge.git
```

Run backend

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Server becomes available at:

```
http://4.193.226.56:8000
```

Docs:

```
http://4.193.226.56:8000/docs
```

# Frontend Deployment

Platform:

```
Vercel
```

Deployment workflow:

```
push to github
↓
vercel auto builds
↓
frontend deployed
```

# Development Workflow

Local development:

```
edit code locally
git commit
git push
```

Frontend:

```
auto deploy via vercel
```

Backend update:

```
ssh to VPS
cd streamforge
git pull
restart backend
```

# Current System Status

Working:

- YouTube video analysis
- format extraction
- playlist detection
- direct stream downloads
- frontend UI
- backend API
- Azure VPS backend
- Vercel frontend

# Known Issues

## yt-dlp bot detection

Some videos require:

```
cookies.txt
```

Possible fix:

```
browser cookies export
```

## Backend persistence

Server currently runs manually.

If SSH closes, server stops.

Better solutions:

- systemd service
- pm2
- docker

## No HTTPS

Backend uses IP instead of domain.

Future improvement:

- nginx reverse proxy
- SSL
- domain

# Planned Improvements

## Infrastructure

- systemd service
- nginx reverse proxy
- https
- domain
- docker container

## Backend

- queue workers
- rate limiting
- redis caching
- stream proxy
- cookie authentication

## Frontend

- progress bars
- download manager
- drag and drop
- UI redesign
- mobile support

# Instructions For AI Agents (Copilot / LLM)

When modifying this project:

- Backend logic lives in `backend/`
- Frontend logic lives in `frontend/`
- API base URL comes from `VITE_API_URL`
- Video streams come directly from yt-dlp extraction
- Do NOT implement server-side video downloads unless necessary
- Keep the architecture stateless and lightweight

# Project Goal

Build a modern web-based YouTube downloader similar to:

- SnapTube
- SaveFrom
- Y2Mate

But with:

- modern UI
- lightweight backend
- cloud deployment

# Maintainer

```
Sheikh Siam Najat
CSE Student
RUET
```

# Current Stage

```
Functional MVP
Cloud deployed
Actively under development
```

---

## Deployment Log — Actions, Errors & Solutions

- Actions performed:
  - Added `GET /health`, Prometheus metrics at `GET /metrics`, JSON logging, and `slowapi` rate limiting.
  - Updated `downloader.py` to support `COOKIEFILE`, `PROXY_LIST`, retry/backoff, and improved logging.
  - Added deploy templates: `deploy/streamforge.service`, `deploy/nginx_streamforge.conf`, `deploy/streamforge.env.example`, and `DEPLOY.md`.
  - Created and pushed branch `feat/deploy-systemd-nginx` with the above changes.
  - Provisioned an Azure VM (public IP 4.193.226.56), created `streamforge` user, cloned the repo, created a virtualenv, and attempted to install and run the service.

- Errors encountered and their solutions:
  - **ModuleNotFoundError: No module named 'prometheus_client'**
    - Cause: the VM virtualenv was installed before `prometheus-client` (and other new packages) were added to `requirements.txt`.
    - Solution: install the updated requirements into the app venv as the `streamforge` user, for example:

      sudo -u streamforge /home/streamforge/venv/bin/pip install -r /home/streamforge/streamforge-backend/requirements.txt

      then run:

      sudo systemctl daemon-reload
      sudo systemctl restart streamforge.service

  - **Git permission / branch checkout issues**
    - Cause: repository ownership and `safe.directory` configuration prevented `git fetch`/`checkout` as the `streamforge` user.
    - Solution: set `git config --global --add safe.directory /home/streamforge/streamforge-backend` and/or temporarily fix ownership (`chown`) so the `streamforge` user can checkout the feature branch.

  - **Cookies / file transfer confusion**
    - Cause: `cookies.txt` was transferred via Cloud Shell and initially not placed under `/home/streamforge` with correct ownership/permissions.
    - Solution: securely copy `cookies.txt` to the VM, then `chown streamforge:streamforge /home/streamforge/cookies.txt` and `chmod 600 /home/streamforge/cookies.txt`.

  - **systemd service repeatedly restarting**
    - Cause: missing dependencies (see prometheus_client error) caused the process to crash and systemd to restart it.
    - Solution: install required Python packages into the venv, inspect `journalctl -u streamforge.service -l` for traces, then restart the service.

## Current State (2026-03-07)

- Code:
  - Backend changes (health, metrics, logging, rate-limiting, downloader improvements) are committed on branch `feat/deploy-systemd-nginx` and pushed to the remote.

- VM / runtime:
  - Azure VM `streamforge-vps` exists and is reachable at 4.193.226.56.
  - `streamforge` system user created; virtualenv created at `/home/streamforge/venv`.
  - Repository cloned and feature branch checked out on the VM.
  - Initial Python packages were installed earlier, but the updated `requirements.txt` (including `prometheus-client`, `slowapi`, `python-json-logger`) has not yet been fully installed into the VM venv.
  - Systemd unit was installed and started but the service is failing due to the missing `prometheus_client` dependency (blocking further smoke tests).

- Next recommended steps (blocking items):
  1. Install updated Python dependencies into the app virtualenv as the `streamforge` user:

     sudo -u streamforge /home/streamforge/venv/bin/pip install -r /home/streamforge/streamforge-backend/requirements.txt

  2. Reload systemd and restart the service:

     sudo systemctl daemon-reload
     sudo systemctl restart streamforge.service

  3. Verify service and endpoints:

     curl http://127.0.0.1:8000/health
     curl http://127.0.0.1:8000/metrics

  4. If service is healthy, configure nginx from `deploy/nginx_streamforge.conf` and obtain TLS certs via certbot.

If any step fails, gather `journalctl -u streamforge.service -l` and the venv pip install output for troubleshooting.

---

# Recent Operations Log — 2026-03-08

Summary of operational work performed and fixes applied since the previous snapshot above. These items were applied to the repository and the Azure VM during the March 8, 2026 deployment/debugging session.

- Playwright-based cookie refresh automation:
  - Added `deploy/refresh_cookies.py` — non-locking Playwright flow that reads Firefox `cookies.sqlite`, normalizes expiry values, imports cookies into a temporary Playwright context, navigates YouTube with retries/wait_until networkidle, and exports a Netscape-format cookie file at `/home/streamforge/firefox-cookies.txt` for `yt-dlp`.
  - Fixed cookie expiry validation (convert floats/strings to int, use `-1` for session cookies) so `context.add_cookies()` no longer fails.
  - Fallback: `refresh_cookies.py` writes a fallback netscape file directly from `cookies.sqlite` immediately and the script will exit 0 if fallback exists even when Playwright navigation fails.

- Systemd integration and scheduling:
  - Added and iteratively hardened `deploy/ytcookies-refresh.service` and `deploy/ytcookies-refresh.timer` (service runs as `streamforge`, sets `XDG_RUNTIME_DIR=/run/user/110`, uses temporary profile, and uses `Restart=on-failure` in production after initial `Restart=no` debugging runs).
  - Enabled user linger for `streamforge` so systemd user services have `/run/user/<uid>` available.
  - Verified the timer runs and `ytcookies-refresh.service` now exits cleanly while creating `/home/streamforge/firefox-cookies.txt`.

- Playwright issues encountered and mitigations:
  - Symptoms: navigation timeouts, "profile in use/newer version" errors, sandbox warnings, and occasional IPC EPIPE errors.
  - Fixes: use a temporary Playwright profile (no locking of the real profile), increase timeouts and use `wait_until='networkidle'`, add retry/backoff, and normalize cookie `expires` values. Also added robust logging to `/home/streamforge/playwright-refresh.log`.

- Monitoring, rotation, and healthchecks:
  - Added `deploy/logrotate-streamforge-playwright` and documented installation so Playwright logs are rotated daily.
  - Added healthcheck tooling: `deploy/check-ytcookies.sh`, `deploy/check-ytcookies.service`, and `deploy/check-ytcookies.timer` to run daily and alert when `/home/streamforge/firefox-cookies.txt` is missing or stale.
  - Healthcheck supports `WEBHOOK_URL` (JSON POST) and `MAILTO` (local `mail`); for this deployment we used webhook.site for quick webhook testing and confirmed POST payloads.

- Documentation and operator notes:
  - Updated `deploy/README_PLAYWRIGHT.md` with install, testing, and permission steps for Playwright, systemd, logrotate, and healthcheck configuration.

- Functional verification:
  - Manually ran `refresh_cookies.py` as user `streamforge` (with `XDG_RUNTIME_DIR=/run/user/110`) and confirmed `/home/streamforge/firefox-cookies.txt` is created.
  - Verified `yt-dlp` can perform an authenticated download using the exported cookies (sample run succeeded; formats downloaded and merged via ffmpeg).

- Notes and outstanding items:
  - Postfix was initially installed during `mailutils` install but no `main.cf` was configured; healthcheck uses webhook by default to avoid depending on local MTA. If email delivery is desired, configure Postfix relay or use mail-sending API.
  - Continue to monitor timers for 24h to ensure stability; adjust timeouts or fallback behavior if transient YouTube changes cause navigation failures.

These operational changes were committed under the `deploy/` directory and tested on the Azure VM. See the `deploy/` files for exact unit/timer names and paths.

---

# Next steps to connect backend ↔ frontend

1. Ensure the backend is running locally on the VM (systemd or `uvicorn`) and `GET /health` returns 200:

```bash
sudo systemctl status streamforge.service || true
curl -sS http://127.0.0.1:8000/health
```

2. Point the frontend to the backend API:

- Locally: set `VITE_API_URL` when running the frontend dev server, or edit `.env` before building.
- Vercel: set the `VITE_API_URL` environment variable in your Vercel project to `http://4.193.226.56:8000` (or your domain) and redeploy.

3. Test an end-to-end analyze request from the frontend or with `curl`:

```bash
curl -X POST -H 'Content-Type: application/json' -d '{"url":"https://www.youtube.com/watch?v=<ID>"}' http://4.193.226.56:8000/analyze
```

4. If the frontend cannot access the backend from the browser (CORS/network issues), confirm nginx is configured (if used), port forwarding, and CORS settings in FastAPI.

5. Monitor logs and metrics:

- `journalctl -u streamforge.service -f`
- `/home/streamforge/playwright-refresh.log`
- Prometheus metrics at `/metrics` (if enabled)

If you want, I can now help you: (A) start the backend service on the VM and verify `/health`, (B) set `VITE_API_URL` on Vercel for the frontend, or (C) run an end-to-end analyze test from the VM. Which should I do next?
