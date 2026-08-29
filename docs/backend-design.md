# Backend Design

## Purpose

This document defines the incremental FastAPI and PostgreSQL backend for Family Hub photos, chores, and shopping. It
describes the MVP architecture, responsibilities, dependency direction, API boundaries, data model, file storage,
safety, and testing. See [`product-brief.md`](./product-brief.md) for product scope and
[`database-design.md`](./database-design.md) for the detailed schema and migration policy.

## Design principles

- Organize code by feature.
- Separate routers, models, schemas, and services inside each feature.
- Keep feature-specific code local until more than one feature needs it.
- Do not use imports for implicit initialization or registration.
- Register FastAPI routers explicitly with `app.include_router(...)`.
- Use a FastAPI lifespan for startup and shutdown.
- Assume filesystem and PostgreSQL can become inconsistent and make detection and recovery possible.
- Parallelize reception per file; serialize only finalization of originals, sidecars, and database records.
- Prefer learning and a working MVP over premature abstraction.

## Directory structure

```text
backend/
├── alembic/
├── app/
│   ├── main.py
│   ├── commands/
│   ├── core/
│   ├── database/
│   └── features/
│       ├── albums/
│       ├── auth/
│       ├── chores/
│       ├── groups/
│       ├── health/
│       ├── maintenance/
│       ├── notifications/
│       ├── photos/
│       └── shopping/
└── tests/
    ├── commands/
    ├── core/
    ├── database/
    └── features/
```

Commands include user and dummy-user creation, password reset, database and secondary-storage backup, photo-integrity
checking, old orphaned-photo cleanup, sidecar synchronization, trash purge, OpenAPI export, notification enqueue and
delivery, monitoring reporting, and role management. User creation permits regular users only after an active system
administrator exists; initial setup must explicitly create the administrator. Role management uses the same transaction
advisory lock as web administration.
Do not create empty packages or placeholder tests before they are needed.

## Responsibilities

### `core`

`config.py` owns typed environment settings, `lifespan.py` owns application and process-resource startup/shutdown, and
`middleware.py` owns application-wide HTTP constraints that run before feature input. `core` is not a general-purpose home
for feature logic.

### `database`

`base.py` defines SQLAlchemy Declarative Base and Alembic metadata. `session.py` defines the engine, session factory, and
request-scoped session dependency. Model discovery must not rely on import side effects; provide an explicit model-loading
function or registry for Alembic. The current Alembic chain consists of four explicit schema-only domain baseline revisions
(`core`, `media`, `household`, and `shopping`). The `household` baseline contains the complete current chore schema,
including categories, completion snapshots, report settings, and category ordering. The `shopping` baseline contains the
complete current shopping schema, including categories, assignments, trips, purchase history, and discarded-trip state.
Migrations must not write application data, seed rows, or perform backfills.

### `features.health`

Public liveness reports only that the application process is running. Loopback-only readiness checks PostgreSQL and photo
storage readability and returns `503` when either is unavailable, without preventing the process from starting. Caddy blocks
the exact readiness path with `404` on the public route. Detailed authenticated storage status belongs to the photo feature.

### `features.auth`

Owns family login, server-side sessions, system roles, invitation-based account creation, CSRF validation, and login-rate
limiting. It contains routers, service logic, `User`, `UserSession`, `UserInvitation`, and `LoginRateLimit` models,
Argon2id password helpers, rate limiting, authentication dependencies, invitation handling, and a deliberately small
`public.py` boundary.

Login, password changes, and current-password reauthentication lock the target `User` row with `FOR UPDATE` before
verifying the current hash. This prevents an old-password login or protected mutation from passing concurrently with a
password change. The query uses `populate_existing` so verification reads the row version obtained after the lock.

An operator password reset marks the user as requiring a password change. The user may authenticate only to retrieve the
current session, change the password, or log out while this flag is set; all other authenticated feature APIs return `403`.
Invitation acceptance is separate from operator reset: invitees choose their own password during one-time invitation
acceptance, and those accounts do not receive the forced-change flag.

