# Production Deployment Design

## Purpose and status

This document defines how Family Hub is served at the same HTTPS URL from iPhones inside and outside the home. It is the
source of truth for the current deployment architecture and acceptance criteria. Family Hub is currently operated through
a custom domain on the Cloudflare Free plan using one Named Tunnel, with Caddy, Uvicorn, and the application release on
the origin host. The repository does not include host-specific production state; operators should record and verify that
state outside the repository using this design and the production runbook.

Family Hub authentication remains the primary authentication system, and Cloudflare Access is not used. Because the public
hostname is reachable from the Internet, all data APIs except health, login, and invitation acceptance remain protected by
Family Hub session authentication and authorization.

## Target architecture

Cloudflare is the public Internet entry point and Caddy is the only HTTP entry point on the origin host.

```text
iPhone at home or away
        ↓ HTTPS
Cloudflare Edge
        ↓ Cloudflare Tunnel
cloudflared
        ↓ http://127.0.0.1:8080
Caddy
  ├── /*     → frontend/dist
  └── /api/* → http://127.0.0.1:8000
                         FastAPI
                            ├── 127.0.0.1:5433
                            │     Docker PostgreSQL
                            └── External HDD
```

- Production uses a Named Tunnel with a fixed hostname; Quick Tunnels are limited to temporary development checks.
- Do not port-forward ports 80, 443, 8080, or 8000 on the router.
- Do not expose Caddy, FastAPI, PostgreSQL, or photo storage directly to the Internet or LAN.
- Do not put photo originals under Caddy's static file root; serve them through authenticated and authorized FastAPI endpoints.
- Static content and APIs must use the same origin from the browser's perspective.

Cloudflare Tunnel Published Applications can connect a public hostname to a local service. Quick Tunnels are officially
intended for testing and are therefore not part of the production path.

## Listening and process boundaries

| Process | Listen / connection | Policy |
| --- | --- | --- |
| `cloudflared` | Outbound connection to Cloudflare | Creates no inbound Internet port |
| Caddy | `127.0.0.1:8080` | Reachable only from `cloudflared` |
| Uvicorn | `127.0.0.1:8000` | Reachable only from Caddy |
| PostgreSQL | `127.0.0.1:5433` | Managed by the production-only Compose project and unreachable from clients |

The production database is managed by `deploy/compose.production.yaml` and separated from the development `compose.yaml`.
The production Compose project is `family-hub-production`, and its volume is `family-hub-production-postgres-data`. Create
the volume as an external volume in advance so `compose down --volumes` cannot remove it. Development PostgreSQL uses
`127.0.0.1:15432`. Development FastAPI listens on `127.0.0.1:18000`, and Vite listens on `127.0.0.1:15173` while its
`/api` proxy uses the development backend port. Keep the backend ports separated so the development frontend cannot
accidentally connect to production FastAPI at `127.0.0.1:8000`.
For real-device LAN testing, bind development FastAPI to `0.0.0.0`, allow the Vite LAN origin in both
`CORS_ORIGINS` and `AUTH_TRUSTED_ORIGINS`, and use the development frontend URL on the device. The development React
client sends resumable upload chunks directly to port `18000`; other API requests continue to use the Vite proxy.

`family-hub-database.service` waits for Docker startup and a successful Compose health check. Backend and database-related
maintenance units must declare this service in `Requires` and `After`; they must not depend on an OS-provided
`postgresql.service` that may not exist. The [`production-runbook.md`](./production-runbook.md) is the source of truth for
construction and cutover procedures.

Uvicorn is managed by a service definition under `deploy/systemd/`. Only the production database service is a backend
startup requirement. The backend remains available for authentication, chore, shopping, groups, and other database-backed
features when the photo HDD is unavailable; photo operations that need the HDD return `503` or an equivalent unavailable
status.

Application logs are written to stderr with an ISO-like timestamp, level, logger name, and request ID. The systemd backend
unit collects them in the journal; use `journalctl -u family-hub-backend.service` for application and request logs. Set
`APP_LOG_LEVEL` in the host environment file when a different application log level is needed. Request paths exclude query
strings so search text and other user-entered values are not copied into application logs.

