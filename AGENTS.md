# AGENTS.md

## Project structure

* `backend/`: FastAPI backend using Python 3.13.
* `backend/app/`: Backend application code.
* `backend/tests/`: Backend tests.
* `frontend/`: React and TypeScript frontend built with Vite.

Keep backend and frontend independently manageable. Run Python commands from
`backend/` and Node.js commands from `frontend/` unless otherwise specified.

## Product documentation

Before product or architecture decisions, read `docs/product-brief.md`.

Also read:

* `docs/backend-design.md` for backend architecture or implementation decisions.
* `docs/deployment.md` for production hosting, proxy, cache, or network decisions.

Treat `docs/proposals/` as unimplemented options, not current contracts.

Update the relevant English documentation in the same change when product scope,
behavior, API contracts, setup, architecture, storage policy, safety
requirements, implementation status, or major assumptions change.

After source-code changes, review `README.md` and the relevant English files
under `docs/` for consistency. Update them when needed; otherwise report that the
review was completed and no update was required.

All documentation instructions in this file exclude Japanese documentation and
files ending in `.ja.md`.

### Documentation language policy

* English documentation is the sole source of truth for development, product,
  architecture, implementation, and operations.
* Files ending in `.ja.md` are user-managed, public-facing Japanese
  translations and are outside the scope of agent work.
* Treat `.ja.md` files as protected user-managed content. Never read, open,
  print, search, inspect, parse, summarize, compare, validate, edit, create,
  copy, diff, delete, rename, move, format, or otherwise process their contents.
* Exclude `.ja.md` files from repository-wide searches, documentation reviews,
  consistency checks, bulk edits, formatting, translation, and generated-file
  operations.
* Never use `.ja.md` files as context or as input for product, architecture,
  implementation, operational, or documentation decisions.
* Changes to code or English documentation do not require reviewing or updating
  corresponding `.ja.md` files.
* Do not use Japanese-only documentation as a source. If no English counterpart
  exists, report that the required English documentation is unavailable rather
  than opening the Japanese file.
* If a task requires reading or changing a `.ja.md` file, stop and ask the user
  to perform that step manually.

## Backend

Install locked development dependencies from the repository root:

```bash
make backend-sync
```

Keep runtime dependencies in `requirements.txt`, development-only dependencies in
`requirements-dev.txt`, and reproducible resolutions in `requirements.lock`.

Use compatible version ranges, not unrestricted versions. After changing either
requirements input file, run:

```bash
make backend-lock
```

Configure Python tools in `backend/pyproject.toml`.

### Development database

* The development database may be fully reset when that is the simplest response
  to a schema change.
* The user has granted standing approval for development database resets without
  confirmation.
* Before resetting, verify the target is the development database at
  `127.0.0.1:5432`, not production or production photo storage.
* Do not add compatibility migrations or backfills solely to preserve local
  development data unless requested.
* This approval applies only to the development database. Resetting any other
  database or deleting photo files or storage requires explicit approval.

### Python imports and side effects

* Do not import modules solely for initialization or registration side effects.
  Route decorators inside explicitly registered routers are allowed.
* Unused imports must always be safe to remove.
* Use explicit function calls for initialization and registration.
* Register FastAPI routers explicitly with `app.include_router(...)`.
* Use FastAPI lifespan handlers for startup and shutdown logic.
* Avoid `# noqa: F401`; use it only for intentional public API re-exports from
  `__init__.py` when the intent is clear.

### Linting, formatting, and tests

After editing backend Python files, run:

```bash
ruff check . --fix
ruff format .
```

This is the standard workflow. Do not use `--unsafe-fixes` unless explicitly
requested. Structure code so Ruff safe fixes, including unused-import removal, do
not alter intended behavior.

Before completing backend work, run:

```bash
ruff check .
ruff format --check .
pytest
```

Add tests under `backend/tests/`. Do not add placeholder tests solely to make
pytest collect tests. While the suite is empty, report pytest exit status 5 as
“no tests collected,” not an application failure.

Run the development server from `backend/`:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

## Frontend

Run frontend commands from `frontend/`.

Use `npm ci` for reproducible installation from the committed lockfile. Use
`npm install` only when intentionally adding or updating dependencies.

Common commands:

```bash
npm ci
npm run format
npm run lint
npm run test:run
npm run build
npm run dev
```

Use React with TypeScript and follow the existing Vite and ESLint configuration.
Format frontend files with Prettier.

After frontend changes, run the relevant formatting, linting, testing, and build
commands. Before completing frontend work, verify:

```bash
npm run format:check
npm run lint
npm run test:run
npm run build
```

API response types and enums under `frontend/src/shared/api/generated/` are
generated from FastAPI's OpenAPI schema. Do not edit them directly.

After changing backend routes or Pydantic schemas, run the following from
`frontend/` and commit the result:

```bash
npm run api:generate
```

### CSS naming

* Name CSS custom properties by semantic role, such as `--color-bg-page` or
  `--color-text-primary`, rather than visual value, such as `--paper`, `--navy`,
  or `--blue`.
* Define global design tokens in `frontend/src/index.css`.
* Implement themes by overriding token values, not duplicating component styles.
* Prefix feature-specific properties with the feature name, such as `--photo-*`,
  `--album-*`, or `--group-*`.
* Do not create a custom property used only once unless it has a clear reuse or
  theming purpose.
* Use the existing BEM-style class convention: `.block`, `.block__element`, and
  `.block--modifier`.

## Environment variables

* Never commit `.env` files.
* Document required variables in `.env.example`.
* Do not put secrets or environment-specific credentials in source files.
* Keep backend environment files under `backend/`.
* Treat `.env` files as user-managed secrets. Never read, print, search, edit,
  copy, diff, delete, or otherwise inspect their contents.
* Do not run commands that expose environment variables, including `env`,
  `printenv`, or unrestricted environment dumps.
* Use `.env.example` only to understand configuration structure.
* If a task requires a secret value or an `.env` change, stop and ask the user to
  perform that step manually.

## Branch workflow

* Use `dev` by default for implementation, documentation, commits, and pushes.
* Check the current branch before starting and again before committing or
  pushing.
* Never commit or push directly to `main`. If currently on `main`, switch to
  `dev` before changing files.
* Treat `main` as the confirmed stable branch.
* Merge `dev` into `main` only after relevant automated checks and manual
  operation checks pass.
* Do not merge or push to `main` unless the user explicitly requests a stable
  release.
* When asked only to commit or push without a branch name, use `dev`.

## Commit messages

Use Conventional Commits:

```text
<type>: <summary>
```

Common types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `build`, and
`ci`.

Use a lowercase type and a concise English imperative summary without a trailing
period. Keep each commit focused on one related change.

## Development guidelines

* Target approximately 120 characters per line in backend and frontend code.
  Treat formatter widths as targets, not strict limits, when URLs, generated
  content, or readability make wrapping impractical.
* Keep changes small and focused.
* Avoid unnecessary abstractions while the project is in its early stages.
* Prefer explicit behavior over implicit registration or hidden initialization.
* Preserve existing user changes.
* Do not edit generated or dependency artifacts such as `frontend/dist/`, Python
  cache files, or dependency directories.
* Run checks proportional to the files changed and report any checks that could
  not be run.