Other features may use only `features.auth.public`, `require_authenticated_user`, `require_password_change_complete`, and
`require_csrf_token`; they must not import auth internals directly.

Login rate limiting is shared by all application processes through PostgreSQL. The request key combines the trusted client IP
and normalized username, but only its SHA-256 hash is stored. A PostgreSQL transaction advisory lock serializes attempts for
the hash; the attempt row is created or updated atomically, successful authentication removes it, and stale rows are removed
opportunistically. A database outage is surfaced rather than silently falling back to a per-process limiter.

### `features.groups`

Owns group creation, membership, group-local roles, invitations, administration summaries, audit access, and member changes.
Non-members receive `404` without disclosure of group existence. Candidate users are returned only to group administrators and
must be active and not already members. A database unique constraint and pre-check both map duplicate names to `409 Conflict`.

There is no HTTP group-deletion API. The sole physical-delete path is
`python -m app.commands.delete_group --group-id <UUID>` for operators. If related data exists, `--include-related-data` is
required. The command displays counts, requires exact group-name confirmation, re-locks and re-counts before deletion, and
aborts if state changed. Cascades remove membership, invitations, albums and relations, chore history, shopping items and
shopping workflow rows,
photo shares, activity-group relations, and upload-batch shares. Photos remain; affected sidecars are synchronized after commit.

Membership removal and photo, upload, album, chore, and shopping operations that depend on membership are serialized by
locking the target `FamilyGroup` first and rechecking membership. When several kinds of rows are needed, lock groups, photos,
albums, chore tasks, and shopping items in that order.
Upload batch creation locks the requested groups before checking membership. Notification fan-out locks all target groups in
stable ID order before reading members, preventing membership removal from racing the read-and-enqueue operation.

Mutations that can change the last active system or group administrator use one PostgreSQL transaction advisory lock. The
lock is acquired before authorization checks and held through the decision and commit so system-admin status changes and
group-admin membership changes cannot leave an administrator invariant broken by a concurrent request.

### `features.chores`

Owns group-scoped chore categories, tasks, day intervals, and append-only completion history. Every group member may
create, rename, and delete unused categories; members may list and complete active tasks; group administrators may create,
edit, categorize, pause, and resume them. Category order is group-shared and updated through a complete ordered ID list.
Mutations lock the group, recheck membership, then lock the category or task.
Completion time always comes from the server's current UTC time. Completion rows store task and category name snapshots,
while their nullable category reference uses `ON DELETE SET NULL`. The monthly report endpoint aggregates completion rows
in SQL after converting the UTC range to the group's IANA time zone. It returns daily, category, member, and task/member
breakdowns without a report table; non-members receive `404`. Group administrators may update the group time zone, which
defaults to `Asia/Tokyo`.

### `features.shopping`

Owns active shopping requests, shared categories, shopping trips, purchase events that are append-only during normal correction
flows, assignment snapshots, trip-level amounts, and statistics. All group members may perform the operations; an assignee is informational and never a purchase
permission. In-store writes lock the group, recheck membership, then lock the item and trip, so concurrent completion of the
same request produces one success and one `409`. Starting a trip locks the group and resumes the latest in-progress,
non-discarded trip instead of creating a duplicate. Purchase events retain item, assignee, and category snapshots and are never
deleted by undo, correction, or discard. Trip amounts are nullable non-negative yen integers and are excluded from totals when
null. Trips can be finished immediately, discarded only while in progress, or permanently deleted when in progress with zero
purchase events or when finished. Deleting a finished trip removes its purchase events in the same locked transaction and
synchronizes affected planned-item state; deleting an empty trip uses the same locked transaction to remove it after confirmation.
Discarded trips and events are excluded from statistics. The history endpoint hides discarded trips by default and accepts
`include_discarded=true` for audit viewing; it uses an opaque `(started_at, id)` cursor, and statistics convert date boundaries
through the group's IANA time zone. Shopping trip PATCH requests preserve omitted fields; an explicit
`total_amount_yen: null` clears the amount. Purchase PATCH requests preserve omitted category and purchaser fields, allow an
explicit null category, and reject an explicit null purchaser with `422`. Existing legacy purchase state is converted by
`app.commands.migrate_shopping_history`, never by Alembic.

