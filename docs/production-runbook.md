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

The repository provides two release helpers:

- `scripts/create-production-release.sh` runs the repository checks, builds the frontend, and creates an archive without
  `.env`, `.venv`, or `frontend/node_modules`.
- `deploy/production-release.sh` installs an archive and performs the guarded production cutover described in the release
  update section below.

The production host must provide `uv` at `/usr/local/bin/uv` or `/usr/bin/uv`. The installer runs it as root while preparing the
new release and leaves the resulting runtime readable and executable by the `family-hub` service user. A user-local `uv` path
may be supplied explicitly with `UV_BIN`, but the service user must not be expected to traverse an operator's home directory.

The installer creates the pinned runtime environment before switching the release symlink:

```bash
cd /opt/family-hub/releases/<new-release>/backend
/usr/local/bin/uv sync --locked --no-dev
```

Do not run this command against `/opt/family-hub/current` during a release update. A missing or incomplete `.venv` must never
become the target of the production symlink.

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

For a fresh database with no legacy albums, apply migrations with a temporary unit that reads the production environment:

```bash
sudo systemd-run --wait --pipe --collect \
  --uid=family-hub \
  --gid=family-hub \
  --property=WorkingDirectory=/opt/family-hub/current/backend \
  --property=EnvironmentFile=/etc/family-hub/backend.env \
  /opt/family-hub/current/backend/.venv/bin/alembic upgrade head
```

For an existing database currently stamped at `20260829_04_shopping`, do not apply `upgrade head` in one step: the legacy
`albums.group_id` column is needed by the data migration. Apply the album schema revision, copy the existing album targets,
verify that a dry run reports zero rows, and then apply the revision that removes the legacy column:

```bash
sudo systemd-run --wait --pipe --collect \
  --uid=family-hub \
  --gid=family-hub \
  --property=WorkingDirectory=/opt/family-hub/current/backend \
  --property=EnvironmentFile=/etc/family-hub/backend.env \
  /opt/family-hub/current/backend/.venv/bin/alembic upgrade 20260830_01_album_groups
sudo systemd-run --wait --pipe --collect \
  --uid=family-hub \
  --gid=family-hub \
  --property=WorkingDirectory=/opt/family-hub/current/backend \
  --property=EnvironmentFile=/etc/family-hub/backend.env \
  /opt/family-hub/current/backend/.venv/bin/python \
  -m app.commands.migrate_album_group_shares --apply
sudo systemd-run --wait --pipe --collect \
  --uid=family-hub \
  --gid=family-hub \
  --property=WorkingDirectory=/opt/family-hub/current/backend \
  --property=EnvironmentFile=/etc/family-hub/backend.env \
  /opt/family-hub/current/backend/.venv/bin/python \
  -m app.commands.migrate_album_group_shares
sudo systemd-run --wait --pipe --collect \
  --uid=family-hub \
  --gid=family-hub \
  --property=WorkingDirectory=/opt/family-hub/current/backend \
  --property=EnvironmentFile=/etc/family-hub/backend.env \
  /opt/family-hub/current/backend/.venv/bin/alembic upgrade head
```

Fresh databases with no legacy albums can use `alembic upgrade head` directly. Never run the data command after the second
revision has removed `albums.group_id`.

When applying a schema change while retaining existing photos, regenerate all photo sidecars from PostgreSQL and run the
read-only integrity check before starting the Backend. An intentional empty-environment reset uses the guarded orphan-file
cleanup command in the reset procedure below instead.

```bash
sudo systemd-run --wait --pipe --collect \
  --uid=family-hub \
  --gid=family-hub \
  --property=WorkingDirectory=/opt/family-hub/current/backend \
  --property=EnvironmentFile=/etc/family-hub/backend.env \
  /opt/family-hub/current/backend/.venv/bin/python \
  -m app.commands.sync_photo_sidecars
sudo systemd-run --wait --pipe --collect \
  --uid=family-hub \
  --gid=family-hub \
  --property=WorkingDirectory=/opt/family-hub/current/backend \
  --property=EnvironmentFile=/etc/family-hub/backend.env \
  /opt/family-hub/current/backend/.venv/bin/python \
  -m app.commands.check_photo_integrity
```

