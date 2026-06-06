# UrlTrack

UrlTrack is a self-hosted link tracking platform built with Flask. It sits between a public link and its destination, giving you full control over who can access it and deep visibility into what happens after the click.

Unlike traditional link shorteners, UrlTrack focuses on context: it helps you understand who is interacting with your links, how, and why.

It is designed for controlled campaigns, demos, internal investigations, and analytical use cases where standard shorteners and basic trackers fall short.

## What UrlTrack does

At its core, UrlTrack sits between a public link and its destination.

A key design choice is the built-in anti-bot and anti-crawler system on both the domain and generated links. This makes the platform resistant to URL expanders and similar automated tools: UrlTrack can return a valid HTTP 200 response without ever exposing or resolving the real destination URL, effectively feeding false or empty information to automated systems.

In practice, this means the final destination remains hidden from many automated inspection tools while still allowing the link to behave normally for intended visitors.

## Anti-bot comparison

### UrlTrack behavior (HTTP 200, destination hidden)
![codice 200](our.png)

### Comparison with standard tools (final URL exposed)
![rivelano url finale](others.png)

## Main features

You can protect a link with:

- captcha
- password
- email capture
- country allowlist
- VPN blocking
- consent gate
- schedule windows

After the visitor passes those checks, UrlTrack records the visit and enriches it in the background. From the dashboard you can inspect individual campaigns, trace repeated visitors across links, view device profiles, and monitor leads that emerge from repeated visits.

Depending on configuration, tracking data can include:

- country and geolocation
- device and browser details
- fingerprint signals
- dwell time
- email capture
- VPN hints
- cross-visit correlations

## Why this project exists

Many URL shorteners hide useful statistics behind paid plans and often do not offer the level of flexibility or customization that advanced users need.

UrlTrack was created to address that gap: a self-hosted solution with deep tracking, strong customization potential, and room for further expansion.

It aims to provide a level of control and analytical depth comparable to platforms such as IPLogger or Grabify, while remaining fully customizable and under your own infrastructure.

## Quick start

If you want the least-friction local setup:

```bash
git clone https://github.com/MN-company/UrlTrack.git
cd UrlTrack
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
- on first boot use `http://127.0.0.1:8000/register`

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

If you do not want the installer flow:

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
DATABASE_URL=sqlite:///data/urltrack.db
```

## First run

On a clean database:

1. open `/register`
2. create the first owner account
3. name the initial workspace
4. optionally enable TOTP or passkeys from security settings
5. invite additional members from Team settings

Additional accounts are invite-only and receive a workspace role (`viewer`, `analyst`, `editor`, `admin`, or `owner`).

## Authentication

Local authentication works without external services. Supabase Auth is optional:

```env
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
```

When Supabase is configured, UrlTrack still creates a local user record for Flask sessions, TOTP, passkeys, and workspace membership. Without those variables, the same UI uses local password authentication.

## Main areas of the dashboard

### Home

Campaign summary, recent links, recent visits, and fast access to common actions.

### Campaigns

Per-link analytics page with visit charts, referrers, countries, engagement metrics, and a visit log.

### Graph

A visual graph connecting `canvas_hash`, visited slugs, and known emails.

### Leads

A lightweight lead view that groups repeated visits by fingerprint or email so you can inspect history in one place.

### AI Analyst

An assistant view that can reason over visits and search context using commands like `@visit:`, `@hash:`, `@link:`, `@ip:`, and `@email:`.

### Settings

Manage domain lists and workspace-specific Telegram/webhook integrations. Server-wide values such as `SERVER_URL`, Gemini, retention, proxy trust, and Supabase are controlled only through `.env`.

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

Telegram and webhook credentials entered in the dashboard are stored per workspace. Global `.env` notification values are used only for single-workspace installations.

### Team invites

SMTP is optional. Without SMTP, invite URLs are printed in the server log.

```env
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASS=
SMTP_FROM=
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

For Fly.io, `fly.toml` is already configured for auto-start and auto-stop machines. For plain Linux, use the systemd and nginx files in `deploy/` as starting points, not as magic one-click infrastructure.

## Useful commands

Run migrations:

```bash
SKIP_BACKGROUND_WORKER=1 ./venv/bin/python -m flask --app server:create_app db upgrade
```

Run tests:

```bash
pip install -r requirements-dev.txt
SKIP_BACKGROUND_WORKER=1 ./venv/bin/python -m pytest -q
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

Usually this means the wrong interpreter is being used or a stale process is still running. Use the repo venv explicitly:

```bash
pkill -f "flask --app server:create_app run" || true
./venv/bin/python -m flask --app server:create_app run --host=127.0.0.1 --port=8000
```

### `flask db` says command not found

Use the repo interpreter, not a global `flask` command:

```bash
./venv/bin/python -m flask --app server:create_app db upgrade
```

### Telegram alerts do not arrive

Check the bot token, chat id, and whether the bot has received at least one message from the target chat.

### Docker starts but shows warning from `requests`

If the app still migrates and Gunicorn comes up, that warning is noisy but not fatal. Check:

```bash
docker compose ps
docker compose logs --tail=200
```

## Final note

UrlTrack should be considered software for educational purposes.

It is not intended to identify any individual. The creator disclaims any responsibility connected to the proper or improper use of this tool.