### `features.photos`

Owns upload, storage, metadata, authorization, sharing, favorites, activity, trash, export, and retrieval. Routers provide
photo, trash, export, and chunked-upload HTTP boundaries. Services coordinate storage and database work; `access.py` defines
owner and group-share visibility; `activity.py` handles New and read positions; `queries.py` handles search, cursors, and
month aggregation; `registration.py` prepares finalized photos, sidecars, and shares; `uploads.py` manages batch state;
`errors.py` owns photo-domain exceptions and `types.py` owns photo DTO/result types. The `storage/` package groups the
filesystem implementation: `storage/paths.py` owns storage-key and path safety validation, while `storage/types.py` owns
storage status, error, and staged/finalized-file types. `storage/uploads.py` and `storage/files.py` implement resumable
upload, sidecar, finalization, and deletion operations; `storage/facade.py` exposes the `PhotoStorage` facade for those
operations and storage state;
`thumbnails.py` creates WebP thumbnails from images or the first video frame, and `video_validation.py` validates supported
video containers with `ffprobe`;
`export.py` streams ZIP output without first creating a full temporary ZIP. `public.py` exposes only the read-only photo
catalog needed by other features. The use-case services are split by responsibility: `access_service.py` handles reads,
content, and favorites; `metadata_service.py` handles memos, capture-time overrides, and sharing; `registration.py` handles
finalized photo registration; `trash_service.py` handles trash transitions and permanent deletion; and
`export_service.py` validates ZIP-export selections. `metadata_persistence.py` coordinates sidecar writes, transaction
commit, and sidecar restoration when metadata persistence fails. Batch uploads remain in `uploads.py`.

### `features.albums`

Owns album creation, editing, deletion, and photo relationships. Album operations never modify originals or JSON sidecars.
Only photos already shared with the album's group may be added; album membership never grants photo visibility. The feature
uses only `features.photos.public`, not photo internals. A repository layer is intentionally deferred until service/database
logic becomes difficult to read.

### `features.maintenance` and `features.notifications`

Maintenance exposes administrator storage summaries and maintenance history. Integrity checks, database backup, secondary-HDD
snapshots, and trash purge run only as management commands and systemd timers, never from HTTP.

Notifications own session-bound Web Push subscriptions, preferences, and outbox. The database composite foreign key keeps
the stored subscription user and session owner identical. Photo sharing and shopping additions create
outbox entries in the same transaction as the business change; chore due notifications are enqueued periodically. Workers
exclude expired sessions, claim with timestamps and tokens, requeue stale claims, and retry only failed devices. Endpoints are
HTTPS and limited to configured provider hosts; VAPID private keys stay outside the repository. An endpoint hash already owned
by another user is rejected with `409 Conflict` and the `push_subscription_endpoint_conflict` error code; the subscription
limit uses `push_subscription_limit_reached`.

## Dependency direction

```text
router
  ↓
service
  ├── SQLAlchemy Session
  ├── registration (read-only session + storage)
  └── storage
```

- Routers do not write files or run SQLAlchemy queries directly.
- Services do not depend on HTTP responses or status codes.
- Storage does not depend on FastAPI or SQLAlchemy.
- Models do not depend on routers, services, or schemas.
- Public service methods own use-case commit, rollback, and compensating deletion of finalized files.
- Shared registration logic does not commit or roll back.
- Features must not import another feature's internal modules; use `public.py` or an explicit public dependency.
- Architecture tests detect cross-feature internal imports.

## Application creation

`main.py` is limited to application creation and explicit router registration:

```python
from fastapi import FastAPI

from app.features.health.router import router as health_router
from app.features.photos.router import router as photos_router


def create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(photos_router, prefix="/api/v1/photos")
    return app


app = create_app()
```