Resumable chunk diagnostics use a client-generated upload attempt ID to correlate browser console entries with backend
request-body reception, durable `.part` synchronization, offset changes, and response status. The browser logs entries with
the `[photo-upload]` prefix and can read the backend `X-Request-ID` header for direct cross-origin development uploads.
Compare `attemptId` in the browser with `attempt_id` in the backend log. An advanced server offset followed by a client
timeout and a `409` retry at the old offset confirms that the server stored the chunk but the response did not reach the
client. These diagnostics intentionally exclude filenames, media contents, cookies, CSRF tokens, and credentials.

Successful resumable chunk responses use `200 OK` with a short, explicitly sized body. After reading the status and
`Upload-Offset` header, the browser aborts that request's response stream without waiting for the body. This avoids iPhone
Safari queueing the seventh request after retaining six cross-origin responses. Preserve `Upload-Offset` through development
and production proxies because it remains the authoritative next position.

This failure was confirmed during LAN development with a 50.5 MiB MOV: six 8 MiB `PATCH` requests reached FastAPI and were
persisted, while the seventh request never reached the backend. Waiting for the empty or short response body could instead
stall the first request. Capturing the response headers and then aborting only that request's response stream allowed the
seventh chunk, item completion, and thumbnail retrieval to succeed without a retry.

The development frontend uses a five-second upload timeout as a temporary diagnostic value. Production builds support the
`VITE_UPLOAD_REQUEST_TIMEOUT_MS` build-time variable and use a 30-second fallback when it is absent or invalid. Before
production acceptance, set the variable from real iPhone Wi-Fi and mobile-network measurements rather than relying on the
fallback. The response-stream abort was added for the development cross-origin direct route and must either be limited to
that route or verified not to produce client-closed responses through Cloudflare.

For example, pass the measured value while building the release:

```bash
VITE_UPLOAD_REQUEST_TIMEOUT_MS=30000 npm run build
```

The value must be an integer from 1,000 through 300,000 milliseconds. Keep the production value in the host-side release
build environment; do not put host-specific values or secrets in the repository.

```bash
uv run --locked python -m uvicorn app.main:app \
  --host 127.0.0.1 \
  --port 8000 \
  --proxy-headers \
  --forwarded-allow-ips=127.0.0.1
```

Do not use `--forwarded-allow-ips="*"`.

## Caddy responsibilities

- Serve `frontend/dist/` as static content.
- Fall back to `index.html` for frontend routes without a matching static file.
- Forward `/api/*` to FastAPI without removing `/api` from the path.
- Block the exact loopback-only readiness path `/api/v1/readiness` with `404` and never forward it through the public route.
- Serve no local files outside `frontend/dist/`.
- Do not use the Vite development or preview server in production.
- Do not write cookies, credentials, invitation tokens, or other secrets to access logs.

Hash-named `/assets/*` files use `public, max-age=31536000, immutable`. `sw.js` returns `Cache-Control: no-store` and
`Cloudflare-CDN-Cache-Control: no-store`. Other static files and `index.html` returned by SPA fallback use
`no-cache, must-revalidate`, allowing every release to be revalidated. The concrete configuration is in `deploy/Caddyfile`.

## Client IP forwarding

The original client IP is forwarded to distinguish login attempts:

```text
Cloudflare Edge
  └── CF-Connecting-IP
        ↓
cloudflared (loopback connection on the same host)
        ↓
Caddy (only the loopback proxy immediately before it is trusted)
  └── X-Forwarded-For
        ↓
Uvicorn (only forwarded headers from 127.0.0.1 are trusted)
```

Cloudflare sends the client IP to the origin in `CF-Connecting-IP`. Caddy explicitly configures `trusted_proxies` and
`client_ip_headers`, limiting trust to `127.0.0.1/8` and `::1` while `cloudflared` runs on the same host. Do not trust the
whole LAN or `private_ranges`. Keeping Caddy on loopback limits header-spoofing paths.

After configuration, verify the client IP recorded by Caddy and FastAPI, the login-rate-limit key, and behavior when
spoofed forwarding headers are sent from a real device.

