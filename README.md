# UrlTrack

**Turn every link into a fast, protected intelligence layer.**

UrlTrack is a self-hosted link intelligence platform built for teams that want
more control than a traditional shortener can offer. Create protected links,
route trusted visitors, filter unwanted traffic, connect identities across
campaigns, and turn every interaction into useful operational context.

Everything runs on infrastructure you control, with no artificial limits on
campaigns and no dependency on a third-party analytics dashboard.

**[Open the interactive website](https://mn-company.github.io/UrlTrack/)**

## Highlights

- **GhostRedirect** routes rejected traffic to a safe URL without revealing the
  protected destination
- **GateFlow** combines password, CAPTCHA, email, consent, country, VPN, and
  scheduling rules
- **SignalGraph** connects fingerprints, links, devices, and known emails
  across campaigns
- **LeadPulse** surfaces repeat visitors and builds a reviewable activity
  history
- **RiskLens** scores traffic and highlights visits that deserve attention
- **AI Analyst** explores campaign data using natural-language, scoped queries
- **LiveRelay** delivers events through Telegram, email, and signed webhooks
- **TeamSpaces** keeps campaigns separated with invitations and role-based
  permissions
- **DataPort** exports campaign intelligence in CSV, JSON, and PDF

## Speed without blind spots

**FastPath** keeps the public redirect flow lean while enrichment runs in the
background. Visitors move through the required checks without waiting for
scoring, notifications, or external integrations to finish.

- fast server-rendered pages with minimal browser overhead
- asynchronous enrichment, scoring, and notifications
- local caching for frequently accessed intelligence
- external services kept outside the critical redirect path
- one-command startup with Python or Docker

## How it works

```mermaid
flowchart LR
    A["Visitor opens the link"] --> B["Bot and request checks"]
    B --> C{"Access gates"}
    C -->|Passed| D["Record visit immediately"]
    C -->|Rejected| E["Stop / GhostRedirect to safe URL"]
    D --> F["Fast redirect"]
    D -.-> G["Background enrichment"]
    G --> H["Scoring and notifications"]
```

GhostRedirect keeps the protected destination out of the rejected flow.
Automated scanners and visitors that do not pass GateFlow can be stopped or
routed to a harmless fallback URL, while eligible traffic continues through
FastPath.

### GhostRedirect comparison

| GhostRedirect | Typical URL inspection tool |
| --- | --- |
| ![GhostRedirect keeps the protected destination private](our.png) | ![Comparison tools expose the final destination](others.png) |

The exact result depends on the client and configuration; this is a defensive
layer rather than a guarantee against every crawler.

## Demo

### Campaign Command Center

Monitor campaign health, identity confidence, risk, interceptions, and active
links from one operational view.

![UrlTrack Campaign Command Center](demo-dashboard.png)

### GateFlow Studio

Build visual routing flows with triggers, conditions, access gates, splits,
GhostRedirect destinations, and real-time notifications.

![UrlTrack GateFlow Studio](demo-flow-studio.png)

## Quick start

### Installer

The fastest way to run UrlTrack locally is:

```bash
git clone https://github.com/MN-company/UrlTrack.git
cd UrlTrack
./install.sh --run
```

The installer creates `.env` when needed, generates a secret key, prepares a
virtual environment, installs dependencies, applies migrations, and starts the
application.

Open [http://127.0.0.1:8000](http://127.0.0.1:8000), then create the first
owner account at `/register`.

### Docker Compose

```bash
git clone https://github.com/MN-company/UrlTrack.git
cd UrlTrack
./install.sh --docker --run
```

To prepare the environment without starting it immediately:

```bash
./install.sh --docker
docker compose up --build
```

The container applies Alembic migrations on boot and runs Gunicorn on port
`8000`. SQLite data is persisted in `server/data/`.

### Manual installation

Requirements:

- Python 3
- `pip` and `venv`
- a supported SQLAlchemy database; SQLite is the default

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r server/requirements.txt
cp .env.example .env
SKIP_BACKGROUND_WORKER=1 python -m flask --app server:create_app db upgrade
./run.sh
```

Minimal configuration:

```env
SECRET_KEY=replace-with-a-long-random-value
SERVER_URL=http://127.0.0.1:8000
DATABASE_URL=sqlite:///data/urltrack.db
```

## First-run checklist

1. Open `/register` and create the first owner.
2. Name the initial workspace.
3. Create a link and choose the gates required for its audience.
4. Confirm that `SERVER_URL` matches the public base URL.
5. Enable TOTP or register a passkey from Security settings.
6. Configure retention, proxy trust, and integrations before production use.

Further users join by invitation. Workspace roles are `viewer`, `analyst`,
`editor`, `admin`, and `owner`.

## Connected by design

UrlTrack works as a standalone application, but its most useful integrations
are built directly into the normal campaign workflow.

### Supabase Core

Connect Supabase to add managed authentication while preserving UrlTrack's
local sessions, workspaces, roles, passkeys, and security settings. Teams can
start with local accounts and introduce Supabase when the installation grows,
without changing how campaigns and analytics are organized.

### Provider-ready AI Analyst

The AI Analyst turns campaign data into a searchable operational view. It can
reason over visits, links, fingerprints, IP addresses, emails, and leads using
scoped references, while streaming responses directly in the interface.

The analysis layer is designed to remain separate from tracking and can be
extended to different model providers. Gemini support is included out of the
box, and AI remains completely optional: links and analytics continue to work
when no model is configured.

### LiveRelay notifications

```mermaid
flowchart LR
    A["New visit"] --> B["Background worker"]
    B --> C["Telegram alert"]
    B --> D["Signed webhook"]
    B --> E["Email workflow"]
    C --> F["Your team"]
    D --> G["CRM or automation"]
    E --> F
```

- **Telegram** delivers real-time visit alerts and campaign updates.
- **Email via SMTP** handles team invitations and collaborative workflows.
- **Signed webhooks** forward events to CRMs, internal tools, or automation
  platforms.

Integrations can be configured per workspace, allowing separate teams to use
their own destinations and credentials. None of them are required for the core
redirect and analytics flow.

## Project status

UrlTrack is under active development. The core redirect, gating, analytics,
workspace, lead, export, and authentication flows are present, while advanced
correlation and AI-assisted features should be treated as experimental. Data
models and configuration may change between releases until a stable versioning
policy is introduced.

Current areas of work include:

- improving documentation and deployment examples
- expanding automated coverage for dashboard workflows
- refining visitor scoring and identity correlation
- making privacy and retention controls easier to audit
- improving observability for background enrichment jobs

This section is intentionally a direction rather than a release promise.

## Troubleshooting

### The wrong application starts or `/` returns an unexpected response

Use the repository virtual environment explicitly and stop stale development
processes:

```bash
pkill -f "flask --app server:create_app run" || true
./venv/bin/python -m flask --app server:create_app run --host=127.0.0.1 --port=8000
```

### `flask db` reports that the command does not exist

```bash
./venv/bin/python -m flask --app server:create_app db upgrade
```

### Telegram notifications do not arrive

Check that the bot token and chat ID are correct and that the target chat has
sent at least one message to the bot.

### Docker starts with dependency warnings

Check whether migrations completed and Gunicorn started successfully:

```bash
docker compose ps
docker compose logs --tail=200
```

## Responsible use

UrlTrack is provided for educational, research, and legitimate analytics use.
It is not designed to establish a person's real-world identity, bypass consent,
or facilitate harassment, surveillance, credential collection, or unauthorized
access. Operators are responsible for informing visitors where required,
collecting valid consent, minimizing retained data, and securing their
deployment.

## License

Distributed under the terms in [LICENSE](LICENSE).