Pass the lifespan explicitly to `FastAPI` and validate setting combinations when creating `Settings`. Do not require the
database or HDD to be available for process startup; check them when used so status endpoints can still explain failure.
Reject upload and original retrieval with `503` when storage is unavailable and uploads with `507` below the free-space safety threshold.

## Production boundary

Cloudflare is the public entry point, Caddy is the only origin HTTP entry point, FastAPI listens on loopback, and PostgreSQL,
the internal photo-storage HDD, and the disconnected external backup HDD are not exposed to clients. Serve originals only
through authenticated and authorized API endpoints.
See [`deployment.md`](./deployment.md) for Tunnel, Caddy, forwarded headers, cache, upload, ZIP, and acceptance details.

## API contract

MVP APIs use `/api/v1`. Informational routes outside this prefix are excluded from the OpenAPI contract. FastAPI's OpenAPI
schema is authoritative: frontend types, fetch clients, and SDKs are generated into
`frontend/src/shared/api/generated/` and must not be edited directly. Regenerate them after router or Pydantic-schema changes.

Every mutation must declare its authentication and CSRF requirements. Authentication and authorization are checked at the
service boundary as well as at the router boundary. Return `404` for resources whose existence must not be disclosed.

Sessions use a random HttpOnly cookie token and store only its SHA-256 hash. Mutations require the session-bound CSRF token.
Use `Cache-Control: private, no-store` for authenticated APIs and binaries.

Photo search provides `GET /api/v1/photos/search-options` for authenticated users who have completed password change.
The response contains stable, name-then-ID-sorted uploader and current-group candidates; uploaders are limited to
authors of active photos visible to the caller. Photo detail responses expose only share groups the caller currently
belongs to, and may therefore return an empty `group_ids` list for a shared photo. Owner metadata updates preserve
existing shares that the owner cannot currently see.

The administrator user list includes both `group_names` and `group_admin_group_names`. The latter lets the administration
client disable user deactivation when the user is the last active administrator of one of those groups; the server-side
invariant checks remain authoritative for stale or concurrent client data.

## File storage and thumbnails

```text
photo-storage/                       # Internal HDD; PHOTO_STORAGE_ROOT
├── originals/YYYY/MM/<UUID>.<ext>
│   └── <UUID>.json
└── incoming/<UUID>.part

backend/var/photo-derivatives/       # Regenerable internal-SSD data
├── thumbnails/YYYY/MM/<UUID>.webp
└── incoming/<UUID>.thumbnail.part

snapshots/<timestamp>/                # Disconnected external HDD; BACKUP_STORAGE_ROOT
├── originals/
└── database-backups/
```

Keep `originals` and `incoming` on one filesystem so finalization can use an atomic rename. `PHOTO_STORAGE_ROOT` must point
to the HDD mount point itself. A root `.photo-storage-marker` must match `PHOTO_STORAGE_MARKER`; the root and marker must not
be symlinks. Linux mount information is checked when available, with a standard mount-point fallback. A bind mount is valid
for internal-SSD development tests, but production must point at the internal photo-storage HDD mount. `BACKUP_STORAGE_ROOT`
must point at a separate mounted external HDD and is used only by maintenance commands.

Never use client filenames or extensions to construct paths. The server chooses extensions after content validation. Accept
JPEG, primary-image MPO, PNG, and HEIF/HEIC without recompression. Also accept MP4, QuickTime MOV, and M4V video files;
`ffprobe` must find a supported container and a usable video stream. Registration requires positive display-oriented width
and height from every accepted image or video, applying EXIF image orientation and video rotation metadata before storing
dimensions. Use the first MPO image or first video frame for validation and thumbnails while preserving the original file.

At finalization, create a WebP thumbnail with a longest edge of at most 480 px, quality 80, and method 4 on the internal SSD.
Do not enlarge small images and preserve alpha. Lists and albums use thumbnail APIs; the enlarged modal uses the original
API. Originals, downloads, thumbnails, and ZIP exports return `private, no-store`.

