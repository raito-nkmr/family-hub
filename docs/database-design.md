# Database Design

## Purpose

This document defines the PostgreSQL schema, constraints, indexes, and migration policy for Family Hub photos, cleaning,
and shopping. Image files are stored on the internal photo-storage HDD; PostgreSQL stores metadata required for search and
integrity checks. JSON sidecars with the same UUID as each original are also stored on the internal HDD for recovery. A
disconnected external HDD stores versioned snapshots of the originals and database backups.

The current application schema is represented by a short three-revision linear baseline because the development and
pre-production databases are reset when the baseline is rebuilt. The revisions are divided by dependency boundaries so
each remains readable. Future approved schema changes should be added as new migrations. Tables for future features such
as person detection are not created until the feature is approved and its requirements are known.

```text
family_groups 1 ───── 0..N albums 1 ───── 0..N album_photos N..0 ───── 1 photos
photos 1 ───── 1 photo_metadata
photos 1 ───── 0..N photo_derivatives
photos 1 ───── 0..N photo_shares N..1 ───── 1 family_groups
users 1 ───── 0..N photo_favorites N..1 ───── 1 photos
photos 1 ───── 0..N photo_activity_events 1 ───── 1..N photo_activity_event_groups N..1 ───── 1 family_groups
users 1 ───── 0..1 photo_activity_states
users 1 ───── 0..N family_group_members N..1 ───── 1 family_groups
family_groups 1 ───── 0..N cleaning_tasks 1 ───── 0..N cleaning_completions
family_groups 1 ───── 0..N shopping_items
users 1 ───── 0..N upload_batches 1 ───── 1..N upload_items N..0 ───── 0..1 photos
upload_batches 1 ───── 0..N upload_batch_group_shares N..1 ───── 1 family_groups
users 1 ───── 0..N push_subscriptions N..1 ───── 1 user_sessions
users 1 ───── 0..N notification_preferences
users 1 ───── 0..N notification_outbox 1 ───── 0..N notification_deliveries
push_subscriptions 1 ───── 0..N notification_deliveries
maintenance_runs
administrative_audit_events
```

The diagram describes only the current schema. Unimplemented proposals are kept under `proposals/` and are not part of the
current relational contract.

## Shared rules

- Use PostgreSQL `UUID` primary keys.
- Generate UUID v4 in Python before writing temporary files, originals, or database rows.
- Store timestamps as `TIMESTAMPTZ` in UTC; keep the PostgreSQL session time zone at UTC.
- FastAPI returns UTC ISO 8601 timestamps and never converts them to JST at the DB/API boundary.
- React explicitly converts display values to `Asia/Tokyo`; JST date boundaries are used for date search and grouping.
- Store the denormalized `effective_captured_at` sort value as owner override, EXIF `captured_at`, then `uploaded_at`; keep
  the source capture fields separate so upload time is never presented as a known capture time.
- Do not store image data, absolute HDD paths, or environment-specific mount points in PostgreSQL.
- Give constraints and indexes stable names managed by Alembic.
- Avoid PostgreSQL-specific ENUMs for now; use strings with `CHECK` constraints so values remain easier to change.

Columns named `updated_at` use a server default for INSERTs only. Application services set them explicitly on every
supported update; the schema does not use a general-purpose update trigger.

## Timestamps

Database and API values are UTC; user-facing values are JST.

```text
PostgreSQL  2026-07-14 03:00:00+00
FastAPI     2026-07-14T03:00:00Z
React       July 14, 2026 12:00 JST
```

The server generates `uploaded_at`. EXIF capture times with an offset are converted using that offset. EXIF values without
an offset are interpreted as JST and then converted to UTC. Missing or invalid EXIF values produce a null `captured_at`.
React must pass `Asia/Tokyo` explicitly to `Intl.DateTimeFormat` or equivalent. JST date ranges are converted to UTC before
being sent to PostgreSQL so the late-night JST interval is included correctly.

## Core tables

### `users`

Stores family users created by a management command or administrator invitation. There is no public registration page.

| Column | Type | Null | Constraint / purpose |
| --- | --- | --- | --- |
| `id` | `UUID` | No | Application-generated primary key |
| `username` | `VARCHAR(64)` | No | NFKC- and case-normalized Unicode username; unique |
| `password_hash` | `TEXT` | No | Argon2id hash; never plaintext |
| `is_active` | `BOOLEAN` | No | Blocks login and existing-session use when false |
| `system_role` | `VARCHAR(16)` | No | `admin` or `user` |
| `must_change_password` | `BOOLEAN` | No | Set by operator password resets; cleared after the user changes the password |
| `created_at` | `TIMESTAMPTZ` | No | Creation time |
| `password_changed_at` | `TIMESTAMPTZ` | No | Invalidates older sessions |