The current resettable schema chain has four readable domain revisions followed by the album sharing revisions. The upgrade contains
schema DDL only; it does not create users, groups, categories, tasks, completion history, or other application data. Run
`create_user` and any other bootstrap commands separately. Development reset and production-like reset are independent
procedures: never run the development `docker compose down --volumes` command against the production-like service or volume.
These revisions replace the disposable pre-production history; a database stamped with a retired revision ID must be rebuilt
using the reset procedure below, not upgraded in place. Never apply that reset to a real-data environment.

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

Convert legacy shopping purchase state after the migration and before using history/statistics:

```bash
cd /opt/family-hub/current/backend
uv run --locked python -m app.commands.migrate_shopping_history --apply
```

Without `--apply`, the command reports the number of rows that would be converted and rolls back. It creates one finalized,
amount-unrecorded trip and one purchase event per legacy purchased item, and is safe to run again.

Existing in-progress trips are not automatically merged or removed. Empty in-progress trips can be permanently deleted from the
history page or by confirming the finish action in the store. In-progress trips with purchase events should be discarded instead;
discard preserves the trip and reverses its purchase events while restoring planned items to the active list.

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
| Chore due | `MONITORING_PING_URL_CHORE_NOTIFICATIONS` |
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

When findings are limited to old orphaned photo files, preview and then explicitly apply the guarded cleanup. It leaves
files newer than 24 hours and refuses to delete when the database has no photos:

```bash
sudo systemd-run --wait --pipe --collect \
  --uid=family-hub \
  --gid=family-hub \
  --property=WorkingDirectory=/opt/family-hub/current/backend \
  --property=EnvironmentFile=/etc/family-hub/backend.env \
  /opt/family-hub/current/backend/.venv/bin/python \
  -m app.commands.cleanup_orphaned_photo_files
sudo systemd-run --wait --pipe --collect \
  --uid=family-hub \
  --gid=family-hub \
  --property=WorkingDirectory=/opt/family-hub/current/backend \
  --property=EnvironmentFile=/etc/family-hub/backend.env \
  /opt/family-hub/current/backend/.venv/bin/python \
  -m app.commands.cleanup_orphaned_photo_files --apply
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
service, and verify device display, click navigation, and non-secret journal output. After chore-due notification is also
verified manually, enable both timers:

```bash
sudo systemctl start family-hub-notifications.service
sudo systemctl start family-hub-chore-notifications.service
sudo systemctl enable --now family-hub-notifications.timer family-hub-chore-notifications.timer
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

Because the development PostgreSQL volume also contains disposable integration-test databases, recreate them after every
volume reset:

```bash
docker compose exec -T db sh -c \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "CREATE DATABASE family_hub_test"'
docker compose exec -T db sh -c \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "CREATE DATABASE family_hub_migration_test"'
```

Apply the latest schema and create development bootstrap data:

```bash
cd backend
uv run --locked alembic upgrade head
uv run --locked python -m app.commands.cleanup_orphaned_photo_files \
  --apply --allow-empty-database --min-age-hours 0
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

After applying the production schema with the production environment file, run the same guarded cleanup against the
production-like database and photo-storage root:

```bash
sudo systemd-run --wait --pipe --collect \
  --uid=family-hub \
  --gid=family-hub \
  --property=WorkingDirectory=/opt/family-hub/current/backend \
  --property=EnvironmentFile=/etc/family-hub/backend.env \
  /opt/family-hub/current/backend/.venv/bin/python \
  -m app.commands.cleanup_orphaned_photo_files \
  --apply --allow-empty-database --min-age-hours 0
