# UrlTrack

UrlTrack is a self-hosted link tracking app built with Flask. You create a link, decide who should get through, and watch what happens after the click: country, device, fingerprint signals, dwell time, email capture, VPN hints, and cross-visit correlations. It is meant for controlled campaigns, demos, internal investigations, and anyone who wants more context than a normal shortener gives.

This repo is the current `v2` line of UrlTrack. It includes the dashboard, public gate pages, background enrichment worker, Telegram alerts, AI analyst, Docker support, and first-run admin setup.

## What UrlTrack does

At its core, UrlTrack sits between a public link and its destination.

You can protect a link with:

- captcha
- password
- email capture
- country allowlist
- VPN blocking
- consent gate
- schedule windows

After the visitor passes those checks, UrlTrack records the visit and enriches it in the background. From the dashboard you can inspect individual campaigns, trace repeated visitors across links, view device profiles, and keep an eye on leads that emerge from repeated visits.

## Why this project exists

Most trackers either feel too light or too invasive. UrlTrack aims for a middle ground: clear operator controls, useful telemetry, a dashboard that helps you reason about visits, and deployment options simple enough to run on your own infrastructure.

If you searched for **UrlTrack**, this is the main repository for the Flask-based self-hosted version.

## Quick start

If you want least-friction local setup:

```bash
git clone https://github.com/MN-company/UrlTrack.git
cd UrlTrack
git checkout v2
./install.sh --run
```

That command will:

- create `.env` if missing
- generate a strong `SECRET_KEY`
- create `venv/`
- install Python dependencies
- run database migrations
- start the local server

Then open:

- `http://127.0.0.1:8000/`
- first boot will send you to `http://127.0.0.1:8000/setup`

## Docker mode

If you prefer to run UrlTrack with Docker instead of a local Python environment:

```bash
./install.sh --docker --run
```

That mode prepares `.env`, keeps SQLite data in `server/data/`, and starts the stack with `docker compose up --build`.

If you want Docker without starting immediately:

```bash
./install.sh --docker
docker compose up --build
```

The container runs Alembic migrations on boot and then starts Gunicorn on port `8000`.

## Manual setup

If you do not want installer flow:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r server/requirements.txt
cp .env.example .env
SKIP_BACKGROUND_WORKER=1 ./venv/bin/python -m flask --app server:create_app db upgrade
./run.sh
```

At minimum, `.env` should contain:

```env
SECRET_KEY=replace-me
SERVER_URL=http://127.0.0.1:8000
DATABASE_URL=sqlite:///data/ulrtrack.db
```

## First run

On a clean database:

1. open `/setup`
2. create first admin account
3. save the one-time admin secret shown after setup
4. sign in to dashboard
5. optionally enable TOTP or passkeys from security settings

That one-time admin secret is only for future admin creation. It is not part of normal login.

## Main areas of dashboard

### Home

Campaign summary, recent links, recent visits, fast access to common actions.

### Campaigns

Per-link analytics page with visit charts, referrers, countries, engagement metrics, and visit log.

### Graph

A visual graph connecting `canvas_hash`, visited slugs, and known emails.

### Leads

A lightweight lead view that groups repeated visits by fingerprint or email so you can inspect history in one place.

### AI Analyst

An assistant view that can reason over visits and search context using commands like `@visit:`, `@hash:`, `@link:`, `@ip:`, and `@email:`.

### Settings

Manage runtime values, domain lists, Telegram credentials, AI model settings, and other operational toggles.

## Optional integrations

None of these are mandatory for basic tracking.

### Gemini

Used by AI Analyst.

Add to `.env`:

```env
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.0-flash
```

If `GEMINI_API_KEY` is empty, AI features stay visible but generation is effectively disabled.

### Telegram

Used for visit notifications and digests.

1. create a bot with `@BotFather`
2. send at least one message to the bot
3. call:

```text
https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
```

4. copy the chat id into `.env`

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

### Cloudflare Turnstile

Used only if you enable captcha gate on links.

```env
TURNSTILE_SITE_KEY=
TURNSTILE_SECRET_KEY=
```

### is.gd

Optional masking for public links when `MASK_WITH_ISGD=true`. No API key required.

## Docker, Fly.io, Linux deploy

This repo includes deploy assets for a few different styles:

- `Dockerfile`
- `docker-compose.yml`
- `fly.toml`
- `deploy/nginx/ulrtrack.conf`
- `deploy/systemd/ulrtrack.service`
- `deploy/fail2ban/...`

For Fly.io, `fly.toml` is already configured for auto-start and auto-stop machines. For plain Linux, use the systemd and nginx files in `deploy/` as starting point, not as magic one-click infra.

## Useful commands

Run migrations:

```bash
SKIP_BACKGROUND_WORKER=1 ./venv/bin/python -m flask --app server:create_app db upgrade
```

Create another admin from CLI:

```bash
python -m server.create_admin
```

Run local server with repo interpreter:

```bash
./venv/bin/python -m flask --app server:create_app run --host=127.0.0.1 --port=8000
```

## Repo structure

- `server/` Flask app, routes, models, worker, templates, static assets
- `migrations/` Alembic revisions
- `deploy/` nginx, fail2ban, systemd, helper scripts
- `tests/` pytest suite

## Troubleshooting

### Root returns 404 or wrong app boots

Usually wrong interpreter or stale process. Use repo venv explicitly:

```bash
pkill -f "flask --app server:create_app run" || true
./venv/bin/python -m flask --app server:create_app run --host=127.0.0.1 --port=8000
```

### `flask db` says command not found

Use repo interpreter, not global `flask`:

```bash
./venv/bin/python -m flask --app server:create_app db upgrade
```

### Telegram alerts do not arrive

Check bot token, chat id, and whether bot has received at least one message from target chat.

### Docker starts but shows warning from `requests`

If app still migrates and Gunicorn comes up, that warning is noisy but not fatal. Check:

```bash
docker compose ps
docker compose logs --tail=200
```

## Final note

UrlTrack is opinionated software. It is meant to be run deliberately, with clear ownership and clear intent. If that matches how you work, this repo should feel straightforward once it is up.