Sidecars use schema version 8 and contain original recovery data, derivative locations, editable memo metadata, owner-entered
capture-time overrides, and `group_ids`. The database stores `effective_captured_at` as the denormalized sort value
`captured_at_override`, then original EXIF `captured_at_original`, then `uploaded_at`. It is synchronized at registration and
override updates; `captured_at_original` and `captured_at_override` remain separate so the API does not present upload time as
a known capture time. `ix_photos_sort_date_id` covers `(effective_captured_at DESC, id DESC)`.
After a sharing or sidecar-schema migration, run `python -m app.commands.sync_photo_sidecars` to regenerate every sidecar
from the database.

## Upload processing

Register a batch, its share groups, and its items. Batches are valid for 24 hours. Serialize batch creation with a
transaction-level advisory lock, then include unreceived bytes from existing active batches in the free-space check.
Browsers send 8 MiB chunks; the server accepts at most 8 MiB and validates `Upload-Offset`. Each browser request has a
timeout; after a transient failure, the client reconciles the server offset and retries the chunk up to three times.
Reconcile the database position with `.part` size after interruption and resume only within the same open page. Expired
batches are canceled and temporary files removed on access or new-batch creation. Expiration cleanup locks the batch and all
its items in batch-then-item order before deleting resumable files, so it cannot race a chunk write.

The current five-second request timeout is intentionally short for development diagnostics on the LAN. It makes a stalled
request and its retries observable quickly; it is not the production timeout target and increasing it does not fix a
retained Safari response. Before production acceptance, use an environment-specific timeout based on real iPhone Wi-Fi and
mobile-network measurements, and ensure the development value is not included in the production build.

Each chunk attempt carries a client-generated attempt ID, retry count, and direct or same-origin route label. Browser
diagnostic messages and backend logs record the attempt ID, item ID, offsets, byte counts, response request ID, and timing.
The backend separately records request-body reception, durable `.part` synchronization, and offset-conflict recovery so an
interrupted request can be distinguished from a lost response. Do not log filenames, file contents, cookies, CSRF tokens, or
other credentials as upload diagnostics.

Successful `PATCH` responses use `200 OK` with a short, explicitly sized body instead of an empty `204`. After receiving the
status and `Upload-Offset` header, the browser aborts that request's response stream without waiting for its body only on
the development direct-upload route. This forces iPhone Safari to release a development-LAN cross-origin request instead of
retaining six responses and indefinitely queueing the seventh. Same-origin production responses are consumed normally.

The response-stream abort is a workaround for development uploads sent directly from the Vite origin on port `15173` to
FastAPI on port `18000`. Production uploads use the public same-origin `/api` path through Cloudflare, Caddy, and FastAPI;
the production response stream is not aborted by the browser.

The upload router streams each request body into a bounded temporary file and checks `Content-Length` before reading when it
is available. The service then streams that file into the durable `.part` file, so a request does not retain all received
chunks in memory. Upload state is committed before a cancel or expiration removes `.part`; if the database commit fails,
the `.part` remains available for offset reconciliation. Cleanup is best effort and the orphan-file maintenance command
recovers failed deletions. The production React client always uses chunked upload. The Cloudflare request limit and whole-file
`PHOTO_MAX_UPLOAD_BYTES` are separate constraints. The frontend sends at most two files concurrently and shows success,
duplicate, and failure independently; retry failed files without rolling back successful ones.

```text
Check Content-Length when available
  ↓
Validate HDD identity, mount, write access, and free space
  ↓
Write chunks to incoming/<UUID>.part and calculate size and SHA-256
  ↓
Validate size and actual image or MP4/MOV/M4V video content
  ↓
Read dimensions and EXIF or video creation time
  ↓
Check same-owner SHA-256 duplicate
  ↓
Create temporary WebP thumbnail and JSON sidecar
  ↓
Rename original, sidecar, and thumbnail into final locations
  ↓
Insert metadata, shares, and activity in PostgreSQL and commit
  ↓
Return 201 Created
```

