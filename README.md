# UrlTrack V2

UrlTrack V2 is a self-hosted link intelligence platform for marketing teams that need fast redirects, visitor identification, identity graphs, flow-based link rules, webhook automation, and dashboard analytics.

This branch introduces the TypeScript monorepo requested for V2:

- `apps/api` - Fastify public API, redirect engine, ThumbmarkJS bounce page, OpenAPI docs at `/api/docs`
- `apps/dashboard` - Next.js App Router dashboard with Supabase Auth surfaces and React Flow link builder
- `packages/db` - Prisma schema and Supabase Postgres RLS migration
- `packages/worker` - BullMQ queues, identity matching, webhook signing and retry utilities
- `packages/shared` - shared validation, types and scoring defaults

## Local Setup

```bash
git clone https://github.com/MN-company/UrlTrack.git
cd UrlTrack
cp .env.example .env
corepack enable
pnpm install
pnpm db:migrate
pnpm dev
```

Open:

- Dashboard: `http://localhost:3000`
- API: `http://localhost:8000/health`
- OpenAPI docs: `http://localhost:8000/api/docs`

## Docker

```bash
cp .env.example .env
docker compose up --build
```

The compose stack starts `api`, `dashboard`, `worker`, and `redis`. Postgres is intentionally not included because UrlTrack V2 uses Supabase Postgres.

## Required Environment

```env
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
DATABASE_URL=
REDIS_URL=
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_API_URL=
BASE_DOMAIN=
VISIT_TOKEN_SECRET=
```

## Validation

```bash
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

## API Shape

Public API responses follow:

```json
{ "data": {}, "meta": { "page": 1, "per_page": 20, "total": 150 } }
```

Authentication accepts either `X-Api-Key` or a Supabase Bearer token plus `X-Workspace-Id`.

The redirect endpoint `GET /:slug` keeps redirect-side work minimal: it evaluates synchronous access rules, records a visit, serves a tiny ThumbmarkJS bounce page, and queues enrichment work through BullMQ.

## Webhooks

Outbound webhooks are signed with HMAC-SHA256:

```text
X-UrlTrack-Signature: sha256=<hash>
```

Retry timing is `30s`, `5min`, `30min`, `2h`, and `24h`. After the fifth failed attempt, the delivery is marked failed and the endpoint can be disabled by the worker.