```

The production-like database and storage reset is a separate operation. Do not continue with its database, photo-storage,
derivative, or backup deletion commands as part of the development reset above. When that operation is approved, repeat the
schema, guarded orphan-file cleanup, bootstrap, and storage steps against the production-like service and its explicitly
verified paths.

For the development storage reset, use the guarded cleanup command for `originals/`, sidecars, primary `incoming/`,
derivative `thumbnails/`, and derivative `incoming/`; it preserves each root directory and storage marker. It intentionally
does not delete `database-backups/` or the separate development backup root. Remove those backup contents only as a separate,
explicitly reviewed operation when they are no longer needed. Never use an unset or broad environment variable as a deletion
target.

The guarded cleanup command clears old originals, sidecars, thumbnails, and upload parts while preserving storage markers and
database-backup files. Recreate only the development directories that are intentionally part of the local reset, apply the
new migrations to the development database, and recreate its initial administrator. The cleanup command performs a final
integrity check; verify separately that the first test upload creates one original, one sidecar, and one thumbnail. After a
real-data rebuild, use backup restoration instead of this reset procedure.

## Release update

Create and install a release through the repository helpers. The archive creation step must run from a clean worktree so the
release contains exactly the committed source and the freshly built frontend:

```bash
release_id="$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD)"
VITE_UPLOAD_REQUEST_TIMEOUT_MS=30000 \
  ./scripts/create-production-release.sh "$release_id"
```

Replace `30000` with the measured production value before building the release.

Transfer the resulting archive to the production host through the approved operator channel and verify the printed SHA-256
before starting the installer. The archive path passed to the installer must be readable on that host.

Install the cutover helper once on the production host. Keep `uv` in a system path, or pass an absolute `UV_BIN` path to the
transient unit when that is not possible:

```bash
sudo install -o root -g root -m 0755 \
  deploy/production-release.sh \
  /usr/local/sbin/family-hub-production-release

sudo systemd-run --unit="family-hub-release-${release_id}" --collect \
  /usr/local/sbin/family-hub-production-release \
  "/tmp/family-hub-release-${release_id}.tar.gz" "$release_id"
```

If `uv` is not installed in one of the default system paths, add a systemd environment assignment without putting secrets in
the command:

```bash
sudo systemd-run --unit="family-hub-release-${release_id}" --collect \
  --setenv=UV_BIN=/absolute/path/to/uv \
  /usr/local/sbin/family-hub-production-release \
  "/tmp/family-hub-release-${release_id}.tar.gz" "$release_id"
```

The transient unit continues after an SSH or terminal disconnect. Follow its output after reconnecting with:

```bash
sudo journalctl -u "family-hub-release-${release_id}" --no-pager
```

The installer performs these guarded steps:

1. Acquire a host-wide release lock and verify the current release and backend health.
2. Reject unsafe archive paths, `.env`, `.venv`, and `node_modules` entries.
3. Extract into a new timestamped release directory without touching `current`.
4. Run the locked backend sync and verify the new Python runtime can start Uvicorn.
5. Create a temporary symlink and atomically replace `current` with it.
6. Restart Backend and wait up to 30 seconds for Backend, Caddy API health, and the static root to return successfully with the
   new `index.html` content.
7. Restore the previous release and restart Backend automatically if any post-switch check fails.

The script leaves a failed release directory for inspection and never deletes an existing release automatically. It does not
apply Alembic migrations or reload Caddy configuration. Review and run schema migrations separately when the release changes
the backend schema; frontend-only releases such as the photo layout fix do not require a migration.

For a release with a database schema change, review backward compatibility before applying Alembic. The application rollback
protects the release symlink and service, but it must not downgrade an already-upgraded database.

The normal release sequence is therefore:

1. Build and verify the archive.
2. Review any Alembic changes and apply them through the separate migration procedure when required.
3. Start the detached release helper.
4. Check the helper journal and loopback health.
5. Run the public smoke, login, and core-screen acceptance checks.

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
