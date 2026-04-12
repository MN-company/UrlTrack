# UrlTrack

UrlTrack is a self-hosted Flask platform for controlled link routing, visit analytics, fingerprint correlation, and operator alerts. It can gate access with consent, email, password, captcha, geo and VPN checks, then record browser and network telemetry for later investigation in the dashboard.

## Current feature set

- Link routing with per-link controls for captcha, password, email capture, bot blocking, VPN blocking, country allowlists, scheduling, mobile targeting, safe fallback URLs, and click limits
- Visit analytics with IP, hostname, geography, device type, OS family, browser signals, canvas fingerprint, ETag, dwell time, and referrer data
- Device investigation pages keyed by `canvas_hash` or `etag`
- Global graph view that correlates `canvas_hash -> slug -> email`
- AI analyst console with `@visit:`, `@hash:`, `@link:`, `@ip:`, and `@email:` shortcuts
- First-run admin bootstrap with email/password plus optional TOTP and passkeys
- Background enrichment worker with optional Telegram alerts for each enriched visit
- Deployment assets for Docker, Compose, nginx, fail2ban, systemd, and Fly.io

## Repository layout

- `server/` Flask application, models, routes, worker, templates, static assets
- `migrations/` Alembic revisions
- `deploy/` nginx, fail2ban, systemd, and bootstrap scripts
- `Dockerfile`, `docker-compose.yml`, `fly.toml` deployment entrypoints

## Quickstart

### 1. Clone and install

```bash
git clone https://github.com/MN-company/UrlTrack.git
cd UrlTrack
git checkout v2
python3 -m venv venv
source venv/bin/activate
pip install -r server/requirements.txt
```

### 2. Create `.env`

```bash
cp .env.example .env
```

At minimum set:

```env
SECRET_KEY=replace-with-long-random-secret
SERVER_URL=http://127.0.0.1:8000
DATABASE_URL=sqlite:///data/ulrtrack.db
```

### 3. Run migrations

```bash
SKIP_BACKGROUND_WORKER=1 ./venv/bin/python -m flask --app server:create_app db upgrade
```

### 4. Run locally

```bash
./run.sh
```

Then open:

- `http://127.0.0.1:8000/`
- first boot will redirect to `http://127.0.0.1:8000/setup`

## First-run admin setup

1. Open `/setup`
2. Create first admin with email and password
3. Store generated server secret code shown once after setup
4. Login to dashboard
5. Optionally enable TOTP and register passkeys from Security settings

That server secret is only for creating more admins later. It is not used for normal login.

## Environment variables

### Required

- `SECRET_KEY`
- `SERVER_URL`
- `DATABASE_URL`

### Core runtime

- `ANONYMIZE_IP`
- `VISIT_RETENTION_DAYS`
- `TRUST_PROXY_HEADERS`
- `MASK_WITH_ISGD`
- `REQUIRE_VISIT_TOKEN`
- `VISIT_TOKEN_TTL_SECONDS`
- `SKIP_BACKGROUND_WORKER`

### Public gate behavior

- `REQUIRE_CONSENT`
- `ALLOW_PARTIAL_EMAIL_CAPTURE`
- `CONSENT_TTL_DAYS`
- `TURNSTILE_SITE_KEY`
- `TURNSTILE_SECRET_KEY`

### AI

- `GEMINI_API_KEY`
- `GEMINI_MODEL`

### Telegram alerts

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

### Rate limiting and abuse controls

- `RATE_LIMIT_REDIRECT`
- `RATE_LIMIT_AUTH`
- `MALICIOUS_IP_REFRESH_SECONDS`
- `MALICIOUS_IP_MIN_COUNT`

## External integrations and API setup

### 1. Gemini API for AI Analyst

Used for:

- AI console answers
- visit and graph-oriented context lookups
- streaming responses in dashboard AI view

Setup:

1. Go to Google AI Studio
2. Create or copy an API key
3. Put it in `.env`:

```env
GEMINI_API_KEY=your-key
GEMINI_MODEL=gemini-2.0-flash
```

Notes:

- If `GEMINI_API_KEY` is empty, AI routes stay available but generation should be treated as disabled
- Model name is runtime-configurable from dashboard settings

### 2. Cloudflare Turnstile for captcha gate

Used for:

- captcha-protected public link visits
- `captcha.html` verification flow

Setup:

1. Create a Turnstile site in Cloudflare dashboard
2. Add your local or production domain
3. Copy site key and secret key into `.env`

```env
TURNSTILE_SITE_KEY=your-site-key
TURNSTILE_SECRET_KEY=your-secret-key
```

Notes:

- If either value is empty, captcha-protected links cannot validate challenges
- CSP already allows Turnstile script and frame origins

### 3. Telegram Bot API for native visit alerts

Used for:

- real-time notification each time worker finishes `enrich_visit`

Message includes:

- slug
- city and country
- email if known
- device and OS
- VPN status
- timestamp

Setup:

1. Open Telegram and message `@BotFather`
2. Run `/newbot`
3. Create bot name and username
4. Copy bot token into `.env`

```env
TELEGRAM_BOT_TOKEN=123456:ABCDEF...
```

5. Get target chat ID

Private chat method:

1. Start a conversation with your bot
2. Send at least one message to bot
3. Open:

`https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`

4. Read `message.chat.id`
5. Put it in `.env`

```env
TELEGRAM_CHAT_ID=123456789
```

Group method:

1. Add bot to group
2. Send one message in group
3. Call `getUpdates`
4. Use group chat id, often negative, for example `-100xxxxxxxxxx`

Notes:

- If either `TELEGRAM_BOT_TOKEN` or `TELEGRAM_CHAT_ID` is empty, Telegram alerts are disabled
- Delivery happens in a daemon thread after visit enrichment, so worker queue is not blocked by Telegram latency

### 4. is.gd public masking

Used for:

- optional public short masking when `MASK_WITH_ISGD=true`

Setup:

- no API key required
- toggle from dashboard settings or `.env`

Notes:

- masking is best-effort
- failures do not block link creation

### 5. IP geolocation and malicious IP feeds

Used for:

- `ip-api.com` geolocation lookup during enrichment
- GitHub-hosted malicious IP list refresh

Setup:

- no local credentials required in current implementation

Notes:

- these are network-dependent
- if lookup fails, visit is still recorded and worker continues

## Dashboard areas

### Command Center

- recent links
- recent visits
- top-level activity summary

### Campaign analytics

Per-slug stats page includes:

- 7-day visit chart
- top countries
- top referrers
- visit log
- average engagement from `dwell_ms`
- engaged visit count where dwell time is greater than 5 seconds

### Global Intel

- search across slug, IP, email, fingerprint, city, country, org, hostname
- cross-visit timeline
- graph view for `canvas_hash -> slug -> email`

### Settings

Settings page now manages:

- domain deny lists for disposable and privacy email providers
- runtime values written into `.env`
- live runtime refresh for values that do not require restart

Editable from dashboard:

- `GEMINI_API_KEY`
- `GEMINI_MODEL`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `MASK_WITH_ISGD`
- `TRUST_PROXY_HEADERS`
- `VISIT_RETENTION_DAYS`

`SERVER_URL` is written to `.env` but restart is required.

## Public request flow

For each visit:

1. Resolve slug to link
2. Create initial `Visit` row
3. Sign visit token for browser callbacks
4. Apply consent, geo, bot, VPN, captcha, password, and email checks
5. Serve `loading.html`
6. Browser posts beacon data
7. Browser posts dwell time through `/api/dwell`
8. Redirect to final destination
9. Worker enriches visit
10. Worker optionally sends Telegram notification

## Database and migrations

Schema is controlled by Flask-Migrate and Alembic only.

Common commands:

```bash
SKIP_BACKGROUND_WORKER=1 ./venv/bin/python -m flask --app server:create_app db upgrade
SKIP_BACKGROUND_WORKER=1 ./venv/bin/python -m flask --app server:create_app db migrate -m "describe change"
```

Current manual follow-up revision for engagement tracking:

- `migrations/versions/f2b6c0a33d21_add_dwell_ms.py`

## Docker

### Start

```bash
docker compose down --remove-orphans
docker compose up --build
```

Compose mounts:

- local `./server/data`
- container `/app/server/data`

Compose also forces:

```env
DATABASE_URL=sqlite:////app/server/data/ulrtrack.db
```

This keeps SQLite on mounted storage.

Container boot command:

```bash
SKIP_BACKGROUND_WORKER=1 python -m flask --app server:create_app db upgrade && gunicorn --bind 0.0.0.0:8000 --workers 1 server.wsgi:app
```

`--workers 1` is intentional because SQLite does not behave well with multiple write-heavy workers.

## Linux deployment

Reference files:

- `deploy/nginx/ulrtrack.conf`
- `deploy/fail2ban/ulrtrack.conf`
- `deploy/fail2ban/filter.d/ulrtrack-auth.conf`
- `deploy/fail2ban/filter.d/ulrtrack-scan.conf`
- `deploy/systemd/ulrtrack.service`
- `deploy/scripts/setup.sh`

Suggested sequence:

1. Clone repo to `/opt/ulrtrack`
2. Create `.env`
3. Install venv and requirements
4. Run migration upgrade
5. Enable systemd service
6. Reload nginx and fail2ban

## CLI helpers

Create additional admin from CLI:

```bash
python -m server.create_admin
```

If `which flask` points outside `venv`, always prefer:

```bash
./venv/bin/python -m flask --app server:create_app <command>
```

## Troubleshooting

### `/` returns 404 but `/setup` works

You are probably running stale process or wrong interpreter. Restart with repo venv:

```bash
pkill -f "flask --app server:create_app run" || true
./venv/bin/python -m flask --app server:create_app run --host=127.0.0.1 --port=8000
```

### Docker shows `RequestsDependencyWarning`

That warning is noisy but not fatal if container continues to:

- run Alembic upgrade
- start Gunicorn
- listen on `0.0.0.0:8000`

Check with:

```bash
docker compose ps
docker compose logs --tail=200
```

### Telegram alerts do not arrive

Check:

1. `TELEGRAM_BOT_TOKEN` correct
2. `TELEGRAM_CHAT_ID` correct
3. bot has already received at least one message from target chat
4. worker is running

## License

Use according to repository owner policy.
