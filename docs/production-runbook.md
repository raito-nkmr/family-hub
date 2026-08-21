# Production Build and Release Runbook

## Purpose

This runbook explains how to reproduce Family Hub production from reviewed repository configuration. The target design is in
[`deployment.md`](./deployment.md). Host-specific production state is intentionally kept outside the public repository.

The production layout uses Caddy and FastAPI on the host, a dedicated PostgreSQL container managed by Docker Compose, an
internal HDD for primary photo storage, and a disconnected external HDD for versioned backups. Do not include the development
`compose.yaml` or its database volume in production.

## Secret boundary

The following remain on the host and must never be copied, displayed, diffed, or committed to the repository:

- `/etc/family-hub/backend.env`, including the production `DATABASE_URL`
- `/etc/family-hub/database.env`, used to initialize the PostgreSQL container
- Cloudflare Tunnel token
- Web Push private key

See `deploy/database.env.example` for database variable names. Do not share the database password with development; configure
the production `DATABASE_URL` and `database.env` deliberately. Production PostgreSQL listens on `127.0.0.1:5433`.
Agents do not operate `.env` or these secret files; operators create and change them directly.

## Storage mounts

The production host uses fixed mount points so the systemd sandbox and application settings refer to the same devices:

| Mount point | Role | Availability |
| --- | --- | --- |
| `/mnt/family-hub-data` | Internal HDD; primary photo storage and staged database backups | Required for photo operations |
| `/mnt/family-hub-backup` | External HDD; versioned snapshots only | Mounted only while a backup runs |

`PHOTO_STORAGE_ROOT` must point at `/mnt/family-hub-data` itself and use a matching `.photo-storage-marker`. Configure
`BACKUP_STORAGE_ROOT` as `/mnt/family-hub-backup` with a separate `.family-hub-backup-marker`. Never use the backup mount as
`PHOTO_STORAGE_ROOT` and never create a fallback path on the SSD when the internal HDD is unavailable.

## Database boundary

| Area | Development | Production |
| --- | --- | --- |
| Compose file | Repository `compose.yaml` | `/opt/family-hub/current/deploy/compose.production.yaml` |
| Compose project | `fastapi-react-playground` | `family-hub-production` |
| Host port | `127.0.0.1:15432` | `127.0.0.1:5433` |
| Volume | `fastapi-react-playground_postgres-data` | `family-hub-production-postgres-data` |
| Environment | `backend/.env` | `/etc/family-hub/database.env` |
| Lifecycle | Developer-controlled Compose | `family-hub-database.service` |

Create the production volume as an external volume so `docker compose down --volumes` cannot remove it. An intentional
production reset must stop services and explicitly remove this named volume after verifying the target.

## Release contents

`/opt/family-hub/releases/<timestamp>/` contains at least:

```text
<release>/
├── backend/
│   ├── .venv/
│   ├── alembic/
│   ├── alembic.ini
│   ├── app/
│   ├── pyproject.toml
│   └── uv.lock
├── frontend/
│   └── dist/
└── deploy/
    └── compose.production.yaml
```

Do not include `.env`, test data, Python cache, `frontend/node_modules`, or development Compose volumes. Before creating a
release, run `npm ci`, frontend checks, and `npm run build`; set `VITE_UPLOAD_REQUEST_TIMEOUT_MS` to the measured
production value during the build and deploy only `dist/`. Create the backend environment from the
committed `pyproject.toml` and `uv.lock` with `uv sync --locked --no-dev`. Update the lock file with `make backend-lock`
when backend dependencies change.

On the production host, install the pinned runtime environment after switching the release symlink:

```bash
cd /opt/family-hub/current/backend
uv sync --locked --no-dev
```

## Pre-construction validation

Create the Caddy access-log directory before validation:

```bash
sudo install -d -o caddy -g caddy -m 0750 /var/log/family-hub
sudo touch /var/log/family-hub/access.log
sudo chown caddy:caddy /var/log/family-hub/access.log
sudo chmod 0640 /var/log/family-hub/access.log
```

Validate the repository configuration:

```bash
FAMILY_HUB_DATABASE_ENV_FILE="$PWD/deploy/database.env.example" \
  docker compose --file deploy/compose.production.yaml config --quiet

sudo caddy validate --config deploy/Caddyfile --adapter caddyfile
systemd-analyze verify deploy/systemd/*.service deploy/systemd/*.timer
```