`ck_users_username_lowercase` validates one to 64 Unicode letters or digits plus `.`, `_`, and `-`. Group roles are
independent of `system_role`; invitation acceptance always creates a `user`.

### `user_invitations`

Stores one-time account invitations issued by system administrators. It contains a normalized reserved username, a unique
SHA-256 token hash, creator, creation and expiry times, and optional used and revoked times. Only one unused, unrevoked
invitation may exist for a username. Acceptance locks the row, validates expiry, use, revocation, and username uniqueness,
then creates the user and sets `used_at` in one transaction. The raw token is returned only once and is never stored.
Creating a replacement invitation revokes any previous unused invitation for the same username, including an expired one,
in the same transaction before inserting the replacement.

### `user_sessions`

Stores server-side sessions. The raw cookie token is not stored; only its lowercase SHA-256 hash is stored in the unique
`token_hash` column. The table also stores a session-bound CSRF token, creation time, last-use time, absolute expiry, and
optional revocation time. `expires_at` must be later than `created_at`. Index `user_id` as `ix_user_sessions_user_id` to
revoke all sessions efficiently.

### `family_groups`

Stores family sharing scopes with a globally unique name, creator, creation time, and update time. Index
`created_by_user_id` for creator lookups.

### `family_group_members`

Stores the many-to-many user/group relationship and the group-local `admin` or `member` role. Use `(group_id, user_id)` as
the composite primary key and index `user_id`. Create a group and its creator's admin membership in one transaction. Lock the
group during membership and role changes and reject demotion or removal of the last active administrator before commit.

### `family_group_membership_invitations`

Stores group-admin invitations to existing active users, including group, invitee, inviter, proposed role, `pending`,
`accepted`, or `rejected` state, and creation and response times. Only one pending invitation per group and user is allowed.
Acceptance creates membership in the same transaction; group deletion cascades.

## Cleaning and shopping tables

### `cleaning_tasks`

Stores group-scoped cleaning locations, required fixed categories (`watering`, `cleaning`, or `children`), and day
intervals. `interval_days` is 1–3650, `is_active` defaults to true, and creator and timestamps are retained. Index
`(group_id, is_active)` as `ix_cleaning_tasks_group_id_is_active`. Do not store a countdown or `next_due_at`; calculate it
from the latest completion or `created_at` plus the interval. Pausing is a logical state change and preserves history.
Category filtering is performed by the authenticated client after loading the group task list.

### `cleaning_completions`

Append-only completion history with task, completing user, and server-generated UTC time. Index
`(task_id, completed_at DESC, id DESC)` as `ix_cleaning_completions_task_id_completed_at`. Concurrent completions are both
retained; the newest timestamp and UUID determine the next due time. Editing and deleting history are out of scope.

### `shopping_items`

Stores a group item, creator, optional purchaser, creation and update times, and optional purchase time. The purchaser and
purchase time must both be null or both be set. Index `(group_id, purchased_at, created_at)` as
`ix_shopping_items_group_id_purchase_state`; list unpurchased items by `created_at ASC, id ASC` and purchased items by
`purchased_at DESC, id DESC`. Lock rows while changing purchase state and clear purchaser and time when restoring an item.

## Photo tables

### `photos`

Stores one metadata row per original. Important fields are uploader and username snapshot, display filename, relative
`storage_key`, verified content type, positive size, lowercase SHA-256, dimensions, source capture and upload timestamps,
the denormalized `effective_captured_at` sort timestamp, lifecycle state (`active`, `trashed`, or `purge_pending`), and
trash/purge timestamps and owner. The same row represents either an
image or a supported video; `content_type` distinguishes them. Dimensions describe the displayed orientation after applying
EXIF image orientation or video rotation metadata.

Constraints include unique `storage_key`, required existing owner, unique `(uploaded_by_user_id, sha256)`, positive size,
lowercase 64-character SHA-256, required positive width and height, and valid lifecycle/timestamp combinations. Do not include
allowed media formats in a database `CHECK`; validate MIME type and file content during upload and recovery. Supported media
includes JPEG, primary-image MPO selected as JPEG, PNG, HEIF/HEIC, MP4, QuickTime MOV, and M4V.

### `photo_metadata`

