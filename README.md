# UrlTrack

UrlTrack is a self-hosted traffic routing and visit analytics platform. It shortens or fronts links, applies access gates such as email, password, captcha, country and VPN checks, and records visit telemetry for later analysis in the dashboard.

## Features

- Link routing with per-link controls for email gate, password, captcha, country allowlist, VPN blocking, bot blocking, safe URL fallback, mobile targeting, scheduling, and click limits
- Visit analytics with IP, geography, device, browser, fingerprint, ETag, and referrer data
- Fingerprint-centric investigation pages through the dashboard device profile
- AI analyst console over links and visits with `@visit:`, `@hash:`, `@link:`, `@ip:`, and `@email:` shortcuts
- Admin authentication with email and password, optional TOTP, optional passkeys, and first-run bootstrap
- Deployment assets for `nginx`, `fail2ban`, `systemd`, Docker, Compose, and Fly.io

## Quickstart

### 1. Clone and install

```bash
git clone https://github.com/MN-company/UrlTrack.git
cd UrlTrack
python3 -m venv venv
source venv/bin/activate
pip install -r server/requirements.txt
```

### 2. Configure environment

Copy `.env.example` to `.env` and fill in at least:

```bash
SECRET_KEY=replace-this
SERVER_URL=http://127.0.0.1:8000
DATABASE_URL=sqlite:///data/ulrtrack.db
```

Optional integrations:

- `GEMINI_API_KEY` enables the AI analyst
- `TURNSTILE_SITE_KEY` and `TURNSTILE_SECRET_KEY` enable captcha gates

### 3. Initialize the database

```bash
export FLASK_APP=server:create_app
SKIP_BACKGROUND_WORKER=1 python -m flask --app server:create_app db upgrade
```

### 4. Run locally

```bash
./run.sh
```

Visit [http://127.0.0.1:8000/setup](http://127.0.0.1:8000/setup) on first start to create the first admin account. The setup flow will generate a server secret code and show it once. Keep it safe: it is required later when creating additional admin accounts.

## Authentication

- Login identity is the admin email address
- Passwords must be at least 12 characters
- TOTP can be enabled from the dashboard security page
- Passkeys can be registered after login and can also be used during the second step of login
- The server secret code is only for creating admins, not for normal login

## Public Flow

For each incoming visit UrlTrack:

1. Resolves the link by slug
2. Applies optional consent, schedule, geo, bot, VPN, and rate-limit checks
3. Enforces optional captcha, password, and email gates
4. Records the visit and queues background enrichment
5. Serves the loading page, gathers browser telemetry, then redirects to the final destination

## Database and Migrations

Schema changes are managed only through Flask-Migrate. The app no longer performs runtime `ALTER TABLE` operations.

Useful commands:

```bash
export FLASK_APP=server:create_app
SKIP_BACKGROUND_WORKER=1 python -m flask --app server:create_app db upgrade
SKIP_BACKGROUND_WORKER=1 python -m flask --app server:create_app db migrate -m "describe change"
```

## Deployment

### Docker

```bash
docker compose up --build
```

The Docker image runs:

```bash
SKIP_BACKGROUND_WORKER=1 python -m flask --app server:create_app db upgrade && gunicorn --bind 0.0.0.0:8000 --workers 1 server.wsgi:app
```

`--workers 1` is intentional for SQLite deployments because multiple Gunicorn workers writing to the same SQLite database can introduce lock contention and inconsistent behavior.

### Linux service stack

Deployment examples are included in:

- `deploy/nginx/ulrtrack.conf`
- `deploy/fail2ban/ulrtrack.conf`
- `deploy/fail2ban/filter.d/ulrtrack-auth.conf`
- `deploy/fail2ban/filter.d/ulrtrack-scan.conf`
- `deploy/systemd/ulrtrack.service`
- `deploy/scripts/setup.sh`

## Notes

- Environment variables are deployment-owned and are not edited from the dashboard
- Domain deny lists for disposable and privacy email providers are managed from dashboard settings and stored under `server/data/`
- If you need to create an admin from the CLI, use `python -m server.create_admin`
- If `which flask` points outside `venv`, use `python -m flask` or `./venv/bin/python -m flask` to force correct interpreter
