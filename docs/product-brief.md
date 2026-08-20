# Family Hub

## Overview

Family Hub provides several household web applications on shared authentication and family groups: a photo application
that stores and displays photos from an iPhone, a cleaning application for sharing tasks and schedules, and a shopping list
for household purchases. The primary client is Safari 17 or later on iPhone; support for other devices and browsers may be
considered later.

The project is also intended as a learning project for web application development using FastAPI, React, Vite, and
PostgreSQL. The product should be built as a small working application first, then expanded incrementally rather than
starting as a full-featured photo-management service.

## Current implementation status

The following scope is implemented: the core MVP; authentication; invitation-based account creation by a system
administrator; private photo use and sharing with multiple family groups; per-photo shared memos editable by viewers;
per-user favorites; group albums with cover selection; a new-photo activity view and read state; bulk sharing of up to 100
owned photos; group membership management; group-scoped cleaning; and group-scoped shopping lists.

Cleaning supports task names, day-based intervals, pause and resume, completion user and timestamp, and next-due display.
Cleaning and shopping remember the last selected family group in browser storage and use it when a page opens without an
explicit group in the URL.
Batch photo and video upload supports multiple share groups, per-file progress, retry, cancellation, server-side resumable
state kept for 24 hours, and partial success. JPEG, PNG, HEIF/HEIC, MP4, QuickTime MOV, and M4V are supported. A WebP
thumbnail with a longest edge of at most 480 px is generated synchronously from the image or the first video frame when an
upload is finalized. Lists and albums serve thumbnails; the enlarged modal serves images or playable video originals. Resume from React is
limited to retrying requests while the same page remains open; resume after a page reload is not implemented.

Automated frontend and backend tests, CI, and TypeScript API generation from OpenAPI are in place. Shopping lists allow all
group members to add items and record the purchaser and purchase time. The recent 20 purchased items can be restored to
the unpurchased state.

The home screen aggregates recent photos, unread photo updates, active cleaning tasks across all groups, and unpurchased
shopping items. A read-only photo-storage integrity command reports missing originals, JSON sidecars, thumbnails, size or
content mismatches, and orphaned files using the database as the reference. Original SHA-256 recalculation is optional.
Photo details can download an accessible original by its original filename. The library can select up to 100 visible photos
and stream them as one ZIP for manual backup.

The Account screen supports password changes after checking the current password, active-session listing, individual
session revocation, and logout from all devices. A password change revokes every existing session and requires login again.
There is no email-based password recovery; an operator who verifies the user's identity resets a temporary password using a
management command. The reset also revokes all sessions, and the user must change the temporary password immediately after login.

Fixed UI text, operation messages, warnings, and errors support English and Japanese. English is the default and source
language for UI translations. The `EN` / `JA` toggle changes the language, which is stored in the browser and also controls
the HTML `lang` attribute and date and number formatting. User-entered filenames, usernames, group names, album names,
descriptions, and memos are displayed without translation.

A public bilingual privacy page is available from the shared footer before and after login. It describes stored information,
purposes, group visibility, retention, deletion, backup, external services, cookies, browser storage, and how to contact an
administrator. The footer displays the application version from `frontend/package.json` at build time.

The frontend is mobile-first. On iPhone-sized screens, Home, Photos, Cleaning, Shopping, and Other appear in bottom
navigation. New, Library, Albums, and Trash are tabs inside Photos; Groups, invitation administration, Account, and the
administrator-only System screen are under Other. Screens wider than 900 px switch to a left sidebar and expand the photo
area and other features.

The photo list uses 50-item cursor pagination with infinite scrolling, a year/month timeline, date range, uploader, shared
group, favorite, capture-time presence, and memo/original-filename search. The album photo picker uses the same pagination,
infinite scrolling, and search controls. Failed automatic loading can be retried manually. Infinite scrolling combines
`IntersectionObserver` with direct scroll-position checks for iPhone Safari.

On mobile, the photo list shows thumbnails with month headings, favorite state, and sharing state. Users can choose 2, 3,
or 4 columns; 3 is the default and the choice is stored in the browser. Filename, capture time, and file format are shown
in photo details. On desktop, clicking the left or right edge of the enlarged photo view moves to the adjacent photo;
horizontal swipes provide the same navigation on mobile. Both operate on photos already loaded in the library.
Photo details fit the complete image or video inside a bounded media stage without cropping. If the device cannot display or
play an original, the unavailable-preview message retains the same bounded stage instead of collapsing vertically. Search
conditions and the upload panel start collapsed on mobile; the active search count appears on the search toggle, and the
upload panel stays open while uploading. Both are always visible at widths of 641 px or more.

