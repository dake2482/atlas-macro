# Atlas Macro

Atlas Macro is a clean-room macro-research and AI supply-chain intelligence
platform. It reproduces the useful information architecture and analytical
workflows of a dense research terminal while using original presentation,
first-party calculations, traceable upstream sources, and explicit data-quality
labels. It does **not** copy protected pages, private APIs, proprietary reports,
or restricted datasets from another site.

The application is a Django 5.2 server-rendered site backed by PostgreSQL. Celery
and Redis run scheduled ingestion, validation, and snapshot publication. ECharts
and lightweight browser JavaScript provide the interactive charts and filters.

## Included product areas

- Daily thesis, evidence, invalidation conditions, triggers, regime ledger, and
  paginated daily reports.
- Cross-asset, rates, Federal Reserve, liquidity, economy, volatility, credit,
  positioning, options, and crypto-derivatives dashboards.
- Searchable news, research mentions, fund letters, and glossary entries. Only
  metadata, links, and original summaries are stored for third-party material.
- AI supply-chain map and graph, company profiles, model and coding-agent
  rankings, GitHub application radar, and glossary.
- Component-level provenance, observation timestamps, quality/fallback states,
  dynamic sitemap, robots policy, light/dark themes, and PWA offline fallback.

The offline seed command creates the full product-shape baseline: 45 supply-chain
nodes, 219 companies, 12 model profiles, 11 coding-agent profiles, 45 GitHub
projects, and 32 glossary terms. Seed values are illustrative and visibly
labelled; they are not current investment data.

## Quick start with Docker

Requirements: Docker Engine with Compose v2.

```bash
cp .env.example .env
docker compose build
docker compose up -d db redis
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py seed_platform
docker compose up -d
```

Open <http://localhost>. The admin is at <http://localhost/admin/>. Create its
first user with:

```bash
docker compose run --rm web python manage.py createsuperuser
```

Useful operational commands:

```bash
docker compose ps
docker compose logs -f web worker beat
docker compose exec web python manage.py check --deploy
docker compose exec web python manage.py seed_platform
docker compose down
```

`seed_platform` is idempotent, so it is safe to run again after an upgrade. Data
in PostgreSQL and Redis uses named Docker volumes and survives `docker compose
down`; use `docker compose down -v` only when intentionally deleting local data.

## Local development

Python 3.12+, Node.js 22+, and a running PostgreSQL/Redis pair are recommended.
SQLite and eager Celery remain available for a lightweight UI session.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
npm install
npm run build
cp .env.example .env
export DATABASE_URL=sqlite:///db.sqlite3
export CELERY_TASK_ALWAYS_EAGER=1
python manage.py migrate
python manage.py seed_platform
python manage.py runserver
```

During UI work, run `npm run dev:css` and `npm run dev:js` in separate terminals
to rebuild the Tailwind and JavaScript bundles on changes.

Run verification with:

```bash
pytest
ruff check .
python manage.py check
```

## Configuration

All runtime configuration is environment-driven; see [`.env.example`](.env.example).
Important settings are:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL URL; omitted means local SQLite |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | Redis endpoints for tasks |
| `SITE_URL` / `SITE_NAME` | Canonical URL and independent product identity |
| `FRED_API_KEY` | Optional FRED access for official time series |
| `SEC_USER_AGENT` | Required descriptive identity for SEC requests |
| `MARKET_DATA_PROVIDER` | Provider adapter; `demo` is offline-only |
| `MARKET_DATA_API_KEY` | Credential for a redistribution-approved provider |
| `AI_PROVIDER` / `AI_API_KEY` | Optional evidence-bound analysis provider |

Do not publish the defaults in `.env.example`. Production must use a random
`DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, explicit hosts and trusted origins,
encrypted secrets, TLS at the edge, and a licensed market-data provider.

## Data provenance and publication contract

Every numerical observation or published snapshot carries its source, value/as-
of time, fetch time, batch ID, quality state, licence scope, and fallback marker
where relevant. Raw artifacts are content-hashed. A dashboard snapshot becomes
public only after its required inputs pass the batch quality gate; on failure,
the last complete snapshot remains visible and is marked stale.

Default source adapters target official/open services such as FRED/ALFRED, the
New York Fed, US Treasury FiscalData, Federal Reserve, BLS, BEA, Census, CFTC,
SEC EDGAR, GitHub, OKX, and Deribit. Availability does not imply redistribution
permission: source licence records are the release gate. Paid CDS, commercial
news, exchange data, and third-party PDFs stay disabled until a suitable licence
is recorded.

This is a research interface, not an order-entry or automated-trading system.
Estimates such as GEX, DEX, Vanna, Charm, gamma flip, walls, max pain, and proxy
credit metrics must retain their on-page method labels.

## Service topology and production notes

The Compose stack runs `nginx -> gunicorn/Django`, PostgreSQL, Redis, a Celery
worker, and Celery beat. Nginx serves versioned static assets directly, prevents
service-worker caching mistakes, and forwards application traffic with proxy
headers. WhiteNoise remains a safe direct-Gunicorn fallback.

Before public deployment:

1. Put TLS and rate limiting at the edge (for example Cloudflare or a managed
   load balancer) and restrict direct access to the origin.
2. Run migrations as a one-off release job instead of concurrently on every
   replica; the Compose web command is intended for a single local instance.
3. Configure PostgreSQL point-in-time backups and object-store versioning.
4. Set Sentry/OpenTelemetry endpoints and alert on ingestion failure, stale
   required snapshots, queue depth, HTTP error rate, and backup verification.
5. Run `python manage.py check --deploy`, the complete test suite, and a route/
   sitemap reconciliation before promoting the release.

## Tests

The test suite treats public URLs and shareable query parameters as a product
contract. It covers seed cardinality and idempotence, numerical lineage,
calculation formulas, route status, dynamic detail pages, search/filter isolation,
sitemap and robots behaviour, retired-route HTTP 410 responses, and PWA assets.

The repository intentionally avoids exhaustive pixel matching. Visual regression
should compare this product's own 1440 px and 390 px baselines in both themes,
preserving information density and usability without copying another site's
branding or CSS.