## Authentication and origin

- Use Family Hub server-side sessions, CSRF validation, and group authorization as the primary authentication system.
- Do not add Cloudflare Access in the initial configuration.
- Production cookies use `__Host-photo_session`, `Secure`, `HttpOnly`, `SameSite=Lax`, and `Path=/`.
- Set `AUTH_TRUSTED_ORIGINS` and `CORS_ORIGINS` to the public production origin only.
- Do not mix development `http://localhost:15173` values into production settings.

For a public URL such as `https://family.example.com`, configure the origin without a trailing slash:

```dotenv
APP_ENV=production
AUTH_TRUSTED_ORIGINS=https://family.example.com
CORS_ORIGINS=https://family.example.com
AUTH_COOKIE_SECURE=true
```

Do not record the real hostname, credentials, or Tunnel token in the repository.

## Cache policy

Do not store API responses whose contents depend on authentication or authorization at the Cloudflare Edge.

- Set a Cloudflare Cache Rule for `URI Path starts with /api/` to `Bypass cache`.
- Set Cloudflare Browser Cache TTL to `Respect Existing Headers` so it does not override Caddy's purpose-specific headers.
- Bypass `/sw.js` in Cache Rules as well, so Service Worker update checks are not delayed.
- Return `Cache-Control: private, no-store` for authenticated binaries such as originals, thumbnails, and ZIP exports.
- Apply `private, no-store` consistently to dynamic authentication, group, album, chore, and shopping APIs.
- Hashed `/assets/*` files may use `public, max-age=31536000, immutable`.
- Do not long-cache `index.html`.

Because Cloudflare Cache Rules can override origin headers, an explicit API bypass is a production acceptance requirement.

## Uploads

Cloudflare-proxied requests have plan-specific body-size limits; Free and Pro plans allow 100 MB. Since 100 MiB is
104,857,600 bytes, do not treat the values as interchangeable.

- The production React client always uses the batch chunk-upload API.
- Keep each chunk comfortably below Cloudflare's request limit.
- The batch chunk-upload API is the only supported photo upload route; do not rely on a single-request upload endpoint.
- Recheck the current official limit and the actual `413` boundary after changing the production plan or Cloudflare settings.

Treat `PHOTO_MAX_UPLOAD_BYTES` as the whole-file application limit and `PHOTO_UPLOAD_CHUNK_BYTES` as the per-request
chunk limit.

The backend host must provide `ffprobe` and `ffmpeg` on `PATH` for MP4, QuickTime MOV, and M4V validation and thumbnail
generation. Video originals are stored without conversion; playback uses the browser's native support for the returned MIME
type.

## Web Push outbound communication

Accept only HTTPS subscription endpoints whose provider hosts are listed in `PUSH_ALLOWED_ENDPOINT_HOSTS`. The default
list covers major Safari, Chromium, and Firefox providers. If a real device requires a new host, an operator must verify
the provider before adding it to the production `backend.env`. Do not allow arbitrary hosts, IP addresses, loopback, or
LAN endpoints. Limit subscriptions per user with `PUSH_MAX_SUBSCRIPTIONS_PER_USER`, defaulting to 10.

Only the notification worker makes outbound HTTPS connections to providers. The subscription API must not make synchronous
requests to arbitrary URLs, and the inbound exposure of Caddy, Uvicorn, PostgreSQL, and photo storage must not change.

See [`web-push.md`](./web-push.md) for notification triggers, the relationship between subscriptions and login sessions,
and retry behavior. Keep notification timers disabled until VAPID configuration and iPhone validation are complete. Record
the verification and current timer state in the host operational record.

## Dead-man monitoring for maintenance jobs

The systemd units for database backup, photo integrity, trash purge, notification delivery, chore-due notifications,
and secondary-storage backup can send start, success, and failure pings to any Healthchecks-compatible URL. Configure each
job's `MONITORING_PING_URL_*` in the production `backend.env`; never store actual URLs or check identifiers in the
repository. Require HTTPS, allowing loopback HTTP only for a self-hosted monitor on the same host. Unconfigured jobs do
not send pings and continue their maintenance work. Ping failures must not fail the main job; record only the ping type in
the journal and exit with status 0.

