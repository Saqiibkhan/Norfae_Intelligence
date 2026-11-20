# Norfae Intelligence OS

Norfae Intelligence OS is a business intelligence platform for e-commerce
operations. The repository contains a FastAPI backend, PostgreSQL persistence,
a React/Vite frontend (the package includes Electron), integrations for Shopify
and Meta Ads, and deterministic analytics and intelligence modules.

This README is the project orientation document for contributors and coding
agents. Read it before changing code. Use the focused documents listed below
for authentication, tenancy, and intelligence details.

## Project status

As of November 16, 2026:

- Phase 1 backend foundation and Phase 2 multi-tenant data architecture are
  implemented.
- Phase 3 Parts 1-4 are implemented: data quality, deterministic profitability,
  product and city intelligence, marketing intelligence, and limited creative
  intelligence.
- The complete backend test suite last passed with **103 tests** using the
  repository root `.venv`. Tests use isolated SQLite fixtures and mock external
  services; they do not require production database credentials.
- PostgreSQL 16.16 development database is `norfae_intelligence_os`. The Phase 2
  audit recorded the initial 2 expense rows and 1 settings row as assigned to
  development business ID 1. Business IDs and data must never be assumed to
  match in another database.
- The migration chain in this checkout runs through `20261116_0004`.
- Phase 4 has not started. Do not start new product scope without user review.

The status above records the last completed implementation and test run. It is
not a claim that external integrations or the live development database were
rechecked during every later documentation change.

## Repository map

```text
norfae-intelligence-os/
|-- backend/
|   |-- app/
|   |   |-- agents/          # Typed, permission-aware intelligence agents
|   |   |-- core/            # Settings, auth, tenant scope, DB, middleware
|   |   |-- events/          # SQLAlchemy event listeners
|   |   |-- llm/             # Centralized OpenRouter client and safe errors
|   |   |-- models/          # SQLAlchemy models
|   |   |-- routers/         # FastAPI API routes
|   |   |-- schemas/         # Pydantic request/response schemas
|   |   |-- services/        # Business, integration and analytics services
|   |   |-- tasks/           # Explicitly scoped background task entry points
|   |   `-- websocket/       # Legacy WebSocket routes (currently closed)
|   |-- migrations/          # Alembic env and revisions
|   |-- tests/               # Pytest suite
|   |-- .env.example         # Safe configuration template
|   |-- INTELLIGENCE.md      # Metric definitions and intelligence limits
|   |-- AUTHENTICATION.md    # Login, roles and API authorization
|   |-- MULTITENANCY.md      # Tenant data boundary and migration details
|   |-- requirements.txt
|   `-- start_backend.bat
|-- frontend-electron/       # React/Vite user interface
|-- scripts/                 # Convenience scripts (inspect before running)
|-- docs/                    # Reserved documentation directory
`-- .venv/                   # Shared repository Python environment
```

The frontend currently has screens for dashboard, orders, inventory/products,
expenses, reports, Meta Ads, city intelligence, product intelligence, and
settings. Its API helper targets `http://127.0.0.1:8000`.

Backend route families include `/auth`, `/businesses`, `/settings`, `/system`,
`/orders`, `/order-items`, `/products`, `/expenses`, `/inventory`, `/reports`,
`/meta-ads`, `/shopify`, `/discord`, `/analytics`, `/dashboard`, `/creatives`,
`/city-intelligence`, `/product-intelligence`, and `/intelligence`. FastAPI's
`/docs` and `/openapi.json` are the live source for the complete route list.

The database includes the identity tables `users`, `businesses`, and
`business_memberships`, plus the existing business tables `analytics`,
`audit_logs`, `categories`, `creatives`, `expenses`, `inventory_products`,
`meta_daily_stats`, `orders`, `order_items`, `products`,
`product_match_memory`, `reports`, and `settings`. `audit_logs.business_id` may
be null for system-wide audit events. Models are defined under
`backend/app/models/`; Alembic metadata imports the full model set.

## Technology and environment

- Backend: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, Uvicorn.
- Database: PostgreSQL 16.16 for development; tests use in-memory SQLite.
- Frontend: React 19, Vite, React Router, Axios, Recharts, and Tailwind tooling.
- Optional AI client: OpenRouter through the shared `app.llm` client. Financial
  calculations and intelligence rankings are deterministic Python, not LLM
  output.
- Integrations: Meta Ads and Shopify use credentials configured per business;
  Discord support is present in the backend.

Pinned backend versions are in `backend/requirements.txt`; pytest is pinned in
`backend/requirements-dev.txt`. Use the repository-level `.venv`. A historical
`backend/venv` exists but is stale and should not be used as the project
environment.

## Local setup