Separates user-editable information from original metadata. It is keyed by `photo_id` and stores a memo of at most 2,000
characters, an optional owner-entered `captured_at_override`, memo attribution, last-edit time, optimistic-lock `version`, and
timestamps. `photos.effective_captured_at` is synchronized from `captured_at_override`, the original EXIF `photos.captured_at`,
or `photos.uploaded_at` when the override is cleared. The API continues to expose only the source/override capture values as
known capture times.
Viewers can edit the shared memo; only the owner can edit sharing or the capture-time override. Every metadata update
increments the version and synchronizes `metadata_version` in the JSON sidecar.

### `photo_derivatives`

Stores regenerable display files, initially one thumbnail per photo. Each row has an ID, photo ID, kind (`thumbnail`),
relative derivative `storage_key`, content type (`image/webp`), positive dimensions, and creation time. Photo deletion
cascades; storage keys are unique.

### `photo_shares`

Associates a photo with a family group. The composite photo/group key prevents duplicates. Authorization for lists and details
checks the owner or a current group membership; albums do not grant access by themselves.

### `photo_favorites`

Stores a user/photo pair with a creation time. Favorites are independent of sharing, albums, and other users.

### Activity tables

`photo_activity_events` records `uploaded` or `shared`, the photo, an operation ID, and occurrence time. Batch uploads and
bulk shares use one operation ID so New can group them; individual operations also receive an ID. `photo_activity_event_groups`
records groups that gained access at the event. Retrieval verifies current membership, membership start before the event, and
an active current share, excluding pre-membership and later-unshared events.

`photo_activity_states` stores each user's `(seen_through_at, seen_through_event_id)` read position. Unread events are newer
than that pair and currently visible to the user. Use `(occurred_at DESC, id DESC)` for cursor pagination.

## List indexes and search

Photo ordering uses the effective capture time: owner override, original capture time, then upload time:

```sql
SELECT *
FROM photos
ORDER BY effective_captured_at DESC, id DESC;

CREATE INDEX ix_photos_sort_date_id
    ON photos (effective_captured_at DESC, id DESC);
```

The date and UUID pair is stored in the cursor; fetch at most 100 rows smaller than the last pair. Use `pg_trgm` GIN indexes
for partial filename and memo search:

```sql
CREATE INDEX ix_photos_original_filename_trgm
    ON photos USING gin (original_filename gin_trgm_ops);
CREATE INDEX ix_photo_metadata_memo_trgm
    ON photo_metadata USING gin (memo gin_trgm_ops);
```

Convert `effective_captured_at` to `Asia/Tokyo` for month and date boundaries while keeping stored timestamps UTC. The
`captured_at` and `captured_at_override` columns remain separate so the API can distinguish known capture time from the
upload-time fallback.
Do not duplicate indexes already supplied by unique constraints.

## Upload tables and transaction

`upload_batches` stores browser batch ownership, `active`, `completed`, or `canceled` state, creation, resumable expiry, and
completion times. Index `(owner_user_id, created_at DESC)`. Expired active batches become canceled and their `.part` files are
removed on the next access or creation. Derive API `visibility` from zero or one-or-more share groups rather than storing it.
Recheck owner group membership when each file completes.

`upload_batch_group_shares` stores the unique `(batch_id, group_id)` share set applied to every finalized photo.

`upload_items` stores the browser `client_id`, original filename, declared content type, expected and received byte counts,
status (`queued`, `uploading`, `processing`, `succeeded`, `duplicate`, or `failed`), stable error code, optional photo ID, and
timestamps. `(batch_id, client_id)` is unique and received bytes must be between zero and size. Files complete independently;
one failure does not roll back successful photos.

After each chunk, commit `received_bytes` so the `.part` size can be reconciled after interruption. After receipt, commit the
item as `processing`, finalize original, sidecar, and WebP thumbnail, then insert `photos`, `photo_metadata`,
`photo_derivatives`, required shares, and activity rows in one transaction. Use `UploadItem.id` as `Photo.id` to make retries
idempotent.

```text
Finalize original on HDD
  ↓
Finalize JSON sidecar on HDD
  ↓
Finalize WebP thumbnail on internal SSD
  ↓
Insert photos, photo_metadata, photo_derivatives, and photo_shares
  ↓
Insert activity event and target groups when shared
  ↓
Commit one database transaction
```

If the commit fails, try to remove finalized files; unrecoverable files become integrity-recovery candidates. File renames and
database commits cannot form one transaction, so maintenance checks must find partial originals, sidecars, thumbnails,
unregistered files, and database rows missing files.