The New view shows photos uploaded by other users to the user's groups and photos newly shared with those groups, ordered
by operation time. A batch upload or bulk share is represented as one operation. Events before group membership, the user's
own operations, and photos no longer shared with the user are excluded. Opening New stores the latest event as the user's
read position. Existing photos are not backfilled as activity events during migration.

The library can select up to 100 visible photos for export. Adding groups as sharing targets remains limited to selected
photos uploaded by the current user; photos already shared with a selected group are unchanged. After a successful upload,
the upload panel can pass saved photos to the same bulk-sharing flow.

The implemented scope also includes an owner trash, restore, retryable permanent deletion after a 30-day retention period, administrator
storage and maintenance status, database backup, versioned snapshots to a disconnected external HDD, a PWA app shell, iPhone Home Screen
instructions, and the Web Push backend foundation. The install prompt appears only in a normal browser tab, persists its
dismissed state in the browser, can be shown again from Account, and is hidden in standalone mode. Trash uses the same 2/3/4
thumbnail density choices as the library. Album details and trash also use 50-item cursor pagination and infinite scrolling.

Cloudflare Tunnel and Caddy provide the fixed HTTPS production path. Family Hub is currently operated through a custom
domain on the Cloudflare Free plan using one Named Tunnel. Cloudflare Access is not used. Production database separation,
database-backup, photo-integrity, and trash-purge timers, the first manual runs, and a temporary-database restore test are
complete. Device-specific Web Push subscriptions, unsubscriptions, and preference UI are implemented. Some operational
validation may remain. Person detection, automatic repair and full recovery from analysis results, and tags are not part
of the completed scope. Video upload and playback are implemented for the supported formats above. See [`web-push.md`](./web-push.md) and
[`deployment.md`](./deployment.md) for the current documented operational prerequisites. Update this section when
implementation status changes.

## Development direction

Prioritize everyday usability of Family Hub, integration between existing features, and safe photo operations. Do not fix
the next feature set in advance; choose it after reviewing user problems and implementation cost.

Person detection remains a future candidate, not a near-term feature. Consider it only after photo volume and search
problems establish a need and the asynchronous-processing and thumbnail foundations are stable. Reassess model accuracy,
processing load, licensing, and maintenance cost before starting. The provisional proposal is in
[`proposals/person-detection.md`](./proposals/person-detection.md).

### Provisional roadmap

This is not a committed implementation plan. Revisit it after each feature based on actual usage, cost, and safety.

- Next candidate: verify maintenance-timer automation, reboot recovery, and authenticated core features.
- After infrastructure cleanup: accept the PWA, notifications, and core features on a real iPhone.
- Only when clearly needed: tags and person detection.
- Important non-software task: connect the external backup HDD, run the snapshot, verify the result, and disconnect it.

Original downloads and exports, password and session management, and safe trash state transitions are implemented. PWA
operation and Web Push depend on the HTTPS production path. Decide on tags and person detection only when photo
volume and usage requirements justify them.

## Current hardware and operations

- Internal SSD: 500 GB
- Current external HDD: one 2 TB drive, currently used as the photo-storage device until the hardware cutover
- Planned internal HDD: primary photo and video storage
- Planned external HDD: disconnected backup storage, mounted only while snapshots are running
- Manually back up irreplaceable files to cloud storage.
- Treat files that exist only on the primary HDD as unbacked-up.

## Technology

- Backend: FastAPI and Python 3.13
- Frontend: React, React Router, TanStack Query, TypeScript, and Vite
- Frontend E2E: Playwright with an iPhone-like WebKit configuration
- Database: PostgreSQL
- Development: PostgreSQL via Docker Compose; FastAPI and Vite started separately on the host

## Storage policy

The target layout below applies after the internal-HDD cutover. Until that cutover, the current external HDD may remain
configured as `PHOTO_STORAGE_ROOT`; it must not also be treated as a backup of itself.

### Internal HDD

The internal HDD is the primary photo storage device. It stores photo and video originals, recovery JSON metadata, in-progress
upload files, and database backups staged for the external snapshot. Originals are stored in directories based on upload date
and use server-generated UUIDs as filenames. Capture time
is used for organization, list ordering, search, and date timelines, but not for choosing the HDD directory because EXIF may
be absent or not yet parsed.