Do not replace an existing virtual environment as a routine setup step. From
the repository root, if `.venv` does not exist, create it and install the
backend dependencies:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
```

Create `backend/.env` from `backend/.env.example`, then set the local PostgreSQL
URL and a private development JWT secret. The settings module resolves this
file relative to its own source path, so launching from another working
directory does not change which `.env` is loaded. Environment variables may
override file settings.

Important settings include:

- `DATABASE_URL`: PostgreSQL SQLAlchemy URL. Keep credentials private.
- `APP_ENV`: `development`, `test`, or `production`.
- `JWT_SECRET_KEY`, `JWT_ALGORITHM`, and
  `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`: bearer-token signing configuration.
- `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `OPENROUTER_MODEL`,
  `OPENROUTER_TIMEOUT`, and `OPENROUTER_MAX_RETRIES`.
- Shopify, Meta, Discord, shipping/tax, and warehouse values as applicable.

Never commit `.env`, print credentials/tokens, reuse the OpenRouter key as the
JWT secret, or add secrets to tests or documentation. Production startup
requires a strong JWT secret of at least 32 bytes. See
[`backend/.env.example`](backend/.env.example) for the full variable list.

## Start the backend

PowerShell, from `backend`:

```powershell
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Or run `backend\start_backend.bat` from Explorer or PowerShell. It changes to
the backend directory, activates the repository `.venv`, and serves port 8000.
Port 8000 matches the frontend API client. Previous backend verification also
used port 8001; use that port only when intentionally running a separate
instance and point the client at it accordingly.

Avoid `--reload` on Windows in this project. Earlier startup investigation
encountered Windows multiprocessing permission errors with the reload process;
normal `python -m uvicorn` startup was verified. Check the running service with:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

OpenAPI documentation is at `http://127.0.0.1:8000/docs` and the schema is at
`http://127.0.0.1:8000/openapi.json`.

## Start the frontend

From `frontend-electron`:

```powershell
npm ci
npm run dev
```

Other available scripts are `npm run build`, `npm run lint`, and
`npm run preview`. Although Electron is a dependency and the folder is named
`frontend-electron`, `package.json` currently defines no Electron launch or
packaging script.

### Current frontend/backend auth integration gap

Business API routes require `Authorization: Bearer <token>` and
`X-Business-ID`. The current frontend source does not yet implement login,
token storage/injection, or business selection/header injection. Backend APIs
can be exercised through Swagger UI or an HTTP client, but frontend calls to
protected routes will need that client-side auth flow before normal use. Do
not weaken backend authorization to work around this gap.

## Authentication and tenant security

Authentication endpoints are `POST /auth/register`, `POST /auth/login`, and
`GET /auth/me`. Registration creates the user, business, and owner membership
in one transaction. Passwords are hashed and public responses exclude hashes.

Every business REST request must select a business using `X-Business-ID` and
include a bearer token. The selected business ID is validated against the
active user membership; it is not trusted as identity by itself. Tenant-aware
`TenantSession` filters tenant-owned reads and rejects unscoped tenant queries
and cross-business writes. Route dependencies check role permissions.

Roles are `owner`, `admin`, `analyst`, and `viewer`. Owners/admins can read
analytics; only owners/admins manage memberships; integration credential writes
are owner-only. See [`backend/AUTHENTICATION.md`](backend/AUTHENTICATION.md) for
the full role matrix and [`backend/MULTITENANCY.md`](backend/MULTITENANCY.md)
for data-boundary details.

The current frontend has not implemented this protocol yet. The legacy global
WebSocket routes remain closed because they do not provide business-specific
channels. Background schedulers do not start automatically; explicit task
entry points require business IDs and tenant context.

## Database and migrations

The application uses PostgreSQL via SQLAlchemy. Importing `app.main` does not
run `Base.metadata.create_all()`. Schema changes belong in reviewed Alembic
migrations; migration setup imports model metadata without importing or
starting FastAPI, schedulers, or external integrations.

The migration chain in the repository is:

1. `20261116_0001`: no-op baseline marker for the pre-existing schema.
2. `20261116_0002`: users, businesses, and business memberships.
3. `20261116_0003`: tenant ownership columns, scoped constraints/indexes, and
   cross-business order-item relationship protections.
4. `20261116_0004`: enforces non-null business ownership for tenant tables;
   `audit_logs.business_id` remains nullable for system-wide events.

Safe read-only migration inspection, from `backend`:

```powershell
..\.venv\Scripts\python.exe -m alembic current
..\.venv\Scripts\python.exe -m alembic history
```

Before creating or applying any migration, verify the target database, take a
backup, inspect the migration operations, and test against a disposable copy.
Never use `create_all()` or destructive SQL to resolve a migration mismatch.
Do not run migrations against production without an explicit reviewed plan.

## Tests and verification