Complete the normal backend and frontend checks as well. Repeat Caddy and systemd validation with the versions installed on
the target host.

After the public hostname is serving the release, run the repository-level public checks from a trusted operator machine:

```bash
PUBLIC_BASE_URL=https://family.example.com make production-smoke
```

Run the live authentication, CSRF, and chunk-upload check separately with a dedicated test account. The account must have
completed any required password change and the test cancels its temporary upload batch:

```bash
FAMILY_HUB_E2E_BASE_URL=https://family.example.com \
FAMILY_HUB_E2E_USERNAME=<dedicated-test-user> \
FAMILY_HUB_E2E_PASSWORD=<dedicated-test-password> \
npm --prefix frontend run test:e2e:live
```

Do not store the credentials in the repository, shell history, CI logs, or screenshots.

## First construction

An operator performs these steps on the Ubuntu host after creating and checking the secret files:

1. Create `/etc/family-hub/database.env` as `root:family-hub`, mode `0640`.
2. Point `/etc/family-hub/backend.env` at production PostgreSQL on `127.0.0.1:5433`.
3. Create the external production volume.
4. Deploy a release and switch `/opt/family-hub/current`.
5. Install Caddy configuration and systemd units.
6. Reload systemd and start the production database.
7. Apply Alembic migrations.
8. Create the initial system administrator.
9. Start or reload Backend, Caddy, and cloudflared.

```bash
sudo docker volume create family-hub-production-postgres-data
sudo install -o root -g root -m 0644 \
  deploy/systemd/family-hub-database.service \
  /etc/systemd/system/family-hub-database.service
sudo install -o root -g root -m 0644 \
  deploy/systemd/family-hub-backend.service \
  /etc/systemd/system/family-hub-backend.service
sudo systemctl daemon-reload
sudo systemctl enable --now family-hub-database.service
```

Apply migrations with a temporary unit that reads the production environment:

```bash
sudo systemd-run --wait --pipe --collect \
  --uid=family-hub \
  --gid=family-hub \
  --property=WorkingDirectory=/opt/family-hub/current/backend \
  --property=EnvironmentFile=/etc/family-hub/backend.env \
  /opt/family-hub/current/backend/.venv/bin/alembic upgrade head
```

The current resettable schema chain has five revisions, ending at `20260821_05_cleaning_reports`. The upgrade contains
schema DDL only; it does not create users, groups, categories, tasks, or completion history. Run `create_user` and any
other bootstrap commands separately. Development reset and production-like reset are independent procedures: never run
the development `docker compose down --volumes` command against the production-like service or volume.

Create the initial administrator with a PTY so password input is hidden:

```bash
sudo systemd-run --wait --pty --collect \
  --uid=family-hub \
  --gid=family-hub \
  --property=WorkingDirectory=/opt/family-hub/current/backend \
  --property=EnvironmentFile=/etc/family-hub/backend.env \
  /opt/family-hub/current/backend/.venv/bin/python \
  -m app.commands.create_user --username owner --system-role admin
```

Replace the username with the operator's value. Never put the password in an argument, environment variable, or log.

## Initial cutover from the public test environment

During the initial cutover, `fastapi-react-playground-db-1` was resettable public-test data. The first production-like
rehearsal created an empty schema in the new production volume instead of migrating this database. This is a one-time
bootstrap procedure; use the release-update procedure for normal operation.

Use this order:

1. Stop `family-hub-backend.service`.
2. Prepare the new production volume and secret files.
3. Deploy the new release and systemd units.
4. Start the database service and confirm its Compose health check.
5. Apply Alembic and create the initial administrator.
6. Start Backend and check loopback health and readiness. The backend must start even when the photo HDD is unavailable;
   readiness reports the photo-storage problem separately, and photo operations remain unavailable until the HDD is restored.
7. Validate and reload Caddy.
8. From the custom domain, check health, login, invitations, core features, and public readiness `404`.
9. Stop the old development DB only after the new configuration is accepted.

Do not remove the old development database until all required checks pass against the new one.

## Cloudflare and browser cache

Set Cloudflare Browser Cache TTL to `Respect Existing Headers`; the default four-hour policy can override Caddy's shorter
TTL and revalidation instructions. Add at least these public-host rules:

| Condition | Cache eligibility | Purpose |
| --- | --- | --- |
| URI path starts with `/api/` | Bypass cache | Never store authenticated APIs at the Edge |
| URI path equals `/sw.js` | Bypass cache | Do not delay Service Worker update checks |