Each original has a JSON sidecar with the same UUID. It records the schema version, ID, upload user ID and username,
filename, storage path, MIME type, file size, SHA-256 hash, media dimensions, capture and upload times, derivatives, shared
memo and its last editor and timestamp, share targets, and lifecycle state. The current integrity command uses PostgreSQL as
the reference, and sidecar-to-database re-registration or automatic thumbnail repair is not implemented; restore the database
from a backup after database loss.

```text
photo-storage/                       # Internal HDD
├── originals/
│   └── 2026/07/
│       ├── <UUID>.jpg
│       └── <UUID>.json
├── incoming/
└── database-backups/

backend/var/photo-derivatives/       # Internal SSD; configurable with PHOTO_DERIVATIVE_ROOT
└── thumbnails/YYYY/MM/<UUID>.webp
```

### Disconnected external HDD

The external HDD is not used by normal application requests. When mounted, the secondary-storage backup command creates a
versioned snapshot containing `originals/` and `database-backups/` from the internal HDD. The backup root is protected by a
separate marker so an incorrectly mounted disk cannot be used as a backup target.

### Internal SSD

The internal SSD stores the application, PostgreSQL data, thumbnails, and regenerable caches. Do not normally duplicate
photo or video originals there. Set a future usage limit so thumbnails and caches cannot consume the SSD.

### Cloud storage

Cloud storage is for irreplaceable photo and video originals and, when needed, important metadata or database backups. It is
manual for the time being.

## Production deployment policy

In production, Cloudflare is the public Internet entry point, Caddy is the only HTTP entry point on the origin, and
Cloudflare Tunnel serves the React frontend and API on one origin. Family Hub authentication remains primary; Cloudflare
Access is not used. Caddy, FastAPI, PostgreSQL, the internal photo-storage HDD, and the disconnected external
backup HDD are not exposed directly to the Internet or LAN.

Listening ports, trusted proxies, cache, upload limits, ZIP-export acceptance, and LAN access are defined in
[`deployment.md`](./deployment.md). The fixed HTTPS production path is active. The production environment is separated
from the development Compose database, and database-backup, photo-integrity, and trash-purge timers are configured. Local
development continues to start Vite and Uvicorn separately.

## First completion goal

From an iPhone connected to the home Wi-Fi, log in, upload one photo, save it safely to the internal HDD, and display it in React.

## MVP

1. Access from iPhone Safari 17 or later on the home Wi-Fi and log in.
2. Select JPEG (including the primary image from iPhone-generated MPO), PNG, HEIF/HEIC, MP4, QuickTime MOV, or M4V media.
3. Upload the media to FastAPI.
4. Store the original on the internal HDD.
5. Read capture time when it exists in EXIF.
6. Store file metadata in PostgreSQL.
7. List uploaded media in React, newest capture time first.
8. Select media for enlarged display or playback.
9. Detect duplicate uploads by the same user using the SHA-256 hash.

## Authentication policy

The target is approximately ten family users, not public self-registration. Create the initial system administrator with a
backend command. The management command refuses to create a regular user until at least one active system administrator
exists. A system administrator then issues a one-time invitation URL for a specified username. Usernames may
contain Unicode letters and numbers, including Japanese, plus periods, underscores, and hyphens. Invitation URLs contain no
username; only a URL-safe random token is stored in the fragment.

The invitee sets a password and creates a regular account. Management-command creation of regular users remains available.
Passwords are hashed with Argon2id and never stored in plaintext. New or changed passwords are 8–128 characters. Password
changes verify the current password and revoke every session, including the current one.

Password recovery is limited to an operator with server and database access. Temporary passwords must not appear in command
arguments, environment variables, shell history, or command output and must be entered invisibly in the terminal.

Each photo records its uploader as its owner. New uploads default to `private`; the owner may share a photo with zero or
more of their family groups. Only the owner and members of target groups can view it. Adding a photo to an album grants no
new access; the photo must already be shared with the album's group. Unauthorized photo IDs are treated as not found.

After login, use a server-side session represented by a sufficiently long random token in an HttpOnly cookie. Store only the
SHA-256 token hash in PostgreSQL. Sessions can be revoked by logout, expiration, password change, or user deactivation.
Mutation APIs require a session-bound CSRF token. Users can view session last-use and expiration times and revoke any other
active session individually.