From `backend`:

```powershell
..\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
```

The test fixtures set a test database URL and override the API database with
isolated in-memory SQLite. They do not use the configured PostgreSQL database
or make real Shopify, Meta, or OpenRouter calls. Mock external integrations in
new tests. The last recorded full run passed 103 tests; rerun the command after
code changes rather than relying on the prior result.

Useful checks:

```powershell
..\.venv\Scripts\python.exe -c "from app.main import app; print(app.title, len(app.routes))"
Invoke-RestMethod http://127.0.0.1:8000/health
```

## Architecture guide for agents and contributors

Before changing a feature, inspect the relevant model, schema, router,
dependency, service, tests, and documentation. Prefer additive, narrow changes
and reuse existing behavior. Use this request path as the default mental model:

```text
HTTP router -> authentication/business-context dependency -> typed schema/agent
            -> deterministic service -> TenantSession/PostgreSQL
```

For intelligence work:

1. Check whether a service or metric already exists before implementing it.
2. Treat `AgentContext` as trusted only when constructed by a verified API
   dependency. Agents declare `required_permission` and obtain business ID and
   database session through its scoped accessors.
3. Add new agents to `app/agents/intelligence_registry.py` and expose routes
   through `app/routers/intelligence.py` where appropriate.
4. Explicitly scope service queries by verified `business_id`; do not accept a
   caller-supplied business ID as proof of access.
5. Keep financial calculations deterministic and state formulas, missing-data
   behavior, attribution, and uncertainty. Do not let an LLM calculate profit.
6. Mock Meta, Shopify, OpenRouter, and other external calls in tests. Avoid
   sync jobs and scheduler startup in request tests.
7. Add focused tests, run the complete pytest suite, and update
   `backend/INTELLIGENCE.md` when metrics or limitations change.

Do not restructure the backend, alter business calculations, or edit old
migration files as a shortcut. For database changes, add a new Alembic
revision only after inspecting current metadata and migration history.

When a feature, migration, dependency, command, integration boundary, or test
status changes, update this README's corresponding overview and the focused
document for that area in the same change. Keep dated test results labeled as
the last recorded run, and update them only after actually rerunning the suite.

## Intelligence capabilities and limits

Detailed formulas and endpoint contracts live in
[`backend/INTELLIGENCE.md`](backend/INTELLIGENCE.md). The current modules are:

- **Data quality:** validates order and catalog-product data and returns
  normalization suggestions without modifying original rows.
- **Profitability:** deterministic estimates from recorded costs and delivered
  orders. Missing discounts/refunds and zero-default legacy costs limit
  completeness; results are not certified profit.
- **Product intelligence:** units, order counts, revenue, item contribution,
  status indicators, comparisons, and evidence-based recommendations.
- **City intelligence:** delivered revenue/contribution and recorded delivery
  costs by city; city-level allocated business expenses are unavailable.
- **Marketing intelligence:** stored Meta daily spend/traffic plus on-demand
  campaign/ad-set/ad snapshots. Meta purchase actions are attribution reports;
  current sources omit conversion value, making ROAS unavailable. Business
  revenue is not assigned to campaigns.
- **Creative intelligence:** reads legacy creative rows only. Zero-default
  metrics may be ambiguous; no creative-level history or media assets are
  stored. A local optional image helper reports limited geometry/color data;
  video, OCR, product recognition, and causal visual-performance analysis are
  not available.

## Integration and operational cautions

- Meta campaign/ad-set/ad APIs make live provider requests when explicitly
  called and the selected business has Meta credentials. Do not call sync or
  provider methods from tests without mocking them.
- Shopify and Discord integrations also require per-environment credentials.
- OpenRouter is centralized at `backend/app/llm/openrouter_client.py`, uses
  configured model/timeouts/bounded retries, and redacts provider failures.
  No production agent should call it for deterministic calculations.
- Settings responses expose connection status, not stored integration secrets.
- Application startup does not run global schedulers. Do not enable them as a
  side effect of importing the app or running tests.
- Do not print `.env`, database URLs, password hashes, JWTs, access tokens, or
  provider keys in logs, test failures, or reports.

## Reference documents

- [`backend/INTELLIGENCE.md`](backend/INTELLIGENCE.md): metric definitions,
  endpoints, assumptions, and intelligence limitations.
- [`backend/AUTHENTICATION.md`](backend/AUTHENTICATION.md): auth endpoints,
  roles, and credential handling.
- [`backend/MULTITENANCY.md`](backend/MULTITENANCY.md): tenant boundaries,
  migration/backfill state, and isolation guarantees.
- [`backend/.env.example`](backend/.env.example): configuration names and
  safe placeholders.
- [`backend/migrations/`](backend/migrations/): Alembic environment and
  revision history.