## Albums and file mapping

`albums` stores title, optional description, group, cover photo, creator snapshots, and timestamps. Names need not be unique.
Members of the group can view and edit albums. List by `updated_at DESC, id DESC` and count `album_photos`.

`album_photos` has composite primary key `(album_id, photo_id)` and `added_at`. Index `photo_id`; order album photos by
`effective_captured_at ASC, photos.id ASC`. An unset cover falls back to the oldest added photo. A cover must
belong to the album, and removing a photo clears the cover. Removing a group share also removes the inaccessible album
relationship in the same transaction. Album relationships are not written to JSON sidecars.

Store only relative keys, for example:

```text
originals/2026/07/550e8400-e29b-41d4-a716-446655440000.jpg
```

`YYYY/MM` is based on upload time, not capture time. Changing capture metadata does not move an original. Do not use
`original_filename` to construct paths. Store accepted JPEG, primary-image MPO, PNG, HEIF/HEIC, MP4, QuickTime MOV, and M4V
bytes without recompression or format conversion. Validate actual content during upload and recovery rather than trusting
`content_type` alone. Video thumbnails are regenerable first-frame WebP derivatives; video conversion and streaming
optimization are not part of this implementation.

## JSON sidecars

Store one same-UUID JSON file beside every original. The sidecar is recovery information, not the source for ordinary lists or
search. Schema version 7 separates the original and derivative asset data, editable metadata, sharing, and lifecycle state:

| Field | Purpose |
| --- | --- |
| `schema_version` | Sidecar format version |
| `id` | UUID shared by `photos.id` and the original filename |
| `metadata_version` | Matches `photo_metadata.version` |
| `asset` | Uploader, original details, dimensions, timestamps, and derivatives |
| `metadata` | Shared memo and its last editor and timestamp |
| `sharing` | Sharing audiences, currently family-group IDs with their audience type |
| `lifecycle` | Current trash and permanent-deletion state |

The current integrity command uses PostgreSQL as the reference and is read-only. It verifies UUID/path correspondence,
original size, optional hashes, sidecar contents, and derivative files. `sync_photo_sidecars` rewrites sidecars from current
database records. Automatic repair and sidecar-to-database rebuilding are not implemented; restore the database from a backup
if PostgreSQL is lost. Thumbnail locations are recorded for integrity checks, but not other regenerable derived data such as
person-analysis results.

## Maintenance and notification tables

`maintenance_runs` stores job type, status, start/end times, structured summary, and a non-secret failure reason.
`administrative_audit_events` stores administrative scope, actor ID and username snapshot, target, non-secret JSON details,
and time. It deliberately has no foreign keys to actors or groups so audit rows survive physical deletion.

`push_subscriptions` associates an endpoint and encryption keys with a user and login session. A composite foreign key to
`(user_sessions.id, user_sessions.user_id)` prevents a subscription from pairing one user with another user's session.
`notification_preferences`
stores photo-sharing, cleaning-due, and shopping-added preferences per user. `notification_outbox` has a unique recipient
and deduplication key and is created in the same transaction as the business operation. `claimed_at` and `claim_token` track
worker ownership. `notification_deliveries` uses the outbox/subscription pair as a composite key and stores per-device
attempt count, status, completion time, and a non-secret error code.

## Future schema and migration policy

Do not add tables for person detection, tags, face recognition, or scene classification until their requirements are approved.
The provisional person-detection model is in [`proposals/person-detection.md`](./proposals/person-detection.md).

The development and pre-production history is reset and rebuilt as the following immutable baseline chain:

- `20260821_01_core` — extensions, identity, and family groups
- `20260821_02_media` — photos, activity, uploads, and albums
- `20260821_03_household` — cleaning, shopping, notifications, maintenance, and audit

The final constraints and indexes, including forced password changes, lifecycle invariants, and required positive photo
dimensions, effective photo capture time, and cleaning categories, are included in the baseline chain. Never rewrite these
revisions after the rebuild; future approved schema changes must be added as new migrations.

Alembic migrations are schema-only: they may create or alter schema objects and schema defaults, but must not insert,
update, delete, seed, transform, migrate, or backfill application data. Required application data is created by separate
bootstrap or management commands. Development and pre-production resets are separate operations; do not use the
development reset procedure against a real-data environment. Do not create schema implicitly with application startup
`create_all()`; every schema change must be an Alembic migration that can be applied and rolled back in a controlled unit.

日本語版: [database-design.ja.md](./database-design.ja.md)