Production requires Cloudflare, Caddy, HTTPS, Secure cookies, and same-origin delivery. HTTP cookies are allowed only for
localhost development. Photo metadata, storage status, upload, and original retrieval require authentication; only health,
login, and invitation acceptance APIs are public.

The system has `admin` and `user` roles. Only system administrators issue, list, cancel, and hide invitation history. Accounts
created from invitations are always regular users. A system administrator must re-enter the current password to deactivate
or reactivate users and change system roles. The last active system administrator or group administrator cannot be removed,
and web-based physical user deletion is not provided. Invitations are username-bound, valid for 1, 3, or 7 days, and usable
once. Only a cryptographic token hash is stored in the database; the token is kept in the URL fragment to avoid ordinary
HTTP logs and Referer headers.

## Family groups

Users can belong to multiple family groups to separate scopes such as a household and an extended family. Group `admin` and
`member` roles are independent of system `admin` and `user` roles.

Any logged-in user can create a group and is registered as its administrator. Users see only their groups; group existence is
not disclosed to non-members. Group names are globally unique, and duplicate creation is rejected.

Group administrators can rename a group and invite an existing active user who is not a member. Membership is created when
the invitee accepts. Administrators can change `admin` and `member` roles and remove membership after reviewing impact counts.
Members cannot perform administrative actions. Every group must retain at least one active administrator; the last active
administrator cannot be demoted or removed. Only accounts created by invitation acceptance or management command can be added.

Group physical deletion is available only as an operator management command, not through the web API or UI. Before deletion,
show counts for members, invitations, albums, cleaning history, shopping items, photo shares, activity events, and upload
batch targets. Require an exact group-name confirmation. Delete related data only with an explicit option. Preserve photo
records, originals, and thumbnails, and synchronize affected JSON sidecars with the remaining share state.

Owners can share a photo with multiple groups. Each album belongs to one group and is visible and editable by that group's
members. A cover is selected explicitly, with the first added photo as the fallback. Removing a group share also removes the
photo and cover assignment from albums of that group. A group administrator can re-enter the current password to remove
another user's share for that group; the photo remains and the action is recorded in the audit log. System administrators see
user, group-health, maintenance, and all audit information; group administrators see related counts and that group's audit log.
Favorites are independent of sharing and albums and belong only to each user.

Batch uploads verify group membership both when the batch is created and when each file is finalized. If membership is
removed after batch creation, unfinished items are stopped so the old permission cannot share new photos.

## Cleaning application

Household members share cleaning locations and completion state for areas such as the kitchen, bathroom, and living room.
Cleaning data belongs to a family group and is independent of the photo `family` visibility scope.

- Group administrators manage task names, intervals of 1–3650 days, and active or paused state.
- All group members can view active tasks and record completion.
- Completion records the server time and user without overwriting history.
- The next due time adds the interval to the latest completion, or to task creation time when no completion exists.
- React calculates countdown display from `next_due_at` and current time; countdowns are not stored in the database.
- Pausing a task preserves history, and administrators can resume it later.
- Non-members are not told that tasks or the group exist and receive not-found behavior.

The initial schedule is a day interval measured from completion time. Calendar schedules such as every Monday or the first of
each month, assignees, notifications, points, and completion undo are future features.

## Shopping list application

Family members add items when they notice a need and mark them purchased from a phone while shopping or after returning home.
The list is shared per family group.

- All group members can add an item between 1 and 120 characters.
- Unpurchased items are shown oldest first.
- Any member can mark an item purchased; the purchaser and server time are recorded.
- The latest 20 purchased items are shown newest first and can be returned to unpurchased.
- Purchase and unpurchase operations are serialized with row locks; operations against stale state are rejected as conflicts.
- Non-members are not told that items or the group exist and receive not-found behavior.

Quantity, unit, memo, store, and category are not separate fields initially and may be included in the item name. Assignees,
notifications, real-time sync, item edit/delete, permanent purchase-history audit display, and recurring-item re-add are future features.

## Future person-detection policy

Person detection is not implemented and is not part of the current committed roadmap or implementation contract. Reassess
accuracy, processing cost, licensing, and maintenance if a clear need emerges. The provisional proposal is in
[`proposals/person-detection.md`](./proposals/person-detection.md).

## Albums