Do not trust `Content-Length`, filename, extension, or declared MIME type alone. Validate actual image content with Pillow and
`pillow-heif`, and actual video content with `ffprobe`; reject AVIF and unsupported video containers. The runtime must have
the `ffprobe` and `ffmpeg` commands available for video validation and thumbnail generation. If any finalization step fails,
remove completed files when possible and report unremovable files for integrity recovery.

## Filesystem and database consistency

Original, sidecar, thumbnail renames, and PostgreSQL commit cannot be one transaction. Finalize in original → sidecar →
thumbnail → database order and compensate on failure. Keep stable path rules and sidecar schema so originals and sidecars can
rebuild photo metadata. The integrity command is read-only: it reports missing files, size mismatches, sidecar mismatches,
orphaned files, and unmatched `.part` files; `--verify-hashes` additionally reads originals to compare SHA-256. It returns
0 with no findings and 1 with findings and never changes files or the database. Automatic repair and sidecar-to-database
rebuild are not implemented. `python -m app.commands.cleanup_orphaned_photo_files` can remove orphaned originals, sidecars,
derivatives, and stale upload parts after a 24-hour grace period. It defaults to a dry run, requires `--apply` to delete,
and refuses an empty database unless `--allow-empty-database` is explicitly provided for an intentional full reset.

## Storage availability

Before upload, verify the configured root is the expected HDD mount, the marker exists and matches, `originals`, `incoming`, and
`database-backups` are writable, free space meets the safety threshold, and path resolution cannot escape the allowed root.
Integrity checks and database backups use the same validated storage-path derivation and reject absolute paths, `..`, and
symlinks without reading outside the root. A directory merely existing is not sufficient; this prevents writing to an
identically named internal-SSD directory when the HDD is detached.

## Database access and settings

Use SQLAlchemy 2 synchronous Engine and Session with psycopg 3. Create and close a session per request. Keep commit and
rollback boundaries explicit at service use-case boundaries. Manage all schema changes with Alembic and never create the
production schema implicitly with `create_all()`. Start with synchronous file and database I/O; measure before introducing
async database access.

Use typed settings and never hard-code environment paths or credentials. Both the web application and management commands use
the same settings loader: process environment variables take precedence, and `backend/.env` is the fallback for local direct
invocation. Key settings include `DATABASE_URL`, trusted origins,
session idle/absolute/touch limits, secure-cookie and login limits, fixed invitation expiry choices of 24, 72, or 168 hours,
`PHOTO_STORAGE_ROOT`, `PHOTO_DERIVATIVE_ROOT`, `BACKUP_STORAGE_ROOT`, storage markers, upload and free-space limits,
default timezone, Push provider allowlist and
subscription limit, and optional `MONITORING_PING_URL_*` values. The recommended development values in `.env.example` are
100 MiB maximum file size, 1 MiB chunks, and 10 GiB minimum free space; these are configuration examples, not code defaults.
Never place real `.env` values in code or documentation.

## Testing strategy

### PostgreSQL test databases

Unit tests use mocked sessions or temporary resources, so the normal test run does not need a database connection. The
PostgreSQL integration tests are skipped unless `TEST_DATABASE_URL` is set. The migration round-trip test additionally
requires `MIGRATION_TEST_DATABASE_URL`.

For local testing, use two disposable databases on the development PostgreSQL instance at `127.0.0.1:15432`. Reuse the
existing local PostgreSQL role and use `family_hub_test` and `family_hub_migration_test`. A development volume reset also
deletes these databases, so recreate them immediately after `docker compose up --detach --wait db`:

```bash
docker compose exec -T db sh -c \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "CREATE DATABASE family_hub_test"'
docker compose exec -T db sh -c \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "CREATE DATABASE family_hub_migration_test"'
```

The role must exist, while the databases must be created before running the tests. Never use the production PostgreSQL
endpoint at `127.0.0.1:5433` or a production database for tests.