## ZIP exports

FastAPI reads originals sequentially without creating a complete temporary ZIP. Cloudflare Tunnel may buffer responses other
than `Content-Type: text/event-stream`, so the same streaming and memory characteristics have not been verified through
Cloudflare. An origin that does not respond for a period may also receive a `524` response.

Before production, measure the following with an export of approximately 100 photos and several gigabytes:

- Time until download starts
- Whether the download completes in iPhone Safari
- Memory usage of `cloudflared`, Caddy, and FastAPI
- Cloudflare `524` responses or interrupted connections
- Whether failed exports leave unwanted temporary files on the server or browser

If problems occur, lower the external export limit or move large backups to a LAN-only administration path or management
command. Until measurement is complete, do not claim that multi-gigabyte ZIP exports through Cloudflare are supported.

## Home LAN access

The initial operation uses the same public URL, such as `https://family.example.com`, on home Wi-Fi and away from home. This
keeps Secure Cookie and origin configuration to one path.

This path is unavailable when the Internet or Cloudflare is unavailable. If independent LAN access becomes necessary,
design local HTTPS, certificates, name resolution, cookies, origins, and Caddy trust boundaries separately. Do not use
plain `http://192.168.x.x:8080` as an alternative path for production cookies.

## Production acceptance checklist

- The Named Tunnel reconnects automatically after reboot and does not depend on a Quick Tunnel.
- The router has no inbound port forwards, and Caddy and Uvicorn listen only on loopback.
- Protected APIs and photo originals cannot be fetched while unauthenticated.
- Loopback `/api/v1/readiness` reports both database and photo-storage status, while the Caddy route returns `404`. Photo
  storage being unavailable must not prevent the backend process or non-photo APIs from running.
- `AUTH_TRUSTED_ORIGINS`, CORS, and cookie attributes match the production origin.
- Spoofed forwarding headers sent directly are not accepted as the client IP.
- `/api/*` bypasses Cloudflare cache and authenticated binaries return `private, no-store`.
- Near-limit photos and supported videos can be saved through React chunked upload.
- ZIP export measurements are complete or operational limits have been decided.
- PostgreSQL, the internal photo-storage HDD, and the disconnected external backup HDD cannot be reached directly from
  Cloudflare, the LAN, or clients.
- Backup and restore procedures have been verified using separate media.
- Dead-man monitoring detects start, success, and intentional failure for every enabled maintenance timer.

The repository smoke checks can be run against the public origin after deployment:

```bash
PUBLIC_BASE_URL=https://family.example.com make production-smoke
```

This checks public health, the externally blocked readiness route, unauthenticated API responses, SPA and Service Worker
availability, and the expected cache-control headers. It does not replace the authenticated live E2E test or real-device
upload and ZIP measurements.

## References

- [Cloudflare Tunnel: Set up](https://developers.cloudflare.com/tunnel/setup/)
- [Cloudflare Tunnel: Routing](https://developers.cloudflare.com/tunnel/routing/)
- [Cloudflare HTTP headers](https://developers.cloudflare.com/fundamentals/reference/http-headers/)
- [Cloudflare Cache Rules settings](https://developers.cloudflare.com/cache/how-to/cache-rules/settings/)
- [Cloudflare Edge and Browser Cache TTL](https://developers.cloudflare.com/cache/how-to/edge-browser-cache-ttl/)
- [Cloudflare default cache behavior and upload limits](https://developers.cloudflare.com/cache/concepts/default-cache-behavior/)
- [Cloudflare Tunnel troubleshooting](https://developers.cloudflare.com/cloudflare-one/troubleshooting/tunnel/)
- [Cloudflare error 524](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-524/)
- [Caddy global server options](https://caddyserver.com/docs/caddyfile/options)
- [FastAPI: Behind a Proxy](https://fastapi.tiangolo.com/advanced/behind-a-proxy/)

日本語版: [deployment.ja.md](./deployment.ja.md)
