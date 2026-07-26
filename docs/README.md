# Documentation Guide

Family Hub documentation separates current contracts from unimplemented proposals. English files are the canonical versions;
Japanese translations are kept beside them with a `.ja.md` suffix.

## Language policy

- English is the source of truth whenever an English version exists.
- Japanese files are translations and must not introduce independent decisions.
- Use a `.ja.md` suffix for Japanese translations.
- When an English document changes, update the Japanese translation when practical.
- If a Japanese translation is temporarily outdated, add an `Out of date` notice and link to the English document.
- Existing Japanese-only documents remain current until their English counterparts are created.

## Current documents

- [`product-brief.md`](./product-brief.md) — [日本語版](./product-brief.ja.md): Product goals, scope, safety requirements, and roadmap
- [`backend-design.md`](./backend-design.md) — [日本語版](./backend-design.ja.md): FastAPI responsibilities, APIs, storage, authentication, and testing
- [`database-design.md`](./database-design.md) — [日本語版](./database-design.ja.md): PostgreSQL schema, constraints, indexes, and migrations
- [`deployment.md`](./deployment.md) — [日本語版](./deployment.ja.md): Cloudflare Tunnel, Caddy, Uvicorn, and acceptance checks
- [`production-runbook.md`](./production-runbook.md) — [日本語版](./production-runbook.ja.md): Production construction, release, and reset procedures
- [`web-push.md`](./web-push.md) — [日本語版](./web-push.ja.md): Web Push implementation and validation status

When implementation or operations change, update every affected document in the same change.

## Unimplemented proposals

- [`proposals/person-detection.md`](./proposals/person-detection.md) — [日本語版](./proposals/person-detection.ja.md): Provisional person-detection proposal

The contents of `proposals/` are not current implementation contracts. When work is approved, revalidate the requirements
and design, then move the adopted decisions into the relevant current documents.
