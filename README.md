# Family Hub

Family Hub is a self-hosted web application for sharing family photos and coordinating household tasks. It combines
photo storage, group-based access control, cleaning schedules, and shopping lists in one family workspace.

The project is designed primarily for mobile Safari, while also supporting larger screens through a responsive desktop
layout.

## Features

- **Photo library**
  - Cursor-based infinite scrolling, timeline navigation, and server-side search
  - Image and video uploads with first-frame thumbnails and in-browser playback
  - Favorites, shared photos, photo activity, shared memos, and group-based visibility
  - Desktop edge clicks and mobile detail-view swipes between adjacent photos in the library
  - Group albums with selectable cover photos
  - Bulk sharing to multiple family groups
  - Individual downloads and streamed ZIP exports for owned photos
  - Trash, restore, permanent deletion, and storage integrity checks
- **Household coordination**
  - Cleaning tasks with configurable intervals, completion history, pause, and resume
  - Shared shopping lists with purchased and unpurchased states
  - Home dashboard aggregating recent photos, due cleaning tasks, and shopping items
- **Family and account management**
  - Invitation-based account creation
  - Family groups, membership management, and group administration
  - Password changes, active-session management, and logout from all devices
  - System administration for users, roles, group health, audit logs, and maintenance status
- **Mobile and accessibility-oriented features**
  - Responsive navigation designed for iPhone-sized screens
  - PWA installation guidance and Web Push notification settings
  - English and Japanese UI with browser-persisted language selection
  - Public privacy information page

## Technology

- Python 3.13, FastAPI, SQLAlchemy, Alembic, and PostgreSQL
- React, TypeScript, React Router, TanStack Query, and Vite
- Docker Compose for the local PostgreSQL database
- pytest, Vitest, Playwright, Ruff, ESLint, and Prettier

## Repository layout

- `backend/` — FastAPI application, database migrations, commands, and backend tests
- `frontend/` — React and TypeScript application, frontend tests, and end-to-end tests
- `docs/` — Detailed product, architecture, deployment, and operations documentation
- `deploy/` — Production-oriented Caddy, PostgreSQL, and systemd configuration

## Requirements

- Python 3.13
- [uv](https://docs.astral.sh/uv/)
- Node.js and npm
- Docker with Docker Compose
- `ffmpeg` with `ffprobe` on `PATH` for video validation and thumbnails

## Quick start

Create the Python environment and install the locked backend dependencies:

```bash
make backend-sync
```

Create a local backend environment file from the example. Do not commit the resulting file:

```bash
cp backend/.env.example backend/.env
```

Install frontend dependencies and start PostgreSQL:

```bash
cd frontend
npm ci
cd ..
docker compose up -d db
```

Apply database migrations and create an initial system administrator:

```bash
cd backend
uv run --locked alembic upgrade head
uv run --locked python -m app.commands.create_user --username owner --system-role admin
```

Configure database credentials and photo storage paths in `backend/.env`. Storage configuration and safety requirements
are documented in [Backend Design](docs/backend-design.md).

## Run locally

Start the backend from `backend/`:

```bash
uv run --locked uvicorn app.main:app --reload --env-file .env --host 127.0.0.1 --port 18000
```

Start the frontend from `frontend/` in another terminal:

```bash
npm run dev
```

The development API listens on `127.0.0.1:18000`. Vite runs on `127.0.0.1:15173` and proxies `/api` requests to it.

For real-device LAN testing, start FastAPI with `--host 0.0.0.0` and add the Vite origin (for example,
`http://192.168.3.7:15173`) to both `CORS_ORIGINS` and `AUTH_TRUSTED_ORIGINS`. In development, upload chunks are sent
directly to the FastAPI port to avoid unreliable repeated large requests through the Vite proxy.

VS Code users can also use the `Dev: Start All` task to start the database and both development servers.

## Verification

Run the repository checks from the root:

```bash
make check
```

Frontend end-to-end checks can be run separately:

```bash
cd frontend
npm run test:e2e
npm run test:e2e:pwa
```

After a production deployment, run the public-origin smoke checks and the opt-in live authentication/upload check with a
dedicated test account:

```bash
PUBLIC_BASE_URL=https://family.example.com make production-smoke
FAMILY_HUB_E2E_BASE_URL=https://family.example.com \
FAMILY_HUB_E2E_USERNAME=<dedicated-test-user> \
FAMILY_HUB_E2E_PASSWORD=<dedicated-test-password> \
npm --prefix frontend run test:e2e:live
```

Keep the live-test credentials outside the repository and shell history.

## Documentation

The README intentionally stays focused on orientation and setup. Detailed behavior, design decisions, operational
procedures, storage rules, and production assumptions are documented separately:

- [Documentation guide](docs/README.md)
- [Product brief](docs/product-brief.md)
- [Backend design](docs/backend-design.md)
- [Database design](docs/database-design.md)
- [Deployment design](docs/deployment.md)
- [Production runbook](docs/production-runbook.md)
- [Web Push](docs/web-push.md)

## Project status

Family Hub is an actively developed personal project. Production deployment infrastructure exists, but production
operation and some real-device validation remain ongoing. See the detailed documentation for current limitations and
operational prerequisites.