Set the URLs in the current shell rather than committing credentials or adding them to repository files:

```bash
read -rsp 'TEST_DATABASE_URL: ' TEST_DATABASE_URL
echo
export TEST_DATABASE_URL
read -rsp 'MIGRATION_TEST_DATABASE_URL: ' MIGRATION_TEST_DATABASE_URL
echo
export MIGRATION_TEST_DATABASE_URL
```

Apply the latest schema to the ordinary integration-test database, then run the complete backend suite. The migration test
uses its separate empty database and applies and rolls back the full Alembic history itself:

```bash
DATABASE_URL="$TEST_DATABASE_URL" uv run --locked alembic upgrade head
uv run --locked pytest
```

The ordinary integration-test database receives the latest schema before the suite runs. Keep
`family_hub_migration_test` empty; the migration round-trip test applies and rolls back the full Alembic history itself.

Unset the variables when finished if the shell will be reused for another database:

```bash
unset TEST_DATABASE_URL MIGRATION_TEST_DATABASE_URL
```

### Storage

Use pytest temporary directories, never the real HDD. Test chunk writes, hashing, original/JSON renames, size limits,
cleanup, sidecar schema and correspondence, orphan detection, unavailable-storage conditions, and backup-root rejection
when the external HDD is absent, unmounted, or has the wrong marker.

### Authentication

Test Argon2id, username normalization, token hashing, expiry, revocation, CSRF, trusted origins, login limiting, cookie
attributes, generic login errors, and session invalidation. Use real PostgreSQL concurrency tests for password-change/login
serialization.

### Services

Control Storage and Session boundaries to test success and cleanup after duplicate, commit, and finalization failures. Cover
chore authorization, admin roles, due calculation, pause, completion user, snapshots, monthly report aggregation,
time-zone boundaries, shopping ordering, purchaser, restore, and concurrent conflicts. Use real PostgreSQL for group-lock
serialization, all Alembic revisions, notification claim and stale
recovery, deduplication, per-device retries, and maintenance terminal states.

### Routers and migrations

Replace FastAPI dependencies with test Session and Storage implementations. Test resumable chunk upload, response schemas, and
domain-exception-to-HTTP conversion. Shopping tests cover assignment membership, purchaser/assignee differences, unplanned
purchases, nullable trip totals, reversal retention, cursor history, statistics, and the idempotent legacy conversion command.
CI must apply the latest migrations to an empty PostgreSQL database, while integration and unit tests remain separately runnable.

## Future design candidates and open decisions

Candidates include a home aggregation API if existing calls become a problem, repair commands for integrity findings,
background derivative regeneration, and non-iPhone or non-Safari support. Open decisions include exact HDD mount and
marker values, upload and free-space limits, derivative-cache policy, original range requests and caching, and independent
LAN HTTPS when Cloudflare is unavailable.

Person detection is excluded from the current backend contract; see [`proposals/person-detection.md`](./proposals/person-detection.md).

## Trash and permanent deletion

Photos move between `active`, `trashed`, and `purge_pending` without moving originals. Trash removes a photo from ordinary
authorization, lists, New, albums, and exports. Only the owner can view or restore it; shares, album relationships, memo, and
favorite data remain for restoration. Album counts, pages, and covers consider active photos only, while the `AlbumPhoto`
relationship remains so restoration returns the photo to its existing album memberships. The lifecycle is also stored in
sidecar schema 8.

Permanent deletion requests for `trashed` photos are accepted only after `purge_after`; an early request is rejected with `409`.
The request first commits `purge_pending`, then clears album covers for the photo in the same database transaction, idempotently
deletes original, sidecar, and derivatives, and finally deletes database rows. A photo already in `purge_pending` can be retried
regardless of its retention timestamp so interrupted work remains recoverable. `python -m
app.commands.purge_trashed_photos` retries interrupted work. The default retention period is 30 days.

日本語版: [backend-design.ja.md](./backend-design.ja.md)