Albums organize photos into collections such as a trip. They are an addition after the MVP. React switches between photos and
albums with tabs and supports album creation, editing, deletion, adding photos, and removing photos. Browsing prioritizes
photos; cover selection and removal appear only in an “organize photos” mode. Multiple photos can be selected; cover selection
requires one selection and removal requires at least one.

- A photo can belong to multiple albums.
- An album belongs to one family group and is visible and editable by all group members.
- Album membership grants no photo access.
- Only photos already shared with the album's group can be added.
- Albums have a name, optional description, group, creator, and creation and update timestamps.
- Photos are ordered by oldest capture time, falling back to upload time when capture time is unknown.
- A cover can be selected; the first added photo is the fallback.
- Deleting an album or removing a photo from it never deletes the photo, original, or JSON sidecar.
- Manual photo reordering is not part of the initial implementation.

Album relationships are editable organization data stored only in PostgreSQL and not in photo JSON sidecars. Restoring photo
metadata and album structure after database loss therefore requires a database backup; sidecar-to-database re-registration is
not currently implemented.

## Metadata

PostgreSQL stores metadata rather than image content. At minimum it stores ID, uploader ID and username, upload filename,
HDD path, MIME type, file size, SHA-256 hash, capture time, upload time, and media dimensions. See
[`database-design.md`](./database-design.md) for tables, constraints, and indexes.

Thumbnail locations are recorded in JSON for integrity checks, and owner-entered capture-time overrides are recorded for
recovery. A command to re-register photo metadata by scanning originals and JSON sidecars is not currently implemented. The
original EXIF capture time is retained separately; lists, search, timelines, and album ordering use the owner override when
present.
Person-analysis results and future tags are not recorded in sidecars; restore or regenerate those from database backups when
necessary.

Lists prioritize capture time and use upload time only when capture time is unavailable. The UI distinguishes unknown capture
time from upload time.

## Dates and time zones

- Store database timestamps in UTC.
- Return UTC ISO 8601 timestamps from FastAPI.
- Convert timestamps to Japan Standard Time (`Asia/Tokyo`) for React display.
- Use JST date boundaries for date search, grouping, and timelines.
- Interpret EXIF capture times without an offset as JST before converting to UTC.

For example, `2026-07-14T03:00:00Z` is shown as `July 14, 2026 12:00` in the UI. Display must not depend on the time zone
configured on the browser or server operating system.

## Safety requirements

- Reject uploads when the HDD is not mounted, is read-only, or is not the expected device.
- Check free HDD space and warn or reject before capacity is exhausted.
- Count unreceived bytes as reserved capacity when creating batch uploads and include concurrent batches.
- Never fall back to a same-named directory on the internal SSD when the HDD is absent.
- Never use a client-provided filename directly as a storage path.
- Use temporary names or extensions for incomplete uploads.
- Rename to the final storage name only after the original and JSON sidecar are fully written.
- Detect missing and orphaned originals, sidecars, and database records.
- Stream files in bounded chunks rather than loading them entirely into memory.
- Validate allowed formats and maximum file size on the server.
- Store uploaded originals as received without recompression or format conversion.
- Never expose originals as unauthenticated static files.
- Require application authentication for every data API except health, login, and invitation acceptance.
- Never store session tokens in plaintext in localStorage or PostgreSQL.
- Use HTTPS and `Secure`, `HttpOnly`, and `SameSite` cookies in production.
- Validate CSRF tokens on cookie-authenticated mutation APIs.
- Avoid revealing whether a username exists in login failures and rate-limit attempts.

## Out of scope for the MVP

- Fully automatic iPhone backup
- Public registration for arbitrary users
- Video conversion or streaming optimization
- Person detection, face recognition, personal identification, or scene classification
- NAS or RAID support
- Automatic cloud backup

## Future candidates

- Repair and recovery commands for integrity findings
- Background regeneration of derivatives for existing photos
- Devices other than iPhone and browsers other than Safari
- Additional EXIF fields
- Tags
- A lightweight-DNN people filter
- Scene classification after operating person detection is understood
- Scheduled or operator-triggered snapshots to a disconnected external HDD
- Calendar cleaning schedules, assignees, notifications, and completion undo
- Shopping quantity, unit, store, category, assignee, notifications, real-time sync, and recurring items

## Open decisions

- Maximum file size
- Derivative-cache storage limit and deletion/regeneration policy
- Whether to provide independent LAN access when Cloudflare is unavailable

日本語版: [product-brief.ja.md](./product-brief.ja.md)