Do not apply Cache Everything to HTML. Verify externally:

```bash
curl -sSI https://<public-host>/
curl -sSI https://<public-host>/invitations
curl -sSI https://<public-host>/sw.js
curl -sSI https://<public-host>/assets/<current-hash>.js
curl -sSI https://<public-host>/api/v1/health
```

Expected results are `no-cache, must-revalidate` for `/` and SPA routes, `no-store` and `DYNAMIC` or `BYPASS` for `sw.js`,
long immutable cache and second-request `HIT` for hashed assets, and `private, no-store` with `DYNAMIC` or `BYPASS` for APIs.
Cache purge does not clear four-hour browser caches already stored; use Safari website-data deletion or another browser during
immediate post-change checks.

## Operational timers

Before production begins, introduce database backup, photo integrity, and trash purge one at a time. Installing units is not
enough: run each service manually, verify success, and enable its timer only afterward. Configure optional Healthchecks-style
URLs in `/etc/family-hub/backend.env` before starting units:

| Job | Variable |
| --- | --- |
| DB backup | `MONITORING_PING_URL_DB_BACKUP` |
| Photo integrity | `MONITORING_PING_URL_INTEGRITY` |
| Trash purge | `MONITORING_PING_URL_TRASH_PURGE` |
| Web Push delivery | `MONITORING_PING_URL_NOTIFICATIONS` |
| Cleaning due | `MONITORING_PING_URL_CLEANING_NOTIFICATIONS` |
| Secondary storage backup | `MONITORING_PING_URL_SECONDARY_BACKUP` |

Units POST `/start`, the base URL on success, and `/fail` on failure. Unconfigured values are no-ops. Never record actual
monitoring URLs or identifiers in the repository or this runbook.

### Required tools

The database backup command uses host `pg_dump`. Install a version compatible with PostgreSQL 18 and verify:

```bash
command -v pg_dump && pg_dump --version
command -v pg_restore && pg_restore --version
command -v rsync
```

`rsync` is needed only for an external-HDD snapshot. Do not enable `family-hub-secondary-backup.timer` until the backup HDD is
mounted and its marker has been verified.

### Install units

```bash
sudo install -o root -g root -m 0644 \
  deploy/systemd/family-hub-db-backup.service \
  deploy/systemd/family-hub-db-backup.timer \
  deploy/systemd/family-hub-integrity.service \
  deploy/systemd/family-hub-integrity.timer \
  deploy/systemd/family-hub-trash-purge.service \
  deploy/systemd/family-hub-trash-purge.timer \
  /etc/systemd/system/
sudo systemctl daemon-reload
```

### Database backup

```bash
sudo systemctl start family-hub-db-backup.service
sudo systemctl status family-hub-db-backup.service --no-pager
sudo journalctl -u family-hub-db-backup.service -n 50 --no-pager
```

Before enabling the timer, verify successful exit, a `.dump` and `.json` under `database-backups/YYYY/MM/`, restricted file
permissions, a `succeeded` maintenance record, and restoration into a temporary database.

```bash
sudo systemctl enable --now family-hub-db-backup.timer
```

For restore drills, use a real dump and a disposable loopback-only PostgreSQL 18 container. Wait for `pg_isready` to report
`accepting connections`, then run `pg_restore --no-owner --no-privileges --exit-on-error`. Check `alembic_version`, user count,
and administrator count before stopping the container. `POSTGRES_HOST_AUTH_METHOD=trust` is permitted only in this temporary
loopback container, never in production. The drill does not change the production database.

Custom-format dumps may include `maintenance_runs` that were `running` when the snapshot was taken. Restore does not carry
running processes; mark such records interrupted before starting Backend.

### Photo integrity

Start the normal read-only check first, without recalculating every original hash:

```bash
sudo systemctl start family-hub-integrity.service
sudo systemctl status family-hub-integrity.service --no-pager
sudo journalctl -u family-hub-integrity.service -n 100 --no-pager
```

Findings return status 1. Investigate and classify any findings before enabling the timer:

```bash
sudo systemctl enable --now family-hub-integrity.timer
```

### Trash purge

Trash purge permanently deletes photos past retention. Run it only after database backup and integrity succeed and the trash
contents and retention policy are verified:

```bash
sudo systemctl start family-hub-trash-purge.service
sudo systemctl status family-hub-trash-purge.service --no-pager
sudo journalctl -u family-hub-trash-purge.service -n 100 --no-pager
sudo systemctl enable --now family-hub-trash-purge.timer
sudo systemctl list-timers 'family-hub-*' --all --no-pager
```

Do not enable notification timers before VAPID configuration and real-device validation. Verify that
`PUSH_ALLOWED_ENDPOINT_HOSTS` contains only verified providers and that the per-user subscription limit is intended.
Enable notifications from standalone iPhone Family Hub, trigger an event from another user, manually run the delivery
service, and verify device display, click navigation, and non-secret journal output. After cleaning-due notification is also
verified manually, enable both timers:

```bash
sudo systemctl start family-hub-notifications.service
sudo systemctl start family-hub-cleaning-notifications.service
sudo systemctl enable --now family-hub-notifications.timer family-hub-cleaning-notifications.timer
sudo systemctl list-timers 'family-hub-*notifications*' --all --no-pager
```

## One-time development database reset and migration rebuild

The following procedure rebuilds the development database for disposable dummy data. It does not reset the production-like
database and does not replace the separate production reset procedure below. Do not use it after real family data is stored;
use database and storage restoration instead.

Before deleting anything:

- Stop the development backend and any development workers.
- Verify development PostgreSQL is `127.0.0.1:15432` and production PostgreSQL is `127.0.0.1:5433`.
- Verify the development Compose volume and `family-hub-production-postgres-data` are separate volumes.
- Verify each `PHOTO_STORAGE_ROOT`, its `.photo-storage-marker`, each derivative root, and the separate backup marker.
- Confirm that only dummy data exists and that no command targets a mounted backup path accidentally used as primary storage.

Reset the development database only after confirming the current Compose project and volume:

```bash
docker compose ps --all
docker compose config --volumes
docker compose down --volumes
docker compose up --detach --wait db
```

Apply the latest schema and create development bootstrap data:

```bash
cd backend
uv run --locked alembic upgrade head
uv run --locked python -m app.commands.create_user --username owner --system-role admin
```

Reset the production-like database only as a separate, explicitly approved operation after confirming the named external volume:

```bash
sudo systemctl stop family-hub-backend.service
sudo systemctl stop family-hub-database.service
sudo docker volume inspect family-hub-production-postgres-data
sudo docker volume rm family-hub-production-postgres-data
sudo docker volume create family-hub-production-postgres-data
sudo systemctl start family-hub-database.service
```

The production-like database and storage reset is a separate operation. Do not continue with its database, photo-storage,
derivative, or backup deletion commands as part of the development reset above. When that operation is approved, repeat the
schema, bootstrap, and storage steps against the production-like service and its explicitly verified paths.

For the development storage reset only, remove the contents of each development primary photo root's `originals/`,
`incoming/`, and `database-backups/`. For each development derivative root, remove only the contents of `thumbnails/` and
`incoming/`. For the separate development backup root, remove only its snapshot and database-backup contents. Preserve each
root directory, storage marker, and backup marker. Resolve and review the absolute paths before deletion; never use an unset
or broad environment variable as a deletion target.

Recreate only the development directories that are intentionally part of the local reset, apply the new migrations to the
development database, and recreate its initial administrator. Run the photo-integrity command against the empty development
primary storage and verify that the first test upload creates one original, one sidecar, and one thumbnail. After a real-data
rebuild, use backup restoration instead of this reset procedure.

## Release update

For a release without a database schema change:

1. Run all backend and frontend checks.
2. Create a timestamped release.
3. Review Alembic upgrades and irreversible changes.
4. Stop Backend.
5. Switch `current` to the new release.
6. Apply Alembic.
7. Start Backend.
8. Validate and reload Caddy only when its configuration changed.
9. Check loopback and custom-domain health, login, and core screens.
10. If needed, roll back the application release; do not automatically downgrade the database.

## Ongoing production conditions

- Production database is separated from development.
- Database health, Backend, Caddy, and cloudflared recover automatically after reboot.
- Database backups are written to separate storage.
- A backup can be restored into a temporary database.
- Photo integrity checks succeed.
- Authenticated core features pass external smoke tests.
- Cloudflare, Caddy, and Service Worker caching follow the intended policy.
- iPhone Safari has verified PWA, upload, and original display.
- The acceptance checklist in [`deployment.md`](./deployment.md#production-acceptance-checklist) passes.

日本語版: [production-runbook.ja.md](./production-runbook.ja.md)
